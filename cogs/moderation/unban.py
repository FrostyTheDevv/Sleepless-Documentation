import discord
from discord.ext import commands
from discord import ui
from utils.Tools import *
from utils.timezone_helpers import get_timezone_helpers
import inspect

class BanView(ui.View):
    def __init__(self, user, author, tz_helpers):
        super().__init__(timeout=120)
        self.user = user
        self.author = author
        self.tz_helpers = tz_helpers
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
        if self.message:
            try:
                edit_method = getattr(self.message, "edit", None)
                if edit_method:
                    if callable(edit_method):
                        result = edit_method(view=self)
                        if inspect.isawaitable(result):
                            await result
            except Exception:
                pass

    @ui.button(label="Ban", style=discord.ButtonStyle.danger)
    async def ban(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ReasonModal(user=self.user, author=self.author, view=self, tz_helpers=self.tz_helpers)
        await interaction.response.send_modal(modal)

    @ui.button(style=discord.ButtonStyle.gray, emoji="<:feast_delete:1400140670659989524>")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        msg = getattr(interaction, "message", None)
        if msg:
            delete_method = getattr(msg, "delete", None)
            if callable(delete_method):
                result = delete_method()
                if inspect.isawaitable(result):
                    await result

class AlreadyUnbannedView(ui.View):
    def __init__(self, user, author, tz_helpers):
        super().__init__(timeout=60)
        self.user = user
        self.author = author
        self.tz_helpers = tz_helpers
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
        if self.message:
            edit_method = getattr(self.message, "edit", None)
            if edit_method:
                if callable(edit_method):
                    result = edit_method(view=self)
                    if inspect.isawaitable(result):
                        await result

    @ui.button(label="Ban", style=discord.ButtonStyle.danger)
    async def ban(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ReasonModal(user=self.user, author=self.author, view=self, tz_helpers=self.tz_helpers)
        await interaction.response.send_modal(modal)

    @ui.button(style=discord.ButtonStyle.gray, emoji="<:feast_delete:1400140670659989524>")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        msg = getattr(interaction, "message", None)
        if msg:
            delete_method = getattr(msg, "delete", None)
            if callable(delete_method):
                result = delete_method()
                if inspect.isawaitable(result):
                    await result

class ReasonModal(ui.Modal):
    def __init__(self, user, author, view, tz_helpers):
        super().__init__(title="Ban Reason")
        self.user = user
        self.author = author
        self.view = view
        self.tz_helpers = tz_helpers
        self.reason_input = ui.TextInput(label="Reason for Banning", placeholder="Provide a reason for banning or leave it blank for no reason.", required = False, max_length=2000, style=discord.TextStyle.paragraph)
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        reason = self.reason_input.value or "No reason provided"
        try:
            await self.user.send(f"<:feast_warning:1400143131990560830> You have been Banned from **{self.author.guild.name}** by **{self.author}**. Reason: {reason or 'No reason provided'}")
            dm_status = "Yes"
        except discord.Forbidden:
            dm_status = "No"
        except discord.HTTPException:
            dm_status = "No"

        embed = discord.Embed(description=f"** Target User:** [{self.user}](https://discord.com/users/{self.user.id})\n **User Mention:** {self.user.mention}\n** DM Sent:** {dm_status}\n** Reason:** {reason}", color=0x006fb9)
        embed.set_author(name=f"Successfully Banned {self.user.name}", icon_url=self.user.avatar.url if self.user.avatar else self.user.default_avatar.url)
        embed.add_field(name=" Moderator:", value=interaction.user.mention, inline=False)
        embed.set_footer(text=f"Requested by {self.author}", icon_url=self.author.avatar.url if self.author.avatar else self.author.default_avatar.url)
        embed.timestamp = self.tz_helpers.get_utc_now()

        guild = getattr(interaction, "guild", None)
        if guild:
            ban_method = getattr(guild, "ban", None)
            if callable(ban_method):
                try:
                    result = ban_method(self.user, reason=f"Ban requested by {self.author}")
                    if inspect.isawaitable(result):
                        await result
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    pass

        try:
            edit_message_method = getattr(interaction.response, "edit_message", None)
            if callable(edit_message_method):
                result = edit_message_method(embed=embed, view=self.view)
                if inspect.isawaitable(result):
                    await result
            for item in self.view.children:
                if isinstance(item, (discord.ui.Button, discord.ui.Select)):
                    item.disabled = True
            msg = getattr(interaction, "message", None)
            if msg:
                edit_method = getattr(msg, "edit", None)
                if callable(edit_method):
                    result = edit_method(view=self.view)
                    if inspect.isawaitable(result):
                        await result
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass
            

class Unban(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tz_helpers = get_timezone_helpers(bot)
        self.color = discord.Color.from_rgb(0, 0, 0)

    def get_user_avatar(self, user):
        return user.avatar.url if user.avatar else user.default_avatar.url

    @commands.hybrid_command(
        name="unban",
        help="Unbans a user from the Server",
        usage="unban <member>",
        aliases=["forgive", "pardon"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def unban(self, ctx, user: discord.User, *, reason=None):
        bans = [entry async for entry in ctx.guild.bans()]
        if not any(ban_entry.user.id == user.id for ban_entry in bans):
            embed = discord.Embed(description="**Requested User is not banned in this server.**", color=self.color)
            embed.add_field(name="__Ban__:", value="Click on the `Ban` button to ban the mentioned user.")
            embed.set_author(name=f"{user.name} is Not Banned!", icon_url=self.get_user_avatar(user))
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=self.get_user_avatar(ctx.author))
            view = AlreadyUnbannedView(user=user, author=ctx.author, tz_helpers=self.tz_helpers)
            message = await ctx.send(embed=embed, view=view)
            view.message = message 
            return

        try:
            await user.send(f"<:feast_tick:1400143469892210753> You have been unbanned from **{ctx.guild.name}** by **{ctx.author}**. Reason: {reason or 'No reason provided'}")
            dm_status = "Yes"
        except discord.Forbidden:
            dm_status = "No"
        except discord.HTTPException:
            dm_status = "No"

        await ctx.guild.unban(user, reason=f"Unban requested by {ctx.author} for reason: {reason or 'No reason provided'}")

        reasonn = reason or "No reason provided"
        embed = discord.Embed(description=f"** Target User:** [{user}](https://discord.com/users/{user.id})\n**User Mention:** {user.mention}\n** DM Sent:** {dm_status}\n**Reason:** {reasonn}", color=self.color)
        embed.set_author(name=f"Successfully Unbanned {user.name}", icon_url=self.get_user_avatar(user))
        embed.add_field(name=" Moderator:", value=ctx.author.mention, inline=False)
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=self.get_user_avatar(ctx.author))
        embed.timestamp = self.tz_helpers.get_utc_now()

        view = BanView(user=user, author=ctx.author, tz_helpers=self.tz_helpers)
        message = await ctx.send(embed=embed, view=view)
        view.message = message


"""
@Author: Frosty
    + Discord: frosty.pyro
    + Community: https://discord.gg/5wtjDkYbVh (Sleepless Development)
    + for any queries reach out in the server; or send a dm.
"""