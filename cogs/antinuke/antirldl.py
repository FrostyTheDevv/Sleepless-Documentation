import discord
from discord.ext import commands
import aiosqlite
import asyncio
from utils.action_tracker import ActionTracker
from utils.whitelist_helper import is_whitelisted
from utils.escalation import get_escalation_level, apply_escalated_punishment

class AntiRoleDelete(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tracker = ActionTracker()
        
    async def cog_load(self):
        await self.tracker.initialize()
    
    async def cog_unload(self):
        await self.tracker.close()

    async def is_blacklisted_guild(self, guild_id):
        async with aiosqlite.connect('db/block.db') as block_db:
            cursor = await block_db.execute("SELECT 1 FROM guild_blacklist WHERE guild_id = ?", (str(guild_id),))
            return await cursor.fetchone() is not None

    async def fetch_audit_logs(self, guild, action):
        if not guild.me.guild_permissions.view_audit_log:
            return []
        try:
            entries = []
            async for entry in guild.audit_logs(action=action, limit=10):
                entries.append(entry)
            return entries
        except Exception:
            return []

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        guild = role.guild
        if await self.is_blacklisted_guild(guild.id):
            return
        async with aiosqlite.connect('db/anti.db') as db:
            cursor = await db.execute("SELECT status FROM antinuke WHERE guild_id = ?", (guild.id,))
            status = await cursor.fetchone()
            if not status or not status[0]:
                return
        audit_entries = await self.fetch_audit_logs(guild, discord.AuditLogAction.role_delete)
        if not audit_entries:
            return
        delete_entry = None
        for entry in audit_entries:
            if entry.target.id == role.id:
                delete_entry = entry
                break
        if not delete_entry:
            return
        executor = delete_entry.user
        if executor.id in {guild.owner_id, self.bot.user.id}:
            return
        executor_member = guild.get_member(executor.id)
        if not executor_member:
            return
        if await is_whitelisted(guild.id, executor_member, 'rldl'):
            return
        await self.tracker.track_action(guild_id=guild.id, user_id=executor.id, action_type="role_delete", metadata={"role_id": role.id, "role_name": role.name, "role_permissions": role.permissions.value, "role_color": str(role.color), "role_hoist": role.hoist, "role_mentionable": role.mentionable})
        exceeded, action_count, config = await self.tracker.check_threshold(guild_id=guild.id, user_id=executor.id, action_type="role_delete")
        if exceeded:
            await self.apply_punishment(guild, executor, role, action_count, config)

    async def apply_punishment(self, guild, executor, last_role, action_count, config):
        try:
            # Get escalation level based on offense history

            escalation_level = await get_escalation_level(guild.id, executor.id)

            # If config punishment_type is "escalation", get the actual punishment for this level
            if config.punishment_type == "escalation":
                from utils.escalation import ESCALATION_LEVELS
                actual_punishment = ESCALATION_LEVELS[escalation_level]["punishment"]
                duration = ESCALATION_LEVELS[escalation_level]["duration"]
            else:
                actual_punishment = config.punishment_type
                duration = None


            

            # Apply escalated punishment

            punishment_applied = await apply_escalated_punishment(

                guild=guild,

                member=executor,

                punishment_type=actual_punishment,

                escalation_level=escalation_level,

                duration=duration,

                reason=f"Antinuke: {action_count} role_deletes in {config.time_window}s (Level {escalation_level})"

            )
            recent_actions = await self.tracker.get_recent_actions(guild.id, executor.id, "role_delete", config.time_window)
            recreated = 0
            for action in recent_actions:
                if action.reverted:
                    continue
                try:
                    await guild.create_role(name=action.metadata.get("role_name", "Deleted Role"), permissions=discord.Permissions(action.metadata.get("role_permissions", 0)), color=discord.Color(int(action.metadata.get("role_color", "#000000").replace("#", ""), 16)) if "#" in action.metadata.get("role_color", "") else discord.Color.default(), hoist=action.metadata.get("role_hoist", False), mentionable=action.metadata.get("role_mentionable", False), reason=f"Recreating role deleted by {executor}")
                    recreated += 1
                    await asyncio.sleep(0.5)
                except Exception as e:
                    print(f"Failed to recreate role: {e}")
            await self.tracker.mark_actions_reverted(guild.id, executor.id, "role_delete")
            await self.tracker.log_punishment(guild.id, executor.id, "role_delete", config.punishment_type, recreated, f"Deleted {action_count} roles")
        except Exception as e:
            print(f"Error: {e}")

async def setup(bot):
    await bot.add_cog(AntiRoleDelete(bot))
