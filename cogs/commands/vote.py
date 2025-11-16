import discord
import time
import aiosqlite
from discord import Embed, ButtonStyle
from discord.ui import Button, View
from discord.ext import commands

from utils.error_helpers import StandardErrorHandler
class Vote(commands.Cog):
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot
        self.start_time = time.time()
        self.total_songs_played = 0
        # Removed loop access from __init__

    async def setup_hook(self):
        """Called when the cog is loaded"""
        await self.setup_database()

    async def setup_database(self):
        # Your DB setup logic
        pass

    @commands.command()
    async def Vote(self, ctx):
        view = View()

        # --- topgg Button ---
        topgg_button = Button(label="TOPGG", style=ButtonStyle.green)

        async def topgg_button_callback(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("This menu isn't for you!", ephemeral=True)

            embed = Embed(title="Sleepless Vote Links", color=0x006fb9)
            embed.add_field(name="🏆 **TOP.GG VOTE LINK**",
                            value="[🗳️ Vote on Top.gg](https://top.gg/bot/1414317652066832527/vote)\n*Help us climb the leaderboards!*", inline=False)
            embed.set_footer(text="Powered by Sleepless Development™", icon_url=self.bot.user.display_avatar.url)
            await interaction.response.edit_message(embed=embed, view=view)

        topgg_button.callback = topgg_button_callback
        view.add_item(topgg_button)

        # --- DBL Button ---
        dbl_button = Button(label="DBL", style=ButtonStyle.red)

        async def dbl_button_callback(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("This menu isn't for you!", ephemeral=True)

            embed = Embed(title="Sleepless Vote Link", color=0x006fb9)
            embed.add_field(name="📊 **DISCORD BOT LIST**", value="[🗳️ Vote on DBL](https://discordbotlist.com/bots/sleepless-1414317652066832527)\n*Support us on Discord Bot List!*", inline=False)
            embed.set_footer(text="Powered by Sleepless Development™", icon_url=self.bot.user.display_avatar.url)
            await interaction.response.edit_message(embed=embed, view=view)

        dbl_button.callback = dbl_button_callback
        view.add_item(dbl_button)

        # --- Delete Button ---
        delete_button = Button(emoji="❌", style=ButtonStyle.red)

        async def delete_button_callback(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("This menu isn't for you!", ephemeral=True)
            await interaction.message.delete()

        delete_button.callback = delete_button_callback
        view.add_item(delete_button)


        # --- Initial Embed ---
        embed = Embed(title="Sleepless Voting Panel", description="Select An Voter Below:", color=0x2F3136)
        await ctx.send(embed=embed, view=view)

# Setup
async def setup(bot):
    await bot.add_cog(Vote(bot))
