import discord
from discord.ext import commands
import sqlite3
import os
from utils.timezone_helpers import get_timezone_helpers

from utils.error_helpers import StandardErrorHandler
DB_FILE = "db/joinchannel.db"

class joinchannel(commands.Cog):
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot
        self.tz_helpers = get_timezone_helpers(bot)
        self.guild_invites = {}
        self.default_join_message = "{invited.mention} is invited by {inviter.mention} ({inviter.invites} invites)"

    async def setup_hook(self):
        await self.init_db()

    async def init_db(self):
        await self.bot.wait_until_ready()
        os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute("""
            CREATE TABLE IF NOT EXISTS join_channels (
                guild_id TEXT,
                channel_id TEXT,
                PRIMARY KEY (guild_id, channel_id)
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS invite_settings (
                guild_id TEXT PRIMARY KEY,
                join_message TEXT DEFAULT NULL
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS invite_counts (
                guild_id TEXT,
                user_id TEXT,
                invites INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            );
            """)
            conn.commit()

    # ---------------- VAR REPLACER ----------------
    from typing import Optional

    async def replace_vars(self, message: str, inviter: Optional[discord.User], invited: discord.Member):
        inviter_invites = 0
        if inviter:
            with sqlite3.connect(DB_FILE) as conn:
                cur = conn.cursor()
                cur.execute("SELECT invites FROM invite_counts WHERE guild_id = ? AND user_id = ?",
                            (str(invited.guild.id), str(inviter.id)))
                row = cur.fetchone()
                inviter_invites = row[0] if row else 0

        # Format join time with timezone
        join_time_str = "Unknown"
        if invited.joined_at:
            join_time_str = await self.tz_helpers.format_datetime_for_guild(invited.joined_at, invited.guild, "%Y-%m-%d %H:%M:%S %Z")

        repl = {
            "{inviter}": f"{inviter}" if inviter else "Unknown",
            "{inviter.username}": inviter.name if inviter else "Unknown",
            "{inviter.mention}": inviter.mention if inviter else "Unknown",
            "{inviter.id}": str(inviter.id) if inviter else "Unknown",
            "{inviter.tag}": f"{inviter}" if inviter else "Unknown",
            "{inviter.invites}": str(inviter_invites),
            "{invited}": f"{invited}",
            "{invited.username}": invited.name,
            "{invited.mention}": invited.mention,
            "{invited.id}": str(invited.id),
            "{invited.tag}": f"{invited}",
            "{server}": invited.guild.name,
            "{server.id}": str(invited.guild.id),
            "{server.membercount}": str(invited.guild.member_count),
            "{join.time}": join_time_str,
            "{join.timestamp}": str(int(invited.joined_at.timestamp())) if invited.joined_at else "Unknown"
        }
        for k, v in repl.items():
            message = message.replace(k, v)
        return message

    # ---------------- LISTENER ----------------
    @commands.Cog.listener()
    async def on_member_join(self, member):
        inviter = None
        try:
            before = self.guild_invites.get(member.guild.id, [])
            after = await member.guild.invites()
            for old in before:
                for new in after:
                    if old.code == new.code and old.uses < new.uses:
                        inviter = new.inviter
                        break
            self.guild_invites[member.guild.id] = after
        except discord.Forbidden:
            pass

        if inviter:
            with sqlite3.connect(DB_FILE) as conn:
                cur = conn.cursor()
                cur.execute("INSERT OR IGNORE INTO invite_counts VALUES (?, ?, 0)", (str(member.guild.id), str(inviter.id)))
                cur.execute("UPDATE invite_counts SET invites = invites + 1 WHERE guild_id = ? AND user_id = ?",
                            (str(member.guild.id), str(inviter.id)))
                conn.commit()

        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute("SELECT channel_id FROM join_channels WHERE guild_id = ?", (str(member.guild.id),))
            chans = [int(r[0]) for r in cur.fetchall()]
            cur.execute("SELECT join_message FROM invite_settings WHERE guild_id = ?", (str(member.guild.id),))
            row = cur.fetchone()
            join_msg = row[0] if row and row[0] else self.default_join_message

        if not chans:
            return
        msg = await self.replace_vars(join_msg, inviter, member)
        for cid in chans:
            ch = member.guild.get_channel(cid)
            if ch:
                await ch.send(msg)

    # ---------------- COMMANDS ----------------
    @commands.group(invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def joinchannel(self, ctx):
        emb = discord.Embed(
            title="JoinChannel Commands",
            description=(
                "`add <#channel>` - Add a join channel\n"
                "`remove <#channel>` - Remove one\n"
                "`list` - List channels\n"
                "`setmessage <msg>` - Set custom join msg\n"
                "`viewmessage` - View current\n"
                "`testmessage` - Send test"
            ),
            color=discord.Color.blurple()
        )
        await ctx.send(embed=emb)

    @joinchannel.command()
    async def add(self, ctx, channel: discord.TextChannel):
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute("INSERT OR IGNORE INTO join_channels VALUES (?, ?)", (str(ctx.guild.id), str(channel.id)))
            conn.commit()
        await ctx.send(f"✅ Added {channel.mention}")

    @joinchannel.command()
    async def remove(self, ctx, channel: discord.TextChannel):
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("DELETE FROM join_channels WHERE guild_id = ? AND channel_id = ?",
                         (str(ctx.guild.id), str(channel.id)))
            conn.commit()
        await ctx.send(f"✅ Removed {channel.mention}")

    @joinchannel.command()
    async def list(self, ctx):
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute("SELECT channel_id FROM join_channels WHERE guild_id = ?", (str(ctx.guild.id),))
            rows = cur.fetchall()
        if not rows:
            return await ctx.send("ℹ No join channels set.")
        channels = [f"<#{r[0]}>" for r in rows]
        emb = discord.Embed(title="Join Channels", description="\n".join(channels), color=discord.Color.green())
        await ctx.send(embed=emb)

    @joinchannel.command()
    async def setmessage(self, ctx, *, message: str):
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("INSERT OR IGNORE INTO invite_settings (guild_id) VALUES (?)", (str(ctx.guild.id),))
            conn.execute("UPDATE invite_settings SET join_message = ? WHERE guild_id = ?",
                         (message, str(ctx.guild.id)))
            conn.commit()
        await ctx.send("✅ Custom join message set.")

    @joinchannel.command()
    async def viewmessage(self, ctx):
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute("SELECT join_message FROM invite_settings WHERE guild_id = ?", (str(ctx.guild.id),))
            row = cur.fetchone()
        msg = row[0] if row and row[0] else self.default_join_message
        await ctx.send(f"📢 Current message:\n```\n{msg}\n```")

    @joinchannel.command()
    async def testmessage(self, ctx):
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute("SELECT channel_id FROM join_channels WHERE guild_id = ?", (str(ctx.guild.id),))
            rows = cur.fetchall()
            cur.execute("SELECT join_message FROM invite_settings WHERE guild_id = ?", (str(ctx.guild.id),))
            row = cur.fetchone()
            join_msg = row[0] if row and row[0] else self.default_join_message
        if not rows:
            return await ctx.send("❌ No join channels set.")
        ch = ctx.guild.get_channel(int(rows[0][0]))
        if not ch:
            return await ctx.send("❌ Join channel not found.")
        msg = await self.replace_vars(join_msg, ctx.author, ctx.author)
        await ch.send(msg)
        await ctx.send(f"✅ Sent test message in {ch.mention}")

def setup(bot):
    bot.add_cog(joinchannel(bot))
