from utils.error_helpers import StandardErrorHandler
# cogs/commands/call.py
import discord
from discord.ext import commands
from typing import Optional

class Call(commands.Cog):
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="call")
    async def call(self, ctx, member: discord.Member, *, reason: Optional[str] = None):
        """Call a user and send them a DM with an optional reason"""
        if member.bot:
            await ctx.send(embed=discord.Embed(
                description=f"❌ You cannot call bots.",
                color=discord.Color.red()
            ))
            return

        try:
            # Prepare DM message
            if reason:
                dm_message = f"**YOU ARE CALLED BY {ctx.author} in #{ctx.channel.name} for: {reason}**"
            else:
                dm_message = f"**YOU ARE CALLED BY {ctx.author} from #{ctx.channel.name} in {ctx.guild.name}**"
            
            await member.send(dm_message)

            # Confirmation embed
            channel_link = f"<#{ctx.channel.id}>"
            embed = discord.Embed(
                title="User Called",
                description=f"✅ **{member.name}** is called in {channel_link}.",
                color=discord.Color.green()
            )
            if reason:
                embed.add_field(name="Reason", value=reason, inline=False)
            embed.set_footer(text=f"Called by {ctx.author}", icon_url=ctx.author.avatar.url)

            await ctx.send(embed=embed)

        except discord.Forbidden:
            await ctx.send(embed=discord.Embed(
                description=f"❌ Could not DM {member.mention}. They might have DMs closed.",
                color=discord.Color.red()
            ))

    @commands.command(name="dmuser")
    @commands.has_permissions(administrator=True)
    async def dmuser(self, ctx, member: discord.Member, *, message: str):
        """Send a custom DM to a user (Administrator only)."""
        if member.bot:
            await ctx.send(embed=discord.Embed(
                description=f"❌ You cannot DM bots.",
                color=discord.Color.red()
            ))
            return

        try:
            # Send the custom DM
            await member.send(f"📩 **Message from {ctx.guild.name} Admin:**\n{message}")

            # Confirmation embed
            embed = discord.Embed(
                title="DM Sent",
                description=f"✅ Your message was sent to **{member.name}**.",
                color=discord.Color.green()
            )
            embed.add_field(name="Message", value=message, inline=False)
            embed.set_footer(text=f"Sent by {ctx.author}", icon_url=ctx.author.avatar.url)

            await ctx.send(embed=embed)

        except discord.Forbidden:
            await ctx.send(embed=discord.Embed(
                description=f"❌ Could not DM {member.mention}. They might have DMs closed.",
                color=discord.Color.red()
            ))

async def setup(bot):
    await bot.add_cog(Call(bot))
