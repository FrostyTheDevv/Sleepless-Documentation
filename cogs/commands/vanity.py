import discord
from discord.ext import commands
import sqlite3
import aiosqlite
import json
import os
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import re
from utils.Tools import *

from utils.error_helpers import StandardErrorHandler
def validate_color(color_input: str) -> Optional[int]:
    """Enhanced color validation supporting hex codes, color names, and RGB values"""
    if not color_input:
        return None
    
    color_input = color_input.strip().lower()
    
    # Named colors
    color_names = {
        'red': 0xFF0000, 'blue': 0x0000FF, 'green': 0x00FF00, 'yellow': 0xFFFF00,
        'orange': 0xFFA500, 'purple': 0x800080, 'pink': 0xFFC0CB, 'cyan': 0x00FFFF,
        'magenta': 0xFF00FF, 'lime': 0x00FF00, 'teal': 0x008080, 'navy': 0x000080,
        'maroon': 0x800000, 'olive': 0x808000, 'silver': 0xC0C0C0, 'gray': 0x808080,
        'grey': 0x808080, 'black': 0x000000, 'white': 0xFFFFFF, 'aqua': 0x00FFFF,
        'fuchsia': 0xFF00FF, 'discord': 0x5865F2, 'blurple': 0x5865F2, 'greyple': 0x99AAB5,
        'dark_theme': 0x36393F, 'light_theme': 0xF2F3F5, 'gold': 0xFFD700, 'embed': 0x2F3136
    }
    
    if color_input in color_names:
        return color_names[color_input]
    
    # Hex color codes
    hex_match = re.match(r'^#?([a-f0-9]{6}|[a-f0-9]{3})$', color_input)
    if hex_match:
        hex_code = hex_match.group(1)
        if len(hex_code) == 3:
            hex_code = ''.join(c*2 for c in hex_code)
        return int(hex_code, 16)
    
    # RGB values
    rgb_match = re.match(r'^rgb\((\d+),\s*(\d+),\s*(\d+)\)$', color_input)
    if rgb_match:
        r, g, b = map(int, rgb_match.groups())
        if all(0 <= val <= 255 for val in [r, g, b]):
            return (r << 16) + (g << 8) + b
    
    # Decimal color values
    if color_input.isdigit():
        value = int(color_input)
        if 0 <= value <= 0xFFFFFF:
            return value
    
    return None

def replace_variables(text: str, **kwargs) -> str:
    """Enhanced variable replacement with all supported variables"""
    if not text:
        return text
    
    # Default variables
    variables = {
        # User variables
        'user': kwargs.get('user', 'Unknown User'),
        'mention': kwargs.get('mention', '@Unknown'),
        'user_avatar': kwargs.get('user_avatar', 'https://cdn.discordapp.com/embed/avatars/0.png'),
        'user_nick': kwargs.get('user_nick', 'Unknown User'),
        'user_id': kwargs.get('user_id', '123456789'),
        
        # Server variables
        'server': kwargs.get('server', 'Unknown Server'),
        'guild': kwargs.get('server', 'Unknown Server'),  # Alias
        'server_icon': kwargs.get('server_icon', 'https://cdn.discordapp.com/embed/avatars/0.png'),
        'server_id': kwargs.get('server_id', '123456789'),
        'server_boostcount': kwargs.get('server_boostcount', '0'),
        'server_boostlevel': kwargs.get('server_boostlevel', '0'),
        'member_count': kwargs.get('member_count', '1'),
        
        # Vanity specific
        'vanity': kwargs.get('vanity', 'example'),
        'rep_count': kwargs.get('rep_count', '1'),
        'channel': kwargs.get('channel', '#general'),
        'keyword': kwargs.get('keyword', 'example'),
        
        # System variables
        'date': kwargs.get('date', datetime.now().strftime('%B %d, %Y')),
        'time': kwargs.get('time', datetime.now().strftime('%I:%M %p')),
        'timestamp': kwargs.get('timestamp', f'<t:{int(datetime.now().timestamp())}:R>'),
        'bot_name': kwargs.get('bot_name', 'Sleepless'),
        'prefix': kwargs.get('prefix', '!'),
        'invite': kwargs.get('invite', 'discord.gg/example')
    }
    
    # Replace all variables
    for var, value in variables.items():
        text = text.replace(f'{{{var}}}', str(value))
    
    return text

