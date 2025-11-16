import discord
from discord.ext import commands
import sqlite3
import os
import typing
from datetime import datetime, timezone

from utils.error_helpers import StandardErrorHandler
DB_PATH = "db/vctracker.db"
os.makedirs("db", exist_ok=True)


# ------------------ VC Leaderboard Paginator ------------------
class VCLBPaginator(discord.ui.View):
    def __init__(self, ctx, rows, per_page: int = 10, timeout: int = 120):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.rows = rows
        self.per_page = per_page
        self.current_page = 0
        self.max_pages = (len(rows) - 1) // per_page + 1 if rows else 1
        self.message = None  # Allow assignment later
        self.update_button_states()

    def format_time(self, seconds: int):
        mins, sec = divmod(seconds, 60)
        hrs, mins = divmod(mins, 60)
        return f"{hrs}h {mins}m {sec}s"

    def update_button_states(self):
        self.first_button.disabled = self.current_page == 0
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page >= self.max_pages - 1
        self.last_button.disabled = self.current_page >= self.max_pages - 1

    def format_embed(self):
        start = self.current_page * self.per_page
        chunk = self.rows[start:start + self.per_page]

        lines = []
        for idx, (user_id, total) in enumerate(chunk):
            overall_index = start + idx + 1
            member = self.ctx.guild.get_member(int(user_id))
            name = f"{member.name}#{member.discriminator}" if member else f"<@{user_id}>"
            time_str = self.format_time(total)
            lines.append(f"**#{overall_index} {name}** — {time_str}")

        description = "\n".join(lines) if lines else "<:feast_cross:1400143488695144609> No data."
        embed = discord.Embed(
            title=f"<:feast_trophy:1401572811159371808> VC Leaderboard",
            description=description,
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Page {self.current_page + 1}/{self.max_pages} • {len(self.rows)} users total")
        return embed

    @discord.ui.button(label="First", style=discord.ButtonStyle.secondary,
                       emoji=discord.PartialEmoji(name="feast_next", id=1400141978095583322))
    async def first_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.defer()
        self.current_page = 0
        self.update_button_states()
        await interaction.response.edit_message(embed=self.format_embed(), view=self)

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary,
                       emoji=discord.PartialEmoji(name="feast_piche", id=1400142845402284102))
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.defer()
        self.current_page = max(0, self.current_page - 1)
        self.update_button_states()
        await interaction.response.edit_message(embed=self.format_embed(), view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary,
                       emoji=discord.PartialEmoji(name="feast_age", id=1400142030205878274))
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.defer()
        self.current_page = min(self.max_pages - 1, self.current_page + 1)
        self.update_button_states()
        await interaction.response.edit_message(embed=self.format_embed(), view=self)

    @discord.ui.button(label="Last", style=discord.ButtonStyle.secondary,
                       emoji=discord.PartialEmoji(name="feast_prev", id=1400142835914637524))
    async def last_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.defer()
        self.current_page = self.max_pages - 1
        self.update_button_states()
        await interaction.response.edit_message(embed=self.format_embed(), view=self)


