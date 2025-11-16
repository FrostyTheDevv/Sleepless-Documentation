import discord
from discord.ext import commands
import aiosqlite
from utils.action_tracker import ActionTracker
from utils.whitelist_helper import is_whitelisted
from utils.escalation import get_escalation_level, apply_escalated_punishment
from utils.antinuke_notifier import AntinukeNotifier

class AntiBotAdd(commands.Cog):
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
    async def on_member_join(self, member):
        if not member.bot:
            return
        
        guild = member.guild
        
        async with aiosqlite.connect('db/anti.db') as db:
            cursor = await db.execute(
                "SELECT status FROM antinuke WHERE guild_id = ?",
                (guild.id,)
            )
            status = await cursor.fetchone()
            if not status or not status[0]:
                return
        
        log_entry = await self.fetch_audit_logs(guild, discord.AuditLogAction.bot_add, member.id)
        if not log_entry:
            return
        
        executor = log_entry.user
        
        if executor.id in {guild.owner_id, self.bot.user.id}:
            return
        
        executor_member = guild.get_member(executor.id)
        if not executor_member:
            return
        
        if await is_whitelisted(guild.id, executor_member, 'botadd'):
            return
        
        await self.tracker.track_action(
            guild_id=guild.id,
            user_id=executor.id,
            action_type="bot_add",
            metadata={
                "bot_id": member.id,
                "bot_name": str(member),
                "reason": log_entry.reason
            }
        )
        
        exceeded, action_count, config = await self.tracker.check_threshold(
            guild_id=guild.id,
            user_id=executor.id,
            action_type="bot_add"
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
                    reason=f"Antinuke: {action_count} bot adds in {config.time_window}s (Level {escalation_level})"
                )
                
                # Kick the bot
                await member.kick(reason=f"Bot added by {executor} (threshold breach)")
                
                await self.tracker.log_punishment(
                    guild_id=guild.id,
                    user_id=executor.id,
                    action_type="bot_add",
                    punishment_type=config.punishment_type,
                    actions_reverted=1,
                    reason=f"Added {action_count} bots in {config.time_window} seconds",
                    escalation_level=escalation_level
                )
                
                # Send notification to server owner
                try:
                    await AntinukeNotifier.send_notification(
                        guild=guild,
                        violator=executor,
                        action_type="bot_add",
                        action_count=action_count,
                        punishment_type=actual_punishment,
                        reason=f"Added {action_count} bots in {config.time_window} seconds",
                        escalation_level=escalation_level,
                        bot=self.bot
                    )
                except Exception as notify_error:
                    print(f"Failed to send notification: {notify_error}")
            except Exception as e:
                print(f"Error applying punishment in antibotadd: {e}")

async def setup(bot):
    await bot.add_cog(AntiBotAdd(bot))
