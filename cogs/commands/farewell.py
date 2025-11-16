import discord
from discord.ext import commands
from discord.ui import Button, View, Select, Modal, TextInput
import aiosqlite
import asyncio
import json
import re
from utils.Tools import blacklist_check, ignore_check
from utils.dynamic_dropdowns import DynamicChannelSelect, DynamicChannelView, PaginatedChannelView
from utils.timezone_helpers import get_timezone_helpers
from utils.button_manager import ButtonManager, create_button_management_view
from utils.enhanced_button_manager import EnhancedButtonManager, create_enhanced_button_management_view
from utils.button_integration import ButtonIntegrationHelper, EmbedButtonTemplate
from utils.button_database import button_db, save_embed_buttons, load_embed_buttons
from utils.button_config import button_config, setup_welcome_config

from utils.error_helpers import StandardErrorHandler
# Database path
DB_PATH = "db/farewell.db"

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

def get_placeholder_embed():
    """Returns an embed showing available placeholders"""
    embed = discord.Embed(
        title="🏷️ Available Placeholders",
        description="Use these placeholders in your farewell message:",
        color=0x006fb9
    )
    
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
    
    for var, desc in variables.items():
        embed.add_field(name=var, value=desc, inline=False)
    
    embed.set_footer(text="Add placeholders directly in the farewell message or embed fields.")
    return embed

class VariableButton(Button):
    def __init__(self, author):
        super().__init__(label="Variables", emoji="🏷️", style=discord.ButtonStyle.secondary)
        self.author = author

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            await interaction.response.send_message("You cannot interact with this setup.", ephemeral=True)
            return
        
        embed = get_placeholder_embed()
        await interaction.response.send_message(embed=embed, ephemeral=True)

