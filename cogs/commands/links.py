import discord
import time
import aiosqlite
from discord import Embed, ButtonStyle
from discord.ui import Button, View
from discord.ext import commands

from utils.error_helpers import StandardErrorHandler
class Links(commands.Cog):
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot
        self.start_time = time.time()
        self.total_songs_played = 0

    async def setup_hook(self):
        await self.setup_database()

    async def setup_database(self):
        # Your DB setup logic
        pass

    @commands.command(name="links")
    async def links(self, ctx):
        view = View()

        # Invite Button
        invite_button = Button(label="Invite", style=ButtonStyle.green)

        async def invite_button_callback(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("This menu isn't for you!", ephemeral=True)

            embed = Embed(title="Sleepless Invite Links", color=0x006fb9)
            embed.add_field(
                name=" ** Sleepless Invite Link**",
                value="[Click Here](https://discord.com/oauth2/authorize?client_id=1414317652066832527&permissions=8&integration_type=0&scope=bot+applications.commands)",
                inline=False
            )
            embed.set_footer(text="Powered by Sleepless Development™", icon_url=self.bot.user.display_avatar.url)
            await interaction.response.edit_message(embed=embed, view=view)

        invite_button.callback = invite_button_callback
        view.add_item(invite_button)

        # Support Button
        support_button = Button(label="Support", style=ButtonStyle.red)

        async def support_button_callback(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("This menu isn't for you!", ephemeral=True)

            embed = Embed(title="Support Server Link", color=0x006fb9)
            embed.add_field(
                name="Discord Server :",
                value="[Click Here](https://discord.gg/5wtjDkYbVh)",
                inline=False
            )
            embed.set_footer(text="Powered by Sleepless Development™", icon_url=self.bot.user.display_avatar.url)
            await interaction.response.edit_message(embed=embed, view=view)

        support_button.callback = support_button_callback
        view.add_item(support_button)

        # Vote Button
        vote_button = Button(label="Vote", style=ButtonStyle.green)

        async def vote_button_callback(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("This menu isn't for you!", ephemeral=True)

            embed = Embed(title="Vote Links", color=0x006fb9)
            embed.add_field(name="🏆 **TOP.GG**", value="[🗳️ Vote Here](https://top.gg/bot/1414317652066832527/vote)", inline=False)
            embed.add_field(name="📋 **DISCORD BOT LIST**", value="[🗳️ Vote Here](https://discordbotlist.com/bots/sleepless)", inline=False)
            embed.set_footer(text="Powered by Sleepless Development™", icon_url=self.bot.user.display_avatar.url)
            await interaction.response.edit_message(embed=embed, view=view)

        vote_button.callback = vote_button_callback
        view.add_item(vote_button)

        # Delete Button
        delete_button = Button(emoji="❌", style=ButtonStyle.red)

        async def delete_button_callback(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("This menu isn't for you!", ephemeral=True)
            await interaction.message.delete()

        delete_button.callback = delete_button_callback
        view.add_item(delete_button)

        # Initial Embed
        embed = Embed(title="Sleepless Essential Links", description="Select a link embed below:", color=0x2F3136)
        await ctx.send(embed=embed, view=view)

# Setup function
async def setup(bot):
    await bot.add_cog(Links(bot))
