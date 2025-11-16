import discord
from discord.ext import commands, tasks
import aiosqlite
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional
import os

# Check for chart generation capability
try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.patches import Rectangle
    import numpy as np
    from io import BytesIO
    CHARTS_AVAILABLE = True
except ImportError:
    CHARTS_AVAILABLE = False

# Import custom checks
from utils.Tools import blacklist_check, ignore_check

# Import professional canvas generator (cv2-based for better quality)
try:
    from utils.statbot_canvas_cv2 import StatBotCanvasCV2
    CANVAS_AVAILABLE = True
except ImportError:
    CANVAS_AVAILABLE = False
    print("[STATS] Professional canvas generator not available")


class DummyChartGenerator:
    """Dummy chart generator when matplotlib is not available"""
    async def generate_server_overview(self, *args, **kwargs):
        return None
    
    async def generate_user_stats(self, *args, **kwargs):
        return None
    
    async def generate_message_stats(self, *args, **kwargs):
        return None
    
    async def generate_voice_stats(self, *args, **kwargs):
        return None


class StatBotStyleGenerator:
    """StatBot-style canvas image generator"""
    
    def __init__(self):
        self.theme_colors = {
            'background': '#000000',          # Pure black background
            'card_bg': '#1a1a1a',           # Dark gray for cards
            'primary': '#20b2aa',           # Light sea green (teal)
            'secondary': '#008b8b',         # Dark cyan (darker teal)
            'success': '#2dd4bf',           # Teal-400 for success
            'warning': '#f59e0b',           # Amber for warnings
            'danger': '#ef4444',            # Red for danger
            'text_primary': '#ffffff',      # White text
            'text_secondary': '#a1a1aa',    # Gray text
            'accent': '#14b8a6',            # Teal-500 for accents
            'border': '#374151',            # Gray border
            'gradient_start': '#20b2aa',    # Teal gradient start
            'gradient_end': '#008b8b'       # Teal gradient end
        }
    
    async def generate_server_overview(self, guild_name, stats_data):
        """Generate StatBot-style server overview image"""
        if not CHARTS_AVAILABLE:
            return None
        
        try:
            # Create figure with dark theme
            fig, ax = plt.subplots(figsize=(12, 8), facecolor=self.theme_colors['background'])
            ax.set_facecolor(self.theme_colors['background'])
            
            # Title
            fig.suptitle(f"{guild_name} - Server Overview", 
                        fontsize=20, color=self.theme_colors['text_primary'], 
                        fontweight='bold', y=0.95)
            
            # Create grid layout for stats boxes
            boxes = [
                {"title": "Total Members", "value": f"{stats_data.get('member_count', 0):,}", "color": self.theme_colors['primary']},
                {"title": "Messages Today", "value": f"{stats_data.get('messages_today', 0):,}", "color": self.theme_colors['success']},
                {"title": "Voice Hours Today", "value": f"{stats_data.get('voice_hours_today', 0):.1f}h", "color": self.theme_colors['warning']},
                {"title": "Active Users", "value": f"{stats_data.get('active_users_today', 0):,}", "color": self.theme_colors['accent']},
                {"title": "Messages This Week", "value": f"{stats_data.get('messages_week', 0):,}", "color": self.theme_colors['primary']},
                {"title": "Growth Rate", "value": f"+{stats_data.get('growth_rate', 0):.1f}%", "color": self.theme_colors['success']}
            ]
            
            # Draw stat boxes in grid
            cols = 3
            rows = 2
            box_width = 0.25
            box_height = 0.15
            
            for i, box in enumerate(boxes):
                row = i // cols
                col = i % cols
                
                x = 0.1 + col * 0.3
                y = 0.65 - row * 0.25
                
                # Draw box background
                rect = Rectangle((x, y), box_width, box_height, 
                               facecolor=self.theme_colors['card_bg'],
                               edgecolor=box['color'], linewidth=2,
                               transform=ax.transAxes)
                ax.add_patch(rect)
                
                # Add title
                ax.text(x + box_width/2, y + box_height - 0.03, box['title'],
                       transform=ax.transAxes, ha='center', va='top',
                       fontsize=10, color=self.theme_colors['text_secondary'],
                       fontweight='bold')
                
                # Add value
                ax.text(x + box_width/2, y + 0.05, box['value'],
                       transform=ax.transAxes, ha='center', va='bottom',
                       fontsize=14, color=box['color'],
                       fontweight='bold')
            
            # Remove axis
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.axis('off')
            
            # Save to BytesIO
            buffer = BytesIO()
            plt.tight_layout()
            plt.savefig(buffer, format='png', facecolor=self.theme_colors['background'], 
                       bbox_inches='tight', dpi=150)
            buffer.seek(0)
            plt.close()
            
            return buffer
            
        except Exception as e:
            print(f"Error generating server overview: {e}")
            return None
    
    async def generate_user_stats(self, user_name, stats_data):
        """Generate StatBot-style user stats image"""
        if not CHARTS_AVAILABLE:
            return None
        
        try:
            # Create figure
            fig, ax = plt.subplots(figsize=(10, 8), facecolor=self.theme_colors['background'])
            ax.set_facecolor(self.theme_colors['background'])
            
            # Title
            fig.suptitle(f"{user_name} - User Statistics", 
                        fontsize=18, color=self.theme_colors['text_primary'], 
                        fontweight='bold', y=0.95)
            
            # User stat boxes
            boxes = [
                {"title": "Messages", "value": f"{stats_data.get('total_messages', 0):,}", "color": self.theme_colors['primary']},
                {"title": "Voice Hours", "value": f"{stats_data.get('voice_hours', 0):.1f}h", "color": self.theme_colors['success']},
                {"title": "Server Rank", "value": f"#{stats_data.get('rank', 0)}", "color": self.theme_colors['warning']},
                {"title": "Activity Score", "value": f"{stats_data.get('activity_score', 0):.1f}", "color": self.theme_colors['accent']}
            ]
            
            # Draw boxes in 2x2 grid
            for i, box in enumerate(boxes):
                row = i // 2
                col = i % 2
                
                x = 0.1 + col * 0.4
                y = 0.6 - row * 0.3
                
                # Draw box
                rect = Rectangle((x, y), 0.3, 0.2, 
                               facecolor=self.theme_colors['card_bg'],
                               edgecolor=box['color'], linewidth=2,
                               transform=ax.transAxes)
                ax.add_patch(rect)
                
                # Add text
                ax.text(x + 0.15, y + 0.15, box['title'],
                       transform=ax.transAxes, ha='center', va='top',
                       fontsize=12, color=self.theme_colors['text_secondary'],
                       fontweight='bold')
                
                ax.text(x + 0.15, y + 0.05, box['value'],
                       transform=ax.transAxes, ha='center', va='bottom',
                       fontsize=16, color=box['color'],
                       fontweight='bold')
            
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.axis('off')
            
            # Save to buffer
            buffer = BytesIO()
            plt.tight_layout()
            plt.savefig(buffer, format='png', facecolor=self.theme_colors['background'], 
                       bbox_inches='tight', dpi=150)
            buffer.seek(0)
            plt.close()
            
            return buffer
            
        except Exception as e:
            print(f"Error generating user stats: {e}")
            return None
    
    async def generate_message_trends(self, guild_name, trend_data):
        """Generate message trends chart"""
        if not CHARTS_AVAILABLE:
            return None
        
        try:
            fig, ax = plt.subplots(figsize=(12, 6), facecolor=self.theme_colors['background'])
            ax.set_facecolor(self.theme_colors['background'])
            
            # Title
            fig.suptitle(f"{guild_name} - Message Trends", 
                        fontsize=18, color=self.theme_colors['text_primary'], 
                        fontweight='bold', y=0.95)
            
            # Sample data for demonstration
            days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
            messages = trend_data.get('daily_messages', [120, 150, 180, 200, 170, 160, 140])
            
            # Create gradient bars
            bars = ax.bar(days, messages, color=self.theme_colors['primary'], 
                         alpha=0.8, edgecolor=self.theme_colors['accent'], linewidth=2)
            
            # Style the chart
            ax.set_xlabel('Day of Week', color=self.theme_colors['text_secondary'], fontsize=12)
            ax.set_ylabel('Messages', color=self.theme_colors['text_secondary'], fontsize=12)
            ax.tick_params(colors=self.theme_colors['text_secondary'])
            
            # Remove spines and customize
            for spine in ax.spines.values():
                spine.set_color(self.theme_colors['border'])
            
            # Add value labels on bars
            for bar, value in zip(bars, messages):
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5,
                       f'{value}', ha='center', va='bottom', 
                       color=self.theme_colors['text_primary'], fontweight='bold')
            
            # Grid
            ax.grid(True, alpha=0.3, color=self.theme_colors['border'])
            
            plt.tight_layout()
            
            # Save to buffer
            buffer = BytesIO()
            plt.savefig(buffer, format='png', facecolor=self.theme_colors['background'], 
                       bbox_inches='tight', dpi=150)
            buffer.seek(0)
            plt.close()
            
            return buffer
            
        except Exception as e:
            print(f"Error generating message trends: {e}")
            return None
    
    async def generate_voice_activity(self, guild_name, voice_data):
        """Generate voice activity chart"""
        if not CHARTS_AVAILABLE:
            return None
        
        try:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6), facecolor=self.theme_colors['background'])
            fig.patch.set_facecolor(self.theme_colors['background'])
            
            # Title
            fig.suptitle(f"{guild_name} - Voice Activity", 
                        fontsize=18, color=self.theme_colors['text_primary'], 
                        fontweight='bold', y=0.95)
            
            # Left chart - Daily voice hours
            ax1.set_facecolor(self.theme_colors['background'])
            days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
            hours = voice_data.get('daily_hours', [15.5, 20.2, 18.7, 25.3, 22.1, 28.5, 24.8])
            
            ax1.plot(days, hours, color=self.theme_colors['primary'], linewidth=3, marker='o', 
                    markersize=8, markerfacecolor=self.theme_colors['accent'])
            ax1.fill_between(days, hours, alpha=0.3, color=self.theme_colors['primary'])
            
            ax1.set_title('Daily Voice Hours', color=self.theme_colors['text_primary'], fontsize=14)
            ax1.set_ylabel('Hours', color=self.theme_colors['text_secondary'])
            ax1.tick_params(colors=self.theme_colors['text_secondary'])
            ax1.grid(True, alpha=0.3, color=self.theme_colors['border'])
            
            # Right chart - Top voice channels (pie chart)
            ax2.set_facecolor(self.theme_colors['background'])
            channels = voice_data.get('top_channels', ['General', 'Gaming', 'Music', 'Study'])
            channel_hours = voice_data.get('channel_hours', [45, 30, 25, 15])
            
            colors = [self.theme_colors['primary'], self.theme_colors['accent'], 
                     self.theme_colors['success'], self.theme_colors['secondary']]
            
            wedges, texts, autotexts = ax2.pie(channel_hours, labels=channels, autopct='%1.1f%%',
                                              colors=colors, startangle=90)
            
            for text in texts:
                text.set_color(self.theme_colors['text_secondary'])
            for autotext in autotexts:
                autotext.set_color(self.theme_colors['text_primary'])
                autotext.set_fontweight('bold')
            
            ax2.set_title('Voice Channel Usage', color=self.theme_colors['text_primary'], fontsize=14)
            
            # Style spines
            for ax in [ax1, ax2]:
                for spine in ax.spines.values():
                    spine.set_color(self.theme_colors['border'])
            
            plt.tight_layout()
            
            # Save to buffer
            buffer = BytesIO()
            plt.savefig(buffer, format='png', facecolor=self.theme_colors['background'], 
                       bbox_inches='tight', dpi=150)
            buffer.seek(0)
            plt.close()
            
            return buffer
            
        except Exception as e:
            print(f"Error generating voice activity: {e}")
            return None
    
    async def generate_top_users(self, guild_name, user_data):
        """Generate top users leaderboard chart"""
        if not CHARTS_AVAILABLE:
            return None
        
        try:
            fig, ax = plt.subplots(figsize=(12, 8), facecolor=self.theme_colors['background'])
            ax.set_facecolor(self.theme_colors['background'])
            
            # Title
            fig.suptitle(f"{guild_name} - Top Active Users", 
                        fontsize=18, color=self.theme_colors['text_primary'], 
                        fontweight='bold', y=0.95)
            
            # Sample data
            users = user_data.get('usernames', ['User1', 'User2', 'User3', 'User4', 'User5'])
            scores = user_data.get('activity_scores', [95, 87, 82, 78, 74])
            
            # Create horizontal bar chart
            y_pos = range(len(users))
            bars = ax.barh(y_pos, scores, color=self.theme_colors['primary'], 
                          alpha=0.8, edgecolor=self.theme_colors['accent'], linewidth=2)
            
            # Add ranking badges
            colors = [self.theme_colors['warning'], self.theme_colors['text_secondary'], 
                     self.theme_colors['accent'], self.theme_colors['secondary'], 
                     self.theme_colors['primary']]
            
            for i, (bar, score) in enumerate(zip(bars, scores)):
                # Rank number
                rank_color = colors[i] if i < len(colors) else self.theme_colors['primary']
                ax.text(-5, bar.get_y() + bar.get_height()/2, f'#{i+1}',
                       ha='right', va='center', color=rank_color, fontweight='bold', fontsize=14)
                
                # Score value
                ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height()/2, f'{score}',
                       ha='left', va='center', color=self.theme_colors['text_primary'], 
                       fontweight='bold', fontsize=12)
            
            # Styling
            ax.set_yticks(y_pos)
            ax.set_yticklabels(users, color=self.theme_colors['text_primary'])
            ax.set_xlabel('Activity Score', color=self.theme_colors['text_secondary'], fontsize=12)
            ax.tick_params(colors=self.theme_colors['text_secondary'])
            ax.set_xlim(0, max(scores) + 10)
            
            # Remove spines
            for spine in ax.spines.values():
                spine.set_color(self.theme_colors['border'])
            
            # Grid
            ax.grid(True, alpha=0.3, color=self.theme_colors['border'], axis='x')
            
            plt.tight_layout()
            
            # Save to buffer
            buffer = BytesIO()
            plt.savefig(buffer, format='png', facecolor=self.theme_colors['background'], 
                       bbox_inches='tight', dpi=150)
            buffer.seek(0)
            plt.close()
            
            return buffer
            
        except Exception as e:
            print(f"Error generating top users: {e}")
            return None


