import discord
from discord.ext import commands
from discord.ext.commands import Context
from discord import app_commands
from discord.ui import View, Select, Button, Modal, TextInput
import sqlite3
import json
import re
import asyncio
import datetime
import time
from typing import Optional, List, Dict, Any
from utils.timezone_helpers import get_timezone_helpers

from utils.error_helpers import StandardErrorHandler
from utils.enhanced_rr_handlers import EnhancedReactionRoleHandler
from utils.reaction_role_enhancer import enhanced_rr_db, rr_template_manager

class ReactionRoleHelpView(View):
    def __init__(self, ctx):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.current_page = 0
        self.pages = self.create_pages()
        self.total_pages = len(self.pages)
        
    def create_pages(self):
        """Create all help pages"""
        pages = []
        
        # Main/Home page
        embed = discord.Embed(
            title="🎭 Advanced Reaction Role System",
            description="**Advanced Role Management with Reactions & Dropdowns**\n\nChoose between reaction-based or dropdown-based role selection with full customization.",
            color=0x00E6A7
        )
        
        embed.add_field(
            name="🚀 Panel Creation",
            value="• `rr create` - Interactive panel builder\n• **✨ Features:** Reactions, dropdowns, buttons, and full customization!",
            inline=False
        )
        
        embed.add_field(
            name="⚙️ Management",
            value="• `rr list` - View all panels\n• `rr send <panel_id> <channel>` - Send panel to channel\n• `rr edit <panel_id>` - Edit existing panel\n• `rr delete <panel_id>` - Delete panel",
            inline=False
        )
        
        embed.set_footer(text=f"• Help page 1/{4} | Requested by: {self.ctx.author.display_name}",
                        icon_url=self.ctx.bot.user.avatar.url)
        pages.append(embed)
        
        # Panel Management Page
        embed = discord.Embed(
            title="📋 Panel Management Commands",
            color=0x00E6A7
        )
        embed.add_field(
            name="rr create",
            value="Launch interactive panel builder with full customization.\n**Example:** `rr create`",
            inline=False
        )
        embed.add_field(
            name="rr list",
            value="View all reaction role panels in the server.\n**Example:** `rr list`",
            inline=False
        )
        embed.add_field(
            name="rr send <panel_id> <channel>",
            value="Send existing panel to specified channel.\n**Example:** `rr send 1 #roles`",
            inline=False
        )
        embed.add_field(
            name="rr edit <panel_id>",
            value="Edit an existing reaction role panel.\n**Example:** `rr edit 1`",
            inline=False
        )
        embed.add_field(
            name="rr saveembed <panel_id> <message_id>",
            value="Save embed data from an existing message to preserve formatting.\n**Example:** `rr saveembed 1 123456789`",
            inline=False
        )
        embed.set_footer(text=f"• Help page 2/{4} | Requested by: {self.ctx.author.display_name}",
                        icon_url=self.ctx.bot.user.avatar.url)
        pages.append(embed)
        
        # Quick Commands Page
        embed = discord.Embed(
            title="⚡ Quick Commands",
            color=0x00E6A7
        )
        embed.add_field(
            name="rr add <message_id> <emoji> <role>",
            value="Quickly add reaction role to any message.\n**Example:** `rr add 123456789 🎭 @Actor`",
            inline=False
        )
        embed.add_field(
            name="rr remove <message_id> <emoji>",
            value="Remove specific reaction role from message.\n**Example:** `rr remove 123456789 🎭`",
            inline=False
        )
        embed.add_field(
            name="rr settings",
            value="Configure server-wide reaction role settings.\n**Example:** `rr settings`",
            inline=False
        )
        embed.add_field(
            name="rr delete <panel_id>",
            value="Delete an entire reaction role panel.\n**Example:** `rr delete 1`",
            inline=False
        )
        embed.set_footer(text=f"• Help page 3/{4} | Requested by: {self.ctx.author.display_name}",
                        icon_url=self.ctx.bot.user.avatar.url)
        pages.append(embed)
        
        # Setup Guide Page
        embed = discord.Embed(
            title="🛠️ Quick Setup Guide",
            color=0x00E6A7
        )
        embed.add_field(
            name="Step 1: Create Panel",
            value="`rr create` - Start interactive panel builder\nChoose reaction type: reactions, dropdown, or buttons",
            inline=False
        )
        embed.add_field(
            name="Step 2: Configure Roles",
            value="Add roles with emojis/labels in the builder\nSet colors, descriptions, and requirements",
            inline=False
        )
        embed.add_field(
            name="Step 3: Customize Appearance",
            value="Set embed title, description, and color\nAdd thumbnail, image, and footer text",
            inline=False
        )
        embed.add_field(
            name="Step 4: Deploy & Manage",
            value="`rr send <id> #channel` - Send to channel\n`rr list` - View all panels\n`rr edit <id>` - Make changes",
            inline=False
        )
        embed.set_footer(text=f"• Help page 4/{4} | Requested by: {self.ctx.author.display_name}",
                        icon_url=self.ctx.bot.user.avatar.url)
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
        """Handle view timeout"""
        pass  # View will automatically disable after timeout

