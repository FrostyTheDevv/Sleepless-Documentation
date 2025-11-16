import discord
from discord.ext import commands
import aiosqlite
import asyncio
from utils.action_tracker import ActionTracker
from utils.whitelist_helper import is_whitelisted
from utils.escalation import get_escalation_level, apply_escalated_punishment
from utils.antinuke_notifier import AntinukeNotifier
from utils.backup_manager import BackupManager

class AntiChannelDelete(commands.Cog):
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
    async def on_guild_channel_delete(self, channel):
        guild = channel.guild
        print(f"[ANTICHDL DEBUG] Channel deleted: {channel.name} in guild {guild.id}")
        
        if await self.is_blacklisted_guild(guild.id):
            print(f"[ANTICHDL DEBUG] Guild {guild.id} is blacklisted, skipping")
            return
        
        async with aiosqlite.connect('db/anti.db') as db:
            cursor = await db.execute(
                "SELECT status FROM antinuke WHERE guild_id = ?",
                (guild.id,)
            )
            status = await cursor.fetchone()
            print(f"[ANTICHDL DEBUG] Antinuke status for guild {guild.id}: {status}")
            if not status or not status[0]:
                print(f"[ANTICHDL DEBUG] Antinuke not enabled, skipping")
                return
        
        print(f"[ANTICHDL DEBUG] Fetching audit logs...")
        audit_entries = await self.fetch_audit_logs(guild, discord.AuditLogAction.channel_delete)
        if not audit_entries:
            print(f"[ANTICHDL DEBUG] No audit log entries found")
            return
        
        print(f"[ANTICHDL DEBUG] Found {len(audit_entries)} audit log entries")
        delete_entry = None
        for entry in audit_entries:
            if entry.target.id == channel.id:
                delete_entry = entry
                break
        
        if not delete_entry:
            print(f"[ANTICHDL DEBUG] No matching audit log entry for channel {channel.id}")
            return
        
        executor = delete_entry.user
        print(f"[ANTICHDL DEBUG] Executor: {executor} (ID: {executor.id})")
        
        if executor.id in {guild.owner_id, self.bot.user.id}:
            print(f"[ANTICHDL DEBUG] Executor is guild owner or bot, skipping")
            return
        
        executor_member = guild.get_member(executor.id)
        if not executor_member:
            print(f"[ANTICHDL DEBUG] Could not find executor member in guild")
            return
        
        if await is_whitelisted(guild.id, executor_member, 'chdl'):
            print(f"[ANTICHDL DEBUG] Executor is whitelisted, skipping")
            return
        
        print(f"[ANTICHDL DEBUG] Tracking action for user {executor.id}...")
        await self.tracker.track_action(
            guild_id=guild.id,
            user_id=executor.id,
            action_type="channel_delete",
            metadata={
                "channel_id": channel.id,
                "channel_name": channel.name,
                "channel_type": str(channel.type),
                "category_id": channel.category.id if channel.category else None,
                "reason": delete_entry.reason
            }
        )
        
        print(f"[ANTICHDL DEBUG] Checking threshold...")
        exceeded, action_count, config = await self.tracker.check_threshold(
            guild_id=guild.id,
            user_id=executor.id,
            action_type="channel_delete"
        )
        
        print(f"[ANTICHDL DEBUG] Threshold check result: exceeded={exceeded}, count={action_count}, config={config}")
        if exceeded:
            print(f"[ANTICHDL DEBUG] Threshold exceeded! Calling apply_punishment...")
            await self.apply_punishment(guild, executor, channel, action_count, config)
            print(f"[ANTICHDL DEBUG] apply_punishment completed")

    async def apply_punishment(self, guild, executor, last_deleted_channel, action_count, config):
        print(f"[ANTICHDL DEBUG] apply_punishment called for user {executor.id}")
        try:
            # Create backup before applying punishment
            try:
                print(f"[ANTICHDL DEBUG] Creating automatic backup...")
                await BackupManager.create_channel_backup(
                    guild=guild,
                    channels=guild.channels,
                    reason=f"Auto-backup before antinuke action (channel_delete by {executor})",
                    created_by=guild.me
                )
                print(f"[ANTICHDL DEBUG] Backup created successfully")
            except Exception as backup_error:
                print(f"[ANTICHDL DEBUG] Backup failed (non-critical): {backup_error}")
            
            # Get escalation level based on offense history
            print(f"[ANTICHDL DEBUG] Getting escalation level...")
            escalation_level = await get_escalation_level(guild.id, executor.id)
            print(f"[ANTICHDL DEBUG] Escalation level: {escalation_level}")
            
            # If config punishment_type is "escalation", get the actual punishment for this level
            if config.punishment_type == "escalation":
                from utils.escalation import ESCALATION_LEVELS
                actual_punishment = ESCALATION_LEVELS[escalation_level]["punishment"]
                duration = ESCALATION_LEVELS[escalation_level]["duration"]
                print(f"[ANTICHDL DEBUG] Escalation mode: Level {escalation_level} → {actual_punishment}")
            else:
                actual_punishment = config.punishment_type
                duration = None
                print(f"[ANTICHDL DEBUG] Direct punishment mode: {actual_punishment}")
            
            # Apply escalated punishment
            print(f"[ANTICHDL DEBUG] Applying punishment: {actual_punishment} (level {escalation_level})...")
            punishment_applied = await apply_escalated_punishment(
                guild=guild,
                member=executor,
                punishment_type=actual_punishment,
                escalation_level=escalation_level,
                duration=duration,
                reason=f"Antinuke: {action_count} channel_deletes in {config.time_window}s (Level {escalation_level})"
            )
            print(f"[ANTICHDL DEBUG] Punishment applied: {punishment_applied}")
            
            recent_actions = await self.tracker.get_recent_actions(
                guild_id=guild.id,
                user_id=executor.id,
                action_type="channel_delete",
                time_window=config.time_window
            )
            
            # Note: Cannot easily recreate channels with all permissions/settings
            # Log the deletion information for manual review
            
            await self.tracker.mark_actions_reverted(
                guild_id=guild.id,
                user_id=executor.id,
                action_type="channel_delete"
            )
            
            await self.tracker.log_punishment(
                guild_id=guild.id,
                user_id=executor.id,
                action_type="channel_delete",
                punishment_type=config.punishment_type,
                actions_reverted=0,  # Cannot automatically restore channels
                reason=f"Deleted {action_count} channels in {config.time_window} seconds",
                escalation_level=escalation_level
            )
            
            # Send notification to server owner
            try:
                await AntinukeNotifier.send_notification(
                    guild=guild,
                    violator=executor,
                    action_type="channel_delete",
                    action_count=action_count,
                    punishment_type=actual_punishment,
                    reason=f"Deleted {action_count} channels in {config.time_window} seconds",
                    escalation_level=escalation_level,
                    bot=self.bot
                )
            except Exception as notify_error:
                print(f"Failed to send notification: {notify_error}")
            
        except Exception as e:
            print(f"Error applying punishment in antichdl: {e}")

async def setup(bot):
    await bot.add_cog(AntiChannelDelete(bot))
