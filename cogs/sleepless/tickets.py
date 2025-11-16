import discord
from discord.ext import commands


class _tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    """Ticket System"""

    def help_custom(self):
        emoji = '<:ticket1:1428163964017049690>'
        label = "Ticket System"
        description = "Professional support ticket system with customizable panels and moderation tools"
        return emoji, label, description

async def setup(bot):
    await bot.add_cog(_tickets(bot))