import discord
from discord.ext import commands
from discord.ui import Button, View, Select, Modal, TextInput
import aiosqlite
import os
import json
import aiohttp
from io import BytesIO
from typing import Optional, Union, Dict, Any
from utils.Tools import *
from core import Cog, sleepless, Context

from utils.error_helpers import StandardErrorHandler
DB_PATH = "db/customize.db"

class ServerProfileModal(Modal, title='🤖 Bot Server Profile'):
    def __init__(self, setting_type: str):
        super().__init__()
        self.setting_type = setting_type
        
        if setting_type == "avatar":
            self.url_input = TextInput(
                label='Bot Avatar URL',
                placeholder='Enter image URL for the bot avatar in this server',
                max_length=500,
                style=discord.TextStyle.short
            )
        elif setting_type == "banner":
            self.url_input = TextInput(
                label='Bot Banner URL', 
                placeholder='Enter image URL for the bot banner in this server',
                max_length=500,
                style=discord.TextStyle.short
            )
        
        self.add_item(self.url_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        url = self.url_input.value.strip()
        
        if not url.startswith(('http://', 'https://')):
            embed = discord.Embed(
                title="❌ Invalid URL",
                description="Please provide a valid image URL starting with http:// or https://",
                color=0xFF0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        try:
            # Download and validate the image
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        await interaction.response.send_message(
                            embed=discord.Embed(
                                title="❌ Error",
                                description="Could not download image from the provided URL",
                                color=0xFF0000
                            ), ephemeral=True
                        )
                        return
                    
                    # Check if it's an image
                    content_type = resp.headers.get('content-type', '')
                    if not content_type.startswith('image/'):
                        await interaction.response.send_message(
                            embed=discord.Embed(
                                title="❌ Invalid File Type",
                                description="The URL must point to an image file (PNG, JPG, GIF, etc.)",
                                color=0xFF0000
                            ), ephemeral=True
                        )
                        return
                    
                    image_data = await resp.read()
                    
                    # Check file size (Discord limits)
                    if len(image_data) > 8 * 1024 * 1024:  # 8MB limit
                        await interaction.response.send_message(
                            embed=discord.Embed(
                                title="❌ File Too Large",
                                description="Image must be smaller than 8MB",
                                color=0xFF0000
                            ), ephemeral=True
                        )
                        return
            
            # Apply the server profile change
            if self.setting_type == "avatar":
                # Check if guild and bot member exist
                if not interaction.guild:
                    await interaction.response.send_message(
                        embed=discord.Embed(
                            title="❌ Error",
                            description="This command can only be used in a server",
                            color=0xFF0000
                        ), ephemeral=True
                    )
                    return
                
                bot_member = interaction.guild.me
                if not bot_member:
                    await interaction.response.send_message(
                        embed=discord.Embed(
                            title="❌ Error", 
                            description="Bot member not found in this server",
                            color=0xFF0000
                        ), ephemeral=True
                    )
                    return
                
                # Use Discord's REST API for server-specific profile updates
                try:
                    # Prepare the data for the API call
                    import base64
                    
                    # Convert image data to base64
                    image_b64 = base64.b64encode(image_data).decode('utf-8')
                    
                    # Determine the image format
                    if url.lower().endswith('.png'):
                        mime_type = 'image/png'
                    elif url.lower().endswith('.gif'):
                        mime_type = 'image/gif'
                    elif url.lower().endswith(('.jpg', '.jpeg')):
                        mime_type = 'image/jpeg'
                    else:
                        # Try to detect from content-type header if available
                        async with aiohttp.ClientSession() as session:
                            async with session.head(url) as resp:
                                content_type = resp.headers.get('content-type', 'image/png')
                                mime_type = content_type
                    
                    data_uri = f"data:{mime_type};base64,{image_b64}"
                    
                    # Use the bot's http client to make the API call
                    from discord.http import Route
                    route = Route(
                        'PATCH', 
                        '/guilds/{guild_id}/members/@me',
                        guild_id=interaction.guild.id
                    )
                    await interaction.client.http.request(
                        route,
                        json={'avatar': data_uri},
                        reason=f"Server avatar updated by {interaction.user}"
                    )
                    
                    success_embed = discord.Embed(
                        title="✅ Avatar Updated!",
                        description=f"Successfully updated the bot's avatar for **{interaction.guild.name}**!",
                        color=0x20b2aa  # Teal theme
                    )
                    success_embed.set_thumbnail(url=url)
                    success_embed.add_field(
                        name="📝 Note",
                        value="This change only affects this server. The bot's global avatar remains unchanged.",
                        inline=False
                    )
                    await interaction.response.send_message(embed=success_embed, ephemeral=True)
                    
                except discord.HTTPException as e:
                    if "50035" in str(e):  # Invalid image format
                        await interaction.response.send_message(
                            embed=discord.Embed(
                                title="❌ Format Error",
                                description="The image format is not supported. Please use PNG, JPG, or GIF.",
                                color=0xFF0000
                            ), ephemeral=True
                        )
                    elif "40005" in str(e):  # Request entity too large
                        await interaction.response.send_message(
                            embed=discord.Embed(
                                title="❌ File Too Large",
                                description="The image file is too large. Please use an image under 8MB.",
                                color=0xFF0000
                            ), ephemeral=True
                        )
                    else:
                        await interaction.response.send_message(
                            embed=discord.Embed(
                                title="❌ Discord Error",
                                description=f"Discord API error: {str(e)}",
                                color=0xFF0000
                            ), ephemeral=True
                        )
                except Exception as e:
                    await interaction.response.send_message(
                        embed=discord.Embed(
                            title="❌ Error",
                            description=f"Failed to update avatar: {str(e)}",
                            color=0xFF0000
                        ), ephemeral=True
                    )
                
            elif self.setting_type == "banner":
                # Set server-specific banner using the Discord API
                try:
                    if not interaction.guild:
                        await interaction.response.send_message(
                            embed=discord.Embed(
                                title="❌ Error",
                                description="This command can only be used in a server",
                                color=0xFF0000
                            ), ephemeral=True
                        )
                        return
                    
                    bot_member = interaction.guild.me
                    if not bot_member:
                        await interaction.response.send_message(
                            embed=discord.Embed(
                                title="❌ Error", 
                                description="Bot member not found in this server",
                                color=0xFF0000
                            ), ephemeral=True
                        )
                        return
                    
                    # Prepare the data for the API call
                    import base64
                    
                    # Convert image data to base64
                    image_b64 = base64.b64encode(image_data).decode('utf-8')
                    
                    # Determine the image format
                    if url.lower().endswith('.png'):
                        mime_type = 'image/png'
                    elif url.lower().endswith('.gif'):
                        mime_type = 'image/gif'
                    elif url.lower().endswith(('.jpg', '.jpeg')):
                        mime_type = 'image/jpeg'
                    else:
                        # Try to detect from content-type header if available
                        async with aiohttp.ClientSession() as session:
                            async with session.head(url) as resp:
                                content_type = resp.headers.get('content-type', 'image/png')
                                mime_type = content_type
                    
                    data_uri = f"data:{mime_type};base64,{image_b64}"
                    
                    # Use the bot's http client to make the API call
                    from discord.http import Route
                    route = Route(
                        'PATCH', 
                        '/guilds/{guild_id}/members/@me',
                        guild_id=interaction.guild.id
                    )
                    await interaction.client.http.request(
                        route,
                        json={'banner': data_uri},
                        reason=f"Server banner updated by {interaction.user}"
                    )
                    
                    success_embed = discord.Embed(
                        title="✅ Banner Updated!",
                        description=f"Successfully updated the bot's banner for **{interaction.guild.name}**!",
                        color=0x20b2aa  # Teal theme
                    )
                    success_embed.set_image(url=url)
                    success_embed.add_field(
                        name="📝 Note",
                        value="This change only affects this server. The bot's global banner remains unchanged.",
                        inline=False
                    )
                    await interaction.response.send_message(embed=success_embed, ephemeral=True)
                    
                except discord.HTTPException as e:
                    if "50035" in str(e):  # Invalid image format
                        await interaction.response.send_message(
                            embed=discord.Embed(
                                title="❌ Format Error",
                                description="The image format is not supported. Please use PNG, JPG, or GIF.",
                                color=0xFF0000
                            ), ephemeral=True
                        )
                    elif "40005" in str(e):  # Request entity too large
                        await interaction.response.send_message(
                            embed=discord.Embed(
                                title="❌ File Too Large",
                                description="The image file is too large. Please use an image under 8MB.",
                                color=0xFF0000
                            ), ephemeral=True
                        )
                    else:
                        await interaction.response.send_message(
                            embed=discord.Embed(
                                title="❌ Discord Error",
                                description=f"Discord API error: {str(e)}",
                                color=0xFF0000
                            ), ephemeral=True
                        )
                except Exception as e:
                    await interaction.response.send_message(
                        embed=discord.Embed(
                            title="❌ Error",
                            description=f"Failed to update banner: {str(e)}",
                            color=0xFF0000
                        ), ephemeral=True
                    )
            
        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Permission Error",
                description="I don't have permission to change my server profile. Please check bot permissions.",
                color=0xFF0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"An error occurred: {str(e)}",
                color=0xFF0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

class ServerCustomizeSelect(Select):
    def __init__(self, ctx: Context):
        self.ctx = ctx
        
        options = [
            discord.SelectOption(
                label="Set Server Avatar",
                description="Change the bot's avatar for this server only",
                emoji="🤖",
                value="avatar"
            ),
            discord.SelectOption(
                label="Set Server Banner", 
                description="Change the bot's banner for this server only",
                emoji="🎨",
                value="banner"
            )
        ]
        
        super().__init__(
            placeholder="Choose what to customize...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"Only **{self.ctx.author}** can use this command.",
                    color=0xFF0000
                ), 
                ephemeral=True
            )
            return
        
        # Additional permission check for server owner or administrator
        if not isinstance(interaction.user, discord.Member) or not interaction.guild:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Error",
                    description="This feature can only be used by server members.",
                    color=0xFF0000
                ), 
                ephemeral=True
            )
            return
            
        if not (interaction.user.guild_permissions.administrator or interaction.user.id == interaction.guild.owner_id):
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Insufficient Permissions",
                    description="This feature can only be used by the **server owner** or users with **administrator** permissions.",
                    color=0xFF0000
                ), 
                ephemeral=True
            )
            return

        modal = ServerProfileModal(self.values[0])
        await interaction.response.send_modal(modal)


