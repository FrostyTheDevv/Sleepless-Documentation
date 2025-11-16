import discord
from discord.ext import commands
from discord import ui
from utils.Tools import *
from utils.timezone_helpers import get_timezone_helpers
import typing

class BanView(ui.View):
    def __init__(self, user, author, tz_helpers=None):
        super().__init__(timeout=120)
        self.user = user
        self.author = author
        self.message = None  
        self.color = discord.Color.from_rgb(0, 0, 0)
        self.tz_helpers = tz_helpers

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("You are not allowed to interact with this!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        import discord
        import inspect
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        if self.message:
            try:
                edit_func = getattr(self.message, 'edit', None)
                if edit_func and inspect.iscoroutinefunction(edit_func):
                    await edit_func(view=self)
                elif edit_func:
                    edit_func(view=self)
            except Exception:
                pass

    @ui.button(label="Unban", style=discord.ButtonStyle.success)
    async def unban(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ReasonModal(user=self.user, author=self.author, view=self, tz_helpers=self.tz_helpers)
        await interaction.response.send_modal(modal)

    @ui.button(style=discord.ButtonStyle.gray, emoji="<:feast_delete:1400140670659989524>")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        import inspect
        msg = getattr(interaction, 'message', None)
        delete_func = getattr(msg, 'delete', None)
        if delete_func and inspect.iscoroutinefunction(delete_func):
            await delete_func()
        elif delete_func:
            delete_func()

class AlreadyBannedView(ui.View):
    def __init__(self, user, author, tz_helpers=None):
        super().__init__(timeout=120)
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
        import discord
        import inspect
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        if self.message:
            edit_func = getattr(self.message, 'edit', None)
            if edit_func and inspect.iscoroutinefunction(edit_func):
                await edit_func(view=self)
            elif edit_func:
                edit_func(view=self)

    @ui.button(label="Unban", style=discord.ButtonStyle.success)
    async def unban(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ReasonModal(user=self.user, author=self.author, view=self, tz_helpers=self.tz_helpers)
        await interaction.response.send_modal(modal)

    @ui.button(style=discord.ButtonStyle.gray, emoji="<:feast_delete:1400140670659989524>")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        import inspect
        msg = getattr(interaction, 'message', None)
        delete_func = getattr(msg, 'delete', None)
        if delete_func and inspect.iscoroutinefunction(delete_func):
            await delete_func()
        elif delete_func:
            delete_func()

class ReasonModal(ui.Modal):
    def __init__(self, user, author, view, tz_helpers=None):
        super().__init__(title="Unban Reason")
        self.user = user
        self.author = author
        self.view = view
        self.tz_helpers = tz_helpers
        self.reason_input = ui.TextInput(label="Reason for Unbanning", placeholder="Provide a reason to unban or leave it blank for no reason.", required = False, max_length=2000, style=discord.TextStyle.paragraph)
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        reason = self.reason_input.value or "No reason provided"
        try:
            await self.user.send(f"<:feast_tick:1400143469892210753> You have been Unbanned from **{getattr(getattr(self.author, 'guild', None), 'name', 'Unknown Guild')}** by **{self.author}**. Reason: {reason or 'No reason provided'}")
            dm_status = "Yes"
        except (discord.Forbidden, discord.HTTPException):
            dm_status = "No"

        embed = discord.Embed(description=f"**<:user:1329379728603353108> Target User:** [{self.user}](https://discord.com/users/{self.user.id})\n<a:mention:1329408091011285113> **User Mention:** {self.user.mention}\n**<:feast_tick:1400143469892210753> DM Sent:** {dm_status}\n**<:Commands:1329004882992300083> Reason:** {reason}", color=0x006fb9)
        embed.set_author(name=f"Successfully Unbanned {getattr(self.user, 'name', str(self.user))}", icon_url=getattr(getattr(self.user, 'avatar', None), 'url', None) or getattr(getattr(self.user, 'default_avatar', None), 'url', None))
        embed.add_field(name="<:U_admin:1327829252120510567> Moderator:", value=interaction.user.mention, inline=False)
        embed.set_footer(text=f"Requested by {self.author}", icon_url=getattr(getattr(self.author, 'avatar', None), 'url', None) or getattr(getattr(self.author, 'default_avatar', None), 'url', None))
        embed.timestamp = self.tz_helpers.get_utc_now() if self.tz_helpers else discord.utils.utcnow()

        import inspect
        guild = getattr(interaction, 'guild', None)
        if guild and hasattr(guild, 'unban') and callable(guild.unban):
            try:
                unban_func = guild.unban
                if inspect.iscoroutinefunction(unban_func):
                    await unban_func(self.user, reason=f"Unban requested by {self.author}")
                else:
                    unban_func(self.user, reason=f"Unban requested by {self.author}")
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass

        try:
            await interaction.response.edit_message(embed=embed, view=self.view)
            for item in getattr(self.view, 'children', []):
                if hasattr(item, 'disabled'):
                    item.disabled = True
            msg = getattr(interaction, 'message', None)
            if msg and hasattr(msg, 'edit') and callable(msg.edit):
                edit_func = msg.edit
                if inspect.iscoroutinefunction(edit_func):
                    await edit_func(view=self.view)
                else:
                    edit_func(view=self.view)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass
        
        

class Ban(commands.Cog):

    async def _send_response(self, ctx, *args, **kwargs):
        """
        Helper to send a response that works for both prefix and slash/hybrid commands.
        Uses interaction response if available, otherwise falls back to ctx.send.
        """
        if hasattr(ctx, 'interaction') and ctx.interaction is not None and not ctx.interaction.response.is_done():
            return await ctx.interaction.response.send_message(*args, **kwargs)
        else:
            return await ctx.send(*args, **kwargs)

    def __init__(self, bot):
        self.bot = bot
        self.tz_helpers = get_timezone_helpers(bot)
        self.color = discord.Color.from_rgb(0, 0, 0)

    def get_user_avatar(self, user):
        return user.avatar.url if user.avatar else user.default_avatar.url

    @commands.hybrid_command(
        name="ban",
        help="Bans a user from the Server",
        usage="ban <member> [reason]",
        aliases=["fuckban", "hackban"])
    @blacklist_check()
    @ignore_check()
    @top_check()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def ban(self, ctx, user: typing.Union[discord.User, None] = None, *, reason=None):
        """
        Ban a user from the server.
        Usage: ban <member> [reason]
        """
        # Check if user parameter is provided
        if user is None:
            embed = discord.Embed(
                title="❌ Missing Parameter",
                description="Please provide a user to ban.\n\n**Usage:** `ban <user> [reason]`\n**Example:** `ban @user spamming`",
                color=0xFF6B6B
            )
            await self._send_response(ctx, embed=embed)
            return
            
        member = ctx.guild.get_member(user.id)
        if not member:
            try:
                user = await self.bot.fetch_user(user.id)
            except discord.NotFound:
                embed = discord.Embed(
                    title="❌ User Not Found",
                    description=f"User with ID `{user.id}` was not found.",
                    color=0xFF6B6B
                )
                await self._send_response(ctx, embed=embed)
                return
        
        # Assert for type checker - user is guaranteed to not be None here
        assert user is not None

        bans = [entry async for entry in ctx.guild.bans()]
        if any(ban_entry.user.id == user.id for ban_entry in bans):
            embed = discord.Embed(description=f"**Requested User is already banned in this server.**", color=self.color)
            embed.add_field(name="__Unban__:", value="Click on the `Unban` button to unban the mentioned user.")
            embed.set_author(name=f"{user.name} is Already Banned!", icon_url=self.get_user_avatar(user))
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=self.get_user_avatar(ctx.author))
            view = AlreadyBannedView(user=user, author=ctx.author)
            message = await self._send_response(ctx, embed=embed, view=view)
            view.message = message 
            return

        if member == ctx.guild.owner:
            error = discord.Embed(color=self.color, description="I can't ban the Server Owner!")
            error.set_author(name="Error Banning User", icon_url="https://cdn.discordapp.com/attachments/1329411292532051999/1329451540028719255/Feast_X.jpeg?ex=678a63bb&is=6789123b&hm=917647b44f40b887260074c1ccc602f0b7b8f4054c18ccc5ab6a5824bf77a9aa&")
            error.set_footer(text=f"Requested by {ctx.author}", icon_url=self.get_user_avatar(ctx.author))
            return await self._send_response(ctx, embed=error)

        if isinstance(member, discord.Member) and member.top_role >= ctx.guild.me.top_role:
            error = discord.Embed(color=self.color, description="I can't ban a user with a higher or equal role!")
            error.set_footer(text=f"Requested by {ctx.author}", icon_url=self.get_user_avatar(ctx.author))
            error.set_author(name="Error Banning User", icon_url="https://cdn.discordapp.com/attachments/1329411292532051999/1329451540028719255/Feast_X.jpeg?ex=678a63bb&is=6789123b&hm=917647b44f40b887260074c1ccc602f0b7b8f4054c18ccc5ab6a5824bf77a9aa&")
            return await self._send_response(ctx, embed=error)

        if isinstance(member, discord.Member):
            if ctx.author != ctx.guild.owner:
                if member.top_role >= ctx.author.top_role:
                    error = discord.Embed(color=self.color, description="You can't ban a user with a higher or equal role!")
                    error.set_footer(text=f"Requested by {ctx.author}", icon_url=self.get_user_avatar(ctx.author))
                    error.set_author(name="Error Banning User", icon_url="https://cdn.discordapp.com/attachments/1329411292532051999/1329451540028719255/Feast_X.jpeg?ex=678a63bb&is=6789123b&hm=917647b44f40b887260074c1ccc602f0b7b8f4054c18ccc5ab6a5824bf77a9aa&")
                    return await self._send_response(ctx, embed=error)

        try:
            await user.send(f"⚠️ You have been banned from **{ctx.guild.name}** by **{ctx.author}**. Reason: {reason or 'No reason provided'}")
            dm_status = "Yes"
        except discord.Forbidden:
            dm_status = "No"
        except discord.HTTPException:
            dm_status = "No"

        await ctx.guild.ban(user, reason=f"Ban requested by {ctx.author} for reason: {reason or 'No reason provided'}")
        
        # Add reaction to show command completed
        try:
            await ctx.message.add_reaction("✅")
        except:
            pass

        reasonn = reason or "No reason provided"
        embed = discord.Embed(description=f"**👤 Target User:** [{user}](https://discord.com/users/{user.id})\n**📢 User Mention:** {user.mention}\n**✅ DM Sent:** {dm_status}\n**📝 Reason:** {reasonn}", color=0x00FF00)
        embed.set_author(name=f"Successfully Banned {user.name}", icon_url=self.get_user_avatar(user))
        embed.add_field(name="👮 Moderator:", value=ctx.author.mention, inline=False)
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=self.get_user_avatar(ctx.author))
        embed.timestamp = self.tz_helpers.get_utc_now()

        await self._send_response(ctx, embed=embed)

        # Log ban event
        try:
            from utils.activity_logger import ActivityLogger
            activity_logger = ActivityLogger()
            await activity_logger.log(
                guild_id=ctx.guild.id,
                user_id=user.id,
                username=str(user),
                action=f"Banned by {ctx.author}",
                type_="moderation",
                details=reasonn
            )
        except Exception as e:
            print(f"[ACTIVITY LOG] Failed to log ban: {e}")





"""
@Author: Frosty
    + Discord: frosty.pyro
    + Community: https://discord.gg/5wtjDkYbVh (Sleepless Development)
    + for any queries reach out in the server; or send a dm.
"""