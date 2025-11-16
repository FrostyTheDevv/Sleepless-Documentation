import discord
from discord.ext import commands
from discord.ui import View, Button, Select, Modal, TextInput
from typing import Optional
import json
import aiosqlite
from utils.Tools import *
from utils.error_helpers import StandardErrorHandler

class ButtonManager(commands.Cog):
    """
    Button management system with dropdown builders
    """
    
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "db/buttons.db"
        
    async def ensure_button_db(self):
        """Ensure button database exists"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS server_buttons (
                    guild_id INTEGER,
                    button_id TEXT,
                    button_name TEXT,
                    button_type TEXT,
                    button_data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (guild_id, button_id)
                )
            ''')
            await db.commit()
    
    @commands.group(name="button", aliases=["btn"], invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def button_group(self, ctx):
        """Button management system"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="Button Management System",
                description="Manage interactive buttons for your server",
                color=0x2F3136
            )
            
            embed.add_field(
                name="Available Commands",
                value="• `button create` - Create a new button\n"
                      "• `button list` - View all server buttons\n"
                      "• `button edit <id>` - Edit an existing button\n"
                      "• `button link <id> <message_id>` - Link button to message\n"
                      "• `button delete <id>` - Delete a button\n\n"
                      "**Aliases:** `btn create`, `btn list`, `btn link`, etc.",
                inline=False
            )
            
            await ctx.send(embed=embed)
    
    @button_group.command(name="create")
    async def create_button(self, ctx):
        """Create a new interactive button with dropdown builder"""
        await self.ensure_button_db()
        
        # Create button builder view
        view = ButtonBuilderView(ctx, self)
        
        embed = discord.Embed(
            title="Button Builder",
            description="Choose the type of button you want to create:",
            color=0x2F3136
        )
        
        await ctx.send(embed=embed, view=view)
    
    @button_group.command(name="list")
    async def list_buttons(self, ctx):
        """List all buttons in the server"""
        await self.ensure_button_db()
        
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT button_id, button_name, button_type FROM server_buttons WHERE guild_id = ?",
                (ctx.guild.id,)
            ) as cursor:
                buttons = list(await cursor.fetchall())
        
        if not buttons:
            embed = discord.Embed(
                title="Server Buttons",
                description="No buttons have been created yet.\nUse `button create` to make your first button!",
                color=0x2F3136
            )
            await ctx.send(embed=embed)
            return
        
        # Group buttons by type
        button_types = {}
        for button_id, name, btn_type in buttons:
            if btn_type not in button_types:
                button_types[btn_type] = []
            button_types[btn_type].append(f"`{button_id}` - {name}")
        
        embed = discord.Embed(
            title="Server Buttons",
            description=f"Total: {len(buttons)} buttons",
            color=0x2F3136
        )
        
        type_emojis = {
            'link': '🔗',
            'role': '🎭', 
            'channel': '📍',
            'message': '💬',
            'action': '⚡'
        }
        
        for btn_type, btn_list in button_types.items():
            emoji = type_emojis.get(btn_type, '🔘')
            embed.add_field(
                name=f"{emoji} {btn_type.title()} Buttons",
                value="\n".join(btn_list[:10]) + (f"\n... and {len(btn_list)-10} more" if len(btn_list) > 10 else ""),
                inline=False
            )
        
        embed.set_footer(text="Use 'button edit <id>' to modify or 'button delete <id>' to remove")
        await ctx.send(embed=embed)
    
    @button_group.command(name="link")
    async def link_button(self, ctx, button_id: str, message_id: str, *, channel: Optional[discord.TextChannel] = None):
        """Link/attach a button to an existing message
        
        Usage: 
        !btn link <button_id> <message_id> [#channel]
        
        If no channel is specified, uses the current channel.
        """
        await self.ensure_button_db()
        
        # Use current channel if none specified
        if channel is None:
            channel = ctx.channel
        
        # Type assertion for mypy
        assert channel is not None
        
        # Get button data
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT button_name, button_type, button_data FROM server_buttons WHERE guild_id = ? AND button_id = ?",
                (ctx.guild.id, button_id)
            ) as cursor:
                button_data = await cursor.fetchone()
        
        if not button_data:
            embed = discord.Embed(
                title="Button Not Found",
                description=f"No button found with ID: `{button_id}`\nUse `button list` to see available buttons.",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        
        button_name, button_type, button_config_str = button_data
        
        try:
            button_config = json.loads(button_config_str)
        except json.JSONDecodeError:
            embed = discord.Embed(
                title="Button Configuration Error",
                description=f"Invalid button configuration for `{button_id}`",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        
        # Get the target message
        try:
            message = await channel.fetch_message(int(message_id))
        except discord.NotFound:
            embed = discord.Embed(
                title="Message Not Found",
                description=f"Could not find message with ID `{message_id}` in {channel.mention}",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        except discord.Forbidden:
            embed = discord.Embed(
                title="Permission Error",
                description=f"No permission to access message in {channel.mention}",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        except ValueError:
            embed = discord.Embed(
                title="Invalid Message ID",
                description=f"`{message_id}` is not a valid message ID",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        
        # Create the button based on type
        view = discord.ui.View(timeout=None)
        
        if button_type == 'link':
            button = discord.ui.Button(
                label=button_name,
                url=button_config.get('url'),
                style=discord.ButtonStyle.link
            )
            view.add_item(button)
            
        elif button_type == 'role':
            # Create role button with callback
            button = discord.ui.Button(
                label=button_name,
                style=discord.ButtonStyle.secondary,
                custom_id=f"role_{button_id}_{ctx.guild.id}"
            )
            
            async def role_button_callback(interaction):
                role_id = button_config.get('role_id')
                action = button_config.get('action', 'toggle')
                
                role = interaction.guild.get_role(role_id)
                if not role:
                    await interaction.response.send_message("Role no longer exists!", ephemeral=True)
                    return
                
                member = interaction.user
                has_role = role in member.roles
                
                try:
                    if action == 'add' or (action == 'toggle' and not has_role):
                        await member.add_roles(role)
                        await interaction.response.send_message(f"✅ Added role {role.name}", ephemeral=True)
                    elif action == 'remove' or (action == 'toggle' and has_role):
                        await member.remove_roles(role)
                        await interaction.response.send_message(f"❌ Removed role {role.name}", ephemeral=True)
                except discord.Forbidden:
                    await interaction.response.send_message("❌ Bot lacks permission to manage this role", ephemeral=True)
                except Exception as e:
                    await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)
            
            button.callback = role_button_callback
            view.add_item(button)
            
        elif button_type == 'channel':
            # Channel buttons redirect to channels
            channel_id = button_config.get('channel_id')
            target_channel = ctx.guild.get_channel(channel_id)
            
            if target_channel:
                button = discord.ui.Button(
                    label=button_name,
                    style=discord.ButtonStyle.secondary,
                    custom_id=f"channel_{button_id}_{ctx.guild.id}"
                )
                
                async def channel_button_callback(interaction):
                    await interaction.response.send_message(
                        f"📍 {target_channel.mention}", 
                        ephemeral=True
                    )
                
                button.callback = channel_button_callback
                view.add_item(button)
            else:
                embed = discord.Embed(
                    title="Channel Not Found",
                    description=f"Target channel for button `{button_id}` no longer exists",
                    color=0xFF0000
                )
                await ctx.send(embed=embed)
                return
                
        elif button_type == 'message':
            # Message buttons send predefined messages
            button = discord.ui.Button(
                label=button_name,
                style=discord.ButtonStyle.secondary,
                custom_id=f"message_{button_id}_{ctx.guild.id}"
            )
            
            async def message_button_callback(interaction):
                message_content = button_config.get('message', 'No message configured')
                await interaction.response.send_message(message_content, ephemeral=True)
            
            button.callback = message_button_callback
            view.add_item(button)
            
        elif button_type == 'action':
            # Action buttons for custom actions
            button = discord.ui.Button(
                label=button_name,
                style=discord.ButtonStyle.secondary,
                custom_id=f"action_{button_id}_{ctx.guild.id}"
            )
            
            async def action_button_callback(interaction):
                action_type = button_config.get('action_type', 'unknown')
                action_data = button_config.get('action_data', '')
                await interaction.response.send_message(
                    f"🔧 Action: {action_type}\n📝 Data: {action_data}", 
                    ephemeral=True
                )
            
            button.callback = action_button_callback
            view.add_item(button)
        
        else:
            embed = discord.Embed(
                title="Unsupported Button Type",
                description=f"Button type `{button_type}` is not supported for linking",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        
        # Edit the message to add the button
        try:
            await message.edit(view=view)
            
            embed = discord.Embed(
                title="Button Linked Successfully",
                description=f"✅ Button `{button_id}` (`{button_name}`) has been attached to the message!",
                color=0x00FF00
            )
            embed.add_field(name="Message", value=f"[Jump to Message]({message.jump_url})", inline=False)
            embed.add_field(name="Channel", value=channel.mention, inline=True)
            embed.add_field(name="Button Type", value=button_type.title(), inline=True)
            
            await ctx.send(embed=embed)
            
        except discord.Forbidden:
            embed = discord.Embed(
                title="Permission Error",
                description="Bot lacks permission to edit that message",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                title="Error Linking Button",
                description=f"Failed to attach button: {str(e)}",
                color=0xFF0000
            )
            await ctx.send(embed=embed)

    @button_group.command(name="delete")
    async def delete_button(self, ctx, button_id: str):
        """Delete a button by ID"""
        await self.ensure_button_db()
        
        # Check if button exists
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT button_name, button_type FROM server_buttons WHERE guild_id = ? AND button_id = ?",
                (ctx.guild.id, button_id)
            ) as cursor:
                button_data = await cursor.fetchone()
        
        if not button_data:
            embed = discord.Embed(
                title="Button Not Found",
                description=f"No button found with ID: `{button_id}`\nUse `button list` to see available buttons.",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        
        name, btn_type = button_data
        
        # Confirmation view
        class ConfirmDeleteView(View):
            def __init__(self, db_path):
                super().__init__(timeout=60)
                self.db_path = db_path
            
            @discord.ui.button(label="Delete", style=discord.ButtonStyle.secondary)
            async def confirm_delete(self, interaction, button):
                if interaction.user != ctx.author:
                    await interaction.response.send_message("Only the command author can delete buttons.", ephemeral=True)
                    return
                
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute(
                        "DELETE FROM server_buttons WHERE guild_id = ? AND button_id = ?",
                        (ctx.guild.id, button_id)
                    )
                    await db.commit()
                
                success_embed = discord.Embed(
                    title="Button Deleted",
                    description=f"Successfully deleted button: `{name}` ({btn_type})",
                    color=0x00FF00
                )
                await interaction.response.edit_message(embed=success_embed, view=None)
            
            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
            async def cancel_delete(self, interaction, button):
                if interaction.user != ctx.author:
                    await interaction.response.send_message("Only the command author can cancel.", ephemeral=True)
                    return
                
                cancel_embed = discord.Embed(
                    title="Deletion Cancelled",
                    description="Button deletion has been cancelled.",
                    color=0x2F3136
                )
                await interaction.response.edit_message(embed=cancel_embed, view=None)
        
        confirm_embed = discord.Embed(
            title="Confirm Button Deletion",
            description=f"Are you sure you want to delete this button?\n\n"
                       f"**Name:** {name}\n"
                       f"**Type:** {btn_type}\n"
                       f"**ID:** `{button_id}`",
            color=0x2F3136
        )
        
        await ctx.send(embed=confirm_embed, view=ConfirmDeleteView(self.db_path))
    
    @button_group.command(name="edit")
    async def edit_button(self, ctx, button_id: str):
        """Edit an existing button"""
        await self.ensure_button_db()
        
        # Get button data
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT button_name, button_type, button_data FROM server_buttons WHERE guild_id = ? AND button_id = ?",
                (ctx.guild.id, button_id)
            ) as cursor:
                button_data = await cursor.fetchone()
        
        if not button_data:
            embed = discord.Embed(
                title="Button Not Found",
                description=f"No button found with ID: `{button_id}`\nUse `button list` to see available buttons.",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        
        name, btn_type, data_json = button_data
        button_config = json.loads(data_json)
        
        # Create edit view with current data pre-filled
        view = ButtonEditView(ctx, self, button_id, name, btn_type, button_config)
        
        embed = discord.Embed(
            title="Edit Button",
            description=f"Editing: `{name}` ({btn_type})\nID: `{button_id}`",
            color=0x2F3136
        )
        
        await ctx.send(embed=embed, view=view)
    
    @button_group.command(name="testmessage", aliases=["tm"])
    async def test_message(self, ctx):
        """Send a test message that you can link buttons to"""
        embed = discord.Embed(
            title="🧪 Button Test Message",
            description="This is a test message for linking buttons!\n\n"
                       f"**Message ID:** `{ctx.message.id}`\n"
                       "Copy this message ID and use it with `!btn link <button_id> <message_id>`",
            color=0x2F3136
        )
        embed.add_field(
            name="How to Link Buttons",
            value="1. Create a button with `!btn create`\n"
                  "2. Right-click this message → Copy Message ID\n"
                  "3. Use `!btn link <button_id> <message_id>`",
            inline=False
        )
        
        message = await ctx.send(embed=embed)
        
        # Update the embed with the actual message ID
        embed.description = (f"This is a test message for linking buttons!\n\n"
                           f"**Message ID:** `{message.id}`\n"
                           "Copy this message ID and use it with `!btn link <button_id> <message_id>`")
        await message.edit(embed=embed)

    async def save_button(self, guild_id: int, button_id: str, name: str, btn_type: str, config: dict):
        """Save button to database"""
        await self.ensure_button_db()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT OR REPLACE INTO server_buttons 
                (guild_id, button_id, button_name, button_type, button_data)
                VALUES (?, ?, ?, ?, ?)
            ''', (guild_id, button_id, name, btn_type, json.dumps(config)))
            await db.commit()


class ButtonBuilderView(View):
    def __init__(self, ctx, manager):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.manager = manager
    
    @discord.ui.select(
        placeholder="Choose button type to create...",
        options=[
            discord.SelectOption(
                label="Link Button",
                description="Add a link to website or Discord server",
                emoji="🔗",
                value="link"
            ),
            discord.SelectOption(
                label="Role Button", 
                description="Add/remove roles when clicked",
                emoji="🎭",
                value="role"
            ),
            discord.SelectOption(
                label="Channel Button",
                description="Link to a specific channel", 
                emoji="📍",
                value="channel"
            ),
            discord.SelectOption(
                label="Message Button",
                description="Send a message when clicked",
                emoji="💬", 
                value="message"
            ),
            discord.SelectOption(
                label="Action Button",
                description="Trigger custom actions",
                emoji="⚡",
                value="action"
            )
        ]
    )
    async def button_type_select(self, interaction: discord.Interaction, select: Select):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("Only the command author can use this.", ephemeral=True)
            return
        
        button_type = select.values[0]
        
        # Show appropriate modal for the button type
        if button_type == "link":
            modal = LinkButtonModal(self.ctx, self.manager)
        elif button_type == "role":
            modal = RoleButtonModal(self.ctx, self.manager)
        elif button_type == "channel":
            modal = ChannelButtonModal(self.ctx, self.manager)
        elif button_type == "message":
            modal = MessageButtonModal(self.ctx, self.manager)
        elif button_type == "action":
            modal = ActionButtonModal(self.ctx, self.manager)
        
        await interaction.response.send_modal(modal)


class LinkButtonModal(Modal):
    def __init__(self, ctx, manager):
        super().__init__(title="Create Link Button")
        self.ctx = ctx
        self.manager = manager
        
        self.add_item(TextInput(
            label="Button Name",
            placeholder="Enter the button text (e.g., 'Visit Website')",
            max_length=80
        ))
        
        self.add_item(TextInput(
            label="URL",
            placeholder="https://example.com or discord.gg/invite",
            max_length=200
        ))
        
        self.add_item(TextInput(
            label="Button ID",
            placeholder="Unique identifier (e.g., 'website_link')",
            max_length=50
        ))
    
    async def on_submit(self, interaction: discord.Interaction):
        name = self.children[0].value  # type: ignore
        url = self.children[1].value  # type: ignore
        button_id = self.children[2].value  # type: ignore
        
        # Validate URL
        if not (url.startswith('http://') or url.startswith('https://') or url.startswith('discord.gg/')):
            await interaction.response.send_message("Invalid URL. Must start with http://, https://, or discord.gg/", ephemeral=True)
            return
        
        config = {
            'name': name,
            'url': url,
            'style': 'link'
        }
        
        await self.manager.save_button(self.ctx.guild.id, button_id, name, 'link', config)
        
        embed = discord.Embed(
            title="Link Button Created",
            description=f"✅ Successfully created link button!\n\n"
                       f"**Name:** {name}\n"
                       f"**URL:** {url}\n"
                       f"**ID:** `{button_id}`",
            color=0x00FF00
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class RoleButtonModal(Modal):
    def __init__(self, ctx, manager):
        super().__init__(title="Create Role Button")
        self.ctx = ctx
        self.manager = manager
        
        self.add_item(TextInput(
            label="Button Name",
            placeholder="Enter the button text (e.g., 'Get Member Role')",
            max_length=80
        ))
        
        self.add_item(TextInput(
            label="Role Name or ID",
            placeholder="Role name or role ID",
            max_length=100
        ))
        
        self.add_item(TextInput(
            label="Button ID", 
            placeholder="Unique identifier (e.g., 'member_role')",
            max_length=50
        ))
        
        self.add_item(TextInput(
            label="Action",
            placeholder="add, remove, or toggle",
            max_length=10,
            default="toggle"
        ))
    
    async def on_submit(self, interaction: discord.Interaction):
        name = self.children[0].value  # type: ignore
        role_input = self.children[1].value  # type: ignore
        button_id = self.children[2].value  # type: ignore
        action = self.children[3].value.lower()  # type: ignore
        
        # Find role
        role = None
        if role_input.isdigit():
            role = self.ctx.guild.get_role(int(role_input))
        else:
            role = discord.utils.get(self.ctx.guild.roles, name=role_input)
        
        if not role:
            await interaction.response.send_message(f"Role '{role_input}' not found!", ephemeral=True)
            return
        
        if action not in ['add', 'remove', 'toggle']:
            await interaction.response.send_message("Action must be 'add', 'remove', or 'toggle'", ephemeral=True)
            return
        
        config = {
            'name': name,
            'role_id': role.id,
            'role_name': role.name,
            'action': action
        }
        
        await self.manager.save_button(self.ctx.guild.id, button_id, name, 'role', config)
        
        embed = discord.Embed(
            title="Role Button Created",
            description=f"✅ Successfully created role button!\n\n"
                       f"**Name:** {name}\n"
                       f"**Role:** {role.mention}\n"
                       f"**Action:** {action}\n"
                       f"**ID:** `{button_id}`",
            color=0x00FF00
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ChannelButtonModal(Modal):
    def __init__(self, ctx, manager):
        super().__init__(title="Create Channel Button")
        self.ctx = ctx
        self.manager = manager
        
        self.add_item(TextInput(
            label="Button Name",
            placeholder="Enter the button text (e.g., 'Go to General')",
            max_length=80
        ))
        
        self.add_item(TextInput(
            label="Channel Name or ID",
            placeholder="Channel name or channel ID",
            max_length=100
        ))
        
        self.add_item(TextInput(
            label="Button ID",
            placeholder="Unique identifier (e.g., 'general_channel')",
            max_length=50
        ))
    
    async def on_submit(self, interaction: discord.Interaction):
        name = self.children[0].value  # type: ignore
        channel_input = self.children[1].value  # type: ignore
        button_id = self.children[2].value  # type: ignore
        
        # Find channel
        channel = None
        if channel_input.isdigit():
            channel = self.ctx.guild.get_channel(int(channel_input))
        else:
            channel = discord.utils.get(self.ctx.guild.channels, name=channel_input)
        
        if not channel:
            await interaction.response.send_message(f"Channel '{channel_input}' not found!", ephemeral=True)
            return
        
        config = {
            'name': name,
            'channel_id': channel.id,
            'channel_name': channel.name
        }
        
        await self.manager.save_button(self.ctx.guild.id, button_id, name, 'channel', config)
        
        embed = discord.Embed(
            title="Channel Button Created",
            description=f"✅ Successfully created channel button!\n\n"
                       f"**Name:** {name}\n"
                       f"**Channel:** {channel.mention}\n"
                       f"**ID:** `{button_id}`",
            color=0x00FF00
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class MessageButtonModal(Modal):
    def __init__(self, ctx, manager):
        super().__init__(title="Create Message Button")
        self.ctx = ctx
        self.manager = manager
        
        self.add_item(TextInput(
            label="Button Name",
            placeholder="Enter the button text (e.g., 'Server Info')",
            max_length=80
        ))
        
        self.add_item(TextInput(
            label="Message Content",
            placeholder="Message to send when button is clicked",
            style=discord.TextStyle.paragraph,
            max_length=2000
        ))
        
        self.add_item(TextInput(
            label="Button ID",
            placeholder="Unique identifier (e.g., 'info_message')",
            max_length=50
        ))
    
    async def on_submit(self, interaction: discord.Interaction):
        name = self.children[0].value  # type: ignore
        message = self.children[1].value  # type: ignore
        button_id = self.children[2].value  # type: ignore
        
        config = {
            'name': name,
            'message': message
        }
        
        await self.manager.save_button(self.ctx.guild.id, button_id, name, 'message', config)
        
        embed = discord.Embed(
            title="Message Button Created",
            description=f"✅ Successfully created message button!\n\n"
                       f"**Name:** {name}\n"
                       f"**Message:** {message[:100]}{'...' if len(message) > 100 else ''}\n"
                       f"**ID:** `{button_id}`",
            color=0x00FF00
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ActionButtonModal(Modal):
    def __init__(self, ctx, manager):
        super().__init__(title="Create Action Button")
        self.ctx = ctx
        self.manager = manager
        
        self.add_item(TextInput(
            label="Button Name",
            placeholder="Enter the button text (e.g., 'Custom Action')",
            max_length=80
        ))
        
        self.add_item(TextInput(
            label="Action Type",
            placeholder="Type of action to perform",
            max_length=50
        ))
        
        self.add_item(TextInput(
            label="Action Data",
            placeholder="Additional data for the action",
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=False
        ))
        
        self.add_item(TextInput(
            label="Button ID",
            placeholder="Unique identifier (e.g., 'custom_action')",
            max_length=50
        ))
    
    async def on_submit(self, interaction: discord.Interaction):
        name = self.children[0].value  # type: ignore
        action_type = self.children[1].value  # type: ignore
        action_data = self.children[2].value  # type: ignore
        button_id = self.children[3].value  # type: ignore
        
        config = {
            'name': name,
            'action_type': action_type,
            'action_data': action_data
        }
        
        await self.manager.save_button(self.ctx.guild.id, button_id, name, 'action', config)
        
        embed = discord.Embed(
            title="Action Button Created",
            description=f"✅ Successfully created action button!\n\n"
                       f"**Name:** {name}\n"
                       f"**Action Type:** {action_type}\n"
                       f"**ID:** `{button_id}`",
            color=0x00FF00
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ButtonEditView(View):
    def __init__(self, ctx, manager, button_id, name, btn_type, config):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.manager = manager
        self.button_id = button_id
        self.name = name
        self.btn_type = btn_type
        self.config = config
    
    @discord.ui.button(label="Edit Configuration", style=discord.ButtonStyle.secondary)
    async def edit_config(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("Only the command author can edit buttons.", ephemeral=True)
            return
        
        # Show appropriate modal based on button type
        if self.btn_type == "link":
            modal = EditLinkModal(self.ctx, self.manager, self.button_id, self.config)
        elif self.btn_type == "role":
            modal = EditRoleModal(self.ctx, self.manager, self.button_id, self.config)
        elif self.btn_type == "channel":
            modal = EditChannelModal(self.ctx, self.manager, self.button_id, self.config)
        elif self.btn_type == "message":
            modal = EditMessageModal(self.ctx, self.manager, self.button_id, self.config)
        elif self.btn_type == "action":
            modal = EditActionModal(self.ctx, self.manager, self.button_id, self.config)
        
        await interaction.response.send_modal(modal)


class EditLinkModal(Modal):
    def __init__(self, ctx, manager, button_id, config):
        super().__init__(title="Edit Link Button")
        self.ctx = ctx
        self.manager = manager
        self.button_id = button_id
        
        self.add_item(TextInput(
            label="Button Name",
            placeholder="Enter the button text",
            max_length=80,
            default=config.get('name', '')
        ))
        
        self.add_item(TextInput(
            label="URL",
            placeholder="https://example.com or discord.gg/invite",
            max_length=200,
            default=config.get('url', '')
        ))
    
    async def on_submit(self, interaction: discord.Interaction):
        name = self.children[0].value  # type: ignore
        url = self.children[1].value  # type: ignore
        
        if not (url.startswith('http://') or url.startswith('https://') or url.startswith('discord.gg/')):
            await interaction.response.send_message("Invalid URL format!", ephemeral=True)
            return
        
        config = {
            'name': name,
            'url': url,
            'style': 'link'
        }
        
        await self.manager.save_button(self.ctx.guild.id, self.button_id, name, 'link', config)
        
        embed = discord.Embed(
            title="Link Button Updated",
            description=f"✅ Successfully updated button `{self.button_id}`!",
            color=0x00FF00
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class EditRoleModal(Modal):
    def __init__(self, ctx, manager, button_id, config):
        super().__init__(title="Edit Role Button")
        self.ctx = ctx
        self.manager = manager
        self.button_id = button_id
        
        self.add_item(TextInput(
            label="Button Name",
            placeholder="Enter the button text",
            max_length=80,
            default=config.get('name', '')
        ))
        
        self.add_item(TextInput(
            label="Role Name or ID",
            placeholder="Role name or role ID",
            max_length=100,
            default=config.get('role_name', '')
        ))
        
        self.add_item(TextInput(
            label="Action",
            placeholder="add, remove, or toggle",
            max_length=10,
            default=config.get('action', 'toggle')
        ))
    
    async def on_submit(self, interaction: discord.Interaction):
        name = self.children[0].value  # type: ignore
        role_input = self.children[1].value  # type: ignore
        action = self.children[2].value.lower()  # type: ignore
        
        # Find role
        role = None
        if role_input.isdigit():
            role = self.ctx.guild.get_role(int(role_input))
        else:
            role = discord.utils.get(self.ctx.guild.roles, name=role_input)
        
        if not role:
            await interaction.response.send_message(f"Role '{role_input}' not found!", ephemeral=True)
            return
        
        if action not in ['add', 'remove', 'toggle']:
            await interaction.response.send_message("Action must be 'add', 'remove', or 'toggle'", ephemeral=True)
            return
        
        config = {
            'name': name,
            'role_id': role.id,
            'role_name': role.name,
            'action': action
        }
        
        await self.manager.save_button(self.ctx.guild.id, self.button_id, name, 'role', config)
        
        embed = discord.Embed(
            title="Role Button Updated",
            description=f"✅ Successfully updated button `{self.button_id}`!",
            color=0x00FF00
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class EditChannelModal(Modal):
    def __init__(self, ctx, manager, button_id, config):
        super().__init__(title="Edit Channel Button")
        self.ctx = ctx
        self.manager = manager
        self.button_id = button_id
        
        self.add_item(TextInput(
            label="Button Name",
            placeholder="Enter the button text",
            max_length=80,
            default=config.get('name', '')
        ))
        
        self.add_item(TextInput(
            label="Channel Name or ID",
            placeholder="Channel name or channel ID",
            max_length=100,
            default=config.get('channel_name', '')
        ))
    
    async def on_submit(self, interaction: discord.Interaction):
        name = self.children[0].value  # type: ignore
        channel_input = self.children[1].value  # type: ignore
        
        # Find channel
        channel = None
        if channel_input.isdigit():
            channel = self.ctx.guild.get_channel(int(channel_input))
        else:
            channel = discord.utils.get(self.ctx.guild.channels, name=channel_input)
        
        if not channel:
            await interaction.response.send_message(f"Channel '{channel_input}' not found!", ephemeral=True)
            return
        
        config = {
            'name': name,
            'channel_id': channel.id,
            'channel_name': channel.name
        }
        
        await self.manager.save_button(self.ctx.guild.id, self.button_id, name, 'channel', config)
        
        embed = discord.Embed(
            title="Channel Button Updated",
            description=f"✅ Successfully updated button `{self.button_id}`!",
            color=0x00FF00
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class EditMessageModal(Modal):
    def __init__(self, ctx, manager, button_id, config):
        super().__init__(title="Edit Message Button")
        self.ctx = ctx
        self.manager = manager
        self.button_id = button_id
        
        self.add_item(TextInput(
            label="Button Name",
            placeholder="Enter the button text",
            max_length=80,
            default=config.get('name', '')
        ))
        
        self.add_item(TextInput(
            label="Message Content",
            placeholder="Message to send when button is clicked",
            style=discord.TextStyle.paragraph,
            max_length=2000,
            default=config.get('message', '')
        ))
    
    async def on_submit(self, interaction: discord.Interaction):
        name = self.children[0].value  # type: ignore
        message = self.children[1].value  # type: ignore
        
        config = {
            'name': name,
            'message': message
        }
        
        await self.manager.save_button(self.ctx.guild.id, self.button_id, name, 'message', config)
        
        embed = discord.Embed(
            title="Message Button Updated",
            description=f"✅ Successfully updated button `{self.button_id}`!",
            color=0x00FF00
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class EditActionModal(Modal):
    def __init__(self, ctx, manager, button_id, config):
        super().__init__(title="Edit Action Button")
        self.ctx = ctx
        self.manager = manager
        self.button_id = button_id
        
        self.add_item(TextInput(
            label="Button Name",
            placeholder="Enter the button text",
            max_length=80,
            default=config.get('name', '')
        ))
        
        self.add_item(TextInput(
            label="Action Type",
            placeholder="Type of action to perform",
            max_length=50,
            default=config.get('action_type', '')
        ))
        
        self.add_item(TextInput(
            label="Action Data",
            placeholder="Additional data for the action",
            style=discord.TextStyle.paragraph,
            max_length=500,
            default=config.get('action_data', ''),
            required=False
        ))
    
    async def on_submit(self, interaction: discord.Interaction):
        name = self.children[0].value  # type: ignore
        action_type = self.children[1].value  # type: ignore
        action_data = self.children[2].value  # type: ignore
        
        config = {
            'name': name,
            'action_type': action_type,
            'action_data': action_data
        }
        
        await self.manager.save_button(self.ctx.guild.id, self.button_id, name, 'action', config)
        
        embed = discord.Embed(
            title="Action Button Updated",
            description=f"✅ Successfully updated button `{self.button_id}`!",
            color=0x00FF00
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(ButtonManager(bot))