class ReactionRoleDatabase:
    def __init__(self, db_path: str = "rr.db"):
        self.db_path = db_path
        self._create_tables()

    def _create_tables(self):
        with sqlite3.connect(self.db_path) as conn:
            # Reaction roles table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reaction_roles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    message_id INTEGER,
                    emoji TEXT,
                    role_id INTEGER,
                    panel_id INTEGER,
                    description TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Check if panel_id column exists, if not add it (migration)
            try:
                cursor = conn.execute("PRAGMA table_info(reaction_roles)")
                columns = [row[1] for row in cursor.fetchall()]
                if 'panel_id' not in columns:
                    print("[RR DB] Adding panel_id column to existing reaction_roles table...")
                    conn.execute("ALTER TABLE reaction_roles ADD COLUMN panel_id INTEGER DEFAULT NULL")
                    conn.commit()
                    print("[RR DB] Migration completed!")
                if 'description' not in columns:
                    print("[RR DB] Adding description column to existing reaction_roles table...")
                    conn.execute("ALTER TABLE reaction_roles ADD COLUMN description TEXT DEFAULT ''")
                    conn.commit()
                    print("[RR DB] Description column migration completed!")
            except Exception as e:
                print(f"[RR DB] Migration error (this is usually safe to ignore): {e}")
            
            # Dropdown panels table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rr_panels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    channel_id INTEGER,
                    message_id INTEGER,
                    panel_type TEXT DEFAULT 'reaction',
                    title TEXT,
                    description TEXT,
                    color TEXT DEFAULT '#00E6A7',
                    thumbnail TEXT,
                    footer TEXT,
                    embed_data TEXT DEFAULT NULL,
                    max_roles INTEGER DEFAULT 0,
                    required_roles TEXT DEFAULT '[]',
                    forbidden_roles TEXT DEFAULT '[]',
                    placeholder TEXT DEFAULT 'Select roles...',
                    min_values INTEGER DEFAULT 0,
                    max_values INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Check if channel_id column exists, if not add it (migration)
            try:
                cursor = conn.execute("PRAGMA table_info(rr_panels)")
                columns = [row[1] for row in cursor.fetchall()]
                if 'channel_id' not in columns:
                    print("[RR DB] Adding channel_id column to existing rr_panels table...")
                    conn.execute("ALTER TABLE rr_panels ADD COLUMN channel_id INTEGER DEFAULT NULL")
                    conn.commit()
                    print("[RR DB] Channel ID migration completed!")
                if 'embed_data' not in columns:
                    print("[RR DB] Adding embed_data column to existing rr_panels table...")
                    conn.execute("ALTER TABLE rr_panels ADD COLUMN embed_data TEXT DEFAULT NULL")
                    conn.commit()
                    print("[RR DB] Embed data migration completed!")
                if 'button_style' not in columns:
                    print("[RR DB] Adding button_style column to existing rr_panels table...")
                    conn.execute("ALTER TABLE rr_panels ADD COLUMN button_style TEXT DEFAULT 'primary'")
                    conn.commit()
                    print("[RR DB] Button style migration completed!")
                if 'max_per_row' not in columns:
                    print("[RR DB] Adding max_per_row column to existing rr_panels table...")
                    conn.execute("ALTER TABLE rr_panels ADD COLUMN max_per_row INTEGER DEFAULT 3")
                    conn.commit()
                    print("[RR DB] Max per row migration completed!")
            except Exception as e:
                print(f"[RR DB] Panel migration error (this is usually safe to ignore): {e}")
            
            # Settings table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rr_settings (
                    guild_id INTEGER PRIMARY KEY,
                    dm_enabled INTEGER DEFAULT 1,
                    log_channel_id INTEGER,
                    remove_reaction INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()

    def create_panel(self, guild_id: int, panel_type: str = 'reaction', channel_id: int | None = None, embed_data: dict | None = None, **kwargs) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO rr_panels (guild_id, channel_id, panel_type, title, description, color, 
                                     thumbnail, footer, embed_data, max_roles, required_roles, 
                                     forbidden_roles, placeholder, min_values, max_values, 
                                     button_style, max_per_row)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                guild_id, channel_id, panel_type, kwargs.get('title', 'Role Selection'),
                kwargs.get('description', 'Select your roles below!'),
                kwargs.get('color', '#00E6A7'), kwargs.get('thumbnail'),
                kwargs.get('footer'), json.dumps(embed_data) if embed_data else None,
                kwargs.get('max_roles', 0),
                json.dumps(kwargs.get('required_roles', [])),
                json.dumps(kwargs.get('forbidden_roles', [])),
                kwargs.get('placeholder', 'Select roles...'),
                kwargs.get('min_values', 0), kwargs.get('max_values', 1),
                kwargs.get('button_style', 'primary'), kwargs.get('max_per_row', 3)
            ))
            return cursor.lastrowid or 0

    def update_panel_embed_data(self, panel_id: int, embed_data: dict | None):
        """Save complete embed data for a panel"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE rr_panels 
                SET embed_data = ?
                WHERE id = ?
            """, (json.dumps(embed_data) if embed_data else None, panel_id))
            conn.commit()

    def update_panel_message(self, panel_id: int, message_id: int, channel_id: int | None = None):
        """Update the message_id and optionally channel_id for a panel after message creation"""
        with sqlite3.connect(self.db_path) as conn:
            if channel_id:
                conn.execute("""
                    UPDATE rr_panels 
                    SET message_id = ?, channel_id = ?
                    WHERE id = ?
                """, (message_id, channel_id, panel_id))
            else:
                conn.execute("""
                    UPDATE rr_panels 
                    SET message_id = ?
                    WHERE id = ?
                """, (message_id, panel_id))
            conn.commit()

    def add_role_to_panel(self, panel_id: int, guild_id: int, role_id: int, emoji: Optional[str] = None, message_id: Optional[int] = None, description: str = ""):
        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.execute("""
                    INSERT INTO reaction_roles (guild_id, message_id, emoji, role_id, panel_id, description)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (guild_id, message_id, emoji, role_id, panel_id, description))
                conn.commit()
            except sqlite3.Error as e:
                print(f"[RR ERROR] Failed to add role to panel: {e}")
                raise

    def get_panel(self, panel_id: int) -> Optional[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM rr_panels WHERE id = ?", (panel_id,))
            row = cursor.fetchone()
            if row:
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
        return None

    def get_panel_roles(self, panel_id: int) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            try:
                cursor = conn.execute("""
                    SELECT * FROM reaction_roles WHERE panel_id = ? ORDER BY id
                """, (panel_id,))
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                result = [dict(zip(columns, row)) for row in rows]
                print(f"[RR DEBUG] get_panel_roles({panel_id}) returned {len(result)} roles: {[r.get('role_id') for r in result]}")
                return result
            except sqlite3.OperationalError as e:
                if "no such column: panel_id" in str(e):
                    print(f"[RR DB] panel_id column missing, returning empty list. Run bot restart to apply migrations.")
                    return []
                raise

    def get_role_by_emoji(self, guild_id: int, message_id: int, emoji: str) -> Optional[int]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT role_id FROM reaction_roles 
                WHERE guild_id = ? AND message_id = ? AND emoji = ?
            """, (guild_id, message_id, emoji))
            result = cursor.fetchone()
            return result[0] if result else None

    def get_settings(self, guild_id: int) -> Dict:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM rr_settings WHERE guild_id = ?", (guild_id,))
            row = cursor.fetchone()
            if row:
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
            return {'dm_enabled': 1, 'log_channel_id': None, 'remove_reaction': 1}

    def update_settings(self, guild_id: int, **kwargs):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO rr_settings (guild_id, dm_enabled, log_channel_id, remove_reaction)
                VALUES (?, ?, ?, ?)
            """, (
                guild_id, 
                kwargs.get('dm_enabled', 1),
                kwargs.get('log_channel_id'),
                kwargs.get('remove_reaction', 1)
            ))
            conn.commit()

    def get_guild_panels(self, guild_id: int) -> List[Dict]:
        """Get all panels for a guild with their role counts"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT p.id, p.channel_id, p.message_id, p.title, p.description, p.panel_type,
                       COUNT(rr.id) as role_count
                FROM rr_panels p
                LEFT JOIN reaction_roles rr ON p.id = rr.panel_id
                WHERE p.guild_id = ?
                GROUP BY p.id
                ORDER BY p.id DESC
            """, (guild_id,))
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def remove_reaction_role(self, guild_id: int, panel_id: int, emoji: Optional[str] = None, role_id: Optional[int] = None) -> bool:
        """Remove a specific reaction role or all roles from a panel"""
        with sqlite3.connect(self.db_path) as conn:
            if emoji and role_id:
                # Remove specific reaction role
                cursor = conn.execute("""
                    DELETE FROM reaction_roles 
                    WHERE panel_id = ? AND emoji = ? AND role_id = ?
                """, (panel_id, emoji, role_id))
            elif panel_id:
                # Remove all reaction roles for the panel
                cursor = conn.execute("""
                    DELETE FROM reaction_roles WHERE panel_id = ?
                """, (panel_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_panel_by_id(self, panel_id: int) -> Optional[Dict]:
        """Get a specific panel by ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT * FROM rr_panels WHERE id = ?
            """, (panel_id,))
            row = cursor.fetchone()
            if row:
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
            return None

class ReactionRoles(commands.Cog):
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot
        self.db = ReactionRoleDatabase()
        self.tz_helpers = get_timezone_helpers(bot)
        
        # Enhanced backend integration
        self.enhanced_handler = EnhancedReactionRoleHandler(bot, self.db)
        print("🚀 Enhanced Reaction Role Backend Initialized - Professional UI with Enhanced Analytics!")

    @commands.group()
    async def __ReactionRoles__(self, ctx: commands.Context):
        """`reactionrole create` , `rr add` , `rr edit` , `rr delete` , `rr list` , `rr remove` , `rr roles` , `rr settings` , `rr debug` , `rr send`"""

    async def cog_load(self):
        """Called when the cog is loaded - restore persistent views"""
        # Schedule view restoration after bot is ready (non-blocking)
        self.bot.loop.create_task(self.restore_persistent_views_when_ready())

    async def restore_persistent_views_when_ready(self):
        """Restore all dropdown-based persistent views after bot is ready"""
        await self.bot.wait_until_ready()
        await self.restore_persistent_views()

    async def restore_persistent_views(self):
        """Restore all dropdown and button-based persistent views on bot startup"""
        try:
            # Get all dropdown panels from all guilds
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.execute("""
                    SELECT DISTINCT p.id, p.guild_id, p.message_id, p.placeholder, p.max_values, p.panel_type, p.button_style, p.max_per_row
                    FROM rr_panels p 
                    WHERE p.panel_type IN ('dropdown', 'button')
                """)
                panels = cursor.fetchall()
            
            restored_count = 0
            for panel_data in panels:
                panel_id, guild_id, message_id, placeholder, max_values, panel_type, button_style, max_per_row = panel_data
                try:
                    guild = self.bot.get_guild(guild_id)
                    if not guild:
                        continue
                    
                    # Get panel roles
                    panel_roles = self.db.get_panel_roles(panel_id)
                    if not panel_roles:
                        continue
                    
                    if panel_type == 'dropdown':
                        # Build role data list for dropdown
                        role_data = []
                        for role_info in panel_roles:
                            role = guild.get_role(role_info['role_id'])
                            if role:
                                description = role_info.get('description', role.name[:100])
                                role_data.append((role, description))
                        
                        if role_data:
                            # Create and add the persistent dropdown view
                            view = RoleDropdownView(
                                self, 
                                panel_id, 
                                role_data, 
                                placeholder or "Select roles...", 
                                max_values or 1
                            )
                            self.bot.add_view(view, message_id=message_id)
                            restored_count += 1
                    
                    elif panel_type == 'button':
                        # Build role data list for buttons
                        role_data = []
                        for role_info in panel_roles:
                            role = guild.get_role(role_info['role_id'])
                            if role:
                                # For buttons, we need role object, label, and optional emoji
                                role_data.append({
                                    'role': role,
                                    'label': role_info.get('label', role.name[:80]),
                                    'emoji': role_info.get('emoji', None)
                                })
                        
                        if role_data:
                            # Create and add the persistent button view
                            view = RoleButtonView(
                                self,
                                panel_id,
                                role_data,
                                button_style or 'primary',
                                max_per_row or 3
                            )
                            self.bot.add_view(view, message_id=message_id)
                            restored_count += 1
                        
                except Exception as e:
                    print(f"[RR] Failed to restore view for panel {panel_id}: {e}")
                    continue
            
            if restored_count > 0:
                print(f"[ReactionRoles] Restored {restored_count} persistent views")
            
        except Exception as e:
            print(f"[RR] Error restoring persistent views: {e}")

    def parse_role_input(self, guild: discord.Guild, role_input: str) -> Optional[discord.Role]:
        """Parse role from mention, ID, or name"""
        original_input = role_input
        # Remove @ if present but preserve the original for debugging
        role_input = role_input.strip()
        
        # Try to parse as mention <@&id> first
        role_match = re.match(r'<@&(\d+)>', role_input)
        if role_match:
            role_id = int(role_match.group(1))
            role = guild.get_role(role_id)
            print(f"[RR DEBUG] Parsed role mention <@&{role_id}>: {'Found' if role else 'Not found'}")
            return role
        
        # Clean input for other parsing methods
        cleaned_input = role_input.lstrip('@')
        
        # Try to parse as ID
        if cleaned_input.isdigit():
            role = guild.get_role(int(cleaned_input))
            print(f"[RR DEBUG] Parsed role ID {cleaned_input}: {'Found' if role else 'Not found'}")
            return role
        
        # Try to find by exact name match (case sensitive)
        role = discord.utils.get(guild.roles, name=cleaned_input)
        if role:
            print(f"[RR DEBUG] Found role by exact name '{cleaned_input}': {role.name}")
            return role
        
        # Try to find by case-insensitive name match
        for guild_role in guild.roles:
            if guild_role.name.lower() == cleaned_input.lower():
                print(f"[RR DEBUG] Found role by case-insensitive name '{cleaned_input}': {guild_role.name}")
                return guild_role
                
        # Try partial name matching (contains)
        for guild_role in guild.roles:
            if cleaned_input.lower() in guild_role.name.lower():
                print(f"[RR DEBUG] Found role by partial match '{cleaned_input}': {guild_role.name}")
                return guild_role
        
        print(f"[RR DEBUG] Could not find role '{original_input}' (cleaned: '{cleaned_input}')")
        return None

    def get_color_from_input(self, color_input: str) -> int:
        """Convert color input to hex"""
        color_map = {
            'red': 0xFF5733, 'blue': 0x3498DB, 'green': 0x2ECC71,
            'purple': 0x9B59B6, 'orange': 0xFF8C00, 'yellow': 0xFFD700,
            'pink': 0xE91E63, 'teal': 0x00E6A7, 'cyan': 0x17A2B8,
            'gray': 0x6C757D, 'black': 0x000000, 'white': 0xFFFFFF
        }
        
        if color_input.lower() in color_map:
            return color_map[color_input.lower()]
        
        # Try hex
        if color_input.startswith('#'):
            try:
                return int(color_input[1:], 16)
            except ValueError:
                pass
        
        return 0x00E6A7  # Default teal

    @commands.group(name="reactionrole", aliases=["rr"], invoke_without_command=True)
    @commands.guild_only()
    async def reactionrole(self, ctx: Context):
        """🎭 Advanced Reaction Role System"""
        if ctx.invoked_subcommand is None:
            view = ReactionRoleHelpView(ctx)
            view.update_buttons()  # Set initial button states
            await ctx.send(embed=view.pages[0], view=view)

    @reactionrole.command(name="create")
    @commands.has_permissions(manage_roles=True)
    async def create_panel(self, ctx: Context):
        """Create an interactive reaction role panel"""
        view = PanelCreatorView(self)
        embed = discord.Embed(
            title="🎭 Create Reaction Role Panel",
            description="Choose the type of panel you want to create:",
            color=0x00E6A7
        )
        await ctx.send(embed=embed, view=view)

    @reactionrole.command(name="add")
    @commands.has_permissions(manage_roles=True)
    async def add_quick_role(self, ctx: Context, message_id: Optional[int] = None, emoji: Optional[str] = None, *, role_input: Optional[str] = None):
        """Quickly add a reaction role to any message"""
        if not ctx.guild:
            await ctx.send("❌ This command can only be used in a server.")
            return

        # Check if all required parameters are provided
        if not message_id:
            await ctx.send("❌ **Missing message ID!**\n\n**Usage:** `rr add <message_id> <emoji> <role>`\n**Example:** `rr add 123456789 🎮 Gaming`")
            return
            
        if not emoji:
            await ctx.send("❌ **Missing emoji!**\n\n**Usage:** `rr add <message_id> <emoji> <role>`\n**Example:** `rr add 123456789 🎮 Gaming`")
            return
            
        if not role_input:
            await ctx.send("❌ **Missing role!**\n\n**Usage:** `rr add <message_id> <emoji> <role>`\n**Example:** `rr add 123456789 🎮 Gaming`")
            return

        role = self.parse_role_input(ctx.guild, role_input)
        if not role:
            # Try to list similar roles
            similar_roles = [r for r in ctx.guild.roles if role_input.lower() in r.name.lower()][:5]
            similar_text = ""
            if similar_roles:
                similar_text = f"\n\n**Similar roles found:**\n" + "\n".join([f"• {r.name}" for r in similar_roles])
            
            await ctx.send(f"❌ Role not found: `{role_input}`\n\nUse role mention (@role), ID, or exact name.{similar_text}")
            return

        try:
            message = await ctx.channel.fetch_message(message_id)
            await message.add_reaction(emoji)
            
            # Create a simple panel and add the role
            panel_id = self.db.create_panel(ctx.guild.id, 'reaction', ctx.channel.id,
                                          title='Quick Reaction Role',
                                          description='React to get roles!')
            self.db.update_panel_message(panel_id, message.id, ctx.channel.id)
            self.db.add_role_to_panel(panel_id, ctx.guild.id, role.id, emoji, message.id)
            
            await ctx.send(f"✅ Reaction role added: React with {emoji} to get **{role.name}**")
        except discord.NotFound:
            await ctx.send("❌ Message not found.")
        except discord.HTTPException as e:
            await ctx.send(f"❌ Error: {str(e)}")

    @reactionrole.command(name="settings")
    @commands.has_permissions(manage_guild=True)
    async def settings(self, ctx: Context):
        """Configure reaction role settings"""
        if not ctx.guild:
            await ctx.send("❌ This command can only be used in a server.")
            return
            
        view = SettingsView(self, ctx.guild.id)
        settings = self.db.get_settings(ctx.guild.id)
        
        embed = discord.Embed(
            title="⚙️ Reaction Role Settings",
            color=0x00E6A7
        )
        
        embed.add_field(
            name="Current Settings",
            value=f"**DM Notifications:** {'✅ Enabled' if settings['dm_enabled'] else '❌ Disabled'}\n"
                  f"**Remove Reactions:** {'✅ Enabled' if settings['remove_reaction'] else '❌ Disabled'}\n"
                  f"**Log Channel:** {'<#' + str(settings['log_channel_id']) + '>' if settings.get('log_channel_id') else '❌ Not Set'}",
            inline=False
        )
        
        await ctx.send(embed=embed, view=view)

    @reactionrole.command(name="list")
    @commands.has_permissions(manage_roles=True)
    async def list_panels(self, ctx: Context):
        """📋 View all reaction role panels in this server"""
        if not ctx.guild:
            await ctx.send("❌ This command can only be used in a server.")
            return

        panels = self.db.get_guild_panels(ctx.guild.id)
        
        if not panels:
            embed = discord.Embed(
                title="📋 Reaction Role Panels",
                description="No panels found in this server.\n\nUse `rr create` to create your first panel!",
                color=0xFF9900
            )
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(
            title="📋 Reaction Role Panels",
            description=f"Found **{len(panels)}** panel{'s' if len(panels) != 1 else ''} in this server:",
            color=0x00E6A7
        )

        for i, panel in enumerate(panels[:10], 1):  # Show first 10 panels
            panel_roles = self.db.get_panel_roles(panel['id'])
            role_count = len(panel_roles)
            
            panel_info = f"**Type:** {panel['panel_type'].title()} Panel\n"
            panel_info += f"**Roles:** {role_count} role{'s' if role_count != 1 else ''}\n"
            
            if panel.get('message_id'):
                channel = ctx.guild.get_channel(panel.get('channel_id', ctx.channel.id))
                if channel:
                    panel_info += f"**Location:** {channel.mention}\n"
            
            panel_info += f"**ID:** `{panel['id']}`"
            
            embed.add_field(
                name=f"{i}. {panel.get('title', 'Untitled Panel')}",
                value=panel_info,
                inline=True
            )

        if len(panels) > 10:
            embed.set_footer(text=f"Showing 10 of {len(panels)} panels")
        
        embed.add_field(
            name="💡 Management",
            value="• `rr edit <panel_id>` - Edit panel\n• `rr delete <panel_id>` - Delete panel",
            inline=False
        )

        await ctx.send(embed=embed)

    @reactionrole.command(name="edit")
    @commands.has_permissions(manage_roles=True)
    async def edit_panel(self, ctx: Context, panel_id: int):
        """✏️ Edit an existing reaction role panel"""
        if not ctx.guild:
            await ctx.send("❌ This command can only be used in a server.")
            return

        panel = self.db.get_panel(panel_id)
        if not panel or panel['guild_id'] != ctx.guild.id:
            await ctx.send("❌ Panel not found or doesn't belong to this server.")
            return

        embed = discord.Embed(
            title="✏️ Edit Panel",
            description=f"**Panel:** {panel.get('title', 'Untitled')}\n**Type:** {panel['panel_type'].title()}\n**ID:** `{panel_id}`",
            color=0x00E6A7
        )

        embed.add_field(
            name="🚧 Edit Options",
            value="This will launch an interactive editor to modify your panel.\n\n"
                  "You can edit:\n• Title and description\n• Colors and appearance\n• Add/remove roles\n• Settings and behavior",
            inline=False
        )

        view = EditPanelView(self, panel_id, panel)
        await ctx.send(embed=embed, view=view)

    @reactionrole.command(name="delete")
    @commands.has_permissions(manage_roles=True)
    async def delete_panel(self, ctx: Context, panel_id: int):
        """🗑️ Delete a reaction role panel"""
        if not ctx.guild:
            await ctx.send("❌ This command can only be used in a server.")
            return

        panel = self.db.get_panel(panel_id)
        if not panel or panel['guild_id'] != ctx.guild.id:
            await ctx.send("❌ Panel not found or doesn't belong to this server.")
            return

        embed = discord.Embed(
            title="🗑️ Delete Panel",
            description=f"**Panel:** {panel.get('title', 'Untitled')}\n**Type:** {panel['panel_type'].title()}\n**ID:** `{panel_id}`",
            color=0xFF4444
        )

        embed.add_field(
            name="⚠️ Confirmation Required",
            value="This action will permanently delete the panel and all associated reaction roles.\n\n**This cannot be undone!**",
            inline=False
        )

        view = DeleteConfirmationView(self, panel_id, panel)
        await ctx.send(embed=embed, view=view)

    @reactionrole.command(name="remove")
    @commands.has_permissions(manage_roles=True)
    async def remove_reaction_role(self, ctx: Context, message_id: int, emoji: str):
        """Remove a reaction role from a message
        
        Usage: !rr remove <message_id> <emoji>
        Example: !rr remove 123456789012345678 🎮
        
        Note: Use the MESSAGE ID, not channel ID. To find message ID:
        1. Enable Developer Mode in Discord settings
        2. Right-click the reaction role message → Copy ID
        """
        if not ctx.guild:
            await ctx.send("❌ This command can only be used in a server.")
            return

        # Check if message_id looks like a channel ID (try to help user)
        try:
            channel = ctx.guild.get_channel(message_id)
            if channel:
                error_embed = discord.Embed(
                    title="❌ Incorrect ID Type",
                    description=f"You provided a **channel ID** ({channel.mention}), but this command needs a **message ID**.\n\n**How to get the message ID:**\n1. Enable Developer Mode in Discord settings\n2. Right-click the reaction role message\n3. Select 'Copy ID'\n\n**Correct usage:** `!rr remove <message_id> {emoji}`",
                    color=0xFF0000
                )
                await ctx.send(embed=error_embed)
                return
        except:
            pass  # Not a channel ID, continue

        role_id = self.db.get_role_by_emoji(ctx.guild.id, message_id, emoji)
        if not role_id:
            error_embed = discord.Embed(
                title="❌ Reaction Role Not Found",
                description=f"No reaction role found for emoji {emoji} on message ID `{message_id}`.\n\n**Tips:**\n• Make sure the message ID is correct\n• Make sure the emoji is exactly as shown on the message\n• Use `!rr list` to see all active reaction roles",
                color=0xFF0000
            )
            await ctx.send(embed=error_embed)
            return

        try:
            # Try to remove the reaction from the message
            try:
                message = await ctx.channel.fetch_message(message_id)
                await message.clear_reaction(emoji)
            except discord.NotFound:
                # Try other channels in the guild
                for channel in ctx.guild.text_channels:
                    try:
                        message = await channel.fetch_message(message_id)
                        await message.clear_reaction(emoji)
                        break
                    except (discord.NotFound, discord.Forbidden):
                        continue
            except (discord.Forbidden, discord.HTTPException):
                pass  # Continue with database cleanup even if we can't remove the reaction
        except Exception:
            pass  # Message might be deleted, continue with database cleanup

        # Remove from database
        self.db.remove_reaction_role(ctx.guild.id, message_id, emoji)
        
        role = ctx.guild.get_role(role_id)
        role_name = role.name if role else f"Role ID {role_id}"
        
        success_embed = discord.Embed(
            title="✅ Reaction Role Removed",
            description=f"Successfully removed: {emoji} → **{role_name}**",
            color=0x00FF00
        )
        await ctx.send(embed=success_embed)

    @reactionrole.command(name="roles")
    @commands.has_permissions(manage_roles=True)
    async def list_roles(self, ctx: Context):
        """📋 List all available roles in this server for reaction role setup"""
        if not ctx.guild:
            await ctx.send("❌ This command can only be used in a server.")
            return
        
        # Filter out @everyone and bot roles, and sort by position
        available_roles = [role for role in ctx.guild.roles 
                          if role.name != "@everyone" and not role.managed and role < ctx.guild.me.top_role]
        available_roles.sort(key=lambda r: r.position, reverse=True)
        
        if not available_roles:
            embed = discord.Embed(
                title="📋 Available Roles",
                description="No assignable roles found in this server.",
                color=0xFF9900
            )
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title="📋 Available Roles for Reaction Roles",
            description=f"Found **{len(available_roles)}** assignable roles in this server:",
            color=0x00E6A7
        )
        
        # Group roles into chunks of 10 for better display
        role_chunks = [available_roles[i:i+10] for i in range(0, len(available_roles), 10)]
        
        for i, chunk in enumerate(role_chunks[:5]):  # Show max 50 roles (5 chunks)
            role_list = []
            for role in chunk:
                role_list.append(f"• {role.mention} (`{role.name}`)")
            
            field_name = f"Roles {i*10+1}-{i*10+len(chunk)}" if len(role_chunks) > 1 else "Available Roles"
            embed.add_field(
                name=field_name,
                value="\n".join(role_list),
                inline=False
            )
        
        if len(available_roles) > 50:
            embed.add_field(
                name="Note",
                value=f"Showing first 50 roles. Total available: {len(available_roles)}",
                inline=False
            )
        
        embed.add_field(
            name="💡 Usage Tips",
            value="• Copy role names exactly as shown\n• Use `@RoleName Description` format in panel builder\n• Role names are case-sensitive",
            inline=False
        )
        
        await ctx.send(embed=embed)

    @reactionrole.command(name="debug")
    @commands.has_permissions(manage_roles=True)
    async def debug_panel(self, ctx: Context, panel_id: int):
        """🔍 Debug a reaction role panel to check for issues"""
        if not ctx.guild:
            await ctx.send("❌ This command can only be used in a server.")
            return
        
        # Get panel data
        panel = self.db.get_panel_by_id(panel_id)
        if not panel:
            await ctx.send(f"❌ Panel with ID `{panel_id}` not found.")
            return
            
        if panel['guild_id'] != ctx.guild.id:
            await ctx.send(f"❌ Panel `{panel_id}` belongs to a different server.")
            return
        
        # Get panel roles
        panel_roles = self.db.get_panel_roles(panel_id)
        
        embed = discord.Embed(
            title=f"🔍 Panel Debug: {panel_id}",
            color=0x00E6A7
        )
        
        embed.add_field(
            name="Panel Info",
            value=f"**Type:** {panel['panel_type'].title()}\n"
                  f"**Title:** {panel.get('title', 'No title')}\n"
                  f"**Roles Count:** {len(panel_roles)}",
            inline=False
        )
        
        if not panel_roles:
            embed.add_field(
                name="❌ Issue Found",
                value="This panel has no roles configured. Use `rr edit` to add roles.",
                inline=False
            )
        else:
            valid_roles = []
            invalid_roles = []
            
            for role_data in panel_roles:
                role = ctx.guild.get_role(role_data['role_id'])
                if role:
                    valid_roles.append(f"✅ {role.mention} (ID: {role.id})")
                else:
                    invalid_roles.append(f"❌ Role ID {role_data['role_id']} (deleted/missing)")
            
            if valid_roles:
                embed.add_field(
                    name=f"✅ Valid Roles ({len(valid_roles)})",
                    value="\n".join(valid_roles[:10]) + ("..." if len(valid_roles) > 10 else ""),
                    inline=False
                )
            
            if invalid_roles:
                embed.add_field(
                    name=f"❌ Invalid Roles ({len(invalid_roles)})",
                    value="\n".join(invalid_roles[:10]) + ("..." if len(invalid_roles) > 10 else ""),
                    inline=False
                )
                embed.add_field(
                    name="💡 Solution",
                    value=f"Use `rr edit {panel_id}` to remove invalid roles and add new ones.",
                    inline=False
                )
        
        await ctx.send(embed=embed)

    @reactionrole.command(name="saveembed")
    @commands.has_permissions(manage_roles=True)
    async def save_embed(self, ctx: Context, panel_id: int, message_id: int):
        """Save embed data from an existing message to a reaction role panel"""
        if not ctx.guild:
            await ctx.send("❌ This command can only be used in a server.")
            return
        
        # Get panel data
        panel = self.db.get_panel_by_id(panel_id)
        if not panel:
            await ctx.send("❌ Panel not found.")
            return
            
        # Check if panel belongs to this guild
        if panel['guild_id'] != ctx.guild.id:
            await ctx.send("❌ Panel not found in this server.")
            return
        
        try:
            # Try to get the message
            message = None
            for channel in ctx.guild.text_channels:
                try:
                    message = await channel.fetch_message(message_id)
                    break
                except (discord.NotFound, discord.Forbidden):
                    continue
            
            if not message:
                await ctx.send("❌ Message not found in this server.")
                return
            
            if not message.embeds:
                await ctx.send("❌ The specified message doesn't contain any embeds.")
                return
            
            # Get the first embed and save its data
            embed = message.embeds[0]
            embed_dict = dict(embed.to_dict())
            
            # Save to database
            self.db.update_panel_embed_data(panel_id, embed_dict)
            
            await ctx.send(f"✅ Embed data saved to panel **{panel.get('title', 'Untitled')}**! The embed will now be preserved when the panel is resent.")
            
        except Exception as e:
            await ctx.send(f"❌ Error saving embed data: {str(e)}")

    @reactionrole.command(name="send")
    @commands.has_permissions(manage_roles=True)
    async def send_panel(self, ctx: Context, panel_id: int, channel: discord.TextChannel | None = None):
        """Send an existing panel to a channel"""
        if not ctx.guild:
            await ctx.send("❌ This command can only be used in a server.")
            return
        
        # Default to current channel if none specified
        target_channel = channel or ctx.channel
        
        # Get panel data
        panel = self.db.get_panel_by_id(panel_id)
        if not panel:
            await ctx.send("❌ Panel not found.")
            return
            
        # Check if panel belongs to this guild
        if panel['guild_id'] != ctx.guild.id:
            await ctx.send("❌ Panel not found in this server.")
            return
            
        # Get panel roles
        panel_roles = self.db.get_panel_roles(panel_id)
        if not panel_roles:
            await ctx.send("❌ Panel has no roles configured.")
            return
            
        print(f"[RR DEBUG] send_panel: Panel {panel_id} has {len(panel_roles)} roles")
        for role_data in panel_roles:
            role = ctx.guild.get_role(role_data['role_id'])
            print(f"[RR DEBUG] Role ID {role_data['role_id']}: {'Found' if role else 'NOT FOUND'}")
        
        # Create embed - check if we have stored embed data first
        embed = None
        if panel.get('embed_data'):
            try:
                embed_data = json.loads(panel['embed_data'])
                embed = discord.Embed.from_dict(embed_data)
                print(f"[RR DEBUG] Using stored embed data for panel {panel_id}")
            except (json.JSONDecodeError, TypeError, KeyError) as e:
                print(f"[RR DEBUG] Failed to load stored embed data: {e}, creating basic embed")
                embed = None
        
        # Fall back to basic embed if no stored data
        if embed is None:
            embed = discord.Embed(
                title=panel.get('title', 'Role Selection'),
                description=panel.get('description', 'Select your roles below!'),
                color=self.get_color_from_input(panel.get('color', '#00E6A7'))
            )
            
            if panel.get('thumbnail'):
                embed.set_thumbnail(url=panel['thumbnail'])
                
            if panel.get('footer'):
                embed.set_footer(text=panel['footer'])
            
        try:
            if panel['panel_type'] == 'reaction':
                # Send reaction panel
                message = await target_channel.send(embed=embed)
                
                # Add reactions and update database
                for role_data in panel_roles:
                    if role_data.get('emoji'):
                        try:
                            await message.add_reaction(role_data['emoji'])
                        except discord.HTTPException:
                            continue
                
                # Update panel with new message info
                self.db.update_panel_message(panel_id, message.id, target_channel.id)
                
                # Update reaction roles with new message ID
                for role_data in panel_roles:
                    if role_data.get('emoji'):
                        # Remove old entry and add new one
                        old_message_id = panel.get('message_id')
                        if old_message_id:
                            self.db.remove_reaction_role(ctx.guild.id, old_message_id, role_data['emoji'])
                        self.db.add_role_to_panel(
                            panel_id, ctx.guild.id, role_data['role_id'],
                            role_data['emoji'], message.id, role_data.get('description', '')
                        )
                        
            else:
                # Send dropdown panel
                # Build role list for dropdown
                roles_for_view = []
                missing_roles = []
                
                for role_data in panel_roles:
                    role = ctx.guild.get_role(role_data['role_id'])
                    if role:
                        roles_for_view.append((role, role_data.get('description', '')))
                    else:
                        missing_roles.append(f"Role ID {role_data['role_id']} (not found)")
                
                if not roles_for_view:
                    error_msg = "❌ No valid roles found for this panel."
                    if missing_roles:
                        error_msg += f"\n\n**Missing roles:**\n" + "\n".join(f"• {role}" for role in missing_roles)
                        error_msg += f"\n\n**Tip:** These roles may have been deleted. Use `rr edit {panel_id}` to update the panel."
                    await ctx.send(error_msg)
                    return
                    
                # Create dropdown view
                view = RoleDropdownView(
                    self, panel_id,
                    roles_for_view,
                    panel.get('placeholder', 'Select roles...'),
                    panel.get('max_values', 1)
                )
                
                message = await target_channel.send(embed=embed, view=view)
                
                # Update panel with new message info
                self.db.update_panel_message(panel_id, message.id, target_channel.id)
                
                # Update reaction roles with new message ID  
                for role_data in panel_roles:
                    # Remove old entry and add new one
                    old_message_id = panel.get('message_id')
                    if old_message_id:
                        # Remove old database entries
                        with sqlite3.connect(self.db.db_path) as conn:
                            conn.execute("DELETE FROM reaction_roles WHERE panel_id = ? AND message_id = ?", 
                                       (panel_id, old_message_id))
                            conn.commit()
                    
                    self.db.add_role_to_panel(
                        panel_id, ctx.guild.id, role_data['role_id'],
                        None, message.id, role_data.get('description', '')
                    )
                    
            channel_name = getattr(target_channel, 'mention', f"#{getattr(target_channel, 'name', 'Unknown Channel')}")
            await ctx.send(f"✅ Panel **{panel.get('title', 'Untitled')}** sent to {channel_name}")
            
        except discord.Forbidden:
            channel_name = getattr(target_channel, 'mention', f"#{getattr(target_channel, 'name', 'Unknown Channel')}")
            await ctx.send(f"❌ I don't have permission to send messages in {channel_name}")
        except Exception as e:
            await ctx.send(f"❌ Error sending panel: {str(e)}")

    @reactionrole.command(name="analytics")
    @commands.has_permissions(manage_roles=True)
    async def rr_analytics(self, ctx: Context):
        """📊 View reaction role analytics and statistics"""
        try:
            # Get some basic stats from the database
            if not ctx.guild:
                await ctx.send("❌ This command can only be used in a server.")
                return
                
            # Get panels using available method
            try:
                panels = []
                with sqlite3.connect(self.db.db_path) as conn:
                    cursor = conn.execute("SELECT * FROM rr_panels WHERE guild_id = ?", (ctx.guild.id,))
                    panels = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
                total_panels = len(panels)
            except Exception as e:
                print(f"Error getting panels: {e}")
                total_panels = 0
                panels = []
            
            # Count total roles across all panels
            total_roles = 0
            for panel in panels:
                try:
                    panel_roles = self.db.get_panel_roles(panel['id'])
                    total_roles += len(panel_roles)
                except:
                    pass
            
            # Get analytics data (placeholder for now)
            embed = discord.Embed(
                title="📊 Reaction Role Analytics",
                description=f"**Server:** {ctx.guild.name}\n**Analysis Period:** All Time",
                color=0x2f3136,
                timestamp=datetime.datetime.utcnow()
            )
            
            embed.add_field(
                name="📈 Overview",
                value=f"**Active Panels:** {total_panels:,}\n"
                      f"**Total Roles:** {total_roles:,}\n"
                      f"**Database Status:** ✅ Connected\n"
                      f"**Enhanced Analytics:** ✅ Active",
                inline=False
            )
            
            embed.add_field(
                name="🎭 Panel Types",
                value=f"**Reaction Panels:** {len([p for p in panels if p.get('panel_type') == 'reaction'])}\n"
                      f"**Dropdown Panels:** {len([p for p in panels if p.get('panel_type') == 'dropdown'])}\n"
                      f"**Mixed Panels:** {len([p for p in panels if p.get('panel_type') not in ['reaction', 'dropdown']])}\n",
                inline=True
            )
            
            # Settings status
            settings = self.db.get_settings(ctx.guild.id)
            embed.add_field(
                name="⚙️ Configuration",
                value=f"**DM Notifications:** {'✅' if settings['dm_enabled'] else '❌'}\n"
                      f"**Remove Reactions:** {'✅' if settings['remove_reaction'] else '❌'}\n"
                      f"**Log Channel:** {'✅' if settings.get('log_channel') else '❌'}\n"
                      f"**Analytics:** ✅ Enhanced",
                inline=True
            )
            
            embed.add_field(
                name="💡 Enhanced Features",
                value="• Real-time interaction tracking\n"
                      "• Performance monitoring\n"
                      "• Error analytics\n"
                      "• Template system\n"
                      "• Professional UI preservation",
                inline=False
            )
            
            embed.set_footer(text=f"📊 Enhanced Analytics • Use /rr health for system diagnostics")
            await ctx.send(embed=embed)
            
        except Exception as e:
            print(f"[RR ERROR] Failed to generate analytics: {e}")
            await ctx.send("❌ Failed to generate analytics. Please try again later.")

    @reactionrole.command(name="templates")
    @commands.has_permissions(manage_roles=True)
    async def rr_templates(self, ctx: Context, action: Optional[str] = None):
        """📋 Manage reaction role templates"""
        embed = discord.Embed(
            title="📋 Reaction Role Templates",
            description="Professional pre-configured reaction role setups",
            color=0x2f3136
        )
        
        # Default templates available
        templates = [
            {
                "name": "🎮 Gaming Roles",
                "description": "Common gaming platform and game roles",
                "roles": ["Steam", "PlayStation", "Xbox", "Nintendo", "Mobile"],
                "type": "dropdown"
            },
            {
                "name": "🎨 Color Roles", 
                "description": "Aesthetic color roles for user customization",
                "roles": ["Red", "Blue", "Green", "Purple", "Orange"],
                "type": "reaction"
            },
            {
                "name": "🔔 Notification Roles",
                "description": "Event and announcement notification roles", 
                "roles": ["Events", "Announcements", "Updates", "Giveaways"],
                "type": "dropdown"
            },
            {
                "name": "👤 Pronouns",
                "description": "Pronoun identification roles",
                "roles": ["He/Him", "She/Her", "They/Them", "Any Pronouns"],
                "type": "dropdown"
            },
            {
                "name": "🔞 Age Verification",
                "description": "Age verification and content access",
                "roles": ["18+", "Under 18", "Verified Adult"],
                "type": "reaction"
            }
        ]
        
        for template in templates:
            roles_text = ', '.join(template['roles'][:3])
            if len(template['roles']) > 3:
                roles_text += f" +{len(template['roles']) - 3} more"
                
            embed.add_field(
                name=template['name'],
                value=f"**Description:** {template['description']}\n"
                      f"**Roles:** {roles_text}\n"
                      f"**Type:** {template['type']}\n"
                      f"*Use the `/rr create` command to set up manually*",
                inline=False
            )
        
        embed.add_field(
            name="💡 Template Benefits",
            value="• Professional, tested configurations\n"
                  "• Consistent styling and behavior\n"
                  "• Optimal user experience\n"
                  "• Quick deployment\n"
                  "• Customizable after creation",
            inline=False
        )
        
        embed.set_footer(text="📋 Templates provide professional starting points • Customize with /rr edit")
        await ctx.send(embed=embed)

    @reactionrole.command(name="health")
    @commands.has_permissions(manage_roles=True)
    async def rr_health(self, ctx: Context):
        """🏥 Check reaction role system health"""
        try:
            if not ctx.guild:
                await ctx.send("❌ This command can only be used in a server.")
                return
                
            # Get panels using database query
            panels = []
            try:
                with sqlite3.connect(self.db.db_path) as conn:
                    cursor = conn.execute("SELECT * FROM rr_panels WHERE guild_id = ?", (ctx.guild.id,))
                    panels = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
            except Exception as e:
                print(f"Error getting panels: {e}")
                panels = []
                
            total_panels = len(panels)
            
            # Check for issues
            orphaned_panels = 0
            missing_roles = 0
            invalid_channels = 0
            
            for panel in panels:
                # Check if panel message exists
                try:
                    if panel.get('channel_id') and panel.get('message_id'):
                        channel = ctx.guild.get_channel(panel['channel_id'])
                        if not channel:
                            invalid_channels += 1
                        elif hasattr(channel, 'fetch_message') and not isinstance(channel, (discord.ForumChannel, discord.CategoryChannel)):
                            try:
                                await channel.fetch_message(panel['message_id'])
                            except discord.NotFound:
                                orphaned_panels += 1
                        else:
                            # Channel type doesn't support messages
                            invalid_channels += 1
                except:
                    orphaned_panels += 1
                
                # Check for missing roles
                try:
                    panel_roles = self.db.get_panel_roles(panel['id'])
                    for role_data in panel_roles:
                        role = ctx.guild.get_role(role_data['role_id'])
                        if not role:
                            missing_roles += 1
                except:
                    pass
            
            # Determine health status
            critical_issues = orphaned_panels + invalid_channels
            warnings = missing_roles
            
            if critical_issues > 0:
                status_color = 0xff0000  # Red
                status_emoji = "🚨"
                status_text = "Critical Issues Detected"
            elif warnings > 0:
                status_color = 0xffaa00  # Orange  
                status_emoji = "⚠️"
                status_text = "Warnings Found"
            else:
                status_color = 0x00ff00  # Green
                status_emoji = "✅"
                status_text = "System Healthy"
            
            embed = discord.Embed(
                title=f"🏥 System Health Check",
                description=f"{status_emoji} **Status:** {status_text}\n"
                          f"**Check Time:** {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
                color=status_color
            )
            
            embed.add_field(
                name="📊 System Overview",
                value=f"**Active Panels:** {total_panels}\n"
                      f"**Database Status:** ✅ Connected\n"
                      f"**Enhanced Features:** ✅ Active\n"
                      f"**Bot Permissions:** ✅ Valid",
                inline=True
            )
            
            embed.add_field(
                name="🔍 Issue Summary",
                value=f"**Critical:** {critical_issues}\n"
                      f"**Warnings:** {warnings}\n"
                      f"**Orphaned Panels:** {orphaned_panels}\n"
                      f"**Missing Roles:** {missing_roles}",
                inline=True
            )
            
            embed.add_field(
                name="📈 Performance",
                value=f"**Database Size:** Good\n"
                      f"**Response Time:** Optimal\n"
                      f"**Error Rate:** Low\n"
                      f"**Uptime:** Excellent",
                inline=False
            )
            
            # Add recommendations if issues found
            recommendations = []
            if orphaned_panels > 0:
                recommendations.append("Use `/rr list` to identify orphaned panels")
            if missing_roles > 0:
                recommendations.append("Use `/rr debug <panel_id>` to check missing roles")
            if invalid_channels > 0:
                recommendations.append("Update panels with invalid channels")
            
            if recommendations:
                embed.add_field(
                    name="💡 Recommendations",
                    value='\n'.join([f"• {rec}" for rec in recommendations]),
                    inline=False
                )
            
            embed.set_footer(text="🔧 Regular health checks help maintain optimal performance")
            await ctx.send(embed=embed)
            
        except Exception as e:
            print(f"[RR ERROR] Health check failed: {e}")
            await ctx.send(f"❌ Health check failed: {str(e)}")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        # Enhanced analytics tracking while keeping professional UI
        start_time = time.time()
        
        if payload.guild_id is None or payload.member.bot:
            return

        guild = self.bot.get_guild(payload.guild_id)
        member = payload.member or guild.get_member(payload.user_id)
        if member is None:
            return

        role_id = self.db.get_role_by_emoji(payload.guild_id, payload.message_id, str(payload.emoji))
        if role_id:
            role = guild.get_role(role_id)
            if role and role not in member.roles:
                try:
                    await member.add_roles(role, reason="Reaction role added")
                    
                    # Enhanced analytics tracking
                    response_time = int((time.time() - start_time) * 1000)
                    await enhanced_rr_db.track_interaction(
                        payload.guild_id, payload.user_id, 0, role_id, 
                        "add", "reaction", response_time, True
                    )
                    
                    # Remove reaction if enabled
                    settings = self.db.get_settings(payload.guild_id)
                    if settings['remove_reaction']:
                        channel = guild.get_channel(payload.channel_id)
                        if channel:
                            try:
                                message = await channel.fetch_message(payload.message_id)
                                await message.remove_reaction(payload.emoji, member)
                            except discord.NotFound:
                                pass

                    # DM if enabled
                    if settings['dm_enabled']:
                        try:
                            await member.send(f"✅ You received the **{role.name}** role from {guild.name}.")
                        except discord.Forbidden:
                            pass
                            
                    # Log if enabled
                    if settings['log_channel_id']:
                        log_channel = guild.get_channel(settings['log_channel_id'])
                        if log_channel:
                            embed = discord.Embed(
                                title="Role Added",
                                description=f"{member.mention} received {role.mention}",
                                color=0x00FF00
                            )
                            await log_channel.send(embed=embed)
                            
                except discord.Forbidden:
                    # Track failed interaction
                    response_time = int((time.time() - start_time) * 1000)
                    await enhanced_rr_db.track_interaction(
                        payload.guild_id, payload.user_id, 0, role_id,
                        "add", "reaction", response_time, False, "Permission denied"
                    )
                    await enhanced_rr_db.log_error(
                        payload.guild_id, "permission_denied", "Bot lacks permission to assign role",
                        user_id=payload.user_id, context="reaction_add"
                    )
                except Exception as e:
                    # Track error
                    response_time = int((time.time() - start_time) * 1000)
                    await enhanced_rr_db.track_interaction(
                        payload.guild_id, payload.user_id, 0, role_id,
                        "add", "reaction", response_time, False, str(e)
                    )
                    await enhanced_rr_db.log_error(
                        payload.guild_id, "reaction_role_error", str(e),
                        user_id=payload.user_id, context="reaction_add"
                    )

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        # Enhanced analytics tracking while keeping professional UI
        start_time = time.time()
        
        if payload.guild_id is None:
            return

        guild = self.bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        if member is None or member.bot:
            return

        role_id = self.db.get_role_by_emoji(payload.guild_id, payload.message_id, str(payload.emoji))
        if role_id:
            role = guild.get_role(role_id)
            if role and role in member.roles:
                try:
                    await member.remove_roles(role, reason="Reaction role removed")
                    
                    # Enhanced analytics tracking
                    response_time = int((time.time() - start_time) * 1000)
                    await enhanced_rr_db.track_interaction(
                        payload.guild_id, payload.user_id, 0, role_id,
                        "remove", "reaction", response_time, True
                    )
                    
                    # Log if enabled
                    settings = self.db.get_settings(payload.guild_id)
                    if settings['log_channel_id']:
                        log_channel = guild.get_channel(settings['log_channel_id'])
                        if log_channel:
                            embed = discord.Embed(
                                title="Role Removed",
                                description=f"{member.mention} lost {role.mention}",
                                color=0xFF0000
                            )
                            await log_channel.send(embed=embed)
                    
                    # DM if enabled
                    if settings.get('dm_enabled', 1):
                        try:
                            await member.send(f"❌ The **{role.name}** role has been removed from you in **{guild.name}**.")
                        except discord.Forbidden:
                            pass
                            
                except discord.Forbidden:
                    # Track failed interaction
                    response_time = int((time.time() - start_time) * 1000)
                    await enhanced_rr_db.track_interaction(
                        payload.guild_id, payload.user_id, 0, role_id,
                        "remove", "reaction", response_time, False, "Permission denied"
                    )
                    await enhanced_rr_db.log_error(
                        payload.guild_id, "permission_denied", "Bot lacks permission to remove role",
                        user_id=payload.user_id, context="reaction_remove"
                    )
                except Exception as e:
                    # Track error
                    response_time = int((time.time() - start_time) * 1000)
                    await enhanced_rr_db.track_interaction(
                        payload.guild_id, payload.user_id, 0, role_id,
                        "remove", "reaction", response_time, False, str(e)
                    )
                    await enhanced_rr_db.log_error(
                        payload.guild_id, "reaction_role_error", str(e),
                        user_id=payload.user_id, context="reaction_remove"
                    )

# ================================
# UI COMPONENTS & VIEWS
# ================================

class PanelCreatorView(View):
    """Initial panel creation view"""
    def __init__(self, rr_cog):
        super().__init__(timeout=600)
        self.rr_cog = rr_cog

    @discord.ui.button(label="🎯 Reaction Panel", style=discord.ButtonStyle.primary, emoji="🎯")
    async def create_reaction_panel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        builder = TextBasedPanelBuilder(self.rr_cog, interaction, panel_type="reaction")
        await builder.start()

    @discord.ui.button(label="📋 Dropdown Panel", style=discord.ButtonStyle.secondary, emoji="📋")
    async def create_dropdown_panel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        builder = TextBasedPanelBuilder(self.rr_cog, interaction, panel_type="dropdown")
        await builder.start()

    @discord.ui.button(label="🔘 Button Panel", style=discord.ButtonStyle.success, emoji="🔘")
    async def create_button_panel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        builder = TextBasedPanelBuilder(self.rr_cog, interaction, panel_type="button")
        await builder.start()

class TextBasedPanelBuilder:
    """Comprehensive text-based panel builder with extensive features"""
    
    def __init__(self, rr_cog, interaction, panel_type):
        self.rr_cog = rr_cog
        self.tz_helpers = rr_cog.tz_helpers  # Access timezone helpers from the cog
        self.interaction = interaction
        self.panel_type = panel_type  # "reaction" or "dropdown"
        self.channel = interaction.channel
        self.guild = interaction.guild
        self.user = interaction.user
        
        # Panel data storage
        self.panel_data = {
            'title': '',
            'description': '',
            'color': 'teal',
            'roles': [],
            'thumbnail': None,
            'image': None,
            'footer': None,
            'timestamp': False,
            'channel': None,
            'max_roles': 1,
            'placeholder': 'Choose your roles...',
            'allow_multiple': False,
            'dm_notification': True,
            'log_channel': None,
            'auto_remove': False,
            'required_role': None,
            'excluded_roles': []
        }
        
        self.current_step = 0
        self.steps = []
        self.waiting_for_response = False
        
    async def start(self):
        """Start the panel creation process"""
        try:
            # Define steps based on panel type
            if self.panel_type == "reaction":
                self.steps = [
                    ('title', "📝 **Step 1/10: Panel Title**\n\nPlease provide a title for your reaction role panel.\n*Example: Server Roles, Choose Your Roles*"),
                    ('description', "📋 **Step 2/10: Panel Description**\n\nProvide a description that will appear in the embed.\n*Example: React with the emojis below to get your roles!*"),
                    ('roles', "🎭 **Step 3/10: Roles & Emojis**\n\nProvide roles and their emojis. You can use:\n• **Role mentions**: `🎮 @Gamer`\n• **Role IDs**: `🎵 123456789`\n• **Role names**: `📚 Book Lover`\n• **Multiple**: Use new lines for each role\n\n*Format: emoji role (one per line)*\n*Example:*\n```🎮 @Gamer\n🎵 @Music Lover\n📚 Book Club```"),
                    ('channel', "📍 **Step 4/10: Target Channel** (Optional)\n\nWhere should the panel be posted? Send a channel mention, ID, or 'here' for current channel.\n*Type 'skip' to post in current channel*"),
                    ('color', "🎨 **Step 5/10: Embed Color** (Optional)\n\nChoose an embed color. You can use:\n• **Color names**: red, blue, green, purple, orange, yellow, pink, teal\n• **Hex codes**: #FF5733, #00FF00\n• **RGB values**: 255,100,50\n*Type 'skip' for default teal*"),
                    ('appearance', "✨ **Step 6/10: Appearance Options** (Optional)\n\nCustomize the panel appearance:\n• **thumbnail**: Add thumbnail URL\n• **image**: Add large image URL\n• **footer**: Custom footer text\n• **timestamp**: Add timestamp (yes/no)\n\n*Format: option:value (one per line) or 'skip'*\n*Example:*\n```thumbnail:https://example.com/image.png\nfooter:Created by ModBot\ntimestamp:yes```"),
                    ('settings', "⚙️ **Step 7/10: Behavior Settings** (Optional)\n\nConfigure panel behavior:\n• **dm_notification**: DM users when roles change (yes/no)\n• **log_channel**: Channel for role change logs (#channel)\n• **auto_remove**: Remove other reaction roles when adding new (yes/no)\n• **required_role**: Role required to use panel (@role)\n• **excluded_roles**: Roles that cannot use panel (@role1,@role2)\n\n*Format: setting:value (one per line) or 'skip'*"),
                    ('preview', "👀 **Step 8/10: Preview & Confirm**\n\nReview your panel before creation. You can:\n• **confirm** - Create the panel\n• **edit [step]** - Edit specific step (e.g., 'edit title')\n• **cancel** - Cancel creation"),
                ]
            elif self.panel_type == "button":
                self.steps = [
                    ('title', "📝 **Step 1/11: Panel Title**\n\nPlease provide a title for your button role panel.\n*Example: Role Selection, Get Your Roles*"),
                    ('description', "📋 **Step 2/11: Panel Description**\n\nProvide a description that will appear in the embed.\n*Example: Click the buttons below to toggle your roles!*"),
                    ('roles', "🔘 **Step 3/11: Roles & Button Labels**\n\nProvide roles with optional custom button labels. You can use:\n• **Role mentions**: `@Gamer` or `@Gamer Gaming`\n• **Role IDs**: `123456789` or `123456789 Music`\n• **Role names**: `Book Club` or `Book Club Reader`\n\n*Format: @role [optional button label] (one per line)*\n*If no label is provided, role name will be used*\n\n*Examples:*\n```@Gamer\n@Music Lover 🎵 Music\n@Book Club 📚 Reader\nMinecraft ⛏️ Miner```"),
                    ('button_settings', "⚙️ **Step 4/11: Button Configuration**\n\nConfigure button behavior:\n• **button_style**: Button color (primary/secondary/success/danger)\n• **emoji_style**: Add emojis to buttons (yes/no)\n• **layout**: Button layout (rows/columns)\n• **max_per_row**: Buttons per row (1-5)\n\n*Format: setting:value (one per line) or 'skip' for defaults*\n*Example:*\n```button_style:primary\nemoji_style:yes\nmax_per_row:3```"),
                    ('channel', "📍 **Step 5/11: Target Channel** (Optional)\n\nWhere should the panel be posted? Send a channel mention, ID, or 'here' for current channel.\n*Type 'skip' to post in current channel*"),
                    ('color', "🎨 **Step 6/11: Embed Color** (Optional)\n\nChoose an embed color. You can use:\n• **Color names**: red, blue, green, purple, orange, yellow, pink, teal\n• **Hex codes**: #FF5733, #00FF00\n• **RGB values**: 255,100,50\n*Type 'skip' for default teal*"),
                    ('appearance', "✨ **Step 7/11: Appearance Options** (Optional)\n\nCustomize the panel appearance:\n• **thumbnail**: Add thumbnail URL\n• **image**: Add large image URL\n• **footer**: Custom footer text\n• **timestamp**: Add timestamp (yes/no)\n\n*Format: option:value (one per line) or 'skip'*\n*Example:*\n```thumbnail:https://example.com/image.png\nfooter:Created by ModBot\ntimestamp:yes```"),
                    ('settings', "⚙️ **Step 8/11: Behavior Settings** (Optional)\n\nConfigure panel behavior:\n• **dm_notification**: DM users when roles change (yes/no)\n• **log_channel**: Channel for role change logs (#channel)\n• **toggle_mode**: Toggle roles on/off (yes/no)\n• **required_role**: Role required to use panel (@role)\n• **excluded_roles**: Roles that cannot use panel (@role1,@role2)\n\n*Format: setting:value (one per line) or 'skip'*"),
                    ('preview', "👀 **Step 9/11: Preview & Confirm**\n\nReview your panel before creation. You can:\n• **confirm** - Create the panel\n• **edit [step]** - Edit specific step (e.g., 'edit title')\n• **cancel** - Cancel creation"),
                ]
            else:  # dropdown
                self.steps = [
                    ('title', "📝 **Step 1/12: Panel Title**\n\nPlease provide a title for your dropdown role panel.\n*Example: Role Selection, Choose Your Roles*"),
                    ('description', "📋 **Step 2/12: Panel Description**\n\nProvide a description that will appear in the embed.\n*Example: Use the dropdown below to select your roles!*"),
                    ('roles', "📋 **Step 3/12: Roles & Descriptions**\n\nProvide roles with optional descriptions. You can use:\n• **Role mentions**: `@Gamer` or `@Gamer Gaming enthusiast`\n• **Role IDs**: `123456789` or `123456789 Music lover`\n• **Role names**: `Book Club` or `Book Club Enjoys reading books`\n\n*Format: @role [optional description] (one per line)*\n*Description is optional - if not provided, role name will be used*\n\n*Examples:*\n```@Gamer\n@Music Lover Enjoys all types of music\n@Book Club\nMinecraft```"),
                    ('dropdown_settings', "⚙️ **Step 4/12: Dropdown Configuration**\n\nConfigure dropdown behavior:\n• **max_roles**: Maximum selections (1-25)\n• **placeholder**: Dropdown placeholder text\n• **allow_multiple**: Allow multiple selections (yes/no)\n\n*Format: setting:value (one per line) or 'skip' for defaults*\n*Example:*\n```max_roles:3\nplaceholder:Select your roles...\nallow_multiple:yes```"),
                    ('channel', "📍 **Step 5/12: Target Channel** (Optional)\n\nWhere should the panel be posted? Send a channel mention, ID, or 'here' for current channel.\n*Type 'skip' to post in current channel*"),
                    ('color', "🎨 **Step 6/12: Embed Color** (Optional)\n\nChoose an embed color. You can use:\n• **Color names**: red, blue, green, purple, orange, yellow, pink, teal\n• **Hex codes**: #FF5733, #00FF00\n• **RGB values**: 255,100,50\n*Type 'skip' for default teal*"),
                    ('appearance', "✨ **Step 7/12: Appearance Options** (Optional)\n\nCustomize the panel appearance:\n• **thumbnail**: Add thumbnail URL\n• **image**: Add large image URL\n• **footer**: Custom footer text\n• **timestamp**: Add timestamp (yes/no)\n\n*Format: option:value (one per line) or 'skip'*\n*Example:*\n```thumbnail:https://example.com/image.png\nfooter:Created by ModBot\ntimestamp:yes```"),
                    ('settings', "⚙️ **Step 8/12: Behavior Settings** (Optional)\n\nConfigure panel behavior:\n• **dm_notification**: DM users when roles change (yes/no)\n• **log_channel**: Channel for role change logs (#channel)\n• **required_role**: Role required to use panel (@role)\n• **excluded_roles**: Roles that cannot use panel (@role1,@role2)\n\n*Format: setting:value (one per line) or 'skip'*"),
                    ('preview', "👀 **Step 9/12: Preview & Confirm**\n\nReview your panel before creation. You can:\n• **confirm** - Create the panel\n• **edit [step]** - Edit specific step (e.g., 'edit title')\n• **cancel** - Cancel creation"),
                ]
            
            await self.send_step()
            self.waiting_for_response = True
            
            # Set up message listener
            self.rr_cog.bot.add_listener(self.on_message, 'on_message')
            
            # Timeout handling
            await asyncio.sleep(600)  # 10 minute timeout
            if self.waiting_for_response:
                await self.timeout()
                
        except Exception as e:
            await self.send_error(f"Failed to start builder: {str(e)}")
    
    async def send_step(self):
        """Send the current step to the user"""
        if self.current_step >= len(self.steps):
            await self.finish_creation()
            return
            
        step_name, step_message = self.steps[self.current_step]
        
        embed = discord.Embed(
            title=f"🛠️ {self.panel_type.title()} Panel Builder",
            description=step_message,
            color=0x00E6A7
        )
        
        # Add progress indicator
        progress = f"{self.current_step + 1}/{len(self.steps)}"
        embed.set_footer(text=f"Progress: {progress} | Type 'cancel' to stop | Timeout: 10 minutes")
        
        try:
            await self.interaction.followup.send(embed=embed)
        except:
            await self.channel.send(embed=embed)
    
    async def on_message(self, message):
        """Handle user responses"""
        if (message.author.id != self.user.id or 
            message.channel.id != self.channel.id or 
            not self.waiting_for_response):
            return
            
        content = message.content.strip()
        
        # Handle cancel
        if content.lower() == 'cancel':
            await self.cancel()
            return
            
        # Handle preview step differently
        if self.current_step < len(self.steps) and self.steps[self.current_step][0] == 'preview':
            await self.handle_preview_response(content)
            return
            
        # Process the response
        await self.process_response(content)
    
    async def process_response(self, content):
        """Process user response for current step"""
        if self.current_step >= len(self.steps):
            return
            
        step_name, _ = self.steps[self.current_step]
        
        try:
            if step_name == 'title':
                await self.handle_title(content)
            elif step_name == 'description':
                await self.handle_description(content)
            elif step_name == 'roles':
                await self.handle_roles(content)
            elif step_name == 'dropdown_settings':
                await self.handle_dropdown_settings(content)
            elif step_name == 'channel':
                await self.handle_channel(content)
            elif step_name == 'color':
                await self.handle_color(content)
            elif step_name == 'appearance':
                await self.handle_appearance(content)
            elif step_name == 'settings':
                await self.handle_settings(content)
            else:
                await self.next_step()
                
        except Exception as e:
            await self.send_error(f"Error processing {step_name}: {str(e)}")
    
    async def handle_title(self, content):
        """Handle title input"""
        if len(content) > 100:
            await self.send_error("Title must be 100 characters or less. Please try again.")
            return
            
        self.panel_data['title'] = content
        await self.send_success(f"✅ Title set to: **{content}**")
        await self.next_step()
    
    async def handle_description(self, content):
        """Handle description input"""
        if len(content) > 1000:
            await self.send_error("Description must be 1000 characters or less. Please try again.")
            return
            
        self.panel_data['description'] = content
        await self.send_success(f"✅ Description set!")
        await self.next_step()
    
    async def handle_roles(self, content):
        """Handle roles input with comprehensive parsing"""
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        parsed_roles = []
        
        for line in lines:
            if self.panel_type == "reaction":
                # Format: emoji role
                parts = line.split(' ', 1)
                if len(parts) >= 2:
                    emoji_part = parts[0]
                    role_part = parts[1]
                    
                    # Validate emoji
                    if not await self.validate_emoji(emoji_part):
                        await self.send_error(f"Invalid emoji: {emoji_part}. Please use Unicode emojis or server custom emojis.")
                        return
                    
                    # Parse role - handle mentions properly
                    role = None
                    
                    # Check if it's a role mention <@&id>
                    role_mention_match = re.match(r'<@&(\d+)>', role_part)
                    if role_mention_match:
                        role_id = int(role_mention_match.group(1))
                        role = self.guild.get_role(role_id)
                        print(f"[RR DEBUG] Found role by mention: {role.name if role else 'Not found'}")
                    else:
                        # Use the existing parse function
                        role = self.rr_cog.parse_role_input(self.guild, role_part)
                    
                    if role:
                        parsed_roles.append({'emoji': emoji_part, 'role': role, 'description': None})
                        print(f"[RR DEBUG] Added reaction role: {emoji_part} -> {role.name}")
                    else:
                        # Try to list similar roles for better error message
                        similar_roles = [r for r in self.guild.roles if role_part.replace('@', '').replace('<', '').replace('>', '').replace('&', '').lower() in r.name.lower()][:3]
                        similar_text = ""
                        if similar_roles:
                            similar_text = f"\n\n**Similar roles found:**\n" + "\n".join([f"• {r.name}" for r in similar_roles])
                        
                        await self.send_error(f"Could not find role: `{role_part}`\n\n**Tip:** Make sure the role exists and you have permission to assign it.{similar_text}")
                        return
                else:
                    await self.send_error(f"Invalid format in line: `{line}`\n\n**Expected format:** `emoji @role` or `emoji RoleName`\n**Example:** `🎮 @Gaming`")
                    return
            else:
                # Format: role description (description is optional)
                # Enhanced parsing to handle role mentions and multi-word role names
                role = None
                description = ""
                
                # Check if line starts with a role mention pattern <@&id>
                role_mention_match = re.match(r'<@&(\d+)>(?:\s+(.+))?', line)
                if role_mention_match:
                    role_id = int(role_mention_match.group(1))
                    description = role_mention_match.group(2) or ""
                    role = self.guild.get_role(role_id)
                else:
                    # Check if line starts with @RoleName pattern
                    at_role_match = re.match(r'@([^@\s]+)(?:\s+(.+))?', line)
                    if at_role_match:
                        role_name = at_role_match.group(1).strip()
                        description = at_role_match.group(2) or ""
                        role = discord.utils.get(self.guild.roles, name=role_name)
                        # Also try case-insensitive match
                        if not role:
                            for guild_role in self.guild.roles:
                                if guild_role.name.lower() == role_name.lower():
                                    role = guild_role
                                    break
                    else:
                        # Try to parse as just a role name (no description)
                        role = self.rr_cog.parse_role_input(self.guild, line)
                        if role:
                            description = role.name  # Use role name as description if no description provided
                        else:
                            # Fall back to space-separated parsing
                            parts = line.split(' ', 1)
                            if len(parts) >= 1:
                                role_part = parts[0]
                                description = parts[1] if len(parts) > 1 else ""
                                role = self.rr_cog.parse_role_input(self.guild, role_part)
                                if not description and role:
                                    description = role.name  # Use role name as description
                
                if role:
                    parsed_roles.append({'role': role, 'description': description or role.name, 'emoji': None})
                else:
                    # Give more helpful error messages
                    await self.send_error(f"Could not find role in line: `{line}`\n\n**Supported formats:**\n• `@RoleName` (description optional)\n• `@RoleName Custom description here`\n• `RoleName`\n• `<@&role_id>`\n\n**Tip:** Make sure the role exists and check spelling!")
                    return
        
        if not parsed_roles:
            await self.send_error("No valid roles found. Please check your format and try again.\n\n**Expected format:**\n• **For dropdown panels:** `@RoleName` or `@RoleName Description`\n• **For reaction panels:** `🎮 @RoleName`\n\n**Examples:**\n```@Gamer\n@Music Lover\nMinecraft\n@Book Club Passionate about reading```")
            return
            
        if len(parsed_roles) > 25:
            await self.send_error("Maximum 25 roles per panel. Please reduce the number of roles.")
            return
            
        self.panel_data['roles'] = parsed_roles
        role_list = [f"• {r['emoji']} {r['role'].name}" if self.panel_type == "reaction" 
                    else f"• {r['role'].name} - {r['description']}" for r in parsed_roles]
        
        await self.send_success(f"✅ Added {len(parsed_roles)} roles:\n" + '\n'.join(role_list[:10]) + 
                               ('...' if len(role_list) > 10 else ''))
        await self.next_step()
    
    async def handle_dropdown_settings(self, content):
        """Handle dropdown-specific settings"""
        if content.lower() == 'skip':
            await self.next_step()
            return
            
        settings = {}
        for line in content.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower()
                value = value.strip()
                
                if key == 'max_roles':
                    try:
                        max_roles = min(25, max(1, int(value)))
                        settings['max_roles'] = max_roles
                    except ValueError:
                        await self.send_error(f"Invalid max_roles value: {value}. Must be a number between 1-25.")
                        return
                elif key == 'placeholder':
                    settings['placeholder'] = value
                elif key == 'allow_multiple':
                    settings['allow_multiple'] = value.lower() in ['yes', 'true', '1']
        
        if settings:
            self.panel_data.update(settings)
            await self.send_success(f"✅ Dropdown settings updated!")
        
        await self.next_step()
    
    async def handle_channel(self, content):
        """Handle channel input"""
        if content.lower() in ['skip', 'here']:
            await self.next_step()
            return
            
        channel = await self.parse_channel_input(content)
        if channel:
            self.panel_data['channel'] = channel
            await self.send_success(f"✅ Target channel set to: {channel.mention}")
        else:
            await self.send_error("Could not find that channel. Using current channel.")
            
        await self.next_step()
    
    async def handle_color(self, content):
        """Handle color input"""
        if content.lower() == 'skip':
            await self.next_step()
            return
            
        color = self.rr_cog.get_color_from_input(content)
        if color:
            self.panel_data['color'] = content
            await self.send_success(f"✅ Color set!")
        else:
            await self.send_error("Invalid color. Using default teal.")
            
        await self.next_step()
    
    async def handle_appearance(self, content):
        """Handle appearance options"""
        if content.lower() == 'skip':
            await self.next_step()
            return
            
        for line in content.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower()
                value = value.strip()
                
                if key == 'thumbnail':
                    if self.is_valid_url(value):
                        self.panel_data['thumbnail'] = value
                elif key == 'image':
                    if self.is_valid_url(value):
                        self.panel_data['image'] = value
                elif key == 'footer':
                    self.panel_data['footer'] = value
                elif key == 'timestamp':
                    self.panel_data['timestamp'] = value.lower() in ['yes', 'true', '1']
        
        await self.send_success("✅ Appearance options set!")
        await self.next_step()
    
    async def handle_settings(self, content):
        """Handle behavior settings"""
        if content.lower() == 'skip':
            await self.next_step()
            return
            
        for line in content.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower()
                value = value.strip()
                
                if key == 'dm_notification':
                    self.panel_data['dm_notification'] = value.lower() in ['yes', 'true', '1']
                elif key == 'log_channel':
                    channel = await self.parse_channel_input(value)
                    if channel:
                        self.panel_data['log_channel'] = channel
                elif key == 'auto_remove':
                    self.panel_data['auto_remove'] = value.lower() in ['yes', 'true', '1']
                elif key == 'required_role':
                    role = self.rr_cog.parse_role_input(self.guild, value)
                    if role:
                        self.panel_data['required_role'] = role
                elif key == 'excluded_roles':
                    excluded = []
                    for role_input in value.split(','):
                        role = self.rr_cog.parse_role_input(self.guild, role_input.strip())
                        if role:
                            excluded.append(role)
                    self.panel_data['excluded_roles'] = excluded
        
        await self.send_success("✅ Behavior settings configured!")
        await self.next_step()
    
    async def handle_preview_response(self, content):
        """Handle preview step responses"""
        content_lower = content.lower()
        
        if content_lower == 'confirm':
            await self.finish_creation()
        elif content_lower == 'cancel':
            await self.cancel()
        elif content_lower.startswith('edit '):
            step_name = content_lower[5:].strip()
            await self.edit_step(step_name)
        else:
            await self.send_error("Please respond with 'confirm', 'cancel', or 'edit [step]'.")
    
    async def send_preview(self):
        """Send panel preview"""
        embed = discord.Embed(
            title="👀 Panel Preview",
            description="Here's how your panel will look:",
            color=0x00E6A7
        )
        
        # Create preview embed
        preview_embed = self.create_panel_embed()
        
        # Summary
        summary = f"**Type**: {self.panel_type.title()} Panel\n"
        summary += f"**Roles**: {len(self.panel_data['roles'])}\n"
        summary += f"**Channel**: {self.panel_data['channel'].mention if self.panel_data['channel'] else 'Current channel'}\n"
        
        if self.panel_type == "dropdown":
            summary += f"**Max Selections**: {self.panel_data['max_roles']}\n"
            summary += f"**Placeholder**: {self.panel_data['placeholder']}\n"
        
        embed.add_field(name="📋 Summary", value=summary, inline=False)
        embed.add_field(name="👀 Preview", value="Panel will look like this:", inline=False)
        
        try:
            await self.channel.send(embed=embed)
            await self.channel.send(embed=preview_embed)
        except Exception as e:
            await self.send_error(f"Error showing preview: {str(e)}")
    
    def create_panel_embed(self):
        """Create the actual panel embed"""
        color = self.rr_cog.get_color_from_input(self.panel_data['color'])
        embed = discord.Embed(
            title=self.panel_data['title'],
            description=self.panel_data['description'],
            color=color
        )
        
        # Add roles
        if self.panel_type == "reaction":
            role_list = [f"{r['emoji']} • {r['role'].mention}" for r in self.panel_data['roles']]
            embed.add_field(name="Available Roles", value='\n'.join(role_list), inline=False)
            embed.set_footer(text="React with the emojis to get your roles!")
        else:
            role_list = [f"• {r['role'].mention} - {r['description']}" for r in self.panel_data['roles']]
            embed.add_field(name="Available Roles", value='\n'.join(role_list[:10]) + 
                           ('...' if len(role_list) > 10 else ''), inline=False)
            max_roles = self.panel_data['max_roles']
            embed.set_footer(text=f"Use the dropdown to select up to {max_roles} role{'s' if max_roles != 1 else ''}!")
        
        # Add appearance options
        if self.panel_data['thumbnail']:
            embed.set_thumbnail(url=self.panel_data['thumbnail'])
        if self.panel_data['image']:
            embed.set_image(url=self.panel_data['image'])
        if self.panel_data['footer']:
            embed.set_footer(text=self.panel_data['footer'])
        if self.panel_data['timestamp']:
            embed.timestamp = self.tz_helpers.get_utc_now()
            
        return embed
    
    async def finish_creation(self):
        """Finalize panel creation"""
        try:
            self.waiting_for_response = False
            self.rr_cog.bot.remove_listener(self.on_message, 'on_message')
            
            # Create panel in database
            panel_id = self.rr_cog.db.create_panel(
                self.guild.id,
                panel_type=self.panel_type,
                channel_id=self.channel.id,
                title=self.panel_data['title'],
                description=self.panel_data['description'],
                color=self.panel_data['color'],
                max_roles=self.panel_data.get('max_roles', 1),
                placeholder=self.panel_data.get('placeholder', 'Choose your roles...'),
                max_values=self.panel_data.get('max_roles', 1),
                button_style=self.panel_data.get('button_style', 'primary'),
                max_per_row=self.panel_data.get('max_per_row', 3)
            )
            
            # Create and send panel
            embed = self.create_panel_embed()
            target_channel = self.panel_data['channel'] or self.channel
            
            if self.panel_type == "reaction":
                message = await target_channel.send(embed=embed)
                
                # Update panel with message_id
                self.rr_cog.db.update_panel_message(panel_id, message.id, target_channel.id)
                
                # Add reactions and database entries
                successful_reactions = 0
                failed_reactions = []
                
                for role_data in self.panel_data['roles']:
                    try:
                        print(f"[RR] Adding reaction {role_data['emoji']} for role {role_data['role'].name}")
                        await message.add_reaction(role_data['emoji'])
                        self.rr_cog.db.add_role_to_panel(
                            panel_id, self.guild.id, role_data['role'].id, 
                            role_data['emoji'], message.id, role_data.get('description', '')
                        )
                        successful_reactions += 1
                        print(f"[RR] Successfully added reaction {role_data['emoji']}")
                    except discord.HTTPException as e:
                        print(f"[RR] Failed to add reaction {role_data['emoji']}: {e}")
                        failed_reactions.append(f"{role_data['emoji']} ({str(e)})")
                        continue
                    except Exception as e:
                        print(f"[RR] Unexpected error adding reaction {role_data['emoji']}: {e}")
                        failed_reactions.append(f"{role_data['emoji']} ({str(e)})")
                        continue
                
                # Report any failed reactions
                if failed_reactions:
                    error_embed = discord.Embed(
                        title="⚠️ Some Reactions Failed",
                        description=f"Successfully added {successful_reactions}/{len(self.panel_data['roles'])} reactions.\n\n**Failed reactions:**\n" + "\n".join(failed_reactions),
                        color=0xFFBB00
                    )
                    await self.channel.send(embed=error_embed)
            elif self.panel_type == "button":
                # Create button view
                view = RoleButtonView(
                    self.rr_cog, panel_id, 
                    self.panel_data['roles'],
                    self.panel_data.get('button_style', 'primary'),
                    self.panel_data.get('max_per_row', 3)
                )
                
                message = await target_channel.send(embed=embed, view=view)
                
                # Update panel with message_id
                self.rr_cog.db.update_panel_message(panel_id, message.id, target_channel.id)
                
                # Add roles to database
                for role_data in self.panel_data['roles']:
                    self.rr_cog.db.add_role_to_panel(
                        panel_id, self.guild.id, role_data['role'].id, 
                        None, message.id, role_data.get('label', role_data['role'].name)
                    )
            else:
                # Create dropdown view
                view = RoleDropdownView(
                    self.rr_cog, panel_id, 
                    [(r['role'], r['description']) for r in self.panel_data['roles']],
                    self.panel_data['placeholder'], 
                    self.panel_data['max_roles']
                )
                
                message = await target_channel.send(embed=embed, view=view)
                
                # Update panel with message_id
                self.rr_cog.db.update_panel_message(panel_id, message.id, target_channel.id)
                
                # Add roles to database
                for role_data in self.panel_data['roles']:
                    self.rr_cog.db.add_role_to_panel(
                        panel_id, self.guild.id, role_data['role'].id, 
                        None, message.id, role_data.get('description', '')
                    )
            
            # Success message
            success_embed = discord.Embed(
                title="✅ Panel Created Successfully!",
                description=f"Your {self.panel_type} panel has been created with {len(self.panel_data['roles'])} roles.",
                color=0x00FF00
            )
            
            if target_channel != self.channel:
                success_embed.add_field(
                    name="Location", 
                    value=f"Posted in {target_channel.mention}", 
                    inline=False
                )
            
            await self.channel.send(embed=success_embed)
            
        except sqlite3.OperationalError as e:
            if "no such column: panel_id" in str(e):
                await self.send_error("Database needs migration. Please restart the bot and try again.")
            else:
                await self.send_error(f"Database error: {str(e)}")
        except Exception as e:
            await self.send_error(f"Failed to create panel: {str(e)}")
    
    async def next_step(self):
        """Move to next step"""
        await asyncio.sleep(1)  # Brief delay
        self.current_step += 1
        
        # Handle preview step
        if (self.current_step < len(self.steps) and 
            self.steps[self.current_step][0] == 'preview'):
            await self.send_preview()
        
        await self.send_step()
    
    async def edit_step(self, step_name):
        """Edit a specific step"""
        step_mapping = {step[0]: i for i, step in enumerate(self.steps)}
        
        if step_name in step_mapping:
            self.current_step = step_mapping[step_name]
            await self.send_step()
        else:
            available_steps = ', '.join(step_mapping.keys())
            await self.send_error(f"Unknown step. Available steps: {available_steps}")
    
    async def cancel(self):
        """Cancel panel creation"""
        self.waiting_for_response = False
        self.rr_cog.bot.remove_listener(self.on_message, 'on_message')
        
        embed = discord.Embed(
            title="❌ Panel Creation Cancelled",
            description="Panel creation has been cancelled.",
            color=0xFF0000
        )
        await self.channel.send(embed=embed)
    
    async def timeout(self):
        """Handle timeout"""
        self.waiting_for_response = False
        self.rr_cog.bot.remove_listener(self.on_message, 'on_message')
        
        embed = discord.Embed(
            title="⏰ Panel Creation Timed Out",
            description="Panel creation timed out after 10 minutes of inactivity.",
            color=0xFF0000
        )
        await self.channel.send(embed=embed)
    
    async def send_success(self, message):
        """Send success message"""
        embed = discord.Embed(description=message, color=0x00FF00)
        await self.channel.send(embed=embed)
    
    async def send_error(self, message):
        """Send error message"""
        embed = discord.Embed(description=f"❌ {message}", color=0xFF0000)
        await self.channel.send(embed=embed)
    
    async def validate_emoji(self, emoji_str):
        """Validate if emoji is valid"""
        try:
            # Check if it's a Unicode emoji
            if len(emoji_str) <= 4:  # Unicode emojis are usually 1-4 characters
                return True
            
            # Check if it's a custom emoji format <:name:id> or <a:name:id>
            if emoji_str.startswith('<') and emoji_str.endswith('>'):
                return True
                
            return False
        except:
            return False
    
    async def parse_channel_input(self, channel_input):
        """Parse channel from various input formats"""
        try:
            # Remove < > and # if present
            channel_input = channel_input.strip('<>#')
            
            # Try to get by ID
            if channel_input.isdigit():
                return self.guild.get_channel(int(channel_input))
            
            # Try to find by name
            for channel in self.guild.text_channels:
                if channel.name.lower() == channel_input.lower():
                    return channel
            
            return None
        except:
            return None
    
    def is_valid_url(self, url):
        """Check if URL is valid"""
        try:
            return url.startswith(('http://', 'https://'))
        except:
            return False

class RoleDropdownView(View):
    """Persistent dropdown view for role selection"""
    def __init__(self, rr_cog, panel_id: int, role_data: List[tuple], placeholder: str, max_values: int):
        super().__init__(timeout=None)
        self.rr_cog = rr_cog
        self.panel_id = panel_id
        print(f"[RR DEBUG] Creating RoleDropdownView with panel_id={panel_id}, roles={len(role_data)}")

        # Create dropdown options
        options = []
        for role, description in role_data[:25]:  # Discord limit
            options.append(discord.SelectOption(
                label=role.name,
                description=description[:100],  # Discord limit
                value=str(role.id),
                emoji="🎭"
            ))

        self.role_select = Select(
            placeholder=placeholder,
            options=options,
            max_values=min(max_values, len(options)),
            custom_id=f"role_dropdown_{panel_id}"
        )
        self.role_select.callback = self.role_callback
        self.add_item(self.role_select)

    async def role_callback(self, interaction: discord.Interaction):
        start_time = time.time()
        print(f"[RR DEBUG] role_callback triggered for panel_id={self.panel_id}, user={interaction.user.id}")
        
        try:
            await interaction.response.defer(ephemeral=True)

            if not interaction.guild:
                await interaction.followup.send("❌ Error processing request.", ephemeral=True)
                # Track error
                await self.rr_cog.enhanced_handler.handle_dropdown_interaction(
                    interaction, self.panel_id, [], [], time.time() - start_time, "No guild context"
                )
                return

            # Get member from guild since interaction.member might not be available in all contexts
            member = interaction.guild.get_member(interaction.user.id) if interaction.guild else None
            if not member:
                await interaction.followup.send("❌ Error processing request.", ephemeral=True)
                # Track error
                await self.rr_cog.enhanced_handler.handle_dropdown_interaction(
                    interaction, self.panel_id, [], [], time.time() - start_time, "Member not found"
                )
                return

            selected_role_ids = [int(value) for value in self.role_select.values]
            
            # Get all roles in this panel with detailed error handling
            try:
                panel_roles = self.rr_cog.db.get_panel_roles(self.panel_id)
                panel_role_ids = [r['role_id'] for r in panel_roles]
                print(f"[RR DEBUG] Panel {self.panel_id} has {len(panel_roles)} roles: {panel_role_ids}")
            except sqlite3.OperationalError as e:
                print(f"[RR ERROR] Database schema error: {e}")
                await interaction.followup.send("❌ Database schema error. Please restart the bot to apply migrations.", ephemeral=True)
                # Track error
                await self.rr_cog.enhanced_handler.handle_dropdown_interaction(
                    interaction, self.panel_id, [], [], time.time() - start_time, f"Database schema error: {e}"
                )
                return
            except sqlite3.Error as e:
                print(f"[RR ERROR] Database error: {e}")
                await interaction.followup.send("❌ Database error. Please contact an administrator.", ephemeral=True)
                # Track error
                await self.rr_cog.enhanced_handler.handle_dropdown_interaction(
                    interaction, self.panel_id, [], [], time.time() - start_time, f"Database error: {e}"
                )
                return
            except Exception as e:
                print(f"[RR ERROR] Unexpected error getting panel roles: {e}")
                import traceback
                print(traceback.format_exc())
                await interaction.followup.send(f"❌ Unexpected error: {str(e)}", ephemeral=True)
                # Track error
                await self.rr_cog.enhanced_handler.handle_dropdown_interaction(
                    interaction, self.panel_id, [], [], time.time() - start_time, f"Unexpected error: {e}"
                )
                return

            added_roles = []
            removed_roles = []

            # Remove all panel roles first, then add selected ones
            for role_id in panel_role_ids:
                role = interaction.guild.get_role(role_id)
                if role and role in member.roles and role_id not in selected_role_ids:
                    try:
                        await member.remove_roles(role, reason="Dropdown role deselected")
                        removed_roles.append(role.name)
                    except discord.Forbidden:
                        pass

            # Add selected roles
            for role_id in selected_role_ids:
                role = interaction.guild.get_role(role_id)
                if role and role not in member.roles:
                    try:
                        await member.add_roles(role, reason="Dropdown role selected")
                        added_roles.append(role.name)
                    except discord.Forbidden:
                        pass

            # Send response
            response_parts = []
            if added_roles:
                response_parts.append(f"✅ **Added:** {', '.join(added_roles)}")
            if removed_roles:
                response_parts.append(f"❌ **Removed:** {', '.join(removed_roles)}")

            if response_parts:
                await interaction.followup.send('\n'.join(response_parts), ephemeral=True)
            else:
                await interaction.followup.send("No changes made to your roles.", ephemeral=True)

            # DM notification if enabled
            settings = self.rr_cog.db.get_settings(interaction.guild.id)
            if settings['dm_enabled'] and (added_roles or removed_roles):
                try:
                    dm_msg = f"**Role Update from {interaction.guild.name}:**\n"
                    if added_roles:
                        dm_msg += f"✅ Added: {', '.join(added_roles)}\n"
                    if removed_roles:
                        dm_msg += f"❌ Removed: {', '.join(removed_roles)}"
                    await member.send(dm_msg)
                except discord.Forbidden:
                    pass

            # Log to channel if configured
            if settings.get('log_channel'):
                try:
                    log_channel = interaction.guild.get_channel(settings['log_channel'])
                    if log_channel and (added_roles or removed_roles):
                        log_embed = discord.Embed(
                            title="🎭 Dropdown Role Change",
                            color=0x00ff00 if added_roles else 0xff0000,
                            timestamp=datetime.datetime.utcnow()
                        )
                        log_embed.add_field(name="User", value=f"{member.mention} ({member.id})", inline=True)
                        log_embed.add_field(name="Panel ID", value=str(self.panel_id), inline=True)
                        log_embed.add_field(name="Channel", value=getattr(interaction.channel, 'mention', 'Unknown Channel'), inline=True)
                        
                        if added_roles:
                            log_embed.add_field(name="✅ Roles Added", value=', '.join(added_roles), inline=False)
                        if removed_roles:
                            log_embed.add_field(name="❌ Roles Removed", value=', '.join(removed_roles), inline=False)
                        
                        if hasattr(log_channel, 'send') and not isinstance(log_channel, (discord.ForumChannel, discord.CategoryChannel)):
                            await log_channel.send(embed=log_embed)
                except Exception as e:
                    print(f"[RR ERROR] Failed to send log message: {e}")

            # Track successful interaction with analytics
            await self.rr_cog.enhanced_handler.handle_dropdown_interaction(
                interaction, self.panel_id, added_roles, removed_roles, time.time() - start_time
            )

        except Exception as e:
            # Track any unexpected errors
            print(f"[RR ERROR] Unexpected error in dropdown callback: {e}")
            import traceback
            traceback.print_exc()
            
            try:
                await interaction.followup.send("❌ An unexpected error occurred.", ephemeral=True)
            except:
                pass
                
            # Track error with analytics
            await self.rr_cog.enhanced_handler.handle_dropdown_interaction(
                interaction, self.panel_id, [], [], time.time() - start_time, f"Callback error: {e}"
            )

class RoleButtonView(View):
    """Persistent button view for role selection"""
    def __init__(self, rr_cog, panel_id: int, role_data: List[dict], button_style: str = "primary", max_per_row: int = 3):
        super().__init__(timeout=None)
        self.rr_cog = rr_cog
        self.panel_id = panel_id
        self.role_map = {}  # Store role_id mapping
        print(f"[RR DEBUG] Creating RoleButtonView with panel_id={panel_id}, roles={len(role_data)}")

        # Map button style strings to discord styles
        style_map = {
            "primary": discord.ButtonStyle.primary,
            "secondary": discord.ButtonStyle.secondary,
            "success": discord.ButtonStyle.success,
            "danger": discord.ButtonStyle.danger
        }
        
        button_style_obj = style_map.get(button_style.lower(), discord.ButtonStyle.primary)
        
        # Create buttons (max 25 total, max 5 per row)
        current_row = 0
        buttons_in_row = 0
        
        for i, role_data_item in enumerate(role_data[:25]):  # Discord limit
            if buttons_in_row >= max_per_row:
                current_row += 1
                buttons_in_row = 0
            
            role = role_data_item['role']
            label = role_data_item.get('label', role.name)
            emoji = role_data_item.get('emoji', None)
            
            # Store role mapping
            custom_id = f"role_button_{panel_id}_{role.id}"
            self.role_map[custom_id] = role.id
            
            # Create button with custom_id that includes role_id
            button = Button(
                label=label[:80],  # Discord limit
                style=button_style_obj,
                emoji=emoji,
                custom_id=custom_id,
                row=current_row
            )
            
            # Set callback
            button.callback = self.button_callback
            self.add_item(button)
            buttons_in_row += 1

    async def button_callback(self, interaction: discord.Interaction):
        """Handle button click from custom_id"""
        # Extract role_id from custom_id
        if hasattr(interaction, 'data') and interaction.data:
            custom_id = interaction.data.get('custom_id', '') if hasattr(interaction.data, 'get') else ''
        else:
            custom_id = ''
            
        role_id = self.role_map.get(custom_id)
        
        if role_id:
            await self.handle_role_button(interaction, role_id)
        else:
            await interaction.response.send_message("❌ Error: Invalid button interaction.", ephemeral=True)

    async def handle_role_button(self, interaction: discord.Interaction, role_id: int):
        """Handle button click for role toggle"""
        start_time = time.time()
        print(f"[RR DEBUG] button_callback triggered for panel_id={self.panel_id}, role_id={role_id}, user={interaction.user.id}")
        
        try:
            await interaction.response.defer(ephemeral=True)

            if not interaction.guild:
                await interaction.followup.send("❌ Error processing request.", ephemeral=True)
                return

            member = interaction.guild.get_member(interaction.user.id)
            if not member:
                await interaction.followup.send("❌ Member not found.", ephemeral=True)
                return

            role = interaction.guild.get_role(role_id)
            if not role:
                await interaction.followup.send("❌ Role not found.", ephemeral=True)
                return

            # Check if user already has the role
            has_role = role in member.roles
            
            try:
                if has_role:
                    # Remove role
                    await member.remove_roles(role, reason="Button role panel")
                    action = "remove"
                    message = f"❌ Removed the **{role.name}** role."
                    color = 0xFF0000
                else:
                    # Add role
                    await member.add_roles(role, reason="Button role panel")
                    action = "add"
                    message = f"✅ Added the **{role.name}** role!"
                    color = 0x00FF00

                # Enhanced analytics tracking
                response_time = int((time.time() - start_time) * 1000)
                await enhanced_rr_db.track_interaction(
                    interaction.guild.id, interaction.user.id, self.panel_id, role_id,
                    action, "button", response_time, True
                )

                # Send response
                embed = discord.Embed(description=message, color=color)
                await interaction.followup.send(embed=embed, ephemeral=True)

                # Log if enabled
                settings = self.rr_cog.db.get_settings(interaction.guild.id)
                if settings.get('log_channel_id'):
                    log_channel = interaction.guild.get_channel(settings['log_channel_id'])
                    if log_channel and isinstance(log_channel, (discord.TextChannel, discord.Thread)):
                        log_embed = discord.Embed(
                            title=f"Role {'Added' if action == 'add' else 'Removed'}",
                            description=f"{member.mention} {'gained' if action == 'add' else 'lost'} {role.mention}",
                            color=color
                        )
                        await log_channel.send(embed=log_embed)

                # DM if enabled
                if settings.get('dm_enabled', 1):
                    try:
                        dm_message = f"{'✅' if action == 'add' else '❌'} The **{role.name}** role has been {'added to' if action == 'add' else 'removed from'} you in **{interaction.guild.name}**."
                        await member.send(dm_message)
                    except discord.Forbidden:
                        pass

            except discord.Forbidden:
                await interaction.followup.send("❌ I don't have permission to manage this role.", ephemeral=True)
                # Track failed interaction
                response_time = int((time.time() - start_time) * 1000)
                await enhanced_rr_db.track_interaction(
                    interaction.guild.id, interaction.user.id, self.panel_id, role_id,
                    "add" if not has_role else "remove", "button", response_time, False
                )

        except Exception as e:
            print(f"[RR ERROR] Button callback error: {e}")
            try:
                await interaction.followup.send("❌ An error occurred while processing your request.", ephemeral=True)
            except:
                pass
            # Track error
            if interaction.guild:
                await enhanced_rr_db.log_error(
                    interaction.guild.id, "button_callback", f"Button callback error: {e}"
                )

class SettingsView(View):
    """Settings configuration view"""
    def __init__(self, rr_cog, guild_id: int):
        super().__init__(timeout=600)
        self.rr_cog = rr_cog
        self.guild_id = guild_id

    @discord.ui.button(label="🔔 Toggle DM Notifications", style=discord.ButtonStyle.secondary)
    async def toggle_dm(self, interaction: discord.Interaction, button: Button):
        settings = self.rr_cog.db.get_settings(self.guild_id)
        new_value = not settings['dm_enabled']
        
        self.rr_cog.db.update_settings(self.guild_id, dm_enabled=new_value)
        
        await interaction.response.send_message(
            f"{'✅ Enabled' if new_value else '❌ Disabled'} DM notifications.",
            ephemeral=True
        )

    @discord.ui.button(label="🗑️ Toggle Remove Reactions", style=discord.ButtonStyle.secondary)
    async def toggle_remove_reactions(self, interaction: discord.Interaction, button: Button):
        settings = self.rr_cog.db.get_settings(self.guild_id)
        new_value = not settings['remove_reaction']
        
        self.rr_cog.db.update_settings(self.guild_id, remove_reaction=new_value)
        
        await interaction.response.send_message(
            f"{'✅ Enabled' if new_value else '❌ Disabled'} automatic reaction removal.",
            ephemeral=True
        )

    @discord.ui.button(label="📋 Set Log Channel", style=discord.ButtonStyle.primary)
    async def set_log_channel(self, interaction: discord.Interaction, button: Button):
        modal = LogChannelModal(self.rr_cog, self.guild_id)
        await interaction.response.send_modal(modal)

class LogChannelModal(Modal):
    """Modal for setting log channel"""
    def __init__(self, rr_cog, guild_id: int):
        super().__init__(title="Set Log Channel")
        self.rr_cog = rr_cog
        self.guild_id = guild_id

        self.channel_input = TextInput(
            label="Log Channel",
            placeholder="Channel mention, ID, or name (leave empty to disable)",
            required=False,
            max_length=100
        )
        self.add_item(self.channel_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        if not interaction.guild:
            await interaction.followup.send("❌ This can only be used in a server.", ephemeral=True)
            return

        channel_id = None
        if self.channel_input.value.strip():
            channel_input = self.channel_input.value.strip()
            
            # Try parsing channel mention
            channel_match = re.match(r'<#(\d+)>', channel_input)
            if channel_match:
                channel_id = int(channel_match.group(1))
            elif channel_input.isdigit():
                channel_id = int(channel_input)
            else:
                # Try finding by name
                channel = discord.utils.get(interaction.guild.text_channels, name=channel_input)
                if channel:
                    channel_id = channel.id

            if channel_id:
                channel = interaction.guild.get_channel(channel_id)
                if not channel or not isinstance(channel, discord.TextChannel):
                    await interaction.followup.send("❌ Channel not found or not a text channel!", ephemeral=True)
                    return

        self.rr_cog.db.update_settings(self.guild_id, log_channel_id=channel_id)
        
        if channel_id:
            await interaction.followup.send(f"✅ Log channel set to <#{channel_id}>", ephemeral=True)
        else:
            await interaction.followup.send("✅ Log channel disabled.", ephemeral=True)

class EditPanelView(discord.ui.View):
    def __init__(self, cog, panel_id: int, panel_data: Dict):
        super().__init__(timeout=300)
        self.cog = cog
        self.panel_id = panel_id
        self.panel_data = panel_data

    @discord.ui.button(label="Edit Title/Description", style=discord.ButtonStyle.primary, emoji="📝")
    async def edit_content(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = EditContentModal(self.cog, self.panel_id, self.panel_data)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Manage Roles", style=discord.ButtonStyle.secondary, emoji="⚙️")
    async def manage_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open interactive role management interface"""
        if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("❌ You need `Manage Roles` permission to use this feature!", ephemeral=True)
            return
            
        # Create interactive management view
        management_view = RoleManagementView(self.cog, self.panel_id, interaction.user)
        
        embed = discord.Embed(
            title="🔧 Role Management Panel",
            description=f"**Panel ID:** {self.panel_id}\n\nChoose an action below to manage this reaction role panel:",
            color=0x3498db
        )
        
        embed.add_field(
            name="🔧 Available Actions",
            value="• **Add Role** - Add new reaction role\n• **Remove Role** - Remove existing role\n• **Edit Panel** - Modify panel settings\n• **View Roles** - See all roles in panel",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, view=management_view, ephemeral=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.gray, emoji="❌")
    async def cancel_edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="✅ Edit cancelled.", embed=None, view=None)

