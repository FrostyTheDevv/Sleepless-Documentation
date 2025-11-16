from utils.error_helpers import StandardErrorHandler
##################################
import discord
import typing
import requests
import aiohttp
import datetime
import random
import os
from discord.ext import commands
from random import randint
from utils.Tools import *
from core import Cog, sleepless, Context
from utils.config import *
from pathlib import Path
import json
from PIL import Image, ImageDraw, ImageOps
import io


def RandomColor():
  randcolor = discord.Color(random.randint(0x006fb9, 0xFFFFFF))
  return randcolor

RAPIDAPI_HOST = "truth-dare.p.rapidapi.com"
RAPIDAPI_KEY = "1cd7c71534msh2544b357ec07ad8p18fa0bjsn1358eef1f8e9"

class Fun(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.giphy_token = 'y3KcqQTdiS0RYcpNJrWn8hFGglKqX4is'
        self.google_api_key = 'AIzaSyA022fwm_TOQcYTg1N_ohqqIj_RUFUM9BY'
        self.search_engine_id = '2166875ec165a6c21'

    async def download_avatar(self, url):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                data = await resp.read()
                return Image.open(io.BytesIO(data)).convert("RGBA")

    def circle_avatar(self, avatar):
        mask = Image.new("L", avatar.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0) + avatar.size, fill=255)
        avatar = ImageOps.fit(avatar, mask.size, centering=(0.5, 0.5))
        avatar.putalpha(mask)
        return avatar

    async def add_role(self, *, role: int, member: discord.Member):
        if member.guild.me.guild_permissions.manage_roles:
            # Fetch the actual Role object from the guild
            role_obj = discord.utils.get(member.guild.roles, id=role)
            if role_obj:
                await member.add_roles(role_obj, reason="Role Added via Fun cog")

    async def remove_role(self, *, role: int, member: discord.Member):
        if member.guild.me.guild_permissions.manage_roles:
            # Fetch the actual Role object from the guild
            role_obj = discord.utils.get(member.guild.roles, id=role)
            if role_obj:
                await member.remove_roles(role_obj, reason="Role Removed via Fun cog")


    async def fetch_data(self, endpoint):
        async with aiohttp.ClientSession() as session:
            headers = {
                "X-RapidAPI-Host": RAPIDAPI_HOST,
                "X-RapidAPI-Key": RAPIDAPI_KEY
            }
            async with session.get(f"https://{RAPIDAPI_HOST}{endpoint}", headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return None


    async def fetch_image(self, ctx, endpoint):
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://nekos.life/api/v2/img/{endpoint}") as response:
                if response.status == 200:
                    data = await response.json()
                    return data["url"]
                else:
                    await ctx.send("Failed to fetch image.")




    async def fetch_action_image(self, action):
        url = f"https://api.waifu.pics/sfw/{action}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.json().get('url')
        except requests.exceptions.RequestException:
            return None

    @commands.command()
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def mydog(self, ctx, user: discord.User):
        processing= await ctx.reply("<:feast_loadkr:1328740531907461233> Processing Image...")
        base_image_path = "data/pictures/mydog.jpg"
        base_image = Image.open(base_image_path).convert("RGBA")

        author_avatar_url = ctx.author.display_avatar.url
        user_avatar_url = user.display_avatar.url

        author_avatar = await self.download_avatar(author_avatar_url)
        user_avatar = await self.download_avatar(user_avatar_url)

        if author_avatar is None or user_avatar is None:
            await ctx.send("Failed to retrieve avatars.")
            return

        author_avatar = self.circle_avatar(author_avatar.resize((230, 230)))
        user_avatar = self.circle_avatar(user_avatar.resize((310, 310)))

        base_image.paste(author_avatar, (370, 0), author_avatar)
        base_image.paste(user_avatar, (0, 220), user_avatar)

        final_buffer = io.BytesIO()
        base_image.save(final_buffer, "PNG")
        final_buffer.seek(0)

        file = discord.File(fp=final_buffer, filename="mydog.png")
        await ctx.reply(file=file)
        await processing.delete()


    @commands.command(name="image", help="Search for an image and display a random one.", aliases=["img"], with_app_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def image(self, ctx, *, search_query: str):
        if not ctx.channel.is_nsfw():
            await ctx.reply("This command can only be used in NSFW (age-restricted) channels.", ephemeral=True)
            return
        
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://www.googleapis.com/customsearch/v1?key={self.google_api_key}&cx={self.search_engine_id}&q={search_query}&searchType=image") as response:
                data = await response.json()
                if "items" in data:
                    image = discord.Embed(title=f"Random Image for '{search_query}'", color=discord.Color.random())
                    image.set_image(url=random.choice(data["items"])["link"])
                    await ctx.reply(embed=image)
                else:
                    await ctx.reply("No images found for that search query.")




    @commands.command(name="howgay",
        aliases=['gay'],
        help="check someone gay percentage",
        usage="Howgay <person>")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def howgay(self, ctx, *, person: str):
        embed = discord.Embed(title="About your gayness", color=discord.Color.random())
        responses = random.randrange(1, 150)
        embed.description = f'**{person} is {responses}% Gay** :rainbow:'
        embed.set_footer(text=f'{responses}% is your gayness- {ctx.author.name}')
        await ctx.reply(embed=embed)


    @commands.command(name="lesbian",
        aliases=['lesbo'],
        help="check someone lesbian percentage",
        usage="lesbian <person>")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def lesbian(self, ctx, *, person):
        embed = discord.Embed(title=" Lesbian Meter", color=discord.Color.random())
        responses = random.randrange(1, 150)
        embed.description = f'**{person} is {responses}% Lesbian** '
        embed.set_footer(text=f'How lesbian are you? - {ctx.author.name}')
        await ctx.reply(embed=embed)

    @commands.command(name="chutiya",
        aliases=['chu'],
        help="check someone chootiyapa percentage",
        usage="Chutiya <person>")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def chutiya(self, ctx, *, person):
        embed = discord.Embed(title=" About your Chumtiyapa", color=discord.Color.random())
        responses = random.randrange(1, 150)
        embed.description = f'**Abbe {person} to {responses}% Chootiya Ha** 😂'
        embed.set_footer(text=f'How chutiya are you? - {ctx.author.name}')
        await ctx.reply(embed=embed)

    @commands.command(name="tharki",
        help="check someone tharkipan percentage",
        usage="Tharki <person>")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def tharki(self, ctx, *, person):
        embed = discord.Embed(title=" About your Tharkipan", color=discord.Color.random())
        responses = random.randrange(1, 150)
        embed.description = f'**Sala {person} to {responses}% Tharki Nikla** 😂'
        embed.set_footer(text=f'How tharki are you? - {ctx.author.name}')
        await ctx.reply(embed=embed)

    @commands.command(name="horny",
        aliases=['horniness'],
        help="check someone horniness percentage",
        usage="Horny <person>")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def horny(self, ctx, *, person):
        embed = discord.Embed(title="about your horniness", color=discord.Color.random())
        responses = random.randrange(1, 150)
        embed.description = f'**{person} is {responses}% Horny** 😳'
        embed.set_footer(text=f'How horny are you? - {ctx.author.name}')
        await ctx.reply(embed=embed)

    @commands.command(name="cute",
        aliases=['cuteness'],
        help="check someone cuteness percentage",
        usage="Cute <person>")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def cute(self, ctx, *, person):
        embed = discord.Embed(title=" About your cuteness", color=discord.Color.random())
        responses = random.randrange(1, 150)
        embed.description = f'**{person} is {responses}% Cute** 🥰'
        embed.set_footer(text=f'How cute are you? - {ctx.author.name}')
        await ctx.reply(embed=embed)

    @commands.command(name="intelligence",
        aliases=['iq'],
        help="check someone intelligence percentage",
        usage="Intelligence <person>")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def intelligence(self, ctx, *, person):
        embed = discord.Embed(title=" About your intelligence", color=discord.Color.random())
        responses = random.randrange(1, 150)
        embed.description = f'**{person} has an IQ of {responses}%** '
        embed.set_footer(text=f'How intelligent are you? - {ctx.author.name}')
        await ctx.reply(embed=embed)

    @commands.command(name="gif", help="Search for a gif and display a random one.", with_app_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def gif(self, ctx, *, search_query: str):
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.giphy.com/v1/gifs/search?api_key={self.giphy_token}&q={search_query}&limit=10") as response:
                data = await response.json()
                if "data" in data:
                    gif = discord.Embed(title=f"Random GIF for '{search_query}'", color=discord.Color.random())
                    gif.set_image(url=random.choice(data["data"])["images"]["original"]["url"])
                    await ctx.reply(embed=gif)
                else:
                    await ctx.reply("No GIFs found for that search query.")

    @commands.command(name="iplookup", aliases=['ip'], help="Get accurate IP info for IPv4 and IPv6", usage="iplookup [ip]")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def iplookup(self, ctx, *, ip=None):
        import ipaddress
        import re

        # Track if we're showing user's own IP
        is_own_ip = ip is None

        # If IP is provided, validate it
        if ip is not None:
            ip = ip.strip()
            try:
                # Validate if it's a proper IP address (IPv4 or IPv6)
                ipaddress.ip_address(ip)
            except ValueError:
                embed = discord.Embed(
                    description=f"❌ Invalid IP address format: `{ip}`\nPlease provide a valid IPv4 or IPv6 address.",
                    color=0xFF0000
                )
                await ctx.send(embed=embed)
                return

        # If no IP provided, get the user's public IP
        if ip is None:
            async with aiohttp.ClientSession() as session:
                try:
                    # Try to get user's public IP (usually IPv4)
                    timeout = aiohttp.ClientTimeout(total=10)
                    async with session.get("http://ip-api.com/json/", timeout=timeout) as response:
                        data = await response.json()

                        if data['status'] == 'fail':
                            embed = discord.Embed(
                                description="❌ Failed to retrieve your IP information. Please provide a specific IP address to lookup.",
                                color=0xFF0000)
                            await ctx.send(embed=embed)
                            return

                        # Use the detected IP
                        ip = data.get('query', '')
                        if not ip:
                            embed = discord.Embed(
                                description="❌ Could not detect your IP address. Please provide a specific IP address to lookup.",
                                color=0xFF0000)
                            await ctx.send(embed=embed)
                            return
                except Exception as e:
                    embed = discord.Embed(
                        description=f"❌ Error detecting your IP address: {str(e)}\nPlease provide a specific IP address to lookup.",
                        color=0xFF0000
                    )
                    await ctx.send(embed=embed)
                    return

        # Determine IP version for display
        try:
            ip_obj = ipaddress.ip_address(ip)
            ip_version = f"IPv{ip_obj.version}"
            is_ipv6 = ip_obj.version == 6
        except:
            ip_version = "IP"
            is_ipv6 = False

        async with aiohttp.ClientSession() as session:
            try:
                # Use ip-api.com which supports both IPv4 and IPv6
                lookup_timeout = aiohttp.ClientTimeout(total=15)
                async with session.get(f"http://ip-api.com/json/{ip}?fields=status,message,continent,continentCode,country,countryCode,region,regionName,city,district,zip,lat,lon,timezone,offset,currency,isp,org,as,asname,reverse,mobile,proxy,hosting,query", timeout=lookup_timeout) as response:
                    data = await response.json()

                if data.get('status') == 'fail':
                    error_msg = data.get('message', 'Unknown error')
                    embed = discord.Embed(
                        description=f"❌ Failed to retrieve data for `{ip}`: {error_msg}\nPlease check the IP address and try again.",
                        color=0xFF0000)
                    await ctx.send(embed=embed)
                    return

                # Extract data with fallbacks
                query = data.get('query', ip)
                continent = data.get('continent', 'N/A')
                continent_code = data.get('continentCode', 'N/A')
                country = data.get('country', 'N/A')
                country_code = data.get('countryCode', 'N/A')
                region_name = data.get('regionName', 'N/A')
                region = data.get('region', 'N/A')
                city = data.get('city', 'N/A')
                district = data.get('district', 'N/A')
                zip_code = data.get('zip', 'N/A')
                latitude = data.get('lat', 'N/A')
                longitude = data.get('lon', 'N/A')
                timezone = data.get('timezone', 'N/A')
                offset = data.get('offset', 'N/A')
                currency = data.get('currency', 'N/A')
                isp = data.get('isp', 'N/A')
                organization = data.get('org', 'N/A')
                asn = data.get('as', 'N/A')
                asname = data.get('asname', 'N/A')
                reverse_dns = data.get('reverse', 'N/A')
                mobile = data.get('mobile', 'N/A')
                proxy = data.get('proxy', 'N/A')
                hosting = data.get('hosting', 'N/A')

                # Create enhanced embed with IPv6 support
                title = f"{'🔍 Your IP' if is_own_ip else f'🔍 {ip_version} Lookup'}: {query}"

                embed = discord.Embed(
                    title=title,
                    description=(
                        f"🌏 **Location Information**\n"
                        f"**IP Address:** `{query}` ({ip_version})\n"
                        f"**Continent:** {continent} ({continent_code})\n"
                        f"**Country:** {country} 🌐 {country_code}\n"
                        f"**Region:** {region_name} ({region})\n"
                        f"**City:** {city}\n"
                        + (f"**District:** {district}\n" if district != 'N/A' else "")
                        + (f"**Postal Code:** {zip_code}\n" if zip_code != 'N/A' else "")
                        + f"**Coordinates:** {latitude}, {longitude}\n"
                        f"\n"
                        f"⏰ **Time Information**\n"
                        f"**Timezone:** {timezone}\n"
                        f"**UTC Offset:** {offset}\n"
                        + (f"**Currency:** {currency}\n" if currency != 'N/A' else "")
                        + f"\n"
                        f"🛜 **Network Information**\n"
                        f"**ISP:** {isp}\n"
                        f"**Organization:** {organization}\n"
                        f"**ASN:** {asn}\n"
                        f"**AS Name:** {asname}\n"
                        + (f"**Reverse DNS:** {reverse_dns}\n" if reverse_dns != 'N/A' else "")
                        + f"\n"
                        f"⚠️ **Security Information**\n"
                        f"**Mobile:** {'✅ Yes' if mobile else '❌ No'}\n"
                        f"**Proxy:** {'⚠️ Yes' if proxy else '✅ No'}\n"
                        f"**Hosting:** {'🏢 Yes' if hosting else '🏠 No'}\n"
                    ),
                    color=0x006fb9 if not proxy else 0xff9500  # Orange if proxy detected
                )

                # Add special IPv6 footer
                footer_text = f'Made by Sleepless Development™'
                if is_ipv6:
                    footer_text += ' • IPv6 Supported'

                embed.set_footer(
                    text=footer_text,
                    icon_url=getattr(getattr(self.bot.user, 'avatar', None), 'url', None)
                )

                # Add warning for proxies/hosting
                if proxy or hosting:
                    embed.add_field(
                        name="⚠️ Security Notice",
                        value="This IP appears to be associated with " + 
                            ("a proxy service" if proxy else "") +
                            (" and " if proxy and hosting else "") +
                            ("hosting services" if hosting else ""),
                        inline=False
                    )

                await ctx.reply(embed=embed)

            except Exception as e:
                embed = discord.Embed(
                    description=f"❌ An error occurred while looking up `{ip}`: {str(e)}",
                    color=0xFF0000
                )
                await ctx.send(embed=embed)

        ############################

    @commands.command()
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def weather(self, ctx, *, city: str):
        api_key = "b81e2218c328686836ab6d9d31ce97d0"
        base_url = "http://api.openweathermap.org/data/2.5/weather?"
        city_name = city
        complete_url = f"{base_url}q={city_name}&APPID={api_key}"

        async with aiohttp.ClientSession() as session:
            async with session.get(complete_url) as response:
                data = await response.json()
                if data["cod"] != "404":
                    main = data['main']
                    temperature = main['temp']
                    temp_celsius = temperature - 273.15
                    humidity = main['humidity']
                    pressure = main['pressure']
                    report = data['weather']
                    weather_desc = report[0]['description']

                    weather_embed = discord.Embed(
                        title=f"☁️ Weather in {city_name}",
                        color=0x006fb9
                    )
                    weather_embed.add_field(name="Description", value=weather_desc.capitalize(), inline=False)
                    weather_embed.add_field(name="Temperature (Celsius)", value=f"{temp_celsius:.2f} °C", inline=False)
                    weather_embed.add_field(name="Humidity", value=f"{humidity}%", inline=False)
                    weather_embed.add_field(name="Pressure", value=f"{pressure} hPa", inline=False)
                    weather_embed.set_footer(
                        text=f"Requested By {ctx.author}",
                        icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
                    )

                    await ctx.reply(embed=weather_embed)
                else:
                    await ctx.reply("City not found. Please enter a valid city name.")

    @commands.command(name="fakeban", aliases=['fban'], help="Send a fake ban message for fun", usage="fakeban <member>")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def fake_ban(self, ctx, user: discord.Member):
        embed = discord.Embed(
        title="Successfully Banned!",
        description=f"<:feast_tick:1400143469892210753> | {user.mention} has been successfully banned",
        color=0x006fb9
        )
        embed.set_footer(
        text=f"Banned By {ctx.author}",
        icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
        )
        await ctx.reply(embed=embed)





    @commands.command(name="truth", aliases=["t"], help="Get a random truth question for games", usage="truth")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.max_concurrency(5, per=commands.BucketType.default, wait=False)
    async def truth(self, ctx):
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.truthordarebot.xyz/api/truth") as response:
                if response.status == 200:
                    data = await response.json()
                    question = data.get("question")
                    if question:
                        embed= discord.Embed(title="__**TRUTH**__",description=f"{question}", color=0x006fb9)
                        await ctx.reply(embed=embed)
                    else:
                        await ctx.send("Couldn't retrieve a truth question. Please try again.")
                else:
                    await ctx.send("Error fetching truth question. Please try again.")

    @commands.command(name="dare", aliases=["d"], help="Get a random dare challenge for games", usage="dare")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.max_concurrency(5, per=commands.BucketType.default, wait=False)
    async def dare(self, ctx):
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.truthordarebot.xyz/api/dare") as response:
                if response.status == 200:
                    data = await response.json()
                    question = data.get("question")
                    if question:
                        embed= discord.Embed(title="__**DARE**__",description=f"{question}", color=0x006fb9)
                        await ctx.reply(embed=embed)
                    else:
                        await ctx.send("Couldn't retrieve a dare question. Please try again.")
                else:
                    await ctx.send("Error fetching dare question. Please try again.")




    @commands.command(name="translate", aliases=["tl"], help="Translate text to English using AI", usage="translate <text>")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def translate_command(self, ctx, *, message=None):
        import requests  # Make sure this is at the top of your file

        if message is None:
            if ctx.message.reference:
                replied_msg = await ctx.fetch_message(ctx.message.reference.message_id)
                if replied_msg:
                    message = replied_msg.content
                else:
                    await ctx.reply("❌ Error: No message found to translate.")
                    return
            else:
                await ctx.reply("❌ Please provide a message to translate or reply to one.")
                return

        processing_message = await ctx.send("🔄 Translating...")

        base_url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": "auto",     # Auto-detect source language
            "tl": "en",       # Translate to English
            "dt": "t",
            "q": message
        }

        try:
            response = requests.get(base_url, params=params)
            if response.status_code == 200:
                data = response.json()
                translated_text = data[0][0][0]
                detected_lang = data[2]  # Detected language code

                embed = discord.Embed(title="🌐 Translation Result", color=0x5865F2)
                embed.add_field(name="Original", value=message, inline=False)
                embed.add_field(name="Translated", value=translated_text, inline=False)
                embed.set_footer(
                    text=f"Detected Language: {detected_lang.upper()} • Requested by {ctx.author}",
                    icon_url=ctx.author.display_avatar.url
                )
                await ctx.reply(embed=embed)
            else:
                await ctx.send("❌ Translation failed. Please try again later.")
        except Exception as e:
            await ctx.reply(f"⚠️ An error occurred: `{e}`")
        finally:
            await processing_message.delete()

    @commands.command(name="wiki", aliases=['wikipedia'], help="Search Wikipedia for articles", usage="wiki <search term>")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def wiki(self, ctx, *, search_term: str):
        """Search Wikipedia for articles and display summary with rich formatting"""
        import re

        if not search_term or len(search_term.strip()) < 2:
            embed = discord.Embed(
                description="❌ Please provide a search term with at least 2 characters.",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return

        # Clean the search term
        search_term = search_term.strip()

        # Send processing message
        processing = await ctx.send("🔍 Searching Wikipedia...")

        # Set proper headers for Wikipedia API
        headers = {
            'User-Agent': 'SleeplessBot/1.0 (Discord Bot; https://github.com/FrostyTheDevv/Sleepless.Pyt; Contact: frostythedevvm@gmail.com)'
        }

        async with aiohttp.ClientSession(headers=headers) as session:
            try:
                # Step 1: Search for articles
                search_url = "https://en.wikipedia.org/api/rest_v1/page/summary/"
                search_timeout = aiohttp.ClientTimeout(total=10)

                # First try direct page lookup
                try:
                    encoded_term = search_term.replace(' ', '_')
                    async with session.get(f"{search_url}{encoded_term}", timeout=search_timeout) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get('type') != 'disambiguation':
                                # Found direct match
                                await self._send_wiki_result(ctx, data, processing)
                                return
                except:
                    pass

                # Step 2: Use search API if direct lookup failed
                search_api = "https://en.wikipedia.org/w/api.php"
                search_params = {
                    'action': 'query',
                    'format': 'json',
                    'list': 'search',
                    'srsearch': search_term,
                    'srlimit': 5,
                    'srprop': 'snippet|titlesnippet'
                }

                async with session.get(search_api, params=search_params, timeout=search_timeout) as response:
                    if response.status != 200:
                        raise Exception("Wikipedia search API unavailable")

                    search_data = await response.json()
                    search_results = search_data.get('query', {}).get('search', [])

                    if not search_results:
                        embed = discord.Embed(
                            title="📚 Wikipedia Search",
                            description=f"❌ No results found for **{search_term}**",
                            color=0xFF0000
                        )
                        await processing.edit(content="", embed=embed)
                        return

                    # Get the first result's full page data
                    first_result = search_results[0]
                    page_title = first_result['title']

                    # Get full page summary
                    encoded_title = page_title.replace(' ', '_')
                    async with session.get(f"{search_url}{encoded_title}", timeout=search_timeout) as response:
                        if response.status == 200:
                            page_data = await response.json()
                            await self._send_wiki_result(ctx, page_data, processing, search_results)
                        else:
                            raise Exception("Failed to fetch page details")

            except Exception as e:
                embed = discord.Embed(
                    title="❌ Wikipedia Error",
                    description=f"Failed to search Wikipedia: {str(e)}",
                    color=0xFF0000
                )
                await processing.edit(content="", embed=embed)

    async def _send_wiki_result(self, ctx, page_data, processing_msg, search_results=None):
        """Send formatted Wikipedia result"""
        try:
            title = page_data.get('title', 'Unknown')
            extract = page_data.get('extract', 'No summary available.')
            page_url = page_data.get('content_urls', {}).get('desktop', {}).get('page', '')
            thumbnail = page_data.get('thumbnail', {}).get('source', '')

            # Clean and truncate extract
            if len(extract) > 1000:
                extract = extract[:997] + "..."

            # Remove HTML tags and fix formatting
            import re
            extract = re.sub(r'<[^>]+>', '', extract)
            extract = re.sub(r'\([^)]*\)', '', extract)  # Remove parenthetical info
            extract = re.sub(r'\s+', ' ', extract).strip()  # Clean whitespace

            # Create main embed
            embed = discord.Embed(
                title=f"📚 {title}",
                description=extract,
                url=page_url,
                color=0x006fb9
            )

            # Add thumbnail if available
            if thumbnail:
                embed.set_thumbnail(url=thumbnail)

            # Add page info
            if 'coordinates' in page_data:
                coords = page_data['coordinates']
                embed.add_field(
                    name="📍 Location",
                    value=f"{coords.get('lat', 0):.4f}, {coords.get('lon', 0):.4f}",
                    inline=True
                )

            # Add page stats
            if 'length' in page_data:
                embed.add_field(
                    name="📄 Page Length",
                    value=f"{page_data['length']:,} characters",
                    inline=True
                )

            # Add last modified if available
            if 'timestamp' in page_data:
                from datetime import datetime
                try:
                    timestamp = datetime.fromisoformat(page_data['timestamp'].replace('Z', '+00:00'))
                    embed.add_field(
                        name="🕒 Last Modified",
                        value=timestamp.strftime("%B %d, %Y"),
                        inline=True
                    )
                except:
                    pass

            # Add disambiguation info if we have search results
            if search_results and len(search_results) > 1:
                other_results = []
                for i, result in enumerate(search_results[1:4], 1):  # Show up to 3 more
                    snippet = result.get('snippet', '').replace('<span class="searchmatch">', '**').replace('</span>', '**')
                    snippet = re.sub(r'<[^>]+>', '', snippet)
                    if len(snippet) > 100:
                        snippet = snippet[:97] + "..."
                    other_results.append(f"{i+1}. **{result['title']}** - {snippet}")

                if other_results:
                    embed.add_field(
                        name="🔍 Other Results",
                        value="\n".join(other_results),
                        inline=False
                    )

            # Add footer
            embed.set_footer(
                text="Wikipedia • Click title to read full article",
                icon_url="https://upload.wikimedia.org/wikipedia/commons/thumb/8/80/Wikipedia-logo-v2.svg/200px-Wikipedia-logo-v2.svg.png"
            )

            # Create view with buttons
            view = WikipediaView(page_url, title)

            await processing_msg.edit(content="", embed=embed, view=view)

        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to format Wikipedia result: {str(e)}",
                color=0xFF0000
            )
            await processing_msg.edit(content="", embed=embed)

class WikipediaView(discord.ui.View):
    """Interactive view for Wikipedia results"""
    
    def __init__(self, page_url, title):
        super().__init__(timeout=300)
        self.page_url = page_url
        self.title = title
        
        # Add external link button
        if page_url:
            self.add_item(discord.ui.Button(
                label="Read Full Article",
                url=page_url,
                emoji="📖",
                style=discord.ButtonStyle.link
            ))
    
    @discord.ui.button(label="Random Article", emoji="🎲", style=discord.ButtonStyle.secondary)
    async def random_article(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Get a random Wikipedia article"""
        await interaction.response.defer()
        
        # Set proper headers for Wikipedia API
        headers = {
            'User-Agent': 'SleeplessBot/1.0 (Discord Bot; https://github.com/FrostyTheDevv/Sleepless.Pyt; Contact: billyv.com@gmail.com)'
        }
        
        async with aiohttp.ClientSession(headers=headers) as session:
            try:
                # Get random article
                random_url = "https://en.wikipedia.org/api/rest_v1/page/random/summary"
                timeout = aiohttp.ClientTimeout(total=10)
                
                async with session.get(random_url, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        title = data.get('title', 'Unknown')
                        extract = data.get('extract', 'No summary available.')
                        page_url = data.get('content_urls', {}).get('desktop', {}).get('page', '')
                        thumbnail = data.get('thumbnail', {}).get('source', '')
                        
                        # Truncate extract
                        if len(extract) > 800:
                            extract = extract[:797] + "..."
                        
                        embed = discord.Embed(
                            title=f"🎲 Random Article: {title}",
                            description=extract,
                            url=page_url,
                            color=0x006fb9
                        )
                        
                        if thumbnail:
                            embed.set_thumbnail(url=thumbnail)
                        
                        embed.set_footer(
                            text="Wikipedia • Random Article",
                            icon_url="https://upload.wikimedia.org/wikipedia/commons/thumb/8/80/Wikipedia-logo-v2.svg/200px-Wikipedia-logo-v2.svg.png"
                        )
                        
                        # Update view with new URL
                        new_view = WikipediaView(page_url, title)
                        await interaction.edit_original_response(embed=embed, view=new_view)
                    else:
                        await interaction.followup.send("❌ Failed to get random article", ephemeral=True)
            except Exception as e:
                await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

    def help_custom(self):
        return "🎮", "Fun & AI Generation", "Fun commands, AI generation, IP lookup & interactive games"

async def setup(bot):
    await bot.add_cog(Fun(bot))




