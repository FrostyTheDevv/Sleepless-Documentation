import discord
from discord.ext import commands


class _interactions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    """Interaction commands"""
  
    def help_custom(self):
        emoji = '<:web:1428162947187736679>'
        label = "Interactions"
        description = "Social interaction commands with accept/decline system"
        return emoji, label, description

    def get_commands(self):
        """Get commands from the actual Interactions cog"""
        interactions_cog = self.bot.get_cog('Interactions')
        if interactions_cog:
            return interactions_cog.get_commands()
        return []

    @commands.group()
    async def __Interactions__(self, ctx: commands.Context):
        """`hug` , `slap` , `handshake` , `highfive` , `kiss` , `pat` , `poke` , `cuddle` , `tickle` , `bite` , `wink` , `wave` , `feed` , `dance` , `glomp` , `handhold` , `nuzzle` , `salute` , `interactions` , `interaction_leaderboard`"""