import discord
from discord.ext import commands


class _reactionroles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    """Reaction Roles"""

    def help_custom(self):
        emoji = '<:plusu:1428164526884257852>'
        label = "Reaction Roles"
        description = "Shows you commands for Reaction Roles"
        return emoji, label, description

async def setup(bot):
    await bot.add_cog(_reactionroles(bot))