from __future__ import annotations
from discord.ext import commands
import discord
from discord.ext import commands
import datetime
from collections import Counter
from PIL import Image, ImageDraw, ImageFont
import discord
import json
import datetime
import asyncio
import aiosqlite
from typing import Optional
from utils import Paginator, DescriptionEmbedPaginator, FieldPagePaginator, TextPaginator
from utils.Tools import *
from utils.config import OWNER_IDS
from core import Cog, sleepless, Context
from utils.timezone_helpers import get_timezone_helpers
import sqlite3
import os
import subprocess
import requests
from io import BytesIO
import yt_dlp
try:
    import wavelink
except ImportError:
    wavelink = None
from utils.config import OWNER_IDS
from discord.errors import Forbidden
from discord import Embed
from discord.ui import Button, View




from utils.error_helpers import StandardErrorHandler
BADGE_URLS = {
    "owner": "https://cdn.discordapp.com/emojis/1228227536207740989.png",
    "staff": "https://cdn.discordapp.com/emojis/1228227884481515613.png",
    "partner": "https://cdn.discordapp.com/emojis/1228228301089144976.png",
    "sponsor": "https://cdn.discordapp.com/emojis/1228246375180013678.png",
    "friend": "https://cdn.discordapp.com/emojis/1228229690376982549.png",
    "early": "https://cdn.discordapp.com/emojis/1228241490246111302.png",
    "vip": "https://cdn.discordapp.com/emojis/1228230884583276584.png",
    "bug": "https://cdn.discordapp.com/emojis/1228231513456382015.png"
}

BADGE_NAMES = {
    "owner": "Owner",
    "staff": "Staff",
    "partner": "Partner",
    "sponsor": "Sponsor",
    "friend": "Owner's Friend",
    "early": "Early Supporter",
    "vip": "VIP",
    "bug": "Bug Hunter"
}


db_folder = 'db'
db_file = 'badges.db'
db_path = os.path.join(db_folder, db_file)
FONT_PATH = os.path.join('utils', 'arial.ttf')


conn = sqlite3.connect(db_path)
c = conn.cursor()


c.execute('''CREATE TABLE IF NOT EXISTS badges (
    user_id INTEGER PRIMARY KEY,
    owner INTEGER DEFAULT 0,
    staff INTEGER DEFAULT 0,
    partner INTEGER DEFAULT 0,
    sponsor INTEGER DEFAULT 0,
    friend INTEGER DEFAULT 0,
    early INTEGER DEFAULT 0,
    vip INTEGER DEFAULT 0,
    bug INTEGER DEFAULT 0
)''')
conn.commit()

