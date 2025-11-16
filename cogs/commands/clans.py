"""
Comprehensive Clan System with customizable emojis
Supports role-based management, leaderboards, and flexible requirements
"""

import discord
from discord.ext import commands, tasks
import aiosqlite
import os
from typing import Optional, Dict, List
from datetime import datetime
from utils.Tools import *
from utils.error_helpers import StandardErrorHandler

DB_PATH = "db/clans.db"

# Default emojis from design document
DEFAULT_EMOJIS = {
    "icon": "<a:hackerman:1431909176472240140>",
    "leader": "<a:crown:1437503143591153756>",
    "trophy": "<:trophy:1428163126360146034>",
    "boost": "<:boost:1427471537149186140>",
    "members": "<:ar:1427471532841631855>",
    "stats": "<:stats:1437456326157668362>",
    "role": "<:paint:1437499837036625960>",
    "locked": "<a:lock:1437496504955699402>",
    "unlocked": "<a:lock:1437496504955699402>",
    "settings": "<a:gear:1430203750324240516>",
    "success": "<a:yes:1431909187247673464>",
    "error": "<a:wrong:1436956421110632489>",
}


class ClanSystem(commands.Cog):
    """Comprehensive clan management system"""
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot
        self.emoji_cache: Dict[int, Dict[str, str]] = {}
        
    async def cog_load(self):
        """Called when the cog is loaded"""
        await self.initialize_db()
        if not self.leaderboard_updater.is_running():
            self.leaderboard_updater.start()
        if not self.reset_daily_stats.is_running():
            self.reset_daily_stats.start()
        if not self.reset_weekly_stats.is_running():
            self.reset_weekly_stats.start()
        
    async def cog_unload(self):
        """Called when the cog is unloaded"""
        self.leaderboard_updater.cancel()
        self.reset_daily_stats.cancel()
        self.reset_weekly_stats.cancel()
    
    async def initialize_db(self):
        """Ensure database and tables exist"""
        # Ensure directory exists
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        
        # Create tables if they don't exist
        async with self.get_db() as db:
            # Clans table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS clans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    leader_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    member_count INTEGER DEFAULT 0,
                    boost_count INTEGER DEFAULT 0,
                    UNIQUE(guild_id, name COLLATE NOCASE)
                )
            """)
            
            # Clan members table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS clan_members (
                    clan_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (clan_id, user_id),
                    FOREIGN KEY (clan_id) REFERENCES clans(id) ON DELETE CASCADE
                )
            """)
            
            # Clan roles table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS clan_roles (
                    clan_id INTEGER PRIMARY KEY,
                    role_id INTEGER NOT NULL,
                    booster_count INTEGER DEFAULT 0,
                    FOREIGN KEY (clan_id) REFERENCES clans(id) ON DELETE CASCADE
                )
            """)
            
            # Clan config table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS clan_config (
                    guild_id INTEGER PRIMARY KEY,
                    required_role_id INTEGER,
                    requirement_type TEXT DEFAULT 'boost',
                    requirement_value INTEGER DEFAULT 2
                )
            """)
            
            # Clan leaderboards table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS clan_leaderboards (
                    guild_id INTEGER PRIMARY KEY,
                    channel_id INTEGER NOT NULL,
                    message_id INTEGER,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Clan activity tracking table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS clan_activity (
                    clan_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    messages INTEGER DEFAULT 0,
                    voice_minutes INTEGER DEFAULT 0,
                    PRIMARY KEY (clan_id, date),
                    FOREIGN KEY (clan_id) REFERENCES clans(id) ON DELETE CASCADE
                )
            """)
            
            # Clan activity cache (for current period)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS clan_activity_cache (
                    clan_id INTEGER PRIMARY KEY,
                    daily_messages INTEGER DEFAULT 0,
                    daily_voice_minutes INTEGER DEFAULT 0,
                    weekly_messages INTEGER DEFAULT 0,
                    weekly_voice_minutes INTEGER DEFAULT 0,
                    monthly_messages INTEGER DEFAULT 0,
                    monthly_voice_minutes INTEGER DEFAULT 0,
                    last_reset TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (clan_id) REFERENCES clans(id) ON DELETE CASCADE
                )
            """)
            
            # Clan emojis table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS clan_emojis (
                    guild_id INTEGER NOT NULL,
                    emoji_key TEXT NOT NULL,
                    emoji_value TEXT NOT NULL,
                    PRIMARY KEY (guild_id, emoji_key)
                )
            """)
            
            # Create indexes
            await db.execute("CREATE INDEX IF NOT EXISTS idx_clans_guild ON clans(guild_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_clan_members_user ON clan_members(user_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_clan_members_clan ON clan_members(clan_id)")
            
            await db.commit()
            print("✅ Clan system database initialized")
    
    def get_db(self):
        """Get database connection"""
        return aiosqlite.connect(DB_PATH)
    
    async def get_emoji(self, guild_id: int, key: str) -> str:
        """Get emoji for a guild (uses cache)"""
        # Check cache first
        if guild_id in self.emoji_cache and key in self.emoji_cache[guild_id]:
            return self.emoji_cache[guild_id][key]
        
        # Load from database
        async with self.get_db() as db:
            cursor = await db.execute(
                "SELECT emoji_value FROM clan_emojis WHERE guild_id = ? AND emoji_key = ?",
                (guild_id, key)
            )
            result = await cursor.fetchone()
            
            if result:
                emoji = result[0]
            else:
                # Use default emoji
                emoji = DEFAULT_EMOJIS.get(key, "❓")
            
            # Cache it
            if guild_id not in self.emoji_cache:
                self.emoji_cache[guild_id] = {}
            self.emoji_cache[guild_id][key] = emoji
            
            return emoji
    
    async def get_all_emojis(self, guild_id: int) -> Dict[str, str]:
        """Get all emojis for a guild"""
        emojis = {}
        for key in DEFAULT_EMOJIS.keys():
            emojis[key] = await self.get_emoji(guild_id, key)
        return emojis
    
    async def set_emoji(self, guild_id: int, key: str, value: str):
        """Set custom emoji for a guild"""
        async with self.get_db() as db:
            await db.execute(
                "INSERT OR REPLACE INTO clan_emojis (guild_id, emoji_key, emoji_value) VALUES (?, ?, ?)",
                (guild_id, key, value)
            )
            await db.commit()
        
        # Update cache
        if guild_id not in self.emoji_cache:
            self.emoji_cache[guild_id] = {}
        self.emoji_cache[guild_id][key] = value
    
    async def reset_emojis(self, guild_id: int):
        """Reset all emojis to defaults for a guild"""
        async with self.get_db() as db:
            await db.execute("DELETE FROM clan_emojis WHERE guild_id = ?", (guild_id,))
            await db.commit()
        
        # Clear cache
        if guild_id in self.emoji_cache:
            del self.emoji_cache[guild_id]
    
    async def has_clan_permissions(self, ctx: commands.Context) -> bool:
        """Check if user has permission to manage clans (mod or required role)"""
        assert ctx.guild is not None
        assert isinstance(ctx.author, discord.Member)
        
        # Check if user is admin/mod
        if ctx.author.guild_permissions.administrator or ctx.author.guild_permissions.manage_guild:
            return True
        
        # Check for required role
        async with self.get_db() as db:
            cursor = await db.execute(
                "SELECT required_role_id FROM clan_config WHERE guild_id = ?",
                (ctx.guild.id,)
            )
            result = await cursor.fetchone()
            
            if result and result[0]:
                required_role = ctx.guild.get_role(result[0])
                if required_role and required_role in ctx.author.roles:
                    return True
        
        return False
    
    async def get_user_clan(self, guild_id: int, user_id: int) -> Optional[int]:
        """Get the clan ID for a user in a guild"""
        async with self.get_db() as db:
            cursor = await db.execute(
                """
                SELECT clan_id FROM clan_members 
                WHERE user_id = ? AND clan_id IN (
                    SELECT id FROM clans WHERE guild_id = ?
                )
                """,
                (user_id, guild_id)
            )
            result = await cursor.fetchone()
            return result[0] if result else None
    
    async def get_clan_info(self, clan_id: int) -> Optional[dict]:
        """Get full clan information"""
        async with self.get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM clans WHERE id = ?",
                (clan_id,)
            )
            result = await cursor.fetchone()
            
            if not result:
                return None
            
            return {
                "id": result[0],
                "name": result[1],
                "guild_id": result[2],
                "leader_id": result[3],
                "created_at": result[4],
                "member_count": result[5],
                "boost_count": result[6]
            }
    
    async def get_clan_members(self, clan_id: int) -> List[int]:
        """Get list of member user IDs for a clan"""
        async with self.get_db() as db:
            cursor = await db.execute(
                "SELECT user_id FROM clan_members WHERE clan_id = ?",
                (clan_id,)
            )
            results = await cursor.fetchall()
            return [r[0] for r in results]
    
    async def update_clan_stats(self, clan_id: int, guild: discord.Guild):
        """Update clan member count and boost count"""
        members = await self.get_clan_members(clan_id)
        
        # Count boosters
        boost_count = 0
        for member_id in members:
            member = guild.get_member(member_id)
            if member and member.premium_since:
                boost_count += 1
        
        async with self.get_db() as db:
            await db.execute(
                "UPDATE clans SET member_count = ?, boost_count = ? WHERE id = ?",
                (len(members), boost_count, clan_id)
            )
            await db.commit()
    
    # ==================== EMOJI CUSTOMIZATION COMMANDS ====================
    
    @commands.group(name="clan", invoke_without_command=True)
    async def clan(self, ctx: commands.Context, *, clan_name: Optional[str] = None):
        """View clan information. Use `$clan me` or `$clan <name>`"""
        assert ctx.guild is not None
        assert isinstance(ctx.author, discord.Member)
        
        if clan_name and clan_name.lower() == "me":
            # Show user's clan
            clan_id = await self.get_user_clan(ctx.guild.id, ctx.author.id)
            if not clan_id:
                emojis = await self.get_all_emojis(ctx.guild.id)
                embed = discord.Embed(
                    description=f"{emojis['error']} You are not in a clan!",
                    color=discord.Color.red()
                )
                return await ctx.send(embed=embed)
        elif clan_name:
            # Show specific clan by name
            async with self.get_db() as db:
                cursor = await db.execute(
                    "SELECT id FROM clans WHERE guild_id = ? AND name = ?",
                    (ctx.guild.id, clan_name)
                )
                result = await cursor.fetchone()
                if not result:
                    emojis = await self.get_all_emojis(ctx.guild.id)
                    embed = discord.Embed(
                        description=f"{emojis['error']} Clan `{clan_name}` not found!",
                        color=discord.Color.red()
                    )
                    return await ctx.send(embed=embed)
                clan_id = result[0]
        else:
            # Show help
            await ctx.send_help(ctx.command)
            return
        
        # Get clan info
        clan = await self.get_clan_info(clan_id)
        if not clan:
            return await ctx.send("Clan not found!")
        
        # Get emojis
        emojis = await self.get_all_emojis(ctx.guild.id)
        
        # Get leader
        leader = ctx.guild.get_member(clan["leader_id"])
        leader_mention = leader.mention if leader else f"<@{clan['leader_id']}>"
        
        # Get members
        members = await self.get_clan_members(clan_id)
        member_list = []
        for member_id in members[:10]:  # Show first 10
            member = ctx.guild.get_member(member_id)
            if member:
                member_list.append(member.mention)
        
        if len(members) > 10:
            member_list.append(f"*...and {len(members) - 10} more*")
        
        # Check if clan has custom role
        async with self.get_db() as db:
            cursor = await db.execute(
                "SELECT role_id FROM clan_roles WHERE clan_id = ?",
                (clan_id,)
            )
            role_result = await cursor.fetchone()
            has_role = bool(role_result)
            role_status = f"{emojis['unlocked']} Custom Role" if has_role else f"{emojis['locked']} No Custom Role"
        
        # Create embed
        embed = discord.Embed(
            title=f"{emojis['icon']} Clan: {clan['name']}",
            color=discord.Color.blue(),
            timestamp=datetime.fromisoformat(clan["created_at"])
        )
        
        embed.add_field(
            name=f"{emojis['leader']} Leader",
            value=leader_mention,
            inline=True
        )
        
        embed.add_field(
            name=f"{emojis['members']} Members",
            value=f"{clan['member_count']}/7",
            inline=True
        )
        
        embed.add_field(
            name=f"{emojis['boost']} Boosters",
            value=str(clan["boost_count"]),
            inline=True
        )
        
        embed.add_field(
            name=f"{emojis['stats']} Members List",
            value="\n".join(member_list) if member_list else "No members",
            inline=False
        )
        
        embed.add_field(
            name=f"{emojis['role']} Role Status",
            value=role_status,
            inline=False
        )
        
        embed.set_footer(text=f"Created")
        
        await ctx.send(embed=embed)
    
    @clan.group(name="emoji", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def clan_emoji(self, ctx: commands.Context):
        """Manage clan emojis (Admin only)"""
        assert ctx.guild is not None
        assert isinstance(ctx.author, discord.Member)
        
        await ctx.send_help(ctx.command)
    
    @clan_emoji.command(name="set")
    @commands.has_permissions(administrator=True)
    async def emoji_set(self, ctx: commands.Context, key: str, emoji: str):
        """Set a custom emoji for the clan system
        
        Available keys: icon, leader, trophy, boost, members, stats, role, locked, unlocked, settings, success, error
        
        Example: `$clan emoji set icon <a:clan:123456789>`
        """
        assert ctx.guild is not None
        assert isinstance(ctx.author, discord.Member)
        
        emojis = await self.get_all_emojis(ctx.guild.id)
        
        if key not in DEFAULT_EMOJIS:
            embed = discord.Embed(
                description=f"{emojis['error']} Invalid emoji key! Available keys:\n`{'`, `'.join(DEFAULT_EMOJIS.keys())}`",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Set the emoji
        await self.set_emoji(ctx.guild.id, key, emoji)
        
        embed = discord.Embed(
            description=f"{emojis['success']} Set `{key}` emoji to {emoji}",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    
    @clan_emoji.command(name="list")
    async def emoji_list(self, ctx: commands.Context):
        """List all current clan emojis"""
        assert ctx.guild is not None
        
        emojis = await self.get_all_emojis(ctx.guild.id)
        
        embed = discord.Embed(
            title=f"{emojis['settings']} Clan System Emojis",
            description="Current emojis being used in this server:",
            color=discord.Color.blue()
        )
        
        for key, value in emojis.items():
            embed.add_field(
                name=f"`{key}`",
                value=value,
                inline=True
            )
        
        embed.set_footer(text="Use $clan emoji set <key> <emoji> to customize (Admin only)")
        await ctx.send(embed=embed)
    
    @clan_emoji.command(name="reset")
    @commands.has_permissions(administrator=True)
    async def emoji_reset(self, ctx: commands.Context):
        """Reset all emojis to defaults (Admin only)"""
        assert ctx.guild is not None
        assert isinstance(ctx.author, discord.Member)
        
        await self.reset_emojis(ctx.guild.id)
        emojis = await self.get_all_emojis(ctx.guild.id)
        
        embed = discord.Embed(
            description=f"{emojis['success']} Reset all clan emojis to defaults!",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    
    # ==================== CLAN CONFIGURATION COMMANDS ====================
    
    @commands.command(name="reqrole")
    @commands.has_permissions(manage_guild=True)
    async def reqrole(self, ctx: commands.Context, role: Optional[discord.Role] = None):
        """Set the required role for clan management (Mod only)
        
        Example: `$reqrole @ClanManager`
        Use without a role to remove the requirement
        """
        assert ctx.guild is not None
        
        emojis = await self.get_all_emojis(ctx.guild.id)
        
        async with self.get_db() as db:
            if role:
                # Set the required role
                await db.execute(
                    """
                    INSERT INTO clan_config (guild_id, required_role_id) 
                    VALUES (?, ?)
                    ON CONFLICT(guild_id) DO UPDATE SET required_role_id = ?
                    """,
                    (ctx.guild.id, role.id, role.id)
                )
                await db.commit()
                
                embed = discord.Embed(
                    description=f"{emojis['success']} Set clan management role to {role.mention}",
                    color=discord.Color.green()
                )
            else:
                # Remove the required role
                await db.execute(
                    """
                    INSERT INTO clan_config (guild_id, required_role_id) 
                    VALUES (?, NULL)
                    ON CONFLICT(guild_id) DO UPDATE SET required_role_id = NULL
                    """,
                    (ctx.guild.id,)
                )
                await db.commit()
                
                embed = discord.Embed(
                    description=f"{emojis['success']} Removed clan management role requirement",
                    color=discord.Color.green()
                )
        
        await ctx.send(embed=embed)
    
    # ==================== CLAN CREATION COMMANDS ====================
    
    @clan.command(name="create")
    async def clan_create(self, ctx: commands.Context, name: str, *members: discord.Member):
        """Create a new clan (Mod/Required Role only)
        
        Example: `$clan create "Shadow Warriors" @user1 @user2 @user3`
        Maximum 7 members including yourself
        """
        assert ctx.guild is not None
        assert isinstance(ctx.author, discord.Member)
        
        emojis = await self.get_all_emojis(ctx.guild.id)
        
        # Check permissions
        if not await self.has_clan_permissions(ctx):
            embed = discord.Embed(
                description=f"{emojis['error']} You don't have permission to create clans!",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Validate clan name
        if len(name) < 2 or len(name) > 32:
            embed = discord.Embed(
                description=f"{emojis['error']} Clan name must be between 2 and 32 characters!",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Check if clan name already exists
        async with self.get_db() as db:
            cursor = await db.execute(
                "SELECT id FROM clans WHERE guild_id = ? AND name = ?",
                (ctx.guild.id, name)
            )
            if await cursor.fetchone():
                embed = discord.Embed(
                    description=f"{emojis['error']} A clan with the name `{name}` already exists!",
                    color=discord.Color.red()
                )
                return await ctx.send(embed=embed)
        
        # Validate member count (including creator)
        all_members = [ctx.author] + list(members)
        if len(all_members) > 7:
            embed = discord.Embed(
                description=f"{emojis['error']} Maximum 7 members per clan! You provided {len(all_members)}.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Check if any member is already in a clan
        for member in all_members:
            existing_clan = await self.get_user_clan(ctx.guild.id, member.id)
            if existing_clan:
                clan_info = await self.get_clan_info(existing_clan)
                if clan_info:  # Add None check
                    embed = discord.Embed(
                        description=f"{emojis['error']} {member.mention} is already in clan `{clan_info['name']}`!",
                        color=discord.Color.red()
                    )
                    return await ctx.send(embed=embed)
        
        # Create the clan
        async with self.get_db() as db:
            cursor = await db.execute(
                """
                INSERT INTO clans (name, guild_id, leader_id, member_count, boost_count)
                VALUES (?, ?, ?, ?, 0)
                """,
                (name, ctx.guild.id, ctx.author.id, len(all_members))
            )
            clan_id = cursor.lastrowid
            
            # Add all members
            for member in all_members:
                await db.execute(
                    "INSERT OR IGNORE INTO clan_members (clan_id, user_id) VALUES (?, ?)",
                    (clan_id, member.id)
                )
            
            await db.commit()
        
        # Update boost count
        if clan_id:
            await self.update_clan_stats(clan_id, ctx.guild)
        
        # Success message
        member_mentions = ", ".join([m.mention for m in all_members])
        embed = discord.Embed(
            title=f"{emojis['success']} Clan Created!",
            description=f"{emojis['icon']} **{name}**\n{emojis['leader']} Leader: {ctx.author.mention}\n{emojis['members']} Members: {member_mentions}",
            color=discord.Color.green()
        )
        
        await ctx.send(embed=embed)
    
    # ==================== CLAN LEADERSHIP COMMANDS ====================
    
    @clan.command(name="leader")
    async def clan_leader(self, ctx: commands.Context, clan_name: str, new_leader: discord.Member):
        """Transfer clan leadership (Current Leader/Mod only)
        
        Example: `$clan leader "Shadow Warriors" @newleader`
        """
        assert ctx.guild is not None
        assert isinstance(ctx.author, discord.Member)
        
        emojis = await self.get_all_emojis(ctx.guild.id)
        
        # Get clan
        async with self.get_db() as db:
            cursor = await db.execute(
                "SELECT id, leader_id FROM clans WHERE guild_id = ? AND name = ?",
                (ctx.guild.id, clan_name)
            )
            result = await cursor.fetchone()
            
            if not result:
                embed = discord.Embed(
                    description=f"{emojis['error']} Clan `{clan_name}` not found!",
                    color=discord.Color.red()
                )
                return await ctx.send(embed=embed)
            
            clan_id, current_leader_id = result
        
        # Check permissions (must be current leader or have clan management permissions)
        is_leader = ctx.author.id == current_leader_id
        has_perms = await self.has_clan_permissions(ctx)
        
        if not (is_leader or has_perms):
            embed = discord.Embed(
                description=f"{emojis['error']} You must be the clan leader or have clan management permissions!",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Check if new leader is in the clan
        members = await self.get_clan_members(clan_id)
        if new_leader.id not in members:
            embed = discord.Embed(
                description=f"{emojis['error']} {new_leader.mention} is not in this clan!",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Transfer leadership
        async with self.get_db() as db:
            await db.execute(
                "UPDATE clans SET leader_id = ? WHERE id = ?",
                (new_leader.id, clan_id)
            )
            await db.commit()
        
        embed = discord.Embed(
            description=f"{emojis['success']} {emojis['leader']} Transferred leadership of `{clan_name}` to {new_leader.mention}!",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    
    # ==================== CLAN LEADERBOARD ====================
    
    @commands.command(name="clanlb")
    @commands.has_permissions(manage_guild=True)
    async def clanlb(self, ctx: commands.Context, sort_mode: str = "balanced", channel: Optional[discord.TextChannel] = None):
        """Setup auto-updating clan leaderboard (Mod only)
        
        Sort modes:
        • `balanced` - Overall score (members + activity + voice)
        • `members` - By member count
        • `messages` - By message activity
        • `voice` - By voice time
        
        Examples:
        `$clanlb balanced #clan-leaderboard`
        `$clanlb messages`
        `$clanlb voice #leaderboard`
        
        Updates every hour automatically
        """
        assert ctx.guild is not None
        assert isinstance(ctx.author, discord.Member)
        
        emojis = await self.get_all_emojis(ctx.guild.id)
        
        # Validate sort mode
        valid_modes = ["balanced", "members", "messages", "voice"]
        sort_lower = sort_mode.lower()
        
        if sort_lower not in valid_modes:
            # Maybe they passed a channel as first arg
            if sort_mode.startswith("<#"):
                try:
                    channel = await commands.TextChannelConverter().convert(ctx, sort_mode)
                    sort_lower = "balanced"
                except:
                    embed = discord.Embed(
                        description=f"{emojis['error']} Invalid channel or sort mode!",
                        color=discord.Color.red()
                    )
                    return await ctx.send(embed=embed)
            else:
                embed = discord.Embed(
                    description=f"{emojis['error']} Invalid sort mode! Use: `balanced`, `members`, `messages`, or `voice`",
                    color=discord.Color.red()
                )
                return await ctx.send(embed=embed)
        
        if not channel:
            if not isinstance(ctx.channel, discord.TextChannel):
                return await ctx.send(f"{emojis['error']} This command must be used in a server text channel!")
            channel = ctx.channel
        
        # Create initial leaderboard message
        embed = await self.generate_leaderboard_embed(ctx.guild, sort_lower)
        message = await channel.send(embed=embed)
        
        # Save to database
        async with self.get_db() as db:
            await db.execute(
                """
                INSERT INTO clan_leaderboards (guild_id, channel_id, message_id, last_updated)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(guild_id) DO UPDATE SET
                    channel_id = ?,
                    message_id = ?,
                    last_updated = CURRENT_TIMESTAMP
                """,
                (ctx.guild.id, channel.id, message.id, channel.id, message.id)
            )
            await db.commit()
        
        mode_desc = {
            "balanced": "Overall ranking (balanced score)",
            "members": "Member count",
            "messages": "Message activity",
            "voice": "Voice time"
        }
        
        embed = discord.Embed(
            description=f"{emojis['success']} Clan leaderboard setup in {channel.mention}!\n"
                       f"**Sort Mode:** {mode_desc[sort_lower]}\n"
                       f"Updates every hour automatically.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    
    async def generate_leaderboard_embed(self, guild: discord.Guild, sort_by: str = "members") -> discord.Embed:
        """Generate the leaderboard embed with multiple sorting options
        
        Args:
            guild: Discord guild
            sort_by: Sorting method - "members", "activity", "voice", "messages", or "balanced"
        """
        emojis = await self.get_all_emojis(guild.id)
        
        # Get all clans with their activity stats
        async with self.get_db() as db:
            if sort_by == "members":
                # Sort by member count, then boost count
                cursor = await db.execute(
                    """
                    SELECT c.name, c.leader_id, c.member_count, c.boost_count,
                           COALESCE(ca.weekly_messages, 0) as weekly_messages,
                           COALESCE(ca.weekly_voice_minutes, 0) as weekly_voice
                    FROM clans c
                    LEFT JOIN clan_activity_cache ca ON c.id = ca.clan_id
                    WHERE c.guild_id = ?
                    ORDER BY c.member_count DESC, c.boost_count DESC
                    LIMIT 10
                    """,
                    (guild.id,)
                )
            elif sort_by == "messages":
                # Sort by message activity
                cursor = await db.execute(
                    """
                    SELECT c.name, c.leader_id, c.member_count, c.boost_count,
                           COALESCE(ca.weekly_messages, 0) as weekly_messages,
                           COALESCE(ca.weekly_voice_minutes, 0) as weekly_voice
                    FROM clans c
                    LEFT JOIN clan_activity_cache ca ON c.id = ca.clan_id
                    WHERE c.guild_id = ?
                    ORDER BY weekly_messages DESC, c.member_count DESC
                    LIMIT 10
                    """,
                    (guild.id,)
                )
            elif sort_by == "voice":
                # Sort by voice activity
                cursor = await db.execute(
                    """
                    SELECT c.name, c.leader_id, c.member_count, c.boost_count,
                           COALESCE(ca.weekly_messages, 0) as weekly_messages,
                           COALESCE(ca.weekly_voice_minutes, 0) as weekly_voice
                    FROM clans c
                    LEFT JOIN clan_activity_cache ca ON c.id = ca.clan_id
                    WHERE c.guild_id = ?
                    ORDER BY weekly_voice DESC, c.member_count DESC
                    LIMIT 10
                    """,
                    (guild.id,)
                )
            else:  # "balanced" - combined score
                # Score: (members * 10) + (messages / 100) + (voice_hours * 5)
                cursor = await db.execute(
                    """
                    SELECT c.name, c.leader_id, c.member_count, c.boost_count,
                           COALESCE(ca.weekly_messages, 0) as weekly_messages,
                           COALESCE(ca.weekly_voice_minutes, 0) as weekly_voice
                    FROM clans c
                    LEFT JOIN clan_activity_cache ca ON c.id = ca.clan_id
                    WHERE c.guild_id = ?
                    ORDER BY (c.member_count * 10 + weekly_messages / 100.0 + weekly_voice / 12.0) DESC
                    LIMIT 10
                    """,
                    (guild.id,)
                )
            
            clans = await cursor.fetchall()
        
        # Title based on sort mode
        title_map = {
            "members": f"{emojis['trophy']} Clan Leaderboard - By Members",
            "messages": f"{emojis['trophy']} Clan Leaderboard - By Activity",
            "voice": f"{emojis['trophy']} Clan Leaderboard - By Voice Time",
            "balanced": f"{emojis['trophy']} Clan Leaderboard - Overall"
        }
        
        embed = discord.Embed(
            title=title_map.get(sort_by, f"{emojis['trophy']} Clan Leaderboard"),
            description=f"Top clans in **{guild.name}**",
            color=discord.Color.gold(),
            timestamp=datetime.utcnow()
        )
        
        if not clans:
            embed.description = (embed.description or "") + "\n\n*No clans yet!*"
        else:
            medals = ["🥇", "🥈", "🥉"]
            leaderboard_text = []
            
            for i, (name, leader_id, member_count, boost_count, weekly_messages, weekly_voice) in enumerate(clans, 1):
                medal = medals[i-1] if i <= 3 else f"`#{i}`"
                leader = guild.get_member(leader_id)
                leader_name = leader.name if leader else "Unknown"
                
                # Format voice time
                voice_hours = weekly_voice / 60
                if voice_hours >= 1:
                    voice_display = f"{voice_hours:.1f}h"
                else:
                    voice_display = f"{weekly_voice}m"
                
                # Format messages
                if weekly_messages >= 1000:
                    msg_display = f"{weekly_messages/1000:.1f}k"
                else:
                    msg_display = str(weekly_messages)
                
                leaderboard_text.append(
                    f"{medal} **{name}**\n"
                    f"   {emojis['leader']} {leader_name} | "
                    f"{emojis['members']} {member_count} | "
                    f"{emojis['boost']} {boost_count}\n"
                    f"   💬 {msg_display} msgs | 🎤 {voice_display} voice"
                )
            
            embed.description = (embed.description or "") + "\n\n" + "\n\n".join(leaderboard_text)
        
        embed.set_footer(text="📊 Weekly stats • Updates every hour")
        return embed
    
    @tasks.loop(hours=1)
    async def leaderboard_updater(self):
        """Update all leaderboards every hour"""
        try:
            async with self.get_db() as db:
                cursor = await db.execute(
                    "SELECT guild_id, channel_id, message_id FROM clan_leaderboards"
                )
                leaderboards = await cursor.fetchall()
            
            for guild_id, channel_id, message_id in leaderboards:
                try:
                    guild = self.bot.get_guild(guild_id)
                    if not guild:
                        continue
                    
                    channel = guild.get_channel(channel_id)
                    if not channel:
                        continue
                    
                    try:
                        message = await channel.fetch_message(message_id)
                        embed = await self.generate_leaderboard_embed(guild)
                        await message.edit(embed=embed)
                        
                        # Update timestamp
                        async with self.get_db() as db:
                            await db.execute(
                                "UPDATE clan_leaderboards SET last_updated = CURRENT_TIMESTAMP WHERE guild_id = ? AND channel_id = ?",
                                (guild_id, channel_id)
                            )
                            await db.commit()
                    except discord.NotFound:
                        # Message was deleted, remove from database
                        async with self.get_db() as db:
                            await db.execute(
                                "DELETE FROM clan_leaderboards WHERE guild_id = ? AND channel_id = ?",
                                (guild_id, channel_id)
                            )
                            await db.commit()
                except Exception as e:
                    print(f"Error updating leaderboard for guild {guild_id}: {e}")
        except Exception as e:
            print(f"Error in leaderboard updater: {e}")
    
    @leaderboard_updater.before_loop
    async def before_leaderboard_updater(self):
        """Wait until bot is ready"""
        await self.bot.wait_until_ready()
    
    # ==================== ACTIVITY TRACKING ====================
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Track messages sent by clan members"""
        # Ignore DMs, bots, and empty messages
        if not message.guild or message.author.bot or not message.content:
            return
        
        try:
            # Check if user is in a clan
            clan_id = await self.get_user_clan(message.guild.id, message.author.id)
            if not clan_id:
                return
            
            # Update clan activity
            today = datetime.utcnow().strftime("%Y-%m-%d")
            
            async with self.get_db() as db:
                # Update daily activity log
                await db.execute(
                    """
                    INSERT INTO clan_activity (clan_id, date, messages, voice_minutes)
                    VALUES (?, ?, 1, 0)
                    ON CONFLICT(clan_id, date) DO UPDATE SET
                        messages = messages + 1
                    """,
                    (clan_id, today)
                )
                
                # Update activity cache
                await db.execute(
                    """
                    INSERT INTO clan_activity_cache (clan_id, daily_messages, weekly_messages, monthly_messages)
                    VALUES (?, 1, 1, 1)
                    ON CONFLICT(clan_id) DO UPDATE SET
                        daily_messages = daily_messages + 1,
                        weekly_messages = weekly_messages + 1,
                        monthly_messages = monthly_messages + 1
                    """,
                    (clan_id,)
                )
                
                await db.commit()
        except Exception as e:
            # Silently fail - don't interrupt normal message flow
            print(f"Error tracking clan message activity: {e}")
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Track voice activity for clan members"""
        if member.bot:
            return
        
        try:
            # Check if user is in a clan
            clan_id = await self.get_user_clan(member.guild.id, member.id)
            if not clan_id:
                return
            
            # User joined voice channel
            if before.channel is None and after.channel is not None:
                # Store join time
                if not hasattr(self, '_voice_sessions'):
                    self._voice_sessions = {}
                self._voice_sessions[member.id] = datetime.utcnow()
            
            # User left voice channel
            elif before.channel is not None and after.channel is None:
                # Calculate session duration
                if not hasattr(self, '_voice_sessions'):
                    self._voice_sessions = {}
                
                if member.id in self._voice_sessions:
                    join_time = self._voice_sessions.pop(member.id)
                    duration_minutes = int((datetime.utcnow() - join_time).total_seconds() / 60)
                    
                    if duration_minutes > 0:
                        today = datetime.utcnow().strftime("%Y-%m-%d")
                        
                        async with self.get_db() as db:
                            # Update daily activity log
                            await db.execute(
                                """
                                INSERT INTO clan_activity (clan_id, date, messages, voice_minutes)
                                VALUES (?, ?, 0, ?)
                                ON CONFLICT(clan_id, date) DO UPDATE SET
                                    voice_minutes = voice_minutes + ?
                                """,
                                (clan_id, today, duration_minutes, duration_minutes)
                            )
                            
                            # Update activity cache
                            await db.execute(
                                """
                                INSERT INTO clan_activity_cache (clan_id, daily_voice_minutes, weekly_voice_minutes, monthly_voice_minutes)
                                VALUES (?, ?, ?, ?)
                                ON CONFLICT(clan_id) DO UPDATE SET
                                    daily_voice_minutes = daily_voice_minutes + ?,
                                    weekly_voice_minutes = weekly_voice_minutes + ?,
                                    monthly_voice_minutes = monthly_voice_minutes + ?
                                """,
                                (clan_id, duration_minutes, duration_minutes, duration_minutes, 
                                 duration_minutes, duration_minutes, duration_minutes)
                            )
                            
                            await db.commit()
        except Exception as e:
            print(f"Error tracking clan voice activity: {e}")
    
    @tasks.loop(hours=24)
    async def reset_daily_stats(self):
        """Reset daily stats at midnight UTC"""
        try:
            async with self.get_db() as db:
                await db.execute(
                    "UPDATE clan_activity_cache SET daily_messages = 0, daily_voice_minutes = 0"
                )
                await db.commit()
                print("✅ Reset daily clan stats")
        except Exception as e:
            print(f"Error resetting daily clan stats: {e}")
    
    @tasks.loop(hours=168)  # 7 days
    async def reset_weekly_stats(self):
        """Reset weekly stats every Monday"""
        try:
            async with self.get_db() as db:
                await db.execute(
                    "UPDATE clan_activity_cache SET weekly_messages = 0, weekly_voice_minutes = 0"
                )
                await db.commit()
                print("✅ Reset weekly clan stats")
        except Exception as e:
            print(f"Error resetting weekly clan stats: {e}")
    
    # ==================== CLAN ROLE CREATION ====================
    
    @clan.command(name="role")
    async def clan_role(self, ctx: commands.Context, clan_name: str, color1: str, color2: Optional[str] = None, icon: Optional[str] = None):
        """Create a custom clan role (Requires 10+ boosters in clan)
        
        Examples:
        `$clan role "Shadow Warriors" #FF5733`
        `$clan role "Shadow Warriors" #FF5733 #C70039 🔥`
        
        Note: Role will be automatically deleted if clan falls below 10 boosters
        """
        assert ctx.guild is not None
        assert isinstance(ctx.author, discord.Member)
        
        emojis = await self.get_all_emojis(ctx.guild.id)
        
        # Get clan
        async with self.get_db() as db:
            cursor = await db.execute(
                "SELECT id, leader_id, boost_count FROM clans WHERE guild_id = ? AND name = ?",
                (ctx.guild.id, clan_name)
            )
            result = await cursor.fetchone()
            
            if not result:
                embed = discord.Embed(
                    description=f"{emojis['error']} Clan `{clan_name}` not found!",
                    color=discord.Color.red()
                )
                return await ctx.send(embed=embed)
            
            clan_id, leader_id, boost_count = result
        
        # Check if user is clan leader
        if ctx.author.id != leader_id:
            embed = discord.Embed(
                description=f"{emojis['error']} Only the clan leader can create a custom role!",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Check booster requirement
        if boost_count < 10:
            embed = discord.Embed(
                description=f"{emojis['locked']} Your clan needs **10 boosters** to unlock custom roles!\nCurrent: **{boost_count}/10**",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Parse colors
        try:
            # Remove # if present
            color1 = color1.replace("#", "")
            main_color = discord.Color(int(color1, 16))
        except:
            embed = discord.Embed(
                description=f"{emojis['error']} Invalid color format! Use hex colors like `#FF5733`",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Check if clan already has a role
        async with self.get_db() as db:
            cursor = await db.execute(
                "SELECT role_id FROM clan_roles WHERE clan_id = ?",
                (clan_id,)
            )
            existing_role = await cursor.fetchone()
            
            if existing_role:
                # Delete old role
                old_role = ctx.guild.get_role(existing_role[0])
                if old_role:
                    try:
                        await old_role.delete(reason=f"Replacing with new clan role for {clan_name}")
                    except:
                        pass
        
        # Create the new role
        try:
            role = await ctx.guild.create_role(
                name=f"⚔️ {clan_name}",
                color=main_color,
                reason=f"Clan role for {clan_name} (10+ boosters)"
            )
            
            # Give role to all clan members
            members = await self.get_clan_members(clan_id)
            for member_id in members:
                member = ctx.guild.get_member(member_id)
                if member:
                    try:
                        await member.add_roles(role, reason=f"Member of clan {clan_name}")
                    except:
                        pass
            
            # Save to database
            async with self.get_db() as db:
                await db.execute(
                    """
                    INSERT INTO clan_roles (clan_id, role_id, guild_id, booster_count)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(clan_id) DO UPDATE SET
                        role_id = ?,
                        booster_count = ?
                    """,
                    (clan_id, role.id, ctx.guild.id, boost_count, role.id, boost_count)
                )
                await db.commit()
            
            embed = discord.Embed(
                title=f"{emojis['success']} Clan Role Created!",
                description=f"{emojis['role']} {role.mention} has been created for `{clan_name}`!\n\n{emojis['members']} All clan members have received the role.",
                color=main_color
            )
            embed.set_footer(text="Role will be removed if clan falls below 10 boosters")
            
            await ctx.send(embed=embed)
            
        except discord.Forbidden:
            embed = discord.Embed(
                description=f"{emojis['error']} I don't have permission to create roles!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                description=f"{emojis['error']} Failed to create role: {str(e)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
    
    # ==================== CLAN MANAGEMENT COMMANDS ====================
    
    @clan.command(name="disband")
    async def clan_disband(self, ctx: commands.Context, clan_name: Optional[str] = None):
        """Disband your clan (Leader only)
        
        Example: `$clan disband "Shadow Warriors"`
        Or just: `$clan disband` (if you're in a clan)
        """
        assert ctx.guild is not None
        assert isinstance(ctx.author, discord.Member)
        
        emojis = await self.get_all_emojis(ctx.guild.id)
        
        # Get user's clan if no name provided
        if not clan_name:
            clan_id = await self.get_user_clan(ctx.guild.id, ctx.author.id)
            if not clan_id:
                embed = discord.Embed(
                    description=f"{emojis['error']} You are not in a clan!",
                    color=discord.Color.red()
                )
                return await ctx.send(embed=embed)
        else:
            # Get clan by name
            async with self.get_db() as db:
                cursor = await db.execute(
                    "SELECT id FROM clans WHERE guild_id = ? AND name = ?",
                    (ctx.guild.id, clan_name)
                )
                result = await cursor.fetchone()
                if not result:
                    embed = discord.Embed(
                        description=f"{emojis['error']} Clan `{clan_name}` not found!",
                        color=discord.Color.red()
                    )
                    return await ctx.send(embed=embed)
                clan_id = result[0]
        
        # Get clan info
        clan = await self.get_clan_info(clan_id)
        if not clan:
            return await ctx.send(f"{emojis['error']} Clan not found!")
        
        # Check if user is leader
        if ctx.author.id != clan["leader_id"]:
            embed = discord.Embed(
                description=f"{emojis['error']} Only the clan leader can disband the clan!",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Delete clan role if it exists
        async with self.get_db() as db:
            cursor = await db.execute(
                "SELECT role_id FROM clan_roles WHERE clan_id = ?",
                (clan_id,)
            )
            role_result = await cursor.fetchone()
            
            if role_result:
                role = ctx.guild.get_role(role_result[0])
                if role:
                    try:
                        await role.delete(reason=f"Clan {clan['name']} disbanded")
                    except:
                        pass
        
        # Delete clan from database (CASCADE will remove members and roles)
        async with self.get_db() as db:
            await db.execute("DELETE FROM clans WHERE id = ?", (clan_id,))
            await db.commit()
        
        embed = discord.Embed(
            description=f"{emojis['success']} Clan `{clan['name']}` has been disbanded!",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    
    @clan.command(name="kick")
    async def clan_kick(self, ctx: commands.Context, member: discord.Member, clan_name: Optional[str] = None):
        """Kick a member from your clan (Leader only)
        
        Example: `$clan kick @user "Shadow Warriors"`
        Or: `$clan kick @user` (kicks from your clan)
        """
        assert ctx.guild is not None
        assert isinstance(ctx.author, discord.Member)
        
        emojis = await self.get_all_emojis(ctx.guild.id)
        
        # Get clan
        if not clan_name:
            clan_id = await self.get_user_clan(ctx.guild.id, ctx.author.id)
            if not clan_id:
                embed = discord.Embed(
                    description=f"{emojis['error']} You are not in a clan!",
                    color=discord.Color.red()
                )
                return await ctx.send(embed=embed)
        else:
            async with self.get_db() as db:
                cursor = await db.execute(
                    "SELECT id FROM clans WHERE guild_id = ? AND name = ?",
                    (ctx.guild.id, clan_name)
                )
                result = await cursor.fetchone()
                if not result:
                    embed = discord.Embed(
                        description=f"{emojis['error']} Clan `{clan_name}` not found!",
                        color=discord.Color.red()
                    )
                    return await ctx.send(embed=embed)
                clan_id = result[0]
        
        # Get clan info
        clan = await self.get_clan_info(clan_id)
        if not clan:
            return await ctx.send(f"{emojis['error']} Clan not found!")
        
        # Check if user is leader
        if ctx.author.id != clan["leader_id"]:
            embed = discord.Embed(
                description=f"{emojis['error']} Only the clan leader can kick members!",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Can't kick yourself
        if member.id == ctx.author.id:
            embed = discord.Embed(
                description=f"{emojis['error']} You can't kick yourself! Use `$clan disband` instead.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Check if member is in clan
        members = await self.get_clan_members(clan_id)
        if member.id not in members:
            embed = discord.Embed(
                description=f"{emojis['error']} {member.mention} is not in this clan!",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Remove member
        async with self.get_db() as db:
            await db.execute(
                "DELETE FROM clan_members WHERE clan_id = ? AND user_id = ?",
                (clan_id, member.id)
            )
            await db.commit()
        
        # Update stats
        await self.update_clan_stats(clan_id, ctx.guild)
        
        # Remove clan role if they have it
        async with self.get_db() as db:
            cursor = await db.execute(
                "SELECT role_id FROM clan_roles WHERE clan_id = ?",
                (clan_id,)
            )
            role_result = await cursor.fetchone()
            
            if role_result:
                role = ctx.guild.get_role(role_result[0])
                if role and role in member.roles:
                    try:
                        await member.remove_roles(role, reason=f"Kicked from clan {clan['name']}")
                    except:
                        pass
        
        embed = discord.Embed(
            description=f"{emojis['success']} Kicked {member.mention} from `{clan['name']}`!",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    
    @clan.command(name="invite", aliases=["add"])
    async def clan_invite(self, ctx: commands.Context, member: discord.Member, clan_name: Optional[str] = None):
        """Invite a member to your clan (Leader only)
        
        Example: `$clan invite @user "Shadow Warriors"`
        Or: `$clan invite @user` (invites to your clan)
        """
        assert ctx.guild is not None
        assert isinstance(ctx.author, discord.Member)
        
        emojis = await self.get_all_emojis(ctx.guild.id)
        
        # Get clan
        if not clan_name:
            clan_id = await self.get_user_clan(ctx.guild.id, ctx.author.id)
            if not clan_id:
                embed = discord.Embed(
                    description=f"{emojis['error']} You are not in a clan!",
                    color=discord.Color.red()
                )
                return await ctx.send(embed=embed)
        else:
            async with self.get_db() as db:
                cursor = await db.execute(
                    "SELECT id FROM clans WHERE guild_id = ? AND name = ?",
                    (ctx.guild.id, clan_name)
                )
                result = await cursor.fetchone()
                if not result:
                    embed = discord.Embed(
                        description=f"{emojis['error']} Clan `{clan_name}` not found!",
                        color=discord.Color.red()
                    )
                    return await ctx.send(embed=embed)
                clan_id = result[0]
        
        # Get clan info
        clan = await self.get_clan_info(clan_id)
        if not clan:
            return await ctx.send(f"{emojis['error']} Clan not found!")
        
        # Check if user is leader
        if ctx.author.id != clan["leader_id"]:
            embed = discord.Embed(
                description=f"{emojis['error']} Only the clan leader can invite members!",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Check if member is already in a clan
        existing_clan = await self.get_user_clan(ctx.guild.id, member.id)
        if existing_clan:
            existing_info = await self.get_clan_info(existing_clan)
            if existing_info:
                embed = discord.Embed(
                    description=f"{emojis['error']} {member.mention} is already in clan `{existing_info['name']}`!",
                    color=discord.Color.red()
                )
                return await ctx.send(embed=embed)
        
        # Check member limit
        if clan["member_count"] >= 7:
            embed = discord.Embed(
                description=f"{emojis['error']} Your clan is full! (7/7 members)",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Add member
        async with self.get_db() as db:
            await db.execute(
                "INSERT INTO clan_members (clan_id, user_id) VALUES (?, ?)",
                (clan_id, member.id)
            )
            await db.commit()
        
        # Update stats
        await self.update_clan_stats(clan_id, ctx.guild)
        
        # Give clan role if it exists
        async with self.get_db() as db:
            cursor = await db.execute(
                "SELECT role_id FROM clan_roles WHERE clan_id = ?",
                (clan_id,)
            )
            role_result = await cursor.fetchone()
            
            if role_result:
                role = ctx.guild.get_role(role_result[0])
                if role:
                    try:
                        await member.add_roles(role, reason=f"Joined clan {clan['name']}")
                    except:
                        pass
        
        embed = discord.Embed(
            description=f"{emojis['success']} {member.mention} has joined `{clan['name']}`!",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    
    @clan.command(name="leave")
    async def clan_leave(self, ctx: commands.Context):
        """Leave your current clan
        
        Example: `$clan leave`
        Note: Leaders must transfer leadership or disband first
        """
        assert ctx.guild is not None
        assert isinstance(ctx.author, discord.Member)
        
        emojis = await self.get_all_emojis(ctx.guild.id)
        
        # Get user's clan
        clan_id = await self.get_user_clan(ctx.guild.id, ctx.author.id)
        if not clan_id:
            embed = discord.Embed(
                description=f"{emojis['error']} You are not in a clan!",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Get clan info
        clan = await self.get_clan_info(clan_id)
        if not clan:
            return await ctx.send(f"{emojis['error']} Clan not found!")
        
        # Check if user is leader
        if ctx.author.id == clan["leader_id"]:
            embed = discord.Embed(
                description=f"{emojis['error']} You are the clan leader! Transfer leadership with `$clan leader` or disband with `$clan disband`.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Remove member
        async with self.get_db() as db:
            await db.execute(
                "DELETE FROM clan_members WHERE clan_id = ? AND user_id = ?",
                (clan_id, ctx.author.id)
            )
            await db.commit()
        
        # Update stats
        await self.update_clan_stats(clan_id, ctx.guild)
        
        # Remove clan role if they have it
        async with self.get_db() as db:
            cursor = await db.execute(
                "SELECT role_id FROM clan_roles WHERE clan_id = ?",
                (clan_id,)
            )
            role_result = await cursor.fetchone()
            
            if role_result:
                role = ctx.guild.get_role(role_result[0])
                if role and role in ctx.author.roles:
                    try:
                        await ctx.author.remove_roles(role, reason=f"Left clan {clan['name']}")
                    except:
                        pass
        
        embed = discord.Embed(
            description=f"{emojis['success']} You have left `{clan['name']}`!",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    
    # ==================== AUTO ROLE MONITORING ====================
    
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Monitor booster status changes and auto-delete clan roles if below 10"""
        # Check if boost status changed
        if before.premium_since == after.premium_since:
            return
        
        # Get all clans in this guild
        async with self.get_db() as db:
            cursor = await db.execute(
                "SELECT id FROM clans WHERE guild_id = ?",
                (after.guild.id,)
            )
            clans = await cursor.fetchall()
        
        # Update all clans this member is in
        for (clan_id,) in clans:
            members = await self.get_clan_members(clan_id)
            if after.id in members:
                await self.update_clan_stats(clan_id, after.guild)
                
                # Check if clan has a role and needs removal
                clan = await self.get_clan_info(clan_id)
                if clan and clan["boost_count"] < 10:
                    async with self.get_db() as db:
                        cursor = await db.execute(
                            "SELECT role_id FROM clan_roles WHERE clan_id = ?",
                            (clan_id,)
                        )
                        role_result = await cursor.fetchone()
                        
                        if role_result:
                            role = after.guild.get_role(role_result[0])
                            if role:
                                try:
                                    await role.delete(reason=f"Clan {clan['name']} fell below 10 boosters ({clan['boost_count']}/10)")
                                    
                                    # Remove from database
                                    await db.execute(
                                        "DELETE FROM clan_roles WHERE clan_id = ?",
                                        (clan_id,)
                                    )
                                    await db.commit()
                                    
                                    # Notify clan leader
                                    leader = after.guild.get_member(clan["leader_id"])
                                    if leader:
                                        emojis = await self.get_all_emojis(after.guild.id)
                                        try:
                                            embed = discord.Embed(
                                                description=f"{emojis['locked']} Your clan `{clan['name']}` custom role was removed because you fell below 10 boosters ({clan['boost_count']}/10).",
                                                color=discord.Color.red()
                                            )
                                            await leader.send(embed=embed)
                                        except:
                                            pass
                                except:
                                    pass
    
    # ==================== CLAN STATISTICS COMMANDS ====================
    
    @clan.command(name="stats")
    async def clan_stats(self, ctx: commands.Context, *, clan_name: Optional[str] = None):
        """View detailed statistics for a clan
        
        Examples:
        `$clan stats` - View your clan's stats
        `$clan stats Shadow Warriors` - View specific clan stats
        """
        assert ctx.guild is not None
        assert isinstance(ctx.author, discord.Member)
        
        emojis = await self.get_all_emojis(ctx.guild.id)
        
        # Determine which clan to show
        if not clan_name:
            clan_id = await self.get_user_clan(ctx.guild.id, ctx.author.id)
            if not clan_id:
                embed = discord.Embed(
                    description=f"{emojis['error']} You are not in a clan! Specify a clan name to view.",
                    color=discord.Color.red()
                )
                return await ctx.send(embed=embed)
        else:
            async with self.get_db() as db:
                cursor = await db.execute(
                    "SELECT id FROM clans WHERE guild_id = ? AND name = ?",
                    (ctx.guild.id, clan_name)
                )
                result = await cursor.fetchone()
                if not result:
                    embed = discord.Embed(
                        description=f"{emojis['error']} Clan `{clan_name}` not found!",
                        color=discord.Color.red()
                    )
                    return await ctx.send(embed=embed)
                clan_id = result[0]
        
        # Get clan info and stats
        clan = await self.get_clan_info(clan_id)
        if not clan:
            return await ctx.send(f"{emojis['error']} Clan not found!")
        
        async with self.get_db() as db:
            # Get activity stats
            cursor = await db.execute(
                """
                SELECT daily_messages, daily_voice_minutes,
                       weekly_messages, weekly_voice_minutes,
                       monthly_messages, monthly_voice_minutes
                FROM clan_activity_cache
                WHERE clan_id = ?
                """,
                (clan_id,)
            )
            stats = await cursor.fetchone()
            
            if stats:
                daily_msg, daily_voice, weekly_msg, weekly_voice, monthly_msg, monthly_voice = stats
            else:
                daily_msg = daily_voice = weekly_msg = weekly_voice = monthly_msg = monthly_voice = 0
        
        # Get leader
        leader = ctx.guild.get_member(clan["leader_id"])
        leader_name = leader.mention if leader else "Unknown"
        
        # Format voice times
        def format_voice(minutes):
            if minutes >= 60:
                hours = minutes / 60
                return f"{hours:.1f} hours"
            return f"{minutes} minutes"
        
        embed = discord.Embed(
            title=f"{emojis['icon']} {clan['name']} Statistics",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name=f"{emojis['leader']} Leadership",
            value=f"**Leader:** {leader_name}\n"
                  f"**Created:** <t:{int(datetime.fromisoformat(clan['created_at']).timestamp())}:R>",
            inline=False
        )
        
        embed.add_field(
            name=f"{emojis['members']} Members",
            value=f"**Total:** {clan['member_count']}/7\n"
                  f"**Boosters:** {emojis['boost']} {clan['boost_count']}",
            inline=True
        )
        
        embed.add_field(
            name="📊 Activity Today",
            value=f"**Messages:** 💬 {daily_msg:,}\n"
                  f"**Voice:** 🎤 {format_voice(daily_voice)}",
            inline=True
        )
        
        embed.add_field(
            name="📈 This Week",
            value=f"**Messages:** 💬 {weekly_msg:,}\n"
                  f"**Voice:** 🎤 {format_voice(weekly_voice)}",
            inline=True
        )
        
        embed.add_field(
            name="📅 This Month",
            value=f"**Messages:** 💬 {monthly_msg:,}\n"
                  f"**Voice:** 🎤 {format_voice(monthly_voice)}",
            inline=True
        )
        
        # Calculate activity score
        activity_score = (clan['member_count'] * 10) + (weekly_msg / 100) + (weekly_voice / 12)
        
        embed.add_field(
            name=f"{emojis['stats']} Overall Score",
            value=f"**{activity_score:.0f}** points\n"
                  f"*Based on members, messages, and voice time*",
            inline=False
        )
        
        embed.set_footer(text="Stats update in real-time")
        await ctx.send(embed=embed)
    
    @commands.command(name="clanranks")
    async def clan_ranks(self, ctx: commands.Context, sort_by: str = "balanced"):
        """View clan rankings (quick view without auto-update)
        
        Sort options: `balanced`, `members`, `messages`, `voice`
        
        Examples:
        `$clanranks` - View overall rankings
        `$clanranks messages` - Sort by message activity
        `$clanranks voice` - Sort by voice time
        """
        assert ctx.guild is not None
        
        emojis = await self.get_all_emojis(ctx.guild.id)
        
        # Validate sort mode
        valid_modes = ["balanced", "members", "messages", "voice"]
        if sort_by.lower() not in valid_modes:
            embed = discord.Embed(
                description=f"{emojis['error']} Invalid sort mode! Use: `balanced`, `members`, `messages`, or `voice`",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Generate and send embed
        embed = await self.generate_leaderboard_embed(ctx.guild, sort_by.lower())
        await ctx.send(embed=embed)
    
    @clan.command(name="activity")
    async def clan_activity(self, ctx: commands.Context):
        """View your clan's recent activity breakdown"""
        assert ctx.guild is not None
        assert isinstance(ctx.author, discord.Member)
        
        emojis = await self.get_all_emojis(ctx.guild.id)
        
        # Get user's clan
        clan_id = await self.get_user_clan(ctx.guild.id, ctx.author.id)
        if not clan_id:
            embed = discord.Embed(
                description=f"{emojis['error']} You are not in a clan!",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        clan = await self.get_clan_info(clan_id)
        if not clan:
            return await ctx.send(f"{emojis['error']} Clan not found!")
        
        # Get last 7 days of activity
        async with self.get_db() as db:
            cursor = await db.execute(
                """
                SELECT date, messages, voice_minutes
                FROM clan_activity
                WHERE clan_id = ?
                ORDER BY date DESC
                LIMIT 7
                """,
                (clan_id,)
            )
            activity = await cursor.fetchall()
        
        embed = discord.Embed(
            title=f"{emojis['stats']} {clan['name']} - Activity History",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        if not activity:
            embed.description = "Last 7 days of clan activity\n\n*No activity recorded yet!*"
        else:
            activity_text = []
            for date_str, messages, voice_minutes in activity:
                voice_hours = voice_minutes / 60
                voice_display = f"{voice_hours:.1f}h" if voice_hours >= 1 else f"{voice_minutes}m"
                
                activity_text.append(
                    f"**{date_str}**\n"
                    f"💬 {messages:,} messages • 🎤 {voice_display} voice"
                )
            
            embed.description = "Last 7 days of clan activity\n\n" + "\n\n".join(activity_text)
        
        embed.set_footer(text="Activity tracking started when clan was created")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(ClanSystem(bot))
