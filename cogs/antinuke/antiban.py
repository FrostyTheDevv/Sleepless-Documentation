# Extension loader for Discord.py
async def setup(bot):
    await bot.add_cog(AntiBan(bot))

import discord
from discord.ext import commands
import aiosqlite
import asyncio
import datetime
import pytz
from utils.antinuke_notifier import AntinukeNotifier
from utils.action_tracker import ActionTracker
from utils.whitelist_helper import is_whitelisted
from utils.escalation import get_escalation_level, apply_escalated_punishment

class AntiBan(commands.Cog):
    """Professional-grade ban protection with intelligent threshold system"""
    
    def __init__(self, bot):
        self.bot = bot
        self.action_tracker = ActionTracker()
        asyncio.create_task(self.action_tracker.initialize())

    async def fetch_audit_logs(self, guild, action, target_id):
        """Fetch recent audit log entry for an action"""
        if not guild.me.guild_permissions.ban_members:
            return None
        try:
            async for entry in guild.audit_logs(action=action, limit=1):
                if entry.target.id == target_id:
                    now = datetime.datetime.now(pytz.utc)
                    # Only consider actions from last hour
                    if (now - entry.created_at).total_seconds() >= 3600:
                        return None
                    return entry
        except Exception:
            pass
        return None

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        """Monitor ban events and apply threshold-based protection"""
        try:
            # Check if antinuke is enabled for this guild
            async with aiosqlite.connect('db/anti.db') as db:
                async with db.execute(
                    "SELECT status FROM antinuke WHERE guild_id = ?", 
                    (guild.id,)
                ) as cursor:
                    antinuke_status = await cursor.fetchone()
                    if not antinuke_status or not antinuke_status[0]:
                        return

            # Fetch audit log to find who performed the ban
            entry = await self.fetch_audit_logs(guild, discord.AuditLogAction.ban, user.id)
            if not entry:
                return

            executor = entry.user
            
            # Bypass for guild owner and bot itself
            if executor.id in {guild.owner_id, self.bot.user.id}:
                return

            # Get executor as Member object for role-based whitelist checking
            executor_member = guild.get_member(executor.id)
            if not executor_member:
                return  # Executor left the guild

            # Check whitelist (both user and role-based)
            if await is_whitelisted(guild.id, executor_member, 'ban'):
                return

            # Track this action
            await self.action_tracker.track_action(
                guild_id=guild.id,
                user_id=executor.id,
                action_type="ban",
                metadata={
                    "target_id": user.id,
                    "target_name": str(user),
                    "reason": entry.reason or "No reason provided"
                }
            )

            # Check if threshold has been exceeded
            threshold_exceeded, action_count, config = await self.action_tracker.check_threshold(
                guild.id, executor.id, "ban"
            )

            if threshold_exceeded:
                # Threshold breached - apply punishment
                await self.apply_punishment(guild, executor, user, action_count, config)

        except Exception as e:
            print(f"Error in antiban on_member_ban: {e}")

    async def apply_punishment(self, guild, executor, last_banned_user, action_count, config):
        """Apply punishment when threshold is exceeded"""
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

            
            # Get all recent ban actions to revert
            recent_actions = await self.action_tracker.get_recent_actions(
                guild.id, executor.id, "ban", config.time_window
            )

            # Apply escalated punishment
            punishment_applied = await apply_escalated_punishment(
                guild=guild,
                member=executor,
                punishment_type=actual_punishment,
                escalation_level=escalation_level,
                duration=duration,
                reason=f"Antinuke: {action_count} bans in {config.time_window}s (Level {escalation_level})"
            )

            # Revert all recent bans
            actions_reverted = 0
            for action in recent_actions:
                if action.reverted:
                    continue
                    
                try:
                    # Unban the user that was banned
                    target_id = action.metadata.get("target_id")
                    if target_id:
                        user_to_unban = await self.bot.fetch_user(target_id)
                        await guild.unban(
                            user_to_unban, 
                            reason=f"AntiNuke: Reverting unauthorized ban by {executor}"
                        )
                        actions_reverted += 1
                        await asyncio.sleep(0.5)  # Rate limit protection
                except Exception as e:
                    print(f"Failed to revert ban for user {target_id}: {e}")

            # Mark actions as reverted
            await self.action_tracker.mark_actions_reverted(guild.id, executor.id, "ban")

            # Log punishment with escalation level
            await self.action_tracker.log_punishment(
                guild_id=guild.id,
                user_id=executor.id,
                action_type="ban",
                punishment_type=config.punishment_type,
                actions_reverted=actions_reverted,
                reason=f"Exceeded ban threshold: {action_count} bans in {config.time_window} seconds",
                escalation_level=escalation_level
            )
            
            # Send notification to server owner
            try:
                await AntinukeNotifier.send_notification(
                    guild=guild,
                    violator=executor,
                    action_type="ban",
                    action_count=action_count,
                    punishment_type=actual_punishment,
                    reason=f"Exceeded ban threshold: {action_count} bans in {config.time_window} seconds",
                    escalation_level=escalation_level,
                    bot=self.bot
                )
            except Exception as notify_error:
                print(f"Failed to send notification: {notify_error}")

            print(f"[AntiNuke] Punished {executor} in {guild.name}: {action_count} bans detected, {actions_reverted} actions reverted, escalation level {escalation_level}")

        except Exception as e:
            print(f"Error applying punishment in antiban: {e}")

