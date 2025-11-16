import discord
from discord.ext import commands
import aiosqlite
import asyncio
from utils.action_tracker import ActionTracker
from utils.whitelist_helper import is_whitelisted
from utils.escalation import get_escalation_level, apply_escalated_punishment
from utils.antinuke_notifier import AntinukeNotifier
from utils.backup_manager import BackupManager

class AntiRoleCreate(commands.Cog):
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
    async def on_guild_role_create(self, role):
        guild = role.guild
        
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
        
        audit_entries = await self.fetch_audit_logs(guild, discord.AuditLogAction.role_create)
        if not audit_entries:
            return
        
        create_entry = None
        for entry in audit_entries:
            if entry.target.id == role.id:
                create_entry = entry
                break
        
        if not create_entry:
            return
        
        executor = create_entry.user
        
        if executor.id in {guild.owner_id, self.bot.user.id}:
            return
        
        executor_member = guild.get_member(executor.id)
        if not executor_member:
            return
        
        if await is_whitelisted(guild.id, executor_member, 'rlcr'):
            return
        
        await self.tracker.track_action(
            guild_id=guild.id,
            user_id=executor.id,
            action_type="role_create",
            metadata={
                "role_id": role.id,
                "role_name": role.name,
                "role_permissions": role.permissions.value,
                "role_color": str(role.color),
                "reason": create_entry.reason
            }
        )
        
        # Check for suspicious patterns AND thresholds
        should_punish, reason, action_count, config = await self.tracker.check_pattern_and_threshold(
            guild_id=guild.id,
            user_id=executor.id,
            action_type="role_create"
        )
        
        if should_punish:
            await self.apply_punishment(guild, executor, role, action_count, config, reason)

    async def apply_punishment(self, guild, executor, last_created_role, action_count, config, trigger_reason=""):
        try:
            # Create backup before applying punishment
            try:
                await BackupManager.create_role_backup(
                    guild=guild,
                    roles=guild.roles,
                    reason=f"Auto-backup before antinuke action (role_create by {executor})",
                    created_by=guild.me
                )
            except Exception as backup_error:
                print(f"Backup failed (non-critical): {backup_error}")
            
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

            # Build reason with pattern info if detected
            base_reason = trigger_reason if trigger_reason else f"{action_count} role_creates in {config.time_window}s"
            full_reason = f"Antinuke: {base_reason} (Level {escalation_level})"
            
            # Apply escalated punishment
            punishment_applied = await apply_escalated_punishment(
                guild=guild,
                member=executor,
                punishment_type=actual_punishment,
                escalation_level=escalation_level,
                duration=duration,
                reason=full_reason
            )
            
            recent_actions = await self.tracker.get_recent_actions(
                guild_id=guild.id,
                user_id=executor.id,
                action_type="role_create",
                time_window=config.time_window
            )
            
            deleted_count = 0
            for action in recent_actions:
                if action.reverted:
                    continue
                
                try:
                    target_role = guild.get_role(action.metadata.get("role_id"))
                    if target_role:
                        await target_role.delete(reason=f"Role created by {executor} (threshold breach)")
                        deleted_count += 1
                        await asyncio.sleep(0.5)
                except Exception as e:
                    print(f"Failed to delete role: {e}")
            
            await self.tracker.mark_actions_reverted(
                guild_id=guild.id,
                user_id=executor.id,
                action_type="role_create"
            )
            
            await self.tracker.log_punishment(
                guild_id=guild.id,
                user_id=executor.id,
                action_type="role_create",
                punishment_type=config.punishment_type,
                actions_reverted=deleted_count,
                reason=f"Created {action_count} roles in {config.time_window} seconds",
                escalation_level=escalation_level
            )
            
            # Send notification to server owner
            try:
                await AntinukeNotifier.send_notification(
                    guild=guild,
                    violator=executor,
                    action_type="role_create",
                    action_count=action_count,
                    punishment_type=actual_punishment,
                    reason=trigger_reason,
                    escalation_level=escalation_level,
                    bot=self.bot
                )
            except Exception as notify_error:
                print(f"Failed to send notification: {notify_error}")
            
        except Exception as e:
            print(f"Error applying punishment in antirlcr: {e}")

async def setup(bot):
    await bot.add_cog(AntiRoleCreate(bot))
