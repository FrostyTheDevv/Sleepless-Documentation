import discord

from discord.ext import commands

class _MessageTracker(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

    """Message Tracker"""

    def help_custom(self):
        emoji = '<:warning:1428163138322301018>'
        label = "Message Tracker"
        description = "Show you Commands of Message Tracker"
        return emoji, label, description

    @commands.group()

    async def __messageTracker__(self, ctx: commands.Context):

        """`$messages` , `$clearmsgs `, `$addmsgs` , `$removemsgs`"""