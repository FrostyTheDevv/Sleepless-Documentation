import discord
from discord.ext import commands


class _jail(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    """Jail & Timeout"""

    def help_custom(self):
        emoji = '<:skull1:1428168178936188968>'
        label = "Jail & Timeout"
        description = "Show you commands of Jail & Timeout"
        return emoji, label, description

async def setup(bot):
    await bot.add_cog(_jail(bot))