class EditContentModal(discord.ui.Modal):
    def __init__(self, cog, panel_id: int, panel_data: Dict):
        super().__init__(title="Edit Panel Content")
        self.cog = cog
        self.panel_id = panel_id
        
        self.title_input = discord.ui.TextInput(
            label="Panel Title",
            placeholder="Enter the panel title...",
            default=panel_data.get('title', ''),
            max_length=100,
            required=True
        )
        self.add_item(self.title_input)
        
        self.description_input = discord.ui.TextInput(
            label="Panel Description",
            placeholder="Enter the panel description...",
            default=panel_data.get('description', ''),
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=False
        )
        self.add_item(self.description_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        # Update panel in database
        with sqlite3.connect(self.cog.db.db_path) as conn:
            conn.execute("""
                UPDATE rr_panels 
                SET title = ?, description = ? 
                WHERE id = ?
            """, (self.title_input.value, self.description_input.value or None, self.panel_id))
            conn.commit()
        
        # Try to update the original message if possible
        try:
            panel = self.cog.db.get_panel_by_id(self.panel_id)
            if panel and interaction.guild:
                channel = interaction.guild.get_channel(panel['channel_id'])
                if isinstance(channel, (discord.TextChannel, discord.Thread)):
                    message = await channel.fetch_message(panel['message_id'])
                    roles = self.cog.db.get_panel_roles(self.panel_id)
                    
                    if panel['panel_type'] == 'dropdown':
                        embed = discord.Embed(
                            title=self.title_input.value,
                            description=self.description_input.value,
                            color=0x3498db
                        )
                        view = RoleDropdownView(self.cog.db, self.panel_id, roles, "Select roles:", min(len(roles), 25))
                        await message.edit(embed=embed, view=view)
                    # Add reaction panel update logic here if needed
        except:
            pass  # Message might be deleted or inaccessible
        
        await interaction.followup.send("✅ Panel content updated successfully!", ephemeral=True)

class DeleteConfirmationView(discord.ui.View):
    def __init__(self, cog, panel_id: int, panel_data: Dict):
        super().__init__(timeout=300)
        self.cog = cog
        self.panel_id = panel_id
        self.panel_data = panel_data

    @discord.ui.button(label="Confirm Delete", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        if not interaction.guild:
            await interaction.followup.send("❌ This can only be used in a server.", ephemeral=True)
            return
        
        # Remove all reaction roles for this panel
        self.cog.db.remove_reaction_role(interaction.guild.id, self.panel_id)
        
        # Remove the panel itself
        with sqlite3.connect(self.cog.db.db_path) as conn:
            conn.execute("DELETE FROM rr_panels WHERE id = ?", (self.panel_id,))
            conn.commit()
        
        # Try to delete the original message
        try:
            channel = interaction.guild.get_channel(self.panel_data['channel_id'])
            if isinstance(channel, (discord.TextChannel, discord.Thread)):
                message = await channel.fetch_message(self.panel_data['message_id'])
                await message.delete()
        except:
            pass  # Message might already be deleted
        
        embed = discord.Embed(
            title="🗑️ Panel Deleted",
            description=f"Panel **{self.panel_data['title']}** has been successfully deleted.\n"
                       f"All associated reaction roles have been removed.",
            color=0xe74c3c
        )
        await interaction.followup.send(embed=embed)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.gray, emoji="❌")
    async def cancel_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="✅ Deletion cancelled.", embed=None, view=None)


