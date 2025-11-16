import discord
from discord.ext import commands
from discord.ui import View, Select, Button
import aiosqlite
import asyncio
import re
import json
from utils.Tools import *
from utils.dynamic_dropdowns import DynamicChannelSelect, DynamicChannelView, PaginatedChannelView
from utils.timezone_helpers import get_timezone_helpers
from utils.button_manager import ButtonManager, create_button_management_view, QuickButtonsView
from utils.enhanced_button_manager import EnhancedButtonManager, create_enhanced_button_management_view
from utils.button_integration import ButtonIntegrationHelper, EmbedButtonTemplate
from utils.button_database import button_db, save_embed_buttons, load_embed_buttons
from utils.button_config import button_config, setup_welcome_config

from utils.error_helpers import StandardErrorHandler
# Color validation function
def validate_color(color_input):
    """Validate and convert color input to hex integer"""
    if not color_input:
        return 0x006fb9  # Default blue
    
    color_input = color_input.strip().lower()
    
    # Predefined color names
    color_map = {
        "red": 0xFF0000, "green": 0x00FF00, "blue": 0x0000FF,
        "yellow": 0xFFFF00, "orange": 0xFFA500, "purple": 0x800080,
        "pink": 0xFFC0CB, "cyan": 0x00FFFF, "magenta": 0xFF00FF,
        "lime": 0x00FF00, "indigo": 0x4B0082, "violet": 0xEE82EE,
        "brown": 0xA52A2A, "black": 0x000000, "white": 0xFFFFFF,
        "gray": 0x808080, "grey": 0x808080, "gold": 0xFFD700,
        "silver": 0xC0C0C0, "navy": 0x000080, "teal": 0x008080,
        "maroon": 0x800000, "olive": 0x808000, "aqua": 0x00FFFF,
        "fuchsia": 0xFF00FF, "default": 0x006fb9
    }
    
    if color_input in color_map:
        return color_map[color_input]
    
    # Try to parse hex color
    if color_input.startswith('#'):
        color_input = color_input[1:]
    
    if len(color_input) == 6 and all(c in '0123456789abcdef' for c in color_input):
        return int(color_input, 16)
    
    return 0x006fb9  # Default if invalid