# ------------------ VC Tracker Cog ------------------
class VCTracker(commands.Cog):
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot
        self.vc_sessions = {}
        # Initialize database when cog loads
        self.bot.loop.create_task(self.init_db())

    async def init_db(self):
        """Initialize the database"""
        await self.bot.wait_until_ready()
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS vc_stats (
                    guild_id TEXT,
                    user_id TEXT,
                    time INTEGER DEFAULT 0,
                    PRIMARY KEY(guild_id, user_id)
                );
            """)
            conn.commit()

    def format_time(self, seconds: int):
        mins, sec = divmod(seconds, 60)
        hrs, mins = divmod(mins, 60)
        return f"{hrs}h {mins}m {sec}s"

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if before.channel is None and after.channel is not None:
            self.vc_sessions[member.id] = datetime.now(timezone.utc)
        elif before.channel is not None and after.channel is None:
            start_time = self.vc_sessions.pop(member.id, None)
            if start_time:
                seconds = int((datetime.now(timezone.utc) - start_time).total_seconds())
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute("""
                        INSERT OR IGNORE INTO vc_stats (guild_id, user_id, time)
                        VALUES (?, ?, 0)
                    """, (str(member.guild.id), str(member.id)))
                    conn.execute("""
                        UPDATE vc_stats SET time = time + ? WHERE guild_id = ? AND user_id = ?
                    """, (seconds, str(member.guild.id), str(member.id)))
                    conn.commit()

    @commands.group(name="vctime", invoke_without_command=True)
    async def vctime(self, ctx):
        embed = discord.Embed(
            title="🕒 VC Time Help",
            description="`vctime add <member> <seconds>`\n`vctime remove <member> <seconds>`\n`vctime reset <member>`",
            color=discord.Color.green()
        )
        await ctx.reply(embed=embed)

    @vctime.command(name="add")
    @commands.has_permissions(manage_guild=True)
    async def add(self, ctx, member: discord.Member, seconds: int):
        if seconds <= 0:
            return await ctx.reply(embed=discord.Embed(description="<:feast_cross:1400143488695144609> Seconds must be positive.", color=discord.Color.red()))
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                INSERT OR IGNORE INTO vc_stats (guild_id, user_id, time)
                VALUES (?, ?, 0)
            """, (str(ctx.guild.id), str(member.id)))
            conn.execute("""
                UPDATE vc_stats SET time = time + ? WHERE guild_id = ? AND user_id = ?
            """, (seconds, str(ctx.guild.id), str(member.id)))
            conn.commit()
        await ctx.reply(embed=discord.Embed(description=f"<:feast_tick:1400143469892210753> Added **{self.format_time(seconds)}** to {member.mention}.", color=discord.Color.green()))

    @vctime.command(name="remove")
    @commands.has_permissions(manage_guild=True)
    async def remove(self, ctx, member: discord.Member, seconds: int):
        if seconds <= 0:
            return await ctx.reply(embed=discord.Embed(description="<:feast_cross:1400143488695144609> Seconds must be positive.", color=discord.Color.red()))
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute("SELECT time FROM vc_stats WHERE guild_id = ? AND user_id = ?", (str(ctx.guild.id), str(member.id)))
            row = cursor.fetchone()
            if not row:
                return await ctx.reply(embed=discord.Embed(description=f"<:feast_cross:1400143488695144609> No VC time for {member.mention}.", color=discord.Color.red()))
            new_time = max(0, row[0] - seconds)
            conn.execute("""
                UPDATE vc_stats SET time = ? WHERE guild_id = ? AND user_id = ?
            """, (new_time, str(ctx.guild.id), str(member.id)))
            conn.commit()
        await ctx.reply(embed=discord.Embed(description=f"<:feast_tick:1400143469892210753> Removed **{self.format_time(seconds)}** from {member.mention}.", color=discord.Color.green()))

    @vctime.command(name="reset")
    @commands.has_permissions(administrator=True)
    async def reset(self, ctx, member: discord.Member):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM vc_stats WHERE guild_id = ? AND user_id = ?", (str(ctx.guild.id), str(member.id)))
            conn.commit()
        await ctx.reply(embed=discord.Embed(description=f"<:feast_tick:1400143469892210753> Reset VC time for {member.mention}.", color=discord.Color.green()))

    @commands.command(name="vclb", aliases=["vcleaderboard"])
    async def vclb(self, ctx):
        # Always read fresh data from vctracker.db
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute("""
                SELECT user_id, time FROM vc_stats
                WHERE guild_id = ?
                ORDER BY time DESC
            """, (str(ctx.guild.id),))
            rows = cursor.fetchall()

        paginator = VCLBPaginator(ctx, rows, per_page=10)
        embed = paginator.format_embed()
        message = await ctx.reply(embed=embed, view=paginator)
        paginator.message = message

    @commands.command(name="vctrack")
    async def vctracker(self, ctx, member: typing.Optional[discord.Member] = None):
        # Accept None for member, fallback to ctx.author
        member = member or ctx.author
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute("""
                SELECT time FROM vc_stats
                WHERE guild_id = ? AND user_id = ?
            """, (str(ctx.guild.id), str(member.id)))
            row = cursor.fetchone()
        total = row[0] if row else 0
        embed = discord.Embed(
            title=f"<:feast_itmt:1400137318991663317> VC Tracker",
            description=f"**User:** {member.mention}\n**Total VC Time:** {self.format_time(total)}",
            color=discord.Color.green()
        )
        await ctx.reply(embed=embed)


async def setup(bot):
    await bot.add_cog(VCTracker(bot))