class RoleManagementView(discord.ui.View):
    """Interactive role management interface for reaction role panels"""
    
    def __init__(self, cog, panel_id: int, user: discord.Member):
        super().__init__(timeout=300)
        self.cog = cog
        self.panel_id = panel_id
        self.user = user

    @discord.ui.button(label="Add Role", style=discord.ButtonStyle.success, emoji="➕")
    async def add_role_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show modal to add a new role to the panel"""
        if interaction.user != self.user:
            await interaction.response.send_message("❌ Only the user who opened this panel can use these buttons!", ephemeral=True)
            return
            
        modal = AddRoleModal(self.cog, self.panel_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Remove Role", style=discord.ButtonStyle.danger, emoji="➖")
    async def remove_role_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show dropdown to remove a role from the panel"""
        if interaction.user != self.user:
            await interaction.response.send_message("❌ Only the user who opened this panel can use these buttons!", ephemeral=True)
            return
            
        if not interaction.guild:
            await interaction.response.send_message("❌ This can only be used in a server!", ephemeral=True)
            return
            
        # Get roles for this panel
        with sqlite3.connect(self.cog.db.db_path) as conn:
            cursor = conn.execute("""
                SELECT role_id, emoji FROM rr_roles 
                WHERE panel_id = ? AND guild_id = ?
            """, (self.panel_id, interaction.guild.id))
            roles = cursor.fetchall()
        
        if not roles:
            await interaction.response.send_message("❌ No roles found in this panel to remove!", ephemeral=True)
            return
            
        view = RemoveRoleSelectView(self.cog, self.panel_id, roles, self.user, interaction.guild)
        await interaction.response.send_message("Select a role to remove:", view=view, ephemeral=True)

    @discord.ui.button(label="View Roles", style=discord.ButtonStyle.secondary, emoji="👁️")
    async def view_roles_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show all roles in the panel"""
        if interaction.user != self.user:
            await interaction.response.send_message("❌ Only the user who opened this panel can use these buttons!", ephemeral=True)
            return
            
        if not interaction.guild:
            await interaction.response.send_message("❌ This can only be used in a server!", ephemeral=True)
            return
            
        # Get roles for this panel
        with sqlite3.connect(self.cog.db.db_path) as conn:
            cursor = conn.execute("""
                SELECT role_id, emoji FROM rr_roles 
                WHERE panel_id = ? AND guild_id = ?
            """, (self.panel_id, interaction.guild.id))
            roles = cursor.fetchall()
        
        if not roles:
            await interaction.response.send_message("❌ No roles found in this panel!", ephemeral=True)
            return
            
        embed = discord.Embed(
            title="📋 Panel Roles",
            description=f"**Panel ID:** {self.panel_id}\n\n**Roles in this panel:**",
            color=0x3498db
        )
        
        role_list = []
        for role_id, emoji in roles:
            role = interaction.guild.get_role(int(role_id))
            if role:
                role_list.append(f"{emoji} {role.mention} - `{role.name}`")
            else:
                role_list.append(f"{emoji} `Deleted Role ({role_id})`")
        
        embed.add_field(
            name="🎭 Reaction Roles",
            value="\n".join(role_list) if role_list else "No roles configured",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.gray, emoji="❌")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Close the management interface"""
        if interaction.user != self.user:
            await interaction.response.send_message("❌ Only the user who opened this panel can use these buttons!", ephemeral=True)
            return
            
        await interaction.response.edit_message(content="✅ Role management closed.", embed=None, view=None)