class VanityHelpView(discord.ui.View):
    """Paginated help view for vanity system"""
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
            title="<:vanity:1428163639814389771> Advanced Vanity System",
            description="**Complete server repping and vanity URL management**\n\nFull-featured vanity system with auto-responder, analytics, and custom embeds.",
            color=0x1ABC9C
        )
        
        embed.add_field(
            name="<:sleep_dot:1427471567838777347> **Quick Start**",
            value="<:sleep_dot:1427471567838777347> `vanity setup` - Interactive setup wizard\n<:sleep_dot:1427471567838777347> **Features:** Custom URLs, auto-responder, analytics, and role management!",
            inline=False
        )
        
        embed.add_field(
            name="<:cloud1:1427471615473750039> **Core Management**",
            value="<:sleep_dot:1427471567838777347> `vanity url <custom>` - Set vanity URL\n<:sleep_dot:1427471567838777347> `vanity role <role>` - Set vanity role\n<:sleep_dot:1427471567838777347> `vanity config` - View configuration\n<:sleep_dot:1427471567838777347> `vanity reset` - Reset all settings",
            inline=False
        )
        
        embed.set_footer(text=f"• Help page 1/{4} | Requested by: {self.ctx.author.display_name}",
                        icon_url=self.ctx.bot.user.avatar.url)
        pages.append(embed)
        
        # Auto-Responder Page
        embed = discord.Embed(
            title="<:clock1:1427471544409657354> Auto-Responder System",
            color=0x1ABC9C
        )
        embed.add_field(
            name="<:bot:1428163130663375029> vanity responder enable",
            value="Enable automatic responses to pic permission requests.\n**Example:** `vanity responder enable`",
            inline=False
        )
        embed.add_field(
            name="<:bot:1428163130663375029> vanity responder disable",
            value="Disable the auto-responder system.\n**Example:** `vanity responder disable`",
            inline=False
        )
        embed.add_field(
            name="<:tchat:1430364431195570198> vanity keywords add <word>",
            value="Add trigger keywords for auto-responses.\n**Example:** `vanity keywords add rep` or `vanity keywords add role`",
            inline=False
        )
        embed.add_field(
            name="<:tchat:1430364431195570198> vanity message <text>",
            value="Set custom response message with variables.\n**Example:** `vanity message <:vanity:1428163639814389771> Rep {vanity} to earn your vanity role! <:sleep_customrole:1427471561085943988>`",
            inline=False
        )
        embed.set_footer(text=f"• Help page 2/{4} | Requested by: {self.ctx.author.display_name}",
                        icon_url=self.ctx.bot.user.avatar.url)
        pages.append(embed)
        
        # Customization & Embeds Page
        embed = discord.Embed(
            title="<:web:1428162947187736679> Customization & Embeds",
            color=0x1ABC9C
        )
        embed.add_field(
            name="<:confetti:1428163119187890358> vanity embed color <hex>",
            value="Set embed color for auto-responder.\n**Example:** `vanity embed color #1ABC9C`",
            inline=False
        )
        embed.add_field(
            name="<:file:1427471573304217651> vanity embed title <text>",
            value="Set custom embed title with variables.\n**Example:** `vanity embed title Thanks {user}! 🎉`",
            inline=False
        )
        embed.add_field(
            name="<:tchat:1430364431195570198> vanity channel setup",
            value="Configure channel message embeds with full customization.\n**Example:** `vanity channel setup`",
            inline=False
        )
        embed.add_field(
            name="<:skull1:1428168178936188968> vanity embed reset",
            value="Reset all embed settings to defaults.\n**Example:** `vanity embed reset`",
            inline=False
        )
        embed.set_footer(text=f"• Help page 3/{4} | Requested by: {self.ctx.author.display_name}",
                        icon_url=self.ctx.bot.user.avatar.url)
        pages.append(embed)
        
        # Analytics & Variables Page
        embed = discord.Embed(
            title="<:ppl:1427471598578958386> Analytics & Variables",
            color=0x1ABC9C
        )
        embed.add_field(
            name="<:slash:1428164524372000879> vanity stats",
            value="View comprehensive server rep statistics and analytics.\n**Example:** `vanity stats`",
            inline=False
        )
        embed.add_field(
            name="<:plusu:1428164526884257852> vanity leaderboard",
            value="Show top rep contributors leaderboard.\n**Example:** `vanity leaderboard`",
            inline=False
        )
        embed.add_field(
            name="<:web:1428162947187736679> **Available Variables**",
            value="<:sleep_dot:1427471567838777347> `{user}` - User mention\n<:sleep_dot:1427471567838777347> `{server}` - Server name\n<:sleep_dot:1427471567838777347> `{vanity}` - Vanity URL\n<:sleep_dot:1427471567838777347> `{channel}` - Channel mention\n<:sleep_dot:1427471567838777347> `{keyword}` - Trigger keyword\n<:sleep_dot:1427471567838777347> `{rep_count}` - User's total reps",
            inline=False
        )
        embed.add_field(
            name="<:woah:1428170830042632292> **Pro Tips**",
            value="<:sleep_dot:1427471567838777347> Use variables in titles, descriptions, and messages\n<:sleep_dot:1427471567838777347> Keywords trigger vanity role auto-responder\n<:sleep_dot:1427471567838777347> Channel setup creates beautiful embed messages\n<:sleep_dot:1427471567838777347> Analytics track user engagement and role distribution",
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

class VanityDatabase:
    """Database handler for vanity system"""
    
    def __init__(self, db_path: str = "db/vanity.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._create_tables()
    
    def _create_tables(self):
        """Create database tables with migration support"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Main vanity configuration table with proper migration
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS vanity_config (
                    guild_id INTEGER PRIMARY KEY,
                    vanity_url TEXT,
                    vanity_role_id INTEGER,
                    rep_channel_id INTEGER,
                    auto_responder BOOLEAN DEFAULT 0,
                    custom_message TEXT,
                    embed_color INTEGER DEFAULT 1752220,
                    embed_title TEXT,
                    embed_description TEXT,
                    embed_thumbnail TEXT,
                    embed_image TEXT,
                    embed_footer TEXT,
                    channel_message_data TEXT,
                    channel_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Add missing columns if they don't exist (for existing databases)
            try:
                cursor.execute("ALTER TABLE vanity_config ADD COLUMN channel_message_data TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            try:
                cursor.execute("ALTER TABLE vanity_config ADD COLUMN channel_id INTEGER")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            # Vanity statistics table - correct schema
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS vanity_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    user_id INTEGER,
                    rep_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    keyword_used TEXT
                )
            ''')
            
            # Vanity logs table  
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS vanity_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    user_id INTEGER,
                    action TEXT,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Auto-responder keywords table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS vanity_keywords (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    keyword TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()

class VanityView(discord.ui.View):
    """Interactive view for vanity setup"""
    
    def __init__(self, ctx, db_instance=None, timeout=300):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.db = db_instance
        self.config = {}
    
    @discord.ui.button(label="🔗 Set Vanity URL", style=discord.ButtonStyle.primary)
    async def set_vanity_url(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("Only the command user can interact!", ephemeral=True)
            return
        
        modal = VanityURLModal(self.config)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🎭 Setup Role", style=discord.ButtonStyle.secondary)
    async def setup_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("Only the command user can interact!", ephemeral=True)
            return
        
        modal = VanityRoleModal(self.config, interaction.guild)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="💬 Auto Responder", style=discord.ButtonStyle.success)
    async def auto_responder(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("Only the command user can interact!", ephemeral=True)
            return
        
        # Create a simple toggle view for auto responder
        view = AutoResponderToggleView(self.config, interaction.guild)
        embed = discord.Embed(
            title="💬 Auto Responder Setup",
            description="Choose how you want to set up the auto responder",
            color=0x1ABC9C
        )
        embed.add_field(
            name="🚀 Quick Setup",
            value="Enable auto responder with basic settings:\n• Keywords: `pic`, `pics`, `rep`\n• Message: Simple rep message with your vanity URL",
            inline=False
        )
        embed.add_field(
            name="⚙️ Custom Setup", 
            value="Configure custom keywords and messages for advanced control",
            inline=False
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="🎨 Custom Embed", style=discord.ButtonStyle.secondary)
    async def custom_embed(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("Only the command user can interact!", ephemeral=True)
            return
        
        await interaction.response.send_message("<a:loading:1430203733593034893> **Starting Embed Builder...**", ephemeral=True)
        # Start comprehensive embed builder
        await self.start_embed_builder(self.ctx)
    
    @discord.ui.button(label="📋 Variables", style=discord.ButtonStyle.secondary)
    async def show_variables(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("Only the command user can interact!", ephemeral=True)
            return
        
        var_embed = discord.Embed(
            title="<:slash:1428164524372000879> Available Variables",
            description="**Use these placeholders in your vanity messages and embeds:**\n*Variables will be automatically replaced when users rep your server*",
            color=0x1ABC9C
        )
        
        # User-related variables
        var_embed.add_field(
            name="<:ppl:1427471598578958386> User Variables",
            value=(
                "<:sleep_dot:1427471567838777347> `{user}` - User display name\n"
                "<:sleep_dot:1427471567838777347> `{mention}` - User mention (@user)\n"
                "<:sleep_dot:1427471567838777347> `{user_avatar}` - User avatar URL\n"
                "<:sleep_dot:1427471567838777347> `{user_nick}` - User nickname\n"
                "<:sleep_dot:1427471567838777347> `{user_id}` - User ID\n"
                "<:sleep_dot:1427471567838777347> `{rep_count}` - User's total rep count"
            ),
            inline=True
        )
        
        # Server-related variables  
        var_embed.add_field(
            name="<:cloud1:1427471615473750039> Server Variables",
            value=(
                "<:sleep_dot:1427471567838777347> `{server}` - Server name\n"
                "<:sleep_dot:1427471567838777347> `{guild}` - Server name (alias)\n"
                "<:sleep_dot:1427471567838777347> `{server_icon}` - Server icon URL\n"
                "<:sleep_dot:1427471567838777347> `{server_id}` - Server ID\n"
                "<:sleep_dot:1427471567838777347> `{server_boostcount}` - Boost count\n"
                "<:sleep_dot:1427471567838777347> `{server_boostlevel}` - Boost level\n"
                "<:sleep_dot:1427471567838777347> `{member_count}` - Total members"
            ),
            inline=True
        )
        
        # Time & System variables
        var_embed.add_field(
            name="<:clock1:1427471544409657354> Time & System",
            value=(
                "<:sleep_dot:1427471567838777347> `{date}` - Current date (Month DD, YYYY)\n"
                "<:sleep_dot:1427471567838777347> `{time}` - Current time (HH:MM AM/PM)\n"
                "<:sleep_dot:1427471567838777347> `{day}` - Current day (Monday, Tuesday, etc.)\n"
                "<:sleep_dot:1427471567838777347> `{month}` - Current month (January, February, etc.)\n"
                "<:sleep_dot:1427471567838777347> `{year}` - Current year (YYYY)\n"
                "<:sleep_dot:1427471567838777347> `{bot_name}` - Bot's display name\n"
                "<:sleep_dot:1427471567838777347> `{prefix}` - Server command prefix"
            ),
            inline=True
        )
        
        # Action-related variables
        var_embed.add_field(
            name="<:bot:1428163130663375029> Action & Detection",
            value=(
                "<:sleep_dot:1427471567838777347> `{keyword}` - Keyword that triggered response\n"
                "<:sleep_dot:1427471567838777347> `{detected_content}` - What was detected in user's status/bio\n"
                "<:sleep_dot:1427471567838777347> `{vanity}` - Server vanity URL\n"
                "<:sleep_dot:1427471567838777347> `{invite}` - Full invite link (discord.gg/{vanity})\n"
                "<:sleep_dot:1427471567838777347> `{channel}` - Channel where detection occurred"
            ),
            inline=True
        )
        
        # Add examples
        var_embed.add_field(
            name="<:file:1427471573304217651> Example Usage",
            value=(
                "**Auto-Responder Message:**\n```Hey {user}! Thanks for repping {server}! 🎉```\n"
                "**Embed Title:**\n```🎉 {user} is repping {server}!```\n"
                "**Embed Description:**\n```Thanks {mention} for spreading the word!\n"
                "Detected: {detected_content}\n"
                "Total reps: {rep_count} • Join: {invite}```"
            ),
            inline=False
        )
        
        var_embed.set_footer(text="💡 Use these variables in any vanity message, embed title, description, or field!")
        await interaction.response.send_message(embed=var_embed, ephemeral=True)
    
    @discord.ui.button(label="✅ Save Config", style=discord.ButtonStyle.success)
    async def save_config(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("Only the command user can interact!", ephemeral=True)
            return
        
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server!", ephemeral=True)
            return
        
        if not self.config:
            await interaction.response.send_message("❌ No configuration data to save! Please set up some options first.", ephemeral=True)
            return
        
        # Save configuration to database using proper insert/update pattern
        try:
            # Use the correct database path from the db instance if available, otherwise fallback
            db_path = self.db.db_path if self.db else "databases/vanity.db"
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                
                # Ensure record exists
                cursor.execute('INSERT OR IGNORE INTO vanity_config (guild_id) VALUES (?)', (interaction.guild.id,))
                
                # Update fields based on what was configured
                if 'vanity_url' in self.config:
                    cursor.execute('''
                        UPDATE vanity_config SET vanity_url = ?, updated_at = ? 
                        WHERE guild_id = ?
                    ''', (self.config['vanity_url'], datetime.now(), interaction.guild.id))
                
                if 'vanity_role_id' in self.config:
                    cursor.execute('''
                        UPDATE vanity_config SET vanity_role_id = ?, updated_at = ? 
                        WHERE guild_id = ?
                    ''', (self.config['vanity_role_id'], datetime.now(), interaction.guild.id))
                
                if 'rep_channel_id' in self.config:
                    cursor.execute('''
                        UPDATE vanity_config SET response_channel_id = ?, updated_at = ? 
                        WHERE guild_id = ?
                    ''', (self.config['rep_channel_id'], datetime.now(), interaction.guild.id))
                
                if 'auto_responder' in self.config:
                    cursor.execute('''
                        UPDATE vanity_config SET auto_responder = ?, updated_at = ? 
                        WHERE guild_id = ?
                    ''', (self.config['auto_responder'], datetime.now(), interaction.guild.id))
                
                if 'custom_message' in self.config:
                    cursor.execute('''
                        UPDATE vanity_config SET custom_message = ?, updated_at = ? 
                        WHERE guild_id = ?
                    ''', (self.config['custom_message'], datetime.now(), interaction.guild.id))
                
                # Save keywords if configured
                if 'keywords' in self.config:
                    # Clear existing keywords for this guild
                    cursor.execute('DELETE FROM vanity_keywords WHERE guild_id = ?', (interaction.guild.id,))
                    # Insert new keywords
                    for keyword in self.config['keywords']:
                        cursor.execute('''
                            INSERT INTO vanity_keywords (guild_id, keyword) VALUES (?, ?)
                        ''', (interaction.guild.id, keyword))
                
                conn.commit()
            
            # Show success message with what was saved
            saved_items = []
            if 'vanity_url' in self.config:
                saved_items.append(f"🔗 Vanity URL: `discord.gg/{self.config['vanity_url']}`")
            if 'vanity_role_id' in self.config:
                role = interaction.guild.get_role(self.config['vanity_role_id']) if interaction.guild else None
                saved_items.append(f"🎭 Vanity Role: {role.mention if role else 'Unknown Role'}")
            if 'rep_channel_id' in self.config:
                channel = interaction.guild.get_channel(self.config['rep_channel_id']) if interaction.guild else None
                saved_items.append(f"💬 Rep Channel: {channel.mention if channel else 'Unknown Channel'}")
            if 'auto_responder' in self.config:
                saved_items.append(f"🤖 Auto Responder: {'Enabled' if self.config['auto_responder'] else 'Disabled'}")
            if 'custom_message' in self.config:
                saved_items.append(f"📝 Custom Message: Set")
            if 'keywords' in self.config:
                keywords_text = ", ".join(f"`{k}`" for k in self.config['keywords'][:3])  # Show first 3 keywords
                if len(self.config['keywords']) > 3:
                    keywords_text += f" +{len(self.config['keywords']) - 3} more"
                saved_items.append(f"🔤 Keywords: {keywords_text}")
            
            embed = discord.Embed(
                title="✅ Configuration Saved Successfully!",
                description="Your vanity system configuration has been saved:\n\n" + "\n".join(saved_items),
                color=0x1ABC9C
            )
            embed.set_footer(text="Use 'vanity config' to view your complete configuration")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Save Failed",
                description=f"An error occurred while saving: {str(e)}",
                color=0xED4245
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def start_embed_builder(self, ctx):
        """Start comprehensive embed builder like sticky setup system"""
        # Initialize embed config
        embed = discord.Embed(
            title="<:vanity:1428163639814389771> Server Vanity Role",
            description="<:sleep_customrole:1427471561085943988> Rep our server to earn exclusive vanity role: discord.gg/{vanity}",
            color=0x1ABC9C
        )
        embed.set_footer(text=" Thanks for repping, {user}!")
        
        interaction_user = ctx.author
        
        def check_author(msg):
            return msg.channel.id == ctx.channel.id and msg.author.id == interaction_user.id and not msg.author.bot
        
        # Handler functions for each embed component
        async def handle_title():
            await ctx.send("📝 **Enter embed title** (or 'none' to remove):")
            msg = await ctx.bot.wait_for("message", timeout=60, check=check_author)
            embed.title = None if msg.content.lower() == 'none' else msg.content
        
        async def handle_description():
            await ctx.send("📄 **Enter embed description** (or 'none' to remove):\n*Variables: {user}, {server}, {vanity}*")
            msg = await ctx.bot.wait_for("message", timeout=120, check=check_author)
            embed.description = None if msg.content.lower() == 'none' else msg.content
        
        async def handle_color():
            await ctx.send(
                "🎨 **Enter embed color:**\n"
                "**Examples:** `red`, `blue`, `#1ABC9C`, `rgb(255,100,50)`, `discord`"
            )
            msg = await ctx.bot.wait_for("message", timeout=60, check=check_author)
            if msg.content.lower() == 'default':
                embed.color = 0x1ABC9C
            else:
                color_value = validate_color(msg.content)
                if color_value is not None:
                    embed.color = color_value
                    await ctx.send(f"✅ Color set to: {msg.content}")
                else:
                    await ctx.send("❌ Invalid color format! Using default color.")
                    embed.color = 0x1ABC9C
        
        async def handle_footer():
            await ctx.send("📋 **Enter footer text** (or 'none' to remove):\n*Variables: {user}, {server}, {vanity}*")
            msg = await ctx.bot.wait_for("message", timeout=60, check=check_author)
            if msg.content.lower() == 'none':
                embed.set_footer()
            else:
                embed.set_footer(text=msg.content)
        
        async def handle_thumbnail():
            await ctx.send("🖼️ **Enter thumbnail URL** (or 'none' to remove):")
            msg = await ctx.bot.wait_for("message", timeout=60, check=check_author)
            if msg.content.lower() == 'none':
                embed.set_thumbnail(url=None)
            elif msg.content.startswith('http'):
                embed.set_thumbnail(url=msg.content)
            else:
                await ctx.send("❌ Invalid URL format! Thumbnail not updated.")
        
        async def handle_image():
            await ctx.send("🖥️ **Enter image URL** (or 'none' to remove):")
            msg = await ctx.bot.wait_for("message", timeout=60, check=check_author)
            if msg.content.lower() == 'none':
                embed.set_image(url=None)
            elif msg.content.startswith('http'):
                embed.set_image(url=msg.content)
            else:
                await ctx.send("❌ Invalid URL format! Image not updated.")
        
        async def handle_author():
            await ctx.send("👤 **Enter author name** (or 'none' to remove):")
            msg = await ctx.bot.wait_for("message", timeout=60, check=check_author)
            if msg.content.lower() == 'none':
                embed.set_author(name=None)
            else:
                author_name = msg.content
                await ctx.send("👤 **Enter author icon URL** (or 'none' for no icon):")
                icon_msg = await ctx.bot.wait_for("message", timeout=60, check=check_author)
                if icon_msg.content.lower() != 'none' and icon_msg.content.startswith('http'):
                    embed.set_author(name=author_name, icon_url=icon_msg.content)
                else:
                    embed.set_author(name=author_name)
        
        async def handle_add_field():
            await ctx.send("➕ **Enter field name:**")
            name_msg = await ctx.bot.wait_for("message", timeout=60, check=check_author)
            field_name = name_msg.content
            
            await ctx.send("➕ **Enter field value:**")
            value_msg = await ctx.bot.wait_for("message", timeout=120, check=check_author)
            field_value = value_msg.content
            
            await ctx.send("➕ **Inline field?** (yes/no):")
            inline_msg = await ctx.bot.wait_for("message", timeout=30, check=check_author)
            inline = inline_msg.content.lower() in ['yes', 'y', 'true', '1']
            
            embed.add_field(name=field_name, value=field_value, inline=inline)
        
        async def handle_clear_fields():
            embed.clear_fields()
            await ctx.send("🗑️ **All fields cleared!**")
        
        # Define handlers mapping
        handlers = {
            "Title": handle_title,
            "Description": handle_description,
            "Color": handle_color,
            "Footer": handle_footer,
            "Thumbnail": handle_thumbnail,
            "Image": handle_image,
            "Author": handle_author,
            "Add Field": handle_add_field,
            "Clear Fields": handle_clear_fields,
        }
        
        # Create dropdown select menu
        async def select_callback(interaction):
            if interaction.user.id != interaction_user.id:
                await interaction.response.send_message("❌ This embed builder isn't yours!", ephemeral=True)
                return
            
            await interaction.response.defer()
            value = interaction.data['values'][0]
            
            if value in handlers:
                try:
                    await handlers[value]()
                    await msg.edit(embed=embed, view=view)
                except asyncio.TimeoutError:
                    await ctx.send("⏰ **Timed out!** Please try again.")
                except Exception as e:
                    await ctx.send(f"❌ **Error:** {str(e)}")
        
        # Create UI components
        select = discord.ui.Select(
            placeholder="🎨 Select an option to customize the embed",
            options=[
                discord.SelectOption(label="Title", description="Set the embed title", emoji="📝"),
                discord.SelectOption(label="Description", description="Set the embed description", emoji="📄"),
                discord.SelectOption(label="Color", description="Set the embed color", emoji="🎨"),
                discord.SelectOption(label="Footer", description="Set footer text", emoji="📋"),
                discord.SelectOption(label="Thumbnail", description="Set thumbnail image", emoji="🖼️"),
                discord.SelectOption(label="Image", description="Set large image", emoji="🖥️"),
                discord.SelectOption(label="Author", description="Set author name and icon", emoji="👤"),
                discord.SelectOption(label="Add Field", description="Add a custom field", emoji="➕"),
                discord.SelectOption(label="Clear Fields", description="Remove all fields", emoji="🗑️"),
            ]
        )
        select.callback = select_callback
        
        # Save and cancel buttons
        async def save_callback(interaction):
            if interaction.user.id != interaction_user.id:
                await interaction.response.send_message("❌ This embed builder isn't yours!", ephemeral=True)
                return
            
            # Convert embed to config format for database storage
            embed_config = {
                'title': embed.title,
                'description': embed.description,
                'color': embed.color.value if embed.color else 0x1ABC9C,
                'footer': embed.footer.text if embed.footer else None,
                'thumbnail': embed.thumbnail.url if embed.thumbnail else None,
                'image': embed.image.url if embed.image else None,
                'author_name': embed.author.name if embed.author else None,
                'author_icon': embed.author.icon_url if embed.author else None,
                'fields': [{'name': f.name, 'value': f.value, 'inline': f.inline} for f in embed.fields]
            }
            
            # Save to database using existing columns
            db = VanityDatabase("databases/vanity.db")
            with sqlite3.connect(db.db_path) as conn:
                cursor = conn.cursor()
                # First ensure the guild record exists
                cursor.execute('''
                    INSERT OR IGNORE INTO vanity_config (guild_id) VALUES (?)
                ''', (ctx.guild.id,))
                
                # Then update the embed settings
                cursor.execute('''
                    UPDATE vanity_config 
                    SET embed_title = ?, embed_description = ?, embed_color = ?, 
                        embed_footer = ?, embed_thumbnail = ?, embed_image = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE guild_id = ?
                ''', (
                    embed_config['title'],
                    embed_config['description'], 
                    embed_config['color'],
                    embed_config['footer'],
                    embed_config['thumbnail'],
                    embed_config['image'],
                    ctx.guild.id
                ))
                conn.commit()
            
            success_embed = discord.Embed(
                title="✅ Embed Saved Successfully!",
                description="Your vanity auto-responder embed has been configured and saved.",
                color=0x00FF00
            )
            await interaction.response.edit_message(embed=success_embed, view=None)
        
        async def cancel_callback(interaction):
            if interaction.user.id != interaction_user.id:
                await interaction.response.send_message("❌ This embed builder isn't yours!", ephemeral=True)
                return
            
            cancel_embed = discord.Embed(
                title="❌ Embed Builder Cancelled",
                description="No changes were saved.",
                color=0xFF0000
            )
            await interaction.response.edit_message(embed=cancel_embed, view=None)
        
        save_button = discord.ui.Button(label="💾 Save & Apply", style=discord.ButtonStyle.success)
        save_button.callback = save_callback
        
        cancel_button = discord.ui.Button(label="❌ Cancel", style=discord.ButtonStyle.danger)
        cancel_button.callback = cancel_callback
        
        # Create view with components
        view = discord.ui.View(timeout=300)
        view.add_item(select)
        view.add_item(save_button)
        view.add_item(cancel_button)
        
        # Send initial message with preview
        content = "**🎨 Vanity Embed Builder** - Customize your auto-responder embed using the dropdown below:\n\n*Variables: {user}, {server}, {vanity}*"
        
        msg = await ctx.send(content=content, embed=embed, view=view)
    
    def create_preview_embed(self, config, guild):
        """Create preview embed with variable substitution"""
        # Sample variables for preview
        sample_vars = {
            'user': "SampleUser",
            'mention': "@SampleUser",
            'user_avatar': "https://cdn.discordapp.com/avatars/123456789/sample.png",
            'user_nick': "SampleUser",
            'user_id': "123456789",
            'server': guild.name,
            'guild': guild.name,
            'server_icon': guild.icon.url if guild.icon else 'https://cdn.discordapp.com/embed/avatars/0.png',
            'server_id': str(guild.id),
            'server_boostcount': str(guild.premium_subscription_count or 0),
            'server_boostlevel': str(guild.premium_tier),
            'member_count': str(guild.member_count) if guild else "500",
            'vanity': "your-vanity",
            'channel': "#general",
            'keyword': "pic",
            'rep_count': "10",
            'bot_name': "Sleepless",
            'prefix': "!",
            'invite': "discord.gg/example"
        }
        
        # Replace variables using enhanced function
        title = replace_variables(config['title'], **sample_vars)
        description = replace_variables(config['description'], **sample_vars)
        
        embed = discord.Embed(
            title=title,
            description=description,
            color=config['color']
        )
        
        if config['footer']:
            footer_text = replace_variables(config['footer'], **sample_vars)
            embed.set_footer(text=footer_text)
        
        if config['thumbnail']:
            embed.set_thumbnail(url=config['thumbnail'])
        
        if config['image']:
            embed.set_image(url=config['image'])
        
        if config['author_name']:
            author_name = replace_variables(config['author_name'], **sample_vars)
            embed.set_author(name=author_name, icon_url=config['author_icon'])
        
        # Add custom fields
        for field in config['fields']:
            name = replace_variables(field['name'], **sample_vars)
            value = replace_variables(field['value'], **sample_vars)
            embed.add_field(name=name, value=value, inline=field.get('inline', False))
        
        # Add preview indicator
        embed.add_field(
            name="🔍 Preview Mode",
            value="This shows how your auto-responder embed will look. Variables are replaced with sample data.",
            inline=False
        )
        
        return embed

class VanityURLModal(discord.ui.Modal):
    """Modal for setting vanity URL"""
    
    def __init__(self, config):
        super().__init__(title="🔗 Set Custom Vanity URL")
        self.config = config
        
        self.vanity_input = discord.ui.TextInput(
            label="Vanity URL (without discord.gg/)",
            placeholder="myserver",
            required=True,
            max_length=32
        )
        self.add_item(self.vanity_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        vanity_url = self.vanity_input.value.lower().strip()
        
        # Validate vanity URL
        if not re.match(r'^[a-zA-Z0-9-_]+$', vanity_url):
            await interaction.response.send_message(
                "❌ Vanity URL can only contain letters, numbers, hyphens, and underscores!",
                ephemeral=True
            )
            return
        
        self.config['vanity_url'] = vanity_url
        
        embed = discord.Embed(
            title="✅ Vanity URL Set",
            description=f"🔗 **Custom URL:** `discord.gg/{vanity_url}`",
            color=0x1ABC9C
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

class VanityRoleModal(discord.ui.Modal):
    """Modal for setting vanity role"""
    
    def __init__(self, config, guild):
        super().__init__(title="🎭 Setup Vanity Role")
        self.config = config
        self.guild = guild
        
        self.role_input = discord.ui.TextInput(
            label="Role Name or ID",
            placeholder="VIP Member",
            required=True
        )
        
        self.channel_input = discord.ui.TextInput(
            label="Rep Channel (name or ID)",
            placeholder="vanity-reps",
            required=True
        )
        
        self.add_item(self.role_input)
        self.add_item(self.channel_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        # Find role
        role = None
        role_input = self.role_input.value.strip()
        
        if role_input.isdigit():
            role = self.guild.get_role(int(role_input))
        else:
            role = discord.utils.get(self.guild.roles, name=role_input)
        
        if not role:
            await interaction.response.send_message(
                f"❌ Could not find role: `{role_input}`",
                ephemeral=True
            )
            return
        
        # Find channel
        channel = None
        channel_input = self.channel_input.value.strip()
        
        if channel_input.isdigit():
            channel = self.guild.get_channel(int(channel_input))
        else:
            channel = discord.utils.get(self.guild.text_channels, name=channel_input)
        
        if not channel:
            await interaction.response.send_message(
                f"❌ Could not find channel: `{channel_input}`",
                ephemeral=True
            )
            return
        
        self.config['vanity_role_id'] = role.id
        self.config['rep_channel_id'] = channel.id
        
        embed = discord.Embed(
            title="✅ Vanity Role Setup",
            color=0x1ABC9C
        )
        embed.add_field(name="🎭 Role", value=role.mention, inline=True)
        embed.add_field(name="📝 Channel", value=channel.mention, inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class AutoResponderModal(discord.ui.Modal):
    """Modal for auto-responder setup"""
    
    def __init__(self, config):
        super().__init__(title="💬 Auto Responder Setup")
        self.config = config
        
        self.keywords_input = discord.ui.TextInput(
            label="Keywords (comma separated)",
            placeholder="pic, pics, pic perms, server rep, rep for pic",
            style=discord.TextStyle.paragraph,
            required=True
        )
        
        self.message_input = discord.ui.TextInput(
            label="Response Message",
            placeholder="<:vanity:1428163639814389771> Rep {vanity} for pic perms! 📸 <:sleep_customrole:1427471561085943988>",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=2000
        )
        
        self.add_item(self.keywords_input)
        self.add_item(self.message_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        keywords = [k.strip().lower() for k in self.keywords_input.value.split(',')]
        message = self.message_input.value
        
        self.config['auto_responder'] = True
        self.config['keywords'] = keywords
        self.config['custom_message'] = message
        
        embed = discord.Embed(
            title="✅ Auto Responder Configured",
            color=0x1ABC9C
        )
        embed.add_field(
            name="🔤 Keywords", 
            value=", ".join(f"`{k}`" for k in keywords), 
            inline=False
        )
        embed.add_field(
            name="💬 Response", 
            value=f"```{message[:100]}{'...' if len(message) > 100 else ''}```", 
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class AutoResponderToggleView(discord.ui.View):
    """Simple toggle view for auto responder setup"""
    
    def __init__(self, config, guild):
        super().__init__(timeout=180)
        self.config = config
        self.guild = guild
    
    @discord.ui.button(label="🚀 Quick Setup", style=discord.ButtonStyle.primary, emoji="⚡")
    async def quick_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Enable auto responder with basic settings"""
        # Set basic configuration
        self.config['auto_responder'] = True
        self.config['keywords'] = ['pic', 'pics', 'rep', 'pic perms', 'server rep']
        
        # Get vanity URL for default message
        vanity_url = self.config.get('vanity_url', 'your-server')
        self.config['custom_message'] = f"Rep **{vanity_url}** for access! 🎉"
        
        embed = discord.Embed(
            title="✅ Quick Auto Responder Enabled",
            description="Basic auto responder has been configured with default settings",
            color=0x1ABC9C
        )
        embed.add_field(
            name="🔤 Keywords",
            value="`pic`, `pics`, `rep`, `pic perms`, `server rep`",
            inline=False
        )
        embed.add_field(
            name="💬 Default Message",
            value=f"Rep **{vanity_url}** for access! 🎉",
            inline=False
        )
        embed.add_field(
            name="💡 Next Steps",
            value="• Click **Save Config** to apply settings\n• Use **Custom Setup** if you want to customize keywords/message",
            inline=False
        )
        
        # Disable all buttons
        self.quick_setup.disabled = True
        self.custom_setup.disabled = True
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="⚙️ Custom Setup", style=discord.ButtonStyle.secondary)
    async def custom_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open advanced modal for custom configuration"""
        modal = AutoResponderModal(self.config)
        await interaction.response.send_modal(modal)
        
        # Keep the view but update the message
        embed = discord.Embed(
            title="⚙️ Custom Auto Responder Setup",
            description="Please fill out the modal that just appeared to configure custom keywords and messages.",
            color=0x5865F2
        )
        
        # Disable buttons after modal is shown
        self.quick_setup.disabled = True
        self.custom_setup.disabled = True
        
        await interaction.edit_original_response(embed=embed, view=self)

# Channel Message Setup Views (Sticky-Style)
    
class VanityChannelSetup(discord.ui.View):
    """Sticky-style setup for vanity channel messages"""
    
    def __init__(self, user_id, timeout=600):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.embed_data = {
            "title": "<:sleep_customrole:1427471561085943988> New Rep - Pic Perms Earned!",
            "description": "Thanks {user} for repping **{server}**! <:vanity:1428163639814389771> You now have pic permissions! 📸 <:confetti:1428163119187890358>\n\n**Rep:** `discord.gg/{vanity}`",
            "color": 0x5865F2,
            "author_name": "",
            "author_icon": "",
            "footer_text": "<:ppl:1427471598578958386> Total reps: {rep_count} • Keep repping for more pic perms!",
            "footer_icon": "",
            "thumbnail": "",
            "image": "",
            "fields": []
        }
        
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id
    
    def build_embed(self):
        """Build the embed from stored data"""
        embed = discord.Embed(
            title=self.embed_data.get("title") or "Server Rep",
            description=self.embed_data.get("description") or "Thanks for repping!",
            color=self.embed_data.get("color", 0x5865F2)
        )
        
        # Handle author fields
        if self.embed_data.get("author_name"):
            embed.set_author(
                name=self.embed_data["author_name"],
                icon_url=self.embed_data.get("author_icon", "")
            )
        
        # Handle footer fields  
        if self.embed_data.get("footer_text"):
            embed.set_footer(
                text=self.embed_data["footer_text"],
                icon_url=self.embed_data.get("footer_icon", "")
            )
        
        # Handle images
        if self.embed_data.get("thumbnail"):
            embed.set_thumbnail(url=self.embed_data["thumbnail"])
        if self.embed_data.get("image"):
            embed.set_image(url=self.embed_data["image"])
            
        # Handle fields
        for field in self.embed_data.get("fields", []):
            embed.add_field(
                name=field.get("name", "No Name"),
                value=field.get("value", "No Value"),
                inline=field.get("inline", True)
            )
        
        return embed
    
    # Row 1: Basic Settings
    @discord.ui.button(label="Set Title", emoji="<:file:1427471573304217651>", style=discord.ButtonStyle.primary, row=0)
    async def set_title(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = VanityTitleModal(self.embed_data.get("title", ""))
        await interaction.response.send_modal(modal)
        await modal.wait()
        if hasattr(modal, 'value') and modal.value is not None:
            self.embed_data["title"] = modal.value
            await self.update_preview(interaction)
    
    @discord.ui.button(label="Set Description", emoji="<:tchat:1430364431195570198>", style=discord.ButtonStyle.primary, row=0)
    async def set_description(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = VanityDescriptionModal(self.embed_data.get("description", ""))
        await interaction.response.send_modal(modal)
        await modal.wait()
        if hasattr(modal, 'value') and modal.value is not None:
            self.embed_data["description"] = modal.value
            await self.update_preview(interaction)
    
    @discord.ui.button(label="Set Color", emoji="<:confetti:1428163119187890358>", style=discord.ButtonStyle.primary, row=0)
    async def set_color(self, interaction: discord.Interaction, button: discord.ui.Button):
        current_color = self.embed_data.get("color", 0x5865F2)
        modal = VanityColorModal(hex(current_color))
        await interaction.response.send_modal(modal)
        await modal.wait()
        if hasattr(modal, 'value') and modal.value is not None:
            self.embed_data["color"] = modal.value
            await self.update_preview(interaction)
    
    @discord.ui.button(label="Set Author", emoji="<:ppl:1427471598578958386>", style=discord.ButtonStyle.primary, row=0)
    async def set_author(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = VanityAuthorModal(
            self.embed_data.get("author_name", ""),
            self.embed_data.get("author_icon", "")
        )
        await interaction.response.send_modal(modal)
        await modal.wait()
        if hasattr(modal, 'author_name'):
            self.embed_data["author_name"] = modal.author_name or ""
            self.embed_data["author_icon"] = modal.author_icon or ""
            await self.update_preview(interaction)
    
    # Row 2: Advanced Settings
    @discord.ui.button(label="Set Footer", emoji="<:dotdot:1428168822887546930>", style=discord.ButtonStyle.secondary, row=1)
    async def set_footer(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = VanityFooterModal(
            self.embed_data.get("footer_text", ""),
            self.embed_data.get("footer_icon", "")
        )
        await interaction.response.send_modal(modal)
        await modal.wait()
        if hasattr(modal, 'footer_text'):
            self.embed_data["footer_text"] = modal.footer_text or ""
            self.embed_data["footer_icon"] = modal.footer_icon or ""
            await self.update_preview(interaction)
    
    @discord.ui.button(label="Set Thumbnail", emoji="<:web:1428162947187736679>", style=discord.ButtonStyle.secondary, row=1)
    async def set_thumbnail(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = VanityThumbnailModal(self.embed_data.get("thumbnail", ""))
        await interaction.response.send_modal(modal)
        await modal.wait()
        if hasattr(modal, 'value') and modal.value is not None:
            self.embed_data["thumbnail"] = modal.value
            await self.update_preview(interaction)
    
    @discord.ui.button(label="Set Image", emoji="<:web:1428162947187736679>", style=discord.ButtonStyle.secondary, row=1)
    async def set_image(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = VanityImageModal(self.embed_data.get("image", ""))
        await interaction.response.send_modal(modal)
        await modal.wait()
        if hasattr(modal, 'value') and modal.value is not None:
            self.embed_data["image"] = modal.value
            await self.update_preview(interaction)
    
    @discord.ui.button(label="Add Field", emoji="<:plusu:1428164526884257852>", style=discord.ButtonStyle.secondary, row=1)
    async def add_field(self, interaction: discord.Interaction, button: discord.ui.Button):
        if len(self.embed_data.get("fields", [])) >= 25:
            await interaction.response.send_message("❌ Maximum 25 fields allowed!", ephemeral=True)
            return
        
        modal = VanityFieldModal()
        await interaction.response.send_modal(modal)
        await modal.wait()
        if hasattr(modal, 'name') and hasattr(modal, 'value'):
            field = {
                "name": modal.name,
                "value": modal.value,
                "inline": modal.inline
            }
            if "fields" not in self.embed_data:
                self.embed_data["fields"] = []
            self.embed_data["fields"].append(field)
            await self.update_preview(interaction)
    
    # Row 3: Utility Buttons
    @discord.ui.button(label="Clear Fields", emoji="<:skull1:1428168178936188968>", style=discord.ButtonStyle.secondary, row=2)
    async def clear_fields(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.embed_data["fields"] = []
        await interaction.response.send_message("✅ All fields cleared!", ephemeral=True)
        await self.update_preview(interaction)
    
    @discord.ui.button(label="Variables", emoji="<:slash:1428164524372000879>", style=discord.ButtonStyle.secondary, row=2)
    async def show_variables(self, interaction: discord.Interaction, button: discord.ui.Button):
        var_embed = discord.Embed(
            title="<:slash:1428164524372000879> Available Variables",
            description="**Use these placeholders in your vanity messages:**\n*Variables will be automatically replaced when users rep your server for pic permissions*",
            color=0x5865F2
        )
        
        # User-related variables
        var_embed.add_field(
            name="<:ppl:1427471598578958386> User Variables",
            value=(
                "<:sleep_dot:1427471567838777347> `{user}` - User display name\n"
                "<:sleep_dot:1427471567838777347> `{mention}` - User mention (@user)\n"
                "<:sleep_dot:1427471567838777347> `{user_avatar}` - User avatar URL\n"
                "<:sleep_dot:1427471567838777347> `{user_nick}` - User nickname\n"
                "<:sleep_dot:1427471567838777347> `{user_id}` - User ID\n"
                "<:sleep_dot:1427471567838777347> `{rep_count}` - User's total rep count"
            ),
            inline=True
        )
        
        # Server-related variables  
        var_embed.add_field(
            name="<:cloud1:1427471615473750039> Server Variables",
            value=(
                "<:sleep_dot:1427471567838777347> `{server}` - Server name\n"
                "<:sleep_dot:1427471567838777347> `{guild}` - Server name (alias)\n"
                "<:sleep_dot:1427471567838777347> `{server_icon}` - Server icon URL\n"
                "<:sleep_dot:1427471567838777347> `{server_id}` - Server ID\n"
                "<:sleep_dot:1427471567838777347> `{server_boostcount}` - Boost count\n"
                "<:sleep_dot:1427471567838777347> `{server_boostlevel}` - Boost level\n"
                "<:sleep_dot:1427471567838777347> `{member_count}` - Total members"
            ),
            inline=True
        )
        
        # Time & System variables
        var_embed.add_field(
            name="<:clock1:1427471544409657354> Time & System",
            value=(
                "<:sleep_dot:1427471567838777347> `{date}` - Current date (Month DD, YYYY)\n"
                "<:sleep_dot:1427471567838777347> `{time}` - Current time (HH:MM AM/PM)\n"
                "<:sleep_dot:1427471567838777347> `{day}` - Current day (Monday, Tuesday, etc.)\n"
                "<:sleep_dot:1427471567838777347> `{month}` - Current month (January, February, etc.)\n"
                "<:sleep_dot:1427471567838777347> `{year}` - Current year (YYYY)\n"
                "<:sleep_dot:1427471567838777347> `{bot_name}` - Bot's display name\n"
                "<:sleep_dot:1427471567838777347> `{prefix}` - Server command prefix"
            ),
            inline=True
        )
        
        # Action-related variables
        var_embed.add_field(
            name="<:bot:1428163130663375029> Action & Detection",
            value=(
                "<:sleep_dot:1427471567838777347> `{keyword}` - Keyword that triggered response\n"
                "<:sleep_dot:1427471567838777347> `{detected_content}` - What was detected in user's status/bio\n"
                "<:sleep_dot:1427471567838777347> `{vanity}` - Server vanity URL\n"
                "<:sleep_dot:1427471567838777347> `{invite}` - Full invite link (discord.gg/{vanity})\n"
                "<:sleep_dot:1427471567838777347> `{channel}` - Channel where detection occurred"
            ),
            inline=True
        )
        
        # Add examples
        var_embed.add_field(
            name="<:file:1427471573304217651> Example Usage",
            value=(
                "**Title:** `🎉 Thanks for repping {server}, {user}!`\n"
                "**Description:**\n```Thanks {mention} for spreading the word! 📸\n\n"
                "🔗 Detected: {detected_content}\n"
                "📊 Your total reps: {rep_count}\n"
                "👥 Server members: {member_count}\n"
                "📅 Repped on: {day}, {date} at {time}\n\n"
                "Join us: {invite}```\n"
                "**Footer:** `Vanity System • {bot_name} • {time}`"
            ),
            inline=False
        )
        
        var_embed.set_footer(text="💡 Click any text input field and use these variables!")
        await interaction.response.send_message(embed=var_embed, ephemeral=True)
    
    @discord.ui.button(label="Preview", emoji="<:woah:1428170830042632292>", style=discord.ButtonStyle.secondary, row=2)
    async def preview_embed(self, interaction: discord.Interaction, button: discord.ui.Button):
        preview = self.build_embed()
        
        # Prepare sample variables for preview
        sample_vars = {
            'user': interaction.user.display_name,
            'mention': interaction.user.mention,
            'user_avatar': interaction.user.display_avatar.url if interaction.user.display_avatar else interaction.user.default_avatar.url,
            'user_nick': interaction.user.display_name,
            'user_id': str(interaction.user.id),
            'server': interaction.guild.name if interaction.guild else "Sample Server",
            'guild': interaction.guild.name if interaction.guild else "Sample Server",
            'server_icon': interaction.guild.icon.url if interaction.guild and interaction.guild.icon else 'https://cdn.discordapp.com/embed/avatars/0.png',
            'server_id': str(interaction.guild.id) if interaction.guild else "123456789",
            'server_boostcount': str(interaction.guild.premium_subscription_count) if interaction.guild else "5",
            'server_boostlevel': str(interaction.guild.premium_tier) if interaction.guild else "2",
            'member_count': str(interaction.guild.member_count) if interaction.guild else "1337",
            'vanity': "example",
            'channel': interaction.channel.mention if isinstance(interaction.channel, (discord.TextChannel, discord.VoiceChannel, discord.Thread)) else "#general",
            'keyword': "pic",
            'rep_count': "42",
            'bot_name': interaction.client.user.display_name if interaction.client.user else "Sleepless",
            'prefix': "!",
            'invite': "discord.gg/example"
        }
        
        # Replace variables in all text fields
        if preview.title:
            preview.title = replace_variables(preview.title, **sample_vars)
        if preview.description:
            preview.description = replace_variables(preview.description, **sample_vars)
        if preview.footer and preview.footer.text:
            footer_text = replace_variables(preview.footer.text, **sample_vars)
            preview.set_footer(text=footer_text, icon_url=preview.footer.icon_url)
        if preview.author and preview.author.name:
            author_name = replace_variables(preview.author.name, **sample_vars)
            preview.set_author(name=author_name, icon_url=preview.author.icon_url)
        
        # Replace variables in fields
        for i, field in enumerate(preview.fields):
            if field.name:
                field_name = replace_variables(field.name, **sample_vars)
            else:
                field_name = field.name
            if field.value:
                field_value = replace_variables(field.value, **sample_vars)
            else:
                field_value = field.value
            preview.set_field_at(i, name=field_name, value=field_value, inline=field.inline)
        
        await interaction.response.send_message(embed=preview, ephemeral=True)
    
    # Row 4: Action Buttons
    @discord.ui.button(label="Confirm", emoji="<:confetti:1428163119187890358>", style=discord.ButtonStyle.success, row=3)
    async def confirm_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild or not interaction.channel:
            await interaction.response.send_message("❌ Can only setup vanity messages in server channels!", ephemeral=True)
            return
        
        if not isinstance(interaction.channel, (discord.TextChannel, discord.Thread)):
            await interaction.response.send_message("❌ Can only setup vanity messages in text channels!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            # Save vanity channel message configuration
            db_instance = VanityDatabase("databases/vanity.db")
            async with aiosqlite.connect(db_instance.db_path) as db:
                embed_json = json.dumps(self.embed_data)
                await db.execute('''
                    INSERT OR IGNORE INTO vanity_config (guild_id) VALUES (?)
                ''', (interaction.guild.id,))
                await db.execute('''
                    UPDATE vanity_config SET channel_message_data = ?, channel_id = ?, updated_at = ?
                    WHERE guild_id = ?
                ''', (embed_json, interaction.channel.id, datetime.now(), interaction.guild.id))
                await db.commit()
            
            success_embed = discord.Embed(
                title="✅ Vanity Channel Message Setup Complete",
                description=f"Channel messages will now be posted in {interaction.channel.mention} when members rep the server!",
                color=0x00ff00
            )
            await interaction.edit_original_response(embed=success_embed, view=None)
            
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Setup Failed",
                description=f"An error occurred: {e}",
                color=0xff0000
            )
            await interaction.edit_original_response(embed=error_embed, view=None)
    
    @discord.ui.button(label="Cancel", emoji="<:skull1:1428168178936188968>", style=discord.ButtonStyle.danger, row=3)
    async def cancel_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        cancel_embed = discord.Embed(
            title="❌ Setup Cancelled",
            description="No changes were saved.",
            color=0xff0000
        )
        await interaction.response.edit_message(embed=cancel_embed, view=None)
    
    async def update_preview(self, interaction: discord.Interaction):
        """Update the embed preview after changes with variable processing"""
        try:
            preview_embed = self.build_embed()
            
            # Prepare sample variables for preview processing
            sample_vars = {
                'user': interaction.user.display_name,
                'mention': interaction.user.mention,
                'user_avatar': interaction.user.display_avatar.url if interaction.user.display_avatar else interaction.user.default_avatar.url,
                'user_nick': interaction.user.display_name,
                'user_id': str(interaction.user.id),
                'server': interaction.guild.name if interaction.guild else "Sample Server",
                'guild': interaction.guild.name if interaction.guild else "Sample Server",
                'server_icon': interaction.guild.icon.url if interaction.guild and interaction.guild.icon else 'https://cdn.discordapp.com/embed/avatars/0.png',
                'server_id': str(interaction.guild.id) if interaction.guild else "123456789",
                'server_boostcount': str(interaction.guild.premium_subscription_count) if interaction.guild else "5",
                'server_boostlevel': str(interaction.guild.premium_tier) if interaction.guild else "2",
                'member_count': str(interaction.guild.member_count) if interaction.guild else "1337",
                'vanity': "example",
                'channel': interaction.channel.mention if isinstance(interaction.channel, (discord.TextChannel, discord.VoiceChannel, discord.Thread)) else "#general",
                'keyword': "pic",
                'rep_count': "42",
                'bot_name': interaction.client.user.display_name if interaction.client.user else "Sleepless",
                'prefix': "!",
                'invite': "discord.gg/example"
            }
            
            # Process variables in all text fields
            if preview_embed.title:
                preview_embed.title = replace_variables(preview_embed.title, **sample_vars)
            if preview_embed.description:
                preview_embed.description = replace_variables(preview_embed.description, **sample_vars)
            if preview_embed.footer and preview_embed.footer.text:
                footer_text = replace_variables(preview_embed.footer.text, **sample_vars)
                preview_embed.set_footer(text=footer_text, icon_url=preview_embed.footer.icon_url)
            if preview_embed.author and preview_embed.author.name:
                author_name = replace_variables(preview_embed.author.name, **sample_vars)
                preview_embed.set_author(name=author_name, icon_url=preview_embed.author.icon_url)
            
            # Process variables in fields
            for i, field in enumerate(preview_embed.fields):
                if field.name:
                    field_name = replace_variables(field.name, **sample_vars)
                else:
                    field_name = field.name
                if field.value:
                    field_value = replace_variables(field.value, **sample_vars)
                else:
                    field_value = field.value
                preview_embed.set_field_at(i, name=field_name, value=field_value, inline=field.inline)
            
            # Add confirmation message to footer if no custom footer is set
            if not self.embed_data.get("footer_text"):
                preview_embed.set_footer(
                    text="✅ Changes saved! • Use buttons below to continue customizing"
                )
            else:
                # If there's a custom footer, add a small confirmation field
                preview_embed.add_field(
                    name="✅ Changes Saved",
                    value="Your changes have been applied to the preview above!",
                    inline=False
                )
            
            # Edit the original message with the updated embed
            await interaction.edit_original_response(embed=preview_embed, view=self)
            
        except Exception as e:
            print(f"Error updating preview: {e}")
            # Send a fallback message
            try:
                await interaction.followup.send("✅ Changes saved! Please check the embed above.", ephemeral=True)
            except:
                pass


# Legacy VanityEmbedBuilderView removed - replaced with sticky-style system

# Modal Classes for VanityChannelSetup

class VanityTitleModal(discord.ui.Modal):
    def __init__(self, current_title=""):
        super().__init__(title="📝 Set Embed Title")
        self.value = None
        
        self.title_input = discord.ui.TextInput(
            label="Embed Title",
            placeholder="<:sleep_customrole:1427471561085943988> Server Rep • Pic Perms Earned {user}! 📸",
            default=current_title,
            required=False,
            max_length=256
        )
        self.add_item(self.title_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        self.value = self.title_input.value if self.title_input.value else ""
        await interaction.response.defer()

class VanityDescriptionModal(discord.ui.Modal):
    def __init__(self, current_description=""):
        super().__init__(title="📄 Set Embed Description")
        self.value = None
        
        self.description_input = discord.ui.TextInput(
            label="Embed Description",
            placeholder="Thanks {user} for repping **{server}**! <:vanity:1428163639814389771>\nYou've earned your vanity role! Join us: discord.gg/{vanity}",
            default=current_description,
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=2048
        )
        self.add_item(self.description_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        self.value = self.description_input.value if self.description_input.value else ""
        await interaction.response.defer()

class VanityColorModal(discord.ui.Modal):
    def __init__(self, current_color="#5865F2"):
        super().__init__(title="🎨 Set Embed Color")
        self.value = None
        
        self.color_input = discord.ui.TextInput(
            label="Embed Color",
            placeholder="Examples: #1ABC9C, red, blue, rgb(255,100,50), discord, 16711680",
            default=current_color,
            required=False,
            max_length=50,
            style=discord.TextStyle.short
        )
        self.add_item(self.color_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            if not self.color_input.value:
                self.value = 0x5865F2  # Default Discord color
                await interaction.response.defer()
                return
            
            color_value = validate_color(self.color_input.value)
            if color_value is not None:
                self.value = color_value
                await interaction.response.defer()
            else:
                await interaction.response.send_message(
                    "❌ **Invalid color format!**\n\n"
                    "**Supported formats:**\n"
                    "• **Color names:** red, blue, green, purple, discord, teal\n"
                    "• **Hex codes:** #1ABC9C, #FF0000, 1ABC9C\n" 
                    "• **RGB values:** rgb(255,100,50)\n"
                    "• **Decimal:** 16711680", 
                    ephemeral=True
                )
        except Exception as e:
            await interaction.response.send_message(f"❌ Error processing color: {str(e)}", ephemeral=True)

class VanityAuthorModal(discord.ui.Modal):
    def __init__(self, current_name="", current_icon=""):
        super().__init__(title="👤 Set Embed Author")
        self.author_name = None
        self.author_icon = None
        
        self.name_input = discord.ui.TextInput(
            label="Author Name",
            placeholder="<:vanity:1428163639814389771> {server} Official • Vanity Role System",
            default=current_name,
            required=False,
            max_length=256
        )
        
        self.icon_input = discord.ui.TextInput(
            label="Author Icon URL (optional)",
            placeholder="https://cdn.discordapp.com/icons/123.png",
            default=current_icon,
            required=False
        )
        
        self.add_item(self.name_input)
        self.add_item(self.icon_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        self.author_name = self.name_input.value if self.name_input.value else ""
        self.author_icon = self.icon_input.value if self.icon_input.value else ""
        await interaction.response.defer()

class VanityFooterModal(discord.ui.Modal):
    def __init__(self, current_text="", current_icon=""):
        super().__init__(title="📋 Set Embed Footer")
        self.footer_text = None
        self.footer_icon = None
        
        self.text_input = discord.ui.TextInput(
            label="Footer Text",
            placeholder="<:sleep_customrole:1427471561085943988> Thanks for repping, {user}! • Total reps: {rep_count}",
            default=current_text,
            required=False,
            max_length=2048
        )
        
        self.icon_input = discord.ui.TextInput(
            label="Footer Icon URL (optional)",
            placeholder="https://cdn.discordapp.com/emojis/123.png",
            default=current_icon,
            required=False
        )
        
        self.add_item(self.text_input)
        self.add_item(self.icon_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        self.footer_text = self.text_input.value if self.text_input.value else ""
        self.footer_icon = self.icon_input.value if self.icon_input.value else ""
        await interaction.response.defer()

class VanityThumbnailModal(discord.ui.Modal):
    def __init__(self, current_thumbnail=""):
        super().__init__(title="🖼️ Set Embed Thumbnail")
        self.value = None
        
        self.thumbnail_input = discord.ui.TextInput(
            label="Thumbnail URL",
            placeholder="https://cdn.discordapp.com/icons/server_id/icon.png",
            default=current_thumbnail,
            required=False
        )
        self.add_item(self.thumbnail_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        self.value = self.thumbnail_input.value if self.thumbnail_input.value else ""
        await interaction.response.defer()

class EmbedCustomizationModal(discord.ui.Modal):
    def __init__(self, current_thumbnail=""):
        super().__init__(title="🖼️ Set Embed Thumbnail")
        self.value = None
        
        self.thumbnail_input = discord.ui.TextInput(
            label="Thumbnail URL",
            placeholder="https://example.com/image.png",
            default=current_thumbnail,
            required=False
        )
        self.add_item(self.thumbnail_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        self.value = self.thumbnail_input.value if self.thumbnail_input.value else ""
        await interaction.response.defer()

class VanityImageModal(discord.ui.Modal):
    def __init__(self, current_image=""):
        super().__init__(title="🖥️ Set Embed Image")
        self.value = None
        
        self.image_input = discord.ui.TextInput(
            label="Image URL",
            placeholder="https://example.com/image.png",
            default=current_image,
            required=False
        )
        self.add_item(self.image_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        self.value = self.image_input.value if self.image_input.value else ""
        await interaction.response.defer()

class VanityFieldModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title=" Add Embed Field")
        self.name = None
        self.value = None
        self.inline = False
        
        self.name_input = discord.ui.TextInput(
            label="Field Name",
            placeholder=" Quick Join",
            max_length=256
        )
        
        self.value_input = discord.ui.TextInput(
            label="Field Value",
            placeholder="Join us: discord.gg/{vanity}",
            style=discord.TextStyle.paragraph,
            max_length=1024
        )
        
        self.inline_input = discord.ui.TextInput(
            label="Inline (true/false)",
            placeholder="false",
            default="false",
            max_length=5
        )
        
        self.add_item(self.name_input)
        self.add_item(self.value_input)
        self.add_item(self.inline_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        self.name = self.name_input.value
        self.value = self.value_input.value
        self.inline = self.inline_input.value.lower() in ['true', 'yes', '1']
        await interaction.response.defer()

# Legacy Modals for Auto-Responder

class EmbedTitleModal(discord.ui.Modal):
    def __init__(self, config):
        super().__init__(title=" Embed Title")
        self.config = config
        self.view = None
        
        self.title_input = discord.ui.TextInput(
            label="Embed Title",
            placeholder="<:vanity:1428163639814389771> Server Vanity Role System",
            default=config['title'],
            max_length=256
        )
        self.add_item(self.title_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        self.config['title'] = self.title_input.value
        await interaction.response.defer()

class EmbedDescriptionModal(discord.ui.Modal):
    def __init__(self, config):
        super().__init__(title=" Embed Description")
        self.config = config
        self.view = None
        
        self.description_input = discord.ui.TextInput(
            label="Embed Description",
            placeholder="<:sleep_customrole:1427471561085943988> Rep our server to earn your vanity role: discord.gg/{vanity}",
            default=config['description'],
            style=discord.TextStyle.paragraph,
            max_length=2048
        )
        self.add_item(self.description_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        self.config['description'] = self.description_input.value
        await interaction.response.defer()

class EmbedColorModal(discord.ui.Modal):
    def __init__(self, config):
        super().__init__(title=" Embed Color")
        self.config = config
        self.view = None
        
        current_color = hex(config['color']).replace('0x', '#').upper()
        self.color_input = discord.ui.TextInput(
            label="Embed Color (hex code)",
            placeholder="#1ABC9C",
            default=current_color,
            max_length=7
        )
        self.add_item(self.color_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            color_hex = self.color_input.value.replace('#', '')
            self.config['color'] = int(color_hex, 16)
            await interaction.response.defer()
        except ValueError:
            await interaction.response.send_message("<:cancel:1427471557055352892> Invalid color! Use format: #1ABC9C", ephemeral=True)

class EmbedFooterModal(discord.ui.Modal):
    def __init__(self, config):
        super().__init__(title=" Embed Footer")
        self.config = config
        self.view = None
        
        self.footer_input = discord.ui.TextInput(
            label="Footer Text",
            placeholder="Thanks for repping, {user}!",
            default=config['footer'] or "",
            max_length=2048
        )
        self.add_item(self.footer_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        self.config['footer'] = self.footer_input.value
        await interaction.response.defer()

class EmbedThumbnailModal(discord.ui.Modal):
    def __init__(self, config):
        super().__init__(title=" Thumbnail")
        self.config = config
        self.view = None
        
        self.thumbnail_input = discord.ui.TextInput(
            label="Thumbnail URL",
            placeholder="https://example.com/image.png",
            default=config['thumbnail'] or "",
            required=False
        )
        self.add_item(self.thumbnail_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        self.config['thumbnail'] = self.thumbnail_input.value if self.thumbnail_input.value else None
        await interaction.response.defer()

class EmbedImageModal(discord.ui.Modal):
    def __init__(self, config):
        super().__init__(title="<a:media:1430203744661798993> Edit Main Image")
        self.config = config
        self.view = None
        
        self.image_input = discord.ui.TextInput(
            label="Image URL",
            placeholder="https://example.com/image.png",
            default=config['image'] or "",
            required=False
        )
        self.add_item(self.image_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        self.config['image'] = self.image_input.value if self.image_input.value else None
        await interaction.response.defer()

class EmbedAuthorModal(discord.ui.Modal):
    def __init__(self, config):
        super().__init__(title="<:profile:1428199763953582201> Edit Author")
        self.config = config
        self.view = None
        
        self.author_name_input = discord.ui.TextInput(
            label="Author Name",
            placeholder="{server} Official",
            default=config['author_name'] or "",
            required=False
        )
        
        self.author_icon_input = discord.ui.TextInput(
            label="Author Icon URL",
            placeholder="https://example.com/icon.png",
            default=config['author_icon'] or "",
            required=False
        )
        
        self.add_item(self.author_name_input)
        self.add_item(self.author_icon_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        self.config['author_name'] = self.author_name_input.value if self.author_name_input.value else None
        self.config['author_icon'] = self.author_icon_input.value if self.author_icon_input.value else None
        await interaction.response.defer()

class EmbedFieldModal(discord.ui.Modal):
    def __init__(self, config, field_index):
        super().__init__(title="<:plusu:1428164526884257852> Add Embed Field")
        self.config = config
        self.field_index = field_index
        self.view = None
        
        self.field_name_input = discord.ui.TextInput(
            label="Field Name",
            placeholder=" Quick Join",
            max_length=256
        )
        
        self.field_value_input = discord.ui.TextInput(
            label="Field Value",
            placeholder="discord.gg/{vanity}",
            style=discord.TextStyle.paragraph,
            max_length=1024
        )
        
        self.field_inline_input = discord.ui.TextInput(
            label="Inline (true/false)",
            placeholder="false",
            default="false",
            max_length=5
        )
        
        self.add_item(self.field_name_input)
        self.add_item(self.field_value_input)
        self.add_item(self.field_inline_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        inline = self.field_inline_input.value.lower() in ['true', 'yes', '1']
        
        field = {
            'name': self.field_name_input.value,
            'value': self.field_value_input.value,
            'inline': inline
        }
        
        self.config['fields'].append(field)
        await interaction.response.defer()

class VanitySystem(commands.Cog):
    """Complete Vanity System with extensive features"""
    
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot
        self.db = VanityDatabase("databases/vanity.db")
        
    def help_custom(self):
        emoji = '🔗'
        label = "Vanity System"
        description = "Complete vanity URL and server repping system with custom invites, auto-responder, and analytics"
        return emoji, label, description

    @commands.group(name="vanity", aliases=['v'], invoke_without_command=True)
    @blacklist_check()
    @commands.has_permissions(manage_guild=True)
    async def vanity(self, ctx):
        """Complete vanity system management"""
        if ctx.invoked_subcommand is None:
            view = VanityHelpView(ctx)
            view.update_buttons()  # Set initial button states
            await ctx.send(embed=view.pages[0], view=view)

    @vanity.command(name="setup")
    @blacklist_check()
    @commands.has_permissions(manage_guild=True)
    async def vanity_setup(self, ctx):
        """Interactive vanity system setup wizard"""
        embed = discord.Embed(
            title="🔗 Vanity System Setup Wizard",
            description="**Configure your server's complete vanity and repping system!**\n\n🎯 Click the buttons below to configure each feature:",
            color=0x1ABC9C
        )
        
        embed.add_field(
            name="<:slash:1428164524372000879> **Vanity URL**",
            value="Set your custom discord.gg link",
            inline=True
        )
        
        embed.add_field(
            name="<:ignore:1427471588915150900> **Vanity Role**",
            value="Role given to active reppers",
            inline=True
        )
        
        embed.add_field(
            name="<:tchat:1430364431195570198> **Auto Responder**",
            value="Automatic replies to rep keywords",
            inline=True
        )
        
        embed.add_field(
            name="<a:gear:1430203750324240516> **Custom Embeds**",
            value="Custom embedded responses",
            inline=True
        )
        
        embed.add_field(
            name="<:profile:1428199763953582201> **Analytics**",
            value="Track reps and user engagement",
            inline=True
        )
        
        # Create initial database record if it doesn't exist
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT OR IGNORE INTO vanity_config (guild_id) VALUES (?)', (ctx.guild.id,))
            conn.commit()
        
        view = VanityView(ctx, self.db)
        await ctx.send(embed=embed, view=view)

    @vanity.command(name="url")
    @blacklist_check()
    @commands.has_permissions(manage_guild=True)
    async def vanity_url(self, ctx, *, custom_url: str):
        """Set custom vanity URL for the server"""
        # Validate URL format
        custom_url = custom_url.lower().strip()
        if not re.match(r'^[a-zA-Z0-9-_]+$', custom_url):
            embed = discord.Embed(
                title="<:cancel:1427471557055352892> Invalid Vanity URL",
                description="Vanity URL can only contain letters, numbers, hyphens, and underscores!",
                color=0xED4245
            )
            await ctx.send(embed=embed)
            return
        
        # Save to database (using proper update pattern)
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            # Ensure record exists
            cursor.execute('INSERT OR IGNORE INTO vanity_config (guild_id) VALUES (?)', (ctx.guild.id,))
            # Update the specific field
            cursor.execute('''
                UPDATE vanity_config 
                SET vanity_url = ?, updated_at = ?
                WHERE guild_id = ?
            ''', (custom_url, datetime.now(), ctx.guild.id))
            conn.commit()
        
        embed = discord.Embed(
            title="<:check:1428163122710970508> Configuration | Vanity URL Set Successfully!",
            description=f"🔗 **Your custom invite:** `discord.gg/{custom_url}`",
            color=0x1ABC9C
        )
        embed.add_field(
            name="<:question:1428173442947088486> **How to use:**",
            value=f"Share `discord.gg/{custom_url}` to promote your server!\nUsers can use keywords to trigger auto-responder.",
            inline=False
        )
        embed.add_field(
            name="<:clock1:1427471544409657354> **Configuration Status:**",
            value="<:check:1428163122710970508> Vanity URL configured\n<:like:1428199620554657842> Next: Enable auto-responder with `vanity responder enable`",
            inline=False
        )
        embed.set_footer(text="<a:gear:1430203750324240516> Vanity System Configuration")
        await ctx.send(embed=embed)

    @vanity.command(name="config", aliases=['configuration', 'settings'])
    @blacklist_check()
    @commands.has_permissions(manage_guild=True)
    async def vanity_config(self, ctx):
        """View current vanity system configuration"""
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT guild_id, vanity_url, vanity_role_id, response_channel_id, auto_responder, 
                       auto_responder_message, embed_color, embed_title, embed_description, 
                       channel_message_data, channel_id, created_at, updated_at
                FROM vanity_config WHERE guild_id = ?
            ''', (ctx.guild.id,))
            config = cursor.fetchone()
        
        if not config:
            embed = discord.Embed(
                title="<:cancel:1427471557055352892> No Configuration Found",
                description="Use `vanity setup` to configure the vanity system first.",
                color=0xED4245
            )
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title="<:cog:1428163115136057486> Vanity System Configuration",
            description=f"Current settings for **{ctx.guild.name}**",
            color=0x5865F2
        )
        
        # Extract data with proper column names
        (guild_id, vanity_url, vanity_role_id, response_channel_id, auto_responder, 
         auto_responder_message, embed_color, embed_title, embed_description, 
         channel_message_data, channel_id, created_at, updated_at) = config
        
        # Vanity URL
        if vanity_url:
            embed.add_field(name="🔗 Vanity URL", value=f"`discord.gg/{vanity_url}`", inline=True)
        else:
            embed.add_field(name="🔗 Vanity URL", value="<:cancel:1427471557055352892> Not configured", inline=True)
        
        # Vanity Role
        vanity_role = ctx.guild.get_role(vanity_role_id) if vanity_role_id else None
        if vanity_role:
            embed.add_field(name="<:vanity:1428163639814389771> Vanity Role", value=vanity_role.mention, inline=True)
        else:
            embed.add_field(name="<:vanity:1428163639814389771> Vanity Role", value="<:cancel:1427471557055352892> Not set", inline=True)
        
        # Rep Channel
        rep_channel = ctx.guild.get_channel(response_channel_id) if response_channel_id else None
        if rep_channel:
            embed.add_field(name="<:file:1427471573304217651> Rep Channel", value=rep_channel.mention, inline=True)
        else:
            embed.add_field(name="<:file:1427471573304217651> Rep Channel", value="<:cancel:1427471557055352892> Not set", inline=True)
        
        # Auto Responder
        if auto_responder:
            embed.add_field(name="<:bot:1428163130663375029> Auto Responder", value="<:check:1428163122710970508> Enabled", inline=True)
        else:
            embed.add_field(name="<:bot:1428163130663375029> Auto Responder", value="<:cancel:1427471557055352892> Disabled", inline=True)
        
        # Custom Message
        if auto_responder_message:
            display_msg = auto_responder_message[:50] + "..." if len(auto_responder_message) > 50 else auto_responder_message
            embed.add_field(name="<:tchat:1430364431195570198> Custom Message", value=f"`{display_msg}`", inline=True)
        else:
            embed.add_field(name="<:tchat:1430364431195570198> Custom Message", value="<:cancel:1427471557055352892> Not set", inline=True)
        
        # Channel Messages
        if channel_message_data:
            embed.add_field(name="<:file:1427471573304217651> Channel Messages", value="<:check:1428163122710970508> Configured", inline=True)
        else:
            embed.add_field(name="<:file:1427471573304217651> Channel Messages", value="<:cancel:1427471557055352892> Not set", inline=True)
            
        # Embed Configuration
        embed_configured = any([embed_title, embed_description])
        if embed_configured:
            embed.add_field(name="🎨 Embed Settings", value="<:check:1428163122710970508> Configured", inline=True)
        else:
            embed.add_field(name="🎨 Embed Settings", value="<:cancel:1427471557055352892> Not set", inline=True)
        
        # Add debug info for troubleshooting (can remove later)
        if ctx.author.id == ctx.guild.owner_id:  # Only show to server owner
            embed.add_field(
                name="🔧 Debug Info (Owner Only)",
                value=f"Database Record: `{len([x for x in config if x is not None])}` non-null fields",
                inline=False
            )
        
        embed.set_footer(text=" Use vanity reset to clear all settings")
        await ctx.send(embed=embed)

    @vanity.command(name="reset", aliases=['clear'])
    @blacklist_check()
    @commands.has_permissions(manage_guild=True)
    async def vanity_reset(self, ctx):
        """Reset all vanity system configuration"""
        # Confirmation embed
        embed = discord.Embed(
            title="⚠️ Reset Vanity Configuration",
            description="**This will permanently delete:**\n• Vanity URL settings\n• Role configuration\n• Auto-responder setup\n• Channel message settings\n• All statistics and logs",
            color=0xED4245
        )
        embed.set_footer(text="This action cannot be undone!")
        
        # Confirmation view
        class ConfirmResetView(discord.ui.View):
            def __init__(self, db_instance):
                super().__init__(timeout=60)
                self.db = db_instance
            
            @discord.ui.button(label="✅ Confirm Reset", style=discord.ButtonStyle.danger)
            async def confirm_reset(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("Only the command user can confirm this action.", ephemeral=True)
                    return
                
                # Delete all data
                with sqlite3.connect(self.db.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute('DELETE FROM vanity_config WHERE guild_id = ?', (ctx.guild.id,))
                    cursor.execute('DELETE FROM vanity_stats WHERE guild_id = ?', (ctx.guild.id,))
                    cursor.execute('DELETE FROM vanity_logs WHERE guild_id = ?', (ctx.guild.id,))
                    conn.commit()
                
                success_embed = discord.Embed(
                    title="<:check:1428163122710970508> Configuration Reset",
                    description="All vanity system data has been cleared for this server.",
                    color=0x00FF00
                )
                await interaction.response.edit_message(embed=success_embed, view=None)
            
            @discord.ui.button(label="<:cancel:1427471557055352892> Cancel", style=discord.ButtonStyle.secondary)
            async def cancel_reset(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("Only the command user can cancel this action.", ephemeral=True)
                    return
                
                cancel_embed = discord.Embed(
                    title="<:cancel:1427471557055352892> Reset Cancelled",
                    description="No changes were made to your configuration.",
                    color=0x5865F2
                )
                await interaction.response.edit_message(embed=cancel_embed, view=None)
        
        view = ConfirmResetView(self.db)
        await ctx.send(embed=embed, view=view)

    @vanity.command(name="role")
    @blacklist_check()
    @commands.has_permissions(manage_guild=True)
    async def vanity_role(self, ctx, *, role: discord.Role):
        """Set the vanity role given to active reppers"""
        # Check if role has dangerous permissions
        if role.permissions.administrator or role.permissions.ban_members or role.permissions.kick_members:
            embed = discord.Embed(
                title="<:woah:1428170830042632292> Dangerous Role",
                description="Please select a role without dangerous permissions (Administrator, Ban Members, Kick Members).",
                color=0xED4245
            )
            await ctx.send(embed=embed)
            return
        
        # Save to database
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO vanity_config (guild_id) VALUES (?)
            ''', (ctx.guild.id,))
            cursor.execute('''
                UPDATE vanity_config SET vanity_role_id = ?, updated_at = ? 
                WHERE guild_id = ?
            ''', (role.id, datetime.now(), ctx.guild.id))
            conn.commit()
        
        embed = discord.Embed(
            title="<:check:1428163122710970508> Vanity Role Set Successfully!",
            description=f"🎭 **Vanity Role:** {role.mention}",
            color=0x1ABC9C
        )
        embed.add_field(
            name="<:sleep_customrole:1427471561085943988> **Benefits:**",
            value="Active reppers will automatically receive this role based on their rep activity!",
            inline=False
        )
        await ctx.send(embed=embed)

    @vanity.command(name="channel")
    @blacklist_check()
    @commands.has_permissions(manage_guild=True)
    async def vanity_channel(self, ctx, *, channel: discord.TextChannel):
        """Set the channel for vanity rep responses"""
        # Save to database
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO vanity_config (guild_id) VALUES (?)
            ''', (ctx.guild.id,))
            cursor.execute('''
                UPDATE vanity_config SET rep_channel_id = ?, updated_at = ? 
                WHERE guild_id = ?
            ''', (channel.id, datetime.now(), ctx.guild.id))
            conn.commit()
        
        embed = discord.Embed(
            title="<:check:1428163122710970508> Vanity Channel Set Successfully!",
            description=f" **Rep Channel:** {channel.mention}",
            color=0x1ABC9C
        )
        embed.add_field(
            name="<:sleep_functions:1427471540823392307> **Function:**",
            value="All vanity responses and rep tracking will happen in this channel!",
            inline=False
        )
        await ctx.send(embed=embed)

    @vanity.group(name="responder", aliases=['resp'], invoke_without_command=True)
    @blacklist_check()
    @commands.has_permissions(manage_guild=True)
    async def vanity_responder(self, ctx):
        """Manage auto-responder system"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="<:tchat:1430364431195570198> Auto-Responder System",
                description="**Automatically respond to vanity keywords**",
                color=0x1ABC9C
            )
            
            embed.add_field(
                name="<:like:1428199620554657842> **Quick Commands**",
                value=(
                    "`vanity responder enable` - Turn on auto-responder\n"
                    "`vanity responder disable` - Turn off auto-responder\n"
                    "`vanity responder test` - Test current setup"
                ),
                inline=False
            )
            
            embed.add_field(
                name="<a:gear:1430203750324240516> **Configuration**",
                value=(
                    "`vanity keywords add <word>` - Add trigger keyword\n"
                    "`vanity keywords remove <word>` - Remove keyword\n"
                    "`vanity keywords list` - Show all keywords\n"
                    "`vanity message <text>` - Set response message"
                ),
                inline=False
            )
            
            await ctx.send(embed=embed)

    @vanity_responder.command(name="enable")
    @blacklist_check()
    @commands.has_permissions(manage_guild=True)
    async def responder_enable(self, ctx):
        """Enable auto-responder system"""
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO vanity_config (guild_id) VALUES (?)
            ''', (ctx.guild.id,))
            cursor.execute('''
                UPDATE vanity_config SET auto_responder = ?, updated_at = ? 
                WHERE guild_id = ?
            ''', (1, datetime.now(), ctx.guild.id))
            
            # Add default "pic" keyword if none exist
            cursor.execute('SELECT COUNT(*) FROM vanity_keywords WHERE guild_id = ?', (ctx.guild.id,))
            if cursor.fetchone()[0] == 0:
                cursor.execute('''
                    INSERT INTO vanity_keywords (guild_id, keyword)
                    VALUES (?, ?)
                ''', (ctx.guild.id, 'pic'))
            
            conn.commit()
        
        embed = discord.Embed(
            title="<:cog:1428163115136057486> Configuration | Auto-Responder Enabled!",
            description="<:bot:1428163130663375029> The bot will now automatically respond to vanity keywords!",
            color=0x1ABC9C
        )
        embed.add_field(
            name="<:flag:1427471551200100403> **Default Keyword:**",
            value="`pic` - Type this word in chat to test the auto-responder",
            inline=False
        )
        embed.add_field(
            name="<:cog:1428163115136057486> **Configuration Status:**",
            value="<:check:1428163122710970508> Auto-responder enabled\n<:like:1428199620554657842> Test by typing `pic` in any channel",
            inline=False
        )
        embed.add_field(
            name="<:cog:1428163115136057486> **Customization Options:**",
            value=(
                "• Custom message: `vanity message <text>`\n"
                "• More keywords: `vanity keywords add <word>`\n"
                "• Custom embed: Use `vanity setup` → <a:media:1430203744661798993> Custom Embed"
            ),
            inline=False
        )
        embed.set_footer(text="<:cog:1428163115136057486> Vanity System Configuration")
        await ctx.send(embed=embed)

    @vanity_responder.command(name="disable")
    @blacklist_check()
    @commands.has_permissions(manage_guild=True)
    async def responder_disable(self, ctx):
        """Disable auto-responder system"""
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE vanity_config 
                SET auto_responder = ?, updated_at = ?
                WHERE guild_id = ?
            ''', (False, datetime.now(), ctx.guild.id))
            conn.commit()
        
        embed = discord.Embed(
            title="<:cancel:1427471557055352892><:cancel:1427471557055352892> Auto-Responder Disabled",
            description="<:woah:1428170830042632292> The bot will no longer respond to vanity keywords.",
            color=0xED4245
        )
        embed.add_field(
            name="<:loop:1428181740580638771> **Re-enable:**",
            value="Use `vanity responder enable` to turn it back on.",
            inline=False
        )
        await ctx.send(embed=embed)

    @vanity.group(name="keywords", aliases=['kw'], invoke_without_command=True)
    @blacklist_check()
    @commands.has_permissions(manage_guild=True)
    async def vanity_keywords(self, ctx):
        """Manage vanity trigger keywords"""
        if ctx.invoked_subcommand is None:
            # Show current keywords
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT keyword FROM vanity_keywords 
                    WHERE guild_id = ? ORDER BY created_at
                ''', (ctx.guild.id,))
                keywords = [row[0] for row in cursor.fetchall()]
            
            if not keywords:
                embed = discord.Embed(
                    title="<:woah:1428170830042632292> No Keywords Set",
                    description="No trigger keywords configured yet!",
                    color=0xFEE75C
                )
                embed.add_field(
                    name="<:plusu:1428164526884257852> **Add Keywords:**",
                    value="Use `vanity keywords add <word>` to add trigger words.",
                    inline=False
                )
            else:
                embed = discord.Embed(
                    title="🔤 Vanity Keywords",
                    description=f"**{len(keywords)} trigger words configured:**",
                    color=0x1ABC9C
                )
                
                # Group keywords for better display
                keyword_list = ", ".join(f"`{kw}`" for kw in keywords)
                embed.add_field(
                    name="📋 **Current Keywords:**",
                    value=keyword_list,
                    inline=False
                )
            
            embed.add_field(
                name="<:mod:1427471611262537830> **Management:**",
                value=(
                    "`vanity keywords add <word>` - Add keyword\n"
                    "`vanity keywords remove <word>` - Remove keyword\n"
                    "`vanity keywords clear` - Remove all keywords"
                ),
                inline=False
            )
            await ctx.send(embed=embed)

    @vanity_keywords.command(name="add")
    @blacklist_check()
    @commands.has_permissions(manage_guild=True)
    async def keywords_add(self, ctx, *, keyword: str):
        """Add a trigger keyword for auto-responder"""
        keyword = keyword.lower().strip()
        
        # Check if keyword already exists
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) FROM vanity_keywords 
                WHERE guild_id = ? AND keyword = ?
            ''', (ctx.guild.id, keyword))
            
            if cursor.fetchone()[0] > 0:
                embed = discord.Embed(
                    title="<:woah:1428170830042632292> Keyword Already Exists",
                    description=f"The keyword `{keyword}` is already configured!",
                    color=0xFEE75C
                )
                await ctx.send(embed=embed)
                return
            
            # Add keyword
            cursor.execute('''
                INSERT INTO vanity_keywords (guild_id, keyword)
                VALUES (?, ?)
            ''', (ctx.guild.id, keyword))
            conn.commit()
        
        embed = discord.Embed(
            title="<:check:1428163122710970508> Keyword Added Successfully!",
            description=f" **New Keyword:** `{keyword}`",
            color=0x1ABC9C
        )
        embed.add_field(
            name="<:bot:1428163130663375029> **Auto-Response:**",
            value="The bot will now respond when users mention this keyword!",
            inline=False
        )
        await ctx.send(embed=embed)

    @vanity_keywords.command(name="remove", aliases=['delete', 'del'])
    @blacklist_check()
    @commands.has_permissions(manage_guild=True)
    async def keywords_remove(self, ctx, *, keyword: str):
        """Remove a trigger keyword"""
        keyword = keyword.lower().strip()
        
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM vanity_keywords 
                WHERE guild_id = ? AND keyword = ?
            ''', (ctx.guild.id, keyword))
            
            if cursor.rowcount == 0:
                embed = discord.Embed(
                    title=" Keyword Not Found",
                    description=f"The keyword `{keyword}` is not configured!",
                    color=0xED4245
                )
                await ctx.send(embed=embed)
                return
            
            conn.commit()
        
        embed = discord.Embed(
            title=" Keyword Removed",
            description=f" **Removed:** `{keyword}`",
            color=0x1ABC9C
        )
        await ctx.send(embed=embed)

    @vanity_keywords.command(name="clear")
    @blacklist_check()
    @commands.has_permissions(manage_guild=True)
    async def keywords_clear(self, ctx):
        """Remove all trigger keywords"""
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM vanity_keywords WHERE guild_id = ?', (ctx.guild.id,))
            count = cursor.fetchone()[0]
            
            if count == 0:
                embed = discord.Embed(
                    title=" No Keywords to Clear",
                    description="No keywords are currently configured!",
                    color=0xFEE75C
                )
                await ctx.send(embed=embed)
                return
            
            cursor.execute('DELETE FROM vanity_keywords WHERE guild_id = ?', (ctx.guild.id,))
            conn.commit()
        
        embed = discord.Embed(
            title=" All Keywords Cleared",
            description=f"Removed all {count} trigger keywords!",
            color=0x1ABC9C
        )
        await ctx.send(embed=embed)

    @vanity.command(name="message")
    @blacklist_check()
    @commands.has_permissions(manage_guild=True)
    async def vanity_message(self, ctx, *, message: str):
        """Set custom auto-responder message"""
        if len(message) > 1000:
            embed = discord.Embed(
                title=" Message Too Long",
                description="Custom message must be under 1000 characters!",
                color=0xED4245
            )
            await ctx.send(embed=embed)
            return
        
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO vanity_config (guild_id) VALUES (?)
            ''', (ctx.guild.id,))
            cursor.execute('''
                UPDATE vanity_config SET custom_message = ?, updated_at = ? 
                WHERE guild_id = ?
            ''', (message, datetime.now(), ctx.guild.id))
            conn.commit()
        
        embed = discord.Embed(
            title="✅ Custom Message Set!",
            description="💬 **New auto-responder message:**",
            color=0x1ABC9C
        )
        embed.add_field(
            name="📝 **Preview:**",
            value=message,
            inline=False
        )
        embed.add_field(
            name="💡 **Variables:**",
            value=(
                "`{vanity}` - Your vanity URL\n"
                "`{server}` - Server name\n"
                "`{user}` - User mention"
            ),
            inline=False
        )
        await ctx.send(embed=embed)

    @vanity.group(name="embed", invoke_without_command=True)
    @blacklist_check()
    @commands.has_permissions(manage_guild=True)
    async def vanity_embed(self, ctx):
        """Customize auto-responder embed appearance"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="🎨 Embed Customization",
                description="**Make your auto-responder stand out!**",
                color=0x1ABC9C
            )
            
            embed.add_field(
                name="🎨 **Appearance:**",
                value=(
                    "`vanity embed color <hex>` - Set embed color\n"
                    "`vanity embed title <text>` - Set embed title\n"
                    "`vanity embed footer <text>` - Set embed footer\n"
                    "`vanity embed thumbnail <url>` - Set thumbnail image"
                ),
                inline=False
            )
            
            embed.add_field(
                name="<:cog:1428163115136057486> **Management:**",
                value=(
                    "``\\n"
                    "`vanity embed reset` - Reset to default"
                ),
                inline=False
            )
            
            await ctx.send(embed=embed)

    @vanity_embed.command(name="color")
    @blacklist_check()
    @commands.has_permissions(manage_guild=True)
    async def embed_color(self, ctx, *, color_hex: str):
        """Set embed color (hex format: #FF5733 or FF5733)"""
        # Clean and validate hex color
        color_hex = color_hex.strip().replace('#', '')
        if not re.match(r'^[0-9A-Fa-f]{6}$', color_hex):
            embed = discord.Embed(
                title="❌ Invalid Color",
                description="Please provide a valid hex color code!\n**Examples:** `#FF5733`, `00FF00`, `#5865F2`",
                color=0xED4245
            )
            await ctx.send(embed=embed)
            return
        
        color_int = int(color_hex, 16)
        
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO vanity_config (guild_id) VALUES (?)
            ''', (ctx.guild.id,))
            cursor.execute('''
                UPDATE vanity_config SET embed_color = ?, updated_at = ? 
                WHERE guild_id = ?
            ''', (color_int, datetime.now(), ctx.guild.id))
            conn.commit()
        
        embed = discord.Embed(
            title="🎨 Embed Color Updated!",
            description=f"**New Color:** #{color_hex.upper()}",
            color=color_int
        )
        embed.add_field(
            name="✨ **Preview:**",
            value="This is how your vanity embeds will look!",
            inline=False
        )
        await ctx.send(embed=embed)

    @vanity_embed.command(name="reset")
    @blacklist_check()
    @commands.has_permissions(manage_guild=True)
    async def embed_reset(self, ctx):
        """Reset embed to default settings"""
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE vanity_config 
                SET embed_color = ?, embed_title = NULL, embed_description = NULL,
                    embed_footer = NULL, embed_thumbnail = NULL, updated_at = ?
                WHERE guild_id = ?
            ''', (1752220, datetime.now(), ctx.guild.id))  # Teal color as integer
            conn.commit()
        
        embed = discord.Embed(
            title="🔄 Embed Reset Complete!",
            description="All embed settings have been reset to defaults.",
            color=0x1ABC9C
        )
        embed.add_field(
            name="<:cog:1428163115136057486> **Default Settings:**",
            value=(
                "• **Color:** Teal\n"
                "• **Title:** 🔗 Server Invite\n"
                "• **Footer:** Thanks for repping!\n"
                "• **Thumbnail:** None"
            ),
            inline=False
        )
        await ctx.send(embed=embed)

    @vanity.command(name="stats", aliases=['statistics', 'analytics'])
    @blacklist_check()
    async def vanity_stats(self, ctx, user: Optional[discord.Member] = None):
        """View vanity statistics for user or server"""
        if user is None:
            # Server statistics
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.cursor()
                
                # Get server config
                cursor.execute('''
                    SELECT vanity_url, auto_responder, auto_responder_message, vanity_role_id
                    FROM vanity_config WHERE guild_id = ?
                ''', (ctx.guild.id,))
                config = cursor.fetchone()
                
                # Get total reps today
                today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                cursor.execute('''
                    SELECT COUNT(*) FROM vanity_stats 
                    WHERE guild_id = ? AND rep_date >= ?
                ''', (ctx.guild.id, today))
                reps_today = cursor.fetchone()[0]
                
                # Get total reps all time
                cursor.execute('''
                    SELECT COUNT(*) FROM vanity_stats WHERE guild_id = ?
                ''', (ctx.guild.id,))
                total_reps = cursor.fetchone()[0]
                
                # Get top reppers
                cursor.execute('''
                    SELECT user_id, COUNT(*) as rep_count
                    FROM vanity_stats WHERE guild_id = ?
                    GROUP BY user_id ORDER BY rep_count DESC LIMIT 3
                ''', (ctx.guild.id,))
                top_reppers = cursor.fetchall()
            
            embed = discord.Embed(
                title="📊 Server Vanity Statistics",
                description=f"**{ctx.guild.name} Rep Analytics**",
                color=0x1ABC9C
            )
            
            # Configuration Status
            if config:
                vanity_url, auto_responder, auto_responder_message, role_id = config
                status_text = "✅ Configured" if vanity_url else "❌ Not Set"
                responder_status = "🟢 Enabled" if auto_responder else "🔴 Disabled"
                role_mention = f"<@&{role_id}>" if role_id else "None"
                
                embed.add_field(
                    name="<:cog:1428163115136057486> **Configuration**",
                    value=(
                        f"**Vanity URL:** {status_text}\n"
                        f"**Auto-Responder:** {responder_status}\n"
                        f"**Vanity Role:** {role_mention}"
                    ),
                    inline=True
                )
            
            embed.add_field(
                name="📈 **Rep Statistics**",
                value=(
                    f"**Today:** {reps_today:,}\n"
                    f"**All Time:** {total_reps:,}\n"
                    f"**Average/Day:** {total_reps // max(1, (datetime.now() - ctx.guild.created_at).days):,}"
                ),
                inline=True
            )
            
            if top_reppers:
                top_list = []
                for i, (user_id, count) in enumerate(top_reppers, 1):
                    try:
                        user = ctx.guild.get_member(user_id)
                        name = user.display_name if user else f"User {user_id}"
                        top_list.append(f"{['🥇', '🥈', '🥉'][i-1]} **{name}:** {count:,}")
                    except:
                        continue
                
                embed.add_field(
                    name="<:trophy:1428163126360146034> **Top Reppers**",
                    value="\n".join(top_list) if top_list else "No data yet",
                    inline=False
                )
        
        else:
            # Individual user statistics
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.cursor()
                
                # Get user rep count
                cursor.execute('''
                    SELECT COUNT(*) FROM vanity_stats 
                    WHERE guild_id = ? AND user_id = ?
                ''', (ctx.guild.id, user.id))
                user_reps = cursor.fetchone()[0]
                
                # Get user rank
                cursor.execute('''
                    SELECT COUNT(DISTINCT user_id) + 1 FROM vanity_stats s1
                    WHERE s1.guild_id = ? AND (
                        SELECT COUNT(*) FROM vanity_stats s2 
                        WHERE s2.guild_id = s1.guild_id AND s2.user_id = s1.user_id
                    ) > (
                        SELECT COUNT(*) FROM vanity_stats s3
                        WHERE s3.guild_id = ? AND s3.user_id = ?
                    )
                ''', (ctx.guild.id, ctx.guild.id, user.id))
                user_rank = cursor.fetchone()[0] if user_reps > 0 else "N/A"
                
                # Get last rep date
                cursor.execute('''
                    SELECT MAX(rep_date) FROM vanity_stats 
                    WHERE guild_id = ? AND user_id = ?
                ''', (ctx.guild.id, user.id))
                last_rep = cursor.fetchone()[0]
                # Normalize last_rep into a Discord relative timestamp if possible
                last_rep_display = 'Never'
                if last_rep:
                    ts = None
                    try:
                        # If it's already a datetime object
                        if isinstance(last_rep, datetime):
                            ts = int(last_rep.timestamp())
                        else:
                            # If it's an integer/float timestamp string
                            try:
                                ts = int(float(last_rep))
                            except Exception:
                                # Try ISO format first, then fallback to common SQLite format
                                try:
                                    dt = datetime.fromisoformat(str(last_rep))
                                except Exception:
                                    try:
                                        dt = datetime.strptime(str(last_rep), '%Y-%m-%d %H:%M:%S')
                                    except Exception:
                                        dt = None
                                if dt:
                                    ts = int(dt.timestamp())
                    except Exception:
                        ts = None
                    if ts:
                        last_rep_display = f'<t:{ts}:R>'
                    else:
                        # As a fallback, show the raw value
                        last_rep_display = str(last_rep)
            
            embed = discord.Embed(
                title="👤 Individual Rep Statistics",
                description=f"**{user.display_name}'s Rep Activity**",
                color=0x1ABC9C
            )
            embed.set_thumbnail(url=user.display_avatar.url)
            
            embed.add_field(
                name="📊 **Rep Stats**",
                value=(
                    f"**Total Reps:** {user_reps:,}\n"
                    f"**Server Rank:** #{user_rank}\n"
                    f"**Last Rep:** {last_rep_display}"
                ),
                inline=False
            )
            
            # Check if user has vanity role
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT vanity_role_id FROM vanity_config WHERE guild_id = ?
                ''', (ctx.guild.id,))
                role_config = cursor.fetchone()
                
                if role_config and role_config[0]:
                    vanity_role = ctx.guild.get_role(role_config[0])
                    has_role = vanity_role in user.roles if vanity_role else False
                    role_status = "✅ Active Repper" if has_role else "⏳ Earn More Reps"
                    
                    embed.add_field(
                        name="🎭 **Vanity Role**",
                        value=f"**Status:** {role_status}",
                        inline=False
                    )
        
        await ctx.send(embed=embed)

    @vanity.command(name="leaderboard", aliases=['lb', 'top'])
    @blacklist_check()
    async def vanity_leaderboard(self, ctx, limit: int = 10):
        """View top vanity reppers leaderboard"""
        if limit > 25:
            limit = 25
        elif limit < 1:
            limit = 10
        
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT user_id, COUNT(*) as rep_count
                FROM vanity_stats WHERE guild_id = ?
                GROUP BY user_id ORDER BY rep_count DESC LIMIT ?
            ''', (ctx.guild.id, limit))
            leaderboard = cursor.fetchall()
        
        if not leaderboard:
            embed = discord.Embed(
                title="📊 Vanity Leaderboard",
                description="No rep activity yet! Be the first to start repping!",
                color=0xFEE75C
            )
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title="🏆 Vanity Rep Leaderboard",
            description=f"**Top {len(leaderboard)} Server Reppers**",
            color=0x1ABC9C
        )
        
        leaderboard_text = []
        for i, (user_id, rep_count) in enumerate(leaderboard, 1):
            try:
                user = ctx.guild.get_member(user_id)
                name = user.display_name if user else f"User {user_id}"
                
                # Add medal emojis for top 3
                if i == 1:
                    medal = "🥇"
                elif i == 2:
                    medal = "🥈"
                elif i == 3:
                    medal = "🥉"
                else:
                    medal = f"`{i:2d}.`"
                
                leaderboard_text.append(f"{medal} **{name}** - {rep_count:,} reps")
            except:
                continue
        
        embed.add_field(
            name="📈 **Rankings:**",
            value="\n".join(leaderboard_text),
            inline=False
        )
        
        embed.set_footer(text=f"📊 Showing top {len(leaderboard)} reppers")
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        """Auto-responder listener for vanity keywords"""
        if message.author.bot or not message.guild:
            return
        
        # Check if auto-responder is enabled and get full embed configuration
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT auto_responder, vanity_url, auto_responder_message, embed_color, response_channel_id,
                       embed_title, embed_description
                FROM vanity_config WHERE guild_id = ?
            ''', (message.guild.id,))
            config = cursor.fetchone()
            
            if not config or not config[0]:  # auto_responder not enabled
                return
            
            (auto_responder, vanity_url, auto_responder_message, embed_color, response_channel_id,
             embed_title, embed_description) = config
            
            # Check if message contains any trigger keywords
            cursor.execute('''
                SELECT keyword FROM vanity_keywords WHERE guild_id = ?
            ''', (message.guild.id,))
            keywords = [row[0] for row in cursor.fetchall()]
            
            if not keywords:
                return
            
            message_content = message.content.lower()
            triggered_keyword = None
            
            for keyword in keywords:
                if keyword in message_content:
                    triggered_keyword = keyword
                    break
            
            if not triggered_keyword:
                return
            
            # Check rep channel restriction
            if response_channel_id and message.channel.id != response_channel_id:
                return
            
            # Log the rep activity
            cursor.execute('''
                INSERT INTO vanity_stats (guild_id, user_id, rep_date, keyword_used)
                VALUES (?, ?, ?, ?)
            ''', (message.guild.id, message.author.id, datetime.now(), triggered_keyword))
            
            cursor.execute('''
                INSERT INTO vanity_logs (guild_id, user_id, action, details)
                VALUES (?, ?, ?, ?)
            ''', (message.guild.id, message.author.id, 'keyword_trigger', f'Triggered: {triggered_keyword}'))
            
            conn.commit()
        
        # Create auto-responder message with fallback
        if not vanity_url:
            vanity_url = "your-server"
        
        # Use auto_responder_message if available, otherwise provide basic default
        if auto_responder_message:
            # Use custom message
            response_message = auto_responder_message
        else:
            # Provide basic default message
            response_message = f"Rep **{vanity_url}** for access! 🎉"
        
        # Use custom embed configuration or defaults (for embed mode)
        title = embed_title or "<:bot:1428163130663375029> Auto-Responder"
        description = embed_description or response_message
        footer_text = f"Auto-response to '{triggered_keyword}' • Thanks for repping!"
        
        # Get user's current rep count for variable replacement
        with sqlite3.connect(self.db.db_path) as conn2:
            cursor2 = conn2.cursor()
            cursor2.execute('''
                SELECT COUNT(*) FROM vanity_stats WHERE guild_id = ? AND user_id = ?
            ''', (message.guild.id, message.author.id))
            result = cursor2.fetchone()
            rep_count = result[0] if result else 0
        
        # Prepare comprehensive variables for replacement
        variables = {
            'user': message.author.display_name,
            'mention': message.author.mention,
            'user_avatar': message.author.display_avatar.url,
            'user_nick': message.author.display_name,
            'user_id': str(message.author.id),
            'server': message.guild.name,
            'guild': message.guild.name,
            'server_icon': message.guild.icon.url if message.guild.icon else 'https://cdn.discordapp.com/embed/avatars/0.png',
            'server_id': str(message.guild.id),
            'server_boostcount': str(message.guild.premium_subscription_count),
            'server_boostlevel': str(message.guild.premium_tier),
            'member_count': str(message.guild.member_count),
            'vanity': vanity_url,
            'channel': message.channel.mention,
            'keyword': triggered_keyword,
            'rep_count': str(rep_count),
            'bot_name': self.bot.user.display_name,
            'prefix': '!',  # You can make this dynamic if needed
            'invite': f"discord.gg/{vanity_url}",
            'time': datetime.now().strftime("%I:%M %p"),
            'date': datetime.now().strftime("%B %d, %Y"),
            'day': datetime.now().strftime("%A"),
            'month': datetime.now().strftime("%B"),
            'year': datetime.now().strftime("%Y")
        }
        
        # Replace variables in all text fields using enhanced function
        response_message = replace_variables(response_message, **variables)
        title = replace_variables(title, **variables)
        description = replace_variables(description, **variables)
        footer_text = replace_variables(footer_text, **variables)
        
        # Send simple message if using basic auto responder, embed if custom configured
        try:
            if not embed_title and not embed_description and auto_responder_message:
                # Send simple message response
                await message.channel.send(response_message)
            else:
                # Send full embed response
                embed = discord.Embed(
                    title=title,
                    description=description,
                    color=embed_color or 0x1ABC9C
                )
                
                # Set custom footer
                embed.set_footer(
                    text=footer_text,
                    icon_url=message.author.display_avatar.url
                )
                
                await message.channel.send(embed=embed)
                
        except discord.Forbidden:
            # Fallback to plain text if embed/message fails
            fallback_msg = f"Rep **{vanity_url}** for access!"
            await message.channel.send(fallback_msg)
        
        # Note: We do NOT log this as a rep or give roles - this is just encouragement!

    async def manage_vanity_role(self, guild: discord.Guild, user: discord.Member, embed: discord.Embed) -> Optional[str]:
        """Comprehensive vanity role management for all rep scenarios"""
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            
            # Get vanity role configuration
            cursor.execute('''
                SELECT vanity_role_id FROM vanity_config WHERE guild_id = ?
            ''', (guild.id,))
            role_config = cursor.fetchone()
            
            if not role_config or not role_config[0]:
                return None
            
            vanity_role = guild.get_role(role_config[0])
            if not vanity_role:
                return None
            
            # Get current user rep count and recent activity
            cursor.execute('''
                SELECT COUNT(*) FROM vanity_stats 
                WHERE guild_id = ? AND user_id = ?
            ''', (guild.id, user.id))
            user_reps = cursor.fetchone()[0]
            
            # Check for recent activity (last 24 hours) to determine if role should be kept
            cursor.execute('''
                SELECT COUNT(*) FROM vanity_stats 
                WHERE guild_id = ? AND user_id = ? AND rep_date >= datetime('now', '-24 hours')
            ''', (guild.id, user.id))
            recent_reps = cursor.fetchone()[0]
            
            has_role = vanity_role in user.roles
            # Instant role logic: Give role if ANY reps, keep role if recent activity (last 24h)
            should_have_role = user_reps > 0  # Any reps at all
            should_keep_role = recent_reps > 0 or user_reps >= 5  # Recent activity OR established repper (5+ total reps)
            
            try:
                if should_have_role and not has_role:
                    # Give role instantly on any rep
                    await user.add_roles(vanity_role, reason=f"Instant vanity role assignment - {user_reps} reps")
                    return f"🎉 **Role Earned!** You now have the {vanity_role.mention} role! ({user_reps} reps)"
                
                elif has_role and not should_keep_role:
                    # Remove role if no recent activity and not established repper
                    await user.remove_roles(vanity_role, reason=f"No recent activity - {recent_reps} reps in last 24h")
                    return f"📉 **Role Removed** - No recent activity (Need activity to keep {vanity_role.mention})"
                
                elif has_role:
                    # User has role and qualifies - acknowledge with activity status
                    activity_status = f"{recent_reps} recent" if recent_reps > 0 else "established repper"
                    return f"✅ **Active Repper** - {vanity_role.mention} ({user_reps} total reps, {activity_status})"
                
            except discord.Forbidden:
                return f"⚠️ **Permission Error** - Cannot manage {vanity_role.mention} role"
            except Exception as e:
                return f"❌ **Error** - Role management failed"
        
        return None

    async def send_vanity_channel_message(self, guild: discord.Guild, user: discord.Member, source_channel: discord.TextChannel, keyword: str, vanity_url: str):
        """Send vanity channel message when someone reps"""
        try:
            # Get channel message configuration
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT channel_message_data, channel_id FROM vanity_config WHERE guild_id = ?
                ''', (guild.id,))
                config = cursor.fetchone()
                
                if not config or not config[0] or not config[1]:
                    return  # No channel message configured - fail silently until setup
                
                channel_message_data, channel_id = config
            
            # Get the target channel
            target_channel = guild.get_channel(channel_id)
            if not target_channel or not isinstance(target_channel, discord.TextChannel):
                return  # Channel not found or not a text channel
            
            # Parse the embed data
            embed_data = json.loads(channel_message_data)
            
            # Get user's total rep count for variables
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT COUNT(*) FROM vanity_stats WHERE guild_id = ? AND user_id = ?
                ''', (guild.id, user.id))
                rep_count = cursor.fetchone()[0]
            
            # Create embed with variable substitution
            embed = discord.Embed(
                title=embed_data.get("title", "Server Rep"),
                description=embed_data.get("description", "Thanks for repping!"),
                color=embed_data.get("color", 0x5865F2)
            )
            
            # Prepare comprehensive variables for replacement
            var_data = {
                'user': user.display_name,
                'mention': user.mention,
                'user_avatar': user.display_avatar.url if user.display_avatar else user.default_avatar.url,
                'user_nick': user.display_name,
                'user_id': str(user.id),
                'server': guild.name,
                'guild': guild.name,
                'server_icon': guild.icon.url if guild.icon else 'https://cdn.discordapp.com/embed/avatars/0.png',
                'server_id': str(guild.id),
                'server_boostcount': str(guild.premium_subscription_count or 0),
                'server_boostlevel': str(guild.premium_tier),
                'member_count': str(guild.member_count),
                'vanity': vanity_url,
                'channel': source_channel.mention,
                'keyword': keyword,
                'rep_count': str(rep_count),
                'bot_name': guild.me.display_name if guild.me else 'Sleepless',
                'prefix': '!',
                'invite': f'discord.gg/{vanity_url}' if vanity_url else 'discord.gg/example',
                'time': datetime.now().strftime("%I:%M %p"),
                'date': datetime.now().strftime("%B %d, %Y"),
                'day': datetime.now().strftime("%A"),
                'month': datetime.now().strftime("%B"),
                'year': datetime.now().strftime("%Y")
            }
            
            # Replace variables in title
            if embed.title:
                embed.title = replace_variables(embed.title, **var_data)
            
            # Replace variables in description
            if embed.description:
                embed.description = replace_variables(embed.description, **var_data)
            
            # Handle author fields
            if embed_data.get("author_name"):
                author_name = replace_variables(embed_data["author_name"], **var_data)
                embed.set_author(
                    name=author_name,
                    icon_url=embed_data.get("author_icon", "")
                )
            
            # Handle footer fields  
            if embed_data.get("footer_text"):
                footer_text = replace_variables(embed_data["footer_text"], **var_data)
                embed.set_footer(
                    text=footer_text,
                    icon_url=embed_data.get("footer_icon", "")
                )
            
            # Handle images
            if embed_data.get("thumbnail"):
                embed.set_thumbnail(url=embed_data["thumbnail"])
            if embed_data.get("image"):
                embed.set_image(url=embed_data["image"])
                
            # Handle fields with variable replacement
            for field in embed_data.get("fields", []):
                field_name = field.get("name", "No Name")
                field_value = field.get("value", "No Value")
                
                # Replace variables in field name and value using enhanced function
                field_name = replace_variables(field_name, **var_data)
                field_value = replace_variables(field_value, **var_data)
                
                embed.add_field(
                    name=field_name,
                    value=field_value,
                    inline=field.get("inline", True)
                )
            
            # Send the message
            await target_channel.send(embed=embed)
            print(f"[VANITY DEBUG] Successfully sent channel message to {target_channel.name}")
            
        except Exception as e:
            print(f"[VANITY DEBUG] Error sending vanity channel message: {e}")
            # Fail silently to not break the main rep functionality

    async def manage_vanity_role_silent(self, guild: discord.Guild, user: discord.Member) -> bool:
        """Silent vanity role management (no embed updates) for status/bio changes"""
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            
            # Get vanity role configuration
            cursor.execute('''
                SELECT vanity_role_id FROM vanity_config WHERE guild_id = ?
            ''', (guild.id,))
            role_config = cursor.fetchone()
            
            if not role_config or not role_config[0]:
                return False
            
            vanity_role = guild.get_role(role_config[0])
            if not vanity_role:
                return False
            
            # Get current user rep count and recent activity
            cursor.execute('''
                SELECT COUNT(*) FROM vanity_stats 
                WHERE guild_id = ? AND user_id = ?
            ''', (guild.id, user.id))
            user_reps = cursor.fetchone()[0]
            
            # Check for recent activity (last 24 hours)
            cursor.execute('''
                SELECT COUNT(*) FROM vanity_stats 
                WHERE guild_id = ? AND user_id = ? AND rep_date >= datetime('now', '-24 hours')
            ''', (guild.id, user.id))
            recent_reps = cursor.fetchone()[0]
            
            has_role = vanity_role in user.roles
            # Instant role logic: Give role if ANY reps, keep role if recent activity
            should_have_role = user_reps > 0  # Any reps at all
            should_keep_role = recent_reps > 0 or user_reps >= 5  # Recent activity OR established repper
            
            try:
                if should_have_role and not has_role:
                    # Give role silently and instantly
                    await user.add_roles(vanity_role, reason=f"Instant vanity role - {user_reps} reps (status/bio)")
                    return True
                
                elif has_role and not should_keep_role:
                    # Remove role silently if no recent activity
                    await user.remove_roles(vanity_role, reason=f"No recent activity - {recent_reps} reps in 24h")
                    return True
                
            except discord.Forbidden:
                pass
            except Exception:
                pass
        
        return False

    async def check_and_update_all_vanity_roles(self, guild: discord.Guild):
        """Check and update vanity roles for all users (maintenance function)"""
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            
            # Get vanity role configuration
            cursor.execute('''
                SELECT vanity_role_id FROM vanity_config WHERE guild_id = ?
            ''', (guild.id,))
            role_config = cursor.fetchone()
            
            if not role_config or not role_config[0]:
                return
            
            vanity_role = guild.get_role(role_config[0])
            if not vanity_role:
                return
            
            # Get all users with rep stats and recent activity
            cursor.execute('''
                SELECT user_id, COUNT(*) as rep_count
                FROM vanity_stats 
                WHERE guild_id = ?
                GROUP BY user_id
            ''', (guild.id,))
            
            user_reps = dict(cursor.fetchall())
            
            # Get users with recent activity (last 24 hours)
            cursor.execute('''
                SELECT user_id, COUNT(*) as recent_reps
                FROM vanity_stats 
                WHERE guild_id = ? AND rep_date >= datetime('now', '-24 hours')
                GROUP BY user_id
            ''', (guild.id,))
            
            recent_activity = dict(cursor.fetchall())
            updated_count = 0
            
            # Check all members with the role
            for member in vanity_role.members:
                user_rep_count = user_reps.get(member.id, 0)
                recent_reps = recent_activity.get(member.id, 0)
                
                # Remove role if no reps at all OR (no recent activity AND not established repper)
                should_keep_role = user_rep_count > 0 and (recent_reps > 0 or user_rep_count >= 5)
                
                if not should_keep_role:
                    try:
                        await member.remove_roles(vanity_role, reason=f"No recent activity ({recent_reps} in 24h, {user_rep_count} total)")
                        updated_count += 1
                    except discord.Forbidden:
                        pass
            
            # Check users who should have the role but don't (instant assignment for ANY reps)
            for user_id, rep_count in user_reps.items():
                if rep_count > 0:  # Any reps = should have role
                    member = guild.get_member(user_id)
                    if member and vanity_role not in member.roles:
                        try:
                            await member.add_roles(vanity_role, reason=f"Instant vanity role assignment - {rep_count} reps")
                            updated_count += 1
                        except discord.Forbidden:
                            pass
            
            return updated_count

    @vanity.command(name="roles", aliases=['role-check', 'role-update'])
    @blacklist_check()
    @commands.has_permissions(manage_guild=True)
    async def vanity_roles(self, ctx):
        """Check and update all vanity roles based on current rep counts"""
        
        # Send initial status message
        status_embed = discord.Embed(
            title="🔄 Checking Vanity Roles...",
            description="Analyzing all member rep counts and updating roles accordingly...",
            color=0x1ABC9C
        )
        status_message = await ctx.send(embed=status_embed)
        
        # Run the role update check
        updated_count = await self.check_and_update_all_vanity_roles(ctx.guild)
        
        if updated_count is None:
            result_embed = discord.Embed(
                title="❌ No Vanity Role Configured",
                description="Set up a vanity role first using `vanity role @RoleName`",
                color=0xED4245
            )
        elif updated_count == 0:
            result_embed = discord.Embed(
                title="✅ All Roles Up to Date",
                description="No role changes needed - all members have correct vanity roles!",
                color=0x1ABC9C
            )
        else:
            result_embed = discord.Embed(
                title="✅ Vanity Roles Updated",
                description=f"Successfully updated {updated_count} member role(s) based on rep counts.",
                color=0x1ABC9C
            )
            
        result_embed.add_field(
            name="💡 **Auto-Updates:**",
            value="Roles are automatically managed when users trigger auto-responder keywords!",
            inline=False
        )
        
        await status_message.edit(embed=result_embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Listen for member updates to catch status/bio changes that might indicate repping"""
        
        # Only process if status or activity changed
        if before.status == after.status and before.activities == after.activities:
            return
        
        print(f"[VANITY DEBUG] Member update detected: {after.display_name} in {after.guild.name}")
            
        # Check if they have the server invite in their status/bio
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT vanity_url FROM vanity_config WHERE guild_id = ?
            ''', (after.guild.id,))
            config = cursor.fetchone()
            
            if not config or not config[0]:  # No vanity URL configured
                print(f"[VANITY DEBUG] No vanity URL configured for guild {after.guild.id}")
                return
                
            vanity_url = config[0]
            print(f"[VANITY DEBUG] Checking for vanity URL '{vanity_url}' in {after.display_name}'s activities")
            
            # Check if user has server invite in their status/activity OR BIO
            server_mentioned = False
            detected_content = ""
            
            print(f"[VANITY DEBUG] {after.display_name} has {len(after.activities)} activities")
            
            # First, check Discord bio/profile (if accessible)
            try:
                # Check if member has bio attribute (newer Discord.py versions)
                bio_text = getattr(after, 'bio', None)
                if not bio_text:
                    # Try accessing through user object
                    user_obj = getattr(after, '_user', None)
                    if user_obj:
                        bio_text = getattr(user_obj, 'bio', None)
                
                if bio_text:
                    bio_lower = bio_text.lower()
                    if (vanity_url.lower() in bio_lower or 
                        after.guild.name.lower() in bio_lower or 
                        'discord.gg' in bio_lower):
                        server_mentioned = True
                        detected_content = f"Discord bio: {bio_text}"
                        print(f"[VANITY DEBUG] Found in Discord bio: {bio_text}")
                else:
                    print(f"[VANITY DEBUG] No bio found for {after.display_name}")
            except Exception as e:
                print(f"[VANITY DEBUG] Bio check failed (may require special intents): {e}")
            
            # If not found in bio, check activities/status
            if not server_mentioned:
                # Check custom status and activities
                for i, activity in enumerate(after.activities):
                    print(f"[VANITY DEBUG] Activity {i}: {type(activity).__name__} - {getattr(activity, 'name', 'No name')}")
                    
                    # Check activity name (works for all activity types)
                    if hasattr(activity, 'name') and activity.name:
                        activity_name_lower = activity.name.lower()
                        if (vanity_url.lower() in activity_name_lower or 
                            after.guild.name.lower() in activity_name_lower or 
                            'discord.gg' in activity_name_lower):
                            server_mentioned = True
                            detected_content = f"Activity name: {activity.name}"
                            print(f"[VANITY DEBUG] Found in activity name: {activity.name}")
                            break
                    
                    # Check activity state (for custom status) - use getattr for type safety
                    activity_state = getattr(activity, 'state', None)
                    if activity_state:
                        activity_state_lower = activity_state.lower()
                        if (vanity_url.lower() in activity_state_lower or 
                            after.guild.name.lower() in activity_state_lower or
                            'discord.gg' in activity_state_lower):
                            server_mentioned = True
                            detected_content = f"Custom status: {activity_state}"
                            print(f"[VANITY DEBUG] Found in custom status: {activity_state}")
                            break
                    
                    # Check activity details (only for Rich Presence activities) - use getattr for type safety
                    activity_details = getattr(activity, 'details', None)
                    if activity_details:
                        activity_details_lower = activity_details.lower()
                        if (vanity_url.lower() in activity_details_lower or 
                            after.guild.name.lower() in activity_details_lower or
                            'discord.gg' in activity_details_lower):
                            server_mentioned = True
                            detected_content = f"Activity details: {activity_details}"
                            print(f"[VANITY DEBUG] Found in activity details: {activity_details}")
                            break
            
            if server_mentioned:
                print(f"[VANITY DEBUG] 🎉 Rep detected for {after.display_name}! Content: {detected_content}")
                
                # Log this as a rep activity
                cursor.execute('''
                    INSERT INTO vanity_stats (guild_id, user_id, rep_date, keyword_used)
                    VALUES (?, ?, ?, ?)
                ''', (after.guild.id, after.id, datetime.now(), 'status_bio'))
                
                cursor.execute('''
                    INSERT INTO vanity_logs (guild_id, user_id, action, details)
                    VALUES (?, ?, ?, ?)
                ''', (after.guild.id, after.id, 'status_rep', f'Server mentioned in status/bio: {detected_content}'))
                
                conn.commit()
                print(f"[VANITY DEBUG] Logged rep activity to database")
                
                # Update their vanity role (with role management)
                role_result = await self.manage_vanity_role_silent(after.guild, after)
                print(f"[VANITY DEBUG] Role management result: {role_result}")
                
                # Send channel message for status/bio rep (use general channel as source)
                general_channel = next((ch for ch in after.guild.text_channels if ch.permissions_for(after.guild.me).send_messages), None)
                if general_channel:
                    await self.send_vanity_channel_message(after.guild, after, general_channel, 'status_bio', vanity_url)
                # Fail silently if no channel configured - user can set up with !vanity channelsetup
            else:
                print(f"[VANITY DEBUG] No server mention detected for {after.display_name}")

    @vanity.command(name="channelsetup", aliases=["channel-setup", "csetup"])
    @blacklist_check()
    @commands.has_permissions(manage_guild=True)
    async def vanity_channel_setup(self, ctx):
        """Setup vanity channel messages (sticky-style)"""
        setup_view = VanityChannelSetup(ctx.author.id)
        
        # Show the initial preview embed instead of setup instructions
        initial_embed = setup_view.build_embed()
        initial_embed.set_footer(text="💡 Use the buttons below to customize your vanity message • Click Variables to see available options")
        
        await ctx.send(embed=initial_embed, view=setup_view)

    @vanity.command(name="test-rep", aliases=["testrep", "simulaterep"])
    @blacklist_check()
    @commands.has_permissions(manage_guild=True)
    async def test_rep(self, ctx, member: Optional[discord.Member] = None):
        """Test the rep detection system (simulates someone repping the server)"""
        target_member = member or ctx.author
        
        # Get current configuration
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT vanity_url, vanity_role_id FROM vanity_config WHERE guild_id = ?
            ''', (ctx.guild.id,))
            result = cursor.fetchone()
            
            if not result:
                await ctx.send("❌ No vanity configuration found. Run `vanity setup` first.")
                return
                
            vanity_url, vanity_role_id = result
            vanity_url = vanity_url or "test-server"
            
            # Check if role exists
            role_status = "❌ No role configured"
            if vanity_role_id:
                vanity_role = ctx.guild.get_role(vanity_role_id)
                if vanity_role:
                    role_status = f"✅ Role: {vanity_role.mention}"
                else:
                    role_status = f"❌ Role ID {vanity_role_id} not found"
        
        # Show current setup
        embed = discord.Embed(
            title="🧪 Vanity Rep Test",
            description=f"Testing rep detection for {target_member.mention}",
            color=0x1ABC9C
        )
        embed.add_field(name="Vanity URL", value=f"`discord.gg/{vanity_url}`", inline=True)
        embed.add_field(name="Vanity Role", value=role_status, inline=True)
        
        status_msg = await ctx.send(embed=embed)
        
        try:
            # Simulate a rep detection by logging in database
            cursor.execute('''
                INSERT INTO vanity_stats (guild_id, user_id, rep_date, keyword_used)
                VALUES (?, ?, ?, ?)
            ''', (ctx.guild.id, target_member.id, datetime.now(), 'test_simulation'))
            
            cursor.execute('''
                INSERT INTO vanity_logs (guild_id, user_id, action, details)
                VALUES (?, ?, ?, ?)
            ''', (ctx.guild.id, target_member.id, 'test_rep', 'Simulated rep for testing'))
            
            conn.commit()
            
            # Test role management
            role_result = await self.manage_vanity_role_silent(ctx.guild, target_member)
            
            # Test channel message
            await self.send_vanity_channel_message(ctx.guild, target_member, ctx.channel, 'test_simulation', vanity_url)
            
            # Show results
            embed.add_field(
                name="✅ Test Results", 
                value=f"• Database logging: ✅ Success\n• Role management: {'✅ Success' if role_result else '❌ Failed or no role configured'}\n• Channel message: ✅ Sent (if configured)", 
                inline=False
            )
            embed.color = 0x00ff00
            
        except Exception as e:
            embed.add_field(name="❌ Error", value=f"Test failed: {str(e)}", inline=False)
            embed.color = 0xff0000
        
        await status_msg.edit(embed=embed)
        
        await status_msg.edit(embed=embed)

    @vanity.command(name="debug-status", aliases=["debugstatus", "checkstatus"])
    @blacklist_check()
    @commands.has_permissions(manage_guild=True)
    async def debug_status(self, ctx, member: Optional[discord.Member] = None):
        """Debug member status/activities for rep detection"""
        target_member = member or ctx.author
        
        embed = discord.Embed(
            title="🔍 Member Status Debug",
            description=f"Analyzing {target_member.mention}'s activities",
            color=0x5865F2
        )
        
        embed.add_field(name="Status", value=str(target_member.status), inline=True)
        embed.add_field(name="Activity Count", value=str(len(target_member.activities)), inline=True)
        
        # Get vanity config
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT vanity_url FROM vanity_config WHERE guild_id = ?', (ctx.guild.id,))
            result = cursor.fetchone()
            vanity_url = result[0] if result else None
        
        if vanity_url:
            embed.add_field(name="Looking For", value=f"`{vanity_url}`, `{ctx.guild.name}`, `discord.gg`", inline=False)
        
        # Analyze each activity
        for i, activity in enumerate(target_member.activities):
            activity_info = f"**Type:** {type(activity).__name__}\n"
            
            if hasattr(activity, 'name') and activity.name:
                activity_info += f"**Name:** {activity.name}\n"
            
            state = getattr(activity, 'state', None)
            if state:
                activity_info += f"**State:** {state}\n"
                
            details = getattr(activity, 'details', None)
            if details:
                activity_info += f"**Details:** {details}\n"
            
            embed.add_field(name=f"Activity {i+1}", value=activity_info or "No data", inline=True)
        
        if not target_member.activities:
            embed.add_field(name="Activities", value="No activities detected", inline=False)
        
        await ctx.send(embed=embed)

    @vanity.command(name="quicksetup", aliases=["qsetup"])
    @blacklist_check()
    @commands.has_permissions(manage_guild=True)
    async def quick_setup(self, ctx, vanity_url: str, vanity_role: Optional[discord.Role] = None):
        """Quick setup for vanity system
        
        Usage: vanity quicksetup <vanity_url> [@role]
        Example: vanity quicksetup sleepless @VIP
        """
        
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            
            # Ensure record exists
            cursor.execute('INSERT OR IGNORE INTO vanity_config (guild_id) VALUES (?)', (ctx.guild.id,))
            
            # Update vanity URL and enable auto-responder
            cursor.execute('''
                UPDATE vanity_config 
                SET vanity_url = ?, auto_responder = ?, updated_at = ?
                WHERE guild_id = ?
            ''', (vanity_url, 1, datetime.now(), ctx.guild.id))
            
            # Set role if provided
            if vanity_role:
                cursor.execute('''
                    UPDATE vanity_config 
                    SET vanity_role_id = ?
                    WHERE guild_id = ?
                ''', (vanity_role.id, ctx.guild.id))
            
            conn.commit()
        
        embed = discord.Embed(
            title="✅ Quick Setup Complete!",
            description="Basic vanity system has been configured",
            color=0x00ff00
        )
        embed.add_field(name="Vanity URL", value=f"`discord.gg/{vanity_url}`", inline=True)
        embed.add_field(name="Auto-Responder", value="✅ Enabled", inline=True)
        
        if vanity_role:
            embed.add_field(name="Vanity Role", value=vanity_role.mention, inline=True)
        else:
            embed.add_field(name="Vanity Role", value="❌ Not set (use `vanity role @RoleName`)", inline=True)
        
        embed.add_field(
            name="Next Steps:",
            value="• Test auto-responder: Type `pic` in chat\n• Test rep detection: Put server name in your Discord status\n• Configure channel messages: `vanity channelsetup`",
            inline=False
        )
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(VanitySystem(bot))
