import os 
import discord
from discord.ext import commands
import datetime
import sys
from discord.ui import Button, View
import psutil
import time
import re
from utils.Tools import *
from utils.timezone_helpers import get_timezone_helpers
from discord.ext import commands, menus
from discord.ext.commands import BucketType, cooldown
import requests
from typing import Optional, Union, List, Tuple, Any, Dict
from utils import *
from utils.config import BotName, serverLink
from utils import Paginator, DescriptionEmbedPaginator, FieldPagePaginator, TextPaginator
from core import Cog, sleepless, Context
from typing import Optional
import aiosqlite 
import asyncio
import aiohttp

start_time = time.time()

# Custom emojis for extra commands
EXTRA_EMOJIS = {
    "success": "<:feast_tick:1400143469892210753>",
    "error": "<:feast_cross:1400143488695144609>",
    "warning": "<:feast_warning:1400143131990560830>",
    "time": "<:feast_time:1400143469892210757>",
    "list": "<:web:1428162947187736679>",
    "settings": "<:Feast_Utility:1400135926298185769>",
    "test": "<:feast_piche:1400142845402284102>",
    "empty": "<:feast_warning:1400143131990560830>",
    "plus": "<:feast_plus:1400142875483836547>"
}


def datetime_to_seconds(thing: datetime.datetime):
  current_time = datetime.datetime.fromtimestamp(time.time())
  return round(
    round(time.time()) +
    (current_time - thing.replace(tzinfo=None)).total_seconds())

tick = "<:feast_tick:1400143469892210753>"
cross = "<:feast_cross:1400143488695144609>"


