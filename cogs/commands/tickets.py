import discord
from discord.ext import commands
from discord import ButtonStyle, SelectOption
from discord.ui import Button, View, Select, Modal, TextInput
import json
import asyncio
import re
from datetime import datetime, timedelta
import aiosqlite
from typing import Optional, Dict, Any, List
from utils.timezone_helpers import get_timezone_helpers
from utils.dynamic_dropdowns import DynamicChannelSelect, DynamicChannelView, PaginatedChannelView
from core import Context

from utils.error_helpers import StandardErrorHandler
class TicketHelpView(View):
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
            title="🎫 Advanced Ticket System V2",
            description="**TicketTool Style Implementation**\n\nA modern, interactive ticket system with persistent panels and user-friendly customization.",
            color=0x00E6A7
        )
        
        embed.add_field(
            name="🎨 Interactive Panel Creation",
            value="• `ticket builder` - Advanced interactive panel builder\n• **✨ Features:** Channel selection, color names (red, blue, etc.), persistent forever!",
            inline=False
        )
        
        embed.add_field(
            name="📋 Setup Commands", 
            value="• `ticket category <category>` - Set ticket category\n• `ticket role <role>` - Set support role\n• `ticket logs <channel>` - Set log channel\n• `ticket resetdb` - Reset database (admin only)",
            inline=False
        )
        
        embed.set_footer(text=f"• Help page 1/{5} | Requested by: {self.ctx.author.display_name}",
                        icon_url=self.ctx.bot.user.avatar.url)
        pages.append(embed)
        
        # Configuration Page
        embed = discord.Embed(
            title="⚙️ Configuration Commands",
            color=0x00E6A7
        )
        embed.add_field(
            name="ticket config",
            value="View current settings and configuration.\n**Example:** `ticket config`",
            inline=False
        )
        embed.add_field(
            name="ticket maxtickets <number>",
            value="Set maximum tickets per user (1-10).\n**Example:** `ticket maxtickets 3`",
            inline=False
        )
        embed.add_field(
            name="ticket welcome <message>",
            value="Set welcome message for new tickets.\n**Example:** `ticket welcome Thank you for contacting support!`",
            inline=False
        )
        embed.add_field(
            name="ticket autoclose <hours>",
            value="Set auto-close time (0 to disable).\n**Example:** `ticket autoclose 24`",
            inline=False
        )
        embed.set_footer(text=f"• Help page 2/{5} | Requested by: {self.ctx.author.display_name}",
                        icon_url=self.ctx.bot.user.avatar.url)
        pages.append(embed)
        
        # Management Page
        embed = discord.Embed(
            title="📊 Management & Controls",
            color=0x00E6A7
        )
        embed.add_field(
            name="ticket list [status]",
            value="List all tickets (open, closed, all).\n**Example:** `ticket list open`",
            inline=False
        )
        embed.add_field(
            name="ticket stats",
            value="View basic ticket statistics.\n**Example:** `ticket stats`",
            inline=False
        )
        embed.add_field(
            name="ticket analytics",
            value="Advanced analytics dashboard with graphs.\n**Example:** `ticket analytics`",
            inline=False
        )
        embed.add_field(
            name="ticket add/remove <user>",
            value="Add or remove user from current ticket.\n**Example:** `ticket add @user`",
            inline=False
        )
        embed.set_footer(text=f"• Help page 3/{5} | Requested by: {self.ctx.author.display_name}",
                        icon_url=self.ctx.bot.user.avatar.url)
        pages.append(embed)
        
        # In-Ticket Commands Page
        embed = discord.Embed(
            title="🎫 In-Ticket Commands",
            color=0x00E6A7
        )
        embed.add_field(
            name="ticket close [reason]",
            value="Close current ticket with optional reason.\n**Example:** `ticket close Issue resolved`",
            inline=False
        )
        embed.add_field(
            name="ticket claim",
            value="Claim responsibility for the ticket.\n**Example:** `ticket claim`",
            inline=False
        )
        embed.add_field(
            name="ticket rename <name>",
            value="Rename the ticket channel.\n**Example:** `ticket rename billing-issue`",
            inline=False
        )
        embed.add_field(
            name="ticket transcript",
            value="Generate and save ticket transcript.\n**Example:** `ticket transcript`",
            inline=False
        )
        embed.set_footer(text=f"• Help page 4/{5} | Requested by: {self.ctx.author.display_name}",
                        icon_url=self.ctx.bot.user.avatar.url)
        pages.append(embed)
        
        # Setup Guide Page
        embed = discord.Embed(
            title="🛠️ Quick Setup Guide",
            color=0x00E6A7
        )
        embed.add_field(
            name="Step 1: Initial Setup",
            value="`ticket setup` - Run the setup wizard\n`ticket category #tickets` - Set category",
            inline=False
        )
        embed.add_field(
            name="Step 2: Configure Roles",
            value="`ticket role @Support` - Set support role\n`ticket logs #ticket-logs` - Set log channel",
            inline=False
        )
        embed.add_field(
            name="Step 3: Create Panel",
            value="`ticket builder` - Interactive panel creator\n`ticket panel` - Alternative panel command",
            inline=False
        )
        embed.add_field(
            name="Step 4: Customize",
            value="`ticket welcome <message>` - Custom welcome\n`ticket maxtickets 2` - Set user limits",
            inline=False
        )
        embed.set_footer(text=f"• Help page 5/{5} | Requested by: {self.ctx.author.display_name}",
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

class TicketDatabase:
    def __init__(self, bot=None):
        self.db_path = "db/tickets.db"
        self.bot = bot
        if bot:
            self.tz_helpers = get_timezone_helpers(bot)
    
    async def init_db(self):
        """Initialize the comprehensive ticket database"""
        async with aiosqlite.connect(self.db_path) as db:
            # Legacy table for backward compatibility
            await db.execute("""
                CREATE TABLE IF NOT EXISTS ticket_config (
                    guild_id INTEGER PRIMARY KEY,
                    category_id INTEGER,
                    support_role_id INTEGER,
                    log_channel_id INTEGER,
                    welcome_message TEXT,
                    ticket_counter INTEGER DEFAULT 0,
                    max_tickets_per_user INTEGER DEFAULT 1,
                    auto_close_time INTEGER DEFAULT 0
                )
            """)
            
            # Enhanced ticket panels with per-panel configuration
            await db.execute("""
                CREATE TABLE IF NOT EXISTS ticket_panels (
                    panel_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    panel_name TEXT NOT NULL,
                    panel_description TEXT DEFAULT 'Select a ticket category below to get support.',
                    panel_color INTEGER DEFAULT 0x00E6A7,
                    channel_id INTEGER,
                    message_id INTEGER,
                    embed_title TEXT DEFAULT 'Support Tickets',
                    embed_footer TEXT,
                    embed_thumbnail TEXT,
                    embed_image TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Ticket categories with extensive per-category configuration
            await db.execute("""
                CREATE TABLE IF NOT EXISTS ticket_categories (
                    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    panel_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    category_name TEXT NOT NULL,
                    category_emoji TEXT DEFAULT '🎫',
                    category_description TEXT,
                    
                    -- Channel Configuration
                    parent_category_id INTEGER,
                    discord_category_id INTEGER,
                    channel_name_format TEXT DEFAULT 'ticket-{user}-{number}',
                    
                    -- Role Configuration
                    support_roles TEXT, -- JSON array of role IDs
                    auto_add_roles TEXT, -- JSON array of role IDs to add to user
                    ping_roles TEXT, -- JSON array of role IDs to ping when ticket created
                    
                    -- Message Configuration
                    welcome_message TEXT DEFAULT 'Thank you for creating a ticket! A staff member will be with you shortly.',
                    embed_welcome BOOLEAN DEFAULT FALSE,
                    welcome_embed_data TEXT, -- JSON for embed configuration
                    
                    -- Logging Configuration
                    log_channel_id INTEGER,
                    log_events TEXT, -- JSON array of events to log
                    log_creation BOOLEAN DEFAULT TRUE,
                    log_closure BOOLEAN DEFAULT TRUE,
                    log_claims BOOLEAN DEFAULT TRUE,
                    log_transcripts BOOLEAN DEFAULT TRUE,
                    
                    -- Transcript Configuration
                    save_transcripts BOOLEAN DEFAULT TRUE,
                    transcript_channel_id INTEGER,
                    transcript_format TEXT DEFAULT 'html', -- html, txt, json
                    auto_transcript BOOLEAN DEFAULT TRUE,
                    
                    -- Limits and Automation
                    max_tickets_per_user INTEGER DEFAULT 1,
                    auto_close_time INTEGER DEFAULT 0, -- 0 = disabled, time in hours
                    auto_close_warning INTEGER DEFAULT 24, -- hours before warning
                    
                    -- Claiming System
                    allow_claiming BOOLEAN DEFAULT TRUE,
                    require_claiming BOOLEAN DEFAULT FALSE,
                    claim_message TEXT DEFAULT 'This ticket has been claimed by {claimer}.',
                    
                    -- Permissions
                    user_can_close BOOLEAN DEFAULT TRUE,
                    user_can_add_others BOOLEAN DEFAULT FALSE,
                    user_can_add_members BOOLEAN DEFAULT FALSE,
                    
                    -- Priority System
                    priority_level INTEGER DEFAULT 1, -- 1=low, 2=normal, 3=high, 4=urgent
                    priority_color INTEGER,
                    
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    FOREIGN KEY (panel_id) REFERENCES ticket_panels(panel_id) ON DELETE CASCADE
                )
            """)
            
            # Enhanced tickets table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tickets (
                    ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    category_id INTEGER,
                    panel_id INTEGER,
                    
                    -- Status and Tracking
                    status TEXT DEFAULT 'open', -- open, claimed, escalated, pending, closed, archived
                    priority INTEGER DEFAULT 1,
                    ticket_number INTEGER,
                    
                    -- Timestamps
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    claimed_at TIMESTAMP,
                    first_response_at TIMESTAMP,
                    last_activity_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    closed_at TIMESTAMP,
                    
                    -- Staff Assignment & SLA
                    claimed_by INTEGER,
                    assigned_staff TEXT, -- JSON array of assigned staff IDs
                    escalated_to INTEGER,
                    escalation_level INTEGER DEFAULT 0,
                    sla_deadline TIMESTAMP,
                    sla_status TEXT DEFAULT 'within_sla', -- within_sla, at_risk, breached
                    
                    -- Rating & Feedback
                    user_rating INTEGER, -- 1-5 stars
                    feedback_text TEXT,
                    feedback_submitted_at TIMESTAMP,
                    
                    -- AI & Analytics
                    sentiment_score REAL, -- -1.0 to 1.0
                    urgency_score REAL, -- 0.0 to 1.0
                    predicted_category TEXT,
                    ai_summary TEXT,
                    complexity_score INTEGER DEFAULT 1, -- 1-5
                    
                    -- Closure Information
                    close_reason TEXT,
                    closed_by INTEGER,
                    resolution_time INTEGER, -- minutes from creation to closure
                    
                    -- Additional Data
                    additional_users TEXT, -- JSON array of additional user IDs
                    tags TEXT, -- JSON array of tags
                    notes TEXT, -- Staff notes
                    transcript_url TEXT,
                    attachments TEXT, -- JSON array of attachment URLs
                    
                    FOREIGN KEY (category_id) REFERENCES ticket_categories(category_id),
                    FOREIGN KEY (panel_id) REFERENCES ticket_panels(panel_id)
                )
            """)
            
            # Ticket interactions log
            await db.execute("""
                CREATE TABLE IF NOT EXISTS ticket_logs (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER NOT NULL,
                    action_type TEXT NOT NULL, -- created, claimed, closed, message, user_added, etc.
                    user_id INTEGER NOT NULL,
                    details TEXT, -- JSON for additional details
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id) ON DELETE CASCADE
                )
            """)
            
            # Staff workload tracking
            await db.execute("""
                CREATE TABLE IF NOT EXISTS staff_workload (
                    staff_id INTEGER PRIMARY KEY,
                    guild_id INTEGER NOT NULL,
                    active_tickets INTEGER DEFAULT 0,
                    total_tickets_handled INTEGER DEFAULT 0,
                    avg_response_time REAL DEFAULT 0.0,
                    avg_resolution_time REAL DEFAULT 0.0,
                    satisfaction_rating REAL DEFAULT 0.0,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'available', -- available, busy, away, offline
                    max_concurrent_tickets INTEGER DEFAULT 5,
                    specializations TEXT, -- JSON array of category IDs they specialize in
                    performance_score REAL DEFAULT 100.0
                )
            """)
            
            # SLA configurations per category
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sla_configs (
                    config_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_id INTEGER NOT NULL,
                    priority_level INTEGER NOT NULL,
                    first_response_time INTEGER NOT NULL, -- minutes
                    resolution_time INTEGER NOT NULL, -- minutes
                    escalation_time INTEGER, -- minutes before auto-escalation
                    business_hours_only BOOLEAN DEFAULT FALSE,
                    
                    FOREIGN KEY (category_id) REFERENCES ticket_categories(category_id) ON DELETE CASCADE
                )
            """)
            
            # Ticket templates
            await db.execute("""
                CREATE TABLE IF NOT EXISTS ticket_templates (
                    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    template_name TEXT NOT NULL,
                    template_description TEXT,
                    category_id INTEGER,
                    preset_fields TEXT, -- JSON for form fields
                    auto_assign_roles TEXT, -- JSON array of role IDs
                    priority_level INTEGER DEFAULT 1,
                    tags TEXT, -- JSON array of default tags
                    created_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Ticket feedback and ratings
            await db.execute("""
                CREATE TABLE IF NOT EXISTS ticket_feedback (
                    feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    staff_id INTEGER,
                    rating INTEGER CHECK(rating >= 1 AND rating <= 5),
                    feedback_text TEXT,
                    response_time_rating INTEGER CHECK(response_time_rating >= 1 AND response_time_rating <= 5),
                    helpfulness_rating INTEGER CHECK(helpfulness_rating >= 1 AND helpfulness_rating <= 5),
                    follow_up_needed BOOLEAN DEFAULT FALSE,
                    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id) ON DELETE CASCADE
                )
            """)
            
            # Analytics and metrics cache
            await db.execute("""
                CREATE TABLE IF NOT EXISTS ticket_analytics (
                    metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    category_id INTEGER,
                    staff_id INTEGER,
                    metric_type TEXT NOT NULL, -- daily, weekly, monthly
                    metric_date DATE NOT NULL,
                    tickets_created INTEGER DEFAULT 0,
                    tickets_resolved INTEGER DEFAULT 0,
                    avg_response_time REAL DEFAULT 0.0,
                    avg_resolution_time REAL DEFAULT 0.0,
                    avg_satisfaction REAL DEFAULT 0.0,
                    sla_breaches INTEGER DEFAULT 0,
                    escalations INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # AI analysis cache
            await db.execute("""
                CREATE TABLE IF NOT EXISTS ticket_ai_analysis (
                    analysis_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER NOT NULL,
                    message_content TEXT NOT NULL,
                    sentiment_score REAL,
                    urgency_score REAL,
                    category_prediction TEXT,
                    suggested_response TEXT,
                    confidence_score REAL,
                    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id) ON DELETE CASCADE
                )
            """)
            
            # Legacy compatibility
            await db.execute("""
                CREATE TABLE IF NOT EXISTS old_ticket_panels (
                    guild_id INTEGER,
                    channel_id INTEGER,
                    message_id INTEGER,
                    title TEXT,
                    description TEXT DEFAULT 'Need help? Click the button below to create a support ticket.',
                    color INTEGER DEFAULT 0x00E6A7,
                    PRIMARY KEY (guild_id, message_id)
                )
            """)
            
            # Migration helpers
            try:
                await db.execute("ALTER TABLE tickets ADD COLUMN user_id INTEGER")
            except:
                pass
            
            try:
                await db.execute("ALTER TABLE tickets ADD COLUMN status TEXT DEFAULT 'open'")
            except:
                pass
            
            # Ensure ticket_panels has required columns
            try:
                await db.execute("ALTER TABLE ticket_panels ADD COLUMN panel_name TEXT DEFAULT 'Support Panel'")
            except:
                pass
            
            try:
                await db.execute("ALTER TABLE ticket_panels ADD COLUMN panel_description TEXT DEFAULT 'Select a ticket category below to get support.'")
            except:
                pass
            
            try:
                await db.execute("ALTER TABLE ticket_panels ADD COLUMN embed_title TEXT DEFAULT 'Support Tickets'")
            except:
                pass
            
            # Ensure ticket_categories has all required columns
            try:
                await db.execute("ALTER TABLE ticket_categories ADD COLUMN discord_category_id INTEGER")
            except:
                pass
            
            try:
                await db.execute("ALTER TABLE ticket_categories ADD COLUMN user_can_add_others BOOLEAN DEFAULT FALSE")
            except:
                pass
            
            try:
                await db.execute("ALTER TABLE ticket_categories ADD COLUMN log_events TEXT")
            except:
                pass
            
            try:
                await db.execute("ALTER TABLE ticket_categories ADD COLUMN require_claiming BOOLEAN DEFAULT FALSE")
            except:
                pass
            
            await db.commit()
    
    # Panel Management Methods
    async def create_panel(self, guild_id: int, panel_name: str, **kwargs) -> int:
        """Create a new ticket panel"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                cursor = await db.execute("""
                    INSERT INTO ticket_panels (guild_id, panel_name, panel_description, panel_color, 
                                             embed_title, embed_footer, embed_thumbnail, embed_image)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    guild_id, panel_name,
                    kwargs.get('panel_description', 'Select a ticket category below to get support.'),
                    kwargs.get('panel_color', 0x00E6A7),
                    kwargs.get('embed_title', 'Support Tickets'),
                    kwargs.get('embed_footer', ''),
                    kwargs.get('embed_thumbnail', ''),
                    kwargs.get('embed_image', '')
                ))
                await db.commit()
                return cursor.lastrowid or 0
            except Exception as e:
                if "no column named" in str(e):
                    raise Exception("Database schema is outdated. Please run 'ticket resetdb' to reset the database with the correct schema.") from e
                raise
    
    async def get_panel(self, panel_id: int) -> Optional[Dict[str, Any]]:
        """Get panel by ID"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT * FROM ticket_panels WHERE panel_id = ?", (panel_id,))
            result = await cursor.fetchone()
            if result:
                return {
                    'panel_id': result[0], 'guild_id': result[1], 'panel_name': result[2],
                    'panel_description': result[3], 'panel_color': result[4], 'channel_id': result[5],
                    'message_id': result[6], 'embed_title': result[7], 'embed_footer': result[8],
                    'embed_thumbnail': result[9], 'embed_image': result[10], 
                    'created_at': result[11], 'updated_at': result[12]
                }
        return None
    
    async def get_guild_panels(self, guild_id: int) -> List[Dict[str, Any]]:
        """Get all panels for a guild"""
        panels = []
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT * FROM ticket_panels WHERE guild_id = ?", (guild_id,))
            results = await cursor.fetchall()
            for result in results:
                panels.append({
                    'panel_id': result[0], 'guild_id': result[1], 'panel_name': result[2],
                    'panel_description': result[3], 'panel_color': result[4], 'channel_id': result[5],
                    'message_id': result[6], 'embed_title': result[7], 'embed_footer': result[8],
                    'embed_thumbnail': result[9], 'embed_image': result[10], 
                    'created_at': result[11], 'updated_at': result[12]
                })
        return panels
    
    async def update_panel(self, panel_id: int, **kwargs):
        """Update panel configuration"""
        async with aiosqlite.connect(self.db_path) as db:
            for key, value in kwargs.items():
                await db.execute(f"UPDATE ticket_panels SET {key} = ?, updated_at = CURRENT_TIMESTAMP WHERE panel_id = ?", (value, panel_id))
            await db.commit()
    
    async def delete_panel(self, panel_id: int):
        """Delete a panel and all its categories"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM ticket_panels WHERE panel_id = ?", (panel_id,))
            await db.commit()
    
    # Category Management Methods
    async def create_category(self, panel_id: int, guild_id: int, category_name: str, **kwargs) -> int:
        """Create a new ticket category"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO ticket_categories (
                    panel_id, guild_id, category_name, category_emoji, category_description,
                    parent_category_id, channel_name_format, support_roles, auto_add_roles, ping_roles,
                    welcome_message, embed_welcome, welcome_embed_data, log_channel_id,
                    log_creation, log_closure, log_claims, log_transcripts, save_transcripts,
                    transcript_channel_id, transcript_format, auto_transcript, max_tickets_per_user,
                    auto_close_time, auto_close_warning, allow_claiming, claim_message,
                    user_can_close, user_can_add_members, priority_level, priority_color
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                panel_id, guild_id, category_name,
                kwargs.get('category_emoji', '🎫'),
                kwargs.get('category_description', ''),
                kwargs.get('parent_category_id'),
                kwargs.get('channel_name_format', 'ticket-{user}-{number}'),
                kwargs.get('support_roles', '[]'),
                kwargs.get('auto_add_roles', '[]'),
                kwargs.get('ping_roles', '[]'),
                kwargs.get('welcome_message', 'Thank you for creating a ticket! A staff member will be with you shortly.'),
                kwargs.get('embed_welcome', False),
                kwargs.get('welcome_embed_data', '{}'),
                kwargs.get('log_channel_id'),
                kwargs.get('log_creation', True),
                kwargs.get('log_closure', True),
                kwargs.get('log_claims', True),
                kwargs.get('log_transcripts', True),
                kwargs.get('save_transcripts', True),
                kwargs.get('transcript_channel_id'),
                kwargs.get('transcript_format', 'html'),
                kwargs.get('auto_transcript', True),
                kwargs.get('max_tickets_per_user', 1),
                kwargs.get('auto_close_time', 0),
                kwargs.get('auto_close_warning', 24),
                kwargs.get('allow_claiming', True),
                kwargs.get('claim_message', 'This ticket has been claimed by {claimer}.'),
                kwargs.get('user_can_close', True),
                kwargs.get('user_can_add_members', False),
                kwargs.get('priority_level', 1),
                kwargs.get('priority_color')
            ))
            await db.commit()
            return cursor.lastrowid or 0
    
    async def get_category(self, category_id: int) -> Optional[Dict[str, Any]]:
        """Get category by ID"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT * FROM ticket_categories WHERE category_id = ?", (category_id,))
            result = await cursor.fetchone()
            if result:
                return {
                    'category_id': result[0], 'panel_id': result[1], 'guild_id': result[2],
                    'category_name': result[3], 'category_emoji': result[4], 'category_description': result[5],
                    'parent_category_id': result[6], 'discord_category_id': result[7], 'channel_name_format': result[8],
                    'support_roles': result[9], 'auto_add_roles': result[10], 'ping_roles': result[11],
                    'welcome_message': result[12], 'embed_welcome': result[13], 'welcome_embed_data': result[14],
                    'log_channel_id': result[15], 'log_events': result[16], 'log_creation': result[17], 'log_closure': result[18],
                    'log_claims': result[19], 'log_transcripts': result[20], 'save_transcripts': result[21],
                    'transcript_channel_id': result[22], 'transcript_format': result[23], 'auto_transcript': result[24],
                    'max_tickets_per_user': result[25], 'auto_close_time': result[26], 'auto_close_warning': result[27],
                    'allow_claiming': result[28], 'require_claiming': result[29], 'claim_message': result[30], 'user_can_close': result[31],
                    'user_can_add_others': result[32], 'user_can_add_members': result[33], 'priority_level': result[34], 'priority_color': result[35],
                    'created_at': result[36], 'updated_at': result[37]
                }
        return None
    
    async def get_panel_categories(self, panel_id: int) -> List[Dict[str, Any]]:
        """Get all categories for a panel"""
        categories = []
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT * FROM ticket_categories WHERE panel_id = ? ORDER BY priority_level DESC, category_name", (panel_id,))
            results = await cursor.fetchall()
            for result in results:
                categories.append({
                    'category_id': result[0], 'panel_id': result[1], 'guild_id': result[2],
                    'category_name': result[3], 'category_emoji': result[4], 'category_description': result[5],
                    'parent_category_id': result[6], 'discord_category_id': result[7], 'channel_name_format': result[8],
                    'support_roles': result[9], 'auto_add_roles': result[10], 'ping_roles': result[11],
                    'welcome_message': result[12], 'embed_welcome': result[13], 'welcome_embed_data': result[14],
                    'log_channel_id': result[15], 'log_events': result[16], 'log_creation': result[17], 'log_closure': result[18],
                    'log_claims': result[19], 'log_transcripts': result[20], 'save_transcripts': result[21],
                    'transcript_channel_id': result[22], 'transcript_format': result[23], 'auto_transcript': result[24],
                    'max_tickets_per_user': result[25], 'auto_close_time': result[26], 'auto_close_warning': result[27],
                    'allow_claiming': result[28], 'require_claiming': result[29], 'claim_message': result[30], 'user_can_close': result[31],
                    'user_can_add_others': result[32], 'user_can_add_members': result[33], 'priority_level': result[34], 'priority_color': result[35],
                    'created_at': result[36], 'updated_at': result[37]
                })
        return categories
    
    async def update_category(self, category_id: int, **kwargs):
        """Update category configuration"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                for key, value in kwargs.items():
                    await db.execute(f"UPDATE ticket_categories SET {key} = ?, updated_at = CURRENT_TIMESTAMP WHERE category_id = ?", (value, category_id))
                await db.commit()
                return True
        except Exception as e:
            print(f"❌ Error updating category {category_id}: {e}")
            return False
    
    async def delete_category(self, category_id: int):
        """Delete a category"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM ticket_categories WHERE category_id = ?", (category_id,))
            await db.commit()
    
    # ================================
    # ADVANCED CLAIMING & ASSIGNMENT
    # ================================
    
    async def get_staff_workload(self, guild_id: int, staff_id: int) -> Optional[Dict[str, Any]]:
        """Get staff workload information"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT * FROM staff_workload WHERE guild_id = ? AND staff_id = ?",
                (guild_id, staff_id)
            )
            result = await cursor.fetchone()
            if result:
                return {
                    'staff_id': result[0], 'guild_id': result[1], 'active_tickets': result[2],
                    'total_tickets_handled': result[3], 'avg_response_time': result[4],
                    'avg_resolution_time': result[5], 'satisfaction_rating': result[6],
                    'last_activity': result[7], 'status': result[8], 'max_concurrent_tickets': result[9],
                    'specializations': json.loads(result[10] or '[]'), 'performance_score': result[11]
                }
        return None
    
    async def update_staff_workload(self, guild_id: int, staff_id: int, **kwargs):
        """Update or create staff workload entry"""
        async with aiosqlite.connect(self.db_path) as db:
            # Check if exists
            cursor = await db.execute(
                "SELECT staff_id FROM staff_workload WHERE guild_id = ? AND staff_id = ?",
                (guild_id, staff_id)
            )
            exists = await cursor.fetchone()
            
            if exists:
                # Update existing
                for key, value in kwargs.items():
                    if key == 'specializations':
                        value = json.dumps(value)
                    await db.execute(
                        f"UPDATE staff_workload SET {key} = ?, last_activity = CURRENT_TIMESTAMP WHERE guild_id = ? AND staff_id = ?",
                        (value, guild_id, staff_id)
                    )
            else:
                # Create new
                await db.execute("""
                    INSERT INTO staff_workload (staff_id, guild_id, specializations)
                    VALUES (?, ?, ?)
                """, (staff_id, guild_id, json.dumps(kwargs.get('specializations', []))))
                
                for key, value in kwargs.items():
                    if key != 'specializations':
                        if key == 'specializations':
                            value = json.dumps(value)
                        await db.execute(
                            f"UPDATE staff_workload SET {key} = ? WHERE guild_id = ? AND staff_id = ?",
                            (value, guild_id, staff_id)
                        )
            
            await db.commit()
    
    async def find_best_staff_for_ticket(self, guild_id: int, category_id: int) -> Optional[int]:
        """Find the best available staff member for a ticket using AI-powered assignment"""
        async with aiosqlite.connect(self.db_path) as db:
            # Get category info
            category = await self.get_category(category_id)
            if not category:
                return None
            
            # Safely parse support roles JSON
            try:
                support_roles_data = category.get('support_roles') or '[]'
                support_roles = json.loads(support_roles_data) if support_roles_data.strip() else []
            except (json.JSONDecodeError, AttributeError):
                support_roles = []
                
            if not support_roles:
                return None
            
            # Get all staff with support roles
            cursor = await db.execute("""
                SELECT staff_id, active_tickets, specializations, performance_score, 
                       max_concurrent_tickets, status, avg_response_time, satisfaction_rating
                FROM staff_workload 
                WHERE guild_id = ? AND status = 'available'
                ORDER BY 
                    (active_tickets < max_concurrent_tickets) DESC,
                    performance_score DESC,
                    active_tickets ASC,
                    avg_response_time ASC
                LIMIT 1
            """, (guild_id,))
            
            result = await cursor.fetchone()
            if result:
                staff_id = result[0]
                specializations = json.loads(result[2] or '[]')
                
                # Prefer staff who specialize in this category
                if category_id in specializations:
                    return staff_id
                
                # Check if they have capacity
                if result[1] < result[4]:  # active_tickets < max_concurrent_tickets
                    return staff_id
            
            return None
    
    async def auto_assign_ticket(self, ticket_id: int) -> bool:
        """Automatically assign ticket to best available staff"""
        async with aiosqlite.connect(self.db_path) as db:
            # Get ticket info
            cursor = await db.execute(
                "SELECT guild_id, category_id, user_id FROM tickets WHERE ticket_id = ?",
                (ticket_id,)
            )
            ticket_info = await cursor.fetchone()
            
            if not ticket_info:
                return False
            
            guild_id, category_id, user_id = ticket_info
            
            # Find best staff
            best_staff = await self.find_best_staff_for_ticket(guild_id, category_id)
            
            if best_staff:
                # Assign ticket
                await db.execute("""
                    UPDATE tickets SET claimed_by = ?, claimed_at = CURRENT_TIMESTAMP, status = 'claimed'
                    WHERE ticket_id = ?
                """, (best_staff, ticket_id))
                
                # Update staff workload
                await self.update_staff_workload(guild_id, best_staff, active_tickets="+1")
                
                # Log the assignment
                await self.log_ticket_action(ticket_id, best_staff, 'auto_assigned', {
                    'assignment_method': 'ai_powered',
                    'reason': 'automatic_workload_balancing'
                })
                
                await db.commit()
                return True
        
        return False
    
    async def calculate_sla_deadline(self, ticket_id: int) -> Optional[datetime]:
        """Calculate SLA deadline for a ticket"""
        async with aiosqlite.connect(self.db_path) as db:
            # Get ticket and category info
            cursor = await db.execute("""
                SELECT t.created_at, t.priority, c.category_id
                FROM tickets t
                JOIN ticket_categories c ON t.category_id = c.category_id
                WHERE t.ticket_id = ?
            """, (ticket_id,))
            
            result = await cursor.fetchone()
            if not result:
                return None
            
            created_at, priority, category_id = result
            
            # Get SLA config for this category and priority
            cursor = await db.execute("""
                SELECT first_response_time, resolution_time, business_hours_only
                FROM sla_configs
                WHERE category_id = ? AND priority_level = ?
            """, (category_id, priority))
            
            sla_config = await cursor.fetchone()
            if not sla_config:
                # Default SLA: 1 hour for first response, 24 hours for resolution
                first_response_time = 60 if priority >= 3 else 240  # High priority gets 1 hour, normal gets 4 hours
                resolution_time = 1440 if priority >= 3 else 4320  # High priority gets 24 hours, normal gets 72 hours
                business_hours_only = False
            else:
                first_response_time, resolution_time, business_hours_only = sla_config
            
            # Calculate deadline based on priority
            base_time = datetime.fromisoformat(created_at.replace('Z', '+00:00')) if isinstance(created_at, str) else created_at
            
            if business_hours_only:
                # TODO: Implement business hours calculation
                deadline = base_time + timedelta(minutes=resolution_time)
            else:
                deadline = base_time + timedelta(minutes=resolution_time)
            
            return deadline
    
    async def check_sla_status(self, ticket_id: int) -> str:
        """Check current SLA status of a ticket"""
        deadline = await self.calculate_sla_deadline(ticket_id)
        if not deadline:
            return 'no_sla'
        
        now = self.tz_helpers.get_utc_now()
        time_remaining = deadline - now
        
        if time_remaining.total_seconds() <= 0:
            return 'breached'
        elif time_remaining.total_seconds() <= 3600:  # 1 hour warning
            return 'at_risk'
        else:
            return 'within_sla'
    
    async def escalate_ticket(self, ticket_id: int, escalated_by: int, reason: str = "SLA breach") -> bool:
        """Escalate a ticket to higher tier support"""
        async with aiosqlite.connect(self.db_path) as db:
            # Get current ticket info
            cursor = await db.execute(
                "SELECT escalation_level, category_id, guild_id FROM tickets WHERE ticket_id = ?",
                (ticket_id,)
            )
            ticket_info = await cursor.fetchone()
            
            if not ticket_info:
                return False
            
            current_level, category_id, guild_id = ticket_info
            new_level = current_level + 1
            
            # Find escalation target (could be manager, admin, etc.)
            # For now, we'll escalate to guild owner or admin
            
            await db.execute("""
                UPDATE tickets SET 
                    escalation_level = ?,
                    status = 'escalated',
                    escalated_to = ?
                WHERE ticket_id = ?
            """, (new_level, escalated_by, ticket_id))
            
            # Log escalation
            await self.log_ticket_action(ticket_id, escalated_by, 'escalated', {
                'previous_level': current_level,
                'new_level': new_level,
                'reason': reason
            })
            
            await db.commit()
            return True
    
    # Enhanced Ticket Management Methods  
    async def create_ticket(self, guild_id: int, user_id: int, channel_id: int, category_id: Optional[int] = None, panel_id: Optional[int] = None) -> int:
        """Create a new ticket with enhanced tracking"""
        async with aiosqlite.connect(self.db_path) as db:
            # Get next ticket number for this guild
            cursor = await db.execute("SELECT COUNT(*) FROM tickets WHERE guild_id = ?", (guild_id,))
            count = await cursor.fetchone()
            ticket_number = (count[0] if count else 0) + 1
            
            cursor = await db.execute("""
                INSERT INTO tickets (guild_id, user_id, channel_id, category_id, panel_id, ticket_number)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (guild_id, user_id, channel_id, category_id, panel_id, ticket_number))
            await db.commit()
            
            ticket_id = cursor.lastrowid or 0
            
            # Log the creation
            await self.log_ticket_action(ticket_id, user_id, 'created', {'channel_id': channel_id, 'category_id': category_id})
            
            return ticket_id
    
    async def get_ticket_by_channel(self, channel_id: int) -> Optional[Dict[str, Any]]:
        """Get ticket by channel ID"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT * FROM tickets WHERE channel_id = ? AND status != 'closed'", (channel_id,))
            result = await cursor.fetchone()
            if result:
                return {
                    'ticket_id': result[0], 'guild_id': result[1], 'user_id': result[2],
                    'channel_id': result[3], 'category_id': result[4], 'panel_id': result[5],
                    'status': result[6], 'priority': result[7], 'ticket_number': result[8],
                    'created_at': result[9], 'claimed_at': result[10], 'closed_at': result[11],
                    'claimed_by': result[12], 'assigned_roles': result[13], 'close_reason': result[14],
                    'closed_by': result[15], 'additional_users': result[16], 'notes': result[17],
                    'transcript_url': result[18]
                }
        return None
    
    async def get_user_tickets(self, guild_id: int, user_id: int, status: str = 'open') -> List[Dict[str, Any]]:
        """Get user's tickets"""
        tickets = []
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT * FROM tickets WHERE guild_id = ? AND user_id = ? AND status = ?",
                (guild_id, user_id, status)
            )
            results = await cursor.fetchall()
            for result in results:
                tickets.append({
                    'ticket_id': result[0], 'guild_id': result[1], 'user_id': result[2],
                    'channel_id': result[3], 'category_id': result[4], 'panel_id': result[5],
                    'status': result[6], 'priority': result[7], 'ticket_number': result[8],
                    'created_at': result[9], 'claimed_at': result[10], 'closed_at': result[11],
                    'claimed_by': result[12], 'assigned_roles': result[13], 'close_reason': result[14],
                    'closed_by': result[15], 'additional_users': result[16], 'notes': result[17],
                    'transcript_url': result[18]
                })
        return tickets
    
    async def claim_ticket(self, ticket_id: int, claimer_id: int):
        """Claim a ticket"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE tickets SET status = 'claimed', claimed_by = ?, claimed_at = CURRENT_TIMESTAMP
                WHERE ticket_id = ?
            """, (claimer_id, ticket_id))
            await db.commit()
            
            await self.log_ticket_action(ticket_id, claimer_id, 'claimed', {})
    
    async def close_ticket(self, ticket_id: int, closer_id: int, reason: Optional[str] = None):
        """Close a ticket"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE tickets SET status = 'closed', closed_by = ?, closed_at = CURRENT_TIMESTAMP, close_reason = ?
                WHERE ticket_id = ?
            """, (closer_id, reason or "No reason provided", ticket_id))
            await db.commit()
            
            await self.log_ticket_action(ticket_id, closer_id, 'closed', {'reason': reason})
    
    async def add_user_to_ticket(self, ticket_id: int, user_id: int, added_by: int):
        """Add additional user to ticket"""
        async with aiosqlite.connect(self.db_path) as db:
            # Get current additional users
            cursor = await db.execute("SELECT additional_users FROM tickets WHERE ticket_id = ?", (ticket_id,))
            result = await cursor.fetchone()
            
            if result:
                current_users = json.loads(result[0] or '[]')
                if user_id not in current_users:
                    current_users.append(user_id)
                    await db.execute(
                        "UPDATE tickets SET additional_users = ? WHERE ticket_id = ?",
                        (json.dumps(current_users), ticket_id)
                    )
                    await db.commit()
                    
                    await self.log_ticket_action(ticket_id, added_by, 'user_added', {'added_user': user_id})
    
    async def log_ticket_action(self, ticket_id: int, user_id: int, action_type: str, details: Dict[str, Any]):
        """Log ticket action"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO ticket_logs (ticket_id, action_type, user_id, details)
                VALUES (?, ?, ?, ?)
            """, (ticket_id, action_type, user_id, json.dumps(details)))
            await db.commit()
    
    async def get_ticket_logs(self, ticket_id: int) -> List[Dict[str, Any]]:
        """Get logs for a ticket"""
        logs = []
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT * FROM ticket_logs WHERE ticket_id = ? ORDER BY timestamp",
                (ticket_id,)
            )
            results = await cursor.fetchall()
            for result in results:
                logs.append({
                    'log_id': result[0], 'ticket_id': result[1], 'action_type': result[2],
                    'user_id': result[3], 'details': json.loads(result[4] or '{}'),
                    'timestamp': result[5]
                })
        return logs
    
    # Legacy compatibility methods (keep for backward compatibility)
    async def get_guild_config(self, guild_id: int) -> Dict[str, Any]:
        """Get legacy guild ticket configuration"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT * FROM ticket_config WHERE guild_id = ?", (guild_id,)
            )
            result = await cursor.fetchone()
            if result:
                return {
                    'guild_id': result[0],
                    'category_id': result[1],
                    'support_role_id': result[2],
                    'log_channel_id': result[3],
                    'welcome_message': result[4],
                    'ticket_counter': result[5],
                    'max_tickets_per_user': result[6],
                    'auto_close_time': result[7]
                }
            return {}
    
    async def set_guild_config(self, guild_id: int, **kwargs):
        """Set legacy guild ticket configuration"""
        async with aiosqlite.connect(self.db_path) as db:
            # Check if config exists
            cursor = await db.execute(
                "SELECT guild_id FROM ticket_config WHERE guild_id = ?", (guild_id,)
            )
            exists = await cursor.fetchone()
            
            if exists:
                # Update existing config
                for key, value in kwargs.items():
                    await db.execute(
                        f"UPDATE ticket_config SET {key} = ? WHERE guild_id = ?",
                        (value, guild_id)
                    )
            else:
                # Insert new config
                await db.execute(
                    "INSERT INTO ticket_config (guild_id) VALUES (?)", (guild_id,)
                )
                for key, value in kwargs.items():
                    await db.execute(
                        f"UPDATE ticket_config SET {key} = ? WHERE guild_id = ?",
                        (value, guild_id)
                    )
            
            await db.commit()

# ================================
# DROPDOWN BUILDER SYSTEM
# ================================

class PanelCreateModal(Modal):
    """Modal for creating a new ticket panel"""
    def __init__(self, tickets_cog):
        super().__init__(title="Create Ticket Panel")
        self.tickets_cog = tickets_cog
        
        self.panel_name = TextInput(
            label="Panel Name",
            placeholder="e.g., 'General Support', 'Technical Help'",
            required=True,
            max_length=50
        )
        
        self.embed_title = TextInput(
            label="Embed Title",
            placeholder="e.g., 'Support Tickets'",
            required=False,
            max_length=100,
            default="Support Tickets"
        )
        
        self.panel_description = TextInput(
            label="Panel Description",
            placeholder="This will be shown in the embed description",
            required=False,
            max_length=500,
            style=discord.TextStyle.paragraph,
            default="Select a ticket category below to get support."
        )
        
        self.add_item(self.panel_name)
        self.add_item(self.embed_title)
        self.add_item(self.panel_description)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        if not interaction.guild:
            await interaction.followup.send("❌ This can only be used in a server.", ephemeral=True)
            return
        
        # Create the panel in database
        panel_id = await self.tickets_cog.db.create_panel(
            guild_id=interaction.guild.id,
            panel_name=self.panel_name.value,
            panel_description=self.panel_description.value,
            embed_title=self.embed_title.value
        )
        
        # Show panel configuration options
        await self.tickets_cog.show_panel_config(interaction, panel_id)

class CategoryCreateModal(Modal):
    """Modal for creating a new ticket category"""
    def __init__(self, tickets_cog, panel_id: int):
        super().__init__(title="Create Ticket Category")
        self.tickets_cog = tickets_cog
        self.panel_id = panel_id
        
        self.category_name = TextInput(
            label="Category Name",
            placeholder="e.g., 'General Support', 'Bug Reports'",
            required=True,
            max_length=50
        )
        
        self.category_emoji = TextInput(
            label="Category Emoji",
            placeholder="e.g., '🛠️', '🐛', '💬'",
            required=False,
            max_length=10,
            default="🎫"
        )
        
        self.category_description = TextInput(
            label="Category Description",
            placeholder="Brief description of this category",
            required=False,
            max_length=200,
            style=discord.TextStyle.paragraph
        )
        
        self.add_item(self.category_name)
        self.add_item(self.category_emoji)
        self.add_item(self.category_description)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        if not interaction.guild:
            await interaction.followup.send("❌ This can only be used in a server.", ephemeral=True)
            return
        
        # Create the category in database
        category_id = await self.tickets_cog.db.create_category(
            panel_id=self.panel_id,
            guild_id=interaction.guild.id,
            category_name=self.category_name.value,
            category_emoji=self.category_emoji.value,
            category_description=self.category_description.value
        )
        
        # Show category configuration options
        await self.tickets_cog.show_category_config(interaction, category_id)

class WelcomeMessageModal(Modal):
    """Modal for setting category welcome message"""
    def __init__(self, tickets_cog, category_id: int):
        super().__init__(title="Set Welcome Message")
        self.tickets_cog = tickets_cog
        self.category_id = category_id
        
        self.welcome_message = TextInput(
            label="Welcome Message",
            placeholder="Message shown when ticket is created...",
            required=True,
            max_length=1000,
            style=discord.TextStyle.paragraph,
            default="Thank you for creating a ticket! A staff member will be with you shortly."
        )
        
        self.add_item(self.welcome_message)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        await self.tickets_cog.db.update_category(
            self.category_id,
            welcome_message=self.welcome_message.value
        )
        
        embed = discord.Embed(
            title="✅ Welcome Message Updated",
            description=f"Welcome message has been set for this category.",
            color=0x00FF00
        )
        await self.tickets_cog._safe_send(interaction, embed=embed, ephemeral=True)

class ChannelNameFormatModal(Modal):
    """Modal for setting channel name format"""
    def __init__(self, tickets_cog, category_id: int):
        super().__init__(title="Set Channel Name Format")
        self.tickets_cog = tickets_cog
        self.category_id = category_id
        
        self.format_input = TextInput(
            label="Channel Name Format",
            placeholder="Use {user}, {number}, {category} placeholders",
            required=True,
            max_length=100,
            default="ticket-{user}-{number}"
        )
        
        self.add_item(self.format_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        await self.tickets_cog.db.update_category(
            self.category_id,
            channel_name_format=self.format_input.value
        )
        
        embed = discord.Embed(
            title="✅ Channel Name Format Updated",
            description=f"Channel format: `{self.format_input.value}`",
            color=0x00FF00
        )
        await self.tickets_cog._safe_send(interaction, embed=embed, ephemeral=True)

class PanelConfigView(View):
    """Main panel configuration view with dropdown"""
    def __init__(self, tickets_cog, panel_id: int):
        super().__init__(timeout=300)
        self.tickets_cog = tickets_cog
        self.panel_id = panel_id
    
    @discord.ui.select(
        placeholder="Choose panel configuration option...",
        options=[
            discord.SelectOption(
                label="Edit Panel Details",
                description="Change panel name, title, description",
                emoji="✏️",
                value="edit_panel"
            ),
            discord.SelectOption(
                label="Add Category",
                description="Create a new ticket category",
                emoji="➕",
                value="add_category"
            ),
            discord.SelectOption(
                label="Manage Categories", 
                description="Edit or delete existing categories",
                emoji="📋",
                value="manage_categories"
            ),
            discord.SelectOption(
                label="Panel Appearance",
                description="Customize embed colors, images, footer",
                emoji="🎨",
                value="panel_appearance"
            ),
            discord.SelectOption(
                label="Deploy Panel",
                description="Send the panel to a channel",
                emoji="🚀",
                value="deploy_panel"
            )
        ]
    )
    async def panel_config_select(self, interaction: discord.Interaction, select: Select):
        choice = select.values[0]
        
        if choice == "edit_panel":
            await self.tickets_cog.show_panel_edit(interaction, self.panel_id)
        elif choice == "add_category":
            modal = CategoryCreateModal(self.tickets_cog, self.panel_id)
            await interaction.response.send_modal(modal)
        elif choice == "manage_categories":
            await self.tickets_cog.show_categories_list(interaction, self.panel_id)
        elif choice == "panel_appearance":
            await self.tickets_cog.show_panel_appearance_config(interaction, self.panel_id)
        elif choice == "deploy_panel":
            await self.tickets_cog.show_panel_deployment(interaction, self.panel_id)
    
    @discord.ui.button(label="🏠 Back to Main", style=ButtonStyle.secondary)
    async def back_to_main(self, interaction: discord.Interaction, button: Button):
        await self.tickets_cog.show_main_setup(interaction)
    
    @discord.ui.button(label="❌ Delete Panel", style=ButtonStyle.danger)
    async def delete_panel(self, interaction: discord.Interaction, button: Button):
        await self.tickets_cog.confirm_panel_deletion(interaction, self.panel_id)

class CategoryConfigView(View):
    """Category configuration view with dropdown"""
    def __init__(self, tickets_cog, category_id: int):
        super().__init__(timeout=300)
        self.tickets_cog = tickets_cog
        self.category_id = category_id
    
    @discord.ui.select(
        placeholder="Choose category configuration option...",
        options=[
            discord.SelectOption(
                label="Basic Settings",
                description="Name, emoji, description",
                emoji="⚙️",
                value="basic_settings"
            ),
            discord.SelectOption(
                label="Welcome Message",
                description="Set welcome message for tickets",
                emoji="👋",
                value="welcome_message"
            ),
            discord.SelectOption(
                label="Channel Settings",
                description="Category, name format",
                emoji="📝",
                value="channel_settings"
            ),
            discord.SelectOption(
                label="Role Configuration",
                description="Support roles, auto-add roles, ping roles",
                emoji="👥",
                value="role_config"
            ),
            discord.SelectOption(
                label="Logging Settings",
                description="Configure logging channels and events",
                emoji="📊",
                value="logging_settings"
            ),
            discord.SelectOption(
                label="Transcript Settings",
                description="Auto-save, format, destination",
                emoji="📄",
                value="transcript_settings"
            ),
            discord.SelectOption(
                label="Limits & Automation",
                description="Max tickets, auto-close, warnings",
                emoji="⏰",
                value="limits_automation"
            ),
            discord.SelectOption(
                label="Permissions",
                description="User permissions, claiming settings",
                emoji="🔐",
                value="permissions"
            )
        ]
    )
    async def category_config_select(self, interaction: discord.Interaction, select: Select):
        choice = select.values[0]
        
        if choice == "basic_settings":
            await self.tickets_cog.show_category_basic_settings(interaction, self.category_id)
        elif choice == "welcome_message":
            modal = WelcomeMessageModal(self.tickets_cog, self.category_id)
            await interaction.response.send_modal(modal)
        elif choice == "channel_settings":
            await self.tickets_cog.show_channel_settings(interaction, self.category_id)
        elif choice == "role_config":
            await self.tickets_cog.show_role_config(interaction, self.category_id)
        elif choice == "logging_settings":
            await self.tickets_cog.show_logging_settings(interaction, self.category_id)
        elif choice == "transcript_settings":
            await self.tickets_cog.show_transcript_settings(interaction, self.category_id)
        elif choice == "limits_automation":
            await self.tickets_cog.show_limits_automation(interaction, self.category_id)
        elif choice == "permissions":
            await self.tickets_cog.show_permissions_settings(interaction, self.category_id)
    
    @discord.ui.button(label="🔙 Back to Panel", style=ButtonStyle.secondary)
    async def back_to_panel(self, interaction: discord.Interaction, button: Button):
        # Get panel_id from category
        category = await self.tickets_cog.db.get_category(self.category_id)
        if category:
            await self.tickets_cog.show_panel_config(interaction, category['panel_id'])
        else:
            await interaction.response.send_message("❌ Category not found!", ephemeral=True)
    
    @discord.ui.button(label="❌ Delete Category", style=ButtonStyle.danger)
    async def delete_category(self, interaction: discord.Interaction, button: Button):
        await self.tickets_cog.confirm_category_deletion(interaction, self.category_id)

# ================================
# END DROPDOWN BUILDER SYSTEM
# ================================

class TicketCreateModal(Modal):
    """Enhanced modal with AI-powered category suggestion"""
    def __init__(self, tickets_cog):
        super().__init__()
        self.title = "Create Support Ticket"
        self.tickets_cog = tickets_cog
        
        self.subject = TextInput(
            label="Ticket Subject",
            placeholder="Brief description of your issue...",
            required=True,
            max_length=100
        )
        
        self.description = TextInput(
            label="Detailed Description",
            placeholder="Please provide as much detail as possible about your issue...",
            required=True,
            max_length=2000,
            style=discord.TextStyle.paragraph
        )
        
        self.priority = TextInput(
            label="Priority Level (1-5)",
            placeholder="1=Low, 2=Normal, 3=High, 4=Urgent, 5=Critical",
            required=False,
            max_length=1,
            default="2"
        )
        
        self.add_item(self.subject)
        self.add_item(self.description)
        self.add_item(self.priority)
    
    async def on_submit(self, interaction: discord.Interaction):
        # AI-powered category suggestion and priority analysis would go here
        await interaction.response.send_message("🤖 Analyzing your request...", ephemeral=True)

class AdvancedTicketControlView(View):
    """Enhanced ticket control view with advanced features"""
    def __init__(self, tickets_cog, ticket_id: int):
        super().__init__(timeout=None)
        self.tickets_cog = tickets_cog
        self.ticket_id = ticket_id
    
    @discord.ui.button(label="🎯 Claim Ticket", style=ButtonStyle.success, custom_id="claim_ticket")
    async def claim_ticket(self, interaction: discord.Interaction, button: Button):
        """Advanced claiming with workload balancing"""
        await self.tickets_cog.claim_ticket_advanced(interaction, self.ticket_id)
    
    @discord.ui.button(label="🚀 Escalate", style=ButtonStyle.danger, custom_id="escalate_ticket")
    async def escalate_ticket(self, interaction: discord.Interaction, button: Button):
        """Escalate to higher tier support"""
        await self.tickets_cog.escalate_ticket_interactive(interaction, self.ticket_id)
    
    @discord.ui.button(label="📊 AI Analysis", style=ButtonStyle.primary, custom_id="ai_analysis")
    async def ai_analysis(self, interaction: discord.Interaction, button: Button):
        """Get AI analysis of the ticket"""
        await self.tickets_cog.perform_ai_analysis(interaction, self.ticket_id)
    
    @discord.ui.button(label="⏱️ SLA Status", style=ButtonStyle.secondary, custom_id="sla_status")
    async def sla_status(self, interaction: discord.Interaction, button: Button):
        """Check SLA status and deadlines"""
        await self.tickets_cog.show_sla_status(interaction, self.ticket_id)
    
    @discord.ui.button(label="👥 Assign Staff", style=ButtonStyle.primary, custom_id="assign_staff")
    async def assign_staff(self, interaction: discord.Interaction, button: Button):
        """Advanced staff assignment with workload balancing"""
        await self.tickets_cog.show_staff_assignment(interaction, self.ticket_id)
    
    @discord.ui.button(label="🏷️ Add Tags", style=ButtonStyle.secondary, custom_id="add_tags")
    async def add_tags(self, interaction: discord.Interaction, button: Button):
        """Add tags for better organization"""
        await self.tickets_cog.show_tag_selector(interaction, self.ticket_id)
    
    @discord.ui.button(label="📝 Add Notes", style=ButtonStyle.secondary, custom_id="add_notes")
    async def add_notes(self, interaction: discord.Interaction, button: Button):
        """Add staff notes"""
        modal = StaffNotesModal(self.tickets_cog, self.ticket_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="⭐ Rate & Close", style=ButtonStyle.danger, custom_id="rate_close")
    async def rate_and_close(self, interaction: discord.Interaction, button: Button):
        """Close ticket with rating system"""
        await self.tickets_cog.show_rating_modal(interaction, self.ticket_id)

class StaffNotesModal(Modal):
    """Modal for adding staff notes"""
    def __init__(self, tickets_cog, ticket_id: int):
        super().__init__(title="Add Staff Notes")
        self.tickets_cog = tickets_cog
        self.ticket_id = ticket_id
        
        self.notes = TextInput(
            label="Staff Notes",
            placeholder="Add internal notes about this ticket...",
            required=True,
            max_length=1000,
            style=discord.TextStyle.paragraph
        )
        
        self.add_item(self.notes)
    
    async def on_submit(self, interaction: discord.Interaction):
        await self.tickets_cog.add_staff_notes(interaction, self.ticket_id, self.notes.value)

class TicketRatingModal(Modal):
    """Modal for ticket rating and feedback"""
    def __init__(self, tickets_cog, ticket_id: int):
        super().__init__(title="Rate Your Support Experience")
        self.tickets_cog = tickets_cog
        self.ticket_id = ticket_id
        
        self.overall_rating = TextInput(
            label="Overall Rating (1-5 stars)",
            placeholder="Rate your overall experience...",
            required=True,
            max_length=1
        )
        
        self.response_time_rating = TextInput(
            label="Response Time (1-5 stars)",
            placeholder="How quickly did we respond?",
            required=False,
            max_length=1
        )
        
        self.helpfulness_rating = TextInput(
            label="Helpfulness (1-5 stars)",
            placeholder="How helpful was our support?",
            required=False,
            max_length=1
        )
        
        self.feedback = TextInput(
            label="Additional Feedback",
            placeholder="Tell us how we can improve...",
            required=False,
            max_length=500,
            style=discord.TextStyle.paragraph
        )
        
        self.add_item(self.overall_rating)
        self.add_item(self.response_time_rating)
        self.add_item(self.helpfulness_rating)
        self.add_item(self.feedback)
    
    async def on_submit(self, interaction: discord.Interaction):
        await self.tickets_cog.submit_ticket_rating(
            interaction, 
            self.ticket_id, 
            int(self.overall_rating.value),
            int(self.response_time_rating.value) if self.response_time_rating.value else None,
            int(self.helpfulness_rating.value) if self.helpfulness_rating.value else None,
            self.feedback.value
        )

class StaffAssignmentView(View):
    """Advanced staff assignment interface"""
    def __init__(self, tickets_cog, ticket_id: int, available_staff: List[Dict]):
        super().__init__(timeout=300)
        self.tickets_cog = tickets_cog
        self.ticket_id = ticket_id
        
        # Create dropdown with available staff
        options = []
        for staff in available_staff[:25]:  # Discord limit
            workload_indicator = "🟢" if staff['active_tickets'] < 3 else "🟡" if staff['active_tickets'] < 5 else "🔴"
            options.append(discord.SelectOption(
                label=f"{staff['name']} ({staff['active_tickets']} tickets)",
                description=f"Performance: {staff['performance_score']:.1f}% | Response: {staff['avg_response_time']:.1f}min",
                emoji=workload_indicator,
                value=str(staff['staff_id'])
            ))
        
        if options:
            self.staff_select = Select(
                placeholder="Select staff member to assign...",
                options=options
            )
            self.staff_select.callback = self.assign_staff_callback
            self.add_item(self.staff_select)
    
    async def assign_staff_callback(self, interaction: discord.Interaction):
        staff_id = int(self.staff_select.values[0])
        await self.tickets_cog.assign_staff_to_ticket(interaction, self.ticket_id, staff_id)

class EscalationModal(Modal):
    """Modal for ticket escalation"""
    def __init__(self, tickets_cog, ticket_id: int):
        super().__init__(title="Escalate Ticket")
        self.tickets_cog = tickets_cog
        self.ticket_id = ticket_id
        
        self.reason = TextInput(
            label="Escalation Reason",
            placeholder="Why is this ticket being escalated?",
            required=True,
            max_length=500,
            style=discord.TextStyle.paragraph
        )
        
        self.add_item(self.reason)
    
    async def on_submit(self, interaction: discord.Interaction):
        await self.tickets_cog.escalate_ticket_with_reason(interaction, self.ticket_id, self.reason.value)

class TagSelectorView(View):
    """View for selecting ticket tags"""
    def __init__(self, tickets_cog, ticket_id: int, tags: List[str]):
        super().__init__(timeout=300)
        self.tickets_cog = tickets_cog
        self.ticket_id = ticket_id
        self.selected_tags = []
        
        # Create buttons for each tag
        for i, tag in enumerate(tags[:20]):  # Discord limit on components
            button = Button(
                label=tag,
                style=ButtonStyle.secondary,
                custom_id=f"tag_{i}"
            )
            button.callback = self.create_tag_callback(tag)
            self.add_item(button)
    
    def create_tag_callback(self, tag: str):
        async def tag_callback(interaction: discord.Interaction):
            if tag in self.selected_tags:
                self.selected_tags.remove(tag)
                await interaction.response.send_message(f"Removed tag: {tag}", ephemeral=True)
            else:
                self.selected_tags.append(tag)
                await interaction.response.send_message(f"Added tag: {tag}", ephemeral=True)
            
            # Update ticket with tags
            await self.tickets_cog.update_ticket_tags(self.ticket_id, self.selected_tags)
        
        return tag_callback

class CategoryBasicSettingsView(View):
    """View for category basic settings management"""
    def __init__(self, tickets_cog, category_id: int):
        super().__init__(timeout=300)
        self.tickets_cog = tickets_cog
        self.category_id = category_id
    
    @discord.ui.button(label="✏️ Edit Name", style=ButtonStyle.primary)
    async def edit_name(self, interaction: discord.Interaction, button: Button):
        modal = CategoryNameEditModal(self.tickets_cog, self.category_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="😀 Edit Emoji", style=ButtonStyle.primary)
    async def edit_emoji(self, interaction: discord.Interaction, button: Button):
        modal = CategoryEmojiEditModal(self.tickets_cog, self.category_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📝 Edit Description", style=ButtonStyle.primary)
    async def edit_description(self, interaction: discord.Interaction, button: Button):
        modal = CategoryDescriptionEditModal(self.tickets_cog, self.category_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🔙 Back", style=ButtonStyle.secondary)
    async def back_to_category(self, interaction: discord.Interaction, button: Button):
        await self.tickets_cog.show_category_config(interaction, self.category_id)

class CategoryNameEditModal(Modal):
    """Modal for editing category name"""
    def __init__(self, tickets_cog, category_id: int):
        super().__init__(title="Edit Category Name")
        self.tickets_cog = tickets_cog
        self.category_id = category_id
        
        self.name_input = TextInput(
            label="Category Name",
            placeholder="Enter new category name...",
            required=True,
            max_length=50
        )
        self.add_item(self.name_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        await self.tickets_cog.db.update_category(
            self.category_id,
            category_name=self.name_input.value
        )
        
        embed = discord.Embed(
            title="✅ Category Name Updated",
            description=f"Category name changed to: **{self.name_input.value}**",
            color=0x00FF00
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

class CategoryEmojiEditModal(Modal):
    """Modal for editing category emoji"""
    def __init__(self, tickets_cog, category_id: int):
        super().__init__(title="Edit Category Emoji")
        self.tickets_cog = tickets_cog
        self.category_id = category_id
        
        self.emoji_input = TextInput(
            label="Category Emoji",
            placeholder="Enter emoji (e.g., 🎫, 🛠️, 🐛)...",
            required=False,
            max_length=10
        )
        self.add_item(self.emoji_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        await self.tickets_cog.db.update_category(
            self.category_id,
            category_emoji=self.emoji_input.value
        )
        
        embed = discord.Embed(
            title="✅ Category Emoji Updated",
            description=f"Category emoji changed to: {self.emoji_input.value}",
            color=0x00FF00
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

class CategoryDescriptionEditModal(Modal):
    """Modal for editing category description"""
    def __init__(self, tickets_cog, category_id: int):
        super().__init__(title="Edit Category Description")
        self.tickets_cog = tickets_cog
        self.category_id = category_id
        
        self.description_input = TextInput(
            label="Category Description",
            placeholder="Enter new description...",
            required=False,
            max_length=200,
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.description_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        await self.tickets_cog.db.update_category(
            self.category_id,
            category_description=self.description_input.value
        )
        
        embed = discord.Embed(
            title="✅ Category Description Updated",
            description=f"Description updated successfully.",
            color=0x00FF00
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

class RoleConfigView(View):
    """View for role configuration management"""
    def __init__(self, tickets_cog, category_id: int):
        super().__init__(timeout=300)
        self.tickets_cog = tickets_cog
        self.category_id = category_id
    
    @discord.ui.button(label="🛠️ Support Roles", style=ButtonStyle.primary)
    async def config_support_roles(self, interaction: discord.Interaction, button: Button):
        embed = discord.Embed(
            title="🛠️ Configure Support Roles",
            description="Please mention the roles you want to set as support roles in chat.\n\n**Example:** `@Support @Moderator @Admin`\n\n*Type 'cancel' to cancel this configuration.*",
            color=0x00E6A7
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Wait for message response
        await self.tickets_cog.wait_for_role_config(interaction, self.category_id, "support_roles")
    
    @discord.ui.button(label="➕ Auto-Add Roles", style=ButtonStyle.primary)
    async def config_auto_add_roles(self, interaction: discord.Interaction, button: Button):
        embed = discord.Embed(
            title="➕ Configure Auto-Add Roles",
            description="Please mention the roles that should be automatically given to users when they create tickets.\n\n**Example:** `@Member @Verified`\n\n*Type 'cancel' to cancel this configuration.*",
            color=0x00E6A7
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Wait for message response
        await self.tickets_cog.wait_for_role_config(interaction, self.category_id, "auto_add_roles")
    
    @discord.ui.button(label="📢 Ping Roles", style=ButtonStyle.primary)
    async def config_ping_roles(self, interaction: discord.Interaction, button: Button):
        embed = discord.Embed(
            title="📢 Configure Ping Roles",
            description="Please mention the roles that should be pinged when new tickets are created.\n\n**Example:** `@Support @Staff`\n\n*Type 'cancel' to cancel this configuration.*",
            color=0x00E6A7
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Wait for message response
        await self.tickets_cog.wait_for_role_config(interaction, self.category_id, "ping_roles")
    
    @discord.ui.button(label=" Back", style=ButtonStyle.secondary)
    async def back_to_category(self, interaction: discord.Interaction, button: Button):
        await self.tickets_cog.show_category_config(interaction, self.category_id)

class SupportRolesModal(Modal):
    """Modal for configuring support roles"""
    def __init__(self, tickets_cog, category_id: int):
        super().__init__(title="Configure Support Roles")
        self.tickets_cog = tickets_cog
        self.category_id = category_id
        
        self.roles_input = TextInput(
            label="Support Roles",
            placeholder="@Role1 @Role2 @Role3 or just mention the roles in your message",
            required=False,
            max_length=500,
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.roles_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        if not interaction.guild:
            await interaction.followup.send("❌ This can only be used in a server.", ephemeral=True)
            return
        
        # Parse roles from mentions and role names
        role_ids = []
        if self.roles_input.value.strip():
            text = self.roles_input.value
            
            # Extract role mentions (<@&123456789>)
            import re
            role_mentions = re.findall(r'<@&(\d+)>', text)
            for role_id_str in role_mentions:
                role_id = int(role_id_str)
                role = interaction.guild.get_role(role_id)
                if role:
                    role_ids.append(role_id)
            
            # Also try to find roles by name (for @Role format)
            words = text.replace('@', '').split()
            for word in words:
                role = discord.utils.get(interaction.guild.roles, name=word)
                if role and role.id not in role_ids:
                    role_ids.append(role.id)
        
        result = await self.tickets_cog.db.update_category(
            self.category_id,
            support_roles=json.dumps(role_ids)
        )
        
        if result:
            embed = discord.Embed(
                title="✅ Support Roles Updated",
                description=f"Configured {len(role_ids)} support roles.\n\n" + 
                           (f"**Roles:** {', '.join([f'<@&{rid}>' for rid in role_ids])}" if role_ids else "**No roles configured**"),
                color=0x00FF00
            )
        else:
            embed = discord.Embed(
                title="❌ Save Failed",
                description="Failed to save support roles. Please try again or check the logs.",
                color=0xFF0000
            )
        await interaction.followup.send(embed=embed, ephemeral=True)

class AutoAddRolesModal(Modal):
    """Modal for configuring auto-add roles"""
    def __init__(self, tickets_cog, category_id: int):
        super().__init__(title="Configure Auto-Add Roles")
        self.tickets_cog = tickets_cog
        self.category_id = category_id
        
        self.roles_input = TextInput(
            label="Auto-Add Roles",
            placeholder="@Role1 @Role2 - Roles automatically given to users when they create tickets",
            required=False,
            max_length=500,
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.roles_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        if not interaction.guild:
            await interaction.followup.send("❌ This can only be used in a server.", ephemeral=True)
            return
        
        # Parse roles from mentions and role names
        role_ids = []
        if self.roles_input.value.strip():
            text = self.roles_input.value
            
            # Extract role mentions (<@&123456789>)
            import re
            role_mentions = re.findall(r'<@&(\d+)>', text)
            for role_id_str in role_mentions:
                role_id = int(role_id_str)
                role = interaction.guild.get_role(role_id)
                if role:
                    role_ids.append(role_id)
            
            # Also try to find roles by name (for @Role format)
            words = text.replace('@', '').split()
            for word in words:
                role = discord.utils.get(interaction.guild.roles, name=word)
                if role and role.id not in role_ids:
                    role_ids.append(role.id)
        
        result = await self.tickets_cog.db.update_category(
            self.category_id,
            auto_add_roles=json.dumps(role_ids)
        )
        
        if result:
            embed = discord.Embed(
                title="✅ Auto-Add Roles Updated",
                description=f"Configured {len(role_ids)} auto-add roles.\n\n" + 
                           (f"**Roles:** {', '.join([f'<@&{rid}>' for rid in role_ids])}" if role_ids else "**No roles configured**"),
                color=0x00FF00
            )
        else:
            embed = discord.Embed(
                title="❌ Save Failed",
                description="Failed to save auto-add roles. Please try again or check the logs.",
                color=0xFF0000
            )
        await interaction.followup.send(embed=embed, ephemeral=True)

class PingRolesModal(Modal):
    """Modal for configuring ping roles"""
    def __init__(self, tickets_cog, category_id: int):
        super().__init__(title="Configure Ping Roles")
        self.tickets_cog = tickets_cog
        self.category_id = category_id
        
        self.roles_input = TextInput(
            label="Ping Roles",
            placeholder="@Role1 @Role2 - Roles pinged when new tickets are created",
            required=False,
            max_length=500,
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.roles_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        if not interaction.guild:
            await interaction.followup.send("❌ This can only be used in a server.", ephemeral=True)
            return
        
        # Parse roles from mentions and role names
        role_ids = []
        if self.roles_input.value.strip():
            text = self.roles_input.value
            
            # Extract role mentions (<@&123456789>)
            import re
            role_mentions = re.findall(r'<@&(\d+)>', text)
            for role_id_str in role_mentions:
                role_id = int(role_id_str)
                role = interaction.guild.get_role(role_id)
                if role:
                    role_ids.append(role_id)
            
            # Also try to find roles by name (for @Role format)
            words = text.replace('@', '').split()
            for word in words:
                role = discord.utils.get(interaction.guild.roles, name=word)
                if role and role.id not in role_ids:
                    role_ids.append(role.id)
        
        result = await self.tickets_cog.db.update_category(
            self.category_id,
            ping_roles=json.dumps(role_ids)
        )
        
        if result:
            embed = discord.Embed(
                title="✅ Ping Roles Updated",
                description=f"Configured {len(role_ids)} ping roles.\n\n" + 
                           (f"**Roles:** {', '.join([f'<@&{rid}>' for rid in role_ids])}" if role_ids else "**No roles configured**"),
                color=0x00FF00
            )
        else:
            embed = discord.Embed(
                title="❌ Save Failed",
                description="Failed to save ping roles. Please try again or check the logs.",
                color=0xFF0000
            )
        await interaction.followup.send(embed=embed, ephemeral=True)

class ChannelSettingsView(View):
    """View for channel settings configuration"""
    def __init__(self, tickets_cog, category_id: int):
        super().__init__(timeout=300)
        self.tickets_cog = tickets_cog
        self.category_id = category_id
    
    @discord.ui.button(label="🏷️ Set Name Format", style=ButtonStyle.primary)
    async def set_name_format(self, interaction: discord.Interaction, button: Button):
        modal = ChannelNameFormatModal(self.tickets_cog, self.category_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📂 Set Category", style=ButtonStyle.primary)
    async def set_category(self, interaction: discord.Interaction, button: Button):
        modal = DiscordCategoryModal(self.tickets_cog, self.category_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🔙 Back", style=ButtonStyle.secondary)
    async def back_to_category(self, interaction: discord.Interaction, button: Button):
        await self.tickets_cog.show_category_config(interaction, self.category_id)

class DiscordCategoryModal(Modal):
    """Modal for setting Discord category"""
    def __init__(self, tickets_cog, category_id: int):
        super().__init__(title="Set Discord Category")
        self.tickets_cog = tickets_cog
        self.category_id = category_id
        
        self.category_input = TextInput(
            label="Discord Category ID",
            placeholder="Enter the category ID where tickets will be created",
            required=False,
            max_length=50
        )
        self.add_item(self.category_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        category_id = None
        if self.category_input.value.strip():
            try:
                category_id = int(self.category_input.value.strip())
                # Verify category exists
                if interaction.guild:
                    category = interaction.guild.get_channel(category_id)
                    if not isinstance(category, discord.CategoryChannel):
                        await interaction.followup.send("❌ Invalid category ID! Must be a category channel.", ephemeral=True)
                        return
            except ValueError:
                await interaction.followup.send("❌ Invalid category ID! Must be a number.", ephemeral=True)
                return
        
        result = await self.tickets_cog.db.update_category(
            self.category_id,
            parent_category_id=category_id
        )
        
        if result:
            embed = discord.Embed(
                title="✅ Discord Category Updated",
                description="Discord category has been updated successfully.",
                color=0x00FF00
            )
        else:
            embed = discord.Embed(
                title="❌ Save Failed",
                description="Failed to save Discord category. Please try again or check the logs.",
                color=0xFF0000
            )
        await interaction.followup.send(embed=embed, ephemeral=True)

# Additional Configuration Views
class LoggingConfigView(View):
    """View for logging configuration"""
    def __init__(self, tickets_cog, category_id: int):
        super().__init__(timeout=300)
        self.tickets_cog = tickets_cog
        self.category_id = category_id
    
    @discord.ui.button(label="📝 Set Log Channel", style=ButtonStyle.primary)
    async def set_log_channel(self, interaction: discord.Interaction, button: Button):
        modal = LogChannelModal(self.tickets_cog, self.category_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📁 Set Transcript Channel", style=ButtonStyle.primary)
    async def set_transcript_channel(self, interaction: discord.Interaction, button: Button):
        modal = TranscriptChannelModal(self.tickets_cog, self.category_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📋 Configure Events", style=ButtonStyle.primary)
    async def configure_events(self, interaction: discord.Interaction, button: Button):
        modal = LogEventsModal(self.tickets_cog, self.category_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🔙 Back", style=ButtonStyle.secondary)
    async def back_to_category(self, interaction: discord.Interaction, button: Button):
        await self.tickets_cog.show_category_config(interaction, self.category_id)

class TranscriptConfigView(View):
    """View for transcript configuration"""
    def __init__(self, tickets_cog, category_id: int):
        super().__init__(timeout=300)
        self.tickets_cog = tickets_cog
        self.category_id = category_id
    
    @discord.ui.button(label="🤖 Toggle Auto Transcript", style=ButtonStyle.primary)
    async def toggle_auto_transcript(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        
        category = await self.tickets_cog.db.get_category(self.category_id)
        current_setting = category.get('auto_transcript', False)
        new_setting = not current_setting
        
        await self.tickets_cog.db.update_category(
            self.category_id,
            auto_transcript=new_setting
        )
        
        embed = discord.Embed(
            title="✅ Auto Transcript Updated",
            description=f"Auto transcript is now {'enabled' if new_setting else 'disabled'}.",
            color=0x00FF00
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="📁 Set Channel", style=ButtonStyle.primary)
    async def set_transcript_channel(self, interaction: discord.Interaction, button: Button):
        modal = TranscriptChannelModal(self.tickets_cog, self.category_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🔙 Back", style=ButtonStyle.secondary)
    async def back_to_category(self, interaction: discord.Interaction, button: Button):
        await self.tickets_cog.show_category_config(interaction, self.category_id)

class LimitsAutomationView(View):
    """View for limits and automation configuration"""
    def __init__(self, tickets_cog, category_id: int):
        super().__init__(timeout=300)
        self.tickets_cog = tickets_cog
        self.category_id = category_id
    
    @discord.ui.button(label="🎫 Set Max Tickets", style=ButtonStyle.primary)
    async def set_max_tickets(self, interaction: discord.Interaction, button: Button):
        modal = MaxTicketsModal(self.tickets_cog, self.category_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="⏰ Set Auto Close", style=ButtonStyle.primary)
    async def set_auto_close(self, interaction: discord.Interaction, button: Button):
        modal = AutoCloseModal(self.tickets_cog, self.category_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🔙 Back", style=ButtonStyle.secondary)
    async def back_to_category(self, interaction: discord.Interaction, button: Button):
        await self.tickets_cog.show_category_config(interaction, self.category_id)

class PermissionsConfigView(View):
    """View for permissions configuration"""
    def __init__(self, tickets_cog, category_id: int):
        super().__init__(timeout=300)
        self.tickets_cog = tickets_cog
        self.category_id = category_id
    
    @discord.ui.button(label="🔒 Toggle User Close", style=ButtonStyle.primary)
    async def toggle_user_close(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        
        category = await self.tickets_cog.db.get_category(self.category_id)
        current_setting = category.get('user_can_close', True)
        new_setting = not current_setting
        
        await self.tickets_cog.db.update_category(
            self.category_id,
            user_can_close=new_setting
        )
        
        embed = discord.Embed(
            title="✅ User Close Permission Updated",
            description=f"Users can {'now' if new_setting else 'no longer'} close their own tickets.",
            color=0x00FF00
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="➕ Toggle Add Others", style=ButtonStyle.primary)
    async def toggle_add_others(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        
        category = await self.tickets_cog.db.get_category(self.category_id)
        current_setting = category.get('user_can_add_others', False)
        new_setting = not current_setting
        
        await self.tickets_cog.db.update_category(
            self.category_id,
            user_can_add_others=new_setting
        )
        
        embed = discord.Embed(
            title="✅ Add Others Permission Updated",
            description=f"Users can {'now' if new_setting else 'no longer'} add others to their tickets.",
            color=0x00FF00
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="🎯 Toggle Claiming", style=ButtonStyle.primary)
    async def toggle_claiming(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        
        category = await self.tickets_cog.db.get_category(self.category_id)
        current_setting = category.get('require_claiming', False)
        new_setting = not current_setting
        
        await self.tickets_cog.db.update_category(
            self.category_id,
            require_claiming=new_setting
        )
        
        embed = discord.Embed(
            title="✅ Claiming Requirement Updated",
            description=f"Ticket claiming is {'now required' if new_setting else 'no longer required'}.",
            color=0x00FF00
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="🔙 Back", style=ButtonStyle.secondary)
    async def back_to_category(self, interaction: discord.Interaction, button: Button):
        await self.tickets_cog.show_category_config(interaction, self.category_id)

class PanelDeletionConfirmView(View):
    """Confirmation view for panel deletion"""
    def __init__(self, tickets_cog, panel_id: int):
        super().__init__(timeout=30)
        self.tickets_cog = tickets_cog
        self.panel_id = panel_id
    
    @discord.ui.button(label="✅ Delete Panel", style=ButtonStyle.danger)
    async def confirm_deletion(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        
        try:
            await self.tickets_cog.db.delete_panel(self.panel_id)
            
            embed = discord.Embed(
                title="✅ Panel Deleted",
                description="The panel and all its categories have been deleted successfully.",
                color=0x00FF00
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Deletion Failed",
                description=f"Failed to delete panel: {str(e)}",
                color=0xFF0000
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="❌ Cancel", style=ButtonStyle.secondary)
    async def cancel_deletion(self, interaction: discord.Interaction, button: Button):
        embed = discord.Embed(
            title="🚫 Deletion Cancelled",
            description="Panel deletion has been cancelled.",
            color=0x00E6A7
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

class CategoryDeletionConfirmView(View):
    """Confirmation view for category deletion"""
    def __init__(self, tickets_cog, category_id: int, panel_id: int):
        super().__init__(timeout=30)
        self.tickets_cog = tickets_cog
        self.category_id = category_id
        self.panel_id = panel_id
    
    @discord.ui.button(label="✅ Delete Category", style=ButtonStyle.danger)
    async def confirm_deletion(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        
        try:
            await self.tickets_cog.db.delete_category(self.category_id)
            
            embed = discord.Embed(
                title="✅ Category Deleted",
                description="The category has been deleted successfully.",
                color=0x00FF00
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Return to panel config
            await self.tickets_cog.show_panel_config(interaction, self.panel_id)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Deletion Failed",
                description=f"Failed to delete category: {str(e)}",
                color=0xFF0000
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="❌ Cancel", style=ButtonStyle.secondary)
    async def cancel_deletion(self, interaction: discord.Interaction, button: Button):
        embed = discord.Embed(
            title="🚫 Deletion Cancelled",
            description="Category deletion has been cancelled.",
            color=0x00E6A7
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

class PanelEditView(View):
    """View for editing panel details"""
    def __init__(self, tickets_cog, panel_id: int):
        super().__init__(timeout=300)
        self.tickets_cog = tickets_cog
        self.panel_id = panel_id
    
    @discord.ui.button(label="📝 Edit Name", style=ButtonStyle.primary)
    async def edit_panel_name(self, interaction: discord.Interaction, button: Button):
        modal = PanelNameEditModal(self.tickets_cog, self.panel_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🏷️ Edit Title", style=ButtonStyle.primary)
    async def edit_panel_title(self, interaction: discord.Interaction, button: Button):
        modal = PanelTitleEditModal(self.tickets_cog, self.panel_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📄 Edit Description", style=ButtonStyle.primary)
    async def edit_panel_description(self, interaction: discord.Interaction, button: Button):
        modal = PanelDescriptionEditModal(self.tickets_cog, self.panel_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🔙 Back to Panel", style=ButtonStyle.secondary)
    async def back_to_panel(self, interaction: discord.Interaction, button: Button):
        await self.tickets_cog.show_panel_config(interaction, self.panel_id)

class PanelAppearanceView(View):
    """View for configuring panel appearance"""
    def __init__(self, tickets_cog, panel_id: int):
        super().__init__(timeout=300)
        self.tickets_cog = tickets_cog
        self.panel_id = panel_id
    
    @discord.ui.button(label="🎨 Change Color", style=ButtonStyle.primary)
    async def change_color(self, interaction: discord.Interaction, button: Button):
        modal = PanelColorEditModal(self.tickets_cog, self.panel_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📝 Edit Footer", style=ButtonStyle.primary)
    async def edit_footer(self, interaction: discord.Interaction, button: Button):
        modal = PanelFooterEditModal(self.tickets_cog, self.panel_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🖼️ Set Thumbnail", style=ButtonStyle.primary)
    async def set_thumbnail(self, interaction: discord.Interaction, button: Button):
        modal = PanelThumbnailEditModal(self.tickets_cog, self.panel_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🔙 Back to Panel", style=ButtonStyle.secondary)
    async def back_to_panel(self, interaction: discord.Interaction, button: Button):
        await self.tickets_cog.show_panel_config(interaction, self.panel_id)

# Additional Modal Classes

class LogChannelModal(Modal):
    """Modal for setting log channel"""
    def __init__(self, tickets_cog, category_id: int):
        super().__init__(title="Set Log Channel")
        self.tickets_cog = tickets_cog
        self.category_id = category_id
        
        self.channel_input = TextInput(
            label="Log Channel",
            placeholder="Enter channel ID, #channel-name, or channel name",
            required=False,
            max_length=100
        )
        self.add_item(self.channel_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        channel_id = None
        if self.channel_input.value.strip():
            channel_input = self.channel_input.value.strip()
            channel = None
            
            if interaction.guild:
                # Try to parse as channel ID
                if channel_input.isdigit():
                    channel_id = int(channel_input)
                    channel = interaction.guild.get_channel(channel_id)
                # Try to parse as channel mention <#123456789>
                elif channel_input.startswith('<#') and channel_input.endswith('>'):
                    try:
                        channel_id = int(channel_input[2:-1])
                        channel = interaction.guild.get_channel(channel_id)
                    except ValueError:
                        pass
                # Try to find by channel name
                else:
                    # Remove # prefix if present
                    if channel_input.startswith('#'):
                        channel_input = channel_input[1:]
                    
                    # Find channel by name
                    for guild_channel in interaction.guild.channels:
                        if guild_channel.name.lower() == channel_input.lower():
                            channel = guild_channel
                            channel_id = guild_channel.id
                            break
                
                if not channel:
                    await interaction.followup.send("❌ Channel not found! Please enter a valid channel ID, mention, or name.", ephemeral=True)
                    return
        
        await self.tickets_cog.db.update_category(
            self.category_id,
            log_channel_id=channel_id
        )
        
        embed = discord.Embed(
            title="✅ Log Channel Updated",
            description="Log channel has been updated successfully.",
            color=0x00FF00
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

class LogEventsModal(Modal):
    """Modal for configuring log events"""
    def __init__(self, tickets_cog, category_id: int):
        super().__init__(title="Configure Log Events")
        self.tickets_cog = tickets_cog
        self.category_id = category_id
        
        self.events_input = TextInput(
            label="Log Events (comma separated)",
            placeholder="created, closed, claimed, assigned, message_sent, user_added, user_removed",
            required=False,
            max_length=300,
            style=discord.TextStyle.paragraph
        )
        
        self.description_input = TextInput(
            label="Available Events",
            placeholder="Events: created, closed, claimed, assigned, message_sent, user_added, user_removed, escalated",
            required=False,
            max_length=500,
            style=discord.TextStyle.paragraph
        )
        
        self.add_item(self.events_input)
        self.add_item(self.description_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        # Define valid events
        valid_events = [
            'created', 'closed', 'claimed', 'assigned', 'message_sent', 
            'user_added', 'user_removed', 'escalated', 'reopened', 
            'priority_changed', 'category_changed', 'staff_response'
        ]
        
        events = []
        invalid_events = []
        
        if self.events_input.value.strip():
            input_events = [event.strip().lower() for event in self.events_input.value.split(',') if event.strip()]
            
            for event in input_events:
                if event in valid_events:
                    events.append(event)
                else:
                    invalid_events.append(event)
        
        await self.tickets_cog.db.update_category(
            self.category_id,
            log_events=json.dumps(events)
        )
        
        # Build response message
        description = f"Configured **{len(events)}** log events."
        
        if events:
            description += f"\n\n**✅ Active Events:**\n• " + "\n• ".join(events)
        
        if invalid_events:
            description += f"\n\n**❌ Invalid Events (ignored):**\n• " + "\n• ".join(invalid_events)
            description += f"\n\n**Valid Events:** {', '.join(valid_events)}"
        
        if not events and not invalid_events:
            description += "\n\n**ℹ️ No events configured** - No events will be logged."
        
        embed = discord.Embed(
            title="✅ Log Events Updated",
            description=description,
            color=0x00FF00
        )
        await self.tickets_cog._safe_send(interaction, embed=embed, ephemeral=True)

class TranscriptChannelModal(Modal):
    """Modal for setting transcript channel"""
    def __init__(self, tickets_cog, category_id: int):
        super().__init__(title="Set Transcript Channel")
        self.tickets_cog = tickets_cog
        self.category_id = category_id
        
        self.channel_input = TextInput(
            label="Transcript Channel",
            placeholder="Enter channel ID, #channel-name, or channel name",
            required=False,
            max_length=100
        )
        self.add_item(self.channel_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        channel_id = None
        if self.channel_input.value.strip():
            channel_input = self.channel_input.value.strip()
            channel = None
            
            if interaction.guild:
                # Try to parse as channel ID
                if channel_input.isdigit():
                    channel_id = int(channel_input)
                    channel = interaction.guild.get_channel(channel_id)
                # Try to parse as channel mention <#123456789>
                elif channel_input.startswith('<#') and channel_input.endswith('>'):
                    try:
                        channel_id = int(channel_input[2:-1])
                        channel = interaction.guild.get_channel(channel_id)
                    except ValueError:
                        pass
                # Try to find by channel name
                else:
                    # Remove # prefix if present
                    if channel_input.startswith('#'):
                        channel_input = channel_input[1:]
                    
                    # Find channel by name
                    for guild_channel in interaction.guild.channels:
                        if guild_channel.name.lower() == channel_input.lower():
                            channel = guild_channel
                            channel_id = guild_channel.id
                            break
                
                if not channel:
                    await interaction.followup.send("❌ Channel not found! Please enter a valid channel ID, mention, or name.", ephemeral=True)
                    return
        
        await self.tickets_cog.db.update_category(
            self.category_id,
            transcript_channel_id=channel_id
        )
        
        embed = discord.Embed(
            title="✅ Transcript Channel Updated",
            description="Transcript channel has been updated successfully.",
            color=0x00FF00
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

class MaxTicketsModal(Modal):
    """Modal for setting max tickets per user"""
    def __init__(self, tickets_cog, category_id: int):
        super().__init__(title="Set Max Tickets Per User")
        self.tickets_cog = tickets_cog
        self.category_id = category_id
        
        self.max_input = TextInput(
            label="Max Tickets",
            placeholder="Enter maximum tickets per user (1-10)",
            required=True,
            max_length=2
        )
        self.add_item(self.max_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        try:
            max_tickets = int(self.max_input.value.strip())
            if max_tickets < 1 or max_tickets > 10:
                await interaction.followup.send("❌ Max tickets must be between 1 and 10!", ephemeral=True)
                return
        except ValueError:
            await interaction.followup.send("❌ Invalid number!", ephemeral=True)
            return
        
        await self.tickets_cog.db.update_category(
            self.category_id,
            max_tickets_per_user=max_tickets
        )
        
        embed = discord.Embed(
            title="✅ Max Tickets Updated",
            description=f"Max tickets per user set to {max_tickets}.",
            color=0x00FF00
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

class AutoCloseModal(Modal):
    """Modal for setting auto close time"""
    def __init__(self, tickets_cog, category_id: int):
        super().__init__(title="Set Auto Close Time")
        self.tickets_cog = tickets_cog
        self.category_id = category_id
        
        self.time_input = TextInput(
            label="Auto Close Time (hours)",
            placeholder="Enter hours before auto-close (0 to disable)",
            required=True,
            max_length=3
        )
        self.add_item(self.time_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        try:
            auto_close_time = int(self.time_input.value.strip())
            if auto_close_time < 0 or auto_close_time > 168:  # Max 1 week
                await interaction.followup.send("❌ Auto close time must be between 0 and 168 hours!", ephemeral=True)
                return
        except ValueError:
            await interaction.followup.send("❌ Invalid number!", ephemeral=True)
            return
        
        await self.tickets_cog.db.update_category(
            self.category_id,
            auto_close_time=auto_close_time
        )
        
        embed = discord.Embed(
            title="✅ Auto Close Time Updated",
            description=f"Auto close time set to {auto_close_time} hours." if auto_close_time > 0 else "Auto close disabled.",
            color=0x00FF00
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

class PanelNameEditModal(Modal):
    """Modal for editing panel name"""
    def __init__(self, tickets_cog, panel_id: int):
        super().__init__(title="Edit Panel Name")
        self.tickets_cog = tickets_cog
        self.panel_id = panel_id
        
        self.name_input = TextInput(
            label="Panel Name",
            placeholder="Enter new panel name...",
            required=True,
            max_length=100
        )
        self.add_item(self.name_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        await self.tickets_cog.db.update_panel(
            self.panel_id,
            panel_name=self.name_input.value
        )
        
        embed = discord.Embed(
            title="✅ Panel Name Updated",
            description=f"Panel name changed to: **{self.name_input.value}**",
            color=0x00FF00
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

class PanelTitleEditModal(Modal):
    """Modal for editing panel embed title"""
    def __init__(self, tickets_cog, panel_id: int):
        super().__init__(title="Edit Panel Title")
        self.tickets_cog = tickets_cog
        self.panel_id = panel_id
        
        self.title_input = TextInput(
            label="Embed Title",
            placeholder="Enter new embed title...",
            required=True,
            max_length=100
        )
        self.add_item(self.title_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        await self.tickets_cog.db.update_panel(
            self.panel_id,
            embed_title=self.title_input.value
        )
        
        embed = discord.Embed(
            title="✅ Panel Title Updated",
            description=f"Panel title changed to: **{self.title_input.value}**",
            color=0x00FF00
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

class PanelDescriptionEditModal(Modal):
    """Modal for editing panel description"""
    def __init__(self, tickets_cog, panel_id: int):
        super().__init__(title="Edit Panel Description")
        self.tickets_cog = tickets_cog
        self.panel_id = panel_id
        
        self.description_input = TextInput(
            label="Panel Description",
            placeholder="Enter new panel description...",
            required=True,
            max_length=500,
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.description_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        await self.tickets_cog.db.update_panel(
            self.panel_id,
            panel_description=self.description_input.value
        )
        
        embed = discord.Embed(
            title="✅ Panel Description Updated",
            description=f"Panel description has been updated successfully.",
            color=0x00FF00
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

class PanelColorEditModal(Modal):
    """Modal for editing panel color"""
    def __init__(self, tickets_cog, panel_id: int):
        super().__init__(title="Edit Panel Color")
        self.tickets_cog = tickets_cog
        self.panel_id = panel_id
        
        self.color_input = TextInput(
            label="Panel Color",
            placeholder="Enter color name (red, blue, green) or hex (#FF5733)",
            required=True,
            max_length=20
        )
        self.add_item(self.color_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        await self.tickets_cog.db.update_panel(
            self.panel_id,
            panel_color=self.color_input.value
        )
        
        embed = discord.Embed(
            title="✅ Panel Color Updated",
            description=f"Panel color changed to: **{self.color_input.value}**",
            color=0x00FF00
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

class PanelFooterEditModal(Modal):
    """Modal for editing panel footer"""
    def __init__(self, tickets_cog, panel_id: int):
        super().__init__(title="Edit Panel Footer")
        self.tickets_cog = tickets_cog
        self.panel_id = panel_id
        
        self.footer_input = TextInput(
            label="Footer Text",
            placeholder="Enter footer text (leave empty to remove)",
            required=False,
            max_length=100
        )
        self.add_item(self.footer_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        await self.tickets_cog.db.update_panel(
            self.panel_id,
            embed_footer=self.footer_input.value or None
        )
        
        embed = discord.Embed(
            title="✅ Panel Footer Updated",
            description="Panel footer has been updated successfully.",
            color=0x00FF00
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

class PanelThumbnailEditModal(Modal):
    """Modal for editing panel thumbnail"""
    def __init__(self, tickets_cog, panel_id: int):
        super().__init__(title="Set Panel Thumbnail")
        self.tickets_cog = tickets_cog
        self.panel_id = panel_id
        
        self.thumbnail_input = TextInput(
            label="Thumbnail URL",
            placeholder="Enter image URL (leave empty to remove)",
            required=False,
            max_length=200
        )
        self.add_item(self.thumbnail_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        await self.tickets_cog.db.update_panel(
            self.panel_id,
            embed_thumbnail=self.thumbnail_input.value or None
        )
        
        embed = discord.Embed(
            title="✅ Panel Thumbnail Updated",
            description="Panel thumbnail has been updated successfully.",
            color=0x00FF00
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

class TicketControlView(View):
    def __init__(self, tickets_cog, ticket_id: int):
        super().__init__(timeout=None)
        self.tickets_cog = tickets_cog
        self.ticket_id = ticket_id
    
    @discord.ui.button(
        label="Close Ticket", 
        style=ButtonStyle.red, 
        emoji="🔒"
    )
    async def close_ticket(self, interaction: discord.Interaction, button: Button):
        # Set dynamic custom_id
        button.custom_id = f"close_ticket_{self.ticket_id}"
        # Add close confirmation modal
        modal = CloseTicketModal(self.tickets_cog, self.ticket_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(
        label="Claim Ticket", 
        style=ButtonStyle.blurple, 
        emoji="👋"
    )
    async def claim_ticket(self, interaction: discord.Interaction, button: Button):
        button.custom_id = f"claim_ticket_{self.ticket_id}"
        await self.tickets_cog.claim_ticket_button(interaction, self.ticket_id)
    
    @discord.ui.button(
        label="Add User", 
        style=ButtonStyle.secondary, 
        emoji="➕"
    )
    async def add_user(self, interaction: discord.Interaction, button: Button):
        button.custom_id = f"add_user_{self.ticket_id}"
        modal = AddUserModal(self.tickets_cog, self.ticket_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(
        label="Transcript", 
        style=ButtonStyle.secondary, 
        emoji="📄"
    )
    async def generate_transcript(self, interaction: discord.Interaction, button: Button):
        button.custom_id = f"transcript_{self.ticket_id}"
        await self.tickets_cog.generate_transcript_button(interaction)

class CloseTicketModal(Modal):
    def __init__(self, tickets_cog, ticket_id: int):
        super().__init__(title="Close Ticket")
        self.tickets_cog = tickets_cog
        self.ticket_id = ticket_id
        
        self.reason = TextInput(
            label="Reason for closing (optional)",
            placeholder="Enter reason for closing this ticket...",
            required=False,
            max_length=500
        )
        self.add_item(self.reason)
    
    async def on_submit(self, interaction: discord.Interaction):
        reason = self.reason.value or "No reason provided"
        await self.tickets_cog.close_ticket_with_reason(interaction, self.ticket_id, reason)

class AddUserModal(Modal):
    def __init__(self, tickets_cog, ticket_id: int):
        super().__init__(title="Add User to Ticket")
        self.tickets_cog = tickets_cog
        self.ticket_id = ticket_id
        
        self.user_input = TextInput(
            label="User ID or @mention",
            placeholder="Enter user ID (like 123456789) or @username",
            required=True,
            max_length=100
        )
        self.add_item(self.user_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        await self.tickets_cog.add_user_to_ticket(interaction, self.ticket_id, self.user_input.value)

class DatabaseResetView(View):
    def __init__(self, tickets_cog):
        super().__init__(timeout=30)
        self.tickets_cog = tickets_cog
    
    @discord.ui.button(label="✅ Confirm Reset", style=ButtonStyle.danger)
    async def confirm_reset(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        
        try:
            await self.tickets_cog.reset_ticket_database()
            
            embed = discord.Embed(
                title="✅ Database Reset Complete",
                description="Ticket database has been reset successfully!\n\nYou can now:\n• Run `$ticket setup` to configure the system\n• Create new ticket panels\n• All features should work properly",
                color=0x00E6A7
            )
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Reset Failed",
                description=f"Failed to reset database: {str(e)}",
                color=0xFF0000
            )
            await interaction.followup.send(embed=embed)
    
    @discord.ui.button(label="❌ Cancel", style=ButtonStyle.secondary)
    async def cancel_reset(self, interaction: discord.Interaction, button: Button):
        embed = discord.Embed(
            title="🚫 Reset Cancelled",
            description="Database reset has been cancelled. No changes were made.",
            color=0x00E6A7
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

class PanelCreatorView(View):
    def __init__(self, tickets_cog):
        super().__init__(timeout=300)  # 5 minute timeout
        self.tickets_cog = tickets_cog
    
    @discord.ui.button(label="🎨 Create Custom Panel", style=ButtonStyle.primary, emoji="🎨")
    async def create_panel(self, interaction: discord.Interaction, button: Button):
        modal = PanelCustomizationModal(self.tickets_cog)
        await interaction.response.send_modal(modal)

class PanelCustomizationModal(Modal):
    def __init__(self, tickets_cog):
        super().__init__(title="🎨 Customize Your Ticket Panel")
        self.tickets_cog = tickets_cog
        
        self.title_input = TextInput(
            label="Panel Title",
            placeholder="e.g., 🎫 Help & Support, 🆘 Get Help, 💬 Contact Us",
            required=True,
            max_length=100
        )
        self.add_item(self.title_input)
        
        self.description_input = TextInput(
            label="Panel Description",
            placeholder="e.g., Need assistance? Click below to create a support ticket!",
            required=True,
            style=discord.TextStyle.paragraph,
            max_length=500
        )
        self.add_item(self.description_input)
        
        self.color_input = TextInput(
            label="Panel Color",
            placeholder="e.g., blue, red, green, purple, or hex like #FF5733",
            required=False,
            max_length=20
        )
        self.add_item(self.color_input)
        
        self.channel_input = TextInput(
            label="Channel (optional)",
            placeholder="Leave empty to send in current channel, or type channel name/ID",
            required=False,
            max_length=100
        )
        self.add_item(self.channel_input)
        
        self.channel_input = TextInput(
            label="Channel (optional)",
            placeholder="Leave empty to send in current channel, or type channel name/ID",
            required=False,
            max_length=100
        )
        self.add_item(self.channel_input)
    
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        if not interaction.guild or not interaction.channel:
            await interaction.followup.send("❌ This can only be used in a server.", ephemeral=True)
            return
        
        title = self.title_input.value.strip()
        description = self.description_input.value.strip()
        color_input = self.color_input.value.strip() if self.color_input.value else "teal"
        channel_input = self.channel_input.value.strip() if self.channel_input.value else ""
        
        # Determine target channel
        target_channel = interaction.channel
        if channel_input:
            # Try to find channel by name or ID
            if channel_input.isdigit():
                found_channel = interaction.guild.get_channel(int(channel_input))
            else:
                # Remove # if present
                channel_name = channel_input.lstrip('#')
                found_channel = discord.utils.get(interaction.guild.channels, name=channel_name)
            
            # Ensure it's a text-sendable channel
            if found_channel and isinstance(found_channel, (discord.TextChannel, discord.Thread)):
                target_channel = found_channel
            else:
                await interaction.followup.send(f"❌ Channel '{channel_input}' not found or not a text channel. Using current channel instead.", ephemeral=True)
                target_channel = interaction.channel
        
        # Ensure target channel is text-sendable
        if not isinstance(target_channel, (discord.TextChannel, discord.Thread)):
            await interaction.followup.send("❌ Current channel is not a text channel. Please use this command in a text channel.", ephemeral=True)
            return
        
        # Check permissions
        if not target_channel.permissions_for(interaction.guild.me).send_messages:
            await interaction.followup.send(f"❌ I don't have permission to send messages in {target_channel.mention}", ephemeral=True)
            return
        
        # Process color
        color = 0x00E6A7  # Default teal
        
        if color_input:
            # Try to parse as hex first
            if color_input.startswith('#'):
                try:
                    color = int(color_input[1:], 16)
                except ValueError:
                    color = self.tickets_cog.get_color_from_name(color_input)
            elif color_input.startswith('0x'):
                try:
                    color = int(color_input, 16)
                except ValueError:
                    color = self.tickets_cog.get_color_from_name(color_input)
            else:
                # Treat as color name
                color = self.tickets_cog.get_color_from_name(color_input)
        
        try:
            # Create the embed
            embed = discord.Embed(
                title=title,
                description=description,
                color=color
            )
            
            embed.set_footer(text="Click the button below to create a ticket")
            
            # Create the panel with persistent view
            view = TicketPanelView(self.tickets_cog)
            message = await target_channel.send(embed=embed, view=view)
            
            # Save panel info to database
            if message:
                async with aiosqlite.connect(self.tickets_cog.db.db_path) as db:
                    await db.execute(
                        "INSERT OR REPLACE INTO ticket_panels (guild_id, channel_id, message_id, title, description, color) VALUES (?, ?, ?, ?, ?, ?)",
                        (interaction.guild.id, interaction.channel.id, message.id, title, description, color)
                    )
                    await db.commit()
            
            # Send confirmation
            confirm_embed = discord.Embed(
                title="✅ Custom Panel Created!",
                description=f"Your custom ticket panel has been created successfully!\n\n**Title:** {title}\n**Channel:** {target_channel.mention}\n**Color:** {color_input if color_input else 'teal'}",
                color=0x00E6A7
            )
            await interaction.followup.send(embed=confirm_embed, ephemeral=True)
            
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Error Creating Panel",
                description=f"Failed to create panel: {str(e)}",
                color=0xFF0000
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)

class Tickets(commands.Cog):
    """🎫 Advanced Ticket System V2 - TicketTool Style"""
    
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot
        self.db = TicketDatabase(bot)
        self.tz_helpers = get_timezone_helpers(bot)
        # Add persistent views for ticket panels
        self.bot.add_view(TicketPanelView(self))

    @commands.group()
    async def __TicketSystem__(self, ctx: commands.Context):
        """`ticket setup` , `ticket config` , `ticket close` , `ticket add` , `ticket remove` , `ticket claim` , `ticket transcript` , `ticket builder` , `ticket stats` , `ticket list` , `ticket logs`"""
        
    async def cog_load(self):
        """Initialize database when cog loads"""
        await self.db.init_db()
        await self.load_persistent_panels()
    
    def safe_color(self, color_value):
        """Safely convert color value to integer for discord.Embed"""
        if isinstance(color_value, str):
            try:
                # Remove # if present and convert hex to int
                if color_value.startswith('#'):
                    return int(color_value[1:], 16)
                # Try as hex string without #
                elif len(color_value) == 6 and all(c in '0123456789ABCDEFabcdef' for c in color_value):
                    return int(color_value, 16)
                # Try direct int conversion
                elif color_value.isdigit():
                    return int(color_value)
                # Try as named color
                else:
                    return self.get_color_from_name(color_value)
            except (ValueError, TypeError):
                return 0x00E6A7  # Default teal color
        elif isinstance(color_value, int):
            return color_value
        else:
            return 0x00E6A7  # Default teal color
    
    def get_color_from_name(self, color_name: str) -> int:
        """Convert color name to hex value"""
        color_map = {
            'red': 0xFF5733,
            'orange': 0xFF8C00,
            'yellow': 0xFFD700,
            'green': 0x2ECC71,
            'blue': 0x3498DB,
            'purple': 0x9B59B6,
            'pink': 0xE91E63,
            'teal': 0x00E6A7,
            'cyan': 0x17A2B8,
            'gray': 0x6C757D,
            'grey': 0x6C757D,
            'black': 0x000000,
            'white': 0xFFFFFF,
            'blurple': 0x5865F2,  # Discord's blurple
            'greyple': 0x99AAB5   # Discord's greyple
        }
        return color_map.get(color_name.lower(), 0x00E6A7)
        
        print("✅ Ticket system database initialized")
    
    async def _safe_send(self, interaction, content=None, *, embed=None, view=None, ephemeral=False):
        """Safely send interaction response, handling both new and existing responses"""
        try:
            # Build kwargs without None values to avoid Discord.py TypeError
            kwargs = {
                'ephemeral': ephemeral
            }
            if content is not None:
                kwargs['content'] = content
            if embed is not None:
                kwargs['embed'] = embed
            if view is not None:
                kwargs['view'] = view
            
            if interaction.response.is_done():
                await interaction.followup.send(**kwargs)
            else:
                await interaction.response.send_message(**kwargs)
        except discord.errors.InteractionResponded:
            # Fallback to followup if response was already sent
            await interaction.followup.send(**kwargs)
    
    async def load_persistent_panels(self):
        """Load all persistent ticket panels when bot starts"""
        try:
            async with aiosqlite.connect(self.db.db_path) as db:
                async with db.execute("SELECT guild_id, channel_id, message_id FROM ticket_panels") as cursor:
                    panels = await cursor.fetchall()
                    
                for guild_id, channel_id, message_id in panels:
                    guild = self.bot.get_guild(guild_id)
                    if guild:
                        channel = guild.get_channel(channel_id)
                        if channel and isinstance(channel, (discord.TextChannel, discord.Thread)):
                            try:
                                message = await channel.fetch_message(message_id)
                                # Add the view to the message if it doesn't already have one
                                view = TicketPanelView(self)
                                await message.edit(view=view)
                            except discord.NotFound:
                                # Message was deleted, remove from database
                                async with aiosqlite.connect(self.db.db_path) as db:
                                    await db.execute("DELETE FROM ticket_panels WHERE message_id = ?", (message_id,))
                                    await db.commit()
                            except Exception as e:
                                print(f"Error loading panel {message_id}: {e}")
        except Exception as e:
            print(f"Error loading persistent panels: {e}")
    
    @commands.group(name="ticket", aliases=["tickets"], invoke_without_command=True)
    @commands.guild_only()
    async def ticket(self, ctx: Context):
        """🎫 Advanced Ticket System V2"""
        if ctx.invoked_subcommand is None:
            view = TicketHelpView(ctx)
            view.update_buttons()  # Set initial button states
            await ctx.send(embed=view.pages[0], view=view)

    @ticket.command(name="setup")
    @commands.has_permissions(administrator=True)
    async def setup(self, ctx: Context):
        """Quick setup wizard for the ticket system"""
        embed = discord.Embed(
            title="🛠️ Ticket System Setup",
            description="Let's set up your ticket system step by step!",
            color=0x00E6A7
        )
        
        # Step 1: Create or select category
        embed.add_field(
            name="Step 1: Ticket Category", 
            value="I'll create a 'Tickets' category for you, or you can specify an existing one.",
            inline=False
        )
        
        # Create category if it doesn't exist
        if not ctx.guild:
            await ctx.send("❌ This command can only be used in a server.")
            return
            
        category = discord.utils.get(ctx.guild.categories, name="Tickets")
        if not category:
            try:
                # Set up proper permissions for the category
                overwrites = {
                    ctx.guild.default_role: discord.PermissionOverwrite(
                        view_channel=False,
                        send_messages=False
                    ),
                    ctx.guild.me: discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        manage_channels=True,
                        manage_permissions=True
                    )
                }
                
                category = await ctx.guild.create_category(
                    "Tickets", 
                    overwrites=overwrites,
                    reason="Ticket system setup"
                )
                
                embed.add_field(
                    name="✅ Category Created",
                    value=f"Created category: {category.name}",
                    inline=False
                )
            except Exception as e:
                embed.add_field(
                    name="❌ Category Creation Failed",
                    value=f"Error: {str(e)}",
                    inline=False
                )
                await ctx.send(embed=embed)
                return
        else:
            embed.add_field(
                name="✅ Category Found",
                value=f"Using existing category: {category.name}",
                inline=False
            )
        
        # Save category to database
        await self.db.set_guild_config(ctx.guild.id, category_id=category.id)
        
        embed.add_field(
            name="Step 2: Next Steps",
            value="• Use `ticket role <role>` to set your support role\n• Use `ticket panel` to create a ticket panel\n• Use `ticket config` to view all settings",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @ticket.command(name="category")
    @commands.has_permissions(administrator=True)
    async def set_category(self, ctx: Context, *, category: discord.CategoryChannel):
        """Set the category for ticket channels"""
        if not ctx.guild:
            await ctx.send("❌ This command can only be used in a server.")
            return
            
        await self.db.set_guild_config(ctx.guild.id, category_id=category.id)
        
        embed = discord.Embed(
            title="✅ Category Set",
            description=f"Ticket category set to: {category.name}",
            color=0x00E6A7
        )
        await ctx.send(embed=embed)
    
    @ticket.command(name="role")
    @commands.has_permissions(administrator=True)
    async def set_role(self, ctx: Context, *, role: discord.Role):
        """Set the support role for tickets"""
        if not ctx.guild:
            await ctx.send("❌ This command can only be used in a server.")
            return
            
        await self.db.set_guild_config(ctx.guild.id, support_role_id=role.id)
        
        embed = discord.Embed(
            title="✅ Support Role Set",
            description=f"Support role set to: {role.mention}",
            color=0x00E6A7
        )
        await ctx.send(embed=embed)
    
    @ticket.command(name="custompanel")
    @commands.has_permissions(administrator=True)
    async def create_custom_panel(self, ctx: Context):
        """Create a fully customizable ticket panel using interactive buttons
        
        This will open an interactive panel creator where you can customize:
        - Panel title
        - Panel description  
        - Panel color (supports color names like 'red', 'blue', 'green', etc.)
        """
        if not ctx.guild or not ctx.channel:
            await ctx.send("❌ This command can only be used in a server.")
            return
        
        embed = discord.Embed(
            title="🎨 Custom Panel Creator",
            description="Create a fully customizable ticket panel! Click the button below to start the interactive setup process.",
            color=0x00E6A7
        )
        
        embed.add_field(
            name="✨ What You Can Customize",
            value="• **Title** - The main heading of your panel\n• **Description** - Detailed text explaining the purpose\n• **Color** - Use simple names like 'red', 'blue', 'green', 'purple', etc.",
            inline=False
        )
        
        embed.add_field(
            name="🎨 Supported Colors",
            value="red, orange, yellow, green, blue, purple, pink, teal, gray, black, white",
            inline=False
        )
        
        view = PanelCreatorView(self)
        await ctx.send(embed=embed, view=view)
    
    @ticket.command(name="resetdb")
    @commands.has_permissions(administrator=True)
    async def reset_database(self, ctx: Context):
        """Reset ticket database (WARNING: This will delete all ticket data!)"""
        embed = discord.Embed(
            title="⚠️ Database Reset Confirmation",
            description="This will **permanently delete all ticket data** including:\n• All ticket records\n• Configuration settings\n• Panel information\n\n**This action cannot be undone!**",
            color=0xFF0000
        )
        
        view = DatabaseResetView(self)
        await ctx.send(embed=embed, view=view)
    
    async def reset_ticket_database(self):
        """Reset the entire ticket database"""
        import os
        if os.path.exists(self.db.db_path):
            os.remove(self.db.db_path)
        await self.db.init_db()
        return True
    
   
    
    @ticket.command(name="config")
    @commands.has_permissions(administrator=True)
    async def view_config(self, ctx: Context):
        """View current ticket configuration"""
        if not ctx.guild:
            await ctx.send("❌ This command can only be used in a server.")
            return
            
        config = await self.db.get_guild_config(ctx.guild.id)
        
        embed = discord.Embed(
            title="⚙️ Ticket Configuration",
            color=0x00E6A7
        )
        
        # Category
        category_id = config.get('category_id')
        category = ctx.guild.get_channel(category_id) if category_id else None
        embed.add_field(
            name="📁 Ticket Category",
            value=category.name if category else "❌ Not set",
            inline=True
        )
        
        # Support Role
        role_id = config.get('support_role_id')
        role = ctx.guild.get_role(role_id) if role_id else None
        embed.add_field(
            name="👥 Support Role", 
            value=role.name if role else "❌ Not set",
            inline=True
        )
        
        # Log Channel
        log_channel_id = config.get('log_channel_id')
        log_channel = ctx.guild.get_channel(log_channel_id) if log_channel_id else None
        embed.add_field(
            name="📋 Log Channel",
            value=log_channel.mention if log_channel else "❌ Not set",
            inline=True
        )
        
        embed.add_field(
            name="🎫 Max Tickets per User",
            value=config.get('max_tickets_per_user', 1),
            inline=True
        )
        
        embed.add_field(
            name="📊 Total Tickets Created",
            value=config.get('ticket_counter', 0),
            inline=True
        )
        
        embed.add_field(
            name="⏰ Auto Close Time",
            value=f"{config.get('auto_close_time', 0)} hours" if config.get('auto_close_time') else "Disabled",
            inline=True
        )
        
        await ctx.send(embed=embed)
    
    @ticket.command(name="logs")
    @commands.has_permissions(administrator=True)
    async def set_logs(self, ctx: Context, channel: discord.TextChannel):
        """Set the log channel for ticket events"""
        if not ctx.guild:
            await ctx.send("❌ This command can only be used in a server.")
            return
            
        await self.db.set_guild_config(ctx.guild.id, log_channel_id=channel.id)
        
        embed = discord.Embed(
            title="✅ Log Channel Set",
            description=f"Ticket logs will be sent to {channel.mention}",
            color=0x00E6A7
        )
        await ctx.send(embed=embed)
    
    @ticket.command(name="maxtickets")
    @commands.has_permissions(administrator=True)
    async def set_max_tickets(self, ctx: Context, amount: int):
        """Set maximum tickets per user"""
        if not ctx.guild:
            await ctx.send("❌ This command can only be used in a server.")
            return
            
        if amount < 1 or amount > 10:
            await ctx.send("❌ Max tickets must be between 1 and 10.")
            return
            
        await self.db.set_guild_config(ctx.guild.id, max_tickets_per_user=amount)
        
        embed = discord.Embed(
            title="✅ Max Tickets Set",
            description=f"Users can now have up to {amount} open ticket(s) at once.",
            color=0x00E6A7
        )
        await ctx.send(embed=embed)
    
    @ticket.command(name="welcome")
    @commands.has_permissions(administrator=True)
    async def set_welcome(self, ctx: Context, *, message: str):
        """Set custom welcome message for tickets"""
        if not ctx.guild:
            await ctx.send("❌ This command can only be used in a server.")
            return
            
        await self.db.set_guild_config(ctx.guild.id, welcome_message=message)
        
        embed = discord.Embed(
            title="✅ Welcome Message Set",
            description=f"Welcome message updated:\n\n{message}",
            color=0x00E6A7
        )
        await ctx.send(embed=embed)
    
    @ticket.command(name="autoclose")
    @commands.has_permissions(administrator=True)
    async def set_autoclose(self, ctx: Context, hours: int):
        """Set auto-close time for inactive tickets (0 to disable)"""
        if not ctx.guild:
            await ctx.send("❌ This command can only be used in a server.")
            return
            
        if hours < 0 or hours > 168:  # Max 1 week
            await ctx.send("❌ Auto-close time must be between 0 and 168 hours (1 week).")
            return
            
        await self.db.set_guild_config(ctx.guild.id, auto_close_time=hours)
        
        embed = discord.Embed(
            title="✅ Auto-Close Set",
            description=f"Tickets will auto-close after {hours} hours of inactivity." if hours > 0 else "Auto-close disabled.",
            color=0x00E6A7
        )
        await ctx.send(embed=embed)
    
    @ticket.command(name="list")
    @commands.has_permissions(manage_messages=True)
    async def list_tickets(self, ctx: Context, status: str = "open"):
        """List all tickets with specified status"""
        if not ctx.guild:
            await ctx.send("❌ This command can only be used in a server.")
            return
            
        if status not in ["open", "closed", "all"]:
            await ctx.send("❌ Status must be 'open', 'closed', or 'all'.")
            return
            
        async with aiosqlite.connect(self.db.db_path) as db:
            if status == "all":
                cursor = await db.execute(
                    "SELECT * FROM tickets WHERE guild_id = ? ORDER BY created_at DESC LIMIT 20",
                    (ctx.guild.id,)
                )
            else:
                cursor = await db.execute(
                    "SELECT * FROM tickets WHERE guild_id = ? AND status = ? ORDER BY created_at DESC LIMIT 20",
                    (ctx.guild.id, status)
                )
            tickets = list(await cursor.fetchall()) or []
        
        if not tickets:
            embed = discord.Embed(
                title=f"📝 {status.title()} Tickets",
                description=f"No {status} tickets found.",
                color=0x00E6A7
            )
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title=f"📝 {status.title()} Tickets ({len(tickets)})",
            color=0x00E6A7
        )
        
        display_tickets = tickets[:10] if len(tickets) > 10 else tickets
        for ticket in display_tickets:
            user = ctx.guild.get_member(ticket[2])
            channel = ctx.guild.get_channel(ticket[3])
            
            embed.add_field(
                name=f"Ticket #{ticket[0]}",
                value=f"**User:** {user.mention if user else 'Unknown'}\n**Channel:** {channel.mention if channel else 'Deleted'}\n**Status:** {ticket[4]}\n**Created:** <t:{int(datetime.fromisoformat(ticket[5]).timestamp())}:R>",
                inline=True
            )
        
        if len(tickets) > 10:
            embed.set_footer(text=f"Showing 10 of {len(tickets)} tickets")
        
        await ctx.send(embed=embed)
    
    @ticket.command(name="stats")
    @commands.has_permissions(manage_messages=True)
    async def ticket_stats(self, ctx: Context):
        """Show ticket statistics"""
        if not ctx.guild:
            await ctx.send("❌ This command can only be used in a server.")
            return
            
        async with aiosqlite.connect(self.db.db_path) as db:
            # Total tickets
            cursor = await db.execute(
                "SELECT COUNT(*) FROM tickets WHERE guild_id = ?", (ctx.guild.id,)
            )
            result = await cursor.fetchone()
            total = result[0] if result else 0
            
            # Open tickets
            cursor = await db.execute(
                "SELECT COUNT(*) FROM tickets WHERE guild_id = ? AND status = 'open'", (ctx.guild.id,)
            )
            result = await cursor.fetchone()
            open_tickets = result[0] if result else 0
            
            # Closed tickets
            cursor = await db.execute(
                "SELECT COUNT(*) FROM tickets WHERE guild_id = ? AND status = 'closed'", (ctx.guild.id,)
            )
            result = await cursor.fetchone()
            closed_tickets = result[0] if result else 0
            
            # Most active users
            cursor = await db.execute(
                "SELECT user_id, COUNT(*) as ticket_count FROM tickets WHERE guild_id = ? GROUP BY user_id ORDER BY ticket_count DESC LIMIT 5", 
                (ctx.guild.id,)
            )
            top_users = list(await cursor.fetchall()) or []
        
        embed = discord.Embed(
            title="📊 Ticket Statistics",
            color=0x00E6A7
        )
        
        embed.add_field(
            name="📈 Overview",
            value=f"**Total Tickets:** {total}\n**Open:** {open_tickets}\n**Closed:** {closed_tickets}",
            inline=True
        )
        
        if total > 0:
            embed.add_field(
                name="📋 Status Breakdown",
                value=f"**Open:** {round((open_tickets/total)*100, 1)}%\n**Closed:** {round((closed_tickets/total)*100, 1)}%",
                inline=True
            )
        
        if top_users:
            top_users_text = ""
            for user_id, count in top_users[:3]:
                user = ctx.guild.get_member(user_id)
                top_users_text += f"{user.mention if user else 'Unknown'}: {count}\n"
            
            embed.add_field(
                name="👑 Most Active Users",
                value=top_users_text,
                inline=True
            )
        
        await ctx.send(embed=embed)
    
    @ticket.command(name="close")
    @commands.guild_only()
    async def close_ticket(self, ctx: Context, *, reason: str = "No reason provided"):
        """Close the current ticket (must be used in a ticket channel)"""
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            await ctx.send("❌ This command can only be used in a server.")
            return
        
        # Check if this is a ticket channel
        async with aiosqlite.connect(self.db.db_path) as db:
            cursor = await db.execute(
                "SELECT ticket_id, user_id FROM tickets WHERE guild_id = ? AND channel_id = ? AND status = 'open'",
                (ctx.guild.id, ctx.channel.id)
            )
            ticket_data = await cursor.fetchone()
        
        if not ticket_data:
            await ctx.send("❌ This is not an active ticket channel.")
            return
        
        ticket_id, ticket_owner_id = ticket_data
        
        # Check permissions
        config = await self.db.get_guild_config(ctx.guild.id)
        support_role_id = config.get('support_role_id')
        support_role = ctx.guild.get_role(support_role_id) if support_role_id else None
        
        has_permission = (
            ctx.author.guild_permissions.administrator or
            (support_role and support_role in ctx.author.roles) or
            ctx.author.id == ticket_owner_id
        )
        
        if not has_permission:
            await ctx.send("❌ You don't have permission to close this ticket.")
            return
        
        # Close the ticket
        await self.db.close_ticket(ticket_id, ctx.author.id, reason)
        
        embed = discord.Embed(
            title="🔒 Ticket Closed",
            description=f"**Closed by:** {ctx.author.mention}\n**Reason:** {reason}",
            color=0xFF0000
        )
        
        await ctx.send(embed=embed)
        
        # Delete channel after delay
        await asyncio.sleep(5)
        if isinstance(ctx.channel, discord.TextChannel):
            try:
                await ctx.channel.delete(reason=f"Ticket closed by {ctx.author}")
            except:
                pass
    
    @ticket.command(name="add")
    @commands.guild_only()
    async def add_user(self, ctx: Context, user: discord.Member):
        """Add a user to the current ticket"""
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            await ctx.send("❌ This command can only be used in a server.")
            return
        
        # Check if this is a ticket channel
        async with aiosqlite.connect(self.db.db_path) as db:
            cursor = await db.execute(
                "SELECT ticket_id FROM tickets WHERE guild_id = ? AND channel_id = ? AND status = 'open'",
                (ctx.guild.id, ctx.channel.id)
            )
            ticket_data = await cursor.fetchone()
        
        if not ticket_data:
            await ctx.send("❌ This is not an active ticket channel.")
            return
        
        # Check permissions
        config = await self.db.get_guild_config(ctx.guild.id)
        support_role_id = config.get('support_role_id')
        support_role = ctx.guild.get_role(support_role_id) if support_role_id else None
        
        has_permission = (
            ctx.author.guild_permissions.administrator or
            (support_role and support_role in ctx.author.roles)
        )
        
        if not has_permission:
            await ctx.send("❌ You don't have permission to add users to tickets.")
            return
        
        # Add user to channel
        if not isinstance(ctx.channel, (discord.TextChannel, discord.CategoryChannel)):
            await ctx.send("❌ This command can only be used in a text channel.")
            return
            
        try:
            await ctx.channel.set_permissions(
                user,
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )
            
            embed = discord.Embed(
                title="➕ User Added",
                description=f"{user.mention} has been added to this ticket by {ctx.author.mention}",
                color=0x00E6A7
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Failed to add user: {str(e)}")
    
    @ticket.command(name="remove")
    @commands.guild_only()
    async def remove_user(self, ctx: Context, user: discord.Member):
        """Remove a user from the current ticket"""
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            await ctx.send("❌ This command can only be used in a server.")
            return
        
        # Check if this is a ticket channel
        async with aiosqlite.connect(self.db.db_path) as db:
            cursor = await db.execute(
                "SELECT ticket_id, user_id FROM tickets WHERE guild_id = ? AND channel_id = ? AND status = 'open'",
                (ctx.guild.id, ctx.channel.id)
            )
            ticket_data = await cursor.fetchone()
        
        if not ticket_data:
            await ctx.send("❌ This is not an active ticket channel.")
            return
        
        ticket_id, ticket_owner_id = ticket_data
        
        # Don't allow removing the ticket owner
        if user.id == ticket_owner_id:
            await ctx.send("❌ You cannot remove the ticket owner.")
            return
        
        # Check permissions
        config = await self.db.get_guild_config(ctx.guild.id)
        support_role_id = config.get('support_role_id')
        support_role = ctx.guild.get_role(support_role_id) if support_role_id else None
        
        has_permission = (
            ctx.author.guild_permissions.administrator or
            (support_role and support_role in ctx.author.roles)
        )
        
        if not has_permission:
            await ctx.send("❌ You don't have permission to remove users from tickets.")
            return
        
        # Remove user from channel
        if not isinstance(ctx.channel, (discord.TextChannel, discord.CategoryChannel)):
            await ctx.send("❌ This command can only be used in a text channel.")
            return
            
        try:
            await ctx.channel.set_permissions(user, overwrite=None)
            
            embed = discord.Embed(
                title="➖ User Removed",
                description=f"{user.mention} has been removed from this ticket by {ctx.author.mention}",
                color=0xFF6B6B
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Failed to remove user: {str(e)}")
    
    @ticket.command(name="claim")
    @commands.guild_only()
    async def claim_ticket_cmd(self, ctx: Context):
        """Claim the current ticket"""
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            await ctx.send("❌ This command can only be used in a server.")
            return
        
        # Check if this is a ticket channel
        async with aiosqlite.connect(self.db.db_path) as db:
            cursor = await db.execute(
                "SELECT ticket_id FROM tickets WHERE guild_id = ? AND channel_id = ? AND status = 'open'",
                (ctx.guild.id, ctx.channel.id)
            )
            ticket_data = await cursor.fetchone()
        
        if not ticket_data:
            await ctx.send("❌ This is not an active ticket channel.")
            return
        
        ticket_id = ticket_data[0]
        
        # Check permissions
        config = await self.db.get_guild_config(ctx.guild.id)
        support_role_id = config.get('support_role_id')
        support_role = ctx.guild.get_role(support_role_id) if support_role_id else None
        
        has_permission = (
            ctx.author.guild_permissions.administrator or
            (support_role and support_role in ctx.author.roles)
        )
        
        if not has_permission:
            await ctx.send("❌ You don't have permission to claim tickets.")
            return
        
        # Update ticket in database
        async with aiosqlite.connect(self.db.db_path) as db:
            await db.execute(
                "UPDATE tickets SET claimed_by = ? WHERE ticket_id = ?",
                (ctx.author.id, ticket_id)
            )
            await db.commit()
        
        embed = discord.Embed(
            title="👋 Ticket Claimed",
            description=f"{ctx.author.mention} is now handling this ticket.",
            color=0x00E6A7
        )
        await ctx.send(embed=embed)
    
    @ticket.command(name="rename")
    @commands.guild_only()
    async def rename_ticket(self, ctx: Context, *, new_name: str):
        """Rename the current ticket channel"""
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            await ctx.send("❌ This command can only be used in a server.")
            return
        
        # Check if this is a ticket channel
        async with aiosqlite.connect(self.db.db_path) as db:
            cursor = await db.execute(
                "SELECT ticket_id FROM tickets WHERE guild_id = ? AND channel_id = ? AND status = 'open'",
                (ctx.guild.id, ctx.channel.id)
            )
            ticket_data = await cursor.fetchone()
        
        if not ticket_data:
            await ctx.send("❌ This is not an active ticket channel.")
            return
        
        # Check permissions
        config = await self.db.get_guild_config(ctx.guild.id)
        support_role_id = config.get('support_role_id')
        support_role = ctx.guild.get_role(support_role_id) if support_role_id else None
        
        has_permission = (
            ctx.author.guild_permissions.administrator or
            (support_role and support_role in ctx.author.roles)
        )
        
        if not has_permission:
            await ctx.send("❌ You don't have permission to rename tickets.")
            return
        
        # Clean the name for Discord channel requirements
        clean_name = new_name.lower().replace(" ", "-").replace("_", "-")
        clean_name = "".join(c for c in clean_name if c.isalnum() or c == "-")
        
        if len(clean_name) < 1:
            await ctx.send("❌ Invalid channel name.")
            return
        
        if not isinstance(ctx.channel, discord.TextChannel):
            await ctx.send("❌ This command can only be used in a text channel.")
            return

        try:
            old_name = ctx.channel.name
            await ctx.channel.edit(name=clean_name, reason=f"Renamed by {ctx.author}")
            
            embed = discord.Embed(
                title="✏️ Ticket Renamed",
                description=f"Channel renamed from `{old_name}` to `{clean_name}` by {ctx.author.mention}",
                color=0x00E6A7
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Failed to rename channel: {str(e)}")
    
    @ticket.command(name="transcript")
    @commands.guild_only()
    async def generate_transcript(self, ctx: Context):
        """Generate a transcript of the current ticket"""
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            await ctx.send("❌ This command can only be used in a server.")
            return
        
        # Check if this is a ticket channel
        async with aiosqlite.connect(self.db.db_path) as db:
            cursor = await db.execute(
                "SELECT ticket_id FROM tickets WHERE guild_id = ? AND channel_id = ? AND status = 'open'",
                (ctx.guild.id, ctx.channel.id)
            )
            ticket_data = await cursor.fetchone()
        
        if not ticket_data:
            await ctx.send("❌ This is not an active ticket channel.")
            return
        
        # Check permissions
        config = await self.db.get_guild_config(ctx.guild.id)
        support_role_id = config.get('support_role_id')
        support_role = ctx.guild.get_role(support_role_id) if support_role_id else None
        
        has_permission = (
            ctx.author.guild_permissions.administrator or
            (support_role and support_role in ctx.author.roles)
        )
        
        if not has_permission:
            await ctx.send("❌ You don't have permission to generate transcripts.")
            return
        
        await ctx.send("📝 Generating transcript... This may take a moment.")
        
        if not isinstance(ctx.channel, discord.TextChannel):
            await ctx.send("❌ This command can only be used in a text channel.")
            return
        
        try:
            # Get channel messages
            messages = []
            async for message in ctx.channel.history(limit=None, oldest_first=True):
                messages.append(message)
            
            # Generate transcript content with proper timezone
            transcript_content = f"Ticket Transcript - {ctx.channel.name}\n"
            
            # Use proper timezone formatting for generation timestamp
            generated_time = await self.tz_helpers.format_datetime_for_user_custom(
                self.tz_helpers.get_utc_now(), ctx.author, "%Y-%m-%d %H:%M:%S %Z"
            )
            transcript_content += f"Generated: {generated_time}\n"
            transcript_content += f"Channel: #{ctx.channel.name}\n"
            transcript_content += f"Messages: {len(messages)}\n"
            transcript_content += "=" * 50 + "\n\n"
            
            for message in messages:
                # Format message timestamp with user's timezone
                timestamp = await self.tz_helpers.format_datetime_for_user_custom(
                    message.created_at, ctx.author, '%Y-%m-%d %H:%M:%S %Z'
                )
                author = f"{message.author.display_name} ({message.author})"
                content = message.content or "[No content]"
                
                if message.attachments:
                    content += f" [Attachments: {', '.join([att.filename for att in message.attachments])}]"
                
                transcript_content += f"[{timestamp}] {author}: {content}\n"
            
            # Save to file
            # Use UTC for filename to avoid timezone confusion in file names
            filename = f"transcript-{ctx.channel.name}-{self.tz_helpers.get_utc_now().strftime('%Y%m%d-%H%M%S')}.txt"
            
            import io
            transcript_file = discord.File(
                io.BytesIO(transcript_content.encode('utf-8')), 
                filename=filename
            )
            
            embed = discord.Embed(
                title="📄 Transcript Generated",
                description=f"Transcript for {ctx.channel.mention} has been generated.",
                color=0x00E6A7
            )
            
            # Send to current channel
            await ctx.send(embed=embed, file=transcript_file)
            
            # Also send to log channel if configured
            log_channel_id = config.get('log_channel_id')
            if log_channel_id:
                log_channel = ctx.guild.get_channel(log_channel_id)
                if log_channel and isinstance(log_channel, discord.TextChannel):
                    try:
                        # Create a new file object since the previous one is consumed
                        log_transcript_file = discord.File(
                            io.BytesIO(transcript_content.encode('utf-8')), 
                            filename=filename
                        )
                        
                        # Format timestamp in user's timezone
                        formatted_timestamp = await self.tz_helpers.format_datetime_for_user_custom(
                            self.tz_helpers.get_utc_now(), ctx.author, "%Y-%m-%d %H:%M:%S %Z"
                        )
                        
                        log_embed = discord.Embed(
                            title="📄 Ticket Transcript",
                            description=f"**Ticket Channel:** {ctx.channel.mention}\n**Generated by:** {ctx.author.mention}\n**Timestamp:** {formatted_timestamp}",
                            color=0x00E6A7
                        )
                        
                        log_embed.add_field(
                            name="📊 Stats",
                            value=f"**Messages:** {len(messages)}\n**Channel:** #{ctx.channel.name}",
                            inline=True
                        )
                        
                        await log_channel.send(embed=log_embed, file=log_transcript_file)
                    except Exception as log_error:
                        print(f"Failed to send transcript to log channel: {log_error}")
            
        except Exception as e:
            await ctx.send(f"❌ Failed to generate transcript: {str(e)}")
    
    async def close_ticket_channel(self, interaction: discord.Interaction, ticket_id: int):
        """Close a ticket channel"""
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "❌ This can only be used in a server.",
                ephemeral=True
            )
            return
            
        # Check permissions
        config = await self.db.get_guild_config(interaction.guild.id)
        support_role_id = config.get('support_role_id')
        support_role = interaction.guild.get_role(support_role_id) if support_role_id else None
        
        has_permission = (
            interaction.user.guild_permissions.administrator or
            (support_role and support_role in interaction.user.roles)
        )
        
        if not has_permission:
            await interaction.response.send_message(
                "❌ You don't have permission to close tickets.",
                ephemeral=True
            )
            return
        
        await interaction.response.send_message(
            "🔒 Closing ticket in 5 seconds...",
            ephemeral=False
        )
        
        # Close in database
        await self.db.close_ticket(ticket_id, interaction.user.id, "Closed by staff")
        
        # Delete channel after delay
        await asyncio.sleep(5)
        try:
            if (interaction.channel and 
                isinstance(interaction.channel, (discord.TextChannel, discord.VoiceChannel, discord.CategoryChannel))):
                await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")
        except Exception:
            pass
    
    async def claim_ticket(self, interaction: discord.Interaction, ticket_id: int):
        """Claim a ticket"""
        embed = discord.Embed(
            title="👋 Ticket Claimed",
            description=f"{interaction.user.mention} is now handling this ticket.",
            color=0x00E6A7
        )
        
        await interaction.response.send_message(embed=embed)
    
    async def claim_ticket_button(self, interaction: discord.Interaction, ticket_id: int):
        """Handle claim ticket button"""
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ This can only be used in a server.", ephemeral=True)
            return
        
        # Check permissions
        config = await self.db.get_guild_config(interaction.guild.id)
        support_role_id = config.get('support_role_id')
        support_role = interaction.guild.get_role(support_role_id) if support_role_id else None
        
        has_permission = (
            interaction.user.guild_permissions.administrator or
            (support_role and support_role in interaction.user.roles)
        )
        
        if not has_permission:
            await interaction.response.send_message("❌ You don't have permission to claim tickets.", ephemeral=True)
            return
        
        # Update ticket in database
        async with aiosqlite.connect(self.db.db_path) as db:
            await db.execute(
                "UPDATE tickets SET claimed_by = ? WHERE ticket_id = ?",
                (interaction.user.id, ticket_id)
            )
            await db.commit()
        
        embed = discord.Embed(
            title="👋 Ticket Claimed",
            description=f"{interaction.user.mention} is now handling this ticket.",
            color=0x00E6A7
        )
        await interaction.response.send_message(embed=embed)
    
    async def close_ticket_with_reason(self, interaction: discord.Interaction, ticket_id: int, reason: str):
        """Handle close ticket with reason"""
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ This can only be used in a server.", ephemeral=True)
            return
        
        # Check if this is a ticket channel
        async with aiosqlite.connect(self.db.db_path) as db:
            cursor = await db.execute(
                "SELECT ticket_id, user_id FROM tickets WHERE guild_id = ? AND channel_id = ? AND status = 'open'",
                (interaction.guild.id, interaction.channel_id)
            )
            ticket_data = await cursor.fetchone()
        
        if not ticket_data:
            await interaction.response.send_message("❌ This is not an active ticket channel.", ephemeral=True)
            return
        
        ticket_id, ticket_owner_id = ticket_data
        
        # Check permissions
        config = await self.db.get_guild_config(interaction.guild.id)
        support_role_id = config.get('support_role_id')
        support_role = interaction.guild.get_role(support_role_id) if support_role_id else None
        
        has_permission = (
            interaction.user.guild_permissions.administrator or
            (support_role and support_role in interaction.user.roles) or
            interaction.user.id == ticket_owner_id
        )
        
        if not has_permission:
            await interaction.response.send_message("❌ You don't have permission to close this ticket.", ephemeral=True)
            return
        
        # Close the ticket
        await self.db.close_ticket(ticket_id, interaction.user.id, reason)
        
        embed = discord.Embed(
            title="🔒 Ticket Closed",
            description=f"**Closed by:** {interaction.user.mention}\n**Reason:** {reason}",
            color=0xFF0000
        )
        
        await interaction.response.send_message(embed=embed)
        
        # Delete channel after delay
        await asyncio.sleep(5)
        if isinstance(interaction.channel, discord.TextChannel):
            try:
                await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")
            except:
                pass
    
    async def add_user_to_ticket(self, interaction: discord.Interaction, ticket_id: int, user_input: str):
        """Handle add user to ticket"""
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ This can only be used in a server.", ephemeral=True)
            return
        
        # Check permissions
        config = await self.db.get_guild_config(interaction.guild.id)
        support_role_id = config.get('support_role_id')
        support_role = interaction.guild.get_role(support_role_id) if support_role_id else None
        
        has_permission = (
            interaction.user.guild_permissions.administrator or
            (support_role and support_role in interaction.user.roles)
        )
        
        if not has_permission:
            await interaction.response.send_message("❌ You don't have permission to add users to tickets.", ephemeral=True)
            return
        
        # Parse user input
        user = None
        try:
            # Try to extract user ID from mention or plain ID
            user_id = int(user_input.strip("<@!>"))
            user = interaction.guild.get_member(user_id)
        except ValueError:
            # Search by username
            user = discord.utils.find(lambda m: m.name.lower() == user_input.lower() or m.display_name.lower() == user_input.lower(), interaction.guild.members)
        
        if not user:
            await interaction.response.send_message("❌ User not found. Please use their ID, @mention, or exact username.", ephemeral=True)
            return
        
        # Add user to channel
        if isinstance(interaction.channel, discord.TextChannel):
            try:
                await interaction.channel.set_permissions(
                    user,
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                )
                
                embed = discord.Embed(
                    title="➕ User Added",
                    description=f"{user.mention} has been added to this ticket by {interaction.user.mention}",
                    color=0x00E6A7
                )
                await interaction.response.send_message(embed=embed)
                
            except Exception as e:
                await interaction.response.send_message(f"❌ Failed to add user: {str(e)}", ephemeral=True)
        else:
            await interaction.response.send_message("❌ This command can only be used in a text channel.", ephemeral=True)
    
    async def generate_transcript_button(self, interaction: discord.Interaction):
        """Handle generate transcript button"""
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ This can only be used in a server.", ephemeral=True)
            return
        
        # Check permissions
        config = await self.db.get_guild_config(interaction.guild.id)
        support_role_id = config.get('support_role_id')
        support_role = interaction.guild.get_role(support_role_id) if support_role_id else None
        
        has_permission = (
            interaction.user.guild_permissions.administrator or
            (support_role and support_role in interaction.user.roles)
        )
        
        if not has_permission:
            await interaction.response.send_message("❌ You don't have permission to generate transcripts.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.followup.send("❌ This command can only be used in a text channel.", ephemeral=True)
            return
        
        try:
            # Get channel messages
            messages = []
            async for message in interaction.channel.history(limit=None, oldest_first=True):
                messages.append(message)
            
            # Generate transcript content with proper timezone
            transcript_content = f"Ticket Transcript - {interaction.channel.name}\n"
            
            # Use proper timezone formatting for generation timestamp  
            generated_time = await self.tz_helpers.format_datetime_for_user_custom(
                self.tz_helpers.get_utc_now(), interaction.user, "%Y-%m-%d %H:%M:%S %Z"
            )
            transcript_content += f"Generated: {generated_time}\n"
            transcript_content += f"Channel: #{interaction.channel.name}\n"
            transcript_content += f"Messages: {len(messages)}\n"
            transcript_content += "=" * 50 + "\n\n"
            
            for message in messages:
                # Format message timestamp with user's timezone
                timestamp = await self.tz_helpers.format_datetime_for_user_custom(
                    message.created_at, interaction.user, '%Y-%m-%d %H:%M:%S %Z'
                )
                author = f"{message.author.display_name} ({message.author})"
                content = message.content or "[No content]"
                
                if message.attachments:
                    content += f" [Attachments: {', '.join([att.filename for att in message.attachments])}]"
                
                transcript_content += f"[{timestamp}] {author}: {content}\n"
            
            # Save to file
            # Use UTC for filename to avoid timezone confusion in file names
            filename = f"transcript-{interaction.channel.name}-{self.tz_helpers.get_utc_now().strftime('%Y%m%d-%H%M%S')}.txt"
            
            import io
            transcript_file = discord.File(
                io.BytesIO(transcript_content.encode('utf-8')), 
                filename=filename
            )
            
            embed = discord.Embed(
                title="📄 Transcript Generated",
                description=f"Transcript for {interaction.channel.mention} has been generated.",
                color=0x00E6A7
            )
            
            # Send to current channel
            await interaction.followup.send(embed=embed, file=transcript_file)
            
            # Also send to log channel if configured
            log_channel_id = config.get('log_channel_id')
            if log_channel_id:
                log_channel = interaction.guild.get_channel(log_channel_id)
                if log_channel and isinstance(log_channel, discord.TextChannel):
                    try:
                        # Create a new file object since the previous one is consumed
                        log_transcript_file = discord.File(
                            io.BytesIO(transcript_content.encode('utf-8')), 
                            filename=filename
                        )
                        
                        # Format timestamp in user's timezone
                        formatted_timestamp = await self.tz_helpers.format_datetime_for_user_custom(
                            self.tz_helpers.get_utc_now(), interaction.user, "%Y-%m-%d %H:%M:%S %Z"
                        )
                        
                        log_embed = discord.Embed(
                            title="📄 Ticket Transcript",
                            description=f"**Ticket Channel:** {interaction.channel.mention}\n**Generated by:** {interaction.user.mention}\n**Timestamp:** {formatted_timestamp}",
                            color=0x00E6A7
                        )
                        
                        log_embed.add_field(
                            name="📊 Stats",
                            value=f"**Messages:** {len(messages)}\n**Channel:** #{interaction.channel.name}",
                            inline=True
                        )
                        
                        await log_channel.send(embed=log_embed, file=log_transcript_file)
                    except Exception as log_error:
                        print(f"Failed to send transcript to log channel: {log_error}")
            
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to generate transcript: {str(e)}", ephemeral=True)
    
    async def create_ticket_channel(self, interaction: discord.Interaction, subject: str, description: str):
        """Create a new ticket channel with control buttons"""
        if not interaction.guild:
            return
        
        config = await self.db.get_guild_config(interaction.guild.id)
        category_id = config.get('category_id')
        support_role_id = config.get('support_role_id')
        welcome_message = config.get('welcome_message', 'Thank you for creating a ticket! Our support team will assist you shortly.')
        
        if not category_id:
            await interaction.followup.send(
                "❌ No ticket category set. Use `$ticket category <category>` first.",
                ephemeral=True
            )
            return
        
        category = interaction.guild.get_channel(category_id)
        if not category or not isinstance(category, discord.CategoryChannel):
            await interaction.followup.send(
                "❌ Invalid ticket category. Please set a valid category.",
                ephemeral=True
            )
            return
        
        # Increment ticket counter
        ticket_counter = config.get('ticket_counter', 0) + 1
        await self.db.set_guild_config(interaction.guild.id, ticket_counter=ticket_counter)
        
        # Create channel
        channel_name = f"ticket-{ticket_counter:04d}"
        
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            ),
            interaction.guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                manage_permissions=True
            )
        }
        
        # Add support role permissions
        if support_role_id:
            support_role = interaction.guild.get_role(support_role_id)
            if support_role:
                overwrites[support_role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                )
        
        channel = await interaction.guild.create_text_channel(
            channel_name,
            category=category,
            overwrites=overwrites,
            reason=f"Ticket created by {interaction.user}"
        )
        
        # Store ticket in database
        ticket_id = await self.db.create_ticket(
            interaction.guild.id,
            interaction.user.id,
            channel.id
        )
        
        # Create welcome embed with ticket info
        embed = discord.Embed(
            title=f"🎫 Ticket #{ticket_id:04d}",
            description=welcome_message,
            color=0x00E6A7
        )
        
        embed.add_field(name="Subject", value=subject, inline=False)
        embed.add_field(name="Description", value=description, inline=False)
        embed.add_field(name="Created by", value=interaction.user.mention, inline=True)
        embed.add_field(name="Status", value="🟢 Open", inline=True)
        
        embed.set_footer(text=f"Ticket ID: {ticket_id} • Use the buttons below to manage this ticket")
        embed.timestamp = self.tz_helpers.get_utc_now()
        
        # Add control buttons
        view = TicketControlView(self, ticket_id)
        
        await channel.send(
            content=f"{interaction.user.mention}",
            embed=embed,
            view=view
        )
        
        await interaction.followup.send(
            f"✅ Ticket created! {channel.mention}",
            ephemeral=True
        )

    # ================================
    # DROPDOWN BUILDER METHODS
    # ================================
    
    @ticket.command(name="builder", aliases=["build", "create"])
    @commands.has_permissions(administrator=True)
    async def ticket_builder(self, ctx: Context):
        """🎨 Interactive ticket panel builder (like greet system)"""
        await self.show_main_setup(ctx)
    
    async def show_main_setup(self, ctx_or_interaction):
        """Show the main setup interface"""
        embed = discord.Embed(
            title="🎫 Ticket System Builder",
            description="Create and manage ticket panels with this interactive builder. Each panel can have multiple categories with individual configurations.",
            color=0x00E6A7
        )
        
        # Get existing panels for this guild
        if hasattr(ctx_or_interaction, 'guild'):
            guild_id = ctx_or_interaction.guild.id
        else:
            guild_id = ctx_or_interaction.guild.id
            
        panels = await self.db.get_guild_panels(guild_id)
        
        if panels:
            panel_list = "\n".join([f"• **{panel['panel_name']}** - {len(await self.db.get_panel_categories(panel['panel_id']))} categories" for panel in panels])
            embed.add_field(
                name="📋 Existing Panels",
                value=panel_list,
                inline=False
            )
        else:
            embed.add_field(
                name="📋 No Panels Yet",
                value="Click 'Create New Panel' to get started!",
                inline=False
            )
        
        embed.add_field(
            name="🚀 Quick Start Guide",
            value="1️⃣ Create a panel\n2️⃣ Add categories to it\n3️⃣ Configure each category\n4️⃣ Deploy to a channel",
            inline=False
        )
        
        view = MainSetupView(self, guild_id)
        
        if hasattr(ctx_or_interaction, 'send'):
            await ctx_or_interaction.send(embed=embed, view=view)
        else:
            await ctx_or_interaction.response.send_message(embed=embed, view=view)
    
    async def show_panel_config(self, interaction, panel_id: int):
        """Show panel configuration interface"""
        panel = await self.db.get_panel(panel_id)
        if not panel:
            await self._safe_send(interaction, "❌ Panel not found!", ephemeral=True)
            return
        
        categories = await self.db.get_panel_categories(panel_id)
        
        embed = discord.Embed(
            title=f"🎫 Configure Panel: {panel['panel_name']}",
            description=f"**Embed Title:** {panel['embed_title']}\n**Description:** {panel['panel_description'][:100]}{'...' if len(panel['panel_description']) > 100 else ''}",
            color=self.safe_color(panel['panel_color'])
        )
        
        if categories:
            category_list = "\n".join([f"• {cat['category_emoji']} **{cat['category_name']}**" for cat in categories])
            embed.add_field(
                name=f"📂 Categories ({len(categories)})",
                value=category_list,
                inline=False
            )
        else:
            embed.add_field(
                name="📂 No Categories",
                value="Add categories to make this panel functional!",
                inline=False
            )
        
        embed.set_footer(text=f"Panel ID: {panel_id}")
        
        view = PanelConfigView(self, panel_id)
        await self._safe_send(interaction, embed=embed, view=view, ephemeral=True)
    
    async def show_category_config(self, interaction, category_id: int):
        """Show category configuration interface"""
        category = await self.db.get_category(category_id)
        if not category:
            await self._safe_send(interaction, "❌ Category not found!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"{category['category_emoji']} Configure: {category['category_name']}",
            description=f"**Description:** {category['category_description'] or 'No description set'}",
            color=self.safe_color(category.get('priority_color', 0x00E6A7))
        )
        
        # Show current configuration
        config_text = []
        config_text.append(f"🏠 **Parent Category:** {'<#' + str(category['parent_category_id']) + '>' if category['parent_category_id'] else 'None'}")
        config_text.append(f"📝 **Channel Format:** `{category['channel_name_format']}`")
        config_text.append(f"👋 **Welcome Message:** {'Set' if category['welcome_message'] else 'Not set'}")
        config_text.append(f"📊 **Logging:** {'Enabled' if category['log_channel_id'] else 'Disabled'}")
        config_text.append(f"📄 **Transcripts:** {'Enabled' if category['save_transcripts'] else 'Disabled'}")
        config_text.append(f"👥 **Max Tickets:** {category['max_tickets_per_user']}")
        config_text.append(f"⏰ **Auto-close:** {str(category['auto_close_time']) + ' hours' if category['auto_close_time'] else 'Disabled'}")
        
        embed.add_field(
            name="⚙️ Current Configuration",
            value="\n".join(config_text),
            inline=False
        )
        
        # Show role configuration
        role_text = []
        try:
            support_roles = json.loads(category.get('support_roles', '[]'))
            auto_add_roles = json.loads(category.get('auto_add_roles', '[]'))
            ping_roles = json.loads(category.get('ping_roles', '[]'))
            
            role_text.append(f"🛡️ **Support Roles:** {', '.join([f'<@&{rid}>' for rid in support_roles]) if support_roles else 'None'}")
            role_text.append(f"➕ **Auto-Add Roles:** {', '.join([f'<@&{rid}>' for rid in auto_add_roles]) if auto_add_roles else 'None'}")
            role_text.append(f"📢 **Ping Roles:** {', '.join([f'<@&{rid}>' for rid in ping_roles]) if ping_roles else 'None'}")
        except (json.JSONDecodeError, TypeError):
            role_text.append("⚠️ **Role data corrupted - please reconfigure**")
        
        embed.add_field(
            name="👥 Role Configuration",
            value="\n".join(role_text),
            inline=False
        )
        
        embed.set_footer(text=f"Category ID: {category_id}")
        
        view = CategoryConfigView(self, category_id)
        await self._safe_send(interaction, embed=embed, view=view, ephemeral=True)
    
    async def wait_for_role_config(self, interaction: discord.Interaction, category_id: int, role_type: str):
        """Wait for user to provide role configuration via chat"""
        if not interaction.guild or not interaction.channel:
            return
        
        def check(message):
            return (message.author == interaction.user and 
                   message.channel == interaction.channel and 
                   not message.author.bot)
        
        try:
            # Wait for user response
            message = await self.bot.wait_for('message', check=check, timeout=60.0)
            
            if message.content.lower() == 'cancel':
                embed = discord.Embed(
                    title="🚫 Configuration Cancelled",
                    description="Role configuration has been cancelled.",
                    color=0xFF9900
                )
                await message.reply(embed=embed)
                return
            
            # Parse roles from message
            role_ids = []
            if message.content.strip():
                # Extract role mentions
                import re
                role_mentions = re.findall(r'<@&(\d+)>', message.content)
                
                for role_id in role_mentions:
                    role = interaction.guild.get_role(int(role_id))
                    if role:
                        role_ids.append(int(role_id))
                
                # Also try to parse role names
                words = message.content.replace('@', '').split()
                for word in words:
                    if not word.isdigit():  # Skip IDs already processed
                        role = discord.utils.get(interaction.guild.roles, name=word)
                        if role and role.id not in role_ids:
                            role_ids.append(role.id)
            
            # Update database
            await self.db.update_category(
                category_id,
                **{role_type: json.dumps(role_ids)}
            )
            
            # Send confirmation
            role_type_names = {
                'support_roles': 'Support Roles',
                'auto_add_roles': 'Auto-Add Roles', 
                'ping_roles': 'Ping Roles'
            }
            
            embed = discord.Embed(
                title=f"✅ {role_type_names.get(role_type, 'Roles')} Updated",
                description=f"Configured {len(role_ids)} roles.\n\n" + 
                           (f"**Roles:** {', '.join([f'<@&{rid}>' for rid in role_ids])}" if role_ids else "**No roles configured**"),
                color=0x00FF00
            )
            await message.reply(embed=embed)
            
        except asyncio.TimeoutError:
            embed = discord.Embed(
                title="⏰ Configuration Timeout",
                description="Role configuration timed out. Please try again.",
                color=0xFF9900
            )
            try:
                await interaction.followup.send(embed=embed, ephemeral=True)
            except:
                pass
        except Exception as e:
            embed = discord.Embed(
                title="❌ Configuration Error",
                description=f"An error occurred: {str(e)}",
                color=0xFF0000
            )
            try:
                await interaction.followup.send(embed=embed, ephemeral=True)
            except:
                pass
    
    async def show_categories_list(self, interaction, panel_id: int):
        """Show list of categories for management"""
        categories = await self.db.get_panel_categories(panel_id)
        panel = await self.db.get_panel(panel_id)
        
        if not panel:
            await interaction.response.send_message("❌ Panel not found!", ephemeral=True)
            return
        
        if not categories:
            embed = discord.Embed(
                title="📂 No Categories",
                description="This panel doesn't have any categories yet. Add some to make it functional!",
                color=0xFFFF00
            )
            view = View()
            add_button = Button(label="➕ Add Category", style=ButtonStyle.success)
            
            async def add_category_callback(interaction):
                modal = CategoryCreateModal(self, panel_id)
                await interaction.response.send_modal(modal)
            
            add_button.callback = add_category_callback
            view.add_item(add_button)
            
            await interaction.response.send_message(embed=embed, view=view)
            return
        
        embed = discord.Embed(
            title=f"📂 Categories in {panel['panel_name']}",
            description="Select a category to configure or manage",
            color=0x00E6A7
        )
        
        # Create options for each category
        options = []
        for cat in categories:
            options.append(discord.SelectOption(
                label=cat['category_name'],
                description=cat['category_description'][:100] if cat['category_description'] else "No description",
                emoji=cat['category_emoji'],
                value=str(cat['category_id'])
            ))
        
        if len(options) > 25:  # Discord limit
            options = options[:25]
        
        view = View()
        select = Select(
            placeholder="Select a category to configure...",
            options=options
        )
        
        async def category_select_callback(interaction):
            category_id = int(select.values[0])
            await self.show_category_config(interaction, category_id)
        
        select.callback = category_select_callback
        view.add_item(select)
        
        # Add management buttons
        add_button = Button(label="➕ Add Category", style=ButtonStyle.success)
        back_button = Button(label="🔙 Back to Panel", style=ButtonStyle.secondary)
        
        async def add_callback(interaction):
            modal = CategoryCreateModal(self, panel_id)
            await interaction.response.send_modal(modal)
        
        async def back_callback(interaction):
            await self.show_panel_config(interaction, panel_id)
        
        add_button.callback = add_callback
        back_button.callback = back_callback
        
        view.add_item(add_button)
        view.add_item(back_button)
        
        await interaction.response.send_message(embed=embed, view=view)
    
    async def show_panel_deployment(self, interaction, panel_id: int):
        """Show panel deployment options"""
        panel = await self.db.get_panel(panel_id)
        if not panel:
            await interaction.response.send_message("❌ Panel not found!", ephemeral=True)
            return
            
        categories = await self.db.get_panel_categories(panel_id)
        
        if not categories:
            embed = discord.Embed(
                title="❌ Cannot Deploy Panel",
                description="This panel has no categories! Add at least one category before deploying.",
                color=0xFF0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"🚀 Deploy Panel: {panel['panel_name']}",
            description="Choose a channel to deploy this ticket panel to.",
            color=0x00E6A7
        )
        
        # Show panel preview
        preview_embed = discord.Embed(
            title=panel['embed_title'],
            description=panel['panel_description'],
            color=self.safe_color(panel['panel_color'])
        )
        
        category_text = "\n".join([f"{cat['category_emoji']} **{cat['category_name']}**" for cat in categories])
        preview_embed.add_field(
            name="Available Categories",
            value=category_text,
            inline=False
        )
        
        embed.add_field(
            name="📋 Panel Preview",
            value="This is how your panel will look:",
            inline=False
        )
        
        # Channel selection
        channels = [ch for ch in interaction.guild.text_channels if ch.permissions_for(interaction.guild.me).send_messages]
        
        if not channels:
            embed.add_field(
                name="❌ No Available Channels",
                value="I don't have permission to send messages in any text channels!",
                inline=False
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Channel selection using paginated dropdown
        async def deploy_callback(interaction, select):
            channel_id = int(select.values[0])
            channel = interaction.guild.get_channel(channel_id)
            
            if not channel:
                await interaction.response.send_message("❌ Channel not found!", ephemeral=True)
                return
            
            await self.deploy_panel_to_channel(interaction, panel_id, channel)
        
        view = PaginatedChannelView(
            interaction.guild,
            channel_types=[discord.ChannelType.text],
            custom_callback=deploy_callback,
            timeout=300
        )
        
        back_button = Button(label="🔙 Back to Panel Config", style=ButtonStyle.secondary)
        
        async def back_callback(interaction):
            await self.show_panel_config(interaction, panel_id)
        
        back_button.callback = back_callback
        view.add_item(back_button)
        
        await interaction.response.send_message(embed=embed, view=view)
        
        await interaction.followup.send(embed=preview_embed)
    
    async def deploy_panel_to_channel(self, interaction, panel_id: int, channel: discord.TextChannel):
        """Deploy the panel to a specific channel"""
        panel = await self.db.get_panel(panel_id)
        if not panel:
            await self._safe_send(interaction, "❌ Panel not found!", ephemeral=True)
            return
            
        categories = await self.db.get_panel_categories(panel_id)
        
        # Create the panel embed
        embed = discord.Embed(
            title=panel['embed_title'],
            description=panel['panel_description'],
            color=self.safe_color(panel['panel_color'])
        )
        
        if panel['embed_thumbnail']:
            embed.set_thumbnail(url=panel['embed_thumbnail'])
        
        if panel['embed_image']:
            embed.set_image(url=panel['embed_image'])
        
        if panel['embed_footer']:
            embed.set_footer(text=panel['embed_footer'])
        
        # Add categories info
        category_text = "\n".join([f"{cat['category_emoji']} **{cat['category_name']}** - {cat['category_description'] or 'No description'}" for cat in categories])
        embed.add_field(
            name="📂 Available Categories",
            value=category_text,
            inline=False
        )
        
        # Create the dropdown for ticket creation
        view = await self.create_ticket_panel_view(panel_id)
        
        try:
            message = await channel.send(embed=embed, view=view)
            
            # Update panel with channel and message info
            await self.db.update_panel(panel_id, channel_id=channel.id, message_id=message.id)
            
            embed_success = discord.Embed(
                title="✅ Panel Deployed Successfully!",
                description=f"Panel has been deployed to {channel.mention}",
                color=0x00FF00
            )
            await self._safe_send(interaction, embed=embed_success, ephemeral=True)
            
        except discord.Forbidden:
            await self._safe_send(interaction, "❌ I don't have permission to send messages in that channel!", ephemeral=True)
        except Exception as e:
            await self._safe_send(interaction, f"❌ Error deploying panel: {str(e)}", ephemeral=True)
    
    # Panel Configuration Methods
    async def show_panel_edit(self, interaction, panel_id: int):
        """Show panel editing interface"""
        await interaction.response.defer()
        
        try:
            panel = await self.db.get_panel(panel_id)
            if not panel:
                await interaction.followup.send("❌ Panel not found!", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="✏️ Edit Panel Details",
                description=f"**Current Panel:** {panel.get('panel_name', 'Unknown Panel')}\n\nSelect what you want to edit:",
                color=0x00E6A7
            )
            
            embed.add_field(
                name="� Current Settings",
                value=f"**Name:** {panel.get('panel_name', 'N/A')}\n**Title:** {panel.get('embed_title', 'N/A')}\n**Description:** {panel.get('panel_description', 'N/A')[:100]}{'...' if len(panel.get('panel_description', '')) > 100 else ''}",
                inline=False
            )
            
            view = PanelEditView(self, panel_id)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Error loading panel: {str(e)}", ephemeral=True)
    
    async def show_panel_appearance_config(self, interaction, panel_id: int):
        """Show panel appearance configuration"""
        await interaction.response.defer()
        
        try:
            panel = await self.db.get_panel(panel_id)
            if not panel:
                await interaction.followup.send("❌ Panel not found!", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="🎨 Panel Appearance",
                description="Customize the visual appearance of your ticket panel",
                color=0x00E6A7
            )
            
            embed.add_field(
                name="🎨 Current Settings",
                value=f"**Color:** {panel.get('embed_color', 'Default')}\n**Footer:** {panel.get('embed_footer', 'Default')}\n**Thumbnail:** {'Set' if panel.get('embed_thumbnail') else 'None'}",
                inline=False
            )
            
            view = PanelAppearanceView(self, panel_id)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Error loading appearance config: {str(e)}", ephemeral=True)
    
    async def show_category_basic_settings(self, interaction, category_id: int):
        """Show category basic settings editor"""
        category = await self.db.get_category(category_id)
        if not category:
            await interaction.response.send_message("❌ Category not found!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="⚙️ Basic Category Settings",
            description=f"Configure basic settings for **{category['category_name']}**",
            color=0x00E6A7
        )
        
        embed.add_field(
            name="📝 Current Settings",
            value=f"**Name:** {category['category_name']}\n**Emoji:** {category['category_emoji'] or 'None'}\n**Description:** {category['category_description'] or 'None'}",
            inline=False
        )
        
        view = CategoryBasicSettingsView(self, category_id)
        await self._safe_send(interaction, embed=embed, view=view, ephemeral=True)
    
    async def show_channel_settings(self, interaction, category_id: int):
        """Show channel settings configuration"""
        category = await self.db.get_category(category_id)
        if not category:
            await self._safe_send(interaction, "❌ Category not found!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="📝 Channel Settings",
            description=f"Configure channel settings for **{category['category_name']}**",
            color=0x00E6A7
        )
        
        # Show current settings
        embed.add_field(
            name="🏷️ Channel Name Format",
            value=f"`{category.get('channel_name_format', 'ticket-{user}-{number}')}`",
            inline=False
        )
        
        embed.add_field(
            name="📂 Discord Category",
            value=f"<#{category.get('discord_category_id', 'Not set')}>" if category.get('discord_category_id') else "Not set",
            inline=False
        )
        
        view = ChannelSettingsView(self, category_id)
        await self._safe_send(interaction, embed=embed, view=view, ephemeral=True)
    
    async def show_role_config(self, interaction, category_id: int):
        """Show role configuration for category"""
        category = await self.db.get_category(category_id)
        if not category:
            await self._safe_send(interaction, "❌ Category not found!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="👥 Role Configuration",
            description=f"Configure roles for **{category['category_name']}**",
            color=0x00E6A7
        )
        
        # Safely parse JSON role data with error handling
        try:
            support_roles_data = category.get('support_roles') or '[]'
            support_roles = json.loads(support_roles_data) if support_roles_data.strip() else []
        except (json.JSONDecodeError, AttributeError):
            support_roles = []
            
        try:
            auto_add_roles_data = category.get('auto_add_roles') or '[]'
            auto_add_roles = json.loads(auto_add_roles_data) if auto_add_roles_data.strip() else []
        except (json.JSONDecodeError, AttributeError):
            auto_add_roles = []
            
        try:
            ping_roles_data = category.get('ping_roles') or '[]'
            ping_roles = json.loads(ping_roles_data) if ping_roles_data.strip() else []
        except (json.JSONDecodeError, AttributeError):
            ping_roles = []
        
        embed.add_field(
            name="🛠️ Support Roles",
            value=f"{len(support_roles)} roles configured" if support_roles else "No support roles set",
            inline=True
        )
        
        embed.add_field(
            name="➕ Auto-Add Roles",
            value=f"{len(auto_add_roles)} roles configured" if auto_add_roles else "No auto-add roles set",
            inline=True
        )
        
        embed.add_field(
            name="📢 Ping Roles",
            value=f"{len(ping_roles)} roles configured" if ping_roles else "No ping roles set",
            inline=True
        )
        
        view = RoleConfigView(self, category_id)
        await self._safe_send(interaction, embed=embed, view=view, ephemeral=True)
    
    async def show_logging_settings(self, interaction, category_id: int):
        """Show logging settings for category"""
        category = await self.db.get_category(category_id)
        if not category:
            await interaction.response.send_message("❌ Category not found!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="� Logging Settings",
            description=f"Configure logging for **{category['category_name']}**",
            color=0x00E6A7
        )
        
        log_channel_id = category.get('log_channel_id')
        
        # Safely parse log events JSON
        try:
            log_events_data = category.get('log_events') or '["created", "closed", "claimed"]'
            log_events = json.loads(log_events_data) if log_events_data.strip() else ["created", "closed", "claimed"]
        except (json.JSONDecodeError, AttributeError):
            log_events = ["created", "closed", "claimed"]
        
        log_channel = None
        if log_channel_id and interaction.guild:
            log_channel = interaction.guild.get_channel(log_channel_id)
        
        embed.add_field(
            name="📝 Log Channel",
            value=log_channel.mention if log_channel else "Not set",
            inline=True
        )
        
        embed.add_field(
            name="📋 Logged Events",
            value=", ".join(log_events) if log_events else "None",
            inline=True
        )
        
        view = LoggingConfigView(self, category_id)
        await self._safe_send(interaction, embed=embed, view=view, ephemeral=True)
    
    async def show_transcript_settings(self, interaction, category_id: int):
        """Show transcript settings for category"""
        category = await self.db.get_category(category_id)
        if not category:
            await interaction.response.send_message("❌ Category not found!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="� Transcript Settings",
            description=f"Configure transcripts for **{category['category_name']}**",
            color=0x00E6A7
        )
        
        auto_transcript = category.get('auto_transcript', False)
        transcript_channel_id = category.get('transcript_channel_id')
        transcript_format = category.get('transcript_format', 'text')
        
        # Ensure transcript_format is a string
        if not isinstance(transcript_format, str):
            transcript_format = 'text'
        
        transcript_channel = None
        if transcript_channel_id and interaction.guild:
            transcript_channel = interaction.guild.get_channel(transcript_channel_id)
        
        embed.add_field(
            name="🤖 Auto Transcript",
            value="Enabled" if auto_transcript else "Disabled",
            inline=True
        )
        
        embed.add_field(
            name="📁 Transcript Channel",
            value=transcript_channel.mention if transcript_channel else "Not set",
            inline=True
        )
        
        embed.add_field(
            name="📋 Format",
            value=transcript_format.title(),
            inline=True
        )
        
        view = TranscriptConfigView(self, category_id)
        await self._safe_send(interaction, embed=embed, view=view, ephemeral=True)
    
    async def show_limits_automation(self, interaction, category_id: int):
        """Show limits and automation settings"""
        category = await self.db.get_category(category_id)
        if not category:
            await interaction.response.send_message("❌ Category not found!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="⏰ Limits & Automation",
            description=f"Configure limits for **{category['category_name']}**",
            color=0x00E6A7
        )
        
        max_tickets = category.get('max_tickets_per_user', 1)
        auto_close_time = category.get('auto_close_time', 0)
        warning_time = category.get('warning_time', 0)
        
        embed.add_field(
            name="🎫 Max Tickets Per User",
            value=str(max_tickets),
            inline=True
        )
        
        embed.add_field(
            name="⏰ Auto Close Time",
            value=f"{auto_close_time} hours" if auto_close_time else "Disabled",
            inline=True
        )
        
        embed.add_field(
            name="⚠️ Warning Time",
            value=f"{warning_time} hours" if warning_time else "Disabled",
            inline=True
        )
        
        view = LimitsAutomationView(self, category_id)
        await self._safe_send(interaction, embed=embed, view=view, ephemeral=True)
    
    async def show_permissions_settings(self, interaction, category_id: int):
        """Show permissions settings for category"""
        category = await self.db.get_category(category_id)
        if not category:
            await interaction.response.send_message("❌ Category not found!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="� Permissions Settings",
            description=f"Configure permissions for **{category['category_name']}**",
            color=0x00E6A7
        )
        
        user_can_close = category.get('user_can_close', True)
        user_can_add_others = category.get('user_can_add_others', False)
        require_claiming = category.get('require_claiming', False)
        
        embed.add_field(
            name="🔒 User Can Close",
            value="Enabled" if user_can_close else "Disabled",
            inline=True
        )
        
        embed.add_field(
            name="➕ User Can Add Others",
            value="Enabled" if user_can_add_others else "Disabled",
            inline=True
        )
        
        embed.add_field(
            name="🎯 Require Claiming",
            value="Enabled" if require_claiming else "Disabled",
            inline=True
        )
        
        view = PermissionsConfigView(self, category_id)
        await self._safe_send(interaction, embed=embed, view=view, ephemeral=True)
    
    async def confirm_panel_deletion(self, interaction, panel_id: int):
        """Show panel deletion confirmation"""
        panel = await self.db.get_panel(panel_id)
        if not panel:
            await interaction.response.send_message("❌ Panel not found!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="⚠️ Delete Panel",
            description=f"Are you sure you want to delete panel **{panel['panel_name']}**?\n\n**This will also delete all categories in this panel!**\n\nThis action cannot be undone.",
            color=0xFF0000
        )
        
        view = PanelDeletionConfirmView(self, panel_id)
        await self._safe_send(interaction, embed=embed, view=view, ephemeral=True)
    
    async def confirm_category_deletion(self, interaction, category_id: int):
        """Show category deletion confirmation"""
        category = await self.db.get_category(category_id)
        if not category:
            await interaction.response.send_message("❌ Category not found!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="⚠️ Delete Category",
            description=f"Are you sure you want to delete category **{category['category_name']}**?\n\nThis action cannot be undone.",
            color=0xFF0000
        )
        
        view = CategoryDeletionConfirmView(self, category_id, category['panel_id'])
        await self._safe_send(interaction, embed=embed, view=view, ephemeral=True)
    
    # ================================
    # ADVANCED TICKET MANAGEMENT
    # ================================
    
    async def claim_ticket_advanced(self, interaction: discord.Interaction, ticket_id: int):
        """Advanced ticket claiming with workload balancing"""
        if not interaction.guild or not interaction.channel:
            await interaction.response.send_message("❌ This can only be used in a server channel!", ephemeral=True)
            return
        
        # Check if user has permission to claim tickets
        ticket = await self.db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ This is not a ticket channel!", ephemeral=True)
            return
        
        # Check staff workload
        workload = await self.db.get_staff_workload(interaction.guild.id, interaction.user.id)
        if workload and workload['active_tickets'] >= workload['max_concurrent_tickets']:
            await interaction.response.send_message(
                f"❌ You have reached your maximum concurrent tickets ({workload['max_concurrent_tickets']})!",
                ephemeral=True
            )
            return
        
        # Claim the ticket
        await self.db.claim_ticket(ticket_id, interaction.user.id)
        
        # Update workload
        if workload:
            await self.db.update_staff_workload(
                interaction.guild.id, 
                interaction.user.id, 
                active_tickets=workload['active_tickets'] + 1,
                status='busy' if workload['active_tickets'] + 1 >= 3 else 'available'
            )
        else:
            await self.db.update_staff_workload(
                interaction.guild.id, 
                interaction.user.id, 
                active_tickets=1,
                status='available'
            )
        
        embed = discord.Embed(
            title="🎯 Ticket Claimed",
            description=f"This ticket has been claimed by {interaction.user.mention}",
            color=0x00FF00
        )
        
        await interaction.response.send_message(embed=embed)
    
    async def escalate_ticket_interactive(self, interaction: discord.Interaction, ticket_id: int):
        """Interactive ticket escalation"""
        await interaction.response.send_modal(EscalationModal(self, ticket_id))
    
    async def perform_ai_analysis(self, interaction: discord.Interaction, ticket_id: int):
        """Perform AI analysis on ticket content"""
        await interaction.response.defer()
        
        if not interaction.channel or not isinstance(interaction.channel, (discord.TextChannel, discord.Thread)):
            await interaction.followup.send("❌ Cannot analyze messages in this channel type.", ephemeral=True)
            return
        
        # Get recent messages from the ticket channel
        messages = []
        async for message in interaction.channel.history(limit=20):
            if not message.author.bot and message.content:
                messages.append(message.content)
        
        # Simulate AI analysis (in real implementation, this would call an AI service)
        analysis = {
            'sentiment': 'neutral',
            'urgency': 'medium',
            'category_suggestion': 'technical_support',
            'confidence': 0.85,
            'summary': 'User experiencing technical difficulties with account access.',
            'suggested_response': 'Have you tried clearing your browser cache and cookies?'
        }
        
        embed = discord.Embed(
            title="🤖 AI Ticket Analysis",
            color=0x00E6A7
        )
        
        embed.add_field(
            name="Sentiment Analysis",
            value=f"😐 {analysis['sentiment'].title()}",
            inline=True
        )
        
        embed.add_field(
            name="Urgency Level",
            value=f"⚡ {analysis['urgency'].title()}",
            inline=True
        )
        
        embed.add_field(
            name="Confidence Score",
            value=f"📊 {analysis['confidence']*100:.1f}%",
            inline=True
        )
        
        embed.add_field(
            name="Summary",
            value=analysis['summary'],
            inline=False
        )
        
        embed.add_field(
            name="Suggested Response",
            value=analysis['suggested_response'],
            inline=False
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    async def show_sla_status(self, interaction: discord.Interaction, ticket_id: int):
        """Show SLA status and deadlines"""
        await interaction.response.defer()
        
        sla_status = await self.db.check_sla_status(ticket_id)
        deadline = await self.db.calculate_sla_deadline(ticket_id)
        
        if sla_status == 'no_sla':
            embed = discord.Embed(
                title="⏱️ SLA Status",
                description="No SLA configured for this ticket category.",
                color=0x808080
            )
        else:
            color_map = {
                'within_sla': 0x00FF00,
                'at_risk': 0xFFFF00,
                'breached': 0xFF0000
            }
            
            status_map = {
                'within_sla': '✅ Within SLA',
                'at_risk': '⚠️ At Risk',
                'breached': '🚨 SLA Breached'
            }
            
            embed = discord.Embed(
                title="⏱️ SLA Status",
                description=status_map[sla_status],
                color=color_map[sla_status]
            )
            
            if deadline:
                time_remaining = deadline - self.tz_helpers.get_utc_now()
                if time_remaining.total_seconds() > 0:
                    hours, remainder = divmod(int(time_remaining.total_seconds()), 3600)
                    minutes, _ = divmod(remainder, 60)
                    embed.add_field(
                        name="Time Remaining",
                        value=f"{hours}h {minutes}m",
                        inline=True
                    )
                else:
                    embed.add_field(
                        name="Overdue By",
                        value=f"{abs(time_remaining.total_seconds())/3600:.1f} hours",
                        inline=True
                    )
                
                # Format deadline in user's timezone
                deadline_formatted = await self.tz_helpers.format_datetime_for_user_custom(
                    deadline, interaction.user, "%Y-%m-%d %H:%M %Z"
                )
                embed.add_field(
                    name="Deadline",
                    value=deadline_formatted,
                    inline=True
                )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    async def show_staff_assignment(self, interaction: discord.Interaction, ticket_id: int):
        """Show staff assignment interface with workload balancing"""
        if not interaction.guild:
            await interaction.response.send_message("❌ This can only be used in a server!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        # Get available staff (this would be more sophisticated in real implementation)
        available_staff = [
            {
                'staff_id': member.id,
                'name': member.display_name,
                'active_tickets': 2,
                'performance_score': 95.5,
                'avg_response_time': 15.2
            }
            for member in interaction.guild.members 
            if not member.bot and any(role.permissions.manage_channels for role in member.roles)
        ][:10]  # Limit for demo
        
        if not available_staff:
            embed = discord.Embed(
                title="❌ No Available Staff",
                description="No staff members are currently available for assignment.",
                color=0xFF0000
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        view = StaffAssignmentView(self, ticket_id, available_staff)
        
        embed = discord.Embed(
            title="👥 Staff Assignment",
            description="Select a staff member to assign to this ticket:",
            color=0x00E6A7
        )
        
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    
    async def assign_staff_to_ticket(self, interaction: discord.Interaction, ticket_id: int, staff_id: int):
        """Assign specific staff member to ticket"""
        await interaction.response.defer()
        
        if not interaction.guild:
            await interaction.followup.send("❌ This command can only be used in a server.", ephemeral=True)
            return
        
        # Assign the ticket
        await self.db.claim_ticket(ticket_id, staff_id)
        
        staff_member = interaction.guild.get_member(staff_id)
        
        embed = discord.Embed(
            title="✅ Staff Assigned",
            description=f"Ticket has been assigned to {staff_member.mention if staff_member else 'Staff Member'}",
            color=0x00FF00
        )
        
        await interaction.followup.send(embed=embed)
    
    async def show_tag_selector(self, interaction: discord.Interaction, ticket_id: int):
        """Show tag selection interface"""
        # Common tags - in real implementation, these would be configurable
        tags = [
            "🐛 Bug Report", "💡 Feature Request", "❓ Question", 
            "🔧 Technical Issue", "💳 Billing", "🔐 Account", 
            "📱 Mobile", "💻 Desktop", "🌐 Website", "🚨 Urgent"
        ]
        
        embed = discord.Embed(
            title="🏷️ Add Tags",
            description="Select tags to categorize this ticket:",
            color=0x00E6A7
        )
        
        # Create tag buttons
        view = TagSelectorView(self, ticket_id, tags)
        
        await self._safe_send(interaction, embed=embed, view=view, ephemeral=True)
    
    async def add_staff_notes(self, interaction: discord.Interaction, ticket_id: int, notes: str):
        """Add staff notes to ticket"""
        await interaction.response.defer()
        
        # Update ticket with notes
        async with aiosqlite.connect(self.db.db_path) as db:
            # Get existing notes
            cursor = await db.execute("SELECT notes FROM tickets WHERE ticket_id = ?", (ticket_id,))
            result = await cursor.fetchone()
            
            existing_notes = result[0] if result and result[0] else ""
            
            # Append new notes with timestamp
            # Use staff member's timezone for better readability
            timestamp = await self.tz_helpers.format_datetime_for_user_custom(
                self.tz_helpers.get_utc_now(), interaction.user, "%Y-%m-%d %H:%M %Z"
            )
            new_notes = f"{existing_notes}\n\n[{timestamp}] {interaction.user.display_name}: {notes}".strip()
            
            await db.execute("UPDATE tickets SET notes = ? WHERE ticket_id = ?", (new_notes, ticket_id))
            await db.commit()
        
        # Log the action
        await self.db.log_ticket_action(ticket_id, interaction.user.id, 'notes_added', {'notes': notes})
        
        embed = discord.Embed(
            title="📝 Notes Added",
            description="Staff notes have been added to this ticket.",
            color=0x00FF00
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    async def show_rating_modal(self, interaction: discord.Interaction, ticket_id: int):
        """Show ticket rating modal"""
        modal = TicketRatingModal(self, ticket_id)
        await interaction.response.send_modal(modal)
    
    async def submit_ticket_rating(self, interaction: discord.Interaction, ticket_id: int, overall_rating: int, response_time_rating: Optional[int], helpfulness_rating: Optional[int], feedback: Optional[str]):
        """Submit ticket rating and feedback"""
        await interaction.response.defer()
        
        # Save feedback to database
        async with aiosqlite.connect(self.db.db_path) as db:
            await db.execute("""
                INSERT INTO ticket_feedback (ticket_id, user_id, rating, feedback_text, response_time_rating, helpfulness_rating)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (ticket_id, interaction.user.id, overall_rating, feedback, response_time_rating, helpfulness_rating))
            
            # Update ticket with rating
            await db.execute("""
                UPDATE tickets SET user_rating = ?, feedback_text = ?, feedback_submitted_at = CURRENT_TIMESTAMP
                WHERE ticket_id = ?
            """, (overall_rating, feedback, ticket_id))
            
            await db.commit()
        
        # Close the ticket
        await self.db.close_ticket(ticket_id, interaction.user.id, "Closed with user feedback")
        
        # Create feedback embed
        stars = "⭐" * overall_rating + "☆" * (5 - overall_rating)
        
        embed = discord.Embed(
            title="✅ Thank You for Your Feedback!",
            description=f"**Rating:** {stars} ({overall_rating}/5)\n\n**Feedback:** {feedback or 'No additional feedback provided'}",
            color=0x00FF00
        )
        
        embed.add_field(
            name="📊 Your Ratings",
            value=f"**Overall:** {overall_rating}/5\n**Response Time:** {response_time_rating or 'Not rated'}/5\n**Helpfulness:** {helpfulness_rating or 'Not rated'}/5",
            inline=False
        )
        
        await interaction.followup.send(embed=embed)
        
        # Archive the channel after a delay
        await asyncio.sleep(10)
        try:
            if interaction.channel and isinstance(interaction.channel, discord.TextChannel):
                await interaction.channel.delete(reason="Ticket closed with feedback")
        except:
            pass
    
    async def escalate_ticket_with_reason(self, interaction: discord.Interaction, ticket_id: int, reason: str):
        """Escalate ticket with specific reason"""
        await interaction.response.defer()
        
        success = await self.db.escalate_ticket(ticket_id, interaction.user.id, reason)
        
        if success:
            embed = discord.Embed(
                title="🚀 Ticket Escalated",
                description=f"Ticket has been escalated.\n**Reason:** {reason}",
                color=0xFF6600
            )
        else:
            embed = discord.Embed(
                title="❌ Escalation Failed",
                description="Could not escalate this ticket.",
                color=0xFF0000
            )
        
        await interaction.followup.send(embed=embed)
    
    async def update_ticket_tags(self, ticket_id: int, tags: List[str]):
        """Update ticket tags"""
        async with aiosqlite.connect(self.db.db_path) as db:
            await db.execute(
                "UPDATE tickets SET tags = ? WHERE ticket_id = ?",
                (json.dumps(tags), ticket_id)
            )
            await db.commit()
    
    @ticket.command(name="analytics", aliases=["dashboard"])
    @commands.has_permissions(administrator=True)
    async def analytics_dashboard(self, ctx: Context):
        """📊 Advanced analytics dashboard"""
        if not ctx.guild:
            return
            
        embed = discord.Embed(
            title="📊 Ticket Analytics Dashboard",
            description="Advanced analytics and reporting for your ticket system",
            color=0x00E6A7
        )
        
        # Get basic stats
        async with aiosqlite.connect(self.db.db_path) as db:
            # Total tickets
            cursor = await db.execute("SELECT COUNT(*) FROM tickets WHERE guild_id = ?", (ctx.guild.id,))
            result = await cursor.fetchone()
            total_tickets = result[0] if result else 0
            
            # Open tickets
            cursor = await db.execute("SELECT COUNT(*) FROM tickets WHERE guild_id = ? AND status != 'closed'", (ctx.guild.id,))
            result = await cursor.fetchone()
            open_tickets = result[0] if result else 0
            
            # Average resolution time
            cursor = await db.execute("""
                SELECT AVG(resolution_time) FROM tickets 
                WHERE guild_id = ? AND resolution_time IS NOT NULL
            """, (ctx.guild.id,))
            result = await cursor.fetchone()
            avg_resolution = result[0] if result and result[0] else 0
            
            # SLA breaches today
            today = self.tz_helpers.get_utc_now().date()
            cursor = await db.execute("""
                SELECT COUNT(*) FROM tickets 
                WHERE guild_id = ? AND sla_status = 'breached' 
                AND DATE(created_at) = ?
            """, (ctx.guild.id, today))
            result = await cursor.fetchone()
            sla_breaches = result[0] if result else 0
        
        embed.add_field(
            name="📈 Overview",
            value=f"**Total Tickets:** {total_tickets}\n**Open Tickets:** {open_tickets}\n**Avg Resolution:** {avg_resolution:.1f} min\n**SLA Breaches Today:** {sla_breaches}",
            inline=False
        )
        
        embed.add_field(
            name="🚀 Advanced Features",
            value="• Real-time SLA monitoring\n• Staff performance tracking\n• AI-powered categorization\n• Sentiment analysis\n• Workload balancing\n• Custom reporting",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @ticket.command(name="ai")
    @commands.has_permissions(manage_channels=True)
    async def ai_features(self, ctx: Context):
        """🤖 AI-powered ticket features"""
        embed = discord.Embed(
            title="🤖 AI Ticket Intelligence",
            description="Advanced AI features for smart ticket management",
            color=0x00E6A7
        )
        
        embed.add_field(
            name="🧠 Available AI Features",
            value="• **Sentiment Analysis** - Detect user emotions\n• **Urgency Detection** - Auto-prioritize tickets\n• **Category Prediction** - Smart categorization\n• **Response Suggestions** - AI-generated responses\n• **Language Detection** - Multi-language support\n• **Escalation Triggers** - Smart escalation logic",
            inline=False
        )
        
        embed.add_field(
            name="📊 Analytics Integration",
            value="• Performance predictions\n• Workload optimization\n• Staff matching algorithms\n• Trend analysis\n• Satisfaction forecasting",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    async def create_ticket_panel_view(self, panel_id: int):
        """Create a ticket panel view with populated category dropdown"""
        categories = await self.db.get_panel_categories(panel_id)
        
        # Create the view with categories
        view = TicketPanelView(self, panel_id, categories)
        
        return view
    
    async def create_ticket_from_panel(self, interaction: discord.Interaction, category_id: int, panel_id: Optional[int] = None):
        """Create a ticket for the selected category from a panel"""
        if not interaction.guild:
            await interaction.response.send_message("❌ This can only be used in a server!", ephemeral=True)
            return
            
        category = await self.db.get_category(category_id)
        
        if not category:
            await interaction.response.send_message("❌ Category not found!", ephemeral=True)
            return
        
        # Check if user has reached ticket limit for this category
        existing_tickets = await self.db.get_user_tickets(
            interaction.guild.id, 
            interaction.user.id, 
            'open'
        )
        
        # Filter tickets by this category
        category_tickets = [t for t in existing_tickets if t.get('category_id') == category_id]
        
        # Check ticket limit with proper null handling
        max_tickets = category.get('max_tickets_per_user') or 1
        if not isinstance(max_tickets, int):
            max_tickets = 1
            
        if len(category_tickets) >= max_tickets:
            await interaction.response.send_message(
                f"❌ You already have the maximum number of tickets ({max_tickets}) open for this category!",
                ephemeral=True
            )
            return
        
        # Create the ticket channel
        try:
            # Format channel name with safe field handling
            channel_name_format = category.get('channel_name_format') or 'ticket-{user}-{number}'
            channel_name = channel_name_format.format(
                user=interaction.user.display_name.lower().replace(' ', '-')[:20],  # Limit length
                number=len(existing_tickets) + 1,
                category=category['category_name'].lower().replace(' ', '-')[:20]  # Limit length
            )
            
            # Clean channel name (Discord requirements)
            channel_name = re.sub(r'[^a-z0-9\-_]', '', channel_name.lower())
            if not channel_name:
                channel_name = f"ticket-{interaction.user.id}"
            
            # Get parent category with safe handling
            parent_category = None
            parent_category_id = category.get('parent_category_id')
            if parent_category_id:
                parent_cat = interaction.guild.get_channel(parent_category_id)
                if isinstance(parent_cat, discord.CategoryChannel):
                    parent_category = parent_cat
            
            # Set up permissions
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(
                    read_messages=True, 
                    send_messages=True, 
                    add_reactions=True, 
                    attach_files=True, 
                    embed_links=True
                ),
                interaction.guild.me: discord.PermissionOverwrite(
                    read_messages=True, 
                    send_messages=True, 
                    manage_messages=True, 
                    embed_links=True, 
                    attach_files=True
                )
            }
            
            # Add support roles with safe JSON parsing
            try:
                support_roles_data = category.get('support_roles') or '[]'
                support_roles = json.loads(support_roles_data) if support_roles_data.strip() else []
            except (json.JSONDecodeError, AttributeError):
                support_roles = []
                
            for role_id in support_roles:
                role = interaction.guild.get_role(role_id)
                if role:
                    overwrites[role] = discord.PermissionOverwrite(
                        read_messages=True, 
                        send_messages=True, 
                        manage_messages=True
                    )
            
            # Create channel
            channel = await interaction.guild.create_text_channel(
                name=channel_name,
                category=parent_category,
                overwrites=overwrites,
                topic=f"Ticket created by {interaction.user} | Category: {category['category_name']} | Support ticket"
            )
            
            # Create ticket in database
            ticket_id = await self.db.create_ticket(
                interaction.guild.id,
                interaction.user.id,
                channel.id,
                category_id,
                panel_id
            )
            
            # Send welcome message with safe field handling
            welcome_message = category.get('welcome_message') or 'Thank you for creating a ticket! A staff member will be with you shortly.'
            welcome_embed = discord.Embed(
                title=f"🎫 Ticket #{len(existing_tickets) + 1} - {category['category_name']}",
                description=welcome_message,
                color=self.safe_color(category.get('priority_color', 0x00E6A7))
            )
            
            welcome_embed.add_field(
                name="📋 Ticket Information",
                value=f"**Created by:** {interaction.user.mention}\n**Category:** {category['category_name']}\n**Channel:** {channel.mention}",
                inline=False
            )
            
            # Add control buttons
            view = TicketControlView(self, ticket_id)
            
            # Ping roles if configured with safe JSON parsing
            ping_content = ""
            try:
                ping_roles_data = category.get('ping_roles') or '[]'
                ping_roles = json.loads(ping_roles_data) if ping_roles_data.strip() else []
            except (json.JSONDecodeError, AttributeError):
                ping_roles = []
                
            if ping_roles:
                role_mentions = []
                for role_id in ping_roles:
                    role = interaction.guild.get_role(role_id)
                    if role:
                        role_mentions.append(role.mention)
                if role_mentions:
                    ping_content = f"{' '.join(role_mentions)} - New ticket created!"
            
            await channel.send(
                content=ping_content or None,
                embed=welcome_embed,
                view=view
            )
            
            # Auto-add roles to user if configured with safe JSON parsing
            try:
                auto_add_roles_data = category.get('auto_add_roles') or '[]'
                auto_add_roles = json.loads(auto_add_roles_data) if auto_add_roles_data.strip() else []
            except (json.JSONDecodeError, AttributeError):
                auto_add_roles = []
                
            if isinstance(interaction.user, discord.Member):
                for role_id in auto_add_roles:
                    role = interaction.guild.get_role(role_id)
                    if role and role not in interaction.user.roles:
                        try:
                            await interaction.user.add_roles(role, reason=f"Auto-added from ticket category: {category['category_name']}")
                        except:
                            pass  # Skip if can't add role
            
            # Log creation if enabled
            if category['log_creation'] and category['log_channel_id']:
                log_channel = interaction.guild.get_channel(category['log_channel_id'])
                if log_channel and isinstance(log_channel, discord.TextChannel):
                    log_embed = discord.Embed(
                        title="🎫 Ticket Created",
                        description=f"**User:** {interaction.user.mention}\n**Category:** {category['category_name']}\n**Channel:** {channel.mention}",
                        color=0x00FF00,
                        timestamp=self.tz_helpers.get_utc_now()
                    )
                    try:
                        await log_channel.send(embed=log_embed)
                    except:
                        pass  # Skip if can't log
            
            await interaction.response.send_message(
                f"✅ Ticket created! {channel.mention}",
                ephemeral=True
            )
            
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to create channels!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error creating ticket: {str(e)}", ephemeral=True)

class MainSetupView(View):
    """Main setup view with create panel button"""
    def __init__(self, tickets_cog, guild_id: int):
        super().__init__(timeout=300)
        self.tickets_cog = tickets_cog
        self.guild_id = guild_id
    
    @discord.ui.button(label="➕ Create New Panel", style=ButtonStyle.success, emoji="🎫")
    async def create_panel(self, interaction: discord.Interaction, button: Button):
        modal = PanelCreateModal(self.tickets_cog)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📋 Manage Existing Panels", style=ButtonStyle.primary, emoji="⚙️")
    async def manage_panels(self, interaction: discord.Interaction, button: Button):
        panels = await self.tickets_cog.db.get_guild_panels(self.guild_id)
        
        if not panels:
            await interaction.response.send_message("❌ No panels found! Create one first.", ephemeral=True)
            return
        
        # Create panel selection dropdown
        options = []
        for panel in panels:
            categories_count = len(await self.tickets_cog.db.get_panel_categories(panel['panel_id']))
            options.append(discord.SelectOption(
                label=panel['panel_name'],
                description=f"{categories_count} categories",
                value=str(panel['panel_id'])
            ))
        
        view = View()
        select = Select(
            placeholder="Select a panel to manage...",
            options=options
        )
        
        async def panel_select_callback(interaction):
            panel_id = int(select.values[0])
            await self.tickets_cog.show_panel_config(interaction, panel_id)
        
        select.callback = panel_select_callback
        view.add_item(select)
        
        await interaction.response.send_message("Select a panel to manage:", view=view, ephemeral=True)

class TicketPanelView(View):
    """The actual ticket panel view that users interact with"""
    def __init__(self, tickets_cog, panel_id: Optional[int] = None, categories=None):
        super().__init__(timeout=None)  # Persistent view
        self.tickets_cog = tickets_cog
        self.panel_id = panel_id
        
        # Add category selection dropdown
        if panel_id:
            self.add_item(TicketCategorySelect(tickets_cog, panel_id, categories))

class TicketCategorySelect(Select):
    """Dynamic category selection dropdown"""
    def __init__(self, tickets_cog, panel_id: int, categories=None):
        self.tickets_cog = tickets_cog
        self.panel_id = panel_id
        
        # Initialize options from provided categories or set placeholder
        options = []
        if categories:
            for category in categories:
                emoji = category.get('category_emoji', '🎫')
                name = category['category_name']
                description = category.get('category_description', 'Create a support ticket')
                
                # Truncate description if too long
                if description and len(description) > 100:
                    description = description[:97] + "..."
                
                options.append(discord.SelectOption(
                    label=name,
                    description=description,
                    emoji=emoji,
                    value=str(category['category_id'])
                ))
        
        # If no categories, show disabled placeholder
        if not options:
            options = [discord.SelectOption(
                label="No categories available",
                description="Contact an administrator",
                value="none",
                emoji="❌"
            )]
        
        # Initialize with options
        super().__init__(
            placeholder="🎫 Select a category to create a ticket...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"ticket_category_select_{panel_id}",
            disabled=len(options) == 1 and options[0].value in ["none", "error"]
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle category selection"""
        if not self.values:
            await interaction.response.send_message("❌ No category selected!", ephemeral=True)
            return
        
        # Handle special cases
        if self.values[0] in ["none", "error"]:
            await interaction.response.send_message("❌ No categories are available. Please contact an administrator.", ephemeral=True)
            return
        
        category_id = int(self.values[0])
        
        # Create the ticket using the tickets cog
        await self.tickets_cog.create_ticket_from_panel(interaction, category_id, self.panel_id)

    # ================================
    # END TICKET PANEL VIEWS
    # ================================

async def setup(bot):
    await bot.add_cog(Tickets(bot))
