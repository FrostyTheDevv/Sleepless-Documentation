# cogs/commands/np.py
from discord.ext import commands, tasks
from discord import SelectOption, ButtonStyle
import discord
import aiosqlite
from typing import Optional, Set
from datetime import datetime, timedelta, timezone
from discord.ui import View, Button, Select
from utils.config import OWNER_IDS
from utils import Paginator, DescriptionEmbedPaginator
from utils.timezone_helpers import get_timezone_helpers

# ─────────────────────────────────────────────────────────────────────────────
# Config / constants
# ─────────────────────────────────────────────────────────────────────────────
LOG_CHANNEL_ID = 1414349197146062858  # where we post shard + lifecycle messages

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def load_owner_ids():
    return OWNER_IDS

async def is_staff(user: discord.abc.User, staff_ids: Set[int]):
    return user.id in staff_ids

async def is_owner_or_staff(ctx: commands.Context):
    cog = getattr(ctx, "cog", None)
    staff_ids = getattr(cog, "staff", set())
    return (await is_staff(ctx.author, staff_ids)) or (ctx.author.id in OWNER_IDS)

# ─────────────────────────────────────────────────────────────────────────────
# Select UI (uses shared DB connection, not file paths)
# ─────────────────────────────────────────────────────────────────────────────

class TimeSelect(Select):
    def __init__(self, user: discord.User, db: aiosqlite.Connection, author: discord.abc.User):
        super().__init__(placeholder="Select the duration")
        self.user = user
        self.db: aiosqlite.Connection = db
        self.author = author

        self.options = [
            SelectOption(label="10 Minutes", description="Trial for 10 minutes", value="10m"),
            SelectOption(label="1 Week",     description="No prefix for 1 week",   value="1w"),
            SelectOption(label="2 Weeks",    description="No prefix for 2 weeks",  value="2w"),
            SelectOption(label="3 Weeks",    description="No prefix for 3 weeks",  value="3w"),
            SelectOption(label="1 Month",    description="No prefix for 1 month",  value="1m"),
            SelectOption(label="3 Months",   description="No prefix for 3 months", value="3m"),
            SelectOption(label="6 Months",   description="No prefix for 6 months", value="6m"),
            SelectOption(label="1 Year",     description="No prefix for 1 year",   value="1y"),
            SelectOption(label="3 Years",    description="No prefix for 3 years",  value="3y"),
            SelectOption(label="Lifetime",   description="No prefix permanently",  value="lifetime"),
        ]

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message("You can't select this option.", ephemeral=True)

        duration_mapping = {
            "10m": timedelta(minutes=10),
            "1w": timedelta(weeks=1),
            "2w": timedelta(weeks=2),
            "3w": timedelta(weeks=3),
            "1m": timedelta(days=30),
            "3m": timedelta(days=90),
            "6m": timedelta(days=180),
            "1y": timedelta(days=365),
            "3y": timedelta(days=365 * 3),
            "lifetime": None
        }

        selected = self.values[0]

        if selected == "lifetime":
            expiry_time = None
            expiry_str: Optional[str] = None
            expiry_display = "**Lifetime**"
            expiry_timestamp = "None (Permanent)"
        else:
            expiry_time = datetime.now(timezone.utc) + duration_mapping[selected]
            expiry_str = expiry_time.isoformat()
            # Use Discord timestamp format which automatically shows in user's timezone
            expiry_timestamp = f"<t:{int(expiry_time.timestamp())}:f>"
            expiry_display = expiry_timestamp

        # Upsert behavior - fixed to match database schema
        await self.db.execute(
            """
            INSERT INTO np (user_id, track_name, provider, expiry_time)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET expiry_time=excluded.expiry_time
            """,
            (str(self.user.id), "No Prefix Purchase", "Manual", int(expiry_time.timestamp()) if expiry_time else None)
        )
        await self.db.commit()

        # Add role in your main guild
        guild = interaction.client.get_guild(1369497441061179398208 // 10000000000 * 10000000000)  # placeholder to keep line length safe
        guild = interaction.client.get_guild(1369497441061179393)
        if guild:
            member = guild.get_member(self.user.id)
            if member:
                role = guild.get_role(1369504776219398208)
                if role:
                    try:
                        await member.add_roles(role, reason="No prefix added")
                    except discord.HTTPException:
                        pass

        # Log channel
        log_channel = interaction.client.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            embed = discord.Embed(
                title="User Added to No Prefix",
                description=(
                    f"**User**: [{self.user}](https://discord.com/users/{self.user.id})\n"
                    f"**User Mention**: {self.user.mention}\n"
                    f"**ID**: {self.user.id}\n\n"
                    f"**Added By**: [{self.author.display_name}](https://discord.com/users/{self.author.id})\n"
                    f"<a:timer:1329404677820911697> **Expiry Time**: {expiry_display}\n"
                    f"**Timestamp**: {expiry_timestamp}\n\n"
                    f"<a:premium:1204110058124873889> **Tier**: **{selected.upper()}**"
                ),
                color=0x006fb9
            )
            thumb = self.user.avatar.url if self.user.avatar else self.user.default_avatar.url
            embed.set_thumbnail(url=thumb)
            try:
                if isinstance(log_channel, discord.abc.Messageable):
                    await log_channel.send(f"<#{LOG_CHANNEL_ID}>", embed=embed)
            except discord.HTTPException:
                pass

        embed = discord.Embed(
            description=(
                f"**Added Global No Prefix**:\n"
                f"**User**: **[{self.user}](https://discord.com/users/{self.user.id})**\n"
                f"**User Mention**: {self.user.mention}\n"
                f"**User ID**: {self.user.id}\n\n"
                f"__**Additional Info**__:\n"
                f"**Added By**: **[{self.author.display_name}](https://discord.com/users/{self.author.id})**\n"
                f"<a:timer:1329404677820911697> **Expiry Time:** {expiry_display}\n"
                f"**Timestamp:** {expiry_timestamp}"
            ),
            color=0x006fb9
        )
        embed.set_author(
            name="Added No Prefix",
            icon_url="https://cdn.discordapp.com/icons/1166303696263585852/eeb00b2cf541438e88cdf842394c5b30.png?size=1024"
        )
        embed.set_footer(text="DM will be sent to the user when No Prefix expires.")
        await interaction.response.edit_message(embed=embed, view=None)

class TimeSelectView(View):
    def __init__(self, user: discord.User, db: aiosqlite.Connection, author: discord.abc.User):
        super().__init__()
        self.add_item(TimeSelect(user, db, author))

# ─────────────────────────────────────────────────────────────────────────────
# Cog
# ─────────────────────────────────────────────────────────────────────────────

class NoPrefix(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client
        self.tz_helpers = get_timezone_helpers(client)
        self.staff: Set[int] = set()
        self.db: Optional[aiosqlite.Connection] = None
        self._announced_ready = False  # to avoid duplicate on_ready posts

    # Small helper to post lifecycle/status embeds
    async def _status_embed(self, title: str, description: str, color: int = 0x006fb9):
        channel = self.client.get_channel(LOG_CHANNEL_ID)
        from discord import TextChannel, Thread
        if not isinstance(channel, (TextChannel, Thread)):
            return
        embed = discord.Embed(title=title, description=description, color=color)
        embed.timestamp = discord.utils.utcnow()
        try:
            await channel.send(f"<#{LOG_CHANNEL_ID}>", embed=embed)
        except discord.HTTPException:
            pass

    # IMPORTANT: discord.py calls cog_load for cogs, not setup_hook
    async def cog_load(self):
        # Grab the already-open connection registered in your runner
        try:
            self.db = self.client.dbs["np"]  # type: ignore[attr-defined]
            assert isinstance(self.db, aiosqlite.Connection)
        except Exception:
            raise RuntimeError("NoPrefix: expected self.client.dbs['np'] to be an aiosqlite.Connection")

        # Ensure schema exists (idempotent)
        await self.db.execute("""
        CREATE TABLE IF NOT EXISTS np (
            id INTEGER PRIMARY KEY,
            user_id TEXT,
            expiry_time TEXT NULL
        );
        """)
        await self.db.execute("CREATE INDEX IF NOT EXISTS idx_np_expiry ON np(expiry_time);")

        await self.db.execute("""
        CREATE TABLE IF NOT EXISTS autonp (
            guild_id INTEGER PRIMARY KEY
        );
        """)

        await self.db.execute("""
        CREATE TABLE IF NOT EXISTS staff (
            id INTEGER PRIMARY KEY
        );
        """)
        await self.db.commit()

        # Load staff and start the task only after DB is ready
        # Don't wait for ready during cog_load as it causes deadlock
        self.expiry_check.start()

        # Announce successful cog load
        print("[NP] Cog loaded successfully: schema ensured, task started.")
        await self._status_embed(
            "Cog Loaded",
            "✅ **np** cog loaded successfully. Schema ensured and expiry task started."
        )

    async def cog_unload(self):
        self.expiry_check.cancel()
        print("[NP] Cog unloaded.")
        await self._status_embed("Cog Unloaded", "ℹ️ **np** cog unloaded.", color=0xBBBBBB)

    async def load_staff(self):
        await self.client.wait_until_ready()
        if self.db:
            try:
                # Ensure staff table exists
                await self.db.execute('''
                CREATE TABLE IF NOT EXISTS staff (
                    id INTEGER PRIMARY KEY
                )
                ''')
                await self.db.commit()
                
                # Load staff IDs
                async with self.db.execute('SELECT id FROM staff') as cursor:
                    self.staff = {row[0] for row in await cursor.fetchall()}
                    print(f"[NP] Loaded {len(self.staff)} staff members")
            except Exception as e:
                print(f"[NP] Error loading staff: {e}")
                self.staff = set()  # Fallback to empty set

    # ───────────────────────────── Shard / Ready logs ─────────────────────────────

    @commands.Cog.listener()
    async def on_ready(self):
        if self._announced_ready:
            return
        self._announced_ready = True
        # Load staff when bot is ready, not during cog_load
        await self.load_staff()
        if self.client.user:
            print(f"[NP] Client ready as {self.client.user} ({self.client.user.id})")
            await self._status_embed(
                "Client Ready",
                f"🟢 Client ready as **{self.client.user}** (`{self.client.user.id}`)"
            )

    @commands.Cog.listener()
    async def on_shard_connect(self, shard_id: int):
        print(f"[NP] Shard {shard_id} has connected.")
        await self._status_embed(
            "Shard Connected",
            f"🟢 **Shard {shard_id}** has connected."
        )

    @commands.Cog.listener()
    async def on_shard_ready(self, shard_id: int):
        print(f"[NP] Shard {shard_id} is ready.")
        await self._status_embed(
            "Shard Ready",
            f"✅ **Shard {shard_id}** is ready."
        )

    @commands.Cog.listener()
    async def on_shard_disconnect(self, shard_id: int):
        print(f"[NP] Shard {shard_id} disconnected.")
        await self._status_embed(
            "Shard Disconnected",
            f"🔴 **Shard {shard_id}** disconnected."
        )

    # ───────────────────────────── Tasks ─────────────────────────────

    @tasks.loop(minutes=10)
    async def expiry_check(self):
        """Periodically remove expired no-prefix entries and DM users."""
        now_timestamp = int(datetime.now(timezone.utc).timestamp())

        # Collect expired users
        if not self.db:
            return
        async with self.db.execute(
            "SELECT user_id FROM np WHERE expiry_time IS NOT NULL AND expiry_time <= ?",
            (now_timestamp,)
        ) as cursor:
            expired_users = [row[0] for row in await cursor.fetchall()]

        if not expired_users:
            return

        # Delete in chunks to avoid very long SQL IN lists
        CHUNK = 100
        for i in range(0, len(expired_users), CHUNK):
            chunk = expired_users[i:i+CHUNK]
            placeholders = ",".join(["?"] * len(chunk))
            await self.db.execute(f"DELETE FROM np WHERE user_id IN ({placeholders})", tuple(chunk))
        await self.db.commit()

        # Post-process users: DM + remove role + log
        for user_id_str in expired_users:
            if user_id_str is None:
                continue
            try:
                user_id = int(user_id_str)
            except (TypeError, ValueError):
                continue
            user = self.client.get_user(user_id)
            if not user:
                continue

            log_channel = self.client.get_channel(LOG_CHANNEL_ID)
            from discord import TextChannel, Thread
            if isinstance(log_channel, (TextChannel, Thread)):
                embed_log = discord.Embed(
                    title="No Prefix Expired",
                    description=(
                        f"**User**: [{user}](https://discord.com/users/{user.id})\n"
                        f"**User Mention**: {user.mention}\n"
                        f"**ID**: {user.id}\n\n"
                        f"**Removed By**: **Sleepless Development**\n"
                    ),
                    color=0x006fb9
                )
                thumb = user.display_avatar.url if user.avatar else user.default_avatar.url
                embed_log.set_thumbnail(url=thumb)
                embed_log.set_footer(text="No Prefix Removal Log")
                try:
                    await log_channel.send(f"<#{LOG_CHANNEL_ID}>", embed=embed_log)
                except discord.HTTPException:
                    pass

            guild = self.client.get_guild(1369497441061179393)
            if guild:
                member = guild.get_member(user.id)
                if member:
                    role = guild.get_role(1414349030498107413)
                    if role and role in member.roles:
                        try:
                            await member.remove_roles(role)
                        except discord.HTTPException:
                            pass

            embed = discord.Embed(
                description="<:feast_warning:1400143131990560830> Your No Prefix status has **Expired**. You will now require the prefix to use commands.",
                color=0x006fb9
            )
            icon = user.avatar.url if user.avatar else user.default_avatar.url
            embed.set_author(name="No Prefix Expired", icon_url=icon)
            embed.set_footer(text="Sleepless - No Prefix, join support to regain access.")

            support = Button(label='Support', style=ButtonStyle.link, url='https://discord.gg/5wtjDkYbVh')
            view = View()
            view.add_item(support)

            try:
                await user.send(f"{user.mention}", embed=embed, view=view)
            except (discord.Forbidden, discord.HTTPException):
                pass

    @expiry_check.before_loop
    async def before_expiry_check(self):
        await self.client.wait_until_ready()

    # ───────────────────────────── Commands ─────────────────────────────

    @commands.group(name="np", help="Allows you to add someone to the no-prefix list (owner/staff only)")
    @commands.check(is_owner_or_staff)
    async def _np(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @_np.command(name="list", help="List of no-prefix users")
    @commands.check(is_owner_or_staff)
    async def np_list(self, ctx: commands.Context):
        if not self.db:
            await ctx.reply("Database not available.", mention_author=False)
            return
        async with self.db.execute("SELECT user_id FROM np") as cursor:
            ids = [int(row[0]) for row in await cursor.fetchall()]

        if not ids:
            await ctx.reply("No users in the no-prefix list.", mention_author=False)
            return

        entries = [
            (f"User #{no+1}", f"[PROFILE URL](https://discord.com/users/{mem}) (ID: {mem})")
            for no, mem in enumerate(ids, start=0)
        ]
        paginator = Paginator(
            source=DescriptionEmbedPaginator(
                entries=entries,
                title=f"No Prefix Users [{len(ids)}]",
                description="",
                per_page=10,
                color=0x006fb9
            ),
            ctx=ctx
        )
        await paginator.paginate()

    @_np.command(name="add", help="Add user to no-prefix with time options")
    @commands.check(is_owner_or_staff)
    async def np_add(self, ctx: commands.Context, user: discord.User):
        if not self.db:
            await ctx.reply("Database not available.", mention_author=False)
            return
        async with self.db.execute("SELECT user_id FROM np WHERE user_id = ?", (str(user.id),)) as cursor:
            exists = await cursor.fetchone()

        if exists:
            embed = discord.Embed(
                description=(
                    f"**{user}** is already in the No Prefix list.\n\n"
                    f"**Requested By**: [{ctx.author.display_name}](https://discord.com/users/{ctx.author.id})"
                ),
                color=0x006fb9
            )
            embed.set_author(name="Error")
            await ctx.reply(embed=embed)
            return

        # Ensure author is a discord.User, not Member
        author = ctx.author
        author = getattr(author, "_user", author)
        view = TimeSelectView(user, self.db, author)
        embed = discord.Embed(
            title="Select No Prefix Duration",
            description="**Choose how long no-prefix should be enabled for this user:**",
            color=0x006fb9
        )
        await ctx.reply(embed=embed, view=view)

    @_np.command(name="remove", help="Remove user from no-prefix")
    @commands.check(is_owner_or_staff)
    async def np_remove(self, ctx: commands.Context, user: discord.User):
        if not self.db:
            await ctx.reply("Database not available.", mention_author=False)
            return
        async with self.db.execute("SELECT user_id FROM np WHERE user_id = ?", (str(user.id),)) as cursor:
            exists = await cursor.fetchone()

        if not exists:
            embed = discord.Embed(
                description=(
                    f"**{user}** is not in the No Prefix list.\n\n"
                    f"**Requested By**: [{ctx.author.display_name}](https://discord.com/users/{ctx.author.id})"
                ),
                color=0x006fb9
            )
            embed.set_author(name="Error")
            await ctx.reply(embed=embed)
            return

        await self.db.execute("DELETE FROM np WHERE user_id = ?", (str(user.id),))
        await self.db.commit()

        guild = ctx.bot.get_guild(1369497441061179393)
        if guild:
            member = guild.get_member(user.id)
            if member:
                role = guild.get_role(1414349030498107413)
                if role and role in member.roles:
                    try:
                        await member.remove_roles(role)
                    except discord.HTTPException:
                        pass

        embed = discord.Embed(
            description=(
                f"**User**: [{user}](https://discord.com/users/{user.id})\n"
                f"**User Mention**: {user.mention}\n"
                f"**ID**: {user.id}\n\n"
                f"**Removed By**: **Sleepless Development**"
            ),
            color=0x006fb9
        )
        embed.set_author(name="Removed No Prefix")
        await ctx.reply(embed=embed)

        log_channel = ctx.bot.get_channel(LOG_CHANNEL_ID)
        if isinstance(log_channel, discord.abc.Messageable):
            embed_log = discord.Embed(
                title="No Prefix Removed",
                description=(
                    f"**User**: [{user}](https://discord.com/users/{user.id})\n"
                    f"**User Mention**: {user.mention}\n"
                    f"**ID**: {user.id}\n\n"
                    f"**Removed By**: **Sleepless Development**"
                ),
                color=0x006fb9
            )
            thumb = user.display_avatar.url if user.avatar else user.default_avatar.url
            embed_log.set_thumbnail(url=thumb)
            embed_log.set_footer(text="No Prefix Removal Log")
            try:
                await log_channel.send(f"<@774922425548013609>", embed=embed_log)
            except discord.HTTPException:
                pass

    @_np.command(name="status", help="Check if a user is in the No Prefix list and show details.")
    @commands.check(is_owner_or_staff)
    async def np_status(self, ctx: commands.Context, user: discord.User):
        if not self.db:
            await ctx.reply("Database not available.", mention_author=False)
            return
        async with self.db.execute("SELECT user_id, expiry_time FROM np WHERE user_id = ?", (str(user.id),)) as cursor:
            row = await cursor.fetchone()

        if not row:
            embed = discord.Embed(
                title="No Prefix Status",
                description=(
                    f"**{user}** is not in the No Prefix list.\n\n"
                    f"**Requested By**: [{ctx.author.display_name}](https://discord.com/users/{ctx.author.id})"
                ),
                color=0x006fb9
            )
            await ctx.reply(embed=embed)
            return

        _, expires = row
        if expires:
            expire_time = datetime.fromtimestamp(expires)
            expire_display = f"{expire_time:%Y-%m-%d %H:%M:%S} UTC"
            expire_timestamp = f"<t:{int(expires)}:F>"
        else:
            expire_display = "Lifetime"
            expire_timestamp = "Lifetime"

        embed = discord.Embed(
            title="No Prefix Status",
            description=(
                f"**User**: [{user}](https://discord.com/users/{user.id})\n"
                f"**User ID**: {user.id}\n\n"
                f"**<a:timer:1329404677820911697> Expiry**: {expire_display} ({expire_timestamp})"
            ),
            color=0x006fb9
        )
        thumb = user.display_avatar.url if user.avatar else user.default_avatar.url
        embed.set_thumbnail(url=thumb)
        await ctx.reply(embed=embed)

    # ───────────────────────────── AutoNP (Partners) ─────────────────────────────

    @commands.group(name="autonp", help="Manage auto no-prefix for partner guilds.")
    @commands.is_owner()
    async def autonp(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @autonp.group(name="guild", help="Manage partner guilds for auto no-prefix.")
    async def autonp_guild(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @autonp_guild.command(name="add", help="Add a guild to auto no-prefix.")
    async def add_guild(self, ctx: commands.Context, guild_id: int):
        if not self.db:
            await ctx.reply("Database not available.", mention_author=False)
            return
        async with self.db.execute("SELECT 1 FROM autonp WHERE guild_id = ?", (guild_id,)) as cursor:
            if await cursor.fetchone():
                await ctx.reply("Guild is already added.")
                return
        await self.db.execute("INSERT INTO autonp (guild_id) VALUES (?)", (guild_id,))
        await self.db.commit()
        await ctx.reply(f"Guild {guild_id} added to auto no-prefix.")

    @autonp_guild.command(name="remove", help="Remove a guild from auto no-prefix.")
    async def remove_guild(self, ctx: commands.Context, guild_id: int):
        if not self.db:
            await ctx.reply("Database not available.", mention_author=False)
            return
        async with self.db.execute("SELECT 1 FROM autonp WHERE guild_id = ?", (guild_id,)) as cursor:
            if not await cursor.fetchone():
                await ctx.reply("Guild is not in auto no-prefix.")
                return
        await self.db.execute("DELETE FROM autonp WHERE guild_id = ?", (guild_id,))
        await self.db.commit()
        await ctx.reply(f"Guild {guild_id} removed from auto no-prefix.")

    @autonp_guild.command(name="list", help="List all guilds with auto no-prefix.")
    @commands.check(is_owner_or_staff)
    async def list_guilds(self, ctx: commands.Context):
        if not self.db:
            await ctx.reply("Database not available.", mention_author=False)
            return
        async with self.db.execute("SELECT guild_id FROM autonp") as cursor:
            guilds = [row[0] for row in await cursor.fetchall()]
        if not guilds:
            await ctx.reply("No guilds in auto no-prefix.", mention_author=False)
            return
        await ctx.reply(
            "Guilds in auto no-prefix:\n" + "\n".join(str(g) for g in guilds),
            mention_author=False
        )

    # ───────────────────────────── Nitro Boost Hooks ─────────────────────────────

    async def is_user_in_np(self, user_id: int) -> bool:
        if not self.db:
            return False
        async with self.db.execute("SELECT 1 FROM np WHERE user_id = ?", (str(user_id),)) as cursor:
            return (await cursor.fetchone()) is not None

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        # Avoid using the DB if it hasn't been initialized yet
        if not self.db:
            return

        # Added boost
        if before.premium_since is None and after.premium_since is not None:
            async with self.db.execute("SELECT 1 FROM autonp WHERE guild_id = ?", (after.guild.id,)) as cursor:
                if not await cursor.fetchone():
                    return
            if not await self.is_user_in_np(after.id):
                await self.add_np(getattr(after, '_user', after), timedelta(days=60))
                log_channel = self.client.get_channel(LOG_CHANNEL_ID)
                if isinstance(log_channel, discord.abc.Messageable):
                    embed = discord.Embed(
                        title="Added No Prefix due to Boosting Partner Server",
                        description=f"**User**: **[{after}](https://discord.com/users/{after.id})** (ID: {after.id})\n**Server**: {after.guild.name}",
                        color=0x00FF00
                    )
                    try:
                        message = await log_channel.send("<@774922425548013609>", embed=embed)
                        if hasattr(message, "publish"):
                            await message.publish()
                    except discord.HTTPException:
                        pass

    async def handle_boost_removal(self, user: discord.Member):
        # Avoid using the DB if it hasn't been initialized yet
        if not self.db:
            return

        async with self.db.execute("SELECT 1 FROM autonp WHERE guild_id = ?", (user.guild.id,)) as cursor:
            if not await cursor.fetchone():
                return
        if await self.is_user_in_np(user.id):
            log_channel = self.client.get_channel(1402339343242100966)
            if isinstance(log_channel, discord.abc.Messageable):
                embed = discord.Embed(
                    title="Removed No Prefix due to Unboosting Partner Server",
                    description=f"**User**: **[{user}](https://discord.com/users/{user.id})** (ID: {user.id})\n**Server**: {user.guild.name}",
                    color=0xFF0000
                )
                try:
                    message = await log_channel.send("<@1402339343242100966>", embed=embed)
                    if hasattr(message, "publish"):
                        await message.publish()
                except discord.HTTPException:
                    pass
                    pass

    async def add_np(self, user: discord.abc.User, duration: timedelta):
        expiry_time = datetime.now(timezone.utc) + duration
        if self.db:
            await self.db.execute(
                "INSERT INTO np (user_id, track_name, provider, expiry_time) VALUES (?, ?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET expiry_time=excluded.expiry_time",
                (str(user.id), "Boost Reward", "Auto", int(expiry_time.timestamp()))
            )
            await self.db.commit()

        embed = discord.Embed(
            title="Congratulations—you got 2 months No Prefix!",
            description=(
                "You've been credited 2 months of global No Prefix for boosting our Partnered Servers. "
                "You can now use my commands without prefix. If you wish to remove it, please reach out "
                "[Support Server](https://discord.gg/5wtjDkYbVh)."
            ),
            color=0x006fb9
        )
        # Only attempt to DM if the object supports sending messages
        import inspect
        send_method = getattr(user, "send", None)
        if callable(send_method) and inspect.iscoroutinefunction(send_method):
            try:
                await send_method(embed=embed)
            except (discord.Forbidden, discord.HTTPException):
                pass

        guild = self.client.get_guild(1369497441061179393)
        if guild:
            member = guild.get_member(user.id)
            if member is not None:
                role = guild.get_role(1369504776219398208)
                if role:
                    try:
                        await member.add_roles(role)
                    except discord.HTTPException:
                        pass

    async def remove_np(self, user: discord.User):
        if not self.db:
            return
        async with self.db.execute("SELECT expiry_time FROM np WHERE user_id = ?", (str(user.id),)) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return

        await self.db.execute("DELETE FROM np WHERE user_id = ?", (str(user.id),))
        await self.db.commit()

        embed = discord.Embed(
            title="<a:Warning:1299512982006665216> Global No Prefix Expired",
            description=(
                f"Hey {user.mention}, your global no prefix has expired!\n\n"
                "__**Reason:**__ Unboosting our Partnered Server.\n"
                "If you think this is a mistake then please reach out "
                "[Support Server](https://discord.gg/5wtjDkYbVh)."
            ),
            color=0x006fb9
        )
        # Only attempt to DM if the object supports sending messages
        if hasattr(user, "send"):
            try:
                await user.send(embed=embed)
            except (discord.Forbidden, discord.HTTPException):
                pass

        guild = self.client.get_guild(1369497441061179393)
        if guild:
            member = guild.get_member(user.id)
            if member is not None:
                role = guild.get_role(1369504776219398208)
                if role and role in member.roles:
                    try:
                        await member.remove_roles(role)
                    except discord.HTTPException:
                        pass

    @_np.command(name="reset", help="Reset/clear all users from the no-prefix list")
    @commands.is_owner()
    async def np_reset(self, ctx: commands.Context):
        embed = discord.Embed(
            title="Confirm Reset",
            description="Are you sure you want to remove **ALL** users from the no-prefix list? This action cannot be undone.",
            color=0x006fb9
        )

        yes_button = Button(label="Yes", style=ButtonStyle.danger)
        no_button  = Button(label="No",  style=ButtonStyle.secondary)

        view = View()
        view.add_item(yes_button)
        view.add_item(no_button)

        async def yes_callback(interaction: discord.Interaction):
            if interaction.user.id != ctx.author.id:
                return await interaction.response.send_message("This interaction is not for you.", ephemeral=True)

            if not self.db:
                await interaction.response.send_message("Database not available.", ephemeral=True)
                return
            async with self.db.execute("SELECT COUNT(*) FROM np") as cursor:
                result = await cursor.fetchone()
                count = result[0] if result else 0

            await self.db.execute("DELETE FROM np")
            await self.db.commit()

            guild = self.client.get_guild(1369497441061179393)
            if guild:
                role = guild.get_role(1369504776219398208)
                if role:
                    for member in list(guild.members):
                        if role in member.roles:
                            try:
                                await member.remove_roles(role, reason="Global no-prefix reset")
                            except discord.HTTPException:
                                pass

            success_embed = discord.Embed(
                title="<:tick_red:1374052118020882563> No-Prefix Reset Complete",
                description=f"Successfully removed {count} users from the no-prefix list.",
                color=0x006fb9
            )
            await interaction.response.edit_message(embed=success_embed, view=None)

            log_channel = self.client.get_channel(1400412781949222962)
            if isinstance(log_channel, discord.abc.Messageable):
                log_embed = discord.Embed(
                    title="No-Prefix List Reset",
                    description=(
                        f"**Reset By**: [{ctx.author.display_name}](https://discord.com/users/{ctx.author.id})\n"
                        f"**Users Removed**: {count}"
                    ),
                    color=0x006fb9
                )
                log_embed.set_footer(text="No Prefix Reset Log")
                try:
                    await log_channel.send("<#1376174251174002799>", embed=log_embed)
                except discord.HTTPException:
                    pass

        async def no_callback(interaction: discord.Interaction):
            if interaction.user.id != ctx.author.id:
                return await interaction.response.send_message("This interaction is not for you.", ephemeral=True)
            cancel_embed = discord.Embed(
                title="Reset Cancelled",
                description="No changes have been made to the no-prefix list.",
                color=0x006fb9
            )
            await interaction.response.edit_message(embed=cancel_embed, view=None)

        yes_button.callback = yes_callback
        no_button.callback  = no_callback

        await ctx.reply(embed=embed, view=view)

# ─────────────────────────────────────────────────────────────────────────────
# Setup entrypoint
# ─────────────────────────────────────────────────────────────────────────────

async def setup(bot: commands.Bot):
    await bot.add_cog(NoPrefix(bot))
