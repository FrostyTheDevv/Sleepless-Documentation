import discord
from discord.ext import commands
from typing import Union
import wavelink
import aiosqlite
from utils.Tools import *

class FilterCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Removed in-memory active_filters: self.active_filters = {}

    async def save_active_filter(self, guild_id: int, filter_name: str):
        """Save the active filter for a guild to the database"""
        async with aiosqlite.connect('db/filters.db') as db:
            await db.execute('''
                INSERT OR REPLACE INTO active_filters (guild_id, filter_name)
                VALUES (?, ?)
            ''', (guild_id, filter_name))
            await db.commit()

    async def get_active_filter(self, guild_id: int):
        """Get the active filter for a guild from the database"""
        async with aiosqlite.connect('db/filters.db') as db:
            cursor = await db.execute('''
                SELECT filter_name FROM active_filters WHERE guild_id = ?
            ''', (guild_id,))
            
            row = await cursor.fetchone()
            return row[0] if row else None

    async def remove_active_filter(self, guild_id: int):
        """Remove the active filter for a guild from the database"""
        async with aiosqlite.connect('db/filters.db') as db:
            await db.execute('''
                DELETE FROM active_filters WHERE guild_id = ?
            ''', (guild_id,))
            await db.commit()

    async def setup_database(self):
        """Create the filters database and tables"""
        async with aiosqlite.connect('db/filters.db') as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS active_filters (
                    guild_id INTEGER PRIMARY KEY,
                    filter_name TEXT NOT NULL
                )
            ''')
            await db.commit()

    @commands.Cog.listener()
    async def on_ready(self):
        await self.setup_database()

    async def apply_filter(self, ctx: commands.Context, filter_name: str):
        player = getattr(ctx, "voice_client", None)
        if not player or not getattr(player, "playing", False):
            await ctx.send("I'm not playing anything.")
            return

        author_voice = getattr(ctx.author, "voice", None)
        player_channel = getattr(player, "channel", None)
        if author_voice is None or getattr(author_voice, "channel", None) != player_channel:
            await ctx.send("You need to be in the same voice channel as me.")
            return

        filters = wavelink.Filters()

        if filter_name == "nightcore":
            filters.timescale.set(pitch=1.2, speed=1.2, rate=1)
        elif filter_name == "bassboost":
            filters.equalizer.set(bands=[{"band": 0, "gain": 0.5}, {"band": 1, "gain": 0.5}, {"band": 2, "gain": 0.5}])
        elif filter_name == "vaporwave":
            filters.timescale.set(rate=0.85, pitch=0.85)
        elif filter_name == "karaoke":
            filters.karaoke.set(level=1.0, mono_level=1.0, filter_band=220.0, filter_width=100.0)
        elif filter_name == "tremolo":
            filters.tremolo.set(depth=0.5, frequency=14.0)
        elif filter_name == "vibrato":
            filters.vibrato.set(depth=0.5, frequency=14.0)
        elif filter_name == "rotation":
            filters.rotation.set(rotation_hz=5.0)
        elif filter_name == "distortion":
            filters.distortion.set(
                sin_offset=0.0,
                sin_scale=1.0,
                cos_offset=0.0,
                cos_scale=1.0,
                tan_offset=0.0,
                tan_scale=1.0,
                offset=0.0,
                scale=1.0
            )
        elif filter_name == "channelmix":
            filters.channel_mix.set(left_to_left=0.5, left_to_right=0.5, right_to_left=0.5, right_to_right=0.5)

        await player.set_filters(filters)
        guild = getattr(ctx, "guild", None)
        if guild:
            await self.save_active_filter(guild.id, filter_name)
        await ctx.send(embed=discord.Embed(description=f"Filter set to **{filter_name}**.", color=discord.Color.green()))

    @commands.hybrid_group(invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def filter(self, ctx: commands.Context):
        await ctx.send("Use `filter enable` to enable a filter or `filter disable` to disable the current filter.")

    @filter.command(help="Enable a filter.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def enable(self, ctx: commands.Context):
        player = getattr(ctx, "voice_client", None)
        if not player or not getattr(player, "playing", False):
            await ctx.send("I'm not connected to a voice channel.")
            return

        author_voice = getattr(ctx.author, "voice", None)
        player_channel = getattr(player, "channel", None)
        if author_voice is None or getattr(author_voice, "channel", None) != player_channel:
            await ctx.send("You need to be in the same voice channel as me.")
            return

        # Import SelectOption from discord if not already
        from discord import SelectOption
        filter_options = [
            SelectOption(label="Vaporwave", description="Apply vaporwave effect"),
            SelectOption(label="Nightcore", description="Apply nightcore effect"),
            SelectOption(label="Vibrato", description="Apply vibrato effect"),
            SelectOption(label="Tremolo", description="Apply tremolo effect"),
            SelectOption(label="Bassboost", description="Apply bass boost effect"),
            SelectOption(label="Karaoke", description="Apply karaoke effect"),
            SelectOption(label="Rotation", description="Apply rotation effect"),
            SelectOption(label="Distortion", description="Apply distortion effect"),
            SelectOption(label="Channelmix", description="Apply channel mix effect"),
        ]

        class FilterSelect(discord.ui.View):
            def __init__(self, cog):
                super().__init__()
                self.cog = cog
                self.add_item(self.FilterDropdown(self))
                self.add_item(self.CancelButton())

            class FilterDropdown(discord.ui.Select):
                def __init__(self, parent):
                    super().__init__(placeholder="Choose a filter...", options=filter_options)
                    self.parent_view = parent

                async def callback(self, interaction: discord.Interaction):
                    await interaction.response.defer()
                    selected_filter = self.values[0].lower()
                    await self.parent_view.cog.apply_filter(ctx, selected_filter)
                    self.parent_view.disable_all()

            class CancelButton(discord.ui.Button):
                def __init__(self):
                    super().__init__(label="Cancel", style=discord.ButtonStyle.red)
                async def callback(self, interaction: discord.Interaction):
                    message = getattr(interaction, "message", None)
                    if message is not None and hasattr(message, "delete"):
                        await message.delete()
                    if self.view is not None and hasattr(self.view, "disable_all"):
                        self.view.disable_all()

            def disable_all(self):
                for child in self.children:
                    if isinstance(child, (discord.ui.Select, discord.ui.Button)):
                        child.disabled = True
                self.stop()

        view = FilterSelect(self)

        guild = getattr(ctx, "guild", None)
        current_filter = "None"
        if guild:
            active_filter = await self.get_active_filter(guild.id)
            current_filter = active_filter or "None"
        embed = discord.Embed(title="Enable Filter", description="Choose a filter to apply:", color=discord.Color.blue())
        embed.add_field(name="Current Filter", value=current_filter, inline=False)
        await ctx.send(embed=embed, view=view)

    @filter.command(help="Disable the current filter.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def disable(self, ctx: commands.Context):
        player = getattr(ctx, "voice_client", None)
        if not player or not getattr(player, "playing", False):
            await ctx.send("I'm not connected to a voice channel.")
            return

        author_voice = getattr(ctx.author, "voice", None)
        player_channel = getattr(player, "channel", None)
        if author_voice is None or getattr(author_voice, "channel", None) != player_channel:
            await ctx.send("You need to be in the same voice channel as me.")
            return

        filters = wavelink.Filters()
        await player.set_filters(filters)
        guild = getattr(ctx, "guild", None)
        if guild:
            await self.remove_active_filter(guild.id)
        await ctx.send(embed=discord.Embed(description="Filter disabled.", color=discord.Color.red()))