def add_badge(user_id, badge):
    c.execute(f"SELECT {badge} FROM badges WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    if result is None:
        c.execute(f"INSERT INTO badges (user_id, {badge}) VALUES (?, 1)", (user_id,))
    elif result[0] == 0:
        c.execute(f"UPDATE badges SET {badge} = 1 WHERE user_id = ?", (user_id,))
    else:
        return False
    conn.commit()
    return True

def remove_badge(user_id, badge):
    c.execute(f"SELECT {badge} FROM badges WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    if result and result[0] == 1:
        c.execute(f"UPDATE badges SET {badge} = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        return True
    return False


def convert_time_to_seconds(time_str):
    time_units = {
        "h": "hours",
        "d": "days",
        "m": "months"
    }
    num = int(time_str[:-1])
    unit = time_units.get(time_str[-1])
    if isinstance(unit, str) and isinstance(num, int):
        return datetime.timedelta(**{str(unit): num})
    return None


async def do_removal(ctx, limit, predicate, *, before=None, after=None):
  if limit > 2000:
      return await ctx.error(f"Too many messages to search given ({limit}/2000)")

  if before is None:
      before = ctx.message
  else:
      before = discord.Object(id=before)

  if after is not None:
      after = discord.Object(id=after)

  try:
      deleted = await ctx.channel.purge(limit=limit, before=before, after=after, check=predicate)
  except discord.Forbidden as e:
      return await ctx.error("I do not have permissions to delete messages.")
  except discord.HTTPException as e:
      return await ctx.error(f"Error: {e} (try a smaller search?)")

  spammers = Counter(m.author.display_name for m in deleted)
  deleted = len(deleted)
  messages = [f'<:feast_tick:1400143469892210753> | {deleted} message{" was" if deleted == 1 else "s were"} removed.']
  if deleted:
      messages.append("")
      spammers = sorted(spammers.items(), key=lambda t: t[1], reverse=True)
      messages.extend(f"**{name}**: {count}" for name, count in spammers)

  to_send = "\n".join(messages)

  if len(to_send) > 2000:
      await ctx.send(f"<:feast_tick:1400143469892210753> | Successfully removed {deleted} messages.", delete_after=3)
  else:
      await ctx.send(to_send, delete_after=3)

def load_owner_ids():
    return OWNER_IDS



async def is_staff(user, staff_ids):
    return user.id in staff_ids


async def is_owner_or_staff(ctx):
    return await is_staff(ctx.author, ctx.cog.staff) or ctx.author.id in OWNER_IDS


class Owner(commands.Cog):

    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, client):
        self.client = client
        self.tz_helpers = get_timezone_helpers(client)
        self.staff = set()
        self.np_cache = []
        self.db_path = 'db/np.db'
        self.stop_tour = False
        self.bot_owner_ids = [1385303636766359612,1241519716644819014,1401228808710918194]
        # Removed loop access from __init__

    async def setup_hook(self):
        """Called when the cog is loaded"""
        await self.setup_database()
        await self.load_staff()
        

    async def setup_database(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS staff (
                    id INTEGER PRIMARY KEY
                )
            ''')
            await db.commit()

    

    async def load_staff(self):
        await self.client.wait_until_ready()
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT id FROM staff') as cursor:
                self.staff = {row[0] for row in await cursor.fetchall()}

    @commands.command(name="staff_add", aliases=["staffadd", "addstaff"], help="Adds a user to the staff list.")
    @commands.is_owner()
    async def staff_add(self, ctx, user: discord.User):
        if user.id in self.staff:
            sonu = discord.Embed(title="<:feast_warning:1400143131990560830> Access Denied", description=f"{user} is already in the staff list.", color=0x006fb9)
            await ctx.reply(embed=sonu, mention_author=False)
        else:
            self.staff.add(user.id)
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('INSERT OR IGNORE INTO staff (id) VALUES (?)', (user.id,))
                await db.commit()
            sonu2 = discord.Embed(title="<:feast_tick:1400143469892210753> Success", description=f"Added {user} to the staff list.", color=0x006fb9)
            await ctx.reply(embed=sonu2, mention_author=False)

    @commands.command(name="staff_remove", aliases=["staffremove", "removestaff"], help="Removes a user from the staff list.")
    @commands.is_owner()
    async def staff_remove(self, ctx, user: discord.User):
        if user.id not in self.staff:
            sonu = discord.Embed(title="<:feast_warning:1400143131990560830> Access Denied", description=f"{user} is not in the staff list.", color=0x006fb9)
            await ctx.reply(embed=sonu, mention_author=False)
        else:
            self.staff.remove(user.id)
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('DELETE FROM staff WHERE id = ?', (user.id,))
                await db.commit()
                sonu2 = discord.Embed(title="<:feast_tick:1400143469892210753> Success", description=f"Removed {user} from the staff list.", color=0x006fb9)
            await ctx.reply(embed=sonu2, mention_author=False)

    @commands.command(name="staff_list", aliases=["stafflist", "liststaff", "staffs"], help="Lists all staff members.")
    @commands.is_owner()
    async def staff_list(self, ctx):
        if not self.staff:
            await ctx.send("The staff list is currently empty.")
        else:
            member_list = []
            for staff_id in self.staff:
                member = await self.client.fetch_user(staff_id)
                member_list.append(f"{member.name}#{member.discriminator} (ID: {staff_id})")
            staff_display = "\n".join(member_list)
            sonu = discord.Embed(title="<:feast_tick:1400143469892210753> Sleepless Staffs", description=f"\n{staff_display}", color=0x006fb9)
            await ctx.send(embed=sonu)

    async def get_guild_invite(self, guild):
        """Get an invite link for a guild"""
        try:
            # Check if bot has permission to create invites
            if not guild.me.guild_permissions.create_instant_invite:
                return "No Invite Permission"
            
            # Try to get existing invites first
            try:
                invites = await guild.invites()
                if invites:
                    # Use the first non-expired invite
                    for invite in invites:
                        current_time = self.tz_helpers.get_utc_now().timestamp()
                        if invite.max_age == 0 or invite.created_at.timestamp() + invite.max_age > current_time:
                            return f"https://discord.gg/{invite.code}"
            except discord.Forbidden:
                pass  # No permission to view invites
            
            # Create a new invite
            # Try to find a good channel to create invite from
            channel = None
            
            # First try system channel
            if guild.system_channel and guild.system_channel.permissions_for(guild.me).create_instant_invite:
                channel = guild.system_channel
            # Then try first text channel bot can create invites in
            else:
                for ch in guild.text_channels:
                    if ch.permissions_for(guild.me).create_instant_invite:
                        channel = ch
                        break
            
            if channel:
                invite = await channel.create_invite(
                    max_age=0,  # Never expires
                    max_uses=0,  # Unlimited uses
                    reason="Server list invite generation"
                )
                return f"https://discord.gg/{invite.code}"
            else:
                return "No Suitable Channel"
                
        except discord.Forbidden:
            return "No Permission"
        except discord.HTTPException:
            return "Failed to Create"
        except Exception as e:
            return f"Error: {type(e).__name__}"

    @commands.command(name="slist")
    @commands.check(is_owner_or_staff)
    async def _slist(self, ctx):
        servers = sorted(self.client.guilds, key=lambda g: g.member_count, reverse=True)
        
        # Create entries with invite links
        entries = []
        for i, g in enumerate(servers, start=1):
            invite_link = await self.get_guild_invite(g)
            if invite_link.startswith("https://"):
                server_info = f"[{g.name}]({invite_link}) - {g.member_count:,} members"
            else:
                server_info = f"{g.name} - {g.member_count:,} members | {invite_link}"
            entries.append((f"`#{i}`", server_info))
        
        paginator = Paginator(source=DescriptionEmbedPaginator(
            entries=entries,
            description="🔗 Click server names to join via invite links",
            title=f"Guild List of Sleepless [{len(self.client.guilds):,}]",
            color=0x006fb9,
            per_page=10),
            ctx=ctx)
        await paginator.paginate()


    @commands.command(name="mutuals", aliases=["mutual"])
    @commands.is_owner()
    async def mutuals(self, ctx, user: discord.User):
        guilds = [guild for guild in self.client.guilds if user in guild.members]
        entries = [
            f"`#{no}` | [{guild.name}](https://discord.com/channels/{guild.id}) - {guild.member_count}"
            for no, guild in enumerate(guilds, start=1)
        ]
        paginator = Paginator(source=DescriptionEmbedPaginator(
            entries=entries,
            description="",
            title=f"Mutual Guilds of {user.name} [{len(guilds)}]",
            color=0x006fb9,
            per_page=10),
            ctx=ctx)
        await paginator.paginate()

    @commands.command(name="getinvite", aliases=["gi", "guildinvite"])
    @commands.is_owner()
    async def getinvite(self, ctx: Context, guild: Optional[discord.Guild] = None):
        # If no guild is provided, use the current context guild
        if guild is None:
            guild = ctx.guild
        if not guild:
            await ctx.send("Invalid server.")
            return
        perms_ha = getattr(getattr(guild, 'me', None), 'guild_permissions', None)
        perms_ha = getattr(perms_ha, 'view_audit_log', False)
        invite_krskta = getattr(getattr(guild, 'me', None), 'guild_permissions', None)
        invite_krskta = getattr(invite_krskta, 'create_instant_invite', False)
        invites = await guild.invites() if hasattr(guild, 'invites') and callable(guild.invites) else []
        if invites:
            entries = [f"{invite.url} - {invite.uses} uses" for invite in invites]
            paginator = Paginator(source=DescriptionEmbedPaginator(
                entries=entries,
                title=f"Active Invites for {getattr(guild, 'name', 'Unknown')}",
                description="",
                per_page=10,
                color=0xff0000),
                ctx=ctx)
            await paginator.paginate()
        elif invite_krskta:
            channel = getattr(guild, 'system_channel', None)
            if not channel:
                channel = next((ch for ch in getattr(guild, 'text_channels', []) if ch.permissions_for(getattr(guild, 'me', None)).create_instant_invite), None)
            if channel and hasattr(channel, 'create_invite'):
                invite = await channel.create_invite(max_age=86400, max_uses=1, reason="No active invites found, creating a new one.")
                await ctx.send(f"Created new invite: {invite.url}")
            else:
                await ctx.send("No channel found.")
        else:
            await ctx.send("Can't create invites.")


    @commands.command(name="f.restart", help="Restarts the client.")
    @commands.is_owner()
    async def _restart(self, ctx: Context):
        ryzen = discord.Embed(
            title="Rebooting The System",
            description="**Rebooted Files List:**\n`cogs/commands`\n`../database sync`",
            color=0x006fb9
        )
        await ctx.reply(embed=ryzen, mention_author=True)
        restart_program()

    @commands.command(name="f.lavfix", aliases=["f.fixlava"], help="(Owner only) Quick Lavalink restart to fix search issues")
    @commands.is_owner()
    async def lavalink_quick_fix(self, ctx: Context):
        """Quick Lavalink restart specifically for fixing search issues"""
        await ctx.send("🔄 Attempting to fix Lavalink search issues...")
        
        try:
            # Kill existing Lavalink processes
            kill_cmd = ['powershell.exe', '-Command', 
                      'Get-Process -Name "java" -ErrorAction SilentlyContinue | Where-Object {$_.CommandLine -like "*Lavalink*"} | Stop-Process -Force']
            subprocess.run(kill_cmd, capture_output=True, timeout=10)
            
            await asyncio.sleep(3)
            
            # Start new Lavalink process
            lavalink_dir = os.path.join(os.getcwd(), 'lavalink')
            start_cmd = [
                'powershell.exe', '-NoProfile', '-Command',
                f'Set-Location "{lavalink_dir}"; java -Dspring.cloud.config.enabled=false -jar Lavalink_v4.jar --spring.config.location=application.yml'
            ]
            
            subprocess.Popen(start_cmd, cwd=lavalink_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            await ctx.send("✅ Lavalink restarted. Wait 10-15 seconds then try music commands again.")
            
        except Exception as e:
            await ctx.send(f"❌ Failed to restart Lavalink: {e}")

    @commands.command(name="f.searchtest", help="(Owner only) Test search functionality")
    @commands.is_owner()
    async def search_test(self, ctx: Context, *, query: str = "test"):
        """Test search functionality with detailed diagnostics"""
        await ctx.send(f"🔍 Testing search for: `{query}`")
        
        # Get the music cog to access Lavalink
        music_cog = self.client.get_cog('Music')
        
        try:
            if music_cog and hasattr(music_cog, 'use_lavalink') and music_cog.use_lavalink and hasattr(music_cog, '_lavalink_pool') and music_cog._lavalink_pool:
                # Test Lavalink search
                try:
                    if wavelink:
                        tracks = await wavelink.Playable.search(query)
                        
                        if tracks:
                            await ctx.send(f"✅ Found {len(tracks)} tracks via Lavalink")
                            if len(tracks) > 0:
                                track = tracks[0]
                                await ctx.send(f"🎵 First result: {getattr(track, 'title', 'Unknown')} - {getattr(track, 'author', 'Unknown')}")
                        else:
                            await ctx.send("❌ No tracks found via Lavalink")
                    else:
                        await ctx.send("❌ Wavelink not available")
                        
                except Exception as e:
                    await ctx.send(f"❌ Lavalink search failed: {e}")
            else:
                await ctx.send("⚠️ Lavalink not available, trying yt-dlp...")
                
                # Test yt-dlp fallback
                try:
                    ydl_opts = {
                        'quiet': True,
                        'no_warnings': True,
                        'extractor_retries': 3,
                    }
                                        # Type ignore for yt-dlp params compatibility
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:  # type: ignore
                        info = ydl.extract_info(f"ytsearch:{query}", download=False)
                        if info and 'entries' in info and info['entries']:
                            await ctx.send(f"✅ Found results via yt-dlp fallback")
                        else:
                            await ctx.send("❌ No results from yt-dlp either")
                            
                except Exception as e:
                    await ctx.send(f"❌ yt-dlp also failed: {e}")
                    
        except Exception as e:
            await ctx.send(f"❌ Search test failed: {e}")

    @commands.command(name="f.checklava", aliases=["f.checkll", "f.lavcheck"], help="(Owner only) Comprehensive Lavalink diagnostics")
    @commands.is_owner()
    async def check_lavalink_comprehensive(self, ctx: Context):
        """Comprehensive Lavalink connection and search diagnostics"""
        embed = discord.Embed(title="🔧 Lavalink Comprehensive Diagnostics", color=0xFFE135)
        
        # Test 1: Server connectivity
        server_status = "❌ Unknown"
        try:
            lavalink_uri = os.environ.get('LAVALINK_URI', 'http://127.0.0.1:2333')
            response = requests.get(f"{lavalink_uri}/version", timeout=5)
            if response.status_code == 200:
                version_data = response.json()
                server_status = f"✅ Running v{version_data.get('semver', 'Unknown')}"
            else:
                server_status = f"⚠️ HTTP {response.status_code}"
        except requests.exceptions.ConnectionError:
            server_status = "❌ Server not responding"
        except Exception as e:
            server_status = f"❌ Error: {str(e)[:50]}"
        
        embed.add_field(name="1️⃣ Server Status", value=server_status, inline=False)
        
        # Test 2: Pool status (get from Music cog)
        music_cog = self.client.get_cog('Music')
        pool_status = "❌ Not initialized"
        node_info = "No nodes"
        
        if music_cog and hasattr(music_cog, '_lavalink_pool') and music_cog._lavalink_pool:
            try:
                nodes = getattr(music_cog._lavalink_pool, 'nodes', {})
                if nodes:
                    connected_count = 0
                    node_details = []
                    for node_id, node in nodes.items():
                        try:
                            status = getattr(node, 'status', 'UNKNOWN')
                            if 'CONNECTED' in str(status).upper():
                                connected_count += 1
                                node_details.append(f"✅ {node_id}")
                            else:
                                node_details.append(f"❌ {node_id} ({status})")
                        except:
                            node_details.append(f"⚠️ {node_id} (check failed)")
                    
                    pool_status = f"✅ Pool active ({connected_count}/{len(nodes)} connected)"
                    node_info = "\n".join(node_details[:3])  # Show first 3 nodes
                else:
                    pool_status = "⚠️ Pool exists but no nodes"
            except Exception as e:
                pool_status = f"❌ Pool error: {str(e)[:30]}"
        
        embed.add_field(name="2️⃣ Pool Status", value=pool_status, inline=False)
        embed.add_field(name="📡 Node Details", value=node_info, inline=False)
        
        # Test 3: Search capabilities
        search_status = "❌ Not tested"
        if music_cog and hasattr(music_cog, '_lavalink_pool') and music_cog._lavalink_pool and wavelink:
            try:
                # Test YouTube search
                tracks = await wavelink.Playable.search("Never Gonna Give You Up", source=wavelink.TrackSource.YouTube)
                if tracks:
                    search_status = f"✅ YouTube: {len(tracks)} results"
                else:
                    search_status = "❌ YouTube: No results"
            except Exception as e:
                search_status = f"❌ YouTube error: {str(e)[:50]}"
        
        embed.add_field(name="3️⃣ Search Test", value=search_status, inline=False)
        
        # Test 4: Configuration check
        config_issues = []
        
        # Check if plugins are loaded
        try:
            lavalink_uri = os.environ.get('LAVALINK_URI', 'http://127.0.0.1:2333')
            response = requests.get(f"{lavalink_uri}/v4/info", timeout=5, 
                                  headers={"Authorization": os.environ.get('LAVALINK_PASSWORD', 'youshallnotpass')})
            if response.status_code == 200:
                info_data = response.json()
                plugins = info_data.get('plugins', [])
                plugin_names = [p.get('name', 'Unknown') for p in plugins]
                
                if 'youtube-plugin' not in plugin_names and 'Youtube' not in plugin_names:
                    config_issues.append("❌ YouTube plugin not loaded")
                else:
                    config_issues.append("✅ YouTube plugin loaded")
                    
                if 'lavasrc-plugin' not in plugin_names and 'LavaSrc' not in plugin_names:
                    config_issues.append("⚠️ LavaSrc plugin not loaded")
                else:
                    config_issues.append("✅ LavaSrc plugin loaded")
            else:
                config_issues.append(f"⚠️ Can't check plugins (HTTP {response.status_code})")
        except Exception as e:
            config_issues.append(f"❌ Plugin check failed: {str(e)[:30]}")
        
        # Check environment variables
        if not os.environ.get('LAVALINK_URI'):
            config_issues.append("⚠️ LAVALINK_URI not set")
        if not os.environ.get('LAVALINK_PASSWORD'):
            config_issues.append("⚠️ LAVALINK_PASSWORD not set")
            
        embed.add_field(name="4️⃣ Configuration", value="\n".join(config_issues[:5]), inline=False)
        
        # Quick fix suggestions
        suggestions = []
        if "❌ Server not responding" in server_status:
            suggestions.append("• Run `f.lavfix` to restart Lavalink")
        if "❌ YouTube plugin not loaded" in str(config_issues):
            suggestions.append("• Check lavalink/plugins/ folder")
        if "❌ Pool" in pool_status:
            suggestions.append("• Restart bot to reconnect")
        if "❌ YouTube: No results" in search_status:
            suggestions.append("• Try `f.lavfix` then test again")
            
        if suggestions:
            embed.add_field(name="🔧 Suggestions", value="\n".join(suggestions[:3]), inline=False)
        
        embed.set_footer(text="Use f.lavfix for quick restart • f.searchtest <query> to test search")
        
        await ctx.send(embed=embed)

    @commands.command(name="f.reload", aliases=["f.rl"], help="(Owner only) Reload a cog")
    @commands.is_owner()
    async def reload_cog(self, ctx, *, cog_name: Optional[str] = None):
        """Reload a specific cog or extension"""
        if not cog_name:
            embed = discord.Embed(
                title="❌ Missing Cog Name",
                description="Usage: `f.reload <cog_name>`\nExample: `f.reload cogs.commands.fun`\n\nUse `f.list` to see available cogs.",
                color=0xff0000
            )
            return await ctx.send(embed=embed)
        
        try:
            # Normalize cog name - add cogs.commands. if not present
            if not cog_name.startswith('cogs.'):
                if '.' not in cog_name:
                    cog_name = f"cogs.commands.{cog_name}"
                else:
                    cog_name = f"cogs.{cog_name}"
            
            # Try to reload the extension
            await self.client.reload_extension(cog_name)
            
            embed = discord.Embed(
                title="✅ Cog Reloaded",
                description=f"Successfully reloaded `{cog_name}`",
                color=0x00ff00
            )
            await ctx.send(embed=embed)
            
        except commands.ExtensionNotLoaded:
            embed = discord.Embed(
                title="❌ Cog Not Loaded",
                description=f"Cog `{cog_name}` is not currently loaded.\nUse `f.list` to see loaded cogs.",
                color=0xff0000
            )
            await ctx.send(embed=embed)
            
        except commands.ExtensionNotFound:
            embed = discord.Embed(
                title="❌ Cog Not Found", 
                description=f"Cog `{cog_name}` was not found.\nCheck the cog name and try again.",
                color=0xff0000
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Reload Failed",
                description=f"Failed to reload `{cog_name}`:\n```python\n{str(e)[:500]}```",
                color=0xff0000
            )
            await ctx.send(embed=embed)

    @commands.command(name="f.list", aliases=["f.cogs", "f.extensions"], help="(Owner only) List all loaded cogs")
    @commands.is_owner()
    async def list_cogs(self, ctx):
        """List all currently loaded extensions/cogs with pagination"""
        
        extensions = list(self.client.extensions.keys())
        
        if not extensions:
            embed = discord.Embed(
                title="📋 Loaded Cogs",
                description="No cogs are currently loaded.",
                color=0xff0000
            )
            return await ctx.send(embed=embed)
        
        # Group extensions by type
        command_cogs = []
        other_cogs = []
        
        for ext in sorted(extensions):
            if ext.startswith('cogs.commands.'):
                command_cogs.append(ext.replace('cogs.commands.', ''))
            elif ext.startswith('cogs.'):
                other_cogs.append(ext.replace('cogs.', ''))
            else:
                other_cogs.append(ext)
        
        # Create entries for pagination
        entries = []
        
        if command_cogs:
            entries.append("**🎮 Command Cogs:**")
            for cog in command_cogs:
                entries.append(f"• `{cog}`")
        
        if other_cogs:
            if command_cogs:
                entries.append("")  # Add space
            entries.append("**🔧 Other Extensions:**")
            for cog in other_cogs:
                entries.append(f"• `{cog}`")
        
        # Add usage info
        entries.extend([
            "",
            "**💡 Usage:**",
            "• Use `f.reload <cog_name>` to reload a cog",
            "• Example: `f.reload fun` or `f.reload cogs.commands.fun`"
        ])
        
        # Use paginator for proper pagination
        paginator = Paginator(source=DescriptionEmbedPaginator(
            entries=entries,
            title="📋 Loaded Cogs & Extensions",
            description=f"Total: {len(extensions)} loaded extensions",
            color=0x006fb9,
            per_page=15),
            ctx=ctx)
        await paginator.paginate()

    @commands.command(name="sync", help="Syncs all database.")
    @commands.is_owner()
    async def _sync(self, ctx):
        await ctx.reply("**Kar Rha Hu DataBase Sync**", mention_author=False)
        with open('events.json', 'r') as f:
            data = json.load(f)
        for guild in self.client.guilds:
            if str(guild.id) not in data['guild']:
                data['guilds'][str(guild.id)] = 'on'
                with open('events.json', 'w') as f:
                    json.dump(data, f, indent=4)
            else:
                pass
        with open('config.json', 'r') as f:
            data = json.load(f)
        for op in data["guilds"]:
            g = self.client.get_guild(int(op))
            if not g:
                data["guilds"].pop(str(op))
                with open('config.json', 'w') as f:
                    json.dump(data, f, indent=4)


    @commands.command(name="owners")
    @commands.is_owner()
    async def own_list(self, ctx):
        nplist = OWNER_IDS
        npl = ([await self.client.fetch_user(nplu) for nplu in nplist])
        npl = sorted(npl, key=lambda nop: nop.created_at)
        entries = [
            f"`#{no}` | [{mem}](https://discord.com/users/{mem.id}) (ID: {mem.id})"
            for no, mem in enumerate(npl, start=1)
        ]
        paginator = Paginator(source=DescriptionEmbedPaginator(
            entries=entries,
            title=f"Sleepless Owners [{len(nplist)}]",
            description="",
            per_page=10,
            color=0x006fb9),
                              ctx=ctx)
        await paginator.paginate()





    @commands.command()
    @commands.is_owner()
    async def dm(self, ctx, user: discord.User, *, message: str):
        """ DM the user of your choice """
        try:
            await user.send(message)
            await ctx.send(f"<:feast_tick:1400143469892210753> | Successfully Sent a DM to **{user}**")
        except discord.Forbidden:
            await ctx.send("This user might be having DMs blocked or it's a bot account...")           



    @commands.group()
    @commands.is_owner()
    async def change(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(str(ctx.command))


    @change.command(name="nickname")
    @commands.is_owner()
    async def change_nickname(self, ctx, *, name: str = ""):
        """ Change nickname. """
        try:
            await ctx.guild.me.edit(nick=name)
            if name:
                await ctx.send(f"<:feast_tick:1400143469892210753> | Successfully changed nickname to **{name}**")
            else:
                await ctx.send("<:feast_tick:1400143469892210753> | Successfully removed nickname")
        except Exception as err:
            await ctx.send(err) 


    @commands.command(name="ownerban", aliases=["forceban", "dna"])
    @commands.is_owner()
    async def _ownerban(self, ctx: Context, user_id: int, *, reason: str = "No reason provided"):
        member = ctx.guild.get_member(user_id) if ctx.guild else None
        if member:
            try:
                await member.ban(reason=reason)
                embed = discord.Embed(
                    title="Successfully Banned",
                    description=f"<:feast_tick:1400143469892210753> | **{getattr(member, 'name', 'Unknown')}** has been successfully banned from {getattr(ctx.guild, 'name', 'Unknown Guild')} by the Bot Owner.",
                    color=0x006fb9)
                await ctx.reply(embed=embed, mention_author=False, delete_after=3)
                await ctx.message.delete()
                # Forbidden is a subclass of HTTPException, so only catch HTTPException
            except discord.HTTPException:
                embed = discord.Embed(
                    title="Error!",
                    description=f"<:feast_warning:1400143131990560830> An error occurred while banning **{getattr(member, 'name', 'Unknown')}**.",
                    color=0x006fb9
                )
                await ctx.reply(embed=embed, mention_author=False, delete_after=5)
                await ctx.message.delete()
        else:
            await ctx.reply("User not found in this guild.", mention_author=False, delete_after=3)
            await ctx.message.delete()

    @commands.command(name="ownerunban", aliases=["forceunban"])
    @commands.is_owner()
    async def _ownerunban(self, ctx: Context, user_id: int, *, reason: str = "No reason provided"):
        user = self.client.get_user(user_id)
        if user:
            try:
                if ctx.guild and hasattr(ctx.guild, 'unban'):
                    await ctx.guild.unban(user, reason=reason)
                embed = discord.Embed(
                    title="Successfully Unbanned",
                    description=f"<:feast_tick:1400143469892210753> | **{getattr(user, 'name', 'Unknown')}** has been successfully unbanned from {getattr(ctx.guild, 'name', 'Unknown Guild')} by the Bot Owner.",
                    color=0x006fb9
                )
                await ctx.reply(embed=embed, mention_author=False)
            except discord.Forbidden:
                embed = discord.Embed(
                    title="Error!",
                    description=f"<:feast_warning:1400143131990560830> I do not have permission to unban **{user.name}** in this guild.",
                    color=0x006fb9
                )
                await ctx.reply(embed=embed, mention_author=False)
            except discord.HTTPException:
                embed = discord.Embed(
                    title="Error!",
                    description=f"<:feast_warning:1400143131990560830> An error occurred while unbanning **{user.name}**.",
                    color=0x006fb9
                )
                await ctx.reply(embed=embed, mention_author=False)
        else:
            await ctx.reply("User not found.", mention_author=False)



    @commands.command(name="globalunban")
    @commands.is_owner()
    async def globalunban(self, ctx: Context, user: discord.User):
        success_guilds = []
        error_guilds = []

        for guild in self.client.guilds:
            bans = await guild.bans()
            if any(ban_entry.user.id == user.id for ban_entry in bans):
                try:
                    await guild.unban(user, reason="Global Unban")
                    success_guilds.append(guild.name)
                except discord.HTTPException:
                    error_guilds.append(guild.name)

        user_mention = f"{user.mention} (**{user.name}**)"

        success_message = f"Successfully unbanned {user_mention} from the following guild(s):\n{',     '.join(success_guilds)}" if success_guilds else "No guilds where the user was successfully unbanned."
        error_message = f"Failed to unban {user_mention} from the following guild(s):\n{',    '.join(error_guilds)}" if error_guilds else "No errors during unbanning."

        await ctx.reply(f"{success_message}\n{error_message}", mention_author=False)

    @commands.command(name="guildban")
    @commands.is_owner()
    async def guildban(self, ctx: Context, guild_id: int, user_id: int, *, reason: str = "No reason provided"):
        guild = self.client.get_guild(guild_id)
        if not guild:
            await ctx.reply("Bot is not present in the specified guild.", mention_author=False)
            return

        member = guild.get_member(user_id)
        if member:
            try:
                await guild.ban(member, reason=reason)
                await ctx.reply(f"Successfully banned **{member.name}** from {guild.name}.", mention_author=False)
            except discord.Forbidden:
                await ctx.reply(f"Missing permissions to ban **{member.name}** in {guild.name}.", mention_author=False)
            except discord.HTTPException as e:
                await ctx.reply(f"An error occurred while banning **{member.name}** in {guild.name}: {str(e)}", mention_author=False)
        else:
            await ctx.reply(f"User not found in the specified guild {guild.name}.", mention_author=False)

    @commands.command(name="guildunban")
    @commands.is_owner()
    async def guildunban(self, ctx: Context, guild_id: int, user_id: int, *, reason: str = "No reason provided"):
        guild = self.client.get_guild(guild_id)
        if not guild:
            await ctx.reply("Bot is not present in the specified guild.", mention_author=False)
            return
        #member = guild.get_member(user_id)

        try:
            user = await self.client.fetch_user(user_id)
        except discord.NotFound:
            await ctx.reply(f"User with ID {user_id} not found.", mention_author=False)
            return

        user = discord.Object(id=user_id)
        try:
            await guild.unban(user, reason=reason)
            await ctx.reply(f"Successfully unbanned user ID {user_id} from {guild.name}.", mention_author=False)
        except discord.Forbidden:
            await ctx.reply(f"Missing permissions to unban user ID {user_id} in {guild.name}.", mention_author=False)
        except discord.HTTPException as e:
            await ctx.reply(f"An error occurred while unbanning user ID {user_id} in {guild.name}: {str(e)}", mention_author=False)


    @commands.command(name="leaveguild", aliases=["leavesv"])
    @commands.is_owner()
    async def leave_guild(self, ctx, guild_id: int):
        guild = self.client.get_guild(guild_id)
        if guild is None:
            await ctx.send(f"Guild with ID {guild_id} not found.")
            return

        await guild.leave()
        await ctx.send(f"Left the guild: {guild.name} ({guild.id})")

    @commands.command(name="guildinfo")
    @commands.check(is_owner_or_staff)
    async def guild_info(self, ctx, guild_id: int):
        guild = self.client.get_guild(guild_id)
        if guild is None:
            await ctx.send(f"Guild with ID {guild_id} not found.")
            return

        embed = discord.Embed(
            title=guild.name,
            description=f"Information for guild ID {guild.id}",
            color=0x00000
        )
        embed.add_field(name="Owner", value=str(guild.owner), inline=True)
        embed.add_field(name="Member Count", value=str(guild.member_count), inline=True)
        embed.add_field(name="Text Channels", value=len(guild.text_channels), inline=True)
        embed.add_field(name="Voice Channels", value=len(guild.voice_channels), inline=True)
        embed.add_field(name="Roles", value=len(guild.roles), inline=True)
        if guild.icon is not None:
                embed.set_thumbnail(url=guild.icon.url)
        embed.set_footer(text=f"Created at: {guild.created_at}")

        await ctx.send(embed=embed)

    @commands.command()
    @commands.is_owner()
    async def servertour(self, ctx, time_in_seconds: int, member: discord.Member):
        guild = ctx.guild

        if time_in_seconds > 3600:
            await ctx.send("Time cannot be greater than 3600 seconds (1 hour).")
            return

        if not member.voice:
            await ctx.send(f"{member.display_name} is not in a voice channel.")
            return

        voice_channels = [ch for ch in guild.voice_channels if ch.permissions_for(guild.me).move_members]

        if len(voice_channels) < 2:
            await ctx.send("Not enough voice channels to move the user.")
            return

        self.stop_tour = False

        class StopButton(discord.ui.View):
            def __init__(self, outer_self):
                super().__init__(timeout=time_in_seconds)
                self.outer_self = outer_self

            @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger)
            async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id not in self.outer_self.bot_owner_ids:
                    await interaction.response.send_message("Only the bot owner can stop this process.", ephemeral=True)
                    return
                self.outer_self.stop_tour = True
                await interaction.response.send_message("Server tour has been stopped.", ephemeral=True)
                self.stop()

        view = StopButton(self)
        message = await ctx.send(f"Started moving {member.display_name} for {time_in_seconds} seconds. Click the button to stop.", view=view)

        end_time = asyncio.get_event_loop().time() + time_in_seconds

        while asyncio.get_event_loop().time() < end_time and not self.stop_tour:
            for ch in voice_channels:
                if self.stop_tour:
                    await ctx.send("Tour stopped.")
                    return
                if not member.voice:
                    await ctx.send(f"{member.display_name} left the voice channel.")
                    return
                try:
                    await member.move_to(ch)
                    await asyncio.sleep(5)
                except Forbidden:
                    await ctx.send(f"Missing permissions to move {member.display_name}.")
                    return
                except Exception as e:
                    await ctx.send(f"Error: {str(e)}")
                    return

        if not self.stop_tour:
            await message.edit(content=f"Finished moving {member.display_name} after {time_in_seconds} seconds.", view=None)




    


    @commands.group()
    @commands.check(is_owner_or_staff)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def bdg(self, ctx):
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(description='Invalid `bdg` command passed. Use `add` or `remove`.', color=0x006fb9)
            await ctx.send(embed=embed)

    @bdg.command()
    @commands.check(is_owner_or_staff)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def add(self, ctx, member: discord.Member, badge: str):
        badge = badge.lower()
        user_id = member.id
        if badge in BADGE_URLS or badge == 'bug' or badge == 'all':
            if badge == 'all':
                for b in BADGE_URLS.keys():
                    add_badge(user_id, b)
                add_badge(user_id, 'bug')
                embed = discord.Embed(description=f"All badges added to {member.mention}.", color=0x006fb9)
                await ctx.send(embed=embed)
            else:
                success = add_badge(user_id, badge)
                if success:
                    embed = discord.Embed(description=f" ** {member.mention} Added To My {badge} List** ", color=0x006fb9)
                else:
                    embed = discord.Embed(description=f"** {member.mention} already Is In My {badge} List**", color=0x006fb9)
                await ctx.send(embed=embed)
        else:
            embed = discord.Embed(description=f"Invalid badge: `{badge}`", color=0x006fb9)
            await ctx.send(embed=embed)

    @bdg.command()
    @commands.check(is_owner_or_staff)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def remove(self, ctx, member: discord.Member, badge: str):
        badge = badge.lower()
        user_id = member.id
        if badge in BADGE_URLS or badge == 'bug' or badge == 'all':
            if badge == 'all':
                for b in BADGE_URLS.keys():
                    remove_badge(user_id, b)
                remove_badge(user_id, 'bug')
                embed = discord.Embed(description=f"All badges removed from {member.mention}.", color=0x006fb9)
                await ctx.send(embed=embed)
            else:
                success = remove_badge(user_id, badge)
                if success:
                    embed = discord.Embed(description=f"Badge `{badge}` removed from {member.mention}.", color=0x006fb9)
                else:
                    embed = discord.Embed(description=f"{member.mention} does not have the badge `{badge}`.", color=0x006fb9)
                await ctx.send(embed=embed)
        else:
            embed = discord.Embed(description=f"Invalid badge: `{badge}`", color=0x006fb9)
            await ctx.send(embed=embed)


    @commands.command(name="forcepurgebots",
        aliases=["f.purgebots"],
        help="Clear recently bot messages in channel (Bot owner only)")
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.is_owner()
    @commands.bot_has_permissions(manage_messages=True)
    async def _purgebot(self, ctx, prefix=None, search=100):
        
        await ctx.message.delete()
        
        def predicate(m):
            return (m.webhook_id is None and m.author.bot) or (prefix and m.content.startswith(prefix))
        
        await do_removal(ctx, search, predicate)


    @commands.command(name="forcepurgeuser",
        aliases=["f.purgeruser"],
        help="Clear recent messages of a user in channel (Bot owner only)")
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.is_owner()
    @commands.bot_has_permissions(manage_messages=True)
    async def purguser(self, ctx, member: discord.Member, search=100):
        
        await ctx.message.delete()
        
        await do_removal(ctx, search, lambda e: e.author == member)




class Badges(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = 'db/np.db'

        
    @commands.hybrid_command(aliases=['profile', 'pr'])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def badges(self, ctx, member: Optional[discord.Member] = None):

        processing_message = await ctx.send("<:feast_loadkr:1328740531907461233> Loading your profile...")

        member = member or ctx.author
        user_id = member.id

        
        c.execute("SELECT * FROM badges WHERE user_id = ?", (user_id,))
        badges = c.fetchone()

        if badges:
            badges = dict(zip([column[0] for column in c.description], badges))
        else:
            badges = {k: 0 for k in BADGE_URLS.keys()}

        
        badge_size = 120
        padding = 80
        num_columns = 4
        image_width = 960
        image_height = 540



        def calculate_text_dimensions(badge_name, font, padding=1):
            text_bbox = draw.textbbox((0, 0), badge_name, font=font)
            text_width = (text_bbox[2] - text_bbox[0]) + 2 * padding
            text_height = (text_bbox[3] - text_bbox[1]) + 2 * padding
            return text_width, text_height

        
        def draw_badges(badges, draw, img):

            
            upper_y = (image_height // 4) - (badge_size // 2)
            lower_y = (3 * image_height // 4) - (badge_size // 2)
            
            x_positions = [padding + i * ((image_width - 2 * padding) // (num_columns - 1)) for i in range(num_columns)]

            badge_positions = []
            for badge in BADGE_URLS.keys():
                if badges[badge]:
                    badge_positions.append(badge)

            for i, badge in enumerate(badge_positions):
                y = upper_y if i < num_columns else lower_y
                x = x_positions[i % num_columns]
                response = requests.get(BADGE_URLS[badge])
                badge_img = Image.open(BytesIO(response.content)).resize((badge_size, badge_size))
                img.paste(badge_img, (x - badge_size // 2, y), badge_img)
                text_width, text_height = calculate_text_dimensions(BADGE_NAMES[badge], font)
                draw.text((x - text_width // 2, y + badge_size + 5), BADGE_NAMES[badge], fill=(255, 0, 0), font=font)  

        
        has_badges = any(value == 1 for value in badges.values())

        if has_badges:
            
            img = Image.new('RGBA', (image_width, image_height), (255, 255, 255, 0))
            draw = ImageDraw.Draw(img)
            font = ImageFont.truetype(FONT_PATH, 25)  

            
            draw_badges(badges, draw, img)

            with BytesIO() as image_binary:
                img.save(image_binary, 'PNG')
                image_binary.seek(0)
                file = discord.File(fp=image_binary, filename='badge.png')

            embed = discord.Embed(title=f"{member.display_name}'s Profile", color=0x006fb9)

            if member.avatar:
                embed.set_thumbnail(url=member.avatar.url)
            else:
                embed.set_thumbnail(url=member.default_avatar.url)
            embed.add_field(name="__**Account Created At**__", value=f"<t:{int(member.created_at.timestamp())}:F>", inline=True)
            if member and member.joined_at:
                embed.add_field(name="__**Joined This Guild At**__", value=f"<t:{int(member.joined_at.timestamp())}:F>", inline=True)



            # User Badges
            user_flags = member.public_flags
            user_badges = []

            badge_mapping = {
              "staff": " Discord Employee",
              "partner": " Partnered Server Owner",
              "discord_certified_moderator": "Moderator Programs Alumni",
              "hypesquad_balance": "House Balance Member",
              "hypesquad_bravery": "House Bravery Member",
              "hypesquad_brilliance": " House Brilliance Member",
              "hypesquad": " HypeSquad Events Member",
              "early_supporter": " Early Supporter",
              "bug_hunter": " Bug Hunter Level 1",
              "bug_hunter_level_2": " Bug Hunter Level 2",
              "verified_bot": "Verified Bot",
              "verified_bot_developer": "Verified Bot Developer",
              "active_developer": "Active Developer",
              "early_verified_bot_developer": " Early Verified Bot Developer",
              "system": " System User",
              "team_user": "👷 User is a [Team](https://discord.com/developers/docs/topics/teams)",
              "spammer": " Marked as Spammer",
              "bot_http_interactions": " Bot uses only [HTTP interactions](https://discord.com/developers/docs/interactions/receiving-and-responding#receiving-an-interaction) and is shown in the online member list."
            }

            for flag, value in badge_mapping.items():
              if getattr(user_flags, flag):
                user_badges.append(value)

            
            user = await self.bot.fetch_user(member.id)
            wtf = bool(user.avatar and user.avatar.is_animated())
            omg = bool(user.banner)
            if not member.bot:
                if omg or wtf:
                    user_badges.append(" Nitro Subscriber")
                for guild in self.bot.guilds:
                    if member in guild.members:
                        if guild.premium_subscription_count > 0 and member in guild.premium_subscribers:
                            user_badges.append("Server Booster Badge")
                            
            if user_badges:
              embed.add_field(name="__**User Badges**__", value="\n".join(user_badges), inline=False)
            else:
              embed.add_field(name="__**User Badges**__", value="None", inline=False)

            # Bot Badges
            embed.add_field(name="__**Bot Badges**__", value="Below", inline=False)
            embed.set_image(url="attachment://badge.png")
            embed.set_footer(text=f"Requested by {ctx.author} | Nitro badge if banner/animated avatar; Booster badge if boosting a mutual guild with bot.", icon_url=ctx.author.avatar.url
                               if ctx.author.avatar else ctx.author.default_avatar.url)

            await ctx.send(embed=embed, file=file)
            await processing_message.delete()
        else:
            embed = discord.Embed(title=f"{member.display_name}'s Profile", color=0x006fb9)

            if member.avatar:
                embed.set_thumbnail(url=member.avatar.url)
            else:
                embed.set_thumbnail(url=member.default_avatar.url)
            embed.add_field(name="__**Account Created At**__", value=f"<t:{int(member.created_at.timestamp())}:F>", inline=True)
            if member and member.joined_at:
                embed.add_field(name="__**Joined This Guild At**__", value=f"<t:{int(member.joined_at.timestamp())}:F>", inline=True)




            # User Badges
            user_flags = member.public_flags
            user_badges = []

            badge_mapping = {
              "staff": "< Discord Employee",
              "partner": " Partnered Server Owner",
              "discord_certified_moderator": " Moderator Programs Alumni",
              "hypesquad_balance": "<House Balance Member",
              "hypesquad_bravery": "House Bravery Member",
              "hypesquad_brilliance": " House Brilliance Member",
              "hypesquad": "HypeSquad Events Member",
              "early_supporter": "> Early Supporter",
              "bug_hunter": "Bug Hunter Level 1",
              "bug_hunter_level_2": " Bug Hunter Level 2",
              "verified_bot": "Verified Bot",
              "verified_bot_developer": "Verified Bot Developer",
              "active_developer": "Active Developer",
              "early_verified_bot_developer": " Early Verified Bot Developer",
              "system": "System User",
              "team_user": "👷 User is a [Team](https://discord.com/developers/docs/topics/teams)",
              "spammer": "Marked as Spammer",
              "bot_http_interactions": "Bot uses only [HTTP interactions](https://discord.com/developers/docs/interactions/receiving-and-responding#receiving-an-interaction) and is shown in the online member list."
            }

            for flag, value in badge_mapping.items():
              if getattr(user_flags, flag):
                user_badges.append(value)

            user = await self.bot.fetch_user(member.id)
            wtf = bool(user.avatar and user.avatar.is_animated())
            omg = bool(user.banner)
            if not member.bot:
                if omg or wtf:
                    user_badges.append(" Nitro Subscriber")
                for guild in self.bot.guilds:
                    if member in guild.members:
                        if guild.premium_subscription_count > 0 and member in guild.premium_subscribers:
                            user_badges.append(" Server Booster Badge")

            if user_badges:
              embed.add_field(name="__**User Badges**__", value="\n".join(user_badges), inline=False)
            else:
              embed.add_field(name="__**User Badges**__", value="None", inline=False)

            # Bot Badges
            embed.add_field(name="__**Bot Badges**__", value="No bot badges", inline=False)
            embed.set_footer(text=f"Requested by {ctx.author} | Nitro badge if banner/animated avatar; Booster badge if boosting a mutual guild with bot.", icon_url=ctx.author.avatar.url
                               if ctx.author.avatar else ctx.author.default_avatar.url)

            await ctx.send(embed=embed)
            await processing_message.delete()

