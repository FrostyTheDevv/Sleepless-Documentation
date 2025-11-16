import discord
from discord.ext import commands


class _sticky(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    """Sticky Messages"""

    def help_custom(self):
        emoji = '<:clock1:1427471544409657354>'
        label = "Sticky Messages"
        description = "Commands for sticky messages to keep important info visible"
        return emoji, label, description

async def setup(bot):
    await bot.add_cog(_sticky(bot))