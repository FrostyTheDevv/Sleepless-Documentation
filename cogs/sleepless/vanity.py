import discord

from discord.ext import commands

class _vanity(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

    """Vanity System"""

    def help_custom(self):
        emoji = '<:vanity:1428163639814389771>'
        label = "Vanity System"
        description = "Show you Commands of Vanity System"
        return emoji, label, description

    @commands.group()

    async def __VanitySystem__(self, ctx: commands.Context):

        """`$vanity setup` , `$vanity url <custom_url>` , `$vanity role <role>` , `$vanity channel <channel>` , `$vanity responder enable/disable` , `$vanity keywords add/remove <word>` , `$vanity keywords list` , `$vanity keywords clear` , `$vanity message <text>` , `$vanity embed color <hex>` , `$vanity embed title <text>` , `$vanity embed footer <text>` , `$vanity embed preview` , `$vanity embed reset` , `$vanity stats [user]` , `$vanity leaderboard [limit]`"""