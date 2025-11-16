import discord
from discord.ext import commands
import aiosqlite
import asyncio
from utils.action_tracker import ActionTracker
from utils.whitelist_helper import is_whitelisted
from utils.escalation import get_escalation_level, apply_escalated_punishment

class AntiChannelUpdate(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tracker = ActionTracker()
        
    async def cog_load(self):
        await self.tracker.initialize()
    
    async def cog_unload(self):
        await self.tracker.close()

    async def is_blacklisted_guild(self, guild_id):
        async with aiosqlite.connect('db/block.db') as block_db:
            cursor = await block_db.execute(
                "SELECT 1 FROM guild_blacklist WHERE guild_id = ?", 
                (str(guild_id),)
            )
            return await cursor.fetchone() is not None

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
    async def on_guild_channel_update(self, before, after):
        guild = before.guild
        
        if await self.is_blacklisted_guild(guild.id):
            return
        
        async with aiosqlite.connect('db/anti.db') as db:
            cursor = await db.execute(
                "SELECT status FROM antinuke WHERE guild_id = ?",
                (guild.id,)
            )
            status = await cursor.fetchone()
            if not status or not status[0]:
                return
        
        log_entry = await self.fetch_audit_logs(guild, discord.AuditLogAction.channel_update, after.id)
        if not log_entry:
            return
        
        executor = log_entry.user
        
        if executor.id in {guild.owner_id, self.bot.user.id}:
            return
        
        executor_member = guild.get_member(executor.id)
        if not executor_member:
            return
        
        if await is_whitelisted(guild.id, executor_member, 'chup'):
            return
        
        await self.tracker.track_action(
            guild_id=guild.id,
            user_id=executor.id,
            action_type="channel_update",
            metadata={
                "channel_id": after.id,
                "channel_name": after.name,
                "old_name": before.name,
                "reason": log_entry.reason
            }
        )
        
        exceeded, action_count, config = await self.tracker.check_threshold(
            guild_id=guild.id,
            user_id=executor.id,
            action_type="channel_update"
        )
        
        if exceeded:
            await self.apply_punishment(guild, executor, before, after, action_count, config)

    async def apply_punishment(self, guild, executor, before, after, action_count, config):
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
                reason=f"Antinuke: {action_count} channel_updates in {config.time_window}s (Level {escalation_level})"
            )
            
            recent_actions = await self.tracker.get_recent_actions(
                guild_id=guild.id,
                user_id=executor.id,
                action_type="channel_update",
                time_window=config.time_window
            )
            
            reverted_count = 0
            for action in recent_actions:
                if action.reverted:
                    continue
                
                try:
                    target_channel = guild.get_channel(action.metadata.get("channel_id"))
                    if target_channel:
                        await target_channel.edit(
                            name=action.metadata.get("old_name", target_channel.name),
                            reason=f"Reverting changes by {executor} (threshold breach)"
                        )
                        reverted_count += 1
                        await asyncio.sleep(0.5)
                except Exception as e:
                    print(f"Failed to revert channel update: {e}")
            
            await self.tracker.mark_actions_reverted(
                guild_id=guild.id,
                user_id=executor.id,
                action_type="channel_update"
            )
            
            await self.tracker.log_punishment(
                guild_id=guild.id,
                user_id=executor.id,
                action_type="channel_update",
                punishment_type=config.punishment_type,
                actions_reverted=reverted_count,
                reason=f"Updated {action_count} channels in {config.time_window} seconds",
                escalation_level=escalation_level
            )
            
        except Exception as e:
            print(f"Error applying punishment in antichup: {e}")

async def setup(bot):
    await bot.add_cog(AntiChannelUpdate(bot))