class ServerInfoPaginator(discord.ui.View):
    """Enhanced paginator for serverinfo with role pagination support"""
    
    def __init__(self, guild: discord.Guild, author: discord.Member, tz_helpers):
        super().__init__(timeout=180)
        self.guild = guild
        self.author = author
        self.tz_helpers = tz_helpers
        self.current_page = 0
        self.role_page = 0
        self.message = None
        
        # Prepare role pagination
        self.roles = list(reversed(guild.roles[1:]))  # Exclude @everyone, show highest first
        self.roles_per_page = 25  # Safe limit for embed
        self.total_role_pages = max(1, (len(self.roles) + self.roles_per_page - 1) // self.roles_per_page)
        
        # Calculate member stats
        self.bots = len([m for m in guild.members if m.bot])
        self.humans = len(guild.members) - self.bots
        
        # Calculate emoji stats
        self.regular_emojis = [emoji for emoji in guild.emojis if not emoji.animated]
        self.animated_emojis = [emoji for emoji in guild.emojis if emoji.animated]
        
        self.update_buttons()
        
    def update_buttons(self):
        """Update button states based on current page"""
        # Disable/enable main navigation buttons
        self.previous_main.disabled = (self.current_page == 0)
        self.next_main.disabled = (self.current_page == 2)
        
        # Show role pagination only on page 3 (roles page)
        if self.current_page == 2:  # Roles page
            self.previous_role.disabled = (self.role_page == 0)
            self.next_role.disabled = (self.role_page >= self.total_role_pages - 1)
            self.previous_role.style = discord.ButtonStyle.primary
            self.next_role.style = discord.ButtonStyle.primary
        else:
            self.previous_role.disabled = True
            self.next_role.disabled = True
            self.previous_role.style = discord.ButtonStyle.secondary
            self.next_role.style = discord.ButtonStyle.secondary
    
    def get_current_embed(self) -> discord.Embed:
        """Generate the embed for the current page"""
        guild = self.guild
        
        if self.current_page == 0:
            # Page 1: Overview
            created_timestamp = discord.utils.format_dt(guild.created_at, style='F')
            created_relative = discord.utils.format_dt(guild.created_at, style='R')
            
            embed = discord.Embed(color=0x006fb9, timestamp=self.tz_helpers.get_utc_now())
            embed.set_author(name=f"{guild.name}'s Information", icon_url=guild.icon.url if guild.icon else None)
            embed.set_footer(
                text=f"Page 1/3 • Requested by {self.author}",
                icon_url=self.author.avatar.url if self.author.avatar else self.author.default_avatar.url
            )
            if guild.icon:
                embed.set_thumbnail(url=guild.icon.url)
            
            embed.add_field(
                name="**__About__**",
                value=f"**Name:** {guild.name}\n**ID:** {guild.id}\n**Owner <:owner:1329041011984433185>:** {guild.owner} (<@{guild.owner_id}>)\n**Created At:** {created_timestamp}\n{created_relative}",
                inline=False
            )
            
            if guild.description:
                embed.add_field(name="**__Description__**", value=guild.description[:1024], inline=False)
            
            embed.add_field(
                name="**__Members__**",
                value=f"**Total:** {len(guild.members):,}\n**Humans:** {self.humans:,}\n**Bots:** {self.bots:,}",
                inline=True
            )
            embed.add_field(
                name="**__Channels__**",
                value=f"**Total:** {len(guild.channels)}\n**Text:** {len(guild.text_channels)}\n**Voice:** {len(guild.voice_channels)}\n**Categories:** {len(guild.categories)}",
                inline=True
            )
            embed.add_field(
                name="**__Boost Status__**",
                value=f"**Level:** {guild.premium_tier}\n**Boosts:** <:feast_booster:1400426437479235645> {guild.premium_subscription_count}\n**Boosters:** {len(guild.premium_subscribers)}",
                inline=True
            )
            
        elif self.current_page == 1:
            # Page 2: Stats & Features
            embed = discord.Embed(color=0x006fb9, timestamp=self.tz_helpers.get_utc_now())
            embed.set_author(name=f"{guild.name}'s Information", icon_url=guild.icon.url if guild.icon else None)
            embed.set_footer(
                text=f"Page 2/3 • Requested by {self.author}",
                icon_url=self.author.avatar.url if self.author.avatar else self.author.default_avatar.url
            )
            if guild.icon:
                embed.set_thumbnail(url=guild.icon.url)
            
            embed.add_field(
                name="**__General Stats__**",
                value=f"**Verification Level:** {str(guild.verification_level).title()}\n**Explicit Content Filter:** {str(guild.explicit_content_filter).replace('_', ' ').title()}\n**2FA Requirement:** {'Enabled' if guild.mfa_level else 'Disabled'}\n**Roles:** {len(guild.roles)}\n**Emojis:** {len(guild.emojis)}/200\n**Stickers:** {len(guild.stickers)}",
                inline=False
            )
            embed.add_field(
                name="**__Emoji Info__**",
                value=f"**Regular:** {len(self.regular_emojis)}/100\n**Animated:** {len(self.animated_emojis)}/100\n**Total:** {len(guild.emojis)}/200",
                inline=True
            )
            
            if guild.features:
                features_list = [f"<:feast_tick:1400143469892210753> {feature.replace('_', ' ').title()}" for feature in guild.features]
                features_text = "\n".join(features_list[:15])
                if len(features_list) > 15:
                    features_text += f"\n*...and {len(features_list) - 15} more*"
                embed.add_field(name=f"**__Features__ [{len(guild.features)}]**", value=features_text, inline=False)
                
        else:
            # Page 3: Roles (with pagination)
            embed = discord.Embed(color=0x006fb9, timestamp=self.tz_helpers.get_utc_now())
            embed.set_author(name=f"{guild.name}'s Information", icon_url=guild.icon.url if guild.icon else None)
            
            # Calculate role range for current role page
            start_idx = self.role_page * self.roles_per_page
            end_idx = min(start_idx + self.roles_per_page, len(self.roles))
            current_roles = self.roles[start_idx:end_idx]
            
            roles_display = ", ".join([role.mention for role in current_roles]) if current_roles else "No roles"
            
            # Update footer to show role pagination info
            footer_text = f"Page 3/3 • Role Page {self.role_page + 1}/{self.total_role_pages} • Requested by {self.author}"
            embed.set_footer(text=footer_text, icon_url=self.author.avatar.url if self.author.avatar else self.author.default_avatar.url)
            
            if guild.icon:
                embed.set_thumbnail(url=guild.icon.url)
            
            embed.add_field(
                name=f"**__Server Roles__ [{len(self.roles)} total • Showing {start_idx + 1}-{end_idx}]**",
                value=roles_display,
                inline=False
            )
            
            if guild.banner and self.role_page == 0:
                embed.set_image(url=guild.banner.url)
        
        return embed
    
    async def start(self, ctx):
        """Start the paginator"""
        try:
            embed = self.get_current_embed()
            self.message = await ctx.send(embed=embed, view=self)
        except discord.Forbidden:
            try:
                await ctx.send("❌ I don't have permission to send embeds in this channel.")
            except:
                pass
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the command author can use the buttons"""
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("This pagination menu is not for you!", ephemeral=True)
            return False
        return True
    
    @discord.ui.button(emoji="<:left:1428164942036729896>", style=discord.ButtonStyle.secondary, row=0)
    async def previous_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Previous main page"""
        self.current_page = max(0, self.current_page - 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_current_embed(), view=self)
    
    @discord.ui.button(emoji="<:right:1427471506287362068>", style=discord.ButtonStyle.secondary, row=0)
    async def next_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Next main page"""
        self.current_page = min(2, self.current_page + 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_current_embed(), view=self)
    
    @discord.ui.button(label="◀ Roles", style=discord.ButtonStyle.primary, row=1, disabled=True)
    async def previous_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Previous role page"""
        self.role_page = max(0, self.role_page - 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_current_embed(), view=self)
    
    @discord.ui.button(label="Roles ▶", style=discord.ButtonStyle.primary, row=1, disabled=True)
    async def next_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Next role page"""
        self.role_page = min(self.total_role_pages - 1, self.role_page + 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_current_embed(), view=self)
    
    async def on_timeout(self):
        """Remove buttons when view times out"""
        if self.message:
            try:
                await self.message.edit(view=None)
            except:
                pass


class RoleInfoView(View):
  def __init__(self, role: discord.Role, author_id):
    super().__init__(timeout=180)
    self.role = role
    self.author_id = author_id

  @discord.ui.button(label='Show Permissions',  emoji="<:Commands:1329004882992300083>", style=discord.ButtonStyle.secondary)
  async def show_permissions(self, interaction: discord.Interaction, button: Button):
    if interaction.user.id != self.author_id:
          await interaction.response.send_message("Uh oh! That message doesn't belong to you. You must run this command to interact with it.", ephemeral=True)
          return

    permissions = [perm.replace("_", " ").title() for perm, value in self.role.permissions if value]
    permission_text = ", ".join(permissions) if permissions else "None"
    embed = discord.Embed(title=f"Permissions for {self.role.name}", description=permission_text or "No permissions.", color=self.role.color)
    await interaction.response.send_message(embed=embed, ephemeral=True)

    
class OverwritesView(View):
  def __init__(self, channel, author_id):
      super().__init__(timeout=180)
      self.channel = channel
      self.author_id = author_id

  @discord.ui.button(label='Show Overwrites', style=discord.ButtonStyle.primary)
  async def show_overwrites(self, interaction: discord.Interaction, button: Button):
      if interaction.user.id != self.author_id:
          await interaction.response.send_message("Uh oh! That message doesn't belong to you. You must run this command to interact with it.", ephemeral=True)
          return

      overwrites = []
      for target, perms in self.channel.overwrites.items():
          permissions = {
              "View Channel": perms.view_channel,
              "Send Messages": perms.send_messages,
              "Read Message History": perms.read_message_history,
              "Manage Messages": perms.manage_messages,
              "Embed Links": perms.embed_links,
              "Attach Files": perms.attach_files,
              "Manage Channels": perms.manage_channels,
              "Manage Permissions": perms.manage_permissions,
              "Manage Webhooks": perms.manage_webhooks,
              "Create Instant Invite": perms.create_instant_invite,
              "Add Reactions": perms.add_reactions,
              "Mention Everyone": perms.mention_everyone,
              "Kick Members": perms.kick_members,
              "Ban Members": perms.ban_members,
              "Moderate Members": perms.moderate_members,
              "Send TTS Messages": perms.send_tts_messages,
              "Use External Emojis": perms.external_emojis,
              "Use External Stickers": perms.external_stickers,
              "View Audit Log": perms.view_audit_log,
              "Voice Mute Members": perms.mute_members,
              "Voice Deafen Members": perms.deafen_members,
              "Administrator": perms.administrator
          }

          overwrites.append(f"**For {target.name}**\n" +
                            "\n".join(f"  * **{perm}:** {'<:feast_tick:1400143469892210753>' if value else '<:feast_cross:1400143488695144609>' if value is False else '⛔'}" for perm, value in permissions.items()))

      embed = discord.Embed(title=f"Overwrites for {self.channel.name}", color=discord.Color.blurple())
      embed.description = "\n".join(overwrites) if overwrites else "No overwrites for this channel."
      embed.set_footer(text="<:feast_tick:1400143469892210753> = Allowed, <:feast_cross:1400143488695144609> = Denied, ⛔ = None")
      await interaction.response.send_message(embed=embed, ephemeral=True)




class Extra(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        self.color = 0x006fb9
        self.start_time = datetime.datetime.now(datetime.timezone.utc)  # Store start time in UTC
        self.tz_helpers = get_timezone_helpers(bot)

    @commands.hybrid_group(name="banner")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def banner(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @banner.command(name="server")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def server(self, ctx):
        if not ctx.guild.banner:
            await ctx.reply(f"{cross} This server doesn't have a banner.")
        else:
            webp = ctx.guild.banner.replace(format='webp')
            jpg = ctx.guild.banner.replace(format='jpg')
            png = ctx.guild.banner.replace(format='png')
            embed = discord.Embed(
                color=int(self.color) if not isinstance(self.color, discord.Colour) else self.color,
                description=f"[`PNG`]({png}) | [`JPG`]({jpg}) | [`WEBP`]({webp})"
                if not ctx.guild.banner.is_animated() else
                f"[`PNG`]({png}) | [`JPG`]({jpg}) | [`WEBP`]({webp}) | [`GIF`]({ctx.guild.banner.replace(format='gif')})"
            )
            embed.set_image(url=ctx.guild.banner)
            embed.set_author(name=ctx.guild.name,
                icon_url=ctx.guild.icon.url
                if ctx.guild.icon else ctx.guild.default_icon.url)
            embed.set_footer(text=f"Requested By {ctx.author}",
                icon_url=ctx.author.avatar.url
                if ctx.author.avatar else ctx.author.default_avatar.url)
            await ctx.reply(embed=embed)

    @banner.command(name="user")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    async def _user(self,
            ctx,
            member: Optional[Union[discord.Member,
            discord.User]] = None):
        if member is None or member == "":
            member = ctx.author
        member_id = getattr(member, 'id', None)
        if member_id is None:
            await ctx.reply(f"{cross} Could not resolve user.")
            return
        bannerUser = await self.bot.fetch_user(member_id)
        if not getattr(bannerUser, 'banner', None):
            await ctx.reply(f"{cross} | {member} doesn't have a banner.")
            return
        webp = bannerUser.banner.replace(format='webp')
        jpg = bannerUser.banner.replace(format='jpg')
        png = bannerUser.banner.replace(format='png')
        desc = (f"[`PNG`]({png}) | [`JPG`]({jpg}) | [`WEBP`]({webp})"
            if not bannerUser.banner.is_animated() else
            f"[`PNG`]({png}) | [`JPG`]({jpg}) | [`WEBP`]({webp}) | [`GIF`]({bannerUser.banner.replace(format='gif')})")
        avatar_url = getattr(member, 'avatar', None)
        default_avatar_url = getattr(member, 'default_avatar', None)
        embed = discord.Embed(
            color=int(self.color) if not isinstance(self.color, discord.Colour) else self.color,
            description=desc
        )
        embed.set_author(name=f"{member}",
            icon_url=avatar_url.url if avatar_url else (default_avatar_url.url if default_avatar_url else None))
        embed.set_image(url=bannerUser.banner)
        ctx_author_avatar = getattr(ctx.author, 'avatar', None)
        ctx_author_default_avatar = getattr(ctx.author, 'default_avatar', None)
        embed.set_footer(text=f"Requested By {ctx.author}",
            icon_url=ctx_author_avatar.url if ctx_author_avatar else (ctx_author_default_avatar.url if ctx_author_default_avatar else None))
        await ctx.reply(embed=embed)
        await ctx.reply(embed=embed)





    @commands.command(name="uptime", description="Shows the Bot's Uptime.")
    @blacklist_check() 
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def uptime(self, ctx):
        pfp = ctx.author.display_avatar.url

        uptime_seconds = int(round(time.time() - start_time))
        uptime_timedelta = datetime.timedelta(seconds=uptime_seconds)

        # Show uptime start in user's timezone
        start_dt = datetime.datetime.utcfromtimestamp(start_time)
        uptime_string_user = await self.tz_helpers.format_datetime_for_user_custom(
        start_dt, ctx.author, "%Y-%m-%d %H:%M:%S %Z"
        )

        # Add Discord timestamp for better display
        start_timestamp = discord.utils.format_dt(start_dt, style='F')  # Full date/time
        start_relative = discord.utils.format_dt(start_dt, style='R')   # Relative time

        uptime_duration_string = f"{uptime_timedelta.days} days, {uptime_timedelta.seconds // 3600} hours, {(uptime_timedelta.seconds // 60) % 60} minutes, {uptime_timedelta.seconds % 60} seconds"

        embed = discord.Embed(title=f"Sleepless Development Uptime", color=int(self.color) if not isinstance(self.color, discord.Colour) else self.color)
        embed.add_field(name="__Started At__", value=f"<:WarningIcon:1327829272697634937> {start_timestamp} ({start_relative})\n\n", inline=False)
        embed.add_field(name="__Online Duration__", value=f"<a:Uptime:1368920252871737444> {uptime_duration_string}", inline=False)
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=pfp)
        embed.timestamp = self.tz_helpers.get_utc_now()  # Add timestamp to show when command was run

        await ctx.send(embed=embed)



    @commands.hybrid_command(name="serverinfo",
        aliases=["sinfo", "si"],
        with_app_command=True)
    @blacklist_check() 
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def serverinfo(self, ctx):
        """Display detailed server information with pagination"""
        paginator = ServerInfoPaginator(ctx.guild, ctx.author, self.tz_helpers)
        await paginator.start(ctx)



    @commands.hybrid_command(name="userinfo",
        aliases=["whois", "ui"],
        usage="Userinfo [user]",
        with_app_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    async def _userinfo(self,
            ctx,
            member: Optional[Union[discord.Member,
            discord.User]] = None):
        if member is None or member == "":
            member = ctx.author
        is_guild_member = isinstance(member, discord.Member) and member in ctx.guild.members
        # If not a member, try to fetch as user
        if not is_guild_member:
            member_id = getattr(member, 'id', None)
            if member_id is not None:
                member = await self.bot.fetch_user(member_id)
            is_guild_member = False

        badges = ""
        public_flags = getattr(member, 'public_flags', None)
        if public_flags:
            if getattr(public_flags, 'hypesquad', False):
                badges += "HypeSquad Events, "
            if getattr(public_flags, 'hypesquad_balance', False):
                badges += "HypeSquad Balance, "
            if getattr(public_flags, 'hypesquad_bravery', False):
                badges += "HypeSquad Bravery, "
            if getattr(public_flags, 'hypesquad_brilliance', False):
                badges += "HypeSquad Brilliance, "
            if getattr(public_flags, 'early_supporter', False):
                badges += "Early Supporter, "
            if getattr(public_flags, 'active_developer', False):
                badges += "Active Developer, "
            if getattr(public_flags, 'verified_bot_developer', False):
                badges += "Early Verified Bot Developer, "
            if getattr(public_flags, 'discord_certified_moderator', False):
                badges += "Moderators Program Alumni, "
            if getattr(public_flags, 'staff', False):
                badges += "Discord Staff, "
            if getattr(public_flags, 'partner', False):
                badges += "Partnered Server Owner "
        if not badges:
            badges += f"{cross}"

        if is_guild_member and isinstance(member, discord.Member):
            nickk = getattr(member, 'nick', 'None') or 'None'
            if member.joined_at is not None:
                joined_timestamp = discord.utils.format_dt(member.joined_at, style='F')  # Full date/time
                joined_relative = discord.utils.format_dt(member.joined_at, style='R')   # Relative time
                joinedat = f"{joined_timestamp} ({joined_relative})"
            else:
                joinedat = 'None'
        else:
            nickk = "None"
            joinedat = "None"

        kp = ""
        if is_guild_member:
            guild_permissions = getattr(member, 'guild_permissions', None)
            if guild_permissions:
                perms = [
                    ('kick_members', 'Kick Members'),
                    ('ban_members', 'Ban Members'),
                    ('administrator', 'Administrator'),
                    ('manage_channels', 'Manage Channels'),
                    ('manage_guild', 'Manage Server'),
                    ('manage_messages', 'Manage Messages'),
                    ('mention_everyone', 'Mention Everyone'),
                    ('manage_roles', 'Manage Roles'),
                    ('manage_webhooks', 'Manage Webhooks'),
                    ('manage_emojis', 'Manage Emojis'),
                ]
                for attr, label in perms:
                    if getattr(guild_permissions, attr, False):
                        if kp:
                            kp += ' , '
                        kp += label
            if not kp:
                kp = "None"

        aklm = "Server Member"
        if is_guild_member:
            if member == getattr(ctx.guild, 'owner', None):
                aklm = "Server Owner"
            elif getattr(getattr(member, 'guild_permissions', None), 'administrator', False):
                aklm = "Server Admin"
            elif getattr(getattr(member, 'guild_permissions', None), 'ban_members', False) or getattr(getattr(member, 'guild_permissions', None), 'kick_members', False):
                aklm = "Server Moderator"

        member_id = getattr(member, 'id', None)
        bannerUser = await self.bot.fetch_user(member_id) if member_id else None
        embed = discord.Embed(color=int(self.color) if not isinstance(self.color, discord.Colour) else self.color)
        embed.timestamp = self.tz_helpers.get_utc_now()
        if bannerUser and getattr(bannerUser, 'banner', None):
            embed.set_image(url=bannerUser.banner)
        member_name = getattr(member, 'name', str(member))
        avatar = getattr(member, 'avatar', None)
        default_avatar = getattr(member, 'default_avatar', None)
        embed.set_author(name=f"{member_name}'s Information",
            icon_url=avatar.url if avatar else (default_avatar.url if default_avatar else None))
        embed.set_thumbnail(
            url=avatar.url if avatar else (default_avatar.url if default_avatar else None))
        member_bot = getattr(member, 'bot', False)
        created_at = getattr(member, 'created_at', None)
        if created_at and hasattr(created_at, 'timestamp'):
            created_timestamp = discord.utils.format_dt(created_at, style='F')  # Full date/time
            created_relative = discord.utils.format_dt(created_at, style='R')   # Relative time
            created_at_str = f"{created_timestamp} ({created_relative})"
        else:
            created_at_str = 'None'
        embed.add_field(name="__General Information__",
            value=f"""
            **Name:** {member_name}
            **ID:** {member_id if member_id else 'None'}
            **Nickname:** {nickk}
            **Bot?:** {'<:feast_tick:1400143469892210753> Yes' if member_bot else '<:feast_cross:1400143488695144609> No'}
            **Badges:** {badges}
            **Account Created:** {created_at_str}
            **Server Joined:** {joinedat}
            """,
            inline=False)
        if is_guild_member:
            roles = getattr(member, 'roles', [])
            r = (', '.join(role.mention for role in roles[1:][::-1]) if len(roles) > 1 else 'None.')
            top_role = getattr(member, 'top_role', None)
            color = getattr(member, 'color', '99aab5')
            embed.add_field(name="__Role Info__",
                value=f"""
                **Highest Role:** {top_role.mention if top_role and len(roles) > 1 else 'None'}
                **Roles [{f'{len(roles) - 1}' if roles else '0'}]:** {r if len(r) <= 1024 else r[0:1006] + ' and more...'}
                **Color:** {color}
                """,
                inline=False)
            premium_since = getattr(member, 'premium_since', None)
            if premium_since and hasattr(premium_since, 'timestamp'):
                premium_timestamp = discord.utils.format_dt(premium_since, style='F')  # Full date/time
                premium_relative = discord.utils.format_dt(premium_since, style='R')   # Relative time
                premium_str = f"{premium_timestamp} ({premium_relative})"
            else:
                premium_str = 'None'
            voice = getattr(member, 'voice', None)
            voice_channel = getattr(voice, 'channel', None)
            embed.add_field(
                name="__Extra__",
                value=f"**Boosting:** {premium_str if member in getattr(ctx.guild, 'premium_subscribers', []) else 'None'}\n**Voice :** {voice_channel.mention if voice_channel else 'None'}",
                inline=False)
            embed.add_field(name="__Key Permissions__",
                value=kp,
                inline=False)
            embed.add_field(name="__Acknowledgement__",
                value=f"{aklm}",
                inline=False)
            ctx_author_avatar = getattr(ctx.author, 'avatar', None)
            ctx_author_default_avatar = getattr(ctx.author, 'default_avatar', None)
            embed.set_footer(text=f"Requested by {ctx.author}",
                icon_url=ctx_author_avatar.url if ctx_author_avatar else (ctx_author_default_avatar.url if ctx_author_default_avatar else None))
        else:
            if member_id:
                ctx_author_avatar = getattr(ctx.author, 'avatar', None)
                ctx_author_default_avatar = getattr(ctx.author, 'default_avatar', None)
                embed.set_footer(text=f"{member_name} not in this server.",
                    icon_url=ctx_author_avatar.url if ctx_author_avatar else (ctx_author_default_avatar.url if ctx_author_default_avatar else None))
        await ctx.send(embed=embed)

    @commands.hybrid_command(name='roleinfo', aliases=["ri"], help="Displays information about a specified role.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def roleinfo(self, ctx, role: discord.Role):
        members = role.members
        created_at = await self.tz_helpers.format_datetime_for_user_custom(
            role.created_at, ctx.author, "%Y-%m-%d %H:%M:%S %Z"
        )

        # Add Discord timestamp for better display
        created_timestamp = discord.utils.format_dt(role.created_at, style='F')  # Full date/time
        created_relative = discord.utils.format_dt(role.created_at, style='R')   # Relative time
        role_created_display = f"{created_timestamp} ({created_relative})"

        embed = discord.Embed(
            title=f"Role Information - {role.name}",
            color=role.color,
            timestamp=self.tz_helpers.get_utc_now()
        )
        embed.add_field(name="__General Information__", value=f"**ID:** {role.id}\n**Name:** {role.name}\n**Mention:** <@&{role.id}>\n**Color:** {str(role.color)}\n**Total Member:** {len(role.members)}\n", inline=True)
        total_roles = len(ctx.guild.roles) - 0
        role_position = total_roles - role.position
        embed.add_field(name="Position", value=str(role_position), inline=True)
        embed.add_field(name="Mentionable", value=str(role.mentionable), inline=True)
        embed.add_field(name="Hoisted", value=str(role.hoist), inline=True)
        embed.add_field(name="Managed", value=str(role.managed), inline=True)
        embed.add_field(name="Created At", value=role_created_display, inline=True)
        embed.set_footer(text=f"Requested By {ctx.author}",
            icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)

        view = RoleInfoView(role, ctx.author.id)
        await ctx.send(embed=embed, view=view)





    @commands.command(name="boostcount",
        help="Shows boosts count",
        usage="boosts",
        aliases=["bco"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def boosts(self, ctx):
        await ctx.send(
        embed=discord.Embed(title=f"<:feast_booster:1400426437479235645> Boosts Count Of {ctx.guild.name}",
        description="**Total `%s` boosts**" %
        (ctx.guild.premium_subscription_count),
        color=self.color))

    @commands.hybrid_group(name="list",
            with_app_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def __list_(self, ctx: commands.Context):
        if ctx.subcommand_passed is None:
            await ctx.send_help(ctx.command)
            if ctx.command is not None:
                ctx.command.reset_cooldown(ctx)

    @__list_.command(name="boosters",
        aliases=["boost", "booster"],
        usage="List boosters",
        help="List of boosters in the Guild",
        with_app_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def list_boost(self, ctx):
        guild = ctx.guild
        entries = [
            (f"`#{no}.`", f"[{mem}](https://discord.com/users/{mem.id}) [{mem.mention}] - <t:{round(mem.premium_since.timestamp())}:R>")
            for no, mem in enumerate(guild.premium_subscribers, start=1)
        ]
        paginator = Paginator(source=DescriptionEmbedPaginator(
            entries=entries,
            title=
            f"List of Boosters in {guild.name} - {len(guild.premium_subscribers)}",
            description="",
            per_page=10),
            ctx=ctx)
        await paginator.paginate()

    @__list_.command(name="bans", help= "List of all banned members in Guild", aliases=["ban"], with_app_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(view_audit_log=True)
    @commands.bot_has_permissions(view_audit_log=True)
    async def list_ban(self, ctx):
        bans = [member async for member in ctx.guild.bans()]
        if len(bans) == 0:
            return await ctx.reply("There aren't any banned users in this guild.", mention_author=False)
        else:
            mems = ([
                member async for member in ctx.guild.bans()
            ])
            guild = ctx.guild
            entries = [
                (f"`#{no}.`", f"{mem}")
                for no, mem in enumerate(mems, start=1)
            ]
            paginator = Paginator(source=DescriptionEmbedPaginator(
                entries=entries,
                title=f"Banned Users in {guild.name} - {len(bans)}",
                description="",
                per_page=10),
                ctx=ctx)
        await paginator.paginate()

    @__list_.command(
        name="inrole",
        aliases=["inside-role"],
        help="List of members that are in the specified role",
        with_app_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def list_inrole(self, ctx, role: discord.Role):
        guild = ctx.guild
        entries = [
            (f"`#{no}.`", f"[{mem}](https://discord.com/users/{mem.id}) [{mem.mention}] - <t:{int(mem.created_at.timestamp())}:D>")
            for no, mem in enumerate(role.members, start=1)
        ]
        paginator = Paginator(source=DescriptionEmbedPaginator(
            entries=entries,
            title=f"List of Members in {role} - {len(role.members)}",
            description="",
            per_page=10),
            ctx=ctx)
        await paginator.paginate()

    @__list_.command(name="emojis",
        aliases=["emoji"],
        help="List of emojis in the Guild with ids",
        with_app_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def list_emojis(self, ctx):
        """Enhanced list emojis command with better error handling."""
        try:
            # Debug logging
            print(f"[LIST_EMOJIS] Command called by {ctx.author.id} in guild {ctx.guild.id if ctx.guild else 'DM'}")

            # Check if we're in a guild
            if not ctx.guild:
                embed = discord.Embed(
                    title=f"{EXTRA_EMOJIS['error']} Error",
                    description="This command can only be used in a server.",
                    color=0xff0000
                )
                await ctx.send(embed=embed)
                return

            guild = ctx.guild
            emojis = guild.emojis

            # Check if server has emojis
            if not emojis:
                embed = discord.Embed(
                    title=f"{EXTRA_EMOJIS['empty']} No Custom Emojis",
                    description=f"**{guild.name}** doesn't have any custom emojis yet.",
                    color=0xffa500
                )
                await ctx.send(embed=embed)
                return

            print(f"[LIST_EMOJIS] Found {len(emojis)} emojis in {guild.name}")

            # Create entries for pagination
            entries = []
            for no, emoji in enumerate(emojis, start=1):
                try:
                    # Create tuple pairs for DescriptionEmbedPaginator
                    entries.append((f"`#{no}.`", f"{emoji} - `{emoji}`"))
                except Exception as e:
                    print(f"[LIST_EMOJIS] Error processing emoji {emoji}: {e}")
                    entries.append((f"`#{no}.`", f"[Error displaying emoji] - `{emoji.name}:{emoji.id}`"))

            # Create paginator - removed try/catch that was causing fallback
            paginator = Paginator(source=DescriptionEmbedPaginator(
                entries=entries,
                title=f"{EXTRA_EMOJIS['list']} List of Emojis in {guild.name} - {len(emojis)}",
                description="",
                per_page=10),
                ctx=ctx)
            await paginator.paginate()
            print(f"[LIST_EMOJIS] Successfully sent emoji list for {guild.name}")

        except commands.CommandOnCooldown as e:
            embed = discord.Embed(
                title=f"{EXTRA_EMOJIS['time']} Cooldown",
                description=f"Please wait {e.retry_after:.1f} seconds before using this command again.",
                color=0xffa500
            )
            await ctx.send(embed=embed, ephemeral=True)

        except Exception as e:
            print(f"[LIST_EMOJIS] Unexpected error: {e}")
            import traceback
            traceback.print_exc()

            embed = discord.Embed(
                title=f"{EXTRA_EMOJIS['error']} Error",
                description=f"An unexpected error occurred: {str(e)[:1000]}",
                color=0xff0000
            )
            embed.set_footer(text="This error has been logged for review.")
            await ctx.send(embed=embed)

    @__list_.command(name="roles",
        aliases=["role"],
        help="List of all roles in the server with ids",
        with_app_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(manage_roles=True)
    async def list_roles(self, ctx):
        guild = ctx.guild
        entries = [
            (f"`#{no}.`", f"{e.mention} - `[{e.id}]`")
            for no, e in enumerate(ctx.guild.roles, start=1)
        ]
        paginator = Paginator(source=DescriptionEmbedPaginator(
            entries=entries,
            title=f"List of Roles in {guild.name} - {len(ctx.guild.roles)}",
            description="",
            per_page=10),
            ctx=ctx)
        await paginator.paginate()

    @__list_.command(name="bots",
        aliases=["bot"],
        help="List of All Bots in a server",
        with_app_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def list_bots(self, ctx):
        guild = ctx.guild
        people = list(filter(lambda member: member.bot, ctx.guild.members))
        people = sorted(people, key=lambda member: member.joined_at)

        # Format entries as tuples for DescriptionEmbedPaginator  
        entries = [
            (f"`#{no}.`", f"[{mem}](https://discord.com/users/{mem.id}) [{mem.mention}]")
            for no, mem in enumerate(people, start=1)
        ]

        paginator = Paginator(source=DescriptionEmbedPaginator(
            entries=entries,
            title=f"Bots in {guild.name} - {len(people)}",
            description="",
            per_page=10),
            ctx=ctx)
        await paginator.paginate()

    @__list_.command(name="admins",
        aliases=["admin"],
        help="List of all Admins of the Guild",
        with_app_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def list_admin(self, ctx):
        mems = ([
            mem for mem in ctx.guild.members
            if mem.guild_permissions.administrator
        ])
        mems = sorted(mems, key=lambda mem: not mem.bot)
        admins = len([
            mem for mem in ctx.guild.members
            if mem.guild_permissions.administrator
        ])
        guild = ctx.guild
        entries = [
            (f"`#{no}.`", f"[{mem}](https://discord.com/users/{mem.id}) [{mem.mention}] - <t:{int(mem.created_at.timestamp())}:D>")
            for no, mem in enumerate(mems, start=1)
        ]
        paginator = Paginator(source=DescriptionEmbedPaginator(
            entries=entries,
            title=f"Admins in {guild.name} - {admins}",
            description="",
            per_page=10),
            ctx=ctx)
        await paginator.paginate()

    @__list_.command(name="invoice", help="List of all users in a voice channel", aliases=["invc"], with_app_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def listusers(self, ctx):
        if not ctx.author.voice:
            return await ctx.send("You are not connected to a voice channel")
        members = ctx.author.voice.channel.members
        entries = [
            (f"`[{n}]`", f"{member} [{member.mention}]")
            for n, member in enumerate(members, start=1)
        ]
        paginator = Paginator(source=DescriptionEmbedPaginator(
            entries=entries,
            description="",
            title=f"Voice List of {ctx.author.voice.channel.name} - {len(members)}",
            color=self.color),
            ctx=ctx)
        await paginator.paginate()

    @__list_.command(name="moderators", help= "List of All Admins of a server", aliases=["mods"], with_app_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def list_mod(self, ctx):
        membs = ([
            mem for mem in ctx.guild.members
            if mem.guild_permissions.ban_members
            or mem.guild_permissions.kick_members
        ])
        mems = filter(lambda member: member.bot, ctx.guild.members)
        mems = sorted(membs, key=lambda mem: mem.joined_at)
        admins = len([
            mem for mem in ctx.guild.members
            if mem.guild_permissions.ban_members
            or mem.guild_permissions.kick_members
        ])
        guild = ctx.guild
        entries = [
            (f"`#{no}.`", f"[{mem}](https://discord.com/users/{mem.id}) [{mem.mention}] - <t:{int(mem.created_at.timestamp())}:D>")
            for no, mem in enumerate(mems, start=1)
        ]
        paginator = Paginator(source=DescriptionEmbedPaginator(
            entries=entries,
            title=f"Mods in {guild.name} - {admins}",
            description="",
            per_page=10),
            ctx=ctx)
        await paginator.paginate()

    @__list_.command(name="early", aliases=["sup"], help= "List of members that have Early Supporter badge.", with_app_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def list_early(self, ctx):
        mems = ([
            memb for memb in ctx.guild.members
            if memb.public_flags.early_supporter
        ])
        mems = sorted(mems, key=lambda memb: memb.created_at)
        admins = len([
            memb for memb in ctx.guild.members
            if memb.public_flags.early_supporter
        ])
        guild = ctx.guild
        entries = [
            (f"`#{no}.`", f"[{mem}](https://discord.com/users/{mem.id})  [{mem.mention}] - <t:{int(mem.created_at.timestamp())}:D>")
            for no, mem in enumerate(mems, start=1)
        ]
        paginator = Paginator(source=DescriptionEmbedPaginator(
            entries=entries,
            title=f"Early Supporters Id's in {guild.name} - {admins}",
            description="",
            per_page=10),
            ctx=ctx)
        await paginator.paginate()

    @__list_.command(name="activedeveloper", help= "List of members that have Active Developer badge.",
        aliases=["activedev"],
        with_app_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def list_activedeveloper(self, ctx):
        mems = ([
            memb for memb in ctx.guild.members
            if memb.public_flags.active_developer
        ])
        mems = sorted(mems, key=lambda memb: memb.created_at)
        admins = len([
            memb for memb in ctx.guild.members
            if memb.public_flags.active_developer
        ])
        guild = ctx.guild
        entries = [
            (f"`#{no}.`", f"[{mem}](https://discord.com/users/{mem.id}) [{mem.mention}] - <t:{int(mem.created_at.timestamp())}:D>")
            for no, mem in enumerate(mems, start=1)
        ]
        paginator = Paginator(source=DescriptionEmbedPaginator(
            entries=entries,
            title=f"Active Developer Id's in {guild.name} - {admins}",
            description="",
            per_page=10),
            ctx=ctx)
        await paginator.paginate()

    @__list_.command(name="createdat", help= "List of Account Creation Date of all Users", with_app_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def list_cpos(self, ctx):
        mems = ([memb for memb in ctx.guild.members])
        mems = sorted(mems, key=lambda memb: memb.created_at)
        admins = len([memb for memb in ctx.guild.members])
        guild = ctx.guild
        entries = [
            (f"`[{no}]`", f"[{mem}](https://discord.com/users/{mem.id}) - <t:{int(mem.created_at.timestamp())}:D>")
            for no, mem in enumerate(mems, start=1)
        ]
        paginator = Paginator(source=DescriptionEmbedPaginator(
            entries=entries,
            title=f"Creation every id in {guild.name} - {admins}",
            description="",
            per_page=10),
            ctx=ctx)
        await paginator.paginate()

    @__list_.command(name="joinedat", help= "List of Guild Joined date of all Users", with_app_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def list_joinpos(self, ctx):
        mems = ([memb for memb in ctx.guild.members])
        mems = sorted(mems, key=lambda memb: memb.joined_at)
        admins = len([memb for memb in ctx.guild.members])
        guild = ctx.guild
        entries = [
            (f"`#{no}.`", f"[{mem}](https://discord.com/users/{mem.id}) Joined At - <t:{int(mem.joined_at.timestamp())}:D>")
            for no, mem in enumerate(mems, start=1)
        ]
        paginator = Paginator(source=DescriptionEmbedPaginator(
            entries=entries,
            title=f"Join Position of every user in {guild.name} - {admins}",
            description="",
            per_page=10),
            ctx=ctx)
        await paginator.paginate()




    @commands.command(name="joined-at",
        help="Shows when a user joined",
        usage="joined-at [user]")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def joined_at(self, ctx):
        joined = await self.tz_helpers.format_datetime_for_user_custom(
            ctx.author.joined_at, ctx.author, "%a, %d %b %Y %I:%M %p %Z"
        )

        # Add Discord timestamp for better display
        if ctx.author.joined_at:
            joined_timestamp = discord.utils.format_dt(ctx.author.joined_at, style='F')  # Full date/time
            joined_relative = discord.utils.format_dt(ctx.author.joined_at, style='R')   # Relative time
            joined_display = f"{joined_timestamp} ({joined_relative})"
        else:
            joined_display = "Unknown"

        embed = discord.Embed(
            title="joined-at", 
            description=f"**{joined_display}**", 
            color=self.color,
            timestamp=self.tz_helpers.get_utc_now()
        )
        await ctx.send(embed=embed)

    @commands.command(name="github", usage="github [user/repo] [search]")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def github(self, ctx, search_type=None, *, search_query=None):
        if not search_type or not search_query:
            embed = discord.Embed(
                title="GitHub Search",
                description="Search for GitHub repositories or users.\n\n**Usage:**\n`github repo [search query]` - Search repositories\n`github user [username]` - Search users\n\n**Examples:**\n`github repo discord.py`\n`github user octocat`",
                color=self.color
            )
            return await ctx.send(embed=embed)

        try:
            if search_type.lower() in ["user", "u"]:
                # Search for users
                print(f"[DEBUG] Searching GitHub users for: {search_query}")
                response = requests.get(f"https://api.github.com/search/users?q={search_query}")
                print(f"[DEBUG] Response status: {response.status_code}")

                if response.status_code != 200:
                    raise Exception(f"GitHub API returned status code {response.status_code}")

                try:
                    json_data = response.json()
                    print(f"[DEBUG] JSON data type: {type(json_data)}")
                except Exception as json_error:
                    raise Exception(f"Failed to parse JSON response: {json_error}")

                if not json_data:
                    raise Exception("GitHub API returned empty response")

                if 'items' not in json_data:
                    print(f"[DEBUG] JSON keys: {list(json_data.keys()) if isinstance(json_data, dict) else 'Not a dict'}")
                    raise Exception("Invalid response structure from GitHub API")

                if json_data.get("total_count", 0) == 0:
                    embed = discord.Embed(
                        title="No Users Found",
                        description=f"No GitHub users found matching: **{search_query}**",
                        color=0xFF6B6B
                    )
                    await ctx.send(embed=embed)
                else:
                    user = json_data['items'][0]
                    # Get detailed user info
                    user_response = requests.get(f"https://api.github.com/users/{user['login']}")
                    if user_response.status_code != 200:
                        user_detail = user  # Fallback to basic user info
                    else:
                        user_detail = user_response.json()

                    embed = discord.Embed(
                        title=f"👤 GitHub User: {user['login']}",
                        description=user_detail.get('bio', 'No bio available'),
                        color=self.color,
                        url=user['html_url']
                    )
                    embed.set_thumbnail(url=user['avatar_url'])
                    embed.add_field(name="📊 Stats", value=f"**Repos:** {user_detail.get('public_repos', 0)}\n**Followers:** {user_detail.get('followers', 0)}\n**Following:** {user_detail.get('following', 0)}", inline=True)
                    embed.add_field(name="📍 Location", value=user_detail.get('location', 'Not specified'), inline=True)
                    embed.add_field(name="🏢 Company", value=user_detail.get('company', 'Not specified'), inline=True)
                    if user_detail.get('blog'):
                        embed.add_field(name="🌐 Website", value=f"[{user_detail['blog']}]({user_detail['blog']})", inline=False)
                    await ctx.send(embed=embed)

            elif search_type.lower() in ["repo", "repository", "r"]:
                # Search for repositories
                print(f"[DEBUG] Searching GitHub repositories for: {search_query}")
                response = requests.get(f"https://api.github.com/search/repositories?q={search_query}")
                print(f"[DEBUG] Response status: {response.status_code}")

                if response.status_code != 200:
                    raise Exception(f"GitHub API returned status code {response.status_code}")

                try:
                    json_data = response.json()
                    print(f"[DEBUG] JSON data type: {type(json_data)}")
                except Exception as json_error:
                    raise Exception(f"Failed to parse JSON response: {json_error}")

                if not json_data:
                    raise Exception("GitHub API returned empty response")

                if 'items' not in json_data:
                    print(f"[DEBUG] JSON keys: {list(json_data.keys()) if isinstance(json_data, dict) else 'Not a dict'}")
                    raise Exception("Invalid response structure from GitHub API")

                if json_data.get("total_count", 0) == 0:
                    embed = discord.Embed(
                        title="No Repositories Found",
                        description=f"No matching repositories found for: **{search_query}**",
                        color=0xFF6B6B
                    )
                    await ctx.send(embed=embed)
                else:
                    repo = json_data['items'][0]
                    embed = discord.Embed(
                        title=f"🔍 GitHub Repository Search",
                        description=f"Found **{json_data['total_count']}** repositories for: **{search_query}**",
                        color=self.color
                    )
                    embed.add_field(
                        name="📦 Top Result",
                        value=f"**[{repo['full_name']}]({repo['html_url']})**\n{repo.get('description', 'No description available')[:100]}{'...' if len(repo.get('description', '')) > 100 else ''}",
                        inline=False
                    )
                    embed.add_field(name="⭐ Stars", value=repo['stargazers_count'], inline=True)
                    embed.add_field(name="🍴 Forks", value=repo['forks_count'], inline=True)
                    embed.add_field(name="📝 Language", value=repo.get('language', 'Unknown'), inline=True)
                    await ctx.send(embed=embed)
            else:
                embed = discord.Embed(
                    title="Invalid Search Type",
                    description="Please use `repo` or `user` as the search type.\n\n**Examples:**\n`github repo discord.py`\n`github user octocat`",
                    color=0xFF6B6B
                )
                await ctx.send(embed=embed)

        except Exception as e:
            print(f"[DEBUG] GitHub command error: {type(e).__name__}: {str(e)}")
            print(f"[DEBUG] search_type: {search_type}, search_query: {search_query}")
            embed = discord.Embed(
                title="Error",
                description=f"Failed to search GitHub: {str(e)}",
                color=0xFF6B6B
            )
            await ctx.send(embed=embed)

    @commands.hybrid_command(name="vcinfo",
        description="View information about a voice channel.",
        help="View information about a voice channel.", 
        usage="<VoiceChannel>",
        with_app_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def vcinfo(self, ctx, channel: Optional[discord.VoiceChannel] = None):
        if channel is None:
            await ctx.reply(f"{cross} Please provide a valid voice channel.")
            return
        embed = discord.Embed(title=f"Voice Channel Info for: {channel.name}", color=self.color)
        embed.add_field(name="ID", value=channel.id, inline=True)
        embed.add_field(name="Members", value=len(channel.members), inline=True)
        embed.add_field(name="Bitrate", value=f"{channel.bitrate/1000} kbps", inline=True)
        created_at_formatted = await self.tz_helpers.format_datetime_for_user_custom(
            channel.created_at, ctx.author, "%Y-%m-%d %H:%M:%S %Z"
        )
        embed.add_field(name="Created At", value=created_at_formatted, inline=True)
        embed.add_field(name="Category", value=channel.category.name if channel.category else "None", inline=True)
        embed.add_field(name="Region", value=channel.rtc_region, inline=True)

        if channel.user_limit:
            embed.add_field(name="User Limit", value=channel.user_limit, inline=True)

        if channel.overwrites:
            overwrites = []
            for role, permissions in channel.overwrites.items():
                overwrites.append(f"**{role}**: {permissions}")
            embed.add_field(name="Overwrites", value="\n".join(overwrites), inline=False)

        view = View()
        view.add_item(Button(label="Join", style=discord.ButtonStyle.green, url=f"https://discord.com/channels/{ctx.guild.id}/{channel.id}"))
        view.add_item(Button(label="Invite", style=discord.ButtonStyle.link, url=f"https://discord.com/channels/{ctx.guild.id}/{channel.id}/invite"))

        await ctx.send(embed=embed, view=view)


    @commands.hybrid_command(name="channelinfo",
        aliases=['cinfo', 'ci'],
        description='Get information about a channel.',
        help='Get information about a channel.',
        usage="<Channel>",
        with_app_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def channelinfo(self, ctx, channel: Optional[discord.TextChannel] = None):
        if channel is None:
            channel = ctx.channel

        if channel is None:
            await ctx.reply(f"{cross} Could not resolve a valid channel.")
            return

        embed = discord.Embed(title=f"Channel Info - {channel.name}",
            color=0x006fb9, timestamp=self.tz_helpers.get_utc_now())
        embed.add_field(name="ID", value=channel.id, inline=False)

        created_at_formatted = await self.tz_helpers.format_datetime_for_user_custom(
            channel.created_at, ctx.author, "%Y-%m-%d %H:%M:%S %Z"
        )

        # Add Discord timestamp for better display
        created_timestamp = discord.utils.format_dt(channel.created_at, style='F')  # Full date/time
        created_relative = discord.utils.format_dt(channel.created_at, style='R')   # Relative time
        channel_created_display = f"{created_timestamp} ({created_relative})"

        embed.add_field(name="Created At", value=channel_created_display, inline=False)
        embed.add_field(name="Category", value=channel.category.name if channel.category else "None", inline=False)
        embed.add_field(name="Topic", value=channel.topic if channel.topic else "None", inline=False)
        embed.add_field(name="Slowmode", value=f"{channel.slowmode_delay} seconds" if channel.slowmode_delay else "None", inline=False)
        embed.add_field(name="NSFW", value=channel.is_nsfw(), inline=False)
        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1205345282158501899.png")
        embed.set_footer(text=f"Requested By {ctx.author}",
            icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)

        view = OverwritesView(channel, ctx.author.id)
        view.add_item(Button(label="Redirect Channel", style=discord.ButtonStyle.green, url=f"https://discord.com/channels/{ctx.guild.id}/{channel.id}"))

        await ctx.send(embed=embed, view=view)


    @commands.command(name="permissions", aliases=["perms"],
        help="Check and list the key permissions of a specific user",
        usage="perms <user>")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def keyperms(self, ctx, member: discord.Member):
        key_permissions = []

        if member.guild_permissions.create_instant_invite:
            key_permissions.append("Create Instant Invite")
        if member.guild_permissions.kick_members:
            key_permissions.append("Kick Members")
        if member.guild_permissions.ban_members:
            key_permissions.append("Ban Members")
        if member.guild_permissions.administrator:
            key_permissions.append("Administrator")
        if member.guild_permissions.manage_channels:
            key_permissions.append("Manage Channels")
        if member.guild_permissions.manage_messages:
            key_permissions.append("Manage Messages")
        if member.guild_permissions.mention_everyone:
            key_permissions.append("Mention Everyone")
        if member.guild_permissions.manage_nicknames:
            key_permissions.append("Manage Nicknames")
        if member.guild_permissions.manage_roles:
            key_permissions.append("Manage Roles")
        if member.guild_permissions.manage_webhooks:
            key_permissions.append("Manage Webhooks")
        if member.guild_permissions.manage_emojis:
            key_permissions.append("Manage Emojis")
        if member.guild_permissions.manage_guild:
            key_permissions.append("Manage Server")
        if member.guild_permissions.manage_permissions:
            key_permissions.append("Manage Permissions")
        if member.guild_permissions.manage_threads:
            key_permissions.append("Manage Threads")
        if member.guild_permissions.moderate_members:
            key_permissions.append("Moderate Members")
        if member.guild_permissions.move_members:
            key_permissions.append("Move Members")
        if member.guild_permissions.mute_members:
            key_permissions.append("Mute Members (VC)")
        if member.guild_permissions.deafen_members:
            key_permissions.append("Deafen Members")
        if member.guild_permissions.priority_speaker:
            key_permissions.append("Priority Speaker")
        if member.guild_permissions.stream:
            key_permissions.append("Stream")

        permissions_list = ", ".join(key_permissions) if key_permissions else "None"

        embed = discord.Embed(title=f"Key Permissions of {member}",
            color=0x006fb9)
        embed.add_field(name="Key Permissions", value=permissions_list, inline=False)
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        await ctx.send(embed=embed)
        embed.add_field(name="__**Key Permissions**__", value=permissions_list, inline=False)

        await ctx.reply(embed=embed)






    @commands.hybrid_command(name="report",
        aliases=["bug"],
        usage='Report [bug description]',
        description='Report a bug to the Development team.',
        help='Report a bug to the Development team.',
        with_app_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def report(self, ctx, *, bug=None):
        # Check if bug description was provided
        if not bug:
            error_embed = discord.Embed(
                title="❌ Missing Bug Description",
                description="Please provide a description of the bug you want to report.",
                color=0xFF0000
            )
            error_embed.add_field(
                name="Usage",
                value=f"`{ctx.prefix}report <bug description>`",
                inline=False
            )
            error_embed.add_field(
                name="Example",
                value=f"`{ctx.prefix}report The music bot stops playing after 5 minutes`",
                inline=False
            )
            await ctx.reply(embed=error_embed)
            return

        channel = self.bot.get_channel(1396762457342738469)
        if not channel:
            error_embed = discord.Embed(
                title="❌ Bug Report Channel Not Found",
                description="The bug report channel is not configured or accessible. Please contact an administrator.",
                color=0xFF0000
            )
            await ctx.reply(embed=error_embed)
            return

        embed = discord.Embed(title='Bug Reported',
            description=bug,
            color=0x006fb9)
        embed.add_field(name='Reported By',
            value=f'{ctx.author.name}',
            inline=True)
        embed.add_field(name="Server", value=ctx.guild.name, inline=False)
        embed.add_field(name="Channel", value=ctx.channel.name, inline=False)

        try:
            await channel.send(embed=embed)
            confirm_embed = discord.Embed(title="<:tick_icons:1397259828061278319> Bug Reported",
                description="Thank you for reporting the bug. We will look into it.",
                color=0x006fb9)
            await ctx.reply(embed=confirm_embed)
        except discord.HTTPException as e:
            error_embed = discord.Embed(
                title="❌ Failed to Send Bug Report",
                description=f"Could not send bug report to the designated channel. Error: {str(e)}",
                color=0xFF0000
            )
            await ctx.reply(embed=error_embed)

    @commands.hybrid_command(name="tos",
        aliases=["terms", "termsofservice"],
        usage='Terms of Service',
        description='Display the Terms of Service for Sleepless.',
        help='Display the Terms of Service for Sleepless.',
        with_app_command=True)
    @blacklist_check()
    @ignore_check()
    async def tos(self, ctx):
        """Display the Terms of Service"""
        import os
        try:
            # Use correct path - should be in the bot's root directory
            tos_path = 'TERMS_OF_SERVICE.md'
            # Fallback to absolute path if needed
            if not os.path.exists(tos_path):
                tos_path = os.path.join(os.getcwd(), 'TERMS_OF_SERVICE.md')

            with open(tos_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Clean up markdown formatting for better embed display
            def clean_markdown(text):
                # Remove markdown headers and make them bold
                text = re.sub(r'^#{1,6}\s+(.+)$', r'**\1**', text, flags=re.MULTILINE)
                # Remove excessive newlines
                text = re.sub(r'\n{3,}', '\n\n', text)
                # Clean up any remaining markdown artifacts
                text = text.replace('**Last Updated:', '\n**Last Updated:')
                return text.strip()

            cleaned_content = clean_markdown(content)

            # Split content into pages (approximately 1800 characters per page for better formatting)
            pages = []
            current_page = ""

            # Split by sections for better page breaks
            sections = cleaned_content.split('\n\n')

            for section in sections:
                # If adding this section would exceed limit, start new page
                if len(current_page + '\n\n' + section) > 1800:
                    if current_page:
                        pages.append(current_page.strip())
                        current_page = section
                    else:
                        # If single section is too long, split it
                        words = section.split(' ')
                        for word in words:
                            if len(current_page + ' ' + word) > 1800:
                                if current_page:
                                    pages.append(current_page.strip())
                                    current_page = word
                                else:
                                    pages.append(word[:1800])
                                    current_page = word[1800:]
                            else:
                                current_page += ' ' + word if current_page else word
                else:
                    if current_page:
                        current_page += '\n\n' + section
                    else:
                        current_page = section

            if current_page:
                pages.append(current_page.strip())

            if len(pages) == 1:
                embed = discord.Embed(
                    title="📋 Terms of Service - Sleepless",
                    description=pages[0],
                    color=0x2b2d31  # Discord's dark theme color
                )
                embed.add_field(
                    name="📞 Need Help?",
                    value="Join our [Support Server](https://discord.gg/5wtjDkYbVh) for assistance",
                    inline=False
                )
                embed.set_footer(
                    text="Sleepless Development © 2025 • Last Updated: September 7, 2025",
                    icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None
                )
                embed.set_thumbnail(url=self.bot.user.avatar.url if self.bot.user.avatar else None)
                await ctx.reply(embed=embed)
            else:
                # Create enhanced pages with better formatting
                enhanced_pages = []
                for i, page in enumerate(pages):
                    embed = discord.Embed(
                        title=f"📋 Terms of Service - Sleepless ({i+1}/{len(pages)})",
                        description=page,
                        color=0x2b2d31
                    )
                    if i == 0:  # Only show thumbnail on first page
                        embed.set_thumbnail(url=self.bot.user.avatar.url if self.bot.user.avatar else None)
                    if i == len(pages) - 1:  # Only show footer info on last page
                        embed.add_field(
                            name="📞 Need Help?",
                            value="Join our [Support Server](https://discord.gg/5wtjDkYbVh) for assistance",
                            inline=False
                        )
                        embed.set_footer(
                            text=f"Sleepless Development © 2025 • Page {i+1}/{len(pages)}",
                            icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None
                        )
                    enhanced_pages.append(embed)

                # For now, just show the first page with a note about multiple pages
                first_embed = discord.Embed(
                    title=f"📋 Terms of Service - Sleepless (Page 1/{len(pages)})",
                    description=pages[0],
                    color=0x2b2d31
                )
                first_embed.add_field(
                    name="📞 Need Help?",
                    value="Join our [Support Server](https://discord.gg/5wtjDkYbVh) for assistance",
                    inline=False
                )
                first_embed.add_field(
                    name="📄 Multiple Pages",
                    value=f"This document has {len(pages)} pages. Visit our support server for the complete Terms of Service.",
                    inline=False
                )
                first_embed.set_footer(
                    text="Sleepless Development © 2025 • Last Updated: September 7, 2025",
                    icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None
                )
                first_embed.set_thumbnail(url=self.bot.user.avatar.url if self.bot.user.avatar else None)
                await ctx.reply(embed=first_embed)

        except FileNotFoundError:
            embed = discord.Embed(
                title="❌ File Not Found",
                description="The Terms of Service document could not be found. Please contact the bot administrators.",
                color=0xff4757
            )
            embed.add_field(
                name="📞 Support",
                value="Join our [Support Server](https://discord.gg/5wtjDkYbVh) for help",
                inline=False
            )
            await ctx.reply(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error Loading Terms",
                description="An error occurred while loading the Terms of Service. Please try again later.",
                color=0xff4757
            )
            embed.add_field(
                name="📞 Support",
                value="Join our [Support Server](https://discord.gg/5wtjDkYbVh) if this problem persists",
                inline=False
            )
            embed.set_footer(text=f"Error: {str(e)}")
            await ctx.reply(embed=embed)

    @commands.hybrid_command(name="privacy",
        aliases=["privacypolicy", "pp"],
        usage='Privacy Policy',
        description='Display the Privacy Policy for Sleepless.',
        help='Display the Privacy Policy for Sleepless.',
        with_app_command=True)
    @blacklist_check()
    @ignore_check()
    async def privacy(self, ctx):
        """Display the Privacy Policy"""
        try:
            with open('/workspaces/feast11/PRIVACY_POLICY.md', 'r', encoding='utf-8') as f:
                content = f.read()

            # Split content into pages (approximately 2000 characters per page)
            pages = []
            current_page = ""

            for line in content.split('\n'):
                if len(current_page + line) > 1900:
                    if current_page:
                        pages.append(current_page)
                        current_page = line + '\n'
                    else:
                        pages.append(line[:1900])
                        current_page = line[1900:] + '\n'
                else:
                    current_page += line + '\n'

            if current_page:
                pages.append(current_page)

            if len(pages) == 1:
                embed = discord.Embed(
                    title="🔒 Privacy Policy - Sleepless",
                    description=pages[0],
                    color=0x185fe5
                )
                embed.set_footer(text="Sleepless Development", icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)
            
            paginator = Paginator(
                source=DescriptionEmbedPaginator(
                    entries=pages,
                    title="🔒 Privacy Policy - Sleepless",
                    color=0x185fe5,
                    footer="Sleepless Development"
                ),
                ctx=ctx
            )
            await paginator.paginate()

        except FileNotFoundError:
            embed = discord.Embed(
                title="❌ Error",
                description="Privacy Policy document not found. Please contact the bot administrators.",
                color=0xff0000
            )
            await ctx.reply(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"An error occurred while loading the Privacy Policy: {str(e)}",
                color=0xff0000
            )
            await ctx.reply(embed=embed)

    @commands.command(name="testemojis")
    async def test_emojis(self, ctx):
        """Test emoji list command with custom pagination buttons."""
        try:
            if not ctx.guild:
                embed = discord.Embed(
                    title=f"{EXTRA_EMOJIS['error']} Error",
                    description="This command only works in servers.",
                    color=0xff0000
                )
                await ctx.send(embed=embed)
                return

            guild = ctx.guild
            emojis = guild.emojis

            if not emojis:
                embed = discord.Embed(
                    title=f"{EXTRA_EMOJIS['empty']} No Custom Emojis",
                    description=f"**{guild.name}** doesn't have any custom emojis yet.",
                    color=0xffa500
                )
                await ctx.send(embed=embed)
                return

            print(f"[TESTEMOJIS] Found {len(emojis)} emojis in {guild.name}")

            # Create entries for pagination using the same format as list emojis
            entries = []
            for no, emoji in enumerate(emojis, start=1):
                try:
                    # Create tuple pairs for DescriptionEmbedPaginator
                    entries.append((f"`#{no}.`", f"{emoji} - `{emoji}`"))
                except Exception as e:
                    print(f"[TESTEMOJIS] Error processing emoji {emoji}: {e}")
                    entries.append((f"`#{no}.`", f"[Error displaying emoji] - `{emoji.name}:{emoji.id}`"))

            # Use the same Paginator system as the main command - removed try/catch that was causing fallback
            paginator = Paginator(source=DescriptionEmbedPaginator(
                entries=entries,
                title=f"{EXTRA_EMOJIS['test']} Test: Emojis in {guild.name} - {len(emojis)} total",
                description="Using custom pagination buttons with feast emojis",
                per_page=10),
                ctx=ctx)
            await paginator.paginate()
            print(f"[TESTEMOJIS] Successfully sent paginated emoji list for {guild.name}")

        except Exception as e:
            print(f"[TESTEMOJIS] Unexpected error: {e}")
            await ctx.send(f"Error: {e}")

    @commands.command(name="testemojis2") 
    async def test_emojis_fixed(self, ctx):
        """Fixed test emoji list command with better error handling."""
        print(f"[TESTEMOJIS2] Starting command...")

        try:
            # Basic validations
            if not ctx.guild:
                await ctx.send(f"{EXTRA_EMOJIS['error']} This command only works in servers.")
                return

            guild = ctx.guild
            emojis = guild.emojis

            print(f"[TESTEMOJIS2] Guild: {guild.name}, Emojis: {len(emojis)}")

            if not emojis:
                await ctx.send(f"{EXTRA_EMOJIS['empty']} **{guild.name}** doesn't have any custom emojis yet.")
                return

            # Create entries - simplified to avoid emoji processing errors
            entries = []
            for no, emoji in enumerate(emojis, start=1):
                # Create tuple pairs for DescriptionEmbedPaginator
                entries.append((f"`#{no}.`", f"{emoji.name} - `<:{emoji.name}:{emoji.id}>`"))

            print(f"[TESTEMOJIS2] Created {len(entries)} entries")

            # Force pagination - don't use try/catch that might trigger fallback
            print(f"[TESTEMOJIS2] Creating paginator...")

            source = DescriptionEmbedPaginator(
                entries=entries,
                title=f"{EXTRA_EMOJIS['test']} Fixed Test: Emojis in {guild.name} - {len(emojis)} total",
                description="Testing fixed pagination with custom feast buttons",
                per_page=10
            )

            paginator = Paginator(source=source, ctx=ctx)

            print(f"[TESTEMOJIS2] Paginator created, starting pagination...")

            await paginator.paginate()

            print(f"[TESTEMOJIS2] Pagination completed successfully!")

        except Exception as e:
            print(f"[TESTEMOJIS2] Error: {e}")
            import traceback
            traceback.print_exc()
            await ctx.send(f"Error: {e}")

async def setup(bot):
    await bot.add_cog(Extra(bot))