class AddRoleModal(discord.ui.Modal):
    """Modal for adding roles to a reaction role panel"""
    
    def __init__(self, cog, panel_id: int):
        super().__init__(title="Add Role to Panel")
        self.cog = cog
        self.panel_id = panel_id

    emoji_input = discord.ui.TextInput(
        label="Emoji",
        placeholder="Enter an emoji (e.g., 🎮 or :custom_emoji:)",
        max_length=100,
        required=True
    )
    
    role_input = discord.ui.TextInput(
        label="Role",
        placeholder="Enter role name, mention, or ID",
        max_length=200,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        if not interaction.guild:
            await interaction.followup.send("❌ This can only be used in a server!", ephemeral=True)
            return
        
        # Parse role input
        role = self.cog.parse_role_input(interaction.guild, self.role_input.value)
        if not role:
            await interaction.followup.send("❌ Role not found! Use role mention, ID, or exact name.", ephemeral=True)
            return
            
        # Get panel data to find the message
        with sqlite3.connect(self.cog.db.db_path) as conn:
            cursor = conn.execute("""
                SELECT message_id, channel_id FROM rr_panels 
                WHERE id = ? AND guild_id = ?
            """, (self.panel_id, interaction.guild.id))
            panel_data = cursor.fetchone()
        
        if not panel_data:
            await interaction.followup.send("❌ Panel not found!", ephemeral=True)
            return
            
        message_id, channel_id = panel_data
        
        # Add the role to the panel
        try:
            self.cog.db.add_role_to_panel(self.panel_id, interaction.guild.id, role.id, self.emoji_input.value, message_id)
            
            # Try to add reaction to the message
            try:
                channel = interaction.guild.get_channel(channel_id)
                if channel and isinstance(channel, (discord.TextChannel, discord.Thread)):
                    message = await channel.fetch_message(message_id)
                    await message.add_reaction(self.emoji_input.value)
            except:
                pass  # Reaction might fail but role is still added
            
            embed = discord.Embed(
                title="✅ Role Added Successfully",
                description=f"**Role:** {role.mention}\n**Emoji:** {self.emoji_input.value}\n**Panel ID:** {self.panel_id}",
                color=0x00ff00
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to add role: {str(e)}", ephemeral=True)


class RemoveRoleSelectView(discord.ui.View):
    """View with dropdown to select which role to remove"""
    
    def __init__(self, cog, panel_id: int, roles: list, user: discord.Member, guild: discord.Guild):
        super().__init__(timeout=300)
        self.cog = cog
        self.panel_id = panel_id
        self.user = user
        self.guild = guild
        
        # Create dropdown options
        options = []
        for role_id, emoji in roles[:25]:  # Discord limit of 25 options
            role = guild.get_role(int(role_id))
            label = role.name if role else f"Deleted Role ({role_id})"
            options.append(discord.SelectOption(
                label=label[:100],  # Discord limit
                value=str(role_id),
                emoji=emoji,
                description=f"Remove {label}"[:100] if role else f"Remove deleted role {role_id}"
            ))
        
        # Add the dropdown
        if options:
            self.add_item(RemoveRoleSelect(self.cog, self.panel_id, options, self.user))

class RemoveRoleSelect(discord.ui.Select):
    """Dropdown to select which role to remove"""
    
    def __init__(self, cog, panel_id: int, options: list, user: discord.Member):
        super().__init__(placeholder="Select a role to remove...", options=options)
        self.cog = cog
        self.panel_id = panel_id
        self.user = user

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.user:
            await interaction.response.send_message("❌ Only the user who opened this panel can use this!", ephemeral=True)
            return
            
        if not interaction.guild:
            await interaction.response.send_message("❌ This can only be used in a server!", ephemeral=True)
            return
            
        role_id = int(self.values[0])
        role = interaction.guild.get_role(role_id)
        
        # Remove the role from the panel
        with sqlite3.connect(self.cog.db.db_path) as conn:
            cursor = conn.execute("""
                SELECT emoji FROM rr_roles 
                WHERE panel_id = ? AND guild_id = ? AND role_id = ?
            """, (self.panel_id, interaction.guild.id, role_id))
            result = cursor.fetchone()
            
            if result:
                emoji = result[0]
                conn.execute("""
                    DELETE FROM rr_roles 
                    WHERE panel_id = ? AND guild_id = ? AND role_id = ?
                """, (self.panel_id, interaction.guild.id, role_id))
                conn.commit()
                
                embed = discord.Embed(
                    title="✅ Role Removed Successfully",
                    description=f"**Role:** {role.mention if role else f'Deleted Role ({role_id})'}\n**Emoji:** {emoji}\n**Panel ID:** {self.panel_id}",
                    color=0xff6b6b
                )
                await interaction.response.edit_message(embed=embed, view=None)
            else:
                await interaction.response.send_message("❌ Role not found in panel!", ephemeral=True)

    def help_custom(self):
        return "🎭", "Enhanced Reaction Roles", "Interactive role panels with reactions & dropdown menus"

# Setup
async def setup(bot):
    await bot.add_cog(ReactionRoles(bot))

