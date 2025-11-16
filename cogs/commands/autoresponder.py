import discord
from discord.ext import commands
import aiosqlite
import os
import json
from utils.Tools import *
from utils.error_helpers import StandardErrorHandler

DB_PATH = "db/autoresponder.db"

class AutoResponder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()

    async def setup_hook(self):
        await self.initialize_db()

    async def initialize_db(self):
        if not os.path.exists(os.path.dirname(DB_PATH)):
            os.makedirs(os.path.dirname(DB_PATH))
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS autoresponses (
                    guild_id INTEGER,
                    name TEXT,
                    message TEXT,
                    response_type TEXT DEFAULT 'text',
                    embed_data TEXT,
                    PRIMARY KEY (guild_id, name)
                )
            ''')
            
            # Add new columns to existing table if they don't exist
            try:
                await db.execute("ALTER TABLE autoresponses ADD COLUMN response_type TEXT DEFAULT 'text'")
            except:
                pass  # Column already exists
                
            try:
                await db.execute("ALTER TABLE autoresponses ADD COLUMN embed_data TEXT")
            except:
                pass  # Column already exists
                
            try:
                await db.execute("ALTER TABLE autoresponses ADD COLUMN trigger_mode TEXT DEFAULT 'word'")
            except:
                pass  # Column already exists
                
            await db.commit()

    @commands.group(name="autoresponder", invoke_without_command=True, aliases=['ar'], help="Manage autoresponders in the server.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def _ar(self, ctx):
        if ctx.subcommand_passed is None:
            await ctx.send_help(ctx.command)
            ctx.command.reset_cooldown(ctx)

    @_ar.command(name="create", aliases=["add"], help="Create autoresponder. Single words (word mode), \"phrases\" (phrase mode), or ^full^ (exact match mode)")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def _create(self, ctx, *, args):
        # Parse arguments to handle quoted triggers
        import shlex
        try:
            parsed_args = shlex.split(args)
        except ValueError:
            return await ctx.reply(embed=discord.Embed(
                title="<:feast_cross:1400143488695144609> Error!",
                description="Invalid format. Use proper quoting:\n"
                           "🔸 `ar create word response` (word mode)\n"
                           "🔸 `ar create \"phrase here\" response` (phrase mode)\n"
                           "🔸 `ar create ^exact message^ response` (full match mode)",
                color=0x006fb9
            ))
        
        if len(parsed_args) < 2:
            return await ctx.reply(embed=discord.Embed(
                title="<:feast_cross:1400143488695144609> Error!",
                description="**Three trigger modes:**\n"
                           "🔸 **Single word:** `ar create poop That's gross!` (full word only)\n"
                           "🔸 **Phrase:** `ar create \"demon slayer\" Amazing anime!` (matches in sentences)\n"
                           "🔸 **Full message:** `ar create ^hello^ Hi there!` (exact message match only)",
                color=0x006fb9
            ))
        
        name = parsed_args[0]
        message = " ".join(parsed_args[1:])
        
        # Determine trigger mode based on syntax
        trigger_mode = "word"  # default
        clean_name = name
        
        if name.startswith('^') and name.endswith('^') and len(name) > 2:
            # Full message mode: ^text^
            trigger_mode = "full"
            clean_name = name[1:-1]  # Remove ^ markers
        elif ' ' in name:
            # Phrase mode: "text with spaces"
            trigger_mode = "phrase"
            clean_name = name
        
        name_lower = clean_name.lower()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT COUNT(*) FROM autoresponses WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()
                count = row[0] if row is not None else 0
                if count >= 20:
                    return await ctx.reply(embed=discord.Embed(
                        title="<:feast_cross:1400143488695144609> Error!",
                        description=f"You can't add more than 20 autoresponses in {ctx.guild.name}",
                        color=0x006fb9
                    ))

            async with db.execute("SELECT 1 FROM autoresponses WHERE guild_id = ? AND LOWER(name) = ?", (ctx.guild.id, name_lower)) as cursor:
                if await cursor.fetchone():
                    return await ctx.reply(embed=discord.Embed(
                        title="<:feast_cross:1400143488695144609> Error!",
                        description=f"The autoresponse with the name `{name}` already exists in {ctx.guild.name}",
                        color=0x006fb9
                    ))

            await db.execute("INSERT INTO autoresponses (guild_id, name, message, response_type, trigger_mode) VALUES (?, ?, ?, ?, ?)", (ctx.guild.id, clean_name.lower(), message, 'text', trigger_mode))
            await db.commit()
            
            # Create success message with mode explanation
            mode_text = {
                "word": "🔸 **Word mode** - triggers only on full word matches",
                "phrase": "🔸 **Phrase mode** - triggers when phrase appears in sentences", 
                "full": "🔸 **Full message mode** - triggers only on exact message match"
            }
            
            await ctx.reply(embed=discord.Embed(
                title="<:feast_tick:1400143469892210753> Success",
                description=f"Created autoresponder `{clean_name}` in {ctx.guild.name}\n{mode_text[trigger_mode]}",
                color=0x006fb9
            ))

    @_ar.command(name="createembed", aliases=["addembed", "embed"], help="Create a new embed autoresponder with interactive builder.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def _create_embed(self, ctx, name, *, description=None):
        """Create an embed autoresponder with interactive builder"""
        
        # Determine trigger mode based on syntax
        trigger_mode = "word"  # default
        clean_name = name
        
        if name.startswith('^') and name.endswith('^') and len(name) > 2:
            # Full message mode: ^text^
            trigger_mode = "full"
            clean_name = name[1:-1]  # Remove ^ markers
        elif ' ' in name:
            # Phrase mode: "text with spaces"
            trigger_mode = "phrase"
            clean_name = name
        
        name_lower = clean_name.lower()
        
        # Check limits
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT COUNT(*) FROM autoresponses WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()
                count = row[0] if row is not None else 0
                if count >= 20:
                    return await ctx.reply(embed=discord.Embed(
                        title="<:feast_cross:1400143488695144609> Error!",
                        description=f"You can't add more than 20 autoresponses in {ctx.guild.name}",
                        color=0x006fb9
                    ))

            # Check if name exists
            async with db.execute("SELECT 1 FROM autoresponses WHERE guild_id = ? AND LOWER(name) = ?", (ctx.guild.id, name_lower)) as cursor:
                if await cursor.fetchone():
                    return await ctx.reply(embed=discord.Embed(
                        title="<:feast_cross:1400143488695144609> Error!",
                        description=f"The autoresponse with the name `{name}` already exists in {ctx.guild.name}",
                        color=0x006fb9
                    ))

        # Start embed builder
        embed_data = {
            "title": "",
            "description": description or "",
            "color": 0x006fb9,
            "footer": "",
            "author": "",
            "thumbnail": "",
            "image": "",
            "fields": []
        }
        
        await self.embed_builder(ctx, clean_name, embed_data, trigger_mode, is_edit=False)

    async def embed_builder(self, ctx, name, embed_data, trigger_mode="word", is_edit=False):
        """Interactive embed builder matching the style of other embed builders"""
        
        class EmbedFieldModal(discord.ui.Modal):
            def __init__(self, title, field_name, current_value="", max_length=1024, placeholder=None):
                super().__init__(title=title)
                self.field_name = field_name
                self.value = None
                
                self.text_input = discord.ui.TextInput(
                    label=field_name.title(),
                    default=current_value,
                    max_length=max_length,
                    placeholder=placeholder or f"Enter {field_name}...",
                    required=False,
                    style=discord.TextStyle.long if max_length > 100 else discord.TextStyle.short
                )
                self.add_item(self.text_input)
            
            async def on_submit(self, interaction: discord.Interaction):
                self.value = self.text_input.value
                await interaction.response.defer()
                self.stop()

        class AddFieldModal(discord.ui.Modal):
            def __init__(self):
                super().__init__(title="Add Embed Field")
                self.field_data = None
                
                self.name_input = discord.ui.TextInput(
                    label="Field Name",
                    placeholder="Enter field name...",
                    max_length=256,
                    required=True
                )
                self.add_item(self.name_input)
                
                self.value_input = discord.ui.TextInput(
                    label="Field Value",
                    placeholder="Enter field value...",
                    max_length=1024,
                    required=True,
                    style=discord.TextStyle.long
                )
                self.add_item(self.value_input)
                
                self.inline_input = discord.ui.TextInput(
                    label="Inline (yes/no)",
                    placeholder="yes or no",
                    max_length=3,
                    required=False,
                    default="no"
                )
                self.add_item(self.inline_input)
            
            async def on_submit(self, interaction: discord.Interaction):
                inline = self.inline_input.value.lower() in ['yes', 'y', 'true', '1']
                self.field_data = {
                    "name": self.name_input.value,
                    "value": self.value_input.value,
                    "inline": inline
                }
                await interaction.response.defer()
                self.stop()
        
        def create_preview_embed():
            embed = discord.Embed(
                title=embed_data["title"] or None,
                description=embed_data["description"] or None,
                color=embed_data["color"]
            )
            
            if embed_data["footer"]:
                embed.set_footer(text=embed_data["footer"])
            if embed_data["author"]:
                embed.set_author(name=embed_data["author"])
            if embed_data["thumbnail"]:
                embed.set_thumbnail(url=embed_data["thumbnail"])
            if embed_data["image"]:
                embed.set_image(url=embed_data["image"])
                
            for field in embed_data["fields"]:
                embed.add_field(
                    name=field["name"],
                    value=field["value"],
                    inline=field.get("inline", False)
                )
            
            return embed
        
        setup_view = discord.ui.View(timeout=600)
        
        # Create initial combined preview message with dropdown
        builder_embed = discord.Embed(
            title="🔧 Embed Builder",
            description=f"Building embed autoresponder: `{name}`\n\nUse the dropdown menu below to customize your embed:",
            color=0x006fb9
        )
        
        # Add immediate preview fields to show what the embed will look like
        preview_embed = create_preview_embed()
        builder_embed.add_field(
            name="📋 Current Preview",
            value=f"**Title:** {preview_embed.title or '*Not set*'}\n"
                  f"**Description:** {preview_embed.description[:50] + '...' if preview_embed.description and len(preview_embed.description) > 50 else preview_embed.description or '*Not set*'}\n"
                  f"**Color:** {hex(preview_embed.color.value) if preview_embed.color else '*Default*'}\n"
                  f"**Fields:** {len(embed_data['fields'])} field{'s' if len(embed_data['fields']) != 1 else ''}",
            inline=False
        )
        
        preview_message = await ctx.send(embed=builder_embed)
        
        async def update_preview():
            """Update the preview embed with immediate preview in same message"""
            updated_embed = create_preview_embed()
            
            # Create builder embed with immediate preview
            builder_embed = discord.Embed(
                title="🔧 Embed Builder",
                description=f"Building embed autoresponder: `{name}`\n\nUse the dropdown menu below to customize your embed:",
                color=0x006fb9
            )
            
            # Add live preview fields
            builder_embed.add_field(
                name="📋 Current Preview",
                value=f"**Title:** {updated_embed.title or '*Not set*'}\n"
                      f"**Description:** {updated_embed.description[:50] + '...' if updated_embed.description and len(updated_embed.description) > 50 else updated_embed.description or '*Not set*'}\n"
                      f"**Color:** {hex(updated_embed.color.value) if updated_embed.color else '*Default*'}\n"
                      f"**Fields:** {len(embed_data['fields'])} field{'s' if len(embed_data['fields']) != 1 else ''}",
                inline=False
            )
            
            # Show actual embed preview if there's content
            if updated_embed.title or updated_embed.description:
                builder_embed.add_field(
                    name="✨ Live Preview",
                    value="*This is how your autoresponder embed will look:*",
                    inline=False
                )
            
            await preview_message.edit(embed=builder_embed, view=setup_view)
            
            # Send separate full preview if there's content to show
            if updated_embed.title or updated_embed.description:
                try:
                    # Try to edit existing preview or send new one
                    if hasattr(update_preview, 'preview_msg') and update_preview.preview_msg:
                        await update_preview.preview_msg.edit(embed=updated_embed)
                    else:
                        update_preview.preview_msg = await ctx.send("**Preview:**", embed=updated_embed)
                except:
                    # Create new preview message
                    update_preview.preview_msg = await ctx.send("**Preview:**", embed=updated_embed)
        
        async def handle_selection(interaction: discord.Interaction):
            """Handle dropdown selection"""
            if interaction.user != ctx.author:
                await interaction.response.send_message("Only the command author can use this.", ephemeral=True)
                return
            
            # Get selected value from select menu
            selected = select_menu.values[0]
            
            if selected == "title":
                modal = EmbedFieldModal("Edit Title", "title", embed_data["title"], max_length=256)
                await interaction.response.send_modal(modal)
                await modal.wait()
                if modal.value is not None:
                    embed_data["title"] = modal.value
                    await update_preview()
                    
            elif selected == "description":
                modal = EmbedFieldModal("Edit Description", "description", embed_data["description"], max_length=4000)
                await interaction.response.send_modal(modal)
                await modal.wait()
                if modal.value is not None:
                    embed_data["description"] = modal.value
                    await update_preview()
                    
            elif selected == "color":
                current_color = hex(embed_data["color"]).replace("0x", "#")
                modal = EmbedFieldModal("Edit Color", "color", current_color, max_length=7, placeholder="Hex color (e.g., #FF0000)")
                await interaction.response.send_modal(modal)
                await modal.wait()
                if modal.value is not None:
                    try:
                        color_value = modal.value.replace("#", "")
                        embed_data["color"] = int(color_value, 16)
                        await update_preview()
                    except ValueError:
                        await interaction.followup.send("Invalid color format. Use hex format like #FF0000", ephemeral=True)
                        
            elif selected == "footer_text":
                modal = EmbedFieldModal("Edit Footer", "footer", embed_data["footer"], max_length=2048)
                await interaction.response.send_modal(modal)
                await modal.wait()
                if modal.value is not None:
                    embed_data["footer"] = modal.value
                    await update_preview()
                    
            elif selected == "author_name":
                modal = EmbedFieldModal("Edit Author", "author", embed_data["author"], max_length=256)
                await interaction.response.send_modal(modal)
                await modal.wait()
                if modal.value is not None:
                    embed_data["author"] = modal.value
                    await update_preview()
                    
            elif selected == "thumbnail":
                modal = EmbedFieldModal("Edit Thumbnail URL", "thumbnail", embed_data["thumbnail"], max_length=512, placeholder="Image URL for thumbnail")
                await interaction.response.send_modal(modal)
                await modal.wait()
                if modal.value is not None:
                    embed_data["thumbnail"] = modal.value
                    await update_preview()
                    
            elif selected == "image":
                modal = EmbedFieldModal("Edit Image URL", "image", embed_data["image"], max_length=512, placeholder="Image URL for main image")
                await interaction.response.send_modal(modal)
                await modal.wait()
                if modal.value is not None:
                    embed_data["image"] = modal.value
                    await update_preview()
                    
            elif selected == "add_field":
                if len(embed_data["fields"]) >= 25:
                    return await interaction.response.send_message("Maximum of 25 fields allowed.", ephemeral=True)
                
                modal = AddFieldModal()
                await interaction.response.send_modal(modal)
                await modal.wait()
                
                if modal.field_data:
                    embed_data["fields"].append(modal.field_data)
                    await update_preview()
                    
            elif selected == "clear_fields":
                embed_data["fields"] = []
                await interaction.response.defer()
                await update_preview()
        
        # Create dropdown select menu
        select_menu = discord.ui.Select(
            placeholder="Choose an embed element to edit...",
            options=[
                discord.SelectOption(label="Title", value="title", emoji="�"),
                discord.SelectOption(label="Description", value="description", emoji="📄"),
                discord.SelectOption(label="Color", value="color", emoji="🎨"),
                discord.SelectOption(label="Footer Text", value="footer_text", emoji="📍"),
                discord.SelectOption(label="Author Name", value="author_name", emoji="👤"),
                discord.SelectOption(label="Thumbnail", value="thumbnail", emoji="🖼️"),
                discord.SelectOption(label="Image", value="image", emoji="🖼️"),
                discord.SelectOption(label="Add Field", value="add_field", emoji="➕"),
                discord.SelectOption(label="Clear Fields", value="clear_fields", emoji="�️")
            ]
        )
        select_menu.callback = handle_selection
        setup_view.add_item(select_menu)
        
        # Submit button
        async def submit_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("Only the command author can use this.", ephemeral=True)
                return
                
            if not any([embed_data["title"], embed_data["description"]]):
                await interaction.response.send_message("Please provide at least a title or description before submitting.", ephemeral=True)
                return
            
            # Save to database
            embed_json = json.dumps(embed_data)
            name_lower = name.lower()
            
            async with aiosqlite.connect(DB_PATH) as db:
                if is_edit:
                    await db.execute(
                        "UPDATE autoresponses SET response_type = ?, embed_data = ?, message = NULL, trigger_mode = ? WHERE guild_id = ? AND LOWER(name) = ?",
                        ('embed', embed_json, trigger_mode, ctx.guild.id, name.lower())
                    )
                else:
                    await db.execute(
                        "INSERT INTO autoresponses (guild_id, name, message, response_type, embed_data, trigger_mode) VALUES (?, ?, ?, ?, ?, ?)",
                        (ctx.guild.id, name.lower(), None, 'embed', embed_json, trigger_mode)
                    )
                await db.commit()
            # Create success message with mode explanation
            mode_text = {
                "word": "🔸 **Word mode** - triggers only on full word matches",
                "phrase": "🔸 **Phrase mode** - triggers when phrase appears in sentences", 
                "full": "🔸 **Full message mode** - triggers only on exact message match"
            }
            
            await interaction.response.send_message(f"<:feast_tick:1400143469892210753> {'Updated' if is_edit else 'Created'} embed autoresponder `{name}` in {ctx.guild.name}\n{mode_text[trigger_mode]}")
            setup_view.stop()

        submit_button = discord.ui.Button(label="Submit", style=discord.ButtonStyle.success, emoji="💾")
        submit_button.callback = submit_callback
        setup_view.add_item(submit_button)
        
        # Cancel button
        async def cancel_callback(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("Only the command author can use this.", ephemeral=True)
                return
                
            cancel_embed = discord.Embed(
                title="❌ Cancelled",
                description="Embed autoresponder creation cancelled.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=cancel_embed)
            setup_view.stop()

        cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")
        cancel_button.callback = cancel_callback
        setup_view.add_item(cancel_button)
        
        await update_preview()

    @_ar.command(name="delete", help="Delete an existing autoresponder.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def _delete(self, ctx, name):
        name_lower = name.lower()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT 1 FROM autoresponses WHERE guild_id = ? AND LOWER(name) = ?", (ctx.guild.id, name_lower)) as cursor:
                if not await cursor.fetchone():
                    return await ctx.reply(embed=discord.Embed(
                        title="<:feast_cross:1400143488695144609> Error!",
                        description=f"No autoresponder found with the name `{name}` in {ctx.guild.name}",
                        color=0x006fb9
                    ))

            await db.execute("DELETE FROM autoresponses WHERE guild_id = ? AND LOWER(name) = ?", (ctx.guild.id, name_lower))
            await db.commit()
            await ctx.reply(embed=discord.Embed(
                title="<:feast_tick:1400143469892210753> Success",
                description=f"Deleted autoresponder `{name}` in {ctx.guild.name}",
                color=0x006fb9
            ))

    @_ar.command(name="edit", help="Edit an existing text autoresponder.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def _edit(self, ctx, name, *, message):
        name_lower = name.lower()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT response_type FROM autoresponses WHERE guild_id = ? AND LOWER(name) = ?", (ctx.guild.id, name_lower)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return await ctx.reply(embed=discord.Embed(
                        title="<:feast_cross:1400143488695144609> Error!",
                        description=f"No autoresponder found with the name `{name}` in {ctx.guild.name}",
                        color=0x006fb9
                    ))
                
                response_type = row[0]
                if response_type == 'embed':
                    return await ctx.reply(embed=discord.Embed(
                        title="<:feast_cross:1400143488695144609> Error!",
                        description=f"This is an embed autoresponder. Use `ar editembed {name}` instead.",
                        color=0x006fb9
                    ))

            await db.execute("UPDATE autoresponses SET message = ?, response_type = ? WHERE guild_id = ? AND LOWER(name) = ?", (message, 'text', ctx.guild.id, name_lower))
            await db.commit()
            await ctx.reply(embed=discord.Embed(
                title="<:feast_tick:1400143469892210753> Success",
                description=f"Edited text autoresponder `{name}` in {ctx.guild.name}",
                color=0x006fb9
            ))

    @_ar.command(name="editembed", help="Edit an existing embed autoresponder.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def _edit_embed(self, ctx, name):
        name_lower = name.lower()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT response_type, embed_data FROM autoresponses WHERE guild_id = ? AND LOWER(name) = ?", (ctx.guild.id, name_lower)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return await ctx.reply(embed=discord.Embed(
                        title="<:feast_cross:1400143488695144609> Error!",
                        description=f"No autoresponder found with the name `{name}` in {ctx.guild.name}",
                        color=0x006fb9
                    ))
                
                response_type, embed_data = row
                if response_type != 'embed':
                    return await ctx.reply(embed=discord.Embed(
                        title="<:feast_cross:1400143488695144609> Error!",
                        description=f"This is a text autoresponder. Use `ar edit {name} <message>` instead.",
                        color=0x006fb9
                    ))

        # Load existing embed data
        try:
            existing_embed_data = json.loads(embed_data) if embed_data else {}
        except:
            existing_embed_data = {}
        
        # Ensure all required fields exist
        embed_data_dict = {
            "title": existing_embed_data.get("title", ""),
            "description": existing_embed_data.get("description", ""),
            "color": existing_embed_data.get("color", 0x006fb9),
            "footer": existing_embed_data.get("footer", ""),
            "author": existing_embed_data.get("author", ""),
            "thumbnail": existing_embed_data.get("thumbnail", ""),
            "image": existing_embed_data.get("image", ""),
            "fields": existing_embed_data.get("fields", [])
        }
        
        await self.embed_builder(ctx, name, embed_data_dict, is_edit=True)

    @_ar.command(name="test", help="Test an autoresponder to see how it will respond")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def _test(self, ctx, name, *, test_message):
        """Test an autoresponder with a sample message"""
        name_lower = name.lower()
        
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT message, response_type, embed_data, trigger_mode FROM autoresponses WHERE guild_id = ? AND LOWER(name) = ?", 
                (ctx.guild.id, name_lower)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return await ctx.reply(embed=discord.Embed(
                        title="<:feast_cross:1400143488695144609> Error!",
                        description=f"No autoresponder found with the name `{name}` in {ctx.guild.name}",
                        color=0x006fb9
                    ))
                
                message_text, response_type, embed_data, trigger_mode = row

        # Test if this message would trigger the autoresponder
        would_trigger = False
        trigger_reason = ""
        
        if trigger_mode == "word":
            words = test_message.lower().split()
            if name_lower in words:
                would_trigger = True
                trigger_reason = f"Word '{name_lower}' found in message"
        elif trigger_mode == "phrase":
            if name_lower in test_message.lower():
                would_trigger = True
                trigger_reason = f"Phrase '{name_lower}' found in message"
        elif trigger_mode == "full":
            if test_message.lower() == name_lower:
                would_trigger = True
                trigger_reason = f"Exact match with trigger '{name_lower}'"
        
        # Create test result embed
        test_embed = discord.Embed(
            title=f"🧪 Autoresponder Test: `{name}`",
            color=0x00ff00 if would_trigger else 0xff0000
        )
        
        test_embed.add_field(
            name="📥 Test Message",
            value=f"```{test_message}```",
            inline=False
        )
        
        test_embed.add_field(
            name="🎯 Trigger Mode", 
            value=f"**{trigger_mode.title()}** mode",
            inline=True
        )
        
        test_embed.add_field(
            name="✅ Would Trigger?" if would_trigger else "❌ Would Not Trigger",
            value=trigger_reason if would_trigger else f"Trigger '{name_lower}' not found in test message",
            inline=True
        )
        
        await ctx.send(embed=test_embed)
        
        # If it would trigger, show the response
        if would_trigger:
            await ctx.send("**📤 Response Preview:**")
            
            if response_type == "text":
                await ctx.send(message_text)
            else:  # embed
                try:
                    embed_dict = json.loads(embed_data)
                    response_embed = discord.Embed(
                        title=embed_dict.get("title"),
                        description=embed_dict.get("description"),
                        color=embed_dict.get("color", 0x006fb9)
                    )
                    
                    if embed_dict.get("footer"):
                        response_embed.set_footer(text=embed_dict["footer"])
                    if embed_dict.get("author"):
                        response_embed.set_author(name=embed_dict["author"])
                    if embed_dict.get("thumbnail"):
                        response_embed.set_thumbnail(url=embed_dict["thumbnail"])
                    if embed_dict.get("image"):
                        response_embed.set_image(url=embed_dict["image"])
                    
                    for field in embed_dict.get("fields", []):
                        response_embed.add_field(
                            name=field["name"],
                            value=field["value"],
                            inline=field.get("inline", False)
                        )
                    
                    await ctx.send(embed=response_embed)
                except Exception as e:
                    await ctx.send(f"❌ Error displaying embed preview: {str(e)}")

    @_ar.command(name="manage", help="Interactive management interface for autoresponders")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def _manage(self, ctx):
        """Interactive management interface for autoresponders"""
        
        async def get_autoresponders():
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute(
                    "SELECT name, response_type, trigger_mode FROM autoresponses WHERE guild_id = ? ORDER BY name",
                    (ctx.guild.id,)
                ) as cursor:
                    rows = await cursor.fetchall()
                    return list(rows) if rows else []
        
        class AutoresponderManageView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=300)
                self.current_page = 0
                self.per_page = 5
            
            async def update_embed(self, interaction):
                autoresponders = await get_autoresponders()
                total_pages = (len(autoresponders) + self.per_page - 1) // self.per_page if autoresponders else 1
                
                embed = discord.Embed(
                    title="🔧 Autoresponder Management",
                    description=f"**Server:** {ctx.guild.name}\n**Total Autoresponders:** {len(autoresponders)}",
                    color=0x006fb9
                )
                
                if autoresponders:
                    start_idx = self.current_page * self.per_page
                    end_idx = start_idx + self.per_page
                    page_items = autoresponders[start_idx:end_idx]
                    
                    for name, response_type, trigger_mode in page_items:
                        type_emoji = "📝" if response_type == "text" else "📊"
                        mode_text = {
                            "word": "Word",
                            "phrase": "Phrase", 
                            "full": "Exact"
                        }.get(trigger_mode, "Unknown")
                        
                        embed.add_field(
                            name=f"{type_emoji} {name}",
                            value=f"**Type:** {response_type.title()}\n**Mode:** {mode_text}",
                            inline=True
                        )
                    
                    embed.set_footer(text=f"Page {self.current_page + 1} of {total_pages}")
                else:
                    embed.add_field(
                        name="📭 No Autoresponders",
                        value="Use `/ar create` to add your first autoresponder!",
                        inline=False
                    )
                
                # Update button states
                self.prev_button.disabled = self.current_page == 0
                self.next_button.disabled = self.current_page >= total_pages - 1
                
                await interaction.response.edit_message(embed=embed, view=self)
            
            @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.secondary, disabled=True)
            async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user != ctx.author:
                    await interaction.response.send_message("Only the command author can use this.", ephemeral=True)
                    return
                
                self.current_page = max(0, self.current_page - 1)
                await self.update_embed(interaction)
            
            @discord.ui.button(label="▶️ Next", style=discord.ButtonStyle.secondary)
            async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user != ctx.author:
                    await interaction.response.send_message("Only the command author can use this.", ephemeral=True)
                    return
                
                autoresponders = await get_autoresponders()
                total_pages = (len(autoresponders) + self.per_page - 1) // self.per_page
                self.current_page = min(total_pages - 1, self.current_page + 1)
                await self.update_embed(interaction)
            
            @discord.ui.button(label="🧪 Test", style=discord.ButtonStyle.primary)
            async def test_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user != ctx.author:
                    await interaction.response.send_message("Only the command author can use this.", ephemeral=True)
                    return
                
                autoresponders = await get_autoresponders()
                if not autoresponders:
                    await interaction.response.send_message("No autoresponders to test!", ephemeral=True)
                    return
                
                # Create test modal
                class TestModal(discord.ui.Modal):
                    def __init__(self):
                        super().__init__(title="Test Autoresponder")
                        
                        self.ar_name = discord.ui.TextInput(
                            label="Autoresponder Name",
                            placeholder="Enter the name of the autoresponder to test",
                            max_length=100,
                            required=True
                        )
                        self.add_item(self.ar_name)
                        
                        self.test_message = discord.ui.TextInput(
                            label="Test Message",
                            placeholder="Enter a message to test against",
                            style=discord.TextStyle.paragraph,
                            max_length=2000,
                            required=True
                        )
                        self.add_item(self.test_message)
                    
                    async def on_submit(self, modal_interaction: discord.Interaction):
                        await modal_interaction.response.defer()
                        
                        # Run the test command logic
                        name_lower = self.ar_name.value.lower()
                        
                        async with aiosqlite.connect(DB_PATH) as db:
                            async with db.execute(
                                "SELECT message, response_type, embed_data, trigger_mode FROM autoresponses WHERE guild_id = ? AND LOWER(name) = ?", 
                                (ctx.guild.id, name_lower)
                            ) as cursor:
                                row = await cursor.fetchone()
                                if not row:
                                    await modal_interaction.followup.send(f"❌ No autoresponder found with name `{self.ar_name.value}`", ephemeral=True)
                                    return
                                
                                message_text, response_type, embed_data, trigger_mode = row
                        
                        # Test logic (same as test command)
                        would_trigger = False
                        trigger_reason = ""
                        
                        if trigger_mode == "word":
                            words = self.test_message.value.lower().split()
                            if name_lower in words:
                                would_trigger = True
                                trigger_reason = f"Word '{name_lower}' found"
                        elif trigger_mode == "phrase":
                            if name_lower in self.test_message.value.lower():
                                would_trigger = True
                                trigger_reason = f"Phrase '{name_lower}' found"
                        elif trigger_mode == "full":
                            if self.test_message.value.lower() == name_lower:
                                would_trigger = True
                                trigger_reason = f"Exact match"
                        
                        result_embed = discord.Embed(
                            title=f"🧪 Test Result: `{self.ar_name.value}`",
                            color=0x00ff00 if would_trigger else 0xff0000
                        )
                        
                        result_embed.add_field(
                            name="📥 Test Message",
                            value=f"```{self.test_message.value[:100]}{'...' if len(self.test_message.value) > 100 else ''}```",
                            inline=False
                        )
                        
                        result_embed.add_field(
                            name="🎯 Result",
                            value=f"{'✅ WOULD TRIGGER' if would_trigger else '❌ WOULD NOT TRIGGER'}\n{trigger_reason if would_trigger else 'Trigger not found'}",
                            inline=False
                        )
                        
                        await modal_interaction.followup.send(embed=result_embed, ephemeral=True)
                
                modal = TestModal()
                await interaction.response.send_modal(modal)
            
            @discord.ui.button(label="📊 Analytics", style=discord.ButtonStyle.success)
            async def analytics_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user != ctx.author:
                    await interaction.response.send_message("Only the command author can use this.", ephemeral=True)
                    return
                
                autoresponders = await get_autoresponders()
                
                # Count by type and mode
                text_count = sum(1 for _, response_type, _ in autoresponders if response_type == "text")
                embed_count = sum(1 for _, response_type, _ in autoresponders if response_type == "embed")
                
                word_count = sum(1 for _, _, trigger_mode in autoresponders if trigger_mode == "word")
                phrase_count = sum(1 for _, _, trigger_mode in autoresponders if trigger_mode == "phrase")
                full_count = sum(1 for _, _, trigger_mode in autoresponders if trigger_mode == "full")
                
                analytics_embed = discord.Embed(
                    title="📊 Autoresponder Analytics",
                    description=f"**Server:** {ctx.guild.name}",
                    color=0x006fb9
                )
                
                analytics_embed.add_field(
                    name="📈 Overview",
                    value=f"**Total:** {len(autoresponders)}\n**Limit:** 20\n**Available:** {20 - len(autoresponders)}",
                    inline=True
                )
                
                analytics_embed.add_field(
                    name="📝 Response Types",
                    value=f"**Text:** {text_count}\n**Embed:** {embed_count}",
                    inline=True
                )
                
                analytics_embed.add_field(
                    name="🎯 Trigger Modes",
                    value=f"**Word:** {word_count}\n**Phrase:** {phrase_count}\n**Exact:** {full_count}",
                    inline=True
                )
                
                if autoresponders:
                    recent_names = [name for name, _, _ in autoresponders[:5]]
                    analytics_embed.add_field(
                        name="📋 Recent Autoresponders",
                        value="\n".join([f"• {name}" for name in recent_names]),
                        inline=False
                    )
                
                await interaction.response.send_message(embed=analytics_embed, ephemeral=True)
        
        # Create initial embed and view
        view = AutoresponderManageView()
        autoresponders = await get_autoresponders()
        
        initial_embed = discord.Embed(
            title="🔧 Autoresponder Management",
            description=f"**Server:** {ctx.guild.name}\n**Total Autoresponders:** {len(autoresponders)}",
            color=0x006fb9
        )
        
        if autoresponders:
            page_items = autoresponders[:5]
            for name, response_type, trigger_mode in page_items:
                type_emoji = "📝" if response_type == "text" else "📊"
                mode_text = {
                    "word": "Word",
                    "phrase": "Phrase", 
                    "full": "Exact"
                }.get(trigger_mode, "Unknown")
                
                initial_embed.add_field(
                    name=f"{type_emoji} {name}",
                    value=f"**Type:** {response_type.title()}\n**Mode:** {mode_text}",
                    inline=True
                )
            
            total_pages = (len(autoresponders) + 5 - 1) // 5
            initial_embed.set_footer(text=f"Page 1 of {total_pages}")
        else:
            initial_embed.add_field(
                name="📭 No Autoresponders",
                value="Use `/ar create` to add your first autoresponder!",
                inline=False
            )
        
        # Update button states
        if not autoresponders or len(autoresponders) <= 5:
            view.next_button.disabled = True
        
        await ctx.send(embed=initial_embed, view=view)

    @_ar.command(name="config", help="List all autoresponders in the server.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def _config(self, ctx):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT name, response_type FROM autoresponses WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                autoresponses = await cursor.fetchall()

        if not autoresponses:
            return await ctx.reply(embed=discord.Embed(
                description=f"There are no autoresponders in {ctx.guild.name}",
                color=0x006fb9
            ))

        embed = discord.Embed(color=0x006fb9, title=f"Autoresponders in {ctx.guild.name}")
        for i, (name, response_type) in enumerate(autoresponses, start=1):
            type_emoji = "📝" if response_type == "text" else "📋"
            embed.add_field(
                name=f"{type_emoji} Autoresponder [{i}]", 
                value=f"**Name:** {name}\n**Type:** {response_type or 'text'}", 
                inline=False
            )
        await ctx.send(embed=embed)

    @_ar.error
    async def _ar_error(self, ctx, error):
        """Error handler for autoresponder command group"""
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="<:feast_cross:1400143488695144609> Access Denied",
                description="You need **Administrator** permissions to use autoresponder commands.",
                color=0xFF0000
            )
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await ctx.send(embed=embed)
        elif isinstance(error, commands.BotMissingPermissions):
            embed = discord.Embed(
                title="<:feast_cross:1400143488695144609> Bot Missing Permissions",
                description=f"I need the following permissions: {', '.join(error.missing_permissions)}",
                color=0xFF0000
            )
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await ctx.send(embed=embed)
        else:
            # Handle other errors
            embed = discord.Embed(
                title="<:feast_cross:1400143488695144609> Error",
                description=f"An error occurred: {str(error)}",
                color=0xFF0000
            )
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        async with aiosqlite.connect(DB_PATH) as db:
            try:
                # Try to select with new columns including trigger_mode
                async with db.execute("SELECT name, message, response_type, embed_data, trigger_mode FROM autoresponses WHERE guild_id = ?", (message.guild.id,)) as cursor:
                    rows = await cursor.fetchall()
            except Exception as e:
                print(f"[AUTORESPONDER] Database error: {e}")
                # Fallback to old schema if new columns don't exist
                try:
                    async with db.execute("SELECT name, message, response_type, embed_data FROM autoresponses WHERE guild_id = ?", (message.guild.id,)) as cursor:
                        old_rows = await cursor.fetchall()
                        # Convert to new format (default to word mode for old entries)
                        rows = [(name, message, response_type or 'text', embed_data, 'word') for name, message, response_type, embed_data in old_rows]
                except Exception as e2:
                    # Ultimate fallback to oldest schema
                    try:
                        async with db.execute("SELECT name, message FROM autoresponses WHERE guild_id = ?", (message.guild.id,)) as cursor:
                            oldest_rows = await cursor.fetchall()
                            rows = [(name, message, 'text', None, 'word') for name, message in oldest_rows]
                    except Exception as e3:
                        print(f"[AUTORESPONDER] All fallback queries failed: {e3}")
                        return

        content_lower = message.content.lower()
        original_content = message.content.strip()  # Keep original case and whitespace
        
        for name, reply, response_type, embed_data, trigger_mode in rows:
            trigger_lower = name.lower()
            should_trigger = False
            
            # Handle missing trigger_mode (for backwards compatibility)
            if trigger_mode is None:
                trigger_mode = "phrase" if ' ' in trigger_lower else "word"
            
            # Apply matching logic based on trigger mode
            if trigger_mode == "full":
                # Full message mode: exact match only (case insensitive)
                should_trigger = original_content.lower().strip() == trigger_lower
            elif trigger_mode == "phrase":
                # Phrase mode: substring match (original behavior for quoted phrases)
                should_trigger = trigger_lower in content_lower
            else:  # trigger_mode == "word"
                # Word mode: full word boundary match only
                import re
                pattern = r'\b' + re.escape(trigger_lower) + r'\b'
                should_trigger = re.search(pattern, content_lower) is not None
            
            if should_trigger:
                try:
                    if response_type == 'embed' and embed_data:
                        # Send embed response
                        embed_dict = json.loads(embed_data)
                        embed = discord.Embed(
                            title=embed_dict.get("title") or None,
                            description=embed_dict.get("description") or None,
                            color=embed_dict.get("color", 0x006fb9)
                        )
                        
                        if embed_dict.get("footer"):
                            embed.set_footer(text=embed_dict["footer"])
                        if embed_dict.get("author"):
                            embed.set_author(name=embed_dict["author"])
                        if embed_dict.get("thumbnail"):
                            embed.set_thumbnail(url=embed_dict["thumbnail"])
                        if embed_dict.get("image"):
                            embed.set_image(url=embed_dict["image"])
                            
                        for field in embed_dict.get("fields", []):
                            embed.add_field(
                                name=field["name"],
                                value=field["value"],
                                inline=field.get("inline", False)
                            )
                        
                        await message.channel.send(embed=embed)
                    else:
                        # Send text response (default)
                        if reply:
                            await message.channel.send(reply)
                except Exception as e:
                    print(f"Error sending autoresponse: {e}")
                    # Fallback to text if embed fails
                    if reply:
                        await message.channel.send(reply)
                break  # stop after first match

async def setup(bot):
    await bot.add_cog(AutoResponder(bot))
