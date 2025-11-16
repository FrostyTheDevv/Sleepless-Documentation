import discord
from discord.ext import commands, tasks
import aiosqlite
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional
import os
from utils.Tools import blacklist_check, ignore_check
from utils.error_helpers import StandardErrorHandler

DB_PATH = "databases/live_leaderboard.db"

class LiveLeaderboard(commands.Cog):
    """Live leaderboard system with automatic role rewards"""
    
    def __init__(self, bot):
        self.bot = bot
        self.update_lock = asyncio.Lock()
        
    async def cog_load(self):
        """Initialize database and start update loop"""
        await self.init_database()
        self.leaderboard_update_loop.start()
        
    async def cog_unload(self):
        """Stop update loop when cog is unloaded"""
        self.leaderboard_update_loop.cancel()
        
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
        
    async def init_database(self):
        """Initialize the live leaderboard database"""
        try:
            os.makedirs("databases", exist_ok=True)
            
            async with aiosqlite.connect(DB_PATH) as db:
                # Message leaderboard data
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS message_leaderboard (
                        guild_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        username TEXT NOT NULL,
                        daily_count INTEGER DEFAULT 0,
                        weekly_count INTEGER DEFAULT 0,
                        monthly_count INTEGER DEFAULT 0,
                        alltime_count INTEGER DEFAULT 0,
                        current_streak INTEGER DEFAULT 0,
                        longest_streak INTEGER DEFAULT 0,
                        last_activity_date DATE,
                        last_daily_reset DATE,
                        last_weekly_reset DATE,
                        last_monthly_reset DATE,
                        PRIMARY KEY (guild_id, user_id)
                    )
                """)
                
                # Voice leaderboard data
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS voice_leaderboard (
                        guild_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        username TEXT NOT NULL,
                        daily_minutes INTEGER DEFAULT 0,
                        weekly_minutes INTEGER DEFAULT 0,
                        monthly_minutes INTEGER DEFAULT 0,
                        alltime_minutes INTEGER DEFAULT 0,
                        current_streak INTEGER DEFAULT 0,
                        longest_streak INTEGER DEFAULT 0,
                        last_activity_date DATE,
                        last_daily_reset DATE,
                        last_weekly_reset DATE,
                        last_monthly_reset DATE,
                        session_start TIMESTAMP,
                        PRIMARY KEY (guild_id, user_id)
                    )
                """)
                
                # Leaderboard channel settings
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS leaderboard_channels (
                        guild_id INTEGER NOT NULL,
                        chat_channel_id INTEGER,
                        voice_channel_id INTEGER,
                        top_chatter_role_id INTEGER,
                        top_voice_role_id INTEGER,
                        PRIMARY KEY (guild_id)
                    )
                """)
                
                # Leaderboard customization settings
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS leaderboard_customization (
                        guild_id INTEGER NOT NULL,
                        chat_title TEXT DEFAULT 'Chat Leaderboard',
                        voice_title TEXT DEFAULT 'Voice Leaderboard',
                        chat_description TEXT DEFAULT 'Top chatters this week',
                        voice_description TEXT DEFAULT 'Top voice users this week',
                        chat_color TEXT DEFAULT '#00ff88',
                        voice_color TEXT DEFAULT '#ff8800',
                        rank_emojis TEXT DEFAULT '🥇,🥈,🥉,4️⃣,5️⃣,6️⃣,7️⃣,8️⃣,9️⃣,🔟',
                        chat_icon_emoji TEXT DEFAULT '💬',
                        voice_icon_emoji TEXT DEFAULT '🎵',
                        thumbnail_url TEXT,
                        author_icon_url TEXT,
                        footer_text TEXT DEFAULT 'Updates every 10 minutes',
                        show_streaks INTEGER DEFAULT 1,
                        show_daily_stats INTEGER DEFAULT 1,
                        compact_mode INTEGER DEFAULT 0,
                        PRIMARY KEY (guild_id)
                    )
                """)
                
                await db.commit()
                print("[LIVE_LB] Database initialized successfully")
                
        except Exception as e:
            print(f"[LIVE_LB] Database initialization error: {e}")
    
    @tasks.loop(minutes=10)
    async def leaderboard_update_loop(self):
        """Update all leaderboard embeds every 10 minutes"""
        async with self.update_lock:
            try:
                await self.update_all_leaderboards()
            except Exception as e:
                print(f"[LIVE_LB] Update loop error: {e}")
    
    @leaderboard_update_loop.before_loop
    async def before_update_loop(self):
        """Wait for bot to be ready before starting loop"""
        await self.bot.wait_until_ready()
    
    async def update_all_leaderboards(self):
        """Update all active leaderboard embeds"""
        async with aiosqlite.connect(DB_PATH) as db:
            # Get all configured leaderboard channels
            cursor = await db.execute("""
                SELECT guild_id, chat_channel_id, voice_channel_id 
                FROM leaderboard_channels 
                WHERE chat_channel_id IS NOT NULL OR voice_channel_id IS NOT NULL
            """)
            
            configs = await cursor.fetchall()
            
            for guild_id, chat_channel_id, voice_channel_id in configs:
                guild = self.bot.get_guild(guild_id)
                if not guild:
                    continue
                    
                # Update chat leaderboard
                if chat_channel_id:
                    channel = guild.get_channel(chat_channel_id)
                    if channel:
                        await self.update_chat_leaderboard(guild, channel)
                        
                # Update voice leaderboard  
                if voice_channel_id:
                    channel = guild.get_channel(voice_channel_id)
                    if channel:
                        await self.update_voice_leaderboard(guild, channel)
                        
                # Update role rewards
                await self.update_role_rewards(guild)
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Track message counts for leaderboard"""
        if message.author.bot or not message.guild:
            return
            
        try:
            current_date = datetime.now(timezone.utc).date()
            
            async with aiosqlite.connect(DB_PATH) as db:
                # Get or create user record
                cursor = await db.execute("""
                    SELECT daily_count, weekly_count, monthly_count, alltime_count,
                           current_streak, longest_streak, last_activity_date,
                           last_daily_reset, last_weekly_reset, last_monthly_reset
                    FROM message_leaderboard 
                    WHERE guild_id = ? AND user_id = ?
                """, (message.guild.id, message.author.id))
                
                row = await cursor.fetchone()
                
                if row:
                    daily, weekly, monthly, alltime, current_streak, longest_streak, last_activity, last_daily, last_weekly, last_monthly = row
                    
                    # Calculate streak
                    if last_activity:
                        last_activity_date = datetime.strptime(last_activity, "%Y-%m-%d").date()
                        days_diff = (current_date - last_activity_date).days
                        
                        if days_diff == 1:
                            # Continue streak
                            current_streak += 1
                        elif days_diff == 0:
                            # Same day, no streak change
                            pass
                        else:
                            # Streak broken
                            current_streak = 1
                    else:
                        # First activity
                        current_streak = 1
                    
                    # Update longest streak
                    if current_streak > longest_streak:
                        longest_streak = current_streak
                    
                    # Reset counters if needed
                    if last_daily != str(current_date):
                        daily = 0
                    if last_weekly != str(current_date) and current_date.weekday() == 0:  # Monday reset
                        weekly = 0
                    if last_monthly != str(current_date) and current_date.day == 1:  # Monthly reset
                        monthly = 0
                        
                    # Increment counts
                    daily += 1
                    weekly += 1
                    monthly += 1
                    alltime += 1
                    
                    await db.execute("""
                        UPDATE message_leaderboard 
                        SET daily_count = ?, weekly_count = ?, monthly_count = ?, alltime_count = ?,
                            current_streak = ?, longest_streak = ?, last_activity_date = ?,
                            last_daily_reset = ?, last_weekly_reset = ?, last_monthly_reset = ?,
                            username = ?
                        WHERE guild_id = ? AND user_id = ?
                    """, (daily, weekly, monthly, alltime, current_streak, longest_streak, str(current_date),
                         str(current_date), str(current_date), str(current_date), 
                         message.author.display_name, message.guild.id, message.author.id))
                else:
                    # Create new record
                    await db.execute("""
                        INSERT INTO message_leaderboard 
                        (guild_id, user_id, username, daily_count, weekly_count, monthly_count, alltime_count,
                         current_streak, longest_streak, last_activity_date,
                         last_daily_reset, last_weekly_reset, last_monthly_reset)
                        VALUES (?, ?, ?, 1, 1, 1, 1, 1, 1, ?, ?, ?, ?)
                    """, (message.guild.id, message.author.id, message.author.display_name,
                         str(current_date), str(current_date), str(current_date), str(current_date)))
                
                await db.commit()
                
        except Exception as e:
            print(f"[LIVE_LB] Message tracking error: {e}")
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Track voice activity for leaderboard"""
        if member.bot:
            return
            
        try:
            current_time = datetime.now(timezone.utc)
            current_date = current_time.date()
            
            async with aiosqlite.connect(DB_PATH) as db:
                if before.channel is None and after.channel is not None:
                    # User joined voice - start session
                    await db.execute("""
                        INSERT OR REPLACE INTO voice_leaderboard
                        (guild_id, user_id, username, daily_minutes, weekly_minutes, monthly_minutes, alltime_minutes,
                         current_streak, longest_streak, last_activity_date,
                         last_daily_reset, last_weekly_reset, last_monthly_reset, session_start)
                        VALUES (?, ?, ?, 
                               COALESCE((SELECT daily_minutes FROM voice_leaderboard WHERE guild_id = ? AND user_id = ?), 0),
                               COALESCE((SELECT weekly_minutes FROM voice_leaderboard WHERE guild_id = ? AND user_id = ?), 0),
                               COALESCE((SELECT monthly_minutes FROM voice_leaderboard WHERE guild_id = ? AND user_id = ?), 0),
                               COALESCE((SELECT alltime_minutes FROM voice_leaderboard WHERE guild_id = ? AND user_id = ?), 0),
                               COALESCE((SELECT current_streak FROM voice_leaderboard WHERE guild_id = ? AND user_id = ?), 0),
                               COALESCE((SELECT longest_streak FROM voice_leaderboard WHERE guild_id = ? AND user_id = ?), 0),
                               COALESCE((SELECT last_activity_date FROM voice_leaderboard WHERE guild_id = ? AND user_id = ?), ?),
                               ?, ?, ?, ?)
                    """, (member.guild.id, member.id, member.display_name,
                         member.guild.id, member.id, member.guild.id, member.id,
                         member.guild.id, member.id, member.guild.id, member.id,
                         member.guild.id, member.id, member.guild.id, member.id,
                         member.guild.id, member.id, str(current_date),
                         str(current_date), str(current_date), str(current_date), current_time))
                    
                elif before.channel is not None and after.channel is None:
                    # User left voice - end session and calculate time
                    cursor = await db.execute("""
                        SELECT session_start, daily_minutes, weekly_minutes, monthly_minutes, alltime_minutes,
                               current_streak, longest_streak, last_activity_date,
                               last_daily_reset, last_weekly_reset, last_monthly_reset
                        FROM voice_leaderboard 
                        WHERE guild_id = ? AND user_id = ?
                    """, (member.guild.id, member.id))
                    
                    row = await cursor.fetchone()
                    if row and row[0]:
                        session_start = datetime.fromisoformat(row[0])
                        session_minutes = (current_time - session_start).total_seconds() / 60
                        
                        daily, weekly, monthly, alltime = row[1], row[2], row[3], row[4]
                        current_streak, longest_streak, last_activity = row[5], row[6], row[7]
                        last_daily, last_weekly, last_monthly = row[8], row[9], row[10]
                        
                        # Calculate streak
                        if last_activity:
                            last_activity_date = datetime.strptime(last_activity, "%Y-%m-%d").date()
                            days_diff = (current_date - last_activity_date).days
                            
                            if days_diff == 1:
                                # Continue streak
                                current_streak += 1
                            elif days_diff == 0:
                                # Same day, no streak change
                                pass
                            else:
                                # Streak broken
                                current_streak = 1
                        else:
                            # First activity
                            current_streak = 1
                        
                        # Update longest streak
                        if current_streak > longest_streak:
                            longest_streak = current_streak
                        
                        # Reset counters if needed
                        if last_daily != str(current_date):
                            daily = 0
                        if last_weekly != str(current_date) and current_date.weekday() == 0:
                            weekly = 0
                        if last_monthly != str(current_date) and current_date.day == 1:
                            monthly = 0
                        
                        # Add session time
                        daily += session_minutes
                        weekly += session_minutes
                        monthly += session_minutes
                        alltime += session_minutes
                        
                        await db.execute("""
                            UPDATE voice_leaderboard 
                            SET daily_minutes = ?, weekly_minutes = ?, monthly_minutes = ?, alltime_minutes = ?,
                                current_streak = ?, longest_streak = ?, last_activity_date = ?,
                                last_daily_reset = ?, last_weekly_reset = ?, last_monthly_reset = ?,
                                session_start = NULL, username = ?
                            WHERE guild_id = ? AND user_id = ?
                        """, (daily, weekly, monthly, alltime, current_streak, longest_streak, str(current_date),
                             str(current_date), str(current_date), str(current_date), 
                             member.display_name, member.guild.id, member.id))
                
                await db.commit()
                
        except Exception as e:
            print(f"[LIVE_LB] Voice tracking error: {e}")
    
    @commands.command(name="glb", help="Setup or view the global chat leaderboard with live updates", usage="glb [#channel]")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def global_leaderboard(self, ctx, channel: Optional[discord.TextChannel] = None):
        """Setup global chat leaderboard in a channel"""
        if not channel:
            # Check if this is a setup request or just showing leaderboard
            async with aiosqlite.connect(DB_PATH) as db:
                cursor = await db.execute("""
                    SELECT chat_channel_id FROM leaderboard_channels WHERE guild_id = ?
                """, (ctx.guild.id,))
                result = await cursor.fetchone()
            
            if not result or not result[0]:
                # No setup found, show setup wizard
                await self.show_setup_wizard(ctx)
                return
            else:
                # Show current leaderboard
                await self.show_chat_leaderboard(ctx)
                return
            
        # Quick setup with just channel
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT OR REPLACE INTO leaderboard_channels (guild_id, chat_channel_id)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET chat_channel_id = excluded.chat_channel_id
            """, (ctx.guild.id, channel.id))
            await db.commit()
        
        # Send initial leaderboard
        await self.update_chat_leaderboard(ctx.guild, channel)
        
        embed = discord.Embed(
            title="<a:loading:1430203733593034893> Live Chat Leaderboard Setup",
            description=f"<:clock1:1427471544409657354> **Chat leaderboard** configured in {channel.mention}\n"
                       f"<:dotdot:1428168822887546930> **Auto-updates** every 10 minutes\n"
                       f"<a:timer:1430203704048484395> **Weekly winners** get top chatter role automatically",
            color=0x00ff88
        )
        await ctx.reply(embed=embed)
    
    async def show_setup_wizard(self, ctx):
        """Show the interactive setup wizard"""
        embed = discord.Embed(
            title="<:profile:1428199763953582201> Live Leaderboard Setup",
            description="**Welcome to the Live Leaderboard System!**\n\n"
                       f"<:deezer:1428207068132933784> **Track chat & voice activity** with live updating leaderboards\n"
                       f"<:woah:1428170830042632292> **Daily streaks** to encourage consistent activity\n"
                       f"<:confetti:1428163119187890358> **Automatic role rewards** for top weekly performers\n"
                       f"<:clock1:1427471544409657354> **Real-time updates** every 10 minutes",
            color=0x006fb9
        )
        
        embed.add_field(
            name="<:question:1428173442947088486> What gets tracked:",
            value=f"<:cloud1:1427471615473750039> **Messages sent** (daily, weekly, monthly, all-time)\n"
                  f"<:ignore:1427471588915150900> **Voice time** (minutes in voice channels)\n"
                  f"<:sleep_dot:1427471567838777347> **Activity streaks** (consecutive active days)\n"
                  f"<:vanity:1428163639814389771> **Weekly rankings** with automatic role rewards",
            inline=False
        )
        
        embed.add_field(
            name="<a:yes:1431909187247673464> Features you'll get:",
            value=f"<:sleep_dot:1427471567838777347> Live updating leaderboards in your channels\n"
                  f"<:sleep_dot:1427471567838777347> Streak tracking with <:streak:1434046527025713213> emojis\n"
                  f"<:sleep_dot:1427471567838777347> Automatic top user role assignment\n"
                  f"<:sleep_dot:1427471567838777347> Personal streak checking commands",
            inline=False
        )
        
        view = LeaderboardSetupView(ctx, self)
        await ctx.reply(embed=embed, view=view)
    
    @commands.command(name="gvclb", help="Setup or view the global voice activity leaderboard", usage="gvclb [#channel]")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def global_voice_leaderboard(self, ctx, channel: Optional[discord.TextChannel] = None):
        """Setup global voice leaderboard in a channel"""
        if not channel:
            # Show current voice leaderboard
            await self.show_voice_leaderboard(ctx)
            return
            
        # Setup voice leaderboard in channel
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT OR REPLACE INTO leaderboard_channels (guild_id, voice_channel_id)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET voice_channel_id = excluded.voice_channel_id
            """, (ctx.guild.id, channel.id))
            await db.commit()
        
        # Send initial leaderboard
        await self.update_voice_leaderboard(ctx.guild, channel)
        
        embed = discord.Embed(
            title="<a:loading:1427471468157829120> Live Voice Leaderboard Setup",
            description=f"<:cloud1:1427471615473750039> **Voice leaderboard** configured in {channel.mention}\n"
                       f"<:clock1:1427471544409657354> **Auto-updates** every 10 minutes\n"
                       f"<:woah:1428170830042632292> **Weekly winners** get top voice role automatically",
            color=0x00ff88
        )
        await ctx.reply(embed=embed)
    
    @commands.command(name="glbreset", help="Reset/remove GLB setup and clear all leaderboard data", usage="glbreset", aliases=["glb-reset", "resetglb"])
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def glb_reset(self, ctx):
        """Reset GLB setup and optionally clear data"""
        # Check if GLB is even setup
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("""
                SELECT chat_channel_id, voice_channel_id, top_chatter_role_id, top_voice_role_id 
                FROM leaderboard_channels WHERE guild_id = ?
            """, (ctx.guild.id,))
            result = await cursor.fetchone()
        
        if not result or (not result[0] and not result[1]):
            embed = discord.Embed(
                title="❌ No GLB Setup Found",
                description="**Global Leaderboard is not configured** in this server.\n\n"
                           f"Use `{ctx.prefix}glb #channel` to set it up first.",
                color=0xff4444
            )
            await ctx.reply(embed=embed)
            return
        
        # Show confirmation with what will be reset
        chat_channel = ctx.guild.get_channel(result[0]) if result[0] else None
        voice_channel = ctx.guild.get_channel(result[1]) if result[1] else None
        top_chatter_role = ctx.guild.get_role(result[2]) if result[2] else None
        top_voice_role = ctx.guild.get_role(result[3]) if result[3] else None
        
        embed = discord.Embed(
            title="⚠️ Confirm GLB Reset",
            description="**This will reset the Global Leaderboard setup.**\n\n"
                       "**Current Configuration:**",
            color=0xff8800
        )
        
        if chat_channel:
            embed.add_field(
                name="📊 Chat Leaderboard",
                value=f"Channel: {chat_channel.mention}\n"
                      f"Top Role: {top_chatter_role.mention if top_chatter_role else 'None'}",
                inline=False
            )
        
        if voice_channel:
            embed.add_field(
                name="🎵 Voice Leaderboard", 
                value=f"Channel: {voice_channel.mention}\n"
                      f"Top Role: {top_voice_role.mention if top_voice_role else 'None'}",
                inline=False
            )
        
        embed.add_field(
            name="🗑️ What will be reset:",
            value="• Leaderboard channel configurations\n"
                  "• Role reward settings\n"
                  "• Auto-update messages will stop\n\n"
                  "**⚠️ User data (messages, voice time, streaks) will be kept**",
            inline=False
        )
        
        view = GLBResetView(ctx.author, ctx.guild.id, ctx.prefix)
        await ctx.reply(embed=embed, view=view)

    @commands.command(name="glbcustomize", help="Customize leaderboard embed appearance with full control", usage="glbcustomize", aliases=["glb-customize", "customizeglb"])
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def glb_customize(self, ctx):
        """Customize GLB leaderboard appearance"""
        # Check if GLB is setup
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("""
                SELECT chat_channel_id, voice_channel_id FROM leaderboard_channels WHERE guild_id = ?
            """, (ctx.guild.id,))
            result = await cursor.fetchone()
        
        if not result or (not result[0] and not result[1]):
            embed = discord.Embed(
                title="❌ No GLB Setup Found",
                description="**Global Leaderboard is not configured** in this server.\n\n"
                           f"Use `{ctx.prefix}glb #channel` to set it up first.",
                color=0xff4444
            )
            await ctx.reply(embed=embed)
            return
        
        # Show customization menu
        view = GLBCustomizeView(ctx, self)
        embed = discord.Embed(
            title="🎨 GLB Leaderboard Customization",
            description="**Customize your leaderboard appearance!**\n\n"
                       "Choose what you'd like to customize from the options below. "
                       "You can change colors, emojis, titles, descriptions, and more to match your server's style.",
            color=0x006fb9
        )
        
        embed.add_field(
            name="🎯 Available Customizations",
            value="🎨 **Colors** - Title, field colors, borders\n"
                  "😀 **Emojis** - Ranking emojis, category icons\n"
                  "📝 **Text** - Titles, descriptions, field names\n"
                  "🖼️ **Images** - Thumbnails, author icons\n"
                  "⚙️ **Layout** - Field arrangement, formatting\n"
                  "🔄 **Reset** - Return to default appearance",
            inline=False
        )
        
        await ctx.reply(embed=embed, view=view)

    async def show_chat_leaderboard(self, ctx):
        """Show chat leaderboard as reply"""
        view = LeaderboardView(ctx, self, "chat")
        embed = await self.create_chat_leaderboard_embed(ctx.guild, "weekly")
        await ctx.reply(embed=embed, view=view)
    
    async def show_voice_leaderboard(self, ctx):
        """Show voice leaderboard as reply"""
        view = LeaderboardView(ctx, self, "voice")
        embed = await self.create_voice_leaderboard_embed(ctx.guild, "weekly")
        await ctx.reply(embed=embed, view=view)
    
    async def update_chat_leaderboard(self, guild, channel):
        """Update the chat leaderboard embed in the specified channel"""
        try:
            # Get or create the leaderboard message
            messages = []
            async for message in channel.history(limit=50):
                if message.author == self.bot.user and message.embeds:
                    embed = message.embeds[0]
                    if "Chat Leaderboard" in (embed.title or ""):
                        messages.append(message)
                        break
            
            embed = await self.create_chat_leaderboard_embed(guild, "weekly")
            view = LeaderboardView(None, self, "chat", persistent=True)
            
            if messages:
                # Update existing message
                await messages[0].edit(embed=embed, view=view)
            else:
                # Send new message
                await channel.send(embed=embed, view=view)
                
        except Exception as e:
            print(f"[LIVE_LB] Error updating chat leaderboard: {e}")
    
    async def update_voice_leaderboard(self, guild, channel):
        """Update the voice leaderboard embed in the specified channel"""
        try:
            # Get or create the leaderboard message
            messages = []
            async for message in channel.history(limit=50):
                if message.author == self.bot.user and message.embeds:
                    embed = message.embeds[0]
                    if "Voice Leaderboard" in (embed.title or ""):
                        messages.append(message)
                        break
            
            embed = await self.create_voice_leaderboard_embed(guild, "weekly")
            view = LeaderboardView(None, self, "voice", persistent=True)
            
            if messages:
                # Update existing message
                await messages[0].edit(embed=embed, view=view)
            else:
                # Send new message
                await channel.send(embed=embed, view=view)
                
        except Exception as e:
            print(f"[LIVE_LB] Error updating voice leaderboard: {e}")
    
    async def get_customization_settings(self, guild_id):
        """Get customization settings for a guild, with defaults if not set"""
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("""
                SELECT chat_title, voice_title, chat_description, voice_description,
                       chat_color, voice_color, rank_emojis, chat_icon_emoji, voice_icon_emoji,
                       thumbnail_url, author_icon_url, footer_text, show_streaks, show_daily_stats, compact_mode
                FROM leaderboard_customization WHERE guild_id = ?
            """, (guild_id,))
            result = await cursor.fetchone()
        
        if not result:
            # Return default settings
            return {
                'chat_title': 'Chat Leaderboard',
                'voice_title': 'Voice Leaderboard', 
                'chat_description': 'Top chatters this week',
                'voice_description': 'Top voice users this week',
                'chat_color': '#00ff88',
                'voice_color': '#ff8800',
                'rank_emojis': ['🥇', '🥈', '🥉', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟'],
                'chat_icon_emoji': '💬',
                'voice_icon_emoji': '🎵',
                'thumbnail_url': None,
                'author_icon_url': None,
                'footer_text': 'Updates every 10 minutes',
                'show_streaks': True,
                'show_daily_stats': True,
                'compact_mode': False
            }
        
        # Parse result and return as dictionary
        rank_emojis = result[6].split(',') if result[6] else ['🥇', '🥈', '🥉', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
        
        return {
            'chat_title': result[0] or 'Chat Leaderboard',
            'voice_title': result[1] or 'Voice Leaderboard',
            'chat_description': result[2] or 'Top chatters this week', 
            'voice_description': result[3] or 'Top voice users this week',
            'chat_color': result[4] or '#00ff88',
            'voice_color': result[5] or '#ff8800',
            'rank_emojis': rank_emojis,
            'chat_icon_emoji': result[7] or '💬',
            'voice_icon_emoji': result[8] or '🎵',
            'thumbnail_url': result[9],
            'author_icon_url': result[10],
            'footer_text': result[11] or 'Updates every 10 minutes',
            'show_streaks': bool(result[12]) if result[12] is not None else True,
            'show_daily_stats': bool(result[13]) if result[13] is not None else True,
            'compact_mode': bool(result[14]) if result[14] is not None else False
        }
    
    async def create_chat_leaderboard_embed(self, guild, timeframe="weekly"):
        """Create chat leaderboard embed for specified timeframe"""
        # Get customization settings
        settings = await self.get_customization_settings(guild.id)
        
        timeframe_column = {
            "daily": "daily_count",
            "weekly": "weekly_count", 
            "monthly": "monthly_count",
            "alltime": "alltime_count"
        }
        
        column = timeframe_column.get(timeframe, "weekly_count")
        
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(f"""
                SELECT user_id, username, {column}, current_streak
                FROM message_leaderboard 
                WHERE guild_id = ? AND {column} > 0
                ORDER BY {column} DESC
                LIMIT 10
            """, (guild.id,))
            
            results = await cursor.fetchall()
        
        # Timeframe icons
        timeframe_icons = {
            "daily": "📅",
            "weekly": "📊",
            "monthly": "📈",
            "alltime": "🏆"
        }
        timeframe_icon = timeframe_icons.get(timeframe, "📊")
        
        # Parse color
        try:
            color = int(settings['chat_color'].replace('#', ''), 16)
        except:
            color = 0x00ff88  # Default green
        
        embed = discord.Embed(
            title=f"{settings['chat_icon_emoji']} **{settings['chat_title']}**",
            description=f"{timeframe_icon} **{timeframe.title()} Leaderboard**\n{settings['chat_description']}",
            color=color,
            timestamp=datetime.now(timezone.utc)
        )
        
        # Add custom thumbnail if set
        if settings['thumbnail_url']:
            embed.set_thumbnail(url=settings['thumbnail_url'])
        
        # Add custom author icon if set
        if settings['author_icon_url']:
            embed.set_author(name=guild.name, icon_url=settings['author_icon_url'])
        
        if results:
            leaderboard_text = ""
            for i, (user_id, username, count, streak) in enumerate(results, 1):
                # Use custom ranking emojis
                emoji = settings['rank_emojis'][i-1] if i <= len(settings['rank_emojis']) else f"`{i:2d}.`"
                
                # Show streaks if enabled
                streak_indicator = ""
                if settings['show_streaks'] and streak >= 3:
                    streak_indicator = f" <:streak:1434046527025713213>`{streak}`"
                
                # Format message count with proper spacing
                count_formatted = f"{count:,}".rjust(6)
                
                # Create clean, aligned format
                if settings['compact_mode']:
                    leaderboard_text += f"{emoji} `{username[:20]:20}` **{count:,}**{streak_indicator}\n"
                else:
                    leaderboard_text += f"{emoji} **{username}** – `{count:,}` messages{streak_indicator}\n"
            
            embed.add_field(
                name=f"{settings['chat_icon_emoji']} Top Chatters",
                value=leaderboard_text,
                inline=False
            )
        else:
            embed.add_field(
                name=f"{settings['chat_icon_emoji']} Top Chatters", 
                value="> No chat activity recorded yet! Start chatting to appear on the leaderboard.",
                inline=False
            )
        
        # Use custom footer text
        embed.set_footer(
            text=f"{settings['footer_text']} • {timeframe.title()}",
            icon_url=guild.icon.url if guild.icon else None
        )
        
        return embed
    
    async def create_voice_leaderboard_embed(self, guild, timeframe="weekly"):
        """Create voice leaderboard embed for specified timeframe"""
        # Get customization settings
        settings = await self.get_customization_settings(guild.id)
        
        timeframe_column = {
            "daily": "daily_minutes",
            "weekly": "weekly_minutes",
            "monthly": "monthly_minutes", 
            "alltime": "alltime_minutes"
        }
        
        column = timeframe_column.get(timeframe, "weekly_minutes")
        
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(f"""
                SELECT user_id, username, {column}, current_streak
                FROM voice_leaderboard 
                WHERE guild_id = ? AND {column} > 0
                ORDER BY {column} DESC
                LIMIT 10
            """, (guild.id,))
            
            results = await cursor.fetchall()
        
        # Timeframe icons
        timeframe_icons = {
            "daily": "📅",
            "weekly": "📊",
            "monthly": "📈",
            "alltime": "🏆"
        }
        timeframe_icon = timeframe_icons.get(timeframe, "📊")
        
        # Parse color
        try:
            color = int(settings['voice_color'].replace('#', ''), 16)
        except:
            color = 0xff6b00  # Default orange
        
        embed = discord.Embed(
            title=f"{settings['voice_icon_emoji']} **{settings['voice_title']}**",
            description=f"{timeframe_icon} **{timeframe.title()} Leaderboard**\n{settings['voice_description']}",
            color=color,
            timestamp=datetime.now(timezone.utc)
        )
        
        # Add custom thumbnail if set
        if settings['thumbnail_url']:
            embed.set_thumbnail(url=settings['thumbnail_url'])
        
        # Add custom author icon if set
        if settings['author_icon_url']:
            embed.set_author(name=guild.name, icon_url=settings['author_icon_url'])
        
        if results:
            leaderboard_text = ""
            for i, (user_id, username, minutes, streak) in enumerate(results, 1):
                hours = minutes / 60
                
                # Use custom ranking emojis
                emoji = settings['rank_emojis'][i-1] if i <= len(settings['rank_emojis']) else f"`{i:2d}.`"
                
                # Show streaks if enabled
                streak_indicator = ""
                if settings['show_streaks'] and streak >= 3:
                    streak_indicator = f" <:streak:1434046527025713213>`{streak}`"
                
                # Format time display
                if hours >= 1:
                    time_display = f"{hours:.1f}h"
                else:
                    time_display = f"{minutes}m"
                
                # Create clean, aligned format
                if settings['compact_mode']:
                    leaderboard_text += f"{emoji} `{username[:20]:20}` **{time_display}**{streak_indicator}\n"
                else:
                    leaderboard_text += f"{emoji} **{username}** – `{time_display}` voice time{streak_indicator}\n"
            
            embed.add_field(
                name=f"{settings['voice_icon_emoji']} Top Voice Users",
                value=leaderboard_text,
                inline=False
            )
        else:
            embed.add_field(
                name=f"{settings['voice_icon_emoji']} Top Voice Users", 
                value="> No voice activity recorded yet! Join a voice channel to appear on the leaderboard.",
                inline=False
            )
        
        # Use custom footer text
        embed.set_footer(
            text=f"{settings['footer_text']} • {timeframe.title()}",
            icon_url=guild.icon.url if guild.icon else None
        )
        
        return embed
    
    async def update_role_rewards(self, guild):
        """Update weekly role rewards for top chatters and voice users"""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                # Get role IDs
                cursor = await db.execute("""
                    SELECT top_chatter_role_id, top_voice_role_id 
                    FROM leaderboard_channels 
                    WHERE guild_id = ?
                """, (guild.id,))
                
                config = await cursor.fetchone()
                if not config:
                    return
                
                top_chatter_role_id, top_voice_role_id = config
                
                # Update top chatter role
                if top_chatter_role_id:
                    role = guild.get_role(top_chatter_role_id)
                    if role:
                        # Get weekly top chatter
                        cursor = await db.execute("""
                            SELECT user_id FROM message_leaderboard 
                            WHERE guild_id = ? AND weekly_count > 0
                            ORDER BY weekly_count DESC LIMIT 1
                        """, (guild.id,))
                        
                        result = await cursor.fetchone()
                        if result:
                            top_user = guild.get_member(result[0])
                            if top_user:
                                # Remove role from all members
                                for member in role.members:
                                    if member != top_user:
                                        await member.remove_roles(role, reason="No longer top chatter")
                                
                                # Add role to top user
                                if role not in top_user.roles:
                                    await top_user.add_roles(role, reason="Weekly top chatter")
                
                # Update top voice role
                if top_voice_role_id:
                    role = guild.get_role(top_voice_role_id)
                    if role:
                        # Get weekly top voice user
                        cursor = await db.execute("""
                            SELECT user_id FROM voice_leaderboard 
                            WHERE guild_id = ? AND weekly_minutes > 0
                            ORDER BY weekly_minutes DESC LIMIT 1
                        """, (guild.id,))
                        
                        result = await cursor.fetchone()
                        if result:
                            top_user = guild.get_member(result[0])
                            if top_user:
                                # Remove role from all members
                                for member in role.members:
                                    if member != top_user:
                                        await member.remove_roles(role, reason="No longer top voice user")
                                
                                # Add role to top user
                                if role not in top_user.roles:
                                    await top_user.add_roles(role, reason="Weekly top voice user")
                                    
        except Exception as e:
            print(f"[LIVE_LB] Role reward error: {e}")
    
    @commands.command(name="streaks", help="View current activity streaks leaderboard (daily, weekly, monthly)", usage="streaks")
    @blacklist_check()
    @ignore_check()
    async def streaks_leaderboard(self, ctx):
        """Show streak leaderboards for both chat and voice"""
        await self.show_streaks_leaderboard(ctx)
    
    @commands.command(name="mystreak", help="View your personal activity streaks and statistics", usage="mystreak [@user]")
    @blacklist_check()
    @ignore_check()
    async def my_streak(self, ctx, user: Optional[discord.Member] = None):
        """Show personal streak information"""
        target_user = user or ctx.author
        
        async with aiosqlite.connect(DB_PATH) as db:
            # Get chat streak
            cursor = await db.execute("""
                SELECT current_streak, longest_streak, last_activity_date
                FROM message_leaderboard 
                WHERE guild_id = ? AND user_id = ?
            """, (ctx.guild.id, target_user.id))
            
            chat_data = await cursor.fetchone()
            chat_current = chat_data[0] if chat_data else 0
            chat_longest = chat_data[1] if chat_data else 0
            chat_last = chat_data[2] if chat_data else "Never"
            
            # Get voice streak
            cursor = await db.execute("""
                SELECT current_streak, longest_streak, last_activity_date
                FROM voice_leaderboard 
                WHERE guild_id = ? AND user_id = ?
            """, (ctx.guild.id, target_user.id))
            
            voice_data = await cursor.fetchone()
            voice_current = voice_data[0] if voice_data else 0
            voice_longest = voice_data[1] if voice_data else 0
            voice_last = voice_data[2] if voice_data else "Never"
        
        embed = discord.Embed(
            title=f"<:feast_time:1400143469892210757> {target_user.display_name}'s Activity Streaks",
            description="Daily consecutive activity tracking",
            color=0xff4500,
            timestamp=datetime.now(timezone.utc)
        )
        
        embed.add_field(
            name="💬 Chat Streaks",
            value=f"**Current:** {chat_current} days <:streak:1434046527025713213>\n"
                  f"**Best:** {chat_longest} days 🏆\n"
                  f"**Last Active:** {chat_last}",
            inline=True
        )
        
        embed.add_field(
            name="🎤 Voice Streaks", 
            value=f"**Current:** {voice_current} days <:streak:1434046527025713213>\n"
                  f"**Best:** {voice_longest} days 🏆\n"
                  f"**Last Active:** {voice_last}",
            inline=True
        )
        
        # Streak status
        total_current = chat_current + voice_current
        if total_current >= 30:
            status = "<:streak:1434046527025713213> ON FIRE! <:streak:1434046527025713213>"
        elif total_current >= 14:
            status = "⚡ STREAK MASTER!"
        elif total_current >= 7:
            status = "🌟 Getting Hot!"
        elif total_current >= 3:
            status = "📈 Building Up"
        else:
            status = "🌱 Just Started"
        
        embed.add_field(
            name="🎯 Streak Status",
            value=status,
            inline=False
        )
        
        embed.set_thumbnail(url=target_user.display_avatar.url)
        await ctx.reply(embed=embed)
    
    async def show_streaks_leaderboard(self, ctx):
        """Show streak leaderboard"""
        view = StreakLeaderboardView(ctx, self)
        embed = await self.create_streak_leaderboard_embed(ctx.guild, "chat")
        await ctx.reply(embed=embed, view=view)
    
    async def create_streak_leaderboard_embed(self, guild, streak_type="chat"):
        """Create streak leaderboard embed"""
        table = "message_leaderboard" if streak_type == "chat" else "voice_leaderboard"
        
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(f"""
                SELECT user_id, username, current_streak, longest_streak
                FROM {table} 
                WHERE guild_id = ? AND current_streak > 0
                ORDER BY current_streak DESC, longest_streak DESC
                LIMIT 10
            """, (guild.id,))
            
            results = await cursor.fetchall()
            
            # Also get longest streaks data
            longest_cursor = await db.execute(f"""
                SELECT username, longest_streak
                FROM {table} 
                WHERE guild_id = ? AND longest_streak > 0
                ORDER BY longest_streak DESC
                LIMIT 3
            """, (guild.id,))
            
            longest_results = await longest_cursor.fetchall()
        
        emoji = "<:feast_plus:1400142875483836547>" if streak_type == "chat" else "<:feast_mod:1400136216497623130>"
        title = f"{emoji} Current {streak_type.title()} Streaks"
        
        embed = discord.Embed(
            title=f"<:feast_time:1400143469892210757> {title} Leaderboard",
            description=f"<:feast_plus:1400142875483836547> **Top 10 Streak Holders** in {guild.name}\n<:feast_time:1400143469892210757> *Consecutive daily activity*",
            color=0xff4500,
            timestamp=datetime.now(timezone.utc)
        )
        
        if results:
            leaderboard_text = ""
            for i, (user_id, username, current_streak, longest_streak) in enumerate(results, 1):
                # Streak emojis based on streak length
                if current_streak >= 30:
                    fire = "<:streak:1434046527025713213><:streak:1434046527025713213><:streak:1434046527025713213>"
                elif current_streak >= 14:
                    fire = "<:streak:1434046527025713213><:streak:1434046527025713213>"
                elif current_streak >= 7:
                    fire = "<:streak:1434046527025713213>"
                else:
                    fire = "<:streak:1434046527025713213>"
                
                emoji = "<:sleep1:1434046300181237820>" if i == 1 else "<:sleep2:1434046416312864810>" if i == 2 else "<:sleep3:1434046379176755332>" if i == 3 else "<:sleep4:1434046395504922728>" if i == 4 else "<:sleep5:1434046405995004034>" if i == 5 else "<:6_:1434046281474510909>" if i == 6 else "<:7_:1434046047046471722>" if i == 7 else "<:8_:1434046065287626752>" if i == 8 else "<:9_:1434046084467916831>" if i == 9 else "<:10:1434046290857033830>" if i == 10 else f"`{i:2d}.`"
                leaderboard_text += f"{emoji} **{username}** - {current_streak} days {fire}\n"
            
            embed.add_field(
                name="<:clock1:1427471544409657354> Current Streaks",
                value=leaderboard_text,
                inline=False
            )
            
            # Show longest streaks too (data already fetched from database)
            if longest_results:
                longest_text = ""
                for i, (username, longest_streak) in enumerate(longest_results, 1):
                    medal = "<:sleep1:1434046300181237820>" if i == 1 else "<:sleep2:1434046416312864810>" if i == 2 else "<:sleep3:1434046379176755332>"
                    longest_text += f"{medal} **{username}** - {longest_streak} days\n"
                
                embed.add_field(
                    name="💡 All-Time Best Streaks",
                    value=longest_text,
                    inline=True
                )
        else:
            embed.add_field(
                name="<:woah:1428170830042632292> Current Streaks",
                value="No active streaks yet! Start your streak today!",
                inline=False
            )
        
        embed.set_footer(
            text="💡 Tip: Stay active daily to build your streak!",
            icon_url=guild.icon.url if guild.icon else None
        )
        
        return embed
    
    @commands.command(name="lbroles", help="Configure top user roles for leaderboards")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def leaderboard_roles(self, ctx, chat_role: Optional[discord.Role] = None, voice_role: Optional[discord.Role] = None):
        """Configure roles for top leaderboard users"""
        async with aiosqlite.connect(DB_PATH) as db:
            current_cursor = await db.execute("""
                SELECT top_chatter_role_id, top_voice_role_id 
                FROM leaderboard_channels 
                WHERE guild_id = ?
            """, (ctx.guild.id,))
            
            current = await current_cursor.fetchone()
            current_chat_role_id = current[0] if current else None
            current_voice_role_id = current[1] if current else None
            
            # Update roles
            new_chat_role_id = chat_role.id if chat_role else current_chat_role_id
            new_voice_role_id = voice_role.id if voice_role else current_voice_role_id
            
            await db.execute("""
                INSERT OR REPLACE INTO leaderboard_channels 
                (guild_id, top_chatter_role_id, top_voice_role_id)
                VALUES (?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET 
                top_chatter_role_id = excluded.top_chatter_role_id,
                top_voice_role_id = excluded.top_voice_role_id
            """, (ctx.guild.id, new_chat_role_id, new_voice_role_id))
            
            await db.commit()
        
        embed = discord.Embed(
            title="🏆 Leaderboard Roles Configured",
            description="Role rewards for weekly leaderboard winners:",
            color=0x00ff88
        )
        
        if new_chat_role_id:
            role = ctx.guild.get_role(new_chat_role_id)
            embed.add_field(
                name="💬 Top Chatter Role",
                value=role.mention if role else "Role not found",
                inline=True
            )
        
        if new_voice_role_id:
            role = ctx.guild.get_role(new_voice_role_id)
            embed.add_field(
                name="🎤 Top Voice Role", 
                value=role.mention if role else "Role not found",
                inline=True
            )
        
        embed.add_field(
            name="ℹ️ How it works",
            value="• Roles automatically assigned to weekly #1 users\n• Updated every 10 minutes\n• Previous winners lose the role when someone new takes #1",
            inline=False
        )
        
        await ctx.reply(embed=embed)

    @commands.command(name="glbhelp", help="View detailed help for GLB system with all commands", usage="glbhelp", aliases=["glb-help", "helpglb"])
    @blacklist_check()
    @ignore_check()
    async def glb_help(self, ctx):
        """Show comprehensive GLB help with pagination"""
        view = GLBHelpView(ctx)
        view.update_buttons()  # Set initial button states
        await ctx.send(embed=view.pages[0], view=view)

    def help_custom(self):
        return "🏆", "Global Leaderboard (GLB)", "Live chat & voice leaderboards with role rewards"

class GLBHelpView(discord.ui.View):
    """Paginated help view for GLB system"""
    def __init__(self, ctx):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.current_page = 0
        self.pages = self.create_pages()
        self.total_pages = len(self.pages)
        
    def create_pages(self):
        """Create all help pages"""
        pages = []
        
        # Page 1: Overview & Setup
        embed = discord.Embed(
            title="🏆 Global Leaderboard (GLB) System",
            description="**Live tracking of chat and voice activity with automatic role rewards**\n\n"
                       "Track your server's most active members with real-time leaderboards that update every 10 minutes!",
            color=0x00ff88
        )
        
        embed.add_field(
            name="<:sleep_dot:1427471567838777347> **Quick Start**",
            value="<:sleep_dot:1427471567838777347> `glb #channel` - Setup chat leaderboard\n"
                  "<:sleep_dot:1427471567838777347> `gvclb #channel` - Setup voice leaderboard\n"
                  "<:sleep_dot:1427471567838777347> `glbcustomize` - Full customization menu",
            inline=False
        )
        
        embed.add_field(
            name="🎯 **Key Features**",
            value="• Real-time activity tracking\n"
                  "• Daily, weekly, monthly, & all-time stats\n"
                  "• Automatic role rewards for top users\n"
                  "• Streak tracking & achievements\n"
                  "• Full embed customization",
            inline=False
        )
        
        embed.set_footer(text=f"• Help page 1/{5} | Requested by: {self.ctx.author.display_name}",
                        icon_url=self.ctx.bot.user.avatar.url if self.ctx.bot.user.avatar else None)
        pages.append(embed)
        
        # Page 2: Setup & Configuration
        embed = discord.Embed(
            title="<a:gear:1430203750324240516> Setup & Configuration",
            description="**Get your leaderboards up and running**",
            color=0x00ff88
        )
        
        embed.add_field(
            name="<:bot:1428163130663375029> glb [#channel]",
            value="Setup chat leaderboard in specified channel.\n"
                  "**Example:** `glb #leaderboard`\n"
                  "**Permissions:** Administrator",
            inline=False
        )
        
        embed.add_field(
            name="<:bot:1428163130663375029> gvclb [#channel]",
            value="Setup voice activity leaderboard.\n"
                  "**Example:** `gvclb #voice-stats`\n"
                  "**Permissions:** Administrator",
            inline=False
        )
        
        embed.add_field(
            name="<:bot:1428163130663375029> lbroles [chat_role] [voice_role]",
            value="Configure automatic role rewards for top users.\n"
                  "**Example:** `lbroles @Top Chatter @Top Voice`\n"
                  "**Permissions:** Administrator",
            inline=False
        )
        
        embed.add_field(
            name="<:bot:1428163130663375029> glbreset",
            value="Reset leaderboard configuration (keeps user data).\n"
                  "**Example:** `glbreset`\n"
                  "**Aliases:** glb-reset, resetglb",
            inline=False
        )
        
        embed.set_footer(text=f"• Help page 2/{5} | Requested by: {self.ctx.author.display_name}",
                        icon_url=self.ctx.bot.user.avatar.url if self.ctx.bot.user.avatar else None)
        pages.append(embed)
        
        # Page 3: Customization
        embed = discord.Embed(
            title="🎨 Leaderboard Customization",
            description="**Personalize your leaderboards to match your server**",
            color=0x00ff88
        )
        
        embed.add_field(
            name="<:bot:1428163130663375029> glbcustomize",
            value="Open full customization menu with options for:\n"
                  "• **Colors & Theme** - Custom hex colors\n"
                  "• **Emojis & Icons** - Ranking emojis, category icons\n"
                  "• **Text & Titles** - Custom titles, descriptions, footer\n"
                  "• **Images & Media** - Thumbnails, author icons\n"
                  "• **Layout & Format** - Display options, compact mode\n"
                  "**Aliases:** glb-customize, customizeglb",
            inline=False
        )
        
        embed.add_field(
            name="💡 **Customization Examples**",
            value="• Change embed colors to match server theme\n"
                  "• Add custom emojis for 1st/2nd/3rd place\n"
                  "• Set custom titles like 'Top Warriors'\n"
                  "• Add server logo as thumbnail\n"
                  "• Toggle streaks and daily stats display",
            inline=False
        )
        
        embed.set_footer(text=f"• Help page 3/{5} | Requested by: {self.ctx.author.display_name}",
                        icon_url=self.ctx.bot.user.avatar.url if self.ctx.bot.user.avatar else None)
        pages.append(embed)
        
        # Page 4: Streaks & Personal Stats
        embed = discord.Embed(
            title="🔥 Streaks & Personal Stats",
            description="**Track activity streaks and view personal progress**",
            color=0x00ff88
        )
        
        embed.add_field(
            name="<:bot:1428163130663375029> streaks",
            value="View server-wide streak leaderboards.\n"
                  "Shows top 10 users with current active streaks.\n"
                  "**Example:** `streaks`",
            inline=False
        )
        
        embed.add_field(
            name="<:bot:1428163130663375029> mystreak [@user]",
            value="Check your personal activity streaks.\n"
                  "Shows current streak, longest streak, and last activity.\n"
                  "**Example:** `mystreak` or `mystreak @User`",
            inline=False
        )
        
        embed.add_field(
            name="📊 **How Streaks Work**",
            value="• Streaks track consecutive days of activity\n"
                  "• Chat streaks: Send at least 1 message per day\n"
                  "• Voice streaks: Be in voice for at least 1 minute per day\n"
                  "• Streaks reset if you miss a day\n"
                  "• Best streak is saved permanently",
            inline=False
        )
        
        embed.set_footer(text=f"• Help page 4/{5} | Requested by: {self.ctx.author.display_name}",
                        icon_url=self.ctx.bot.user.avatar.url if self.ctx.bot.user.avatar else None)
        pages.append(embed)
        
        # Page 5: How It Works & Tips
        embed = discord.Embed(
            title="ℹ️ How GLB Works & Pro Tips",
            description="**Understanding the leaderboard system**",
            color=0x00ff88
        )
        
        embed.add_field(
            name="🔄 **Automatic Updates**",
            value="• Leaderboards update every 10 minutes\n"
                  "• Real-time activity tracking\n"
                  "• Stats persist across bot restarts\n"
                  "• Weekly stats reset on Mondays",
            inline=False
        )
        
        embed.add_field(
            name="🏆 **Role Rewards**",
            value="• Top weekly users get configured roles\n"
                  "• Roles automatically removed when someone else takes #1\n"
                  "• Separate roles for chat and voice\n"
                  "• Updates every 10 minutes with leaderboard",
            inline=False
        )
        
        embed.add_field(
            name="📈 **Timeframes Available**",
            value="• **Daily** - Today's activity\n"
                  "• **Weekly** - This week (default)\n"
                  "• **Monthly** - This month\n"
                  "• **All-Time** - Total since tracking started\n"
                  "*Use buttons on leaderboard embeds to switch*",
            inline=False
        )
        
        embed.add_field(
            name="💡 **Pro Tips**",
            value="• Use `glbcustomize` to make leaderboards unique\n"
                  "• Set role rewards to motivate activity\n"
                  "• Check `mystreak` daily to maintain streaks\n"
                  "• Pin leaderboard channels for easy access",
            inline=False
        )
        
        embed.set_footer(text=f"• Help page 5/{5} | Requested by: {self.ctx.author.display_name}",
                        icon_url=self.ctx.bot.user.avatar.url if self.ctx.bot.user.avatar else None)
        pages.append(embed)
        
        return pages
    
    def update_buttons(self):
        """Update button states based on current page"""
        self.home_btn.disabled = self.current_page == 0
        self.prev_btn.disabled = self.current_page == 0
        self.next_btn.disabled = self.current_page == self.total_pages - 1
        self.last_btn.disabled = self.current_page == self.total_pages - 1
        
    @discord.ui.button(emoji="<:feast_prev:1400142835914637524>", style=discord.ButtonStyle.secondary)
    async def home_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("You must run this command to interact with it.", ephemeral=True)
        
        self.current_page = 0
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    @discord.ui.button(emoji="<:feast_piche:1400142845402284102>", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("You must run this command to interact with it.", ephemeral=True)
        
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    @discord.ui.button(emoji="<:feast_delete:1400140670659989524>", style=discord.ButtonStyle.danger)
    async def delete_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("You must run this command to interact with it.", ephemeral=True)
        
        await interaction.response.defer()
        await interaction.delete_original_response()
    
    @discord.ui.button(emoji="<:feast_age:1400142030205878274>", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("You must run this command to interact with it.", ephemeral=True)
        
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    @discord.ui.button(emoji="<:feast_next:1400141978095583322>", style=discord.ButtonStyle.secondary)
    async def last_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("You must run this command to interact with it.", ephemeral=True)
        
        self.current_page = self.total_pages - 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    async def on_timeout(self):
        """Disable all buttons on timeout"""
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

class LeaderboardView(discord.ui.View):
    """Interactive view for leaderboard embeds with timeframe buttons"""
    
    def __init__(self, ctx, cog, lb_type, persistent=False):
        super().__init__(timeout=300 if not persistent else None)
        self.ctx = ctx
        self.cog = cog
        self.lb_type = lb_type  # "chat" or "voice"
        self.current_timeframe = "weekly"
        
        if persistent:
            self.timeout = None
    
    @discord.ui.button(emoji="📅", label="Daily", style=discord.ButtonStyle.secondary)
    async def daily_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_timeframe(interaction, "daily")
    
    @discord.ui.button(emoji="📊", label="Weekly", style=discord.ButtonStyle.primary)
    async def weekly_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_timeframe(interaction, "weekly")
    
    @discord.ui.button(emoji="📈", label="Monthly", style=discord.ButtonStyle.secondary)
    async def monthly_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_timeframe(interaction, "monthly")
    
    @discord.ui.button(emoji="🏆", label="All-Time", style=discord.ButtonStyle.secondary)
    async def alltime_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_timeframe(interaction, "alltime")
    
    async def update_timeframe(self, interaction: discord.Interaction, timeframe: str):
        """Update the leaderboard to show different timeframe"""
        try:
            self.current_timeframe = timeframe
            
            # Update button styles
            for item in self.children:
                if isinstance(item, discord.ui.Button) and hasattr(item, 'label') and item.label:
                    if item.label.lower() == timeframe:
                        item.style = discord.ButtonStyle.primary
                    else:
                        item.style = discord.ButtonStyle.secondary
            
            # Create new embed
            if self.lb_type == "chat":
                embed = await self.cog.create_chat_leaderboard_embed(interaction.guild, timeframe)
            else:
                embed = await self.cog.create_voice_leaderboard_embed(interaction.guild, timeframe)
            
            await interaction.response.edit_message(embed=embed, view=self)
            
        except Exception as e:
            await interaction.response.send_message(f"Error updating leaderboard: {e}", ephemeral=True)

class StreakLeaderboardView(discord.ui.View):
    """Interactive view for streak leaderboards"""
    
    def __init__(self, ctx, cog):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.cog = cog
        self.current_type = "chat"
    
    @discord.ui.button(emoji="💬", label="Chat Streaks", style=discord.ButtonStyle.primary)
    async def chat_streaks_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_streak_type(interaction, "chat")
    
    @discord.ui.button(emoji="<:music:1427471622335500439>", label="Voice Streaks", style=discord.ButtonStyle.secondary)
    async def voice_streaks_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_streak_type(interaction, "voice")
    
    async def update_streak_type(self, interaction: discord.Interaction, streak_type: str):
        """Update the streak leaderboard to show different type"""
        try:
            self.current_type = streak_type
            
            # Update button styles
            for item in self.children:
                if isinstance(item, discord.ui.Button) and hasattr(item, 'label') and item.label:
                    if ("Chat" in item.label and streak_type == "chat") or ("Voice" in item.label and streak_type == "voice"):
                        item.style = discord.ButtonStyle.primary
                    else:
                        item.style = discord.ButtonStyle.secondary
            
            # Create new embed
            embed = await self.cog.create_streak_leaderboard_embed(interaction.guild, streak_type)
            
            await interaction.response.edit_message(embed=embed, view=self)
            
        except Exception as e:
            await interaction.response.send_message(f"Error updating streak leaderboard: {e}", ephemeral=True)

class LeaderboardSetupView(discord.ui.View):
    """Interactive setup view for live leaderboard"""
    
    def __init__(self, ctx, lb_cog):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.lb_cog = lb_cog
        self.setup_data = {}
        
    async def interaction_check(self, interaction):
        return interaction.user == self.ctx.author
        
    @discord.ui.button(label="Start Setup", emoji="<a:gear:1430203750324240516>", style=discord.ButtonStyle.green)
    async def start_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Start the interactive setup process"""
        await interaction.response.defer()
        
        # Step 1: Channel Selection
        embed = discord.Embed(
            title="<a:gear:1430203750324240516> Live Leaderboard Setup - Step 1",
            description="**Choose a channel for the chat leaderboard**\n\n"
                       f"<:sleep_dot:1427471567838777347> Select a channel where the live chat leaderboard will be displayed\n"
                       f"<:sleep_dot:1427471567838777347> Make sure the bot has permissions to send messages there",
            color=0x006fb9
        )
        
        select_menu = ChannelSelectMenu(self.ctx, self.lb_cog, self)
        view = discord.ui.View()
        view.add_item(select_menu)
        
        await interaction.edit_original_response(embed=embed, view=view)
        
    @discord.ui.button(label="Cancel", emoji="<:stop:1427471993984389180>", style=discord.ButtonStyle.red)
    async def cancel_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel the setup process"""
        embed = discord.Embed(
            title="<:stop:1427471993984389180> Setup Cancelled",
            description="Leaderboard setup has been cancelled.",
            color=0xff6b6b
        )
        await interaction.response.edit_message(embed=embed, view=None)

class ChannelSelectMenu(discord.ui.ChannelSelect):
    """Channel selection dropdown for setup"""
    
    def __init__(self, ctx, lb_cog, setup_view):
        super().__init__(
            placeholder="Select a channel for the chat leaderboard...",
            channel_types=[discord.ChannelType.text],
            max_values=1
        )
        self.ctx = ctx
        self.lb_cog = lb_cog
        self.setup_view = setup_view
        
    async def callback(self, interaction: discord.Interaction):
        """Handle channel selection"""
        channel = self.values[0]
        self.setup_view.setup_data['chat_channel'] = channel
        
        # Step 2: Voice Channel Selection
        embed = discord.Embed(
            title="<a:gear:1430203750324240516> Live Leaderboard Setup - Step 2",
            description="**Choose a channel for the voice leaderboard (Optional)**\n\n"
                       f"{':checkmark:'} Chat channel selected: {channel.mention}\n\n"
                       f"{':plus:'} Select a channel for the voice leaderboard\n"
                       f"{':skip:'} Or skip this step if you only want chat leaderboard",
            color=0x006fb9
        )
        
        view = VoiceChannelSetupView(self.ctx, self.lb_cog, self.setup_view)
        await interaction.response.edit_message(embed=embed, view=view)

class VoiceChannelSetupView(discord.ui.View):
    """Voice channel setup view"""
    
    def __init__(self, ctx, lb_cog, setup_view):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.lb_cog = lb_cog
        self.setup_view = setup_view
        
    async def interaction_check(self, interaction):
        return interaction.user == self.ctx.author
        
    @discord.ui.button(label="Add Voice Channel", emoji="<:plusu:1428164526884257852>", style=discord.ButtonStyle.green)
    async def add_voice_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Add voice channel selection"""
        embed = discord.Embed(
            title="<a:gear:1430203750324240516> Select Voice Leaderboard Channel",
            description="Choose a channel for the voice leaderboard:",
            color=0x006fb9
        )
        
        select_menu = VoiceChannelSelectMenu(self.ctx, self.lb_cog, self.setup_view)
        view = discord.ui.View()
        view.add_item(select_menu)
        
        await interaction.response.edit_message(embed=embed, view=view)
        
    @discord.ui.button(label="Skip Voice Channel", emoji="⏭️", style=discord.ButtonStyle.gray)
    async def skip_voice_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Skip voice channel setup and proceed to roles"""
        await self.proceed_to_roles(interaction)
        
    async def proceed_to_roles(self, interaction):
        """Proceed to role configuration"""
        # Step 3: Role Configuration
        embed = discord.Embed(
            title="<a:gear:1430203750324240516> Live Leaderboard Setup - Step 3",
            description="**Configure reward roles (Optional)**\n\n"
                       f"{':plus:'} Choose roles to reward top performers\n"
                       f"{':warning:'} Top weekly chat/voice users will get these roles automatically\n"
                       f"{':skip:'} You can skip this and configure roles later",
            color=0x006fb9
        )
        
        view = RoleSetupView(self.ctx, self.lb_cog, self.setup_view)
        await interaction.response.edit_message(embed=embed, view=view)

class VoiceChannelSelectMenu(discord.ui.ChannelSelect):
    """Voice channel selection dropdown"""
    
    def __init__(self, ctx, lb_cog, setup_view):
        super().__init__(
            placeholder="Select a channel for the voice leaderboard...",
            channel_types=[discord.ChannelType.text],
            max_values=1
        )
        self.ctx = ctx
        self.lb_cog = lb_cog
        self.setup_view = setup_view
        
    async def callback(self, interaction: discord.Interaction):
        """Handle voice channel selection"""
        channel = self.values[0]
        self.setup_view.setup_data['voice_channel'] = channel
        
        view = VoiceChannelSetupView(self.ctx, self.lb_cog, self.setup_view)
        await view.proceed_to_roles(interaction)

class RoleSetupView(discord.ui.View):
    """Role configuration view"""
    
    def __init__(self, ctx, lb_cog, setup_view):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.lb_cog = lb_cog
        self.setup_view = setup_view
        
    async def interaction_check(self, interaction):
        return interaction.user == self.ctx.author
        
    @discord.ui.button(label="Add Chat Role", emoji="<:plusu:1428164526884257852>", style=discord.ButtonStyle.green)
    async def add_chat_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Add chat role selection"""
        embed = discord.Embed(
            title="<a:gear:1430203750324240516> Select Top Chatter Role",
            description="Choose a role for the top weekly chatter:",
            color=0x006fb9
        )
        
        select_menu = ChatRoleSelectMenu(self.ctx, self.lb_cog, self.setup_view)
        view = discord.ui.View()
        view.add_item(select_menu)
        
        await interaction.response.edit_message(embed=embed, view=view)
        
    @discord.ui.button(label="Add Voice Role", emoji="<:plusu:1428164526884257852>", style=discord.ButtonStyle.blurple)
    async def add_voice_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Add voice role selection"""
        embed = discord.Embed(
            title="<a:gear:1430203750324240516> Select Top Voice Role",
            description="Choose a role for the top weekly voice user:",
            color=0x006fb9
        )
        
        select_menu = VoiceRoleSelectMenu(self.ctx, self.lb_cog, self.setup_view)
        view = discord.ui.View()
        view.add_item(select_menu)
        
        await interaction.response.edit_message(embed=embed, view=view)
        
    @discord.ui.button(label="Complete Setup", emoji="<a:yes:1431909187247673464>", style=discord.ButtonStyle.success)
    async def complete_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Complete the setup process"""
        await self.finalize_setup(interaction)
        
    @discord.ui.button(label="Skip Roles", emoji="⏭️", style=discord.ButtonStyle.gray)
    async def skip_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Skip role configuration and complete setup"""
        await self.finalize_setup(interaction)
        
    async def finalize_setup(self, interaction):
        """Finalize the leaderboard setup"""
        await interaction.response.defer()
        
        # Save configuration to database
        async with aiosqlite.connect(DB_PATH) as db:
            chat_channel_id = self.setup_view.setup_data.get('chat_channel', {}).id if self.setup_view.setup_data.get('chat_channel') else None
            voice_channel_id = self.setup_view.setup_data.get('voice_channel', {}).id if self.setup_view.setup_data.get('voice_channel') else None
            chat_role_id = self.setup_view.setup_data.get('chat_role', {}).id if self.setup_view.setup_data.get('chat_role') else None
            voice_role_id = self.setup_view.setup_data.get('voice_role', {}).id if self.setup_view.setup_data.get('voice_role') else None
            
            await db.execute("""
                INSERT OR REPLACE INTO leaderboard_channels 
                (guild_id, chat_channel_id, voice_channel_id, top_chatter_role_id, top_voice_role_id)
                VALUES (?, ?, ?, ?, ?)
            """, (self.ctx.guild.id, chat_channel_id, voice_channel_id, chat_role_id, voice_role_id))
            await db.commit()
        
        # Send initial leaderboards
        if chat_channel_id:
            chat_channel = self.ctx.guild.get_channel(chat_channel_id)
            await self.lb_cog.update_chat_leaderboard(self.ctx.guild, chat_channel)
            
        if voice_channel_id:
            voice_channel = self.ctx.guild.get_channel(voice_channel_id)
            await self.lb_cog.update_voice_leaderboard(self.ctx.guild, voice_channel)
        
        # Create success embed
        setup_summary = []
        if chat_channel_id:
            setup_summary.append(f"{':checkmark:'} **Chat Leaderboard**: {self.setup_view.setup_data['chat_channel'].mention}")
        if voice_channel_id:
            setup_summary.append(f"{':checkmark:'} **Voice Leaderboard**: {self.setup_view.setup_data['voice_channel'].mention}")
        if chat_role_id:
            setup_summary.append(f"{':checkmark:'} **Top Chatter Role**: {self.setup_view.setup_data['chat_role'].mention}")
        if voice_role_id:
            setup_summary.append(f"{':checkmark:'} **Top Voice Role**: {self.setup_view.setup_data['voice_role'].mention}")
            
        embed = discord.Embed(
            title="<a:yes:1431909187247673464> Live Leaderboard Setup Complete!",
            description="**Configuration Summary:**\n\n" + "\n".join(setup_summary) + 
                       f"\n\n{':timer:'} **Auto-updates** every 10 minutes\n"
                       f"{':warning:'} **Weekly role rewards** will be applied automatically",
            color=0x00ff88
        )
        
        embed.add_field(
            name="💡 Available Commands",
            value="`streaks` - View streak leaderboards\n"
                  "`mystreak` - Check your personal streaks\n"
                  "`lbroles` - Configure reward roles later\n"
                  "`glb` - View/manage chat leaderboard\n"
                  "`gvclb` - View/manage voice leaderboard",
            inline=False
        )
        
        await interaction.edit_original_response(embed=embed, view=None)

class ChatRoleSelectMenu(discord.ui.RoleSelect):
    """Chat role selection dropdown"""
    
    def __init__(self, ctx, lb_cog, setup_view):
        super().__init__(placeholder="Select a role for top chatters...", max_values=1)
        self.ctx = ctx
        self.lb_cog = lb_cog
        self.setup_view = setup_view
        
    async def callback(self, interaction: discord.Interaction):
        """Handle chat role selection"""
        role = self.values[0]
        self.setup_view.setup_data['chat_role'] = role
        
        embed = discord.Embed(
            title="<a:yes:1431909187247673464> Chat Role Selected",
            description=f"Top chatter role set to: {role.mention}",
            color=0x00ff88
        )
        
        view = RoleSetupView(self.ctx, self.lb_cog, self.setup_view)
        await interaction.response.edit_message(embed=embed, view=view)

class VoiceRoleSelectMenu(discord.ui.RoleSelect):
    """Voice role selection dropdown"""
    
    def __init__(self, ctx, lb_cog, setup_view):
        super().__init__(placeholder="Select a role for top voice users...", max_values=1)
        self.ctx = ctx
        self.lb_cog = lb_cog
        self.setup_view = setup_view
        
    async def callback(self, interaction: discord.Interaction):
        """Handle voice role selection"""
        role = self.values[0]
        self.setup_view.setup_data['voice_role'] = role
        
        embed = discord.Embed(
            title="<a:yes:1431909187247673464> Voice Role Selected",
            description=f"Top voice user role set to: {role.mention}",
            color=0x00ff88
        )
        
        view = RoleSetupView(self.ctx, self.lb_cog, self.setup_view)
        await interaction.response.edit_message(embed=embed, view=view)

class GLBResetView(discord.ui.View):
    """Confirmation view for GLB reset"""
    
    def __init__(self, author, guild_id, prefix):
        super().__init__(timeout=60)
        self.author = author
        self.guild_id = guild_id
        self.prefix = prefix
        
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow the command author to interact"""
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the command author can use this.", ephemeral=True)
            return False
        return True
    
    @discord.ui.button(label="✅ Confirm Reset", style=discord.ButtonStyle.danger)
    async def confirm_reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm GLB reset"""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                # Remove the leaderboard configuration
                await db.execute("""
                    DELETE FROM leaderboard_channels WHERE guild_id = ?
                """, (self.guild_id,))
                await db.commit()
            
            embed = discord.Embed(
                title="✅ GLB Reset Complete",
                description="**Global Leaderboard has been reset successfully.**\n\n"
                           "• Leaderboard channels removed\n"
                           "• Role rewards disabled\n"
                           "• Auto-updates stopped\n\n"
                           "**User data (messages, voice time, streaks) has been preserved.**\n\n"
                           f"Use `{self.prefix}glb #channel` to set up again.",
                color=0x00ff88
            )
            
            await interaction.response.edit_message(embed=embed, view=None)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Reset Failed",
                description=f"An error occurred while resetting GLB:\n```{str(e)}```",
                color=0xff4444
            )
            await interaction.response.edit_message(embed=embed, view=None)
    
    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel GLB reset"""
        embed = discord.Embed(
            title="❌ Reset Cancelled",
            description="GLB reset has been cancelled. No changes were made.",
            color=0x888888
        )
        await interaction.response.edit_message(embed=embed, view=None)
    
    async def on_timeout(self):
        """Handle timeout"""
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

class GLBCustomizeView(discord.ui.View):
    """Main customization menu for GLB leaderboards"""
    
    def __init__(self, ctx, lb_cog):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.lb_cog = lb_cog
        self.customization_data = {}
        
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow command author to interact"""
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ Only the command author can use this.", ephemeral=True)
            return False
        return True
    
    @discord.ui.button(label="🎨 Colors & Theme", style=discord.ButtonStyle.primary, row=0)
    async def customize_colors(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Customize colors and theme"""
        view = ColorCustomizeView(self.ctx, self.lb_cog, self)
        embed = discord.Embed(
            title="🎨 Color & Theme Customization",
            description="**Customize the colors and overall theme of your leaderboards.**\n\n"
                       "Choose from preset themes or create custom colors for different elements.",
            color=0x006fb9
        )
        
        embed.add_field(
            name="🎯 Available Options",
            value="🟢 **Chat Leaderboard Color** - Main embed color\n"
                  "🟠 **Voice Leaderboard Color** - Voice embed color\n"
                  "🎭 **Preset Themes** - Professional, Gaming, Minimal\n"
                  "🌈 **Custom Colors** - Enter hex codes",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="😀 Emojis & Icons", style=discord.ButtonStyle.primary, row=0)
    async def customize_emojis(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Customize emojis and icons"""
        view = EmojiCustomizeView(self.ctx, self.lb_cog, self)
        embed = discord.Embed(
            title="😀 Emoji & Icon Customization",
            description="**Customize emojis and icons used in your leaderboards.**\n\n"
                       "Change ranking emojis, category icons, and decorative elements.",
            color=0x006fb9
        )
        
        embed.add_field(
            name="🎯 Available Options",
            value="🏆 **Ranking Emojis** - 1st, 2nd, 3rd place etc.\n"
                  "💬 **Chat Icon** - Icon for chat leaderboard\n"
                  "🎵 **Voice Icon** - Icon for voice leaderboard\n"
                  "✨ **Preset Packs** - Gaming, Professional, Fun",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="📝 Text & Titles", style=discord.ButtonStyle.primary, row=1)
    async def customize_text(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Customize text and titles"""
        view = TextCustomizeView(self.ctx, self.lb_cog, self)
        embed = discord.Embed(
            title="📝 Text & Title Customization",
            description="**Customize titles, descriptions, and text content.**\n\n"
                       "Personalize the text elements to match your server's style.",
            color=0x006fb9
        )
        
        embed.add_field(
            name="🎯 Available Options",
            value="📊 **Chat Title** - Main chat leaderboard title\n"
                  "🎵 **Voice Title** - Main voice leaderboard title\n"
                  "📝 **Descriptions** - Subtitle text under titles\n"
                  "👣 **Footer Text** - Bottom text (update frequency)",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="🖼️ Images & Media", style=discord.ButtonStyle.primary, row=1)
    async def customize_images(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Customize images and media"""
        view = ImageCustomizeView(self.ctx, self.lb_cog, self)
        embed = discord.Embed(
            title="🖼️ Image & Media Customization",
            description="**Add thumbnails, author icons, and other visual elements.**\n\n"
                       "Enhance your leaderboards with custom images and media.",
            color=0x006fb9
        )
        
        embed.add_field(
            name="🎯 Available Options",
            value="🖼️ **Thumbnail** - Small image in top-right corner\n"
                  "👤 **Author Icon** - Icon next to leaderboard title\n"
                  "🔗 **Image URLs** - Link to your custom images\n"
                  "🗑️ **Remove Images** - Clear current images",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="⚙️ Layout & Format", style=discord.ButtonStyle.secondary, row=2)
    async def customize_layout(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Customize layout and formatting"""
        view = LayoutCustomizeView(self.ctx, self.lb_cog, self)
        embed = discord.Embed(
            title="⚙️ Layout & Format Customization",
            description="**Customize the layout and formatting options.**\n\n"
                       "Control what information is shown and how it's displayed.",
            color=0x006fb9
        )
        
        embed.add_field(
            name="🎯 Available Options",
            value="📊 **Show Streaks** - Display activity streaks\n"
                  "📈 **Daily Stats** - Show daily message counts\n"
                  "📱 **Compact Mode** - Condensed view for mobile\n"
                  "🔢 **Leaderboard Size** - Number of users shown",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="🔄 Reset to Default", style=discord.ButtonStyle.danger, row=2)
    async def reset_customization(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Reset all customizations to default"""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                DELETE FROM leaderboard_customization WHERE guild_id = ?
            """, (self.ctx.guild.id,))
            await db.commit()
        
        embed = discord.Embed(
            title="✅ Customization Reset",
            description="All leaderboard customizations have been reset to default.\n\n"
                       "Your leaderboards will now use the standard appearance.",
            color=0x00ff88
        )
        
        await interaction.response.edit_message(embed=embed, view=None)
    
    @discord.ui.button(label="💾 Save & Exit", style=discord.ButtonStyle.success, row=2)
    async def save_exit(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Save changes and exit"""
        embed = discord.Embed(
            title="✅ Customization Complete",
            description="Your leaderboard customizations have been saved!\n\n"
                       "The changes will take effect on the next leaderboard update (every 10 minutes) "
                       "or you can run the leaderboard commands to see them immediately.",
            color=0x00ff88
        )
        
        await interaction.response.edit_message(embed=embed, view=None)

# Customization Modals
class ColorCustomizeModal(discord.ui.Modal, title="🎨 Color Customization"):
    """Modal for customizing leaderboard colors"""
    
    chat_color = discord.ui.TextInput(
        label="Chat Leaderboard Color (Hex)",
        placeholder="#00ff88 or 00ff88",
        max_length=7,
        required=False
    )
    
    voice_color = discord.ui.TextInput(
        label="Voice Leaderboard Color (Hex)",
        placeholder="#ff8800 or ff8800",
        max_length=7,
        required=False
    )
    
    def __init__(self, ctx, lb_cog, current_settings):
        super().__init__()
        self.ctx = ctx
        self.lb_cog = lb_cog
        
        # Set defaults from current settings
        self.chat_color.default = current_settings.get('chat_color', '#00ff88')
        self.voice_color.default = current_settings.get('voice_color', '#ff8800')
    
    async def on_submit(self, interaction: discord.Interaction):
        # Validate and save color settings
        chat_color = self.chat_color.value.strip()
        voice_color = self.voice_color.value.strip()
        
        # Add # if missing
        if chat_color and not chat_color.startswith('#'):
            chat_color = f"#{chat_color}"
        if voice_color and not voice_color.startswith('#'):
            voice_color = f"#{voice_color}"
        
        # Validate hex format
        try:
            if chat_color:
                int(chat_color.replace('#', ''), 16)
            if voice_color:
                int(voice_color.replace('#', ''), 16)
        except:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Invalid Color Format",
                    description="Please use valid hex color codes (e.g., #00ff88 or 00ff88)",
                    color=0xFF0000
                ),
                ephemeral=True
            )
            return
        
        # Save to database
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT OR REPLACE INTO leaderboard_customization (guild_id, chat_color, voice_color)
                VALUES (?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    chat_color = COALESCE(excluded.chat_color, chat_color),
                    voice_color = COALESCE(excluded.voice_color, voice_color)
            """, (self.ctx.guild.id, chat_color or None, voice_color or None))
            await db.commit()
        
        embed = discord.Embed(
            title="✅ Colors Updated",
            description=f"**Chat Color:** {chat_color}\n**Voice Color:** {voice_color}",
            color=int(chat_color.replace('#', ''), 16) if chat_color else 0x00ff88
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

class EmojiCustomizeModal(discord.ui.Modal, title="😀 Emoji Customization"):
    """Modal for customizing leaderboard emojis"""
    
    rank_emojis = discord.ui.TextInput(
        label="Ranking Emojis (comma-separated, 10 emojis)",
        placeholder="🥇,🥈,🥉,4️⃣,5️⃣,6️⃣,7️⃣,8️⃣,9️⃣,🔟",
        style=discord.TextStyle.paragraph,
        max_length=200,
        required=False
    )
    
    chat_icon = discord.ui.TextInput(
        label="Chat Leaderboard Icon Emoji",
        placeholder="💬",
        max_length=10,
        required=False
    )
    
    voice_icon = discord.ui.TextInput(
        label="Voice Leaderboard Icon Emoji",
        placeholder="🎵",
        max_length=10,
        required=False
    )
    
    def __init__(self, ctx, lb_cog, current_settings):
        super().__init__()
        self.ctx = ctx
        self.lb_cog = lb_cog
        
        # Set defaults from current settings
        rank_emojis = current_settings.get('rank_emojis', ['🥇', '🥈', '🥉', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟'])
        self.rank_emojis.default = ','.join(rank_emojis)
        self.chat_icon.default = current_settings.get('chat_icon_emoji', '💬')
        self.voice_icon.default = current_settings.get('voice_icon_emoji', '🎵')
    
    async def on_submit(self, interaction: discord.Interaction):
        # Parse emoji list
        rank_emojis_str = self.rank_emojis.value.strip()
        chat_icon = self.chat_icon.value.strip()
        voice_icon = self.voice_icon.value.strip()
        
        # Save to database
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT OR REPLACE INTO leaderboard_customization (guild_id, rank_emojis, chat_icon_emoji, voice_icon_emoji)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    rank_emojis = COALESCE(excluded.rank_emojis, rank_emojis),
                    chat_icon_emoji = COALESCE(excluded.chat_icon_emoji, chat_icon_emoji),
                    voice_icon_emoji = COALESCE(excluded.voice_icon_emoji, voice_icon_emoji)
            """, (self.ctx.guild.id, rank_emojis_str or None, chat_icon or None, voice_icon or None))
            await db.commit()
        
        embed = discord.Embed(
            title="✅ Emojis Updated",
            description=f"**Chat Icon:** {chat_icon}\n**Voice Icon:** {voice_icon}\n**Rankings:** {rank_emojis_str}",
            color=0x00ff88
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

class TextCustomizeModal(discord.ui.Modal, title="📝 Text Customization"):
    """Modal for customizing leaderboard text"""
    
    chat_title = discord.ui.TextInput(
        label="Chat Leaderboard Title",
        placeholder="Chat Leaderboard",
        max_length=100,
        required=False
    )
    
    voice_title = discord.ui.TextInput(
        label="Voice Leaderboard Title",
        placeholder="Voice Leaderboard",
        max_length=100,
        required=False
    )
    
    chat_description = discord.ui.TextInput(
        label="Chat Description",
        placeholder="Top chatters this week",
        max_length=200,
        required=False
    )
    
    voice_description = discord.ui.TextInput(
        label="Voice Description",
        placeholder="Top voice users this week",
        max_length=200,
        required=False
    )
    
    footer_text = discord.ui.TextInput(
        label="Footer Text",
        placeholder="Updates every 10 minutes",
        max_length=100,
        required=False
    )
    
    def __init__(self, ctx, lb_cog, current_settings):
        super().__init__()
        self.ctx = ctx
        self.lb_cog = lb_cog
        
        # Set defaults from current settings
        self.chat_title.default = current_settings.get('chat_title', 'Chat Leaderboard')
        self.voice_title.default = current_settings.get('voice_title', 'Voice Leaderboard')
        self.chat_description.default = current_settings.get('chat_description', 'Top chatters this week')
        self.voice_description.default = current_settings.get('voice_description', 'Top voice users this week')
        self.footer_text.default = current_settings.get('footer_text', 'Updates every 10 minutes')
    
    async def on_submit(self, interaction: discord.Interaction):
        # Save to database
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT OR REPLACE INTO leaderboard_customization 
                (guild_id, chat_title, voice_title, chat_description, voice_description, footer_text)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    chat_title = COALESCE(excluded.chat_title, chat_title),
                    voice_title = COALESCE(excluded.voice_title, voice_title),
                    chat_description = COALESCE(excluded.chat_description, chat_description),
                    voice_description = COALESCE(excluded.voice_description, voice_description),
                    footer_text = COALESCE(excluded.footer_text, footer_text)
            """, (
                self.ctx.guild.id,
                self.chat_title.value.strip() or None,
                self.voice_title.value.strip() or None,
                self.chat_description.value.strip() or None,
                self.voice_description.value.strip() or None,
                self.footer_text.value.strip() or None
            ))
            await db.commit()
        
        embed = discord.Embed(
            title="✅ Text Updated",
            description=f"**Chat Title:** {self.chat_title.value}\n**Voice Title:** {self.voice_title.value}",
            color=0x00ff88
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

class ImageCustomizeModal(discord.ui.Modal, title="🖼️ Image Customization"):
    """Modal for customizing leaderboard images"""
    
    thumbnail_url = discord.ui.TextInput(
        label="Thumbnail URL (small image in corner)",
        placeholder="https://example.com/image.png",
        max_length=500,
        required=False,
        style=discord.TextStyle.short
    )
    
    author_icon_url = discord.ui.TextInput(
        label="Author Icon URL (icon next to title)",
        placeholder="https://example.com/icon.png",
        max_length=500,
        required=False,
        style=discord.TextStyle.short
    )
    
    def __init__(self, ctx, lb_cog, current_settings):
        super().__init__()
        self.ctx = ctx
        self.lb_cog = lb_cog
        
        # Set defaults from current settings
        self.thumbnail_url.default = current_settings.get('thumbnail_url', '') or ''
        self.author_icon_url.default = current_settings.get('author_icon_url', '') or ''
    
    async def on_submit(self, interaction: discord.Interaction):
        # Validate URLs
        thumbnail = self.thumbnail_url.value.strip()
        author_icon = self.author_icon_url.value.strip()
        
        if thumbnail and not thumbnail.startswith(('http://', 'https://')):
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Invalid URL",
                    description="Thumbnail URL must start with http:// or https://",
                    color=0xFF0000
                ),
                ephemeral=True
            )
            return
        
        if author_icon and not author_icon.startswith(('http://', 'https://')):
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Invalid URL",
                    description="Author icon URL must start with http:// or https://",
                    color=0xFF0000
                ),
                ephemeral=True
            )
            return
        
        # Save to database
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT OR REPLACE INTO leaderboard_customization (guild_id, thumbnail_url, author_icon_url)
                VALUES (?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    thumbnail_url = COALESCE(excluded.thumbnail_url, thumbnail_url),
                    author_icon_url = COALESCE(excluded.author_icon_url, author_icon_url)
            """, (self.ctx.guild.id, thumbnail or None, author_icon or None))
            await db.commit()
        
        embed = discord.Embed(
            title="✅ Images Updated",
            description=f"Thumbnail and author icon URLs have been saved.",
            color=0x00ff88
        )
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        await interaction.response.send_message(embed=embed, ephemeral=True)

# Customization Views (Complete Implementation)
class ColorCustomizeView(discord.ui.View):
    """Color customization interface"""
    def __init__(self, ctx, lb_cog, parent_view):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.lb_cog = lb_cog
        self.parent_view = parent_view
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ Only the command author can use this.", ephemeral=True)
            return False
        return True
    
    @discord.ui.button(label="Custom Colors", emoji="🎨", style=discord.ButtonStyle.primary, row=0)
    async def custom_colors(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal for custom colors"""
        settings = await self.lb_cog.get_customization_settings(self.ctx.guild.id)
        modal = ColorCustomizeModal(self.ctx, self.lb_cog, settings)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="← Back to Menu", style=discord.ButtonStyle.secondary, row=1)
    async def back_to_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to main customization menu"""
        embed = discord.Embed(
            title="🎨 GLB Leaderboard Customization",
            description="**Customize your leaderboard appearance!**\n\n"
                       "Choose what you'd like to customize from the options below.",
            color=0x006fb9
        )
        await interaction.response.edit_message(embed=embed, view=self.parent_view)

class EmojiCustomizeView(discord.ui.View):
    """Emoji customization interface"""
    def __init__(self, ctx, lb_cog, parent_view):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.lb_cog = lb_cog
        self.parent_view = parent_view
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ Only the command author can use this.", ephemeral=True)
            return False
        return True
    
    @discord.ui.button(label="Custom Emojis", emoji="😀", style=discord.ButtonStyle.primary, row=0)
    async def custom_emojis(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal for custom emojis"""
        settings = await self.lb_cog.get_customization_settings(self.ctx.guild.id)
        modal = EmojiCustomizeModal(self.ctx, self.lb_cog, settings)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="← Back to Menu", style=discord.ButtonStyle.secondary, row=1)
    async def back_to_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🎨 GLB Leaderboard Customization",
            description="**Customize your leaderboard appearance!**\n\n"
                       "Choose what you'd like to customize from the options below.",
            color=0x006fb9
        )
        await interaction.response.edit_message(embed=embed, view=self.parent_view)

class TextCustomizeView(discord.ui.View):
    """Text customization interface"""
    def __init__(self, ctx, lb_cog, parent_view):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.lb_cog = lb_cog
        self.parent_view = parent_view
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ Only the command author can use this.", ephemeral=True)
            return False
        return True
    
    @discord.ui.button(label="Custom Text", emoji="📝", style=discord.ButtonStyle.primary, row=0)
    async def custom_text(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal for custom text"""
        settings = await self.lb_cog.get_customization_settings(self.ctx.guild.id)
        modal = TextCustomizeModal(self.ctx, self.lb_cog, settings)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="← Back to Menu", style=discord.ButtonStyle.secondary, row=1)
    async def back_to_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🎨 GLB Leaderboard Customization",
            description="**Customize your leaderboard appearance!**\n\n"
                       "Choose what you'd like to customize from the options below.",
            color=0x006fb9
        )
        await interaction.response.edit_message(embed=embed, view=self.parent_view)

class ImageCustomizeView(discord.ui.View):
    """Image customization interface"""
    def __init__(self, ctx, lb_cog, parent_view):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.lb_cog = lb_cog
        self.parent_view = parent_view
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ Only the command author can use this.", ephemeral=True)
            return False
        return True
    
    @discord.ui.button(label="Custom Images", emoji="🖼️", style=discord.ButtonStyle.primary, row=0)
    async def custom_images(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal for custom images"""
        settings = await self.lb_cog.get_customization_settings(self.ctx.guild.id)
        modal = ImageCustomizeModal(self.ctx, self.lb_cog, settings)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="← Back to Menu", style=discord.ButtonStyle.secondary, row=1)
    async def back_to_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🎨 GLB Leaderboard Customization",
            description="**Customize your leaderboard appearance!**\n\n"
                       "Choose what you'd like to customize from the options below.",
            color=0x006fb9
        )
        await interaction.response.edit_message(embed=embed, view=self.parent_view)

class LayoutCustomizeView(discord.ui.View):
    """Layout customization interface"""
    def __init__(self, ctx, lb_cog, parent_view):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.lb_cog = lb_cog
        self.parent_view = parent_view
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ Only the command author can use this.", ephemeral=True)
            return False
        return True
    
    @discord.ui.button(label="Toggle Streaks", emoji="🔥", style=discord.ButtonStyle.primary, row=0)
    async def toggle_streaks(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Toggle streak display"""
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("""
                SELECT show_streaks FROM leaderboard_customization WHERE guild_id = ?
            """, (self.ctx.guild.id,))
            result = await cursor.fetchone()
            
            current = result[0] if result else True
            new_value = not current
            
            await db.execute("""
                INSERT OR REPLACE INTO leaderboard_customization (guild_id, show_streaks)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET show_streaks = excluded.show_streaks
            """, (self.ctx.guild.id, new_value))
            await db.commit()
        
        status = "enabled" if new_value else "disabled"
        await interaction.response.send_message(
            embed=discord.Embed(
                title="✅ Streaks Updated",
                description=f"Activity streaks are now **{status}**.",
                color=0x00ff88
            ),
            ephemeral=True
        )
    
    @discord.ui.button(label="Toggle Compact Mode", emoji="📱", style=discord.ButtonStyle.primary, row=0)
    async def toggle_compact(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Toggle compact mode"""
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("""
                SELECT compact_mode FROM leaderboard_customization WHERE guild_id = ?
            """, (self.ctx.guild.id,))
            result = await cursor.fetchone()
            
            current = result[0] if result else False
            new_value = not current
            
            await db.execute("""
                INSERT OR REPLACE INTO leaderboard_customization (guild_id, compact_mode)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET compact_mode = excluded.compact_mode
            """, (self.ctx.guild.id, new_value))
            await db.commit()
        
        status = "enabled" if new_value else "disabled"
        await interaction.response.send_message(
            embed=discord.Embed(
                title="✅ Compact Mode Updated",
                description=f"Compact mode is now **{status}**.",
                color=0x00ff88
            ),
            ephemeral=True
        )
    
    @discord.ui.button(label="← Back to Menu", style=discord.ButtonStyle.secondary, row=1)
    async def back_to_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🎨 GLB Leaderboard Customization",
            description="**Customize your leaderboard appearance!**\n\n"
                       "Choose what you'd like to customize from the options below.",
            color=0x006fb9
        )
        await interaction.response.edit_message(embed=embed, view=self.parent_view)

async def setup(bot):
    await bot.add_cog(LiveLeaderboard(bot))