class CustomizeButtonHandler(discord.ui.View):
    """Persistent view to handle customize button interactions from LayoutView."""
    
    def __init__(self):
        super().__init__(timeout=None)  # Persistent view
    
    def _check_permissions(self, interaction: discord.Interaction) -> Optional[discord.Embed]:
        """Check if user has required permissions. Returns error embed if not."""
        if not isinstance(interaction.user, discord.Member) or not interaction.guild:
            return discord.Embed(
                title="❌ Error",
                description="This can only be used in a server.",
                color=0xFF0000
            )
        
        if not (interaction.user.guild_permissions.administrator or interaction.user.id == interaction.guild.owner_id):
            return discord.Embed(
                title="❌ Insufficient Permissions",
                description="Requires **Server Owner** or **Administrator** permissions.",
                color=0xFF0000
            )
        
        return None
    
    def _extract_author_id(self, custom_id: str) -> Optional[int]:
        """Extract author ID from custom_id pattern: customize_action_authorid"""
        try:
            parts = custom_id.split("_")
            if len(parts) >= 3:
                return int(parts[2])
        except:
            pass
        return None
    
    async def _check_author(self, interaction: discord.Interaction, custom_id: str) -> bool:
        """Check if user is the command author based on custom_id."""
        author_id = self._extract_author_id(custom_id)
        if author_id and interaction.user.id != author_id:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"Only <@{author_id}> can use this.",
                    color=0xFF0000
                ), 
                ephemeral=True
            )
            return False
        return True
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Global check for all button interactions."""
        # Check if custom_id matches our pattern
        if not interaction.data or 'custom_id' not in interaction.data:
            return False
        
        custom_id = interaction.data['custom_id']
        
        # Only handle customize_* buttons
        if not custom_id.startswith('customize_'):
            return False
        
        # Check author
        if not await self._check_author(interaction, custom_id):
            return False
        
        return True
    
    @discord.ui.button(label="Change Avatar", emoji="🤖", style=discord.ButtonStyle.primary, custom_id="customize_avatar_placeholder", row=0)
    async def set_avatar(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal to change server avatar."""
        error = self._check_permissions(interaction)
        if error:
            await interaction.response.send_message(embed=error, ephemeral=True)
            return
        
        await interaction.response.send_modal(ServerProfileModal("avatar"))
    
    @discord.ui.button(label="Change Banner", emoji="🎨", style=discord.ButtonStyle.primary, custom_id="customize_banner_placeholder", row=0)
    async def set_banner(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal to change server banner."""
        error = self._check_permissions(interaction)
        if error:
            await interaction.response.send_message(embed=error, ephemeral=True)
            return
        
        await interaction.response.send_modal(ServerProfileModal("banner"))
    
    @discord.ui.button(label="Reset Profile", emoji="🔄", style=discord.ButtonStyle.secondary, custom_id="customize_reset_placeholder", row=1)
    async def reset_profile(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Reset server profile to global profile."""
        if not interaction.guild:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Error",
                    description="This can only be used in a server.",
                    color=0xFF0000
                ), 
                ephemeral=True
            )
            return
        
        try:
            from discord.http import Route
            route = Route('PATCH', '/guilds/{guild_id}/members/@me', guild_id=interaction.guild.id)
            
            await interaction.client.http.request(
                route,
                json={'avatar': None, 'banner': None},
                reason=f"Server profile reset by {interaction.user}"
            )
            
            embed = discord.Embed(
                title="✅ Profile Reset",
                description=f"Bot will now use global profile in **{interaction.guild.name}**.",
                color=0x20b2aa
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Permission Error",
                    description="I don't have permission to change my server profile.",
                    color=0xFF0000
                ), 
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Error",
                    description=f"Failed to reset profile: {str(e)}",
                    color=0xFF0000
                ), 
                ephemeral=True
            )
    
    @discord.ui.button(label="View Profile", emoji="👁️", style=discord.ButtonStyle.secondary, custom_id="customize_view_placeholder", row=1)
    async def view_profile(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Display current server profile."""
        if not interaction.guild:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Error",
                    description="This can only be used in a server.",
                    color=0xFF0000
                ), 
                ephemeral=True
            )
            return
        
        bot_member = interaction.guild.me
        bot_user = interaction.client.user
        
        embed = discord.Embed(
            title="🤖 Current Bot Profile",
            description=f"**{interaction.guild.name}**",
            color=0x20b2aa
        )
        
        # Show current avatar
        if bot_member and bot_member.avatar:
            embed.set_thumbnail(url=bot_member.avatar.url)
            embed.add_field(name="🤖 Avatar", value="Custom", inline=True)
        else:
            if bot_user and bot_user.avatar:
                embed.set_thumbnail(url=bot_user.avatar.url)
            embed.add_field(name="🤖 Avatar", value="Global", inline=True)
        
        # Show current banner
        if bot_member and bot_member.banner:
            embed.set_image(url=bot_member.banner.url)
            embed.add_field(name="🎨 Banner", value="Custom", inline=True)
        else:
            embed.add_field(name="🎨 Banner", value="None", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class customize(commands.Cog):
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, client):
        self.client = client
    
    @commands.hybrid_command(
        name="customize",
        description="Customize the bot's server-specific profile (avatar & banner)"
    )
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 10, commands.BucketType.guild)
    async def customize_command(self, ctx: Context):
        """
        Customize the bot's server-specific profile using Discord's new server customization feature
        
        This command allows server owners and administrators to:
        - Set a custom avatar for the bot in this server only
        - Set a custom banner for the bot in this server only
        - Reset to global profile
        - View current server profile
        
        Note: This uses Discord's new server profile feature and only affects this server.
        Requires: Server Owner or Administrator permissions
        """
        
        # Additional check for server owner or administrator
        if not isinstance(ctx.author, discord.Member) or not ctx.guild:
            embed = discord.Embed(
                title="❌ Error",
                description="This command can only be used by server members.",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
            
        if not (ctx.author.guild_permissions.administrator or ctx.author.id == ctx.guild.owner_id):
            embed = discord.Embed(
                title="❌ Insufficient Permissions",
                description="This command can only be used by the **server owner** or users with **administrator** permissions.",
                color=0xFF0000
            )
            embed.add_field(
                name="Required Permissions",
                value="• Server Owner\n• Administrator",
                inline=False
            )
            await ctx.send(embed=embed)
            return
        
        # Components v2 - LayoutView with Container (embed-like wrapped UI)
        from discord.ui import LayoutView, Container, TextDisplay, Separator, ActionRow
        
        # Build all container items
        container_items = []
        
        # Header
        header = TextDisplay(
            f"🤖 **Customize Bot Profile**\n\n"
            f"Change the bot's **profile picture** and **banner** for this server."
        )
        container_items.append(header)
        
        # Separator
        container_items.append(Separator())
        
        # Button guide
        guide = TextDisplay(
            f"**Available Actions**\n"
            f"🤖 — Change server avatar\n"
            f"🎨 — Change server banner\n"
            f"🔄 — Reset to global profile\n"
            f"👁️ — View current profile"
        )
        container_items.append(guide)
        
        # Separator before buttons
        container_items.append(Separator())
        
        # Action Row 1: Avatar and Banner buttons
        row1 = ActionRow(
            discord.ui.Button(
                emoji="🤖",
                label="Change Avatar",
                style=discord.ButtonStyle.primary,
                custom_id=f"customize_avatar_{ctx.author.id}"
            ),
            discord.ui.Button(
                emoji="🎨",
                label="Change Banner",
                style=discord.ButtonStyle.primary,
                custom_id=f"customize_banner_{ctx.author.id}"
            )
        )
        container_items.append(row1)
        
        # Action Row 2: Reset and View buttons
        row2 = ActionRow(
            discord.ui.Button(
                emoji="🔄",
                label="Reset Profile",
                style=discord.ButtonStyle.secondary,
                custom_id=f"customize_reset_{ctx.author.id}"
            ),
            discord.ui.Button(
                emoji="👁️",
                label="View Profile",
                style=discord.ButtonStyle.secondary,
                custom_id=f"customize_view_{ctx.author.id}"
            )
        )
        container_items.append(row2)
        
        # Wrap everything in Container
        container = Container(
            *container_items,
            accent_color=discord.Color.from_rgb(32, 178, 170)  # Teal
        )
        
        # Create LayoutView and add container
        layout = LayoutView()
        layout.add_item(container)
        
        # Send with Components v2 LayoutView
        await ctx.send(view=layout)

# Setup function
async def setup(bot):
    # Register persistent view for button interactions
    bot.add_view(CustomizeButtonHandler())
    await bot.add_cog(customize(bot))

"""
@Author: Frosty
    + Discord: frosty.pyro
    + Community: https://discord.gg/5wtjDkYbVh (Sleepless Development)
    + for any queries reach out in the server; or send a dm.
"""