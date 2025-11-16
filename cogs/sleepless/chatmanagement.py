import discord
from discord.ext import commands


class _chatmanagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    """Chat Management"""

    def help_custom(self):
        emoji = '<:tchat:1430364431195570198>'
        label = "Chat Management"
        description = "Show commands for Chat Management"
        return emoji, label, description

async def setup(bot):
    await bot.add_cog(_chatmanagement(bot))