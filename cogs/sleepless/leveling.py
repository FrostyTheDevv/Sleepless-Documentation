import discord
from discord.ext import commands


class _leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    """Leveling commands"""

    def help_custom(self):
        emoji = '<:slash:1428164524372000879>'
        label = "Leveling Commands"
        description = "Show you Commands of Leveling System"
        return emoji, label, description

    @commands.group()
    async def __Leveling__(self, ctx: commands.Context):
        """`level` - View your current level and progress\n`level @user` - View someone else's level\n`level leaderboard` - Show server leaderboard\n`level rank` - View detailed rank information\n`level help` - Comprehensive leveling help\n\n__**Configuration (Admin Only)**__\n`level config` - View current settings\n`level settings enable/disable` - Toggle leveling system\n`level settings message <text>` - Set level-up message\n`level settings channel [#channel]` - Set announcement channel\n`level settings roles add/remove/list` - Manage role rewards\n`level settings blacklist add/remove/list` - Manage XP blacklist\n\n__**Admin Management**__\n`level admin set @user <level>` - Set user's level\n`level admin add @user <xp>` - Add XP to user\n`level admin reset @user` - Reset user's progress"""