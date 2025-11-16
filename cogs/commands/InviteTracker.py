import discord
from discord.ext import commands
import sqlite3
import aiosqlite
from datetime import datetime, timezone

from typing import Optional

from utils.error_helpers import StandardErrorHandler
DB_FILE = "db/invite_tracker.db"

# ------------------ Main Cog ------------------
class invitetracker(commands.Cog):
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot
        # Removed in-memory invite cache: self.guild_invites = {}

    async def save_guild_invites(self, guild_id, invites_data):
        """Save guild invites cache to database"""
        async with aiosqlite.connect(DB_FILE) as conn:
            # Store as JSON in a simple key-value table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS invite_cache (
                    guild_id INTEGER PRIMARY KEY,
                    invites_data TEXT
                )
            ''', ())
            
            import json
            await conn.execute('''
                INSERT OR REPLACE INTO invite_cache (guild_id, invites_data)
                VALUES (?, ?)
            ''', (guild_id, json.dumps(invites_data)))
            await conn.commit()

    async def load_guild_invites(self, guild_id):
        """Load guild invites cache from database"""
        async with aiosqlite.connect(DB_FILE) as conn:
            cursor = await conn.execute('''
                SELECT invites_data FROM invite_cache WHERE guild_id = ?
            ''', (guild_id,))
            row = await cursor.fetchone()
            if row:
                import json
                return json.loads(row[0])
            return []

    async def cog_load(self):
        """Runs when the cog is loaded (instead of __init__)."""
        await self.init_db()

    async def init_db(self):
        # Initialize database tables without waiting for bot ready
        with sqlite3.connect(DB_FILE) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS invites (
                    guild_id TEXT,
                    inviter_id TEXT,
                    invite_code TEXT,
                    uses INTEGER DEFAULT 0,
                    PRIMARY KEY(guild_id, invite_code)
                );

                CREATE TABLE IF NOT EXISTS invite_stats (
                    guild_id TEXT,
                    user_id TEXT,
                    invites INTEGER DEFAULT 0,
                    fake INTEGER DEFAULT 0,
                    leaves INTEGER DEFAULT 0,
                    rejoins INTEGER DEFAULT 0,
                    PRIMARY KEY(guild_id, user_id)
                );

                CREATE TABLE IF NOT EXISTS invite_settings (
                    guild_id TEXT PRIMARY KEY,
                    enabled INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS member_invites (
                    guild_id TEXT,
                    member_id TEXT,
                    inviter_id TEXT,
                    PRIMARY KEY(guild_id, member_id)
                );
            """)
            conn.commit()

    async def cache_all_guild_invites(self):
        """Cache invites for all guilds - call this after bot is ready"""
        if not self.bot.is_ready():
            return
            
        for guild in self.bot.guilds:
            try:
                invites = await guild.invites()
                # Convert invites to serializable format
                invites_data = [{'code': inv.code, 'uses': inv.uses, 'max_uses': inv.max_uses, 'inviter_id': inv.inviter.id if inv.inviter else None} for inv in invites]
                await self.save_guild_invites(guild.id, invites_data)
            except discord.Forbidden:
                await self.save_guild_invites(guild.id, [])

    # ------------------ Helper DB Methods ------------------
    async def is_enabled(self, guild_id):
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.execute(
                "SELECT enabled FROM invite_settings WHERE guild_id = ?",
                (str(guild_id),)
            )
            row = cursor.fetchone()
            return bool(row[0]) if row else False

    async def set_enabled(self, guild_id, enabled: bool):
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("""
                INSERT INTO invite_settings (guild_id, enabled)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET enabled=excluded.enabled
            """, (str(guild_id), int(enabled)))
            conn.commit()

    # ------------------ Commands ------------------
    @commands.command(name="inviteenable")
    @commands.has_permissions(administrator=True)
    async def invitetrackerenable(self, ctx):
        await self.set_enabled(ctx.guild.id, True)
        await ctx.reply("✅ Invite tracking **enabled** for this server.")

    @commands.command(name="invitedisable")
    @commands.has_permissions(administrator=True)
    async def invitetrackerdisable(self, ctx):
        await self.set_enabled(ctx.guild.id, False)
        await ctx.reply("✅ Invite tracking **disabled** for this server.")

    # ------------------ Event Listeners ------------------
    @commands.Cog.listener()
    async def on_ready(self):
        """Cache all guild invites when bot is ready"""
        await self.cache_all_guild_invites()

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        try:
            invites = await guild.invites()
            invites_data = [{'code': inv.code, 'uses': inv.uses, 'max_uses': inv.max_uses, 'inviter_id': inv.inviter.id if inv.inviter else None} for inv in invites]
            await self.save_guild_invites(guild.id, invites_data)
        except discord.Forbidden:
            await self.save_guild_invites(guild.id, [])

    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        invites_data = await self.load_guild_invites(invite.guild.id)
        # Add the new invite to the cached data
        invite_data = {'code': invite.code, 'uses': invite.uses, 'max_uses': invite.max_uses, 'inviter_id': invite.inviter.id if invite.inviter else None}
        invites_data.append(invite_data)
        await self.save_guild_invites(invite.guild.id, invites_data)

    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        invites_data = await self.load_guild_invites(invite.guild.id)
        # Remove the deleted invite from cached data
        invites_data = [inv for inv in invites_data if inv['code'] != invite.code]
        await self.save_guild_invites(invite.guild.id, invites_data)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if not await self.is_enabled(member.guild.id):
            return

        guild = member.guild
        before_invites_data = await self.load_guild_invites(guild.id)
        try:
            after_invites = await guild.invites()
        except discord.Forbidden:
            return

        # Update cache with new invite data
        after_invites_data = [{'code': inv.code, 'uses': inv.uses, 'max_uses': inv.max_uses, 'inviter_id': inv.inviter.id if inv.inviter else None} for inv in after_invites]
        await self.save_guild_invites(guild.id, after_invites_data)

        used_invite = None

        for before_data in before_invites_data:
            after = discord.utils.get(after_invites, code=before_data['code'])
            if after and after.uses > before_data['uses']:
                used_invite = after
                break

        inviter_id = None
        if used_invite and getattr(used_invite, 'inviter', None):
            inviter_id = used_invite.inviter.id

        now = datetime.now(timezone.utc)
        acc_age = now - member.created_at

        with sqlite3.connect(DB_FILE) as conn:
            if inviter_id and used_invite and hasattr(used_invite, 'code'):
                conn.execute("""
                    INSERT OR IGNORE INTO invites (guild_id, inviter_id, invite_code, uses)
                    VALUES (?, ?, ?, 0)
                """, (str(guild.id), str(inviter_id), used_invite.code))

                conn.execute("""
                    UPDATE invites
                    SET uses = uses + 1
                    WHERE guild_id = ? AND invite_code = ?
                """, (str(guild.id), used_invite.code))

                conn.execute("""
                    INSERT OR IGNORE INTO invite_stats (guild_id, user_id)
                    VALUES (?, ?)
                """, (str(guild.id), str(inviter_id)))

                if acc_age.total_seconds() < 86400:
                    conn.execute("""
                        UPDATE invite_stats
                        SET fake = fake + 1
                        WHERE guild_id = ? AND user_id = ?
                    """, (str(guild.id), str(inviter_id)))
                else:
                    conn.execute("""
                        UPDATE invite_stats
                        SET invites = invites + 1
                        WHERE guild_id = ? AND user_id = ?
                    """, (str(guild.id), str(inviter_id)))

            conn.execute("""
                INSERT OR REPLACE INTO member_invites (guild_id, member_id, inviter_id)
                VALUES (?, ?, ?)
            """, (str(guild.id), str(member.id), str(inviter_id) if inviter_id else None))
            conn.commit()

        # Send detailed join message to join channel
        join_channel_id = self.get_join_channel(guild.id)
        if join_channel_id:
            join_channel = guild.get_channel(join_channel_id)
            if join_channel:
                embed = discord.Embed(
                    title="🎉 Member Joined",
                    color=0x00FF00,
                    timestamp=datetime.now(timezone.utc)
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.add_field(
                    name="👤 Member",
                    value=f"{member.mention}\n**{member.display_name}**\n`{member.id}`",
                    inline=True
                )
                
                if inviter_id:
                    inviter = guild.get_member(int(inviter_id))
                    if inviter:
                        embed.add_field(
                            name="🎯 Invited By",
                            value=f"{inviter.mention}\n**{inviter.display_name}**\n`{inviter_id}`",
                            inline=True
                        )
                    else:
                        embed.add_field(
                            name="🎯 Invited By",
                            value=f"<@{inviter_id}>\n`{inviter_id}`\n*(User left server)*",
                            inline=True
                        )
                else:
                    embed.add_field(
                        name="🎯 Invited By",
                        value="❓ Unknown\n*(Vanity URL or Widget)*",
                        inline=True
                    )

                if used_invite:
                    embed.add_field(
                        name="📨 Invite Code",
                        value=f"`{used_invite.code}`\n**Uses:** {used_invite.uses}",
                        inline=True
                    )

                # Account age warning
                if acc_age.total_seconds() < 86400:
                    hours = int(acc_age.total_seconds() / 3600)
                    embed.add_field(
                        name="⚠️ Account Age Warning",
                        value=f"Account created **{hours} hours ago**\n*(Potential fake account)*",
                        inline=False
                    )
                    embed.color = 0xFFA500  # Orange for warning
                else:
                    days = acc_age.days
                    embed.add_field(
                        name="📅 Account Age",
                        value=f"Account created **{days} days ago**",
                        inline=False
                    )

                try:
                    await join_channel.send(embed=embed)
                except Exception as e:
                    print(f"Error sending join message: {e}")

        # Log member join event
        try:
            from utils.activity_logger import ActivityLogger
            activity_logger = ActivityLogger()
            await activity_logger.log(
                guild_id=member.guild.id,
                user_id=member.id,
                username=str(member),
                action=f"Joined server",
                type_="member",
                details=f"Invited by: {inviter_id if inviter_id else 'Unknown'}"
            )
        except Exception as e:
            print(f"[ACTIVITY LOG] Failed to log member join: {e}")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if not await self.is_enabled(member.guild.id):
            return
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.execute("""
                SELECT inviter_id
                FROM member_invites
                WHERE guild_id = ? AND member_id = ?
            """, (str(member.guild.id), str(member.id)))
            row = cursor.fetchone()
            if row and row[0]:
                inviter_id = row[0]
                conn.execute("""
                    UPDATE invite_stats
                    SET leaves = leaves + 1
                    WHERE guild_id = ? AND user_id = ?
                """, (str(member.guild.id), inviter_id))
                conn.commit()

        # Log member leave event
        try:
            from utils.activity_logger import ActivityLogger
            activity_logger = ActivityLogger()
            await activity_logger.log(
                guild_id=member.guild.id,
                user_id=member.id,
                username=str(member),
                action=f"Left server",
                type_="member",
                details=f"Inviter: {inviter_id if row and row[0] else 'Unknown'}"
            )
        except Exception as e:
            print(f"[ACTIVITY LOG] Failed to log member leave: {e}")

    # ------------------ Commands to check invites ------------------
    def get_join_channel(self, guild_id):
        """Get the configured join channel for a guild"""
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.execute("""
                SELECT channel_id FROM join_channels WHERE guild_id = ?
            """, (str(guild_id),))
            row = cursor.fetchone()
            return int(row[0]) if row else None

    async def set_join_channel(self, guild_id, channel_id):
        """Set the join channel for a guild"""
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO join_channels (guild_id, channel_id)
                VALUES (?, ?)
            """, (str(guild_id), str(channel_id)))
            conn.commit()

    @commands.command(name="setjoinchannel")
    @commands.has_permissions(manage_guild=True)
    async def set_join_channel_cmd(self, ctx, channel: Optional[discord.TextChannel] = None):
        """Set the channel where member join notifications will be sent"""
        if not await self.is_enabled(ctx.guild.id):
            return await ctx.reply("❌ Invite tracking is disabled for this server.")
        
        if not channel:
            # Clear join channel
            with sqlite3.connect(DB_FILE) as conn:
                conn.execute("DELETE FROM join_channels WHERE guild_id = ?", (str(ctx.guild.id),))
                conn.commit()
            return await ctx.reply("✅ Join channel notifications disabled.")
        
        await self.set_join_channel(ctx.guild.id, channel.id)
        embed = discord.Embed(
            title="✅ Join Channel Set",
            description=f"Member join notifications will now be sent to {channel.mention}",
            color=0x00FF00
        )
        await ctx.reply(embed=embed)
    async def inviteinfo(self, ctx, member: Optional[discord.Member] = None):
        """Get detailed invite information about a user"""
        member = member or ctx.author
        if not await self.is_enabled(ctx.guild.id):
            return await ctx.reply("❌ Invite tracking is disabled for this server.")

        with sqlite3.connect(DB_FILE) as conn:
            # Get who invited this member
            cursor = conn.execute("""
                SELECT inviter_id
                FROM member_invites
                WHERE guild_id = ? AND member_id = ?
            """, (str(ctx.guild.id), str(member.id)))
            inviter_row = cursor.fetchone()

            # Get member's invite stats
            cursor = conn.execute("""
                SELECT SUM(uses) as total_invites
                FROM invites
                WHERE guild_id = ? AND inviter_id = ?
            """, (str(ctx.guild.id), str(member.id)))
            invites_row = cursor.fetchone()

            # Get member's detailed stats
            cursor = conn.execute("""
                SELECT invites, fake, leaves, rejoins
                FROM invite_stats
                WHERE guild_id = ? AND user_id = ?
            """, (str(ctx.guild.id), str(member.id)))
            stats_row = cursor.fetchone()

        embed = discord.Embed(
            title="📨 Invite Information",
            color=0x00E6A7
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        # Who invited this member
        if inviter_row and inviter_row[0]:
            inviter_id = inviter_row[0]
            inviter = ctx.guild.get_member(int(inviter_id))
            if not inviter:
                try:
                    inviter = await self.bot.fetch_user(int(inviter_id))
                except discord.NotFound:
                    inviter = None

            if inviter:
                embed.add_field(
                    name="🎯 Invited By",
                    value=f"**{inviter.display_name}**\n`{inviter.id}`",
                    inline=True
                )
            else:
                embed.add_field(
                    name="🎯 Invited By", 
                    value=f"Unknown User\n`{inviter_id}`",
                    inline=True
                )
        else:
            embed.add_field(
                name="🎯 Invited By",
                value="❓ Unknown",
                inline=True
            )

        # Member's invite count
        total_invites = invites_row[0] if invites_row and invites_row[0] else 0
        embed.add_field(
            name="📊 Total Invites",
            value=f"**{total_invites}** invites",
            inline=True
        )

        # Detailed stats if available
        if stats_row:
            real_invites, fake_invites, leaves, rejoins = stats_row
            embed.add_field(
                name="📈 Detailed Stats",
                value=f"✅ Real: {real_invites or 0}\n"
                      f"⚠️ Fake: {fake_invites or 0}\n" 
                      f"📤 Left: {leaves or 0}\n"
                      f"🔄 Rejoins: {rejoins or 0}",
                inline=True
            )

        # Member join info
        joined_time = member.joined_at.timestamp() if member.joined_at else 0
        embed.add_field(
            name="👤 Member Info",
            value=f"**Joined:** <t:{int(joined_time)}:R>\n"
                  f"**Created:** <t:{int(member.created_at.timestamp())}:R>",
            inline=False
        )

        await ctx.reply(embed=embed)

    @commands.command(name="inviter")
    async def inviter(self, ctx, member: Optional[discord.Member] = None):
        """Check who invited a specific user"""
        member = member or ctx.author
        if not await self.is_enabled(ctx.guild.id):
            return await ctx.reply("❌ Invite tracking is disabled for this server.")

        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.execute("""
                SELECT inviter_id
                FROM member_invites
                WHERE guild_id = ? AND member_id = ?
            """, (str(ctx.guild.id), str(member.id)))
            row = cursor.fetchone()

        if not row or not row[0]:
            embed = discord.Embed(
                title="❓ Inviter Unknown",
                description=f"Could not find who invited **{member.display_name}**.\n"
                           f"This usually means they joined via:\n"
                           f"• Vanity URL\n"
                           f"• Widget invite\n"
                           f"• Before invite tracking was enabled",
                color=0xFF6B6B
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            return await ctx.reply(embed=embed)

        inviter_id = row[0]
        inviter = ctx.guild.get_member(int(inviter_id))
        if not inviter:
            try:
                inviter = await self.bot.fetch_user(int(inviter_id))
            except discord.NotFound:
                inviter = None

        embed = discord.Embed(
            title="🎯 Inviter Found",
            color=0x00E6A7
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        if inviter:
            embed.add_field(
                name="👤 Member",
                value=f"**{member.display_name}**\n`{member.id}`",
                inline=True
            )
            embed.add_field(
                name="🎯 Invited By",
                value=f"**{inviter.display_name}**\n{inviter.mention}\n`{inviter.id}`",
                inline=True
            )
            
            # Add join time if available
            if member.joined_at:
                embed.add_field(
                    name="📅 Joined",
                    value=f"<t:{int(member.joined_at.timestamp())}:F>",
                    inline=False
                )
        else:
            embed.add_field(
                name="👤 Member",
                value=f"**{member.display_name}**\n`{member.id}`",
                inline=True
            )
            embed.add_field(
                name="🎯 Invited By",
                value=f"Unknown User\n`{inviter_id}`\n*(User may have left)*",
                inline=True
            )

        await ctx.reply(embed=embed)
    async def whoinvited(self, ctx, member: Optional[discord.Member] = None):
        """Quick check of who invited a user (alias for inviter)"""
        return await self.inviteinfo(ctx, member)

    @commands.command(name="invites")
    async def invites(self, ctx, member: Optional[discord.Member] = None):
        """Check how many invites a user has"""
        member = member or ctx.author
        if not await self.is_enabled(ctx.guild.id):
            return await ctx.reply("❌ Invite tracking is disabled for this server.")

        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.execute("""
                SELECT SUM(uses) as total_invites
                FROM invites
                WHERE guild_id = ? AND inviter_id = ?
            """, (str(ctx.guild.id), str(member.id)))
            row = cursor.fetchone()
            
            total_invites = row[0] if row and row[0] else 0
            
            embed = discord.Embed(
                title="📨 Invite Count",
                description=f"**{member.display_name}** has **{total_invites}** invites.",
                color=0x00E6A7
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await ctx.reply(embed=embed)

    @commands.command(name="invited")
    async def invited(self, ctx, member: Optional[discord.Member] = None):
        """Check who invited a user"""
        member = member or ctx.author
        return await self.inviter(ctx, member)

    @commands.command(name="resetinvites")
    @commands.has_permissions(manage_guild=True)
    async def resetinvites(self, ctx, member: discord.Member):
        """Reset a user's invite count"""
        if not await self.is_enabled(ctx.guild.id):
            return await ctx.reply("❌ Invite tracking is disabled for this server.")

        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("""
                UPDATE invites SET uses = 0 
                WHERE guild_id = ? AND inviter_id = ?
            """, (str(ctx.guild.id), str(member.id)))
            conn.commit()

        embed = discord.Embed(
            title="� Invites Reset",
            description=f"Reset **{member.display_name}**'s invite count to 0.",
            color=0x00E6A7
        )
        await ctx.reply(embed=embed)

    @commands.command(name="addinvites")
    @commands.has_permissions(manage_guild=True)
    async def addinvites(self, ctx, member: discord.Member, amount: int):
        """Add invites to a user"""
        if not await self.is_enabled(ctx.guild.id):
            return await ctx.reply("❌ Invite tracking is disabled for this server.")

        if amount <= 0:
            return await ctx.reply("❌ Amount must be a positive number.")

        with sqlite3.connect(DB_FILE) as conn:
            # Create or update invite record
            conn.execute("""
                INSERT OR IGNORE INTO invites (guild_id, inviter_id, invite_code, uses)
                VALUES (?, ?, 'manual', 0)
            """, (str(ctx.guild.id), str(member.id)))
            
            conn.execute("""
                UPDATE invites SET uses = uses + ? 
                WHERE guild_id = ? AND inviter_id = ? AND invite_code = 'manual'
            """, (amount, str(ctx.guild.id), str(member.id)))
            conn.commit()

        embed = discord.Embed(
            title="➕ Invites Added",
            description=f"Added **{amount}** invites to **{member.display_name}**.",
            color=0x00E6A7
        )
        await ctx.reply(embed=embed)

    @commands.command(name="removeinvites")
    @commands.has_permissions(manage_guild=True)
    async def removeinvites(self, ctx, member: discord.Member, amount: int):
        """Remove invites from a user"""
        if not await self.is_enabled(ctx.guild.id):
            return await ctx.reply("❌ Invite tracking is disabled for this server.")

        if amount <= 0:
            return await ctx.reply("❌ Amount must be a positive number.")

        with sqlite3.connect(DB_FILE) as conn:
            # Get current invite count
            cursor = conn.execute("""
                SELECT SUM(uses) as total_invites
                FROM invites
                WHERE guild_id = ? AND inviter_id = ?
            """, (str(ctx.guild.id), str(member.id)))
            row = cursor.fetchone()
            current_invites = row[0] if row and row[0] else 0

            if current_invites < amount:
                return await ctx.reply(f"❌ {member.display_name} only has {current_invites} invites. Cannot remove {amount}.")

            # Remove invites (subtract from manual entry or create negative manual entry)
            conn.execute("""
                INSERT OR IGNORE INTO invites (guild_id, inviter_id, invite_code, uses)
                VALUES (?, ?, 'manual', 0)
            """, (str(ctx.guild.id), str(member.id)))
            
            conn.execute("""
                UPDATE invites SET uses = uses - ? 
                WHERE guild_id = ? AND inviter_id = ? AND invite_code = 'manual'
            """, (amount, str(ctx.guild.id), str(member.id)))
            conn.commit()

        embed = discord.Embed(
            title="➖ Invites Removed",
            description=f"Removed **{amount}** invites from **{member.display_name}**.",
            color=0x00E6A7
        )
        await ctx.reply(embed=embed)

    @commands.command(name="resetserverinvites")
    @commands.has_permissions(administrator=True)
    async def resetserverinvites(self, ctx):
        """Reset all invite counts for the server"""
        if not await self.is_enabled(ctx.guild.id):
            return await ctx.reply("❌ Invite tracking is disabled for this server.")

        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("""
                DELETE FROM invites WHERE guild_id = ?
            """, (str(ctx.guild.id),))
            
            conn.execute("""
                DELETE FROM member_invites WHERE guild_id = ?
            """, (str(ctx.guild.id),))
            conn.commit()

        embed = discord.Embed(
            title="🔄 Server Invites Reset",
            description="Reset all invite counts for this server.",
            color=0x00E6A7
        )
        await ctx.reply(embed=embed)

    @commands.command(name="inviteleaderboard", aliases=["invitestop", "topinvites"])
    async def inviteleaderboard(self, ctx):
        """Show the server's invite leaderboard"""
        if not await self.is_enabled(ctx.guild.id):
            return await ctx.reply("❌ Invite tracking is disabled for this server.")

        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.execute("""
                SELECT inviter_id, SUM(uses) as total_invites
                FROM invites
                WHERE guild_id = ?
                GROUP BY inviter_id
                ORDER BY total_invites DESC
                LIMIT 10
            """, (str(ctx.guild.id),))
            rows = cursor.fetchall()

        if not rows:
            return await ctx.reply("❌ No invite data found for this server.")

        embed = discord.Embed(
            title="🏆 Invite Leaderboard",
            color=0x00E6A7
        )

        leaderboard_text = ""
        for i, (inviter_id, total_invites) in enumerate(rows, 1):
            member = ctx.guild.get_member(int(inviter_id))
            if member:
                name = member.display_name
            else:
                try:
                    user = await self.bot.fetch_user(int(inviter_id))
                    name = user.name
                except:
                    name = f"Unknown User ({inviter_id})"

            if i == 1:
                emoji = "🥇"
            elif i == 2:
                emoji = "🥈"
            elif i == 3:
                emoji = "🥉"
            else:
                emoji = f"`{i}.`"

            leaderboard_text += f"{emoji} **{name}** - {total_invites} invites\n"

        embed.description = leaderboard_text
        await ctx.reply(embed=embed)

# ------------------ Setup ------------------
async def setup(bot):
    await bot.add_cog(invitetracker(bot))
