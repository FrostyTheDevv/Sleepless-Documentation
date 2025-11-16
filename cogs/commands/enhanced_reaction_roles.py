import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, List
import json
import sqlite3
from utils.custom_permissions import require_custom_permissions
from utils.member_state import member_state_manager
from utils.error_helpers import StandardErrorHandler
from utils.Tools import blacklist_check, ignore_check

class EnhancedReactionRoleManager:
    """Enhanced reaction role manager with member state integration"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db_path = 'enhanced_reaction_roles.db'
        self.init_database()
    
    def init_database(self):
        """Initialize the enhanced reaction role database"""
        with sqlite3.connect(self.db_path) as conn:
            # Reaction roles table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reaction_roles (
                    id INTEGER PRIMARY KEY,
                    guild_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    emoji TEXT NOT NULL,
                    role_id INTEGER NOT NULL,
                    description TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(guild_id, message_id, emoji)
                )
            """)
            
            # Role assignments table for tracking active assignments
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rr_assignments (
                    id INTEGER PRIMARY KEY,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    role_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    emoji TEXT NOT NULL,
                    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE,
                    UNIQUE(guild_id, user_id, role_id, message_id)
                )
            """)
            
            # Settings table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rr_settings (
                    guild_id INTEGER PRIMARY KEY,
                    dm_enabled BOOLEAN DEFAULT FALSE,
                    log_channel_id INTEGER,
                    remove_reaction BOOLEAN DEFAULT FALSE,
                    auto_restore BOOLEAN DEFAULT TRUE,
                    max_roles_per_user INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Panels table for tracking message panels
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rr_panels (
                    id INTEGER PRIMARY KEY,
                    guild_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    color TEXT DEFAULT '#2f3136',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(guild_id, message_id)
                )
            """)
            
            conn.commit()
    
    async def store_panel(self, guild_id: int, message_id: int, channel_id: int, title: str, description: str, color: str):
        """Store a reaction role panel"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO rr_panels (guild_id, message_id, channel_id, title, description, color)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (guild_id, message_id, channel_id, title, description, color))
            conn.commit()
    
    async def get_role_by_emoji(self, guild_id: int, message_id: int, emoji: str):
        """Get role ID for a specific emoji on a message"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT role_id FROM reaction_roles 
                WHERE guild_id = ? AND message_id = ? AND emoji = ?
            """, (guild_id, message_id, emoji))
            result = cursor.fetchone()
            return result[0] if result else None
    
    async def add_role_to_database(self, guild_id: int, message_id: int, channel_id: int, emoji: str, role_id: int, description: str):
        """Add a role to the database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO reaction_roles (guild_id, message_id, channel_id, emoji, role_id, description)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (guild_id, message_id, channel_id, emoji, role_id, description))
            conn.commit()
        return True
    
    async def remove_role_from_database(self, guild_id: int, message_id: int, emoji: str):
        """Remove a role from the database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                DELETE FROM reaction_roles 
                WHERE guild_id = ? AND message_id = ? AND emoji = ?
            """, (guild_id, message_id, emoji))
            conn.commit()
        return True
    
    async def get_all_reaction_roles(self, guild_id: int):
        """Get all reaction roles for a guild"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM reaction_roles WHERE guild_id = ? ORDER BY message_id, created_at
            """, (guild_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    async def get_message_roles(self, guild_id: int, message_id: int):
        """Get all reaction roles for a specific message"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM reaction_roles 
                WHERE guild_id = ? AND message_id = ? 
                ORDER BY created_at
            """, (guild_id, message_id))
            return [dict(row) for row in cursor.fetchall()]
    
    async def get_settings(self, guild_id: int):
        """Get reaction role settings for a guild"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM rr_settings WHERE guild_id = ?
            """, (guild_id,))
            result = cursor.fetchone()
            if result:
                return dict(result)
            else:
                # Return default settings
                return {
                    'dm_enabled': False,
                    'log_channel_id': None,
                    'remove_reaction': False,
                    'auto_restore': True,
                    'max_roles_per_user': 0,
                    'auto_remove': True,
                    'role_persistence': True
                }
    
    async def update_settings(self, guild_id: int, settings: dict):
        """Update reaction role settings for a guild"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO rr_settings 
                (guild_id, dm_enabled, log_channel_id, remove_reaction, auto_restore, max_roles_per_user, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                guild_id,
                settings.get('dm_enabled', False),
                settings.get('log_channel_id'),
                settings.get('remove_reaction', False),
                settings.get('auto_restore', True),
                settings.get('max_roles_per_user', 0)
            ))
            conn.commit()
        return True
    
    async def get_server_stats(self, guild_id: int):
        """Get statistics for the server"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT 
                    COUNT(DISTINCT message_id) as total_panels,
                    COUNT(*) as total_roles
                FROM reaction_roles 
                WHERE guild_id = ?
            """, (guild_id,))
            row = cursor.fetchone()
            total_panels, total_roles = row if row else (0, 0)
            
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as active_assignments,
                    COUNT(DISTINCT user_id) as active_members
                FROM rr_assignments 
                WHERE guild_id = ? AND is_active = TRUE
            """, (guild_id,))
            row = cursor.fetchone()
            active_assignments, active_members = row if row else (0, 0)
            
            cursor = conn.execute("""
                SELECT COUNT(*) as total_assignments
                FROM rr_assignments 
                WHERE guild_id = ?
            """, (guild_id,))
            row = cursor.fetchone()
            total_assignments = row[0] if row else 0
            
            # Get today's stats (assignments and removals)
            cursor = conn.execute("""
                SELECT COUNT(*) as assignments_today
                FROM rr_assignments 
                WHERE guild_id = ? AND DATE(assigned_at) = DATE('now')
            """, (guild_id,))
            row = cursor.fetchone()
            assignments_today = row[0] if row else 0
            
            cursor = conn.execute("""
                SELECT COUNT(*) as removals_today
                FROM rr_assignments 
                WHERE guild_id = ? AND is_active = FALSE AND DATE(assigned_at) = DATE('now')
            """, (guild_id,))
            row = cursor.fetchone()
            removals_today = row[0] if row else 0
            
            return {
                'total_panels': total_panels,
                'total_roles': total_roles,
                'active_assignments': active_assignments,
                'active_members': active_members,
                'assignments_today': assignments_today,
                'removals_today': removals_today,
                'restorations': 0  # This would come from member state manager
            }
    
    async def log_role_assignment(self, guild_id: int, user_id: int, role_id: int, action: str, message_id: int):
        """Log role assignment or removal"""
        emoji = ""  # You might want to store this as well
        with sqlite3.connect(self.db_path) as conn:
            if action == "add":
                conn.execute("""
                    INSERT OR REPLACE INTO rr_assignments 
                    (guild_id, user_id, role_id, message_id, emoji, is_active)
                    VALUES (?, ?, ?, ?, ?, TRUE)
                """, (guild_id, user_id, role_id, message_id, emoji))
            elif action == "remove":
                conn.execute("""
                    UPDATE rr_assignments 
                    SET is_active = FALSE 
                    WHERE guild_id = ? AND user_id = ? AND role_id = ? AND message_id = ?
                """, (guild_id, user_id, role_id, message_id))
            conn.commit()

