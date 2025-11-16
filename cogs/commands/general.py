import asyncio
import discord
from discord.ext import commands, tasks
from discord.utils import get
import datetime
import random
import requests
import aiohttp
import re
from discord.ext.commands.errors import BadArgument
from discord.ext.commands import Cog
from discord.colour import Color
import hashlib
from utils.Tools import *
from traceback import format_exception
import discord
from discord.ext import commands
import datetime
from discord import ButtonStyle
from discord.ui import Button, View
import psutil
import time
from datetime import datetime, timezone, timedelta
import sqlite3
from typing import Optional, Union
import string
#from cogs.commands.moderation import do_removal

lawda = [
  '8', '3821', '23', '21', '313', '43', '29', '76', '11', '9',
  '44', '470', '318' , '26', '69'
]



class AvatarView(View):
  def __init__(self, user, member, author_id, banner_url):
    super().__init__()
    self.user = user
    self.member = member
    self.author_id = author_id
    self.banner_url = banner_url

    if self.user.avatar:
      if self.user.avatar.is_animated():
        self.add_item(Button(label='GIF', url=self.user.avatar.with_format('gif').url, style=discord.ButtonStyle.link))
      self.add_item(Button(label='PNG', url=self.user.avatar.with_format('png').url, style=discord.ButtonStyle.link))
      self.add_item(Button(label='JPEG', url=self.user.avatar.with_format('jpg').url, style=discord.ButtonStyle.link))
      self.add_item(Button(label='WEBP', url=self.user.avatar.with_format('webp').url, style=discord.ButtonStyle.link))
    else:
      # User has no avatar, use default
      self.add_item(Button(label='Default Avatar', url=self.user.default_avatar.url, style=discord.ButtonStyle.link))

  async def interaction_check(self, interaction: discord.Interaction) -> bool:
    if interaction.user.id != self.author_id:
      await interaction.response.send_message(
        "Uh oh! That message doesn't belong to you. You must run this command to interact with it.",
        ephemeral=True
      )
      return False
    return True

  @discord.ui.button(label='Server Avatar', style=discord.ButtonStyle.success, custom_id='server_avatar_button')
  async def server_avatar(self, interaction: discord.Interaction, button: Button):
    if not self.member.guild_avatar:
      await interaction.response.send_message(
        "This user doesn't have a different guild avatar.",
        ephemeral=True
      )
    else:
      if interaction.message is not None:
        embed = interaction.message.embeds[0]
        embed.set_image(url=self.member.guild_avatar.url)
        await interaction.response.edit_message(embed=embed)
  @discord.ui.button(label='User Banner', style=discord.ButtonStyle.success, custom_id='banner_button')
  async def banner(self, interaction: discord.Interaction, button: Button):
    if not self.banner_url:
      await interaction.response.send_message(
        "This user doesn't have a banner.",
        ephemeral=True
      )
    else:
      if interaction.message is not None:
        embed = interaction.message.embeds[0]
        embed.set_image(url=self.banner_url)
        await interaction.response.edit_message(embed=embed)
      await interaction.response.edit_message(embed=embed)





