import discord
from discord.ext import commands


class _farewell(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    """Farewell commands"""
  
    def help_custom(self):
        emoji = '<:greet:1427471580014837881>'
        label = "Sleepless Farewell"
        description = "Show you Command Of Farewell"
        return emoji, label, description

    @commands.group()
    async def __Farewell__(self, ctx: commands.Context):
        """`farewell setup` , `farewell reset`, `farewell channel` , `farewell edit` , `farewell test` , `farewell config` , `farewell autodelete` , `farewell`"""