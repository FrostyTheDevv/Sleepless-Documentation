import discord
from discord.ext import commands
import asyncio

class React(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        for owner in self.bot.owner_ids:
            if f"<@{owner}>" in message.content:
                try:
                    if owner == 1385303636766359612:
                        
                        emojis = [
                                "<:feast_devs:1400149314348777482>",
                                "<:feast_owner:1400149583153070191>",
                                "<:BadeLog:1138340426844221450>"   
                        ]
                        for emoji in emojis:
                            await message.add_reaction(emoji)
                    else:
                        
                        await message.add_reaction("<:feast_owner:1400149583153070191>>")
                except discord.errors.RateLimited as e:
                    await asyncio.sleep(e.retry_after)
                    await message.add_reaction("<:feast_owner:1400149583153070191>")
                except Exception as e:
                    print(f"An unexpected error occurred Auto react owner mention: {e}")