class EnhancedReactionRoleCommands(commands.Cog):
    """Enhanced reaction role commands with member state integration"""
    
    def __init__(self, bot):
        self.bot = bot
        self.manager = EnhancedReactionRoleManager(bot)
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    @app_commands.command(
        name="rr-create",
        description="Create a new reaction role panel"
    )
    @app_commands.describe(
        channel="Channel to send the panel to",
        title="Title of the embed", 
        description="Description of the embed",
        color="Hex color for the embed (e.g., #ff0000)"
    )
    @require_custom_permissions('manage_roles')
    async def create_reaction_role(
        self, 
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        title: str,
        description: str,
        color: Optional[str] = None
    ):
        """Create a new reaction role setup"""
        
        # Validate guild
        if not interaction.guild:
            return await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
        
        # Parse color
        embed_color = 0x2f3136  # Default color
        if color:
            try:
                if color.startswith('#'):
                    color = color[1:]
                embed_color = int(color, 16)
            except ValueError:
                return await interaction.response.send_message("❌ Invalid color format! Use hex format like #ff0000", ephemeral=True)
        
        # Create the embed
        embed = discord.Embed(
            title=title,
            description=description,
            color=embed_color
        )
        
        embed.set_footer(text="React to get roles • Powered by Enhanced Reaction Roles")
        
        try:
            # Send the message
            message = await channel.send(embed=embed)
            
            # Store the panel in the database for tracking
            await self.manager.store_panel(interaction.guild.id, message.id, channel.id, title, description, color or "#2f3136")
            
            # Success response
            success_embed = discord.Embed(
                title="✅ Reaction Role Panel Created!",
                description=f"Panel created in {channel.mention}",
                color=0x00ff00
            )
            success_embed.add_field(name="Message ID", value=str(message.id), inline=True)
            success_embed.add_field(name="Channel", value=channel.mention, inline=True)
            success_embed.add_field(name="Next Step", value="Use `/rr-add` to add roles to this panel", inline=False)
            
            await interaction.response.send_message(embed=success_embed, ephemeral=True)
            
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to send messages in that channel!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)

    @app_commands.command(
        name="rr-add",
        description="Add a role to a reaction role message"
    )
    @app_commands.describe(
        message_id="ID of the message to add the role to",
        emoji="Emoji to use for the role",
        role="Role to assign",
        description="Description for this role (optional)"
    )
    @require_custom_permissions('manage_roles')
    async def add_reaction_role(
        self,
        interaction: discord.Interaction,
        message_id: str,
        emoji: str,
        role: discord.Role,
        description: Optional[str] = None
    ):
        """Add a role to an existing reaction role message"""
        
        # Validate guild
        if not interaction.guild:
            return await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
        
        try:
            message_id_int = int(message_id)
        except ValueError:
            return await interaction.response.send_message("❌ Invalid message ID!", ephemeral=True)
        
        # Find the message in any text channel
        message = None
        for channel in interaction.guild.text_channels:
            try:
                message = await channel.fetch_message(message_id_int)
                break
            except discord.NotFound:
                continue
            except discord.Forbidden:
                continue
        
        if not message:
            return await interaction.response.send_message("❌ Message not found!", ephemeral=True)
        
        # Add the reaction
        try:
            await message.add_reaction(emoji)
        except discord.HTTPException:
            return await interaction.response.send_message("❌ Invalid emoji or couldn't add reaction!", ephemeral=True)
        
        # Check if role already exists for this emoji
        existing_role = await self.manager.get_role_by_emoji(interaction.guild.id, message_id_int, emoji)
        if existing_role:
            return await interaction.response.send_message("❌ This emoji already has a role assigned!", ephemeral=True)
        
        # Add to database
        success = await self.manager.add_role_to_database(interaction.guild.id, message_id_int, message.channel.id, emoji, role.id, description or "")
        if success:
            await self.update_message_embed(message, interaction.guild.id)
            await interaction.response.send_message(f"✅ Role {role.mention} added for emoji {emoji}!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Failed to add role!", ephemeral=True)

    @app_commands.command(
        name="rr-remove",
        description="Remove a role from a reaction role message"
    )
    @app_commands.describe(
        message_id="ID of the message to remove the role from",
        emoji="Emoji to remove"
    )
    @require_custom_permissions('manage_roles')
    async def remove_reaction_role(
        self,
        interaction: discord.Interaction,
        message_id: str,
        emoji: str
    ):
        """Remove a role from an existing reaction role message"""
        
        # Validate guild
        if not interaction.guild:
            return await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
        
        try:
            message_id_int = int(message_id)
        except ValueError:
            return await interaction.response.send_message("❌ Invalid message ID!", ephemeral=True)
        
        # Find the message
        message = None
        for channel in interaction.guild.text_channels:
            try:
                message = await channel.fetch_message(message_id_int)
                break
            except discord.NotFound:
                continue
            except discord.Forbidden:
                continue
        
        if not message:
            return await interaction.response.send_message("❌ Message not found!", ephemeral=True)
        
        # Check if role exists
        role_id = await self.manager.get_role_by_emoji(interaction.guild.id, message_id_int, emoji)
        if not role_id:
            return await interaction.response.send_message("❌ No role found for this emoji!", ephemeral=True)
        
        # Remove from database
        success = await self.manager.remove_role_from_database(interaction.guild.id, message_id_int, emoji)
        if success:
            # Remove the reaction
            try:
                await message.clear_reaction(emoji)
            except discord.HTTPException:
                pass  # Ignore if we can't remove the reaction
            
            role = interaction.guild.get_role(role_id)
            role_name = role.name if role else f"ID:{role_id}"
            
            await self.update_message_embed(message, interaction.guild.id)
            await interaction.response.send_message(f"✅ Role {role_name} removed for emoji {emoji}!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Failed to remove role!", ephemeral=True)

    @app_commands.command(
        name="rr-list",
        description="List all reaction roles in this server"
    )
    @require_custom_permissions('manage_roles')
    async def list_reaction_roles(self, interaction: discord.Interaction):
        """List all reaction roles in the server"""
        
        # Validate guild
        if not interaction.guild:
            return await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
        
        reaction_roles = await self.manager.get_all_reaction_roles(interaction.guild.id)
        
        if not reaction_roles:
            return await interaction.response.send_message("❌ No reaction roles found in this server!", ephemeral=True)
        
        # Group by message ID
        grouped_roles = {}
        for rr in reaction_roles:
            msg_id = rr['message_id']
            if msg_id not in grouped_roles:
                grouped_roles[msg_id] = []
            grouped_roles[msg_id].append(rr)
        
        embed = discord.Embed(
            title="📋 Reaction Roles",
            description=f"Found {len(reaction_roles)} reaction roles in {len(grouped_roles)} messages",
            color=0x00ff88
        )
        
        for msg_id, roles in grouped_roles.items():
            channel = interaction.guild.get_channel(roles[0]['channel_id'])
            channel_name = channel.mention if channel else f"Unknown Channel"
            
            role_list = []
            for rr in roles:
                role = interaction.guild.get_role(rr['role_id'])
                role_name = role.mention if role else f"Unknown Role (ID: {rr['role_id']})"
                role_list.append(f"{rr['emoji']} → {role_name}")
            
            embed.add_field(
                name=f"Message {msg_id} in {channel_name}",
                value="\n".join(role_list) if role_list else "No roles",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="rr-settings",
        description="Configure reaction role settings"
    )
    @app_commands.describe(
        auto_remove="Automatically remove roles when reaction is removed",
        log_channel="Channel for logging role changes",
        role_persistence="Enable role persistence for members who leave/rejoin"
    )
    @require_custom_permissions('manage_guild')
    async def configure_settings(
        self,
        interaction: discord.Interaction,
        auto_remove: Optional[bool] = None,
        log_channel: Optional[discord.TextChannel] = None,
        role_persistence: Optional[bool] = None
    ):
        """Configure reaction role settings for the server"""
        
        # Validate guild
        if not interaction.guild:
            return await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
        
        current_settings = await self.manager.get_settings(interaction.guild.id)
        
        # Update settings
        new_settings = {
            'auto_remove': auto_remove if auto_remove is not None else current_settings.get('auto_remove', True),
            'log_channel_id': log_channel.id if log_channel else current_settings.get('log_channel_id'),
            'role_persistence': role_persistence if role_persistence is not None else current_settings.get('role_persistence', True)
        }
        
        success = await self.manager.update_settings(interaction.guild.id, new_settings)
        
        if success:
            # Get updated settings for display
            updated_settings = await self.manager.get_settings(interaction.guild.id)
            
            embed = discord.Embed(
                title="⚙️ Reaction Role Settings Updated",
                color=0x00ff88
            )
            
            embed.add_field(
                name="Auto Remove",
                value="✅ Enabled" if updated_settings.get('auto_remove', True) else "❌ Disabled",
                inline=True
            )
            
            embed.add_field(
                name="Role Persistence",
                value="✅ Enabled" if updated_settings.get('role_persistence', True) else "❌ Disabled",
                inline=True
            )
            
            log_channel_obj = interaction.guild.get_channel(updated_settings['log_channel_id']) if updated_settings.get('log_channel_id') else None
            embed.add_field(
                name="Log Channel",
                value=log_channel_obj.mention if log_channel_obj else "None",
                inline=True
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message("❌ Failed to update settings!", ephemeral=True)

    @app_commands.command(
        name="rr-stats",
        description="View reaction role statistics"
    )
    @require_custom_permissions('manage_roles')
    async def reaction_role_stats(self, interaction: discord.Interaction):
        """View statistics about reaction roles in the server"""
        
        # Validate guild
        if not interaction.guild:
            return await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
        
        stats = await self.manager.get_server_stats(interaction.guild.id)
        
        embed = discord.Embed(
            title=f"📊 Reaction Role Statistics - {interaction.guild.name}",
            color=0x00ff88
        )
        
        embed.add_field(name="Total Panels", value=str(stats.get('total_panels', 0)), inline=True)
        embed.add_field(name="Total Roles", value=str(stats.get('total_roles', 0)), inline=True)
        embed.add_field(name="Active Members", value=str(stats.get('active_members', 0)), inline=True)
        embed.add_field(name="Role Assignments Today", value=str(stats.get('assignments_today', 0)), inline=True)
        embed.add_field(name="Role Removals Today", value=str(stats.get('removals_today', 0)), inline=True)
        embed.add_field(name="Member Restorations", value=str(stats.get('restorations', 0)), inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def update_message_embed(self, message: discord.Message, guild_id: int):
        """Update the embed to show current roles"""
        try:
            roles = await self.manager.get_message_roles(guild_id, message.id)
            
            if not roles:
                return
            
            # Get the current embed
            if message.embeds:
                embed = message.embeds[0]
                
                # Create role list
                role_list = []
                for role_data in roles:
                    role = message.guild.get_role(role_data['role_id']) if message.guild else None
                    if role:
                        desc = f" - {role_data['description']}" if role_data['description'] else ""
                        role_list.append(f"{role_data['emoji']} → {role.mention}{desc}")
                
                # Update embed
                if role_list:
                    embed.add_field(
                        name="Available Roles",
                        value="\n".join(role_list),
                        inline=False
                    )
                
                await message.edit(embed=embed)
                
        except Exception as e:
            print(f"[ENHANCED_RR] Error updating message embed: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """Handle reaction additions"""
        if payload.user_id == self.bot.user.id:
            return
            
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
            
        member = guild.get_member(payload.user_id)
        if not member:
            return
            
        # Get role for this emoji
        role_id = await self.manager.get_role_by_emoji(guild.id, payload.message_id, str(payload.emoji))
        if not role_id:
            return
            
        role = guild.get_role(role_id)
        if not role:
            return
            
        try:
            # Add the role
            await member.add_roles(role, reason="Reaction role assignment")
            
            # Save to member state for persistence
            member_state_manager.save_member_roles(guild.id, member.id, member.roles)
            
            # Log the assignment
            await self.manager.log_role_assignment(guild.id, member.id, role.id, "add", payload.message_id)
            
            print(f"[ENHANCED_RR] Added role {role.name} to {member.display_name}")
            
        except discord.Forbidden:
            print(f"[ENHANCED_RR] No permission to add role {role.name} to {member.display_name}")
        except Exception as e:
            print(f"[ENHANCED_RR] Error adding role: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        """Handle reaction removals"""
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
            
        member = guild.get_member(payload.user_id)
        if not member:
            return
            
        # Check settings
        settings = await self.manager.get_settings(guild.id)
        if not settings.get('auto_remove', True):
            return
            
        # Get role for this emoji
        role_id = await self.manager.get_role_by_emoji(guild.id, payload.message_id, str(payload.emoji))
        if not role_id:
            return
            
        role = guild.get_role(role_id)
        if not role or role not in member.roles:
            return
            
        try:
            # Remove the role
            await member.remove_roles(role, reason="Reaction role removal")
            
            # Update member state
            member_state_manager.save_member_roles(guild.id, member.id, member.roles)
            
            # Log the removal
            await self.manager.log_role_assignment(guild.id, member.id, role.id, "remove", payload.message_id)
            
            print(f"[ENHANCED_RR] Removed role {role.name} from {member.display_name}")
            
        except discord.Forbidden:
            print(f"[ENHANCED_RR] No permission to remove role {role.name} from {member.display_name}")
        except Exception as e:
            print(f"[ENHANCED_RR] Error removing role: {e}")

async def setup(bot):
    await bot.add_cog(EnhancedReactionRoleCommands(bot))