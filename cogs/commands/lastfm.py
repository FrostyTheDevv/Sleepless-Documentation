import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput, Select
import aiohttp
import asyncio
import sqlite3
import json
from datetime import datetime, timezone, timedelta
import re
from typing import Optional, Union, List, Dict, Tuple
import urllib.parse
import os
import math
import base64
from io import BytesIO
from collections import defaultdict, Counter
import difflib
import hashlib
import time
import pytz
from utils import Paginator, DescriptionEmbedPaginator, FieldPagePaginator, TextPaginator

class LastFMCog(commands.Cog, name="Last.fm"):
    def __init__(self, bot):
        self.bot = bot
        self.color = 0x006fb9  # Standard blue color
        self.api_key = os.getenv('LASTFM_API_KEY')
        self.api_secret = os.getenv('LASTFM_API_SECRET')
        self.spotify_client_id = os.getenv('SPOTIFY_CLIENT_ID')
        self.spotify_client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
        self.session_cache = {}
        self.spotify_token = None
        self.setup_database()
        
    def setup_database(self):
        """Initialize comprehensive Last.fm database"""
        try:
            with sqlite3.connect('databases/lastfm.db') as conn:
                # Enhanced users table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS lastfm_users (
                        user_id INTEGER PRIMARY KEY,
                        lastfm_username TEXT NOT NULL,
                        linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        privacy_level INTEGER DEFAULT 0,
                        auto_showcase INTEGER DEFAULT 0,
                        crown_optout INTEGER DEFAULT 0,
                        reaction_notifications INTEGER DEFAULT 1,
                        timezone TEXT DEFAULT 'UTC',
                        profile_description TEXT,
                        total_scrobbles INTEGER DEFAULT 0,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Enhanced guild settings
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS lastfm_guild_settings (
                        guild_id INTEGER PRIMARY KEY,
                        showcase_channel_id INTEGER,
                        auto_react INTEGER DEFAULT 1,
                        custom_reactions TEXT DEFAULT '["🎵", "❤️", "🔥", "👎", "🎸", "🎤"]',
                        embed_color TEXT DEFAULT '#d51007',
                        show_album_art INTEGER DEFAULT 1,
                        show_playcount INTEGER DEFAULT 1,
                        show_scrobbles INTEGER DEFAULT 1,
                        reaction_threshold INTEGER DEFAULT 3,
                        whoknows_limit INTEGER DEFAULT 15,
                        crown_system INTEGER DEFAULT 1,
                        auto_crowns INTEGER DEFAULT 1,
                        np_reactions INTEGER DEFAULT 1,
                        chart_size INTEGER DEFAULT 9,
                        chart_period TEXT DEFAULT '7day',
                        embed_thumbnail INTEGER DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # User customization settings
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS lastfm_user_settings (
                        user_id INTEGER PRIMARY KEY,
                        embed_title TEXT DEFAULT 'Now Playing',
                        embed_description TEXT DEFAULT '{user} is listening to **{track}** by **{artist}**',
                        show_private INTEGER DEFAULT 0,
                        custom_footer TEXT DEFAULT 'Last.fm Integration',
                        thumbnail_style TEXT DEFAULT 'album',
                        auto_update INTEGER DEFAULT 0,
                        chart_style TEXT DEFAULT 'grid',
                        show_tags INTEGER DEFAULT 1,
                        show_duration INTEGER DEFAULT 1,
                        show_loved INTEGER DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Crowns system (artist domination)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS lastfm_crowns (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        artist_name TEXT NOT NULL,
                        playcount INTEGER NOT NULL,
                        claimed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(guild_id, artist_name)
                    )
                """)
                
                # Artist stats cache
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS lastfm_artist_cache (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        artist_name TEXT NOT NULL,
                        playcount INTEGER NOT NULL,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(guild_id, user_id, artist_name)
                    )
                """)
                
                # User listening stats
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS lastfm_user_stats (
                        user_id INTEGER PRIMARY KEY,
                        total_artists INTEGER DEFAULT 0,
                        total_albums INTEGER DEFAULT 0,
                        total_tracks INTEGER DEFAULT 0,
                        avg_daily_scrobbles REAL DEFAULT 0,
                        longest_streak INTEGER DEFAULT 0,
                        current_streak INTEGER DEFAULT 0,
                        favorite_artist TEXT,
                        favorite_album TEXT,
                        last_scrobble_time TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Milestone tracking
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS lastfm_milestones (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        milestone_type TEXT NOT NULL,
                        milestone_value INTEGER NOT NULL,
                        achieved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        artist_name TEXT,
                        track_name TEXT
                    )
                """)
                
                # User comparisons cache
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS lastfm_compatibility (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user1_id INTEGER NOT NULL,
                        user2_id INTEGER NOT NULL,
                        compatibility_score REAL NOT NULL,
                        shared_artists INTEGER NOT NULL,
                        calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user1_id, user2_id)
                    )
                """)
                
                print("[LASTFM] Enhanced database initialized successfully!")
                
        except Exception as e:
            print(f"[LASTFM ERROR] Database setup failed: {e}")

    async def get_lastfm_data(self, method: str, **params):
        """Enhanced API calls to Last.fm with caching"""
        if not self.api_key:
            raise ValueError("Last.fm API key not configured. Set LASTFM_API_KEY in environment variables.")
            
        base_url = "http://ws.audioscrobbler.com/2.0/"
        default_params = {
            'method': method,
            'api_key': self.api_key,
            'format': 'json'
        }
        default_params.update(params)
        
        # Create cache key
        cache_key = hashlib.md5(str(sorted(default_params.items())).encode()).hexdigest()
        
        # Dynamic cache duration based on method type
        cache_duration = 300  # Default 5 minutes
        if method in ['user.getrecenttracks']:
            cache_duration = 10   # 10 seconds for recent tracks (now playing) - more frequent updates
        elif method in ['track.getinfo', 'artist.getinfo', 'album.getinfo']:
            cache_duration = 30   # 30 seconds for track/artist/album info
        elif method in ['user.gettoptracks', 'user.gettopartists', 'user.gettopalbums']:
            cache_duration = 300  # 5 minutes for top charts (changes slowly)
        
        # Check cache first
        if cache_key in self.session_cache:
            cached_data, timestamp = self.session_cache[cache_key]
            if time.time() - timestamp < cache_duration:
                return cached_data
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(base_url, params=default_params) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Cache the response
                        self.session_cache[cache_key] = (data, time.time())
                        return data
                    elif response.status == 404:
                        return {'error': 404, 'message': 'User not found'}
                    else:
                        return None
        except Exception as e:
            print(f"[LASTFM API ERROR] {e}")
            return None

    def clear_cache(self, method_filter=None):
        """Clear cache entries, optionally filtered by method"""
        if method_filter:
            # Remove only specific method caches
            keys_to_remove = []
            for key in self.session_cache:
                # This is a simplified approach - we'd need to store method with cache
                # For now, just clear all cache when filter is specified
                keys_to_remove.append(key)
            for key in keys_to_remove:
                del self.session_cache[key]
        else:
            # Clear all cache
            self.session_cache.clear()
        print(f"[LASTFM] Cache cleared{'for ' + method_filter if method_filter else ' completely'}")

    def get_user_lastfm(self, user_id: int):
        """Get linked Last.fm username for a Discord user"""
        try:
            with sqlite3.connect('databases/lastfm.db') as conn:
                cursor = conn.execute(
                    "SELECT lastfm_username FROM lastfm_users WHERE user_id = ?",
                    (user_id,)
                )
                result = cursor.fetchone()
                return result[0] if result else None
        except Exception:
            return None

    def get_guild_settings(self, guild_id: int):
        """Get enhanced guild Last.fm settings"""
        try:
            with sqlite3.connect('databases/lastfm.db') as conn:
                cursor = conn.execute(
                    "SELECT * FROM lastfm_guild_settings WHERE guild_id = ?",
                    (guild_id,)
                )
                result = cursor.fetchone()
                if result:
                    return {
                        'showcase_channel_id': result[1],
                        'auto_react': result[2],
                        'custom_reactions': json.loads(result[3]),
                        'embed_color': result[4],
                        'show_album_art': result[5],
                        'show_playcount': result[6],
                        'show_scrobbles': result[7],
                        'reaction_threshold': result[8],
                        'whoknows_limit': result[9],
                        'crown_system': result[10],
                        'auto_crowns': result[11],
                        'np_reactions': result[12],
                        'chart_size': result[13],
                        'chart_period': result[14],
                        'embed_thumbnail': result[15]
                    }
                return self.get_default_settings()
        except Exception:
            return self.get_default_settings()

    def get_default_settings(self):
        """Enhanced default guild settings"""
        return {
            'showcase_channel_id': None,
            'auto_react': 1,
            'custom_reactions': ["<:speaker:1428183066311921804>", "❤️", "🔥", "👎", "🎸", "🎤"],
            'embed_color': '#006fb9',
            'show_album_art': 1,
            'show_playcount': 1,
            'show_scrobbles': 1,
            'reaction_threshold': 3,
            'whoknows_limit': 15,
            'crown_system': 1,
            'auto_crowns': 1,
            'np_reactions': 1,
            'chart_size': 9,
            'chart_period': '7day',
            'embed_thumbnail': 1
        }

    def safe_get_text(self, data, default='Unknown'):
        """Safely extract text from Last.fm API response data"""
        if isinstance(data, dict):
            return data.get('#text', data.get('name', default))
        elif data:
            return str(data)
        return default
    
    def safe_get_artist(self, track_data, default='Unknown Artist'):
        """Safely extract artist name from track data"""
        artist_data = track_data.get('artist', {})
        return self.safe_get_text(artist_data, default)
    
    def safe_get_album(self, track_data, default='Unknown Album'):
        """Safely extract album name from track data"""
        album_data = track_data.get('album', {})
        return self.safe_get_text(album_data, default)

    async def get_spotify_token(self):
        """Get Spotify access token for API calls"""
        if not self.spotify_client_id or not self.spotify_client_secret:
            return None
            
        try:
            auth_url = "https://accounts.spotify.com/api/token"
            auth_data = {
                'grant_type': 'client_credentials',
                'client_id': self.spotify_client_id,
                'client_secret': self.spotify_client_secret
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(auth_url, data=auth_data) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.spotify_token = data.get('access_token')
                        return self.spotify_token
            return None
        except Exception as e:
            print(f"[SPOTIFY ERROR] Failed to get token: {e}")
            return None

    async def search_spotify_track(self, artist: str, track: str):
        """Search for a track on Spotify and get album artwork with improved query handling"""
        if not self.spotify_token:
            await self.get_spotify_token()
            
        if not self.spotify_token:
            return None
            
        try:
            # Clean up search query - remove special characters and normalize
            clean_artist = re.sub(r'[^\w\s]', '', artist).strip()
            clean_track = re.sub(r'[^\w\s]', '', track).strip()
            
            # Try multiple search strategies
            search_queries = [
                f'artist:"{clean_artist}" track:"{clean_track}"',  # Exact match with quotes
                f'artist:{clean_artist} track:{clean_track}',      # Standard search
                f'"{clean_artist}" "{clean_track}"',               # Simple quoted search
                f'{clean_artist} {clean_track}'                    # Basic search
            ]
            
            for query in search_queries:
                encoded_query = urllib.parse.quote(query)
                search_url = f"https://api.spotify.com/v1/search?q={encoded_query}&type=track&limit=1"
                
                headers = {
                    'Authorization': f'Bearer {self.spotify_token}'
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(search_url, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            tracks = data.get('tracks', {}).get('items', [])
                            
                            if tracks:
                                track_data = tracks[0]
                                album = track_data.get('album', {})
                                images = album.get('images', [])
                                
                                # Get the largest image (first in the list)
                                if images:
                                    return images[0].get('url')
                        elif response.status == 401:
                            # Token expired, try to refresh
                            await self.get_spotify_token()
                            continue
                        
            return None
        except Exception as e:
            print(f"[SPOTIFY ERROR] Search failed: {e}")
            return None

    async def search_track_image(self, artist: str, track: str, album: Optional[str] = None):
        """Enhanced track image search using multiple sources with improved fallbacks"""
        image_url = None
        debug_images = []
        
        # Method 1: Try Spotify search for high-quality artwork
        debug_images.append("Method 1 - Spotify search:")
        try:
            spotify_image = await self.search_spotify_track(artist, track)
            if spotify_image:
                image_url = spotify_image
                debug_images.append(f"  <a:yes:1431909187247673464> Found Spotify image: {spotify_image}")
                return image_url, debug_images
            else:
                debug_images.append("  <a:wrong:1436956421110632489> No Spotify image found")
        except Exception as e:
            debug_images.append(f"  <a:wrong:1436956421110632489> Spotify error: {e}")
        
        # Method 2: Try Spotify album search if available
        if album and album != "Unknown Album" and album.strip():
            debug_images.append("Method 2 - Spotify album search:")
            try:
                # Search for album specifically
                album_query = f"artist:{artist} album:{album}".replace(' ', '%20')
                search_url = f"https://api.spotify.com/v1/search?q={album_query}&type=album&limit=1"
                
                if self.spotify_token:
                    headers = {'Authorization': f'Bearer {self.spotify_token}'}
                    async with aiohttp.ClientSession() as session:
                        async with session.get(search_url, headers=headers) as response:
                            if response.status == 200:
                                data = await response.json()
                                albums = data.get('albums', {}).get('items', [])
                                
                                if albums:
                                    album_data = albums[0]
                                    images = album_data.get('images', [])
                                    
                                    if images:
                                        image_url = images[0].get('url')
                                        debug_images.append(f"  <a:yes:1431909187247673464> Found Spotify album image: {image_url}")
                                        return image_url, debug_images
                                        
                debug_images.append("  <a:wrong:1436956421110632489> No Spotify album image found")
            except Exception as e:
                debug_images.append(f"  <a:wrong:1436956421110632489> Spotify album search error: {e}")
        
        # Method 3: Try Last.fm track.getInfo for high-quality images
        debug_images.append("Method 3 - Last.fm track info:")
        try:
            track_info = await self.get_lastfm_data(
                'track.getinfo',
                artist=artist,
                track=track
            )
            
            if track_info and 'track' in track_info:
                track_data = track_info['track']
                
                # Try album images from track info first
                if 'album' in track_data and 'image' in track_data['album']:
                    for i, img in enumerate(reversed(track_data['album']['image'])):
                        url = img.get('#text', '').strip()
                        debug_images.append(f"    Track album image {i}: {url}")
                        if url and self._is_valid_image_url(url):
                            image_url = url
                            debug_images.append(f"    <a:yes:1431909187247673464> Using track album image: {url}")
                            return image_url, debug_images
                
                # Try track images if no album images
                if 'image' in track_data:
                    for i, img in enumerate(reversed(track_data['image'])):
                        url = img.get('#text', '').strip()
                        debug_images.append(f"    Track image {i}: {url}")
                        if url and self._is_valid_image_url(url):
                            image_url = url
                            debug_images.append(f"    <a:yes:1431909187247673464> Using track image: {url}")
                            return image_url, debug_images
            
            debug_images.append("  <a:wrong:1436956421110632489> No valid Last.fm track images")
        except Exception as e:
            debug_images.append(f"  <a:wrong:1436956421110632489> Last.fm track info error: {e}")
        
        # Method 4: Try Last.fm album.getInfo for dedicated album artwork
        if album and album != "Unknown Album" and album.strip():
            debug_images.append("Method 4 - Last.fm album info:")
            try:
                album_info = await self.get_lastfm_data(
                    'album.getinfo',
                    artist=artist,
                    album=album
                )
                
                if album_info and 'album' in album_info and 'image' in album_info['album']:
                    for i, img in enumerate(reversed(album_info['album']['image'])):
                        url = img.get('#text', '').strip()
                        debug_images.append(f"    Album image {i}: {url}")
                        if url and self._is_valid_image_url(url):
                            image_url = url
                            debug_images.append(f"    <a:yes:1431909187247673464> Using album image: {url}")
                            return image_url, debug_images
                            
                debug_images.append("  <a:wrong:1436956421110632489> No valid Last.fm album images")
            except Exception as e:
                debug_images.append(f"  <a:wrong:1436956421110632489> Last.fm album info error: {e}")
        
        # Method 5: Try Last.fm artist images as final fallback
        debug_images.append("Method 5 - Last.fm artist images:")
        try:
            artist_info = await self.get_lastfm_data(
                'artist.getinfo',
                artist=artist
            )
            
            if artist_info and 'artist' in artist_info and 'image' in artist_info['artist']:
                for i, img in enumerate(reversed(artist_info['artist']['image'])):
                    url = img.get('#text', '').strip()
                    debug_images.append(f"    Artist image {i}: {url}")
                    if url and self._is_valid_image_url(url):
                        image_url = url
                        debug_images.append(f"    <a:yes:1431909187247673464> Using artist image: {url}")
                        return image_url, debug_images
                        
            debug_images.append("  <a:wrong:1436956421110632489> No valid Last.fm artist images")
        except Exception as e:
            debug_images.append(f"  <a:wrong:1436956421110632489> Last.fm artist info error: {e}")
        
        return None, debug_images
    
    def _is_valid_image_url(self, url: str) -> bool:
        """Check if an image URL is valid (not a placeholder)"""
        if not url or url.strip() == '':
            return False
        
        # Last.fm placeholder images to avoid
        placeholders = [
            '2a96cbd8b46e442fc41c2b86b821562f.png',  # Default Last.fm placeholder
            'c6f59c1e5e7240a4c0d427abd71f3dbb.png',  # Another common placeholder
            '4128a6eb29f94943c9d206c08e625904.png',  # Another placeholder
            '/images/spacer.gif',                     # Spacer image
        ]
        
        for placeholder in placeholders:
            if placeholder in url:
                return False
        
        return True

    @commands.group(name="fm", description="Comprehensive Last.fm integration", invoke_without_command=True)
    async def fm(self, ctx):
        """Last.fm integration commands - defaults to now playing"""
        if ctx.invoked_subcommand is None:
            # Default to now playing instead of help
            await self.fm_np(ctx)

    @fm.command(name="help")
    async def fm_help(self, ctx):
        """Show detailed FM command help"""
        # Get server prefix for accurate command examples
        prefix = (await self.bot.get_prefix(ctx.message))[0]
        
        # Create paginated help entries
        entries = [
            ("** Account Management**", 
             f"`{prefix}fm set <username>` - Link your Last.fm account\n"
             f"`{prefix}fm unset` - Unlink your account\n"
             f"`{prefix}fm profile [user]` - Detailed profile with stats\n"
             f"`{prefix}fm privacy` - Configure privacy settings\n"
             f"`{prefix}fm timezone <tz>` - Set your timezone"),
            
            ("** Music Discovery**", 
             f"`{prefix}fm` or `{prefix}fm np [user]` - Enhanced now playing\n"
             f"`{prefix}fm recent [user] [limit]` - Recent tracks\n"
             f"`{prefix}fm topartists [period] [user]` - Top artists\n"
             f"`{prefix}fm topalbums [period] [user]` - Top albums\n"
             f"`{prefix}fm toptracks [period] [user]` - Top tracks\n"
             f"`{prefix}fm loved [user]` - Loved tracks"),
            
            ("** Track & Artist Info**",
             f"`{prefix}fm artist <name>` - Artist information\n"
             f"`{prefix}fm album <name>` - Album information\n"
             f"`{prefix}fm track <name>` - Track information\n"
             f"`{prefix}fm search <query>` - Search artists/tracks\n"
             f"`{prefix}fm similar <artist>` - Find similar artists"),
            
            ("** Social Features**",
             f"`{prefix}fm whoknows <artist>` - Who knows this artist\n"
             f"`{prefix}fm crowns [user]` - View artist crowns\n"
             f"`{prefix}fm compare <user>` - Compare music taste"),
            
            ("** Statistics & Charts**", 
             f"`{prefix}fm chart [period] [size]` - Visual album charts\n"
             f"`{prefix}fm stats [user] [period]` - Comprehensive statistics\n"
             f"`{prefix}fm profile [user]` - Detailed user profile"),
            
            ("** Settings & Customization**", 
             f"`{prefix}fm customize` - Personal settings panel\n"
             f"`{prefix}fm privacy` - Privacy configuration\n"
             f"`{prefix}fm timezone` - Set your timezone")
        ]
        
        paginator = Paginator(source=DescriptionEmbedPaginator(
            entries=entries,
            title="Fm Command Help",
            description="**Tip**: Just use `fm` for quick now playing!",
            color=self.color,
            per_page=2),
            ctx=ctx)
        await paginator.paginate()

    @fm.command(name="set")
    async def fm_set(self, ctx, username: str):
        """Link your Last.fm account with enhanced validation"""
        # Get server prefix for accurate command examples
        prefix = (await self.bot.get_prefix(ctx.message))[0]
        
        # Validate username exists and get user info
        user_data = await self.get_lastfm_data('user.getinfo', user=username)
        
        if not user_data or (user_data and 'error' in user_data):
            embed = discord.Embed(
                title="<a:wrong:1436956421110632489> Invalid Username",
                description=f"Last.fm user `{username}` not found. Please check the spelling and try again.",
                color=0xff0000
            )
            if user_data and 'error' in user_data and user_data['error'] == 404:
                embed.add_field(
                    name="Tip",
                    value="Make sure you're using your exact Last.fm username, not display name.",
                    inline=False
                )
            await ctx.send(embed=embed)
            return

        # Get user stats for initial setup
        user_info = user_data['user']
        total_scrobbles = int(user_info.get('playcount', 0))
        
        try:
            with sqlite3.connect('databases/lastfm.db') as conn:
                # Insert or update user
                conn.execute("""
                    INSERT OR REPLACE INTO lastfm_users 
                    (user_id, lastfm_username, linked_at, total_scrobbles, last_updated)
                    VALUES (?, ?, ?, ?, ?)
                """, (ctx.author.id, username, datetime.now(), total_scrobbles, datetime.now()))
                
                # Create default user settings
                conn.execute("""
                    INSERT OR IGNORE INTO lastfm_user_settings (user_id)
                    VALUES (?)
                """, (ctx.author.id,))
                
                # Initialize user stats
                conn.execute("""
                    INSERT OR REPLACE INTO lastfm_user_stats 
                    (user_id, total_artists, total_albums, total_tracks, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (ctx.author.id, 
                     int(user_info.get('artist_count', 0)),
                     int(user_info.get('album_count', 0)),
                     int(user_info.get('track_count', 0)),
                     datetime.now()))
                
                conn.commit()

            embed = discord.Embed(
                title="<a:yes:1431909187247673464> Account Successfully Linked!",
                description=f"Welcome **{username}**! Your Last.fm account has been linked.",
                color=self.color
            )
            
            # Add user stats to embed
            embed.add_field(
                name="<:stats:1437456326157668362> Your Stats",
                value=(
                    f"**Total Scrobbles:** {total_scrobbles:,}\n"
                    f"**Artists:** {user_info.get('artist_count', 'N/A')}\n"
                    f"**Member Since:** {user_info.get('registered', {}).get('#text', 'Unknown')}"
                ),
                inline=True
            )
            
            embed.add_field(
                name="<a:blue:1437461186391179284> Quick Start",
                value=(
                    f"• `{prefix}fm np` - Show what you're playing\n"
                    f"• `{prefix}fm customize` - Personalize your embeds\n"
                    f"• `{prefix}fm chart` - Generate your album chart\n"
                    f"• `{prefix}fm crowns` - See your artist crowns"
                ),
                inline=True
            )
            
            embed.add_field(
                name="<a:gear:1430203750324240516> Pro Tips",
                value=(
                    f"• Use `{prefix}fm setup` to configure this server\n"
                    f"• Try `{prefix}fm compare @user` to find compatibility\n"
                    f"• Check `{prefix}fm milestones` for achievements"
                ),
                inline=False
            )
            
            # Get user avatar if available
            if 'image' in user_info and user_info['image']:
                for image in reversed(user_info['image']):
                    if image.get('#text'):
                        embed.set_thumbnail(url=image['#text'])
                        break
            
            embed.set_footer(text=f"Last.fm Profile: {username}")
            await ctx.send(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="<a:wrong:1436956421110632489> Database Error",
                description="Failed to link account. Please try again.",
                color=0xff0000
            )
            print(f"[LASTFM ERROR] Failed to link user: {e}")
            await ctx.send(embed=embed)

    @fm.command(name="unset")
    async def fm_unset(self, ctx):
        """Unlink your Last.fm account"""
        try:
            with sqlite3.connect('databases/lastfm.db') as conn:
                cursor = conn.execute(
                    "DELETE FROM lastfm_users WHERE user_id = ?",
                    (ctx.author.id,)
                )
                if cursor.rowcount > 0:
                    embed = discord.Embed(
                        title="<a:yes:1431909187247673464> Account Unlinked",
                        description="Your Last.fm account has been unlinked.",
                        color=self.color
                    )
                else:
                    embed = discord.Embed(
                        title="<a:wrong:1436956421110632489> No Account Linked",
                        description="You don't have a Last.fm account linked.",
                        color=0xff0000
                    )
                await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                title="<a:wrong:1436956421110632489> Error",
                description="Failed to unlink account.",
                color=0xff0000
            )
            await ctx.send(embed=embed)

    @fm.command(name="clearcache", aliases=["cc", "clear"])
    async def fm_clearcache(self, ctx, user: Optional[discord.Member] = None):
        """Refresh/clear Last.fm data cache to get latest information"""
        # Get server prefix for accurate command examples
        prefix = (await self.bot.get_prefix(ctx.message))[0]
        target_user = user or ctx.author
        lastfm_username = self.get_user_lastfm(target_user.id)
        
        if not lastfm_username:
            embed = discord.Embed(
                title="<a:wrong:1436956421110632489> No Account Linked",
                description=f"{'You need' if not user else f'{target_user.mention} needs'} to link a Last.fm account first.",
                color=0xff0000
            )
            await ctx.send(embed=embed)
            return
        
        # Clear cache
        old_cache_count = len(self.session_cache)
        self.clear_cache()
        
        # Force fresh data fetch
        await self.get_lastfm_data(
            'user.getrecenttracks',
            user=lastfm_username,
            limit=1,
            extended=1
        )
        
        embed = discord.Embed(
            title="<:refresh:1437499170087763968> Cache Refreshed",
            description=f"Cleared **{old_cache_count}** cached entries and fetched fresh data for **{target_user.display_name}**",
            color=self.color
        )
        embed.add_field(
            name="<a:blue:1437461186391179284> Tip", 
            value=f"Use `{prefix}fm` now to see the latest track information!",
            inline=False
        )
        
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_interaction(self, interaction):
        """Handle Components v2 button interactions for Last.fm"""
        if not interaction.data or interaction.data.get("component_type") != 2:  # Button
            return
        
        custom_id = interaction.data.get("custom_id", "")
        if not custom_id.startswith("fm_"):
            return
        
        # Parse custom_id: fm_action_userid_param1_param2...
        try:
            parts = custom_id.split("_", 3)
            if len(parts) < 3:
                return
            
            action = parts[1]
            user_id = int(parts[2])
            
            # Check if user can use this button
            if interaction.user.id != user_id:
                return await interaction.response.send_message("<a:wrong:1436956421110632489> This is not your Last.fm panel!", ephemeral=True)
            
            # Handle different actions
            if action == "search":
                await self.handle_fm_search(interaction, parts[3] if len(parts) > 3 else "")
            elif action == "whoknows":
                await self.handle_fm_whoknows(interaction, parts[3] if len(parts) > 3 else "")
            elif action == "stats":
                await self.handle_fm_stats(interaction, parts[3] if len(parts) > 3 else "")
            elif action == "settings":
                await self.handle_fm_settings(interaction)
            elif action == "appearance":
                await self.handle_fm_appearance_settings(interaction)
            elif action == "privacy":
                await self.handle_fm_privacy_settings(interaction)
            elif action == "toggle":
                # Handle mode toggle button
                if len(parts) > 3 and parts[3] == "mode":
                    await self.handle_fm_toggle_mode(interaction, user_id)
            elif action == "customize":
                # Handle customize subactions
                if len(parts) > 3:
                    subaction = parts[3]
                    if subaction == "auto":
                        await self.handle_fm_customize_auto(interaction)
                    elif subaction == "crowns":
                        await self.handle_fm_customize_crowns(interaction)
                    elif subaction == "reactions":
                        await self.handle_fm_customize_reactions(interaction)
                    elif subaction == "colors":
                        await self.handle_fm_customize_colors(interaction)
                    elif subaction == "display":
                        await self.handle_fm_customize_display(interaction)
                    elif subaction == "notifications":
                        await self.handle_fm_customize_notifications(interaction)
                    elif subaction == "mode":
                        await self.handle_fm_customize_mode(interaction)
                    elif subaction == "format":
                        await self.handle_fm_customize_format(interaction)
                    elif subaction == "advanced":
                        await self.handle_fm_customize_advanced(interaction)
                    elif subaction == "reset":
                        await self.handle_fm_customize_reset(interaction)
            
        except (ValueError, IndexError) as e:
            print(f"[FM CV2] Error parsing interaction: {e}")
            return

    async def handle_fm_search(self, interaction, track_artist):
        """Handle search button in CV2 panel"""
        try:
            # Parse track_artist parameter
            if "_" in track_artist:
                track_name, artist_name = track_artist.split("_", 1)
            else:
                track_name = track_artist
                artist_name = ""
            
            # Create search layout with Container
            from discord.ui import LayoutView, Container, Section, TextDisplay, Separator, ActionRow
            
            search_layout = LayoutView()
            
            # Header text
            header_text = TextDisplay(
                f"<a:pengu:1437461955907555449> **Multi-Platform Search**\n\n"
                f"Searching for: **{track_name}** by **{artist_name}**"
            )
            
            # Search platform buttons
            query = f"{track_name} {artist_name}".replace(" ", "%20")
            
            spotify_section = Section(
                TextDisplay("<:spotify:1428206964353269781> **Spotify**"),
                accessory=discord.ui.Button(
                    label="Open",
                    emoji="<:link:1437462772492533791>",
                    style=discord.ButtonStyle.link,
                    url=f"https://open.spotify.com/search/{query}"
                )
            )
            
            youtube_section = Section(
                TextDisplay("<a:youtube:1437463222570586184> **YouTube Music**"),
                accessory=discord.ui.Button(
                    label="Open",
                    emoji="<:link:1437462772492533791>",
                    style=discord.ButtonStyle.link,
                    url=f"https://music.youtube.com/search?q={query}"
                )
            )
            
            apple_section = Section(
                TextDisplay("<:apple:1428207030979526656> **Apple Music**"),
                accessory=discord.ui.Button(
                    label="Open",
                    emoji="<:link:1437462772492533791>",
                    style=discord.ButtonStyle.link,
                    url=f"https://music.apple.com/search?term={query}"
                )
            )
            
            # Wrap in Container with blue accent
            container = Container(
                header_text,
                Separator(),
                spotify_section,
                youtube_section,
                apple_section,
                accent_color=discord.Color.blue()
            )
            
            search_layout.add_item(container)
            
            await interaction.response.send_message(view=search_layout, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"<a:wrong:1436956421110632489> Search error: {e}", ephemeral=True)

    async def handle_fm_whoknows(self, interaction, artist_name):
        """Handle who knows button in CV2 panel - Run actual who knows functionality"""
        try:
            if not interaction.guild:
                return await interaction.response.send_message("<a:wrong:1436956421110632489> Who knows only works in servers!", ephemeral=True)
            
            await interaction.response.defer(ephemeral=True)
            
            # Get all linked users in this guild (same logic as fm_whoknows command)
            try:
                with sqlite3.connect('databases/lastfm.db') as conn:
                    cursor = conn.execute("""
                        SELECT u.user_id, u.lastfm_username 
                        FROM lastfm_users u
                        WHERE u.user_id IN ({})
                    """.format(','.join('?' * len([m.id for m in interaction.guild.members]))),
                    [m.id for m in interaction.guild.members])
                    
                    users = cursor.fetchall()
            except Exception as e:
                return await interaction.followup.send("<a:wrong:1436956421110632489> Database error occurred.", ephemeral=True)
            
            if not users:
                embed = discord.Embed(
                    title="<a:wrong:1436956421110632489> No Linked Users",
                    description="No users in this server have linked their Last.fm accounts.",
                    color=0xff0000
                )
                return await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Get artist plays for each user
            user_plays = []
            
            async def get_user_artist_plays(user_id, username):
                try:
                    data = await self.get_lastfm_data(
                        'artist.getinfo',
                        artist=artist_name,
                        username=username
                    )
                    if data and 'artist' in data and 'userplaycount' in data['artist']:
                        plays = int(data['artist']['userplaycount'])
                        if plays > 0:
                            return (user_id, username, plays)
                except:
                    pass
                return None
            
            # Gather data concurrently
            tasks = [get_user_artist_plays(user_id, username) for user_id, username in users]
            results = await asyncio.gather(*tasks)
            
            # Filter and sort results
            user_plays = [result for result in results if result is not None]
            user_plays.sort(key=lambda x: x[2], reverse=True)
            
            if not user_plays:
                embed = discord.Embed(
                    title="<a:wrong:1436956421110632489> No Data Found",
                    description=f"No one in this server has scrobbled **{artist_name}**.",
                    color=0xff0000
                )
                return await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Create enhanced embed
            embed = discord.Embed(
                title=f"<a:pengu:1437461955907555449> Who **{artist_name}**?",
                color=self.color
            )
            
            # Display top users (limit to 10 for button response)
            limit = min(10, len(user_plays))
            
            description_parts = []
            for i, (user_id, username, plays) in enumerate(user_plays[:limit], 1):
                guild_user = interaction.guild.get_member(user_id)
                display_name = guild_user.display_name if guild_user else username
                
                # Add crown emoji for #1
                crown_emoji = "<a:pengu:1437461955907555449> " if i == 1 else ""
                
                # Format plays nicely
                plays_formatted = f"{plays:,} plays"
                
                description_parts.append(f"**{i}.** {crown_emoji}**{display_name}** — {plays_formatted}")
            
            embed.add_field(
                name=f"<:ar:1427471532841631855> Top {limit} listeners in {interaction.guild.name}",
                value="\n".join(description_parts),
                inline=False
            )
            
            # Add total stats
            total_plays = sum(plays for _, _, plays in user_plays)
            total_listeners = len(user_plays)
            
            embed.add_field(
                name="<:stats:1437456326157668362> Server Stats",
                value=f"**Total plays:** {total_plays:,}\n**Listeners:** {total_listeners}",
                inline=True
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(f"<a:wrong:1436956421110632489> Who knows error: {e}", ephemeral=True)

    async def handle_fm_stats(self, interaction, track_artist):
        """Handle stats button in CV2 panel"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            # Parse parameters
            if "_" in track_artist:
                track_name, artist_name = track_artist.split("_", 1)
            else:
                track_name = track_artist
                artist_name = ""
            
            username = self.get_user_lastfm(interaction.user.id)
            if not username:
                return await interaction.followup.send("<a:wrong:1436956421110632489> No Last.fm account linked!", ephemeral=True)
            
            # Get track info
            track_info = await self.get_lastfm_data(
                'track.getinfo',
                artist=artist_name,
                track=track_name,
                username=username
            )
            
            embed = discord.Embed(
                title=f"<:stats:1437456326157668362> Track Statistics",
                description=f"**{track_name}** by **{artist_name}**",
                color=self.color
            )
            
            if track_info and 'track' in track_info:
                track_data = track_info['track']
                
                stats_text = []
                if 'userplaycount' in track_data:
                    stats_text.append(f"**Your Plays:** {int(track_data['userplaycount']):,}")
                
                if 'playcount' in track_data:
                    stats_text.append(f"**Global Plays:** {int(track_data['playcount']):,}")
                
                if 'listeners' in track_data:
                    stats_text.append(f"**Global Listeners:** {int(track_data['listeners']):,}")
                
                if stats_text:
                    embed.description = f"{embed.description}\n\n" + "\n".join(stats_text)
                
                # Add loved status
                if 'userloved' in track_data and track_data['userloved'] == '1':
                    embed.add_field(name="<a:hearts:1436993503686295634> Status", value="Loved Track", inline=True)
                
            else:
                embed.description = f"{embed.description}\n\nNo detailed statistics available."
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(f"<a:wrong:1436956421110632489> Stats error: {e}", ephemeral=True)

    async def handle_fm_settings(self, interaction):
        """Handle settings button in CV2 panel - show customization options"""
        try:
            # Create CV2 settings panel
            from discord.ui import LayoutView, Section, TextDisplay, Separator
            
            settings_layout = LayoutView()
            
            # Header
            settings_layout.add_item(TextDisplay(
                f"<a:gear:1430203750324240516> **Last.fm Customization**\n"
                f"Personalize your Last.fm experience"
            ))
            
            settings_layout.add_item(Separator())
            
            # Settings sections
            settings_layout.add_item(Section(
                TextDisplay("<:paint:1437499837036625960> **Embed Appearance**"),
                accessory=discord.ui.Button(
                    label="Appearance",
                    emoji="<:paint:1437499837036625960>",
                    style=discord.ButtonStyle.primary,
                    custom_id=f"fm_appearance_{interaction.user.id}"
                )
            ))
            
            settings_layout.add_item(Section(
                TextDisplay("<a:lock:1437496504955699402> **Privacy Settings**"),
                accessory=discord.ui.Button(
                    label="Privacy",
                    emoji="<a:lock:1437496504955699402>",
                    style=discord.ButtonStyle.secondary,
                    custom_id=f"fm_privacy_{interaction.user.id}"
                )
            ))
            
            settings_layout.add_item(Section(
                TextDisplay("🌍 **Timezone Settings**"),
                accessory=discord.ui.Button(
                    label="Timezone",
                    emoji="🌍",
                    style=discord.ButtonStyle.secondary,
                    custom_id=f"fm_timezone_{interaction.user.id}"
                )
            ))
            
            settings_layout.add_item(Section(
                TextDisplay("📊 **Chart Preferences**"),
                accessory=discord.ui.Button(
                    label="Charts",
                    emoji="📊",
                    style=discord.ButtonStyle.secondary,
                    custom_id=f"fm_charts_{interaction.user.id}"
                )
            ))
            
            # Wrap in Container for proper embed-like display
            from discord.ui import Container
            container = Container(
                settings_layout.children[0],  # Header TextDisplay
                settings_layout.children[1],  # Separator
                settings_layout.children[2],  # Appearance section
                settings_layout.children[3],  # Privacy section
                settings_layout.children[4],  # Timezone section
                settings_layout.children[5],  # Charts section
                accent_color=discord.Color.from_rgb(88, 101, 242)  # Discord blurple
            )
            
            final_layout = LayoutView()
            final_layout.add_item(container)
            
            await interaction.response.send_message(view=final_layout, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"<a:wrong:1436956421110632489> Settings error: {e}", ephemeral=True)

    async def handle_fm_appearance_settings(self, interaction):
        """Handle appearance settings CV2 panel"""
        try:
            from discord.ui import LayoutView, Section, TextDisplay, Separator
            
            settings_layout = LayoutView()
            
            settings_layout.add_item(TextDisplay(
                f"<:paint:1437499837036625960> **Appearance Settings**\n"
                f"Customize how your Last.fm embeds look"
            ))
            
            settings_layout.add_item(Separator())
            
            # Color theme options
            settings_layout.add_item(Section(
                TextDisplay("🌈 **Color Theme**\n*Default, Red, Blue, Green, Purple*"),
                accessory=discord.ui.Button(
                    label="Set Color",
                    emoji="🌈",
                    style=discord.ButtonStyle.secondary,
                    custom_id=f"fm_setcolor_{interaction.user.id}"
                )
            ))
            
            # Show/hide elements
            settings_layout.add_item(Section(
                TextDisplay("👁️ **Display Options**\n*Toggle embed elements*"),
                accessory=discord.ui.Button(
                    label="Display",
                    emoji="👁️",
                    style=discord.ButtonStyle.secondary,
                    custom_id=f"fm_display_{interaction.user.id}"
                )
            ))
            
            # Avatar settings
            settings_layout.add_item(Section(
                TextDisplay("🖼️ **Avatar Display**\n*Show/hide profile pictures*"),
                accessory=discord.ui.Button(
                    label="Avatar",
                    emoji="🖼️",
                    style=discord.ButtonStyle.secondary,
                    custom_id=f"fm_avatar_{interaction.user.id}"
                )
            ))
            
            # Components v2 doesn't support embeds
            content = "<:paint:1437499837036625960> **Appearance Settings**"
            await interaction.response.send_message(content=content, view=settings_layout, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"<a:wrong:1436956421110632489> Appearance error: {e}", ephemeral=True)

    async def handle_fm_privacy_settings(self, interaction):
        """Handle privacy settings CV2 panel"""
        try:
            from discord.ui import LayoutView, Section, TextDisplay, Separator
            
            settings_layout = LayoutView()
            
            settings_layout.add_item(TextDisplay(
                f"<a:lock:1437496504955699402> **Privacy Settings**\n"
                f"Control what information is shared"
            ))
            
            settings_layout.add_item(Separator())
            
            # Profile visibility
            settings_layout.add_item(Section(
                TextDisplay("👤 **Profile Visibility**\n*Public, Friends Only, Private*"),
                accessory=discord.ui.Button(
                    label="Visibility",
                    emoji="👤",
                    style=discord.ButtonStyle.secondary,
                    custom_id=f"fm_visibility_{interaction.user.id}"
                )
            ))
            
            # Crown notifications
            settings_layout.add_item(Section(
                TextDisplay("<a:crown:1437503143591153756> **Crown Notifications**\n*Get notified when you earn crowns*"),
                accessory=discord.ui.Button(
                    label="Crowns",
                    emoji="<a:crown:1437503143591153756>",
                    style=discord.ButtonStyle.secondary,
                    custom_id=f"fm_crowns_{interaction.user.id}"
                )
            ))
            
            # Components v2 doesn't support embeds
            content = "<a:lock:1437496504955699402> **Privacy Settings**"
            await interaction.response.send_message(content=content, view=settings_layout, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"<a:wrong:1436956421110632489> Privacy error: {e}", ephemeral=True)

    async def handle_fm_customize_auto(self, interaction):
        """Handle auto showcase toggle"""
        try:
            user_id = interaction.user.id
            with sqlite3.connect('databases/lastfm.db') as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT auto_showcase FROM lastfm_users WHERE user_id = ?", (user_id,))
                result = cursor.fetchone()
                
                if result:
                    current_state = bool(result[0])
                    new_state = not current_state
                    cursor.execute("UPDATE lastfm_users SET auto_showcase = ? WHERE user_id = ?", (new_state, user_id))
                    conn.commit()
                    
                    status = "<a:yes:1431909187247673464> Enabled" if new_state else "<a:wrong:1436956421110632489> Disabled"
                    await interaction.response.send_message(f"<:speaker:1428183066311921804> **Auto Showcase:** {status}", ephemeral=True)
                else:
                    await interaction.response.send_message("<a:wrong:1436956421110632489> No Last.fm account found!", ephemeral=True)
                    
        except Exception as e:
            await interaction.response.send_message(f"<a:wrong:1436956421110632489> Error: {e}", ephemeral=True)

    async def handle_fm_customize_crowns(self, interaction):
        """Handle crown participation toggle"""
        try:
            user_id = interaction.user.id
            with sqlite3.connect('databases/lastfm.db') as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT crown_optout FROM lastfm_users WHERE user_id = ?", (user_id,))
                result = cursor.fetchone()
                
                if result:
                    current_optout = bool(result[0])
                    new_optout = not current_optout
                    cursor.execute("UPDATE lastfm_users SET crown_optout = ? WHERE user_id = ?", (new_optout, user_id))
                    conn.commit()
                    
                    status = "<a:wrong:1436956421110632489> Opted Out" if new_optout else "<a:yes:1431909187247673464> Participating"
                    await interaction.response.send_message(f"<a:crown:1437503143591153756> **Crown Participation:** {status}", ephemeral=True)
                else:
                    await interaction.response.send_message("<a:wrong:1436956421110632489> No Last.fm account found!", ephemeral=True)
                    
        except Exception as e:
            await interaction.response.send_message(f"<a:wrong:1436956421110632489> Error: {e}", ephemeral=True)

    async def get_prefix_from_interaction(self, interaction):
        """Helper to get prefix from interaction"""
        if hasattr(interaction, 'message') and interaction.message:
            return (await self.bot.get_prefix(interaction.message))[0]
        else:
            # Fallback: create a mock message for prefix lookup
            from types import SimpleNamespace
            mock_message = SimpleNamespace()
            mock_message.guild = interaction.guild
            mock_message.channel = interaction.channel if hasattr(interaction, 'channel') else None
            return (await self.bot.get_prefix(mock_message))[0]

    async def handle_fm_customize_reactions(self, interaction):
        """Handle FULLY CUSTOMIZABLE reaction emoji system"""
        try:
            # Get server prefix for accurate command examples
            prefix = await self.get_prefix_from_interaction(interaction)
            user_id = interaction.user.id
            
            # Get user's personal reaction settings
            with sqlite3.connect('databases/lastfm.db') as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT custom_reactions, auto_react FROM lastfm_user_customization WHERE user_id = ?", (user_id,))
                result = cursor.fetchone()
            
            current_reactions = []
            auto_react = True
            
            if result and result[0]:
                import json
                try:
                    current_reactions = json.loads(result[0])
                    auto_react = bool(result[1])
                except:
                    current_reactions = ["<:speaker:1428183066311921804>", "❤️", "🔥", "👎", "🎸", "🎤"]
            else:
                current_reactions = ["<:speaker:1428183066311921804>", "❤️", "🔥", "👎", "🎸", "🎤"]
            
            content = f"<:**FULLY CUSTOMIZABLE Reactions**\n\n"
            content += f"**Current Auto React:** {'<a:yes:1431909187247673464> Enabled' if auto_react else '<a:wrong:1436956421110632489> Disabled'}\n"
            content += f"**Your Custom Reactions:** {' '.join(current_reactions[:8])}\n\n"
            
            content += f"**<:paint:1437499837036625960> UNLIMITED CUSTOMIZATION:**\n"
            content += f"• Use ANY emoji (including server emojis!)\n"
            content += f"• Set up to 8 custom reactions\n"
            content += f"• Mix Unicode + Server emojis\n"
            content += f"• Completely personalized\n\n"
            

            
            content += f"**<a:gear:1430203750324240516> Commands:**\n"
            content += f"• `{prefix}fm reactions custom <emoji1> <emoji2> ...` - Set your reactions\n"
            content += f"• `{prefix}fm reactions toggle` - Enable/disable auto react\n"
            content += f"• `{prefix}fm reactions clear` - Remove all reactions\n\n"
            
            content += f"**<:like:1428199620554657842> Examples:**\n"
            content += f"• `{prefix}fm reactions custom <:speaker:1428183066311921804> <:custom:123> ❤️ 🔥`\n"
            content += f"• `{prefix}fm reactions custom <:vibing:456> <:fire:789> <:love:101>`"
            
            await interaction.response.send_message(content=content, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"<a:wrong:1436956421110632489> Error: {e}", ephemeral=True)

    async def handle_fm_customize_colors(self, interaction):
        """Handle color theme customization"""
        try:
            # Get server prefix for accurate command examples
            prefix = await self.get_prefix_from_interaction(interaction)
            guild_id = interaction.guild.id if interaction.guild else None
            if not guild_id:
                return await interaction.response.send_message("<a:wrong:1436956421110632489> This only works in servers!", ephemeral=True)
            
            settings = self.get_guild_settings(guild_id)
            current_color = settings['embed_color']
            
            content = f"<:paint:1437499837036625960> **Color Themes**\n\n"
            content += f"**Current Color:** {current_color}\n\n"
            content += f"**<:paint:1437499837036625960> Color Customization:**\n"
            content += f"Use any hex color code (e.g., `#ff5733`, `#42a5f5`)\n\n"
            content += f"Use `{prefix}fm color <hex>` to change!\n"
            content += f"Example: `{prefix}fm color #ff5733`"
            
            await interaction.response.send_message(content=content, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"<a:wrong:1436956421110632489> Error: {e}", ephemeral=True)

    async def handle_fm_customize_display(self, interaction):
        """Handle display options customization"""
        try:
            # Get server prefix for accurate command examples
            prefix = await self.get_prefix_from_interaction(interaction)
            guild_id = interaction.guild.id if interaction.guild else None
            if not guild_id:
                return await interaction.response.send_message("<a:wrong:1436956421110632489> This only works in servers!", ephemeral=True)
            
            settings = self.get_guild_settings(guild_id)
            
            content = f"<a:phone:1436953635731800178> **Display Options**\n\n"
            content += f"**Current Settings:**\n"
            content += f"📊 **Show Play Counts:** {'<a:yes:1431909187247673464> Enabled' if settings['show_playcount'] else '<a:wrong:1436956421110632489> Disabled'}\n"
            content += f"📈 **Show Scrobbles:** {'<a:yes:1431909187247673464> Enabled' if settings['show_scrobbles'] else '<a:wrong:1436956421110632489> Disabled'}\n"
            content += f"🖼️ **Show Album Art:** {'<a:yes:1431909187247673464> Enabled' if settings['show_album_art'] else '<a:wrong:1436956421110632489> Disabled'}\n"
            content += f"<a:crown:1437503143591153756> **Crown System:** {'<a:yes:1431909187247673464> Enabled' if settings['crown_system'] else '<a:wrong:1436956421110632489> Disabled'}\n\n"
            content += f"**📋 Toggle Options:**\n"
            content += f"Use `{prefix}fm toggle <option>` to change settings:\n"
            content += f"• `{prefix}fm toggle playcounts`\n"
            content += f"• `{prefix}fm toggle scrobbles`\n"
            content += f"• `{prefix}fm toggle albumart`\n"
            content += f"• `{prefix}fm toggle crowns`"
            
            await interaction.response.send_message(content=content, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"<a:wrong:1436956421110632489> Error: {e}", ephemeral=True)

    async def handle_fm_customize_notifications(self, interaction):
        """Handle notification preferences"""
        try:
            user_id = interaction.user.id
            with sqlite3.connect('databases/lastfm.db') as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT reaction_notifications FROM lastfm_users WHERE user_id = ?", (user_id,))
                result = cursor.fetchone()
                
                if result:
                    current_state = bool(result[0])
                    new_state = not current_state
                    cursor.execute("UPDATE lastfm_users SET reaction_notifications = ? WHERE user_id = ?", (new_state, user_id))
                    conn.commit()
                    
                    status = "<a:yes:1431909187247673464> Enabled" if new_state else "<a:wrong:1436956421110632489> Disabled"
                    await interaction.response.send_message(f"🔔 **Reaction Notifications:** {status}", ephemeral=True)
                else:
                    await interaction.response.send_message("<a:wrong:1436956421110632489> No Last.fm account found!", ephemeral=True)
                    
        except Exception as e:
            await interaction.response.send_message(f"<a:wrong:1436956421110632489> Error: {e}", ephemeral=True)

    async def handle_fm_customize_mode(self, interaction):
        """Handle switching between Embed and CV2 display modes"""
        try:
            # Get server prefix for accurate command examples
            prefix = await self.get_prefix_from_interaction(interaction)
            user_id = interaction.user.id
            
            with sqlite3.connect('databases/lastfm.db') as conn:
                cursor = conn.cursor()
                # Get current mode
                cursor.execute("SELECT display_mode FROM lastfm_user_customization WHERE user_id = ?", (user_id,))
                result = cursor.fetchone()
                
                current_mode = result[0] if result else 'cv2'
                new_mode = 'embed' if current_mode == 'cv2' else 'cv2'
                
                # Update or insert
                cursor.execute("""
                    INSERT OR REPLACE INTO lastfm_user_customization 
                    (user_id, display_mode) VALUES (?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET display_mode = ?
                """, (user_id, new_mode, new_mode))
                conn.commit()
            
            mode_emoji = "🖼️" if new_mode == "embed" else "📋"
            mode_name = "Embed Style" if new_mode == "embed" else "CV2 Style"
            
            content = f"🖥️ **Display Mode Changed!**\n\n"
            content += f"**New Mode:** {mode_emoji} {mode_name}\n\n"
            
            if new_mode == "embed":
                content += f"**📋 Embed Features:**\n"
                content += f"• Rich embed layouts\n"
                content += f"• Thumbnail images\n"
                content += f"• Colored sidebars\n"
                content += f"• Traditional Discord look\n"
            else:
                content += f"**🚀 CV2 Features:**\n"
                content += f"• Modern message-based display\n"
                content += f"• Horizontal interactive buttons\n"
                content += f"• Cleaner text layout\n"
                content += f"• Mobile-friendly design\n"
            
            content += f"\nTry `{prefix}fm` to see your new display mode!"
            
            await interaction.response.send_message(content=content, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"<a:wrong:1436956421110632489> Error: {e}", ephemeral=True)

    async def handle_fm_toggle_mode(self, interaction, user_id):
        """Toggle between CV1 (Embed) and CV2 (Components) display modes"""
        try:
            with sqlite3.connect('databases/lastfm.db') as conn:
                cursor = conn.cursor()
                
                # Get current mode
                cursor.execute("SELECT display_mode FROM lastfm_user_customization WHERE user_id = ?", (user_id,))
                result = cursor.fetchone()
                
                current_mode = result[0] if result else 'cv2'
                new_mode = 'cv1' if current_mode == 'cv2' else 'cv2'
                
                # Update or insert
                if result:
                    cursor.execute("UPDATE lastfm_user_customization SET display_mode = ? WHERE user_id = ?", 
                                 (new_mode, user_id))
                else:
                    cursor.execute("INSERT INTO lastfm_user_customization (user_id, display_mode) VALUES (?, ?)", 
                                 (user_id, new_mode))
                conn.commit()
            
            # Build response
            if new_mode == 'cv1':
                mode_desc = "**Embed Mode** (includes album art)"
                emoji = "<:bot:1428163130663375029>"
            else:
                mode_desc = "**Components v2** (interactive buttons)"
                emoji = "<a:mark:1436953593923244113>"
            
            content = f"{emoji} **Display Mode Switched!**\n\n"
            content += f"Now using: {mode_desc}\n\n"
            content += f"Use `/fm` to see your music in the new mode!"
            
            await interaction.response.send_message(content=content, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"<a:wrong:1436956421110632489> Error: {str(e)}", ephemeral=True)

    async def handle_fm_customize_format(self, interaction):
        """Handle custom message formatting"""
        try:
            # Get server prefix for accurate command examples
            prefix = await self.get_prefix_from_interaction(interaction)
            
            content = f"📝 **Custom Message Format**\n\n"
            content += f"**<:paint:1437499837036625960> Customize Your Display Text:**\n\n"
            
            content += f"**Available Variables:**\n"
            content += f"• `{{track}}` - Track name\n"
            content += f"• `{{artist}}` - Artist name\n"
            content += f"• `{{album}}` - Album name\n"
            content += f"• `{{plays}}` - Your play count\n"
            content += f"• `{{user}}` - Your display name\n"
            content += f"• `{{status}}` - Playing status\n\n"
            
            content += f"**📋 Format Examples:**\n"
            content += f"• Default: `{{status}} {{track}} by {{artist}}`\n"
            content += f"• Minimal: `<:speaker:1428183066311921804> {{track}} - {{artist}}`\n"
            content += f"• Detailed: `{{user}} is vibing to {{track}} by {{artist}} ({{plays}} plays)`\n"
            content += f"• Custom: `🔥 JAMMING TO: {{track}} 🔥`\n\n"
            
            content += f"**<a:gear:1430203750324240516> Commands:**\n"
            content += f"• `{prefix}fm format <your format>` - Set custom format\n"
            content += f"• `{prefix}fm format reset` - Reset to default\n"
            content += f"• `{prefix}fm format preview <format>` - Preview format\n\n"
            
            content += f"**💡 Example:**\n"
            content += f"`{prefix}fm format 🎧 {{user}} is listening to {{track}} by {{artist}} 🎧`"
            
            await interaction.response.send_message(content=content, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"<a:wrong:1436956421110632489> Error: {e}", ephemeral=True)

    async def handle_fm_customize_advanced(self, interaction):
        """Handle advanced customization options"""
        try:
            # Get server prefix for accurate command examples
            prefix = await self.get_prefix_from_interaction(interaction)
            user_id = interaction.user.id
            
            content = f"<a:gear:1430203750324240516> **Advanced Customization**\n\n"
            content += f"**🚀 Power User Features:**\n\n"
            
            content += f"**<:paint:1437499837036625960> Advanced Display:**\n"
            content += f"• Custom CSS-style colors (`#hex`)\n"
            content += f"• Gradient color schemes\n"
            content += f"• Custom emoji sets from multiple servers\n"
            content += f"• Advanced message templates\n\n"
            
            content += f"**📊 Data Options:**\n"
            content += f"• Show/hide specific statistics\n"
            content += f"• Custom timestamp formats\n"
            content += f"• Automatic link generation\n"
            content += f"• Smart scrobble detection\n\n"
            
            content += f"**🔧 Performance:**\n"
            content += f"• Cache preferences\n"
            content += f"• Update frequency settings\n"
            content += f"• Notification timing\n\n"
            
            content += f"**<a:gear:1430203750324240516> Advanced Commands:**\n"
            content += f"• `{prefix}fm color #ff0066` - Custom hex colors\n"
            content += f"• `{prefix}fm template advanced` - Advanced templates\n"
            content += f"• `{prefix}fm cache settings` - Cache preferences\n"
            content += f"• `{prefix}fm export settings` - Export your config\n"
            content += f"• `{prefix}fm import <config>` - Import config\n\n"
            
            content += f"**💡 Pro Tips:**\n"
            content += f"• Use server emojis: `<:name:id>`\n"
            content += f"• Combine multiple color codes\n"
            content += f"• Save configs as presets"
            
            await interaction.response.send_message(content=content, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"<a:wrong:1436956421110632489> Error: {e}", ephemeral=True)

    async def handle_fm_customize_reset(self, interaction):
        """Handle resetting all customization to defaults"""
        try:
            # Get server prefix for accurate command examples
            prefix = await self.get_prefix_from_interaction(interaction)
            user_id = interaction.user.id
            
            # Confirmation step
            content = f"<:refresh:1437499170087763968> **Reset All Customization**\n\n"
            content += f"⚠️ **Warning:** This will reset ALL your customization:\n"
            content += f"• Display mode (back to CV2)\n"
            content += f"• Custom reactions\n"
            content += f"• Color themes\n"
            content += f"• Message formats\n"
            content += f"• All display preferences\n\n"
            content += f"**This action cannot be undone!**\n\n"
            content += f"Use `{prefix}fm reset confirm` to proceed."
            
            await interaction.response.send_message(content=content, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"<a:wrong:1436956421110632489> Error: {e}", ephemeral=True)

    @fm.command(name="cv2test")
    async def fm_cv2_test(self, ctx):
        """Test the Components v2 Last.fm panel"""
        # Get server prefix for accurate command examples
        prefix = (await self.bot.get_prefix(ctx.message))[0]
        
        username = self.get_user_lastfm(ctx.author.id)
        if not username:
            return await ctx.send(f"<a:wrong:1436956421110632489> No Last.fm account linked! Use `{prefix}fm set <username>` first.")
        
        # Create a test CV2 panel (no embed needed - all info in CV2 layout)
        cv2_view = self.create_fm_cv2_panel("Test Track", "Test Artist", "Test Album", username, ctx.author, track_info=None, is_now_playing=True)
        
        await ctx.send(view=cv2_view)

    @fm.command(name="debug", aliases=["test"])
    async def fm_debug(self, ctx, user: Optional[discord.Member] = None):
        """Debug Last.fm data fetching and caching issues"""
        target_user = user or ctx.author
        lastfm_username = self.get_user_lastfm(target_user.id)
        
        if not lastfm_username:
            embed = discord.Embed(
                title="<a:wrong:1436956421110632489> No Account Linked",
                description=f"{'You need' if not user else f'{target_user.mention} needs'} to link a Last.fm account first.",
                color=0xff0000
            )
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title="🧪 Last.fm Debug Information",
            description=f"Debug info for **{target_user.display_name}** ({lastfm_username})",
            color=self.color
        )
        
        # Cache info
        cache_count = len(self.session_cache)
        embed.add_field(
            name="💾 Cache Status",
            value=f"**Entries:** {cache_count}\n**API Key:** {'<a:yes:1431909187247673464> Set' if self.api_key else '<a:wrong:1436956421110632489> Missing'}",
            inline=True
        )
        
        # Current time
        current_time = datetime.now(timezone.utc)
        embed.add_field(
            name="⏰ Current Time",
            value=f"**UTC:** {current_time.strftime('%Y-%m-%d %H:%M:%S')}\n**Unix:** {int(current_time.timestamp())}",
            inline=True
        )
        
        # Clear cache and test fresh API call
        old_cache_count = len(self.session_cache)
        self.clear_cache()
        
        # Make fresh API call
        import time
        start_time = time.time()
        
        data = await self.get_lastfm_data(
            'user.getrecenttracks',
            user=lastfm_username,
            limit=1,
            extended=1
        )
        
        end_time = time.time()
        api_time = end_time - start_time
        
        if data and 'recenttracks' in data and data['recenttracks'].get('track'):
            track = data['recenttracks']['track']
            if isinstance(track, list):
                track = track[0]
            
            track_info = f"**Track:** {track.get('name', 'Unknown')}\n"
            track_info += f"**Artist:** {track.get('artist', {}).get('name', 'Unknown')}\n"
            
            # Check timestamp
            is_now_playing = '@attr' in track and 'nowplaying' in track.get('@attr', {})
            if is_now_playing:
                track_info += f"**Status:** <:speaker:1428183066311921804> Now Playing"
            elif 'date' in track:
                try:
                    uts_timestamp = int(track['date']['uts'])
                    played_time = datetime.fromtimestamp(uts_timestamp)
                    track_info += f"**Last Played:** {played_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    track_info += f"**Unix Time:** {uts_timestamp}"
                except:
                    track_info += f"**Status:** <a:wrong:1436956421110632489> Invalid timestamp"
            else:
                track_info += f"**Status:** <a:wrong:1436956421110632489> No date info"
            
            embed.add_field(
                name="<:speaker:1428183066311921804> Latest Track",
                value=track_info,
                inline=False
            )
        else:
            embed.add_field(
                name="<:speaker:1428183066311921804> Latest Track",
                value="<a:wrong:1436956421110632489> No track data found",
                inline=False
            )
        
        embed.add_field(
            name="🔍 API Call Info",
            value=f"**Response Time:** {api_time:.2f}s\n**Cache Cleared:** {old_cache_count} entries\n**Fresh Data:** <a:yes:1431909187247673464> Yes",
            inline=False
        )
        
        embed.set_footer(text="Use this to troubleshoot fm command issues")
        await ctx.send(embed=embed)

    @fm.command(name="diagnose", aliases=["diag", "check"])
    async def fm_diagnose(self, ctx, user: Optional[discord.Member] = None, limit: int = 10):
        """Diagnose Last.fm connection and scrobbling issues"""
        target_user = user or ctx.author
        lastfm_username = self.get_user_lastfm(target_user.id)
        
        if not lastfm_username:
            embed = discord.Embed(
                title="<a:wrong:1436956421110632489> No Account Linked",
                description=f"{'You need' if not user else f'{target_user.mention} needs'} to link a Last.fm account first.",
                color=0xff0000
            )
            await ctx.send(embed=embed)
            return
        
        # Clear cache to get absolutely fresh data
        self.clear_cache()
        print(f"[DEBUG SCROBBLES] Checking {limit} recent tracks for {lastfm_username}")
        
        # Get recent tracks with higher limit
        data = await self.get_lastfm_data(
            'user.getrecenttracks',
            user=lastfm_username,
            limit=min(limit, 50),  # Max 50 to avoid spam
            extended=1
        )
        
        embed = discord.Embed(
            title=f"🔍 Recent Scrobbles - {target_user.display_name}",
            description=f"Last.fm username: **{lastfm_username}**",
            color=self.color
        )
        
        if not data or 'error' in data or not data.get('recenttracks', {}).get('track'):
            embed.add_field(
                name="<a:wrong:1436956421110632489> No Data Found",
                value="No recent tracks found or API error occurred.",
                inline=False
            )
            
            # Add troubleshooting tips
            embed.add_field(
                name="🔧 Troubleshooting Steps",
                value=(
                    "1. Check https://last.fm/user/" + lastfm_username + "\n"
                    "2. Verify Spotify/music app is connected to Last.fm\n"
                    "3. Play a song and wait 1-2 minutes for scrobbling\n"
                    "4. Check Last.fm settings in your music app"
                ),
                inline=False
            )
            await ctx.send(embed=embed)
            return
        
        tracks = data['recenttracks']['track']
        if not isinstance(tracks, list):
            tracks = [tracks]
        
        print(f"[DEBUG SCROBBLES] Found {len(tracks)} tracks")
        
        # Check account info
        user_info = await self.get_lastfm_data('user.getinfo', user=lastfm_username)
        if user_info and 'user' in user_info:
            user_data = user_info['user']
            total_scrobbles = user_data.get('playcount', 'Unknown')
            registered = user_data.get('registered', {}).get('#text', 'Unknown')
            
            # Format scrobbles with comma if it's a number
            if isinstance(total_scrobbles, str) and total_scrobbles.isdigit():
                total_scrobbles = f"{int(total_scrobbles):,}"
            elif isinstance(total_scrobbles, int):
                total_scrobbles = f"{total_scrobbles:,}"
            # Otherwise keep as string (e.g., "Unknown")
            
            embed.add_field(
                name="📊 Account Info",
                value=f"**Total Scrobbles:** {total_scrobbles}\n**Registered:** {registered}",
                inline=True
            )
        
        # Add recent tracks info
        track_list = []
        now_playing_found = False
        
        for i, track in enumerate(tracks[:limit]):
            track_name = track.get('name', 'Unknown')
            artist_name = track.get('artist', {})
            if isinstance(artist_name, dict):
                artist_name = artist_name.get('name', 'Unknown')
            
            # Check if now playing
            is_now_playing = '@attr' in track and 'nowplaying' in track.get('@attr', {})
            
            if is_now_playing:
                track_list.append(f"<:speaker:1428183066311921804> **{track_name}** by **{artist_name}** *(Now Playing)*")
                now_playing_found = True
            elif 'date' in track:
                try:
                    uts_timestamp = int(track['date']['uts'])
                    played_time = datetime.fromtimestamp(uts_timestamp)
                    time_ago = self.get_time_ago(played_time)
                    track_list.append(f"**{i+1}.** {track_name} by {artist_name} - *{time_ago}*")
                except:
                    track_list.append(f"**{i+1}.** {track_name} by {artist_name} - *Unknown time*")
            else:
                track_list.append(f"**{i+1}.** {track_name} by {artist_name} - *No timestamp*")
        
        if track_list:
            embed.add_field(
                name=f"<:speaker:1428183066311921804> Recent Tracks ({len(track_list)})",
                value="\n".join(track_list[:10]),  # Limit display to avoid embed limits
                inline=False
            )
        
        # Add status info
        status_info = []
        if now_playing_found:
            status_info.append("<a:yes:1431909187247673464> Currently listening")
        
        # Check last scrobble time
        if tracks and 'date' in tracks[0]:
            try:
                last_uts = int(tracks[0]['date']['uts'])
                last_time = datetime.fromtimestamp(last_uts)
                time_since_last = datetime.now() - last_time
                
                if time_since_last.days > 0:
                    status_info.append(f"⚠️ Last scrobble: {time_since_last.days} days ago")
                elif time_since_last.seconds > 3600:  # More than 1 hour
                    hours = time_since_last.seconds // 3600
                    status_info.append(f"⚠️ Last scrobble: {hours} hours ago")
                else:
                    status_info.append("<a:yes:1431909187247673464> Recent scrobbling activity")
            except:
                status_info.append("❓ Cannot determine last scrobble time")
        elif not now_playing_found:
            status_info.append("<a:wrong:1436956421110632489> No recent scrobbling detected")
        
        if status_info:
            embed.add_field(
                name="📡 Scrobbling Status",
                value="\n".join(status_info),
                inline=False
            )
        
        # Add helpful links
        embed.add_field(
            name="<:link:1193611630836207656> Helpful Links",
            value=(
                f"[Your Last.fm Profile](https://last.fm/user/{lastfm_username})\n"
                "[Spotify Last.fm Settings](https://www.last.fm/settings/applications)\n"
                "[Last.fm Troubleshooting](https://support.last.fm/t/spotify-scrobbling-faq/129)"
            ),
            inline=False
        )
        
        embed.set_footer(text="If no recent activity shows, check your music app's Last.fm connection")
        await ctx.send(embed=embed)

    def get_time_ago(self, past_time):
        """Get human readable time ago string"""
        now = datetime.now()
        diff = now - past_time
        
        if diff.days > 0:
            return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        elif diff.seconds >= 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif diff.seconds >= 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return "Just now"

    def create_fm_cv2_panel(self, track_name, artist_name, album_name, lastfm_username, user, track_info=None, is_now_playing=False, image_url=None, embed_color=None):
        """Create Components v2 panel with Container wrapping - proper embed-like display"""
        from discord.ui import LayoutView, Container, Section, TextDisplay, Thumbnail, ActionRow, Separator
        
        layout = LayoutView()
        
        # Status indicator
        status_emoji = "<a:online:1431491381817380985>" if is_now_playing else "⏸️"
        status_text = "Currently Playing" if is_now_playing else "Last Played"
        
        # Create main content section with track info and links
        track_url = f"https://www.last.fm/music/{urllib.parse.quote(artist_name)}/_/{urllib.parse.quote(track_name)}"
        artist_url = f"https://www.last.fm/music/{urllib.parse.quote(artist_name)}"
        
        content_text = f"{status_emoji} **{status_text}**\n\n**[{track_name}]({track_url})**\nby **[{artist_name}]({artist_url})**"
        
        if album_name and album_name not in ["Unknown", "Unknown Album"] and album_name != artist_name:
            content_text += f"\n<a:vinyl:1437493964855836672> *{album_name}*"
        
        # Add play count if available
        if track_info and 'userplaycount' in track_info:
            plays = int(track_info['userplaycount'])
            if plays > 0:
                content_text += f"\n\n<a:plays:1437493915677626388> **{plays:,}** plays"
        
        # Create the main text display
        text_display = TextDisplay(content_text)
        
        # Create section with thumbnail if image available
        if image_url:
            thumbnail = Thumbnail(media=image_url)
            main_section = Section(text_display, accessory=thumbnail)
        else:
            # Section requires accessory, so use TextDisplay directly
            main_section = text_display
        
        # Create horizontal button row using ActionRow pattern
        button_row = ActionRow(
            discord.ui.Button(
                label="Search",
                emoji="🔍",
                style=discord.ButtonStyle.primary,
                custom_id=f"fm_search_{user.id}_{track_name}_{artist_name}"
            ),
            discord.ui.Button(
                label="Who Knows",
                emoji="<a:questionmarks:1436953662122365039>",
                style=discord.ButtonStyle.secondary,
                custom_id=f"fm_whoknows_{user.id}_{artist_name}"
            ),
            discord.ui.Button(
                label="Stats",
                emoji="<:stats:1437456326157668362>",
                style=discord.ButtonStyle.secondary,
                custom_id=f"fm_stats_{user.id}_{track_name}_{artist_name}"
            ),
            discord.ui.Button(
                label="Last.fm",
                emoji="<:link:1193611630836207656>",
                style=discord.ButtonStyle.link,
                url=track_url
            ),
            discord.ui.Button(
                label="Settings",
                emoji="<a:gear:1430203750324240516>",
                style=discord.ButtonStyle.secondary,
                custom_id=f"fm_settings_{user.id}"
            )
        )
        
        # Wrap everything in a Container with embed-like styling
        # Use custom color if provided, otherwise default to blue
        if embed_color:
            # Convert hex color to discord.Color
            color_int = int(embed_color.replace('#', ''), 16)
            accent = discord.Color(color_int)
        else:
            accent = discord.Color.blue()
        
        container = Container(
            main_section,
            Separator(),
            button_row,
            accent_color=accent
        )
        
        layout.add_item(container)
        return layout
        

    @fm.command(name="np", aliases=["nowplaying"])
    async def fm_np(self, ctx, user: Optional[discord.Member] = None):
        """Enhanced now playing with rich information"""
        # Get server prefix for accurate command examples
        prefix = (await self.bot.get_prefix(ctx.message))[0]
        
        target_user = user or ctx.author
        lastfm_username = self.get_user_lastfm(target_user.id)
        
        if not lastfm_username:
            embed = discord.Embed(
                title="<a:wrong:1436956421110632489> No Account Linked",
                description=f"{'You need' if not user else f'{target_user.mention} needs'} to link a Last.fm account first.\nUse `{prefix}fm set <username>` to get started!",
                color=0xff0000
            )
            await ctx.send(embed=embed)
            return

        # Get recent tracks (now playing will be first if currently listening)
        # Clear all cache to ensure completely fresh data
        print(f"[DEBUG FM NP] Clearing cache before fetching data for {lastfm_username}")
        self.clear_cache()
        
        data = await self.get_lastfm_data(
            'user.getrecenttracks',
            user=lastfm_username,
            limit=1,
            extended=1
        )
        
        print(f"[DEBUG FM NP] API Response received: {bool(data)}")
        if data:
            print(f"[DEBUG FM NP] Response keys: {list(data.keys())}")
            if 'recenttracks' in data:
                print(f"[DEBUG FM NP] Recent tracks keys: {list(data['recenttracks'].keys())}")
                if 'track' in data['recenttracks']:
                    track_data = data['recenttracks']['track']
                    if isinstance(track_data, list):
                        print(f"[DEBUG FM NP] Found {len(track_data)} tracks")
                    else:
                        print(f"[DEBUG FM NP] Found single track")
        
        if not data or (data and 'error' in data) or not data.get('recenttracks', {}).get('track'):
            embed = discord.Embed(
                title="<a:wrong:1436956421110632489> No Recent Tracks",
                description=f"{target_user.mention} hasn't scrobbled any tracks recently.",
                color=0xff0000
            )
            print(f"[DEBUG FM NP] <a:wrong:1436956421110632489> No valid data found")
            await ctx.send(embed=embed)
            return

        track = data['recenttracks']['track'][0] if isinstance(data['recenttracks']['track'], list) else data['recenttracks']['track']
        
        # Check if currently playing
        is_now_playing = '@attr' in track and 'nowplaying' in track['@attr']
        
        track_name = track['name']
        artist_name = self.safe_get_artist(track)
        album_name = self.safe_get_album(track)
        
        # Get comprehensive track info
        track_info = await self.get_lastfm_data(
            'track.getinfo',
            artist=artist_name,
            track=track_name,
            username=lastfm_username
        )
        
        # Get artist info for additional context
        artist_info = await self.get_lastfm_data(
            'artist.getinfo',
            artist=artist_name,
            username=lastfm_username
        )
        
        # Create simple, clean embed
        settings = self.get_guild_settings(ctx.guild.id)
        embed_color = int(settings['embed_color'].replace('#', ''), 16)
        
        embed = discord.Embed(color=embed_color)
        
        # Simple status indicator
        if is_now_playing:
            status = "<:music:1427471622335500439> Now Playing"
        else:
            status = "<:play:1428164853591441488> Last Played"
            
        # Clean, minimal description
        embed.description = f"**{status}**\n\n**{track_name}**\nby **{artist_name}**"
        
        # Add album only if it's meaningful
        if album_name and album_name != "Unknown Album" and album_name != artist_name:
            embed.description += f"\nfrom *{album_name}*"
        
        # Simple user info
        embed.set_author(
            name=target_user.display_name,
            icon_url=target_user.display_avatar.url,
            url=f"https://last.fm/user/{lastfm_username}"
        )
        
        # Get track info for image and basic stats
        track_info = await self.get_lastfm_data(
            'track.getinfo',
            artist=artist_name,
            track=track_name,
            username=lastfm_username
        )
        
        # Enhanced image search using our comprehensive method
        image_url, debug_images = await self.search_track_image(artist_name, track_name, album_name)
        
        # Additional fallback for recent tracks data if still no image
        if not image_url:
            debug_images.append("Final fallback - Recent tracks data:")
            
            # Try images from the recent tracks response
            if 'image' in track and isinstance(track['image'], list):
                for i, img in enumerate(reversed(track['image'])):  # Try largest first
                    url = img.get('#text', '').strip()
                    debug_images.append(f"    Recent image {i}: {url}")
                    if url and self._is_valid_image_url(url):
                        image_url = url
                        debug_images.append(f"    <a:yes:1431909187247673464> Using recent tracks image: {url}")
                        break
        
        # Log debug info
        print(f"[DEBUG FM NP] Enhanced image search for {track_name} by {artist_name}:")
        for debug_line in debug_images:
            print(f"[DEBUG FM NP] {debug_line}")
        print(f"[DEBUG FM NP] Final image_url: {image_url}")
        
        # Set the image if we found one
        if image_url:
            embed.set_thumbnail(url=image_url)
            print(f"[DEBUG FM NP] <a:yes:1431909187247673464> Set thumbnail: {image_url}")
        else:
            print(f"[DEBUG FM NP] <a:wrong:1436956421110632489> No image found")
        
        # Simple stats - just user plays if available
        if track_info and 'track' in track_info:
            track_data = track_info['track']
            if 'userplaycount' in track_data and int(track_data['userplaycount']) > 0:
                plays = int(track_data['userplaycount'])
                embed.add_field(
                    name="Your Plays",
                    value=f"{plays:,}",
                    inline=True
                )
        
        # Simple footer
        embed.set_footer(text="Last.fm")
        
        # Set timestamp with detailed logging
        if not is_now_playing and 'date' in track:
            try:
                uts_timestamp = int(track['date']['uts'])
                played_time = datetime.fromtimestamp(uts_timestamp)
                embed.timestamp = played_time
                print(f"[DEBUG FM NP] <a: Set timestamp from Last.fm: {played_time} (UTS: {uts_timestamp})")
            except Exception as e:
                embed.timestamp = datetime.now(timezone.utc)
                print(f"[DEBUG FM NP] <a:wrong:1436956421110632489> Failed to set Last.fm timestamp: {e}, using current time")
        else:
            embed.timestamp = datetime.now(timezone.utc)
            if is_now_playing:
                print(f"[DEBUG FM NP] 🎵 Now playing - using current timestamp: {embed.timestamp}")
            else:
                print(f"[DEBUG FM NP] ⚠️ No date in track data - using current timestamp: {embed.timestamp}")
        
        # Add debug info about track data
        print(f"[DEBUG FM NP] Track data keys: {list(track.keys())}")
        if 'date' in track:
            print(f"[DEBUG FM NP] Date info: {track['date']}")
        print(f"[DEBUG FM NP] Is now playing: {is_now_playing}")
        print(f"[DEBUG FM NP] Final timestamp set: {embed.timestamp}")
        
        # Check user's display mode preference (CV1 = embed, CV2 = Container)
        with sqlite3.connect('databases/lastfm.db') as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT display_mode FROM lastfm_user_customization WHERE user_id = ?", (target_user.id,))
            result = cursor.fetchone()
            display_mode = result[0] if result else 'cv2'
        
        # CV1 Mode: Traditional embed with album art
        if display_mode == 'cv1':
            # Send the embed we already built above
            message1 = await ctx.send(embed=embed)
        # CV2 Mode: Container with embed-like styling
        else:
            detailed_track_info = track_info.get('track') if track_info and 'track' in track_info else None
            cv2_layout = self.create_fm_cv2_panel(
                track_name, 
                artist_name, 
                album_name, 
                lastfm_username, 
                target_user, 
                track_info=detailed_track_info, 
                is_now_playing=is_now_playing,
                image_url=image_url,
                embed_color=settings['embed_color']  # Pass the customizable color
            )
            # Components v2 cannot have content, embeds, stickers, or polls
            message1 = await ctx.send(view=cv2_layout)
        
        # Add reactions
        try:
            await message1.add_reaction("👍")
            await asyncio.sleep(0.2)
            await message1.add_reaction("👎")
        except:
            pass

    @fm.command(name="whoknows", aliases=["wk"])
    async def fm_whoknows(self, ctx, *, artist_name: str):
        """Enhanced who knows with crown system"""
        # Get server prefix for accurate command examples
        prefix = (await self.bot.get_prefix(ctx.message))[0]
        
        if not ctx.guild:
            await ctx.send("<a:wrong:1436956421110632489> This command can only be used in servers.")
            return
            
        # Get all linked users in this guild
        try:
            with sqlite3.connect('databases/lastfm.db') as conn:
                cursor = conn.execute("""
                    SELECT u.user_id, u.lastfm_username 
                    FROM lastfm_users u
                    WHERE u.user_id IN ({})
                """.format(','.join('?' * len([m.id for m in ctx.guild.members]))),
                [m.id for m in ctx.guild.members])
                
                users = cursor.fetchall()
        except Exception as e:
            await ctx.send("<a:wrong:1436956421110632489> Database error occurred.")
            print(f"[LASTFM ERROR] Whoknows query failed: {e}")
            return
        
        if not users:
            embed = discord.Embed(
                title="<a:wrong:1436956421110632489> No Linked Users",
                description="No users in this server have linked their Last.fm accounts.",
                color=0xff0000
            )
            await ctx.send(embed=embed)
            return
        
        # Get artist plays for each user
        user_plays = []
        
        async def get_user_artist_plays(user_id, username):
            try:
                data = await self.get_lastfm_data(
                    'artist.getinfo',
                    artist=artist_name,
                    username=username
                )
                if data and 'artist' in data and 'userplaycount' in data['artist']:
                    plays = int(data['artist']['userplaycount'])
                    if plays > 0:
                        return (user_id, username, plays)
            except:
                pass
            return None
        
        # Gather data concurrently
        tasks = [get_user_artist_plays(user_id, username) for user_id, username in users]
        results = await asyncio.gather(*tasks)
        
        # Filter and sort results
        user_plays = [result for result in results if result is not None]
        user_plays.sort(key=lambda x: x[2], reverse=True)
        
        if not user_plays:
            embed = discord.Embed(
                title="<a:wrong:1436956421110632489> No Data Found",
                description=f"No one in this server has scrobbled **{artist_name}**.",
                color=0xff0000
            )
            await ctx.send(embed=embed)
            return
        
        # Check/update crown system
        settings = self.get_guild_settings(ctx.guild.id)
        crown_holder = None
        crown_changed = False
        
        if settings['crown_system'] and user_plays:
            top_user = user_plays[0]
            try:
                with sqlite3.connect('databases/lastfm.db') as conn:
                    # Check current crown holder
                    cursor = conn.execute("""
                        SELECT user_id, playcount FROM lastfm_crowns 
                        WHERE guild_id = ? AND artist_name = ?
                    """, (ctx.guild.id, artist_name.lower()))
                    
                    current_crown = cursor.fetchone()
                    
                    if not current_crown or current_crown[1] < top_user[2]:
                        # New crown or crown stolen
                        conn.execute("""
                            INSERT OR REPLACE INTO lastfm_crowns 
                            (guild_id, user_id, artist_name, playcount, claimed_at)
                            VALUES (?, ?, ?, ?, ?)
                        """, (ctx.guild.id, top_user[0], artist_name.lower(), top_user[2], datetime.now()))
                        
                        crown_holder = top_user[0]
                        crown_changed = current_crown is not None
            except Exception as e:
                print(f"[LASTFM ERROR] Crown update failed: {e}")
        
        # Create enhanced embed
        embed = discord.Embed(
            title=f"<a:crown:1437503143591153756> Who knows **{artist_name}**?",
            color=self.color
        )
        
        # Add crown information
        if crown_holder:
            crown_user = ctx.guild.get_member(crown_holder)
            if crown_user:
                crown_text = f"<a:crown:1437503143591153756> **{crown_user.display_name}** holds the crown!"
                if crown_changed:
                    crown_text += " *(Crown stolen!)*"
                embed.description = crown_text
        
        # Display top users (limit based on settings)
        limit = min(settings['whoknows_limit'], len(user_plays))
        
        description_parts = []
        for i, (user_id, username, plays) in enumerate(user_plays[:limit], 1):
            guild_user = ctx.guild.get_member(user_id)
            display_name = guild_user.display_name if guild_user else username
            
            # Add crown emoji for #1
            crown_emoji = "<a:crown:1437503143591153756> " if i == 1 and crown_holder else ""
            
            # Format plays nicely
            plays_formatted = f"{plays:,} plays"
            
            description_parts.append(f"**{i}.** {crown_emoji}**{display_name}** — {plays_formatted}")
        
        embed.add_field(
            name=f"📊 Top {limit} listeners in {ctx.guild.name}",
            value="\n".join(description_parts),
            inline=False
        )
        
        # Add total stats
        total_plays = sum(plays for _, _, plays in user_plays)
        total_listeners = len(user_plays)
        
        embed.add_field(
            name="<:stats:1437456326157668362> Server Stats",
            value=f"**Total plays:** {total_plays:,}\n**Listeners:** {total_listeners}/{len(ctx.guild.members)}",
            inline=True
        )
        
        # Get artist info for additional context
        artist_info = await self.get_lastfm_data('artist.getinfo', artist=artist_name)
        if artist_info and 'artist' in artist_info:
            artist_data = artist_info['artist']
            
            stats_text = []
            if 'playcount' in artist_data:
                stats_text.append(f"**Global plays:** {int(artist_data['playcount']):,}")
            if 'listeners' in artist_data:
                stats_text.append(f"**Global listeners:** {int(artist_data['listeners']):,}")
            
            if stats_text:
                embed.add_field(
                    name="<a:earth:1437493493332443136> Global Stats",
                    value="\n".join(stats_text),
                    inline=True
                )
            
            # Add artist image
            if 'image' in artist_data:
                for image in reversed(artist_data['image']):
                    if image.get('#text'):
                        embed.set_thumbnail(url=image['#text'])
                        break
        
        embed.set_footer(text=f"Use '{prefix}fm whoknowstrack' for track-specific data")
        await ctx.send(embed=embed)

    @fm.command(name="chart")
    async def fm_chart(self, ctx, period: str = "7day", size: int = 9, user: Optional[discord.Member] = None):
        """Generate visual album charts"""
        target_user = user or ctx.author
        lastfm_username = self.get_user_lastfm(target_user.id)
        
        if not lastfm_username:
            embed = discord.Embed(
                title="<a:wrong:1436956421110632489> No Account Linked",
                description=f"{'You need' if not user else f'{target_user.mention} needs'} to link a Last.fm account first.",
                color=0xff0000
            )
            await ctx.send(embed=embed)
            return
        
        # Validate period and size
        valid_periods = ["overall", "7day", "1month", "3month", "6month", "12month"]
        if period not in valid_periods:
            period = "7day"
        
        if size not in [4, 9, 16, 25]:
            size = 9
        
        # Get top albums
        data = await self.get_lastfm_data(
            'user.gettopalbums',
            user=lastfm_username,
            period=period,
            limit=size
        )
        
        if not data or (data and 'error' in data) or not data.get('topalbums', {}).get('album'):
            embed = discord.Embed(
                title="<a:wrong:1436956421110632489> No Album Data",
                description=f"No album data found for the {period} period.",
                color=0xff0000
            )
            await ctx.send(embed=embed)
            return
        
        albums = data['topalbums']['album']
        if not isinstance(albums, list):
            albums = [albums]
        
        # Create text-based chart
        embed = discord.Embed(
            title=f"📊 {target_user.display_name}'s Top {size} Albums",
            description=f"**Period:** {period.replace('day', ' day').replace('month', ' month').title()}",
            color=self.color
        )
        
        chart_text = []
        for i, album in enumerate(albums[:size], 1):
            album_name = album['name']
            artist_name = album['artist']['name']
            plays = album['playcount']
            
            # Truncate long names
            if len(album_name) > 25:
                album_name = album_name[:22] + "..."
            if len(artist_name) > 20:
                artist_name = artist_name[:17] + "..."
            
            chart_text.append(f"**{i}.** {album_name}\n*by {artist_name}*\n{plays} plays\n")
        
        # Split into columns for better display
        mid = len(chart_text) // 2
        left_column = "\n".join(chart_text[:mid])
        right_column = "\n".join(chart_text[mid:])
        
        if left_column:
            embed.add_field(name="📀 Albums 1-" + str(mid), value=left_column, inline=True)
        if right_column:
            embed.add_field(name="📀 Albums " + str(mid + 1) + f"-{len(chart_text)}", value=right_column, inline=True)
        
        embed.set_footer(text=f"Last.fm • {lastfm_username}")
        await ctx.send(embed=embed)

    @fm.command(name="topartists", aliases=["ta", "artists"])
    async def fm_topartists(self, ctx, period: str = "overall", limit: int = 10, user: Optional[discord.Member] = None):
        """
        🎤 Show top artists for a user
        
        **Periods:** overall, 7day, 1month, 3month, 6month, 12month
        **Usage:** `fm topartists [period] [limit] [user]`
        """
        try:
            # Get username
            target_user = user or ctx.author
            username = self.get_user_lastfm(target_user.id)
            if not username:
                return await ctx.send(f"<a:wrong:1436956421110632489> {target_user.display_name} hasn't linked their Last.fm account!")
            
            # Validate period
            valid_periods = ["overall", "7day", "1month", "3month", "6month", "12month"]
            if period not in valid_periods:
                return await ctx.send(f"<a:wrong:1436956421110632489> Invalid period! Use: {', '.join(valid_periods)}")
            
            # Limit validation
            limit = max(1, min(limit, 50))
            
            # Get top artists
            data = await self.get_lastfm_data('user.gettopartists', user=username, period=period, limit=limit)
            
            if not data:
                return await ctx.send("<a:wrong:1436956421110632489> Failed to fetch data from Last.fm")
            
            if 'error' in data:
                return await ctx.send(f"<a:wrong:1436956421110632489> Last.fm error: {data['message']}")
            
            artists = data.get('topartists', {}).get('artist', [])
            if not artists:
                return await ctx.send(f"<a:wrong:1436956421110632489> No artists found for {target_user.display_name}")
            
            # Create embed
            period_name = period.replace('day', ' day').replace('month', ' month') if period != 'overall' else 'Overall'
            embed = discord.Embed(
                title=f"<a:sound:1437493915677626388> Top Artists ({period_name})",
                description=f"**{target_user.display_name}**'s most played artists",
                color=self.color
            )
            
            # Add artists
            artist_list = []
            for i, artist in enumerate(artists[:limit], 1):
                name = artist['name']
                plays = int(artist['playcount'])
                artist_list.append(f"`{i:02d}.` **{name}** — {plays:,} plays")
            
            embed.add_field(name="Artists", value="\n".join(artist_list), inline=False)
            embed.set_footer(text=f"Total: {data['topartists']['@attr']['total']} artists")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"<a:wrong:1436956421110632489> Error fetching top artists: {str(e)}")

    @fm.command(name="topalbums", aliases=["tab", "albums"])
    async def fm_topalbums(self, ctx, period: str = "overall", limit: int = 10, user: Optional[discord.Member] = None):
        """
         Show top albums for a user
        
        **Periods:** overall, 7day, 1month, 3month, 6month, 12month
        **Usage:** `fm topalbums [period] [limit] [user]`
        """
        try:
            # Get username
            target_user = user or ctx.author
            username = self.get_user_lastfm(target_user.id)
            if not username:
                return await ctx.send(f"<a:wrong:1436956421110632489> {target_user.display_name} hasn't linked their Last.fm account!")
            
            # Validate period
            valid_periods = ["overall", "7day", "1month", "3month", "6month", "12month"]
            if period not in valid_periods:
                return await ctx.send(f"<a:wrong:1436956421110632489> Invalid period! Use: {', '.join(valid_periods)}")
            
            # Limit validation
            limit = max(1, min(limit, 50))
            
            # Get top albums
            data = await self.get_lastfm_data('user.gettopalbums', user=username, period=period, limit=limit)
            
            if not data:
                return await ctx.send("<a:wrong:1436956421110632489> Failed to fetch data from Last.fm")
            
            if 'error' in data:
                return await ctx.send(f"<a:wrong:1436956421110632489> Last.fm error: {data['message']}")
            
            albums = data.get('topalbums', {}).get('album', [])
            if not albums:
                return await ctx.send(f"<a:wrong:1436956421110632489> No albums found for {target_user.display_name}")
            
            # Create embed
            period_name = period.replace('day', ' day').replace('month', ' month') if period != 'overall' else 'Overall'
            embed = discord.Embed(
                title=f"<a:vinyl:1437493964855836672> Top Albums ({period_name})",
                description=f"**{target_user.display_name}**'s most played albums",
                color=self.color
            )
            
            # Add albums
            album_list = []
            for i, album in enumerate(albums[:limit], 1):
                name = album['name']
                artist = album['artist']['name']
                plays = int(album['playcount'])
                album_list.append(f"`{i:02d}.` **{name}** by {artist} — {plays:,} plays")
            
            embed.add_field(name="Albums", value="\n".join(album_list), inline=False)
            embed.set_footer(text=f"Total: {data['topalbums']['@attr']['total']} albums")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"<a:wrong:1436956421110632489> Error fetching top albums: {str(e)}")

    @fm.command(name="toptracks", aliases=["tt", "tracks"])
    async def fm_toptracks(self, ctx, period: str = "overall", limit: int = 10, user: Optional[discord.Member] = None):
        """
         Show top tracks for a user
        
        **Periods:** overall, 7day, 1month, 3month, 6month, 12month
        **Usage:** `fm toptracks [period] [limit] [user]`
        """
        try:
            # Get username
            target_user = user or ctx.author
            username = self.get_user_lastfm(target_user.id)
            if not username:
                return await ctx.send(f"<a:wrong:1436956421110632489> {target_user.display_name} hasn't linked their Last.fm account!")
            
            # Validate period
            valid_periods = ["overall", "7day", "1month", "3month", "6month", "12month"]
            if period not in valid_periods:
                return await ctx.send(f"<a:wrong:1436956421110632489> Invalid period! Use: {', '.join(valid_periods)}")
            
            # Limit validation
            limit = max(1, min(limit, 50))
            
            # Get top tracks
            data = await self.get_lastfm_data('user.gettoptracks', user=username, period=period, limit=limit)
            
            if not data:
                return await ctx.send("<a:wrong:1436956421110632489> Failed to fetch data from Last.fm")
            
            if 'error' in data:
                return await ctx.send(f"<a:wrong:1436956421110632489> Last.fm error: {data['message']}")
            
            tracks = data.get('toptracks', {}).get('track', [])
            if not tracks:
                return await ctx.send(f"<a:wrong:1436956421110632489> No tracks found for {target_user.display_name}")
            
            # Create embed
            period_name = period.replace('day', ' day').replace('month', ' month') if period != 'overall' else 'Overall'
            embed = discord.Embed(
                title=f"<:speaker:1428183066311921804> Top Tracks ({period_name})",
                description=f"**{target_user.display_name}**'s most played tracks",
                color=self.color
            )
            
            # Add tracks
            track_list = []
            for i, track in enumerate(tracks[:limit], 1):
                name = track['name']
                artist = track['artist']['name']
                plays = int(track['playcount'])
                track_list.append(f"`{i:02d}.` **{name}** by {artist} — {plays:,} plays")
            
            embed.add_field(name="Tracks", value="\n".join(track_list), inline=False)
            embed.set_footer(text=f"Total: {data['toptracks']['@attr']['total']} tracks")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"<a:wrong:1436956421110632489> Error fetching top tracks: {str(e)}")

    @fm.command(name="recent", aliases=["recents", "rc"])
    async def fm_recent(self, ctx, user: Optional[discord.Member] = None, limit: int = 10):
        """
        ⏰ Show recent tracks for a user
        
        **Usage:** `fm recent [user] [limit]`
        """
        try:
            # Get username
            target_user = user or ctx.author
            username = self.get_user_lastfm(target_user.id)
            if not username:
                return await ctx.send(f"<a:wrong:1436956421110632489> {target_user.display_name} hasn't linked their Last.fm account!")
            
            # Limit validation
            limit = max(1, min(limit, 50))
            
            # Get recent tracks
            data = await self.get_lastfm_data('user.getrecenttracks', user=username, limit=limit)
            
            if not data:
                return await ctx.send("<a:wrong:1436956421110632489> Failed to fetch data from Last.fm")
            
            if 'error' in data:
                return await ctx.send(f"<a:wrong:1436956421110632489> Last.fm error: {data['message']}")
            
            tracks = data.get('recenttracks', {}).get('track', [])
            if not tracks:
                return await ctx.send(f"<a:wrong:1436956421110632489> No recent tracks found for {target_user.display_name}")
            
            # Create embed
            embed = discord.Embed(
                title=f"<a:clock:1436953635731800178> Recent Tracks",
                description=f"**{target_user.display_name}**'s recent listening history",
                color=self.color
            )
            
            # Add tracks
            track_list = []
            for i, track in enumerate(tracks[:limit], 1):
                name = track['name']
                artist = self.safe_get_artist(track)
                
                # Check if currently playing
                if '@attr' in track and 'nowplaying' in track['@attr']:
                    status = "<:speaker:1428183066311921804> Now Playing"
                else:
                    # Format timestamp
                    if 'date' in track:
                        timestamp = int(track['date']['uts'])
                        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                        status = f"<t:{timestamp}:R>"
                    else:
                        status = "Recently"
                
                track_list.append(f"`{i:02d}.` **{name}** by {artist}\n     {status}")
            
            embed.add_field(name="Tracks", value="\n".join(track_list), inline=False)
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"<a:wrong:1436956421110632489> Error fetching recent tracks: {str(e)}")

    @fm.command(name="artist", aliases=["a"])
    async def fm_artist(self, ctx, *, artist_name: str):
        """
        🎤 Get detailed artist information
        
        **Usage:** `fm artist <artist name>`
        """
        try:
            # Get artist info
            data = await self.get_lastfm_data('artist.getinfo', artist=artist_name)
            
            if not data:
                return await ctx.send("<a:wrong:1436956421110632489> Failed to fetch data from Last.fm")
            
            if 'error' in data:
                return await ctx.send(f"<a:wrong:1436956421110632489> Artist not found: {artist_name}")
            
            artist = data.get('artist', {})
            
            # Create embed
            embed = discord.Embed(
                title=f"<a:sound:1437493915677626388> {artist['name']}",
                color=self.color
            )
            
            # Add description if available
            if 'bio' in artist and artist['bio'].get('summary'):
                bio = artist['bio']['summary']
                # Clean up the bio text
                bio = re.sub(r'<[^>]+>', '', bio)  # Remove HTML tags
                bio = bio.replace(' Read more on Last.fm', '').strip()
                if len(bio) > 500:
                    bio = bio[:500] + "..."
                embed.description = bio
            
            # Add stats
            stats = []
            if 'stats' in artist:
                stats.append(f"**Listeners:** {int(artist['stats']['listeners']):,}")
                stats.append(f"**Total Plays:** {int(artist['stats']['playcount']):,}")
            
            if stats:
                embed.add_field(name="Statistics", value="\n".join(stats), inline=True)
            
            # Add tags
            if 'tags' in artist and artist['tags'].get('tag'):
                tags = artist['tags']['tag']
                if isinstance(tags, list):
                    tag_names = [tag['name'] for tag in tags[:5]]
                else:
                    tag_names = [tags['name']]
                embed.add_field(name="Tags", value=", ".join(tag_names), inline=True)
            
            # Add similar artists
            similar_data = await self.get_lastfm_data('artist.getsimilar', artist=artist_name, limit=5)
            if similar_data and 'similarartists' in similar_data and similar_data['similarartists'].get('artist'):
                similar = similar_data['similarartists']['artist']
                if isinstance(similar, list):
                    similar_names = [s['name'] for s in similar]
                else:
                    similar_names = [similar['name']]
                embed.add_field(name="Similar Artists", value=", ".join(similar_names), inline=False)
            
            # Add image if available
            if 'image' in artist and artist['image']:
                for img in artist['image']:
                    if img['size'] == 'large' and img.get('#text'):
                        embed.set_thumbnail(url=img['#text'])
                        break
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"<a:wrong:1436956421110632489> Error fetching artist info: {str(e)}")

    @fm.command(name="album", aliases=["ab"])
    async def fm_album(self, ctx, artist_name: str, *, album_name: str):
        """
         Get detailed album information
        
        **Usage:** `fm album <artist> <album name>`
        """
        try:
            # Get album info
            data = await self.get_lastfm_data('album.getinfo', artist=artist_name, album=album_name)
            
            if not data:
                return await ctx.send("<a:wrong:1436956421110632489> Failed to fetch data from Last.fm")
            
            if 'error' in data:
                return await ctx.send(f"<a:wrong:1436956421110632489> Album not found: {album_name} by {artist_name}")
            
            album = data.get('album', {})
            
            # Create embed
            embed = discord.Embed(
                title=f"<a:vinyl:1437493964855836672> {album['name']}",
                description=f"by **{album['artist']}**",
                color=self.color
            )
            
            # Add album description if available
            if 'wiki' in album and album['wiki'].get('summary'):
                bio = album['wiki']['summary']
                # Clean up the bio text
                bio = re.sub(r'<[^>]+>', '', bio)  # Remove HTML tags
                bio = bio.replace(' Read more on Last.fm', '').strip()
                if len(bio) > 400:
                    bio = bio[:400] + "..."
                embed.add_field(name="About", value=bio, inline=False)
            
            # Add stats
            stats = []
            if 'listeners' in album:
                stats.append(f"**Listeners:** {int(album['listeners']):,}")
            if 'playcount' in album:
                stats.append(f"**Total Plays:** {int(album['playcount']):,}")
            
            if stats:
                embed.add_field(name="Statistics", value="\n".join(stats), inline=True)
            
            # Add tags
            if 'tags' in album and album['tags'].get('tag'):
                tags = album['tags']['tag']
                if isinstance(tags, list):
                    tag_names = [tag['name'] for tag in tags[:5]]
                else:
                    tag_names = [tags['name']]
                embed.add_field(name="Tags", value=", ".join(tag_names), inline=True)
            
            # Add tracks if available
            if 'tracks' in album and album['tracks'].get('track'):
                tracks = album['tracks']['track']
                if isinstance(tracks, list):
                    track_list = []
                    for i, track in enumerate(tracks[:10], 1):
                        duration = ""
                        if 'duration' in track and track['duration']:
                            mins, secs = divmod(int(track['duration']), 60)
                            duration = f" ({mins}:{secs:02d})"
                        track_list.append(f"`{i:02d}.` {track['name']}{duration}")
                    
                    embed.add_field(
                        name=f"Tracks ({len(tracks)} total)", 
                        value="\n".join(track_list[:10]), 
                        inline=False
                    )
            
            # Add image if available
            if 'image' in album and album['image']:
                for img in album['image']:
                    if img['size'] == 'large' and img.get('#text'):
                        embed.set_thumbnail(url=img['#text'])
                        break
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"<a:wrong:1436956421110632489> Error fetching album info: {str(e)}")

    @fm.command(name="track", aliases=["t"])
    async def fm_track(self, ctx, artist_name: str, *, track_name: str):
        """
         Get detailed track information
        
        **Usage:** `fm track <artist> <track name>`
        """
        try:
            # Get track info
            data = await self.get_lastfm_data('track.getinfo', artist=artist_name, track=track_name)
            
            if not data:
                return await ctx.send("<a:wrong:1436956421110632489> Failed to fetch data from Last.fm")
            
            if 'error' in data:
                return await ctx.send(f"<a:wrong:1436956421110632489> Track not found: {track_name} by {artist_name}")
            
            track = data.get('track', {})
            
            # Create embed
            embed = discord.Embed(
                title=f"<:speaker:1428183066311921804> {track['name']}",
                description=f"by **{track['artist']['name']}**",
                color=self.color
            )
            
            # Add album info if available
            if 'album' in track and track['album'].get('title'):
                if embed.description:
                    embed.description += f"\nfrom **{track['album']['title']}**"
                else:
                    embed.description = f"from **{track['album']['title']}**"
            
            # Add track description if available
            if 'wiki' in track and track['wiki'].get('summary'):
                bio = track['wiki']['summary']
                # Clean up the bio text
                bio = re.sub(r'<[^>]+>', '', bio)  # Remove HTML tags
                bio = bio.replace(' Read more on Last.fm', '').strip()
                if len(bio) > 400:
                    bio = bio[:400] + "..."
                embed.add_field(name="About", value=bio, inline=False)
            
            # Add stats
            stats = []
            if 'listeners' in track:
                stats.append(f"**Listeners:** {int(track['listeners']):,}")
            if 'playcount' in track:
                stats.append(f"**Total Plays:** {int(track['playcount']):,}")
            if 'duration' in track and track['duration']:
                mins, secs = divmod(int(track['duration']) // 1000, 60)
                stats.append(f"**Duration:** {mins}:{secs:02d}")
            
            if stats:
                embed.add_field(name="Statistics", value="\n".join(stats), inline=True)
            
            # Add tags
            if 'toptags' in track and track['toptags'].get('tag'):
                tags = track['toptags']['tag']
                if isinstance(tags, list):
                    tag_names = [tag['name'] for tag in tags[:5]]
                else:
                    tag_names = [tags['name']]
                embed.add_field(name="Tags", value=", ".join(tag_names), inline=True)
            
            # Add image if available
            if 'album' in track and 'image' in track['album'] and track['album']['image']:
                for img in track['album']['image']:
                    if img['size'] == 'large' and img.get('#text'):
                        embed.set_thumbnail(url=img['#text'])
                        break
            
            # Add search view
            view = EnhancedMusicSearchView(track['name'], self.safe_get_artist(track))
            await ctx.send(embed=embed, view=view)
            
        except Exception as e:
            await ctx.send(f"<a:wrong:1436956421110632489> Error fetching track info: {str(e)}")

    @fm.command(name="profile", aliases=["p", "user"])
    async def fm_profile(self, ctx, user: Optional[discord.Member] = None):
        """
        👤 Show Last.fm profile for a user
        
        **Usage:** `fm profile [user]`
        """
        try:
            # Get username
            target_user = user or ctx.author
            username = self.get_user_lastfm(target_user.id)
            if not username:
                return await ctx.send(f"<a:wrong:1436956421110632489> {target_user.display_name} hasn't linked their Last.fm account!")
            
            # Get user info
            data = await self.get_lastfm_data('user.getinfo', user=username)
            
            if not data:
                return await ctx.send("<a:wrong:1436956421110632489> Failed to fetch data from Last.fm")
            
            if 'error' in data:
                return await ctx.send(f"<a:wrong:1436956421110632489> Error fetching profile for {username}")
            
            profile = data.get('user', {})
            
            # Create embed
            embed = discord.Embed(
                title=f"👤 {profile['name']}'s Last.fm Profile",
                color=self.color,
                url=profile.get('url', f"https://last.fm/user/{username}")
            )
            
            # Add basic info
            info = []
            if 'realname' in profile and profile['realname']:
                info.append(f"**Real Name:** {profile['realname']}")
            if 'age' in profile and profile['age'] and profile['age'] != '0':
                info.append(f"**Age:** {profile['age']}")
            if 'country' in profile and profile['country']:
                info.append(f"**Country:** {profile['country']}")
            if 'registered' in profile and 'unixtime' in profile['registered']:
                timestamp = int(profile['registered']['unixtime'])
                info.append(f"**Joined:** <t:{timestamp}:D> (<t:{timestamp}:R>)")
            
            if info:
                embed.add_field(name="Profile Info", value="\n".join(info), inline=True)
            
            # Add stats
            stats = []
            if 'playcount' in profile:
                stats.append(f"**Total Scrobbles:** {int(profile['playcount']):,}")
            if 'artist_count' in profile:
                stats.append(f"**Artists:** {int(profile['artist_count']):,}")
            if 'track_count' in profile:
                stats.append(f"**Tracks:** {int(profile['track_count']):,}")
            if 'album_count' in profile:
                stats.append(f"**Albums:** {int(profile['album_count']):,}")
            
            if stats:
                embed.add_field(name="Statistics", value="\n".join(stats), inline=True)
            
            # Add image if available
            if 'image' in profile and profile['image']:
                for img in profile['image']:
                    if img['size'] == 'large' and img.get('#text'):
                        embed.set_thumbnail(url=img['#text'])
                        break
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"<a:wrong:1436956421110632489> Error fetching profile: {str(e)}")

    @fm.command(name="compare", aliases=["c"])
    async def fm_compare(self, ctx, user1: Optional[discord.Member] = None, user2: Optional[discord.Member] = None):
        """
        🤝 Compare music taste between two users
        
        **Usage:** `fm compare [user1] [user2]`
        """
        try:
            # Default to author if no users specified
            if not user1:
                user1 = ctx.author
            if not user2:
                return await ctx.send("<a:wrong:1436956421110632489> Please specify a user to compare with!")
            
            # Type assertion for safety
            assert user1 is not None and user2 is not None
            
            # Get usernames
            username1 = self.get_user_lastfm(user1.id)
            username2 = self.get_user_lastfm(user2.id)
            
            if not username1:
                return await ctx.send(f"<a:wrong:1436956421110632489> {user1.display_name} hasn't linked their Last.fm account!")
            if not username2:
                return await ctx.send(f"<a:wrong:1436956421110632489> {user2.display_name} hasn't linked their Last.fm account!")
            
            # Get top artists for both users
            data1 = await self.get_lastfm_data('user.gettopartists', user=username1, period='overall', limit=100)
            data2 = await self.get_lastfm_data('user.gettopartists', user=username2, period='overall', limit=100)
            
            if not data1 or not data2:
                return await ctx.send("<a:wrong:1436956421110632489> Failed to fetch data from Last.fm")
            
            if 'error' in data1 or 'error' in data2:
                return await ctx.send("<a:wrong:1436956421110632489> Error fetching user data for comparison")
            
            # Extract artist names and play counts
            artists1 = {}
            for artist in data1.get('topartists', {}).get('artist', []):
                artists1[artist['name'].lower()] = int(artist['playcount'])
            
            artists2 = {}
            for artist in data2.get('topartists', {}).get('artist', []):
                artists2[artist['name'].lower()] = int(artist['playcount'])
            
            # Find common artists
            common_artists = set(artists1.keys()) & set(artists2.keys())
            
            if not common_artists:
                embed = discord.Embed(
                    title="<a:alone:1437495902867558533> Music Compatibility",
                    description=f"**{user1.display_name}** and **{user2.display_name}** have no artists in common!",
                    color=self.color
                )
                return await ctx.send(embed=embed)
            
            # Calculate compatibility score
            total_artists1 = len(artists1)
            total_artists2 = len(artists2)
            compatibility = len(common_artists) / max(total_artists1, total_artists2) * 100
            
            # Create embed
            embed = discord.Embed(
                title="<a:alone:1437495902867558533> Music Compatibility",
                description=f"**{user1.display_name}** vs **{user2.display_name}**",
                color=self.color
            )
            
            # Add compatibility score
            if compatibility >= 80:
                compat_emoji = "💖"
                compat_text = "Soulmates!"
            elif compatibility >= 60:
                compat_emoji = "❤️"
                compat_text = "Very Compatible"
            elif compatibility >= 40:
                compat_emoji = "💛"
                compat_text = "Good Match"
            elif compatibility >= 20:
                compat_emoji = "🧡"
                compat_text = "Some Common Ground"
            else:
                compat_emoji = "💔"
                compat_text = "Very Different"
            
            embed.add_field(
                name=f"{compat_emoji} Compatibility Score",
                value=f"**{compatibility:.1f}%** - {compat_text}",
                inline=False
            )
            
            # Add shared artists
            shared_list = []
            sorted_common = sorted(common_artists, key=lambda x: artists1[x] + artists2[x], reverse=True)
            
            for i, artist in enumerate(sorted_common[:10], 1):
                plays1 = artists1[artist]
                plays2 = artists2[artist]
                shared_list.append(f"`{i:02d}.` {artist.title()} ({plays1} + {plays2} plays)")
            
            embed.add_field(
                name=f"<:speaker:1428183066311921804> Shared Artists ({len(common_artists)} total)",
                value="\n".join(shared_list),
                inline=False
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"<a:wrong:1436956421110632489> Error comparing users: {str(e)}")

    @fm.command(name="privacy")
    async def fm_privacy(self, ctx):
        """Configure your Last.fm privacy settings"""
        # Get server prefix for accurate command examples
        prefix = (await self.bot.get_prefix(ctx.message))[0]
        
        embed = discord.Embed(
            title="<a:lock:1437496504955699402> Last.fm Privacy Settings",
            description="Configure your privacy preferences for Last.fm commands",
            color=self.color
        )
        
        # Get current settings
        user_id = ctx.author.id
        try:
            with sqlite3.connect('databases/lastfm.db') as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT privacy_level FROM lastfm_users WHERE user_id = ?", (user_id,))
                result = cursor.fetchone()
                
            current_privacy = result[0] if result else 0
            
            privacy_levels = {
                0: "<a:earth:1437493493332443136> **Public** - Anyone can see your stats",
                1: "<:ppl:1427471598578958386> **Friends** - Only friends can see detailed stats", 
                2: "<a:lock:1437496504955699402> **Private** - Minimal public information"
            }
            
            embed.add_field(
                name="Current Setting",
                value=privacy_levels.get(current_privacy, privacy_levels[0]),
                inline=False
            )
            
            embed.add_field(
                name="Available Options",
                value="\n".join([f"{level}: {desc}" for level, desc in privacy_levels.items()]),
                inline=False
            )
            
            embed.add_field(
                name="How to Change",
                value=f"Use `{prefix}fm privacy set <0/1/2>` to change your privacy level",
                inline=False
            )
            
        except Exception as e:
            embed.add_field(name="Error", value=f"Could not load privacy settings: {str(e)}", inline=False)
            
        await ctx.send(embed=embed)

    @fm.command(name="loved")
    async def fm_loved(self, ctx, user: Optional[discord.Member] = None):
        """Show your loved tracks from Last.fm"""
        target_user = user or ctx.author
        username = self.get_user_lastfm(target_user.id)
        
        if not username:
            return await ctx.send(f"<a:wrong:1436956421110632489> {target_user.display_name} hasn't linked their Last.fm account!")
        
        try:
            data = await self.get_lastfm_data('user.getlovedtracks', user=username, limit=10)
            
            if not data or 'error' in data:
                return await ctx.send(f"<a:wrong:1436956421110632489> Could not fetch loved tracks for {username}")
            
            tracks = data.get('lovedtracks', {}).get('track', [])
            if not tracks:
                return await ctx.send(f"<a:wrong:1436956421110632489> {target_user.display_name} has no loved tracks")
            
            embed = discord.Embed(
                title=f"<a:heart:1437811689675558966> {target_user.display_name}'s Loved Tracks",
                color=self.color,
                url=f"https://last.fm/user/{username}/loved"
            )
            
            track_list = []
            for i, track in enumerate(tracks[:10], 1):
                name = track['name']
                artist = self.safe_get_artist(track)
                track_list.append(f"{i}. **{name}** by {artist}")
            
            embed.description = "\n".join(track_list)
            
            total = data.get('lovedtracks', {}).get('@attr', {}).get('total', 0)
            embed.set_footer(text=f"Total loved tracks: {total}")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"<a:wrong:1436956421110632489> Error fetching loved tracks: {str(e)}")

    @fm.command(name="crowns")
    async def fm_crowns(self, ctx, user: Optional[discord.Member] = None):
        """Show artist crowns for a user in this server"""
        target_user = user or ctx.author
        username = self.get_user_lastfm(target_user.id)
        
        if not username:
            return await ctx.send(f"<a:wrong:1436956421110632489> {target_user.display_name} hasn't linked their Last.fm account!")
        
        try:
            # Get user's top artists
            data = await self.get_lastfm_data('user.gettopartists', user=username, period='overall', limit=50)
            
            if not data or 'error' in data:
                return await ctx.send(f"<a:wrong:1436956421110632489> Could not fetch artist data for {username}")
            
            artists = data.get('topartists', {}).get('artist', [])
            if not artists:
                return await ctx.send(f"<a:wrong:1436956421110632489> {target_user.display_name} has no scrobbled artists")
            
            embed = discord.Embed(
                title=f"<a:crown:1437503143591153756> {target_user.display_name}'s Artist Crowns",
                description="Your top artists in this server",
                color=self.color
            )
            
            # For now, show top artists (real crown logic would require tracking all server members)
            crown_list = []
            for i, artist in enumerate(artists[:10], 1):
                name = artist['name']
                plays = int(artist['playcount'])
                crown_list.append(f"{i}. **{name}** - {plays:,} plays")
            
            embed.add_field(
                name="Top Artists",
                value="\n".join(crown_list),
                inline=False
            )
            
            embed.set_footer(text="Crown system tracks who has the most plays for each artist in the server")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"<a:wrong:1436956421110632489> Error fetching crowns: {str(e)}")

    @fm.command(name="customize")
    async def fm_customize(self, ctx):
        """Customize your Last.fm display and preferences"""
        
        try:
            # Get server prefix for accurate command examples
            prefix = (await self.bot.get_prefix(ctx.message))[0]
            
            # Get current user settings
            user_id = ctx.author.id
            username = self.get_user_lastfm(user_id)
            
            if not username:
                content = "<a:wrong:1436956421110632489> **No Last.fm Account Linked**\n\n"
                content += "You need to link your Last.fm account first!\n"
                content += f"Use `{prefix}fm set <username>` to get started."
                return await ctx.send(content=content)
            
            with sqlite3.connect('databases/lastfm.db') as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT auto_showcase, crown_optout, reaction_notifications, timezone, profile_description
                    FROM lastfm_users WHERE user_id = ?
                """, (user_id,))
                result = cursor.fetchone()
                
            # Get user's personal settings from database
            with sqlite3.connect('databases/lastfm.db') as conn:
                cursor = conn.cursor()
                # Check if user has personal customization table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS lastfm_user_customization (
                        user_id INTEGER PRIMARY KEY,
                        display_mode TEXT DEFAULT 'cv2',  -- 'embed' or 'cv2'
                        custom_reactions TEXT,  -- JSON array of custom emojis
                        embed_color TEXT DEFAULT '#006fb9',
                        show_playcount BOOLEAN DEFAULT 1,
                        show_album_art BOOLEAN DEFAULT 1,
                        show_scrobbles BOOLEAN DEFAULT 1,
                        auto_react BOOLEAN DEFAULT 1,
                        custom_format TEXT,  -- Custom message format
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                cursor.execute("SELECT * FROM lastfm_user_customization WHERE user_id = ?", (user_id,))
                custom_settings = cursor.fetchone()
                
            # Get guild settings for fallback
            guild_settings = self.get_guild_settings(ctx.guild.id) if ctx.guild else self.get_default_settings()
            
            # Clean, concise customization interface
            content = f"<a:gear:1430203750324240516> **Last.fm Customization**\n"
            content += f"{'─' * 50}\n\n"
            
            if result:
                auto_showcase, crown_optout, reactions, timezone, description = result
                display_mode = custom_settings[1] if custom_settings else 'cv2'
                
                # Mode switcher section
                if display_mode == 'cv2':
                    content += f"**[CV1]** Switch to **Embed** (includes album art)\n"
                else:
                    content += f"**[CV2]** Switch to **Components v2** (interactive buttons)\n"
                content += f"{'─' * 50}\n\n"
                
                # Current settings status
                content += f"**Current Settings**\n"
                content += f"<:bot:1428163130663375029> **Mode:** {'Components v2' if display_mode == 'cv2' else 'Embed'}\n"
                
                if custom_settings and custom_settings[2]:
                    import json
                    try:
                        custom_reactions = json.loads(custom_settings[2])
                        content += f"<a:mark:1436953593923244113> **Reactions:** {' '.join(custom_reactions[:5])}{'...' if len(custom_reactions) > 5 else ''}\n"
                    except:
                        content += f"<a:mark:1436953593923244113> **Reactions:** Default\n"
                else:
                    content += f"<a:mark:1436953593923244113> **Reactions:** Default\n"
                
                color = custom_settings[3] if custom_settings else guild_settings['embed_color']
                content += f"<:flag:1427471551200100403> **Theme:** {color}\n"
                
                # Accurate status indicators - show what's actually enabled
                show_playcount = custom_settings[4] if custom_settings else guild_settings['show_playcount']
                show_album_art = custom_settings[5] if custom_settings else guild_settings['show_album_art']
                show_scrobbles = custom_settings[6] if custom_settings else guild_settings['show_scrobbles']
                auto_react = custom_settings[7] if custom_settings else guild_settings['auto_react']
                
                active_features = []
                if show_playcount: active_features.append("Play Counts")
                if show_album_art: active_features.append("Album Art")
                if show_scrobbles: active_features.append("Scrobbles")
                if auto_react: active_features.append("Auto React")
                if auto_showcase: active_features.append("Auto Showcase")
                if not crown_optout: active_features.append("Crown System")
                if reactions: active_features.append("Notifications")
                
                content += f"\n**Active Features:** {', '.join(active_features) if active_features else 'Basic setup'}"
            else:
                content += f"Link your account with `{prefix}fm set <username>` to customize!"
            
            # Complete customization buttons with custom emojis
            class CustomizeView(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=300)
                    
                    # Row 0: Mode switcher (full width)
                    mode_label = "Switch to Embed" if display_mode == 'cv2' else "Switch to CV2"
                    mode_emoji = "<:bot:1428163130663375029>"
                    self.add_item(discord.ui.Button(
                        label=mode_label,
                        emoji=mode_emoji,
                        style=discord.ButtonStyle.success,
                        custom_id=f"fm_toggle_mode_{user_id}",
                        row=0
                    ))
                    
                    # Row 1: Core customization
                    self.add_item(discord.ui.Button(
                        label="Custom Reactions", 
                        emoji="<a:mark:1436953593923244113>", 
                        style=discord.ButtonStyle.primary, 
                        custom_id=f"fm_customize_reactions_{user_id}",
                        row=1
                    ))
                    
                    self.add_item(discord.ui.Button(
                        label="Theme Colors", 
                        emoji="<:flag:1427471551200100403>", 
                        style=discord.ButtonStyle.primary, 
                        custom_id=f"fm_customize_colors_{user_id}",
                        row=1
                    ))
                    
                    self.add_item(discord.ui.Button(
                        label="Display Mode", 
                        emoji="<:bot:1428163130663375029>", 
                        style=discord.ButtonStyle.primary, 
                        custom_id=f"fm_customize_display_{user_id}",
                        row=1
                    ))
                    
                    # Row 2: Feature toggles
                    self.add_item(discord.ui.Button(
                        label="Auto Features", 
                        emoji="<:like:1428199620554657842>", 
                        style=discord.ButtonStyle.secondary, 
                        custom_id=f"fm_customize_auto_{user_id}",
                        row=2
                    ))
                    
                    self.add_item(discord.ui.Button(
                        label="Crown System", 
                        emoji="<a:crown:1437503143591153756>", 
                        style=discord.ButtonStyle.secondary, 
                        custom_id=f"fm_customize_crowns_{user_id}",
                        row=2
                    ))
                    
                    self.add_item(discord.ui.Button(
                        label="Privacy & Alerts", 
                        emoji="<a:timer:1430203704048484395>", 
                        style=discord.ButtonStyle.secondary, 
                        custom_id=f"fm_customize_notifications_{user_id}",
                        row=2
                    ))
            
            customize_view = CustomizeView()
            await ctx.send(content=content, view=customize_view)
            
        except Exception as e:
            content = f"<a:wrong:1436956421110632489> **Error Loading Settings**\n\n"
            content += f"Could not load settings: {str(e)}"
            await ctx.send(content=content)

    @fm.command(name="stats")
    async def fm_stats(self, ctx, user: Optional[discord.Member] = None, period: str = "overall"):
        """Show comprehensive Last.fm statistics"""
        target_user = user or ctx.author
        username = self.get_user_lastfm(target_user.id)
        
        if not username:
            return await ctx.send(f"<a:wrong:1436956421110632489> {target_user.display_name} hasn't linked their Last.fm account!")
        
        valid_periods = ["overall", "7day", "1month", "3month", "6month", "12month"]
        if period not in valid_periods:
            return await ctx.send(f"<a:wrong:1436956421110632489> Invalid period. Use: {', '.join(valid_periods)}")
        
        try:
            # Get user info and top data
            user_data = await self.get_lastfm_data('user.getinfo', user=username)
            top_artists = await self.get_lastfm_data('user.gettopartists', user=username, period=period, limit=5)
            top_albums = await self.get_lastfm_data('user.gettopalbums', user=username, period=period, limit=5)
            top_tracks = await self.get_lastfm_data('user.gettoptracks', user=username, period=period, limit=5)
            
            if not user_data or 'error' in user_data:
                return await ctx.send(f"<a:wrong:1436956421110632489> Could not fetch user data for {username}")
            
            profile = user_data.get('user', {})
            
            embed = discord.Embed(
                title=f"📊 {target_user.display_name}'s Last.fm Stats",
                description=f"Statistics for {period}",
                color=self.color,
                url=f"https://last.fm/user/{username}"
            )
            
            # Overall stats
            if period == "overall":
                stats = []
                stats.append(f"**Total Scrobbles:** {int(profile.get('playcount', 0)):,}")
                stats.append(f"**Artists:** {int(profile.get('artist_count', 0)):,}")
                stats.append(f"**Albums:** {int(profile.get('album_count', 0)):,}")
                stats.append(f"**Tracks:** {int(profile.get('track_count', 0)):,}")
                embed.add_field(name="Overall Statistics", value="\n".join(stats), inline=True)
            
            # Top artists
            if top_artists and 'topartists' in top_artists:
                artists = top_artists['topartists'].get('artist', [])[:5]
                if artists:
                    artist_list = []
                    for i, artist in enumerate(artists, 1):
                        name = artist['name']
                        plays = int(artist['playcount'])
                        artist_list.append(f"{i}. **{name}** ({plays:,} plays)")
                    embed.add_field(name="Top Artists", value="\n".join(artist_list), inline=True)
            
            # Top albums
            if top_albums and 'topalbums' in top_albums:
                albums = top_albums['topalbums'].get('album', [])[:5]
                if albums:
                    album_list = []
                    for i, album in enumerate(albums, 1):
                        name = album['name']
                        artist = self.safe_get_artist(album)
                        plays = int(album['playcount'])
                        album_list.append(f"{i}. **{name}** by {artist} ({plays:,})")
                    embed.add_field(name="Top Albums", value="\n".join(album_list), inline=False)
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"<a:wrong:1436956421110632489> Error fetching stats: {str(e)}")

    @fm.command(name="played")
    async def fm_played(self, ctx, *, query: str):
        """Check how many times you've played an artist or track"""
        # Get server prefix for accurate command examples
        prefix = (await self.bot.get_prefix(ctx.message))[0]
        
        username = self.get_user_lastfm(ctx.author.id)
        
        if not username:
            return await ctx.send(f"<a:wrong:1436956421110632489> You haven't linked your Last.fm account! Use `{prefix}fm set <username>`")
        
        try:
            # Try to detect if it's an artist search or track search
            if " - " in query or " by " in query.lower():
                # Likely a track search (Artist - Track or Track by Artist)
                if " - " in query:
                    parts = query.split(" - ", 1)
                    artist_name = parts[0].strip()
                    track_name = parts[1].strip()
                elif " by " in query.lower():
                    parts = query.lower().split(" by ", 1)
                    track_name = parts[0].strip()
                    artist_name = parts[1].strip()
                
                # Get track info
                track_data = await self.get_lastfm_data(
                    'track.getinfo',
                    artist=artist_name,
                    track=track_name,
                    username=username
                )
                
                if not track_data or 'error' in track_data:
                    return await ctx.send(f"<a:wrong:1436956421110632489> Could not find track: **{track_name}** by **{artist_name}**")
                
                track_info = track_data.get('track', {})
                user_plays = int(track_info.get('userplaycount', 0))
                global_plays = int(track_info.get('playcount', 0))
                
                embed = discord.Embed(
                    title="<:speaker:1428183066311921804> Track Play Count",
                    color=self.color,
                    url=f"https://www.last.fm/music/{urllib.parse.quote(artist_name)}/_/{urllib.parse.quote(track_name)}"
                )
                
                embed.add_field(
                    name="Track",
                    value=f"**{track_name}**\nby **{artist_name}**",
                    inline=False
                )
                
                embed.add_field(
                    name="Your Plays",
                    value=f"**{user_plays:,}** times",
                    inline=True
                )
                
                embed.add_field(
                    name="Global Plays", 
                    value=f"**{global_plays:,}** times",
                    inline=True
                )
                
                # Add percentage if both exist
                if user_plays > 0 and global_plays > 0:
                    percentage = (user_plays / global_plays) * 100
                    if percentage >= 0.01:
                        embed.add_field(
                            name="Your Share",
                            value=f"**{percentage:.2f}%** of all plays",
                            inline=True
                        )
                
            else:
                # Artist search
                artist_name = query.strip()
                
                # Get artist info
                artist_data = await self.get_lastfm_data(
                    'artist.getinfo',
                    artist=artist_name,
                    username=username
                )
                
                if not artist_data or 'error' in artist_data:
                    return await ctx.send(f"<a:wrong:1436956421110632489> Could not find artist: **{artist_name}**")
                
                artist_info = artist_data.get('artist', {})
                user_plays = int(artist_info.get('userplaycount', 0))
                global_listeners = int(artist_info.get('stats', {}).get('listeners', 0))
                global_plays = int(artist_info.get('stats', {}).get('playcount', 0))
                
                embed = discord.Embed(
                    title="<a:sound:1437493915677626388> Artist Play Count",
                    color=self.color,
                    url=f"https://www.last.fm/music/{urllib.parse.quote(artist_name)}"
                )
                
                embed.add_field(
                    name="Artist",
                    value=f"**{artist_name}**",
                    inline=False
                )
                
                embed.add_field(
                    name="Your Plays",
                    value=f"**{user_plays:,}** times",
                    inline=True
                )
                
                embed.add_field(
                    name="Global Plays",
                    value=f"**{global_plays:,}** times",
                    inline=True
                )
                
                embed.add_field(
                    name="Global Listeners",
                    value=f"**{global_listeners:,}** people",
                    inline=True
                )
            
            embed.set_footer(text=f"Last.fm • {username}")
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"<a:wrong:1436956421110632489> Error fetching play count: {str(e)}")

    @fm.command(name="timezone")
    async def fm_timezone(self, ctx):
        """Set your timezone for accurate timestamps"""
        embed = discord.Embed(
            title="<a:earth:1437493493332443136> Set Your Timezone",
            description="Select your timezone from the dropdown below for accurate timestamps on your Last.fm activity.",
            color=self.color
        )
        
        # Check current timezone
        try:
            with sqlite3.connect('databases/lastfm.db') as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT timezone FROM lastfm_users WHERE user_id = ?", (ctx.author.id,))
                result = cursor.fetchone()
                current_tz = result[0] if result else 'UTC'
                
            embed.add_field(
                name="Current Timezone",
                value=f"`{current_tz}`",
                inline=False
            )
        except:
            current_tz = 'UTC'
            embed.add_field(
                name="Current Timezone", 
                value="`UTC` (default)",
                inline=False
            )
        
        view = TimezoneSelectionView(ctx.author.id, current_tz, self.bot)
        await ctx.send(embed=embed, view=view)

    @fm.command(name="build")
    async def fm_build(self, ctx):
        """🏗️ Complete Last.fm Integration Showcase - Demonstrates all features and customization options"""
        # Get server prefix for accurate command examples
        prefix = (await self.bot.get_prefix(ctx.message))[0]
        
        username = self.get_user_lastfm(ctx.author.id)
        
        if not username:
            return await ctx.send(f"<a:wrong:1436956421110632489> You need to link your Last.fm account first! Use `{prefix}fm set <username>`")
        
        # Create comprehensive showcase
        pages = []
        
        # Page 1: Feature Overview & Stats
        overview_embed = discord.Embed(
            title="<:tv:1428164884922765473> Last.fm Integration Showcase",
            description="**Complete demonstration of all Last.fm features and customization options**",
            color=self.color
        )
        
        try:
            # Get user stats
            user_data = await self.get_lastfm_data('user.getinfo', user=username)
            if user_data and 'user' in user_data:
                profile = user_data['user']
                overview_embed.add_field(
                    name="<:ar:1427471532841631855> Your Last.fm Profile",
                    value=(
                        f"**Username:** {username}\n"
                        f"**Total Scrobbles:** {int(profile.get('playcount', 0)):,}\n"
                        f"**Artists:** {int(profile.get('artist_count', 0)):,}\n"
                        f"**Tracks:** {int(profile.get('track_count', 0)):,}"
                    ),
                    inline=True
                )
            
            # Feature overview
            overview_embed.add_field(
                name="<:speaker:1428183066311921804> Available Features",
                value=(
                    "<a:yes:1431909187247673464> **Now Playing Display**\n"
                    "<a:yes:1431909187247673464> **Recent Tracks History**\n"
                    "<a:yes:1431909187247673464> **Top Artists/Albums/Tracks**\n"
                    "<a:yes:1431909187247673464> **Artist/Track Information**\n"
                    "<a:yes:1431909187247673464> **Social Features (Who Knows)**\n"
                    "<a:yes:1431909187247673464> **Crown System**\n"
                    "<a:yes:1431909187247673464> **Music Statistics**\n"
                    "<a:yes:1431909187247673464> **Full Customization**"
                ),
                inline=True
            )
            
            overview_embed.add_field(
                name="<a:gear:1430203750324240516> Customization Options",
                value=(
                    "<:paint:1437499837036625960> **Custom Embed Colors**\n"
                    "<:link:1437462772492533791> **Platform Integration**\n"
                    "<a:clock:1436953635731800178> **Timezone Support**\n"
                    "<a:lock:1437496504955699402> **Privacy Controls**\n"
                    "<a:phone:1436953635731800178> **Interactive Buttons**\n"
                    "<:sleep_customrole:1427471561085943988> **Custom Reactions**\n"
                    "<:vanity:1428163639814389771> **Album Art Display**\n"
                    "<:stats:1437456326157668362> **Statistics Toggle**"
                ),
                inline=False
            )
            
            overview_embed.set_footer(text="Page 1/6 • Use reactions to navigate")
            pages.append(overview_embed)
            
            # Page 2: Now Playing Demonstration
            np_embed = discord.Embed(
                title="<:speaker:1428183066311921804> Now Playing Feature Demo",
                description="**Comprehensive now playing display with all customization options**",
                color=self.color
            )
            
            # Get recent track for demo
            recent_data = await self.get_lastfm_data('user.getrecenttracks', user=username, limit=1)
            if recent_data and 'recenttracks' in recent_data:
                track = recent_data['recenttracks']['track'][0] if isinstance(recent_data['recenttracks']['track'], list) else recent_data['recenttracks']['track']
                track_name = track['name']
                artist_name = self.safe_get_artist(track)
                album_name = self.safe_get_album(track)
                
                np_embed.add_field(
                    name="<a:youtube:1437463222570586184> Sample Track Display",
                    value=(
                        f"**Track:** {track_name}\n"
                        f"**Artist:** {artist_name}\n"
                        f"**Album:** {album_name}\n"
                        f"**Status:** {'<:speaker:1428183066311921804> Now Playing' if '@attr' in track else '<:play:1428164853591441488> Last Played'}"
                    ),
                    inline=False
                )
                
                # Get track info for additional data
                track_info = await self.get_lastfm_data('track.getinfo', artist=artist_name, track=track_name, username=username)
                if track_info and 'track' in track_info:
                    track_data = track_info['track']
                    stats_info = []
                    if 'userplaycount' in track_data:
                        stats_info.append(f"**Your Plays:** {int(track_data['userplaycount']):,}")
                    if 'playcount' in track_data:
                        stats_info.append(f"**Global Plays:** {int(track_data['playcount']):,}")
                    if 'duration' in track_data and track_data['duration'] != '0':
                        duration = int(track_data['duration']) // 1000
                        mins, secs = divmod(duration, 60)
                        stats_info.append(f"**Duration:** {mins}:{secs:02d}")
                    
                    if stats_info:
                        np_embed.add_field(
                            name="<:stats:1437456326157668362> Track Statistics",
                            value="\n".join(stats_info),
                            inline=True
                        )
            
            np_embed.add_field(
                name="<:paint:1437499837036625960> Display Features",
                value=(
                    "<:paint:1428164884922765473> **Album Artwork**\n"
                    "<a:clock:1436953635731800178> **Timestamp Display**\n"
                    "<:link:1193611630836207656> **Clickable Links**\n"
                    "<a:phone:1436953635731800178> **Interactive Buttons**\n"
                    "👍 **Reaction System**\n"
                    "<a:phone:1437497640039350282> **Smart Status Detection**"
                ),
                inline=True
            )
            
            np_embed.set_footer(text="Page 2/6 • Now Playing Demo")
            pages.append(np_embed)
            
            # Page 3: Social Features Showcase
            social_embed = discord.Embed(
                title="<a:crown:1437503143591153756> Social Features & Crown System",
                description="**Community interaction and competitive features**",
                color=self.color
            )
            
            # Get top artist for demo
            top_artists = await self.get_lastfm_data('user.gettopartists', user=username, period='overall', limit=5)
            if top_artists and 'topartists' in top_artists:
                artists = top_artists['topartists'].get('artist', [])[:3]
                if artists:
                    artist_list = []
                    for i, artist in enumerate(artists, 1):
                        name = artist['name']
                        plays = int(artist['playcount'])
                        artist_list.append(f"{i}. **{name}** - {plays:,} plays")
                    
                    social_embed.add_field(
                        name="<a:sound:1437493915677626388> Your Top Artists",
                        value="\n".join(artist_list),
                        inline=False
                    )
            
            social_embed.add_field(
                name="<a:crown:1437503143591153756> Crown System Features",
                value=(
                    "<a:crown:1437503143591153756> **Artist Crowns** - Most plays per artist\n"
                    "🥇 **Server Leaderboards** - Competition tracking\n"
                    "<a:mark:1436953593923244113> **Crown Stealing** - Dynamic rankings\n"
                    "<a:questionmarks:1436953662122365039> **Who Knows** - Find music buddies"
                ),
                inline=True
            )
            
            social_embed.add_field(
                name="<a:alone:1437495902867558533> Social Commands",
                value=(
                    f"`{prefix}fm whoknows <artist>` - Server rankings\n"
                    f"`{prefix}fm crowns [user]` - Crown collection\n"
                    f"`{prefix}fm compare <user>` - Music compatibility\n"
                    f"`{prefix}fm recent [user]` - Friend activity"
                ),
                inline=True
            )
            
            social_embed.set_footer(text="Page 3/6 • Social Features")
            pages.append(social_embed)
            
            # Page 4: Customization Options
            custom_embed = discord.Embed(
                title="<a:gear:1430203750324240516> Complete Customization System",
                description="**Every aspect can be personalized to your preferences**",
                color=self.color
            )
            
            # Get current settings
            settings = self.get_guild_settings(ctx.guild.id)
            
            custom_embed.add_field(
                name="<:paint:1437499837036625960> Visual Customization",
                value=(
                    f"**Embed Color:** `{settings['embed_color']}`\n"
                    f"**Album Art:** {'<a:yes:1431909187247673464> Enabled' if settings['show_album_art'] else '<a:wrong:1436956421110632489> Disabled'}\n"
                    f"**Thumbnails:** {'<a:yes:1431909187247673464> Enabled' if settings['embed_thumbnail'] else '<a:wrong:1436956421110632489> Disabled'}\n"
                    f"**Playcount Display:** {'<a:yes:1431909187247673464> Enabled' if settings['show_playcount'] else '<a:wrong:1436956421110632489> Disabled'}"
                ),
                inline=True
            )
            
            custom_embed.add_field(
                name="👍 Reaction System",
                value=(
                    f"**Auto React:** {'<a:yes:1431909187247673464> Enabled' if settings['auto_react'] else '<a:wrong:1436956421110632489> Disabled'}\n"
                    f"**NP Reactions:** {'<a:yes:1431909187247673464> Enabled' if settings['np_reactions'] else '<a:wrong:1436956421110632489> Disabled'}\n"
                    f"**Custom Emojis:** {', '.join(settings['custom_reactions'][:3])}\n"
                    f"**Reaction Threshold:** {settings['reaction_threshold']}"
                ),
                inline=True
            )
            
            custom_embed.add_field(
                name="<a:gear:1430203750324240516> Advanced Settings",
                value=(
                    f"**Crown System:** {'<a:yes:1431909187247673464> Active' if settings['crown_system'] else '<a:wrong:1436956421110632489> Disabled'}\n"
                    f"**Auto Crowns:** {'<a:yes:1431909187247673464> Enabled' if settings['auto_crowns'] else '<a:wrong:1436956421110632489> Disabled'}\n"
                    f"**Who Knows Limit:** {settings['whoknows_limit']} users\n"
                    f"**Chart Size:** {settings['chart_size']} albums"
                ),
                inline=False
            )
            
            custom_embed.add_field(
                name="<a:phone:1436953635731800178> Available Customization Commands",
                value=(
                    f"`{prefix}fm customize` - Personal settings panel\n"
                    f"`{prefix}fm privacy` - Privacy configuration\n"
                    f"`{prefix}fm timezone` - Timezone selection\n"
                    f"`{prefix}fm build` - This showcase command!"
                ),
                inline=False
            )
            
            custom_embed.set_footer(text="Page 4/6 • Customization Options")
            pages.append(custom_embed)
            
            # Page 5: Statistics & Analytics
            stats_embed = discord.Embed(
                title="<:stats:1437456326157668362> Advanced Statistics & Analytics",
                description="**Comprehensive data analysis and insights**",
                color=self.color
            )
            
            # Get comprehensive stats
            if user_data and 'user' in user_data:
                profile = user_data['user']
                
                # Calculate advanced metrics
                total_scrobbles = int(profile.get('playcount', 0))
                total_artists = int(profile.get('artist_count', 0))
                total_tracks = int(profile.get('track_count', 0))
                
                if total_scrobbles > 0 and total_artists > 0:
                    avg_per_artist = total_scrobbles / total_artists
                    stats_embed.add_field(
                        name="🔢 Advanced Metrics",
                        value=(
                            f"**Total Scrobbles:** {total_scrobbles:,}\n"
                            f"**Unique Artists:** {total_artists:,}\n"
                            f"**Unique Tracks:** {total_tracks:,}\n"
                            f"**Avg Plays/Artist:** {avg_per_artist:.1f}"
                        ),
                        inline=True
                    )
                
                # Account age and activity
                if 'registered' in profile:
                    reg_time = datetime.fromtimestamp(int(profile['registered']['unixtime']))
                    days_active = (datetime.now() - reg_time).days
                    if days_active > 0:
                        daily_avg = total_scrobbles / days_active
                        stats_embed.add_field(
                            name="<:stats:1437456326157668362> Activity Analysis",
                            value=(
                                f"**Account Age:** {days_active:,} days\n"
                                f"**Daily Average:** {daily_avg:.1f} scrobbles\n"
                                f"**Joined:** {reg_time.strftime('%B %Y')}"
                            ),
                            inline=True
                        )
            
            stats_embed.add_field(
                name="<:stats:1437456326157668362> Available Statistics Commands",
                value=(
                    f"`{prefix}fm stats [user] [period]` - Comprehensive stats\n"
                    f"`{prefix}fm profile [user]` - Detailed profile\n"
                    f"`{prefix}fm chart [period]` - Visual album charts\n"
                    f"`{prefix}fm topartists/albums/tracks` - Top lists\n"
                    f"`{prefix}fm played <artist/track>` - Play counts"
                ),
                inline=False
            )
            
            stats_embed.set_footer(text="Page 5/6 • Statistics & Analytics")
            pages.append(stats_embed)
            
            # Page 6: Platform Integration & Future
            integration_embed = discord.Embed(
                title="<:link:1193611630836207656> Platform Integration & Advanced Features",
                description="**Seamless integration with multiple music platforms**",
                color=self.color
            )
            
            integration_embed.add_field(
                name="<:speaker:1428183066311921804> Platform Support",
                value=(
                    "🔴 **YouTube** - Direct video links\n"
                    "🟢 **Spotify** - Track/album integration\n"
                    "⚪ **Apple Music** - iOS compatibility\n"
                    "🟠 **SoundCloud** - Independent artists\n"
                    "🔵 **Bandcamp** - Artist support\n"
                    "<:link:1193611630836207656> **Last.fm** - Complete API integration"
                ),
                inline=True
            )
            
           
            
            integration_embed.add_field(
                name="🚀 Getting Started",
                value=(
                    f"1. **Link Account:** `{prefix}fm set <username>`\n"
                    f"2. **Customize:** `{prefix}fm customize`\n"
                    f"3. **Set Timezone:** `{prefix}fm timezone`\n"
                    f"4. **Try Commands:** `{prefix}fm np`, `{prefix}fm recent`\n"
                    f"5. **Explore Social:** `{prefix}fm whoknows <artist>`"
                ),
                inline=False
            )
            
            integration_embed.set_footer(text="Page 6/6 • Platform Integration & Setup")
            pages.append(integration_embed)
            
            # Send showcase with navigation
            view = BuildShowcaseView(pages, ctx.author.id)
            await ctx.send(embed=pages[0], view=view)
            
        except Exception as e:
            error_embed = discord.Embed(
                title="<a:wrong:1436956421110632489> Showcase Error",
                description=f"Failed to generate complete showcase: {str(e)}",
                color=0xff0000
            )
            await ctx.send(embed=error_embed)

    def help_custom(self):
        return "<:speaker:1428183066311921804>", "Last.fm (FM)", "Music tracking, now playing, crowns, charts & stats"

