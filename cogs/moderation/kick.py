import discord
from discord.ext import commands
from discord import ui
from utils.Tools import *
from utils.timezone_helpers import get_timezone_helpers
import typing

class KickView(ui.View):
    def __init__(self, member):
        super().__init__(timeout=120)
        self.member = member
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return True

    async def on_timeout(self):
        for item in self.children:
            if hasattr(item, 'disabled'):
                try:
                    item.disabled = True  # type: ignore[attr-defined]
                except Exception:
                    pass
        if self.message and hasattr(self.message, 'edit') and callable(self.message.edit):
            import inspect
            edit_func = self.message.edit
            try:
                edit_func(view=self)
            except Exception:
                pass

    @ui.button(style=discord.ButtonStyle.gray, emoji="<:delete:1397550174280351775>")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.message:
            await interaction.message.delete()

class Kick(commands.Cog):

    async def _send_response(self, ctx, *args, **kwargs):
        """
        Helper to send a response that works for both prefix and slash/hybrid commands.
        Uses interaction response if available, otherwise falls back to ctx.send/ctx.reply.
        """
        if hasattr(ctx, 'interaction') and ctx.interaction is not None and not ctx.interaction.response.is_done():
            return await ctx.interaction.response.send_message(*args, **kwargs)
        elif hasattr(ctx, 'reply'):
            return await ctx.reply(*args, **kwargs)
        else:
            return await ctx.send(*args, **kwargs)

    def __init__(self, bot):
        self.bot = bot
        self.tz_helpers = get_timezone_helpers(bot)
        self.color = discord.Color.from_rgb(0, 0, 0)

    @commands.hybrid_command(
        name="kick",
        help="Kicks a member from the server.",
        usage="kick <member> [reason]",
        aliases=["kickmember"])
    @blacklist_check()
    @ignore_check()
    @top_check()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    @commands.guild_only()
    async def kick(self, ctx, member: discord.Member, *, reason: typing.Optional[str] = None):
        """
        Kick a member from the server.
        Usage: kick <member> [reason]
        """
        reason = reason or "No reason provided"

        if member == ctx.author:
            return await self._send_response(ctx, "You cannot kick yourself.")

        if member == ctx.bot.user:
            return await self._send_response(ctx, "You cannot kick me.")

        if ctx.author != ctx.guild.owner:
            if member == ctx.guild.owner:
                return await self._send_response(ctx, "I cannot kick the server owner.")
            if ctx.author.top_role <= member.top_role:
                return await self._send_response(ctx, "You cannot kick a member with a higher or equal role.")

        if ctx.guild.me.top_role <= member.top_role:
            return await self._send_response(ctx, "I cannot kick a member with a higher or equal role.")

        if member not in ctx.guild.members:
            embed = discord.Embed(
                description=f"**Member Not Found:** The specified member does not exist in this server.",
                color=self.color
            )
            view = KickView(member)
            message = await self._send_response(ctx, embed=embed, view=view)
            view.message = message
            return

        dm_status = "Yes"
        try:
            await member.send(f"You have been kicked from **{ctx.guild.name}**. Reason: {reason}")
        except discord.Forbidden:
            dm_status = "No"
        except discord.HTTPException:
            dm_status = "No"

        await member.kick(reason=f"Kicked by {ctx.author} | Reason: {reason}")

        embed = discord.Embed(
            description=(
                f"**<:user:1329379728603353108> Target User:** [{member}](https://discord.com/users/{member.id})\n"
                f"<a:mention:1329408091011285113> **User Mention:** {member.mention}\n"
                f"<:Commands:1329004882992300083> **Reason:** {reason}\n"
                f"<:feast_tick:1400143469892210753>**DM Sent:** {dm_status}"
            ),
            color=self.color
        )
        embed.set_author(name=f"Successfully Kicked {str(member.name)}", icon_url=member.avatar.url if member.avatar else member.default_avatar.url)
        embed.add_field(name="<:U_admin:1327829252120510567> Moderator:", value=ctx.author.mention, inline=False)
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        embed.timestamp = self.tz_helpers.get_utc_now()

        # Log kick event
        try:
            from utils.activity_logger import ActivityLogger
            activity_logger = ActivityLogger()
            await activity_logger.log(
                guild_id=ctx.guild.id,
                user_id=member.id,
                username=str(member),
                action=f"Kicked by {ctx.author}",
                type_="moderation",
                details=reason
            )
        except Exception as e:
            print(f"[ACTIVITY LOG] Failed to log kick: {e}")




"""
@Author: Frosty
    + Discord: frosty.pyro
    + Community: https://discord.gg/5wtjDkYbVh (Sleepless Development)
    + for any queries reach out in the server; or send a dm.
"""