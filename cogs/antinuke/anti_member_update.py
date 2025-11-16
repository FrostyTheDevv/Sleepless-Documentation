import discord
from discord.ext import commands
import aiosqlite
from utils.action_tracker import ActionTracker
from utils.whitelist_helper import is_whitelisted
from utils.escalation import get_escalation_level, apply_escalated_punishment

class AntiMemberUpdate(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tracker = ActionTracker()
        
    async def cog_load(self):
        await self.tracker.initialize()
    
    async def cog_unload(self):
        await self.tracker.close()

    async def fetch_audit_logs(self, guild, action, target_id):
        if not guild.me.guild_permissions.view_audit_log:
            return None
        try:
            async for entry in guild.audit_logs(action=action, limit=10):
                if entry.target.id == target_id:
                    return entry
        except Exception:
            pass
        return None

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.roles == after.roles:
            return  # Only track role changes
        
        guild = after.guild
        
        async with aiosqlite.connect('db/anti.db') as db:
            cursor = await db.execute(
                "SELECT status FROM antinuke WHERE guild_id = ?",
                (guild.id,)
            )
            status = await cursor.fetchone()
            if not status or not status[0]:
                return
        
        log_entry = await self.fetch_audit_logs(guild, discord.AuditLogAction.member_role_update, after.id)
        if not log_entry:
            return
        
        executor = log_entry.user
        
        if executor.id in {guild.owner_id, self.bot.user.id}:
            return
        
        executor_member = guild.get_member(executor.id)
        if not executor_member:
            return
        
        if await is_whitelisted(guild.id, executor_member, 'memup'):
            return
        
        # Check for dangerous permission escalation
        dangerous_perm_names = [
            'administrator',
            'ban_members',
            'kick_members',
            'manage_guild',
            'manage_roles'
        ]
        
        old_perms = before.guild_permissions
        new_perms = after.guild_permissions
        
        escalation = False
        for perm_name in dangerous_perm_names:
            if not getattr(old_perms, perm_name) and getattr(new_perms, perm_name):
                escalation = True
                break
        
        await self.tracker.track_action(
            guild_id=guild.id,
            user_id=executor.id,
            action_type="member_role_update",
            metadata={
                "target_id": after.id,
                "target_name": str(after),
                "permission_escalation": escalation,
                "reason": log_entry.reason
            }
        )
        
        exceeded, action_count, config = await self.tracker.check_threshold(
            guild_id=guild.id,
            user_id=executor.id,
            action_type="member_role_update"
        )
        
        if exceeded:
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
                    reason=f"Antinuke: {action_count} member role updates in {config.time_window}s (Level {escalation_level})"
                )
                
                # Revert role changes
                try:
                    await after.edit(roles=before.roles, reason=f"Reverting role changes by {executor} (threshold breach)")
                except:
                    pass
                
                await self.tracker.log_punishment(
                    guild_id=guild.id,
                    user_id=executor.id,
                    action_type="member_role_update",
                    punishment_type=config.punishment_type,
                    actions_reverted=1,
                    reason=f"Updated member roles {action_count} times in {config.time_window} seconds",
                    escalation_level=escalation_level
                )
            except Exception as e:
                print(f"Error applying punishment in anti_member_update: {e}")

async def setup(bot):
    await bot.add_cog(AntiMemberUpdate(bot))
