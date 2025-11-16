import discord
from discord.ext import commands


class _voicemaster(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    """VoiceMaster"""

    def help_custom(self):
        emoji = '<:voice:1428163515318800524>'
        label = "VoiceMaster"
        description = "Dynamic voice channel creation and management system"
        return emoji, label, description

async def setup(bot):
    await bot.add_cog(_voicemaster(bot))