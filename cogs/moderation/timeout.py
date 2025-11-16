import discord
from discord.ext import commands
from discord import ui
from datetime import timedelta
import re
from utils.Tools import *
from utils.timezone_helpers import get_timezone_helpers
from typing import Optional

class TimeoutView(ui.View):
    def __init__(self, user, author, bot):
        super().__init__(timeout=120)
        self.user = user
        self.author = author
        self.bot = bot
        self.message = None  
        self.color = discord.Color.from_rgb(0, 0, 0)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("You are not allowed to interact with this!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            if isinstance(item, (discord.ui.Button, discord.ui.Select)):
                item.disabled = True
        if self.message and hasattr(self.message, "edit"):
            try:
                edit_method = self.message.edit
                if callable(edit_method):
                    result = edit_method(view=self)
                    # Do not await result if it is None or not awaitable
                # else, do nothing (not awaitable)
            except Exception:
                pass

    @ui.button(label="Unmute", style=discord.ButtonStyle.success)
    async def unmute(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ReasonModal(user=self.user, author=self.author, view=self, bot=self.bot)
        await interaction.response.send_modal(modal)

    @ui.button(style=discord.ButtonStyle.gray, emoji="<:feast_delete:1400140670659989524>")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.message and hasattr(interaction.message, "delete"):
            await interaction.message.delete()

class AlreadyTimedoutView(ui.View):
    def __init__(self, user, author, bot):
        super().__init__(timeout=60)
        self.user = user
        self.author = author
        self.bot = bot
        self.message = None  

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("You are not allowed to interact with this!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            if isinstance(item, (discord.ui.Button, discord.ui.Select)):
                item.disabled = True
        if self.message and hasattr(self.message, "edit"):
            try:
                edit_method = self.message.edit
                if callable(edit_method):
                    result = edit_method(view=self)
                    # Do not await result if it is None or not awaitable
                # else, do nothing (not awaitable)
            except Exception:
                pass

    @ui.button(label="Unmute", style=discord.ButtonStyle.success)
    async def unmute(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ReasonModal(user=self.user, author=self.author, view=self, bot=self.bot)
        await interaction.response.send_modal(modal)

    @ui.button(style=discord.ButtonStyle.gray, emoji="<:feast_delete:1400140670659989524>")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.message and hasattr(interaction.message, "delete"):
            await interaction.message.delete()

class ReasonModal(ui.Modal):
    def __init__(self, user, author, view, bot):
        super().__init__(title="Unmute Reason")
        self.user = user
        self.author = author
        self.view = view
        self.bot = bot
        self.tz_helpers = get_timezone_helpers(bot)
        self.reason_input = ui.TextInput(label="Reason for Unmuting", placeholder="Provide a reason to unmute or leave it blank.", required = False, max_length=2000, style=discord.TextStyle.paragraph)
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        reason = self.reason_input.value or "No reason provided"
        try:
            await self.user.send(f"You have been Unmuted in **{self.author.guild.name}** by **{self.author}**. Reason: {reason or 'No reason provided'}")
            dm_status = "Yes"
        except discord.Forbidden:
            dm_status = "No"
        except discord.HTTPException:
            dm_status = "No"

        embed = discord.Embed(description=f"** Target User:** [{self.user}](https://discord.com/users/{self.user.id})\n **User Mention:** {self.user.mention}\n** DM Sent:** {dm_status}\n**Reason:** {reason}", color=0x006fb9)
        embed.set_author(name=f"Successfully Unmuted {self.user.name}", icon_url=self.user.avatar.url if self.user.avatar else self.user.default_avatar.url)
        embed.add_field(name=" Moderator:", value=interaction.user.mention, inline=False)
        embed.set_footer(text=f"Requested by {self.author}", icon_url=self.author.avatar.url if self.author.avatar else self.author.default_avatar.url)
        embed.timestamp = self.tz_helpers.get_utc_now()

        await self.user.edit(timed_out_until=None, reason=f"Unmute requested by {self.author}")
        await interaction.response.edit_message(embed=embed, view=self.view)
        for item in self.view.children:
            item.disabled = True
        if interaction.message and hasattr(interaction.message, "edit"):
            await interaction.message.edit(view=self.view)

class Mute(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = discord.Color.from_rgb(0, 0, 0)
        self.tz_helpers = get_timezone_helpers(bot)

    def get_user_avatar(self, user):
        return user.avatar.url if user.avatar else user.default_avatar.url

    def parse_time(self, time_str):
        """Parse time string and return timedelta and description"""
        if not time_str:
            return None, None
            
        time_pattern = r"(\d+)([mhd])"
        match = re.match(time_pattern, time_str.lower())
        if match:
            time_value = int(match.group(1))
            time_unit = match.group(2)
            
            # Validate ranges and ensure they don't exceed Discord limits
            if time_unit == 'm' and 1 <= time_value <= 40320:  # Max 28 days in minutes
                return timedelta(minutes=time_value), f"{time_value} minute{'s' if time_value != 1 else ''}"
            elif time_unit == 'h' and 1 <= time_value <= 672:  # Max 28 days in hours
                return timedelta(hours=time_value), f"{time_value} hour{'s' if time_value != 1 else ''}"
            elif time_unit == 'd' and 1 <= time_value <= 28:  # Max 28 days
                return timedelta(days=time_value), f"{time_value} day{'s' if time_value != 1 else ''}"
        
        return None, None

    @commands.hybrid_command(
        name="mute",
        help="Mutes a user with optional time and reason",
        usage="mute <member> [time] [reason]",
        aliases=["timeout", "stfu"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def mute(self, ctx, user: discord.Member, time: Optional[str] = None, *, reason=None):
        if reason is None:
            reason = ""

        if user.is_timed_out():
            embed = discord.Embed(description="**Requested User is already muted in this server.**", color=self.color)
            embed.add_field(name="__Unmute__:", value="Click on the `Unmute` button to remove the timeout from the user.")
            embed.set_author(name=f"{user.name} is Already Timed Out!", icon_url=self.get_user_avatar(user))
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=self.get_user_avatar(ctx.author))
            view = AlreadyTimedoutView(user=user, author=ctx.author, bot=self.bot)
            message = await ctx.send(embed=embed, view=view)
            view.message = message
            return

        if user == ctx.guild.owner:
            error = discord.Embed(color=self.color, description="You can't timeout the Server Owner!")
            error.set_author(name="Error Timing Out User")
            error.set_footer(text=f"Requested by {ctx.author}", icon_url=self.get_user_avatar(ctx.author))
            return await ctx.send(embed=error)

        if ctx.author != ctx.guild.owner and user.top_role >= ctx.author.top_role:
            error = discord.Embed(color=self.color, description="You can't timeout users having higher or equal role than yours!")
            error.set_author(name="Error Timing Out User")
            error.set_footer(text=f"Requested by {ctx.author}", icon_url=self.get_user_avatar(ctx.author))
            return await ctx.send(embed=error)

        if user.top_role >= ctx.guild.me.top_role:
            error = discord.Embed(color=self.color, description="I can't timeout users having higher or equal role than mine.")
            error.set_author(name="Error Timing Out User")
            error.set_footer(text=f"Requested by {ctx.author}", icon_url=self.get_user_avatar(ctx.author))
            return await ctx.send(embed=error)

        time_delta, duration_text = self.parse_time(time) if time else (timedelta(hours=24), "24 hours")

        if not time_delta:
            error = discord.Embed(color=self.color, description="Invalid time format! Use one of these formats:\n• `5m` (5 minutes, max 40320m)\n• `2h` (2 hours, max 672h)\n• `1d` (1 day, max 28d)\n\n**Examples:** `mute @user 30m`, `mute @user 2h spam`, `mute @user 1d breaking rules`")
            error.set_author(name="Error Timing Out User")
            error.set_footer(text=f"Requested by {ctx.author}", icon_url=self.get_user_avatar(ctx.author))
            return await ctx.send(embed=error)

        try:
            await user.send(f"<:feast_warning:1400143131990560830> You have been muted in **{ctx.guild.name}** by **{ctx.author}** for {duration_text}. Reason: {reason or 'None'}")
            dm_status = "Yes"
        except discord.Forbidden:
            dm_status = "No"
        except discord.HTTPException:
            dm_status = "No"

        try:
            # Calculate timeout end time with proper validation
            timeout_end = self.tz_helpers.get_utc_now() + time_delta
            
            # Ensure the timeout doesn't exceed Discord's 28-day limit
            max_timeout = self.tz_helpers.get_utc_now() + timedelta(days=28)
            if timeout_end > max_timeout:
                timeout_end = max_timeout
                duration_text = "28 days (maximum)"
            
            # Ensure the timeout is in the future (add a small buffer)
            min_timeout = self.tz_helpers.get_utc_now() + timedelta(seconds=10)
            if timeout_end <= min_timeout:
                timeout_end = min_timeout
                duration_text = "10 seconds (minimum)"
            
            await user.edit(timed_out_until=timeout_end, reason=f"Muted by {ctx.author} for {duration_text}. Reason: {reason or 'None'}")
            mute_success = True
        except discord.Forbidden:
            error = discord.Embed(color=self.color, description="I don't have permission to timeout this user.")
            error.set_author(name="Error Timing Out User")
            error.set_footer(text=f"Requested by {ctx.author}", icon_url=self.get_user_avatar(ctx.author))
            return await ctx.send(embed=error)
        except discord.HTTPException as e:
            error = discord.Embed(color=self.color, description=f"Failed to timeout user: {str(e)}")
            error.set_author(name="Error Timing Out User")
            error.set_footer(text=f"Requested by {ctx.author}", icon_url=self.get_user_avatar(ctx.author))
            return await ctx.send(embed=error)

        embed = discord.Embed(description=f"** Target User:** [{user}](https://discord.com/users/{user.id})\n"
                                          f" **User Mention:** {user.mention}\n"
                                          f"**DM Sent:** {dm_status}\n"
                                          f"** Reason:** {reason or 'None'}\n"
                                          f"** Duration:** {duration_text}",
                              color=self.color)
        embed.set_author(name=f"Successfully Muted {user.name}", icon_url=self.get_user_avatar(user))
        embed.add_field(name=" Moderator:", value=ctx.author.mention, inline=False)
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=self.get_user_avatar(ctx.author))
        embed.timestamp = self.tz_helpers.get_utc_now()

        view = TimeoutView(user=user, author=ctx.author, bot=self.bot)
        message = await ctx.send(embed=embed, view=view)
        view.message = message

        # Log mute event
        try:
            from utils.activity_logger import ActivityLogger
            activity_logger = ActivityLogger()
            await activity_logger.log(
                guild_id=ctx.guild.id,
                user_id=user.id,
                username=str(user),
                action=f"Muted by {ctx.author}",
                type_="moderation",
                details=f"Duration: {duration_text}, Reason: {reason or 'None'}"
            )
        except Exception as e:
                print(f"[ACTIVITY LOG] Failed to log mute: {e}")

    @mute.error
    async def mute_error(self, ctx, error):
        
        if isinstance(error, commands.BotMissingPermissions):
            embed = discord.Embed(title="<:feast_cross:1400143488695144609>> Access Denied", description="I don't have permission to mute members.", color=self.color)
            await ctx.send(embed=embed)
        elif isinstance(error, discord.Forbidden):
            embed = discord.Embed(title="<:feast_cross:1400143488695144609> Missing Permissions", description="I can't mute this user as they might have higher privileges (e.g., Admin).", color=self.color)
            await ctx.send(embed=embed)
            
        else:
            embed = discord.Embed(title="<:feast_cross:1400143488695144609> Unexpected Error", description=str(error), color=self.color)
            await ctx.send(embed=embed)


# Author: Frosty
# Discord: frosty.pyro
# Community: https://discord.gg/5wtjDkYbVh (Sleepless Development)
# For any queries reach out in the server or send a DM.

# Extension loader for Discord.py
async def setup(bot):
    await bot.add_cog(Mute(bot))