class BuildShowcaseView(View):
    def __init__(self, pages, user_id):
        super().__init__(timeout=300)
        self.pages = pages
        self.current_page = 0
        self.user_id = user_id
        self.max_pages = len(pages)
        self.update_buttons()
    
    def update_buttons(self):
        # Update button states based on current page
        self.first_page.disabled = self.current_page == 0
        self.prev_page.disabled = self.current_page == 0
        self.next_page.disabled = self.current_page == self.max_pages - 1
        self.last_page.disabled = self.current_page == self.max_pages - 1
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id
    
    @discord.ui.button(emoji="⏮️", style=discord.ButtonStyle.secondary)
    async def first_page(self, interaction: discord.Interaction, button: Button):
        self.current_page = 0
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.secondary)
    async def prev_page(self, interaction: discord.Interaction, button: Button):
        self.current_page = max(0, self.current_page - 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    @discord.ui.button(emoji="🏠", style=discord.ButtonStyle.primary, label="Home")
    async def home_page(self, interaction: discord.Interaction, button: Button):
        self.current_page = 0
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: Button):
        self.current_page = min(self.max_pages - 1, self.current_page + 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary)
    async def last_page(self, interaction: discord.Interaction, button: Button):
        self.current_page = self.max_pages - 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    @discord.ui.button(emoji="<a:wrong:1436956421110632489>", style=discord.ButtonStyle.danger, label="Close")
    async def close_showcase(self, interaction: discord.Interaction, button: Button):
        # Disable all buttons
        self.first_page.disabled = True
        self.prev_page.disabled = True
        self.home_page.disabled = True
        self.next_page.disabled = True
        self.last_page.disabled = True
        self.close_showcase.disabled = True
        
        final_embed = discord.Embed(
            title="<a:yes:1431909187247673464> Last.fm Showcase Complete",
            description="Thank you for exploring the complete Last.fm integration!",
            color=0x006fb9
        )
        await interaction.response.edit_message(embed=final_embed, view=self)

