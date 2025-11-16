import discord
import psutil
import sys
import os
import time
import aiosqlite
import platform
import importlib.metadata
import datetime
from discord import Embed, ButtonStyle
from discord.ui import Button, View
from discord.ext import commands
from utils.Tools import *
import wavelink
from utils.error_helpers import StandardErrorHandler

class Stats(commands.Cog):
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot
        self.start_time = time.time()
        self.total_songs_played = 0
        # Removed loop access from __init__

    async def setup_hook(self):
        """Called when the cog is loaded"""
        await self.setup_database()

    async def setup_database(self):
        os.makedirs("db", exist_ok=True)
        async with aiosqlite.connect("db/stats.db") as db:
            await db.execute("CREATE TABLE IF NOT EXISTS stats (key TEXT PRIMARY KEY, value INTEGER)")
            await db.commit()
            async with db.execute("SELECT value FROM stats WHERE key = 'total_songs_played'") as cursor:
                row = await cursor.fetchone()
                self.total_songs_played = row[0] if row else 0
            if row is None:
                await db.execute("INSERT INTO stats (key, value) VALUES ('total_songs_played', 0)")
                await db.commit()

    async def update_total_songs_played(self):
        async with aiosqlite.connect("db/stats.db") as db:
            await db.execute("INSERT OR REPLACE INTO stats (key, value) VALUES ('total_songs_played', ?)", (self.total_songs_played,))
            await db.commit()

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload):
        self.total_songs_played += 1
        await self.update_total_songs_played()

    def count_code_stats(self, file_path):
        import os
        total_lines = 0
        total_words = 0
        if not os.path.isfile(file_path):
            return total_lines, total_words
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                for line in file:
                    stripped_line = line.strip()
                    if stripped_line and not stripped_line.startswith(('〇')):
                        total_lines += 1
                        total_words += len(stripped_line.split())
        except (UnicodeDecodeError, IOError):
            pass
        return total_lines, total_words

    def gather_file_stats(self, directory):
        total_files = 0
        total_lines = 0
        total_words = 0
        for root, _, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                if file.endswith('.py') and '.local' not in root:
                    total_files += 1
                    file_lines, file_words = self.count_code_stats(file_path)
                    total_lines += file_lines
                    total_words += file_words
        return total_files, total_lines, total_words

    @commands.hybrid_command(name="botinfo", aliases=["botstats", "bi", "statistics", "stats"], help="Shows the bot's information.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 7, commands.BucketType.user)
    async def botinfo(self, ctx):
        """Show bot information and statistics"""
        processing_message = await ctx.send("🔄 Loading Sleepless information...")
        
        guild_count = len(self.bot.guilds)
        user_count = sum(g.member_count for g in self.bot.guilds if g.member_count is not None)
        bot_count = sum(sum(1 for m in g.members if m.bot) for g in self.bot.guilds)
        human_count = user_count - bot_count
        channel_count = len(set(self.bot.get_all_channels()))
        text_channel_count = len([c for c in self.bot.get_all_channels() if isinstance(c, discord.TextChannel)])
        voice_channel_count = len([c for c in self.bot.get_all_channels() if isinstance(c, discord.VoiceChannel)])
        category_channel_count = len([c for c in self.bot.get_all_channels() if isinstance(c, discord.CategoryChannel)])
        slash_commands = len([cmd for cmd in self.bot.tree.get_commands()])
        commands_count = len(set(self.bot.walk_commands()))
        uptime_seconds = int(round(time.time() - self.start_time))
        uptime_timedelta = datetime.timedelta(seconds=uptime_seconds)
        uptime = f"{uptime_timedelta.days} days, {uptime_timedelta.seconds // 3600} hours, {(uptime_timedelta.seconds // 60) % 60} minutes, {uptime_timedelta.seconds % 60} seconds"
        total_files, total_lines, total_words = self.gather_file_stats('.')
        cpu_info = psutil.cpu_freq()
        memory_info = psutil.virtual_memory()
        total_libraries = len(list(importlib.metadata.distributions()))
        channels_connected = sum(1 for vc in self.bot.voice_clients if vc)
        playing_tracks = sum(1 for vc in self.bot.voice_clients if vc.playing)

        # Main embed (second/detailed version)
        embed = Embed(title="Sleepless Statistics: General", color=0x006fb9)
        embed.add_field(name="📺 Channels", value=f"Total: **{channel_count}**\nText: **{text_channel_count}**   |   Voice: **{voice_channel_count}**   |   Category: **{category_channel_count}**", inline=False)
        embed.add_field(name="⏰ Uptime", value=f"{uptime}", inline=False)
        embed.add_field(name="👥 User Count", value=f"Humans: **{human_count}**   |   Bots: **{bot_count}**", inline=False)
        embed.add_field(name="⚙️ Commands", value=f"Total: **{commands_count}**   |   Slash: **{slash_commands}**", inline=False)
        embed.add_field(name="📚 Libraries Used", value=f"Discord Library: **[discord.py](https://discordpy.readthedocs.io/en/stable/)**\nTotal Libraries: **{total_libraries}**", inline=False)
        embed.add_field(name="💻 Codebase Stats", value=f"Total Python Files: **{total_files}**\nTotal Lines: **{total_lines}**\nTotal Words: **{total_words}**", inline=False)
        embed.add_field(name="🎵 Music Stats", value=f"Currently Connected: **{channels_connected}**\nCurrently Playing: **{playing_tracks}**\nTotal Songs Played: **{self.total_songs_played}**", inline=False)
        embed.set_footer(text="Powered by Sleepless  Development™", icon_url=self.bot.user.display_avatar.url)

        view = View()

        general_button = Button(label="General", style=ButtonStyle.red)
        async def general_button_callback(interaction):
            if interaction.user == ctx.author:
                await interaction.response.edit_message(embed=embed, view=view)
        general_button.callback = general_button_callback
        view.add_item(general_button)

        system_button = Button(label="System", style=ButtonStyle.red)
        async def system_button_callback(interaction):
            if interaction.user == ctx.author:
                system_embed = Embed(title="Sleepless Statistics: System", color=0x006fb9)
                system_embed.add_field(name="💻 System Info", value=f"• Discord.py: **{discord.__version__}**\n• Python: **{platform.python_version()}**\n• Architecture: **{platform.machine()}**\n• Platform: **{platform.system()}**", inline=False)
                system_embed.add_field(name="🧠 Memory Info", value=f"• Total Memory: **{memory_info.total / (1024 ** 2):,.2f} MB**\n• Memory Left: **{memory_info.available / (1024 ** 2):,.2f} MB**\n• Heap Total: **{memory_info.used / (1024 ** 2):,.2f} MB**", inline=False)
                system_embed.add_field(name="⚙️ CPU Info", value=f"• CPU: **{psutil.cpu_freq().max}' GHz**\n• CPU Usage: **{psutil.cpu_percent()}%**\n• CPU Cores: **{psutil.cpu_count(logical=False)}**\n• CPU Speed: **{cpu_info.current:.2f} MHz**", inline=False)
                system_embed.set_footer(text="Powered by Sleepless  Development™", icon_url=self.bot.user.display_avatar.url)
                await interaction.response.edit_message(embed=system_embed, view=view)
        system_button.callback = system_button_callback
        view.add_item(system_button)

        team_button = Button(label="Team", style=ButtonStyle.green)
        async def team_button_callback(interaction):
            if interaction.user == ctx.author:
                s_id = ctx.guild.shard_id
                sh = self.bot.get_shard(s_id)
                db_latency = None
                try:
                    async with aiosqlite.connect("db/afk.db") as db:
                        start_time = time.perf_counter()
                        await db.execute("SELECT 1")
                        end_time = time.perf_counter()
                        db_latency = (end_time - start_time) * 1000
                        db_latency = round(db_latency, 2)
                except Exception:
                    db_latency = "N/A"
                wsping = round(self.bot.latency * 1000, 2)
            embed = Embed(title="Sleepless Team", color=0x006fb9)
            embed.add_field(name="👑 **OWNER**",
                            value="[**FrostyTheDevv**](https://discord.com/channels/@me/YOUR_USER_ID)", inline=False)
            embed.add_field(name="⚙️ **MANAGERS**",
                            value="**Hiring!** DM [FrostyTheDevv](https://discord.com/channels/@me/YOUR_USER_ID) to apply for management position.", inline=False)
            embed.add_field(name="💼 **SUPPORT STAFF**",
                            value="**Looking for dedicated support staff!** Contact owner for opportunities.", inline=False)
            embed.set_footer(text="Powered by Sleepless Development™", icon_url=self.bot.user.display_avatar.url)
            await interaction.response.edit_message(embed=embed, view=view)
        team_button.callback = team_button_callback
        view.add_item(team_button)
        
        partner_button = Button(label="Partners", style=ButtonStyle.green)
        async def partner_button_callback(interaction):
            if interaction.user == ctx.author:
                s_id = ctx.guild.shard_id
                sh = self.bot.get_shard(s_id)
                db_latency = None
                try:
                    async with aiosqlite.connect("db/afk.db") as db:
                        start_time = time.perf_counter()
                        await db.execute("SELECT 1")
                        end_time = time.perf_counter()
                        db_latency = (end_time - start_time) * 1000
                        db_latency = round(db_latency, 2)
                except Exception:
                    db_latency = "N/A"
                wsping = round(self.bot.latency * 1000, 2)
                partner_embed = Embed(title="Sleepless Partners", color=0x006fb9)
                partner_embed.add_field(name="🤝 **CURRENT PARTNERS**", value="**No current partners**", inline=False)
                partner_embed.add_field(name="📧 **PARTNERSHIP INQUIRIES**", value="Interested in partnering? DM [FrostyTheDevv](https://discord.com/channels/@me/YOUR_USER_ID) to discuss partnership opportunities!", inline=False)
                partner_embed.add_field(name="📋 **PARTNERSHIP REQUIREMENTS**", value="• Active Discord server (500+ members)\n• Similar bot/service focus\n• Professional management\n• Mutual benefit opportunities", inline=False)
                partner_embed.set_footer(text="Powered by Sleepless  Development™", icon_url=self.bot.user.display_avatar.url)
                await interaction.response.edit_message(embed=partner_embed, view=view)
        partner_button.callback = partner_button_callback
        view.add_item(partner_button)

        delete_button = Button(emoji="❌", style=ButtonStyle.red)
        async def delete_button_callback(interaction):
            if interaction.user == ctx.author:
                await interaction.message.delete()
        delete_button.callback = delete_button_callback
        view.add_item(delete_button)

        total_users = human_count + bot_count
        server_count_button = Button(label=f"Servers: {guild_count}    |    Users: {total_users:,}", style=ButtonStyle.success, disabled=True)
        view.add_item(server_count_button)

        await processing_message.edit(content=None, embed=embed, view=view)


class BotInfoView(discord.ui.View):
    def __init__(self, ctx, cog):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.cog = cog

    @discord.ui.button(label="🔄 Refresh", style=discord.ButtonStyle.secondary)
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ Only the command user can use this!", ephemeral=True)
            return
        
        await interaction.response.defer()
        await self.cog.botinfo(self.ctx)

    async def on_timeout(self):
        # Disable all buttons when the view times out
        for item in self.children:
            try:
                if isinstance(item, discord.ui.Button):
                    item.disabled = True
            except:
                pass


async def setup(bot):
    await bot.add_cog(Stats(bot))