class General(commands.Cog):
    
    def __init__(self, bot, *args, **kwargs):
        self.bot = bot

        self.aiohttp = aiohttp.ClientSession()
        self._URL_REGEX = r'(?P<url><[^: >]+:\/[^ >]+>|(?:https?|steam):\/\/[^\s<]+[^<.,:;\"\'\]\s])'
        self.color = 0x006fb9


    @commands.hybrid_command(
        usage="Avatar <member>",
        name='avatar',
        aliases=['av'],
        help="Get User avater/Guild avatar & Banner of a user."
        )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def _user(self, ctx, member: Optional[Union[discord.Member, discord.User]] = None):
        try:
            if member is None:
                member = ctx.author
            user = await self.bot.fetch_user(member.id) if member is not None and hasattr(member, 'id') else await self.bot.fetch_user(ctx.author.id)

            banner_url = user.banner.url if user.banner else None

            if user.avatar:
                description = f"[`PNG`]({user.avatar.with_format('png').url}) | [`JPG`]({user.avatar.with_format('jpg').url}) | [`WEBP`]({user.avatar.with_format('webp').url})"
                if user.avatar.is_animated():
                    description += f" | [`GIF`]({user.avatar.with_format('gif').url})"
            else:
                # User has no avatar, use default Discord avatar
                description = f"[`Default Avatar`]({user.default_avatar.url})"

            if banner_url:
                description += f" | [`Banner`]({banner_url})"

            embed = discord.Embed(
                color=self.color,
                description=description
            )
            icon_url = None
            if member and getattr(member, 'avatar', None):
                if member.avatar:
                    icon_url = member.avatar.url if member.avatar.url else None
            elif member and getattr(member, 'default_avatar', None):
                if member.default_avatar:
                    icon_url = member.default_avatar.url if member.default_avatar.url else None
            embed.set_author(name=f"{member}", icon_url=icon_url)
            embed.set_image(url=user.avatar.url)
            author_icon_url = None
            if getattr(ctx.author, 'avatar', None):
                if ctx.author.avatar:
                    author_icon_url = ctx.author.avatar.url if ctx.author.avatar.url else None
            elif getattr(ctx.author, 'default_avatar', None):
                if ctx.author.default_avatar:
                    author_icon_url = ctx.author.default_avatar.url if ctx.author.default_avatar.url else None
            embed.set_footer(text=f"Requested By {ctx.author}", icon_url=author_icon_url)

            view = AvatarView(user, member, ctx.author.id, banner_url)
            await ctx.send(embed=embed, view=view)
        except Exception as e:
            print(f"Error: {e}")

    @commands.hybrid_command(
        name="servericon",
        help="Get the server icon",
        usage="Servericon"
        )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def servericon(self, ctx: commands.Context):
        server = ctx.guild
        if not server or not getattr(server, 'icon', None):
            await ctx.reply("This server does not have an icon.")
            return

        icon = server.icon
        webp = icon.replace(format='webp') if icon else None
        jpg = icon.replace(format='jpg') if icon else None
        png = icon.replace(format='png') if icon else None

        description = f"[`PNG`]({png}) | [`JPG`]({jpg}) | [`WEBP`]({webp})"
        if icon and getattr(icon, 'is_animated', lambda: False)():
            gif = icon.replace(format='gif')
            description += f" | [`GIF`]({gif})"

        avemb = discord.Embed(
            color=self.color,
            title=f"{server}'s Icon",
            description=description
        )
        avemb.set_image(url=icon.url if icon else None)
        await ctx.send(embed=avemb)



    def get_status_emojis(self, ctx):
        """Get custom status emojis or fallback to defaults"""
        # You can customize these emoji IDs to your server's custom emojis
        # Format: <:emoji_name:emoji_id> for custom emojis or <a:emoji_name:emoji_id> for animated
        # Or use Unicode emojis as fallback

        custom_emojis = {
        'online': '<a:online:1431491381817380985>',  # Animated emoji
        'idle': '<a:idle:1431491396061237360>',      # Animated emoji
        'dnd': '<a:dnd:1431491388838645890>',        # Animated emoji
        'offline': '<:offline:1431491401195061393>', # Static emoji
        'members': '<:members:1428199763953582201>', # Use an existing emoji ID
        'humans': '<:profile:1428199763953582201>',   # Static emoji
        'bots': '<:bot:1428163130663375029>',       # Static emoji
        'stats': '<:warning1:1428163138322301018>'      # Static emoji
        }

        # Fallback to Unicode emojis if custom ones aren't available
        fallback_emojis = {
        'online': '🟢',
        'idle': '🟡', 
        'dnd': '🔴',
        'offline': '⚫',
        'members': '👥',
        'humans': '👤',
        'bots': '🤖',
        'stats': '📊'
        }

        # Try to use custom emojis, fallback to Unicode if not found
        result_emojis = {}
        for key, custom_emoji in custom_emojis.items():
            # Check if the custom emoji is available (support both static and animated)
            if (custom_emoji.startswith('<:') or custom_emoji.startswith('<a:')) and custom_emoji.endswith('>'):
                # Extract emoji ID and check if it's in the bot's available emojis
                try:
                    emoji_id = int(custom_emoji.split(':')[-1][:-1])
                    emoji_obj = self.bot.get_emoji(emoji_id)
                    if emoji_obj:
                        result_emojis[key] = custom_emoji
                    else:
                        print(f"[EMOJI DEBUG] Custom emoji {key} (ID: {emoji_id}) not found, using fallback")
                        result_emojis[key] = fallback_emojis[key]
                except (ValueError, IndexError) as e:
                    print(f"[EMOJI DEBUG] Error parsing emoji {key}: {custom_emoji} - {e}")
                    result_emojis[key] = fallback_emojis[key]
            else:
                result_emojis[key] = fallback_emojis[key]

        return result_emojis

    @commands.hybrid_command(name="membercount",
        help="Get total member count of the server",
        usage="membercount",
        aliases=["mc"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def membercount(self, ctx: commands.Context):
        if not ctx.guild or not getattr(ctx.guild, 'members', None):
            await ctx.reply("Guild or members not found.")
            return

        # Get custom emojis
        emojis = self.get_status_emojis(ctx)

        total_members = len(ctx.guild.members)
        total_humans = len([member for member in ctx.guild.members if not member.bot])
        total_bots = len([member for member in ctx.guild.members if member.bot])

        online = len([member for member in ctx.guild.members if member.status == discord.Status.online])
        offline = len([member for member in ctx.guild.members if member.status == discord.Status.offline])
        idle = len([member for member in ctx.guild.members if member.status == discord.Status.idle])
        dnd = len([member for member in ctx.guild.members if member.status == discord.Status.do_not_disturb])

        embed = discord.Embed(
            title=f"{emojis['stats']} {ctx.guild.name} Member Statistics",
            color=self.color
        )
        embed.add_field(
            name=f"{emojis['members']} Total Members",
            value=f"**{total_members:,}**",
            inline=True
        )
        embed.add_field(
            name=f"{emojis['humans']} Humans",
            value=f"**{total_humans:,}**",
            inline=True
        )
        embed.add_field(
            name=f"{emojis['bots']} Bots",
            value=f"**{total_bots:,}**",
            inline=True
        )
        embed.add_field(
            name=f"{emojis['online']} Online",
            value=f"**{online:,}**",
            inline=True
        )
        embed.add_field(
            name=f"{emojis['idle']} Idle",
            value=f"**{idle:,}**",
            inline=True
        )
        embed.add_field(
            name=f"{emojis['dnd']} DND",
            value=f"**{dnd:,}**",
            inline=True
        )
        embed.add_field(
            name=f"{emojis['offline']} Offline",
            value=f"**{offline:,}**",
            inline=True
        )

        if ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)

        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)




    @commands.hybrid_command(name="poll", usage="Poll <message>")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def poll(self, ctx: commands.Context, *, message=None):
        if not message:
            await ctx.send("❌ Please provide a message for the poll!\n**Usage:** `poll <your message here>`")
            return

        author = ctx.author
        emp = discord.Embed(title=f"**Poll raised by {author}!**",
            description=f"{message}",
            color=self.color)
        msg = await ctx.send(embed=emp)
        await msg.add_reaction("<:feast_tick:1400143469892210753>")
        await msg.add_reaction("<:feast_cross:1400143488695144609>")


    @commands.command(name="hack",
        help="hack someone's discord account",
        usage="Hack <member>")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def hack(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        if not member:
            await ctx.send("❌ Please mention a member to hack!\n**Usage:** `hack @member`")
            return

        stringi = member.name
        min_length = 2
        max_length = 12


        lund = await ctx.send(f"Processing to Hack {member.mention}...")
        await asyncio.sleep(2)
        random_pass = random.choice(lawda)

        random_pass2 = ''.join(random.choices(string.ascii_letters + string.digits, k=3))
        embed = discord.Embed(
            title=f"**Hacked {member.display_name}!**",
            description=(
                f"User - {member.mention}\n"
                f"E-Mail - {''.join(letter for letter in stringi if letter.isalnum())}{random_pass}@gmail.com\n"
                f"Account Password - {member.name}@{random_pass2}"
            ),
            color=0x006fb9
        )
        embed.set_footer(
            text=f"Hacked By {ctx.author}",
            icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
        )
        await ctx.send(embed=embed)
        await lund.delete()


    @commands.command(name="token", usage="Token <member>")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def token(self, ctx: commands.Context, user: Optional[Union[discord.Member, discord.User]] = None):
        list = [
            "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N",
            "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z", "_"
            'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n',
            'ñ', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z', '0',
            '1', '2', '3', '4', '5', '6', '7', '8', '9'
        ]
        token = random.choices(list, k=59)
        if user is None:
            user = ctx.author
        mention = getattr(user, 'mention', None)
        if mention is None:
            mention = str(user)
        await ctx.send(mention + "'s token: " + ''.join(token))

    @commands.command(name="users", help="checks total users of Sleepless.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def users(self, ctx: commands.Context):
        users = sum(g.member_count for g in self.bot.guilds
                   if g.member_count != None)
        guilds = len(self.bot.guilds)
        embed = discord.Embed(
            title=f"**Quanutum Users**",
            description=f"❯ Total of __**{users}**__ Users in **{guilds}** Guilds",
            color=self.color)
        await ctx.send(embed=embed)


    @commands.command(name="wizz", usage="Wizz")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def wizz(self, ctx: commands.Context):
        if not ctx.guild:
            await ctx.send("No guild context.")
            return
        guild_name = ctx.guild.name if getattr(ctx.guild, 'name', None) else "Unknown Guild"
        roles = ctx.guild.roles if getattr(ctx.guild, 'roles', None) else []
        channels = ctx.guild.channels if getattr(ctx.guild, 'channels', None) else []
        message6 = await ctx.send(f"`Wizzing {guild_name}, will take 22 seconds to complete`")
        message7 = await ctx.send(f"Changing all guild settings...")
        message5 = await ctx.send(f"Deleting **{len(roles)}** Roles...")
        await asyncio.sleep(1)
        message4 = await ctx.send(f"Deleting **{len(channels)}** Channels...")
        await asyncio.sleep(1)
        message3 = await ctx.send(f"Deleting Webhooks...")
        message2 = await ctx.send(f"Deleting emojis")
        await asyncio.sleep(1)
        message1 = await ctx.send(f"Installing Ban Wave..")
        await asyncio.sleep(1)
        for msg in [message6, message7, message5, message4, message3, message2, message1]:
            if msg:
                await msg.delete()
        embed = discord.Embed(
            title=f"{self.bot.user.name if self.bot and getattr(self.bot, 'user', None) and getattr(self.bot.user, 'name', None) else 'Bot'}",
            description=f"**<:feast_warning:1400143131990560830> Successfully Wizzed {guild_name}**",
            color=self.color,
            timestamp=ctx.message.created_at if hasattr(ctx.message, 'created_at') else None)


    @commands.hybrid_command(
        name="urban",
        description="Searches for specified phrase on urbandictionary",
        help="Get meaning of specified phrase",
        usage="Urban <phrase>")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def urban(self, ctx: commands.Context, *, phrase=None):
        if not phrase:
            await ctx.send("❌ Please provide a phrase to search!\n**Usage:** `urban <word or phrase>`")
            return

        async with self.aiohttp.get(
            "http://api.urbandictionary.com/v0/define?term={}".format(
                phrase)) as urb:
            urban = await urb.json()
            try:
                embed = discord.Embed(title=f"Meaning of \"{phrase}\"", color=self.color)
                embed.add_field(name="__Definition:__",
                               value=urban['list'][0]['definition'].replace(
                                   '[', '').replace(']', ''))
                embed.add_field(name="__Example:__",
                               value=urban['list'][0]['example'].replace('[',
                                                                        '').replace(
                                   ']', ''))

                embed.add_field(name="__Author:__",
                               value=urban['list'][0]['author'].replace('[',
                                                                       '').replace(
                                   ']', ''))

                embed.add_field(name="__Written On:__",
                               value=urban['list'][0]['written_on'].replace('[',
                                                                           '').replace(
                                   ']', ''))
                embed.set_footer(
                    text=f"Requested By {ctx.author}",
                    icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
                )
                temp = await ctx.reply(embed=embed, mention_author=True)
                await asyncio.sleep(45)
                await temp.delete()
                await ctx.message.delete()
            except:
                pass

    @commands.command(name="rickroll",
        help="Detects if provided url is a rick-roll",
        usage="Rickroll <url>")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def rickroll(self, ctx: commands.Context, *, url: str):
        if not re.match(self._URL_REGEX, url):
            raise BadArgument("Invalid URL")

        phrases = [
            "rickroll", "rick roll", "rick astley", "never gonna give you up"
        ]
        source = str(await (await self.aiohttp.get(
            url, allow_redirects=True)).content.read()).lower()
        rickRoll = bool((re.findall('|'.join(phrases), source,
        re.MULTILINE | re.IGNORECASE)))
        await ctx.reply(embed=discord.Embed(
        title="Rick Roll {} in webpage".format(
        "was found" if rickRoll is True else "was not found"),
        color=Color.red() if rickRoll is True else Color.green(),
        ),
        mention_author=True)

    @commands.command(name="hash",
        help="Hashes provided text with provided algorithm")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def hash(self, ctx: commands.Context, algorithm: Optional[str] = None, *, message: Optional[str] = None):
        if algorithm is None:
            embed = discord.Embed(
                title="❌ Missing Algorithm",
                description="Please provide an algorithm to use for hashing.\n\n**Available algorithms:**\n`md5`, `sha1`, `sha224`, `sha3_224`, `sha256`, `sha3_256`, `sha384`, `sha3_384`, `sha512`, `sha3_512`, `blake2b`, `blake2s`\n\n**Usage:** `hash <algorithm> <message>`",
                color=0xff0000
            )
            await ctx.reply(embed=embed, mention_author=True)
            return

        if message is None:
            embed = discord.Embed(
                title="❌ Missing Message",
                description="Please provide a message to hash.\n\n**Usage:** `hash <algorithm> <message>`",
                color=0xff0000
            )
            await ctx.reply(embed=embed, mention_author=True)
            return

        algos: dict[str, str] = {
            "md5": hashlib.md5(bytes(message.encode("utf-8"))).hexdigest(),
            "sha1": hashlib.sha1(bytes(message.encode("utf-8"))).hexdigest(),
            "sha224": hashlib.sha224(bytes(message.encode("utf-8"))).hexdigest(),
            "sha3_224": hashlib.sha3_224(bytes(message.encode("utf-8"))).hexdigest(),
            "sha256": hashlib.sha256(bytes(message.encode("utf-8"))).hexdigest(),
            "sha3_256": hashlib.sha3_256(bytes(message.encode("utf-8"))).hexdigest(),
            "sha384": hashlib.sha384(bytes(message.encode("utf-8"))).hexdigest(),
            "sha3_384": hashlib.sha3_384(bytes(message.encode("utf-8"))).hexdigest(),
            "sha512": hashlib.sha512(bytes(message.encode("utf-8"))).hexdigest(),
            "sha3_512": hashlib.sha3_512(bytes(message.encode("utf-8"))).hexdigest(),
            "blake2b": hashlib.blake2b(bytes(message.encode("utf-8"))).hexdigest(),
            "blake2s": hashlib.blake2s(bytes(message.encode("utf-8"))).hexdigest()
        }
        embed = discord.Embed(color=0x006fb9,
                             title="Hashed \"{}\"".format(message))
        if algorithm.lower() not in list(algos.keys()):
            for algo in list(algos.keys()):
                hashValue = algos[algo]
                embed.add_field(name=algo, value="```{}```".format(hashValue))
        else:
            embed.add_field(name=algorithm,
                           value="```{}```".format(algos[algorithm.lower()]),
                           inline=False)
        await ctx.reply(embed=embed, mention_author=True)


    @commands.command(name="invite",
        aliases=['invite-bot'],
        description="Get Support & Bot invite link!")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def invite(self, ctx: commands.Context):
        embed = discord.Embed(title="Sleepless Invite & Support!",
                             description=
                             f"> <:feast_plus:1400142875483836547> **[Sleepless - Invite Bot](https://discord.com/oauth2/authorize?client_id=1414317652066832527&permissions=8&integration_type=0&scope=bot+applications.commands)**\n> <:feast_plus:1400142875483836547> **[Sleepless - Support](https://discord.gg/5wtjDkYbVh)**",
                             color=0x0ba7ff)

        embed.set_footer(text=f"Requested by {ctx.author.name}",
                        icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        invite = Button(
            label='Invite',
            style=discord.ButtonStyle.link,
            url=
            'https://discord.com/oauth2/authorize?client_id=1414317652066832527&permissions=8&integration_type=0&scope=bot+applications.commands'
        )
        support = Button(label='Support',
                        style=discord.ButtonStyle.link,
                        url=f'https://discord.gg/5wtjDkYbVh')
        view = View()
        view.add_item(invite)
        view.add_item(support)

        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name="about", aliases=["features", "whatcan"], help="Comprehensive overview of all SleeplessPY features and capabilities")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def about_sleepless(self, ctx):
        """Complete feature overview of SleeplessPY Bot"""

        # Get dynamic stats
        command_count = len(set(self.bot.walk_commands()))
        guild_count = len(self.bot.guilds)
        user_count = sum(g.member_count for g in self.bot.guilds if g.member_count)

        # Main About Embed
        main_embed = discord.Embed(
        title="🌟 About SleeplessPY - Your All-in-One Discord Solution",
        description=f"**The most comprehensive Discord bot with {command_count}+ features designed to enhance your server experience**\n\n*Click the buttons below to explore different feature categories*",
        color=0x00E6A7
        )

        main_embed.add_field(
        name="🎯 **What Makes SleeplessPY Special**",
        value=f"• **{command_count}+ Commands** across 15+ categories\n• **Interactive UI** with buttons and modals\n• **Advanced Security** with anti-nuke protection\n• **Professional Grade** ticket and moderation systems\n• **High-Quality Music** with Lavalink integration\n• **Custom Features** like VoiceMaster and AutoMod\n• **Developer Friendly** with extensive APIs",
        inline=False
        )

        main_embed.add_field(
        name="📊 **Quick Stats**",
        value=f"• **Servers:** {guild_count:,}\n• **Users:** {user_count:,}\n• **Commands:** {command_count}+\n• **Uptime:** 99.9%+\n• **Response Time:** <100ms",
        inline=True
        )

        main_embed.add_field(
        name="🔗 **Quick Links**",
        value="[**Invite Bot**](https://discord.com/oauth2/authorize?client_id=1414317652066832527&permissions=8&integration_type=0&scope=bot+applications.commands) | [**Support Server**](https://discord.gg/5wtjDkYbVh)",
        inline=True
        )

        main_embed.set_footer(text="💡 Use the buttons below to explore specific feature categories!")

        # Create view with category buttons
        view = View(timeout=300)

        # Moderation & Security Button
        mod_button = Button(label="🛡️ Moderation & Security", style=ButtonStyle.primary, row=0)
        
        async def mod_callback(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("❌ Only the command user can interact with this!", ephemeral=True)

            embed = discord.Embed(
                title="🛡️ Moderation & Security Features",
                description="**Advanced moderation tools and security systems to protect your server**",
                color=0xFF5733
            )
            embed.add_field(
                name="🔨 **Core Moderation**",
                value="• **Ban/Unban** - Advanced banning with reason tracking\n• **Kick** - Remove users with logging\n• **Mute/Unmute** - Timeout users with duration control\n• **Warn** - Warning system with escalation\n• **Clear** - Bulk message deletion with filters",
                inline=False
            )
            embed.add_field(
                name="🛡️ **Anti-Nuke Protection**",
                value="• **Anti-Ban** - Prevents mass ban attacks\n• **Anti-Kick** - Stops mass kicking\n• **Anti-Channel Delete** - Protects channels\n• **Anti-Role Delete** - Safeguards roles\n• **Anti-Webhook** - Blocks malicious webhooks\n• **Anti-Spam** - Advanced spam detection",
                inline=False
            )
            embed.add_field(
                name="⚙️ **AutoMod Systems**",
                value="• **Auto-Moderation** - AI-powered content filtering\n• **Anti-Link** - Block unwanted links\n• **Anti-Invite** - Prevent server raids\n• **Anti-Caps** - Control excessive caps\n• **Bad Word Filter** - Customizable word blocking",
                inline=False
            )
            embed.add_field(
                name="📋 **Advanced Features**",
                value="• **Jail System** - Isolate problematic users\n• **Role Management** - Advanced role controls\n• **Blacklist** - Server-wide user blocking\n• **Logging** - Comprehensive audit logs",
                inline=False
            )
            await interaction.response.edit_message(embed=embed, view=view)

        mod_button.callback = mod_callback
        view.add_item(mod_button)

        # Music & Entertainment Button
        music_button = Button(label="🎵 Music & Entertainment", style=ButtonStyle.success, row=0)
        
        async def music_callback(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("❌ Only the command user can interact with this!", ephemeral=True)

            embed = discord.Embed(
                title="🎵 Music & Entertainment Features",
                description="**High-quality music streaming and fun interactive commands**",
                color=0x9B59B6
            )
            embed.add_field(
                name="🎼 **Music System**",
                value="• **Lavalink Integration** - Professional audio streaming\n• **Queue Management** - Smart playlist handling\n• **Multiple Sources** - YouTube, Spotify, SoundCloud\n• **Audio Controls** - Volume, skip, pause, resume\n• **Interactive UI** - Button-based music controls\n• **Filters** - Bass boost, nightcore, etc.",
                inline=False
            )
            embed.add_field(
                name="🎮 **Games & Fun**",
                value="• **Blackjack** - Casino-style card game\n• **Slots** - Slot machine gambling\n• **Ship** - Relationship compatibility\n• **8Ball** - Magic 8-ball predictions\n• **Dice & Coin** - Random generators\n• **Rate Commands** - Fun rating system",
                inline=False
            )
            embed.add_field(
                name="🎪 **Interactive Features**",
                value="• **Giveaways** - Advanced giveaway system\n• **Polls** - Interactive voting\n• **Reaction Roles** - Role assignment via reactions\n• **Button Roles** - Modern role selection\n• **Custom Emojis** - Emoji stealing and management",
                inline=False
            )
            await interaction.response.edit_message(embed=embed, view=view)

        music_button.callback = music_callback
        view.add_item(music_button)

        # Tickets & Support Button  
        ticket_button = Button(label="🎫 Tickets & Support", style=ButtonStyle.secondary, row=0)
        
        async def ticket_callback(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("❌ Only the command user can interact with this!", ephemeral=True)

            embed = discord.Embed(
                title="🎫 Tickets & Support Features",
                description="**Professional customer support and ticket management system**",
                color=0x00E6A7
            )
            embed.add_field(
                name="🎪 **TicketTool V2 Style**",
                value="• **Interactive Panels** - Click buttons to create tickets\n• **Custom Colors** - Use simple color names (red, blue, etc.)\n• **Channel Targeting** - Send panels anywhere\n• **Persistent Views** - Work forever, even after restarts\n• **Auto-Cleanup** - Handles deleted messages automatically",
                inline=False
            )
            embed.add_field(
                name="🎛️ **Control Features**",
                value="• **Ticket Controls** - Close, claim, transfer ownership\n• **User Management** - Add/remove users from tickets\n• **Transcripts** - Generate and log conversation history\n• **Role Access** - Permission-based ticket access\n• **Auto-Close** - Automatic cleanup of inactive tickets",
                inline=False
            )
            embed.add_field(
                name="⚙️ **Admin Tools**",
                value="• **Setup Wizard** - Easy configuration\n• **Statistics** - Track ticket metrics\n• **Logging** - Audit all ticket activity\n• **Categories** - Organize tickets by type\n• **Welcome Messages** - Custom greetings",
                inline=False
            )
            await interaction.response.edit_message(embed=embed, view=view)

        ticket_button.callback = ticket_callback
        view.add_item(ticket_button)

        # Voice & Channels Button
        voice_button = Button(label="🎙️ Voice & Channels", style=ButtonStyle.primary, row=1)
        
        async def voice_callback(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("❌ Only the command user can interact with this!", ephemeral=True)

            embed = discord.Embed(
                title="🎙️ Voice & Channel Management",
                description="**Advanced voice channel control and temporary channel systems**",
                color=0x17A2B8
            )
            embed.add_field(
                name="🎧 **VoiceMaster System**",
                value="• **Temporary Channels** - Auto-created voice & text channels\n• **Control Panels** - Lock, unlock, rename channels\n• **Permission Management** - Grant/revoke user access\n• **Auto-Cleanup** - Removes empty channels automatically\n• **Transfer Ownership** - Pass control to other users",
                inline=False
            )
            embed.add_field(
                name="📊 **Voice Tracking**",
                value="• **Voice Time Tracking** - Monitor user activity\n• **Channel Statistics** - Usage analytics\n• **Join/Leave Logs** - Track voice activity\n• **AFK Detection** - Identify inactive users",
                inline=False
            )
            embed.add_field(
                name="🔧 **Channel Tools**",
                value="• **Lock/Unlock** - Control channel access\n• **Hide/Unhide** - Manage channel visibility\n• **Slowmode** - Rate limiting for channels\n• **Channel Info** - Detailed channel statistics",
                inline=False
            )
            await interaction.response.edit_message(embed=embed, view=view)

        voice_button.callback = voice_callback
        view.add_item(voice_button)

        # Utility & Tools Button
        utility_button = Button(label="🔧 Utility & Tools", style=ButtonStyle.success, row=1)
        
        async def utility_callback(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("❌ Only the command user can interact with this!", ephemeral=True)

            embed = discord.Embed(
                title="🔧 Utility & Tools Features",
                description="**Essential server management and utility commands**",
                color=0xFFC107
            )
            embed.add_field(
                name="📝 **Server Management**",
                value="• **Embed Creator** - Custom embed builder\n• **Auto-Responder** - Custom keyword responses\n• **Welcome/Leave** - Greeting and farewell messages\n• **Auto-Nick** - Automatic nickname enforcement\n• **Suggestion System** - Community feedback collection",
                inline=False
            )
            embed.add_field(
                name="📊 **Information Commands**",
                value="• **User Info** - Detailed user profiles\n• **Server Info** - Complete server statistics\n• **Role Info** - Role details and permissions\n• **Channel Info** - Channel statistics and settings\n• **Bot Stats** - Performance and system info",
                inline=False
            )
            embed.add_field(
                name="🌐 **External Tools**",
                value="• **Translation** - Multi-language translation\n• **Weather** - Global weather information\n• **QR Codes** - Generate QR codes\n• **URL Shortener** - Link shortening service\n• **Image Manipulation** - Basic image editing",
                inline=False
            )
            await interaction.response.edit_message(embed=embed, view=view)

        utility_button.callback = utility_callback
        view.add_item(utility_button)

        # Economy & Social Button
        social_button = Button(label="💰 Economy & Social", style=ButtonStyle.secondary, row=1)
        
        async def social_callback(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("❌ Only the command user can interact with this!", ephemeral=True)

            embed = discord.Embed(
                title="💰 Economy & Social Features",
                description="**Community engagement and social interaction systems**",
                color=0xE91E63
            )
            embed.add_field(
                name="👥 **Social Features**",
                value="• **AFK System** - Away status with custom messages\n• **Ship Command** - Relationship compatibility\n• **Marriage System** - Virtual relationships\n• **Profiles** - Customizable user profiles\n• **Activity Tracking** - User engagement metrics",
                inline=False
            )
            embed.add_field(
                name="🎯 **Engagement Tools**",
                value="• **Leveling System** - XP and rank progression\n• **Custom Roles** - User-created role system\n• **Achievement System** - Unlock special badges\n• **Leaderboards** - Competitive rankings\n• **Daily Rewards** - Regular user incentives",
                inline=False
            )
            embed.add_field(
                name="🏆 **Competition Features**",
                value="• **Tournaments** - Organized competitions\n• **Team System** - Group management\n• **Vote Rewards** - Top.gg voting benefits\n• **Premium Features** - Enhanced capabilities\n• **Custom Commands** - User-defined commands",
                inline=False
            )
            await interaction.response.edit_message(embed=embed, view=view)

        social_button.callback = social_callback
        view.add_item(social_button)

        # Back to Main Button
        back_button = Button(label="🏠 Back to Main", style=ButtonStyle.gray, row=2)
        
        async def back_callback(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("❌ Only the command user can interact with this!", ephemeral=True)
            await interaction.response.edit_message(embed=main_embed, view=view)

        back_button.callback = back_callback
        view.add_item(back_button)

        # Links Button
        links_button = Button(label="🔗 Support Server", style=ButtonStyle.link, url="https://discord.gg/5wtjDkYbVh", row=2)
        view.add_item(links_button)

        # Delete Button
        delete_button = Button(label="🗑️ Delete", style=ButtonStyle.danger, row=2)
        
        async def delete_callback(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("❌ Only the command user can interact with this!", ephemeral=True)
            await interaction.message.delete()

        delete_button.callback = delete_callback
        view.add_item(delete_button)

        await ctx.send(embed=main_embed, view=view)

    # ===================== WORD FILTER SYSTEM =====================

    def setup_wordfilter_db(self):
        """Initialize the word filter database"""
        import os
        os.makedirs('databases', exist_ok=True)

        with sqlite3.connect('databases/wordfilter.db') as conn:
            # Table for banned words per user
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_word_bans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    banned_word TEXT NOT NULL,
                    action TEXT DEFAULT 'delete',
                    added_by INTEGER NOT NULL,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(guild_id, user_id, banned_word)
                )
            """)

            # Check if action column exists, if not add it (migration)
            try:
                cursor = conn.execute("PRAGMA table_info(user_word_bans)")
                columns = [row[1] for row in cursor.fetchall()]
                if 'action' not in columns:
                    print("[WORDFILTER] Adding action column to existing user_word_bans table...")
                    conn.execute("ALTER TABLE user_word_bans ADD COLUMN action TEXT DEFAULT 'delete'")
                    conn.commit()
                    print("[WORDFILTER] Action column migration completed!")
            except Exception as e:
                print(f"[WORDFILTER] Migration error (this is usually safe to ignore): {e}")

            # Table for filter settings per guild
            conn.execute("""
                CREATE TABLE IF NOT EXISTS wordfilter_settings (
                    guild_id INTEGER PRIMARY KEY,
                    log_channel_id INTEGER,
                    delete_message INTEGER DEFAULT 1,
                    warn_user INTEGER DEFAULT 1,
                    mute_role_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.commit()

    @commands.group(name="wordfilter", aliases=["wf"], help="Manage word filters for specific users")
    @commands.has_permissions(manage_messages=True)
    @blacklist_check()
    @ignore_check()
    async def wordfilter(self, ctx):
        """Word filter management system"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="🚫 Word Filter System",
                description="Manage banned words for specific users",
                color=self.color
            )
            embed.add_field(
                name="📝 Commands",
                value=(
                    "`wordfilter add <user> <action> <word>` - Ban a word for a user\n"
        "`wordfilter remove <user> <word>` - Remove banned word\n"
        "`wordfilter list [user]` - List banned words\n"
        "`wordfilter clear <user>` - Clear all banned words for user\n"
        "`wordfilter setmute <role>` - Set mute role for mute action\n"
        "`wordfilter settings` - Configure filter settings"
        ),
        inline=False
        )
        embed.add_field(
        name="🔨 Actions Available",
        value=(
        "• **delete** - Delete message only\n"
        "• **warn** - Delete + warn user\n" 
        "• **mute** - Delete + mute user\n"
        "• **kick** - Delete + kick user\n"
        "• **ban** - Delete + ban user"
        ),
        inline=False
        )
        embed.add_field(
        name="⚙️ Features",
        value=(
        "• Target specific users with word bans\n"
        "• Automatic message deletion\n"
        "• Optional user warnings\n"
        "• Optional timeout penalties\n"
        "• Comprehensive logging"
        ),
        inline=False
        )
        await ctx.send(embed=embed)

    @wordfilter.command(name="add")
    @commands.has_permissions(manage_messages=True)
    async def wordfilter_add(self, ctx, user: discord.Member, *, args: str):
        """Add a banned word for a specific user with moderation action

        Usage: $wordfilter add @user <action> <word>
        Actions: delete, warn, mute, kick, ban
        Example: $wordfilter add @user kick badword
        """
        if not ctx.guild:
            await ctx.send("❌ This command can only be used in servers.")
            return

        # Setup database
        self.setup_wordfilter_db()

        # Parse arguments
        parts = args.strip().split(None, 1)
        if len(parts) < 2:
            embed = discord.Embed(
                title="❌ Invalid Usage",
                description="**Correct usage:** `wordfilter add @user <action> <word>`",
                color=0xff0000
            )
            embed.add_field(
                name="Available Actions",
                value="`delete`, `warn`, `mute`, `kick`, `ban`",
                inline=False
            )
            embed.add_field(
                name="Example",
                value="`$wordfilter add @TroubleMaker mute badword`",
                inline=False
            )
            await ctx.send(embed=embed)
            return

        action = parts[0].lower()
        word = parts[1].strip()

        # Validate action
        valid_actions = ['delete', 'warn', 'mute', 'kick', 'ban']
        if action not in valid_actions:
            embed = discord.Embed(
                title="❌ Invalid Action",
                description=f"**Invalid action:** `{action}`",
                color=0xff0000
            )
            embed.add_field(
                name="Valid Actions",
                value="`" + "`, `".join(valid_actions) + "`",
                inline=False
            )
            embed.add_field(
                name="Example",
                value=f"`$wordfilter add {user.mention} mute {word}`",
                inline=False
            )
            await ctx.send(embed=embed)
            return

        # Clean the word (remove extra spaces, convert to lowercase)
        word = word.strip().lower()

        if len(word) < 2:
            await ctx.send("❌ Banned word must be at least 2 characters long.")
            return

        if len(word) > 100:
            await ctx.send("❌ Banned word cannot be longer than 100 characters.")
            return

        try:
            with sqlite3.connect('databases/wordfilter.db') as conn:
                # Check if word already exists for this user
                cursor = conn.execute("""
                    SELECT action FROM user_word_bans 
                    WHERE guild_id = ? AND user_id = ? AND banned_word = ?
                """, (ctx.guild.id, user.id, word))

                existing = cursor.fetchone()
                if existing:
                    # Update existing entry
                    conn.execute("""
                        UPDATE user_word_bans 
                        SET action = ?, added_by = ?, added_at = CURRENT_TIMESTAMP
                        WHERE guild_id = ? AND user_id = ? AND banned_word = ?
                    """, (action, ctx.author.id, ctx.guild.id, user.id, word))
                    action_text = f"Updated action from `{existing[0]}` to `{action}`"
                else:
                    # Insert new entry
                    conn.execute("""
                        INSERT INTO user_word_bans (guild_id, user_id, banned_word, action, added_by)
                        VALUES (?, ?, ?, ?, ?)
                    """, (ctx.guild.id, user.id, word, action, ctx.author.id))
                    action_text = f"Added with action `{action}`"
                
                conn.commit()

                # Create action description
                action_descriptions = {
                    'delete': 'Delete message only',
                    'warn': 'Delete message + warn user',
                    'mute': 'Delete message + mute user',
                    'kick': 'Delete message + kick user',
                    'ban': 'Delete message + ban user'
                }

                embed = discord.Embed(
                    title="✅ Word Banned",
                    description=f"The word `{word}` has been banned for {user.mention}",
                    color=0x00ff00
                )
                embed.add_field(name="Action", value=action_descriptions[action], inline=True)
                embed.add_field(name="Added by", value=ctx.author.mention, inline=True)
                embed.add_field(name="Target User", value=user.mention, inline=True)
                embed.add_field(name="Status", value=action_text, inline=False)
                embed.set_footer(text=f"Use 'wordfilter remove {user.id} {word}' to unban")

                await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Error adding banned word: {str(e)}")
            print(f"[WORDFILTER ERROR] {e}")

    @wordfilter.command(name="setmute")
    @commands.has_permissions(manage_roles=True)
    async def wordfilter_setmute(self, ctx, role: discord.Role):
        """Set the mute role for the word filter mute action"""
        if not ctx.guild:
            await ctx.send("❌ This command can only be used in servers.")
            return

        self.setup_wordfilter_db()

        # Check if bot can assign this role
        if role.position >= ctx.guild.me.top_role.position:
            await ctx.send("❌ I cannot assign this role as it's higher than or equal to my highest role.")
            return

        try:
            with sqlite3.connect('databases/wordfilter.db') as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO wordfilter_settings (guild_id, mute_role_id)
                    VALUES (?, ?)
                """, (ctx.guild.id, role.id))
                conn.commit()

                embed = discord.Embed(
                    title="✅ Mute Role Set",
                    description=f"Mute role has been set to {role.mention}",
                    color=0x00ff00
                )
                embed.add_field(
                    name="ℹ️ Info", 
                    value="This role will be assigned to users when the 'mute' action is triggered for banned words.",
                    inline=False
                )
                await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Error setting mute role: {str(e)}")

    @wordfilter.command(name="remove")
    @commands.has_permissions(manage_messages=True)
    async def wordfilter_remove(self, ctx, user: discord.Member, *, word: str):
        """Remove a banned word for a specific user"""
        if not ctx.guild:
            await ctx.send("❌ This command can only be used in servers.")
            return

        word = word.strip().lower()

        try:
            with sqlite3.connect('databases/wordfilter.db') as conn:
                cursor = conn.execute("""
                    DELETE FROM user_word_bans 
                    WHERE guild_id = ? AND user_id = ? AND banned_word = ?
                """, (ctx.guild.id, user.id, word))

                if cursor.rowcount == 0:
                    await ctx.send(f"❌ The word `{word}` was not found in {user.mention}'s banned words.")
                    return

                conn.commit()

                embed = discord.Embed(
                    title="✅ Word Unbanned",
                    description=f"The word `{word}` has been removed from {user.mention}'s banned words",
                    color=0x00ff00
                )
                await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Error removing banned word: {str(e)}")

    @wordfilter.command(name="list")
    @commands.has_permissions(manage_messages=True)
    async def wordfilter_list(self, ctx, user: Optional[discord.Member] = None):
        """List banned words for a user or all users"""
        if not ctx.guild:
            await ctx.send("❌ This command can only be used in servers.")
            return

        try:
            with sqlite3.connect('databases/wordfilter.db') as conn:
                if user:
                    # List words for specific user
                    cursor = conn.execute("""
                        SELECT banned_word, action, added_by, added_at 
                        FROM user_word_bans 
                        WHERE guild_id = ? AND user_id = ?
                        ORDER BY added_at DESC
                    """, (ctx.guild.id, user.id))

                    words = cursor.fetchall()

                    if not words:
                        await ctx.send(f"❌ No banned words found for {user.mention}")
                        return

                    embed = discord.Embed(
                        title=f"🚫 Banned Words for {user.display_name}",
                        color=self.color
                    )

                    word_list = []
                    for word, action, added_by_id, added_at in words:
                        added_by = ctx.guild.get_member(added_by_id)
                        added_by_name = added_by.display_name if added_by else f"ID:{added_by_id}"
                        word_list.append(f"`{word}` **[{action.upper()}]** - Added by {added_by_name}")

                    embed.description = "\n".join(word_list[:10])  # Limit to 10 words

                    if len(words) > 10:
                        embed.set_footer(text=f"Showing 10 of {len(words)} banned words")

                else:
                    # List all users with banned words
                    cursor = conn.execute("""
                        SELECT user_id, COUNT(*) as word_count
                        FROM user_word_bans 
                        WHERE guild_id = ?
                        GROUP BY user_id
                        ORDER BY word_count DESC
                    """, (ctx.guild.id,))

                    users = cursor.fetchall()

                    if not users:
                        await ctx.send("❌ No banned words found in this server.")
                        return

                    embed = discord.Embed(
                        title="🚫 Word Filter Overview",
                        description="Users with banned words:",
                        color=self.color
                    )

                    user_list = []
                    for user_id, word_count in users[:15]:  # Limit to 15 users
                        member = ctx.guild.get_member(user_id)
                        member_name = member.display_name if member else f"ID:{user_id}"
                        user_list.append(f"{member.mention if member else f'<@{user_id}>'} - {word_count} banned word{'s' if word_count != 1 else ''}")

                    embed.description = "\n".join(user_list)

                    if len(users) > 15:
                        embed.set_footer(text=f"Showing 15 of {len(users)} users with banned words")

                await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Error listing banned words: {str(e)}")

    @wordfilter.command(name="clear")
    @commands.has_permissions(manage_messages=True)
    async def wordfilter_clear(self, ctx, user: discord.Member):
        """Clear all banned words for a specific user"""
        if not ctx.guild:
            await ctx.send("❌ This command can only be used in servers.")
            return

        try:
            with sqlite3.connect('databases/wordfilter.db') as conn:
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM user_word_bans 
                    WHERE guild_id = ? AND user_id = ?
                """, (ctx.guild.id, user.id))

                count = cursor.fetchone()[0]

                if count == 0:
                    await ctx.send(f"❌ {user.mention} has no banned words.")
                    return

                conn.execute("""
                    DELETE FROM user_word_bans 
                    WHERE guild_id = ? AND user_id = ?
                """, (ctx.guild.id, user.id))

                conn.commit()

                embed = discord.Embed(
                    title="✅ Banned Words Cleared",
                    description=f"Removed {count} banned word{'s' if count != 1 else ''} for {user.mention}",
                    color=0x00ff00
                )
                await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Error clearing banned words: {str(e)}")

    @wordfilter.command(name="settings")
    @commands.has_permissions(manage_guild=True)
    async def wordfilter_settings(self, ctx):
        """Configure word filter settings for the server"""
        if not ctx.guild:
            await ctx.send("❌ This command can only be used in servers.")
            return

        self.setup_wordfilter_db()

        embed = discord.Embed(
            title="⚙️ Word Filter Settings",
            description="Configure how the word filter behaves in this server",
            color=self.color
        )
        embed.add_field(
            name="📝 Available Settings",
            value=(
                "• `log_channel` - Set logging channel\n"
                "• `delete_message` - Auto-delete filtered messages\n"
                "• `warn_user` - Send warning to users\n"
                "• `timeout_duration` - Timeout duration (seconds)"
            ),
            inline=False
        )
        embed.set_footer(text="Use 'wordfilter settings <setting> <value>' to configure")

        await ctx.send(embed=embed)

    @commands.command(name="testwordfilter", aliases=["testwf"])
    @commands.has_permissions(manage_messages=True)
    @blacklist_check()
    @ignore_check()
    async def test_wordfilter(self, ctx, user: discord.Member):
        """Test wordfilter for a specific user"""
        try:
            with sqlite3.connect('databases/wordfilter.db') as conn:
                cursor = conn.execute("""
                    SELECT banned_word, action FROM user_word_bans 
                    WHERE guild_id = ? AND user_id = ?
                """, (ctx.guild.id, user.id))

                banned_words = cursor.fetchall()

                embed = discord.Embed(
                    title="🧪 Wordfilter Test Results",
                    description=f"Testing wordfilter for {user.mention}",
                    color=0x0099ff
                )

                if banned_words:
                    word_list = "\n".join([f"`{word}` → **{action}**" for word, action in banned_words])
                    embed.add_field(name="Banned Words", value=word_list, inline=False)
                    embed.add_field(name="Status", value="✅ Wordfilter should be active", inline=False)
                else:
                    embed.add_field(name="Status", value="❌ No banned words found", inline=False)

                # Check bot permissions
                perms = ctx.guild.me.guild_permissions
                perm_status = "✅ Bot can delete messages" if perms.manage_messages else "❌ Bot cannot delete messages"
                embed.add_field(name="Bot Permissions", value=perm_status, inline=False)

                await ctx.send(embed=embed)

        except Exception as e:
            embed = discord.Embed(
                title="❌ Test Failed",
                description=f"Error testing wordfilter: {e}",
                color=0xff0000
            )
            await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        """Check messages for banned words"""
        # More detailed debugging
        if message.guild and not message.author.bot:
            print(f"[WORDFILTER DEBUG] Processing message from {message.author} ({message.author.id}) in {message.guild.name}")
            print(f"[WORDFILTER DEBUG] Message content: '{message.content}'")
            print(f"[WORDFILTER DEBUG] Bot permissions - manage_messages: {message.guild.me.guild_permissions.manage_messages}")
            print(f"[WORDFILTER DEBUG] User permissions - manage_messages: {message.author.guild_permissions.manage_messages}")
        else:
            print(f"[WORDFILTER DEBUG] Skipping message: guild={bool(message.guild)}, author_bot={message.author.bot}")
            return

        if not message.guild or message.author.bot:
            print(f"[WORDFILTER DEBUG] Skipping: guild={message.guild}, bot={message.author.bot}")
            return

        # Skip if user has manage_messages permission
        if message.author.guild_permissions.manage_messages:
            print(f"[WORDFILTER DEBUG] Skipping: {message.author} has manage_messages permission")
            return

        try:
            with sqlite3.connect('databases/wordfilter.db') as conn:
                # Get banned words for this user
                cursor = conn.execute("""
                    SELECT banned_word, action FROM user_word_bans 
                    WHERE guild_id = ? AND user_id = ?
                """, (message.guild.id, message.author.id))

                banned_words = cursor.fetchall()
                print(f"[WORDFILTER DEBUG] Found {len(banned_words)} banned words for user {message.author.id}: {banned_words}")

                if not banned_words:
                    return

                # Check message content for banned words (improved matching)
                message_content = message.content.lower()
                found_violations = []

                for word, action in banned_words:
                    # Use regex for better word boundary matching
                    import re
                    word_pattern = r'\b' + re.escape(word.lower()) + r'\b'
                    print(f"[WORDFILTER DEBUG] Checking pattern '{word_pattern}' against '{message_content}'")
                    if re.search(word_pattern, message_content):
                        found_violations.append((word, action))
                        print(f"[WORDFILTER DEBUG] MATCH FOUND! Word '{word}' with action '{action}'")

                if not found_violations:
                    return

                print(f"[WORDFILTER DEBUG] Found violations for {message.author}: {found_violations}")

                # Get server settings
                cursor = conn.execute("""
                    SELECT log_channel_id, delete_message, warn_user, mute_role_id
                    FROM wordfilter_settings WHERE guild_id = ?
                """, (message.guild.id,))

                settings = cursor.fetchone()
                if not settings:
                    # Default settings
                    delete_msg, warn_user, log_channel_id, mute_role_id = True, True, None, None
                else:
                    log_channel_id, delete_msg, warn_user, mute_role_id = settings

                # Delete message first (for all actions)
                message_deleted = False
                try:
                    if not message.guild.me.guild_permissions.manage_messages:
                        print(f"[WORDFILTER ERROR] Bot lacks 'Manage Messages' permission in {message.guild.name}")
                        action_taken = "Failed - Bot lacks Manage Messages permission"
                    else:
                        await message.delete()
                        message_deleted = True
                        print(f"[WORDFILTER DEBUG] Message deleted from {message.author}")
                except (discord.NotFound, discord.Forbidden) as e:
                    print(f"[WORDFILTER DEBUG] Could not delete message: {e}")
                except Exception as e:
                    print(f"[WORDFILTER ERROR] Unexpected error deleting message: {e}")

                # Apply the highest severity action found
                actions_priority = {'delete': 1, 'warn': 2, 'mute': 3, 'kick': 4, 'ban': 5}
                highest_action = max(found_violations, key=lambda x: actions_priority.get(x[1], 0))[1]
                found_words = [word for word, action in found_violations]

                print(f"[WORDFILTER DEBUG] Applying action: {highest_action}")

                # Apply moderation action
                action_taken = "Message deleted"
                try:
                    if highest_action == 'warn':
                        action_taken = "Message deleted + Warning sent"
                    elif highest_action == 'mute':
                        if mute_role_id:
                            mute_role = message.guild.get_role(mute_role_id)
                            if mute_role and mute_role not in message.author.roles:
                                await message.author.add_roles(mute_role, reason=f"Used banned word(s): {', '.join(found_words)}")
                                action_taken = "Message deleted + User muted"
                            else:
                                action_taken = "Message deleted + Mute failed (role not found or already muted)"
                        else:
                            action_taken = "Message deleted + Mute failed (no mute role set)"
                    elif highest_action == 'kick':
                        await message.author.kick(reason=f"Used banned word(s): {', '.join(found_words)}")
                        action_taken = "Message deleted + User kicked"
                    elif highest_action == 'ban':
                        await message.author.ban(reason=f"Used banned word(s): {', '.join(found_words)}")
                        action_taken = "Message deleted + User banned"
                except discord.Forbidden:
                    action_taken += " (Failed - insufficient permissions)"
                except Exception as e:
                    action_taken += f" (Failed - {str(e)})"
                    print(f"[WORDFILTER ERROR] Action failed: {e}")

                # Send warning to user if configured and action allows it
                if warn_user and highest_action in ['delete', 'warn', 'mute']:
                    embed = discord.Embed(
                        title="⚠️ Message Filtered",
                        description=f"Your message contained banned word{'s' if len(found_words) > 1 else ''}: `{'`, `'.join(found_words)}`",
                        color=0xff9900
                    )
                    embed.add_field(name="Action Taken", value=action_taken, inline=False)
                    try:
                        await message.author.send(embed=embed)
                    except:
                        # If DM fails and user wasn't kicked/banned, send in channel
                        if highest_action in ['delete', 'warn', 'mute']:
                            try:
                                await message.channel.send(f"{message.author.mention}", embed=embed, delete_after=10)
                            except:
                                pass

                # Log the violation
                if log_channel_id:
                    log_channel = message.guild.get_channel(log_channel_id)
                    if log_channel:
                        embed = discord.Embed(
                            title="🚫 Word Filter Triggered",
                            color=0xff0000,
                            timestamp=discord.utils.utcnow()
                        )
                        embed.add_field(name="User", value=f"{message.author.mention} ({message.author})", inline=True)
                        embed.add_field(name="Channel", value=message.channel.mention, inline=True)
                        embed.add_field(name="Action Applied", value=highest_action.upper(), inline=True)
                        embed.add_field(name="Banned Words Found", value=f"`{'`, `'.join(found_words)}`", inline=False)
                        embed.add_field(name="Action Result", value=action_taken, inline=False)
                        embed.add_field(name="Original Message", value=message.content[:1000] if len(message.content) <= 1000 else message.content[:997] + "...", inline=False)

                        try:
                            await log_channel.send(embed=embed)
                        except Exception as e:
                            print(f"[WORDFILTER ERROR] Could not send to log channel: {e}")

        except Exception as e:
            print(f"[WORDFILTER ERROR] {e}")
            import traceback
            traceback.print_exc()


async def setup(bot):
    await bot.add_cog(General(bot))