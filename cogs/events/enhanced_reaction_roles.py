import discord
from discord.ext import commands
import sqlite3
import json
import os
from typing import Optional, List, Dict
from utils.member_state import member_state_manager

class EnhancedReactionRoleManager:
    """Enhanced reaction role manager with member state integration"""
    
    def __init__(self, bot):
        self.bot = bot
        # Use enhanced database path, but fall back to original if it exists
        self.db_path = "db/enhanced_reaction_roles.db"
        if not os.path.exists(self.db_path) and os.path.exists("db/reaction_roles.db"):
            # If enhanced DB doesn't exist but original does, use original
            self.db_path = "db/reaction_roles.db"
        self.init_database()
    
    def init_database(self):
        """Initialize enhanced database schema"""
        with sqlite3.connect(self.db_path) as conn:
            # Enhanced reaction roles table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reaction_roles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    emoji TEXT NOT NULL,
                    role_id INTEGER NOT NULL,
                    panel_id INTEGER,
                    description TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(guild_id, message_id, emoji)
                )
            """)
            
            # Reaction role assignments tracking
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rr_assignments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    role_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    emoji TEXT NOT NULL,
                    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    removed_at TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE,
                    INDEX(guild_id, user_id),
                    INDEX(guild_id, message_id)
                )
            """)
            
            # Settings table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rr_settings (
                    guild_id INTEGER PRIMARY KEY,
                    dm_enabled BOOLEAN DEFAULT TRUE,
                    log_channel_id INTEGER,
                    remove_reaction BOOLEAN DEFAULT FALSE,
                    auto_restore BOOLEAN DEFAULT TRUE,
                    max_roles_per_user INTEGER DEFAULT 0,
                    require_verification BOOLEAN DEFAULT FALSE
                )
            """)
            
            conn.commit()
    
    async def handle_reaction_add(self, payload):
        """Enhanced reaction add handler with persistence"""
        if payload.guild_id is None:
            return
        
        guild = self.bot.get_guild(payload.guild_id)
        member = payload.member or guild.get_member(payload.user_id)
        
        if not member or member.bot:
            return
        
        # Get the role for this reaction
        role_id = self.get_role_by_emoji(payload.guild_id, payload.message_id, str(payload.emoji))
        if not role_id:
            return
        
        role = guild.get_role(role_id)
        if not role:
            return
        
        # Check if user already has this role
        if role in member.roles:
            return
        
        try:
            # Check role limits
            settings = self.get_settings(payload.guild_id)
            if settings['max_roles_per_user'] > 0:
                current_rr_roles = self.get_user_reaction_roles(payload.guild_id, member.id)
                if len(current_rr_roles) >= settings['max_roles_per_user']:
                    # Send DM about limit
                    try:
                        await member.send(f"❌ You've reached the maximum of {settings['max_roles_per_user']} reaction roles in {guild.name}.")
                    except discord.Forbidden:
                        pass
                    return
            
            # Add the role
            await member.add_roles(role, reason="Reaction role assigned")
            
            # Track the assignment in member state system
            member_state_manager.save_member_roles(payload.guild_id, member.id, member.roles)
            
            # Record assignment in database
            self.record_assignment(payload.guild_id, member.id, role_id, payload.message_id, str(payload.emoji))
            
            # Remove reaction if enabled
            if settings['remove_reaction']:
                try:
                    channel = guild.get_channel(payload.channel_id)
                    if channel:
                        message = await channel.fetch_message(payload.message_id)
                        await message.remove_reaction(payload.emoji, member)
                except (discord.NotFound, discord.Forbidden):
                    pass
            
            # Send DM if enabled
            if settings['dm_enabled']:
                try:
                    embed = discord.Embed(
                        title="✅ Role Assigned!",
                        description=f"You received the **{role.name}** role in {guild.name}",
                        color=0x00ff00
                    )
                    await member.send(embed=embed)
                except discord.Forbidden:
                    pass
            
            # Log assignment
            await self.log_role_action(guild, member, role, "added", settings)
            
        except discord.Forbidden:
            # Log permission error
            await self.log_permission_error(guild, member, role, "add", settings)
    
    async def handle_reaction_remove(self, payload):
        """Enhanced reaction remove handler with persistence"""
        if payload.guild_id is None:
            return
        
        guild = self.bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        
        if not member or member.bot:
            return
        
        # Get the role for this reaction
        role_id = self.get_role_by_emoji(payload.guild_id, payload.message_id, str(payload.emoji))
        if not role_id:
            return
        
        role = guild.get_role(role_id)
        if not role or role not in member.roles:
            return
        
        try:
            # Remove the role
            await member.remove_roles(role, reason="Reaction role removed")
            
            # Update member state system
            member_state_manager.save_member_roles(payload.guild_id, member.id, member.roles)
            
            # Mark assignment as inactive
            self.deactivate_assignment(payload.guild_id, member.id, role_id, payload.message_id, str(payload.emoji))
            
            # Log removal
            settings = self.get_settings(payload.guild_id)
            await self.log_role_action(guild, member, role, "removed", settings)
            
        except discord.Forbidden:
            # Log permission error
            settings = self.get_settings(payload.guild_id)
            await self.log_permission_error(guild, member, role, "remove", settings)
    
    async def restore_user_reaction_roles(self, guild_id: int, user_id: int):
        """Restore user's reaction roles when they rejoin"""
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return 0, 0
        
        member = guild.get_member(user_id)
        if not member:
            return 0, 0
        
        # Get user's active reaction role assignments
        assignments = self.get_user_active_assignments(guild_id, user_id)
        if not assignments:
            return 0, 0
        
        restored_roles = []
        failed_roles = []
        
        for assignment in assignments:
            role = guild.get_role(assignment['role_id'])
            if role and role not in member.roles:
                try:
                    await member.add_roles(role, reason="Reaction role restored on rejoin")
                    restored_roles.append(role)
                except discord.Forbidden:
                    failed_roles.append(role)
        
        # Log restoration
        settings = self.get_settings(guild_id)
        if restored_roles:
            await self.log_role_restoration(guild, member, restored_roles, settings)
        
        if failed_roles:
            await self.log_restoration_failures(guild, member, failed_roles, settings)
        
        return len(restored_roles), len(failed_roles)
    
    # Database methods
    def get_role_by_emoji(self, guild_id: int, message_id: int, emoji: str) -> Optional[int]:
        """Get role ID for a specific emoji on a message"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT role_id FROM reaction_roles 
                WHERE guild_id = ? AND message_id = ? AND emoji = ?
            """, (guild_id, message_id, emoji))
            result = cursor.fetchone()
            return result[0] if result else None
    
    def record_assignment(self, guild_id: int, user_id: int, role_id: int, message_id: int, emoji: str):
        """Record a role assignment"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO rr_assignments 
                (guild_id, user_id, role_id, message_id, emoji, is_active)
                VALUES (?, ?, ?, ?, ?, TRUE)
            """, (guild_id, user_id, role_id, message_id, emoji))
            conn.commit()
    
    def deactivate_assignment(self, guild_id: int, user_id: int, role_id: int, message_id: int, emoji: str):
        """Mark an assignment as inactive"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE rr_assignments 
                SET is_active = FALSE, removed_at = CURRENT_TIMESTAMP
                WHERE guild_id = ? AND user_id = ? AND role_id = ? 
                AND message_id = ? AND emoji = ? AND is_active = TRUE
            """, (guild_id, user_id, role_id, message_id, emoji))
            conn.commit()
    
    def get_user_reaction_roles(self, guild_id: int, user_id: int) -> List[int]:
        """Get all active reaction roles for a user"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT DISTINCT role_id FROM rr_assignments 
                WHERE guild_id = ? AND user_id = ? AND is_active = TRUE
            """, (guild_id, user_id))
            return [row[0] for row in cursor.fetchall()]
    
    def get_user_active_assignments(self, guild_id: int, user_id: int) -> List[Dict]:
        """Get all active assignments for a user"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM rr_assignments 
                WHERE guild_id = ? AND user_id = ? AND is_active = TRUE
            """, (guild_id, user_id))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_settings(self, guild_id: int) -> Dict:
        """Get guild settings"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM rr_settings WHERE guild_id = ?", (guild_id,))
            row = cursor.fetchone()
            if row:
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
            return {
                'dm_enabled': True,
                'log_channel_id': None,
                'remove_reaction': False,
                'auto_restore': True,
                'max_roles_per_user': 0,
                'require_verification': False
            }
    
    def update_settings(self, guild_id: int, **kwargs):
        """Update guild settings"""
        with sqlite3.connect(self.db_path) as conn:
            # Get current settings
            current = self.get_settings(guild_id)
            current.update(kwargs)
            
            conn.execute("""
                INSERT OR REPLACE INTO rr_settings 
                (guild_id, dm_enabled, log_channel_id, remove_reaction, auto_restore, max_roles_per_user, require_verification)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (guild_id, current['dm_enabled'], current['log_channel_id'], 
                  current['remove_reaction'], current['auto_restore'], 
                  current['max_roles_per_user'], current['require_verification']))
            conn.commit()
    
    # Logging methods
    async def log_role_action(self, guild, member, role, action, settings):
        """Log role assignment/removal"""
        if not settings['log_channel_id']:
            return
        
        log_channel = guild.get_channel(settings['log_channel_id'])
        if not log_channel:
            return
        
        color = 0x00ff00 if action == "added" else 0xff0000
        embed = discord.Embed(
            title=f"🎭 Reaction Role {action.title()}",
            description=f"{member.mention} {action} {role.mention}",
            color=color,
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(name="User", value=f"{member} ({member.id})", inline=True)
        embed.add_field(name="Role", value=f"{role.name} ({role.id})", inline=True)
        embed.add_field(name="Action", value=action.title(), inline=True)
        
        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            pass
    
    async def log_role_restoration(self, guild, member, restored_roles, settings):
        """Log role restoration on rejoin"""
        if not settings['log_channel_id']:
            return
        
        log_channel = guild.get_channel(settings['log_channel_id'])
        if not log_channel:
            return
        
        embed = discord.Embed(
            title="🔄 Reaction Roles Restored",
            description=f"{member.mention} rejoined and had their reaction roles restored",
            color=0x00aaff,
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(name="User", value=f"{member} ({member.id})", inline=False)
        embed.add_field(
            name=f"Restored Roles ({len(restored_roles)})",
            value="\n".join([f"• {role.mention}" for role in restored_roles[:10]]) + 
                  (f"\n• ...and {len(restored_roles) - 10} more" if len(restored_roles) > 10 else ""),
            inline=False
        )
        
        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            pass
    
    async def log_restoration_failures(self, guild, member, failed_roles, settings):
        """Log failed role restorations"""
        if not settings['log_channel_id']:
            return
        
        log_channel = guild.get_channel(settings['log_channel_id'])
        if not log_channel:
            return
        
        embed = discord.Embed(
            title="⚠️ Role Restoration Failures",
            description=f"Failed to restore some roles for {member.mention}",
            color=0xff9900,
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(name="User", value=f"{member} ({member.id})", inline=False)
        embed.add_field(
            name=f"Failed Roles ({len(failed_roles)})",
            value="\n".join([f"• {role.mention}" for role in failed_roles[:10]]) + 
                  (f"\n• ...and {len(failed_roles) - 10} more" if len(failed_roles) > 10 else ""),
            inline=False
        )
        embed.add_field(name="Reason", value="Missing permissions", inline=False)
        
        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            pass
    
    async def log_permission_error(self, guild, member, role, action, settings):
        """Log permission errors"""
        if not settings['log_channel_id']:
            return
        
        log_channel = guild.get_channel(settings['log_channel_id'])
        if not log_channel:
            return
        
        embed = discord.Embed(
            title="❌ Permission Error",
            description=f"Failed to {action} {role.mention} for {member.mention}",
            color=0xff0000,
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(name="User", value=f"{member} ({member.id})", inline=True)
        embed.add_field(name="Role", value=f"{role.name} ({role.id})", inline=True)
        embed.add_field(name="Action", value=action.title(), inline=True)
        embed.add_field(name="Issue", value="Bot lacks permissions", inline=False)
        
        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            pass

class EnhancedReactionRoleEvents(commands.Cog):
    """Enhanced reaction role event handler with persistence"""
    
    def __init__(self, bot):
        self.bot = bot
        self.manager = EnhancedReactionRoleManager(bot)
    
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """Handle reaction additions"""
        await self.manager.handle_reaction_add(payload)
    
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        """Handle reaction removals"""
        await self.manager.handle_reaction_remove(payload)
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Restore reaction roles when member rejoins"""
        settings = self.manager.get_settings(member.guild.id)
        if settings['auto_restore']:
            restored, failed = await self.manager.restore_user_reaction_roles(member.guild.id, member.id)
            if restored > 0:
                print(f"[RR] Restored {restored} reaction roles for {member} in {member.guild.name}")
            if failed > 0:
                print(f"[RR] Failed to restore {failed} reaction roles for {member} in {member.guild.name}")

async def setup(bot):
    await bot.add_cog(EnhancedReactionRoleEvents(bot))