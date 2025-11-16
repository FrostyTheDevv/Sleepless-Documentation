import discord
from discord.ext import commands


class _afk(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    """AFK & Ping Protection"""

    def help_custom(self):
        emoji = '<a:Loading:1430203733593034893>'
        label = "AFK & Ping Protection"
        description = "Show you commands of AFK & Ping Protection"
        return emoji, label, description

async def setup(bot):
    await bot.add_cog(_afk(bot))