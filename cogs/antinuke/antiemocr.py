import discord
from discord.ext import commands
import aiosqlite
import asyncio
from utils.action_tracker import ActionTracker
from utils.whitelist_helper import is_whitelisted
from utils.escalation import get_escalation_level, apply_escalated_punishment

class AntiEmojiCreate(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tracker = ActionTracker()
        
    async def cog_load(self):
        await self.tracker.initialize()
    
    async def cog_unload(self):
        await self.tracker.close()

    async def fetch_audit_logs(self, guild, action):
        if not guild.me.guild_permissions.view_audit_log:
            return None
        try:
            async for entry in guild.audit_logs(action=action, limit=1):
                return entry
        except Exception:
            pass
        return None

    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild, before, after):
        if len(after) <= len(before):
            return
        
        async with aiosqlite.connect('db/anti.db') as db:
            cursor = await db.execute(
                "SELECT status FROM antinuke WHERE guild_id = ?",
                (guild.id,)
            )
            status = await cursor.fetchone()
            if not status or not status[0]:
                return
        
        log_entry = await self.fetch_audit_logs(guild, discord.AuditLogAction.emoji_create)
        if not log_entry:
            return
        
        executor = log_entry.user
        
        if executor.id in {guild.owner_id, self.bot.user.id}:
            return
        
        executor_member = guild.get_member(executor.id)
        if not executor_member:
            return
        
        if await is_whitelisted(guild.id, executor_member, 'mngstemo'):
            return
        
        # Find new emoji
        new_emoji = [e for e in after if e not in before][0] if len([e for e in after if e not in before]) > 0 else None
        
        await self.tracker.track_action(
            guild_id=guild.id,
            user_id=executor.id,
            action_type="emoji_create",
            metadata={
                "emoji_id": new_emoji.id if new_emoji else None,
                "emoji_name": new_emoji.name if new_emoji else "Unknown",
                "reason": log_entry.reason
            }
        )
        
        exceeded, action_count, config = await self.tracker.check_threshold(
            guild_id=guild.id,
            user_id=executor.id,
            action_type="emoji_create"
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
                    reason=f"Antinuke: {action_count} emoji creates in {config.time_window}s (Level {escalation_level})"
                )
                
                # Delete newly created emoji
                if new_emoji:
                    await new_emoji.delete(reason=f"Emoji created by {executor} (threshold breach)")
                
                await self.tracker.log_punishment(
                    guild_id=guild.id,
                    user_id=executor.id,
                    action_type="emoji_create",
                    punishment_type=config.punishment_type,
                    actions_reverted=1,
                    reason=f"Created {action_count} emojis in {config.time_window} seconds",
                    escalation_level=escalation_level
                )
            except Exception as e:
                print(f"Error applying punishment in antiemocr: {e}")

async def setup(bot):
    await bot.add_cog(AntiEmojiCreate(bot))
