from utils.error_helpers import StandardErrorHandler
# autonick.py
import discord
from discord.ext import commands
import aiosqlite


class AutoNick(commands.Cog):
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, client):
        self.client = client
        self.db_path = "db/autonick.db"
        # Removed loop access from __init__

    async def setup_hook(self):
        """Called when the cog is loaded"""
        await self.setup_database()

    async def setup_database(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS autonick (
                    guild_id INTEGER,
                    category TEXT, -- "bots" or "humans"
                    nickname TEXT,
                    PRIMARY KEY (guild_id, category)
                )
            """)
            await db.commit()

    @commands.group(name="autonick", help="Set auto-nickname for bots or humans.")
    @commands.has_permissions(manage_nicknames=True)
    async def autonick(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    # ======== BOT COMMANDS ========
    @autonick.group(name="bots", help="Manage auto-nickname for bots.")
    async def autonick_bots(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @autonick_bots.command(name="set")
    async def bots_set(self, ctx, *, nickname: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO autonick (guild_id, category, nickname)
                VALUES (?, ?, ?)
                ON CONFLICT(guild_id, category)
                DO UPDATE SET nickname = excluded.nickname
                """,
                (ctx.guild.id, "bots", nickname)
            )
            await db.commit()
        await ctx.reply(embed=discord.Embed(
            title="<:feast_tick:1400143469892210753> Bot Auto-Nickname Set",
            description=f"Bot nickname set to `{nickname}`.",
            color=0x00b9ff
        ))

    @autonick_bots.command(name="remove")
    async def bots_remove(self, ctx):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM autonick WHERE guild_id = ? AND category = ?",
                (ctx.guild.id, "bots")
            )
            await db.commit()
        await ctx.reply(embed=discord.Embed(
            title="<:feast_tick:1400143469892210753> Bot Auto-Nickname Removed",
            description="Bot nickname setting has been removed.",
            color=0xff5555
        ))

    # ======== HUMAN COMMANDS ========
    @autonick.group(name="humans", help="Manage auto-nickname for humans.")
    async def autonick_humans(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @autonick_humans.command(name="set")
    async def humans_set(self, ctx, *, nickname: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO autonick (guild_id, category, nickname)
                VALUES (?, ?, ?)
                ON CONFLICT(guild_id, category)
                DO UPDATE SET nickname = excluded.nickname
                """,
                (ctx.guild.id, "humans", nickname)
            )
            await db.commit()
        await ctx.reply(embed=discord.Embed(
            title="<:feast_tick:1400143469892210753> Human Auto-Nickname Set",
            description=f"Human nickname set to `{nickname}`.",
            color=0x00b9ff
        ))

    @autonick_humans.command(name="remove")
    async def humans_remove(self, ctx):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM autonick WHERE guild_id = ? AND category = ?",
                (ctx.guild.id, "humans")
            )
            await db.commit()
        await ctx.reply(embed=discord.Embed(
            title="<:feast_tick:1400143469892210753> Human Auto-Nickname Removed",
            description="Human nickname setting has been removed.",
            color=0xff5555
        ))

    # ======== EVENT LISTENER ========
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        category = "bots" if member.bot else "humans"

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT nickname FROM autonick WHERE guild_id = ? AND category = ?",
                (member.guild.id, category)
            ) as cursor:
                row = await cursor.fetchone()

        if row:
            try:
                await member.edit(nick=row[0], reason="AutoNick System")
            except discord.Forbidden:
                pass


async def setup(bot):
    await bot.add_cog(AutoNick(bot))
