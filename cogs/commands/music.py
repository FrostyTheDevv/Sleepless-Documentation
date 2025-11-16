# type: ignore
# pyright: reportMissingImports=false
import random
import discord
from discord.ext import commands, tasks
import datetime
from discord.ui import Button, View
import asyncio
import yt_dlp
import re
import os
import subprocess
import requests
from typing import Optional, List, Dict
from utils import Paginator, DescriptionEmbedPaginator
from utils.Tools import blacklist_check, ignore_check
from core import Cog, sleepless, Context
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io
import aiohttp
import base64
from collections import deque
from music_custom_emojis import MUSIC_EMOJIS, MUSIC_STATE_EMOJIS
import aiosqlite

# Load environment variables for Spotify integration
from dotenv import load_dotenv
load_dotenv()
import time
import requests
import threading
import subprocess
import struct
import os as _os

# Wavelink v4 imports for Lavalink integration
try:
    import wavelink
    from wavelink import Playable, TrackSource
    from wavelink import (
        TrackStartEventPayload, 
        TrackEndEventPayload, 
        TrackExceptionEventPayload, 
        TrackStuckEventPayload,
        WebsocketClosedEventPayload
    )
    WAVELINK_AVAILABLE = True
    print("[MUSIC] Wavelink 3.4.1 loaded for Lavalink v4 integration")
except ImportError:
    WAVELINK_AVAILABLE = False
    print("[MUSIC] Wavelink not available - Lavalink features disabled")

# Import voice helper for safer connections
try:
    from voice_helper import safe_voice_connect, safe_voice_disconnect, is_voice_client_valid
    VOICE_HELPER_AVAILABLE = True
    print("[MUSIC] Voice helper loaded for enhanced connection stability")
except ImportError:
    VOICE_HELPER_AVAILABLE = False
    print("[MUSIC] Voice helper not available - using standard connections")

SPOTIFY_TRACK_REGEX = r"https?://open\.spotify\.com/track/([a-zA-Z0-9]+)"
SPOTIFY_PLAYLIST_REGEX = r"https?://open\.spotify\.com/playlist/([a-zA-Z0-9]+)"
SPOTIFY_ALBUM_REGEX = r"https?://open\.spotify\.com/album/([a-zA-Z0-9]+)"

# yt-dlp options for audio download and playback
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'outtmpl': 'downloads/%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',  # Let each search specify its own source instead of forcing ytmsearch
    'source_address': '0.0.0.0',
    'extractaudio': True,
    'audioformat': 'mp3',
    'audioquality': '192K',
}

class Track:
    def __init__(self, data: dict, requester: Optional[discord.Member] = None, local_file: Optional[str] = None):
        self.title = data.get('title', 'Unknown')
        self.url = data.get('url', '')
        self.webpage_url = data.get('webpage_url', '')
        self.duration = data.get('duration', 0)
        self.thumbnail = data.get('thumbnail', '')
        self.author = data.get('uploader', 'Unknown')
        self.requester = requester
        self.source = self._detect_source()
        self.extractor = data.get('extractor', 'Unknown')
        self.local_file = local_file  # Path to downloaded audio file

    def _detect_source(self):
        """Detect the source platform from URL"""
        if 'youtube' in (self.webpage_url or '').lower():
            return 'youtube'
        elif 'soundcloud' in (self.webpage_url or '').lower():
            return 'soundcloud'
        elif 'spotify' in (self.webpage_url or '').lower():
            return 'spotify'
        else:
            return 'unknown'

    @property
    def length(self):
        """Convert duration to milliseconds for compatibility"""
        return self.duration * 1000

class MusicQueue:
    def __init__(self):
        self.queue = deque()
        self.loop_mode = False
        self.shuffle_mode = False
        self.autoplay_mode = False
        self.history = deque(maxlen=50)  # Keep track of last 50 played tracks

    def add(self, track: Track):
        """Add a track to the queue"""
        self.queue.append(track)

    def get_next(self) -> Optional[Track]:
        """Get the next track from queue"""
        if not self.queue:
            return None
        
        if self.shuffle_mode and len(self.queue) > 1:
            # Remove and return random track
            index = random.randint(0, len(self.queue) - 1)
            items = list(self.queue)
            track = items.pop(index)
            self.queue = deque(items)
            return track
        elif self.loop_mode:
            # Loop mode: rotate queue and return first
            track = self.queue[0]
            self.queue.rotate(-1)
            return track
        else:
            return self.queue.popleft()

    def clear(self):
        """Clear the queue"""
        self.queue.clear()

    def shuffle(self):
        """Shuffle the queue"""
        if self.queue:
            items = list(self.queue)
            random.shuffle(items)
            self.queue = deque(items)

    def add_to_history(self, track: Track):
        """Add a track to play history"""
        self.history.append(track)

    def is_empty(self) -> bool:
        return len(self.queue) == 0

    def __len__(self):
        return len(self.queue)

    def __iter__(self):
        return iter(self.queue)

class SpotifyAPI:
    BASE_URL = "https://api.spotify.com/v1"
    
    def __init__(self):
        # Use environment variables for Spotify credentials
        self.client_id = os.getenv('SPOTIFY_CLIENT_ID')
        self.client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
        self.access_token = None
        
        if not self.client_id or not self.client_secret:
            print("[SPOTIFY] Warning: SPOTIFY_CLIENT_ID or SPOTIFY_CLIENT_SECRET not found in environment variables")
            print("[SPOTIFY] Please add them to your .env file for direct Spotify integration")
            # Fallback to previous credentials if env vars not set
            self.client_id = "ac2b614ca5ce46a18dfd1d3475fd6fd9"
            self.client_secret = "df7bec95ae88438e8286db597bac8621"

    async def get_access_token(self) -> Optional[str]:
        """Get Spotify access token"""
        try:
            auth_url = "https://accounts.spotify.com/api/token"
            auth_data = {
                'grant_type': 'client_credentials',
                'client_id': self.client_id,
                'client_secret': self.client_secret
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(auth_url, data=auth_data) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.access_token = data.get('access_token')
                        return self.access_token
            return None
        except:
            return None

    async def get_track_info(self, track_id: str) -> Optional[dict]:
        """Get track information from Spotify"""
        if not self.access_token:
            await self.get_access_token()
            
        if not self.access_token:
            return None
            
        try:
            headers = {'Authorization': f'Bearer {self.access_token}'}
            url = f"{self.BASE_URL}/tracks/{track_id}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        return await response.json()
            return None
        except:
            return None

    async def get_playlist_tracks(self, playlist_id: str) -> List[dict]:
        """Get all tracks from a Spotify playlist"""
        if not self.access_token:
            await self.get_access_token()
            
        if not self.access_token:
            return []
            
        try:
            headers = {'Authorization': f'Bearer {self.access_token}'}
            url = f"{self.BASE_URL}/playlists/{playlist_id}/tracks"
            
            tracks = []
            offset = 0
            limit = 50
            
            while True:
                params = {'offset': offset, 'limit': limit, 'fields': 'items(track(name,artists,id)),next'}
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, params=params) as response:
                        if response.status != 200:
                            break
                        
                        data = await response.json()
                        items = data.get('items', [])
                        
                        for item in items:
                            track = item.get('track')
                            if track and track.get('name') and track.get('artists'):
                                tracks.append(track)
                        
                        # Check if there are more tracks
                        if not data.get('next') or len(items) < limit:
                            break
                        offset += limit
            
            return tracks
        except Exception as e:
            print(f"[SPOTIFY] Error getting playlist tracks: {e}")
            return []

    async def get_album_tracks(self, album_id: str) -> List[dict]:
        """Get all tracks from a Spotify album"""
        if not self.access_token:
            await self.get_access_token()
            
        if not self.access_token:
            return []
            
        try:
            headers = {'Authorization': f'Bearer {self.access_token}'}
            url = f"{self.BASE_URL}/albums/{album_id}/tracks"
            
            tracks = []
            offset = 0
            limit = 50
            
            while True:
                params = {'offset': offset, 'limit': limit}
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, params=params) as response:
                        if response.status != 200:
                            break
                        
                        data = await response.json()
                        items = data.get('items', [])
                        
                        for track in items:
                            if track and track.get('name') and track.get('artists'):
                                tracks.append(track)
                        
                        # Check if there are more tracks
                        if not data.get('next') or len(items) < limit:
                            break
                        offset += limit
            
            return tracks
        except Exception as e:
            print(f"[SPOTIFY] Error getting album tracks: {e}")
            return []

    async def get_playlist_info(self, playlist_id: str) -> Optional[dict]:
        """Get playlist information"""
        if not self.access_token:
            await self.get_access_token()
            
        if not self.access_token:
            return None
            
        try:
            headers = {'Authorization': f'Bearer {self.access_token}'}
            url = f"{self.BASE_URL}/playlists/{playlist_id}"
            params = {'fields': 'name,description,owner.display_name,tracks.total,images'}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        return await response.json()
            return None
        except:
            return None

    async def get_album_info(self, album_id: str) -> Optional[dict]:
        """Get album information"""
        if not self.access_token:
            await self.get_access_token()
            
        if not self.access_token:
            return None
            
        try:
            headers = {'Authorization': f'Bearer {self.access_token}'}
            url = f"{self.BASE_URL}/albums/{album_id}"
            params = {'fields': 'name,artists,release_date,total_tracks,images'}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        return await response.json()
            return None
        except:
            return None

    async def search_track(self, query: str) -> Optional[str]:
        """Search for a track on Spotify and return YouTube search query"""
        if not query:
            return None
            
        # If query is already a track ID, use it directly
        if len(query) == 22 and query.isalnum():
            track_info = await self.get_track_info(query)
        else:
            # Search for the track first
            search_results = await self.search_tracks(query)
            if not search_results or not search_results.get('tracks', {}).get('items'):
                return f"{query} audio"
            track_info = search_results['tracks']['items'][0]
        
        if track_info:
            artist = track_info['artists'][0]['name'] if track_info.get('artists') else ''
            title = track_info.get('name', '')
            return f"{artist} {title} audio"
        return f"{query} audio"
    
    async def search_tracks(self, query: str) -> Optional[dict]:
        """Search for tracks on Spotify"""
        if not self.access_token:
            await self.get_access_token()
            
        if not self.access_token:
            return None
            
        try:
            headers = {'Authorization': f'Bearer {self.access_token}'}
            params = {
                'q': query,
                'type': 'track',
                'limit': 1
            }
            url = f"{self.BASE_URL}/search"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        return await response.json()
            return None
        except:
            return None

class PlatformSelectView(View):
    def __init__(self, ctx, query, music_cog):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.query = query
        self.music_cog = music_cog

        # Updated platforms with YouTube Music prioritized
        platforms = [
            ("YouTube Music", "ytmsearch", discord.ButtonStyle.red, MUSIC_EMOJIS.get('youtube_music', '🎵')),
            ("Spotify", "spsearch", discord.ButtonStyle.green, MUSIC_EMOJIS['spotify']),
            ("YouTube", "ytsearch", discord.ButtonStyle.danger, MUSIC_EMOJIS.get('youtube', '📺')),
            ("SoundCloud", "scsearch", discord.ButtonStyle.secondary, MUSIC_EMOJIS['soundcloud']),
        ]

        for name, source, style, emoji in platforms:
            button = Button(label=name, style=style, emoji=emoji)
            button.callback = self.create_callback(source)
            self.add_item(button)

    def create_callback(self, source):
        async def callback(interaction: discord.Interaction):
            if interaction.user != self.ctx.author:
                await interaction.response.send_message("Only the command author can select a platform.", ephemeral=True)
                return

            await interaction.response.send_message(f"Searching on {source}...", ephemeral=True)
            await self.perform_search(source)
            await interaction.message.delete()
        return callback

    async def perform_search(self, source):
        try:
            results = await self.music_cog.search_tracks(self.query, source)
            if not results:
                await self.ctx.send(embed=discord.Embed(description="No results found.", color=0xFF0000))
                return

            top_results = results[:5]
            embed = discord.Embed(
                title=f"Top 5 Results for '{self.query}' ({source})",
                color=0x1DB954
            )
            for i, track in enumerate(top_results, start=1):
                duration_str = f"{track.duration // 60}:{track.duration % 60:02d}" if track.duration else "Unknown"
                embed.add_field(name=f"{i}. {track.title}", value=f"Duration: {duration_str} | Author: {track.author}", inline=False)

            await self.ctx.send(embed=embed, view=SearchResultView(self.ctx, top_results, self.music_cog))
        except Exception as e:
            await self.ctx.send(embed=discord.Embed(description=f"Search failed: {str(e)}", color=0xFF0000))

class SearchResultView(View):
    def __init__(self, ctx, results, music_cog):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.results = results
        self.music_cog = music_cog

        for i in range(min(5, len(results))):
            button = Button(label=str(i + 1), style=discord.ButtonStyle.primary)
            button.callback = self.create_callback(i)
            self.add_item(button)

    def create_callback(self, index):
        async def callback(interaction: discord.Interaction):
            if interaction.user != self.ctx.author:
                await interaction.response.send_message("Only the command author can select a track.", ephemeral=True)
                return

            # Defer the response since downloading might take time
            await interaction.response.defer()
            
            # Get the selected track data
            track_data = self.results[index]
            
            query = track_data.webpage_url or track_data.title

            # If Lavalink is enabled, avoid downloading and create a Track that references the webpage_url
            if self.music_cog.use_lavalink:
                # Try to ensure the pool is initialized so we can avoid downloading
                pool_ok = True if self.music_cog._lavalink_pool else await self.music_cog._ensure_lavalink_pool()
                if pool_ok and self.music_cog._lavalink_pool:
                    track = Track({
                        'title': track_data.title,
                        'webpage_url': query,
                        'duration': track_data.duration if hasattr(track_data, 'duration') else 0,
                        'thumbnail': track_data.thumbnail if hasattr(track_data, 'thumbnail') else '',
                        'uploader': track_data.author if hasattr(track_data, 'author') else ''
                    }, requester=self.ctx.author, local_file=None)
                    await self.music_cog.add_to_queue(self.ctx, track)
                    await interaction.followup.send(f"Added `{track.title}` to the queue (Lavalink mode).")
                else:
                    # Pool not available; fallthrough to download path depending on ALLOW_DOWNLOAD_FALLBACK
                    allow_fallback = bool(_os.environ.get('ALLOW_DOWNLOAD_FALLBACK', '1'))
                    if not allow_fallback:
                        await interaction.followup.send(f"❌ Lavalink unavailable and download fallback disabled.")
                        await interaction.message.delete()
                        return
                    # else continue to download below
            else:
                # Download the track
                downloaded_track = await self.music_cog.search_and_download_track(query)
                
                if downloaded_track:
                    downloaded_track.requester = self.ctx.author
                    await self.music_cog.add_to_queue(self.ctx, downloaded_track)
                    await interaction.followup.send(f"Added `{downloaded_track.title}` to the queue.")
                else:
                    await interaction.followup.send(f"Failed to download `{track_data.title}`.")
            
            await interaction.message.delete()

        return callback


from typing import Any


