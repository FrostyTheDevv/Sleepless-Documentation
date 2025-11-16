import os
import discord
from discord.ext import commands
from discord.ui import View, Select, Button
import asyncio
import sqlite3
from utils.Tools import *
from utils.button_manager import ButtonManager, create_button_management_view

from utils.error_helpers import StandardErrorHandler
DB_PATH = "db/embed.db"

# Ensure database exists
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute("""
    CREATE TABLE IF NOT EXISTS buttons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT,
        label TEXT,
        emoji TEXT,
        url TEXT,
        message TEXT
    )
""")
conn.commit()
conn.close()


class Embed(commands.Cog):
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot
        self.client = bot

    @commands.hybrid_command(name="embed")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 7, commands.BucketType.user)
    @commands.has_permissions(manage_messages=True)
    async def _embed(self, ctx):
        """Interactive embed builder with optional buttons."""
        embed = discord.Embed(
            title="Edit your Embed!",
            description="- Select Options from the menu below.\n\n*Remember to remove instructions when done.*",
            color=0x006fb9
        )
        interaction_user = ctx.author
        button_manager = ButtonManager()  # Use centralized button manager

        def check_author(msg):
            return msg.channel.id == ctx.channel.id and msg.author.id == interaction_user.id and not msg.author.bot

        # ---------- BUTTON SUBCLASSES ----------
        class MessageButton(Button):
            def __init__(self, label, custom_id, emoji, response_msg):
                super().__init__(label=label, style=discord.ButtonStyle.primary, custom_id=custom_id, emoji=emoji)
                self.response_msg = response_msg

            async def callback(self, interaction: discord.Interaction):
                await interaction.response.send_message(self.response_msg, ephemeral=True)

        # ---------- FIELD HANDLERS ----------
        async def handle_title():
            await ctx.send("Enter embed **title**:")
            msg = await ctx.bot.wait_for("message", timeout=30, check=check_author)
            embed.title = msg.content

        async def handle_description():
            await ctx.send("Enter embed **description**:")
            msg = await ctx.bot.wait_for("message", timeout=30, check=check_author)
            embed.description = msg.content

        async def handle_color():
            await ctx.send("Enter embed **color** in hexadecimal (e.g., #FF0000):")
            msg = await ctx.bot.wait_for("message", timeout=30, check=check_author)
            try:
                embed.color = discord.Colour(int(msg.content.strip("#"), 16))
            except ValueError:
                await ctx.send("Invalid color. Use a hex code like `#FF0000`.")

        async def handle_thumbnail():
            await ctx.send("Enter **thumbnail URL**:")
            msg = await ctx.bot.wait_for("message", timeout=30, check=check_author)
            if not msg.content.startswith("http"):
                await ctx.send("Invalid URL.")
                return
            embed.set_thumbnail(url=msg.content)

        async def handle_image():
            await ctx.send("Enter **image URL**:")
            msg = await ctx.bot.wait_for("message", timeout=30, check=check_author)
            if not msg.content.startswith("http"):
                await ctx.send("Invalid URL.")
                return
            embed.set_image(url=msg.content)

        async def handle_footer_text():
            await ctx.send("Enter **footer text**:")
            msg = await ctx.bot.wait_for("message", timeout=30, check=check_author)
            embed.set_footer(text=msg.content)

        async def handle_footer_icon():
            await ctx.send("Enter **footer icon URL**:")
            msg = await ctx.bot.wait_for("message", timeout=30, check=check_author)
            if not msg.content.startswith("http"):
                await ctx.send("Invalid URL.")
                return
            embed.set_footer(text=embed.footer.text or "Footer", icon_url=msg.content)

        async def handle_author_text():
            await ctx.send("Enter **author text**:")
            msg = await ctx.bot.wait_for("message", timeout=30, check=check_author)
            embed.set_author(name=msg.content)

        async def handle_author_icon():
            await ctx.send("Enter **author icon URL**:")
            msg = await ctx.bot.wait_for("message", timeout=30, check=check_author)
            if not msg.content.startswith("http"):
                await ctx.send("Invalid URL.")
                return
            embed.set_author(name=embed.author.name or "Author", icon_url=msg.content)

        async def handle_add_field():
            await ctx.send("Enter field **title**:")
            name_msg = await ctx.bot.wait_for("message", timeout=30, check=check_author)
            await ctx.send("Enter field **value**:")
            value_msg = await ctx.bot.wait_for("message", timeout=30, check=check_author)
            embed.add_field(name=name_msg.content, value=value_msg.content, inline=False)

        async def handle_add_button():
            # Add buttons using the centralized button manager
            async def button_callback(interaction, button_data):
                """Callback when button is added via modal"""
                button_manager.add_button(
                    button_data['label'],
                    button_data['url'],
                    button_data.get('emoji')
                )
                button_count = len(button_manager.buttons)
                await interaction.response.send_message(f"✅ Button added! Total buttons: {button_count}", ephemeral=True)
                
                # Update the embed preview to show button count
                button_info = f"\n**Buttons:** {button_count} linked button{'s' if button_count != 1 else ''}" if button_count > 0 else ""
                try:
                    await msg.edit(content="**📋 Live Preview:**" + button_info, embed=embed)
                except:
                    pass  # Message might be deleted or edited elsewhere
            
            class ButtonSetupView(View):
                def __init__(self):
                    super().__init__(timeout=60)
                
                @discord.ui.button(label="Add Link Button", style=discord.ButtonStyle.primary, emoji="🔗")
                async def add_button(self, interaction: discord.Interaction, button: Button):
                    if interaction.user.id != interaction_user.id:
                        await interaction.response.send_message("This isn't your embed setup!", ephemeral=True)
                        return
                    
                    # Create and show the button modal
                    from utils.button_manager import ButtonModal
                    modal = ButtonModal(button_callback)
                    await interaction.response.send_modal(modal)

            temp_view = ButtonSetupView()
            await ctx.send("Click the button below to add a link button to your embed:", view=temp_view)

        # ---------- VIEW & COMPONENTS ----------
        select = Select(
            placeholder="Select an option to edit the embed",
            options=[
                discord.SelectOption(label="Title"),
                discord.SelectOption(label="Description"),
                discord.SelectOption(label="Add Field"),
                discord.SelectOption(label="Color"),
                discord.SelectOption(label="Thumbnail"),
                discord.SelectOption(label="Image"),
                discord.SelectOption(label="Footer Text"),
                discord.SelectOption(label="Footer Icon"),
                discord.SelectOption(label="Author Text"),
                discord.SelectOption(label="Author Icon"),
                discord.SelectOption(label="Add Button"),
            ]
        )

        async def send_callback(interaction):
            if interaction.user.id != interaction_user.id:
                await interaction.response.send_message("This button isn't yours!", ephemeral=True)
                return
            await interaction.response.defer()
            await ctx.send("Mention the channel to send embed:")
            try:
                msg_chan = await ctx.bot.wait_for("message", timeout=30, check=check_author)
                channel = msg_chan.channel_mentions[0]
                
                # Create view from button manager
                final_view = None
                if button_manager.buttons:
                    final_view = View(timeout=None)
                    for button_info in button_manager.buttons:
                        button = Button(
                            label=button_info['label'],
                            url=button_info['url'],
                            emoji=button_info.get('emoji'),
                            style=discord.ButtonStyle.link
                        )
                        final_view.add_item(button)
                
                await channel.send(embed=embed, view=final_view)
                await ctx.send("Embed sent successfully ✅")
            except asyncio.TimeoutError:
                await ctx.send("Timed out.")

        async def cancel_callback(interaction):
            if interaction.user.id != interaction_user.id:
                await interaction.response.send_message("This button isn't yours!", ephemeral=True)
                return
            await interaction.response.defer()
            await msg.delete()

        # Create builder interface with immediate preview
        builder_embed = discord.Embed(
            title="🔧 Embed Builder",
            color=0x006fb9
        )
        
        builder_embed.add_field(
            name="📝 Current Configuration",
            value=f"**Title:** {embed.title or 'Not Set'}\n**Description:** {'Set' if embed.description else 'Not Set'}\n**Color:** {f'#{embed.color.value:06x}' if embed.color else 'Default'}\n**Fields:** {len(embed.fields)}\n**Buttons:** {len(button_manager.buttons)}",
            inline=False
        )
        
        builder_embed.set_footer(text="📋 Use the dropdown to customize your embed • Live preview below")

        button_send = Button(label="Send Embed", style=discord.ButtonStyle.success)
        button_send.callback = send_callback

        button_cancel = Button(label="Cancel Setup", style=discord.ButtonStyle.danger)
        button_cancel.callback = cancel_callback

        view = View(timeout=180)
        view.add_item(select)
        view.add_item(button_send)
        view.add_item(button_cancel)

        # Send builder interface and live preview
        msg = await ctx.send(embed=builder_embed, view=view)
        preview_msg = await ctx.send("**📋 Live Preview:**", embed=embed)
        
        # Set up callback after messages are created
        async def select_callback(interaction):
            if interaction.user.id != interaction_user.id:
                await interaction.response.send_message("This menu isn't yours!", ephemeral=True)
                return
            await interaction.response.defer()
            value = select.values[0]

            handlers = {
                "Title": handle_title,
                "Description": handle_description,
                "Color": handle_color,
                "Thumbnail": handle_thumbnail,
                "Image": handle_image,
                "Footer Text": handle_footer_text,
                "Footer Icon": handle_footer_icon,
                "Author Text": handle_author_text,
                "Author Icon": handle_author_icon,
                "Add Field": handle_add_field,
                "Add Button": handle_add_button,
            }

            if value in handlers:
                try:
                    await handlers[value]()
                    
                    # Update builder interface
                    updated_builder_embed = discord.Embed(
                        title="🔧 Embed Builder",
                        color=0x006fb9
                    )
                    
                    updated_builder_embed.add_field(
                        name="📝 Current Configuration",
                        value=f"**Title:** {embed.title or 'Not Set'}\n**Description:** {'Set' if embed.description else 'Not Set'}\n**Color:** {f'#{embed.color.value:06x}' if embed.color else 'Default'}\n**Fields:** {len(embed.fields)}\n**Buttons:** {len(button_manager.buttons)}",
                        inline=False
                    )
                    
                    updated_builder_embed.set_footer(text="📋 Use the dropdown to customize your embed • Live preview below")
                    
                    # Update both builder and live preview
                    await msg.edit(embed=updated_builder_embed, view=view)
                    await preview_msg.edit(content="**📋 Live Preview:**", embed=embed)
                except asyncio.TimeoutError:
                    await ctx.send("Timed out.")
        
        select.callback = select_callback
        ctx.message = msg


"""
@Author: Frosty
    + Discord: frosty.pyro
    + Community: https://discord.gg/5wtjDkYbVh (Sleepless Development)
    + for any queries reach out in the server; or send a dm.
"""
