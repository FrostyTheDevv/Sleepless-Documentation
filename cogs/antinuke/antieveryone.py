import discord
from discord.ext import commands
import aiosqlite
from utils.action_tracker import ActionTracker
from utils.whitelist_helper import is_whitelisted
from utils.escalation import get_escalation_level, apply_escalated_punishment

class AntiEveryone(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tracker = ActionTracker()
        
    async def cog_load(self):
        await self.tracker.initialize()
    
    async def cog_unload(self):
        await self.tracker.close()

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild or message.author.bot:
            return
        
        if not (message.mention_everyone or '@everyone' in message.content or '@here' in message.content):
            return
        
        guild = message.guild
        
        async with aiosqlite.connect('db/anti.db') as db:
            cursor = await db.execute(
                "SELECT status FROM antinuke WHERE guild_id = ?",
                (guild.id,)
            )
            status = await cursor.fetchone()
            if not status or not status[0]:
                return
        
        if message.author.id in {guild.owner_id, self.bot.user.id}:
            return
        
        author_member = guild.get_member(message.author.id)
        if not author_member:
            return
        
        if await is_whitelisted(guild.id, author_member, 'meneve'):
            return
        
        await self.tracker.track_action(
            guild_id=guild.id,
            user_id=message.author.id,
            action_type="everyone_mention",
            metadata={
                "message_id": message.id,
                "channel_id": message.channel.id,
                "content_preview": message.content[:100]
            }
        )
        
        exceeded, action_count, config = await self.tracker.check_threshold(
            guild_id=guild.id,
            user_id=message.author.id,
            action_type="everyone_mention"
        )
        
        if exceeded:
            try:
                # Get escalation level based on offense history
                escalation_level = await get_escalation_level(guild.id, message.author.id)

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
                    member=message.author,
                    punishment_type=actual_punishment,
                    escalation_level=escalation_level,
                    duration=duration,
                    reason=f"Antinuke: {action_count} @everyone/@here mentions in {config.time_window}s (Level {escalation_level})"
                )
                
                # Delete the message
                try:
                    await message.delete()
                except:
                    pass
                
                await self.tracker.log_punishment(
                    guild_id=guild.id,
                    user_id=message.author.id,
                    action_type="everyone_mention",
                    punishment_type=config.punishment_type,
                    actions_reverted=1,
                    reason=f"@everyone/@here spam: {action_count} mentions in {config.time_window} seconds",
                    escalation_level=escalation_level
                )
            except Exception as e:
                print(f"Error applying punishment in antieveryone: {e}")

async def setup(bot):
    await bot.add_cog(AntiEveryone(bot))