class TimezoneSelectionView(View):
    def __init__(self, user_id, current_timezone, bot):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.current_timezone = current_timezone
        self.bot = bot
        
        # Add timezone dropdown
        self.add_item(TimezoneDropdown(user_id, current_timezone, bot))

class TimezoneDropdown(discord.ui.Select):
    def __init__(self, user_id, current_timezone, bot):
        self.user_id = user_id
        self.current_timezone = current_timezone
        self.bot = bot
        
        # Common timezones organized by region
        timezone_options = [
            discord.SelectOption(
                label="UTC (Coordinated Universal Time)",
                value="UTC",
                description="Greenwich Mean Time",
                emoji="🌍",
                default=(current_timezone == "UTC")
            ),
            discord.SelectOption(
                label="EST - Eastern Standard Time",
                value="America/New_York", 
                description="New York, Toronto, Miami",
                emoji="🇺🇸",
                default=(current_timezone == "America/New_York")
            ),
            discord.SelectOption(
                label="CST - Central Standard Time",
                value="America/Chicago",
                description="Chicago, Dallas, Mexico City", 
                emoji="🇺🇸",
                default=(current_timezone == "America/Chicago")
            ),
            discord.SelectOption(
                label="MST - Mountain Standard Time",
                value="America/Denver",
                description="Denver, Salt Lake City",
                emoji="🇺🇸", 
                default=(current_timezone == "America/Denver")
            ),
            discord.SelectOption(
                label="PST - Pacific Standard Time",
                value="America/Los_Angeles",
                description="Los Angeles, Seattle, San Francisco",
                emoji="🇺🇸",
                default=(current_timezone == "America/Los_Angeles")
            ),
            discord.SelectOption(
                label="GMT - Greenwich Mean Time",
                value="Europe/London",
                description="London, Dublin",
                emoji="🇬🇧",
                default=(current_timezone == "Europe/London")
            ),
            discord.SelectOption(
                label="CET - Central European Time", 
                value="Europe/Paris",
                description="Paris, Berlin, Madrid, Rome",
                emoji="🇪🇺",
                default=(current_timezone == "Europe/Paris")
            ),
            discord.SelectOption(
                label="EET - Eastern European Time",
                value="Europe/Helsinki",
                description="Helsinki, Athens, Cairo",
                emoji="🇪🇺",
                default=(current_timezone == "Europe/Helsinki")
            ),
            discord.SelectOption(
                label="JST - Japan Standard Time",
                value="Asia/Tokyo", 
                description="Tokyo, Seoul",
                emoji="🇯🇵",
                default=(current_timezone == "Asia/Tokyo")
            ),
            discord.SelectOption(
                label="AEST - Australian Eastern Time",
                value="Australia/Sydney",
                description="Sydney, Melbourne",
                emoji="🇦🇺",
                default=(current_timezone == "Australia/Sydney")
            ),
            discord.SelectOption(
                label="IST - India Standard Time",
                value="Asia/Kolkata",
                description="Mumbai, Delhi, Bangalore", 
                emoji="🇮🇳",
                default=(current_timezone == "Asia/Kolkata")
            ),
            discord.SelectOption(
                label="CST - China Standard Time",
                value="Asia/Shanghai",
                description="Beijing, Shanghai, Hong Kong",
                emoji="🇨🇳", 
                default=(current_timezone == "Asia/Shanghai")
            )
        ]
        
        super().__init__(
            placeholder="<a:earth:1437493493332443136> Select your timezone...",
            min_values=1,
            max_values=1,
            options=timezone_options
        )
    
    async def callback(self, interaction: discord.Interaction):
        selected_timezone = self.values[0]
        
        try:
            # Update timezone in database
            with sqlite3.connect('databases/lastfm.db') as conn:
                cursor = conn.cursor()
                # First check if user exists
                cursor.execute("SELECT user_id FROM lastfm_users WHERE user_id = ?", (self.user_id,))
                if cursor.fetchone():
                    # Update existing user
                    cursor.execute(
                        "UPDATE lastfm_users SET timezone = ? WHERE user_id = ?",
                        (selected_timezone, self.user_id)
                    )
                else:
                    # Create new user record (they need to link Last.fm account)
                    # Get server prefix for accurate command examples
                    from types import SimpleNamespace
                    mock_message = SimpleNamespace()
                    mock_message.guild = interaction.guild
                    mock_message.channel = interaction.channel if hasattr(interaction, 'channel') else None
                    prefix = (await self.bot.get_prefix(mock_message))[0]
                    
                    await interaction.response.send_message(
                        f"<a:wrong:1436956421110632489> Please link your Last.fm account first using `{prefix}fm set <username>`",
                        ephemeral=True
                    )
                    return
                
                conn.commit()
            
            # Create success embed
            embed = discord.Embed(
                title="<a:yes:1431909187247673464> Timezone Updated",
                description=f"Your timezone has been set to **{selected_timezone}**",
                color=0x006fb9
            )
            
            # Show example of how timestamps will appear
            from datetime import datetime
            import pytz
            
            try:
                tz = pytz.timezone(selected_timezone)
                current_time = datetime.now(tz)
                embed.add_field(
                    name="Current Time",
                    value=f"`{current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}`",
                    inline=False
                )
                embed.add_field(
                    name="Note",
                    value="This timezone will be used for all Last.fm timestamps and activity tracking.",
                    inline=False
                )
            except:
                pass
            
            # Disable the dropdown
            view = self.view
            if view:
                for item in view.children:
                    item.disabled = True
                await interaction.response.edit_message(embed=embed, view=view)
            else:
                await interaction.response.edit_message(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="<a:wrong:1436956421110632489> Error",
                description=f"Failed to update timezone: {str(e)}",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

class EnhancedMusicView(View):
    def __init__(self, cog, track_name, artist_name, album_name, lastfm_username, settings, bot):
        super().__init__(timeout=300)
        self.cog = cog
        self.track_name = track_name
        self.artist_name = artist_name
        self.album_name = album_name
        self.lastfm_username = lastfm_username
        self.settings = settings
        self.bot = bot
        
        # Add Last.fm link button
        lastfm_url = f"https://www.last.fm/music/{urllib.parse.quote(artist_name)}/_/{urllib.parse.quote(track_name)}"
        self.add_item(Button(label="Last.fm", url=lastfm_url, emoji="<:link:1193611630836207656>", style=discord.ButtonStyle.link))

    @discord.ui.button(emoji="🔍", label="Search", style=discord.ButtonStyle.secondary)
    async def search_track(self, interaction: discord.Interaction, button: Button):
        """Search for this track on various platforms"""
        search_view = EnhancedMusicSearchView(self.track_name, self.artist_name)
        embed = discord.Embed(
            title="🔍 Search for Track",
            description=f"**{self.track_name}** by **{self.artist_name}**",
            color=0x1DB954
        )
        embed.add_field(
            name="Available Platforms",
            value="Click the buttons below to search on different music platforms",
            inline=False
        )
        await interaction.response.send_message(embed=embed, view=search_view, ephemeral=True)

    @discord.ui.button(emoji="<a:crown:1437503143591153756>", label="Who Knows", style=discord.ButtonStyle.primary)
    async def whoknows_quick(self, interaction: discord.Interaction, button: Button):
        """Quick who knows for this artist"""
        await interaction.response.defer(ephemeral=True)
        
        # Simplified who knows check
        # Get server prefix for accurate command examples
        from types import SimpleNamespace
        mock_message = SimpleNamespace()
        mock_message.guild = interaction.guild
        mock_message.channel = interaction.channel if hasattr(interaction, 'channel') else None
        prefix = (await self.bot.get_prefix(mock_message))[0]
        
        embed = discord.Embed(
            title=f"<a:crown:1437503143591153756> Quick Who Knows: {self.artist_name}",
            description=f"Use `{prefix}fm whoknows {self.artist_name}` for full server rankings!",
            color=self.cog.color
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(emoji="📊", label="Stats", style=discord.ButtonStyle.secondary)
    async def track_stats(self, interaction: discord.Interaction, button: Button):
        """Show detailed track statistics"""
        await interaction.response.defer(ephemeral=True)
        
        # Get detailed track info
        track_info = await self.cog.get_lastfm_data(
            'track.getinfo',
            artist=self.artist_name,
            track=self.track_name,
            username=self.lastfm_username
        )
        
        embed = discord.Embed(
            title=f"📊 Statistics for {self.track_name}",
            color=self.cog.color
        )
        
        if track_info and 'track' in track_info:
            track_data = track_info['track']
            
            stats_text = []
            
            if 'userplaycount' in track_data:
                stats_text.append(f"**Your plays:** {track_data['userplaycount']}")
            
            if 'playcount' in track_data:
                stats_text.append(f"**Global plays:** {int(track_data['playcount']):,}")
            
            if 'listeners' in track_data:
                stats_text.append(f"**Global listeners:** {int(track_data['listeners']):,}")
            
            if stats_text:
                embed.description = "\n".join(stats_text)
            else:
                embed.description = "No detailed statistics available."
        else:
            embed.description = "Unable to fetch track statistics."
        
        await interaction.followup.send(embed=embed, ephemeral=True)

class EnhancedMusicSearchView(View):
    def __init__(self, track_name, artist_name):
        super().__init__(timeout=60)
        self.track_name = track_name
        self.artist_name = artist_name
        
        # Create search query
        query = f"{track_name} {artist_name}".replace(" ", "%20")
        
        # Add search buttons for different platforms
        spotify_url = f"https://open.spotify.com/search/{query}"
        youtube_url = f"https://www.youtube.com/results?search_query={query}"
        apple_url = f"https://music.apple.com/search?term={query}"
        soundcloud_url = f"https://soundcloud.com/search?q={query}"
        bandcamp_url = f"https://bandcamp.com/search?q={query}"
        
        self.add_item(Button(label="Spotify", url=spotify_url, emoji="🟢"))
        self.add_item(Button(label="YouTube", url=youtube_url, emoji="🔴"))
        self.add_item(Button(label="Apple Music", url=apple_url, emoji="⚪"))
        self.add_item(Button(label="SoundCloud", url=soundcloud_url, emoji="🟠"))
        self.add_item(Button(label="Bandcamp", url=bandcamp_url, emoji="🔵"))

async def setup(bot):
    cog = LastFMCog(bot)
    await bot.add_cog(cog)