class VolumeModal(discord.ui.Modal, title='Volume Control'):
    def __init__(self, music_cog: Any, ctx: Context):
        super().__init__()
        self.music_cog = music_cog
        self.ctx = ctx

    volume = discord.ui.TextInput(
        label='Volume Level',
        placeholder='Enter volume (0-200%)',
        default='40',
        min_length=1,
        max_length=3,
    )

    async def on_submit(self, interaction: discord.Interaction):
        """Handle volume change submission"""
        try:
            # Validate volume input
            volume_str = self.volume.value.strip().replace('%', '')
            
            try:
                volume_level = int(volume_str)
            except ValueError:
                await interaction.response.send_message('❌ Invalid volume! Please enter a number between 0-200.', ephemeral=True)
                return
            
            # Clamp volume between 0 and 200
            volume_level = max(0, min(200, volume_level))
            
            # Get the music controller
            mode, controller = await self.music_cog._get_playback_controller(self.ctx)
            
            if mode == 'lavalink' and controller:
                # Set volume using Wavelink v4 API
                if hasattr(controller, 'set_volume'):
                    await controller.set_volume(volume_level)
                    
                    # Save volume setting for this guild to database
                    guild_id = self.ctx.guild.id
                    await self.music_cog._save_volume_to_db(guild_id, volume_level)
                    
                    # Create success embed
                    embed = discord.Embed(
                        title="🔊 Volume Changed",
                        description=f"Volume set to **{volume_level}%**",
                        color=0x00E6A7
                    )
                    
                    # Add volume bar visualization
                    bar_length = 20
                    filled_length = int(bar_length * volume_level / 200)
                    bar = '█' * filled_length + '░' * (bar_length - filled_length)
                    embed.add_field(name="Volume Bar", value=f"`{bar}` {volume_level}%", inline=False)
                    
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                else:
                    await interaction.response.send_message('❌ Volume control not available in this version!', ephemeral=True)
            else:
                await interaction.response.send_message('❌ No active music player found!', ephemeral=True)
                
        except Exception as e:
            await interaction.response.send_message(f'❌ Error setting volume: {str(e)}', ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        """Handle modal errors"""
        await interaction.response.send_message('❌ An error occurred while processing the volume change.', ephemeral=True)
        print(f"[DEBUG] Volume modal error: {error}")


class MusicControlView(View):
    def __init__(self, music_cog: Any, ctx: Context, timeout: float = 300):
        super().__init__(timeout=timeout)
        self.music_cog = music_cog
        self.ctx = ctx
        self._paused = False

        # Row 1: Main playback controls (5 buttons)
        btn_previous_track = Button(emoji=MUSIC_EMOJIS['previous'], style=discord.ButtonStyle.blurple, row=0, custom_id='music_previous_track')
        btn_previous_track.callback = self._previous_track
        self.add_item(btn_previous_track)

        btn_pause_resume = Button(emoji=MUSIC_EMOJIS['pause'], style=discord.ButtonStyle.blurple, row=0, custom_id='music_pause_resume')
        btn_pause_resume.callback = self._pause_resume
        self.add_item(btn_pause_resume)

        btn_stop = Button(emoji=MUSIC_EMOJIS['stop'], style=discord.ButtonStyle.red, row=0, custom_id='music_stop')
        btn_stop.callback = self._stop
        self.add_item(btn_stop)

        btn_next_track = Button(emoji=MUSIC_EMOJIS['next'], style=discord.ButtonStyle.blurple, row=0, custom_id='music_next_track')
        btn_next_track.callback = self._skip
        self.add_item(btn_next_track)

        btn_shuffle = Button(emoji=MUSIC_EMOJIS['shuffle'], style=discord.ButtonStyle.blurple, row=0, custom_id='music_shuffle')
        btn_shuffle.callback = self._shuffle
        self.add_item(btn_shuffle)

        # Row 2: Control and navigation buttons (5 buttons)
        btn_repeat = Button(emoji=MUSIC_EMOJIS['repeat'], style=discord.ButtonStyle.blurple, row=1, custom_id='music_repeat')
        btn_repeat.callback = self._repeat
        self.add_item(btn_repeat)

        btn_volume = Button(emoji=MUSIC_EMOJIS['volume'], style=discord.ButtonStyle.blurple, row=1, custom_id='music_volume')
        btn_volume.callback = self._volume_control
        self.add_item(btn_volume)

        btn_queue = Button(emoji=MUSIC_EMOJIS['queue'], style=discord.ButtonStyle.secondary, row=1, custom_id='music_queue')
        btn_queue.callback = self._show_queue
        self.add_item(btn_queue)

        btn_settings = Button(emoji=MUSIC_EMOJIS['settings'], style=discord.ButtonStyle.secondary, row=1, custom_id='music_settings')
        btn_settings.callback = self._settings
        self.add_item(btn_settings)

        # Help button with custom question emoji
        btn_help = Button(emoji='<:question:1428173442947088486>', style=discord.ButtonStyle.secondary, row=1, custom_id='music_help')
        btn_help.callback = self._help
        self.add_item(btn_help)

        # Row 3: Additional features (5 buttons)
        btn_favorite = Button(emoji=MUSIC_EMOJIS['favorite'], style=discord.ButtonStyle.secondary, row=2, custom_id='music_favorite')
        btn_favorite.callback = self._favorite
        self.add_item(btn_favorite)

        btn_dislike = Button(emoji=MUSIC_EMOJIS['dislike'], style=discord.ButtonStyle.secondary, row=2, custom_id='music_dislike')
        btn_dislike.callback = self._dislike
        self.add_item(btn_dislike)

        btn_save_playlist = Button(emoji=MUSIC_EMOJIS['save_playlist'], style=discord.ButtonStyle.secondary, row=2, custom_id='music_save_playlist')
        btn_save_playlist.callback = self._save_playlist
        self.add_item(btn_save_playlist)

        btn_random = Button(emoji=MUSIC_EMOJIS['random'], style=discord.ButtonStyle.secondary, row=2, custom_id='music_random')
        btn_random.callback = self._random_track
        self.add_item(btn_random)

        btn_disconnect = Button(emoji=MUSIC_EMOJIS['disconnect'], style=discord.ButtonStyle.danger, row=2, custom_id='music_disconnect')
        btn_disconnect.callback = self._disconnect
        self.add_item(btn_disconnect)

    async def update_button_states(self):
        """Update button states based on current music state"""
        try:
            mode, controller = await self.music_cog._get_playback_controller(self.ctx)
            queue = self.music_cog.get_queue(self.ctx.guild.id)
            
            for item in self.children:
                if item.custom_id == 'music_pause_resume':
                    if mode == 'lavalink' and controller:
                        is_paused = getattr(controller, 'paused', False)
                        if is_paused:
                            item.emoji = MUSIC_STATE_EMOJIS['playing']  # Show play button when paused
                            item.style = discord.ButtonStyle.green
                        else:
                            item.emoji = MUSIC_STATE_EMOJIS['paused']   # Show pause button when playing
                            item.style = discord.ButtonStyle.blurple
                elif item.custom_id == 'music_repeat':
                    if queue.loop_mode:
                        item.emoji = MUSIC_STATE_EMOJIS['repeat_on']
                        item.style = discord.ButtonStyle.green
                    else:
                        item.emoji = MUSIC_STATE_EMOJIS['repeat_off']
                        item.style = discord.ButtonStyle.blurple
                elif item.custom_id == 'music_shuffle':
                    # Add shuffle state tracking - for now just use different styles
                    pass
        except Exception as e:
            print(f"[DEBUG] Button state update error: {e}")

    async def _check_permissions(self, interaction: discord.Interaction) -> bool:
        """Check if user has permission to control music"""
        # Allow command author and users in same voice channel
        if interaction.user == self.ctx.author:
            return True
        
        # Check if user is in same voice channel
        if hasattr(interaction.user, 'voice') and interaction.user.voice:
            vc = self.ctx.guild.voice_client
            if vc and vc.channel == interaction.user.voice.channel:
                return True
        
        await interaction.response.send_message('🚫 You need to be in the same voice channel to control the music!', ephemeral=True)
        return False

    async def _previous_track(self, interaction: discord.Interaction):
        if not await self._check_permissions(interaction):
            return
        
        queue = self.music_cog.get_queue(self.ctx.guild.id)
        if not hasattr(queue, 'history') or not queue.history:
            await interaction.response.send_message(f'{MUSIC_EMOJIS["previous"]} No previous tracks in history!', ephemeral=True)
            return
        
        try:
            # Get the previous track from history
            previous_track = queue.history.pop()
            
            # Add current track back to front of queue if playing
            current_track = self.music_cog.current_tracks.get(self.ctx.guild.id)
            if current_track:
                queue.queue.appendleft(current_track)
            
            # Add previous track to front of queue
            queue.queue.appendleft(previous_track)
            
            # Stop current track to trigger next (previous) track
            mode, controller = await self.music_cog._get_playback_controller(self.ctx)
            if mode == 'lavalink' and controller:
                await controller.stop()
            
            await interaction.response.send_message(f'{MUSIC_EMOJIS["previous"]} Playing previous track: **{previous_track.title}**!', ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f'❌ Error playing previous track: {str(e)}', ephemeral=True)

    async def _pause_resume(self, interaction: discord.Interaction):
        if not await self._check_permissions(interaction):
            return
        
        try:
            mode, controller = await self.music_cog._get_playback_controller(self.ctx)
            if mode is None:
                await interaction.response.send_message('❌ No music is currently playing!', ephemeral=True)
                return
            
            if mode == 'lavalink':
                # Check current state using correct Wavelink v4 API
                is_paused = getattr(controller, 'paused', False)
                await controller.pause(not is_paused)
                
                # Update button appearance based on new state
                for item in self.children:
                    if item.custom_id == 'music_pause_resume':
                        if is_paused:  # Was paused, now playing
                            item.emoji = MUSIC_STATE_EMOJIS['paused']
                            item.style = discord.ButtonStyle.green
                            status = f'{MUSIC_EMOJIS["play"]} Resumed'
                        else:  # Was playing, now paused
                            item.emoji = MUSIC_STATE_EMOJIS['playing']
                            item.style = discord.ButtonStyle.blurple
                            status = f'{MUSIC_EMOJIS["pause"]} Paused'
                        break
                
                await interaction.response.edit_message(view=self)
                await interaction.followup.send(f'{status} by **{interaction.user.display_name}**!', ephemeral=True)
            else:
                # Legacy handling
                if hasattr(controller, 'is_paused') and controller.is_paused():
                    if hasattr(controller, 'resume'):
                        controller.resume()
                    # Update button to show pause state
                    for item in self.children:
                        if item.custom_id == 'music_pause_resume':
                            item.emoji = MUSIC_STATE_EMOJIS['paused']
                            item.style = discord.ButtonStyle.green
                            break
                    await interaction.response.edit_message(view=self)
                    await interaction.followup.send(f'{MUSIC_EMOJIS["play"]} Resumed by **{interaction.user.display_name}**!', ephemeral=True)
                else:
                    if hasattr(controller, 'pause'):
                        controller.pause()
                    # Update button to show play state
                    for item in self.children:
                        if item.custom_id == 'music_pause_resume':
                            item.emoji = MUSIC_STATE_EMOJIS['playing']
                            item.style = discord.ButtonStyle.blurple
                            break
                    await interaction.response.edit_message(view=self)
                    await interaction.followup.send(f'{MUSIC_EMOJIS["pause"]} Paused by **{interaction.user.display_name}**!', ephemeral=True)
                    
        except Exception as e:
            print(f"[DEBUG] Pause/Resume error: {e}")
            await interaction.response.send_message(f'❌ Error: {str(e)}', ephemeral=True)

    async def _stop(self, interaction: discord.Interaction):
        if not await self._check_permissions(interaction):
            return
        
        try:
            mode, controller = await self.music_cog._get_playback_controller(self.ctx)
            if mode is None:
                await interaction.response.send_message('❌ No music is currently playing!', ephemeral=True)
                return
            
            if mode == 'lavalink':
                await controller.stop()
            else:
                controller.stop()
            
            # Clear queue
            queue = self.music_cog.get_queue(self.ctx.guild.id)
            queue.clear()
            
            await interaction.response.send_message(f'{MUSIC_EMOJIS["stop"]} Music stopped and queue cleared by **{interaction.user.display_name}**!', ephemeral=True)
                    
        except Exception as e:
            await interaction.response.send_message(f'❌ Error: {str(e)}', ephemeral=True)

    async def _skip(self, interaction: discord.Interaction):
        if not await self._check_permissions(interaction):
            return
        
        try:
            mode, controller = await self.music_cog._get_playback_controller(self.ctx)
            if mode is None:
                await interaction.response.send_message('❌ No music is currently playing!', ephemeral=True)
                return
            
            if mode == 'lavalink':
                await controller.stop()  # This will trigger next track
            else:
                controller.stop()
            
            await interaction.response.send_message(f'{MUSIC_EMOJIS["next"]} Track skipped by **{interaction.user.display_name}**!', ephemeral=True)
                    
        except Exception as e:
            await interaction.response.send_message(f'❌ Error: {str(e)}', ephemeral=True)

    async def _shuffle(self, interaction: discord.Interaction):
        if not await self._check_permissions(interaction):
            return
        
        queue = self.music_cog.get_queue(self.ctx.guild.id)
        if queue.is_empty():
            await interaction.response.send_message('❌ Queue is empty!', ephemeral=True)
            return
        
        queue.shuffle()
        await interaction.response.send_message(f'{MUSIC_EMOJIS["shuffle"]} Queue shuffled by **{interaction.user.display_name}**!', ephemeral=True)

    async def _repeat(self, interaction: discord.Interaction):
        if not await self._check_permissions(interaction):
            return
        
        queue = self.music_cog.get_queue(self.ctx.guild.id)
        queue.loop_mode = not queue.loop_mode
        
        # Update button appearance based on repeat state
        for item in self.children:
            if item.custom_id == 'music_repeat':
                if queue.loop_mode:
                    item.emoji = MUSIC_STATE_EMOJIS['repeat_on']
                    item.style = discord.ButtonStyle.green
                else:
                    item.emoji = MUSIC_STATE_EMOJIS['repeat_off']
                    item.style = discord.ButtonStyle.blurple
                break
        
        status = 'enabled' if queue.loop_mode else 'disabled'
        emoji = MUSIC_EMOJIS['repeat']
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f'{emoji} Loop mode {status} by **{interaction.user.display_name}**!', ephemeral=True)

    async def _show_queue(self, interaction: discord.Interaction):
        queue = self.music_cog.get_queue(self.ctx.guild.id)
        if queue.is_empty():
            await interaction.response.send_message(f'{MUSIC_EMOJIS["queue"]} Queue is empty!', ephemeral=True)
            return
        
        queue_list = []
        for i, track in enumerate(list(queue.queue)[:10], 1):
            duration = f"{track.duration // 60}:{track.duration % 60:02d}" if track.duration else "Unknown"
            requester = track.requester.display_name if track.requester else "Unknown"
            queue_list.append(f"`{i}.` **{track.title}** by {track.author} `[{duration}]` - *Requested by {requester}*")
        
        embed = discord.Embed(
            title=f"{MUSIC_EMOJIS['queue']} Music Queue",
            description="\n".join(queue_list),
            color=0x00E6A7
        )
        if len(queue.queue) > 10:
            embed.set_footer(text=f"Showing 10 of {len(queue.queue)} tracks")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _volume_down(self, interaction: discord.Interaction):
        if not await self._check_permissions(interaction):
            return
        
        try:
            mode, controller = await self.music_cog._get_playback_controller(self.ctx)
            if mode == 'lavalink' and controller:
                # Use correct Wavelink v4 volume API
                current_volume = getattr(controller, 'volume', 40)
                new_volume = max(0, current_volume - 10)
                
                if hasattr(controller, 'set_volume'):
                    await controller.set_volume(new_volume)
                    
                    # Save volume setting for this guild to database
                    guild_id = self.ctx.guild.id
                    await self.music_cog._save_volume_to_db(guild_id, new_volume)
                    
                    await interaction.response.send_message(f'{MUSIC_EMOJIS["volume"]} Volume set to {new_volume}% by **{interaction.user.display_name}**!', ephemeral=True)
                else:
                    await interaction.response.send_message('❌ Volume control not available in this version!', ephemeral=True)
            else:
                await interaction.response.send_message('❌ No active player found!', ephemeral=True)
        except Exception as e:
            print(f"[DEBUG] Volume down error: {e}")
            await interaction.response.send_message(f'❌ Volume control error: {str(e)}', ephemeral=True)

    async def _volume_up(self, interaction: discord.Interaction):
        if not await self._check_permissions(interaction):
            return
        
        try:
            mode, controller = await self.music_cog._get_playback_controller(self.ctx)
            if mode == 'lavalink' and hasattr(controller, 'set_volume'):
                current_volume = getattr(controller, 'volume', 40)
                new_volume = min(200, current_volume + 10)
                await controller.set_volume(new_volume)
                
                # Save volume setting for this guild to database
                guild_id = self.ctx.guild.id
                await self.music_cog._save_volume_to_db(guild_id, new_volume)
                
                await interaction.response.send_message(f'{MUSIC_EMOJIS["volume"]} Volume set to {new_volume}% by **{interaction.user.display_name}**!', ephemeral=True)
            else:
                await interaction.response.send_message('❌ Volume control not available!', ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f'❌ Error: {str(e)}', ephemeral=True)

    async def _disconnect(self, interaction: discord.Interaction):
        if not await self._check_permissions(interaction):
            return
        
        try:
            vc = self.ctx.guild.voice_client
            if vc:
                await vc.disconnect()
                # Clear queue and current track
                queue = self.music_cog.get_queue(self.ctx.guild.id)
                queue.clear()
                self.music_cog.current_tracks.pop(self.ctx.guild.id, None)
                self.music_cog.voice_clients.pop(self.ctx.guild.id, None)
                
                await interaction.response.send_message(f'{MUSIC_EMOJIS["disconnect"]} Disconnected from voice channel by **{interaction.user.display_name}**!', ephemeral=True)
            else:
                await interaction.response.send_message('❌ Not connected to a voice channel!', ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f'❌ Error: {str(e)}', ephemeral=True)

    # New button callback methods for the enhanced interface
    async def _rewind(self, interaction: discord.Interaction):
        """Rewind the current track by 10 seconds"""
        if not await self._check_permissions(interaction):
            return
        await interaction.response.send_message('⏪ Rewind functionality coming soon!', ephemeral=True)

    async def _volume_control(self, interaction: discord.Interaction):
        """Open volume control modal"""
        if not await self._check_permissions(interaction):
            return
        
        try:
            mode, controller = await self.music_cog._get_playback_controller(self.ctx)
            if mode == 'lavalink' and controller:
                # Create and show the volume modal
                modal = VolumeModal(self.music_cog, self.ctx)
                
                # Set current volume from database as default
                guild_id = self.ctx.guild.id
                saved_volume = await self.music_cog._get_volume_for_guild(guild_id)
                modal.volume.default = str(saved_volume)
                
                await interaction.response.send_modal(modal)
            else:
                await interaction.response.send_message('❌ No active player found! Start playing music first.', ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f'❌ Error opening volume control: {str(e)}', ephemeral=True)

    async def _fast_forward(self, interaction: discord.Interaction):
        """Fast forward the current track by 10 seconds"""
        if not await self._check_permissions(interaction):
            return
        await interaction.response.send_message('⏩ Fast forward functionality coming soon!', ephemeral=True)

    async def _settings(self, interaction: discord.Interaction):
        """Open music settings menu"""
        if not await self._check_permissions(interaction):
            return
        
        embed = discord.Embed(
            title=f"{MUSIC_EMOJIS['settings']} Music Settings",
            description="**Available Settings:**\n• Volume Control\n• Repeat Mode\n• Shuffle Mode\n• Audio Quality",
            color=0x00E6A7
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _favorite(self, interaction: discord.Interaction):
        """Add current track to favorites"""
        if not await self._check_permissions(interaction):
            return
        
        current_track = self.music_cog.current_tracks.get(self.ctx.guild.id)
        if current_track:
            await interaction.response.send_message(f'{MUSIC_EMOJIS["favorite"]} Added **{current_track.title}** to favorites!', ephemeral=True)
        else:
            await interaction.response.send_message('❌ No track currently playing!', ephemeral=True)

    async def _dislike(self, interaction: discord.Interaction):
        """Skip current track and add to disliked"""
        if not await self._check_permissions(interaction):
            return
        
        current_track = self.music_cog.current_tracks.get(self.ctx.guild.id)
        if current_track:
            # Skip the track first
            try:
                mode, controller = await self.music_cog._get_playback_controller(self.ctx)
                if mode == 'lavalink':
                    await controller.stop()
                await interaction.response.send_message(f'{MUSIC_EMOJIS["dislike"]} Skipped **{current_track.title}** (disliked)!', ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f'❌ Error: {str(e)}', ephemeral=True)
        else:
            await interaction.response.send_message('❌ No track currently playing!', ephemeral=True)

    async def _save_playlist(self, interaction: discord.Interaction):
        """Save current queue as a playlist"""
        if not await self._check_permissions(interaction):
            return
        
        queue = self.music_cog.get_queue(self.ctx.guild.id)
        if queue.is_empty():
            await interaction.response.send_message('❌ Queue is empty! Cannot save empty playlist.', ephemeral=True)
            return
        
        await interaction.response.send_message(f'{MUSIC_EMOJIS["save_playlist"]} Playlist saved with {len(queue.queue)} tracks!', ephemeral=True)

    async def _random_track(self, interaction: discord.Interaction):
        """Play a random track"""
        if not await self._check_permissions(interaction):
            return
        await interaction.response.send_message(f'{MUSIC_EMOJIS["random"]} Random track functionality coming soon!', ephemeral=True)

    async def _help(self, interaction: discord.Interaction):
        """Show help information about all music control buttons"""
        help_text = f"""
🎵 **Music Player Control Guide** 🎵

**🔵 Row 1 - Main Playback Controls:**
{MUSIC_EMOJIS['previous']} **Previous** - Go to previous track in queue
{MUSIC_EMOJIS['pause']} **Play/Pause** - Toggle playback (play when paused, pause when playing)
{MUSIC_EMOJIS['stop']} **Stop** - Stop playback and clear current track
{MUSIC_EMOJIS['next']} **Next** - Skip to next track in queue
{MUSIC_EMOJIS['shuffle']} **Shuffle** - Randomize the order of tracks in queue

**🔵 Row 2 - Controls & Navigation:**
{MUSIC_EMOJIS['repeat']} **Repeat** - Toggle repeat mode (off/track/queue)
{MUSIC_EMOJIS['volume']} **Volume** - Adjust volume (0-100%)
{MUSIC_EMOJIS['queue']} **Queue** - View current music queue
{MUSIC_EMOJIS['settings']} **Settings** - Advanced music settings
<:question:1428173442947088486> **Help** - Show this help message (you're here!)

**🔵 Row 3 - Additional Features:**
{MUSIC_EMOJIS['favorite']} **Favorite** - Add current track to your favorites
{MUSIC_EMOJIS['dislike']} **Dislike** - Mark track as disliked
{MUSIC_EMOJIS['save_playlist']} **Save Playlist** - Save current queue as a playlist
{MUSIC_EMOJIS['random']} **Random** - Play a random track
{MUSIC_EMOJIS['disconnect']} **Disconnect** - Disconnect bot from voice channel

**💡 Tips:**
• Only users in the same voice channel can control the music
• Queue supports multiple platforms (YouTube, Spotify, SoundCloud)
• Volume changes are saved per server
• Use shuffle before playing for random order
        """
        
        await interaction.response.send_message(help_text.strip(), ephemeral=True)

class Music(Cog):
    def __init__(self, client: sleepless):
        self.client = client
        self.bot = client  # Add alias for compatibility
        self.music_queues: Dict[int, MusicQueue] = {}
        self.voice_clients: Dict[int, discord.VoiceClient] = {}
        self.current_tracks: Dict[int, Track] = {}
        self.guild_volumes: Dict[int, int] = {}  # Store volume per guild (guild_id -> volume)
        self.spotify_api = SpotifyAPI()
        self.inactivity_timeout = 120  # 2 minutes
        self._last_voice_error: Optional[str] = None
        # Per-guild locks to serialize connect attempts and avoid race conditions
        self._connect_locks: Dict[int, asyncio.Lock] = {}
        
        # Track 4006 errors to prevent endless retry loops
        self._guild_4006_errors: Dict[int, float] = {}  # guild_id -> last_4006_time
        self._guild_4006_counts: Dict[int, int] = {}    # guild_id -> consecutive 4006 count
        self._4006_cooldown = 60.0  # Wait 60 seconds after 4006 before retrying (increased for stability)
        # Lavalink (wavelink) integration: optional
        self.use_lavalink = bool(_os.environ.get('USE_LAVALINK'))
        self._lavalink_pool = None
        print(f"[INIT] Music cog initialized. USE_LAVALINK={self.use_lavalink}")
        
        # Initialize volume database
        asyncio.create_task(self._init_volume_db())

    async def _init_volume_db(self):
        """Initialize volume database"""
        try:
            async with aiosqlite.connect("db/music_volumes.db") as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS guild_volumes (
                        guild_id INTEGER PRIMARY KEY,
                        volume INTEGER NOT NULL DEFAULT 40
                    )
                """)
                await db.commit()
                print("[VOLUME] Volume database initialized")
                
                # Load existing volumes into memory
                await self._load_volumes_from_db()
        except Exception as e:
            print(f"[VOLUME] Error initializing volume database: {e}")

    async def _load_volumes_from_db(self):
        """Load all guild volumes from database into memory"""
        try:
            async with aiosqlite.connect("db/music_volumes.db") as db:
                async with db.execute("SELECT guild_id, volume FROM guild_volumes") as cursor:
                    async for row in cursor:
                        self.guild_volumes[row[0]] = row[1]
                print(f"[VOLUME] Loaded {len(self.guild_volumes)} guild volumes from database")
        except Exception as e:
            print(f"[VOLUME] Error loading volumes from database: {e}")

    async def _save_volume_to_db(self, guild_id: int, volume: int):
        """Save guild volume to database"""
        try:
            async with aiosqlite.connect("db/music_volumes.db") as db:
                await db.execute("""
                    INSERT OR REPLACE INTO guild_volumes (guild_id, volume) 
                    VALUES (?, ?)
                """, (guild_id, volume))
                await db.commit()
                self.guild_volumes[guild_id] = volume  # Update memory cache
                print(f"[VOLUME] Saved volume {volume}% for guild {guild_id} to database")
        except Exception as e:
            print(f"[VOLUME] Error saving volume to database: {e}")

    async def _get_volume_for_guild(self, guild_id: int) -> int:
        """Get volume for guild, defaulting to 40% if not found"""
        if guild_id in self.guild_volumes:
            return self.guild_volumes[guild_id]
        
        try:
            async with aiosqlite.connect("db/music_volumes.db") as db:
                async with db.execute("SELECT volume FROM guild_volumes WHERE guild_id = ?", (guild_id,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        volume = row[0]
                        self.guild_volumes[guild_id] = volume  # Cache in memory
                        return volume
        except Exception as e:
            print(f"[VOLUME] Error getting volume from database: {e}")
        
        # Default to 40% if not found
        return 40

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Handle voice state updates"""
        if member.id == self.client.user.id:
            print(f"[VOICE DEBUG] Bot voice state changed:")
            print(f"[VOICE DEBUG] Before: {before.channel}")
            print(f"[VOICE DEBUG] After: {after.channel}")
            await self._handle_voice_state_change(member, before, after)

    # Wavelink event handlers for debugging audio playback
    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload):
        """Called when a track starts playing"""
        print(f"[WAVELINK] Track started: {payload.track.title} by {payload.track.author}")
        print(f"[WAVELINK] Player: {payload.player}, Guild: {getattr(payload.player, 'guild', 'unknown')}")
        
        # Restore guild volume setting when a new track starts
        if payload.player and hasattr(payload.player, 'guild'):
            guild_id = payload.player.guild.id
            saved_volume = await self._get_volume_for_guild(guild_id)
            
            try:
                current_volume = getattr(payload.player, 'volume', 40)
                if current_volume != saved_volume:
                    if hasattr(payload.player, 'set_volume'):
                        await payload.player.set_volume(saved_volume)
                        print(f"[VOLUME] Restored volume to {saved_volume}% for guild {guild_id}")
                    else:
                        print(f"[VOLUME] Unable to restore volume - set_volume method not available")
                else:
                    print(f"[VOLUME] Volume already at saved level {saved_volume}% for guild {guild_id}")
            except Exception as e:
                print(f"[VOLUME] Error restoring volume for guild {guild_id}: {e}")
                # If there's an error, ensure default volume is set
                try:
                    if hasattr(payload.player, 'set_volume'):
                        await payload.player.set_volume(40)
                        await self._save_volume_to_db(guild_id, 40)
                        print(f"[VOLUME] Set default volume 40% for guild {guild_id}")
                except Exception as e2:
                    print(f"[VOLUME] Error setting default volume for guild {guild_id}: {e2}")

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        """Called when a track ends"""
        print(f"[WAVELINK] Track ended: {payload.track.title}, Reason: {payload.reason}")
        
        # Auto-play next track if queue has items
        if payload.player and hasattr(payload.player, 'guild'):
            guild_id = payload.player.guild.id
            queue = self.get_queue(guild_id)
            print(f"[WAVELINK] Queue has {len(queue.queue)} tracks remaining")
            
            if not queue.is_empty():
                next_track = queue.get_next()
                if next_track:
                    print(f"[WAVELINK] Playing next track: {next_track.title}")
                    try:
                        # Direct Lavalink playback without context dependency
                        await self._play_track_direct_lavalink(payload.player, next_track, guild_id)
                    except Exception as e:
                        print(f"[WAVELINK] Failed to auto-play next track: {e}")
                        # Fallback: Try with mock context
                        try:
                            channel = payload.player.channel
                            if channel:
                                guild = payload.player.guild
                                # Find a member in the voice channel to use as context
                                member = None
                                for m in channel.members:
                                    if not m.bot:
                                        member = m
                                        break
                                
                                if member and guild:
                                    # Create minimal context for auto-play
                                    class MockContext:
                                        def __init__(self, guild, author, channel, client):
                                            self.guild = guild
                                            self.author = author
                                            self.bot = client
                                            self.client = client  # Add missing client attribute
                                            self.voice_client = payload.player
                                            self.channel = channel
                                            self.send = channel.send  # Add send method
                                    
                                    mock_ctx = MockContext(guild, member, channel, self.client)
                                    await self._play_via_lavalink(mock_ctx, next_track, payload.player)
                        except Exception as fallback_error:
                            print(f"[WAVELINK] Fallback auto-play also failed: {fallback_error}")
                else:
                    print(f"[WAVELINK] No next track returned from queue")
            else:
                # Queue is empty - clean up current track tracking
                self.current_tracks.pop(guild_id, None)
                print(f"[WAVELINK] Queue ended for guild {guild_id}, cleaned up current track")
        else:
            print(f"[WAVELINK] No player or guild in payload")

    @commands.Cog.listener()
    async def on_wavelink_track_exception(self, payload: wavelink.TrackExceptionEventPayload):
        """Called when a track encounters an exception"""
        print(f"[WAVELINK] Track exception: {payload.track.title}")
        print(f"[WAVELINK] Exception: {payload.exception}")
        
        # Track recent errors for better user feedback
        if not hasattr(self, '_recent_errors'):
            self._recent_errors = []
        
        exception_msg = str(payload.exception.get('message', ''))
        self._recent_errors.append(exception_msg)
        
        # Keep only last 5 errors to avoid memory bloat
        if len(self._recent_errors) > 5:
            self._recent_errors = self._recent_errors[-5:]
        
        # Check exception type and provide appropriate response
        is_glibc_error = 'GLIBC' in exception_msg or 'libconnector.so' in exception_msg
        is_unavailable = 'unavailable' in exception_msg.lower() or 'not available' in exception_msg.lower()
        is_timeout = 'timeout' in exception_msg.lower() or 'timed out' in exception_msg.lower()
        is_youtube_cipher = any(keyword in exception_msg.lower() for keyword in ['cipher', 'signature', 'script extraction', 'must find sig function'])
        
        if is_youtube_cipher:
            print(f"[WAVELINK] YouTube cipher/signature error detected - plugin needs updating")
        elif is_glibc_error:
            print(f"[WAVELINK] GLIBC compatibility issue detected - trying alternative source")
            # Count GLIBC errors for better user feedback
            if not hasattr(self, '_last_glibc_error_count'):
                self._last_glibc_error_count = 0
            self._last_glibc_error_count += 1
        elif is_unavailable:
            print(f"[WAVELINK] Video unavailable, this is expected for geo-blocked content")
        elif is_timeout:
            print(f"[WAVELINK] Network timeout occurred, will try next track")
        else:
            print(f"[WAVELINK] Unexpected track exception: {exception_msg}")
        
        # Auto-play next track when current track fails
        if payload.player and hasattr(payload.player, 'guild'):
            guild_id = payload.player.guild.id
            queue = self.get_queue(guild_id)
            print(f"[WAVELINK] Track failed, queue has {len(queue.queue)} tracks remaining")
            
            # For GLIBC errors, try to find alternative sources for the same track
            if is_glibc_error and hasattr(payload, 'track'):
                try:
                    print(f"[WAVELINK] Searching for alternative source for: {payload.track.title}")
                    alternative_tracks = await self._find_alternative_sources(payload.track.title)
                    if alternative_tracks:
                        best_playable = alternative_tracks[0]
                        print(f"[WAVELINK] Found alternative: {best_playable.title} from {getattr(best_playable, 'source', 'unknown')}")
                        
                        # Convert Wavelink Playable to our Track format
                        duration = 0
                        try:
                            duration = best_playable.length // 1000 if hasattr(best_playable, 'length') and best_playable.length else 0
                        except:
                            try:
                                duration = best_playable.duration // 1000 if hasattr(best_playable, 'duration') and best_playable.duration else 0
                            except:
                                duration = 0
                        
                        track_data = {
                            'title': getattr(best_playable, 'title', 'Unknown') or 'Unknown',
                            'url': getattr(best_playable, 'uri', '') or '',
                            'webpage_url': getattr(best_playable, 'uri', '') or '',
                            'duration': duration,
                            'thumbnail': getattr(best_playable, 'artwork', '') or getattr(best_playable, 'thumbnail', '') or '',
                            'uploader': getattr(best_playable, 'author', 'Unknown') or 'Unknown',
                            'extractor': 'lavalink_alternative'
                        }
                        best_track = Track(track_data, None)
                        best_track._wavelink_playable = best_playable  # Store original for playback
                        
                        await self._play_track_direct_lavalink(payload.player, best_track, guild_id)
                        
                        # Send notification about using alternative source
                        try:
                            guild = payload.player.guild
                            if guild:
                                for text_channel in guild.text_channels:
                                    if text_channel.permissions_for(guild.me).send_messages:
                                        embed = discord.Embed(
                                            description=f"🔧 **Server Issue Detected** - Using alternative source\n🎵 **Now Playing:** {best_track.title}",
                                            color=0xFFA500
                                        )
                                        await text_channel.send(embed=embed)
                                        break
                        except Exception:
                            pass
                        return
                except Exception as e:
                    print(f"[WAVELINK] Failed to find alternative source: {e}")
            
            if not queue.is_empty():
                next_track = queue.get_next()
                if next_track:
                    print(f"[WAVELINK] Trying next track due to failure: {next_track.title}")
                    try:
                        # Direct Lavalink playback without context dependency
                        await self._play_track_direct_lavalink(payload.player, next_track, guild_id)
                    except Exception as e:
                        print(f"[WAVELINK] Failed to auto-play next track after exception: {e}")
                        # Try to notify about the failure if possible
                        try:
                            guild = payload.player.guild
                            if guild:
                                # Find a text channel to send notification
                                for text_channel in guild.text_channels:
                                    if text_channel.permissions_for(guild.me).send_messages:
                                        error_type = "🔧 Server Issue" if is_glibc_error else "❌ Track Failed"
                                        embed = discord.Embed(
                                            description=f"{error_type}: {payload.track.title}\n🎵 **Trying Next:** {next_track.title}",
                                            color=0xFF0000
                                        )
                                        await text_channel.send(embed=embed)
                                        break
                        except Exception:
                            pass
                else:
                    print(f"[WAVELINK] No next track available after exception")
            else:
                # Queue is empty after failure - clean up
                self.current_tracks.pop(guild_id, None)
                print(f"[WAVELINK] Queue empty after track failure for guild {guild_id}")
                # Notify about the failure
                try:
                    guild = payload.player.guild
                    if guild:
                        for text_channel in guild.text_channels:
                            if text_channel.permissions_for(guild.me).send_messages:
                                embed = discord.Embed(
                                    description=f"❌ **Track Failed:** {payload.track.title}\n🎵 Queue ended.",
                                    color=0xFF0000
                                )
                                await text_channel.send(embed=embed)
                                break
                except Exception:
                    pass

    @commands.Cog.listener()
    async def on_wavelink_track_stuck(self, payload: wavelink.TrackStuckEventPayload):
        """Called when a track gets stuck"""
        print(f"[WAVELINK] Track stuck: {payload.track.title}, Threshold: {payload.threshold}ms")

    @commands.Cog.listener()  
    async def on_wavelink_websocket_closed(self, payload: wavelink.WebsocketClosedEventPayload):
        """Called when WebSocket connection closes"""
        print(f"[WAVELINK] WebSocket closed: Code {payload.code}, Reason: {payload.reason}, By Remote: {payload.by_remote}")
        
        # Special handling for Discord voice error 4006
        if payload.code == 4006:
            print("[WAVELINK] Error 4006 detected - Discord voice gateway session invalidated")
            if hasattr(payload, 'player') and payload.player:
                guild = payload.player.guild
                if guild:
                    print(f"[WAVELINK] Recording 4006 error for guild {guild.id}")
                    self._record_4006_error(guild.id)
                    
                    # Aggressive cleanup for 4006 errors
                    try:
                        # Stop the player first
                        if payload.player.connected:
                            await payload.player.stop()
                            await payload.player.disconnect()
                        
                        # Force disconnect voice client
                        if guild.voice_client:
                            await guild.voice_client.disconnect(force=True)
                            
                        # Clean up our tracking
                        if guild.id in self.voice_clients:
                            del self.voice_clients[guild.id]
                            
                        print(f"[WAVELINK] Completed aggressive cleanup for 4006 error in guild {guild.id}")
                    except Exception as e:
                        print(f"[WAVELINK] Error during 4006 cleanup: {e}")
        
        # Handle other serious WebSocket errors
        elif payload.code in [4014, 4015]:  # Voice channel deleted or moved
            print(f"[WAVELINK] Voice channel issue (code {payload.code})")
            if hasattr(payload, 'player') and payload.player and payload.player.guild:
                guild = payload.player.guild
                if guild.id in self.voice_clients:
                    del self.voice_clients[guild.id]

    async def _handle_voice_state_change(self, member, before, after):
        """Handle bot voice state changes for cleanup"""
        if member.id == self.client.user.id:
            if before.channel and not after.channel:
                print("[VOICE DEBUG] Bot disconnected from voice channel")
                # Clean up voice client
                if before.channel.guild.id in self.voice_clients:
                    del self.voice_clients[before.channel.guild.id]
            elif not before.channel and after.channel:
                print(f"[VOICE DEBUG] Bot connected to voice channel: {after.channel.name}")
                self.voice_clients[after.channel.guild.id] = member.guild.voice_client

    def _is_guild_4006_blocked(self, guild_id: int) -> bool:
        """Check if guild has recent 4006 errors and should wait before retrying with exponential backoff"""
        last_4006_time = self._guild_4006_errors.get(guild_id)
        if last_4006_time:
            error_count = self._guild_4006_counts.get(guild_id, 1)
            backoff_time = min(self._4006_cooldown * (2 ** (error_count - 1)), 480.0)
            time_since_4006 = time.time() - last_4006_time
            
            if time_since_4006 < backoff_time:
                remaining = backoff_time - time_since_4006
                print(f"[VOICE] Guild {guild_id} has 4006 error #{error_count}, waiting {remaining:.1f}s more")
                return True
            else:
                # Reset counter after successful wait period
                if guild_id in self._guild_4006_counts:
                    del self._guild_4006_counts[guild_id]
                print(f"[VOICE] Guild {guild_id} cleared 4006 cooldown after {backoff_time:.1f}s")
                    
        return False
    
    def _record_4006_error(self, guild_id: int):
        """Record a 4006 error for the guild with exponential backoff for repeated errors"""
        current_time = time.time()
        
        # Count consecutive 4006 errors
        last_error_time = self._guild_4006_errors.get(guild_id, 0)
        if current_time - last_error_time < 300:  # Within 5 minutes = consecutive error
            self._guild_4006_counts[guild_id] = self._guild_4006_counts.get(guild_id, 0) + 1
        else:
            self._guild_4006_counts[guild_id] = 1  # Reset counter for isolated errors
            
        self._guild_4006_errors[guild_id] = current_time
        error_count = self._guild_4006_counts[guild_id]
        
        # Exponential backoff: 60s, 120s, 240s, 480s (max 8 minutes)
        backoff_time = min(self._4006_cooldown * (2 ** (error_count - 1)), 480.0)
        
        print(f"[VOICE] Recorded 4006 error #{error_count} for guild {guild_id}, blocking for {backoff_time:.1f}s")
        
        # Clear queue and stop player if this is a repeated 4006 error
        if hasattr(self, 'music_queues') and guild_id in self.music_queues:
            queue = self.music_queues[guild_id]
            if queue.current_track or len(queue.tracks) > 0:
                print(f"[VOICE] Clearing queue for guild {guild_id} due to 4006 error #{error_count}")
                queue.clear()
                queue.current_track = None

    def _get_valid_voice_client(self, guild) -> Optional[discord.VoiceClient]:
        """Standardized method to check if guild has a valid voice connection"""
        print(f"[VOICE DEBUG] Checking for valid voice client in guild {guild.id}")
        
        # Check guild voice client first (this is the most reliable)
        vc = getattr(guild, 'voice_client', None)
        print(f"[VOICE DEBUG] Guild voice client: {vc}")
        if vc and self._is_voice_client_connected(vc):
            print(f"[VOICE DEBUG] Guild voice client is valid")
            # Update our mapping if we found a valid one
            self.voice_clients[guild.id] = vc
            return vc
        
        # Check stored mapping
        vc = self.voice_clients.get(guild.id)
        print(f"[VOICE DEBUG] Stored voice client: {vc}")
        if vc and self._is_voice_client_connected(vc):
            print(f"[VOICE DEBUG] Stored voice client is valid")
            return vc
        
        # Try to find Wavelink player from pool if available
        if WAVELINK_AVAILABLE and self._lavalink_pool:
            print(f"[VOICE DEBUG] Searching Wavelink pool for player...")
            try:
                # For wavelink v3.4.1, try to get player directly
                if hasattr(wavelink, 'Pool'):
                    try:
                        player = wavelink.Pool.get_player(guild.id)
                        print(f"[VOICE DEBUG] Pool player: {player}")
                        if player and self._is_voice_client_connected(player):
                            print(f"[VOICE] Found Wavelink player from pool for guild {guild.id}")
                            self.voice_clients[guild.id] = player
                            return player
                    except Exception as e:
                        print(f"[VOICE DEBUG] Pool.get_player failed: {e}")
                
                # Alternative: check nodes
                pool_nodes = []
                if hasattr(self._lavalink_pool, 'nodes'):
                    nodes_attr = getattr(self._lavalink_pool, 'nodes')
                    if hasattr(nodes_attr, 'values'):
                        pool_nodes = list(nodes_attr.values())
                    elif hasattr(nodes_attr, '__iter__'):
                        pool_nodes = list(nodes_attr)
                
                print(f"[VOICE DEBUG] Found {len(pool_nodes)} nodes to check")
                for i, node in enumerate(pool_nodes):
                    try:
                        if hasattr(node, 'get_player'):
                            player = node.get_player(guild.id)
                            print(f"[VOICE DEBUG] Node {i} player: {player}")
                            if player and self._is_voice_client_connected(player):
                                print(f"[VOICE] Found Wavelink player from node for guild {guild.id}")
                                self.voice_clients[guild.id] = player
                                return player
                    except Exception as e:
                        print(f"[VOICE DEBUG] Node {i} get_player failed: {e}")
                        continue
            except Exception as e:
                print(f"[VOICE] Error looking up Wavelink player: {e}")
        
        # Clean up invalid mapping
        self.voice_clients.pop(guild.id, None)
        print(f"[VOICE DEBUG] No valid voice client found for guild {guild.id}")
        return None
    
    def _is_voice_client_connected(self, vc) -> bool:
        """Standardized method to check voice client connection state"""
        if not vc:
            print(f"[VOICE DEBUG] Voice client is None")
            return False
        
        try:
            print(f"[VOICE DEBUG] Checking connection for: {type(vc)}")
            
            # Handle Wavelink Player (priority check)
            if hasattr(vc, 'connected') and not callable(vc.connected):
                # For Wavelink v3.x, connected is a property
                connected_state = bool(vc.connected)
                has_channel = hasattr(vc, 'channel') and vc.channel
                print(f"[VOICE DEBUG] Wavelink player - connected: {connected_state}, has_channel: {has_channel}")
                if connected_state and has_channel:
                    return True
                    
            # Handle standard VoiceClient
            if hasattr(vc, 'is_connected') and callable(vc.is_connected):
                connected = vc.is_connected()
                print(f"[VOICE DEBUG] Standard VoiceClient - is_connected(): {connected}")
                return connected
            
            # Fallback: check if has channel and node (for Wavelink)
            if hasattr(vc, 'channel') and hasattr(vc, 'node'):
                has_channel = bool(vc.channel)
                print(f"[VOICE DEBUG] Wavelink fallback - has_channel: {has_channel}")
                return has_channel
            
            # Final fallback: if has channel, assume connected
            has_channel = bool(getattr(vc, 'channel', None))
            print(f"[VOICE DEBUG] Final fallback - has_channel: {has_channel}")
            return has_channel
        except Exception as e:
            print(f"[VOICE] Error checking connection state: {e}")
            return False

    def get_queue(self, guild_id: int) -> MusicQueue:
        """Get or create a queue for a guild"""
        if guild_id not in self.music_queues:
            self.music_queues[guild_id] = MusicQueue()
        return self.music_queues[guild_id]

    async def _ensure_voice_client(self, ctx: Context, channel=None, reconnect_attempts: int = 1) -> Optional[discord.VoiceClient]:
        """Ensure we have a usable voice client for the guild. Enhanced stability and error handling."""
        guild = ctx.guild
        if not guild:
            return None
            
        # Check if guild is blocked due to recent 4006 errors
        if self._is_guild_4006_blocked(guild.id):
            return None

        # obtain or create a per-guild connect lock
        lock = self._connect_locks.get(guild.id)
        if lock is None:
            lock = asyncio.Lock()
            self._connect_locks[guild.id] = lock

        # Serialize connect attempts to avoid concurrent connect races
        async with lock:
            # Use standardized connection check
            vc = self._get_valid_voice_client(guild)
            if vc:
                print(f"[VOICE] Found valid existing voice client for {guild.name}")
                self.voice_clients[guild.id] = vc
                return vc

            # If no valid connection exists, try to connect once
            target_channel = channel or (ctx.author.voice.channel if getattr(ctx.author, 'voice', None) else None)
            if not target_channel:
                return None

            # Check bot permissions in the target channel
            bot_member = guild.get_member(ctx.bot.user.id)
            if not bot_member:
                print(f"[VOICE] Could not find bot member in guild {guild.name}")
                return None

            channel_perms = target_channel.permissions_for(bot_member)
            if not channel_perms.connect:
                print(f"[VOICE] Missing CONNECT permission in {target_channel.name}")
                return None
            if not channel_perms.speak:
                print(f"[VOICE] Missing SPEAK permission in {target_channel.name}")
                
            # Check if channel is full
            if target_channel.user_limit > 0 and len(target_channel.members) >= target_channel.user_limit:
                if not channel_perms.move_members:
                    print(f"[VOICE] Channel {target_channel.name} is full and bot lacks MOVE_MEMBERS permission")
                    return None

            # Clean up any existing invalid connections first
            existing_vc = getattr(guild, 'voice_client', None)
            if existing_vc and not self._is_voice_client_connected(existing_vc):
                try:
                    print(f"[VOICE] Cleaning up invalid existing connection")
                    await existing_vc.disconnect(force=True)
                    await asyncio.sleep(1.0)  # Wait for cleanup
                except Exception as e:
                    print(f"[VOICE] Error during cleanup: {e}")

            # Single connection attempt with improved stability
            try:
                print(f"[VOICE] Attempting to connect to {target_channel.name}")
                
                vc = None
                timeout = 15  # Increased timeout for stability
                
                # First try Wavelink if available and properly configured
                if WAVELINK_AVAILABLE:
                    try:
                        # Check if Wavelink Pool is properly connected
                        if hasattr(wavelink.Pool, 'nodes') and wavelink.Pool.nodes:
                            print(f"[VOICE] Attempting Wavelink connection...")
                            vc = await target_channel.connect(cls=wavelink.Player, timeout=timeout)
                            
                            if vc and hasattr(vc, 'connected') and vc.connected:
                                print(f"[VOICE] Wavelink Player connected successfully to {target_channel.name}")
                                # Wait for voice session to stabilize
                                await asyncio.sleep(2.0)
                                self.voice_clients[guild.id] = vc
                                return vc
                            else:
                                print(f"[VOICE] Wavelink connection invalid, trying fallback")
                                if vc:
                                    try:
                                        await vc.disconnect(force=True)
                                    except:
                                        pass
                                vc = None
                        else:
                            print(f"[VOICE] Wavelink Pool not ready, using fallback")
                    except Exception as wavelink_error:
                        print(f"[VOICE] Wavelink connection failed: {wavelink_error}")
                        # Check for 4006 in wavelink error
                        if '4006' in str(wavelink_error):
                            self._record_4006_error(guild.id)
                            return None
                        # Clean up failed Wavelink connection
                        if vc:
                            try:
                                await vc.disconnect(force=True)
                            except:
                                pass
                        vc = None
                
                # Fallback to Discord.py voice client if Wavelink failed or unavailable
                if not vc:
                    try:
                        print(f"[VOICE] Using Discord.py voice client fallback")
                        if VOICE_HELPER_AVAILABLE:
                            vc = await safe_voice_connect(target_channel, timeout=timeout, max_retries=2)
                        else:
                            vc = await target_channel.connect(timeout=timeout, reconnect=False)
                        
                        if vc and vc.is_connected():
                            print(f"[VOICE] Discord.py voice client connected to {target_channel.name}")
                            # Wait for voice session to stabilize
                            await asyncio.sleep(2.0)
                            self.voice_clients[guild.id] = vc
                            return vc
                        else:
                            print(f"[VOICE] Discord.py connection failed or invalid")
                            if vc:
                                try:
                                    await vc.disconnect(force=True)
                                except:
                                    pass
                            return None
                            
                    except discord.errors.ConnectionClosed as e:
                        if hasattr(e, 'code') and e.code == 4006:
                            print(f"[VOICE] 4006 error during fallback connection, blocking guild {guild.id}")
                            self._record_4006_error(guild.id)
                            return None
                        else:
                            print(f"[VOICE] Discord connection error: {e}")
                            return None
                    except Exception as e:
                        print(f"[VOICE] Fallback connection error: {e}")
                        # Check if this is a 4006 buried in another exception
                        if '4006' in str(e):
                            self._record_4006_error(guild.id)
                        return None
                        
            except Exception as e:
                print(f"[VOICE] Unexpected connection error: {e}")
                # Check if this is a 4006 buried in another exception
                if '4006' in str(e):
                    self._record_4006_error(guild.id)
                self.voice_clients.pop(guild.id, None)
                self._last_voice_error = str(e)
                return None

        return None

    def _cleanup_downloads(self, downloads_dir: str = 'downloads', max_age_seconds: int = 60*60*24, max_files: int = 200):
        """Remove old downloaded files to prevent disk growth.
        - max_age_seconds: TTL for files (default 24 hours)
        - max_files: keep most recent N files, delete older beyond this count
        """
        try:
            if not os.path.exists(downloads_dir):
                return

            # Gather files with their modification times
            files = []
            for fname in os.listdir(downloads_dir):
                fpath = os.path.join(downloads_dir, fname)
                if os.path.isfile(fpath):
                    try:
                        mtime = os.path.getmtime(fpath)
                        files.append((fpath, mtime))
                    except Exception:
                        continue

            if not files:
                return

            # Delete files older than TTL and build kept_files list
            now = time.time()
            kept_files = []
            for fpath, mtime in files:
                if now - mtime > max_age_seconds:
                    try:
                        os.remove(fpath)
                        print(f"[CLEANUP] Removed old download: {fpath}")
                    except Exception:
                        continue
                else:
                    kept_files.append((fpath, mtime))

            # Enforce max_files by keeping the most recent files
            kept_files = sorted(kept_files, key=lambda x: x[1], reverse=True)
            if len(kept_files) > max_files:
                for fpath, _ in kept_files[max_files:]:
                    try:
                        os.remove(fpath)
                        print(f"[CLEANUP] Removed excess download: {fpath}")
                    except Exception:
                        continue
        except Exception as e:
            print(f"[CLEANUP] Error during cleanup: {str(e)}")

    async def search_and_download_track(self, query: str, source: str = "ytsearch") -> Optional[Track]:
        """Search for a track and download it using yt-dlp"""
        # If Lavalink is enabled and downloads are explicitly disabled, refuse to proceed
        if self.use_lavalink and not bool(_os.environ.get('ALLOW_DOWNLOAD_FALLBACK', '1')):
            print('[ERROR] search_and_download_track called while USE_LAVALINK active and ALLOW_DOWNLOAD_FALLBACK=0')
            return None

        loop = asyncio.get_event_loop()
        
        # Create downloads directory if it doesn't exist
        downloads_dir = "downloads"
        if not os.path.exists(downloads_dir):
            os.makedirs(downloads_dir)
        
        # Try multiple search strategies in order of preference
        search_strategies = [
            # Strategy 1: SoundCloud (most reliable)
            {
                'name': 'SoundCloud',
                'options': {
                    **YTDL_OPTIONS,
                    'default_search': 'scsearch'
                },
                'search_prefix': 'scsearch'
            },
            # Strategy 2: YouTube with minimal options
            {
                'name': 'SoundCloud',
                'options': {
                    **YTDL_OPTIONS,
                    'default_search': 'scsearch'
                },
                'search_prefix': 'scsearch'
            },
            # Strategy 3: Bandcamp
            {
                'name': 'Bandcamp',
                'options': {
                    **YTDL_OPTIONS,
                    'default_search': 'auto'
                },
                'search_prefix': 'auto'
            }
        ]
        
        # Clean the query
        query = query.strip()
        
        for i, strategy in enumerate(search_strategies, 1):
            try:
                ytdl = yt_dlp.YoutubeDL(strategy['options'])
                
                # If it's already a URL, use it directly
                if query.startswith(('http', 'www')):
                    search_query = query
                else:
                    search_query = f"{strategy['search_prefix']}:{query}"
                
                print(f"[DEBUG] Strategy {i} ({strategy['name']}): Searching and downloading: {search_query}")
                
                # Extract info first (without downloading)
                info_options = {**strategy['options']}
                info_options['noplaylist'] = True
                del info_options['outtmpl']  # Remove download template for info extraction
                info_options['extractaudio'] = False
                
                info_ytdl = yt_dlp.YoutubeDL(info_options)
                info_data = await loop.run_in_executor(None, lambda: info_ytdl.extract_info(search_query, download=False))
                
                if not info_data:
                    print(f"[DEBUG] Strategy {i}: No info data returned")
                    continue
                
                # Get the track entry
                track_entry = None
                if 'entries' in info_data and info_data['entries']:
                    track_entry = info_data['entries'][0]
                elif info_data.get('title'):
                    track_entry = info_data
                
                if not track_entry or not track_entry.get('title'):
                    print(f"[DEBUG] Strategy {i}: No valid track entry found")
                    continue
                
                print(f"[DEBUG] Strategy {i}: Found track: {track_entry.get('title', 'Unknown')}")
                
                # Now download the track
                download_url = track_entry.get('webpage_url') or track_entry.get('url')
                if not download_url:
                    print(f"[DEBUG] Strategy {i}: No download URL found")
                    continue
                
                # Download the audio file
                download_data = await loop.run_in_executor(None, lambda: ytdl.extract_info(download_url, download=True))
                
                if download_data:
                    # Find the downloaded file
                    filename = ytdl.prepare_filename(download_data)
                    
                    # yt-dlp might change the extension due to post-processing or original format
                    if not os.path.exists(filename):
                        base, _ = os.path.splitext(filename)
                        for ext in ['.mp3', '.opus', '.m4a', '.webm', '.mp4', '.wav']:
                            alt_filename = base + ext
                            if os.path.exists(alt_filename):
                                filename = alt_filename
                                break
                    
                    if os.path.exists(filename):
                        print(f"[DEBUG] Strategy {i}: Successfully downloaded to: {filename}")
                        # Cleanup old downloads asynchronously
                        try:
                            # Run cleanup in thread to avoid blocking event loop
                            threading.Thread(target=self._cleanup_downloads, daemon=True).start()
                        except Exception:
                            pass
                        # If a file server is enabled for Lavalink, expose an HTTP URL
                        use_files = bool(_os.environ.get('USE_LAVALINK_FILES'))
                        if use_files:
                            host = _os.environ.get('LAVALINK_FILES_HOST', '127.0.0.1')
                            port = int(_os.environ.get('LAVALINK_FILES_PORT', '8765'))
                            # Build a file URL path: /files/<basename>
                            url_path = os.path.basename(filename)
                            http_url = f"http://{host}:{port}/files/{url_path}"
                            # Set webpage_url so Lavalink can fetch via HTTP
                            track_entry['webpage_url'] = http_url
                            # Return Track without local_file so lavalink path will use the HTTP URL
                            return Track(track_entry, None, None)
                        return Track(track_entry, None, filename)
                    else:
                        print(f"[DEBUG] Strategy {i}: Downloaded file not found: {filename}")
                        continue
                
            except Exception as e:
                error_msg = str(e)
                print(f"[ERROR] Strategy {i} ({strategy['name']}) failed: {error_msg[:100]}...")
                continue
        
        print(f"[ERROR] All download strategies failed for query: {query}")
        return None

    async def search_track(self, query: str, source: str = "ytsearch") -> Optional[dict]:
        """Legacy method - now redirects to search_and_download_track"""
        track = await self.search_and_download_track(query, source)
        if track:
            return {
                'title': track.title,
                'url': track.url,
                'webpage_url': track.webpage_url,
                'duration': track.duration,
                'thumbnail': track.thumbnail,
                'uploader': track.author,
                'extractor': track.extractor
            }
        return None

    async def search_tracks(self, query: str, source: str = "ytmsearch") -> List[Track]:
        """Search for multiple tracks (for search command) with enhanced matching"""
        # If Lavalink is enabled prefer to use wavelink search APIs
        if self.use_lavalink and WAVELINK_AVAILABLE:

            # Ensure pool exists
            pool_ok = True if self._lavalink_pool else await self._ensure_lavalink_pool()
            if not pool_ok or not self._lavalink_pool:
                print('[ERROR] Lavalink pool not available for search')
                return []

            try:
                # Enhanced search query preprocessing
                search_queries = self._generate_search_queries(query, source)
                all_tracks = []
                
                for search_query in search_queries:
                    try:
                        print(f"[DEBUG] Lavalink v4 searching: {search_query}")
                        # Use Wavelink v4 search API
                        results = await Playable.search(search_query, source=TrackSource.YouTube if source != "scsearch" else TrackSource.SoundCloud)
                        print(f"[DEBUG] Wavelink v4 search returned: {len(results) if results else 0} results")

                        if results:
                            for playable in results[:5]:  # Limit to 5 results per query
                                try:
                                    # Convert Wavelink Playable to our Track format - handle different attribute names
                                    duration = 0
                                    try:
                                        duration = playable.length // 1000 if hasattr(playable, 'length') and playable.length else 0
                                    except:
                                        try:
                                            duration = playable.duration // 1000 if hasattr(playable, 'duration') and playable.duration else 0
                                        except:
                                            duration = 0
                                    
                                    data = {
                                        'title': getattr(playable, 'title', 'Unknown') or 'Unknown',
                                        'webpage_url': getattr(playable, 'uri', '') or '',
                                        'duration': duration,
                                        'thumbnail': getattr(playable, 'artwork', '') or getattr(playable, 'thumbnail', '') or '',
                                        'uploader': getattr(playable, 'author', 'Unknown') or 'Unknown',
                                        'extractor': 'lavalink_v4'
                                    }
                                    
                                    # Score and filter results for relevance
                                    track = Track(data, None)
                                    relevance_score = self._calculate_relevance_score(query, track)
                                    track.relevance_score = relevance_score
                                    all_tracks.append(track)
                                    print(f"[DEBUG] Successfully converted track: {data['title']} ({duration}s)")
                                    
                                except Exception as e:
                                    print(f"[DEBUG] Error converting playable to track: {e}")
                                    # Debug - show available attributes
                                    print(f"[DEBUG] Playable attributes: {dir(playable)}")
                                    continue
                                    
                        # If we got good results from first query, don't try more
                        if len([t for t in all_tracks if t.relevance_score > 0.7]) >= 3:
                            break
                            
                    except Exception as e:
                        print(f"[DEBUG] Search query failed: {search_query}, error: {e}")
                        continue

                # Sort by relevance score and return best results
                all_tracks.sort(key=lambda t: getattr(t, 'relevance_score', 0), reverse=True)
                best_tracks = all_tracks[:5]  # Return top 5 most relevant
                
                print(f"[DEBUG] Returning {len(best_tracks)} enhanced search results")
                return best_tracks
                
            except Exception as e:
                print(f"[ERROR] Enhanced Lavalink search failed: {e}")
                return []

        # Fallback (non-lavalink) legacy behavior retained for environments not using Lavalink
        loop = asyncio.get_event_loop()
        # Use info-only extraction for search results (no download)
        search_options = {
            'quiet': True,
            'no_warnings': True,
            'extractaudio': False,
            'noplaylist': True,
            'default_search': source,
            'playlistend': 10  # Increased to get more options for filtering
        }
        
        try:
            # Clean the query with enhanced preprocessing
            search_queries = self._generate_search_queries(query, source)
            all_tracks = []
            
            for search_query in search_queries:
                print(f"[DEBUG] Searching tracks for: {search_query}")
                ytdl = yt_dlp.YoutubeDL(search_options)
                data = await loop.run_in_executor(None, lambda: ytdl.extract_info(search_query, download=False))
                
                if data and 'entries' in data:
                    for entry in data['entries'][:5]:  # Process first 5 results
                        if entry:
                            try:
                                track = Track(entry, None)
                                relevance_score = self._calculate_relevance_score(query, track)
                                track.relevance_score = relevance_score
                                all_tracks.append(track)
                            except Exception as e:
                                print(f"[DEBUG] Error creating track: {e}")
                                continue
                
                # Break if we have good results
                if len([t for t in all_tracks if t.relevance_score > 0.7]) >= 3:
                    break
            
            # Sort by relevance and return best results
            all_tracks.sort(key=lambda t: getattr(t, 'relevance_score', 0), reverse=True)
            return all_tracks[:5]
        
        except Exception as e:
            print(f"[ERROR] Search failed: {e}")
            return []
            
            tracks = []
            if 'entries' in data:
                for entry in data['entries'][:5]:
                    if entry and entry.get('title'):
                        tracks.append(Track(entry, None))  # No requester for search results
                        print(f"[DEBUG] Added track: {entry.get('title', 'Unknown')}")
            else:
                if data.get('title'):
                    tracks.append(Track(data, None))
                    print(f"[DEBUG] Added single track: {data.get('title', 'Unknown')}")
                
            print(f"[DEBUG] Returning {len(tracks)} tracks")
            return tracks
                
        except Exception as e:
            print(f"[ERROR] Search tracks error for '{query}': {str(e)}")
            return []

    async def _find_alternative_sources(self, track_title: str) -> List:
        """Find alternative sources for a track when GLIBC issues occur"""
        print(f"[DEBUG] Searching for alternative sources for: {track_title}")
        
        if not WAVELINK_AVAILABLE or not self._lavalink_pool:
            return []
        
        # Try different search sources - avoid YouTube as it's deprecated for music bots
        # Focus on working sources: Spotify, Apple Music, Deezer
        alternative_sources = [
            'spsearch',  # Spotify search
            'amsearch',  # Apple Music search  
            'dzsearch',  # Deezer search
        ]
        results = []
        
        for source in alternative_sources:
            try:
                search_query = f"{source}:{track_title}"
                print(f"[DEBUG] Trying alternative source: {search_query}")
                
                playables = await wavelink.Playable.search(search_query, source=None)
                if playables:
                    # Filter for non-SoundCloud results to avoid GLIBC issues
                    filtered_playables = []
                    for p in playables:
                        source_str = str(getattr(p, 'source', '')).lower()
                        if 'soundcloud' not in source_str:
                            filtered_playables.append(p)
                    
                    if filtered_playables:
                        print(f"[DEBUG] Found {len(filtered_playables)} alternative tracks from {source}")
                        results.extend(filtered_playables[:2])  # Limit to prevent too many options
                        
            except Exception as e:
                print(f"[DEBUG] Alternative source {source} failed: {e}")
                continue
        
        print(f"[DEBUG] Total alternative sources found: {len(results)}")
        return results

    async def add_to_queue(self, ctx: Context, track: Track, silent: bool = False):
        """Add a track to the queue with enhanced preview filtering"""
        if not ctx.guild:
            await ctx.send(embed=discord.Embed(
                description="❌ This command can only be used in a server.",
                color=0xFF0000
            ))
            return
        
        # Enhanced preview detection at queue level - final safety check
        if self._is_preview_track(track):
            print(f"[DEBUG] BLOCKING PREVIEW TRACK at queue level: {track.title}")
            if not silent:
                await ctx.send(embed=discord.Embed(
                    description=f"❌ Skipped preview track: `{track.title}`\nSearching for full version...",
                    color=0xFF0000
                ))
            
            # Try to find a better version automatically
            await self._search_for_full_version(ctx, track)
            return
            
        queue = self.get_queue(ctx.guild.id)
        # Ensure requester is always set
        if not track.requester:
            track.requester = ctx.author
        
        print(f"[DEBUG] add_to_queue called for track: {track.title} by {track.requester.display_name}")
        
        # If Lavalink is enabled, ensure a lavalink player exists (or create by joining)
        if self.use_lavalink:
            # Try to ensure the pool exists (dynamic init)
            if not self._lavalink_pool:
                pool_ok = await self._ensure_lavalink_pool()
                if not pool_ok:
                    # Enforce Lavalink-only: do not fall back to downloads or local playback
                    await ctx.send(embed=discord.Embed(description="❌ Lavalink is not available. Playback requires a working Lavalink node.", color=0xFF0000))
                    return

            try:
                # Ensure player exists for the guild (may connect the bot to the channel so wavelink creates a player)
                print(f"[DEBUG] Ensuring Lavalink player for guild {ctx.guild.id}")
                player = await self._ensure_lavalink_player(ctx, timeout=15.0)
                print(f"[DEBUG] Lavalink player obtained: {player is not None}")
            except Exception as e:
                print(f"[WARN] ensure_lavalink_player failed: {e}")
                error_msg = f"❌ Lavalink player could not be created: {e}"
                if "voice connection may be unstable" in str(e):
                    error_msg += "\n💡 Try rejoining the voice channel or restart the bot if issues persist."
                elif "User not in voice channel" in str(e):
                    error_msg = "❌ You need to be in a voice channel to play music."
                elif "Failed to connect to voice channel" in str(e):
                    error_msg = "❌ Could not connect to your voice channel. Check bot permissions and try again."
                
                await ctx.send(embed=discord.Embed(description=error_msg, color=0xFF0000))
                return

            # Check if we should play immediately or queue
            player_is_playing = player.playing if player else False
            current_track_exists = ctx.guild.id in self.current_tracks
            
            if queue.is_empty() and not player_is_playing and not current_track_exists:
                try:
                    await self._play_via_lavalink(ctx, track, player=player)
                except Exception as e:
                    print(f"[WARN] Lavalink play failed after ensure: {e}")
                    await ctx.send(embed=discord.Embed(description=f"❌ Lavalink playback failed: {e}", color=0xFF0000))
                return
            else:
                queue.add(track)
                if not silent:  # Only send message if not silent
                    await ctx.send(embed=discord.Embed(description=f"<:feast_plus:1400142875483836547> Added **{track.title}** to the queue.", color=0x006fb9))

            return

        # Non-lavalink (local) path — simplified connection logic with 4006 handling
        vc = self._get_valid_voice_client(ctx.guild)
        print(f"[DEBUG] Valid voice client exists: {vc is not None}")

        if not vc:
            # Check if user is in voice channel
            if not getattr(ctx.author, 'voice', None):
                print("[DEBUG] User not in voice channel")
                await ctx.send(embed=discord.Embed(
                    description="❌ You need to be in a voice channel to play music.",
                    color=0xFF0000
                ))
                return

            # Check for recent 4006 errors
            if self._is_guild_4006_blocked(ctx.guild.id):
                await ctx.send(embed=discord.Embed(
                    description="⏳ Voice connection temporarily unavailable due to Discord session issues. Please try again in a moment.",
                    color=0xFF0000
                ))
                return

            # Single connection attempt
            vc = await self._ensure_voice_client(ctx, channel=ctx.author.voice.channel)
            if not vc:
                error_msg = "❌ Failed to connect to your voice channel."
                if self._last_voice_error and 'PyNaCl' in self._last_voice_error:
                    error_msg = ("❌ Voice support is not available on this host. "
                                 "PyNaCl appears to be missing. Install the 'PyNaCl' package to enable voice support.")
                elif self._is_guild_4006_blocked(ctx.guild.id):
                    error_msg = "⏳ Voice connection temporarily blocked due to Discord issues. Please wait a moment and try again."
                await ctx.send(embed=discord.Embed(description=error_msg, color=0xFF0000))
                return

        # Check if should play immediately or add to queue
        is_playing = False
        try:
            if hasattr(vc, 'is_playing') and callable(vc.is_playing):
                is_playing = vc.is_playing()
            elif hasattr(vc, 'playing'):
                is_playing = bool(vc.playing)
        except:
            pass

        current_track_exists = ctx.guild.id in self.current_tracks
        queue_empty = queue.is_empty()
        
        print(f"[DEBUG] Playback status - is_playing: {is_playing}, queue_empty: {queue_empty}, current_track_exists: {current_track_exists}")

        if not is_playing and queue_empty and not current_track_exists:
            print("[DEBUG] No music playing and queue is empty, playing track immediately")
            await self.play_track(ctx, track)
        else:
            print("[DEBUG] Music is playing or queue has items, adding track to queue")
            queue.add(track)
            embed = discord.Embed(
                description=f"<:feast_plus:1400142875483836547> Added **{track.title}** to the queue.",
                color=0x006fb9
            )
            # Add queue position info
            queue_position = len(queue.queue)
            if queue_position > 0:
                embed.add_field(
                    name="Queue Position", 
                    value=f"#{queue_position}", 
                    inline=True
                )
            await ctx.send(embed=embed)

    def _generate_search_queries(self, query: str, source: str = "scsearch") -> List[str]:
        """Generate multiple search query variations for better matching"""
        queries = []
        clean_query = query.strip()
        
        # Extract actual song info from URLs if possible
        if clean_query.startswith(('http://', 'https://')):
            # Try to extract title from URL if it's a YouTube URL
            if 'youtube.com' in clean_query or 'youtu.be' in clean_query:
                try:
                    import yt_dlp
                    ydl_opts = {
                        'quiet': True,
                        'no_warnings': True,
                        'extract_flat': True
                    }
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(clean_query, download=False)
                        if info and info.get('title'):
                            extracted_title = info['title']
                            # Clean the extracted title and use it for search
                            clean_title = re.sub(r'\b(official|music|video|lyric|lyrics|live|acoustic|cover|remix|extended|version|full|song|track|audio|hd|hq|4k|mv|2023|2024|2025)\b', '', extracted_title, flags=re.IGNORECASE)
                            clean_title = re.sub(r'[^\w\s-]', '', clean_title).strip()
                            clean_title = ' '.join(clean_title.split())  # Remove extra spaces
                            if clean_title:
                                prefix = "scsearch:"  # Always use SoundCloud
                                queries.append(f"{prefix}{clean_title} audio")
                                queries.append(f"{prefix}{clean_title} official audio")
                except Exception as e:
                    print(f"[DEBUG] Failed to extract title from URL: {e}")
            
            # Still add the original URL as fallback
            queries.append(clean_query)
        else:
            # Original query with source prefix - prioritize audio versions
            if not clean_query.startswith(('scsearch:', 'spsearch:', 'amsearch:', 'dzsearch:')):
                prefix = "scsearch:"  # Default to SoundCloud
                # Add audio-specific searches first
                queries.append(f"{prefix}{clean_query} audio")
                queries.append(f"{prefix}{clean_query} official audio")
                queries.append(f"{prefix}{clean_query}")  # Original as fallback
            else:
                queries.append(clean_query)
        
        # Only generate variations for non-URL queries
        if not clean_query.startswith(('http://', 'https://')):
            # Remove common problematic words/characters
            clean_words = re.sub(r'[^\w\s-]', '', clean_query.lower())
            clean_words = re.sub(r'\b(official|music|video|lyric|lyrics|live|acoustic|cover|remix|extended|version|full|song|track|audio|hd|hq|4k|mv|2023|2024|2025)\b', '', clean_words)
            clean_words = ' '.join(clean_words.split())  # Remove extra spaces
            
            if clean_words != clean_query.lower() and clean_words:
                prefix = "scsearch:"  # Always use SoundCloud
                queries.append(f"{prefix}{clean_words} audio")
            
            # Try with quotes for exact phrase matching
            if ' ' in clean_query and '"' not in clean_query:
                prefix = "scsearch:"  # Always use SoundCloud
                queries.append(f'{prefix}"{clean_query}" audio')
                
            # Try artist - song format if there's a dash
            if ' - ' in clean_query:
                parts = clean_query.split(' - ', 1)
                if len(parts) == 2:
                    artist, song = parts[0].strip(), parts[1].strip()
                    prefix = "scsearch:"  # Always use SoundCloud
                    queries.append(f"{prefix}{song} {artist} audio")  # Reverse order with audio
        
        return queries[:5]  # Increase to 5 query variations for better results
    
    def _calculate_relevance_score(self, original_query: str, track: Track) -> float:
        """Calculate how relevant a track is to the original search query"""
        query_lower = original_query.lower()
        title_lower = track.title.lower()
        author_lower = track.author.lower() if track.author else ""
        
        score = 0.0
        
        # Heavy penalty for music videos - we want audio only
        video_keywords = ['music video', 'mv', 'official video', 'lyric video', 'video oficial', 'videoclip']
        for keyword in video_keywords:
            if keyword in title_lower:
                score -= 0.8  # Heavy penalty
        
        # Bonus for audio-only content (but exclude audiobooks and non-music)
        audio_keywords = ['audio', 'official audio', 'original audio', 'full audio', 'hq audio', 'studio audio']
        non_music_keywords = ['audiobook', 'audio book', 'podcast', 'interview', 'commentary', 'special:', 'collection by', 'audio collection', 'episode']
        
        # Check if it's non-music content first
        is_non_music = any(keyword in title_lower for keyword in non_music_keywords)
        if is_non_music:
            score -= 1.0  # Heavy penalty for non-music content
        else:
            # Only give audio bonus if it's not non-music content
            for keyword in audio_keywords:
                if keyword in title_lower:
                    score += 0.3  # Reduced bonus for audio content
                    break
        
        # Exact title match (highest score)
        if query_lower == title_lower:
            score += 1.0
        elif query_lower in title_lower:
            score += 0.8
        
        # Check if query contains both artist and song
        if ' - ' in query_lower:
            parts = query_lower.split(' - ', 1)
            if len(parts) == 2:
                artist_query, song_query = parts[0].strip(), parts[1].strip()
                if artist_query in author_lower and song_query in title_lower:
                    score += 0.9
                elif song_query in title_lower:
                    score += 0.7
                elif artist_query in author_lower:
                    score += 0.5
        
        # Word matching in title - require better matching
        query_words = set(re.findall(r'\b\w+\b', query_lower))
        title_words = set(re.findall(r'\b\w+\b', title_lower))
        # Remove common/filler words that shouldn't count toward matching
        filler_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'ft', 'feat', 'featuring', 'audio', 'official', 'music'}
        meaningful_query_words = query_words - filler_words
        meaningful_title_words = title_words - filler_words
        
        if meaningful_query_words:
            common_words = meaningful_query_words.intersection(meaningful_title_words)
            word_match_ratio = len(common_words) / len(meaningful_query_words)
            
            # Only give positive scores for decent matches
            if word_match_ratio >= 0.6:  # At least 60% of meaningful words must match
                score += word_match_ratio * 0.6
            elif word_match_ratio >= 0.3:  # Partial match gets reduced score
                score += word_match_ratio * 0.3
            else:  # Poor match gets penalty
                score -= 0.3
        
        # Author matching
        if author_lower and any(word in author_lower for word in query_words):
            score += 0.3
        
        # Penalize covers, remixes, live versions, etc. MORE heavily
        penalty_keywords = ['cover', 'remix', 'live', 'acoustic', 'karaoke', 'instrumental', 'nightcore', 'slowed', 'reverb', 'sped up', 'male version', 'female version']
        for keyword in penalty_keywords:
            if keyword in title_lower and keyword not in query_lower:
                score -= 0.3  # Increased penalty
        
        # Heavy penalty for compilation keywords
        compilation_keywords = ['compilation', 'mix', 'mixtape', 'playlist', 'collection', 'various artists', 'best of']
        for keyword in compilation_keywords:
            if keyword in title_lower:
                score -= 0.5
        
        # Penalize very long titles (often compilations or playlists)
        if len(track.title) > 100:
            score -= 0.2  # Increased penalty
        
        # Penalize short titles that might be generic
        if len(track.title) < 10:
            score -= 0.1
        
        # Bonus for official channels and known music labels
        official_indicators = ['official', 'vevo', 'records', 'music', 'entertainment']
        for indicator in official_indicators:
            if indicator in author_lower:
                score += 0.15
                break
        
        # Bonus for exact channel name match
        if author_lower and any(word in author_lower for word in query_words):
            score += 0.2
        
        return max(0.0, min(1.0, score))  # Clamp between 0 and 1

    def _generate_enhanced_search_queries(self, query: str, source: str = "scsearch") -> List[str]:
        """Generate enhanced search queries with better variations for improved matching"""
        queries = []
        
        # Clean the original query
        clean_query = self._clean_search_query(query)
        
        # Primary queries (exact and cleaned)
        queries.append(f"{source}:{clean_query}")
        if clean_query != query:
            queries.append(f"{source}:{query}")
        
        # Enhanced variations for better matching
        if ' - ' in clean_query:
            # Artist - Song format
            parts = clean_query.split(' - ', 1)
            if len(parts) == 2:
                artist, song = parts[0].strip(), parts[1].strip()
                queries.extend([
                    f"{source}:{artist} {song}",
                    f"{source}:{song} {artist}",
                    f"{source}:{song}",  # Song only
                ])
        
        # Add quotes for exact phrase matching (for Spotify especially)
        if source == "spsearch" and len(clean_query.split()) > 1:
            queries.append(f'{source}:"{clean_query}"')
        
        # Remove duplicates while preserving order
        seen = set()
        unique_queries = []
        for q in queries:
            if q not in seen:
                seen.add(q)
                unique_queries.append(q)
        
        return unique_queries[:4]  # Limit to 4 queries per source
    
    def _is_valid_track_candidate(self, track: Track, original_query: str, source_name: str) -> bool:
        """Enhanced track validation with source-specific filtering"""
        
        # Basic validation
        if not track.title or len(track.title.strip()) < 2:
            return False
        
        title_lower = track.title.lower()
        query_lower = original_query.lower()
        
        # Enhanced filtering based on source quality characteristics
        if source_name == "SoundCloud":
            # Check for preview indicators in the URI/URL - be more comprehensive
            if hasattr(track, '_lavalink_playable') and track._lavalink_playable:
                uri = getattr(track._lavalink_playable, 'uri', '')
                # Check multiple preview patterns
                preview_patterns = ['preview', 'preview/hls', '/preview/', 'stream/preview', 'preview.mp3']
                for pattern in preview_patterns:
                    if pattern in uri.lower():
                        print(f"[DEBUG] Filtering SoundCloud preview track (URI pattern '{pattern}'): {track.title}")
                        return False
            
            # Check webpage_url as well
            if track.webpage_url:
                preview_patterns = ['preview', '/preview/', 'stream/preview']
                for pattern in preview_patterns:
                    if pattern in track.webpage_url.lower():
                        print(f"[DEBUG] Filtering SoundCloud preview track (URL pattern '{pattern}'): {track.title}")
                        return False
            
            # Stricter duration filtering for SoundCloud
            if track.duration and track.duration < 70:  # Increased from 60 to 70 seconds
                print(f"[DEBUG] Filtering short SoundCloud track: {track.title} ({track.duration}s)")
                return False
                
        elif source_name in ["YouTube Music", "YouTube"]:
            # YouTube sources are generally high quality, minimal filtering needed
            if track.duration and track.duration < 30:  # Very short tracks only
                print(f"[DEBUG] Filtering very short YouTube track: {track.title} ({track.duration}s)")
                return False
                
        elif source_name == "Spotify":
            # Spotify has excellent quality, minimal filtering
            if track.duration and track.duration < 25:  # Only filter extremely short tracks
                print(f"[DEBUG] Filtering very short Spotify track: {track.title} ({track.duration}s)")
                return False
        else:
            # Regular duration filtering for other sources
            min_duration = 30 if source_name == "Spotify" else 45
            if track.duration and track.duration < min_duration:
                print(f"[DEBUG] Filtering short track: {track.title} ({track.duration}s from {source_name})")
                return False
        
        # Filter out obvious non-music content
        filter_keywords = [
            'podcast', 'audiobook', 'interview', 'news', 'commercial', 'advertisement',
            'meditation', 'sleep sounds', 'white noise', 'nature sounds', 'asmr'
        ]
        
        for keyword in filter_keywords:
            if keyword in title_lower:
                return False
        
        # Enhanced filtering for SoundCloud (more strict due to quality variance)
        if source_name == "SoundCloud":
            # Filter out low-quality indicators
            quality_filters = [
                'snippet', 'teaser', 'preview', 'demo', 'unfinished', 'wip',
                'voice memo', 'voice note', 'test', 'freestyle', 'rough cut',
                'short version', 'cut', 'excerpt'  # Added more preview-related terms
            ]
            
            for keyword in quality_filters:
                if keyword in title_lower:
                    print(f"[DEBUG] Filtering SoundCloud quality issue: {track.title} (contains '{keyword}')")
                    return False
        
        # Prefer official content for Spotify
        if source_name == "Spotify":
            # Spotify generally has good quality, so be less restrictive
            return True
        
        return True
    
    def _is_valid_direct_url_track(self, track: Track, original_url: str) -> bool:
        """Validation specifically for direct URL tracks"""
        
        # Basic validation
        if not track.title or len(track.title.strip()) < 2:
            return False
        
        # Check for preview in the URL itself
        if 'preview' in original_url.lower():
            print(f"[DEBUG] Direct URL contains 'preview': {original_url}")
            return False
        
        # Check duration - be more lenient for direct URLs but still filter obvious previews
        if track.duration and track.duration < 25:  # Very short tracks are likely previews
            print(f"[DEBUG] Direct URL track too short: {track.title} ({track.duration}s)")
            return False
        
        # If from SoundCloud, check for preview indicators
        if 'soundcloud.com' in original_url.lower():
            if hasattr(track, '_lavalink_playable') and track._lavalink_playable:
                uri = getattr(track._lavalink_playable, 'uri', '')
                if 'preview' in uri.lower():
                    print(f"[DEBUG] SoundCloud direct URL is preview: {track.title}")
                    return False
        
        return True
    
    def _clean_search_query(self, query: str) -> str:
        """Clean and normalize search query for better matching"""
        import re
        
        # Remove common prefixes/suffixes that interfere with search
        prefixes_to_remove = ['play ', 'search ', 'find ', 'lookup ']
        for prefix in prefixes_to_remove:
            if query.lower().startswith(prefix):
                query = query[len(prefix):]
        
        # Remove file extensions
        query = re.sub(r'\.(mp3|mp4|wav|flac|m4a)$', '', query, flags=re.IGNORECASE)
        
        # Remove extra whitespace and normalize
        query = ' '.join(query.split())
        
        # Remove brackets with metadata that might interfere
        query = re.sub(r'\[.*?\]', '', query)
        query = re.sub(r'\(.*?video.*?\)', '', query, flags=re.IGNORECASE)
        query = re.sub(r'\(.*?audio.*?\)', '', query, flags=re.IGNORECASE)
        
        # Clean up again
        query = ' '.join(query.split())
        
        return query.strip()
    
    def _is_preview_track(self, track: Track) -> bool:
        """Comprehensive preview track detection"""
        
        # Check duration - anything under 45 seconds is likely a preview
        if track.duration and track.duration < 45:
            print(f"[DEBUG] Preview detected (duration): {track.title} ({track.duration}s)")
            return True
        
        # Check for preview in title
        title_lower = track.title.lower() if track.title else ""
        preview_keywords = ['preview', 'snippet', 'teaser', '30 second', 'short version']
        for keyword in preview_keywords:
            if keyword in title_lower:
                print(f"[DEBUG] Preview detected (title keyword '{keyword}'): {track.title}")
                return True
        
        # Check Lavalink playable URI if available
        if hasattr(track, '_lavalink_playable') and track._lavalink_playable:
            uri = getattr(track._lavalink_playable, 'uri', '')
            if uri and 'preview' in uri.lower():
                print(f"[DEBUG] Preview detected (URI): {track.title} - {uri}")
                return True
        
        # Check webpage_url
        if track.webpage_url and 'preview' in track.webpage_url.lower():
            print(f"[DEBUG] Preview detected (webpage_url): {track.title} - {track.webpage_url}")
            return True
        
        return False
    
    async def _search_for_full_version(self, ctx, preview_track: Track):
        """Try to find a full version of a preview track"""
        print(f"[DEBUG] Searching for full version of: {preview_track.title}")
        
        # Extract clean search terms from the preview track
        title = preview_track.title or ""
        
        # Remove preview-related words from title
        clean_title = title
        for keyword in ['preview', 'snippet', 'teaser', '30 second', 'short version', '[preview]', '(preview)']:
            clean_title = clean_title.replace(keyword, '').strip()
        
        # Try searching with just the clean title
        if clean_title and len(clean_title) > 3:
            try:
                print(f"[DEBUG] Searching for full version with query: {clean_title}")
                # Use our enhanced search but skip the problematic track
                await self.play_source(ctx, clean_title, skip_previews=True)
                return
            except Exception as e:
                print(f"[DEBUG] Failed to find full version: {e}")
        
        # If all else fails, inform the user
        await ctx.send(embed=discord.Embed(
            description=f"❌ Could not find full version of `{preview_track.title}`",
            color=0xFF0000
        ))

    async def play_track(self, ctx: Context, track: Track):
        """Play a track from downloaded file - simplified to prevent connection loops"""
        print(f"[DEBUG] play_track called for: {track.title}")
        
        if not ctx.guild:
            print("[ERROR] No guild in play_track")
            return
            
        # Use standardized connection validation
        vc = self._get_valid_voice_client(ctx.guild)
        print(f"[DEBUG] Valid voice client exists: {vc is not None}")
        
        if not vc:
            print("[ERROR] No valid voice client in play_track")
            await ctx.send(embed=discord.Embed(
                description="❌ Not connected to voice channel.",
                color=0xFF0000
            ))
            return

        # Store current track
        self.current_tracks[ctx.guild.id] = track
        print(f"[DEBUG] Stored current track: {track.title}")

        # If lavalink is enabled and pool is available, prefer to use it
        if self.use_lavalink and self._lavalink_pool is not None:
            try:
                await self._play_via_lavalink(ctx, track)
                return
            except Exception as e:
                print(f"[ERROR] Lavalink playback failed: {e}")
                await ctx.send(embed=discord.Embed(description=f"❌ Lavalink playback failed: {e}", color=0xFF0000))
                return

        # Single playback attempt (no retry loops)
        try:
            # Stop any currently playing audio to avoid overlap
            try:
                if hasattr(vc, 'is_playing') and vc.is_playing():
                    vc.stop()
                elif hasattr(vc, 'is_paused') and vc.is_paused():
                    vc.stop()
            except Exception:
                pass

            # Build audio source
            if track.local_file and os.path.exists(track.local_file):
                audio_source = discord.FFmpegPCMAudio(track.local_file, options='-vn')
            else:
                if not track.url:
                    print("[ERROR] No audio source available for this track")
                    await ctx.send(embed=discord.Embed(description="❌ No audio source available for this track", color=0xFF0000))
                    return
                audio_source = discord.FFmpegPCMAudio(
                    track.url,
                    before_options='-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
                )

            # Start playback with 50% volume (0.5)
            print(f"[DEBUG] Starting playback at 50% volume...")
            vc.play(discord.PCMVolumeTransformer(audio_source, volume=0.5), 
                   after=lambda e: self.client.loop.create_task(self.on_track_end(ctx, e)))

            # Verify playback started
            await asyncio.sleep(0.6)
            if hasattr(vc, 'is_playing') and vc.is_playing():
                print("[DEBUG] Playback started successfully")
                await self.display_player_embed(track, ctx)
                return
            else:
                print("[ERROR] Playback failed to start")
                await ctx.send(embed=discord.Embed(description="❌ Failed to start playback", color=0xFF0000))
                return

        except Exception as e:
            print(f"[ERROR] Playback failed: {e}")
            import traceback
            traceback.print_exc()
            await ctx.send(embed=discord.Embed(description=f"❌ Failed to start playback: {e}", color=0xFF0000))
            return

    async def _play_via_lavalink(self, ctx: Context, track: Track, player=None):
        """Play track using wavelink Lavalink player. If `player` is None, attempt to ensure one."""
        if not WAVELINK_AVAILABLE:
            raise RuntimeError('wavelink not available')

        pool = self._lavalink_pool
        if not pool:
            raise RuntimeError('Lavalink pool not initialized')

        # Ensure we have a player
        if player is None:
            player = await self._ensure_lavalink_player(ctx)

        if not player:
            raise RuntimeError('Lavalink player not available')

        # Local file playback via Lavalink is not supported here (would require serving file over HTTP)
        if track.local_file and os.path.exists(track.local_file):
            raise RuntimeError('Local file playback via Lavalink not supported in this environment')

        query = track.webpage_url or track.title
        print(f"[DEBUG] Original query: {query}")
        
        results = []
        try:
            print(f"[DEBUG] Searching with Wavelink v4 Playable.search: {query}")
            
            # Debug: Check available TrackSource attributes
            available_attrs = [attr for attr in dir(TrackSource) if not attr.startswith('_')]
            print(f"[DEBUG] Available TrackSource attributes: {available_attrs}")
            
            # Try multiple sources in order of preference (SoundCloud and Spotify preferred over YouTube)
            search_sources = []
            
            # Determine search strategy based on query type
            if query.startswith(('http://', 'https://')):
                # For direct URLs, try to use them directly first
                print(f"[DEBUG] Direct URL detected: {query}")
                try:
                    results = await Playable.search(query)
                    if results:
                        print(f"[DEBUG] Direct URL search successful: {len(results)} results")
                    else:
                        print(f"[DEBUG] Direct URL search failed, will try text search")
                        # Strip URL and try as text search
                        import re
                        # Extract potential title from URL
                        url_title = re.sub(r'[^a-zA-Z0-9\\s]', ' ', query.split('/')[-1])
                        if url_title.strip():
                            query = url_title.strip()
                            print(f"[DEBUG] Extracted title from URL: {query}")
                except Exception as e:
                    print(f"[DEBUG] Direct URL processing failed: {e}")
                    
            # Enhanced multi-source search using available TrackSource enums
            if not results:
                print(f"[DEBUG] Starting enhanced multi-source search...")
                
                # Search sources in priority order using only available TrackSource enums
                search_strategies = [
                    # 1. SoundCloud search (most reliable)
                    (TrackSource.SoundCloud, "SoundCloud", 0.9),
                    # 2. YouTube Music search (good quality when working)
                    (TrackSource.YouTubeMusic, "YouTube Music", 0.8),
                    # 3. YouTube search as fallback
                    (TrackSource.YouTube, "YouTube", 0.6)
                ]
                
                for track_source, source_name, weight in search_strategies:
                    try:
                        print(f"[DEBUG] Trying {source_name} search using TrackSource enum")
                        
                        # Use TrackSource enum directly
                        source_results = await Playable.search(query, source=track_source)
                        
                        if source_results and len(source_results) > 0:
                            print(f"[DEBUG] {source_name} found {len(source_results)} results")
                            
                            # Filter results based on source reliability
                            filtered_results = []
                            for track in source_results[:15]:  # Check more tracks for better filtering
                                # Apply preview filtering for all sources
                                if not self._is_preview_track(track):
                                    filtered_results.append(track)
                                    print(f"[DEBUG] Added {source_name} track: {track.title}")
                                else:
                                    print(f"[DEBUG] Skipped preview track: {track.title}")
                            
                            if filtered_results:
                                results = filtered_results
                                print(f"[DEBUG] Using {source_name} as primary source with {len(results)} tracks")
                                break
                                
                    except Exception as e:
                        print(f"[DEBUG] {source_name} search failed: {e}")
                        # Check if this is a YouTube cipher error
                        if 'cipher' in str(e).lower() or 'signature' in str(e).lower():
                            print(f"[DEBUG] YouTube cipher error detected, skipping remaining YouTube sources")
                            # Skip remaining YouTube-based searches if we hit cipher issues
                            if 'youtube' in source_name.lower():
                                break
                        continue
                
                # If no TrackSource searches worked, try string-based searches
                if not results:
                    print(f"[DEBUG] TrackSource searches failed, trying string-based searches...")
                    
                    string_searches = [
                        ("spsearch", "Spotify-via-LavaSrc"),
                        ("scsearch", "SoundCloud-via-LavaSrc"),  
                        ("ytsearch", "YouTube-Direct"),
                        ("", "Generic")
                    ]
                    
                    for search_prefix, source_name in string_searches:
                        try:
                            search_query = f"{search_prefix}:{query}" if search_prefix else query
                            print(f"[DEBUG] Trying {source_name} search: {search_query}")
                            
                            # Try direct search without TrackSource
                            source_results = await Playable.search(search_query)
                            
                            if source_results and len(source_results) > 0:
                                print(f"[DEBUG] {source_name} found {len(source_results)} results")
                                
                                # Filter results
                                filtered_results = []
                                for track in source_results[:10]:
                                    if not self._is_preview_track(track):
                                        filtered_results.append(track)
                                        print(f"[DEBUG] Added {source_name} track: {track.title}")
                                
                                if filtered_results:
                                    results = filtered_results
                                    print(f"[DEBUG] Using {source_name} as primary source with {len(results)} tracks")
                                    break
                                    
                        except Exception as e:
                            print(f"[DEBUG] {source_name} search failed: {e}")
                            continue
            
            print(f"[DEBUG] Final results count: {len(results) if results else 0}")
            
        except Exception as e:
            print(f"[DEBUG] Multi-source search failed: {e}")
            import traceback
            traceback.print_exc()
            
            # Emergency fallback - try simple searches without complex routing
            print(f"[DEBUG] Attempting emergency fallback searches...")
            
            emergency_searches = [
                query,  # Basic search without any prefixes
                f"ytsearch:{query}",  # Direct YouTube search
                f"scsearch:{query}",  # SoundCloud search
                f"spsearch:{query}"   # Spotify search
            ]
            
            for search_query in emergency_searches:
                try:
                    print(f"[DEBUG] Emergency search: {search_query}")
                    emergency_results = await Playable.search(search_query)
                    if emergency_results and len(emergency_results) > 0:
                        print(f"[DEBUG] Emergency search found {len(emergency_results)} results")
                        results = emergency_results[:5]  # Use first 5 results
                        break
                except Exception as emergency_e:
                    print(f"[DEBUG] Emergency search failed: {emergency_e}")
                    continue

        if not results:
            error_msg = 'No results from Lavalink v4 search'
            
            # Provide helpful debugging info
            print(f"[DEBUG] Search failed completely for query: {query}")
            print(f"[DEBUG] Tried TrackSource enums: SoundCloud, YouTubeMusic, YouTube")
            print(f"[DEBUG] Tried string searches: spsearch, scsearch, ytsearch, generic")
            print(f"[DEBUG] Emergency searches also failed")
            
            # Check if Lavalink is responding at all
            try:
                # Try a very basic search to test connectivity
                basic_test = await Playable.search("test")
                if basic_test is None:
                    error_msg += ' (Lavalink connection may be down)'
                else:
                    error_msg += ' (Lavalink connected but no sources returning results)'
            except Exception as test_e:
                error_msg += f' (Lavalink error: {test_e})'
            
            raise RuntimeError(error_msg)

        # Smart track selection using our improved scoring system
        selected_playable = None
        best_score = -1
        
        for i, playable in enumerate(results):
            print(f"[DEBUG] Evaluating track #{i+1}: {playable.title}")
            
            # Convert to Track object for our scoring system
            duration = 0
            try:
                duration = playable.length // 1000 if hasattr(playable, 'length') and playable.length else 0
            except:
                try:
                    duration = playable.duration // 1000 if hasattr(playable, 'duration') and playable.duration else 0
                except:
                    duration = 0
                    
            data = {
                'title': getattr(playable, 'title', 'Unknown') or 'Unknown',
                'webpage_url': getattr(playable, 'uri', ''),
                'duration': duration,
                'thumbnail': getattr(playable, 'artwork', '') or getattr(playable, 'thumbnail', '') or '',
                'uploader': getattr(playable, 'author', 'Unknown') or 'Unknown',
                'extractor': 'lavalink_v4'
            }
            track_for_scoring = Track(data, requester=None)  # No requester needed for scoring
            
            # Use our improved scoring system
            score = self._calculate_relevance_score(query, track_for_scoring)
            
            print(f"[DEBUG] Track #{i+1} score: {score:.2f}")
            
            # Select the best scoring track (only if score is reasonable)
            if score > best_score and score > 0.4:  # Minimum threshold to filter out bad matches
                selected_playable = playable
                best_score = score
                print(f"[DEBUG] New best track: {playable.title} (score: {score:.2f})")
        
        # Fallback to first result if no good scoring matches found
        if selected_playable is None and results:
            selected_playable = results[0]
            print(f"[DEBUG] No good matches found, fallback to first track: {selected_playable.title}")
        
        playable = selected_playable
        print(f"[DEBUG] Final selected playable: {playable.title} by {playable.author}")
        print(f"[DEBUG] Final selection score: {best_score:.2f}")

        # Check if track is actually our Track object or if it's a Playable
        if isinstance(track, Track):
            print(f"[DEBUG] Track is our custom Track class - updating properties")
            # Update our custom Track object with Playable data
            if playable.title:
                track.title = playable.title
            if playable.author:
                track.author = playable.author
            if playable.uri:
                track.url = playable.uri
                track.webpage_url = playable.uri
            try:
                track.duration = playable.length // 1000 if hasattr(playable, 'length') and playable.length else track.duration
            except:
                try:
                    track.duration = playable.duration // 1000 if hasattr(playable, 'duration') and playable.duration else track.duration
                except:
                    pass
            track.thumbnail = getattr(playable, 'artwork', None) or track.thumbnail
        else:
            print(f"[DEBUG] Track is not our Track class ({type(track)}), creating new Track object")
            # Create a new Track object from the Playable data
            duration = 0
            try:
                duration = playable.length // 1000 if hasattr(playable, 'length') and playable.length else 0
            except:
                try:
                    duration = playable.duration // 1000 if hasattr(playable, 'duration') and playable.duration else 0
                except:
                    duration = 0
                    
            track = Track(data={
                'title': getattr(playable, 'title', 'Unknown') or 'Unknown',
                'webpage_url': getattr(playable, 'uri', '') or '',
                'duration': duration,
                'thumbnail': getattr(playable, 'artwork', None) or getattr(playable, 'thumbnail', None),
                'uploader': getattr(playable, 'author', 'Unknown') or 'Unknown',
            }, requester=ctx.author, local_file=None)

        # remember current track metadata
        self.current_tracks[ctx.guild.id] = track

        print(f"[DEBUG] Playing track: {track.title} by {track.author}")
        print(f"[DEBUG] Player state before play: connected={getattr(player, 'connected', 'unknown')}, playing={getattr(player, 'playing', 'unknown')}")
        
        # Set volume to guild's saved volume
        try:
            if hasattr(player, 'set_volume'):
                saved_volume = await self._get_volume_for_guild(ctx.guild.id)
                await player.set_volume(saved_volume)
                print(f"[DEBUG] Volume set to {saved_volume}%")
        except Exception as e:
            print(f"[DEBUG] Failed to set volume: {e}")
        
        try:
            print(f"[DEBUG] About to call player.play with playable: {type(playable)}")
            print(f"[DEBUG] Playable properties: title={getattr(playable, 'title', 'N/A')}, uri={getattr(playable, 'uri', 'N/A')}")
            print(f"[DEBUG] Playable source: {getattr(playable, 'source', 'unknown')}")
            
            await player.play(playable)
            print(f"[DEBUG] player.play() completed successfully")
            
            # Wait longer to check if track actually started and is stable
            await asyncio.sleep(2.0)
            current_playing = getattr(player, 'playing', False)
            current_track = getattr(player, 'current', None)
            
            print(f"[DEBUG] Post-play check: playing={current_playing}, has_current={current_track is not None}")
            
            if not current_playing or current_track is None:
                print(f"[DEBUG] Track failed to start properly, trying alternatives")
                
                # Try alternative tracks with different sources prioritized
                alternatives_tried = 0
                max_alternatives = min(8, len(results))  # Try up to 8 alternatives
                
                for i, alt_playable in enumerate(results):
                    if alt_playable == playable:  # Skip the one we just tried
                        continue
                        
                    if alternatives_tried >= max_alternatives:
                        break
                        
                    try:
                        alt_source = getattr(alt_playable, 'source', 'unknown')
                        print(f"[DEBUG] Trying alternative #{alternatives_tried+1}: {alt_playable.title} (source: {alt_source})")
                        
                        await player.play(alt_playable)
                        await asyncio.sleep(1.5)  # Give it time to start
                        
                        if getattr(player, 'playing', False) and getattr(player, 'current', None):
                            print(f"[DEBUG] Alternative track #{alternatives_tried+1} started successfully!")
                            playable = alt_playable  # Update our playable reference
                            
                            # Update track info with the working alternative
                            if isinstance(track, Track):
                                track.title = alt_playable.title or track.title
                                track.author = alt_playable.author or track.author
                                track.url = alt_playable.uri or track.url
                                track.webpage_url = alt_playable.uri or track.webpage_url
                            break
                        else:
                            print(f"[DEBUG] Alternative #{alternatives_tried+1} also failed to start")
                            
                    except Exception as alt_e:
                        print(f"[DEBUG] Alternative #{alternatives_tried+1} failed with error: {alt_e}")
                    
                    alternatives_tried += 1
                
                # Final check after trying alternatives
                if not getattr(player, 'playing', False):
                    print(f"[WARNING] No working tracks found after trying {alternatives_tried} alternatives")
                    
                    # Check for YouTube cipher/plugin errors in the error logs
                    youtube_cipher_error = any(
                        error_msg in str(e).lower() 
                        for error_msg in ['cipher', 'signature', 'script extraction', 'youtube']
                        for e in getattr(self, '_recent_errors', [])
                    )
                    
                    # Check if all failures were due to GLIBC errors (server-side decoding issues)
                    glibc_failure_detected = hasattr(self, '_last_glibc_error_count') and self._last_glibc_error_count >= alternatives_tried
                    
                    if youtube_cipher_error:
                        # Send helpful message about YouTube plugin issues
                        embed = discord.Embed(
                            title="🔧 YouTube Plugin Issue",
                            description=(
                                "**YouTube cipher extraction error detected.**\n\n"
                                "This is a known issue with YouTube's anti-bot measures that affects "
                                "the Lavalink YouTube plugin.\n\n"
                                "**What this means:**\n"
                                "• YouTube has updated their protection systems\n"
                                "• The YouTube plugin needs updating or reconfiguration\n"
                                "• Alternative music sources (Spotify, SoundCloud) work normally\n\n"
                                "**Recommended actions:**\n"
                                "• Try using Spotify or SoundCloud links instead\n"
                                "• Search by artist/song name (uses multiple sources)\n"
                                "• Avoid direct YouTube URLs temporarily\n"
                                "• Server administrator should update the YouTube plugin"
                            ),
                            color=0xFF6B35
                        )
                        embed.set_footer(text="Technical: YouTube signature cipher extraction failed")
                        
                        try:
                            await ctx.send(embed=embed)
                        except:
                            await ctx.send("🔧 **YouTube plugin issue:** Try using Spotify/SoundCloud links or search by song name instead.")
                    elif glibc_failure_detected:
                        # Send helpful message about server-side audio decoding issues
                        embed = discord.Embed(
                            title="🔧 Audio Decoding Issue",
                            description=(
                                "**Server-side audio decoding issue detected.**\n\n"
                                "This is a known issue with the Lavalink server environment that requires "
                                "server administrator intervention to resolve.\n\n"
                                "**What this means:**\n"
                                "• The music system is working correctly\n"
                                "• Multiple alternative tracks were found and tried\n"
                                "• All tracks failed due to server library compatibility\n\n"
                                "**Recommended actions:**\n"
                                "• Try different music sources (Spotify, SoundCloud)\n"
                                "• Report this issue to server administrators\n"
                                "• The server needs GLIBC library updates"
                            ),
                            color=0xFF6B35
                        )
                        embed.set_footer(text="Technical: GLIBC_2.38 compatibility issue on Lavalink server")
                        
                        try:
                            await ctx.send(embed=embed)
                        except:
                            await ctx.send("🔧 **Audio decoding issue:** Server needs library updates to play this audio format.")
                    else:
                        # Generic failure message
                        embed = discord.Embed(
                            title="❌ Track Unavailable",
                            description=f"Unable to play **{track.title}** - tried {alternatives_tried} alternatives but none worked.",
                            color=0xFF4757
                        )
                        try:
                            await ctx.send(embed=embed)
                        except:
                            await ctx.send(f"❌ Unable to play **{track.title}** - no working alternatives found.")
                    
                    # Reset error counters
                    self._last_glibc_error_count = 0
                    if hasattr(self, '_recent_errors'):
                        self._recent_errors = []
                    return  # Don't try to display player embed for failed tracks
                    
        except Exception as e:
            print(f"[ERROR] player.play() failed: {e}")
            import traceback
            traceback.print_exc()
            raise
        
        # Wait a moment and check if playback started
        await asyncio.sleep(0.5)
        print(f"[DEBUG] Player state after play: connected={getattr(player, 'connected', 'unknown')}, playing={getattr(player, 'playing', 'unknown')}")
        
        # Additional debugging for audio state
        try:
            volume = getattr(player, 'volume', 'unknown')
            position = getattr(player, 'position', 'unknown')
            print(f"[DEBUG] Audio state: volume={volume}, position={position}ms")
            
            # Check if the track has a valid source
            current = getattr(player, 'current', None)
            if current:
                print(f"[DEBUG] Current track info: {getattr(current, 'title', 'unknown')}, uri={getattr(current, 'uri', 'unknown')}")
            else:
                print(f"[DEBUG] No current track found on player")
                
        except Exception as e:
            print(f"[DEBUG] Audio state check failed: {e}")
        
        await self.display_player_embed(track, ctx)

    async def _play_track_direct_lavalink(self, player, track: Track, guild_id: int):
        """Play track directly via Lavalink player without context dependency"""
        if not WAVELINK_AVAILABLE:
            raise RuntimeError('wavelink not available')

        print(f"[DEBUG] Direct Lavalink play for: {track.title}")
        
        # Update current track tracking
        self.current_tracks[guild_id] = track
        
        # Check if this track has a stored Wavelink playable (from alternative source search)
        if hasattr(track, '_wavelink_playable') and track._wavelink_playable:
            print(f"[DEBUG] Using stored Wavelink playable for alternative source")
            lavalink_track = track._wavelink_playable
        else:
            # Search for the track with multiple attempts
            query = track.webpage_url or track.title
            print(f"[DEBUG] Searching for: {query}")
            
            try:
                # Generate multiple search queries for better fallback
                search_queries = [query]
                if track.title and track.title != query:
                    search_queries.append(track.title)
                if track.author and track.title:
                    search_queries.append(f"{track.author} - {track.title}")
                    search_queries.append(f"{track.title} {track.author}")
                
                lavalink_track = None
                all_results = []
                
                # Try each search query
                for search_query in search_queries:
                    try:
                        print(f"[DEBUG] Trying search: {search_query}")
                        results = await Playable.search(search_query)
                        if results:
                            all_results.extend(results[:3])  # Take top 3 from each query
                            print(f"[DEBUG] Found {len(results)} results for: {search_query}")
                    except Exception as e:
                        print(f"[DEBUG] Search failed for '{search_query}': {e}")
                        continue
                
                if not all_results:
                    print(f"[DEBUG] No results found for any search query")
                    raise RuntimeError(f"No results found for: {track.title}")
                
                # Try playing tracks until one works
                for i, candidate in enumerate(all_results[:5]):  # Try up to 5 candidates
                    try:
                        print(f"[DEBUG] Attempting track #{i+1}: {candidate.title}")
                        await player.play(candidate)
                        
                        # Apply saved volume immediately after starting playback
                        try:
                            saved_volume = await self._get_volume_for_guild(guild_id)
                            if hasattr(player, 'set_volume'):
                                await player.set_volume(saved_volume)
                                print(f"[DEBUG] Applied volume {saved_volume}% to player")
                        except Exception as vol_e:
                            print(f"[DEBUG] Warning: Could not set volume: {vol_e}")
                        
                        # Wait and verify playback started
                        await asyncio.sleep(1.0)
                        if getattr(player, 'playing', False) and getattr(player, 'current', None):
                            lavalink_track = candidate
                            print(f"[DEBUG] Successfully started playback: {candidate.title}")
                            break
                        else:
                            print(f"[DEBUG] Track #{i+1} failed to start properly")
                        
                    except Exception as e:
                        print(f"[DEBUG] Track #{i+1} failed with error: {e}")
                        continue
                
                if not lavalink_track:
                    raise RuntimeError(f"All tracks failed to play for: {track.title}")
                    
            except Exception as e:
                print(f"[DEBUG] Track search and play failed: {e}")
                raise e
            
            # Optionally send a simple auto-play notification to the channel
            try:
                if hasattr(player, 'channel') and player.channel:
                    channel = player.channel
                    # Find a text channel in the guild to send notification
                    guild = player.guild
                    if guild:
                        # Try to find the first text channel the bot can send messages to
                        for text_channel in guild.text_channels:
                            if text_channel.permissions_for(guild.me).send_messages:
                                embed = discord.Embed(
                                    description=f"🎵 **Now Playing:** {track.title}",
                                    color=0x00E6A7
                                )
                                if track.requester:
                                    embed.set_footer(text=f"Requested by {track.requester.display_name} (Auto-play)")
                                await text_channel.send(embed=embed)
                                break
            except Exception as e:
                print(f"[DEBUG] Could not send auto-play notification: {e}")

    async def play_next(self, ctx: Context):
        """Play the next track in queue"""
        queue = self.get_queue(ctx.guild.id)
        track = queue.get_next()

        if not track:
            # Queue is empty - clean up current track tracking
            self.current_tracks.pop(ctx.guild.id, None)
            
            # Use standardized voice client checking
            vc = self._get_valid_voice_client(ctx.guild)
            if vc:
                # Check if not playing using standardized method
                is_playing = False
                try:
                    if hasattr(vc, 'is_playing') and callable(vc.is_playing):
                        is_playing = vc.is_playing()
                    elif hasattr(vc, 'playing'):
                        is_playing = bool(vc.playing)
                except:
                    pass
                
                if not is_playing:
                    await asyncio.sleep(5)  # Wait a bit before disconnecting
                    if vc and not is_playing:
                        try:
                            await vc.disconnect()
                        except:
                            pass
                        self.voice_clients.pop(ctx.guild.id, None)
                        
                        embed = discord.Embed(
                            description="🎵 Queue ended. Disconnected from voice channel.",
                            color=0x00E6A7
                        )
                        await ctx.send(embed=embed)
            return

        # Play next track
        print(f"[DEBUG] Playing next track: {track.title}")
        await self.play_track(ctx, track)

    async def on_track_end(self, ctx: Context, error):
        """Called when a track ends"""
        if error:
            print(f"[DEBUG] Player error: {error}")

        queue = self.get_queue(ctx.guild.id)
        current_track = self.current_tracks.get(ctx.guild.id)

        # Handle loop mode for single track
        if queue.loop_mode and current_track and queue.is_empty():
            print("[DEBUG] Loop mode active, replaying current track")
            # Add current track back to queue
            queue.add(current_track)

        print(f"[DEBUG] Track ended, queue has {len(queue.queue)} tracks")
        
        # Play next track
        await self.play_next(ctx)

    def create_progress_bar(self, completed, total, length=10):
        """Create a progress bar"""
        if total <= 0:
            return '░' * length
        filled_length = int(length * (completed / total))
        bar = '█' * filled_length + '░' * (length - filled_length)
        return bar

    async def display_player_embed(self, track: Track, ctx: Context, autoplay=False):
        """Display the now playing embed with controls"""
        # Create custom player image without using the old template
        file = None
        if track.thumbnail:
            try:
                font_path = 'utils/arial.ttf'
                
                if os.path.exists(font_path):
                    # Create a new clean image from scratch (no template with FEAST branding)
                    img_width, img_height = 600, 200
                    base_img = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 255))  # Black background
                    
                    # Download and process track thumbnail
                    async with aiohttp.ClientSession() as session:
                        async with session.get(track.thumbnail) as resp:
                            if resp.status == 200:
                                track_img_data = io.BytesIO(await resp.read())
                                track_img = Image.open(track_img_data).convert("RGBA")
                                
                                # Create circular thumbnail
                                thumb_size = 150
                                track_img = ImageOps.fit(track_img, (thumb_size, thumb_size), centering=(0.5, 0.5))
                                
                                # Create circular mask
                                mask = Image.new('L', (thumb_size, thumb_size), 0)
                                draw_mask = ImageDraw.Draw(mask)
                                draw_mask.ellipse((0, 0, thumb_size, thumb_size), fill=255)
                                track_img.putalpha(mask)
                                
                                # Paste thumbnail on left side
                                thumb_y = (img_height - thumb_size) // 2
                                base_img.paste(track_img, (25, thumb_y), track_img)

                    # Add text elements
                    draw = ImageDraw.Draw(base_img)
                    
                    # Load fonts
                    title_font = ImageFont.truetype(font_path, 32)
                    author_font = ImageFont.truetype(font_path, 24)
                    branding_font = ImageFont.truetype(font_path, 18)
                    
                    # Track title (main text)
                    title_x = 200
                    title_y = 50
                    title_text = track.title[:35] + "..." if len(track.title) > 35 else track.title
                    draw.text((title_x, title_y), title_text, font=title_font, fill="white")
                    
                    # Track author
                    author_y = title_y + 40
                    author_text = f"by {track.author}" if track.author else "Unknown Artist"
                    draw.text((title_x, author_y), author_text, font=author_font, fill=(200, 200, 200))
                    
                    # Duration
                    sec = int(track.duration) if track.duration else 0
                    duration_text = f"{sec // 60}:{sec % 60:02d}" if sec < 3600 else f"{sec // 3600}:{(sec % 3600) // 60:02d}:{sec % 60:02d}"
                    duration_y = author_y + 35
                    draw.text((title_x, duration_y), f"Duration: {duration_text}", font=author_font, fill=(150, 150, 150))
                    
                    # Sleepless.PY branding (bottom right)
                    branding_text = "Sleepless.PY"
                    branding_x = img_width - 120
                    branding_y = img_height - 30
                    draw.text((branding_x, branding_y), branding_text, font=branding_font, fill=(100, 200, 255))
                    
                    # Add decorative elements
                    # Gradient overlay for visual appeal
                    overlay = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0))
                    overlay_draw = ImageDraw.Draw(overlay)
                    
                    # Add subtle gradient effect
                    for i in range(img_height):
                        alpha = int(50 * (1 - i / img_height))
                        overlay_draw.rectangle([(0, i), (img_width, i+1)], fill=(0, 100, 200, alpha))
                    
                    base_img = Image.alpha_composite(base_img, overlay)

                    # Save to bytes
                    image_bytes = io.BytesIO()
                    base_img.save(image_bytes, format="PNG")
                    image_bytes.seek(0)

                    file = discord.File(image_bytes, filename="player.png")
            except Exception as e:
                print(f"[DEBUG] Image generation failed: {e}")
                pass

        # Create embed
        # Ensure duration is an int to avoid format errors when it is float-like
        sec = int(track.duration) if track.duration else 0
        duration = f"0{sec // 60}:{sec % 60:02d}" if sec < 3600 else f"{sec // 3600}:{(sec % 3600) // 60:02d}:{sec % 60:02d}"

        color_map = {
            'spotify': 0x1DB954,
            'soundcloud': 0xFF5500,
            'youtube': 0xFF0000,
        }
        color = color_map.get(track.source, 0x00E6A7)

        embed = discord.Embed(title=f"**{track.title}**", color=color)
        embed.add_field(name="Author", value=f"`{track.author}`", inline=True)
        embed.add_field(name="Duration", value=f"`{duration}`", inline=True)

        # Source link
        source_name = track.source.title() if track.source != 'unknown' else 'Unknown'
        if track.webpage_url:
            embed.add_field(name="Source", value=f"[🎵 Listen on {source_name}]({track.webpage_url})", inline=True)

        if file:
            embed.set_image(url="attachment://player.png")

        # Only set footer if requester exists
        if track.requester:
            try:
                icon_url = track.requester.avatar.url if track.requester.avatar else track.requester.default_avatar.url
            except Exception:
                icon_url = None

            embed.set_footer(
                text=f"Requested by {track.requester.display_name}" + (" (Autoplay Mode)" if autoplay else ""),
                icon_url=icon_url
            )

        # Send with controls
        view = MusicControlView(self, ctx)
        if file:
            await ctx.send(embed=embed, file=file, view=view)
        else:
            await ctx.send(embed=embed, view=view)

    async def _get_playback_controller(self, ctx: Context):
        """Return ('lavalink', player) or ('local', voice_client) or (None, None)."""
        # Lavalink path - try to get the actual player
        if self.use_lavalink and self._lavalink_pool:
            try:
                # First check if there's a guild voice client that's a Wavelink player
                vc = ctx.guild.voice_client
                if vc and hasattr(vc, 'play') and hasattr(vc, 'node'):  # Wavelink players have play method and node
                    print(f"[DEBUG] Found Wavelink player as voice client")
                    return ('lavalink', vc)
                
                # Otherwise try to get player from nodes with proper access
                pool_nodes = []
                if hasattr(self._lavalink_pool, 'nodes'):
                    nodes_attr = getattr(self._lavalink_pool, 'nodes')
                    if hasattr(nodes_attr, 'values'):
                        pool_nodes = list(nodes_attr.values())
                    elif hasattr(nodes_attr, '__iter__'):
                        pool_nodes = list(nodes_attr)
                
                for node in pool_nodes:
                    try:
                        if hasattr(node, 'get_player'):
                            player = node.get_player(ctx.guild.id)
                            if player:
                                print(f"[DEBUG] Found player from node")
                                return ('lavalink', player)
                    except Exception:
                        continue
            except Exception as e:
                print(f"[DEBUG] Lavalink controller lookup failed: {e}")

        # Local path - fallback for non-Wavelink voice clients
        try:
            vc = ctx.guild.voice_client or self.voice_clients.get(ctx.guild.id) or getattr(ctx, 'voice_client', None)
            if vc and not (hasattr(vc, 'play') and hasattr(vc, 'node')):  # Make sure it's not a Wavelink player
                print(f"[DEBUG] Found local voice client")
                return ('local', vc)
        except Exception:
            pass

        print(f"[DEBUG] No playback controller found")
        return (None, None)

    async def _ensure_lavalink_player(self, ctx: Context, timeout: float = 10.0):
        """Ensure a wavelink Player exists for the guild. Simplified to prevent connection loops."""
        if not self._lavalink_pool:
            raise RuntimeError('Lavalink pool not initialized')

        # First, check if we already have a valid Wavelink player
        vc = self._get_valid_voice_client(ctx.guild)
        if vc and hasattr(vc, 'play') and hasattr(vc, 'node'):
            print(f"[LAVALINK] Found valid existing Wavelink player for guild {ctx.guild.id}")
            return vc
        
        # Try to get existing player from Wavelink pool
        try:
            # For wavelink v3.4.1, try to get player from guild
            if hasattr(wavelink, 'Pool'):
                try:
                    # Try to get the player from the pool
                    player = wavelink.Pool.get_player(ctx.guild.id)
                    if player and self._is_voice_client_connected(player):
                        print(f"[LAVALINK] Found existing pool player for guild {ctx.guild.id}")
                        return player
                except Exception:
                    pass
            
            # Alternative method for getting existing players
            pool_nodes = []
            if hasattr(self._lavalink_pool, 'nodes'):
                nodes_attr = getattr(self._lavalink_pool, 'nodes')
                if hasattr(nodes_attr, 'values'):
                    pool_nodes = list(nodes_attr.values())
                elif hasattr(nodes_attr, '__iter__'):
                    pool_nodes = list(nodes_attr)
            
            for node in pool_nodes:
                try:
                    if hasattr(node, 'get_player'):
                        player = node.get_player(ctx.guild.id)
                        if player and self._is_voice_client_connected(player):
                            print(f"[LAVALINK] Found existing node player for guild {ctx.guild.id}")
                            return player
                except Exception:
                    continue
        except Exception as e:
            print(f"[LAVALINK] Player lookup failed: {e}")

        # Check if user is in voice channel
        channel = ctx.author.voice.channel if getattr(ctx.author, 'voice', None) else None
        if not channel:
            raise RuntimeError('User not in voice channel')

        # Check if bot is already connected to ANY voice channel in this guild
        existing_guild_vc = getattr(ctx.guild, 'voice_client', None)
        if existing_guild_vc:
            print(f"[LAVALINK] Bot already connected to voice channel in guild {ctx.guild.id}")
            # If it's connected but not the right type, we have a problem
            if hasattr(existing_guild_vc, 'play') and hasattr(existing_guild_vc, 'node'):
                print(f"[LAVALINK] Existing connection is a Wavelink player")
                return existing_guild_vc
            else:
                print(f"[LAVALINK] Existing connection is NOT a Wavelink player, disconnecting...")
                try:
                    await existing_guild_vc.disconnect(force=True)
                    await asyncio.sleep(1.0)  # Give it time to disconnect
                except Exception as e:
                    print(f"[LAVALINK] Failed to disconnect existing connection: {e}")

        # Enhanced connection attempt to create Wavelink player with 4006 handling
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"[LAVALINK] Creating new Wavelink Player for {channel.name} (attempt {attempt + 1}/{max_retries})")
                vc = await channel.connect(cls=wavelink.Player, timeout=timeout)
                # Critical: Wait for Discord to establish voice session (fixes error 4006)
                await asyncio.sleep(1.0)
                
                if vc and self._is_voice_client_connected(vc):
                    print(f"[LAVALINK] Wavelink Player created successfully for guild {ctx.guild.id}")
                    self.voice_clients[ctx.guild.id] = vc  # Store in our mapping
                    return vc
                else:
                    raise RuntimeError('Player created but not connected')
                    
            except discord.errors.ConnectionClosed as e:
                print(f"[LAVALINK] ConnectionClosed error (attempt {attempt + 1}): {e}")
                
                # Special handling for error 4006
                if hasattr(e, 'code') and e.code == 4006:
                    print("[LAVALINK] Error 4006 detected - waiting for Discord session reset")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2.0 + attempt * 1.0)  # Longer wait for 4006
                        continue
                        
            except Exception as e:
                error_message = str(e)
                print(f"[LAVALINK] Failed to create Wavelink player: {error_message}")
                
                # Handle specific "already connected" error
                if "already connected" in error_message.lower():
                    print(f"[LAVALINK] Bot is already connected, trying to find the existing player...")
                    # Try one more time to find the existing player
                    final_vc = self._get_valid_voice_client(ctx.guild)
                    if final_vc:
                        print(f"[LAVALINK] Found the existing player after connection error")
                        return final_vc
                    else:
                        # Force disconnect and reconnect to resolve state mismatch
                        print(f"[LAVALINK] No valid player found despite connection claim - forcing disconnect and reconnect...")
                        try:
                            if hasattr(ctx.guild, 'voice_client') and ctx.guild.voice_client:
                                await ctx.guild.voice_client.disconnect(force=True)
                            
                            # Clear any cached voice clients
                            self.voice_clients.pop(ctx.guild.id, None)
                            
                            # Wait a moment for cleanup
                            await asyncio.sleep(1.0)
                            
                            # Try to reconnect once more
                            print(f"[LAVALINK] Attempting fresh connection after cleanup...")
                            continue  # Retry the connection loop
                            
                        except Exception as cleanup_e:
                            print(f"[LAVALINK] Error during cleanup: {cleanup_e}")
                            raise RuntimeError('Bot claims to be connected but no valid player found')
                
                # Check for 4006 in general error message
                if '4006' in error_message and attempt < max_retries - 1:
                    print(f"[LAVALINK] 4006 error detected, retrying in {2.0 + attempt}s...")
                    await asyncio.sleep(2.0 + attempt * 1.0)
                    continue
                    
                if attempt == max_retries - 1:
                    raise RuntimeError(f'Failed to create Wavelink player after {max_retries} attempts: {e}')
                    
        raise RuntimeError(f'Failed to create Wavelink player after {max_retries} attempts')

    async def _ensure_lavalink_pool(self) -> bool:
        """Ensure the wavelink Pool is initialized. This attempts to dynamically
        create and connect a Pool+Node with the running bot client. Returns True
        on success, False otherwise.
        """
        if self._lavalink_pool:
            return True

        if not WAVELINK_AVAILABLE:
            return False
            
        try:
            from wavelink.node import Pool

            print('ℹ️ Dynamically initializing Lavalink pool...')
            pool = Pool()
            self._lavalink_pool = pool

            raw_uri = _os.environ.get('LAVALINK_URI', 'http://127.0.0.1:2333')
            lavalink_pass = _os.environ.get('LAVALINK_PASS', 'youshallnotpass')
            
            import urllib.parse
            parsed = urllib.parse.urlparse(raw_uri)
            scheme = parsed.scheme
            host = parsed.hostname or '127.0.0.1'
            port = parsed.port or 2333
            
            # Build WebSocket URI for Lavalink v4 (local hosting)
            if scheme in ('http', ''):
                ws_uri = f'ws://{host}:{port}/v4/websocket'
            elif scheme == 'https':
                ws_uri = f'wss://{host}:{port}/v4/websocket'
            else:
                ws_uri = raw_uri

            print(f'[LAVALINK] Connecting to Lavalink v4 at {ws_uri}')

            # Create node for Lavalink v4 - try setting User-Id via client.user
            client_name = _os.environ.get('LAVALINK_CLIENT_NAME', 'Sleepless.PY')
            
            # Set User-Id on the client for Lavalink v4 compatibility
            if hasattr(self.client, '_user_id') or self.client.user:
                user_id = str(self.client.user.id) if self.client.user else "123456789"
                # Try to set on wavelink module level
                try:
                    import wavelink
                    if hasattr(wavelink, 'USER_ID'):
                        wavelink.USER_ID = user_id
                except:
                    pass
            
            node = wavelink.Node(
                uri=ws_uri,
                password=lavalink_pass,
                identifier="SleeplessNode"
            )

            mapping = await pool.connect(nodes=[node], client=self.client)
            print(f'✅ Lavalink pool connected (local), nodes: {list(mapping.keys())}')
            return True
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f'⚠️ Failed to initialize Lavalink pool dynamically: {e}\n{tb}')
            # Ensure pool remains None on failure
            self._lavalink_pool = None
            return False

    async def play_source(self, ctx, query, skip_previews=False):
        """Main play function that handles different sources"""
        print(f"[DEBUG] play_source called with query: {query}")
        
        if not ctx.author.voice:
            print("[DEBUG] User not in voice channel")
            await ctx.send(embed=discord.Embed(
                description="<:feast_warning:1400143131990560830> You need to be in a voice channel to use this command.",
                color=0x006fb9
            ))
            return

        print("[DEBUG] User is in voice channel, starting async typing")
        async with ctx.typing():
            # Handle Spotify URLs
            if re.match(SPOTIFY_TRACK_REGEX, query):
                print("[DEBUG] Detected Spotify track URL")
                track_match = re.match(SPOTIFY_TRACK_REGEX, query)
                if track_match:
                    track_id = track_match.group(1)
                    print(f"[DEBUG] Extracting Spotify track ID: {track_id}")
                    spotify_query = await self.spotify_api.search_track(track_id)
                    if spotify_query:
                        query = spotify_query
                        print(f"[DEBUG] Converted to search query: {query}")
                    else:
                        return await ctx.send(embed=discord.Embed(
                            description="❌ Could not fetch Spotify track information.",
                            color=0xFF0000
                        ))
            elif re.match(SPOTIFY_PLAYLIST_REGEX, query) or re.match(SPOTIFY_ALBUM_REGEX, query):
                print("[DEBUG] Detected Spotify playlist or album URL")
                
                # Handle playlist
                if re.match(SPOTIFY_PLAYLIST_REGEX, query):
                    playlist_match = re.match(SPOTIFY_PLAYLIST_REGEX, query)
                    if playlist_match:
                        playlist_id = playlist_match.group(1)
                        print(f"[DEBUG] Processing Spotify playlist: {playlist_id}")
                        
                        # Get playlist info
                        playlist_info = await self.spotify_api.get_playlist_info(playlist_id)
                        if not playlist_info:
                            return await ctx.send(embed=discord.Embed(
                                description="❌ Could not fetch Spotify playlist information.",
                                color=0xFF0000
                            ))
                        
                        # Get all tracks from playlist
                        tracks = await self.spotify_api.get_playlist_tracks(playlist_id)
                        if not tracks:
                            return await ctx.send(embed=discord.Embed(
                                description="❌ No tracks found in this playlist or playlist is private.",
                                color=0xFF0000
                            ))
                        
                        # Send confirmation message
                        playlist_name = playlist_info.get('name', 'Unknown Playlist')
                        owner_name = playlist_info.get('owner', {}).get('display_name', 'Unknown')
                        total_tracks = len(tracks)
                        
                        embed = discord.Embed(
                            title="📻 Adding Spotify Playlist",
                            description=f"**{playlist_name}** by {owner_name}\n{total_tracks} tracks",
                            color=0x1DB954
                        )
                        if playlist_info.get('images'):
                            embed.set_thumbnail(url=playlist_info['images'][0]['url'])
                        
                        await ctx.send(embed=embed)
                        
                        # Add tracks to queue (limit to prevent spam)
                        max_tracks = 50  # Reasonable limit
                        added_count = 0
                        
                        for track in tracks[:max_tracks]:
                            try:
                                artist = track['artists'][0]['name'] if track.get('artists') else ''
                                title = track.get('name', '')
                                search_query = f"{artist} {title} audio"
                                
                                # Create Track object
                                data = {
                                    'title': f"{artist} - {title}",
                                    'webpage_url': search_query,
                                    'duration': 0,
                                    'thumbnail': '',
                                    'uploader': artist
                                }
                                track_obj = Track(data, requester=ctx.author, local_file=None)
                                await self.add_to_queue(ctx, track_obj, silent=True)  # Silent for playlist tracks
                                added_count += 1
                                
                                # Small delay to prevent rate limiting
                                await asyncio.sleep(0.1)
                                
                            except Exception as e:
                                print(f"[DEBUG] Failed to add track {title}: {e}")
                                continue
                        
                        # Send final status
                        final_embed = discord.Embed(
                            title="✅ Playlist Added",
                            description=f"Successfully added **{added_count}** tracks from **{playlist_name}**",
                            color=0x00E6A7
                        )
                        if added_count < total_tracks:
                            final_embed.add_field(
                                name="Note", 
                                value=f"Limited to {max_tracks} tracks. {total_tracks - added_count} tracks were skipped.",
                                inline=False
                            )
                        await ctx.send(embed=final_embed)
                        return
                
                # Handle album
                else:
                    album_match = re.match(SPOTIFY_ALBUM_REGEX, query)
                    if album_match:
                        album_id = album_match.group(1)
                        print(f"[DEBUG] Processing Spotify album: {album_id}")
                        
                        # Get album info
                        album_info = await self.spotify_api.get_album_info(album_id)
                        if not album_info:
                            return await ctx.send(embed=discord.Embed(
                                description="❌ Could not fetch Spotify album information.",
                                color=0xFF0000
                            ))
                        
                        # Get all tracks from album
                        tracks = await self.spotify_api.get_album_tracks(album_id)
                        if not tracks:
                            return await ctx.send(embed=discord.Embed(
                                description="❌ No tracks found in this album.",
                                color=0xFF0000
                            ))
                        
                        # Send confirmation message
                        album_name = album_info.get('name', 'Unknown Album')
                        artist_name = album_info.get('artists', [{}])[0].get('name', 'Unknown Artist')
                        total_tracks = len(tracks)
                        
                        embed = discord.Embed(
                            title="💿 Adding Spotify Album",
                            description=f"**{album_name}** by {artist_name}\n{total_tracks} tracks",
                            color=0x1DB954
                        )
                        if album_info.get('images'):
                            embed.set_thumbnail(url=album_info['images'][0]['url'])
                        
                        await ctx.send(embed=embed)
                        
                        # Add tracks to queue
                        added_count = 0
                        
                        for track in tracks:
                            try:
                                title = track.get('name', '')
                                search_query = f"{artist_name} {title} audio"
                                
                                # Create Track object
                                data = {
                                    'title': f"{artist_name} - {title}",
                                    'webpage_url': search_query,
                                    'duration': 0,
                                    'thumbnail': '',
                                    'uploader': artist_name
                                }
                                track_obj = Track(data, requester=ctx.author, local_file=None)
                                await self.add_to_queue(ctx, track_obj, silent=True)  # Silent for album tracks
                                added_count += 1
                                
                                # Small delay to prevent rate limiting
                                await asyncio.sleep(0.1)
                                
                            except Exception as e:
                                print(f"[DEBUG] Failed to add track {title}: {e}")
                                continue
                        
                        # Send final status
                        final_embed = discord.Embed(
                            title="✅ Album Added",
                            description=f"Successfully added **{added_count}** tracks from **{album_name}**",
                            color=0x00E6A7
                        )
                        await ctx.send(embed=final_embed)
                        return
            # Lavalink primary path: try to ensure pool and prefer Lavalink for search/stream
            if self.use_lavalink:
                pool_ok = True if self._lavalink_pool else await self._ensure_lavalink_pool()
                if pool_ok and self._lavalink_pool:
                    print(f"[DEBUG] Using enhanced Lavalink search for: {query}")
                    
                    # Use enhanced multi-source search with intelligent prioritization
                    try:
                        # Enhanced search sources with YouTube Music prioritized for quality
                        search_sources = [
                            ("ytmsearch", "YouTube Music", 0.95),  # Highest quality, official music
                            ("spsearch", "Spotify", 0.9),          # High quality, full tracks  
                            ("ytsearch", "YouTube", 0.8),          # Good quality, wide selection
                            ("scsearch", "SoundCloud", 0.4),       # Lower priority - many previews
                            ("", "Direct", 1.0)                    # Direct URLs get highest priority
                        ]
                        
                        all_candidates = []
                        found_good_match = False
                        
                        # Check if it's a direct URL first
                        if any(url_pattern in query.lower() for url_pattern in ['http://', 'https://', 'youtube.com', 'youtu.be', 'soundcloud.com', 'spotify.com']):
                            print(f"[DEBUG] Detected direct URL, trying direct search first: {query}")
                            try:
                                results = await Playable.search(query)
                                if results:
                                    playable = results[0]
                                    data = {
                                        'title': playable.title or 'Unknown',
                                        'webpage_url': playable.uri or '',
                                        'duration': playable.length // 1000 if playable.length else 0,
                                        'thumbnail': getattr(playable, 'artwork', '') or '',
                                        'uploader': playable.author or 'Unknown',
                                        'extractor': 'lavalink_v4_direct'
                                    }
                                    track = Track(data, requester=ctx.author)
                                    
                                    # Apply quality filtering even for direct URLs
                                    if self._is_valid_direct_url_track(track, query):
                                        track._lavalink_playable = playable
                                        await self.add_to_queue(ctx, track)
                                        return
                                    else:
                                        print(f"[DEBUG] Direct URL track filtered out: {track.title} (duration: {track.duration}s)")
                                        # Fall through to regular search for better alternatives
                            except Exception as e:
                                print(f"[DEBUG] Direct URL search failed: {e}")
                        
                        # Try each source with enhanced search queries
                        for source_prefix, source_name, source_weight in search_sources:
                            if not source_prefix:  # Skip direct URL source in this loop
                                continue
                                
                            try:
                                print(f"[DEBUG] Trying {source_name} with weight {source_weight}")
                                
                                # Generate enhanced search queries for this source
                                search_queries = self._generate_enhanced_search_queries(query, source_prefix)
                                
                                for search_query in search_queries:
                                    try:
                                        print(f"[DEBUG] Lavalink enhanced search ({source_name}): {search_query}")
                                        results = await Playable.search(search_query)
                                        
                                        if results:
                                            # Score each result for relevance and collect candidates
                                            for i, playable in enumerate(results[:5]):  # Check first 5 results
                                                # Convert to Track for scoring
                                                data = {
                                                    'title': playable.title or 'Unknown',
                                                    'webpage_url': playable.uri or '',
                                                    'duration': playable.length // 1000 if playable.length else 0,
                                                    'thumbnail': getattr(playable, 'artwork', '') or '',
                                                    'uploader': playable.author or 'Unknown',
                                                    'extractor': f'lavalink_v4_{source_name.lower()}'
                                                }
                                                track = Track(data, requester=ctx.author)
                                                
                                                # Enhanced filtering for better quality
                                                if self._is_valid_track_candidate(track, query, source_name):
                                                    # Additional preview check before scoring
                                                    if not skip_previews or not self._is_preview_track(track):
                                                        score = self._calculate_relevance_score(query, track) * source_weight
                                                        
                                                        # Higher threshold for better matches, especially strict for SoundCloud
                                                        min_score = 0.7 if source_name == "SoundCloud" else 0.6
                                                        if score > min_score:
                                                            all_candidates.append((track, score, playable, source_name))
                                                            print(f"[DEBUG] Added candidate: {track.title} (score: {score:.2f}, {source_name})")
                                                            
                                                            # If we find a very good Spotify match, prefer it strongly
                                                            if source_name == "Spotify" and score > 0.8:
                                                                found_good_match = True
                                                                print(f"[DEBUG] Found excellent Spotify match, stopping search")
                                                                break
                                                        else:
                                                            print(f"[DEBUG] Rejected low-score candidate: {track.title} (score: {score:.2f})")
                                                    else:
                                                        print(f"[DEBUG] Skipped preview track during search: {track.title}")
                                                else:
                                                    print(f"[DEBUG] Filtered out invalid candidate: {track.title}")
                                        
                                        # Break if we found a very good match
                                        if found_good_match:
                                            break
                                    
                                    except Exception as e:
                                        print(f"[DEBUG] Search query failed: {search_query}, error: {e}")
                                        continue
                                        
                                # Break if we found good candidates from a high-priority source
                                if found_good_match or (source_name == "Spotify" and all_candidates):
                                    print(f"[DEBUG] Found good matches from {source_name}, stopping search")
                                    break
                                        
                            except Exception as e:
                                print(f"[DEBUG] {source_name} search failed: {e}")
                                continue
                        
                        # Sort all candidates by score (best first)
                        all_candidates.sort(key=lambda x: x[1], reverse=True)
                        
                        if all_candidates:
                            # Try the best candidates with enhanced error handling
                            for i, (track, score, playable, source_name) in enumerate(all_candidates[:8]):  # Try top 8 candidates
                                print(f"[DEBUG] Trying candidate #{i+1}: {track.title} (score: {score:.2f}, {source_name})")
                                
                                try:
                                    # Store the playable for later use in play_track
                                    track._lavalink_playable = playable
                                    await self.add_to_queue(ctx, track)
                                    return
                                except Exception as e:
                                    print(f"[DEBUG] Candidate #{i+1} failed: {e}")
                                    continue
                            
                            print("[DEBUG] All candidates failed, using best match as fallback")
                            # If all candidates failed, use the best one anyway
                            best_track, best_score, best_playable, best_source = all_candidates[0]
                            best_track._lavalink_playable = best_playable
                            await self.add_to_queue(ctx, best_track)
                            return
                        else:
                            print("[DEBUG] No good candidates found, trying basic search as fallback")
                            # Enhanced fallback - try a simple search without prefix
                            try:
                                results = await Playable.search(query)
                                if results:
                                    playable = results[0]
                                    data = {
                                        'title': playable.title or query,
                                        'webpage_url': playable.uri or '',
                                        'duration': playable.length // 1000 if playable.length else 0,
                                        'thumbnail': getattr(playable, 'artwork', '') or '',
                                        'uploader': playable.author or 'Unknown',
                                        'extractor': 'lavalink_v4_fallback'
                                    }
                                    track = Track(data, requester=ctx.author)
                                    track._lavalink_playable = playable
                                    await self.add_to_queue(ctx, track)
                                    return
                            except Exception as e:
                                print(f"[DEBUG] Fallback search failed: {e}")
                            
                            # Final fallback
                            data = {
                                'title': query,
                                'webpage_url': query,
                                'duration': 0,
                                'thumbnail': '',
                                'uploader': 'Unknown'
                            }
                            track = Track(data, requester=ctx.author, local_file=None)
                            await self.add_to_queue(ctx, track)
                            return
                    
                    except Exception as e:
                        print(f"[DEBUG] Enhanced search failed, using fallback: {e}")
                        # Fallback to original simple behavior
                        data = {
                            'title': query,
                            'webpage_url': query,
                            'duration': 0,
                            'thumbnail': '',
                            'uploader': ''
                        }
                        track = Track(data, requester=ctx.author, local_file=None)
                        await self.add_to_queue(ctx, track)
                        return
                else:
                    print("[WARN] Lavalink requested but pool not available; will fall back based on ALLOW_DOWNLOAD_FALLBACK")

            # If we reach here, fallback to searching/downloading via yt-dlp
            allow_fallback = bool(_os.environ.get('ALLOW_DOWNLOAD_FALLBACK', '1'))
            if not allow_fallback:
                return await ctx.send(embed=discord.Embed(
                    description="❌ Lavalink playback is not available and download fallback is disabled.",
                    color=0xFF0000
                ))

            print(f"[DEBUG] Searching and downloading track for query: {query}")
            track = await self.search_and_download_track(query)
            if not track:
                print("[DEBUG] No track found")
                return await ctx.send(embed=discord.Embed(
                    description="❌ No results found for your search.",
                    color=0xFF0000
                ))

            print(f"[DEBUG] Track found: {track.title}, local_file: {track.local_file}")
            # Ensure the requester is set
            if not track.requester:
                track.requester = ctx.author
            await self.add_to_queue(ctx, track)

    # COMMANDS START HERE

    @commands.command(name="play", aliases=['p'], usage="play <query>", help="Plays a song or playlist.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def play(self, ctx: Context, *, query: str = None):
        """Play a song"""
        if not query:
            await ctx.send(embed=discord.Embed(description="❌ You must provide a song name or link! Usage: play <query>", color=0xFF0000))
            return
        await self.play_source(ctx, query)

    @commands.hybrid_command(name="search", usage="search <query>", help="Searches music from multiple platforms.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def search2(self, ctx: Context, *, query: str = None):
        """Search for music on different platforms"""
        if not query:
            await ctx.send(embed=discord.Embed(description="❌ You must provide a search term! Usage: search <query>", color=0xFF0000))
            return
        if not ctx.author.voice:
            await ctx.send(embed=discord.Embed(
                description="<:feast_warning:1400143131990560830> You need to be in a voice channel to use this command.",
                color=0x006fb9
            ))
            return
        embed = discord.Embed(
            title="Select a platform to search from:",
            description="Click a button below to choose.",
            color=0xff0000
        )
        await ctx.send(embed=embed, view=PlatformSelectView(ctx, query, self))

    @commands.hybrid_command(name="nowplaying", aliases=["nop"], usage="nowplaying", help="Shows the info about current playing song.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def nowplaying(self, ctx: Context):
        """Show currently playing track"""
        mode, controller = await self._get_playback_controller(ctx)
        if mode is None:
            await ctx.send(embed=discord.Embed(description="No song is currently playing.", color=0xFF0000))
            return

        track = self.current_tracks.get(ctx.guild.id)
        if not track:
            await ctx.send(embed=discord.Embed(description="No current track information available.", color=0xFF0000))
            return

        position = 0  # We don't track position in this implementation
        length = track.duration if track.duration else 0

        progress_bar = self.create_progress_bar(position, length, length=10)
        position_str = f"{int(position // 60)}:{int(position % 60):02}"
        length_str = f"{int(length // 60)}:{int(length % 60):02}"

        queue_length = len(self.music_queues.get(ctx.guild.id, []))

        source_name = track.source.title() if track.source != 'unknown' else "Unknown Source"

        embed = discord.Embed(
            title="Now Playing",
            color=0x1DB954 if source_name == "Spotify" else 0xFF0000
        )
        embed.add_field(name="Track", value=f"[{track.title}]({track.webpage_url})" if track.webpage_url else track.title, inline=False)
        embed.add_field(name="Song By", value=track.author, inline=False)
        embed.add_field(name="Progress", value=f"{position_str} [{progress_bar}] {length_str}", inline=False)
        embed.add_field(name="Duration", value=length_str, inline=False)
        embed.add_field(name="Queue Length", value=str(queue_length), inline=False)
        embed.add_field(name="Source", value=f"{source_name} - [Link]({track.webpage_url})" if track.webpage_url else source_name, inline=False)
        embed.set_thumbnail(url=track.thumbnail if track.thumbnail else "")
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)

        await ctx.send(embed=embed)

    @commands.hybrid_command(name="autoplay", usage="autoplay", help="Toggles autoplay mode.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def autoplay(self, ctx: Context):
        """Toggle autoplay mode"""
        vc = ctx.voice_client
        if not vc:
            await ctx.send(embed=discord.Embed(description="<:feast_warning:1400143131990560830> Not connected to a voice channel.", color=0x006fb9))
            return

        if not ctx.author.voice or ctx.author.voice.channel.id != vc.channel.id:
            await ctx.send(embed=discord.Embed(description="<:feast_warning:1400143131990560830> You need to be in the same voice channel as me to use this command.", color=0xFF0000))
            return

        queue = self.get_queue(ctx.guild.id)
        queue.autoplay_mode = not queue.autoplay_mode
        
        mode = "enabled" if queue.autoplay_mode else "disabled"
        await ctx.send(embed=discord.Embed(description=f"Autoplay {mode} by **{ctx.author.display_name}**.", color=0x00E6A7))

    @commands.hybrid_command(name="loop", usage="loop", help="Toggles loop mode.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def loop(self, ctx: Context):
        """Toggle loop mode"""
        vc = ctx.voice_client
        if not vc:
            await ctx.send(embed=discord.Embed(description="<:feast_warning:1400143131990560830> Not connected to a voice channel.", color=0x006fb9))
            return

        if not ctx.author.voice or ctx.author.voice.channel.id != vc.channel.id:
            await ctx.send(embed=discord.Embed(description="<:feast_warning:1400143131990560830> You need to be in the same voice channel as me to use this command.", color=0xFF0000))
            return

        queue = self.get_queue(ctx.guild.id)
        queue.loop_mode = not queue.loop_mode
        
        mode = "enabled" if queue.loop_mode else "disabled"
        await ctx.send(embed=discord.Embed(description=f"Loop {mode} by **{ctx.author.display_name}**.", color=0x00E6A7))

    @commands.hybrid_command(name="pause", usage="pause", help="Pauses the current song.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def pause(self, ctx: Context):
        """Pause the current track"""
        mode, controller = await self._get_playback_controller(ctx)
        if mode is None:
            await ctx.send(embed=discord.Embed(description="<:feast_warning:1400143131990560830> No song is currently playing.", color=0x006fb9))
            return

        if mode == 'lavalink':
            try:
                await controller.pause(True)
                await ctx.send(embed=discord.Embed(description=f"⏸️ Paused by **{ctx.author.display_name}**.", color=0x00E6A7))
            except Exception as e:
                await ctx.send(embed=discord.Embed(description=f"❌ Failed to pause: {e}", color=0xFF0000))
        else:
            controller.pause()
            await ctx.send(embed=discord.Embed(description=f"⏸️ Paused by **{ctx.author.display_name}**.", color=0x00E6A7))

    @commands.hybrid_command(name="resume", usage="resume", help="Resumes the paused song.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def resume(self, ctx: Context):
        """Resume the paused track"""
        mode, controller = await self._get_playback_controller(ctx)
        if mode is None:
            await ctx.send(embed=discord.Embed(description="<:feast_warning:1400143131990560830> No song is currently paused.", color=0x006fb9))
            return

        if mode == 'lavalink':
            try:
                await controller.pause(False)
                await ctx.send(embed=discord.Embed(description=f"▶️ Resumed by **{ctx.author.display_name}**.", color=0x00E6A7))
            except Exception as e:
                await ctx.send(embed=discord.Embed(description=f"❌ Failed to resume: {e}", color=0xFF0000))
        else:
            controller.resume()
            await ctx.send(embed=discord.Embed(description=f"▶️ Resumed by **{ctx.author.display_name}**.", color=0x00E6A7))

    @commands.hybrid_command(name="skip", usage="skip", help="Skips the current song.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def skip(self, ctx: Context):
        """Skip the current track"""
        queue = self.get_queue(ctx.guild.id)
        print(f"[DEBUG SKIP] Queue has {len(queue.queue)} tracks before skip")
        
        mode, controller = await self._get_playback_controller(ctx)
        if mode is None:
            await ctx.send(embed=discord.Embed(description="<:feast_warning:1400143131990560830> No song is currently playing.", color=0x006fb9))
            return

        print(f"[DEBUG SKIP] Using {mode} mode to skip")

        if mode == 'lavalink':
            try:
                await controller.stop()
                await ctx.send(embed=discord.Embed(description=f"⏭️ Skipped by **{ctx.author.display_name}**.", color=0x00E6A7))
            except Exception as e:
                await ctx.send(embed=discord.Embed(description=f"❌ Failed to skip: {e}", color=0xFF0000))
        else:
            controller.stop()
            await ctx.send(embed=discord.Embed(description=f"⏭️ Skipped by **{ctx.author.display_name}**.", color=0x00E6A7))
            # For local mode, manually trigger playing next track
            await self.play_next(ctx)

    @commands.hybrid_command(name="shuffle", usage="shuffle", help="Shuffles the queue.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def shuffle(self, ctx: Context):
        """Shuffle the queue"""
        vc = ctx.voice_client
        if not vc:
            await ctx.send(embed=discord.Embed(description="<:feast_warning:1400143131990560830> Not connected to a voice channel.", color=0x006fb9))
            return

        if not ctx.author.voice or ctx.author.voice.channel.id != vc.channel.id:
            await ctx.send(embed=discord.Embed(description="<:feast_warning:1400143131990560830> You need to be in the same voice channel as me to use this command.", color=0xFF0000))
            return

        queue = self.get_queue(ctx.guild.id)
        if queue.is_empty():
            await ctx.send(embed=discord.Embed(description="<:feast_warning:1400143131990560830> The queue is empty.", color=0x006fb9))
            return

        queue.shuffle()
        await ctx.send(embed=discord.Embed(description=f"🔀 Queue shuffled by **{ctx.author.display_name}**.", color=0x00E6A7))

    @commands.hybrid_command(name="stop", usage="stop", help="Stops the music and disconnects.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def stop(self, ctx: Context):
        """Stop music and disconnect"""
        mode, controller = await self._get_playback_controller(ctx)
        if mode is None:
            await ctx.send(embed=discord.Embed(description="<:feast_warning:1400143131990560830> Not connected to a voice channel.", color=0x006fb9))
            return

        queue = self.get_queue(ctx.guild.id)
        queue.clear()

        if mode == 'lavalink':
            try:
                await controller.stop()
                await controller.disconnect()
                await ctx.send(embed=discord.Embed(description=f"⏹️ Stopped by **{ctx.author.display_name}**.", color=0x00E6A7))
            except Exception as e:
                await ctx.send(embed=discord.Embed(description=f"❌ Failed to stop: {e}", color=0xFF0000))
        else:
            if controller.is_playing() or controller.is_paused():
                controller.stop()
            await controller.disconnect()
            if ctx.guild.id in self.voice_clients:
                del self.voice_clients[ctx.guild.id]
            await ctx.send(embed=discord.Embed(description=f"⏹️ Stopped by **{ctx.author.display_name}**.", color=0x00E6A7))

    @commands.hybrid_command(name="volume", usage="volume <level>", help="Sets the volume level.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def volume(self, ctx: Context, level: int = None):
        """Set volume level"""
        if level is None:
            await ctx.send(embed=discord.Embed(description="❌ You must provide a volume level! Usage: volume <level>", color=0xFF0000))
            return
        if not 0 <= level <= 100:
            await ctx.send(embed=discord.Embed(description="❌ Volume must be between 0 and 100.", color=0xFF0000))
            return
        mode, controller = await self._get_playback_controller(ctx)
        if mode is None:
            await ctx.send(embed=discord.Embed(description="<:feast_warning:1400143131990560830> Not connected to a voice channel.", color=0x006fb9))
            return
        if mode == 'lavalink':
            try:
                await controller.set_volume(level)
                # Save volume to database
                await self._save_volume_to_db(ctx.guild.id, level)
                await ctx.send(embed=discord.Embed(description=f"🔊 Volume set to **{level}%** by **{ctx.author.display_name}**.", color=0x00E6A7))
            except Exception as e:
                await ctx.send(embed=discord.Embed(description=f"❌ Failed to set volume: {e}", color=0xFF0000))
        else:
            if controller.source and hasattr(controller.source, 'volume'):
                controller.source.volume = level / 100.0
                # Save volume to database
                await self._save_volume_to_db(ctx.guild.id, level)
                await ctx.send(embed=discord.Embed(description=f"🔊 Volume set to **{level}%** by **{ctx.author.display_name}**.", color=0x00E6A7))
            else:
                await ctx.send(embed=discord.Embed(description="❌ Cannot adjust volume for current track.", color=0xFF0000))

    @commands.hybrid_command(name="queue", usage="queue", help="Shows the current music queue.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def queue(self, ctx: Context):
        """Show the music queue"""
        queue = self.get_queue(ctx.guild.id)
        current_track = self.current_tracks.get(ctx.guild.id)

        if not current_track and queue.is_empty():
            await ctx.send(embed=discord.Embed(description="❌ The queue is empty.", color=0xFF0000))
            return

        embed = discord.Embed(title="🎵 Music Queue", color=0x00E6A7)
        
        # Current track
        if current_track:
            embed.add_field(
                name="🎵 Now Playing",
                value=f"**{current_track.title}** - {current_track.author}",
                inline=False
            )

        # Queue
        if not queue.is_empty():
            queue_list = []
            for i, track in enumerate(list(queue.queue)[:10], 1):
                requester = track.requester.display_name if track.requester else "Unknown"
                queue_list.append(f"`{i}.` **{track.title}** - {track.author} *[Requested by {requester}]*")
            
            if len(queue.queue) > 10:
                queue_list.append(f"... and {len(queue.queue) - 10} more tracks")
                
            embed.add_field(
                name="📋 Up Next",
                value="\n".join(queue_list),
                inline=False
            )

        # Queue info
        embed.add_field(
            name="ℹ️ Queue Info",
            value=f"Total tracks: {len(queue.queue)}\nLoop: {'✅' if queue.loop_mode else '❌'}\nShuffle: {'✅' if queue.shuffle_mode else '❌'}",
            inline=True
        )

        await ctx.send(embed=embed)

    @commands.hybrid_command(name="clearqueue", aliases=["clear"], usage="clearqueue", help="Clears the music queue.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def clearqueue(self, ctx: Context):
        """Clear the queue"""
        vc = ctx.voice_client
        if not vc:
            await ctx.send(embed=discord.Embed(description="<:feast_warning:1400143131990560830> Not connected to a voice channel.", color=0x006fb9))
            return

        if not ctx.author.voice or ctx.author.voice.channel.id != vc.channel.id:
            await ctx.send(embed=discord.Embed(description="<:feast_warning:1400143131990560830> You need to be in the same voice channel as me to use this command.", color=0xFF0000))
            return

        queue = self.get_queue(ctx.guild.id)
        if queue.is_empty():
            await ctx.send(embed=discord.Embed(description="❌ The queue is already empty.", color=0xFF0000))
            return

        queue.clear()
        await ctx.send(embed=discord.Embed(description=f"🗑️ Queue cleared by **{ctx.author.display_name}**.", color=0x00E6A7))

    @commands.hybrid_command(name="replay", usage="replay", help="Replays the current song.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def replay(self, ctx: Context):
        """Replay the current track"""
        mode, controller = await self._get_playback_controller(ctx)
        if mode is None:
            await ctx.send(embed=discord.Embed(description="<:feast_warning:1400143131990560830> Not connected to a voice channel.", color=0x006fb9))
            return

        current_track = self.current_tracks.get(ctx.guild.id)
        if not current_track:
            await ctx.send(embed=discord.Embed(description="❌ No track is currently playing.", color=0xFF0000))
            return

        if mode == 'lavalink':
            try:
                await controller.stop()
                await self.play_track(ctx, current_track)
                await ctx.send(embed=discord.Embed(description=f"🔄 Replaying **{current_track.title}** by **{ctx.author.display_name}**.", color=0x00E6A7))
            except Exception as e:
                await ctx.send(embed=discord.Embed(description=f"❌ Failed to replay: {e}", color=0xFF0000))
        else:
            if controller.is_playing() or controller.is_paused():
                controller.stop()
            await self.play_track(ctx, current_track)
            await ctx.send(embed=discord.Embed(description=f"🔄 Replaying **{current_track.title}** by **{ctx.author.display_name}**.", color=0x00E6A7))

    @commands.hybrid_command(name="join", usage="join", help="Joins your voice channel.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def join(self, ctx: Context):
        """Join voice channel"""
        # Check if guild is blocked due to recent 4006 errors
        if self._is_guild_4006_blocked(ctx.guild.id):
            error_count = self._guild_4006_counts.get(ctx.guild.id, 1)
            await ctx.send(embed=discord.Embed(
                description=f"❌ Voice connection temporarily blocked due to repeated errors. Please try again in a moment.",
                color=0xFF0000
            ))
            return
            
        if not ctx.author.voice:
            await ctx.send(embed=discord.Embed(description="❌ You need to be in a voice channel.", color=0xFF0000))
            return

        if ctx.voice_client:
            await ctx.send(embed=discord.Embed(description="❌ Already connected to a voice channel.", color=0xFF0000))
            return

        try:
            # Add timeout and better error handling for voice connection
            channel = ctx.author.voice.channel
            
            # Check bot permissions
            if not channel.permissions_for(ctx.guild.me).connect:
                await ctx.send(embed=discord.Embed(
                    description="❌ I don't have permission to connect to that voice channel.", 
                    color=0xFF0000
                ))
                return
            
            if not channel.permissions_for(ctx.guild.me).speak:
                await ctx.send(embed=discord.Embed(
                    description="❌ I don't have permission to speak in that voice channel.", 
                    color=0xFF0000
                ))
                return
            
            # Send connecting message
            connecting_msg = await ctx.send(embed=discord.Embed(
                description=f"🔄 Connecting to **{channel.name}**...", 
                color=0xFFFF00
            ))
            
            # Connect with enhanced 4006 error handling
            max_retries = 3
            last_error = None
            vc = None
            
            for attempt in range(max_retries):
                try:
                    print(f"[MUSIC] Voice connection attempt {attempt + 1}/{max_retries}")
                    
                    # Clear any existing invalid connections
                    if ctx.guild.voice_client:
                        try:
                            await ctx.guild.voice_client.disconnect(force=True)
                            await asyncio.sleep(0.5)
                        except:
                            pass
                    
                    # Attempt connection
                    if VOICE_HELPER_AVAILABLE:
                        vc = await safe_voice_connect(channel, timeout=15.0, max_retries=1)
                    else:
                        vc = await asyncio.wait_for(channel.connect(reconnect=True), timeout=15.0)
                    
                    if vc and hasattr(vc, 'is_connected') and vc.is_connected():
                        print(f"[MUSIC] Successfully connected on attempt {attempt + 1}")
                        break
                    else:
                        raise discord.ClientException("Connection failed - voice client not connected")
                        
                except discord.errors.ConnectionClosed as e:
                    last_error = e
                    print(f"[MUSIC] ConnectionClosed (attempt {attempt + 1}): {e}")
                    
                    # Special handling for error 4006
                    if hasattr(e, 'code') and e.code == 4006:
                        print("[MUSIC] Error 4006 detected - recording error and performing cleanup")
                        self._record_4006_error(ctx.guild.id)
                        
                        try:
                            if ctx.guild.voice_client:
                                await ctx.guild.voice_client.disconnect(force=True)
                        except:
                            pass
                        
                        # Wait progressively longer for session reset
                        wait_time = 2.0 + attempt * 1.5
                        print(f"[MUSIC] Waiting {wait_time}s for Discord session reset")
                        await asyncio.sleep(wait_time)
                        
                        # Break out of retry loop for 4006 errors to prevent spam
                        if attempt >= 1:  # Allow one retry, then give up
                            break
                    else:
                        if attempt < max_retries - 1:
                            await asyncio.sleep(1.0)
                
                except asyncio.TimeoutError:
                    last_error = TimeoutError("Connection timeout")
                    print(f"[MUSIC] Connection timeout (attempt {attempt + 1})")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(1.0)
                        
                except Exception as e:
                    last_error = e
                    print(f"[MUSIC] Connection error (attempt {attempt + 1}): {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(0.5)
            
            if not vc or not hasattr(vc, 'is_connected') or not vc.is_connected():
                error_msg = "❌ Failed to connect to voice channel."
                if last_error:
                    if hasattr(last_error, 'code') and last_error.code == 4006:
                        error_msg += " (Discord voice gateway error - try again in a moment)"
                    elif "timeout" in str(last_error).lower():
                        error_msg += " (Connection timed out - check network)"
                    else:
                        error_msg += f" ({str(last_error)[:50]})"
                
                await connecting_msg.edit(embed=discord.Embed(
                    description=error_msg,
                    color=0xFF0000
                ))
                return
            self.voice_clients[ctx.guild.id] = vc
            
            # Update message to success
            await connecting_msg.edit(embed=discord.Embed(
                description=f"✅ Joined **{channel.name}**.", 
                color=0x00E6A7
            ))
            
        except asyncio.TimeoutError:
            await ctx.send(embed=discord.Embed(
                description="❌ Connection timed out. The voice channel might be full or there may be network issues.", 
                color=0xFF0000
            ))
        except discord.ClientException as e:
            if "already connected" in str(e).lower():
                await ctx.send(embed=discord.Embed(
                    description="❌ Already connected to a voice channel.", 
                    color=0xFF0000
                ))
            else:
                await ctx.send(embed=discord.Embed(
                    description=f"❌ Failed to connect: {str(e)}", 
                    color=0xFF0000
                ))
        except discord.Forbidden:
            await ctx.send(embed=discord.Embed(
                description="❌ I don't have permission to join that voice channel.", 
                color=0xFF0000
            ))
        except discord.HTTPException:
            await ctx.send(embed=discord.Embed(
                description="❌ Discord connection error. Please try again.", 
                color=0xFF0000
            ))
        except Exception as e:
            await ctx.send(embed=discord.Embed(
                description=f"❌ An unexpected error occurred: {str(e)}", 
                color=0xFF0000
            ))
            print(f"Voice connection error: {e}")
            import traceback
            traceback.print_exc()

    @commands.hybrid_command(name="disconnect", aliases=["leave"], usage="disconnect", help="Disconnects from voice channel.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def disconnect(self, ctx: Context):
        """Disconnect from voice channel"""
        vc = ctx.voice_client
        if not vc:
            await ctx.send(embed=discord.Embed(description="❌ Not connected to a voice channel.", color=0xFF0000))
            return

        if not ctx.author.voice or ctx.author.voice.channel.id != vc.channel.id:
            await ctx.send(embed=discord.Embed(description="❌ You need to be in the same voice channel.", color=0xFF0000))
            return

        try:
            # Clear the queue
            queue = self.get_queue(ctx.guild.id)
            queue.clear()
            
            # Get channel name before disconnecting
            channel_name = vc.channel.name if vc.channel else "voice channel"
            
            # Disconnect with timeout
            await asyncio.wait_for(vc.disconnect(), timeout=5.0)
            
            # Clean up voice client reference
            if ctx.guild.id in self.voice_clients:
                del self.voice_clients[ctx.guild.id]

            await ctx.send(embed=discord.Embed(
                description=f"👋 Disconnected from **{channel_name}** by **{ctx.author.display_name}**.", 
                color=0x00E6A7
            ))
            
        except asyncio.TimeoutError:
            # Force cleanup even if disconnect times out
            if ctx.guild.id in self.voice_clients:
                del self.voice_clients[ctx.guild.id]
            await ctx.send(embed=discord.Embed(
                description="⚠️ Disconnect timed out, but cleaned up connection.", 
                color=0xFFFF00
            ))
        except Exception as e:
            # Force cleanup on any error
            if ctx.guild.id in self.voice_clients:
                del self.voice_clients[ctx.guild.id]
            await ctx.send(embed=discord.Embed(
                description=f"⚠️ Disconnected with error: {str(e)}", 
                color=0xFFFF00
            ))
            print(f"Voice disconnect error: {e}")

    @commands.hybrid_command(name="seek", usage="seek <seconds>", help="Seeks to a specific time in the current track.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def seek(self, ctx: Context, seconds: int = None):
        """Seek to a specific time in the current track"""
        if seconds is None:
            await ctx.send(embed=discord.Embed(description="❌ You must provide the number of seconds to seek! Usage: seek <seconds>", color=0xFF0000))
            return
        vc = ctx.voice_client
        if not vc or not vc.is_playing():
            await ctx.send(embed=discord.Embed(description="<:feast_warning:1400143131990560830> No song is currently playing.", color=0x006fb9))
            return
        if not ctx.author.voice or ctx.author.voice.channel.id != vc.channel.id:
            await ctx.send(embed=discord.Embed(description="<:feast_warning:1400143131990560830> You need to be in the same voice channel as me to use this command.", color=0xFF0000))
            return
        current_track = self.current_tracks.get(ctx.guild.id)
        if not current_track:
            await ctx.send(embed=discord.Embed(description="❌ No track information available.", color=0xFF0000))
            return
        if seconds < 0 or (current_track.duration and seconds > current_track.duration):
            await ctx.send(embed=discord.Embed(description="❌ Invalid seek time.", color=0xFF0000))
            return
        # Note: Seeking in direct PCM streaming is limited
        # This is a simplified implementation that restarts the track
        await ctx.send(embed=discord.Embed(description=f"🔄 Seeking functionality is limited in direct streaming mode. Restarting track instead.", color=0xFF8800))
        if vc.is_playing() or vc.is_paused():
            vc.stop()
        await self.play_track(ctx, current_track)

    @commands.command(name="clearvoiceblock", help="(Owner-only) Clear voice connection blocks for this server.")
    @commands.is_owner()
    async def clear_voice_block(self, ctx: Context):
        """Clear 4006 error blocks for the current guild"""
        if ctx.guild.id in self._guild_4006_errors:
            del self._guild_4006_errors[ctx.guild.id]
            await ctx.send(embed=discord.Embed(
                description="✅ Voice connection block cleared for this server.",
                color=0x00E6A7
            ))
        else:
            await ctx.send(embed=discord.Embed(
                description="ℹ️ No voice connection block found for this server.",
                color=0x006fb9
            ))

    @commands.command(name="debugplay", help="(Owner-only) Play the latest downloaded file for testing.")
    @commands.is_owner()
    async def debugplay(self, ctx: Context):
        downloads_dir = 'downloads'
        if not os.path.exists(downloads_dir):
            await ctx.send("No downloads directory found.")
            return

        files = [os.path.join(downloads_dir, f) for f in os.listdir(downloads_dir) if os.path.isfile(os.path.join(downloads_dir, f))]
        if not files:
            await ctx.send("No downloaded files found.")
            return

        latest = max(files, key=lambda p: os.path.getmtime(p))

        # Create a minimal Track object wrapping the file
        data = {'title': os.path.basename(latest), 'duration': 0, 'webpage_url': '', 'thumbnail': '', 'extractor': 'local'}
        track = Track(data, requester=ctx.author, local_file=latest)

        await ctx.send(f"Attempting to play local file: {os.path.basename(latest)}")
        await self.add_to_queue(ctx, track)

    @commands.command(name="lavalink", aliases=["lres", "lrec", "lstat"], help="(Owner-only) Manage the Lavalink server. Use f.lres (restart), f.lrec (reconnect), f.lstat (status)")
    @commands.is_owner()
    async def restart_lavalink(self, ctx: Context, action: str = "restart"):
        """Restart or manage the Lavalink server
        
        Aliases:
        - f.res: Quick restart (same as f.lavalink restart)
        - f.rec: Quick reconnect (same as f.lavalink reconnect)  
        - f.ls: Quick status (same as f.lavalink status)
        """
        if not self.use_lavalink:
            await ctx.send(embed=discord.Embed(
                description="❌ Lavalink is not enabled on this bot.",
                color=0xFF0000
            ))
            return
        
        # Smart defaults based on alias used
        command_used = ctx.invoked_with.lower()
        if command_used == "lres":
            action = "restart"
        elif command_used == "lrec":  
            action = "reconnect"
        elif command_used == "lstat":
            action = "status"
            
        # Send initial message
        status_msg = await ctx.send(embed=discord.Embed(
            description="🔄 Managing Lavalink server...",
            color=0xFFFF00
        ))
        
        if action.lower() in ["restart", "reload"]:
            try:
                # First, disconnect all voice clients to prevent issues
                disconnected_guilds = []
                for guild_id, vc in self.voice_clients.copy().items():
                    try:
                        if vc and vc.is_connected():
                            guild_name = vc.guild.name if vc.guild else f"Guild {guild_id}"
                            await vc.disconnect()
                            disconnected_guilds.append(guild_name)
                            del self.voice_clients[guild_id]
                    except Exception as e:
                        print(f"[LAVALINK] Error disconnecting from guild {guild_id}: {e}")
                
                # Clear music queues
                for guild_id in list(self.music_queues.keys()):
                    queue = self.music_queues[guild_id]
                    queue.clear()
                    queue.current_track = None
                
                # Clear current tracks
                self.current_tracks.clear()
                
                # Disconnect Lavalink pool
                pool_disconnected = False
                if self._lavalink_pool:
                    try:
                        await self._lavalink_pool.close()
                        self._lavalink_pool = None
                        pool_disconnected = True
                        print("[LAVALINK] Pool disconnected successfully")
                    except Exception as e:
                        print(f"[LAVALINK] Error disconnecting pool: {e}")
                
                await status_msg.edit(embed=discord.Embed(
                    description="🔄 Lavalink pool disconnected. Attempting to restart Lavalink server...",
                    color=0xFFFF00
                ))
                
                # Try to restart Lavalink using PowerShell
                try:
                    # Kill existing Lavalink processes
                    kill_cmd = ['powershell.exe', '-Command', 
                              'Get-Process -Name "java" -ErrorAction SilentlyContinue | Where-Object {$_.CommandLine -like "*Lavalink*"} | Stop-Process -Force']
                    subprocess.run(kill_cmd, capture_output=True, timeout=10)
                    
                    # Wait a moment for processes to stop
                    await asyncio.sleep(2)
                    
                    # Start new Lavalink process
                    lavalink_dir = os.path.join(os.getcwd(), 'lavalink')
                    start_cmd = [
                        'powershell.exe', '-NoProfile', '-Command',
                        f'Set-Location "{lavalink_dir}"; java -Dspring.cloud.config.enabled=false -jar Lavalink_v4.jar --spring.config.location=application.yml'
                    ]
                    
                    # Start Lavalink in background
                    subprocess.Popen(start_cmd, cwd=lavalink_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    
                    await status_msg.edit(embed=discord.Embed(
                        description="🔄 Lavalink server restarted. Waiting for connection...",
                        color=0xFFFF00
                    ))
                    
                    # Wait for Lavalink to start
                    await asyncio.sleep(8)
                    
                    # Reconnect pool
                    try:
                        pool_ok = await self._ensure_lavalink_pool()
                        if pool_ok and self._lavalink_pool:
                            reconnect_count = 0
                            
                            # Provide option to reconnect to voice channels
                            embed = discord.Embed(
                                title="✅ Lavalink Restart Complete",
                                color=0x00FF00
                            )
                            
                            if disconnected_guilds:
                                embed.add_field(
                                    name="Disconnected Servers",
                                    value=f"Disconnected from {len(disconnected_guilds)} servers:\n" + 
                                          "\n".join(f"• {guild}" for guild in disconnected_guilds[:5]) +
                                          (f"\n... and {len(disconnected_guilds)-5} more" if len(disconnected_guilds) > 5 else ""),
                                    inline=False
                                )
                            
                            embed.add_field(
                                name="Status",
                                value="✅ Lavalink server is running\n✅ Pool reconnected\n🔄 Music queues cleared",
                                inline=False
                            )
                            
                            embed.add_field(
                                name="Next Steps",
                                value="Use `f.join` to reconnect to voice channels and `f.play` to resume music.",
                                inline=False
                            )
                            
                            await status_msg.edit(embed=embed)
                            
                        else:
                            raise Exception("Failed to reconnect Lavalink pool")
                            
                    except Exception as e:
                        await status_msg.edit(embed=discord.Embed(
                            title="⚠️ Partial Success",
                            description=f"Lavalink server restarted but pool connection failed: {e}\n\nTry using `f.lavalink status` to check connection.",
                            color=0xFF8800
                        ))
                        
                except subprocess.TimeoutExpired:
                    await status_msg.edit(embed=discord.Embed(
                        description="❌ Timeout while restarting Lavalink server.",
                        color=0xFF0000
                    ))
                    
                except Exception as e:
                    await status_msg.edit(embed=discord.Embed(
                        title="❌ Restart Failed",
                        description=f"Failed to restart Lavalink server: {e}\n\nTry manually restarting Lavalink and using `f.lavalink reconnect`.",
                        color=0xFF0000
                    ))
                    
            except Exception as e:
                await status_msg.edit(embed=discord.Embed(
                    description=f"❌ Error during Lavalink management: {e}",
                    color=0xFF0000
                ))
                
        elif action.lower() == "reconnect":
            try:
                # Just try to reconnect the pool without restarting server
                if self._lavalink_pool:
                    await self._lavalink_pool.close()
                    self._lavalink_pool = None
                
                await asyncio.sleep(2)
                pool_ok = await self._ensure_lavalink_pool()
                
                if pool_ok and self._lavalink_pool:
                    await status_msg.edit(embed=discord.Embed(
                        description="✅ Successfully reconnected to Lavalink server.",
                        color=0x00FF00
                    ))
                else:
                    await status_msg.edit(embed=discord.Embed(
                        description="❌ Failed to reconnect to Lavalink server. Check if server is running.",
                        color=0xFF0000
                    ))
                    
            except Exception as e:
                await status_msg.edit(embed=discord.Embed(
                    description=f"❌ Reconnection failed: {e}",
                    color=0xFF0000
                ))
                
        elif action.lower() == "status":
            # Show detailed status
            embed = discord.Embed(title="🎵 Lavalink Server Status", color=0x00E6A7)
            
            # Check pool status
            pool_status = "✅ Connected" if self._lavalink_pool else "❌ Not connected"
            embed.add_field(name="Pool Status", value=pool_status, inline=True)
            
            # Check if server is running (try to connect)
            try:
                lavalink_uri = _os.environ.get('LAVALINK_URI', 'http://127.0.0.1:2333')
                import requests
                response = requests.get(f"{lavalink_uri}/version", timeout=5)
                server_status = f"✅ Running (HTTP {response.status_code})"
                if response.status_code == 200:
                    try:
                        version_data = response.json()
                        server_status += f"\n📦 Version: {version_data.get('semver', 'Unknown')}"
                    except:
                        pass
            except requests.exceptions.ConnectionError:
                server_status = "❌ Server not responding"
            except Exception as e:
                server_status = f"⚠️ Status check failed: {e}"
                
            embed.add_field(name="Server Status", value=server_status, inline=True)
            
            # Node count
            if self._lavalink_pool:
                try:
                    nodes = getattr(self._lavalink_pool, 'nodes', {})
                    node_count = len(nodes) if nodes else 0
                    embed.add_field(name="Connected Nodes", value=f"{node_count} nodes", inline=True)
                except:
                    embed.add_field(name="Connected Nodes", value="Unable to count", inline=True)
            else:
                embed.add_field(name="Connected Nodes", value="Pool not connected", inline=True)
            
            await status_msg.edit(embed=embed)
            
        else:
            await status_msg.edit(embed=discord.Embed(
                title="❌ Invalid Action",
                description=f"Available actions: `restart`, `reconnect`, `status`\n**Quick aliases:** `f.lres` (restart), `f.lrec` (reconnect), `f.lstat` (status)\n**Quick fix:** `f.lavfix` (restart for search issues)\n**Usage:** `f.lavalink restart` or `f.lres`",
                color=0xFF0000
            ))

    @commands.hybrid_command(name="musicperms", aliases=["mperms", "voiceperms"], help="Check bot's voice permissions")
    @blacklist_check()
    @ignore_check()
    async def check_music_permissions(self, ctx: Context):
        """Check the bot's permissions in user's voice channel"""
        if not getattr(ctx.author, 'voice', None) or not ctx.author.voice.channel:
            return await ctx.send("❌ You need to be in a voice channel to check permissions.")
        
        channel = ctx.author.voice.channel
        bot_member = ctx.guild.get_member(ctx.bot.user.id)
        if not bot_member:
            return await ctx.send("❌ Could not find bot member in this guild.")
        
        perms = channel.permissions_for(bot_member)
        
        # Check essential permissions
        connect = "✅" if perms.connect else "❌"
        speak = "✅" if perms.speak else "❌"
        view_channel = "✅" if perms.view_channel else "❌"
        
        # Check optional permissions
        move_members = "✅" if perms.move_members else "❌"
        manage_channels = "✅" if perms.manage_channels else "❌"
        
        # Check channel limits
        channel_info = ""
        if channel.user_limit > 0:
            current_count = len(channel.members)
            if current_count >= channel.user_limit and not perms.move_members:
                channel_info = f"\n⚠️ **Channel is full** ({current_count}/{channel.user_limit}) and bot lacks Move Members permission"
            else:
                channel_info = f"\n🔢 **Channel usage:** {current_count}/{channel.user_limit}"
        
        embed = discord.Embed(
            title=f"🎵 Music Permissions in {channel.name}",
            color=0x00FF00 if perms.connect and perms.speak else 0xFF0000
        )
        
        embed.add_field(
            name="Essential Permissions",
            value=f"{view_channel} View Channel\n{connect} Connect\n{speak} Speak",
            inline=True
        )
        
        embed.add_field(
            name="Optional Permissions", 
            value=f"{move_members} Move Members\n{manage_channels} Manage Channels",
            inline=True
        )
        
        if channel_info:
            embed.description = channel_info
            
        # Check if music system is ready
        lavalink_status = "❌ Not Connected"
        if self.use_lavalink:
            try:
                # Ensure the pool is initialized first
                pool_ok = await self._ensure_lavalink_pool()
                if pool_ok and self._lavalink_pool:
                    nodes = getattr(self._lavalink_pool, 'nodes', [])
                    if nodes:
                        # Check if any nodes are actually connected
                        connected_nodes = []
                        for node_id in nodes:
                            try:
                                node = self._lavalink_pool.get_node(node_id)
                                if node and hasattr(node, 'status'):
                                    status = str(getattr(node, 'status', 'UNKNOWN'))
                                    if 'CONNECTED' in status.upper():
                                        connected_nodes.append(node_id)
                            except:
                                continue
                        
                        if connected_nodes:
                            lavalink_status = f"✅ Connected ({len(connected_nodes)} nodes)"
                        else:
                            lavalink_status = f"⚠️ {len(nodes)} nodes, checking connection..."
                    else:
                        lavalink_status = "⚠️ Pool initialized but no nodes"
                else:
                    lavalink_status = "❌ Failed to initialize pool"
            except Exception as e:
                lavalink_status = f"⚠️ Error: {str(e)[:30]}"
        else:
            lavalink_status = "⚠️ Lavalink disabled (using yt-dlp)"
        
        embed.add_field(name="Lavalink Status", value=lavalink_status, inline=False)
        
        await ctx.send(embed=embed)

    @commands.command(name="musictest", help="Test if music commands are working")
    async def music_test(self, ctx: Context):
        """Simple test command to verify music cog is loaded"""
        bot_info = f"Bot: {ctx.bot.user.name}#{ctx.bot.user.discriminator}"
        
        # Test Lavalink connection
        lavalink_status = "❌ Not Connected"
        if self.use_lavalink:
            try:
                if self._lavalink_pool:
                    lavalink_status = "✅ Pool Connected"
                else:
                    lavalink_status = "⚠️ Pool Not Initialized"
            except:
                lavalink_status = "❌ Connection Error"
        else:
            lavalink_status = "⚠️ Lavalink Disabled"
            
        await ctx.send(f"✅ Music cog is loaded and working!\n{bot_info}\n🎵 Lavalink: {lavalink_status}\nTry `musicperms` to check voice permissions.")

    @commands.command(name="checklavalinkserver", aliases=["checkserver", "servercheck"], help="Check if Lavalink server is running")
    async def check_lavalink_server(self, ctx: Context):
        """Check if Lavalink server is actually running and responding"""
        lavalink_uri = _os.environ.get('LAVALINK_URI', 'http://127.0.0.1:2333')
        
        try:
            # Test HTTP connection to Lavalink
            import requests
            response = requests.get(f"{lavalink_uri}/version", timeout=5)
            
            if response.status_code == 200:
                version_info = response.json()
                await ctx.send(f"✅ Lavalink server is running!\n📦 Version: {version_info.get('semver', 'Unknown')}\n🌐 URI: {lavalink_uri}")
            else:
                await ctx.send(f"⚠️ Lavalink server responded but with status {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            await ctx.send(f"❌ Cannot connect to Lavalink server at {lavalink_uri}\n💡 Try `f.lavfix` to restart it")
        except Exception as e:
            await ctx.send(f"❌ Error checking Lavalink: {e}")

    @commands.hybrid_command(name="musicstatus", usage="musicstatus", help="Check music system and Lavalink status.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def music_status(self, ctx: Context):
        """Check the status of the music system and Lavalink connection"""
        embed = discord.Embed(title="🎵 Music System Status", color=0x00E6A7)
        
        # Basic info
        embed.add_field(name="Lavalink Mode", value="✅ Enabled" if self.use_lavalink else "❌ Disabled", inline=True)
        
        # Voice client status
        vc = ctx.guild.voice_client or self.voice_clients.get(ctx.guild.id) if ctx.guild else None
        voice_status = "✅ Connected" if vc and vc.is_connected() else "❌ Not connected"
        embed.add_field(name="Voice Connection", value=voice_status, inline=True)
        
        # Lavalink pool status
        if self.use_lavalink:
            pool_status = "✅ Available" if self._lavalink_pool else "❌ Not initialized"
            embed.add_field(name="Lavalink Pool", value=pool_status, inline=True)
            
            # Node status
            if self._lavalink_pool:
                nodes = getattr(self._lavalink_pool, 'nodes', [])
                node_count = len(nodes)
                embed.add_field(name="Lavalink Nodes", value=f"{node_count} connected", inline=True)
                
                # Player status
                player = None
                for node in nodes:
                    try:
                        player = node.get_player(ctx.guild.id)
                        if player:
                            break
                    except:
                        continue
                
                player_status = "✅ Available" if player else "❌ No player"
                embed.add_field(name="Lavalink Player", value=player_status, inline=True)
            else:
                embed.add_field(name="Lavalink Nodes", value="N/A", inline=True)
                embed.add_field(name="Lavalink Player", value="N/A", inline=True)
        
        # Queue status
        queue = self.get_queue(ctx.guild.id) if ctx.guild else None
        queue_size = len(queue) if queue else 0
        embed.add_field(name="Queue Size", value=f"{queue_size} tracks", inline=True)
        
        # Current track
        current_track = self.current_tracks.get(ctx.guild.id) if ctx.guild else None
        current_status = current_track.title if current_track else "Nothing playing"
        embed.add_field(name="Current Track", value=current_status, inline=False)
        
        # Last error
        if self._last_voice_error:
            embed.add_field(name="Last Voice Error", value=f"```{self._last_voice_error[:100]}```", inline=False)
        
        await ctx.send(embed=embed)

    def help_custom(self):
        return "🎵", "Enhanced Music System", "Advanced music player with Lavalink, Spotify & multi-platform support"

async def setup(client):
    cog = Music(client)
    await client.add_cog(cog)

    # If Lavalink mode is enabled, initialize wavelink Pool on bot start
    if cog.use_lavalink:
        import time
        import traceback
        if not WAVELINK_AVAILABLE:
            print('❌ Wavelink not available - Lavalink integration disabled')
            return
            
        try:
            from wavelink.node import Pool

            print('ℹ️ Initializing Lavalink pool (eager connect)...')
            pool = Pool()
            cog._lavalink_pool = pool

            lavalink_uri = _os.environ.get('LAVALINK_URI', 'http://127.0.0.1:2333')
            lavalink_pass = _os.environ.get('LAVALINK_PASS', 'youshallnotpass')
            
            # Use the URI directly for local hosting
            node_uri = lavalink_uri
                
            print(f"[DEBUG] Creating Node with uri={node_uri}")
            node = wavelink.Node(uri=node_uri, password=lavalink_pass)

            # Try connecting with retries to make startup robust and fail loudly if node unavailable
            retries = int(_os.environ.get('LAVALINK_CONNECT_RETRIES', '3'))
            delay = float(_os.environ.get('LAVALINK_CONNECT_RETRY_DELAY', '1.0'))
            last_exc = None
            for attempt in range(1, retries + 1):
                try:
                    mapping = await pool.connect(nodes=[node], client=client)
                    print(f'✅ Lavalink pool connected, nodes: {list(mapping.keys())} (attempt {attempt})')
                    last_exc = None
                    break
                except Exception as e:
                    last_exc = e
                    print(f"[WARN] Lavalink connect attempt {attempt} failed: {e}")
                    if attempt < retries:
                        await asyncio.sleep(delay)

            if last_exc:
                tb = traceback.format_exc()
                print(f'⚠️ Failed to initialize Lavalink pool after {retries} attempts: {last_exc}\n{tb}')
                # Raise to make startup fail loudly so operator can fix node
                raise RuntimeError(f'Lavalink pool init failed: {last_exc}')

        except Exception as e:
            # Re-raise to bubble up to main startup handler which will report the error
            raise

    # Optionally start local static file server to expose downloads for Lavalink
    if _os.environ.get('USE_LAVALINK_FILES'):
        try:
            import subprocess
            python = _os.environ.get('PYTHON', 'python')
            # Start lavalink_file_server.py in background (use absolute path)
            server_path = _os.path.abspath(_os.path.join(_os.path.dirname(__file__), '..', '..', 'lavalink_file_server.py'))
            subprocess.Popen([python, server_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print('ℹ️ Started lavalink file server (background process)')
        except Exception as e:
            print(f'⚠️ Failed to start lavalink file server: {e}')

    @commands.hybrid_command(name="lavastatus", usage="lavastatus", help="Check Lavalink server status and health.")
    @blacklist_check()
    @ignore_check()
    async def lavalink_status(self, ctx: Context):
        """Check the status of the Lavalink server"""
        
        if not self.use_lavalink:
            await ctx.send(embed=discord.Embed(
                description="❌ Lavalink is not enabled on this bot.",
                color=0xFF0000
            ))
            return
            
        embed = discord.Embed(
            title="🎵 Lavalink Server Status",
            color=0x00FF00
        )
        
        # Check if pool exists
        if not self._lavalink_pool:
            embed.color = 0xFF0000
            embed.add_field(
                name="❌ Connection Status", 
                value="Lavalink pool not initialized", 
                inline=False
            )
            await ctx.send(embed=embed)
            return
            
        # Get node information
        try:
            if hasattr(self._lavalink_pool, 'nodes'):
                nodes = getattr(self._lavalink_pool, 'nodes')
                if hasattr(nodes, 'values'):
                    node_list = list(nodes.values())
                elif hasattr(nodes, '__iter__'):
                    node_list = list(nodes)
                else:
                    node_list = []
            else:
                node_list = []
                
            if not node_list:
                embed.color = 0xFF0000
                embed.add_field(
                    name="❌ Node Status", 
                    value="No Lavalink nodes found", 
                    inline=False
                )
            else:
                for i, node in enumerate(node_list):
                    status = getattr(node, 'status', 'Unknown')
                    uri = getattr(node, 'uri', 'Unknown')
                    player_count = getattr(node, 'player_count', 0) if hasattr(node, 'player_count') else len(getattr(node, 'players', {}))
                    
                    status_emoji = "✅" if str(status) == "NodeStatus.CONNECTED" else "❌"
                    embed.add_field(
                        name=f"{status_emoji} Node {i+1}",
                        value=f"**URI:** {uri}\n**Status:** {status}\n**Players:** {player_count}",
                        inline=True
                    )
                    
        except Exception as e:
            embed.add_field(
                name="⚠️ Node Information", 
                value=f"Could not retrieve node details: {e}", 
                inline=False
            )
            
        # Add GLIBC warning if applicable
        embed.add_field(
            name="🔧 Known Issues",
            value="If you see GLIBC_2.38 errors, the Lavalink server needs updating.\nThis requires server administrator action.",
            inline=False
        )
        
        # Environment info
        lavalink_uri = _os.environ.get('LAVALINK_URI', 'Not set')
        embed.add_field(
            name="🌐 Configuration",
            value=f"**URI:** {lavalink_uri}\n**Auto-start:** {_os.environ.get('LAVALINK_AUTOSTART', 'Not set')}",
            inline=False
        )
        
        await ctx.send(embed=embed)