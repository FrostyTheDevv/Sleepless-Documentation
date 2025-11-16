import discord
from discord.ext import commands


class _boosterroles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    """Booster Roles"""

    def help_custom(self):
        emoji = '<:boost:1427471537149186140>'
        label = "Booster Roles"
        description = "Comprehensive booster role management system with custom messages"
        return emoji, label, description

async def setup(bot):
    await bot.add_cog(_boosterroles(bot))