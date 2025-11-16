import discord
from discord.ext import commands
import aiosqlite
import asyncio
import math
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
import logging
import json
import os
import traceback

from core.sleepless import sleepless
from utils.error_logger import ErrorLogger
from utils.Tools import blacklist_check, ignore_check
from utils.dynamic_dropdowns import PaginatedChannelView
from utils.timezone_helpers import get_timezone_helpers

# Setup logger - will be initialized when bot is available
logger = None

# Complete emoji set for leveling system - using your custom emojis
emojis = {
    # Status emojis
    'success': '<:feast_tick:1400143469892210753>',
    'error': '<:feast_cross:1400143488695144609>',
    'warning': '<:feast_warning:1400143131990560830>',
    'check': '<:feast_tick:1400143469892210753>',
    'x': '<:feast_cross:1400143488695144609>',
    
    # Level/achievement emojis
    'trophy': '<:trophy:1428163126360146034>',
    'crown': '<:crown:1428163104281092197>',
    'medal': '<:medal:1428164666079088722>',
    'diamond': '<:diamond:1428164611989774377>',
    'star': '<:star:1428199524722675753>',
    'sparkles': '<:sparkles:1428199568309362859>',
    
    # Progress/action emojis
    'zap': '<:zap:1428199612799692841>',
    'fire': '<:fire:1428199557685485668>',
    'rocket': '<:rocket:1428199539553390713>',
    'target': '<:target:1428199501212139550>',
    'confetti': '<:confetti:1428199487651893323>',
    'party': '<:party:1428199474054418496>',
    
    # System/settings emojis
    'settings': '<:Feast_Utility:1400135926298185769>',
    'cog': '<:cog:1428163115136057486>',
    'gear': '<:gear:1428163099428020295>',
    
    # Number emojis for rankings
    'first': '<:first:1428164689919524905>',
    'second': '<:second:1428164705946079252>',
    'third': '<:third:1428164720982802443>',
    
    # Other useful emojis
    'plus': '<:feast_plus:1400142875483836547>',
    'minus': '<:feast_minus:1400142863433990184>',
    'edit': '<:feast_plus:1400142875483836547>',
    'list': '<:web:1428162947187736679>',
    'time': '<:feast_age:1400142030205878274>',
    'role': '🎭',
    'boost': '📈',
    'channel': '#️⃣',
}

# Database path
DB_PATH = "db/leveling.db"

