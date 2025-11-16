import discord
from discord.ext import commands
import aiosqlite
import asyncio
from utils.action_tracker import ActionTracker
from utils.whitelist_helper import is_whitelisted
from utils.escalation import get_escalation_level, apply_escalated_punishment
from utils.antinuke_notifier import AntinukeNotifier

class AntiKick(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tracker = ActionTracker()
        
    async def cog_load(self):
        """Initialize the action tracker when cog loads"""
        await self.tracker.initialize()
    
    async def cog_unload(self):
        """Clean up when cog unloads"""
        await self.tracker.close()

    async def is_blacklisted_guild(self, guild_id):
        """Check if guild is blacklisted"""
        async with aiosqlite.connect('db/block.db') as block_db:
            cursor = await block_db.execute(
                "SELECT 1 FROM guild_blacklist WHERE guild_id = ?", 
                (str(guild_id),)
            )
            return await cursor.fetchone() is not None

    async def fetch_audit_logs(self, guild, action):
        """Fetch recent audit log entries for specified action"""
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
    async def on_member_remove(self, member):
        """Monitor member kicks and enforce thresholds"""
        guild = member.guild
        
        # Skip if guild is blacklisted
        if await self.is_blacklisted_guild(guild.id):
            return
        
        # Check if antinuke is enabled
        async with aiosqlite.connect('db/anti.db') as db:
            cursor = await db.execute(
                "SELECT status FROM antinuke WHERE guild_id = ?",
                (guild.id,)
            )
            status = await cursor.fetchone()
            if not status or not status[0]:
                return
        
        # Fetch audit logs to find who kicked
        audit_entries = await self.fetch_audit_logs(guild, discord.AuditLogAction.kick)
        if not audit_entries:
            return
        
        # Find the kick entry for this member
        kick_entry = None
        for entry in audit_entries:
            if entry.target.id == member.id:
                kick_entry = entry
                break
        
        if not kick_entry:
            return
        
        executor = kick_entry.user
        
        # Always allow guild owner and bot
        if executor.id in {guild.owner_id, self.bot.user.id}:
            return
        
        # Get executor as Member for role-based whitelist checking
        executor_member = guild.get_member(executor.id)
        if not executor_member:
            return
        
        # Check whitelist (both user and role-based)
        if await is_whitelisted(guild.id, executor_member, 'kick'):
            return
        
        # Track the kick action
        await self.tracker.track_action(
            guild_id=guild.id,
            user_id=executor.id,
            action_type="kick",
            metadata={
                "target_id": member.id,
                "target_name": str(member),
                "reason": kick_entry.reason
            }
        )
        
        # Check if threshold exceeded
        exceeded, action_count, config = await self.tracker.check_threshold(
            guild_id=guild.id,
            user_id=executor.id,
            action_type="kick"
        )
        
        if exceeded:
            await self.apply_punishment(guild, executor, member, action_count, config)

    async def apply_punishment(self, guild, executor, last_kicked_member, action_count, config):
        """Apply punishment and revert recent kicks"""
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
                reason=f"Antinuke: {action_count} kicks in {config.time_window}s (Level {escalation_level})"
            )
            
            # Get all recent kick actions by this user
            recent_actions = await self.tracker.get_recent_actions(
                guild_id=guild.id,
                user_id=executor.id,
                action_type="kick",
                time_window=config.time_window
            )
            
            # Note: We cannot easily re-invite kicked members automatically
            # This would require stored invite links or bot creating new invites
            # Logging this information for manual review
            
            # Mark actions as reverted in the database
            await self.tracker.mark_actions_reverted(
                guild_id=guild.id,
                user_id=executor.id,
                action_type="kick"
            )
            
            # Log the punishment with escalation level
            await self.tracker.log_punishment(
                guild_id=guild.id,
                user_id=executor.id,
                action_type="kick",
                punishment_type=config.punishment_type,
                actions_reverted=len(recent_actions),
                reason=f"Kicked {action_count} members in {config.time_window} seconds",
                escalation_level=escalation_level
            )
            
            # Send notification to server owner
            try:
                await AntinukeNotifier.send_notification(
                    guild=guild,
                    violator=executor,
                    action_type="kick",
                    action_count=action_count,
                    punishment_type=actual_punishment,
                    reason=f"Kicked {action_count} members in {config.time_window} seconds",
                    escalation_level=escalation_level,
                    bot=self.bot
                )
            except Exception as notify_error:
                print(f"Failed to send notification: {notify_error}")
            
        except Exception as e:
            print(f"Error applying punishment in antikick: {e}")

async def setup(bot):
    await bot.add_cog(AntiKick(bot))