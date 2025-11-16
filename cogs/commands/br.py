import discord
import aiosqlite
from discord.ext import commands
from discord.ui import Button, View, Select, Modal, TextInput
from discord import ButtonStyle, SelectOption
import re
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from utils.Tools import blacklist_check, ignore_check
from utils.error_helpers import StandardErrorHandler
class BoosterRoleHelpView(View):
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
            title="🚀 Booster Roles Help",
            description="Comprehensive booster role management system",
            color=0x006fb9
        )
        
        embed.add_field(
            name="👤 User Commands",
            value=(
                "`br create` - Create your booster role\n"
                "`br name <name>` - Change role name\n"
                "`br color <color>` - Change role color\n"
                "`br icon <emoji/url>` - Set role icon\n"
                "`br delete` - Delete your role\n"
                "`br info` - View your role info"
            ),
            inline=False
        )
        
        embed.add_field(
            name="⚙️ Admin Commands",
            value=(
                "`br setup <base_role>` - Setup booster roles\n"
                "`br config` - View configuration\n"
                "`br toggle` - Enable/disable system\n"
                "`br cleanup` - Clean unused roles\n"
                "`br reset <user>` - Reset user's role\n"
                "`br logs` - View activity logs"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🚀 Booster Messages",
            value=(
                "`br message setup` - Setup booster messages\n"
                "`br message channel <channel>` - Set message channel\n"
                "`br message test` - Test booster message\n"
                "`br message config` - View message config\n"
                "`br message reset` - Disable booster messages"
            ),
            inline=False
        )
        
        embed.set_footer(text=f"• Help page 1/{4} | Requested by: {self.ctx.author.display_name}",
                        icon_url=self.ctx.bot.user.avatar.url)
        pages.append(embed)
        
        # User Commands Details
        embed = discord.Embed(
            title="👤 User Commands - Detailed",
            color=0x006fb9
        )
        embed.add_field(
            name="br create <name>",
            value="Create your personal booster role with a custom name.\n**Example:** `br create My Cool Role`",
            inline=False
        )
        embed.add_field(
            name="br name <new_name>",
            value="Change your existing role's name.\n**Example:** `br name Updated Name`",
            inline=False
        )
        embed.add_field(
            name="br color <color>",
            value="Change role color using hex (#ff0000), names (red), or decimal.\n**Example:** `br color #ff6b6b`",
            inline=False
        )
        embed.add_field(
            name="br icon <emoji/url>",
            value="Set role icon using emoji or image URL.\n**Example:** `br icon 🎭`",
            inline=False
        )
        embed.set_footer(text=f"• Help page 2/{4} | Requested by: {self.ctx.author.display_name}",
                        icon_url=self.ctx.bot.user.avatar.url)
        pages.append(embed)
        
        # Admin Commands Details  
        embed = discord.Embed(
            title="⚙️ Admin Commands - Detailed",
            color=0x006fb9
        )
        embed.add_field(
            name="br setup [base_role]",
            value="Initialize booster role system with optional base role for positioning.\n**Example:** `br setup @Booster`",
            inline=False
        )
        embed.add_field(
            name="br config",
            value="View current configuration including all settings and restrictions.\n**Example:** `br config`",
            inline=False
        )
        embed.add_field(
            name="br cleanup",
            value="Remove roles from users who stopped boosting or left the server.\n**Example:** `br cleanup`",
            inline=False
        )
        embed.add_field(
            name="br logs [limit]",
            value="View recent activity logs (max 25 entries).\n**Example:** `br logs 10`",
            inline=False
        )
        embed.set_footer(text=f"• Help page 3/{4} | Requested by: {self.ctx.author.display_name}",
                        icon_url=self.ctx.bot.user.avatar.url)
        pages.append(embed)
        
        # Configuration Commands
        embed = discord.Embed(
            title="📋 Configuration Commands",
            color=0x006fb9
        )
        embed.add_field(
            name="br set maxlength <number>",
            value="Set maximum role name length (1-100).\n**Example:** `br set maxlength 25`",
            inline=False
        )
        embed.add_field(
            name="br set prefix <text>",
            value="Require specific prefix for all role names.\n**Example:** `br set prefix ⭐`",
            inline=False
        )
        embed.add_field(
            name="br set icons <on/off>",
            value="Enable or disable role icons.\n**Example:** `br set icons on`",
            inline=False
        )
        embed.add_field(
            name="br blacklist add/remove <word>",
            value="Manage blacklisted words in role names.\n**Example:** `br blacklist add spam`",
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

BR_DB_PATH = 'db/br.db'

class BoosterRoles(commands.Cog):
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot
        self.color = 0x006fb9
        self.db_path = BR_DB_PATH
        self.bot.loop.create_task(self.init_database())

    async def init_database(self):
        """Initialize the booster roles database"""
        async with aiosqlite.connect(self.db_path) as db:
            # Base booster role configuration per guild
            await db.execute("""
                CREATE TABLE IF NOT EXISTS booster_config (
                    guild_id INTEGER PRIMARY KEY,
                    base_role_id INTEGER,
                    enabled BOOLEAN DEFAULT 1,
                    max_name_length INTEGER DEFAULT 32,
                    allowed_colors TEXT DEFAULT 'all',
                    icon_enabled BOOLEAN DEFAULT 1,
                    require_boost BOOLEAN DEFAULT 1,
                    auto_cleanup BOOLEAN DEFAULT 1,
                    prefix_required TEXT DEFAULT NULL,
                    suffix_required TEXT DEFAULT NULL,
                    blacklisted_words TEXT DEFAULT '[]',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Individual user booster roles
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_booster_roles (
                    id INTEGER PRIMARY KEY,
                    guild_id INTEGER,
                    user_id INTEGER,
                    role_id INTEGER,
                    role_name TEXT,
                    role_color INTEGER DEFAULT 0,
                    role_icon TEXT DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(guild_id, user_id)
                )
            """)
            
            # Booster role activity logs
            await db.execute("""
                CREATE TABLE IF NOT EXISTS booster_logs (
                    id INTEGER PRIMARY KEY,
                    guild_id INTEGER,
                    user_id INTEGER,
                    action TEXT,
                    details TEXT,
                    moderator_id INTEGER DEFAULT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()

        # Create booster messages database
        async with aiosqlite.connect("db/booster_messages.db") as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS booster_messages (
                    guild_id INTEGER PRIMARY KEY,
                    message_type TEXT,
                    message_content TEXT,
                    channel_id INTEGER,
                    embed_data TEXT,
                    auto_delete_duration INTEGER DEFAULT NULL
                )
            """)
            await db.commit()

    async def get_config(self, guild_id: int) -> Optional[Dict]:
        """Get guild booster role configuration"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT * FROM booster_config WHERE guild_id = ?", 
                (guild_id,)
            )
            result = await cursor.fetchone()
            if result:
                return {
                    'guild_id': result[0],
                    'base_role_id': result[1],
                    'enabled': bool(result[2]),
                    'max_name_length': result[3],
                    'allowed_colors': result[4],
                    'icon_enabled': bool(result[5]),
                    'require_boost': bool(result[6]),
                    'auto_cleanup': bool(result[7]),
                    'prefix_required': result[8],
                    'suffix_required': result[9],
                    'blacklisted_words': json.loads(result[10] or '[]'),
                    'created_at': result[11],
                    'updated_at': result[12]
                }
            return None

    async def update_config(self, guild_id: int, **kwargs):
        """Update guild booster role configuration"""
        async with aiosqlite.connect(self.db_path) as db:
            config = await self.get_config(guild_id)
            if not config:
                # Insert new config
                await db.execute(
                    "INSERT INTO booster_config (guild_id) VALUES (?)",
                    (guild_id,)
                )
            
            # Update specific fields
            for key, value in kwargs.items():
                if key == 'blacklisted_words':
                    value = json.dumps(value)
                await db.execute(
                    f"UPDATE booster_config SET {key} = ?, updated_at = CURRENT_TIMESTAMP WHERE guild_id = ?",
                    (value, guild_id)
                )
            await db.commit()

    async def get_user_role(self, guild_id: int, user_id: int) -> Optional[Dict]:
        """Get user's booster role data"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT * FROM user_booster_roles WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id)
            )
            result = await cursor.fetchone()
            if result:
                return {
                    'id': result[0],
                    'guild_id': result[1],
                    'user_id': result[2],
                    'role_id': result[3],
                    'role_name': result[4],
                    'role_color': result[5],
                    'role_icon': result[6],
                    'created_at': result[7],
                    'updated_at': result[8]
                }
            return None

    async def save_user_role(self, guild_id: int, user_id: int, role_id: int, 
                           role_name: str, role_color: int, role_icon: Optional[str] = None):
        """Save user's booster role data"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO user_booster_roles 
                (guild_id, user_id, role_id, role_name, role_color, role_icon, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (guild_id, user_id, role_id, role_name, role_color, role_icon))
            await db.commit()

    async def delete_user_role(self, guild_id: int, user_id: int):
        """Delete user's booster role data"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM user_booster_roles WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id)
            )
            await db.commit()

    async def log_action(self, guild_id: int, user_id: int, action: str, 
                        details: str, moderator_id: Optional[int] = None):
        """Log booster role action"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO booster_logs (guild_id, user_id, action, details, moderator_id) VALUES (?, ?, ?, ?, ?)",
                (guild_id, user_id, action, details, moderator_id)
            )
            await db.commit()

    def validate_role_name(self, name: str, config: Dict) -> tuple[bool, str]:
        """Validate booster role name"""
        # Length check
        if len(name) > config['max_name_length']:
            return False, f"Name must be {config['max_name_length']} characters or less"
        
        # Prefix/suffix requirements
        if config['prefix_required'] and not name.startswith(config['prefix_required']):
            return False, f"Name must start with '{config['prefix_required']}'"
        
        if config['suffix_required'] and not name.endswith(config['suffix_required']):
            return False, f"Name must end with '{config['suffix_required']}'"
        
        # Blacklisted words
        name_lower = name.lower()
        for word in config['blacklisted_words']:
            if word.lower() in name_lower:
                return False, f"Name contains prohibited word: {word}"
        
        # Discord reserved words
        reserved = ['discord', 'everyone', 'here', '@everyone', '@here']
        for word in reserved:
            if word in name_lower:
                return False, f"Name contains reserved word: {word}"
        
        return True, ""

    @commands.group(name="br", invoke_without_command=True, aliases=["boosterrole", "boosterroles"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    async def br(self, ctx):
        """Booster role management system"""
        if ctx.invoked_subcommand is None:
            view = BoosterRoleHelpView(ctx)
            view.update_buttons()  # Set initial button states
            await ctx.send(embed=view.pages[0], view=view)

    @br.command(name="create")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def create_booster_role(self, ctx, *, name: Optional[str] = None):
        """Create your personal booster role"""
        config = await self.get_config(ctx.guild.id)
        if not config or not config['enabled']:
            embed = discord.Embed(
                title="❌ Booster Roles Disabled",
                description="Booster roles are not enabled in this server.",
                color=0xff4757
            )
            return await ctx.reply(embed=embed)

        # Check if user is boosting
        if config['require_boost'] and not ctx.author.premium_since:
            embed = discord.Embed(
                title="💎 Boost Required",
                description="You need to be boosting this server to create a booster role!",
                color=0xff4757
            )
            return await ctx.reply(embed=embed)

        # Check if user already has a role
        existing = await self.get_user_role(ctx.guild.id, ctx.author.id)
        if existing:
            embed = discord.Embed(
                title="⚠️ Role Already Exists",
                description=f"You already have a booster role: <@&{existing['role_id']}>",
                color=0xffa502
            )
            return await ctx.reply(embed=embed)

        if not name:
            embed = discord.Embed(
                title="📝 Role Name Required",
                description="Please provide a name for your booster role.\n\n**Usage:** `br create <name>`",
                color=0xff6348
            )
            return await ctx.reply(embed=embed)

        # Validate name
        is_valid, error = self.validate_role_name(name, config)
        if not is_valid:
            embed = discord.Embed(
                title="❌ Invalid Name",
                description=error,
                color=0xff4757
            )
            return await ctx.reply(embed=embed)

        try:
            # Get base role for positioning
            base_role = ctx.guild.get_role(config['base_role_id']) if config['base_role_id'] else None
            position = base_role.position + 1 if base_role else 1

            # Create the role
            role = await ctx.guild.create_role(
                name=name,
                color=discord.Color.default(),
                reason=f"Booster role created for {ctx.author} ({ctx.author.id})"
            )

            # Position the role
            if base_role:
                await role.edit(position=position)

            # Add role to user
            await ctx.author.add_roles(role, reason="Booster role created")

            # Save to database
            await self.save_user_role(ctx.guild.id, ctx.author.id, role.id, name, 0)
            await self.log_action(ctx.guild.id, ctx.author.id, "role_created", f"Created role: {name}")

            embed = discord.Embed(
                title="✅ Booster Role Created",
                description=f"Successfully created your booster role: {role.mention}",
                color=0x2ed573
            )
            embed.add_field(name="Next Steps", value="Use `br color` to change color\nUse `br icon` to add an icon", inline=False)
            await ctx.reply(embed=embed)

        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Permission Error",
                description="I don't have permission to create roles.",
                color=0xff4757
            )
            await ctx.reply(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to create role: {str(e)}",
                color=0xff4757
            )
            await ctx.reply(embed=embed)

    @br.command(name="name")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def change_name(self, ctx, *, name: str):
        """Change your booster role name"""
        config = await self.get_config(ctx.guild.id)
        if not config or not config['enabled']:
            return await ctx.reply("❌ Booster roles are not enabled.")

        user_role = await self.get_user_role(ctx.guild.id, ctx.author.id)
        if not user_role:
            return await ctx.reply("❌ You don't have a booster role. Use `br create` first.")

        # Validate name
        is_valid, error = self.validate_role_name(name, config)
        if not is_valid:
            embed = discord.Embed(title="❌ Invalid Name", description=error, color=0xff4757)
            return await ctx.reply(embed=embed)

        try:
            role = ctx.guild.get_role(user_role['role_id'])
            if not role:
                await self.delete_user_role(ctx.guild.id, ctx.author.id)
                return await ctx.reply("❌ Your role no longer exists. Use `br create` to make a new one.")

            old_name = role.name
            await role.edit(name=name, reason=f"Name changed by {ctx.author}")
            await self.save_user_role(ctx.guild.id, ctx.author.id, role.id, name, role.color.value)
            await self.log_action(ctx.guild.id, ctx.author.id, "name_changed", f"'{old_name}' → '{name}'")

            embed = discord.Embed(
                title="✅ Name Updated",
                description=f"Role name changed to: **{name}**",
                color=0x2ed573
            )
            await ctx.reply(embed=embed)

        except discord.Forbidden:
            await ctx.reply("❌ I don't have permission to edit your role.")
        except Exception as e:
            await ctx.reply(f"❌ Error updating name: {str(e)}")

    @br.command(name="color")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def change_color(self, ctx, *, color: str):
        """Change your booster role color"""
        config = await self.get_config(ctx.guild.id)
        if not config or not config['enabled']:
            return await ctx.reply("❌ Booster roles are not enabled.")

        user_role = await self.get_user_role(ctx.guild.id, ctx.author.id)
        if not user_role:
            return await ctx.reply("❌ You don't have a booster role. Use `br create` first.")

        # Parse color
        try:
            if color.startswith('#'):
                color_value = int(color[1:], 16)
            elif color.startswith('0x'):
                color_value = int(color, 16)
            elif color.isdigit():
                color_value = int(color)
            elif len(color) == 6 and all(c in '0123456789abcdefABCDEF' for c in color):
                # Handle plain hex colors like "b4c468" or "ffffff"
                color_value = int(color, 16)
            else:
                # Try common color names
                color_names = {
                    'red': 0xff0000, 'blue': 0x0000ff, 'green': 0x00ff00,
                    'yellow': 0xffff00, 'purple': 0x800080, 'pink': 0xffc0cb,
                    'orange': 0xffa500, 'cyan': 0x00ffff, 'magenta': 0xff00ff,
                    'white': 0xffffff, 'black': 0x000000, 'gray': 0x808080
                }
                color_value = color_names.get(color.lower())
                if color_value is None:
                    raise ValueError("Unknown color")
            
            discord_color = discord.Color(color_value)
        except ValueError:
            embed = discord.Embed(
                title="❌ Invalid Color",
                description="Use hex (#ff0000 or ff0000), decimal (16711680), or color names (red, blue, etc.)",
                color=0xff4757
            )
            return await ctx.reply(embed=embed)

        try:
            role = ctx.guild.get_role(user_role['role_id'])
            if not role:
                await self.delete_user_role(ctx.guild.id, ctx.author.id)
                return await ctx.reply("❌ Your role no longer exists. Use `br create` to make a new one.")

            await role.edit(color=discord_color, reason=f"Color changed by {ctx.author}")
            await self.save_user_role(ctx.guild.id, ctx.author.id, role.id, role.name, color_value)
            await self.log_action(ctx.guild.id, ctx.author.id, "color_changed", f"Color: #{color_value:06x}")

            embed = discord.Embed(
                title="✅ Color Updated",
                description=f"Role color changed to: **#{color_value:06x}**",
                color=discord_color
            )
            await ctx.reply(embed=embed)

        except discord.Forbidden:
            await ctx.reply("❌ I don't have permission to edit your role.")
        except Exception as e:
            await ctx.reply(f"❌ Error updating color: {str(e)}")

    @br.command(name="icon")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def change_icon(self, ctx, *, icon: Optional[str] = None):
        """Set your booster role icon (emoji or image URL)"""
        config = await self.get_config(ctx.guild.id)
        if not config or not config['enabled']:
            return await ctx.reply("❌ Booster roles are not enabled.")
        
        if not config['icon_enabled']:
            return await ctx.reply("❌ Role icons are disabled in this server.")

        user_role = await self.get_user_role(ctx.guild.id, ctx.author.id)
        if not user_role:
            return await ctx.reply("❌ You don't have a booster role. Use `br create` first.")

        # Check server boost level
        if ctx.guild.premium_tier < 2:
            embed = discord.Embed(
                title="💎 Server Boost Level Required",
                description="The server needs to be Level 2+ boosted to use role icons.",
                color=0xff4757
            )
            return await ctx.reply(embed=embed)

        try:
            role = ctx.guild.get_role(user_role['role_id'])
            if not role:
                await self.delete_user_role(ctx.guild.id, ctx.author.id)
                return await ctx.reply("❌ Your role no longer exists. Use `br create` to make a new one.")

            # Handle icon removal
            if not icon or icon.lower() in ['none', 'remove', 'clear']:
                await role.edit(display_icon=None, reason=f"Icon removed by {ctx.author}")
                await self.save_user_role(ctx.guild.id, ctx.author.id, role.id, role.name, role.color.value, None)
                await self.log_action(ctx.guild.id, ctx.author.id, "icon_removed", "Icon removed")
                
                embed = discord.Embed(title="✅ Icon Removed", color=0x2ed573)
                return await ctx.reply(embed=embed)

            # Try to use as emoji first
            icon_bytes = None
            if icon.startswith('http'):
                # Download image from URL
                import aiohttp
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(icon) as resp:
                            if resp.status == 200:
                                icon_bytes = await resp.read()
                            else:
                                return await ctx.reply("❌ Could not download image from URL.")
                except:
                    return await ctx.reply("❌ Error downloading image.")
            else:
                # Try as emoji
                try:
                    # Check if it's a custom emoji
                    if icon.startswith('<') and icon.endswith('>'):
                        emoji_id = re.search(r':(\d+)>', icon)
                        if emoji_id:
                            emoji = self.bot.get_emoji(int(emoji_id.group(1)))
                            if emoji:
                                icon_bytes = await emoji.read()
                        else:
                            return await ctx.reply("❌ Invalid emoji format.")
                    else:
                        # Unicode emoji - convert to bytes
                        import aiohttp
                        emoji_url = f"https://twemoji.maxcdn.com/v/latest/72x72/{ord(icon[0]):x}.png"
                        try:
                            async with aiohttp.ClientSession() as session:
                                async with session.get(emoji_url) as resp:
                                    if resp.status == 200:
                                        icon_bytes = await resp.read()
                        except:
                            pass
                            
                    if not icon_bytes:
                        return await ctx.reply("❌ Could not process emoji/image.")
                except:
                    return await ctx.reply("❌ Invalid emoji or image.")

            if icon_bytes:
                await role.edit(display_icon=icon_bytes, reason=f"Icon changed by {ctx.author}")
                await self.save_user_role(ctx.guild.id, ctx.author.id, role.id, role.name, role.color.value, icon)
                await self.log_action(ctx.guild.id, ctx.author.id, "icon_changed", f"Icon: {icon}")
                
                embed = discord.Embed(title="✅ Icon Updated", color=0x2ed573)
                await ctx.reply(embed=embed)
            else:
                await ctx.reply("❌ Could not set icon.")

        except discord.Forbidden:
            await ctx.reply("❌ I don't have permission to edit role icons.")
        except Exception as e:
            await ctx.reply(f"❌ Error updating icon: {str(e)}")

    @br.command(name="delete", aliases=["remove"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def delete_role(self, ctx):
        """Delete your booster role"""
        user_role = await self.get_user_role(ctx.guild.id, ctx.author.id)
        if not user_role:
            return await ctx.reply("❌ You don't have a booster role to delete.")

        try:
            role = ctx.guild.get_role(user_role['role_id'])
            role_name = role.name if role else "Unknown Role"
            
            if role:
                await role.delete(reason=f"Booster role deleted by {ctx.author}")
            
            await self.delete_user_role(ctx.guild.id, ctx.author.id)
            await self.log_action(ctx.guild.id, ctx.author.id, "role_deleted", f"Deleted role: {role_name}")

            embed = discord.Embed(
                title="✅ Role Deleted",
                description="Your booster role has been deleted.",
                color=0x2ed573
            )
            await ctx.reply(embed=embed)

        except discord.Forbidden:
            await ctx.reply("❌ I don't have permission to delete your role.")
        except Exception as e:
            await ctx.reply(f"❌ Error deleting role: {str(e)}")

    @br.command(name="info")
    @blacklist_check()
    @ignore_check()
    async def role_info(self, ctx, member: Optional[discord.Member] = None):
        """View booster role information"""
        target = member or ctx.author
        user_role = await self.get_user_role(ctx.guild.id, target.id)
        
        if not user_role:
            name = "You don't" if target == ctx.author else f"{target.display_name} doesn't"
            return await ctx.reply(f"❌ {name} have a booster role.")

        role = ctx.guild.get_role(user_role['role_id'])
        if not role:
            await self.delete_user_role(ctx.guild.id, target.id)
            return await ctx.reply("❌ Role no longer exists.")

        embed = discord.Embed(
            title=f"🚀 {target.display_name}'s Booster Role",
            color=role.color
        )
        
        embed.add_field(name="Role", value=role.mention, inline=True)
        embed.add_field(name="Color", value=f"#{role.color.value:06x}", inline=True)
        embed.add_field(name="Created", value=f"<t:{int(datetime.fromisoformat(user_role['created_at']).timestamp())}:R>", inline=True)
        embed.add_field(name="Members", value=len(role.members), inline=True)
        embed.add_field(name="Position", value=role.position, inline=True)
        embed.add_field(name="Mentionable", value=role.mentionable, inline=True)
        
        if role.display_icon:
            embed.set_thumbnail(url=role.display_icon.url)
        
        await ctx.reply(embed=embed)

    # Admin Commands
    @br.command(name="setup")
    @commands.has_permissions(administrator=True)
    async def setup_booster_roles(self, ctx, base_role: Optional[discord.Role] = None):
        """Setup booster roles system"""
        if base_role and base_role >= ctx.guild.me.top_role:
            return await ctx.reply("❌ Base role must be below my highest role.")

        await self.update_config(
            ctx.guild.id,
            base_role_id=base_role.id if base_role else None,
            enabled=True
        )
        
        embed = discord.Embed(
            title="✅ Booster Roles Setup Complete",
            description=f"Base role: {base_role.mention if base_role else 'None'}\nSystem: **Enabled**",
            color=0x2ed573
        )
        embed.add_field(
            name="Next Steps",
            value="• Configure settings with `br config`\n• Users can now create roles with `br create`",
            inline=False
        )
        await ctx.reply(embed=embed)

    @br.command(name="config")
    @commands.has_permissions(administrator=True)
    async def view_config(self, ctx):
        """View booster roles configuration"""
        config = await self.get_config(ctx.guild.id)
        if not config:
            return await ctx.reply("❌ Booster roles not setup. Use `br setup` first.")

        base_role = ctx.guild.get_role(config['base_role_id']) if config['base_role_id'] else None
        
        embed = discord.Embed(title="⚙️ Booster Roles Configuration", color=self.color)
        embed.add_field(name="Status", value="✅ Enabled" if config['enabled'] else "❌ Disabled", inline=True)
        embed.add_field(name="Base Role", value=base_role.mention if base_role else "None", inline=True)
        embed.add_field(name="Require Boost", value="Yes" if config['require_boost'] else "No", inline=True)
        embed.add_field(name="Max Name Length", value=config['max_name_length'], inline=True)
        embed.add_field(name="Icons Enabled", value="Yes" if config['icon_enabled'] else "No", inline=True)
        embed.add_field(name="Auto Cleanup", value="Yes" if config['auto_cleanup'] else "No", inline=True)
        
        if config['prefix_required']:
            embed.add_field(name="Required Prefix", value=f"`{config['prefix_required']}`", inline=True)
        if config['suffix_required']:
            embed.add_field(name="Required Suffix", value=f"`{config['suffix_required']}`", inline=True)
        
        if config['blacklisted_words']:
            words = ", ".join(f"`{word}`" for word in config['blacklisted_words'][:5])
            if len(config['blacklisted_words']) > 5:
                words += f" +{len(config['blacklisted_words'])-5} more"
            embed.add_field(name="Blacklisted Words", value=words, inline=False)

        await ctx.reply(embed=embed)

    @br.command(name="toggle")
    @commands.has_permissions(administrator=True)
    async def toggle_system(self, ctx):
        """Enable/disable booster roles system"""
        config = await self.get_config(ctx.guild.id)
        if not config:
            return await ctx.reply("❌ Booster roles not setup. Use `br setup` first.")

        new_status = not config['enabled']
        await self.update_config(ctx.guild.id, enabled=new_status)
        
        status = "enabled" if new_status else "disabled"
        embed = discord.Embed(
            title=f"✅ System {status.title()}",
            description=f"Booster roles have been {status}.",
            color=0x2ed573 if new_status else 0xff4757
        )
        await ctx.reply(embed=embed)

    @br.command(name="cleanup")
    @commands.has_permissions(administrator=True)
    async def cleanup_roles(self, ctx):
        """Clean up unused booster roles"""
        config = await self.get_config(ctx.guild.id)
        if not config:
            return await ctx.reply("❌ Booster roles not setup.")

        # Get all user roles from database
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT user_id, role_id FROM user_booster_roles WHERE guild_id = ?",
                (ctx.guild.id,)
            )
            user_roles = await cursor.fetchall()

        cleaned = 0
        for user_id, role_id in user_roles:
            role = ctx.guild.get_role(role_id)
            member = ctx.guild.get_member(user_id)
            
            # Delete if role doesn't exist, user left, or user not boosting
            should_delete = (
                not role or
                not member or
                (config['require_boost'] and not member.premium_since)
            )
            
            if should_delete:
                if role:
                    try:
                        await role.delete(reason="Booster role cleanup")
                    except:
                        pass
                await self.delete_user_role(ctx.guild.id, user_id)
                cleaned += 1

        embed = discord.Embed(
            title="✅ Cleanup Complete",
            description=f"Cleaned up {cleaned} unused booster roles.",
            color=0x2ed573
        )
        await ctx.reply(embed=embed)

    @br.command(name="reset")
    @commands.has_permissions(administrator=True)
    async def reset_user_role(self, ctx, member: discord.Member):
        """Reset a user's booster role"""
        user_role = await self.get_user_role(ctx.guild.id, member.id)
        if not user_role:
            return await ctx.reply(f"❌ {member.display_name} doesn't have a booster role.")

        try:
            role = ctx.guild.get_role(user_role['role_id'])
            if role:
                await role.delete(reason=f"Role reset by {ctx.author}")
            
            await self.delete_user_role(ctx.guild.id, member.id)
            await self.log_action(ctx.guild.id, member.id, "role_reset", f"Reset by {ctx.author}", ctx.author.id)

            embed = discord.Embed(
                title="✅ Role Reset",
                description=f"Reset {member.display_name}'s booster role.",
                color=0x2ed573
            )
            await ctx.reply(embed=embed)

        except Exception as e:
            await ctx.reply(f"❌ Error resetting role: {str(e)}")

    @br.command(name="logs")
    @commands.has_permissions(administrator=True)
    async def view_logs(self, ctx, limit: int = 10):
        """View booster role activity logs"""
        if limit > 25:
            limit = 25

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT * FROM booster_logs WHERE guild_id = ? ORDER BY timestamp DESC LIMIT ?",
                (ctx.guild.id, limit)
            )
            logs = await cursor.fetchall()

        if not logs:
            return await ctx.reply("❌ No logs found.")

        embed = discord.Embed(title="📋 Booster Role Logs", color=self.color)
        
        for log in logs:
            user = self.bot.get_user(log[2])
            user_name = user.display_name if user else f"ID: {log[2]}"
            timestamp = f"<t:{int(datetime.fromisoformat(log[5]).timestamp())}:R>"
            
            embed.add_field(
                name=f"{log[3].replace('_', ' ').title()} - {user_name}",
                value=f"{log[4]}\n{timestamp}",
                inline=False
            )

        await ctx.reply(embed=embed)

    @br.group(name="set", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def br_set(self, ctx):
        """Configure booster role settings"""
        embed = discord.Embed(
            title="⚙️ Configuration Commands",
            color=self.color
        )
        embed.add_field(
            name="Available Settings",
            value=(
                "`br set maxlength <number>` - Max name length (1-100)\n"
                "`br set prefix <text>` - Required name prefix\n"
                "`br set suffix <text>` - Required name suffix\n"
                "`br set icons <on/off>` - Enable/disable role icons\n"
                "`br set boost <on/off>` - Require server boost\n"
                "`br set cleanup <on/off>` - Auto cleanup roles"
            ),
            inline=False
        )
        await ctx.reply(embed=embed)

    @br_set.command(name="maxlength")
    @commands.has_permissions(administrator=True)
    async def set_max_length(self, ctx, length: int):
        """Set maximum role name length"""
        if not 1 <= length <= 100:
            return await ctx.reply("❌ Length must be between 1 and 100 characters.")

        await self.update_config(ctx.guild.id, max_name_length=length)
        embed = discord.Embed(
            title="✅ Max Length Updated",
            description=f"Maximum role name length set to {length} characters.",
            color=0x2ed573
        )
        await ctx.reply(embed=embed)

    @br_set.command(name="prefix")
    @commands.has_permissions(administrator=True)
    async def set_prefix(self, ctx, *, prefix: Optional[str] = None):
        """Set required role name prefix"""
        if prefix and len(prefix) > 10:
            return await ctx.reply("❌ Prefix cannot be longer than 10 characters.")

        await self.update_config(ctx.guild.id, prefix_required=prefix)
        
        if prefix:
            description = f"Required prefix set to: `{prefix}`"
        else:
            description = "Required prefix removed."
        
        embed = discord.Embed(title="✅ Prefix Updated", description=description, color=0x2ed573)
        await ctx.reply(embed=embed)

    @br_set.command(name="suffix")
    @commands.has_permissions(administrator=True)
    async def set_suffix(self, ctx, *, suffix: Optional[str] = None):
        """Set required role name suffix"""
        if suffix and len(suffix) > 10:
            return await ctx.reply("❌ Suffix cannot be longer than 10 characters.")

        await self.update_config(ctx.guild.id, suffix_required=suffix)
        
        if suffix:
            description = f"Required suffix set to: `{suffix}`"
        else:
            description = "Required suffix removed."
        
        embed = discord.Embed(title="✅ Suffix Updated", description=description, color=0x2ed573)
        await ctx.reply(embed=embed)

    @br_set.command(name="icons")
    @commands.has_permissions(administrator=True)
    async def set_icons(self, ctx, setting: str):
        """Enable or disable role icons"""
        if setting.lower() not in ['on', 'off', 'enable', 'disable', 'true', 'false']:
            return await ctx.reply("❌ Use `on` or `off` to enable/disable icons.")

        enabled = setting.lower() in ['on', 'enable', 'true']
        await self.update_config(ctx.guild.id, icon_enabled=enabled)
        
        status = "enabled" if enabled else "disabled"
        embed = discord.Embed(
            title="✅ Icons Setting Updated",
            description=f"Role icons have been {status}.",
            color=0x2ed573
        )
        await ctx.reply(embed=embed)

    @br_set.command(name="boost")
    @commands.has_permissions(administrator=True)
    async def set_boost_requirement(self, ctx, setting: str):
        """Set whether server boost is required"""
        if setting.lower() not in ['on', 'off', 'enable', 'disable', 'true', 'false']:
            return await ctx.reply("❌ Use `on` or `off` to require/not require boost.")

        required = setting.lower() in ['on', 'enable', 'true']
        await self.update_config(ctx.guild.id, require_boost=required)
        
        status = "required" if required else "not required"
        embed = discord.Embed(
            title="✅ Boost Requirement Updated",
            description=f"Server boost is now {status} for booster roles.",
            color=0x2ed573
        )
        await ctx.reply(embed=embed)

    @br_set.command(name="cleanup")
    @commands.has_permissions(administrator=True)
    async def set_auto_cleanup(self, ctx, setting: str):
        """Set automatic cleanup of unused roles"""
        if setting.lower() not in ['on', 'off', 'enable', 'disable', 'true', 'false']:
            return await ctx.reply("❌ Use `on` or `off` to enable/disable auto cleanup.")

        enabled = setting.lower() in ['on', 'enable', 'true']
        await self.update_config(ctx.guild.id, auto_cleanup=enabled)
        
        status = "enabled" if enabled else "disabled"
        embed = discord.Embed(
            title="✅ Auto Cleanup Updated",
            description=f"Automatic cleanup has been {status}.",
            color=0x2ed573
        )
        await ctx.reply(embed=embed)

    @br.group(name="blacklist", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def blacklist_group(self, ctx):
        """Manage blacklisted words"""
        config = await self.get_config(ctx.guild.id)
        if not config:
            return await ctx.reply("❌ Booster roles not setup.")

        embed = discord.Embed(title="🚫 Blacklisted Words", color=self.color)
        
        if config['blacklisted_words']:
            words = "\n".join(f"• {word}" for word in config['blacklisted_words'])
            embed.description = f"```\n{words}\n```"
        else:
            embed.description = "No blacklisted words."
        
        embed.add_field(
            name="Commands",
            value="`br blacklist add <word>` - Add word\n`br blacklist remove <word>` - Remove word",
            inline=False
        )
        await ctx.reply(embed=embed)

    @blacklist_group.command(name="add")
    @commands.has_permissions(administrator=True)
    async def blacklist_add(self, ctx, *, word: str):
        """Add a word to the blacklist"""
        if len(word) > 50:
            return await ctx.reply("❌ Blacklisted word cannot be longer than 50 characters.")

        config = await self.get_config(ctx.guild.id)
        if not config:
            return await ctx.reply("❌ Booster roles not setup.")

        blacklist = config['blacklisted_words']
        if word.lower() in [w.lower() for w in blacklist]:
            return await ctx.reply("❌ Word is already blacklisted.")

        if len(blacklist) >= 50:
            return await ctx.reply("❌ Cannot have more than 50 blacklisted words.")

        blacklist.append(word)
        await self.update_config(ctx.guild.id, blacklisted_words=blacklist)

        embed = discord.Embed(
            title="✅ Word Blacklisted",
            description=f"Added `{word}` to the blacklist.",
            color=0x2ed573
        )
        await ctx.reply(embed=embed)

    @blacklist_group.command(name="remove")
    @commands.has_permissions(administrator=True)
    async def blacklist_remove(self, ctx, *, word: str):
        """Remove a word from the blacklist"""
        config = await self.get_config(ctx.guild.id)
        if not config:
            return await ctx.reply("❌ Booster roles not setup.")

        blacklist = config['blacklisted_words']
        
        # Find and remove the word (case insensitive)
        removed = None
        for i, blacklisted_word in enumerate(blacklist):
            if blacklisted_word.lower() == word.lower():
                removed = blacklist.pop(i)
                break
        
        if not removed:
            return await ctx.reply("❌ Word is not in the blacklist.")

        await self.update_config(ctx.guild.id, blacklisted_words=blacklist)

        embed = discord.Embed(
            title="✅ Word Removed",
            description=f"Removed `{removed}` from the blacklist.",
            color=0x2ed573
        )
        await ctx.reply(embed=embed)

    @br.command(name="stats")
    @commands.has_permissions(manage_guild=True)
    async def booster_stats(self, ctx):
        """View booster role statistics"""
        async with aiosqlite.connect(self.db_path) as db:
            # Total roles
            cursor = await db.execute(
                "SELECT COUNT(*) FROM user_booster_roles WHERE guild_id = ?",
                (ctx.guild.id,)
            )
            result = await cursor.fetchone()
            total_roles = result[0] if result else 0
            
            # Recent activity
            cursor = await db.execute(
                "SELECT COUNT(*) FROM booster_logs WHERE guild_id = ? AND timestamp > datetime('now', '-7 days')",
                (ctx.guild.id,)
            )
            result = await cursor.fetchone()
            recent_activity = result[0] if result else 0
            
            # Most common actions
            cursor = await db.execute(
                "SELECT action, COUNT(*) as count FROM booster_logs WHERE guild_id = ? GROUP BY action ORDER BY count DESC LIMIT 3",
                (ctx.guild.id,)
            )
            common_actions = await cursor.fetchall()

        embed = discord.Embed(title="📊 Booster Role Statistics", color=self.color)
        embed.add_field(name="Total Roles", value=total_roles, inline=True)
        embed.add_field(name="Active Boosters", value=len([m for m in ctx.guild.members if m.premium_since]), inline=True)
        embed.add_field(name="Recent Activity (7d)", value=recent_activity, inline=True)
        
        if common_actions:
            actions_text = "\n".join(f"{action.replace('_', ' ').title()}: {count}" for action, count in common_actions)
            embed.add_field(name="Common Actions", value=actions_text, inline=False)

        await ctx.reply(embed=embed)

    # ========== BOOSTER MESSAGES ==========
    @br.group(name="message", invoke_without_command=True, aliases=["msg"])
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def br_message(self, ctx):
        """Manage booster messages"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @br_message.command(name="setup", help="Configure a booster message for when members boost the server.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 6, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def br_message_setup(self, ctx):
        """Setup booster messages"""
        async with aiosqlite.connect("db/booster_messages.db") as db:
            async with db.execute("SELECT * FROM booster_messages WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()
        
        if row:
            error = discord.Embed(
                description=f"A booster message has already been set in {ctx.guild.name}. Use `{ctx.prefix}br message reset` to reconfigure.",
                color=0x006fb9
            )
            error.set_author(name="Error", icon_url="https://cdn.discordapp.com/emojis/1294218790082711553.png")
            return await ctx.send(embed=error)
            
        options_view = View(timeout=600)

        async def option_callback(interaction: discord.Interaction, button: Button):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You cannot interact with this setup.", ephemeral=True)
                return
            await interaction.response.defer()

            if button.custom_id == "simple":
                if interaction.message is not None:
                    await interaction.message.delete()
                await self.simple_booster_setup(ctx)
            elif button.custom_id == "embed":
                if interaction.message is not None:
                    await interaction.message.delete()
                await self.embed_booster_setup(ctx)
            elif button.custom_id == "cancel":
                if interaction.message is not None:
                    await interaction.message.delete()

        button_simple = Button(label="Simple", style=discord.ButtonStyle.success, custom_id="simple")
        button_simple.callback = lambda interaction: option_callback(interaction, button_simple)
        options_view.add_item(button_simple)

        button_embed = Button(label="Embed", style=discord.ButtonStyle.success, custom_id="embed")
        button_embed.callback = lambda interaction: option_callback(interaction, button_embed)
        options_view.add_item(button_embed)

        button_cancel = Button(label="Cancel", style=discord.ButtonStyle.danger, custom_id="cancel")
        button_cancel.callback = lambda interaction: option_callback(interaction, button_cancel)
        options_view.add_item(button_cancel)

        setup_embed = discord.Embed(
            title="🚀 Booster Message Setup",
            description="Choose the type of booster message to create:",
            color=0x006fb9
        )
        setup_embed.add_field(
            name="**Simple**",
            value="A basic text message with variables.",
            inline=True
        )
        setup_embed.add_field(
            name="**Embed**",
            value="A rich embed with custom formatting.",
            inline=True
        )
        setup_embed.set_footer(text="This will timeout in 10 minutes.")
        
        await ctx.send(embed=setup_embed, view=options_view)

    async def simple_booster_setup(self, ctx):
        """Setup simple booster message"""
        setup_embed = discord.Embed(
            title="🚀 Simple Booster Message Setup",
            description="Please provide the booster message content.\n\n**Available Variables:**\n`{user}` - User mention\n`{user_name}` - User's name\n`{user_id}` - User's ID\n`{user_avatar}` - User's avatar URL\n`{user_nick}` - User's display name\n`{user_boost_date}` - When user started boosting\n`{server_name}` - Server name\n`{server_id}` - Server ID\n`{server_boost_count}` - Total boost count\n`{server_boost_level}` - Boost level\n`{server_icon}` - Server icon URL\n`{timestamp}` - Current timestamp",
            color=0x006fb9
        )
        
        await ctx.send(embed=setup_embed)
        
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel
        
        try:
            message = await self.bot.wait_for('message', timeout=600.0, check=check)
        except:
            timeout_embed = discord.Embed(
                title="⏰ Timeout", 
                description="Setup timed out. Please try again.", 
                color=0xff4757
            )
            return await ctx.send(embed=timeout_embed)

        # Get channel for booster messages
        channel_embed = discord.Embed(
            title="📍 Channel Selection",
            description="Please mention the channel where booster messages should be sent.",
            color=0x006fb9
        )
        await ctx.send(embed=channel_embed)
        
        try:
            channel_msg = await self.bot.wait_for('message', timeout=300.0, check=check)
            if channel_msg.channel_mentions:
                channel = channel_msg.channel_mentions[0]
            else:
                channel = ctx.channel
        except:
            channel = ctx.channel

        # Save to database
        async with aiosqlite.connect("db/booster_messages.db") as db:
            await db.execute("""
                INSERT INTO booster_messages 
                (guild_id, message_type, message_content, channel_id) 
                VALUES (?, ?, ?, ?)
            """, (ctx.guild.id, "simple", message.content, channel.id))
            await db.commit()

        success_embed = discord.Embed(
            title="✅ Booster Message Setup Complete",
            description=f"Simple booster message has been configured for {channel.mention}!",
            color=0x00ff00
        )
        await ctx.send(embed=success_embed)

    async def embed_booster_setup(self, ctx):
        """Setup embed booster message"""
        setup_embed = discord.Embed(
            title="🚀 Embed Booster Message Setup", 
            color=0x006fb9
        )
        setup_embed.add_field(
            name="📝 Instructions",
            value="I'll guide you through creating a custom embed for booster messages.\n\n**Available Variables:**\n`{user}` - User mention\n`{user_name}` - User's name\n`{user_id}` - User's ID\n`{user_avatar}` - User's avatar URL\n`{user_nick}` - User's display name\n`{user_boost_date}` - When user started boosting\n`{server_name}` - Server name\n`{server_id}` - Server ID\n`{server_boost_count}` - Total boost count\n`{server_boost_level}` - Boost level\n`{server_icon}` - Server icon URL\n`{timestamp}` - Current timestamp",
            inline=False
        )
        
        await ctx.send(embed=setup_embed)

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        embed_data = {}

        # Get embed title
        title_embed = discord.Embed(title="📋 Embed Title", description="Enter the embed title (or 'skip' to skip):", color=0x006fb9)
        await ctx.send(embed=title_embed)
        try:
            title_msg = await self.bot.wait_for('message', timeout=300.0, check=check)
            embed_data['title'] = title_msg.content if title_msg.content.lower() != 'skip' else ""
        except:
            embed_data['title'] = ""

        # Get embed description
        desc_embed = discord.Embed(title="📝 Embed Description", description="Enter the embed description (or 'skip' to skip):", color=0x006fb9)
        await ctx.send(embed=desc_embed)
        try:
            desc_msg = await self.bot.wait_for('message', timeout=300.0, check=check)
            embed_data['description'] = desc_msg.content if desc_msg.content.lower() != 'skip' else ""
        except:
            embed_data['description'] = ""

        # Get embed color
        color_embed = discord.Embed(title="🎨 Embed Color", description="Enter a hex color (e.g., #ff0000) or 'skip' for default:", color=0x006fb9)
        await ctx.send(embed=color_embed)
        try:
            color_msg = await self.bot.wait_for('message', timeout=300.0, check=check)
            if color_msg.content.lower() != 'skip':
                embed_data['color'] = color_msg.content
            else:
                embed_data['color'] = "#006fb9"
        except:
            embed_data['color'] = "#006fb9"

        # Get optional message content
        msg_embed = discord.Embed(title="💬 Message Content", description="Enter optional message content above the embed (or 'skip' to skip):", color=0x006fb9)
        await ctx.send(embed=msg_embed)
        try:
            msg_content = await self.bot.wait_for('message', timeout=300.0, check=check)
            embed_data['message'] = msg_content.content if msg_content.content.lower() != 'skip' else ""
        except:
            embed_data['message'] = ""

        # Get channel
        channel_embed = discord.Embed(title="📍 Channel Selection", description="Please mention the channel where booster messages should be sent:", color=0x006fb9)
        await ctx.send(embed=channel_embed)
        try:
            channel_msg = await self.bot.wait_for('message', timeout=300.0, check=check)
            if channel_msg.channel_mentions:
                channel = channel_msg.channel_mentions[0]
            else:
                channel = ctx.channel
        except:
            channel = ctx.channel

        # Save to database
        async with aiosqlite.connect("db/booster_messages.db") as db:
            await db.execute("""
                INSERT INTO booster_messages 
                (guild_id, message_type, message_content, channel_id, embed_data) 
                VALUES (?, ?, ?, ?, ?)
            """, (ctx.guild.id, "embed", embed_data.get('message', ''), channel.id, json.dumps(embed_data)))
            await db.commit()

        success_embed = discord.Embed(
            title="✅ Booster Message Setup Complete",
            description=f"Embed booster message has been configured for {channel.mention}!",
            color=0x00ff00
        )
        await ctx.send(embed=success_embed)

    @br_message.command(name="reset", aliases=["disable"], help="Reset and disable booster messages.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def br_message_reset(self, ctx):
        """Reset booster messages"""
        async with aiosqlite.connect("db/booster_messages.db") as db:
            result = await db.execute("DELETE FROM booster_messages WHERE guild_id = ?", (ctx.guild.id,))
            await db.commit()
            
        if result.rowcount > 0:
            embed = discord.Embed(
                title="✅ Booster Messages Reset",
                description="Booster messages have been disabled and reset for this server.",
                color=0x00ff00
            )
        else:
            embed = discord.Embed(
                title="❌ No Configuration Found",
                description="No booster message configuration was found for this server.",
                color=0xff4757
            )
        await ctx.send(embed=embed)

    @br_message.command(name="channel", help="Set the channel for booster messages.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def br_message_channel(self, ctx, channel: Optional[discord.TextChannel] = None):
        """Set booster message channel"""
        if channel is None:
            channel = ctx.channel
            
        # Validate that we have a valid channel
        if channel is None:
            embed = discord.Embed(
                title="❌ Invalid Channel",
                description="Please specify a valid text channel or run this command in a text channel.",
                color=0xff4757
            )
            return await ctx.send(embed=embed)

        async with aiosqlite.connect("db/booster_messages.db") as db:
            async with db.execute("SELECT * FROM booster_messages WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()
            
            if not row:
                embed = discord.Embed(
                    title="❌ No Configuration",
                    description="No booster message configuration found. Use `br message setup` first.",
                    color=0xff4757
                )
                return await ctx.send(embed=embed)
            
            await db.execute("UPDATE booster_messages SET channel_id = ? WHERE guild_id = ?", (channel.id, ctx.guild.id))
            await db.commit()

        embed = discord.Embed(
            title="✅ Channel Updated",
            description=f"Booster messages will now be sent to {channel.mention}.",
            color=0x00ff00
        )
        await ctx.send(embed=embed)

    @br_message.command(name="test", help="Test the booster message.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def br_message_test(self, ctx):
        """Test booster message"""
        async with aiosqlite.connect("db/booster_messages.db") as db:
            async with db.execute("SELECT * FROM booster_messages WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()
        
        if not row:
            embed = discord.Embed(
                title="❌ No Configuration",
                description="No booster message configuration found. Use `br message setup` first.",
                color=0xff4757
            )
            return await ctx.send(embed=embed)

        message_type, message_content, channel_id, embed_data = row[1], row[2], row[3], row[4]
        channel = self.bot.get_channel(channel_id)
        if not channel:
            embed = discord.Embed(
                title="❌ Channel Not Found",
                description="The configured channel no longer exists. Please set a new channel.",
                color=0xff4757
            )
            return await ctx.send(embed=embed)

        # Create test placeholders
        from utils.timezone_helpers import get_timezone_helpers
        tz_helpers = get_timezone_helpers(self.bot)
        
        user_boost_date = await tz_helpers.format_datetime_for_guild(
            discord.utils.utcnow(), ctx.guild.id, "%a, %b %d, %Y"
        )
        
        placeholders = {
            "user": ctx.author.mention,
            "user_avatar": ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url,
            "user_name": ctx.author.name,
            "user_id": ctx.author.id,
            "user_nick": ctx.author.display_name,
            "user_boost_date": user_boost_date,
            "server_name": ctx.guild.name,
            "server_id": ctx.guild.id,
            "server_boost_count": ctx.guild.premium_subscription_count,
            "server_boost_level": ctx.guild.premium_tier,
            "server_icon": ctx.guild.icon.url if ctx.guild.icon else "https://cdn.discordapp.com/embed/avatars/0.png",
            "timestamp": discord.utils.format_dt(discord.utils.utcnow())
        }

        try:
            if message_type == "simple":
                content = await self.safe_format(message_content, placeholders)
                await channel.send(content=f"**🧪 TEST MESSAGE**\n{content}")
            elif message_type == "embed":
                embed_info = json.loads(embed_data) if embed_data else {}
                color_value = embed_info.get("color", "#006fb9")
                embed_color = 0x006fb9
                if color_value and isinstance(color_value, str) and color_value.startswith("#"):
                    embed_color = discord.Color(int(color_value.lstrip("#"), 16))
                
                content = await self.safe_format(embed_info.get("message", ""), placeholders) or None
                embed = discord.Embed(
                    title=await self.safe_format(embed_info.get("title", ""), placeholders),
                    description=await self.safe_format(embed_info.get("description", ""), placeholders),
                    color=embed_color
                )
                embed.timestamp = discord.utils.utcnow()
                
                test_content = f"**🧪 TEST MESSAGE**\n{content}" if content else "**🧪 TEST MESSAGE**"
                await channel.send(content=test_content, embed=embed)
            
            success_embed = discord.Embed(
                title="✅ Test Sent",
                description=f"Test booster message sent to {channel.mention}!",
                color=0x00ff00
            )
            await ctx.send(embed=success_embed)
            
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Test Failed",
                description=f"Failed to send test message: {str(e)}",
                color=0xff4757
            )
            await ctx.send(embed=error_embed)

    @br_message.command(name="config", help="Show current booster message configuration.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def br_message_config(self, ctx):
        """Show booster message configuration"""
        async with aiosqlite.connect("db/booster_messages.db") as db:
            async with db.execute("SELECT * FROM booster_messages WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()
        
        if not row:
            embed = discord.Embed(
                title="❌ No Configuration",
                description="No booster message configuration found. Use `br message setup` to get started.",
                color=0xff4757
            )
            return await ctx.send(embed=embed)

        message_type, message_content, channel_id, embed_data, auto_delete = row[1], row[2], row[3], row[4], row[5] if len(row) > 5 else None
        channel = self.bot.get_channel(channel_id)
        
        embed = discord.Embed(
            title="🚀 Booster Message Configuration",
            color=0x006fb9
        )
        
        embed.add_field(
            name="📍 Channel",
            value=channel.mention if channel else "❌ Channel not found",
            inline=True
        )
        
        embed.add_field(
            name="📝 Type",
            value=message_type.title(),
            inline=True
        )
        
        if auto_delete:
            embed.add_field(
                name="⏰ Auto Delete",
                value=f"{auto_delete} seconds",
                inline=True
            )
        
        if message_type == "simple":
            embed.add_field(
                name="💬 Message Content",
                value=f"```{message_content[:500]}{'...' if len(message_content) > 500 else ''}```",
                inline=False
            )
        elif message_type == "embed" and embed_data:
            try:
                embed_info = json.loads(embed_data)
                if embed_info.get("title"):
                    embed.add_field(
                        name="📋 Embed Title",
                        value=embed_info["title"][:100] + ("..." if len(embed_info["title"]) > 100 else ""),
                        inline=False
                    )
                if embed_info.get("description"):
                    embed.add_field(
                        name="📝 Embed Description",
                        value=embed_info["description"][:200] + ("..." if len(embed_info["description"]) > 200 else ""),
                        inline=False
                    )
            except:
                embed.add_field(
                    name="❌ Embed Data",
                    value="Error parsing embed data",
                    inline=False
                )
        
        await ctx.send(embed=embed)

    async def safe_format(self, text, placeholders):
        """Safely format text with placeholders"""
        placeholders_lower = {k.lower(): v for k, v in placeholders.items()}
        def replace_var(match):
            var_name = match.group(1).lower()
            return str(placeholders_lower.get(var_name, f"{{{var_name}}}"))
        return re.sub(r"\{(\w+)\}", replace_var, text or "")

    # Error handling
    @br.error
    async def br_error(self, ctx, error):
        """Error handler for br command group"""
        if isinstance(error, commands.CommandOnCooldown):
            embed = discord.Embed(
                title="⏰ Cooldown",
                description=f"Try again in {error.retry_after:.1f} seconds.",
                color=0xff6348
            )
            await ctx.reply(embed=embed, delete_after=5)
        elif isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="You need administrator permissions for this command.",
                color=0xff4757
            )
            await ctx.reply(embed=embed)

async def setup(bot):
    await bot.add_cog(BoosterRoles(bot))