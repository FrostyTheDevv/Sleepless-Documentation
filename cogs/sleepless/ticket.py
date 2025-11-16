import discord

from discord.ext import commands

class _ticket(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

    """Ticket"""

    def help_custom(self):

              emoji = '<:ticket1:1428163964017049690>'

              label = "Ticket"

              description = "Show you Commands of Ticket"

              return emoji, label, description

    @commands.group()

    async def __Ticket__(self, ctx: commands.Context):

        """`ticket setup` , `ticket category create <name>` , `ticket panel create` , `ticket staff add <role>` , `ticket close` , `ticket list` , `ticket settings`"""