class LevelingSystem(commands.Cog):
    """🏆 Advanced Leveling System - Track XP, levels, and reward roles"""
    
    def __init__(self, bot: sleepless):
        self.bot = bot
        self.xp_cooldowns = {}  # Track XP cooldowns per user
        self.level_up_cooldowns = {}  # Track level up notifications
        self.error_logger = ErrorLogger(bot)  # Initialize Discord error logger
        self.tz_helpers = get_timezone_helpers(bot)  # Initialize timezone helpers
        
    async def cog_load(self):
        """Called when the cog is loaded"""
        await self.ensure_leveling_db()
        
    @staticmethod
    def safe_json_loads(json_string: str, default_value):
        """Safely parse JSON strings with fallback to default value"""
        if not json_string or json_string in ['exclude_channels', 'exclude_roles', 'no_xp_roles', 'multiplier_roles']:
            return default_value
        try:
            return json.loads(json_string)
        except (json.JSONDecodeError, TypeError, ValueError):
            return default_value
        
    @staticmethod
    async def ensure_leveling_db():
        """Ensure all leveling database tables exist"""
        try:
            # Ensure the db directory exists
            import os
            os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
            
            async with aiosqlite.connect(DB_PATH) as db:
                # First, check if table exists and what columns it has
                cursor = await db.execute("PRAGMA table_info(guild_level_settings)")
                existing_columns = [row[1] for row in await cursor.fetchall()]
                print(f"[LEVELING] Existing columns: {existing_columns}")
                
                # Create table if it doesn't exist
                # User levels table
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS user_levels (
                        user_id INTEGER,
                        guild_id INTEGER,
                        xp INTEGER DEFAULT 0,
                        level INTEGER DEFAULT 0,
                        total_xp INTEGER DEFAULT 0,
                        messages_sent INTEGER DEFAULT 0,
                        last_xp_gain TEXT,
                        PRIMARY KEY (user_id, guild_id)
                    )
                """)
                
                # Guild settings table
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS guild_level_settings (
                        guild_id INTEGER PRIMARY KEY,
                        enabled BOOLEAN DEFAULT 0,
                        xp_per_message INTEGER DEFAULT 15,
                        xp_variance INTEGER DEFAULT 10,
                        level_up_channel_id INTEGER,
                        level_up_message TEXT DEFAULT 'Congratulations {user}! You reached **Level {level}**! 🎉',
                        dm_level_ups BOOLEAN DEFAULT 0,
                        level_formula TEXT DEFAULT 'default',
                        stack_roles BOOLEAN DEFAULT 0,
                        remove_previous_roles BOOLEAN DEFAULT 1,
                        xp_cooldown INTEGER DEFAULT 60,
                        exclude_channels TEXT DEFAULT '[]',
                        exclude_roles TEXT DEFAULT '[]',
                        multiplier_roles TEXT DEFAULT '{}',
                        no_xp_roles TEXT DEFAULT '[]'
                    )
                """)
                
                # Level roles table
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS level_roles (
                        guild_id INTEGER,
                        level INTEGER,
                        role_id INTEGER,
                        PRIMARY KEY (guild_id, level, role_id)
                    )
                """)
                
                await db.commit()
                
                # Migration: Add missing columns if they don't exist
                required_columns = {
                    'xp_per_message': 'INTEGER DEFAULT 15',
                    'xp_variance': 'INTEGER DEFAULT 10',
                    'level_up_channel_id': 'INTEGER',
                    'level_up_message': 'TEXT DEFAULT "Congratulations {user}! You reached **Level {level}**! 🎉"',
                    'dm_level_ups': 'BOOLEAN DEFAULT 0',
                    'level_formula': 'TEXT DEFAULT "default"',
                    'stack_roles': 'BOOLEAN DEFAULT 0',
                    'remove_previous_roles': 'BOOLEAN DEFAULT 1',
                    'xp_cooldown': 'INTEGER DEFAULT 60',
                    'exclude_channels': 'TEXT DEFAULT "[]"',
                    'exclude_roles': 'TEXT DEFAULT "[]"',
                    'multiplier_roles': 'TEXT DEFAULT "{}"',
                    'no_xp_roles': 'TEXT DEFAULT "[]"'
                }
                
                for column, definition in required_columns.items():
                    if column not in existing_columns:
                        try:
                            await db.execute(f"ALTER TABLE guild_level_settings ADD COLUMN {column} {definition}")
                            print(f"[LEVELING] Added missing column: {column}")
                        except Exception as e:
                            print(f"[LEVELING] Column {column} migration failed: {e}")
                
                await db.commit()
                print("[LEVELING] Database tables initialized successfully")
        except Exception as e:
            print(f"[LEVELING ERROR] Failed to initialize database: {e}")
            print(f"[LEVELING ERROR] Traceback: {traceback.format_exc()}")
            # Re-raise the exception so main.py can catch it and log to Discord
            raise

    def calculate_level_from_xp(self, xp: int, formula: str = "default") -> int:
        """Calculate level from total XP using specified formula"""
        if xp <= 0:
            return 0
            
        if formula == "default":
            # Default formula: level = sqrt(xp / 1000)
            return int(math.sqrt(xp / 1000))
        elif formula == "linear":
            # Linear formula: level = xp / 5000
            return int(xp / 5000)
        elif formula == "exponential":
            # Exponential formula: more XP needed per level
            return int(math.log(xp / 100 + 1) * 10)
        else:
            return int(math.sqrt(xp / 1000))

    def calculate_xp_for_level(self, level: int, formula: str = "default") -> int:
        """Calculate total XP needed for a specific level"""
        if level <= 0:
            return 0
            
        if formula == "default":
            return int(level ** 2 * 1000)
        elif formula == "linear":
            return int(level * 5000)
        elif formula == "exponential":
            return int((math.exp(level / 10) - 1) * 100)
        else:
            return int(level ** 2 * 1000)

    def calculate_xp_for_next_level(self, current_level: int, formula: str = "default") -> int:
        """Calculate XP needed for next level"""
        return self.calculate_xp_for_level(current_level + 1, formula)

    async def get_guild_settings(self, guild_id: int) -> Dict[str, Any]:
        """Get guild leveling settings"""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute(
                    "SELECT * FROM guild_level_settings WHERE guild_id = ?",
                    (guild_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    
                    if row:
                        columns = [desc[0] for desc in cursor.description]
                        raw_settings = dict(zip(columns, row))
                        
                        # Map database columns to expected code format
                        settings = {
                            'guild_id': raw_settings.get('guild_id'),
                            'enabled': bool(raw_settings.get('enabled', False)),
                            'xp_per_message': raw_settings.get('xp_per_message', raw_settings.get('xp_per_message_min', 15)),
                            'xp_variance': raw_settings.get('xp_variance', 
                                abs(raw_settings.get('xp_per_message_max', 25) - raw_settings.get('xp_per_message_min', 15)) // 2 if 
                                raw_settings.get('xp_per_message_max') and raw_settings.get('xp_per_message_min') else 10),
                            'level_up_channel_id': raw_settings.get('level_up_channel_id', raw_settings.get('level_channel_id')),
                            'level_up_message': raw_settings.get('level_up_message', raw_settings.get('level_message', 'Congratulations {user}! You reached **Level {level}**! 🎉')),
                            'dm_level_ups': bool(raw_settings.get('dm_level_ups', raw_settings.get('send_dm', False))),
                            'level_formula': raw_settings.get('level_formula', 'default'),
                            'stack_roles': bool(raw_settings.get('stack_roles', False)),
                            'remove_previous_roles': bool(raw_settings.get('remove_previous_roles', True)),
                            'xp_cooldown': raw_settings.get('xp_cooldown', 60),
                            'exclude_channels': raw_settings.get('exclude_channels', '[]'),
                            'exclude_roles': raw_settings.get('exclude_roles', '[]'),
                            'multiplier_roles': raw_settings.get('multiplier_roles', '{}'),
                            'no_xp_roles': raw_settings.get('no_xp_roles', '[]')
                        }
                        return settings
                    else:
                        # Create default settings
                        await db.execute("""
                            INSERT INTO guild_level_settings (guild_id) VALUES (?)
                        """, (guild_id,))
                        await db.commit()
                        
                        # Return default settings
                        return {
                            'guild_id': guild_id,
                            'enabled': False,
                            'xp_per_message': 15,
                            'xp_variance': 10,
                            'level_up_channel_id': None,
                            'level_up_message': 'Congratulations {user}! You reached **Level {level}**! 🎉',
                            'dm_level_ups': False,
                            'level_formula': 'default',
                            'stack_roles': False,
                            'remove_previous_roles': True,
                            'xp_cooldown': 60,
                            'exclude_channels': '[]',
                            'exclude_roles': '[]',
                            'multiplier_roles': '{}',
                            'no_xp_roles': '[]'
                        }
        except Exception as e:
            await self.error_logger.log_database_error(
                "Get Guild Settings", e, "guild_level_settings"
            )
            # Return default settings as fallback
            return {
                'guild_id': guild_id,
                'enabled': False,
                'xp_per_message': 15,
                'xp_variance': 10,
                'level_up_channel_id': None,
                'level_up_message': 'Congratulations {user}! You reached **Level {level}**! 🎉',
                'dm_level_ups': False,
                'level_formula': 'default',
                'stack_roles': False,
                'remove_previous_roles': True,
                'xp_cooldown': 60,
                'exclude_channels': '[]',
                'exclude_roles': '[]',
                'multiplier_roles': '{}',
                'no_xp_roles': '[]'
            }

    async def get_user_data(self, guild_id: int, user_id: int) -> Dict[str, Any]:
        """Get user level data"""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute(
                    "SELECT * FROM user_levels WHERE guild_id = ? AND user_id = ?",
                    (guild_id, user_id)
                ) as cursor:
                    row = await cursor.fetchone()
                    
                    if row:
                        columns = [desc[0] for desc in cursor.description]
                        return dict(zip(columns, row))
                    else:
                        # Create new user entry (use INSERT OR IGNORE to prevent UNIQUE constraint errors)
                        await db.execute("""
                            INSERT OR IGNORE INTO user_levels (user_id, guild_id) VALUES (?, ?)
                        """, (user_id, guild_id))
                        await db.commit()
                        
                        return {
                            'user_id': user_id,
                            'guild_id': guild_id,
                            'xp': 0,
                            'level': 0,
                            'total_xp': 0,
                            'messages_sent': 0,
                            'last_xp_gain': None
                        }
        except Exception as e:
            await self.error_logger.log_database_error(
                "Get User Data", e, "user_levels"
            )
            # Return default user data as fallback
            return {
                'user_id': user_id,
                'guild_id': guild_id,
                'xp': 0,
                'level': 0,
                'total_xp': 0,
                'messages_sent': 0,
                'last_xp_gain': None
            }

    async def update_user_xp(self, guild_id: int, user_id: int, xp_gain: int, settings: Dict[str, Any]) -> Tuple[bool, int, int]:
        """Update user XP and return (leveled_up, old_level, new_level)"""
        try:
            user_data = await self.get_user_data(guild_id, user_id)
            
            old_level = user_data['level']
            new_total_xp = user_data['total_xp'] + xp_gain
            new_level = self.calculate_level_from_xp(new_total_xp, settings['level_formula'])
            
            leveled_up = new_level > old_level
            
            # Update database
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("""
                    UPDATE user_levels 
                    SET xp = ?, level = ?, total_xp = ?, messages_sent = messages_sent + 1, last_xp_gain = ?
                    WHERE user_id = ? AND guild_id = ?
                """, (
                    new_total_xp - self.calculate_xp_for_level(new_level, settings['level_formula']),
                    new_level,
                    new_total_xp,
                    self.tz_helpers.get_utc_now().isoformat(),
                    user_id,
                    guild_id
                ))
                await db.commit()
            
            return leveled_up, old_level, new_level
        except Exception as e:
            await self.error_logger.log_database_error(
                "Update User XP", e, "user_levels"
            )
            # Return no level up as fallback
            return False, 0, 0

    async def assign_level_roles(self, member: discord.Member, new_level: int, settings: Dict[str, Any]):
        """Assign roles based on level"""
        guild = member.guild
        
        # Get level roles for this guild
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT level, role_id FROM level_roles WHERE guild_id = ? AND level <= ? ORDER BY level DESC",
                (guild.id, new_level)
            ) as cursor:
                level_roles = list(await cursor.fetchall())
        
        if not level_roles:
            return
        
        # Determine which roles to assign
        if settings['stack_roles']:
            # Assign all roles up to current level
            roles_to_assign = [role_id for level, role_id in level_roles]
        else:
            # Assign only the highest level role
            roles_to_assign = [level_roles[0][1]] if level_roles else []
        
        # Get current roles
        current_role_ids = [role.id for role in member.roles]
        
        # Determine which roles to add/remove
        roles_to_add = []
        roles_to_remove = []
        
        for role_id in roles_to_assign:
            role = guild.get_role(role_id)
            if role and role not in member.roles:
                roles_to_add.append(role)
        
        # If not stacking roles, remove previous level roles
        if not settings['stack_roles'] or settings['remove_previous_roles']:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute(
                    "SELECT role_id FROM level_roles WHERE guild_id = ? AND level < ?",
                    (guild.id, new_level)
                ) as cursor:
                    previous_role_ids = [row[0] for row in await cursor.fetchall()]
            
            for role_id in previous_role_ids:
                role = guild.get_role(role_id)
                if role and role in member.roles and role_id not in roles_to_assign:
                    roles_to_remove.append(role)
        
        # Apply role changes
        try:
            if roles_to_add:
                await member.add_roles(*roles_to_add, reason=f"Level up to {new_level}")
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove, reason=f"Level role update")
        except discord.Forbidden:
            await self.error_logger.log_error(
                "Permission Error", 
                f"Missing permissions to assign level roles in {guild.name}",
                f"Guild: {guild.name} ({guild.id})\nMember: {member.display_name} ({member.id})\nLevel: {new_level}"
            )
        except Exception as e:
            await self.error_logger.log_error(
                "Level Role Assignment Error",
                f"Error assigning level roles: {str(e)}\n{traceback.format_exc()}",
                f"Guild: {guild.name} ({guild.id})\nMember: {member.display_name} ({member.id})\nLevel: {new_level}"
            )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle XP gain from messages"""
        try:
            if not message.guild or message.author.bot:
                return
            
            settings = await self.get_guild_settings(message.guild.id)
            if not settings['enabled']:
                return
            
            # Check cooldown
            user_key = f"{message.guild.id}-{message.author.id}"
            now = self.tz_helpers.get_utc_now()
            
            if user_key in self.xp_cooldowns:
                if (now - self.xp_cooldowns[user_key]).total_seconds() < settings['xp_cooldown']:
                    return
            
            self.xp_cooldowns[user_key] = now
            
            # Check excluded channels
            exclude_channels = self.safe_json_loads(settings['exclude_channels'], [])
            if message.channel.id in exclude_channels:
                return
            
            # Check excluded roles
            exclude_roles = self.safe_json_loads(settings['exclude_roles'], [])
            no_xp_roles = self.safe_json_loads(settings['no_xp_roles'], [])
            
            # Only members have roles, not regular users
            if isinstance(message.author, discord.Member):
                user_role_ids = [role.id for role in message.author.roles]
                if any(role_id in exclude_roles + no_xp_roles for role_id in user_role_ids):
                    return
            else:
                user_role_ids = []
            
            # Calculate XP gain
            base_xp = settings['xp_per_message']
            variance = settings['xp_variance']
            xp_gain = random.randint(max(1, base_xp - variance), base_xp + variance)
            
            # Apply multipliers
            multiplier_roles = self.safe_json_loads(settings['multiplier_roles'], {})
            multiplier = 1.0
            
            for role_id in user_role_ids:
                if str(role_id) in multiplier_roles:
                    multiplier = max(multiplier, float(multiplier_roles[str(role_id)]))
            
            if multiplier != 1.0:
                xp_gain = int(base_xp * multiplier)
            else:
                xp_gain = base_xp
            
            # Update user XP
            leveled_up, old_level, new_level = await self.update_user_xp(
                message.guild.id, message.author.id, xp_gain, settings
            )
            
            # Handle level up
            if leveled_up:
                await self.handle_level_up(message, old_level, new_level, settings)
                
        except Exception as e:
            # Log error but don't interrupt message processing for other cogs
            await self.error_logger.log_error(
                f"XP Processing Error in {message.guild.name if message.guild else 'DM'}",
                f"Error processing XP for message: {str(e)} | Guild: {message.guild.id if message.guild else 'None'} | User: {message.author.id} | Channel: {message.channel.id if hasattr(message.channel, 'id') else 'None'}"
            )

    async def handle_level_up(self, message: discord.Message, old_level: int, new_level: int, settings: Dict[str, Any]):
        """Handle level up notifications and role assignments"""
        try:
            if not message.guild or not isinstance(message.author, discord.Member):
                return
                
            member = message.author
            guild = message.guild
            
            # Assign level roles
            await self.assign_level_roles(member, new_level, settings)
            
            # Send level up notification
            level_up_message = settings['level_up_message'].format(
                user=member.mention,
                username=member.display_name,
                level=new_level,
                old_level=old_level
            )
            
            embed = discord.Embed(
                title=f"{emojis['confetti']} Level Up!",
                description=level_up_message,
                color=0x006fb9
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            
            # Send to level up channel only if configured; do NOT fallback to current channel
            if settings.get('level_up_channel_id'):
                target_channel = guild.get_channel(settings['level_up_channel_id'])
                try:
                    if isinstance(target_channel, discord.TextChannel):
                        await target_channel.send(embed=embed)
                except discord.Forbidden:
                    pass  # No permission to send in target channel
            else:
                # If no channel configured, only send DM if enabled
                pass
            
            # Send DM if enabled
            if settings['dm_level_ups']:
                try:
                    dm_embed = discord.Embed(
                        title=f"{emojis['confetti']} Level Up in {guild.name}!",
                        description=f"You reached **Level {new_level}**! {emojis['party']}",
                        color=0x006fb9
                    )
                    await member.send(embed=dm_embed)
                except discord.Forbidden:
                    pass  # User has DMs disabled
                    
        except Exception as e:
            await self.error_logger.log_error(
                f"Level Up Handling Error in {message.guild.name if message.guild else 'Unknown Guild'}",
                f"Error handling level up: {str(e)} | Guild: {message.guild.id if message.guild else 'None'} | User: {message.author.id} | Old Level: {old_level} | New Level: {new_level}"
            )

    async def add_xp_to_user(self, guild_id: int, user_id: int, xp_amount: int) -> bool:
        """Add XP to a user and return whether they leveled up"""
        try:
            settings = await self.get_guild_settings(guild_id)
            leveled_up, old_level, new_level = await self.update_user_xp(
                guild_id, user_id, xp_amount, settings
            )
            return leveled_up
        except Exception as e:
            await self.error_logger.log_error(
                "XP Addition Error",
                f"Error adding XP to user: {str(e)}\n{traceback.format_exc()}",
                f"Guild ID: {guild_id}\nUser ID: {user_id}\nXP Amount: {xp_amount}"
            )
            return False

    # ================= MAIN LEVEL COMMAND GROUP =================
    @commands.group(name="level", aliases=["lvl", "leveling"], invoke_without_command=True)
    @commands.guild_only()
    @blacklist_check()
    @ignore_check()
    async def level_group(self, ctx, member: Optional[discord.Member] = None):
        """
        🏆 View your level or another user's level
        
        **Usage:**
        `{prefix}level` - View your level
        `{prefix}level @user` - View user's level
        """
        try:
            if not ctx.guild:
                return
                
            target = member or ctx.author
            user_data = await self.get_user_data(ctx.guild.id, target.id)
            settings = await self.get_guild_settings(ctx.guild.id)
            
            if not settings['enabled']:
                embed = discord.Embed(
                    title=f"{emojis['warning']} Leveling Disabled",
                    description=f"Leveling is currently disabled in this server.\n\nAdmins can enable it using `{ctx.prefix}level setup`",
                    color=0xff9900
                )
                return await ctx.send(embed=embed)
            
            # Calculate progress
            current_level_xp = self.calculate_xp_for_level(user_data['level'], settings['level_formula'])
            next_level_xp = self.calculate_xp_for_next_level(user_data['level'], settings['level_formula'])
            xp_needed_for_level = next_level_xp - current_level_xp
            xp_progress = user_data['total_xp'] - current_level_xp
            xp_for_next = next_level_xp - user_data['total_xp']
            
            if xp_needed_for_level > 0:
                progress_percentage = (xp_progress / xp_needed_for_level) * 100
            else:
                progress_percentage = 100
            
            # Create progress bar
            bar_length = 20
            filled_length = int(bar_length * progress_percentage / 100)
            bar = "█" * filled_length + "░" * (bar_length - filled_length)
            
            embed = discord.Embed(
                title=f"{emojis['trophy']} {target.display_name}'s Level",
                color=0x006fb9
            )
            embed.set_thumbnail(url=target.display_avatar.url)
            
            embed.add_field(
                name=f"{emojis['crown']} Level",
                value=f"**{user_data['level']:,}**",
                inline=True
            )
            
            embed.add_field(
                name=f"{emojis['zap']} Total XP",
                value=f"**{user_data['total_xp']:,}**",
                inline=True
            )
            
            embed.add_field(
                name=f"{emojis['fire']} Messages",
                value=f"**{user_data['messages_sent']:,}**",
                inline=True
            )
            
            embed.add_field(
                name=f"{emojis['star']} Progress to Level {user_data['level'] + 1}",
                value=f"`{bar}` {progress_percentage:.1f}%\n**{xp_progress:,}** / **{xp_needed_for_level:,}** XP\n(**{xp_for_next:,}** XP needed)",
                inline=False
            )
            
            if target == ctx.author:
                embed.set_footer(text=f"Keep chatting to earn more XP! • Use {ctx.prefix}level rank for detailed info")
            else:
                embed.set_footer(text=f"Requested by {ctx.author.display_name}")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await self.error_logger.log_error(
                f"Level Command Error in {ctx.guild.name}",
                f"Error in level command: {str(e)} | Guild: {ctx.guild.id} | User: {ctx.author.id} | Target: {target.id if member else ctx.author.id} | Command: level"
            )
            embed = discord.Embed(
                title=f"{emojis['warning']} Error",
                description="An error occurred while fetching level data. Please try again later.",
                color=0xff0000
            )
            await ctx.send(embed=embed)

    @level_group.command(name="rank")
    @commands.guild_only()
    @blacklist_check()
    @ignore_check()
    async def level_rank(self, ctx, member: Optional[discord.Member] = None):
        """
        📊 Shows detailed rank information for a user
        
        **Usage:**
        `{prefix}level rank` - View your detailed rank
        `{prefix}level rank @user` - View user's detailed rank
        """
        if not ctx.guild:
            return
            
        target = member or ctx.author
        user_data = await self.get_user_data(ctx.guild.id, target.id)
        settings = await self.get_guild_settings(ctx.guild.id)
        
        if not settings['enabled']:
            embed = discord.Embed(
                title=f"{emojis['warning']} Leveling Disabled",
                description=f"Leveling is currently disabled in this server.\n\nAdmins can enable it using `{ctx.prefix}level setup`",
                color=0xff9900
            )
            return await ctx.send(embed=embed)
        
        # Get user's rank
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("""
                SELECT COUNT(*) + 1 as rank FROM user_levels 
                WHERE guild_id = ? AND total_xp > ?
            """, (ctx.guild.id, user_data['total_xp'])) as cursor:
                rank_data = await cursor.fetchone()
                rank = rank_data[0] if rank_data else 1
        
        # Get total members with XP
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("""
                SELECT COUNT(*) FROM user_levels WHERE guild_id = ? AND total_xp > 0
            """, (ctx.guild.id,)) as cursor:
                total_data = await cursor.fetchone()
                total_members = total_data[0] if total_data else 1
        
        # Calculate detailed progress
        current_level_xp = self.calculate_xp_for_level(user_data['level'], settings['level_formula'])
        next_level_xp = self.calculate_xp_for_next_level(user_data['level'], settings['level_formula'])
        xp_needed_for_level = next_level_xp - current_level_xp
        xp_progress = user_data['total_xp'] - current_level_xp
        xp_for_next = next_level_xp - user_data['total_xp']
        
        if xp_needed_for_level > 0:
            progress_percentage = (xp_progress / xp_needed_for_level) * 100
        else:
            progress_percentage = 100
        
        # Create detailed progress bar
        bar_length = 25
        filled_length = int(bar_length * progress_percentage / 100)
        bar = "█" * filled_length + "░" * (bar_length - filled_length)
        
        embed = discord.Embed(
            title=f"{emojis['diamond']} Detailed Rank Information",
            description=f"**{target.display_name}**'s complete leveling statistics",
            color=0x006fb9
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        
        # Rank information
        embed.add_field(
            name=f"{emojis['medal']} Server Rank",
            value=f"**#{rank:,}** out of **{total_members:,}** members",
            inline=False
        )
        
        # Level information
        embed.add_field(
            name=f"{emojis['crown']} Current Level",
            value=f"**Level {user_data['level']:,}**",
            inline=True
        )
        
        embed.add_field(
            name=f"{emojis['zap']} Total XP",
            value=f"**{user_data['total_xp']:,}** XP",
            inline=True
        )
        
        embed.add_field(
            name=f"{emojis['fire']} Messages Sent",
            value=f"**{user_data['messages_sent']:,}** messages",
            inline=True
        )
        
        # Progress information
        embed.add_field(
            name=f"{emojis['target']} Level Progress",
            value=f"`{bar}` **{progress_percentage:.1f}%**\n"
                  f"**{xp_progress:,}** / **{xp_needed_for_level:,}** XP\n"
                  f"**{xp_for_next:,}** XP until Level **{user_data['level'] + 1}**",
            inline=False
        )
        
        # Additional stats
        if user_data['messages_sent'] > 0:
            avg_xp_per_message = user_data['total_xp'] / user_data['messages_sent']
            embed.add_field(
                name=f"{emojis['sparkles']} Average XP/Message",
                value=f"**{avg_xp_per_message:.1f}** XP",
                inline=True
            )
        
        # Next level requirements
        embed.add_field(
            name=f"{emojis['rocket']} Next Level",
            value=f"Level **{user_data['level'] + 1}** requires **{next_level_xp:,}** total XP",
            inline=True
        )
        
        # Estimated messages to next level
        if settings['xp_per_message'] > 0:
            messages_needed = max(1, xp_for_next // settings['xp_per_message'])
            embed.add_field(
                name=f"{emojis['target']} Est. Messages Needed",
                value=f"~**{messages_needed:,}** messages",
                inline=True
            )
        
        embed.set_footer(text=f"Requested by {ctx.author.display_name} • Leveling formula: {settings['level_formula']}")
        await ctx.send(embed=embed)

    @level_group.command(name="leaderboard", aliases=["lb", "top"])
    @commands.guild_only()
    @blacklist_check()
    @ignore_check()
    async def level_leaderboard(self, ctx):
        """
        🏆 Shows top 10 members with the highest level
        
        **Usage:**
        `{prefix}level leaderboard` - View top 10 users
        """
        try:
            if not ctx.guild:
                return
                
            settings = await self.get_guild_settings(ctx.guild.id)
            
            if not settings['enabled']:
                embed = discord.Embed(
                    title=f"{emojis['warning']} Leveling Disabled",
                    description=f"Leveling is currently disabled in this server.\n\nAdmins can enable it using `{ctx.prefix}level setup`",
                    color=0xff9900
                )
                return await ctx.send(embed=embed)
            
            # Get top 10 users
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute("""
                    SELECT user_id, level, total_xp, messages_sent 
                    FROM user_levels 
                    WHERE guild_id = ? AND total_xp > 0
                    ORDER BY total_xp DESC 
                    LIMIT 10
                """, (ctx.guild.id,)) as cursor:
                    top_users = list(await cursor.fetchall())
            
            if not top_users:
                embed = discord.Embed(
                    title=f"{emojis['warning']} No Data",
                    description="No users have gained XP yet in this server.",
                    color=0xff9900
                )
                return await ctx.send(embed=embed)
            
            embed = discord.Embed(
                title=f"{emojis['trophy']} Level Leaderboard",
                description=f"Top **{len(top_users)}** members in **{ctx.guild.name}**",
                color=0x006fb9
            )
            
            leaderboard_text = ""
            medals = [emojis['first'], emojis['second'], emojis['third']]
            
            for i, (user_id, level, total_xp, messages) in enumerate(top_users, 1):
                user = self.bot.get_user(user_id)
                if not user:
                    try:
                        user = await self.bot.fetch_user(user_id)
                    except:
                        continue
                
                medal = medals[i-1] if i <= 3 else f"**{i}.**"
                username = user.display_name if hasattr(user, 'display_name') else user.name
                
                leaderboard_text += f"{medal} **{username}** - Level **{level:,}** (**{total_xp:,}** XP)\n"
            
            embed.add_field(
                name=f"{emojis['star']} Rankings",
                value=leaderboard_text,
                inline=False
            )
            
            embed.set_footer(text=f"Requested by {ctx.author.display_name}")
            await ctx.send(embed=embed)
            
        except Exception as e:
            await self.error_logger.log_error(
                f"Level Leaderboard Error in {ctx.guild.name}",
                f"Error in level leaderboard command: {str(e)} | Guild: {ctx.guild.id} | User: {ctx.author.id} | Command: level leaderboard"
            )
            embed = discord.Embed(
                title=f"{emojis['warning']} Error",
                description="An error occurred while fetching the leaderboard. Please try again later.",
                color=0xff0000
            )
            await ctx.send(embed=embed)

    @level_group.command(name="setup")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def level_setup(self, ctx):
        """
        ⚙️ Build the complete level configuration
        
        **Usage:**
        `{prefix}level setup` - Interactive setup builder
        """
        try:
            if not ctx.guild:
                return
            
            print(f"[LEVELING] Setup command called by {ctx.author} in {ctx.guild.name}")
            
            # Ensure database is initialized
            await self.ensure_leveling_db()
            
            embed = discord.Embed(
                title=f"{emojis['settings']} Level System Setup",
                description="**Leveling is disabled by default.** Click the buttons below to configure and enable your server's leveling system.",
                color=0x006fb9
            )
            
            print(f"[LEVELING] Getting guild settings for {ctx.guild.id}")
            settings = await self.get_guild_settings(ctx.guild.id)
            print(f"[LEVELING] Retrieved settings: {settings}")
            
            # Current status
            status = f"{emojis['check']} Enabled" if settings['enabled'] else f"{emojis['x']} Disabled"
            embed.add_field(name="Status", value=status, inline=True)
            embed.add_field(name="XP per Message", value=f"{settings['xp_per_message']} ± {settings['xp_variance']}", inline=True)
            embed.add_field(name="XP Cooldown", value=f"{settings['xp_cooldown']}s", inline=True)
            
            print(f"[LEVELING] Creating view and sending response")
            view = LevelSetupView(ctx.guild.id, self.error_logger)
            await ctx.send(embed=embed, view=view)
            print(f"[LEVELING] Setup command completed successfully")
            
        except Exception as e:
            print(f"[LEVELING] Error in setup command: {e}")
            import traceback
            traceback.print_exc()
            
            error_embed = discord.Embed(
                title=f"{emojis['error']} Setup Error",
                description=f"An error occurred while setting up leveling: {str(e)}",
                color=0xff0000
            )
            await ctx.send(embed=error_embed)

    @level_group.command(name="test")
    @commands.guild_only()
    @blacklist_check()
    @ignore_check()
    async def level_test(self, ctx):
        """Test command to verify leveling system is working"""
        embed = discord.Embed(
            title=f"{emojis['check']} Leveling System Test",
            description="✅ The leveling cog is loaded and commands are working!",
            color=0x00ff00
        )
        embed.add_field(name="Guild ID", value=ctx.guild.id, inline=True)
        embed.add_field(name="User ID", value=ctx.author.id, inline=True)
        embed.add_field(name="Test Status", value="All systems operational", inline=False)
        await ctx.send(embed=embed)

    @level_group.command(name="config")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def level_config(self, ctx):
        """
        📋 Shows current level configuration
        
        **Usage:**
        `{prefix}level config` - View current settings
        """
        if not ctx.guild:
            return
        
        settings = await self.get_guild_settings(ctx.guild.id)
        
        embed = discord.Embed(
            title=f"{emojis['settings']} Level Configuration",
            description=f"Current leveling settings for **{ctx.guild.name}**",
            color=0x006fb9
        )
        
        # Basic Settings
        status = f"{emojis['check']} Enabled" if settings['enabled'] else f"{emojis['x']} Disabled"
        embed.add_field(name="System Status", value=status, inline=True)
        embed.add_field(name="XP per Message", value=f"{settings['xp_per_message']} ± {settings['xp_variance']}", inline=True)
        embed.add_field(name="XP Cooldown", value=f"{settings['xp_cooldown']} seconds", inline=True)
        
        # Level Formula
        embed.add_field(name="Level Formula", value=settings['level_formula'].title(), inline=True)
        
        # Notifications
        level_channel = "Current Channel"
        if settings['level_up_channel_id']:
            channel = ctx.guild.get_channel(settings['level_up_channel_id'])
            level_channel = channel.mention if channel else "Deleted Channel"
        
        embed.add_field(name="Level Up Channel", value=level_channel, inline=True)
        dm_status = f"{emojis['check']} Yes" if settings['dm_level_ups'] else f"{emojis['x']} No"
        embed.add_field(name="DM Level Ups", value=dm_status, inline=True)
        
        # Role Settings
        stack_roles = f"{emojis['check']} Yes" if settings['stack_roles'] else f"{emojis['x']} No"
        remove_prev = f"{emojis['check']} Yes" if settings['remove_previous_roles'] else f"{emojis['x']} No"
        embed.add_field(name="Stack Roles", value=stack_roles, inline=True)
        embed.add_field(name="Remove Previous", value=remove_prev, inline=True)
        
        # Get role count
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT COUNT(*) FROM level_roles WHERE guild_id = ?",
                (ctx.guild.id,)
            ) as cursor:
                role_count_result = await cursor.fetchone()
                role_count = role_count_result[0] if role_count_result else 0
        
        embed.add_field(name="Level Roles", value=f"{role_count} configured", inline=True)
        
        # Exclusions
        exclude_channels = self.safe_json_loads(settings['exclude_channels'], [])
        exclude_roles = self.safe_json_loads(settings['exclude_roles'], [])
        no_xp_roles = self.safe_json_loads(settings['no_xp_roles'], [])
        
        embed.add_field(name="Excluded Channels", value=str(len(exclude_channels)), inline=True)
        embed.add_field(name="Excluded Roles", value=str(len(exclude_roles)), inline=True)
        embed.add_field(name="No XP Roles", value=str(len(no_xp_roles)), inline=True)
        
        # Level Up Message
        embed.add_field(
            name="Level Up Message",
            value=f"```{settings['level_up_message'][:100]}{'...' if len(settings['level_up_message']) > 100 else ''}```",
            inline=False
        )
        
        embed.set_footer(text=f"Use {ctx.prefix}level setup to modify these settings")
        await ctx.send(embed=embed)

    @level_group.command(name="help")
    @commands.guild_only()
    @blacklist_check()
    @ignore_check()
    async def level_help(self, ctx):
        """
        📖 Comprehensive leveling help and command guide
        
        **Usage:**
        `{prefix}level help` - Shows this comprehensive help
        """
        try:
            embed = discord.Embed(
                title=f"{emojis['book']} Comprehensive Leveling Help",
                description="Complete guide to the leveling system commands and features",
                color=0x006fb9
            )
            
            # Basic Commands
            embed.add_field(
                name="📊 **Basic Commands**",
                value=(
                    f"`{ctx.prefix}level` - View your current level and progress\n"
                    f"`{ctx.prefix}level @user` - View someone else's level\n"
                    f"`{ctx.prefix}level rank` - View detailed rank information\n"
                    f"`{ctx.prefix}level leaderboard` - Show server leaderboard"
                ),
                inline=False
            )
            
            # Configuration Commands (Admin Only)
            embed.add_field(
                name="⚙️ **Configuration (Admin Only)**",
                value=(
                    f"`{ctx.prefix}level config` - View current settings\n"
                    f"`{ctx.prefix}level settings enable/disable` - Toggle leveling system\n"
                    f"`{ctx.prefix}level settings message <text>` - Set level-up message\n"
                    f"`{ctx.prefix}level settings channel [#channel]` - Set announcement channel\n"
                    f"`{ctx.prefix}level settings roles add/remove/list` - Manage role rewards\n"
                    f"`{ctx.prefix}level settings blacklist add/remove/list` - Manage XP blacklist\n"
                    f"`{ctx.prefix}level setup` - Interactive setup interface"
                ),
                inline=False
            )
            
            # Role Management
            embed.add_field(
                name="🎭 **Role Management**",
                value=(
                    f"`{ctx.prefix}level role setup` - Interactive role setup\n"
                    f"`{ctx.prefix}level role add <level> <role>` - Add a role for a level\n"
                    f"`{ctx.prefix}level role remove <level> <role>` - Remove a role from a level\n"
                    f"`{ctx.prefix}level role list` - List all level roles"
                ),
                inline=False
            )
            
            # Admin Management
            embed.add_field(
                name="👑 **Admin Management**",
                value=(
                    f"`{ctx.prefix}level admin set @user <level>` - Set user's level\n"
                    f"`{ctx.prefix}level admin add @user <xp>` - Add XP to user\n"
                    f"`{ctx.prefix}level admin remove @user <levels>` - Remove levels from user\n"
                    f"`{ctx.prefix}level admin reset @user` - Reset user's progress\n"
                    f"`{ctx.prefix}level reset` - Reset entire server (Administrator only)"
                ),
                inline=False
            )
            
            # How the System Works
            embed.add_field(
                name="🔧 **How It Works**",
                value=(
                    "• Users gain XP by sending messages in text channels\n"
                    "• XP has a cooldown to prevent spam\n"
                    "• Reaching certain XP thresholds grants levels\n"
                    "• Level roles are automatically assigned\n"
                    "• Admins can configure all aspects of the system"
                ),
                inline=False
            )
            
            # Key Features
            embed.add_field(
                name="✨ **Key Features**",
                value=(
                    "• Multiple level formulas (default, linear, exponential)\n"
                    "• XP multipliers for specific roles\n"
                    "• Channel and role exclusions\n"
                    "• Customizable level-up messages\n"
                    "• Role stacking or replacement options\n"
                    "• DM notifications for level-ups"
                ),
                inline=False
            )
            
            embed.set_footer(text=f"Need more help? Use {ctx.prefix}level config to see current settings or {ctx.prefix}level setup for interactive configuration")
            await ctx.send(embed=embed)
            
        except Exception as e:
            await self.error_logger.log_error(
                f"Level Help Error in {ctx.guild.name}",
                f"Error in level help command: {str(e)} | Guild: {ctx.guild.id} | User: {ctx.author.id}"
            )
            embed = discord.Embed(
                title=f"{emojis['warning']} Error",
                description="An error occurred while showing help. Please try again later.",
                color=0xff0000
            )
            await ctx.send(embed=embed)

    # ================= CONFIG COMMANDS =================
    @level_group.group(name="settings", invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def level_settings_group(self, ctx):
        """Advanced configuration commands for leveling system"""
        if ctx.invoked_subcommand is None:
            # Reuse the existing config display
            await self.level_config(ctx)

    @level_settings_group.command(name="enable")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def level_config_enable(self, ctx):
        """
        ✅ Enable the leveling system
        
        **Usage:**
        `{prefix}level settings enable` - Enable leveling
        """
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE guild_level_settings SET enabled = 1 WHERE guild_id = ?",
                    (ctx.guild.id,)
                )
                await db.commit()
            
            embed = discord.Embed(
                title=f"{emojis['check']} Leveling Enabled",
                description=f"The leveling system is now **enabled** for {ctx.guild.name}!\n\nUsers will start gaining XP from their messages.",
                color=0x00ff00
            )
            embed.add_field(
                name="What's Next?",
                value=f"• Configure level roles with `{ctx.prefix}level role setup`\n• Set up announcement channel with `{ctx.prefix}level settings channel`\n• Customize settings with `{ctx.prefix}level setup`",
                inline=False
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            await self.error_logger.log_error(
                f"Level Config Enable Error in {ctx.guild.name}",
                f"Error enabling leveling: {str(e)} | Guild: {ctx.guild.id} | User: {ctx.author.id}"
            )
            embed = discord.Embed(
                title=f"{emojis['warning']} Error",
                description="An error occurred while enabling leveling. Please try again later.",
                color=0xff0000
            )
            await ctx.send(embed=embed)

    @level_settings_group.command(name="disable")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def level_config_disable(self, ctx):
        """
        ❌ Disable the leveling system
        
        **Usage:**
        `{prefix}level settings disable` - Disable leveling
        """
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE guild_level_settings SET enabled = 0 WHERE guild_id = ?",
                    (ctx.guild.id,)
                )
                await db.commit()
            
            embed = discord.Embed(
                title=f"{emojis['x']} Leveling Disabled",
                description=f"The leveling system is now **disabled** for {ctx.guild.name}.\n\nUsers will no longer gain XP, but existing data is preserved.",
                color=0xff9900
            )
            embed.add_field(
                name="Note",
                value=f"To re-enable, use `{ctx.prefix}level config enable`\nAll user levels and settings are preserved.",
                inline=False
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            await self.error_logger.log_error(
                f"Level Config Disable Error in {ctx.guild.name}",
                f"Error disabling leveling: {str(e)} | Guild: {ctx.guild.id} | User: {ctx.author.id}"
            )
            embed = discord.Embed(
                title=f"{emojis['warning']} Error",
                description="An error occurred while disabling leveling. Please try again later.",
                color=0xff0000
            )
            await ctx.send(embed=embed)

    @level_settings_group.command(name="message")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def level_config_message(self, ctx, *, message: str):
        """
        💬 Set the level-up message
        
        **Usage:**
        `{prefix}level settings message <text>` - Set level-up message
        
        **Available Variables:**
        • `{user}` - User mention
        • `{username}` - User's display name
        • `{level}` - New level reached
        • `{old_level}` - Previous level
        """
        try:
            # Validate message length
            if len(message) > 1000:
                embed = discord.Embed(
                    title=f"{emojis['error']} Message Too Long",
                    description="Level-up messages must be 1000 characters or less.",
                    color=0xff0000
                )
                return await ctx.send(embed=embed)
            
            # Validate required placeholders
            if '{user}' not in message and '{username}' not in message:
                embed = discord.Embed(
                    title=f"{emojis['error']} Missing User Variable",
                    description="Message must contain either `{user}` or `{username}` placeholder.",
                    color=0xff0000
                )
                return await ctx.send(embed=embed)
            
            if '{level}' not in message:
                embed = discord.Embed(
                    title=f"{emojis['error']} Missing Level Variable",
                    description="Message must contain `{level}` placeholder.",
                    color=0xff0000
                )
                return await ctx.send(embed=embed)
            
            # Update database
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE guild_level_settings SET level_up_message = ? WHERE guild_id = ?",
                    (message, ctx.guild.id)
                )
                await db.commit()
            
            embed = discord.Embed(
                title=f"{emojis['check']} Level-Up Message Updated",
                description="Successfully updated the level-up message!",
                color=0x00ff00
            )
            
            # Show preview with example values
            preview_message = message.format(
                user=ctx.author.mention,
                username=ctx.author.display_name,
                level=10,
                old_level=9
            )
            
            embed.add_field(
                name="New Message",
                value=f"```{message}```",
                inline=False
            )
            
            embed.add_field(
                name="Preview",
                value=preview_message,
                inline=False
            )
            
            embed.set_footer(text="Available variables: {user}, {username}, {level}, {old_level}")
            await ctx.send(embed=embed)
            
        except Exception as e:
            await self.error_logger.log_error(
                f"Level Config Message Error in {ctx.guild.name}",
                f"Error setting level message: {str(e)} | Guild: {ctx.guild.id} | User: {ctx.author.id}"
            )
            embed = discord.Embed(
                title=f"{emojis['warning']} Error",
                description="An error occurred while setting the message. Please try again later.",
                color=0xff0000
            )
            await ctx.send(embed=embed)

    @level_settings_group.command(name="channel")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def level_config_channel(self, ctx, channel: Optional[discord.TextChannel] = None):
        """
        📢 Set the level-up announcement channel
        
        **Usage:**
        `{prefix}level settings channel` - Disable announcements
        `{prefix}level settings channel #channel` - Set announcement channel
        """
        try:
            if channel is None:
                # Disable announcements
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute(
                        "UPDATE guild_level_settings SET level_up_channel_id = NULL WHERE guild_id = ?",
                        (ctx.guild.id,)
                    )
                    await db.commit()
                
                embed = discord.Embed(
                    title=f"{emojis['x']} Announcements Disabled",
                    description="Level-up announcements have been disabled.\n\nUsers will only receive DM notifications if enabled.",
                    color=0xff9900
                )
            else:
                # Set announcement channel
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute(
                        "UPDATE guild_level_settings SET level_up_channel_id = ? WHERE guild_id = ?",
                        (channel.id, ctx.guild.id)
                    )
                    await db.commit()
                
                embed = discord.Embed(
                    title=f"{emojis['check']} Announcement Channel Set",
                    description=f"Level-up announcements will now be sent to {channel.mention}",
                    color=0x00ff00
                )
                
                # Test if bot can send messages in the channel
                try:
                    test_embed = discord.Embed(
                        title="📢 Test Announcement",
                        description="This is a test to ensure the bot can send level-up announcements here.",
                        color=0x0099ff
                    )
                    test_msg = await channel.send(embed=test_embed)
                    await test_msg.delete()  # Clean up test message
                    
                    embed.add_field(
                        name="✅ Channel Test",
                        value="Bot can successfully send messages in this channel.",
                        inline=False
                    )
                except discord.Forbidden:
                    embed.add_field(
                        name="⚠️ Permission Warning",
                        value="Bot cannot send messages in this channel. Please check permissions.",
                        inline=False
                    )
                except:
                    embed.add_field(
                        name="⚠️ Warning",
                        value="Could not test channel permissions.",
                        inline=False
                    )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await self.error_logger.log_error(
                f"Level Config Channel Error in {ctx.guild.name}",
                f"Error setting announcement channel: {str(e)} | Guild: {ctx.guild.id} | User: {ctx.author.id}"
            )
            embed = discord.Embed(
                title=f"{emojis['warning']} Error",
                description="An error occurred while setting the channel. Please try again later.",
                color=0xff0000
            )
            await ctx.send(embed=embed)

    @level_settings_group.group(name="roles", invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def level_config_roles_group(self, ctx):
        """Manage role rewards for leveling"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title=f"{emojis['crown']} Level Role Commands",
                description="Manage roles that are given when users reach certain levels",
                color=0x006fb9
            )
            embed.add_field(
                name="Available Commands",
                value=(
                    f"`{ctx.prefix}level settings roles add <level> <role>` - Add a level role\n"
                    f"`{ctx.prefix}level settings roles remove <level>` - Remove a level role\n"
                    f"`{ctx.prefix}level settings roles list` - List all level roles"
                ),
                inline=False
            )
            embed.add_field(
                name="Alternative",
                value=f"Use `{ctx.prefix}level role setup` for an interactive interface",
                inline=False
            )
            await ctx.send(embed=embed)

    @level_config_roles_group.command(name="add")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def level_config_roles_add(self, ctx, level: int, role: discord.Role):
        """
        ➕ Add a role reward for reaching a level
        
        **Usage:**
        `{prefix}level settings roles add 5 @Member` - Give @Member role at level 5
        """
        try:
            if level < 1 or level > 1000:
                embed = discord.Embed(
                    title=f"{emojis['error']} Invalid Level",
                    description="Level must be between 1 and 1000.",
                    color=0xff0000
                )
                return await ctx.send(embed=embed)
            
            # Check if bot can manage this role
            if role >= ctx.guild.me.top_role:
                embed = discord.Embed(
                    title=f"{emojis['error']} Role Too High",
                    description=f"I cannot manage {role.mention} because it's higher than my highest role.\n\nPlease move my role above it in the server settings.",
                    color=0xff0000
                )
                return await ctx.send(embed=embed)
            
            # Add to database
            async with aiosqlite.connect(DB_PATH) as db:
                # Check if level already has a role
                async with db.execute(
                    "SELECT role_id FROM level_roles WHERE guild_id = ? AND level = ?",
                    (ctx.guild.id, level)
                ) as cursor:
                    existing = await cursor.fetchone()
                
                if existing:
                    # Update existing
                    await db.execute(
                        "UPDATE level_roles SET role_id = ? WHERE guild_id = ? AND level = ?",
                        (role.id, ctx.guild.id, level)
                    )
                    action = "updated"
                else:
                    # Insert new
                    await db.execute(
                        "INSERT INTO level_roles (guild_id, level, role_id) VALUES (?, ?, ?)",
                        (ctx.guild.id, level, role.id)
                    )
                    action = "added"
                
                await db.commit()
            
            embed = discord.Embed(
                title=f"{emojis['check']} Level Role {action.title()}",
                description=f"**Level {level}:** {role.mention}",
                color=0x00ff00
            )
            
            if existing:
                old_role = ctx.guild.get_role(existing[0])
                old_role_name = old_role.mention if old_role else "Deleted Role"
                embed.add_field(
                    name="Previous Role",
                    value=old_role_name,
                    inline=True
                )
            
            embed.set_footer(text=f"Users who reach level {level} will automatically receive this role")
            await ctx.send(embed=embed)
            
        except Exception as e:
            await self.error_logger.log_error(
                f"Level Config Roles Add Error in {ctx.guild.name}",
                f"Error adding level role: {str(e)} | Guild: {ctx.guild.id} | User: {ctx.author.id}"
            )
            embed = discord.Embed(
                title=f"{emojis['warning']} Error",
                description="An error occurred while adding the level role. Please try again later.",
                color=0xff0000
            )
            await ctx.send(embed=embed)

    @level_config_roles_group.command(name="remove")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def level_config_roles_remove(self, ctx, level: int):
        """
        ➖ Remove a role reward for a level
        
        **Usage:**
        `{prefix}level settings roles remove 5` - Remove role reward for level 5
        """
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                # Check if level exists
                async with db.execute(
                    "SELECT role_id FROM level_roles WHERE guild_id = ? AND level = ?",
                    (ctx.guild.id, level)
                ) as cursor:
                    existing = await cursor.fetchone()
                
                if not existing:
                    embed = discord.Embed(
                        title=f"{emojis['error']} Level Role Not Found",
                        description=f"No role reward found for level {level}.",
                        color=0xff0000
                    )
                    return await ctx.send(embed=embed)
                
                # Remove from database
                await db.execute(
                    "DELETE FROM level_roles WHERE guild_id = ? AND level = ?",
                    (ctx.guild.id, level)
                )
                await db.commit()
            
            # Get role info for confirmation
            removed_role = ctx.guild.get_role(existing[0])
            role_name = removed_role.mention if removed_role else "Deleted Role"
            
            embed = discord.Embed(
                title=f"{emojis['check']} Level Role Removed",
                description=f"Removed role reward for **Level {level}**",
                color=0x00ff00
            )
            embed.add_field(
                name="Removed Role",
                value=role_name,
                inline=True
            )
            embed.set_footer(text="Users will no longer receive this role when reaching this level")
            await ctx.send(embed=embed)
            
        except Exception as e:
            await self.error_logger.log_error(
                f"Level Config Roles Remove Error in {ctx.guild.name}",
                f"Error removing level role: {str(e)} | Guild: {ctx.guild.id} | User: {ctx.author.id}"
            )
            embed = discord.Embed(
                title=f"{emojis['warning']} Error",
                description="An error occurred while removing the level role. Please try again later.",
                color=0xff0000
            )
            await ctx.send(embed=embed)

    @level_config_roles_group.command(name="list")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def level_config_roles_list(self, ctx):
        """
        📋 List all level role rewards
        
        **Usage:**
        `{prefix}level settings roles list` - Show all level roles
        """
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute(
                    "SELECT level, role_id FROM level_roles WHERE guild_id = ? ORDER BY level ASC",
                    (ctx.guild.id,)
                ) as cursor:
                    level_roles = list(await cursor.fetchall())
            
            if not level_roles:
                embed = discord.Embed(
                    title=f"{emojis['warning']} No Level Roles",
                    description="No level role rewards have been configured yet.",
                    color=0xff9900
                )
                embed.add_field(
                    name="Get Started",
                    value=f"Add your first level role with:\n`{ctx.prefix}level config roles add <level> <role>`",
                    inline=False
                )
                return await ctx.send(embed=embed)
            
            embed = discord.Embed(
                title=f"{emojis['crown']} Level Role Rewards",
                description=f"**{len(level_roles)}** level roles configured for **{ctx.guild.name}**",
                color=0x006fb9
            )
            
            role_list = []
            valid_roles = 0
            
            for level, role_id in level_roles:
                role = ctx.guild.get_role(role_id)
                if role:
                    role_list.append(f"**Level {level}:** {role.mention}")
                    valid_roles += 1
                else:
                    role_list.append(f"**Level {level}:** {emojis['x']} *Deleted Role* (ID: {role_id})")
            
            # Split into fields if too many
            chunk_size = 15
            for i in range(0, len(role_list), chunk_size):
                chunk = role_list[i:i + chunk_size]
                field_name = "Level Roles" if i == 0 else f"Level Roles (continued)"
                embed.add_field(
                    name=field_name,
                    value="\n".join(chunk),
                    inline=False
                )
            
            # Add summary
            if valid_roles != len(level_roles):
                deleted_count = len(level_roles) - valid_roles
                embed.add_field(
                    name="⚠️ Status",
                    value=f"**{valid_roles}** active roles, **{deleted_count}** deleted roles found",
                    inline=False
                )
            
            embed.set_footer(text=f"Use {ctx.prefix}level settings roles add/remove to modify • {valid_roles}/{len(level_roles)} roles active")
            await ctx.send(embed=embed)
            
        except Exception as e:
            await self.error_logger.log_error(
                f"Level Config Roles List Error in {ctx.guild.name}",
                f"Error listing level roles: {str(e)} | Guild: {ctx.guild.id} | User: {ctx.author.id}"
            )
            embed = discord.Embed(
                title=f"{emojis['warning']} Error",
                description="An error occurred while listing level roles. Please try again later.",
                color=0xff0000
            )
            await ctx.send(embed=embed)

    @level_settings_group.group(name="blacklist", invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def level_config_blacklist_group(self, ctx):
        """Manage XP blacklist (channels and roles excluded from gaining XP)"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title=f"{emojis['shield']} XP Blacklist Commands",
                description="Manage channels and roles that are excluded from gaining XP",
                color=0x006fb9
            )
            embed.add_field(
                name="Available Commands",
                value=(
                    f"`{ctx.prefix}level settings blacklist add channel #channel` - Exclude a channel\n"
                    f"`{ctx.prefix}level settings blacklist add role @role` - Exclude a role\n"
                    f"`{ctx.prefix}level settings blacklist remove channel #channel` - Remove channel exclusion\n"
                    f"`{ctx.prefix}level settings blacklist remove role @role` - Remove role exclusion\n"
                    f"`{ctx.prefix}level settings blacklist list` - List all exclusions"
                ),
                inline=False
            )
            embed.add_field(
                name="How it Works",
                value="• Excluded channels: Users gain no XP in these channels\n• Excluded roles: Users with these roles gain no XP anywhere",
                inline=False
            )
            await ctx.send(embed=embed)

    @level_config_blacklist_group.group(name="add", invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def level_config_blacklist_add_group(self, ctx):
        """Add items to XP blacklist"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title=f"{emojis['info']} Add to Blacklist",
                description="Specify what to add to the XP blacklist:",
                color=0x0099ff
            )
            embed.add_field(
                name="Commands",
                value=(
                    f"`{ctx.prefix}level settings blacklist add channel #channel` - Exclude channel\n"
                    f"`{ctx.prefix}level settings blacklist add role @role` - Exclude role"
                ),
                inline=False
            )
            await ctx.send(embed=embed)

    @level_config_blacklist_add_group.command(name="channel")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def level_config_blacklist_add_channel(self, ctx, channel: discord.TextChannel):
        """
        🚫 Add a channel to XP blacklist
        
        **Usage:**
        `{prefix}level settings blacklist add channel #general` - Exclude #general from XP
        """
        try:
            settings = await self.get_guild_settings(ctx.guild.id)
            excluded_channels = self.safe_json_loads(settings['exclude_channels'], [])
            
            if channel.id in excluded_channels:
                embed = discord.Embed(
                    title=f"{emojis['warning']} Already Excluded",
                    description=f"{channel.mention} is already excluded from XP gain.",
                    color=0xff9900
                )
                return await ctx.send(embed=embed)
            
            excluded_channels.append(channel.id)
            
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE guild_level_settings SET exclude_channels = ? WHERE guild_id = ?",
                    (json.dumps(excluded_channels), ctx.guild.id)
                )
                await db.commit()
            
            embed = discord.Embed(
                title=f"{emojis['check']} Channel Excluded",
                description=f"{channel.mention} has been added to the XP blacklist.\n\nUsers will no longer gain XP in this channel.",
                color=0x00ff00
            )
            embed.set_footer(text=f"Total excluded channels: {len(excluded_channels)}")
            await ctx.send(embed=embed)
            
        except Exception as e:
            await self.error_logger.log_error(
                f"Level Config Blacklist Add Channel Error in {ctx.guild.name}",
                f"Error adding channel to blacklist: {str(e)} | Guild: {ctx.guild.id} | User: {ctx.author.id}"
            )
            embed = discord.Embed(
                title=f"{emojis['warning']} Error",
                description="An error occurred while adding the channel to blacklist. Please try again later.",
                color=0xff0000
            )
            await ctx.send(embed=embed)

    @level_config_blacklist_add_group.command(name="role")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def level_config_blacklist_add_role(self, ctx, role: discord.Role):
        """
        🚫 Add a role to XP blacklist
        
        **Usage:**
        `{prefix}level settings blacklist add role @Muted` - Exclude @Muted role from XP
        """
        try:
            settings = await self.get_guild_settings(ctx.guild.id)
            excluded_roles = self.safe_json_loads(settings['exclude_roles'], [])
            
            if role.id in excluded_roles:
                embed = discord.Embed(
                    title=f"{emojis['warning']} Already Excluded",
                    description=f"{role.mention} is already excluded from XP gain.",
                    color=0xff9900
                )
                return await ctx.send(embed=embed)
            
            excluded_roles.append(role.id)
            
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE guild_level_settings SET exclude_roles = ? WHERE guild_id = ?",
                    (json.dumps(excluded_roles), ctx.guild.id)
                )
                await db.commit()
            
            embed = discord.Embed(
                title=f"{emojis['check']} Role Excluded",
                description=f"{role.mention} has been added to the XP blacklist.\n\nUsers with this role will no longer gain XP.",
                color=0x00ff00
            )
            embed.set_footer(text=f"Total excluded roles: {len(excluded_roles)}")
            await ctx.send(embed=embed)
            
        except Exception as e:
            await self.error_logger.log_error(
                f"Level Config Blacklist Add Role Error in {ctx.guild.name}",
                f"Error adding role to blacklist: {str(e)} | Guild: {ctx.guild.id} | User: {ctx.author.id}"
            )
            embed = discord.Embed(
                title=f"{emojis['warning']} Error",
                description="An error occurred while adding the role to blacklist. Please try again later.",
                color=0xff0000
            )
            await ctx.send(embed=embed)

    @level_config_blacklist_group.group(name="remove", invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def level_config_blacklist_remove_group(self, ctx):
        """Remove items from XP blacklist"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title=f"{emojis['info']} Remove from Blacklist",
                description="Specify what to remove from the XP blacklist:",
                color=0x0099ff
            )
            embed.add_field(
                name="Commands",
                value=(
                    f"`{ctx.prefix}level settings blacklist remove channel #channel` - Remove channel exclusion\n"
                    f"`{ctx.prefix}level settings blacklist remove role @role` - Remove role exclusion"
                ),
                inline=False
            )
            await ctx.send(embed=embed)

    @level_config_blacklist_remove_group.command(name="channel")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def level_config_blacklist_remove_channel(self, ctx, channel: discord.TextChannel):
        """
        ✅ Remove a channel from XP blacklist
        
        **Usage:**
        `{prefix}level settings blacklist remove channel #general` - Allow XP in #general again
        """
        try:
            settings = await self.get_guild_settings(ctx.guild.id)
            excluded_channels = self.safe_json_loads(settings['exclude_channels'], [])
            
            if channel.id not in excluded_channels:
                embed = discord.Embed(
                    title=f"{emojis['warning']} Not Excluded",
                    description=f"{channel.mention} is not currently excluded from XP gain.",
                    color=0xff9900
                )
                return await ctx.send(embed=embed)
            
            excluded_channels.remove(channel.id)
            
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE guild_level_settings SET exclude_channels = ? WHERE guild_id = ?",
                    (json.dumps(excluded_channels), ctx.guild.id)
                )
                await db.commit()
            
            embed = discord.Embed(
                title=f"{emojis['check']} Channel Unexcluded",
                description=f"{channel.mention} has been removed from the XP blacklist.\n\nUsers can now gain XP in this channel again.",
                color=0x00ff00
            )
            embed.set_footer(text=f"Total excluded channels: {len(excluded_channels)}")
            await ctx.send(embed=embed)
            
        except Exception as e:
            await self.error_logger.log_error(
                f"Level Config Blacklist Remove Channel Error in {ctx.guild.name}",
                f"Error removing channel from blacklist: {str(e)} | Guild: {ctx.guild.id} | User: {ctx.author.id}"
            )
            embed = discord.Embed(
                title=f"{emojis['warning']} Error",
                description="An error occurred while removing the channel from blacklist. Please try again later.",
                color=0xff0000
            )
            await ctx.send(embed=embed)

    @level_config_blacklist_remove_group.command(name="role")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def level_config_blacklist_remove_role(self, ctx, role: discord.Role):
        """
        ✅ Remove a role from XP blacklist
        
        **Usage:**
        `{prefix}level settings blacklist remove role @Muted` - Allow @Muted role to gain XP again
        """
        try:
            settings = await self.get_guild_settings(ctx.guild.id)
            excluded_roles = self.safe_json_loads(settings['exclude_roles'], [])
            
            if role.id not in excluded_roles:
                embed = discord.Embed(
                    title=f"{emojis['warning']} Not Excluded",
                    description=f"{role.mention} is not currently excluded from XP gain.",
                    color=0xff9900
                )
                return await ctx.send(embed=embed)
            
            excluded_roles.remove(role.id)
            
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE guild_level_settings SET exclude_roles = ? WHERE guild_id = ?",
                    (json.dumps(excluded_roles), ctx.guild.id)
                )
                await db.commit()
            
            embed = discord.Embed(
                title=f"{emojis['check']} Role Unexcluded",
                description=f"{role.mention} has been removed from the XP blacklist.\n\nUsers with this role can now gain XP again.",
                color=0x00ff00
            )
            embed.set_footer(text=f"Total excluded roles: {len(excluded_roles)}")
            await ctx.send(embed=embed)
            
        except Exception as e:
            await self.error_logger.log_error(
                f"Level Config Blacklist Remove Role Error in {ctx.guild.name}",
                f"Error removing role from blacklist: {str(e)} | Guild: {ctx.guild.id} | User: {ctx.author.id}"
            )
            embed = discord.Embed(
                title=f"{emojis['warning']} Error",
                description="An error occurred while removing the role from blacklist. Please try again later.",
                color=0xff0000
            )
            await ctx.send(embed=embed)

    @level_config_blacklist_group.command(name="list")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def level_config_blacklist_list(self, ctx):
        """
        📋 List all XP blacklist exclusions
        
        **Usage:**
        `{prefix}level settings blacklist list` - Show all excluded channels and roles
        """
        try:
            settings = await self.get_guild_settings(ctx.guild.id)
            excluded_channels = self.safe_json_loads(settings['exclude_channels'], [])
            excluded_roles = self.safe_json_loads(settings['exclude_roles'], [])
            
            embed = discord.Embed(
                title=f"{emojis['shield']} XP Blacklist",
                description=f"Channels and roles excluded from gaining XP in **{ctx.guild.name}**",
                color=0x006fb9
            )
            
            # Excluded Channels
            if excluded_channels:
                channel_list = []
                valid_channels = 0
                
                for channel_id in excluded_channels:
                    channel = ctx.guild.get_channel(channel_id)
                    if channel:
                        channel_list.append(f"• {channel.mention}")
                        valid_channels += 1
                    else:
                        channel_list.append(f"• {emojis['x']} *Deleted Channel* (ID: {channel_id})")
                
                embed.add_field(
                    name=f"🚫 Excluded Channels ({len(excluded_channels)})",
                    value="\n".join(channel_list) if channel_list else "None",
                    inline=False
                )
                
                if valid_channels != len(excluded_channels):
                    deleted_channels = len(excluded_channels) - valid_channels
                    embed.add_field(
                        name="⚠️ Channel Status",
                        value=f"{valid_channels} active, {deleted_channels} deleted",
                        inline=True
                    )
            else:
                embed.add_field(
                    name="🚫 Excluded Channels",
                    value="None",
                    inline=False
                )
            
            # Excluded Roles
            if excluded_roles:
                role_list = []
                valid_roles = 0
                
                for role_id in excluded_roles:
                    role = ctx.guild.get_role(role_id)
                    if role:
                        role_list.append(f"• {role.mention}")
                        valid_roles += 1
                    else:
                        role_list.append(f"• {emojis['x']} *Deleted Role* (ID: {role_id})")
                
                embed.add_field(
                    name=f"🚫 Excluded Roles ({len(excluded_roles)})",
                    value="\n".join(role_list) if role_list else "None",
                    inline=False
                )
                
                if valid_roles != len(excluded_roles):
                    deleted_roles = len(excluded_roles) - valid_roles
                    embed.add_field(
                        name="⚠️ Role Status",
                        value=f"{valid_roles} active, {deleted_roles} deleted",
                        inline=True
                    )
            else:
                embed.add_field(
                    name="🚫 Excluded Roles",
                    value="None",
                    inline=False
                )
            
            if not excluded_channels and not excluded_roles:
                embed.description = "No channels or roles are currently excluded from XP gain."
                embed.add_field(
                    name="Get Started",
                    value=f"Add exclusions with:\n`{ctx.prefix}level settings blacklist add channel #channel`\n`{ctx.prefix}level settings blacklist add role @role`",
                    inline=False
                )
            
            embed.set_footer(text=f"Use {ctx.prefix}level settings blacklist add/remove to modify")
            await ctx.send(embed=embed)
            
        except Exception as e:
            await self.error_logger.log_error(
                f"Level Config Blacklist List Error in {ctx.guild.name}",
                f"Error listing blacklist: {str(e)} | Guild: {ctx.guild.id} | User: {ctx.author.id}"
            )
            embed = discord.Embed(
                title=f"{emojis['warning']} Error",
                description="An error occurred while listing the blacklist. Please try again later.",
                color=0xff0000
            )
            await ctx.send(embed=embed)

    # ================= ROLE SETUP =================
    @level_group.group(name="role", invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @blacklist_check()
    @ignore_check()
    async def level_role_group(self, ctx):
        """Role management for leveling system"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title=f"{emojis['settings']} Level Role Commands",
                description="Manage roles attached to reaching levels",
                color=0x006fb9
            )
            embed.add_field(name=f"{ctx.prefix}level role setup", value="Complete role setup interface", inline=False)
            embed.add_field(name=f"{ctx.prefix}level role add <level> <role>", value="Add a role for a level", inline=False)
            embed.add_field(name=f"{ctx.prefix}level role remove <level> <role>", value="Remove a role from a level", inline=False)
            embed.add_field(name=f"{ctx.prefix}level role list", value="List all level roles", inline=False)
            await ctx.send(embed=embed)

    @level_role_group.command(name="setup")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def level_role_setup(self, ctx):
        """
        🎭 Complete setup for roles attached to reaching levels
        
        **Usage:**
        `{prefix}level role setup` - Interactive role setup
        """
        embed = discord.Embed(
            title=f"{emojis['crown']} Level Role Setup",
            description="Configure roles that are automatically assigned when users reach specific levels.",
            color=0x006fb9
        )
        
        # Get current level roles
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("""
                SELECT level, role_id FROM level_roles 
                WHERE guild_id = ? 
                ORDER BY level ASC
            """, (ctx.guild.id,)) as cursor:
                level_roles = list(await cursor.fetchall())
        
        if level_roles:
            role_text = ""
            for level, role_id in level_roles[:10]:  # Show first 10
                role = ctx.guild.get_role(role_id)
                role_name = role.name if role else "Deleted Role"
                role_text += f"Level **{level}**: {role_name}\n"
            
            if len(level_roles) > 10:
                role_text += f"\n... and {len(level_roles) - 10} more"
            
            embed.add_field(name="Current Level Roles", value=role_text, inline=False)
        else:
            embed.add_field(name="Current Level Roles", value="No level roles configured", inline=False)
        
        view = LevelRoleSetupView(ctx.guild.id)
        await ctx.send(embed=embed, view=view)

    @level_role_group.command(name="add")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def level_role_add(self, ctx, level: int, role: discord.Role):
        """
        ➕ Add a role reward for reaching a level
        
        **Usage:**
        `{prefix}level role add 5 @Member` - Give @Member role at level 5
        """
        try:
            if level < 1 or level > 1000:
                embed = discord.Embed(
                    title=f"{emojis['error']} Invalid Level",
                    description="Level must be between 1 and 1000.",
                    color=0xff0000
                )
                return await ctx.send(embed=embed)
            
            # Check if bot can manage this role
            if role >= ctx.guild.me.top_role:
                embed = discord.Embed(
                    title=f"{emojis['error']} Role Too High",
                    description=f"I cannot manage {role.mention} because it's higher than my highest role.\n\nPlease move my role above it in the server settings.",
                    color=0xff0000
                )
                return await ctx.send(embed=embed)
            
            # Add to database
            async with aiosqlite.connect(DB_PATH) as db:
                # Check if level already has a role
                async with db.execute(
                    "SELECT role_id FROM level_roles WHERE guild_id = ? AND level = ?",
                    (ctx.guild.id, level)
                ) as cursor:
                    existing = await cursor.fetchone()
                
                if existing:
                    # Update existing
                    await db.execute(
                        "UPDATE level_roles SET role_id = ? WHERE guild_id = ? AND level = ?",
                        (role.id, ctx.guild.id, level)
                    )
                    action = "updated"
                else:
                    # Insert new
                    await db.execute(
                        "INSERT INTO level_roles (guild_id, level, role_id) VALUES (?, ?, ?)",
                        (ctx.guild.id, level, role.id)
                    )
                    action = "added"
                
                await db.commit()
            
            embed = discord.Embed(
                title=f"{emojis['check']} Level Role {action.title()}",
                description=f"**Level {level}:** {role.mention}",
                color=0x00ff00
            )
            
            if existing:
                old_role = ctx.guild.get_role(existing[0])
                old_role_name = old_role.mention if old_role else "Deleted Role"
                embed.add_field(
                    name="Previous Role",
                    value=old_role_name,
                    inline=True
                )
            
            embed.set_footer(text=f"Users who reach level {level} will automatically receive this role")
            await ctx.send(embed=embed)
            
        except Exception as e:
            await self.error_logger.log_error(
                f"Level Role Add Error in {ctx.guild.name}",
                f"Error adding level role: {str(e)} | Guild: {ctx.guild.id} | User: {ctx.author.id}"
            )
            embed = discord.Embed(
                title=f"{emojis['warning']} Error",
                description="An error occurred while adding the level role. Please try again later.",
                color=0xff0000
            )
            await ctx.send(embed=embed)

    @level_role_group.command(name="remove")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def level_role_remove(self, ctx, level: int):
        """
        ➖ Remove a role reward for a level
        
        **Usage:**
        `{prefix}level role remove 5` - Remove role reward for level 5
        """
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                # Check if level exists
                async with db.execute(
                    "SELECT role_id FROM level_roles WHERE guild_id = ? AND level = ?",
                    (ctx.guild.id, level)
                ) as cursor:
                    existing = await cursor.fetchone()
                
                if not existing:
                    embed = discord.Embed(
                        title=f"{emojis['error']} Level Role Not Found",
                        description=f"No role reward found for level {level}.",
                        color=0xff0000
                    )
                    return await ctx.send(embed=embed)
                
                # Remove from database
                await db.execute(
                    "DELETE FROM level_roles WHERE guild_id = ? AND level = ?",
                    (ctx.guild.id, level)
                )
                await db.commit()
            
            # Get role info for confirmation
            removed_role = ctx.guild.get_role(existing[0])
            role_name = removed_role.mention if removed_role else "Deleted Role"
            
            embed = discord.Embed(
                title=f"{emojis['check']} Level Role Removed",
                description=f"Removed role reward for **Level {level}**",
                color=0x00ff00
            )
            embed.add_field(
                name="Removed Role",
                value=role_name,
                inline=True
            )
            embed.set_footer(text="Users will no longer receive this role when reaching this level")
            await ctx.send(embed=embed)
            
        except Exception as e:
            await self.error_logger.log_error(
                f"Level Role Remove Error in {ctx.guild.name}",
                f"Error removing level role: {str(e)} | Guild: {ctx.guild.id} | User: {ctx.author.id}"
            )
            embed = discord.Embed(
                title=f"{emojis['warning']} Error",
                description="An error occurred while removing the level role. Please try again later.",
                color=0xff0000
            )
            await ctx.send(embed=embed)

    @level_role_group.command(name="list")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def level_role_list(self, ctx):
        """
        📋 List all level role rewards
        
        **Usage:**
        `{prefix}level role list` - Show all level roles
        """
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute(
                    "SELECT level, role_id FROM level_roles WHERE guild_id = ? ORDER BY level ASC",
                    (ctx.guild.id,)
                ) as cursor:
                    level_roles = list(await cursor.fetchall())
            
            if not level_roles:
                embed = discord.Embed(
                    title=f"{emojis['warning']} No Level Roles",
                    description="No level role rewards have been configured yet.",
                    color=0xff9900
                )
                embed.add_field(
                    name="Get Started",
                    value=f"Add your first level role with:\n`{ctx.prefix}level role add <level> <role>`",
                    inline=False
                )
                return await ctx.send(embed=embed)
            
            embed = discord.Embed(
                title=f"{emojis['crown']} Level Role Rewards",
                description=f"**{len(level_roles)}** level roles configured for **{ctx.guild.name}**",
                color=0x006fb9
            )
            
            role_list = []
            valid_roles = 0
            
            for level, role_id in level_roles:
                role = ctx.guild.get_role(role_id)
                if role:
                    role_list.append(f"**Level {level}:** {role.mention}")
                    valid_roles += 1
                else:
                    role_list.append(f"**Level {level}:** {emojis['x']} *Deleted Role* (ID: {role_id})")
            
            # Split into fields if too many
            chunk_size = 15
            for i in range(0, len(role_list), chunk_size):
                chunk = role_list[i:i + chunk_size]
                field_name = "Level Roles" if i == 0 else f"Level Roles (continued)"
                embed.add_field(
                    name=field_name,
                    value="\n".join(chunk),
                    inline=False
                )
            
            # Add summary
            if valid_roles != len(level_roles):
                deleted_count = len(level_roles) - valid_roles
                embed.add_field(
                    name="⚠️ Status",
                    value=f"**{valid_roles}** active roles, **{deleted_count}** deleted roles found",
                    inline=False
                )
            
            embed.set_footer(text=f"Use {ctx.prefix}level role add/remove to modify • {valid_roles}/{len(level_roles)} roles active")
            await ctx.send(embed=embed)
            
        except Exception as e:
            await self.error_logger.log_error(
                f"Level Role List Error in {ctx.guild.name}",
                f"Error listing level roles: {str(e)} | Guild: {ctx.guild.id} | User: {ctx.author.id}"
            )
            embed = discord.Embed(
                title=f"{emojis['warning']} Error",
                description="An error occurred while listing level roles. Please try again later.",
                color=0xff0000
            )
            await ctx.send(embed=embed)

    # ================= ADMIN COMMANDS =================
    @level_group.group(name="admin", invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def level_admin_group(self, ctx):
        """Admin commands for level management"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title=f"{emojis['crown']} Level Admin Commands",
                description="Administrative commands for managing user levels and XP",
                color=0x006fb9
            )
            embed.add_field(name=f"{ctx.prefix}level admin set <user> <level>", value="Set user's level", inline=False)
            embed.add_field(name=f"{ctx.prefix}level admin add <user> <xp>", value="Add XP to user", inline=False)
            embed.add_field(name=f"{ctx.prefix}level admin remove <user> <levels>", value="Remove levels from user", inline=False)
            embed.add_field(name=f"{ctx.prefix}level admin reset <user>", value="Reset user's XP/level completely", inline=False)
            await ctx.send(embed=embed)

    @level_admin_group.command(name="set")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def level_admin_set(self, ctx, member: discord.Member, level: int):
        """
        👑 Set a user's level
        
        **Usage:**
        `{prefix}level admin set @user 10` - Set user to level 10
        """
        try:
            if level < 0:
                embed = discord.Embed(
                    title=f"{emojis['error']} Invalid Level",
                    description="Level cannot be negative.",
                    color=0xff0000
                )
                return await ctx.send(embed=embed)
            
            settings = await self.get_guild_settings(ctx.guild.id)
            total_xp = self.calculate_xp_for_level(level, settings['level_formula'])
            
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("""
                    INSERT OR REPLACE INTO user_levels 
                    (user_id, guild_id, level, total_xp, xp, last_xp_gain)
                    VALUES (?, ?, ?, ?, 0, ?)
                """, (member.id, ctx.guild.id, level, total_xp, self.tz_helpers.get_utc_now().isoformat()))
                await db.commit()
            
            # Assign level roles
            await self.assign_level_roles(member, level, settings)
            
            embed = discord.Embed(
                title=f"{emojis['check']} Level Set",
                description=f"Set **{member.display_name}** to Level **{level:,}** (**{total_xp:,}** XP)",
                color=0x00ff00
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            await self.error_logger.log_error(
                f"Level Admin Set Error in {ctx.guild.name}",
                f"Error setting user level: {str(e)} | Guild: {ctx.guild.id} | Admin: {ctx.author.id} | Target: {member.id} | Level: {level}"
            )
            embed = discord.Embed(
                title=f"{emojis['warning']} Error",
                description="An error occurred while setting the user's level. Please try again later.",
                color=0xff0000
            )
            await ctx.send(embed=embed)

    @level_admin_group.command(name="add")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def level_admin_add(self, ctx, member: discord.Member, xp: int):
        """
        ⚡ Add XP to a user
        
        **Usage:**
        `{prefix}level admin add @user 1000` - Add 1000 XP to user
        """
        if xp <= 0:
            embed = discord.Embed(
                title=f"{emojis['error']} Invalid XP",
                description="XP amount must be positive.",
                color=0xff0000
            )
            return await ctx.send(embed=embed)
        
        settings = await self.get_guild_settings(ctx.guild.id)
        user_data = await self.get_user_data(ctx.guild.id, member.id)
        old_level = user_data['level']
        
        leveled_up, _, new_level = await self.update_user_xp(
            ctx.guild.id, member.id, xp, settings
        )
        
        if leveled_up:
            await self.assign_level_roles(member, new_level, settings)
        
        new_total = user_data['total_xp'] + xp
        
        embed = discord.Embed(
            title=f"{emojis['check']} XP Added",
            description=f"Added **{xp:,}** XP to **{member.display_name}**",
            color=0x00ff00
        )
        embed.add_field(name="New Total XP", value=f"{new_total:,}", inline=True)
        embed.add_field(name="New Level", value=f"{new_level:,}", inline=True)
        
        if leveled_up:
            embed.add_field(name="Level Up!", value=f"Level {old_level} → {new_level}", inline=True)
        
        await ctx.send(embed=embed)

    @level_admin_group.command(name="remove")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def level_admin_remove(self, ctx, member: discord.Member, levels: int):
        """
        📉 Remove levels from a user
        
        **Usage:**
        `{prefix}level admin remove @user 2` - Remove 2 levels from user
        """
        if levels <= 0:
            embed = discord.Embed(
                title=f"{emojis['error']} Invalid Levels",
                description="Level amount must be positive.",
                color=0xff0000
            )
            return await ctx.send(embed=embed)
        
        user_data = await self.get_user_data(ctx.guild.id, member.id)
        old_level = user_data['level']
        new_level = max(0, old_level - levels)
        
        settings = await self.get_guild_settings(ctx.guild.id)
        new_total_xp = self.calculate_xp_for_level(new_level, settings['level_formula'])
        
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                UPDATE user_levels 
                SET total_xp = ?, level = ?, xp = 0
                WHERE user_id = ? AND guild_id = ?
            """, (new_total_xp, new_level, member.id, ctx.guild.id))
            await db.commit()
        
        # Update roles
        await self.assign_level_roles(member, new_level, settings)
        
        embed = discord.Embed(
            title=f"{emojis['check']} Levels Removed",
            description=f"Removed **{levels}** levels from **{member.display_name}**",
            color=0x00ff00
        )
        embed.add_field(name="Previous Level", value=f"{old_level:,}", inline=True)
        embed.add_field(name="New Level", value=f"{new_level:,}", inline=True)
        embed.add_field(name="New Total XP", value=f"{new_total_xp:,}", inline=True)
        
        await ctx.send(embed=embed)

    @level_admin_group.command(name="reset")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def level_admin_reset(self, ctx, member: discord.Member):
        """
        🔄 Reset a user's XP/level completely
        
        **Usage:**
        `{prefix}level admin reset @user` - Reset user's progress
        """
        view = ConfirmResetView(member.id, ctx.guild.id)
        
        embed = discord.Embed(
            title=f"{emojis['warning']} Confirm User Reset",
            description=f"Are you sure you want to reset **{member.display_name}**'s level and XP?\n\n**This action cannot be undone!**",
            color=0xff9900
        )
        
        await ctx.send(embed=embed, view=view)

    @level_group.command(name="reset")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    async def level_server_reset(self, ctx):
        """
        🗑️ Reset the entire level database for the server
        
        **Usage:**
        `{prefix}level reset` - Reset all server leveling data
        **Requires Administrator permission**
        """
        view = ConfirmServerResetView(ctx.guild.id)
        
        embed = discord.Embed(
            title=f"{emojis['warning']} Confirm Server Reset",
            description=f"Are you sure you want to reset **ALL** leveling data for this server?\n\n"
                       f"This will delete:\n"
                       f"• All user levels and XP\n"
                       f"• All level role configurations\n"
                       f"• All server settings\n\n"
                       f"**THIS ACTION CANNOT BE UNDONE!**",
            color=0xff0000
        )
        
        await ctx.send(embed=embed, view=view)


# ================= VIEW CLASSES =================

class XPSettingsModal(discord.ui.Modal, title='⚡ XP Settings Configuration'):
    def __init__(self, current_settings: Dict[str, Any], error_logger=None):
        super().__init__()
        self.error_logger = error_logger
        
        # Pre-fill with current values
        self.xp_per_message.default = str(current_settings.get('xp_per_message', 15))
        self.xp_variance.default = str(current_settings.get('xp_variance', 10))
        self.xp_cooldown.default = str(current_settings.get('xp_cooldown', 60))
        
    xp_per_message = discord.ui.TextInput(
        label='Base XP per Message',
        placeholder='15',
        min_length=1,
        max_length=3
    )
    
    xp_variance = discord.ui.TextInput(
        label='XP Variance (± range)',
        placeholder='10',
        min_length=1,
        max_length=3
    )
    
    xp_cooldown = discord.ui.TextInput(
        label='XP Cooldown (seconds)',
        placeholder='60',
        min_length=1,
        max_length=4
    )

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message("This command can only be used in a server!", ephemeral=True)
        
        try:
            xp_base = int(self.xp_per_message.value)
            xp_var = int(self.xp_variance.value)
            cooldown = int(self.xp_cooldown.value)
            
            if xp_base < 1 or xp_base > 500:
                raise ValueError("Base XP must be between 1-500")
            if xp_var < 0 or xp_var > 100:
                raise ValueError("XP variance must be between 0-100")
            if cooldown < 0 or cooldown > 3600:
                raise ValueError("Cooldown must be between 0-3600 seconds")
            
            # Update database
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("""
                    UPDATE guild_level_settings 
                    SET xp_per_message = ?, xp_variance = ?, xp_cooldown = ?
                    WHERE guild_id = ?
                """, (xp_base, xp_var, cooldown, interaction.guild.id))
                await db.commit()
            
            embed = discord.Embed(
                title=f"{emojis['check']} XP Settings Updated",
                description=f"**Base XP:** {xp_base} ± {xp_var} XP per message\n**Cooldown:** {cooldown} seconds",
                color=0x00ff00
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError as e:
            await interaction.response.send_message(f"❌ Invalid input: {e}", ephemeral=True)
        except Exception as e:
            if self.error_logger:
                await self.error_logger.log_error(
                    f"XP Settings Update Error",
                    f"Error updating XP settings: {str(e)} | Guild: {interaction.guild.id}"
                )
            await interaction.response.send_message("❌ An error occurred while updating XP settings.", ephemeral=True)

class ChannelSettingsView(discord.ui.View):
    def __init__(self, current_settings: Dict[str, Any], error_logger=None):
        super().__init__(timeout=300)
        self.error_logger = error_logger
        self.current_settings = current_settings

    @discord.ui.button(label="📋 Exclude Channels from XP", style=discord.ButtonStyle.secondary, row=0)
    async def exclude_channels_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to open paginated channel exclusion selector"""
        if not interaction.guild:
            return await interaction.response.send_message("This command can only be used in a server!", ephemeral=True)
            
        async def exclude_channels_callback(interaction_inner, select):
            try:
                channel_ids = [int(channel_id) for channel_id in select.values]
                
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute(
                        "UPDATE guild_level_settings SET exclude_channels = ? WHERE guild_id = ?",
                        (json.dumps(channel_ids), interaction.guild and interaction.guild.id)
                    )
                    await db.commit()
                
                channel_mentions = [f"<#{channel_id}>" for channel_id in channel_ids]
                embed = discord.Embed(
                    title=f"{emojis['check']} Excluded Channels Updated",
                    description=f"**{len(channel_ids)}** channels excluded from XP:\n" + "\n".join(channel_mentions) if channel_mentions else "No channels excluded from XP",
                    color=0x00ff00
                )
                await interaction_inner.response.edit_message(embed=embed, view=None)
                
            except Exception as e:
                if self.error_logger:
                    await self.error_logger.log_error(
                        f"Channel Settings Error",
                        f"Error updating excluded channels: {str(e)} | Guild: {interaction.guild and interaction.guild.id}"
                    )
                await interaction_inner.response.send_message("❌ An error occurred while updating channel settings.", ephemeral=True)

        view = PaginatedChannelView(
            interaction.guild,
            channel_types=[discord.ChannelType.text, discord.ChannelType.forum],
            exclude_channels=[],
            custom_callback=exclude_channels_callback,
            timeout=300
        )

        embed = discord.Embed(
            title="📋 Exclude Channels from XP",
            description="Select channels where users should NOT earn XP points.",
            color=0x5865F2
        )
        embed.set_footer(text="Use the dropdown menu to select channels. Navigate pages if needed.")

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="📢 Level Up Channel", style=discord.ButtonStyle.secondary, row=0)
    async def level_up_channel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to open paginated channel selector for level up announcements"""
        if not interaction.guild:
            return await interaction.response.send_message("This command can only be used in a server!", ephemeral=True)
            
        async def level_up_channel_callback(interaction_inner, select):
            try:
                channel_id = int(select.values[0]) if select.values else None
                
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute(
                        "UPDATE guild_level_settings SET level_channel_id = ? WHERE guild_id = ?",
                        (channel_id, interaction.guild and interaction.guild.id)
                    )
                    await db.commit()
                
                embed = discord.Embed(
                    title=f"{emojis['check']} Level Up Channel Updated",
                    description=f"Level up messages will be sent to <#{channel_id}>" if channel_id else "Level up messages will be sent to the same channel as the user's message",
                    color=0x00ff00
                )
                await interaction_inner.response.edit_message(embed=embed, view=None)
                
            except Exception as e:
                if self.error_logger:
                    await self.error_logger.log_error(
                        f"Level Channel Settings Error",
                        f"Error updating level up channel: {str(e)} | Guild: {interaction.guild and interaction.guild.id}"
                    )
                await interaction_inner.response.send_message("❌ An error occurred while updating level up channel.", ephemeral=True)

        view = PaginatedChannelView(
            interaction.guild,
            channel_types=[discord.ChannelType.text],
            exclude_channels=[],
            custom_callback=level_up_channel_callback,
            timeout=300
        )

        embed = discord.Embed(
            title="📢 Level Up Announcement Channel",
            description="Select a channel for level up announcements, or select none to use the same channel as the user's message.",
            color=0x5865F2
        )
        embed.set_footer(text="Use the dropdown menu to select a channel. Navigate pages if needed.")

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class RoleSettingsView(discord.ui.View):
    def __init__(self, error_logger=None):
        super().__init__(timeout=300)
        self.error_logger = error_logger

    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="Select roles to exclude from gaining XP",
        min_values=0,
        max_values=25
    )
    async def exclude_roles(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        if not interaction.guild:
            return await interaction.response.send_message("This command can only be used in a server!", ephemeral=True)
        
        try:
            role_ids = [role.id for role in select.values]
            
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE guild_level_settings SET exclude_roles = ? WHERE guild_id = ?",
                    (json.dumps(role_ids), interaction.guild.id)
                )
                await db.commit()
            
            role_mentions = [role.mention for role in select.values]
            embed = discord.Embed(
                title=f"{emojis['check']} Excluded Roles Updated",
                description=f"**{len(role_ids)}** roles excluded from XP:\n" + "\n".join(role_mentions) if role_mentions else "No roles excluded from XP",
                color=0x00ff00
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            if self.error_logger:
                await self.error_logger.log_error(
                    f"Role Settings Error",
                    f"Error updating excluded roles: {str(e)} | Guild: {interaction.guild.id}"
                )
            await interaction.response.send_message("❌ An error occurred while updating role settings.", ephemeral=True)

    @discord.ui.button(label="Add Level Role", style=discord.ButtonStyle.green, emoji="➕")
    async def add_level_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AddLevelRoleModal(self.error_logger)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Remove Level Role", style=discord.ButtonStyle.red, emoji="➖")
    async def remove_level_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = RemoveLevelRoleModal(self.error_logger)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="View Level Roles", style=discord.ButtonStyle.secondary, emoji="📋")
    async def view_level_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild:
            return await interaction.response.send_message("This command can only be used in a server!", ephemeral=True)
        
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute(
                    "SELECT level, role_id FROM level_roles WHERE guild_id = ? ORDER BY level ASC",
                    (interaction.guild.id,)
                ) as cursor:
                    roles = list(await cursor.fetchall())
            
            if not roles:
                embed = discord.Embed(
                    title=f"{emojis['warning']} No Level Roles",
                    description="No level roles have been configured yet.",
                    color=0xff9900
                )
            else:
                embed = discord.Embed(
                    title=f"{emojis['crown']} Level Roles",
                    description=f"**{len(roles)}** level roles configured:",
                    color=0x006fb9
                )
                
                role_list = []
                for level, role_id in roles:
                    role = interaction.guild.get_role(role_id)
                    if role:
                        role_list.append(f"**Level {level}:** {role.mention}")
                    else:
                        role_list.append(f"**Level {level}:** *Deleted Role* ({role_id})")
                
                # Split into chunks if too long
                chunk_size = 20
                for i in range(0, len(role_list), chunk_size):
                    chunk = role_list[i:i + chunk_size]
                    embed.add_field(
                        name=f"Roles {i+1}-{min(i+chunk_size, len(role_list))}",
                        value="\n".join(chunk),
                        inline=False
                    )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            if self.error_logger:
                await self.error_logger.log_error(
                    f"View Level Roles Error",
                    f"Error viewing level roles: {str(e)} | Guild: {interaction.guild.id}"
                )
            await interaction.response.send_message("❌ An error occurred while viewing level roles.", ephemeral=True)

class AddLevelRoleModal(discord.ui.Modal, title='➕ Add Level Role'):
    def __init__(self, error_logger=None):
        super().__init__()
        self.error_logger = error_logger
        
    level = discord.ui.TextInput(
        label='Level Required',
        placeholder='5',
        min_length=1,
        max_length=4
    )
    
    role_id = discord.ui.TextInput(
        label='Role ID or @mention',
        placeholder='123456789012345678 or @RoleName',
        min_length=1,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message("This command can only be used in a server!", ephemeral=True)
        
        try:
            level_num = int(self.level.value)
            if level_num < 1 or level_num > 1000:
                raise ValueError("Level must be between 1-1000")
            
            # Parse role ID
            role_input = self.role_id.value.strip()
            if role_input.startswith('<@&') and role_input.endswith('>'):
                role_id = int(role_input[3:-1])
            else:
                role_id = int(role_input)
            
            # Verify role exists
            role = interaction.guild.get_role(role_id)
            if not role:
                raise ValueError("Role not found in this server")
            
            # Add to database
            async with aiosqlite.connect(DB_PATH) as db:
                # Check if level already exists
                async with db.execute(
                    "SELECT role_id FROM level_roles WHERE guild_id = ? AND level = ?",
                    (interaction.guild.id, level_num)
                ) as cursor:
                    existing = await cursor.fetchone()
                
                if existing:
                    # Update existing
                    await db.execute(
                        "UPDATE level_roles SET role_id = ? WHERE guild_id = ? AND level = ?",
                        (role_id, interaction.guild.id, level_num)
                    )
                else:
                    # Insert new
                    await db.execute(
                        "INSERT INTO level_roles (guild_id, level, role_id) VALUES (?, ?, ?)",
                        (interaction.guild.id, level_num, role_id)
                    )
                await db.commit()
            
            embed = discord.Embed(
                title=f"{emojis['check']} Level Role Added",
                description=f"**Level {level_num}:** {role.mention}",
                color=0x00ff00
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError as e:
            await interaction.response.send_message(f"❌ Invalid input: {e}", ephemeral=True)
        except Exception as e:
            if self.error_logger:
                await self.error_logger.log_error(
                    f"Add Level Role Error",
                    f"Error adding level role: {str(e)} | Guild: {interaction.guild.id}"
                )
            await interaction.response.send_message("❌ An error occurred while adding the level role.", ephemeral=True)

class RemoveLevelRoleModal(discord.ui.Modal, title='➖ Remove Level Role'):
    def __init__(self, error_logger=None):
        super().__init__()
        self.error_logger = error_logger
        
    level = discord.ui.TextInput(
        label='Level to Remove',
        placeholder='5',
        min_length=1,
        max_length=4
    )

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message("This command can only be used in a server!", ephemeral=True)
        
        try:
            level_num = int(self.level.value)
            
            async with aiosqlite.connect(DB_PATH) as db:
                # Check if level exists
                async with db.execute(
                    "SELECT role_id FROM level_roles WHERE guild_id = ? AND level = ?",
                    (interaction.guild.id, level_num)
                ) as cursor:
                    existing = await cursor.fetchone()
                
                if not existing:
                    raise ValueError(f"No level role found for level {level_num}")
                
                # Remove from database
                await db.execute(
                    "DELETE FROM level_roles WHERE guild_id = ? AND level = ?",
                    (interaction.guild.id, level_num)
                )
                await db.commit()
            
            embed = discord.Embed(
                title=f"{emojis['check']} Level Role Removed",
                description=f"Level role for **Level {level_num}** has been removed.",
                color=0x00ff00
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError as e:
            await interaction.response.send_message(f"❌ {e}", ephemeral=True)
        except Exception as e:
            if self.error_logger and interaction.guild:
                await self.error_logger.log_error(
                    f"Remove Level Role Error",
                    f"Error removing level role: {str(e)} | Guild: {interaction.guild.id}"
                )
            await interaction.response.send_message("❌ An error occurred while removing the level role.", ephemeral=True)

class MultiplierSettingsView(discord.ui.View):
    def __init__(self, error_logger=None):
        super().__init__(timeout=300)
        self.error_logger = error_logger

    @discord.ui.button(label="Add XP Multiplier", style=discord.ButtonStyle.green, emoji="⚡")
    async def add_multiplier(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AddMultiplierModal(self.error_logger)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Remove Multiplier", style=discord.ButtonStyle.red, emoji="➖")
    async def remove_multiplier(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = RemoveMultiplierModal(self.error_logger)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="View Multipliers", style=discord.ButtonStyle.secondary, emoji="📊")
    async def view_multipliers(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild:
            return await interaction.response.send_message("This command can only be used in a server!", ephemeral=True)
        
        try:
            # Get guild settings directly from database
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute(
                    "SELECT multiplier_roles FROM guild_level_settings WHERE guild_id = ?",
                    (interaction.guild.id,)
                ) as cursor:
                    row = await cursor.fetchone()
            
            multiplier_data = row[0] if row and row[0] else '{}'
            try:
                multipliers = json.loads(multiplier_data) if multiplier_data else {}
            except:
                multipliers = {}
            
            if not multipliers:
                embed = discord.Embed(
                    title=f"{emojis['warning']} No XP Multipliers",
                    description="No XP multipliers have been configured yet.",
                    color=0xff9900
                )
            else:
                embed = discord.Embed(
                    title=f"{emojis['zap']} XP Multipliers",
                    description=f"**{len(multipliers)}** role multipliers configured:",
                    color=0x006fb9
                )
                
                multiplier_list = []
                for role_id, multiplier in multipliers.items():
                    role = interaction.guild.get_role(int(role_id))
                    if role:
                        multiplier_list.append(f"{role.mention}: **{multiplier}x** XP")
                    else:
                        multiplier_list.append(f"*Deleted Role* ({role_id}): **{multiplier}x** XP")
                
                embed.add_field(
                    name="Active Multipliers",
                    value="\n".join(multiplier_list) if multiplier_list else "None",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            if self.error_logger:
                await self.error_logger.log_error(
                    f"View Multipliers Error",
                    f"Error viewing multipliers: {str(e)} | Guild: {interaction.guild.id}"
                )
            await interaction.response.send_message("❌ An error occurred while viewing multipliers.", ephemeral=True)

class AddMultiplierModal(discord.ui.Modal, title='⚡ Add XP Multiplier'):
    def __init__(self, error_logger=None):
        super().__init__()
        self.error_logger = error_logger
        
    role_id = discord.ui.TextInput(
        label='Role ID or @mention',
        placeholder='123456789012345678 or @RoleName',
        min_length=1,
        max_length=100
    )
    
    multiplier = discord.ui.TextInput(
        label='XP Multiplier (e.g., 2.0 for 2x XP)',
        placeholder='2.0',
        min_length=1,
        max_length=5
    )

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message("This command can only be used in a server!", ephemeral=True)
        
        try:
            # Parse role ID
            role_input = self.role_id.value.strip()
            if role_input.startswith('<@&') and role_input.endswith('>'):
                role_id = int(role_input[3:-1])
            else:
                role_id = int(role_input)
            
            # Verify role exists
            role = interaction.guild.get_role(role_id)
            if not role:
                raise ValueError("Role not found in this server")
            
            # Parse multiplier
            mult_value = float(self.multiplier.value)
            if mult_value < 0.1 or mult_value > 10.0:
                raise ValueError("Multiplier must be between 0.1 and 10.0")
            
            # Update database - get current multipliers
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute(
                    "SELECT multiplier_roles FROM guild_level_settings WHERE guild_id = ?",
                    (interaction.guild.id,)
                ) as cursor:
                    row = await cursor.fetchone()
            
            multiplier_data = row[0] if row and row[0] else '{}'
            try:
                multipliers = json.loads(multiplier_data) if multiplier_data else {}
            except:
                multipliers = {}
            multipliers[str(role_id)] = mult_value
            
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE guild_level_settings SET multiplier_roles = ? WHERE guild_id = ?",
                    (json.dumps(multipliers), interaction.guild.id)
                )
                await db.commit()
            
            embed = discord.Embed(
                title=f"{emojis['check']} XP Multiplier Added",
                description=f"{role.mention}: **{mult_value}x** XP multiplier",
                color=0x00ff00
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError as e:
            await interaction.response.send_message(f"❌ Invalid input: {e}", ephemeral=True)
        except Exception as e:
            if self.error_logger and interaction.guild:
                await self.error_logger.log_error(
                    f"Add Multiplier Error",
                    f"Error adding multiplier: {str(e)} | Guild: {interaction.guild.id}"
                )
            await interaction.response.send_message("❌ An error occurred while adding the multiplier.", ephemeral=True)

class RemoveMultiplierModal(discord.ui.Modal, title='➖ Remove XP Multiplier'):
    def __init__(self, error_logger=None):
        super().__init__()
        self.error_logger = error_logger
        
    role_id = discord.ui.TextInput(
        label='Role ID or @mention to remove',
        placeholder='123456789012345678 or @RoleName',
        min_length=1,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message("This command can only be used in a server!", ephemeral=True)
        
        try:
            # Parse role ID
            role_input = self.role_id.value.strip()
            if role_input.startswith('<@&') and role_input.endswith('>'):
                role_id = int(role_input[3:-1])
            else:
                role_id = int(role_input)
            
            # Update database - get current multipliers
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute(
                    "SELECT multiplier_roles FROM guild_level_settings WHERE guild_id = ?",
                    (interaction.guild.id,)
                ) as cursor:
                    row = await cursor.fetchone()
            
            multiplier_data = row[0] if row and row[0] else '{}'
            try:
                multipliers = json.loads(multiplier_data) if multiplier_data else {}
            except:
                multipliers = {}
            
            if str(role_id) not in multipliers:
                raise ValueError("This role doesn't have an XP multiplier")
            
            del multipliers[str(role_id)]
            
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE guild_level_settings SET multiplier_roles = ? WHERE guild_id = ?",
                    (json.dumps(multipliers), interaction.guild.id)
                )
                await db.commit()
            
            role = interaction.guild.get_role(role_id)
            role_name = role.mention if role else f"Role ID: {role_id}"
            
            embed = discord.Embed(
                title=f"{emojis['check']} XP Multiplier Removed",
                description=f"Removed XP multiplier for {role_name}",
                color=0x00ff00
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError as e:
            await interaction.response.send_message(f"❌ {e}", ephemeral=True)
        except Exception as e:
            if self.error_logger and interaction.guild:
                await self.error_logger.log_error(
                    f"Remove Multiplier Error",
                    f"Error removing multiplier: {str(e)} | Guild: {interaction.guild.id}"
                )
            await interaction.response.send_message("❌ An error occurred while removing the multiplier.", ephemeral=True)

class MessageSettingsModal(discord.ui.Modal, title='💬 Level Up Message Settings'):
    def __init__(self, current_settings: Dict[str, Any], error_logger=None):
        super().__init__()
        self.error_logger = error_logger
        
        # Pre-fill with current values
        current_message = current_settings.get('level_up_message', 'Congratulations {user}! You reached **Level {level}**! 🎉')
        self.level_message.default = current_message
        
    level_message = discord.ui.TextInput(
        label='Level Up Message',
        placeholder='Congratulations {user}! You reached **Level {level}**! 🎉',
        style=discord.TextStyle.paragraph,
        min_length=10,
        max_length=1000
    )

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message("This command can only be used in a server!", ephemeral=True)
        
        try:
            message = self.level_message.value
            
            # Validate placeholders
            if '{user}' not in message and '{username}' not in message:
                raise ValueError("Message must contain {user} or {username} placeholder")
            if '{level}' not in message:
                raise ValueError("Message must contain {level} placeholder")
            
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE guild_level_settings SET level_up_message = ? WHERE guild_id = ?",
                    (message, interaction.guild.id)
                )
                await db.commit()
            
            embed = discord.Embed(
                title=f"{emojis['check']} Level Up Message Updated",
                description=f"**New Message:**\n{message}",
                color=0x00ff00
            )
            embed.add_field(
                name="Available Placeholders",
                value="`{user}` - User mention\n`{username}` - Username\n`{level}` - New level\n`{old_level}` - Previous level",
                inline=False
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError as e:
            await interaction.response.send_message(f"❌ {e}", ephemeral=True)
        except Exception as e:
            if self.error_logger and interaction.guild:
                await self.error_logger.log_error(
                    f"Message Settings Error",
                    f"Error updating level message: {str(e)} | Guild: {interaction.guild.id}"
                )
            await interaction.response.send_message("❌ An error occurred while updating the message.", ephemeral=True)


class AnnouncementChannelView(PaginatedChannelView):
    """Specialized view for selecting announcement channels with pagination"""
    
    def __init__(self, guild: discord.Guild, guild_id: int):
        # Custom callback that handles channel selection for announcements
        async def handle_channel_selection(interaction: discord.Interaction, selected_channels: List[str]):
            try:
                if not selected_channels:
                    return await interaction.response.send_message("No channel selected!", ephemeral=True)
                
                if not interaction.guild:
                    return await interaction.response.send_message("This command can only be used in a server!", ephemeral=True)
                
                channel_id = int(selected_channels[0])
                channel = interaction.guild.get_channel(channel_id)
                
                if not channel:
                    return await interaction.response.send_message("Channel not found!", ephemeral=True)
                
                # Update database
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute("""
                        UPDATE guild_level_settings 
                        SET level_up_channel_id = ? 
                        WHERE guild_id = ?
                    """, (channel_id, guild_id))
                    await db.commit()
                
                embed = discord.Embed(
                    title=f"{emojis['success']} Announcement Channel Set",
                    description=f"Level-up announcements will be sent to {channel.mention}",
                    color=0x00ff00
                )
                
                await interaction.response.edit_message(embed=embed, view=None)
                
            except Exception as e:
                await interaction.response.send_message(f"Error setting announcement channel: {str(e)}", ephemeral=True)
        
        # Initialize with text channels only and custom callback
        super().__init__(
            guild,
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
            custom_callback=handle_channel_selection,
            timeout=300
        )
        self.guild_id = guild_id
        
        # Add disable button
        self.add_item(DisableAnnouncementsButton(guild_id))


class DisableAnnouncementsButton(discord.ui.Button):
    """Button to disable level-up announcements"""
    
    def __init__(self, guild_id: int):
        super().__init__(
            label="Disable Announcements",
            style=discord.ButtonStyle.secondary,
            emoji="🚫"
        )
        self.guild_id = guild_id
    
    async def callback(self, interaction: discord.Interaction):
        try:
            # Disable announcements in database
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("""
                    UPDATE guild_level_settings 
                    SET level_up_channel_id = NULL 
                    WHERE guild_id = ?
                """, (self.guild_id,))
                await db.commit()
            
            embed = discord.Embed(
                title=f"{emojis['success']} Announcements Disabled",
                description="Level-up announcements have been disabled.",
                color=0x00ff00
            )
            
            await interaction.response.edit_message(embed=embed, view=None)
            
        except Exception as e:
            await interaction.response.send_message(f"Error disabling announcements: {str(e)}", ephemeral=True)


class ResetConfirmView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id

    @discord.ui.button(label="Yes, Reset All", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm_reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm the reset action"""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                # Reset guild settings to default
                await db.execute("""
                    UPDATE guild_level_settings 
                    SET enabled = 0,
                        xp_per_message = 15,
                        xp_variance = 10,
                        xp_cooldown = 60,
                        level_up_message = 'Congratulations {user}! You reached **Level {level}**! 🎉',
                        level_up_channel_id = NULL,
                        dm_level_ups = 0,
                        level_formula = 'default',
                        stack_roles = 0,
                        remove_previous_roles = 1,
                        exclude_channels = '[]',
                        exclude_roles = '[]',
                        multiplier_roles = '{}',
                        no_xp_roles = '[]'
                    WHERE guild_id = ?
                """, (self.guild_id,))
                
                # Remove all level roles
                await db.execute("DELETE FROM level_roles WHERE guild_id = ?", (self.guild_id,))
                
                # Reset all user levels (optional - commented out for safety)
                # await db.execute("DELETE FROM user_levels WHERE guild_id = ?", (self.guild_id,))
                
                await db.commit()
            
            embed = discord.Embed(
                title=f"{emojis['success']} Settings Reset Complete",
                description="All leveling settings have been reset to default values.\n\n**Note:** User levels and XP have been preserved.",
                color=0x00ff00
            )
            await interaction.response.edit_message(embed=embed, view=None)
        except Exception as e:
            embed = discord.Embed(
                title=f"{emojis['error']} Reset Failed",
                description=f"An error occurred while resetting settings: {str(e)}",
                color=0xff0000
            )
            await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel the reset action"""
        embed = discord.Embed(
            title=f"{emojis['info']} Reset Cancelled",
            description="No settings were changed.",
            color=0x0099ff
        )
        await interaction.response.edit_message(embed=embed, view=None)


class LevelSetupView(discord.ui.View):
    def __init__(self, guild_id: int, error_logger=None):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.error_logger = error_logger

    async def _get_current_settings(self) -> Dict[str, Any]:
        """Fetch current guild settings from database"""
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("""
                SELECT * FROM guild_level_settings WHERE guild_id = ?
            """, (self.guild_id,)) as cursor:
                row = await cursor.fetchone()
        
        current_settings = {}
        if row:
            column_names = [description[0] for description in cursor.description]
            settings_dict = dict(zip(column_names, row))
            
            # Parse JSON fields safely
            for field in ['exclude_channels', 'exclude_roles', 'multiplier_roles', 'no_xp_roles']:
                if field in settings_dict and settings_dict[field]:
                    try:
                        settings_dict[field] = json.loads(settings_dict[field])
                    except:
                        settings_dict[field] = []
            
            current_settings = settings_dict
        
        return current_settings

    @discord.ui.button(label="Toggle System", style=discord.ButtonStyle.primary, emoji="🔄")
    async def toggle_system(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Toggle the leveling system on/off"""
        try:
            if not interaction.guild:
                return await interaction.response.send_message("This command can only be used in a server!", ephemeral=True)
            guild_id = interaction.guild.id
            
            async with aiosqlite.connect(DB_PATH) as db:
                # Get current status
                async with db.execute(
                    "SELECT enabled FROM guild_level_settings WHERE guild_id = ?",
                    (guild_id,)
                ) as cursor:
                    result = await cursor.fetchone()
                    current_enabled = result[0] if result else False
                
                # Toggle status
                new_enabled = not current_enabled
                await db.execute(
                    "UPDATE guild_level_settings SET enabled = ? WHERE guild_id = ?",
                    (new_enabled, guild_id)
                )
                await db.commit()
                
                # Fix any existing bad JSON data
                await db.execute("""
                    UPDATE guild_level_settings 
                    SET exclude_channels = '[]'
                    WHERE exclude_channels IS NULL OR exclude_channels = 'exclude_channels' OR exclude_channels = ''
                """)
                
                await db.execute("""
                    UPDATE guild_level_settings 
                    SET exclude_roles = '[]'
                    WHERE exclude_roles IS NULL OR exclude_roles = 'exclude_roles' OR exclude_roles = ''
                """)
                
                await db.execute("""
                    UPDATE guild_level_settings 
                    SET no_xp_roles = '[]'
                    WHERE no_xp_roles IS NULL OR no_xp_roles = 'no_xp_roles' OR no_xp_roles = ''
                """)
                
                await db.execute("""
                    UPDATE guild_level_settings 
                    SET multiplier_roles = '{}'
                    WHERE multiplier_roles IS NULL OR multiplier_roles = 'multiplier_roles' OR multiplier_roles = ''
                """)
                
                await db.commit()
                
        except Exception as e:
            if self.error_logger:
                await self.error_logger.log_error(
                    f"Level Setup Toggle Error in {interaction.guild.name if interaction.guild else 'Unknown Guild'}",
                    f"Error toggling leveling system: {str(e)} | Guild: {interaction.guild.id if interaction.guild else 'None'} | User: {interaction.user.id}"
                )
            await interaction.response.send_message("An error occurred while updating the setting.", ephemeral=True)
            return
        
        status = f"{emojis['check']} Enabled" if new_enabled else f"{emojis['x']} Disabled"
        embed = discord.Embed(
            title=f"{emojis['check']} System Updated",
            description=f"Leveling system is now **{status}**",
            color=0x00ff00
        )
        
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Variables", style=discord.ButtonStyle.secondary, emoji="📋")
    async def variables_guide(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show available variables for leveling messages"""
        try:
            embed = discord.Embed(
                title=f"{emojis['list']} Level-Up Message Variables",
                description="Here are the available variables you can use in your level-up messages:",
                color=0x7289da
            )
            
            # User Variables
            embed.add_field(
                name="👤 **User Variables**",
                value=(
                    "• `{user}` - Mentions the user (@Username)\n"
                    "• `{username}` - User's display name\n"
                    "• `{user.name}` - User's actual username\n"
                    "• `{user.id}` - User's ID number"
                ),
                inline=False
            )
            
            # Level Variables
            embed.add_field(
                name="📈 **Level Variables**",
                value=(
                    "• `{level}` - The new level reached\n"
                    "• `{old_level}` - Previous level\n"
                    "• `{total_xp}` - Total XP earned\n"
                    "• `{level_xp}` - XP needed for next level"
                ),
                inline=False
            )
            
            # Server Variables
            embed.add_field(
                name="🏠 **Server Variables**",
                value=(
                    "• `{server}` - Server name\n"
                    "• `{server.name}` - Server name\n"
                    "• `{server.id}` - Server ID\n"
                    "• `{member_count}` - Total server members"
                ),
                inline=False
            )
            
            # Example Messages
            embed.add_field(
                name="💡 **Example Messages**",
                value=(
                    "```\n"
                    "🎉 {user} just reached Level {level}!\n"
                    "Congratulations {username}! You're now Level {level}! 🎉\n"
                    "Amazing! {user} leveled up to {level} in {server}!\n"
                    "Level up! {user} → Level {level} ({total_xp} total XP)\n"
                    "```"
                ),
                inline=False
            )
            
            embed.set_footer(text=f"Tip: Use these variables in Message Settings", icon_url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"Error showing variables: {str(e)}", ephemeral=True)

    @discord.ui.button(label="XP Settings", style=discord.ButtonStyle.secondary, emoji="⚡", row=1)
    async def xp_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Configure XP settings"""
        try:
            current_settings = await self._get_current_settings()
            modal = XPSettingsModal(current_settings, self.error_logger)
            await interaction.response.send_modal(modal)
        except Exception as e:
            await interaction.response.send_message(f"Error opening XP settings: {str(e)}", ephemeral=True)

    @discord.ui.button(label="Channel Settings", style=discord.ButtonStyle.secondary, emoji="📢", row=1)
    async def channel_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Configure channel settings"""
        try:
            current_settings = await self._get_current_settings()
            view = ChannelSettingsView(current_settings, self.error_logger)
            embed = discord.Embed(
                title=f"{emojis['settings']} Channel Settings",
                description="Configure channel-specific leveling settings",
                color=0x0099ff
            )
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error opening channel settings: {str(e)}", ephemeral=True)

    @discord.ui.button(label="Role Settings", style=discord.ButtonStyle.secondary, emoji="🎭", row=1)
    async def role_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Configure role settings"""
        try:
            view = RoleSettingsView(self.error_logger)
            embed = discord.Embed(
                title=f"{emojis['role']} Role Settings",
                description="Configure level roles and XP multipliers",
                color=0x9b59b6
            )
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error opening role settings: {str(e)}", ephemeral=True)

    @discord.ui.button(label="Multiplier Settings", style=discord.ButtonStyle.secondary, emoji="📈", row=1)
    async def multiplier_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Configure XP multiplier settings"""
        try:
            view = MultiplierSettingsView(self.error_logger)
            embed = discord.Embed(
                title=f"{emojis['boost']} Multiplier Settings",
                description="Configure XP multipliers for roles and channels",
                color=0xff6b6b
            )
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error opening multiplier settings: {str(e)}", ephemeral=True)

   
    @discord.ui.button(label="Message Settings", style=discord.ButtonStyle.secondary, emoji="💬", row=2)
    async def message_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Configure level-up message settings"""
        try:
            current_settings = await self._get_current_settings()
            modal = MessageSettingsModal(current_settings, self.error_logger)
            await interaction.response.send_modal(modal)
        except Exception as e:
            await interaction.response.send_message(f"Error opening message settings: {str(e)}", ephemeral=True)

    @discord.ui.button(label="Announce Channel", style=discord.ButtonStyle.secondary, emoji="📣", row=2)
    async def announce_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Set level-up announcement channel"""
        if not interaction.guild:
            return await interaction.response.send_message("This command can only be used in a server!", ephemeral=True)
        
        try:
            # Use the paginated channel view that handles large channel lists
            view = AnnouncementChannelView(interaction.guild, self.guild_id)
            
            embed = discord.Embed(
                title=f"{emojis['channel']} Select Announcement Channel",
                description=(
                    "Select a channel for level-up announcements from the dropdown below.\n\n"
                    "• Use the **pagination buttons** if you have many channels\n"
                    "• Click **Disable Announcements** to turn them off\n"
                    "• Only text and news channels are shown"
                ),
                color=0x00ff00
            )
            
            # Show current announcement channel if set
            try:
                current_settings = await self._get_current_settings()
                if current_settings.get('level_up_channel_id'):
                    current_channel = interaction.guild.get_channel(current_settings['level_up_channel_id'])
                    if current_channel:
                        embed.add_field(
                            name="Current Channel",
                            value=f"{current_channel.mention}",
                            inline=False
                        )
            except:
                pass  # If we can't get current settings, that's okay
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"Error opening channel selector: {str(e)}", ephemeral=True)

    @discord.ui.button(label="Reset Settings", style=discord.ButtonStyle.danger, emoji="🔄", row=2)
    async def reset_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Reset all leveling settings"""
        embed = discord.Embed(
            title=f"{emojis['warning']} Reset All Settings",
            description="Are you sure you want to reset ALL leveling settings to default? This cannot be undone!",
            color=0xff0000
        )
        
        confirm_view = ResetConfirmView(self.guild_id)
        await interaction.response.send_message(embed=embed, view=confirm_view, ephemeral=True)


class LevelRoleSetupView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id

    @discord.ui.button(label="Add Role", style=discord.ButtonStyle.green, emoji="➕")
    async def add_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Add a level role"""
        await interaction.response.send_message(
            "Level role addition would open here (modal for level and role selection)",
            ephemeral=True
        )

    @discord.ui.button(label="Remove Role", style=discord.ButtonStyle.red, emoji="➖")
    async def remove_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Remove a level role"""
        await interaction.response.send_message(
            "Level role removal would open here",
            ephemeral=True
        )

    @discord.ui.button(label="View All", style=discord.ButtonStyle.primary, emoji="📋")
    async def view_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        """View all level roles"""
        if not interaction.guild:
            return await interaction.response.send_message("This command can only be used in a server!", ephemeral=True)
        
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("""
                SELECT level, role_id FROM level_roles 
                WHERE guild_id = ? 
                ORDER BY level ASC
            """, (self.guild_id,)) as cursor:
                level_roles = list(await cursor.fetchall())
        
        if not level_roles:
            embed = discord.Embed(
                title=f"{emojis['warning']} No Level Roles",
                description="No level roles have been configured yet.",
                color=0xff9900
            )
        else:
            embed = discord.Embed(
                title=f"{emojis['crown']} All Level Roles",
                description=f"**{len(level_roles)}** level roles configured",
                color=0x006fb9
            )
            
            role_text = ""
            for level, role_id in level_roles:
                role = interaction.guild.get_role(role_id)
                role_name = role.mention if role else f"{emojis['x']} Deleted Role"
                role_text += f"Level **{level}**: {role_name}\n"
            
            embed.add_field(name="Configured Roles", value=role_text, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ConfirmResetView(discord.ui.View):
    def __init__(self, user_id: int, guild_id: int):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.guild_id = guild_id

    @discord.ui.button(label="Confirm Reset", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm_reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm the user reset"""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM user_levels WHERE user_id = ? AND guild_id = ?",
                (self.user_id, self.guild_id)
            )
            await db.commit()
        
        user = interaction.guild.get_member(self.user_id) if interaction.guild else None
        username = user.display_name if user else "Unknown User"
        
        embed = discord.Embed(
            title=f"{emojis['check']} User Reset Complete",
            description=f"Successfully reset **{username}**'s level and XP data.",
            color=0x00ff00
        )
        
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel the reset operation"""
        embed = discord.Embed(
            title=f"{emojis['check']} Reset Cancelled",
            description="No data was deleted.",
            color=0x00ff00
        )
        
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()


class ConfirmServerResetView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=60)
        self.guild_id = guild_id

    @discord.ui.button(label="CONFIRM FULL RESET", style=discord.ButtonStyle.danger, emoji="💥")
    async def confirm_server_reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm the complete server reset"""
        async with aiosqlite.connect(DB_PATH) as db:
            # Delete all user data
            await db.execute(
                "DELETE FROM user_levels WHERE guild_id = ?",
                (self.guild_id,)
            )
            # Delete all level roles
            await db.execute(
                "DELETE FROM level_roles WHERE guild_id = ?",
                (self.guild_id,)
            )
            # Delete guild settings
            await db.execute(
                "DELETE FROM guild_level_settings WHERE guild_id = ?",
                (self.guild_id,)
            )
            await db.commit()
        
        embed = discord.Embed(
            title=f"{emojis['check']} Server Reset Complete",
            description="Successfully deleted all leveling data for this server.\n\nAll user levels, XP, role configurations, and settings have been removed.",
            color=0x00ff00
        )
        
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel the reset operation"""
        embed = discord.Embed(
            title=f"{emojis['check']} Reset Cancelled",
            description="No data was deleted.",
            color=0x00ff00
        )
        
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()


async def setup(bot):
    await bot.add_cog(LevelingSystem(bot))