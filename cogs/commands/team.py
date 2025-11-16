import discord
import time
import aiosqlite
from discord import Embed, ButtonStyle
from discord.ui import Button, View
from discord.ext import commands

from utils.error_helpers import StandardErrorHandler
class Team(commands.Cog):
    
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
    async def team(self, ctx):
        view = View()

        # --- Team Button ---
        team_button = Button(label="Team", style=ButtonStyle.green)

        async def team_button_callback(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("This menu isn't for you!", ephemeral=True)

            embed = Embed(title="Sleepless Team", color=0x006fb9)
            embed.add_field(name="<:feast_devs:1400149314348777482> DEVELOPERS",
                            value="[**3dxb**](https://discord.com/channels/@me/1385303636766359612)", inline=False)
            embed.add_field(name="<:feast_owner:1400149583153070191> OWNERS",
                            value="[**._romiyo_.**](https://discord.com/channels/@me/1274199510846931031)\n[**toxic.rtx**](https://discord.com/channels/@me/1235967118676328565)", inline=False)
            embed.add_field(name="<:feast_manager:1400415009816838224> MANAGERS",
                            value="[**HIRING, DM OWNER/DEV TO APPLY**](https://discord.com/channels/@me/1385303636766359612)", inline=False)
            embed.set_footer(text="Powered by Sleepless Development™", icon_url=self.bot.user.display_avatar.url)
            await interaction.response.edit_message(embed=embed, view=view)

        team_button.callback = team_button_callback
        view.add_item(team_button)

        # --- Owner Special Button ---
        ownerspecial_button = Button(label="OwnerSpecial", style=ButtonStyle.red)

        async def ownerspecial_button_callback(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("This menu isn't for you!", ephemeral=True)

            embed = Embed(title="<:friend:1398683719086375063> OWNER FRIENDS", color=0x006fb9)
            embed.add_field(name="<:feast_dot:1400140945617588264>OS #1", value="[NAHI HA](https://discord.gg/5wtjDkYbVh)", inline=False)
            embed.add_field(name="<:feast_dot:1400140945617588264>OS #2", value="[NAHI HA](https://discord.gg/5wtjDkYbVh)", inline=False)
            embed.set_footer(text="Powered by Sleepless Development™", icon_url=self.bot.user.display_avatar.url)
            await interaction.response.edit_message(embed=embed, view=view)

        ownerspecial_button.callback = ownerspecial_button_callback
        view.add_item(ownerspecial_button)

        # --- Partner Button ---
        partner_button = Button(label="Partners", style=ButtonStyle.green)

        async def partner_button_callback(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("This menu isn't for you!", ephemeral=True)

            embed = Embed(title="Sleepless Partners", color=0x006fb9)
            embed.add_field(name="<:feast_partners:1400149267967905812> PARTNER NO 1", value="[VAASTE](https://dsc.gg/vaaste)", inline=False)
            embed.add_field(name="<:feast_partners:1400149267967905812> PARTNER NO 2", value="[DIWALE](https://discord.gg/5wtjDkYbVh)", inline=False)
            embed.set_footer(text="Powered by Sleepless Development™", icon_url=self.bot.user.display_avatar.url)
            await interaction.response.edit_message(embed=embed, view=view)

        partner_button.callback = partner_button_callback
        view.add_item(partner_button)

        # --- Delete Button ---
        delete_button = Button(emoji="<:feast_delete:1400140670659989524>", style=ButtonStyle.red)

        async def delete_button_callback(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("This menu isn't for you!", ephemeral=True)
            await interaction.message.delete()

        delete_button.callback = delete_button_callback
        view.add_item(delete_button)


        # --- Initial Embed ---
        embed = Embed(title="Sleepless Team Panel", description="Select an option below:", color=0x2F3136)
        await ctx.send(embed=embed, view=view)

# Setup
async def setup(bot):
    await bot.add_cog(Team(bot))
