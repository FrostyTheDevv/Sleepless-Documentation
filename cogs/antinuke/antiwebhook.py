import discord
from discord.ext import commands
import aiosqlite
import asyncio
from utils.action_tracker import ActionTracker
from utils.whitelist_helper import is_whitelisted
from utils.escalation import get_escalation_level, apply_escalated_punishment
from utils.antinuke_notifier import AntinukeNotifier

class AntiWebhookUpdate(commands.Cog):
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
    async def on_webhooks_update(self, channel):
        guild = channel.guild
        
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
        
        audit_entries = await self.fetch_audit_logs(guild, discord.AuditLogAction.webhook_update)
        if not audit_entries:
            return
        
        # Find most recent webhook update
        update_entry = audit_entries[0] if audit_entries else None
        if not update_entry:
            return
        
        executor = update_entry.user
        
        if executor.id in {guild.owner_id, self.bot.user.id}:
            return
        
        executor_member = guild.get_member(executor.id)
        if not executor_member:
            return
        
        if await is_whitelisted(guild.id, executor_member, 'mngweb'):
            return
        
        await self.tracker.track_action(
            guild_id=guild.id,
            user_id=executor.id,
            action_type="webhook_update",
            metadata={
                "channel_id": channel.id,
                "channel_name": channel.name,
                "reason": update_entry.reason
            }
        )
        
        exceeded, action_count, config = await self.tracker.check_threshold(
            guild_id=guild.id,
            user_id=executor.id,
            action_type="webhook_update"
        )
        
        if exceeded:
            await self.apply_punishment(guild, executor, channel, action_count, config)

    async def apply_punishment(self, guild, executor, channel, action_count, config):
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
            success = await apply_escalated_punishment(
                guild=guild,
                member=executor,
                punishment_type=actual_punishment,
                escalation_level=escalation_level,
                duration=duration,
                reason=f"Antinuke: {action_count} webhook updates in {config.time_window}s (Level {escalation_level})"
            )
            
            if success:
                await self.tracker.mark_actions_reverted(
                    guild_id=guild.id,
                    user_id=executor.id,
                    action_type="webhook_update"
                )
                
                await self.tracker.log_punishment(
                    guild_id=guild.id,
                    user_id=executor.id,
                    action_type="webhook_update",
                    punishment_type=config.punishment_type,
                    actions_reverted=0,
                    reason=f"Updated webhooks {action_count} times in {config.time_window} seconds",
                    escalation_level=escalation_level
                )
                
                # Send notification to server owner
                try:
                    await AntinukeNotifier.send_notification(
                        guild=guild,
                        violator=executor,
                        action_type="webhook_update",
                        action_count=action_count,
                        punishment_type=actual_punishment,
                        reason=f"Updated webhooks {action_count} times in {config.time_window} seconds",
                        escalation_level=escalation_level,
                        bot=self.bot
                    )
                except Exception as notify_error:
                    print(f"Failed to send notification: {notify_error}")
            
        except Exception as e:
            print(f"Error applying punishment in antiwebhook: {e}")

async def setup(bot):
    await bot.add_cog(AntiWebhookUpdate(bot))