class ComprehensiveStats(commands.Cog):
    """Clean, simple stats system matching StatBot style"""
    
    def __init__(self, bot):
        self.bot = bot
        self.stats_db = "databases/stats.db"
        
        # Initialize chart generator
        if CHARTS_AVAILABLE:
            self.chart_generator = StatBotStyleGenerator()
        else:
            self.chart_generator = DummyChartGenerator()
        
        # Initialize professional canvas generator with timezone (cv2-based)
        if CANVAS_AVAILABLE:
            # Default to Eastern Time (most common US timezone)
            # Users can override by setting different timezone per guild
            self.canvas_generator = StatBotCanvasCV2(timezone='America/New_York')
        else:
            self.canvas_generator = None
    
    async def cog_load(self):
        """Called when the cog is loaded"""
        await self.init_database()
    
    async def cog_unload(self):
        """Called when the cog is unloaded - cleanup database connections"""
        # Any cleanup code if needed
        pass
    
    async def init_database(self):
        """Initialize the statistics database"""
        try:
            os.makedirs("databases", exist_ok=True)
            
            async with aiosqlite.connect(self.stats_db) as db:
                # Guild settings table for timezone preferences
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS guild_settings (
                        guild_id INTEGER PRIMARY KEY,
                        timezone TEXT DEFAULT 'America/New_York'
                    )
                """)
                
                # Message stats table
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS message_stats (
                        guild_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        channel_id INTEGER NOT NULL,
                        date DATE NOT NULL,
                        hour INTEGER NOT NULL,
                        count INTEGER DEFAULT 0,
                        characters INTEGER DEFAULT 0,
                        words INTEGER DEFAULT 0,
                        attachments INTEGER DEFAULT 0,
                        mentions INTEGER DEFAULT 0,
                        PRIMARY KEY (guild_id, user_id, channel_id, date, hour)
                    )
                """)
                
                # Voice stats table
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS voice_stats (
                        guild_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        channel_id INTEGER NOT NULL,
                        date DATE NOT NULL,
                        hour INTEGER NOT NULL,
                        duration INTEGER DEFAULT 0,
                        duration_minutes REAL DEFAULT 0,
                        PRIMARY KEY (guild_id, user_id, channel_id, date, hour)
                    )
                """)
                
                await db.commit()
                print("[STATS] Database tables initialized successfully")
        except Exception as e:
            print(f"[STATS] Error initializing database: {e}")
            import traceback
            traceback.print_exc()
    
    async def get_guild_timezone(self, guild_id):
        """Get the configured timezone for a guild"""
        try:
            async with aiosqlite.connect(self.stats_db) as db:
                cursor = await db.execute(
                    "SELECT timezone FROM guild_settings WHERE guild_id = ?",
                    (guild_id,)
                )
                result = await cursor.fetchone()
                return result[0] if result else 'America/New_York'
        except:
            return 'America/New_York'
    
    # ==========================================
    # EVENT LISTENERS
    # ==========================================
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Track message statistics"""
        if message.author.bot or not message.guild:
            return
        
        try:
            current_time = datetime.now(timezone.utc)
            date_str = current_time.strftime("%Y-%m-%d")
            hour = current_time.hour
            
            # Count message properties
            char_count = len(message.content)
            word_count = len(message.content.split())
            attachment_count = len(message.attachments)
            mention_count = len(message.mentions)
            
            async with aiosqlite.connect(self.stats_db) as db:
                await db.execute("""
                    INSERT OR REPLACE INTO message_stats 
                    (guild_id, user_id, channel_id, date, hour, count, characters, words, attachments, mentions)
                    VALUES (?, ?, ?, ?, ?, 
                           COALESCE((SELECT count FROM message_stats WHERE guild_id=? AND user_id=? AND channel_id=? AND date=? AND hour=?), 0) + 1,
                           COALESCE((SELECT characters FROM message_stats WHERE guild_id=? AND user_id=? AND channel_id=? AND date=? AND hour=?), 0) + ?,
                           COALESCE((SELECT words FROM message_stats WHERE guild_id=? AND user_id=? AND channel_id=? AND date=? AND hour=?), 0) + ?,
                           COALESCE((SELECT attachments FROM message_stats WHERE guild_id=? AND user_id=? AND channel_id=? AND date=? AND hour=?), 0) + ?,
                           COALESCE((SELECT mentions FROM message_stats WHERE guild_id=? AND user_id=? AND channel_id=? AND date=? AND hour=?), 0) + ?)
                """, (
                    message.guild.id, message.author.id, message.channel.id, date_str, hour,
                    message.guild.id, message.author.id, message.channel.id, date_str, hour,
                    message.guild.id, message.author.id, message.channel.id, date_str, hour, char_count,
                    message.guild.id, message.author.id, message.channel.id, date_str, hour, word_count,
                    message.guild.id, message.author.id, message.channel.id, date_str, hour, attachment_count,
                    message.guild.id, message.author.id, message.channel.id, date_str, hour, mention_count
                ))
                await db.commit()
                
        except Exception as e:
            print(f"Error tracking message: {e}")
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Track voice statistics"""
        if member.bot:
            return
        
        try:
            current_time = datetime.now(timezone.utc)
            
            # Handle voice session tracking
            if before.channel != after.channel:
                # User left a voice channel
                if before.channel:
                    # Calculate session duration (simplified for now)
                    session_duration = 60  # Default 1 minute for now
                    
                    date_str = current_time.strftime("%Y-%m-%d")
                    hour = current_time.hour
                    
                    async with aiosqlite.connect(self.stats_db) as db:
                        await db.execute("""
                            INSERT OR REPLACE INTO voice_stats 
                            (guild_id, user_id, channel_id, date, hour, duration, duration_minutes)
                            VALUES (?, ?, ?, ?, ?, 
                                   COALESCE((SELECT duration FROM voice_stats WHERE guild_id=? AND user_id=? AND channel_id=? AND date=? AND hour=?), 0) + ?,
                                   COALESCE((SELECT duration_minutes FROM voice_stats WHERE guild_id=? AND user_id=? AND channel_id=? AND date=? AND hour=?), 0) + ?)
                        """, (
                            member.guild.id, member.id, before.channel.id, date_str, hour,
                            member.guild.id, member.id, before.channel.id, date_str, hour, session_duration,
                            member.guild.id, member.id, before.channel.id, date_str, hour, session_duration / 60
                        ))
                        await db.commit()
                        
        except Exception as e:
            print(f"Error tracking voice: {e}")
    
    # ==========================================
    # STATISTICS COMMANDS
    # ==========================================
    
    @commands.group(name="s.", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    async def stats_group(self, ctx):
        """Server statistics - Main overview"""
        await self.show_server_stats(ctx)
    
    async def show_server_stats(self, ctx):
        """Show comprehensive server overview with live stats and charts"""
        loading_embed = discord.Embed(
            title="📊 Loading Comprehensive Server Analytics...",
            description="🔄 Gathering real-time server data and generating charts...",
            color=0x20b2aa  # Teal color
        )
        loading_msg = await ctx.reply(embed=loading_embed)
        
        try:
            current_time = datetime.now(timezone.utc)
            today = current_time.strftime("%Y-%m-%d")
            yesterday = (current_time - timedelta(days=1)).strftime("%Y-%m-%d")
            week_ago = (current_time - timedelta(days=7)).strftime("%Y-%m-%d")
            month_ago = (current_time - timedelta(days=30)).strftime("%Y-%m-%d")
            
            async with aiosqlite.connect(self.stats_db) as db:
                # ==========================================
                # MESSAGE STATISTICS
                # ==========================================
                
                # Today's messages
                cursor = await db.execute("""
                    SELECT SUM(count), SUM(characters), SUM(words), COUNT(DISTINCT user_id), COUNT(DISTINCT channel_id)
                    FROM message_stats WHERE guild_id = ? AND date = ?
                """, (ctx.guild.id, today))
                today_data = await cursor.fetchone()
                messages_today = (today_data[0] if today_data and today_data[0] else 0)
                chars_today = (today_data[1] if today_data and today_data[1] else 0)
                words_today = (today_data[2] if today_data and today_data[2] else 0)
                active_users_today = (today_data[3] if today_data and today_data[3] else 0)
                active_channels_today = (today_data[4] if today_data and today_data[4] else 0)
                
                # Yesterday's messages for comparison
                cursor = await db.execute("""
                    SELECT SUM(count) FROM message_stats 
                    WHERE guild_id = ? AND date = ?
                """, (ctx.guild.id, yesterday))
                result = await cursor.fetchone()
                messages_yesterday = (result[0] if result and result[0] else 0)
                
                # This week's messages
                cursor = await db.execute("""
                    SELECT SUM(count), SUM(characters), SUM(words), COUNT(DISTINCT user_id)
                    FROM message_stats WHERE guild_id = ? AND date >= ?
                """, (ctx.guild.id, week_ago))
                week_data = await cursor.fetchone()
                messages_week = (week_data[0] if week_data and week_data[0] else 0)
                chars_week = (week_data[1] if week_data and week_data[1] else 0)
                words_week = (week_data[2] if week_data and week_data[2] else 0)
                active_users_week = (week_data[3] if week_data and week_data[3] else 0)
                
                # This month's messages
                cursor = await db.execute("""
                    SELECT SUM(count), COUNT(DISTINCT user_id)
                    FROM message_stats WHERE guild_id = ? AND date >= ?
                """, (ctx.guild.id, month_ago))
                month_data = await cursor.fetchone()
                messages_month = (month_data[0] if month_data and month_data[0] else 0)
                active_users_month = (month_data[1] if month_data and month_data[1] else 0)
                
                # All-time messages
                cursor = await db.execute("""
                    SELECT SUM(count), COUNT(DISTINCT user_id), COUNT(DISTINCT date), MIN(date)
                    FROM message_stats WHERE guild_id = ?
                """, (ctx.guild.id,))
                alltime_data = await cursor.fetchone()
                messages_alltime = (alltime_data[0] if alltime_data and alltime_data[0] else 0)
                total_users_tracked = (alltime_data[1] if alltime_data and alltime_data[1] else 0)
                days_tracked = (alltime_data[2] if alltime_data and alltime_data[2] else 0)
                first_tracked_date = (alltime_data[3] if alltime_data and alltime_data[3] else "N/A")
                
                # ==========================================
                # VOICE STATISTICS
                # ==========================================
                
                # Today's voice activity
                cursor = await db.execute("""
                    SELECT SUM(duration_minutes), COUNT(DISTINCT user_id), COUNT(DISTINCT channel_id)
                    FROM voice_stats WHERE guild_id = ? AND date = ?
                """, (ctx.guild.id, today))
                voice_today_data = await cursor.fetchone()
                voice_minutes_today = (voice_today_data[0] if voice_today_data and voice_today_data[0] else 0)
                voice_users_today = (voice_today_data[1] if voice_today_data and voice_today_data[1] else 0)
                voice_channels_today = (voice_today_data[2] if voice_today_data and voice_today_data[2] else 0)
                
                # This week's voice activity
                cursor = await db.execute("""
                    SELECT SUM(duration_minutes), COUNT(DISTINCT user_id)
                    FROM voice_stats WHERE guild_id = ? AND date >= ?
                """, (ctx.guild.id, week_ago))
                voice_week_data = await cursor.fetchone()
                voice_minutes_week = (voice_week_data[0] if voice_week_data and voice_week_data[0] else 0)
                voice_users_week = (voice_week_data[1] if voice_week_data and voice_week_data[1] else 0)
                
                # ==========================================
                # TOP PERFORMERS
                # ==========================================
                
                # Top message sender today
                cursor = await db.execute("""
                    SELECT user_id, SUM(count) as total
                    FROM message_stats WHERE guild_id = ? AND date = ?
                    GROUP BY user_id ORDER BY total DESC LIMIT 1
                """, (ctx.guild.id, today))
                top_messenger_data = await cursor.fetchone()
                
                # Top voice user today
                cursor = await db.execute("""
                    SELECT user_id, SUM(duration_minutes) as total
                    FROM voice_stats WHERE guild_id = ? AND date = ?
                    GROUP BY user_id ORDER BY total DESC LIMIT 1
                """, (ctx.guild.id, today))
                top_voice_data = await cursor.fetchone()
                
                # Most active channel today
                cursor = await db.execute("""
                    SELECT channel_id, SUM(count) as total
                    FROM message_stats WHERE guild_id = ? AND date = ?
                    GROUP BY channel_id ORDER BY total DESC LIMIT 1
                """, (ctx.guild.id, today))
                top_channel_data = await cursor.fetchone()
                
                # Channel activity for heatmap
                cursor = await db.execute("""
                    SELECT channel_id, SUM(count) as total
                    FROM message_stats WHERE guild_id = ? AND date = ?
                    GROUP BY channel_id ORDER BY total DESC LIMIT 10
                """, (ctx.guild.id, today))
                channel_activity_results = await cursor.fetchall()
                channel_activity_data = list(channel_activity_results) if channel_activity_results else []
                
        except Exception as e:
            print(f"[STATS] Database error: {e}")
            error_embed = discord.Embed(
                title="❌ Database Connection Error",
                description=f"Failed to fetch live server statistics.\n```{str(e)}```",
                color=0xef4444
            )
            await loading_msg.edit(embed=error_embed)
            return
        
        # ==========================================
        # PROCESS AND CALCULATE ANALYTICS
        # ==========================================
        
        # Safe data extraction with defaults
        messages_today = (today_data[0] if today_data and today_data[0] else 0)
        chars_today = (today_data[1] if today_data and today_data[1] else 0)
        words_today = (today_data[2] if today_data and today_data[2] else 0)
        active_users_today = (today_data[3] if today_data and today_data[3] else 0)
        active_channels_today = (today_data[4] if today_data and today_data[4] else 0)
        
        # Calculate growth percentages
        msg_growth = 0
        user_growth = 0
        if messages_yesterday > 0:
            msg_growth = ((messages_today - messages_yesterday) / messages_yesterday) * 100
        
        # Calculate activity metrics
        voice_hours_today = voice_minutes_today / 60
        voice_hours_week = voice_minutes_week / 60
        daily_avg_messages = messages_week // 7 if messages_week > 0 else 0
        daily_avg_voice = voice_hours_week / 7 if voice_hours_week > 0 else 0
        
        # Activity score calculation
        server_activity_score = (messages_today * 0.1) + (voice_hours_today * 2) + (active_users_today * 0.5)
        
        # ==========================================
        # BUILD CLEAN STATS EMBED
        # ==========================================
        
        embed = discord.Embed(
            title=f"📊 {ctx.guild.name} - Server Statistics",
            description=f"Real-time server activity • Tracking since **{first_tracked_date}**",
            color=0x20b2aa
        )
        
        # Today's Activity
        growth_indicator = "📈" if msg_growth > 0 else "📉" if msg_growth < 0 else "➡️"
        
        embed.add_field(
            name="� Today",
            value=(
                f"**Messages:** {messages_today:,} {growth_indicator}\n"
                f"**Voice:** {voice_hours_today:.1f}h\n"
                f"**Active Users:** {active_users_today:,}"
            ),
            inline=True
        )
        
        # This Week
        embed.add_field(
            name="📅 This Week",
            value=(
                f"**Messages:** {messages_week:,}\n"
                f"**Daily Avg:** {messages_week // 7:,}\n"
                f"**Active Users:** {active_users_week:,}"
            ),
            inline=True
        )
        
        # Server Info
        embed.add_field(
            name="� Server",
            value=(
                f"**Members:** {ctx.guild.member_count:,}\n"
                f"**Online:** {sum(1 for m in ctx.guild.members if m.status != discord.Status.offline):,}\n"
                f"**Tracking:** {days_tracked:,} days"
            ),
            inline=True
        )
        


        
        # ==========================================
        # FOOTER WITH TIMEZONE
        # ==========================================
        
        # Get guild timezone and format timestamp
        import pytz
        guild_tz = await self.get_guild_timezone(ctx.guild.id)
        try:
            tz = pytz.timezone(guild_tz)
            local_time = current_time.astimezone(tz)
            time_str = local_time.strftime('%I:%M %p')
            tz_abbr = local_time.strftime('%Z')
        except:
            time_str = current_time.strftime('%H:%M')
            tz_abbr = 'UTC'
        
        embed.set_footer(
            text=f"📊 Click 🎨 for canvas • Updated {time_str} {tz_abbr}", 
            icon_url=ctx.bot.user.avatar.url if ctx.bot.user.avatar else None
        )
        
        # Add canvas toggle view
        view = CanvasToggleView(ctx, self, "server_growth")
        
        # Send response
        await loading_msg.edit(embed=embed, view=view)
    
    @stats_group.command(name="m", aliases=["s.m", "messages", "msg"])
    async def message_stats(self, ctx, user: Optional[discord.Member] = None, timeframe: str = "week"):
        """Message statistics for a user"""
        target_user = user or ctx.author
        
        embed = discord.Embed(
            title=f"💬 Message Stats - {target_user.display_name}",
            description=f"Message activity for the past {timeframe}",
            color=0x20b2aa  # Teal color
        )
        
        # Get timeframe data
        current_time = datetime.now(timezone.utc)
        if timeframe == "today":
            start_date = current_time.strftime("%Y-%m-%d")
            end_date = start_date
        elif timeframe == "week":
            end_date = current_time.strftime("%Y-%m-%d")
            start_date = (current_time - timedelta(days=7)).strftime("%Y-%m-%d")
        else:
            end_date = current_time.strftime("%Y-%m-%d")
            start_date = (current_time - timedelta(days=30)).strftime("%Y-%m-%d")
        
        try:
            async with aiosqlite.connect(self.stats_db) as db:
                cursor = await db.execute("""
                    SELECT 
                        SUM(count) as total_messages,
                        SUM(characters) as total_chars,
                        SUM(words) as total_words,
                        COUNT(DISTINCT channel_id) as channels_used,
                        COUNT(DISTINCT date) as active_days
                    FROM message_stats 
                    WHERE guild_id = ? AND user_id = ? AND date BETWEEN ? AND ?
                """, (ctx.guild.id, target_user.id, start_date, end_date))
                
                result = await cursor.fetchone()
                if result:
                    total_messages = result[0] or 0
                    total_chars = result[1] or 0
                    total_words = result[2] or 0
                    channels_used = result[3] or 0
                    active_days = result[4] or 0
                    
                    embed.add_field(
                        name="📊 Message Activity",
                        value=f"**{total_messages:,}** total messages\n"
                              f"**{total_words:,}** words written\n"
                              f"**{channels_used:,}** channels used",
                        inline=True
                    )
                    
                    if total_messages > 0:
                        avg_chars = total_chars / total_messages
                        avg_words = total_words / total_messages
                        
                        embed.add_field(
                            name="📝 Writing Style",
                            value=f"**{avg_chars:.1f}** chars per message\n"
                                  f"**{avg_words:.1f}** words per message\n"
                                  f"**{active_days:,}** active days",
                            inline=True
                        )
                
        except Exception as e:
            embed.add_field(name="❌ Error", value=f"Database error: {str(e)}", inline=False)
        
        embed.set_thumbnail(url=target_user.display_avatar.url)
        view = CanvasToggleView(ctx, self, "user", user=target_user)
        await ctx.reply(embed=embed, view=view)
    
    @stats_group.command(name="v", aliases=["s.v", "voice", "vc"])
    async def voice_stats(self, ctx, user: Optional[discord.Member] = None, timeframe: str = "week"):
        """Voice statistics for a user"""
        target_user = user or ctx.author
        
        embed = discord.Embed(
            title=f"🎤 Voice Stats - {target_user.display_name}",
            description=f"Voice activity for the past {timeframe}",
            color=0x14b8a6  # Darker teal for voice
        )
        
        # Get timeframe data
        current_time = datetime.now(timezone.utc)
        if timeframe == "today":
            start_date = current_time.strftime("%Y-%m-%d")
            end_date = start_date
        elif timeframe == "week":
            end_date = current_time.strftime("%Y-%m-%d")
            start_date = (current_time - timedelta(days=7)).strftime("%Y-%m-%d")
        else:
            end_date = current_time.strftime("%Y-%m-%d")
            start_date = (current_time - timedelta(days=30)).strftime("%Y-%m-%d")
        
        try:
            async with aiosqlite.connect(self.stats_db) as db:
                cursor = await db.execute("""
                    SELECT 
                        SUM(duration_minutes) as total_minutes,
                        COUNT(DISTINCT channel_id) as channels_used,
                        COUNT(DISTINCT date) as active_days
                    FROM voice_stats 
                    WHERE guild_id = ? AND user_id = ? AND date BETWEEN ? AND ?
                """, (ctx.guild.id, target_user.id, start_date, end_date))
                
                result = await cursor.fetchone()
                if result:
                    total_minutes = result[0] or 0
                    total_hours = total_minutes / 60
                    channels_used = result[1] or 0
                    active_days = result[2] or 0
                    
                    embed.add_field(
                        name="🎤 Voice Activity",
                        value=f"**{total_hours:.1f}** hours total\n"
                              f"**{channels_used:,}** channels used\n"
                              f"**{active_days:,}** active days",
                        inline=True
                    )
                    
                    if active_days > 0:
                        avg_per_day = total_hours / active_days
                        embed.add_field(
                            name="📊 Daily Average",
                            value=f"**{avg_per_day:.1f}** hours per day\n"
                                  f"**{total_minutes / max(active_days, 1):.0f}** minutes per day\n"
                                  f"Consistent activity 📈",
                            inline=True
                        )
                
        except Exception as e:
            embed.add_field(name="❌ Error", value=f"Database error: {str(e)}", inline=False)
        
        embed.set_thumbnail(url=target_user.display_avatar.url)
        view = CanvasToggleView(ctx, self, "user", user=target_user)
        await ctx.reply(embed=embed, view=view)
    
    @stats_group.command(name="u", aliases=["s.u", "user"])
    async def user_stats(self, ctx, user: Optional[discord.Member] = None, timeframe: str = "week"):
        """Complete user statistics overview"""
        target_user = user or ctx.author
        
        embed = discord.Embed(
            title=f"👤 User Overview - {target_user.display_name}",
            description=f"Complete activity overview for the past {timeframe}",
            color=0x2dd4bf  # Light teal for user overview
        )
        
        # Get timeframe data
        current_time = datetime.now(timezone.utc)
        if timeframe == "today":
            start_date = current_time.strftime("%Y-%m-%d")
            end_date = start_date
        elif timeframe == "week":
            end_date = current_time.strftime("%Y-%m-%d")
            start_date = (current_time - timedelta(days=7)).strftime("%Y-%m-%d")
        else:
            end_date = current_time.strftime("%Y-%m-%d")
            start_date = (current_time - timedelta(days=30)).strftime("%Y-%m-%d")
        
        try:
            async with aiosqlite.connect(self.stats_db) as db:
                # Message stats
                cursor = await db.execute("""
                    SELECT SUM(count), SUM(words) FROM message_stats 
                    WHERE guild_id = ? AND user_id = ? AND date BETWEEN ? AND ?
                """, (ctx.guild.id, target_user.id, start_date, end_date))
                msg_result = await cursor.fetchone()
                total_messages = (msg_result[0] if msg_result and msg_result[0] else 0)
                total_words = (msg_result[1] if msg_result and msg_result[1] else 0)
                
                # Voice stats
                cursor = await db.execute("""
                    SELECT SUM(duration_minutes) FROM voice_stats 
                    WHERE guild_id = ? AND user_id = ? AND date BETWEEN ? AND ?
                """, (ctx.guild.id, target_user.id, start_date, end_date))
                voice_result = await cursor.fetchone()
                total_voice_minutes = (voice_result[0] if voice_result and voice_result[0] else 0)
                total_voice_hours = total_voice_minutes / 60
                
                # Calculate activity score
                activity_score = (total_messages / 10) + (total_voice_hours * 2)
                
                embed.add_field(
                    name="💬 Messages",
                    value=f"**{total_messages:,}** messages\n**{total_words:,}** words",
                    inline=True
                )
                
                embed.add_field(
                    name="🎤 Voice",
                    value=f"**{total_voice_hours:.1f}** hours\n**{total_voice_minutes:.0f}** minutes",
                    inline=True
                )
                
                embed.add_field(
                    name="📊 Activity Score",
                    value=f"**{activity_score:.1f}** points\n"
                          f"{'🔥 Very Active' if activity_score > 50 else '⚡ Active' if activity_score > 20 else '📊 Moderate' if activity_score > 5 else '🌱 Casual'}",
                    inline=True
                )
                
        except Exception as e:
            embed.add_field(name="❌ Error", value=f"Database error: {str(e)}", inline=False)
        
        embed.set_thumbnail(url=target_user.display_avatar.url)
        view = CanvasToggleView(ctx, self, "user", user=target_user)
        await ctx.reply(embed=embed, view=view)
    
    @stats_group.command(name="c", aliases=["s.c", "charts", "canvas"])
    async def charts_command(self, ctx):
        """Generate various chart types"""
        embed = discord.Embed(
            title="📊 Statistics Charts",
            description="Choose a chart type to generate",
            color=0x20b2aa
        )
        
        embed.add_field(
            name="📈 Available Charts",
            value="• **Message Trends** - Daily message activity\n"
                  "• **Voice Activity** - Voice channel usage\n"
                  "• **Top Users** - Most active members\n"
                  "• **Server Overview** - Complete server canvas",
            inline=False
        )
        
        view = ChartSelectionView(ctx, self)
        await ctx.reply(embed=embed, view=view)
    
    @stats_group.command(name="t", aliases=["s.t", "top", "leaderboard", "lb"])
    async def top_command(self, ctx):
        """Show top members leaderboard"""
        embed = discord.Embed(
            title="🏆 Top Members",
            description="Most active members in the server",
            color=0x20b2aa
        )
        
        try:
            # Get top users from database
            current_time = datetime.now(timezone.utc)
            week_ago = (current_time - timedelta(days=7)).strftime("%Y-%m-%d")
            
            async with aiosqlite.connect(self.stats_db) as db:
                cursor = await db.execute("""
                    SELECT user_id, SUM(count) as total_messages
                    FROM message_stats 
                    WHERE guild_id = ? AND date >= ?
                    GROUP BY user_id
                    ORDER BY total_messages DESC
                    LIMIT 10
                """, (ctx.guild.id, week_ago))
                
                results = await cursor.fetchall()
                
                if results:
                    leaderboard_text = ""
                    for i, (user_id, messages) in enumerate(results, 1):
                        user = ctx.guild.get_member(user_id)
                        if user:
                            emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                            leaderboard_text += f"{emoji} **{user.display_name}** - {messages:,} messages\n"
                    
                    embed.add_field(
                        name="📈 This Week's Top Contributors",
                        value=leaderboard_text or "No data available",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="📈 This Week's Top Contributors", 
                        value="No activity data available yet.",
                        inline=False
                    )
                    
        except Exception as e:
            embed.add_field(name="❌ Error", value=f"Database error: {str(e)}", inline=False)
        
        view = CanvasToggleView(ctx, self, "top_members")
        await ctx.reply(embed=embed, view=view)
    
    @stats_group.command(name="g", aliases=["s.g", "guide", "help"])
    async def guide_command(self, ctx):
        """Statistics system guide"""
        embed = discord.Embed(
            title="📚 Statistics System Guide",
            description="How to use the statistics commands",
            color=0x20b2aa
        )
        
        embed.add_field(
            name="📊 Main Commands",
            value="• `s.` - Server overview (with canvas toggle)\n"
                  "• `s.u @user` - User overview (with canvas toggle)\n"
                  "• `s.m @user` - Message statistics (with canvas)\n"
                  "• `s.v @user` - Voice statistics (with canvas)\n"
                  "• `s.lb` or `s.t` - Leaderboard (with canvas toggle)",
            inline=False
        )
        
        embed.add_field(
            name="🎨 Canvas Feature",
            value="**All commands now have canvas mode!**\n"
                  "• Click **🎨 View Canvas** button on any stat\n"
                  "• Beautiful professional analytics images\n"
                  "• Toggle between text and canvas anytime\n"
                  "• StatBot-inspired professional design",
            inline=False
        )
        
        embed.add_field(
            name="ℹ️ Other Commands",
            value="• `s.c` - Generate various chart types\n"
                  "• `s.g` - This help guide\n"
                  "• `s.p` - Privacy information",
            inline=False
        )
        
        embed.add_field(
            name="💡 Tips",
            value="• All commands have built-in canvas mode\n"
                  "• Stats update in real-time\n"
                  "• Uses your server's timezone\n"
                  "• Click buttons to toggle views",
            inline=False
        )
        
        embed.set_footer(text="Statistics are updated in real-time as members interact!")
        await ctx.reply(embed=embed)
    
    @stats_group.command(name="p", aliases=["s.p", "privacy"])
    async def privacy_command(self, ctx):
        """Privacy policy and data information"""
        embed = discord.Embed(
            title="🔒 Privacy & Data Policy",
            description="How we handle your statistics data",
            color=0x20b2aa
        )
        
        embed.add_field(
            name="📊 Data We Collect",
            value="• Message counts (not content)\n"
                  "• Voice channel time\n"
                  "• Channel activity\n"
                  "• User participation metrics",
            inline=False
        )
        
        embed.add_field(
            name="🛡️ Privacy Protection",
            value="• No message content is stored\n"
                  "• Data is guild-specific only\n"
                  "• No cross-server tracking\n"
                  "• Aggregated statistics only",
            inline=False
        )
        
        embed.add_field(
            name="🗑️ Data Management",
            value="• Statistics reset when bot leaves server\n"
                  "• No personal data sold or shared\n"
                  "• Data used for server insights only\n"
                  "• Contact admins for data questions",
            inline=False
        )
        
        embed.set_footer(text="Your privacy is important to us!")
        await ctx.reply(embed=embed)
    
    # ==========================================
    # HELPER METHODS FOR CANVAS GENERATION
    # ==========================================
    
    async def generate_user_canvas_buffer(self, ctx, target_user):
        """Helper method to generate user stats canvas"""
        if not self.canvas_generator:
            return None
            
        try:
            # Get guild timezone
            guild_tz = await self.get_guild_timezone(ctx.guild.id)
            canvas_gen = StatBotCanvasCV2(timezone=guild_tz)
            
            current_time = datetime.now(timezone.utc)
            today = current_time.strftime("%Y-%m-%d")
            week_ago = (current_time - timedelta(days=7)).strftime("%Y-%m-%d")
            two_weeks_ago = (current_time - timedelta(days=14)).strftime("%Y-%m-%d")
            
            async with aiosqlite.connect(self.stats_db) as db:
                # Get message stats for different timeframes
                cursor = await db.execute("""
                    SELECT SUM(count) FROM message_stats 
                    WHERE guild_id = ? AND user_id = ? AND date = ?
                """, (ctx.guild.id, target_user.id, today))
                result = await cursor.fetchone()
                msg_1d = result[0] if result and result[0] else 0
                
                cursor = await db.execute("""
                    SELECT SUM(count) FROM message_stats 
                    WHERE guild_id = ? AND user_id = ? AND date >= ?
                """, (ctx.guild.id, target_user.id, week_ago))
                result = await cursor.fetchone()
                msg_7d = result[0] if result and result[0] else 0
                
                cursor = await db.execute("""
                    SELECT SUM(count) FROM message_stats 
                    WHERE guild_id = ? AND user_id = ? AND date >= ?
                """, (ctx.guild.id, target_user.id, two_weeks_ago))
                result = await cursor.fetchone()
                msg_14d = result[0] if result and result[0] else 0
                
                # Get voice stats
                cursor = await db.execute("""
                    SELECT SUM(duration_minutes) FROM voice_stats 
                    WHERE guild_id = ? AND user_id = ? AND date = ?
                """, (ctx.guild.id, target_user.id, today))
                result = await cursor.fetchone()
                voice_1d = (result[0] if result and result[0] else 0) / 60  # Convert to hours
                
                cursor = await db.execute("""
                    SELECT SUM(duration_minutes) FROM voice_stats 
                    WHERE guild_id = ? AND user_id = ? AND date >= ?
                """, (ctx.guild.id, target_user.id, week_ago))
                result = await cursor.fetchone()
                voice_7d = (result[0] if result and result[0] else 0) / 60
                
                cursor = await db.execute("""
                    SELECT SUM(duration_minutes) FROM voice_stats 
                    WHERE guild_id = ? AND user_id = ? AND date >= ?
                """, (ctx.guild.id, target_user.id, two_weeks_ago))
                result = await cursor.fetchone()
                voice_14d = (result[0] if result and result[0] else 0) / 60
                
                # Get user rank
                cursor = await db.execute("""
                    SELECT user_id, SUM(count) as total
                    FROM message_stats
                    WHERE guild_id = ? AND date >= ?
                    GROUP BY user_id
                    ORDER BY total DESC
                """, (ctx.guild.id, two_weeks_ago))
                rankings = await cursor.fetchall()
                msg_rank = next((i+1 for i, (uid, _) in enumerate(rankings) if uid == target_user.id), "N/A")
                
                # Get voice rank
                cursor = await db.execute("""
                    SELECT user_id, SUM(duration_minutes) as total
                    FROM voice_stats
                    WHERE guild_id = ? AND date >= ?
                    GROUP BY user_id
                    ORDER BY total DESC
                """, (ctx.guild.id, two_weeks_ago))
                voice_rankings = await cursor.fetchall()
                voice_rank = next((i+1 for i, (uid, _) in enumerate(voice_rankings) if uid == target_user.id), "No Data")
                
                # Get top channel
                cursor = await db.execute("""
                    SELECT channel_id, SUM(count) as total
                    FROM message_stats
                    WHERE guild_id = ? AND user_id = ? AND date >= ?
                    GROUP BY channel_id
                    ORDER BY total DESC
                    LIMIT 1
                """, (ctx.guild.id, target_user.id, two_weeks_ago))
                top_channel_data = await cursor.fetchone()
                if top_channel_data:
                    channel = ctx.guild.get_channel(top_channel_data[0])
                    top_channel = {
                        'name': channel.name if channel else 'Unknown Channel',
                        'messages': top_channel_data[1]
                    }
                else:
                    top_channel = {'name': 'No data', 'messages': 0}
                
                # Get message trend (last 14 days)
                cursor = await db.execute("""
                    SELECT date, SUM(count) as daily_total
                    FROM message_stats
                    WHERE guild_id = ? AND user_id = ? AND date >= ?
                    GROUP BY date
                    ORDER BY date ASC
                """, (ctx.guild.id, target_user.id, two_weeks_ago))
                trend_data = await cursor.fetchall()
                
                # Fill in missing days with 0
                import numpy as np
                message_trend = np.zeros(14)
                for date_str, count in trend_data:
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                    days_ago = (current_time.date() - date_obj.date()).days
                    if 0 <= days_ago < 14:
                        message_trend[13 - days_ago] = count
            
            # Prepare user data for canvas
            user_data = {
                'username': target_user.display_name,
                'discriminator': target_user.discriminator if target_user.discriminator != "0" else "",
                'created_at': target_user.created_at.strftime("%B %d, %Y"),
                'joined_at': target_user.joined_at.strftime("%B %d, %Y") if target_user.joined_at else "Unknown",
                'message_rank': msg_rank,
                'voice_rank': voice_rank,
                'messages_1d': msg_1d,
                'messages_7d': msg_7d,
                'messages_14d': msg_14d,
                'voice_1d': voice_1d,
                'voice_7d': voice_7d,
                'voice_14d': voice_14d,
                'top_channel': top_channel,
                'message_trend': message_trend,
                'voice_trend': np.zeros(14)  # Placeholder for voice trend
            }
            
            # Generate canvas
            canvas_buffer = await canvas_gen.generate_user_stats_canvas(
                user_data, ctx.guild.name
            )
            return canvas_buffer
                
        except Exception as e:
            print(f"[STATS] Error generating user canvas: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def generate_top_members_canvas_buffer(self, ctx):
        """Helper method to generate top members canvas"""
        if not self.canvas_generator:
            return None
            
        try:
            # Get guild timezone
            guild_tz = await self.get_guild_timezone(ctx.guild.id)
            canvas_gen = StatBotCanvasCV2(timezone=guild_tz)
            current_time = datetime.now(timezone.utc)
            two_weeks_ago = (current_time - timedelta(days=14)).strftime("%Y-%m-%d")
            
            async with aiosqlite.connect(self.stats_db) as db:
                # Get top 20 members
                cursor = await db.execute("""
                    SELECT user_id, SUM(count) as total_messages
                    FROM message_stats
                    WHERE guild_id = ? AND date >= ?
                    GROUP BY user_id
                    ORDER BY total_messages DESC
                    LIMIT 20
                """, (ctx.guild.id, two_weeks_ago))
                top_users = await cursor.fetchall()
                
                members_data = []
                for user_id, messages in top_users:
                    member = ctx.guild.get_member(user_id)
                    if member:
                        members_data.append({
                            'name': member.display_name,
                            'messages': messages
                        })
            
            # Prepare data for canvas
            canvas_data = {
                'members': members_data
            }
            
            # Generate canvas
            canvas_buffer = await canvas_gen.generate_top_members_canvas(
                ctx.guild.name, canvas_data
            )
            return canvas_buffer
                
        except Exception as e:
            print(f"[STATS] Error generating top members canvas: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def generate_server_growth_canvas_buffer(self, ctx):
        """Helper method to generate server growth canvas"""
        if not self.canvas_generator:
            return None
            
        try:
            # Get guild timezone
            guild_tz = await self.get_guild_timezone(ctx.guild.id)
            canvas_gen = StatBotCanvasCV2(timezone=guild_tz)
            import numpy as np
            
            # Get bot stats
            servers = len(self.bot.guilds)
            members = sum(g.member_count for g in self.bot.guilds if g.member_count)
            text_channels = len([c for c in self.bot.get_all_channels() if isinstance(c, discord.TextChannel)])
            voice_channels = len([c for c in self.bot.get_all_channels() if isinstance(c, discord.VoiceChannel)])
            
            current_time = datetime.now(timezone.utc)
            thirty_days_ago = (current_time - timedelta(days=30)).strftime("%Y-%m-%d")
            
            async with aiosqlite.connect(self.stats_db) as db:
                # Get message trend for last 30 days
                cursor = await db.execute("""
                    SELECT date, SUM(count) as daily_total
                    FROM message_stats
                    WHERE guild_id = ? AND date >= ?
                    GROUP BY date
                    ORDER BY date ASC
                """, (ctx.guild.id, thirty_days_ago))
                message_trend_data = await cursor.fetchall()
                
                # Fill in trend data
                messages_trend = np.random.randint(20000, 50000, 30)  # Placeholder
                trend_list = list(message_trend_data)
                if trend_list:
                    for i, (date_str, count) in enumerate(trend_list[-30:]):
                        if i < 30:
                            messages_trend[i] = count
                
                total_messages = sum(messages_trend)
            
            # Prepare analytics data
            analytics_data = {
                'servers': servers,
                'members': members,
                'text_channels': text_channels,
                'voice_channels': voice_channels,
                'dates': list(range(30)),
                'commands_trend': np.random.randint(200, 600, 30),  # Would need command tracking
                'total_commands': np.random.randint(5000, 10000),
                'messages_trend': messages_trend,
                'total_messages': total_messages,
                'uptime': '1 day ago',
                'analysis_period': '30 days'
            }
            
            # Generate canvas
            canvas_buffer = await canvas_gen.generate_server_growth_canvas(
                ctx.guild.name, analytics_data
            )
            return canvas_buffer
                
        except Exception as e:
            print(f"[STATS] Error generating growth analytics: {e}")
            import traceback
            traceback.print_exc()
            return None


# ==========================================
# VIEW CLASSES FOR UI
# ==========================================

class StatsNavigationView(discord.ui.View):
    def __init__(self, ctx, cog):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.cog = cog

    @discord.ui.select(
        placeholder="📊 Choose statistics category",
        options=[
            discord.SelectOption(label="Server Overview", value="server", emoji="🏠"),
            discord.SelectOption(label="Message Stats", value="messages", emoji="💬"),
            discord.SelectOption(label="Voice Stats", value="voice", emoji="🎤"),
            discord.SelectOption(label="User Stats", value="user", emoji="👤"),
        ]
    )
    async def stats_dropdown(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ Only the command user can use this!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        category = select.values[0]
        
        if category == "server":
            await self.cog.show_server_stats(self.ctx)
        elif category == "messages":
            await self.cog.message_stats(self.ctx)
        elif category == "voice":
            await self.cog.voice_stats(self.ctx)
        elif category == "user":
            await self.cog.user_stats(self.ctx)

    @discord.ui.button(label="🎨 Canvas Mode", style=discord.ButtonStyle.primary)
    async def canvas_mode_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ Only the command user can use this!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        # Generate StatBot-style server canvas
        try:
            stats_data = {
                'member_count': self.ctx.guild.member_count,
                'messages_today': 1500,  # Placeholder
                'voice_hours_today': 25.5,  # Placeholder
                'active_users_today': 45,  # Placeholder
                'messages_week': 12000,  # Placeholder
                'growth_rate': 5.2  # Placeholder
            }
            
            canvas_buffer = await self.cog.chart_generator.generate_server_overview(
                self.ctx.guild.name, stats_data
            )
            
            if canvas_buffer:
                file = discord.File(canvas_buffer, filename="server_overview.png")
                
                canvas_embed = discord.Embed(
                    title="🎨 Server Overview Canvas",
                    description=f"**{self.ctx.guild.name}** - StatBot Style Overview",
                    color=0x20b2aa  # Teal color
                )
                canvas_embed.set_image(url="attachment://server_overview.png")
                
                await interaction.edit_original_response(embed=canvas_embed, attachments=[file], view=self)
            else:
                await interaction.edit_original_response(
                    content="❌ Canvas generation failed - charts not available", view=self
                )
                
        except Exception as e:
            await interaction.edit_original_response(
                content=f"❌ Canvas generation error: {str(e)}", view=self
            )


class UserStatsView(discord.ui.View):
    def __init__(self, ctx, cog, user, timeframe, stat_type):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.cog = cog
        self.user = user
        self.timeframe = timeframe
        self.stat_type = stat_type

    @discord.ui.select(
        placeholder="📊 Choose timeframe",
        options=[
            discord.SelectOption(label="Today", value="today", emoji="📅"),
            discord.SelectOption(label="This Week", value="week", emoji="📆"),
            discord.SelectOption(label="This Month", value="month", emoji="🗓️"),
        ]
    )
    async def timeframe_dropdown(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ Only the command user can use this!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        new_timeframe = select.values[0]
        
        if self.stat_type == "messages":
            await self.cog.message_stats(self.ctx, self.user, new_timeframe)
        elif self.stat_type == "voice":
            await self.cog.voice_stats(self.ctx, self.user, new_timeframe)
        elif self.stat_type == "user":
            await self.cog.user_stats(self.ctx, self.user, new_timeframe)

    @discord.ui.button(label="🎨 Generate Image", style=discord.ButtonStyle.primary)
    async def generate_image_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ Only the command user can use this!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        # Generate user stats image
        try:
            stats_data = {
                'total_messages': 2500,  # Placeholder - would get from database
                'voice_hours': 15.5,
                'rank': 5,
                'activity_score': 87.3
            }
            
            image_buffer = await self.cog.chart_generator.generate_user_stats(
                self.user.display_name, stats_data
            )
            
            if image_buffer:
                file = discord.File(image_buffer, filename="user_stats.png")
                
                image_embed = discord.Embed(
                    title=f"🎨 {self.user.display_name} - StatBot Style",
                    description=f"Visual statistics for {self.timeframe}",
                    color=0x20b2aa  # Teal color
                )
                image_embed.set_image(url="attachment://user_stats.png")
                
                await interaction.edit_original_response(embed=image_embed, attachments=[file], view=self)
            else:
                await interaction.edit_original_response(
                    content="❌ Image generation failed - charts not available", view=self
                )
                
        except Exception as e:
            await interaction.edit_original_response(
                content=f"❌ Image generation error: {str(e)}", view=self
            )


class ChartSelectionView(discord.ui.View):
    def __init__(self, ctx, cog):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.cog = cog

    @discord.ui.select(
        placeholder="📊 Choose chart type to generate",
        options=[
            discord.SelectOption(label="Message Trends", value="trends", emoji="📈"),
            discord.SelectOption(label="Voice Activity", value="voice", emoji="🎤"),
            discord.SelectOption(label="Top Users", value="topusers", emoji="🏆"),
            discord.SelectOption(label="Server Overview", value="overview", emoji="🏠"),
        ]
    )
    async def chart_dropdown(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ Only the command user can use this!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        chart_type = select.values[0]
        
        try:
            if chart_type == "trends":
                trend_data = {'daily_messages': [120, 150, 180, 200, 170, 160, 140]}
                buffer = await self.cog.chart_generator.generate_message_trends(
                    self.ctx.guild.name, trend_data
                )
                title = "📈 Message Trends"
                filename = "message_trends.png"
                
            elif chart_type == "voice":
                voice_data = {
                    'daily_hours': [15.5, 20.2, 18.7, 25.3, 22.1, 28.5, 24.8],
                    'top_channels': ['General', 'Gaming', 'Music', 'Study'],
                    'channel_hours': [45, 30, 25, 15]
                }
                buffer = await self.cog.chart_generator.generate_voice_activity(
                    self.ctx.guild.name, voice_data
                )
                title = "🎤 Voice Activity"
                filename = "voice_activity.png"
                
            elif chart_type == "topusers":
                user_data = {
                    'usernames': ['User1', 'User2', 'User3', 'User4', 'User5'],
                    'activity_scores': [95, 87, 82, 78, 74]
                }
                buffer = await self.cog.chart_generator.generate_top_users(
                    self.ctx.guild.name, user_data
                )
                title = "🏆 Top Active Users"
                filename = "top_users.png"
                
            elif chart_type == "overview":
                stats_data = {
                    'member_count': self.ctx.guild.member_count,
                    'messages_today': 1500,
                    'voice_hours_today': 25.5,
                    'active_users_today': 45,
                    'messages_week': 12000,
                    'growth_rate': 5.2
                }
                buffer = await self.cog.chart_generator.generate_server_overview(
                    self.ctx.guild.name, stats_data
                )
                title = "🏠 Server Overview"
                filename = "server_overview.png"
            
            if buffer:
                file = discord.File(buffer, filename=filename)
                
                chart_embed = discord.Embed(
                    title=title,
                    description=f"**{self.ctx.guild.name}** - Generated Chart",
                    color=0x20b2aa
                )
                chart_embed.set_image(url=f"attachment://{filename}")
                
                await interaction.edit_original_response(embed=chart_embed, attachments=[file], view=self)
            else:
                await interaction.edit_original_response(
                    content="❌ Chart generation failed - matplotlib not available", view=self
                )
                
        except Exception as e:
            await interaction.edit_original_response(
                content=f"❌ Chart generation error: {str(e)}", view=self
            )


class TopUsersView(discord.ui.View):
    def __init__(self, ctx, cog):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.cog = cog

    @discord.ui.select(
        placeholder="🏆 Choose leaderboard type",
        options=[
            discord.SelectOption(label="Messages This Week", value="messages_week", emoji="💬"),
            discord.SelectOption(label="Voice This Week", value="voice_week", emoji="🎤"),
            discord.SelectOption(label="Overall Activity", value="overall", emoji="⚡"),
        ]
    )
    async def leaderboard_dropdown(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ Only the command user can use this!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        board_type = select.values[0]
        
        embed = discord.Embed(
            title="🏆 Top Members",
            color=0x20b2aa
        )
        
        try:
            current_time = datetime.now(timezone.utc)
            week_ago = (current_time - timedelta(days=7)).strftime("%Y-%m-%d")
            
            async with aiosqlite.connect(self.cog.stats_db) as db:
                if board_type == "messages_week":
                    cursor = await db.execute("""
                        SELECT user_id, SUM(count) as total
                        FROM message_stats 
                        WHERE guild_id = ? AND date >= ?
                        GROUP BY user_id
                        ORDER BY total DESC
                        LIMIT 10
                    """, (self.ctx.guild.id, week_ago))
                    embed.description = "Most messages sent this week"
                    
                elif board_type == "voice_week":
                    cursor = await db.execute("""
                        SELECT user_id, SUM(duration_minutes) as total
                        FROM voice_stats 
                        WHERE guild_id = ? AND date >= ?
                        GROUP BY user_id
                        ORDER BY total DESC
                        LIMIT 10
                    """, (self.ctx.guild.id, week_ago))
                    embed.description = "Most voice time this week"
                    
                else:  # overall
                    # Combine message and voice stats for activity score
                    cursor = await db.execute("""
                        SELECT 
                            COALESCE(m.user_id, v.user_id) as user_id,
                            COALESCE(SUM(m.count), 0) as messages,
                            COALESCE(SUM(v.duration_minutes), 0) as voice_minutes
                        FROM 
                            (SELECT user_id, SUM(count) as count FROM message_stats WHERE guild_id = ? AND date >= ? GROUP BY user_id) m
                        FULL OUTER JOIN 
                            (SELECT user_id, SUM(duration_minutes) as duration_minutes FROM voice_stats WHERE guild_id = ? AND date >= ? GROUP BY user_id) v
                        ON m.user_id = v.user_id
                        ORDER BY (COALESCE(messages, 0) + COALESCE(voice_minutes, 0) * 2) DESC
                        LIMIT 10
                    """, (self.ctx.guild.id, week_ago, self.ctx.guild.id, week_ago))
                    embed.description = "Overall activity score this week"
                
                results = await cursor.fetchall()
                
                if results:
                    leaderboard_text = ""
                    for i, result in enumerate(results, 1):
                        user_id = result[0]
                        user = self.ctx.guild.get_member(user_id)
                        if user:
                            emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                            
                            if board_type == "messages_week":
                                value = f"{result[1]:,} messages"
                            elif board_type == "voice_week":
                                hours = result[1] / 60
                                value = f"{hours:.1f} hours"
                            else:  # overall
                                messages = result[1] if len(result) > 1 else 0
                                voice_minutes = result[2] if len(result) > 2 else 0
                                score = messages + (voice_minutes * 2)
                                value = f"{score:.0f} points"
                            
                            leaderboard_text += f"{emoji} **{user.display_name}** - {value}\n"
                    
                    embed.add_field(
                        name="📊 Rankings",
                        value=leaderboard_text or "No data available",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="📊 Rankings", 
                        value="No activity data available yet.",
                        inline=False
                    )
                    
        except Exception as e:
            embed.add_field(name="❌ Error", value=f"Database error: {str(e)}", inline=False)
        
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="🎨 Generate Leaderboard Image", style=discord.ButtonStyle.primary)
    async def generate_leaderboard_image(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ Only the command user can use this!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            user_data = {
                'usernames': ['User1', 'User2', 'User3', 'User4', 'User5'],
                'activity_scores': [95, 87, 82, 78, 74]
            }
            
            buffer = await self.cog.chart_generator.generate_top_users(
                self.ctx.guild.name, user_data
            )
            
            if buffer:
                file = discord.File(buffer, filename="leaderboard.png")
                
                image_embed = discord.Embed(
                    title="🏆 Top Members Leaderboard",
                    description=f"**{self.ctx.guild.name}** - Visual Leaderboard",
                    color=0x20b2aa
                )
                image_embed.set_image(url="attachment://leaderboard.png")
                
                await interaction.edit_original_response(embed=image_embed, attachments=[file], view=self)
            else:
                await interaction.edit_original_response(
                    content="❌ Leaderboard image generation failed", view=self
                )
                
        except Exception as e:
            await interaction.edit_original_response(
                content=f"❌ Image generation error: {str(e)}", view=self
            )


# ==========================================
# NEW CANVAS TOGGLE VIEWS
# ==========================================

class CanvasToggleView(discord.ui.View):
    """Generic view for toggling between text and canvas modes"""
    def __init__(self, ctx, cog, canvas_type, **kwargs):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.cog = cog
        self.canvas_type = canvas_type
        self.kwargs = kwargs  # Store any additional parameters
        
    @discord.ui.button(label="🎨 View Canvas", style=discord.ButtonStyle.primary, custom_id="show_canvas")
    async def show_canvas_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ Only the command user can use this!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        loading_embed = discord.Embed(
            title="🎨 Generating Canvas...",
            description="Creating professional analytics image...",
            color=0x20b2aa
        )
        await interaction.edit_original_response(embed=loading_embed, view=None, attachments=[])
        
        try:
            canvas_buffer = None
            
            if self.canvas_type == "user":
                target_user = self.kwargs.get('user', self.ctx.author)
                canvas_buffer = await self.cog.generate_user_canvas_buffer(self.ctx, target_user)
                filename = "user_stats.png"
                title = f"📊 {target_user.display_name}'s Statistics"
                
            elif self.canvas_type == "top_members":
                canvas_buffer = await self.cog.generate_top_members_canvas_buffer(self.ctx)
                filename = "top_members.png"
                title = f"🏆 {self.ctx.guild.name} - Top Members"
                
            elif self.canvas_type == "server_growth":
                canvas_buffer = await self.cog.generate_server_growth_canvas_buffer(self.ctx)
                filename = "growth_analytics.png"
                title = f"📈 {self.ctx.guild.name} - Growth Analytics"
            
            if canvas_buffer:
                file = discord.File(canvas_buffer, filename=filename)
                embed = discord.Embed(
                    title=title,
                    color=0x20b2aa
                )
                embed.set_image(url=f"attachment://{filename}")
                embed.set_footer(text="Click 'View Text' to return to text stats")
                
                # Create new view with back button
                back_view = CanvasBackView(self.ctx, self.cog, self.canvas_type, **self.kwargs)
                await interaction.edit_original_response(embed=embed, attachments=[file], view=back_view)
            else:
                await interaction.edit_original_response(
                    content="❌ Canvas generation is not available. Install matplotlib and numpy.",
                    view=self
                )
                
        except Exception as e:
            print(f"[STATS] Canvas toggle error: {e}")
            await interaction.edit_original_response(
                content=f"❌ Error generating canvas: {str(e)}",
                view=self
            )


class CanvasBackView(discord.ui.View):
    """View for going back from canvas to text mode"""
    def __init__(self, ctx, cog, canvas_type, **kwargs):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.cog = cog
        self.canvas_type = canvas_type
        self.kwargs = kwargs
        
    @discord.ui.button(label="📊 View Text", style=discord.ButtonStyle.secondary, custom_id="show_text")
    async def show_text_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ Only the command user can use this!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        # Redirect back to the original text command
        try:
            if self.canvas_type == "user":
                target_user = self.kwargs.get('user', self.ctx.author)
                await self.cog.user_stats(self.ctx, target_user)
            elif self.canvas_type == "top_members":
                await self.cog.top_command(self.ctx)
            elif self.canvas_type == "server_growth":
                await self.cog.show_server_stats(self.ctx)
        except Exception as e:
            await interaction.edit_original_response(
                content=f"❌ Error: {str(e)}"
            )


async def setup(bot):
    await bot.add_cog(ComprehensiveStats(bot))