class Farewell(commands.Cog):
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot
        self.tz_helpers = get_timezone_helpers(bot)
        
        # Queue system for handling member leaves (similar to greet system)
        self.leave_queue = {}  # guild_id: [member, member, ...]
        self.processing = set()  # Set of guild_ids currently being processed
        
        # Large server threshold
        self.large_server_threshold = 10000

    async def setup_hook(self):
        """Called when the cog is loaded"""
        await self._create_table()
        
        # Initialize enhanced button system
        try:
            from utils.button_init import initialize_enhanced_button_system
            await initialize_enhanced_button_system()
            print("[FAREWELL] Enhanced button system initialized")
        except Exception as e:
            print(f"[FAREWELL] Error initializing enhanced button system: {e}")

    async def _create_table(self):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
            CREATE TABLE IF NOT EXISTS farewell (
                guild_id INTEGER PRIMARY KEY,
                farewell_type TEXT,
                farewell_message TEXT,
                channel_id INTEGER,
                embed_data TEXT,
                auto_delete_duration INTEGER,
                embed_color INTEGER DEFAULT 0x006fb9,
                button_data TEXT
            )
            """)
            await db.commit()

            # Add button_data column if it doesn't exist
            try:
                await db.execute("ALTER TABLE farewell ADD COLUMN button_data TEXT")
                await db.commit()
            except:
                pass  # Column already exists

    async def _ensure_table_exists(self):
        """Ensure the farewell table exists before any database operation"""
        await self._create_table()
    
    async def safe_format(self, text, placeholders):
        """Safely format text with placeholders, avoiding KeyError"""
        if not text:
            return text
        
        try:
            # Case-insensitive variable replacement
            for placeholder, value in placeholders.items():
                text = re.sub(f"{{{placeholder}}}", str(value), text, flags=re.IGNORECASE)
            return text
        except Exception as e:
            print(f"[DEBUG FAREWELL] Error formatting text: {e}")
            return text

    @commands.hybrid_group(invoke_without_command=True, name="farewell", help="Shows all the farewell commands.")
    @blacklist_check()
    @ignore_check()
    async def farewell(self, ctx: commands.Context):
        if ctx.subcommand_passed is None:
            await ctx.send_help(ctx.command)
            if ctx.command is not None and hasattr(ctx.command, 'reset_cooldown'):
                ctx.command.reset_cooldown(ctx)

    @farewell.command(name="setup", help="Configures a farewell message for members leaving the server.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 6, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def farewell_setup(self, ctx):
        await self._ensure_table_exists()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT * FROM farewell WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()
        
        if row:
            error = discord.Embed(description=f"A farewell message has already been set in {ctx.guild.name}. Use `{ctx.prefix}farewell reset` to reconfigure.", color=0x006fb9)
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
            title="Farewell Message Setup",
            description="Choose the type of farewell message you want to create:",
            color=0x006fb9
        )

        embed.add_field(
            name="🔤 Simple",
            value="Send a plain text farewell message. You can use placeholders to personalize it.\n\n",
            inline=False
        )
        embed.add_field(
            name="📋 Embed",
            value="Send a farewell message in an embed format. You can customize the embed with a title, description, image, etc.",
            inline=False
        )

        embed.set_footer(text="Click the buttons below to choose the farewell message type.", icon_url=self.bot.user.display_avatar.url)
        
        await ctx.send(embed=embed, view=options_view)

    async def simple_setup(self, ctx):
        first = View(timeout=600)
        first.add_item(VariableButton(ctx.author))

        preview_message = await ctx.send("__**Simple Message Setup**__ \nEnter your farewell message here:", view=first)

        try:
            msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=300)
        except:
            return await preview_message.edit(content="⏰ Setup timed out!", view=None)

        farewell_message = msg.content
        await msg.delete()

        # Ask for color
        color_message = await ctx.send("🎨 **Color Setup** (Optional)\nEnter a color for the farewell message embed:\n• Color names: `red`, `blue`, `green`, `purple`, etc.\n• Hex codes: `#FF0000`, `#00FF00`, etc.\n• Type `default` for the default color\n• Type `skip` to use default color")
        
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
            ) if ctx.author.joined_at else "Unknown",
            "user_createdate": await self.tz_helpers.format_datetime_for_user_custom(
                ctx.author.created_at, ctx.author, "%a, %b %d, %Y"
            ),
            "server_name": ctx.guild.name,
            "server_id": ctx.guild.id,
            "server_membercount": ctx.guild.member_count,
            "server_icon": ctx.guild.icon.url if ctx.guild.icon else ""
        }

        preview_text = farewell_message
        for placeholder, value in placeholders.items():
            preview_text = preview_text.replace(f"{{{placeholder}}}", str(value))

        preview_embed = discord.Embed(description=preview_text, color=embed_color)
        preview_embed.set_footer(text="This is a preview of your farewell message")

        setup_view = View(timeout=300)

        async def submit_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You cannot interact with this setup.", ephemeral=True)
                return

            await self._save_farewell_data(ctx.guild.id, "simple", farewell_message, embed_color=embed_color)
            
            success_embed = discord.Embed(
                title="✅ Success",
                description="Farewell message has been successfully set up!",
                color=embed_color
            )
            success_embed.add_field(name="Type", value="Simple Message", inline=True)
            success_embed.add_field(name="Next Step", value=f"Use `{ctx.prefix}farewell channel` to set the farewell channel", inline=False)
            
            await interaction.response.edit_message(embed=success_embed, view=None)

        async def edit_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You cannot interact with this setup.", ephemeral=True)
                return
            await interaction.response.send_message("Please send your new farewell message:", ephemeral=True)

        async def cancel_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You cannot interact with this setup.", ephemeral=True)
                return
            await interaction.response.edit_message(content="❌ Farewell setup cancelled.", embed=None, view=None)

        submit_button = Button(label="Submit", style=discord.ButtonStyle.success)
        submit_button.callback = submit_callback
        setup_view.add_item(submit_button)

        edit_button = Button(label="Edit", style=discord.ButtonStyle.primary)
        edit_button.callback = edit_callback
        setup_view.add_item(edit_button)
        setup_view.add_item(VariableButton(ctx.author))

        cancel_button = Button(emoji="❌", style=discord.ButtonStyle.secondary)
        cancel_button.callback = cancel_callback
        setup_view.add_item(cancel_button)

        try:
            await color_message.delete()
        except:
            pass

        await preview_message.edit(content="**📋 Farewell Message Preview:**", embed=preview_embed, view=setup_view)

    async def embed_setup(self, ctx):
        setup_view = View(timeout=600)
        button_manager = EnhancedButtonManager()  # Initialize enhanced button manager
        
        embed_data = {
            "message": None,
            "title": None,
            "description": None,
            "color": 0x006fb9,
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
            ) if ctx.author.joined_at else "Unknown",
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

        select_menu = Select(
            placeholder="Choose what to customize...",
            options=[
                discord.SelectOption(label="Message Content", value="message", emoji="💬"),
                discord.SelectOption(label="Embed Title", value="title", emoji="📝"),
                discord.SelectOption(label="Embed Description", value="description", emoji="📄"),
                discord.SelectOption(label="Embed Color", value="color", emoji="🎨"),
                discord.SelectOption(label="Image URL", value="image", emoji="🖼️"),
                discord.SelectOption(label="Thumbnail URL", value="thumbnail", emoji="🖼️"),
                discord.SelectOption(label="Footer Text", value="footer", emoji="📋"),
                discord.SelectOption(label="Author Name", value="author", emoji="👤")
            ]
        )

        async def handle_selection(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You cannot interact with this setup.", ephemeral=True)
                return

            selected_option = select_menu.values[0]
            await interaction.response.defer()

            try:
                if selected_option == "message":
                    await ctx.send("Enter the farewell message content:")
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
                    color = validate_color(msg.content)
                    if color:
                        embed_data["color"] = color
                        await ctx.send(f"✅ Color set to: {msg.content}")
                    else:
                        await ctx.send("❌ Invalid color. Use named colors (red, blue, green, etc.) or hex codes (#FF0000 or FF0000).")

                elif selected_option == "image":
                    await ctx.send("Enter the image URL:")
                    msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                    embed_data["image"] = msg.content

                elif selected_option == "thumbnail":
                    await ctx.send("Enter the thumbnail URL:")
                    msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                    embed_data["thumbnail"] = msg.content

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

        select_menu.callback = handle_selection

        async def update_preview():
            content = safe_format(embed_data["message"]) or "Message Content."
            preview_embed = discord.Embed(
                title=safe_format(embed_data["title"]) or "",
                description=safe_format(embed_data["description"]) or "```Customize your farewell embed, take help of variables.```",
                color=discord.Color(embed_data["color"]) if embed_data["color"] else discord.Color(0x2f3136)
            )
            
            if embed_data["footer_text"]:
                preview_embed.set_footer(text=safe_format(embed_data["footer_text"]), icon_url=safe_format(embed_data["footer_icon"]) or None)
            if embed_data["author_name"]:
                preview_embed.set_author(name=safe_format(embed_data["author_name"]), icon_url=safe_format(embed_data["author_icon"]) or None)
            if embed_data["thumbnail"]:
                preview_embed.set_thumbnail(url=safe_format(embed_data["thumbnail"]))
            if embed_data["image"]:
                preview_embed.set_image(url=safe_format(embed_data["image"]))

            # Add button count to the preview
            button_count = len(button_manager.buttons)
            button_info = f"\n**Buttons:** {button_count} linked button{'s' if button_count != 1 else ''}" if button_count > 0 else ""

            await preview_message.edit(content="**Embed Preview:** " + content + button_info, embed=preview_embed, view=setup_view)

        preview_message = await ctx.send("Configuring embed farewell message...")

        select_menu = Select(
            placeholder="Choose what to customize",
            options=[
                discord.SelectOption(label="Message Content", value="message"),
                discord.SelectOption(label="Title", value="title"),
                discord.SelectOption(label="Description", value="description"),
                discord.SelectOption(label="Color", value="color"),
                discord.SelectOption(label="Footer Text", value="footer_text"),
                discord.SelectOption(label="Footer Icon", value="footer_icon"),
                discord.SelectOption(label="Author Name", value="author_name"),
                discord.SelectOption(label="Author Icon", value="author_icon"),
                discord.SelectOption(label="Thumbnail", value="thumbnail"),
                discord.SelectOption(label="Image", value="image")
            ]
        )
        
        select_menu.callback = handle_selection
        setup_view.add_item(select_menu)

        # Add button management view
        button_mgmt_view = create_enhanced_button_management_view(ctx.author.id, button_manager, update_preview, ctx.guild)
        for item in button_mgmt_view.children:
            setup_view.add_item(item)

        async def submit_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You cannot interact with this setup.", ephemeral=True)
                return
            if not any(embed_data[key] for key in ["title", "description"]):
                await interaction.response.send_message("Please provide at least a title or an description before submitting.", ephemeral=True)
                return

            # Save to legacy database for compatibility
            button_data = button_manager.to_dict() if button_manager.buttons else None
            await self._save_farewell_data(ctx.guild.id, "embed", embed_data["message"] or "", json.dumps(embed_data), embed_data["color"] or 0x006fb9, button_data)
            
            # Save to enhanced button database for advanced features
            if button_manager.buttons:
                await save_embed_buttons(ctx.guild.id, "farewell", "main", button_manager)
            
            # Enhanced success message
            button_count = len(button_manager.buttons) if button_manager.buttons else 0
            success_text = "<:feast_tick:1400143469892210753> **Enhanced Farewell Message Configured!**"
            
            if button_count > 0:
                button_counts = button_manager.get_button_count_by_type()
                button_summary = []
                for btn_type, count in button_counts.items():
                    type_name = EnhancedButtonManager.BUTTON_TYPES.get(btn_type, btn_type)
                    button_summary.append(f"{count} {type_name.lower()}")
                success_text += f"\n🎛️ Interactive Buttons: {', '.join(button_summary)}"
            
            await interaction.response.send_message(success_text)

            # Removed disabling items, as not all items support 'disabled'
            await preview_message.edit(view=setup_view)

        submit_button = Button(label="Submit", style=discord.ButtonStyle.success)
        submit_button.callback = submit_callback
        setup_view.add_item(submit_button)
        setup_view.add_item(VariableButton(ctx.author))

        async def cancel_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You cannot interact with this setup.", ephemeral=True)
                return
            await preview_message.delete()
            await interaction.response.send_message("Embed setup cancelled.", ephemeral=True)

        cancel_button = Button(label="Cancel", style=discord.ButtonStyle.danger)
        cancel_button.callback = cancel_callback
        setup_view.add_item(cancel_button)

        await update_preview()

    async def _save_farewell_data(self, guild_id, farewell_type, message, embed_data=None, embed_color=0x006fb9, button_data=None):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
            INSERT OR REPLACE INTO farewell (guild_id, farewell_type, farewell_message, embed_data, embed_color, button_data)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (guild_id, farewell_type, message, embed_data, embed_color, json.dumps(button_data) if button_data else None))
            await db.commit()

    @farewell.command(name="reset", aliases=["disable"], help="Resets and deletes the current farewell configuration for the server.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 6, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def farewell_reset(self, ctx):
        await self._ensure_table_exists()
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT 1 FROM farewell WHERE guild_id = ?", (ctx.guild.id,))
            is_set_up = await cursor.fetchone()

        if not is_set_up: 
            error = discord.Embed(description=f"No farewell message has been set for {ctx.guild.name}! Please set a farewell message first using `{ctx.prefix}farewell setup`", color=0x006fb9)
            error.set_author(name="Farewell is not configured!", icon_url="https://cdn.discordapp.com/emojis/1294218790082711553.png")
            return await ctx.send(embed=error)
            
        embed = discord.Embed(
            title="Are you sure?",
            description="This will remove all farewell configurations & data related to farewell messages for this server!",
            color=0x006fb9
        )

        yes_button = Button(label="Confirm", style=discord.ButtonStyle.danger)
        no_button = Button(label="Cancel", style=discord.ButtonStyle.secondary)

        async def yes_button_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("Only the command author can confirm this action.", ephemeral=True)
                return

            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("DELETE FROM farewell WHERE guild_id = ?", (ctx.guild.id,))
                await db.commit()

            embed.color = discord.Color(0x006fb9)
            embed.title = "✅ Success"
            embed.description = "Farewell message configuration has been successfully reset."
            await interaction.response.edit_message(embed=embed, view=None)

        async def no_button_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("Only the command author can cancel this action.", ephemeral=True)
                return

            embed.color = discord.Color(0x006fb9)
            embed.title = "Cancelled"
            embed.description = "Farewell Reset operation has been cancelled."
            await interaction.response.edit_message(embed=embed, view=None)

        yes_button.callback = yes_button_callback
        no_button.callback = no_button_callback

        view = View()
        view.add_item(yes_button)
        view.add_item(no_button)

        await ctx.send(embed=embed, view=view)

    @farewell.command(name="channel", help="Sets the channel where farewell messages will be sent.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 6, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def farewell_channel(self, ctx):
        await self._ensure_table_exists()
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT 1 FROM farewell WHERE guild_id = ?", (ctx.guild.id,))
            is_set_up = await cursor.fetchone()

        if not is_set_up:
            error = discord.Embed(description=f"No farewell message has been set for {ctx.guild.name}! Please set a farewell message first using `{ctx.prefix}farewell setup`", color=0x006fb9)
            error.set_author(name="Farewell is not configured!", icon_url="https://cdn.discordapp.com/emojis/1294218790082711553.png")
            await ctx.send(embed=error)
            return

        # Create paginated channel selector that shows ALL channels
        async def farewell_channel_callback(interaction, select):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You cannot interact with this setup.", ephemeral=True)
                return

            channel_id = int(select.values[0])
            channel = ctx.guild.get_channel(channel_id)

            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE farewell SET channel_id = ? WHERE guild_id = ?", (channel_id, ctx.guild.id))
                await db.commit()

            success_embed = discord.Embed(
                title="✅ Success",
                description=f"Farewell channel has been set to {channel.mention}",
                color=0x006fb9
            )
            await interaction.response.edit_message(embed=success_embed, view=None)

        view = PaginatedChannelView(
            ctx.guild,
            channel_types=[discord.ChannelType.text],
            exclude_channels=[],
            custom_callback=farewell_channel_callback,
            timeout=300
        )

        total_channels = len(view.all_channels)
        content = "**Select Farewell Channel:**"
        if total_channels > 25:
            content += f"\n*({total_channels} channels available - use ◀️ ▶️ buttons to navigate)*"
        
        await ctx.send(content, view=view)

    @farewell.command(name="test", help="Sends a test farewell message to preview the setup.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 6, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def farewell_test(self, ctx):
        await self._ensure_table_exists()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT farewell_type, farewell_message, channel_id, embed_data, embed_color, button_data FROM farewell WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()

        if row is None:
            error = discord.Embed(description=f"No farewell message has been set for {ctx.guild.name}! Please set a farewell message first using `{ctx.prefix}farewell setup`", color=0x006fb9)
            error.set_author(name="Farewell is not configured!", icon_url="https://cdn.discordapp.com/emojis/1294218790082711553.png")
            await ctx.send(embed=error)
            return

        farewell_type, farewell_message, channel_id, embed_data, embed_color, button_data = row
        farewell_channel = self.bot.get_channel(channel_id) if channel_id else None

        if not farewell_channel:
            error2 = discord.Embed(description=f"Farewell channel not set or invalid. Use `{ctx.prefix}farewell channel` to set one.", color=0x006fb9)
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
            ) if ctx.author.joined_at else "Unknown",
            "user_createdate": await self.tz_helpers.format_datetime_for_user_custom(
                ctx.author.created_at, ctx.author, "%a, %b %d, %Y"
            ),
            "server_name": ctx.guild.name,
            "server_id": ctx.guild.id,
            "server_membercount": ctx.guild.member_count,
            "server_icon": ctx.guild.icon.url if ctx.guild.icon else ""
        }

        # Create buttons view if button data exists
        view = None
        if button_data:
            try:
                buttons = json.loads(button_data)
                if buttons:
                    view = View(timeout=None)
                    for button_info in buttons:
                        button = Button(
                            label=button_info['label'],
                            url=button_info['url'],
                            emoji=button_info.get('emoji'),
                            style=discord.ButtonStyle.link
                        )
                        view.add_item(button)
            except (json.JSONDecodeError, KeyError):
                view = None

        if farewell_type == "simple":
            content = farewell_message
            for placeholder, value in placeholders.items():
                content = content.replace(f"{{{placeholder}}}", str(value))
            
            test_embed = discord.Embed(description=content, color=embed_color or 0x006fb9)
            test_embed.set_footer(text="This is a test farewell message")
            await farewell_channel.send(embed=test_embed, view=view)

        elif farewell_type == "embed":
            embed_info = json.loads(embed_data) if embed_data else {}
            test_embed = discord.Embed(color=embed_color or 0x006fb9)
            
            message_content = farewell_message or ""
            
            if embed_info.get("title"):
                title = embed_info["title"]
                for placeholder, value in placeholders.items():
                    title = title.replace(f"{{{placeholder}}}", str(value))
                test_embed.title = title

            if embed_info.get("description"):
                desc = embed_info["description"]
                for placeholder, value in placeholders.items():
                    desc = desc.replace(f"{{{placeholder}}}", str(value))
                test_embed.description = desc

            if embed_info.get("image"):
                test_embed.set_image(url=embed_info["image"])

            if embed_info.get("thumbnail"):
                test_embed.set_thumbnail(url=embed_info["thumbnail"])

            if embed_info.get("footer"):
                footer = embed_info["footer"]
                for placeholder, value in placeholders.items():
                    footer = footer.replace(f"{{{placeholder}}}", str(value))
                test_embed.set_footer(text=f"{footer} • This is a test")
            else:
                test_embed.set_footer(text="This is a test farewell message")

            if embed_info.get("author"):
                author = embed_info["author"]
                for placeholder, value in placeholders.items():
                    author = author.replace(f"{{{placeholder}}}", str(value))
                test_embed.set_author(name=author)

            if message_content:
                for placeholder, value in placeholders.items():
                    message_content = message_content.replace(f"{{{placeholder}}}", str(value))

            await farewell_channel.send(content=message_content if message_content else None, embed=test_embed, view=view)

        success_embed = discord.Embed(
            title="✅ Test Sent",
            description=f"Test farewell message sent to {farewell_channel.mention}",
            color=0x006fb9
        )
        await ctx.send(embed=success_embed)

    @farewell.command(name="config", help="Shows the current farewell configuration.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 6, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def farewell_config(self, ctx):
        await self._ensure_table_exists()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT farewell_type, channel_id, auto_delete_duration, embed_color FROM farewell WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()

        if row:
            farewell_type, channel_id, auto_delete_duration, embed_color = row
            channel = self.bot.get_channel(channel_id) if channel_id else None
            
            embed = discord.Embed(title="Farewell Configuration", color=embed_color or 0x006fb9)
            embed.add_field(name="Type", value=farewell_type.title(), inline=True)
            embed.add_field(name="Channel", value=channel.mention if channel else "Not Set", inline=True)
            embed.add_field(name="Embed Color", value=f"#{embed_color:06x}" if embed_color else "Default", inline=True)
            
            auto_delete_text = f"{auto_delete_duration} seconds" if auto_delete_duration else "Disabled"
            embed.add_field(name="Auto Delete Duration", value=auto_delete_text, inline=False)
            await ctx.send(embed=embed)
        else:
            error = discord.Embed(
                description=f"No farewell message has been set for {ctx.guild.name}! Please set a farewell message first using `{ctx.prefix}farewell setup`",
                color=0x006fb9
            )
            error.set_author(name="Farewell is not configured!", icon_url="https://cdn.discordapp.com/emojis/1294218790082711553.png")
            await ctx.send(embed=error)

    @farewell.command(name="autodelete", aliases=["autodel"], help="Sets the auto-delete duration for the farewell message.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 6, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def farewell_autodelete(self, ctx, time: str):
        await self._ensure_table_exists()
        
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

        
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
            UPDATE farewell
            SET auto_delete_duration = ?
            WHERE guild_id = ?
            """, (auto_delete_duration, ctx.guild.id))
            await db.commit()

        await ctx.send(f"✅ Auto delete duration has been set to **{auto_delete_duration}** seconds.")

    @farewell.command(name="edit", help="Edits the current farewell message settings for the server.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 6, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def farewell_edit(self, ctx):
        await self._ensure_table_exists()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT farewell_type, farewell_message, embed_data, embed_color FROM farewell WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()

        if not row:
            error = discord.Embed(description=f"No farewell message has been set for {ctx.guild.name}! Please set a farewell message first using `{ctx.prefix}farewell setup`", color=0x006fb9)
            error.set_author(name="Farewell is not configured!", icon_url="https://cdn.discordapp.com/emojis/1294218790082711553.png")
            await ctx.send(embed=error)
            return

        farewell_type, farewell_message, embed_data, embed_color = row

        if farewell_type == "simple":
            await ctx.send("Enter your new farewell message:")
            try:
                msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=300)
                new_message = msg.content
                await msg.delete()

                # Ask for new color
                color_msg = await ctx.send("🎨 Enter a new color (or type 'keep' to keep current color):")
                try:
                    color_response = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=60)
                    color_input = color_response.content.strip()
                    await color_response.delete()
                    
                    if color_input.lower() == 'keep':
                        new_color = embed_color
                    else:
                        new_color = validate_color(color_input)
                except:
                    new_color = embed_color

                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute("UPDATE farewell SET farewell_message = ?, embed_color = ? WHERE guild_id = ?", (new_message, new_color, ctx.guild.id))
                    await db.commit()

                await color_msg.delete()
                await ctx.send("✅ Farewell message updated successfully!")

            except:
                await ctx.send("⏰ Edit timed out!")

        elif farewell_type == "embed":
            embed_info = json.loads(embed_data) if embed_data else {}
            
            edit_options = [
                discord.SelectOption(label="Message Content", value="message", emoji="💬"),
                discord.SelectOption(label="Embed Title", value="title", emoji="📝"),
                discord.SelectOption(label="Embed Description", value="description", emoji="📄"),
                discord.SelectOption(label="Embed Color", value="color", emoji="🎨"),
                discord.SelectOption(label="Image URL", value="image", emoji="🖼️"),
                discord.SelectOption(label="Thumbnail URL", value="thumbnail", emoji="🖼️"),
                discord.SelectOption(label="Footer Text", value="footer", emoji="📋"),
                discord.SelectOption(label="Author Name", value="author", emoji="👤")
            ]

            select = Select(placeholder="Choose what to edit...", options=edit_options)

            async def edit_callback(interaction):
                if interaction.user != ctx.author:
                    await interaction.response.send_message("You cannot interact with this edit.", ephemeral=True)
                    return

                selected = select.values[0]
                await interaction.response.defer()

                try:
                    if selected == "message":
                        await ctx.send("Enter the new farewell message content:")
                        msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                        
                        async with aiosqlite.connect(DB_PATH) as db:
                            await db.execute("UPDATE farewell SET farewell_message = ? WHERE guild_id = ?", (msg.content, ctx.guild.id))
                            await db.commit()

                    elif selected == "color":
                        await ctx.send("🎨 Enter a new color:")
                        msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                        new_color = validate_color(msg.content)
                        
                        async with aiosqlite.connect(DB_PATH) as db:
                            await db.execute("UPDATE farewell SET embed_color = ? WHERE guild_id = ?", (new_color, ctx.guild.id))
                            await db.commit()

                    else:
                        field_prompts = {
                            "title": "Enter the new embed title:",
                            "description": "Enter the new embed description:",
                            "image": "Enter the new image URL:",
                            "thumbnail": "Enter the new thumbnail URL:",
                            "footer": "Enter the new footer text:",
                            "author": "Enter the new author name:"
                        }

                        await ctx.send(field_prompts[selected])
                        msg = await self.bot.wait_for("message", check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
                        
                        embed_info[selected] = msg.content
                        
                        async with aiosqlite.connect(DB_PATH) as db:
                            await db.execute("UPDATE farewell SET embed_data = ? WHERE guild_id = ?", (json.dumps(embed_info), ctx.guild.id))
                            await db.commit()

                    await msg.delete()
                    await ctx.send(f"✅ {selected.title()} updated successfully!")

                except:
                    await ctx.send("⏰ Edit timed out!")

            select.callback = edit_callback
            view = View()
            view.add_item(select)

            await ctx.send("**Edit Farewell Message:**", view=view)

    async def send_farewell_message(self, member, farewell_config, is_large_guild=False, max_retries=3, retry_delay=2):
        """Send farewell message with retry logic and rate limiting"""
        farewell_type, farewell_message, channel_id, embed_data, auto_delete_duration, embed_color, button_data = farewell_config
        
        if not channel_id:
            print(f"[DEBUG FAREWELL] No channel configured for guild {member.guild.id}")
            return
        
        channel = self.bot.get_channel(channel_id)
        if not channel:
            print(f"[DEBUG FAREWELL] Channel {channel_id} not found for guild {member.guild.id}")
            return
        
        # Prepare placeholders
        placeholders = {
            "user": member.mention,
            "user_avatar": member.avatar.url if member.avatar else member.default_avatar.url,
            "user_name": member.name,
            "user_id": member.id,
            "user_nick": member.display_name,
            "user_joindate": await self.tz_helpers.format_datetime_for_guild(
                member.joined_at, member.guild, "%a, %b %d, %Y"
            ) if member.joined_at else "Unknown",
            "user_createdate": await self.tz_helpers.format_datetime_for_guild(
                member.created_at, member.guild, "%a, %b %d, %Y"
            ),
            "server_name": member.guild.name,
            "server_id": member.guild.id,
            "server_membercount": member.guild.member_count - 1,  # Subtract 1 because member hasn't been removed from count yet
            "server_icon": member.guild.icon.url if member.guild.icon else ""
        }
        
        # Create enhanced buttons view if button data exists
        view = None
        if button_data:
            try:
                # Try loading from enhanced button database first
                enhanced_manager = await load_embed_buttons(member.guild.id, "farewell", "main")
                
                if enhanced_manager and enhanced_manager.buttons:
                    # Use enhanced button manager
                    view = enhanced_manager.create_view(member.guild)
                    print(f"[DEBUG FAREWELL] Using enhanced buttons: {len(enhanced_manager.buttons)} buttons")
                else:
                    # Fall back to legacy button data
                    legacy_buttons = json.loads(button_data) if isinstance(button_data, str) else button_data
                    if legacy_buttons:
                        # Migrate legacy buttons to enhanced format
                        enhanced_manager = ButtonIntegrationHelper.create_button_manager_from_data(legacy_buttons)
                        view = enhanced_manager.create_view(member.guild)
                        print(f"[DEBUG FAREWELL] Using migrated legacy buttons: {len(legacy_buttons)} buttons")
                        
            except (json.JSONDecodeError, Exception) as e:
                print(f"[DEBUG FAREWELL] Error creating button view: {e}")
                view = None
        
        # Attempt to send message with retry logic
        for attempt in range(max_retries):
            try:
                message = None
                
                if farewell_type == "simple":
                    content = await self.safe_format(farewell_message, placeholders)
                    farewell_embed = discord.Embed(description=content, color=embed_color or 0x006fb9)
                    message = await channel.send(embed=farewell_embed, view=view)

                elif farewell_type == "embed":
                    embed_info = json.loads(embed_data) if embed_data else {}
                    farewell_embed = discord.Embed(color=embed_color or 0x006fb9)
                    
                    message_content = farewell_message or ""
                    
                    if embed_info.get("title"):
                        title = await self.safe_format(embed_info["title"], placeholders)
                        farewell_embed.title = title

                    if embed_info.get("description"):
                        desc = await self.safe_format(embed_info["description"], placeholders)
                        farewell_embed.description = desc

                    if embed_info.get("image"):
                        farewell_embed.set_image(url=embed_info["image"])

                    if embed_info.get("thumbnail"):
                        farewell_embed.set_thumbnail(url=embed_info["thumbnail"])

                    if embed_info.get("footer"):
                        footer = await self.safe_format(embed_info["footer"], placeholders)
                        farewell_embed.set_footer(text=footer)

                    if embed_info.get("author"):
                        author = await self.safe_format(embed_info["author"], placeholders)
                        farewell_embed.set_author(name=author)

                    if message_content:
                        message_content = await self.safe_format(message_content, placeholders)

                    message = await channel.send(content=message_content if message_content else None, embed=farewell_embed, view=view)

                # Auto-delete if configured
                if auto_delete_duration and message:
                    await message.delete(delay=auto_delete_duration)
                
                print(f"[DEBUG FAREWELL] Successfully sent farewell for {member} in {member.guild.name}")
                return message
                
            except discord.Forbidden:
                print(f"[DEBUG FAREWELL] No permission to send farewell in {channel.name} ({member.guild.name})")
                return None
            except discord.HTTPException as e:
                if e.status == 429:  # Rate limit
                    wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                    print(f"[DEBUG FAREWELL] Rate limited, waiting {wait_time}s before retry {attempt + 1}/{max_retries}")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    print(f"[DEBUG FAREWELL] HTTP error sending farewell: {e}")
                    return None
            except Exception as e:
                print(f"[DEBUG FAREWELL] Unexpected error sending farewell: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    continue
                return None
        
        print(f"[DEBUG FAREWELL] Failed to send farewell after {max_retries} attempts")
        return None

    async def handle_large_guild_leave(self, member):
        """Handle member leave for large servers (>10k members)"""
        print(f"[DEBUG FAREWELL] Handling large guild leave for {member} in {member.guild.name} ({member.guild.member_count} members)")
        
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute("SELECT farewell_type, farewell_message, channel_id, embed_data, auto_delete_duration, embed_color, button_data FROM farewell WHERE guild_id = ?", (member.guild.id,)) as cursor:
                    row = await cursor.fetchone()
            
            if row is None:
                print(f"[DEBUG FAREWELL] No farewell configuration found for large guild {member.guild.id}")
                return
            
            # For large guilds, process immediately without queue
            await self.send_farewell_message(member, row, is_large_guild=True)
            
        except Exception as e:
            print(f"[DEBUG FAREWELL] Error handling large guild leave: {e}")

    async def process_leave_queue(self, guild):
        """Process the queue of members who left"""
        print(f"[DEBUG FAREWELL] Processing leave queue for guild {guild.name} ({guild.id})")
        
        while self.leave_queue.get(guild.id):
            member = self.leave_queue[guild.id].pop(0)
            print(f"[DEBUG FAREWELL] Processing member {member} from leave queue")
            
            try:
                async with aiosqlite.connect(DB_PATH) as db:
                    async with db.execute("SELECT farewell_type, farewell_message, channel_id, embed_data, auto_delete_duration, embed_color, button_data FROM farewell WHERE guild_id = ?", (guild.id,)) as cursor:
                        row = await cursor.fetchone()
                        
                if row is None:
                    print(f"[DEBUG FAREWELL] No farewell configuration found for guild {guild.id}")
                    continue
                
                await self.send_farewell_message(member, row, is_large_guild=False)
                
                # Add delay between processing to avoid rate limits
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"[DEBUG FAREWELL] Error processing {member} in leave queue: {e}")
                continue
        
        # Remove guild from processing set
        if guild.id in self.processing:
            self.processing.remove(guild.id)
        print(f"[DEBUG FAREWELL] Finished processing leave queue for guild {guild.id}")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """Send farewell message when a member leaves"""
        # Filter out bots
        if member.bot:
            return
        
        print(f"[DEBUG FAREWELL] Member {member} left {member.guild.name} ({member.guild.member_count} members)")
        
        # Check if this is a large server
        if member.guild.member_count > self.large_server_threshold:
            await self.handle_large_guild_leave(member)
            return
        
        # For smaller servers, use queue system
        if member.guild.id not in self.leave_queue:
            self.leave_queue[member.guild.id] = []
        
        # Limit queue size to prevent memory issues
        if len(self.leave_queue[member.guild.id]) >= 100:
            print(f"[DEBUG FAREWELL] Leave queue full for guild {member.guild.id}, dropping oldest entry")
            self.leave_queue[member.guild.id].pop(0)
        
        self.leave_queue[member.guild.id].append(member)
        
        # Start processing if not already processing
        if member.guild.id not in self.processing:
            self.processing.add(member.guild.id)
            await self.process_leave_queue(member.guild)

async def setup(bot):
    await bot.add_cog(Farewell(bot))