class VariableButton(Button):
    def __init__(self, author, row=None):
        super().__init__(label="Variables", style=discord.ButtonStyle.secondary, row=row)
        self.author = author

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            await interaction.response.send_message("Only the command author can use this button.", ephemeral=True)
            return

        variables = {
            "{user}": "Mentions the user (e.g., @UserName).",
            "{user_avatar}": "The user's avatar URL.",
            "{user_name}": "The user's username.",
            "{user_id}": "The user's ID number.",
            "{user_nick}": "The user's nickname in the server.",
            "{user_joindate}": "The user's join date in the server (formatted as Day, Month Day, Year).",
            "{user_createdate}": "The user's account creation date (formatted as Day, Month Day, Year).",
            "{server_name}": "The server's name.",
            "{server_id}": "The server's ID number.",
            "{server_membercount}": "The server's total member count.",
            "{server_icon}": "The server's icon URL."
        }
        

        embed = discord.Embed(
            title="Available Placeholders",
            description="Use these placeholders in your welcome message:",
            color=discord.Color(0x006fb9)
        )

        for var, desc in variables.items():
            embed.add_field(name=var, value=desc, inline=False)

        embed.set_footer(text="Add placeholders directly in the welcome message or embed fields.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

class Welcomer(commands.Cog):
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot
        self.tz_helpers = get_timezone_helpers(bot)
        # Removed loop access from __init__

    async def setup_hook(self):
        """Called when the cog is loaded"""
        await self._create_table()
        
        # Initialize enhanced button system
        try:
            from utils.button_init import initialize_enhanced_button_system
            await initialize_enhanced_button_system()
            print("[WELCOMER] Enhanced button system initialized")
        except Exception as e:
            print(f"[WELCOMER] Error initializing enhanced button system: {e}")

    async def _create_table(self):
        async with aiosqlite.connect("db/welcome.db") as db:
            await db.execute("""
            CREATE TABLE IF NOT EXISTS welcome (
                guild_id INTEGER PRIMARY KEY,
                welcome_type TEXT,
                welcome_message TEXT,
                channel_id INTEGER,
                embed_data TEXT,
                auto_delete_duration INTEGER,
                embed_color INTEGER DEFAULT 0x006fb9,
                button_data TEXT
            )
            """)
            # Add color column if it doesn't exist (for existing databases)
            try:
                await db.execute("ALTER TABLE welcome ADD COLUMN embed_color INTEGER DEFAULT 0x006fb9")
            except:
                pass  # Column already exists
                
            # Add button_data column if it doesn't exist
            try:
                await db.execute("ALTER TABLE welcome ADD COLUMN button_data TEXT")
            except:
                pass  # Column already exists
            await db.commit()

    def validate_color(self, color_input):
        """Validate and convert color input to integer format"""
        if not color_input:
            return None
            
        # Dictionary of named colors to hex values
        named_colors = {
            'red': 0xFF0000, 'green': 0x00FF00, 'blue': 0x0000FF,
            'yellow': 0xFFFF00, 'orange': 0xFFA500, 'purple': 0x800080,
            'pink': 0xFFC0CB, 'cyan': 0x00FFFF, 'magenta': 0xFF00FF,
            'lime': 0x00FF00, 'indigo': 0x4B0082, 'violet': 0x8A2BE2,
            'gold': 0xFFD700, 'silver': 0xC0C0C0, 'black': 0x000000,
            'white': 0xFFFFFF, 'gray': 0x808080, 'grey': 0x808080,
            'brown': 0xA52A2A, 'maroon': 0x800000, 'navy': 0x000080,
            'teal': 0x008080, 'olive': 0x808000, 'aqua': 0x00FFFF,
            'fuchsia': 0xFF00FF, 'coral': 0xFF7F50, 'salmon': 0xFA8072,
            'crimson': 0xDC143C, 'firebrick': 0xB22222, 'darkred': 0x8B0000,
            'lightgreen': 0x90EE90, 'darkgreen': 0x006400, 'forestgreen': 0x228B22,
            'lightblue': 0xADD8E6, 'darkblue': 0x00008B, 'royalblue': 0x4169E1,
            'skyblue': 0x87CEEB, 'steelblue': 0x4682B4, 'turquoise': 0x40E0D0
        }
        
        color_input = color_input.strip().lower()
        
        # Check if it's a named color
        if color_input in named_colors:
            return named_colors[color_input]
        
        # Check if it's a hex color
        hex_color = color_input.lstrip('#')
        if len(hex_color) in [3, 6] and all(c in '0123456789abcdef' for c in hex_color):
            # Convert 3-digit hex to 6-digit
            if len(hex_color) == 3:
                hex_color = ''.join([c*2 for c in hex_color])
            return int(hex_color, 16)
        
        return None

    @commands.hybrid_group(invoke_without_command=True, name="greet", help="Shows all the greet commands.")
    @blacklist_check()
    @ignore_check()
    async def greet(self, ctx: commands.Context):
        if ctx.subcommand_passed is None:
            await ctx.send_help(ctx.command)
            if ctx.command is not None and hasattr(ctx.command, 'reset_cooldown'):
                ctx.command.reset_cooldown(ctx)

    @greet.command(name="setup", help="Configures a welcome message for new members joining the server. ")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 6, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def greet_setup(self, ctx):
        async with aiosqlite.connect("db/welcome.db") as db:
            async with db.execute("SELECT * FROM welcome WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()
        
        if row:
            error = discord.Embed(description=f"A welcome message has already been set in {ctx.guild.name}. Use `{ctx.prefix}greet reset` to reconfigure.", color=0x006fb9)
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
                await self.simple_setup(ctx)
            elif button.custom_id == "embed":
                if interaction.message is not None:
                    await interaction.message.delete()
                await self.embed_setup(ctx)
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

        embed = discord.Embed(
            title="Welcome Message Setup",
            description="Choose the type of welcome message you want to create:",
            color=0x006fb9
        )

        embed.add_field(
            name=" Simple",
            value="Send a plain text welcome message. You can use placeholders to personalize it.\n\n",
            inline=False
        )
        embed.add_field(
            name=" Embed",
            value="Send a welcome message in an embed format. You can customize the embed with a title, description, image, etc.",
            inline=False
        )

        embed.set_footer(text="Click the buttons below to choose the welcome message type.", icon_url=self.bot.user.display_avatar.url)
        

        await ctx.send(embed=embed, view=options_view)

    async def simple_setup(self, ctx):
        first = View(timeout=600)
        first.add_item(VariableButton(ctx.author))

        preview_message = await ctx.send("__**Simple Message Setup**__ \nEnter your welcome message here:", view=first)

        try:
            msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=300)
        except:
            return await preview_message.edit(content="⏰ Setup timed out!", view=None)

        welcome_message = msg.content
        await msg.delete()

        # Ask for color
        color_message = await ctx.send("🎨 **Color Setup** (Optional)\nEnter a color for the welcome message embed:\n• Color names: `red`, `blue`, `green`, `purple`, etc.\n• Hex codes: `#FF0000`, `#00FF00`, etc.\n• Type `default` for the default color\n• Type `skip` to use default color")
        
        try:
            color_msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=60)
            color_input = color_msg.content.strip()
            await color_msg.delete()
        except:
            color_input = "default"

        embed_color = validate_color(color_input) if color_input.lower() not in ['skip', ''] else 0x006fb9

        # Preview
        placeholders = {
            "user": ctx.author.mention,
            "user_avatar": ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url,
            "user_name": ctx.author.name,
            "user_id": ctx.author.id,
            "user_nick": ctx.author.display_name,
            "user_joindate": await self.tz_helpers.format_datetime_for_user_custom(
                ctx.author.joined_at, ctx.author, "%a, %b %d, %Y"
            ),
            "user_createdate": await self.tz_helpers.format_datetime_for_user_custom(
                ctx.author.created_at, ctx.author, "%a, %b %d, %Y"
            ),
            "server_name": ctx.guild.name,
            "server_id": ctx.guild.id,
            "server_membercount": ctx.guild.member_count,
            "server_icon": ctx.guild.icon.url if ctx.guild.icon else ""
        }

        preview_text = welcome_message
        for placeholder, value in placeholders.items():
            preview_text = preview_text.replace(f"{{{placeholder}}}", str(value))

        preview_embed = discord.Embed(description=preview_text, color=embed_color)
        preview_embed.set_footer(text="This is a preview of your welcome message")

        setup_view = View(timeout=300)

        async def submit_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You cannot interact with this setup.", ephemeral=True)
                return

            await self._save_welcome_data(ctx.guild.id, "simple", welcome_message, embed_color=embed_color)
            
            success_embed = discord.Embed(
                title="✅ Success",
                description="Welcome message has been successfully set up!",
                color=embed_color
            )
            success_embed.add_field(name="Type", value="Simple Message", inline=True)
            success_embed.add_field(name="Next Step", value=f"Use `{ctx.prefix}greet channel` to set the welcome channel", inline=False)
            
            await interaction.response.edit_message(embed=success_embed, view=None)

        async def edit_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You cannot interact with this setup.", ephemeral=True)
                return
            await interaction.response.send_message("Please send your new welcome message:", ephemeral=True)

        async def cancel_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You cannot interact with this setup.", ephemeral=True)
                return
            await interaction.response.edit_message(content="❌ Welcome setup cancelled.", embed=None, view=None)

        submit_button = Button(label="Submit", style=discord.ButtonStyle.success)
        submit_button.callback = submit_callback
        setup_view.add_item(submit_button)

        edit_button = Button(label="Edit", style=discord.ButtonStyle.primary)
        edit_button.callback = edit_callback
        setup_view.add_item(edit_button)
        setup_view.add_item(VariableButton(ctx.author))

        cancel_button = Button(label="Cancel", style=discord.ButtonStyle.secondary)
        cancel_button.callback = cancel_callback
        setup_view.add_item(cancel_button)

        try:
            await color_message.delete()
        except:
            pass

        await preview_message.edit(content="**📋 Welcome Message Preview:**", embed=preview_embed, view=setup_view)

    
    async def _save_welcome_data(self, guild_id, welcome_type, message, embed_data=None, embed_color=0x006fb9, button_data=None):
        async with aiosqlite.connect("db/welcome.db") as db:
            await db.execute("""
            INSERT OR REPLACE INTO welcome (guild_id, welcome_type, welcome_message, embed_data, embed_color, button_data)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (guild_id, welcome_type, message, json.dumps(embed_data) if embed_data else None, embed_color, json.dumps(button_data) if button_data else None))
            await db.commit()

    


    async def embed_setup(self, ctx):
        setup_view = View(timeout=600)
        # Initialize enhanced button manager with welcome templates
        button_manager = EnhancedButtonManager()
        
        # Setup welcome-specific configuration
        setup_welcome_config()
        
        embed_data = {
            "message": None,
            "title": None,
            "description": None,
            "color": 0x006fb9,  # Default to int, can be changed to any int color value
            "footer_text": None,
            "footer_icon": None,
            "author_name": None,
            "author_icon": None,
            "thumbnail": None,
            "image": None,
        }

        placeholders = {
            "user": ctx.author.mention,
            "user_avatar": ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url,
            "user_name": ctx.author.name,
            "user_id": ctx.author.id,
            "user_nick": ctx.author.display_name,
            "user_joindate": await self.tz_helpers.format_datetime_for_user_custom(
                ctx.author.joined_at, ctx.author, "%a, %b %d, %Y"
            ),
            "user_createdate": await self.tz_helpers.format_datetime_for_user_custom(
                ctx.author.created_at, ctx.author, "%a, %b %d, %Y"
            ),
            "server_name": ctx.guild.name,
            "server_id": ctx.guild.id,
            "server_membercount": ctx.guild.member_count,
            "server_icon": ctx.guild.icon.url if ctx.guild.icon else "https://cdn.discordapp.com/embed/avatars/0.png",
            "timestamp": discord.utils.format_dt(ctx.message.created_at)
        }

        def safe_format(text):
            placeholders_lower = {k.lower(): v for k, v in placeholders.items()}  

            def replace_var(match):
                var_name = match.group(1).lower()
                return str(placeholders_lower.get(var_name, f"{{{var_name}}}"))

            return re.sub(r"\{(\w+)\}", replace_var, text or "")
            

        async def update_preview():
            content = safe_format(embed_data["message"]) or "*No message content set*"
            
            # Validate and limit embed fields to Discord's limits
            title = safe_format(embed_data["title"]) or ""
            if len(title) > 256:
                title = title[:253] + "..."
                
            description = safe_format(embed_data["description"]) or "```📝 Customize your welcome embed using the dropdown menu below.\n💡 Use the Variables button to see available placeholders.```"
            if len(description) > 4096:
                description = description[:4093] + "..."
            
            # Validate color value
            try:
                color = discord.Color(embed_data["color"]) if embed_data["color"] else discord.Color(0x006fb9)
            except (ValueError, TypeError):
                color = discord.Color(0x006fb9)  # Default fallback color
            
            embed = discord.Embed(
                title=title,
                description=description,
                color=color
            )

            # Helper function to validate URLs
            def is_valid_url(url):
                if not url:
                    return False
                try:
                    return url.startswith(('http://', 'https://')) and len(url) <= 2048
                except:
                    return False

            # Apply embed settings with URL validation
            if embed_data["footer_text"]:
                footer_text = safe_format(embed_data["footer_text"])
                if len(footer_text) > 2048:
                    footer_text = footer_text[:2045] + "..."
                footer_icon = safe_format(embed_data["footer_icon"]) if is_valid_url(safe_format(embed_data["footer_icon"])) else None
                embed.set_footer(text=footer_text, icon_url=footer_icon)
                
            if embed_data["author_name"]:
                author_name = safe_format(embed_data["author_name"])
                if len(author_name) > 256:
                    author_name = author_name[:253] + "..."
                author_icon = safe_format(embed_data["author_icon"]) if is_valid_url(safe_format(embed_data["author_icon"])) else None
                embed.set_author(name=author_name, icon_url=author_icon)
                
            if embed_data["thumbnail"] and is_valid_url(safe_format(embed_data["thumbnail"])):
                embed.set_thumbnail(url=safe_format(embed_data["thumbnail"]))
                
            if embed_data["image"] and is_valid_url(safe_format(embed_data["image"])):
                embed.set_image(url=safe_format(embed_data["image"]))

            # Create a professional preview header with enhanced button info
            button_count = len(button_manager.buttons)
            button_info = ""
            
            if button_count > 0:
                button_counts = button_manager.get_button_count_by_type()
                button_parts = []
                for btn_type, count in button_counts.items():
                    type_emoji = {'link': '🔗', 'role': '🎭', 'channel': '📍', 'message': '💬', 'action': '⚡'}
                    emoji = type_emoji.get(btn_type, '🔘')
                    button_parts.append(f"{emoji}{count}")
                button_info = f"**🎛️ Interactive Buttons:** {' • '.join(button_parts)} (Total: {button_count})"
            else:
                button_info = "**🎛️ Interactive Buttons:** None added yet"
            
            try:
                await preview_message.edit(embed=embed, view=setup_view)
            except discord.HTTPException as e:
                # If embed is invalid, send a simple error message without view to avoid further issues
                error_embed = discord.Embed(
                    title="❌ Embed Error",
                    description=f"There was an issue with your configuration: {str(e)[:100]}...\nPlease check your URLs, text lengths, and emojis.",
                    color=0xff0000
                )
                try:
                    await preview_message.edit(embeds=[error_embed], view=None)
                except:
                    # If even that fails, send a new message
                    await ctx.send(embed=error_embed, ephemeral=True)

        # Create initial setup message
        setup_embed = discord.Embed(
            title="Welcome Message Setup",
            description="Setting up your custom welcome message with embed...",
            color=0x2F3136
        )
        
        preview_message = await ctx.send(embed=setup_embed)

        async def handle_selection(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You cannot interact with this setup.", ephemeral=True)
                return

            selected_option = select_menu.values[0]
            await interaction.response.defer()

            try:
                if selected_option == "message":
                    await ctx.send("Enter the welcome message content:")
                    msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                    embed_data["message"] = msg.content

                elif selected_option == "title":
                    await ctx.send("Enter the embed title:")
                    msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                    embed_data["title"] = msg.content

                elif selected_option == "description":
                    await ctx.send("Enter the embed description:")
                    msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                    embed_data["description"] = msg.content

                elif selected_option == "color":
                    await ctx.send("Enter a color (named color like 'red', 'blue' or hex code like '#3498db'):")
                    msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                    color = self.validate_color(msg.content)
                    if color:
                        embed_data["color"] = color
                        await ctx.send(f"✅ Color set to: {msg.content}")
                    else:
                        await ctx.send("❌ Invalid color. Use named colors (red, blue, green, etc.) or hex codes (#FF0000 or FF0000).")

                elif selected_option in ["footer_text", "footer_icon", "author_name", "author_icon", "thumbnail", "image"]:
                    await ctx.send(f"Enter the URL or text for {selected_option.replace('_', ' ')}:")
                    msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                    url_or_text = msg.content
                    if selected_option in ["footer_icon", "author_icon", "thumbnail", "image"]:
                        if url_or_text.startswith("http") or url_or_text in ["{user_avatar}", "{server_icon}"]:
                            embed_data[selected_option] = url_or_text
                        else:
                            await ctx.send("Invalid URL. Please enter a valid image URL or a supported placeholder ({user_avatar} or {server_icon}).")
                    else:
                        embed_data[selected_option] = url_or_text

                await update_preview()
                await interaction.followup.send(f"{selected_option.capitalize()} updated.", ephemeral=True)
            except asyncio.TimeoutError:
                await ctx.send("You took too long to respond. Please try again.")
            except Exception as e:
                await ctx.send(f"An error occurred: {e}")

        # Create a clean, professional interface
        select_menu = Select(
            placeholder="🎨 Customize Embed Components",
            row=0,
            options=[
                discord.SelectOption(label="💬 Message Content", value="message", description="Set the text above the embed"),
                discord.SelectOption(label="📝 Title", value="title", description="Main heading of the embed"),
                discord.SelectOption(label="📄 Description", value="description", description="Main content of the embed"),
                discord.SelectOption(label="🎨 Color", value="color", description="Border color of the embed"),
                discord.SelectOption(label="📋 Footer Text", value="footer_text", description="Small text at the bottom"),
                discord.SelectOption(label="🖼️ Footer Icon", value="footer_icon", description="Small icon in footer"),
                discord.SelectOption(label="👤 Author Name", value="author_name", description="Name at the top"),
                discord.SelectOption(label="👤 Author Icon", value="author_icon", description="Icon next to author"),
                discord.SelectOption(label="🖼️ Thumbnail", value="thumbnail", description="Small image on the right"),
                discord.SelectOption(label="🖼️ Large Image", value="image", description="Large image below content")
            ]
        )
        select_menu.callback = handle_selection
        setup_view.add_item(select_menu)

        # Enhanced Button Management Row
        add_button = Button(
            label="Manage Buttons", 
            style=discord.ButtonStyle.secondary,
            row=1
        )
        
        async def add_button_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("❌ Only the command author can manage buttons.", ephemeral=True)
                return
            
            # Use enhanced button management view with all button types
            enhanced_view = create_enhanced_button_management_view(
                ctx.author.id, button_manager, update_preview, ctx.guild
            )
            
            embed = discord.Embed(
                title="Welcome Button Manager",
                description="Add interactive buttons to your welcome message:\n\n"
                           "**Link Buttons** - Discord servers, websites\n"
                           "**Role Buttons** - Auto-assign member roles\n"
                           "**Channel Buttons** - Navigate to important channels\n"
                           "**Message Buttons** - Send helpful information\n"
                           "**Action Buttons** - Custom welcome actions",
                color=0x2F3136
            )
            
            # Add quick templates section
            template_manager = EmbedButtonTemplate.create_welcome_buttons(ctx.guild)
            if template_manager.buttons:
                template_preview = template_manager.get_buttons_preview()
                embed.add_field(
                    name="🚀 Quick Welcome Template Available",
                    value=f"```\n{template_preview}\n```\nUse the button manager to add these or create custom buttons!",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, view=enhanced_view, ephemeral=True)
        
        add_button.callback = add_button_callback
        setup_view.add_item(add_button)

        view_buttons = Button(
            label="View Buttons",
            style=discord.ButtonStyle.secondary,
            row=1
        )
        
        async def view_buttons_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("❌ Only the command author can view buttons.", ephemeral=True)
                return
            
            if not button_manager.buttons:
                await interaction.response.send_message("No buttons added yet. Use **Manage Buttons** to create some!", ephemeral=True)
                return
            
            # Use enhanced button preview
            preview_embed = ButtonIntegrationHelper.get_button_preview_embed(
                button_manager, "Current Welcome Buttons"
            )
            await interaction.response.send_message(embed=preview_embed, ephemeral=True)
        
        view_buttons.callback = view_buttons_callback
        setup_view.add_item(view_buttons)

        clear_buttons = Button(
            label="Clear All Buttons",
            style=discord.ButtonStyle.secondary,
            row=2
        )
        
        async def clear_buttons_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("❌ Only the command author can clear buttons.", ephemeral=True)
                return
            
            if not button_manager.buttons:
                await interaction.response.send_message("📝 No buttons to clear!", ephemeral=True)
                return
            
            # Show confirmation with button type breakdown
            counts = button_manager.get_button_count_by_type()
            count_text = []
            for btn_type, count in counts.items():
                type_name = EnhancedButtonManager.BUTTON_TYPES.get(btn_type, btn_type)
                count_text.append(f"• {type_name}: {count}")
            
            class ConfirmClearView(View):
                def __init__(self):
                    super().__init__(timeout=60)
                
                @discord.ui.button(label="✅ Confirm Clear", style=discord.ButtonStyle.danger)
                async def confirm_clear(self, clear_interaction, button):
                    button_manager.clear_buttons()
                    await clear_interaction.response.send_message("✅ All buttons cleared!", ephemeral=True)
                    await update_preview()
                
                @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
                async def cancel_clear(self, cancel_interaction, button):
                    await cancel_interaction.response.send_message("❌ Clear cancelled.", ephemeral=True)
            
            confirm_embed = discord.Embed(
                title="Clear All Buttons",
                description=f"Are you sure you want to clear **{len(button_manager.buttons)}** buttons?\n\n" + "\n".join(count_text),
                color=0x2F3136
            )
            
            await interaction.response.send_message(embed=confirm_embed, view=ConfirmClearView(), ephemeral=True)
        
        clear_buttons.callback = clear_buttons_callback
        setup_view.add_item(clear_buttons)

        # Variables helper button
        variables_btn = Button(
            label="Variables",
            style=discord.ButtonStyle.secondary,
            row=1
        )
        
        async def variables_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("❌ Only the command author can view variables.", ephemeral=True)
                return

            variables = {
                "{user}": "Mentions the user (e.g., @UserName)",
                "{user_avatar}": "The user's avatar URL",
                "{user_name}": "The user's username",
                "{user_id}": "The user's ID number",
                "{user_nick}": "The user's nickname in the server",
                "{user_joindate}": "When the user joined (Day, Month Day, Year)",
                "{user_createdate}": "When the user created their account",
                "{server_name}": "The server's name",
                "{server_id}": "The server's ID number",
                "{server_membercount}": "Total member count",
                "{server_icon}": "The server's icon URL"
            }

            embed = discord.Embed(
                title="📋 Available Variables",
                description="Copy and paste these variables into your welcome message:",
                color=0x006fb9
            )

            # Split variables into chunks for better display
            var_text = ""
            for var, desc in variables.items():
                var_text += f"**`{var}`** - {desc}\n"

            embed.add_field(name="🔧 How to use:", value=var_text, inline=False)
            embed.set_footer(text="💡 These variables will be replaced with actual values when someone joins")

            await interaction.response.send_message(embed=embed, ephemeral=True)
        
        variables_btn.callback = variables_callback
        setup_view.add_item(variables_btn)

        # Action buttons row - Professional finish
        submit_button = Button(
            label="Save", 
            style=discord.ButtonStyle.secondary,
            row=2
        )

        async def submit_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("❌ Only the command author can save the setup.", ephemeral=True)
                return
            if not any(embed_data[key] for key in ["title", "description"]):
                await interaction.response.send_message("⚠️ Please provide at least a **title** or **description** before saving.", ephemeral=True)
                return

            # Save to legacy database for compatibility
            button_data = button_manager.to_dict() if button_manager.buttons else None
            await self._save_welcome_data(ctx.guild.id, "embed", embed_data["message"] or "", embed_data, embed_color=embed_data["color"] or 0x006fb9, button_data=button_data)
            
            # Save to enhanced button database for advanced features
            if button_manager.buttons:
                await save_embed_buttons(ctx.guild.id, "welcome", "main", button_manager)
            
            # Success message with detailed summary
            button_count = len(button_manager.buttons) if button_manager.buttons else 0
            summary_text = f"✅ **Enhanced Welcome Message Configured!**\n\n"
            summary_text += f"📝 **Components:** {len([k for k, v in embed_data.items() if v and k != 'color'])} embed fields\n"
            
            if button_count > 0:
                # Show button type breakdown
                button_counts = button_manager.get_button_count_by_type()
                button_summary = []
                for btn_type, count in button_counts.items():
                    type_emoji = {'link': '🔗', 'role': '🎭', 'channel': '📍', 'message': '💬', 'action': '⚡'}
                    emoji = type_emoji.get(btn_type, '🔘')
                    type_name = EnhancedButtonManager.BUTTON_TYPES.get(btn_type, btn_type)
                    button_summary.append(f"{emoji} {count} {type_name.lower()}")
                
                summary_text += f"🎛️ **Interactive Buttons:** {', '.join(button_summary)}\n"
            
            summary_text += f"🎨 **Color:** Custom embed styling\n\n"
            summary_text += "*New members will now see this enhanced welcome experience when they join!*"
            
            success_embed = discord.Embed(
                title="🎉 Welcome Setup Complete",
                description=summary_text,
                color=0x00ff00
            )
            
            await interaction.response.send_message(embed=success_embed)
            await preview_message.edit(view=None)  # Remove all buttons after saving

        submit_button.callback = submit_callback
        setup_view.add_item(submit_button)

        cancel_button = Button(
            label="Cancel", 
            style=discord.ButtonStyle.secondary,
            row=2
        )

        async def cancel_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("❌ Only the command author can cancel setup.", ephemeral=True)
                return
            
            cancel_embed = discord.Embed(
                title="Setup Cancelled",
                description="Welcome message setup has been cancelled. No changes were saved.",
                color=0x2F3136
            )
            
            await preview_message.delete()
            await interaction.response.send_message(embed=cancel_embed, ephemeral=True)

        cancel_button.callback = cancel_callback
        setup_view.add_item(cancel_button)

        # Create initial embed with view immediately
        content = safe_format(embed_data["message"]) or "*No message content set*"
        
        # Validate and create embed with proper error handling
        title = safe_format(embed_data["title"]) or ""
        if len(title) > 256:
            title = title[:253] + "..."
            
        description = safe_format(embed_data["description"]) or "```📝 Customize your welcome embed using the dropdown menu below.\n💡 Use the Variables button to see available placeholders.```"
        if len(description) > 4096:
            description = description[:4093] + "..."
        
        # Validate color value
        try:
            color = discord.Color(embed_data["color"]) if embed_data["color"] else discord.Color(0x006fb9)
        except (ValueError, TypeError):
            color = discord.Color(0x006fb9)
        
        embed = discord.Embed(
            title=title,
            description=description,
            color=color
        )

        # Helper function to validate URLs
        def is_valid_url(url):
            if not url:
                return False
            try:
                return url.startswith(('http://', 'https://')) and len(url) <= 2048
            except:
                return False

        # Apply embed settings with URL validation
        if embed_data["footer_text"]:
            footer_text = safe_format(embed_data["footer_text"])
            if len(footer_text) > 2048:
                footer_text = footer_text[:2045] + "..."
            footer_icon = safe_format(embed_data["footer_icon"]) if is_valid_url(safe_format(embed_data["footer_icon"])) else None
            embed.set_footer(text=footer_text, icon_url=footer_icon)
            
        if embed_data["author_name"]:
            author_name = safe_format(embed_data["author_name"])
            if len(author_name) > 256:
                author_name = author_name[:253] + "..."
            author_icon = safe_format(embed_data["author_icon"]) if is_valid_url(safe_format(embed_data["author_icon"])) else None
            embed.set_author(name=author_name, icon_url=author_icon)
            
        if embed_data["thumbnail"] and is_valid_url(safe_format(embed_data["thumbnail"])):
            embed.set_thumbnail(url=safe_format(embed_data["thumbnail"]))
            
        if embed_data["image"] and is_valid_url(safe_format(embed_data["image"])):
            embed.set_image(url=safe_format(embed_data["image"]))

        # Edit the preview message to show the embed and view with error handling
        try:
            await preview_message.edit(embed=embed, view=setup_view)
        except discord.HTTPException as e:
            # If embed is still invalid, send a simple error message without view to avoid further issues
            error_embed = discord.Embed(
                title="❌ Embed Error",
                description=f"There was an issue with your embed configuration: {str(e)[:100]}...\nPlease check your URLs, text lengths, and emojis.",
                color=0xff0000
            )
            try:
                await preview_message.edit(embeds=[error_embed], view=None)
            except:
                # If even that fails, send a new message
                await ctx.send(embed=error_embed, ephemeral=True)

    

    @greet.command(name="reset", aliases=["disable"], help="Resets and deletes the current welcome configuration for the server.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 6, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def greet_reset(self, ctx):
        async with aiosqlite.connect("db/welcome.db") as db:
            cursor = await db.execute("SELECT 1 FROM welcome WHERE guild_id = ?", (ctx.guild.id,))
            is_set_up = await cursor.fetchone()

        if not is_set_up: 
            error = discord.Embed(description=f"No welcome message has been set for {ctx.guild.name}! Please set a welcome message first using `{ctx.prefix}greet setup`", color=0x006fb9)
            error.set_author(name="Greet is not configured!", icon_url="https://cdn.discordapp.com/emojis/1294218790082711553.png")
            return await ctx.send(embed=error)
            
        embed = discord.Embed(
            title="Are you sure?",
            description="This will remove all welcome configurations & data related to welcome messages for this server!",
            color=0x006fb9
        )

        yes_button = Button(label="Confirm", style=discord.ButtonStyle.danger)
        no_button = Button(label="Cancel", style=discord.ButtonStyle.secondary)

        async def yes_button_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("Only the command author can confirm this action.", ephemeral=True)
                return

            async with aiosqlite.connect("db/welcome.db") as db:
                await db.execute("DELETE FROM welcome WHERE guild_id = ?", (ctx.guild.id,))
                await db.commit()

            embed.color = discord.Color(0x006fb9)
            embed.title = "<:feast_tick:1400143469892210753> Success"
            embed.description = "Welcome message configuration has been successfully reset."
            await interaction.message.edit(embed=embed, view=None)

        async def no_button_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("Only the command author can cancel this action.", ephemeral=True)
                return

            embed.color = discord.Color(0x006fb9)
            embed.title = "Cancelled"
            embed.description = "Greet Reset operation has been cancelled."
            await interaction.message.edit(embed=embed, view=None)

        yes_button.callback = yes_button_callback
        no_button.callback = no_button_callback

        view = View()
        view.add_item(yes_button)
        view.add_item(no_button)

        await ctx.send(embed=embed, view=view)
        

    @greet.command(name="channel", help="Sets the channel where welcome messages will be sent.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 6, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def greet_channel(self, ctx):
        async with aiosqlite.connect("db/welcome.db") as db:
            async with db.execute("SELECT welcome_type, channel_id FROM welcome WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                result = await cursor.fetchone()
                welcome_message = result[0] if result else None
                welcome_channel = ctx.guild.get_channel(result[1]) if result and result[1] else None

        if not welcome_message:
            error = discord.Embed(description=f"No welcome message has been set for {ctx.guild.name}! Please set a welcome message first using `{ctx.prefix}greet setup`", color=0x006fb9)
            error.set_author(name="Greet is not configured!", icon_url="https://cdn.discordapp.com/emojis/1294218790082711553.png")
            await ctx.send(embed=error)
            return

        # Create paginated channel selector that shows ALL channels
        async def welcome_channel_callback(interaction, select):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You are not authorized to set the welcome channel.", ephemeral=True)
                return

            selected_channel_id = int(select.values[0])
            selected_channel = ctx.guild.get_channel(selected_channel_id)

            async with aiosqlite.connect("db/welcome.db") as db:
                await db.execute("UPDATE welcome SET channel_id = ? WHERE guild_id = ?", (selected_channel_id, ctx.guild.id))
                await db.commit()

            embed = discord.Embed(
                title=f"Welcome Channel for {ctx.guild.name}",
                description=f"Current Welcome Channel: {selected_channel.mention}",
                color=0x006fb9
            )
            embed.set_footer(text="✅ Welcome channel has been updated!")
            
            await interaction.response.edit_message(embed=embed, view=None)
            await ctx.send(f"<:feast_tick:1400143469892210753> Welcome channel has been set to {selected_channel.mention}")

        view = PaginatedChannelView(
            ctx.guild,
            channel_types=[discord.ChannelType.text],
            exclude_channels=[],
            custom_callback=welcome_channel_callback,
            timeout=300
        )

        total_channels = len(view.all_channels)
        
        embed = discord.Embed(
            title=f"Welcome Channel for {ctx.guild.name}",
            description=f"Current Welcome Channel: {welcome_channel.mention if welcome_channel else 'None'}",
            color=0x006fb9
        )
        
        footer_text = "Use the dropdown menu to select a channel."
        if total_channels > 25:
            footer_text += f" ({total_channels} channels - use ◀️ ▶️ buttons to navigate)"
        embed.set_footer(text=footer_text)

        await ctx.send(embed=embed, view=view)



    @greet.command(name="test", help="Sends a test welcome message to preview the setup.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 6, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def greet_test(self, ctx):
        async with aiosqlite.connect("db/welcome.db") as db:
            async with db.execute("SELECT welcome_type, welcome_message, channel_id, embed_data, embed_color FROM welcome WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()

        if row is None:
            error = discord.Embed(description=f"No welcome message has been set for {ctx.guild.name}! Please set a welcome message first using `{ctx.prefix}greet setup`", color=0x006fb9)
            error.set_author(name="Greet is not configured!", icon_url="https://cdn.discordapp.com/emojis/1294218790082711553.png")
            await ctx.send(embed=error)
            return

        welcome_type, welcome_message, channel_id, embed_data, embed_color = row
        welcome_channel = self.bot.get_channel(channel_id)

        if not welcome_channel:
            error2 = discord.Embed(description=f"Welcome channel not set or invalid. Use `{ctx.prefix}greet channel` to set one.", color=0x006fb9)
            error2.set_author(name="Channel not set", icon_url="https://cdn.discordapp.com/emojis/1294218790082711553.png")
            await ctx.send(embed=error2)
            return

        placeholders = {
            "user": ctx.author.mention,
            "user_avatar": ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url,
            "user_name": ctx.author.name,
            "user_id": ctx.author.id,
            "user_nick": ctx.author.display_name,
            "user_joindate": await self.tz_helpers.format_datetime_for_user_custom(
                ctx.author.joined_at, ctx.author, "%a, %b %d, %Y"
            ),
            "user_createdate": await self.tz_helpers.format_datetime_for_user_custom(
                ctx.author.created_at, ctx.author, "%a, %b %d, %Y"
            ),
            "server_name": ctx.guild.name,
            "server_id": ctx.guild.id,
            "server_membercount": ctx.guild.member_count,
            "server_icon": ctx.guild.icon.url if ctx.guild.icon else "https://cdn.discordapp.com/embed/avatars/0.png",
            "timestamp": discord.utils.format_dt(ctx.message.created_at)
        }

        def safe_format(text):
            placeholders_lower = {k.lower(): v for k, v in placeholders.items()}  

            def replace_var(match):
                var_name = match.group(1).lower()  
                return str(placeholders_lower.get(var_name, f"{{{var_name}}}"))

            return re.sub(r"\{(\w+)\}", replace_var, text or "")
            

        if welcome_type == "simple" and welcome_message:
            await welcome_channel.send(safe_format(welcome_message))

        elif welcome_type == "embed" and embed_data:
            try:
                embed_info = json.loads(embed_data) 
                color_value = embed_info.get("color", embed_color)  # Use stored color from database as fallback

                # Use the color from the database if available, otherwise fallback to embed_info color
                if embed_color:
                    embed_color_final = discord.Color(embed_color)
                elif color_value and isinstance(color_value, str) and color_value.startswith("#"):
                    embed_color_final = discord.Color(int(color_value.lstrip("#"), 16))
                elif isinstance(color_value, int): 
                    embed_color_final = discord.Color(color_value)
                else:
                    embed_color_final = discord.Color(0x2f3136)

            except (ValueError, SyntaxError, json.JSONDecodeError):
                await ctx.send("Invalid embed data format. Please reconfigure.")
                return

            content = safe_format(embed_info.get("message", "")) or None
            embed = discord.Embed(
                title=safe_format(embed_info.get("title", "")),
                description=safe_format(embed_info.get("description", "")),
                color=embed_color_final
            )
            embed.timestamp = self.tz_helpers.get_utc_now()


            if embed_info.get("footer_text"):
                embed.set_footer(
                    text=safe_format(embed_info["footer_text"]),
                    icon_url=safe_format(embed_info.get("footer_icon", ""))
                )
            if embed_info.get("author_name"):
                embed.set_author(
                    name=safe_format(embed_info["author_name"]),
                    icon_url=safe_format(embed_info.get("author_icon", ""))
                )
            if embed_info.get("thumbnail"):
                embed.set_thumbnail(url=safe_format(embed_info["thumbnail"]))
            if embed_info.get("image"):
                embed.set_image(url=safe_format(embed_info["image"]))

            await welcome_channel.send(content=content, embed=embed)



    @greet.command(name="config", help="Shows the current welcome configuration.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 6, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def greet_config(self, ctx):
        async with aiosqlite.connect("db/welcome.db") as db:
            async with db.execute("SELECT guild_id, welcome_type, welcome_message, channel_id, embed_data, auto_delete_duration, embed_color FROM welcome WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()

        if row:
            _, welcome_type, welcome_message, channel_id, embed_data, auto_delete_duration, embed_color = row
            response_type = "Simple" if welcome_type == "simple" else "Embed"

            embed = discord.Embed(
                title=f"Greet Configuration for {ctx.guild.name}",
                color=0x006fb9
            )

            embed.add_field(name="Response Type", value=response_type, inline=False)
            
            # Display embed color if set
            if embed_color:
                color_hex = f"#{embed_color:06x}" if isinstance(embed_color, int) else embed_color
                embed.add_field(name="Embed Color", value=color_hex, inline=False)

            if welcome_type == "simple":
                details = f"Message Content: {welcome_message or 'None'}"
                embed.add_field(name="Details", value=details[:1024], inline=False)
            else:
                embed_details = json.loads(embed_data) if embed_data else {}
                formatted_embed_data = "\n".join(
                    f"{key.replace('_', ' ').title()}: {value or 'None'}" for key, value in embed_details.items()
                ) or "None"

                for i, chunk in enumerate([formatted_embed_data[i:i+1024] for i in range(0, len(formatted_embed_data), 1024)]):
                    embed.add_field(name=f"Embed Data Part {i+1}", value=chunk, inline=False)

            greet_channel = self.bot.get_channel(channel_id)
            channel_display = greet_channel.mention if greet_channel else "None"
            auto_delete_duration = f"{auto_delete_duration} seconds" if auto_delete_duration else "None"

            embed.add_field(name="Greet Channel", value=channel_display, inline=False)
            embed.add_field(name="Auto Delete Duration", value=auto_delete_duration, inline=False)
            await ctx.send(embed=embed)
        else:
            error = discord.Embed(
                description=f"No welcome message has been set for {ctx.guild.name}! Please set a welcome message first using `{ctx.prefix}greet setup`",
                color=0x006fb9
            )
            error.set_author(name="Greet is not configured!", icon_url="https://cdn.discordapp.com/emojis/1294218790082711553.png")
            await ctx.send(embed=error)


    @greet.command(name="autodelete", aliases=["autodel"], help="Sets the auto-delete duration for the welcome message.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 6, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def greet_autodelete(self, ctx, time: str):
        
        if time.endswith("s"):
            seconds = int(time[:-1])
            if 3 <= seconds <= 300:
                auto_delete_duration = seconds
            else:
                await ctx.send("Auto delete time should be between 3 seconds and 300 seconds.")
                return
        elif time.endswith("m"):
            minutes = int(time[:-1])
            if 1 <= minutes <= 5:
                auto_delete_duration = minutes * 60  
            else:
                await ctx.send("Auto delete time should be between 1 minute and 5 minutes.")
                return
        else:
            await ctx.send("Invalid time format. Please use 's' for seconds and 'm' for minutes.")
            return

        
        async with aiosqlite.connect("db/welcome.db") as db:
            await db.execute("""
            UPDATE welcome
            SET auto_delete_duration = ?
            WHERE guild_id = ?
            """, (auto_delete_duration, ctx.guild.id))
            await db.commit()

        await ctx.send(f"<:Ztick:1222750301233090600> Auto delete duration has been set to **{auto_delete_duration}** seconds.")



    @greet.command(name="edit", help="Edits the current welcome message settings for the server.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 6, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def greet_edit(self, ctx):
        async with aiosqlite.connect("db/welcome.db") as db:
            async with db.execute("SELECT welcome_type, welcome_message, embed_data FROM welcome WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()

        if row is None:
            error = discord.Embed(description=f"No welcome message has been set for {ctx.guild.name}! Please set a welcome message first using `{ctx.prefix}greet setup`", color=0x006fb9)
            error.set_author(name="Greet is not configured!", icon_url="https://cdn.discordapp.com/emojis/1294218790082711553.png")
            await ctx.send(embed=error)
            return

        welcome_type, welcome_message, embed_data = row

        cancel_flag = False  

        if welcome_type == "simple":
            embed = discord.Embed(
                title="Edit Welcome Message",
                description=f"**Response Type:** Simple\n**Message Content:** {welcome_message or 'None'}",
                color=0x006fb9
            )
            edit_button = Button(label="Edit", style=discord.ButtonStyle.primary)
            cancel_button = Button(label="Cancel", style=discord.ButtonStyle.danger)

            async def cancel_button_callback(interaction):
                nonlocal cancel_flag
                if interaction.user != ctx.author:
                    await interaction.response.send_message("You are not authorized to cancel the setup.", ephemeral=True)
                    return
                await interaction.response.send_message("Setup has been canceled.", ephemeral=True)
                cancel_flag = True  
                view.clear_items()  
                await interaction.message.edit(embed=embed, view=view)

            cancel_button.callback = cancel_button_callback

            async def edit_button_callback(interaction):
                if interaction.user != ctx.author:
                    await interaction.response.send_message("You are not authorized to edit the welcome message.", ephemeral=True)
                    return

                await interaction.response.send_message("Please provide the new welcome message:", ephemeral=True)
                try:
                    new_message = await self.bot.wait_for(
                        "message",
                        check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
                        timeout=600
                    )
                    if cancel_flag:  
                        await ctx.send("Setup was canceled. No changes were made.")
                        return
                    await new_message.delete()
                    async with aiosqlite.connect("db/welcome.db") as db:
                        await db.execute("UPDATE welcome SET welcome_message = ? WHERE guild_id = ?", (new_message.content, ctx.guild.id))
                        await db.commit()

                    embed.description = f"**Response Type:** Simple\n**Message Content:** {new_message.content}"
                    edit_button.disabled = True
                    cancel_button.disabled = True
                    await interaction.message.edit(embed=embed, view=view)
                    await ctx.send("Welcome message has been successfully updated.")
                except asyncio.TimeoutError:
                    await ctx.send("You took too long to respond.")
                except Exception as e:
                    await ctx.send(f"An error occurred: {e}")

            edit_button.callback = edit_button_callback
            view = View()
            view.add_item(edit_button)
            view.add_item(VariableButton(ctx.author))
            view.add_item(cancel_button)
            
            await ctx.send(embed=embed, view=view)

        elif welcome_type == "embed":
            embed_data_json = json.loads(embed_data) if embed_data else {}
            formatted_embed_data = "\n".join(
                f"{key.replace('_', ' ').title()}: {value or 'None'}" for key, value in embed_data_json.items()
            ) or "None"
            embed = discord.Embed(
                title="Edit Welcome Message",
                description=f"**Response Type:** Embed\n**Embed Data:**\n```{formatted_embed_data}```",
                color=0x006fb9
            )

            select_menu = Select(
                placeholder="Select an embed field to edit",
                options=[
                    discord.SelectOption(label=field.replace('_', ' ').title(), value=field)
                    for field in embed_data_json.keys()
                ]
            )

            cancel_button = Button(label="Cancel", style=discord.ButtonStyle.danger)

            async def cancel_button_callback(interaction):
                nonlocal cancel_flag
                if interaction.user != ctx.author:
                    await interaction.response.send_message("You are not authorized to cancel the setup.", ephemeral=True)
                    return
                await interaction.response.send_message("Setup has been canceled.", ephemeral=True)
                cancel_flag = True  
                view.clear_items()  
                await interaction.message.edit(embed=embed, view=view)

            cancel_button.callback = cancel_button_callback

            async def select_callback(interaction):
                nonlocal cancel_flag
                if interaction.user != ctx.author:
                    await interaction.response.send_message("You are not authorized to edit this embed.", ephemeral=True)
                    return

                selected_option = select_menu.values[0]
                await interaction.response.defer()

                while not cancel_flag:  
                    try:
                        if selected_option == "message":
                            await ctx.send("Enter the welcome message content:")
                            msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                            embed_data_json["message"] = msg.content

                        elif selected_option == "title":
                            await ctx.send("Enter the embed title:")
                            msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                            embed_data_json["title"] = msg.content

                        elif selected_option == "description":
                            await ctx.send("Enter the embed description:")
                            msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                            embed_data_json["description"] = msg.content

                        elif selected_option == "color":
                            await ctx.send("Enter a color (named color like 'red', 'blue' or hex code like '#3498db'):")
                            msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                            color = self.validate_color(msg.content)
                            if color:
                                embed_data_json["color"] = color
                                await ctx.send(f"✅ Color set to: {msg.content}")
                            else:
                                await ctx.send("❌ Invalid color. Use named colors (red, blue, green, etc.) or hex codes (#FF0000 or FF0000).")
                                continue

                        elif selected_option in ["footer_text", "footer_icon", "author_name", "author_icon", "thumbnail", "image"]:
                            await ctx.send(f"Enter the URL or text for {selected_option.replace('_', ' ')}:")
                            msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                            url_or_text = msg.content
                            if selected_option in ["footer_icon", "author_icon", "thumbnail", "image"]:
                                if url_or_text.startswith("http") or url_or_text in ["{user_avatar}", "{server_icon}"]:
                                    embed_data_json[selected_option] = url_or_text
                                else:
                                    await ctx.send("Invalid URL. Please enter a valid image URL or a supported placeholder ({user_avatar} or {server_icon}).")
                                    continue  
                            else:
                                embed_data_json[selected_option] = url_or_text

                        async with aiosqlite.connect("db/welcome.db") as db:
                            await db.execute("UPDATE welcome SET embed_data = ? WHERE guild_id = ?", (json.dumps(embed_data_json), ctx.guild.id))
                            await db.commit()

                        embed.description = f"**Response Type:** Embed\n**Embed Data:**\n```{json.dumps(embed_data_json, indent=4)}```"
                        await interaction.message.edit(embed=embed, view=None)
                        await ctx.send("Embed data has been successfully updated.")
                        break 
                    except asyncio.TimeoutError:
                        await ctx.send("You took too long to respond.")
                        break
                    except Exception as e:
                        await ctx.send(f"An error occurred: {e}")
                        break

            select_menu.callback = select_callback
            view = View()
            view.add_item(select_menu)
            view.add_item(VariableButton(ctx.author))
            view.add_item(cancel_button)
            
            await ctx.send(embed=embed, view=view)


