import discord
from discord.ext import commands
from discord.ui import View, Button, Select, Modal, TextInput
import asyncio
import aiosqlite
import json
from utils.Tools import *

from utils.error_helpers import StandardErrorHandler
class LinkButtonModal(Modal):
    """Modal for creating link buttons with better UX"""
    
    def __init__(self, callback_func):
        super().__init__(title="Add Link Button")
        self.callback_func = callback_func
        
    label = TextInput(
        label="Button Label",
        placeholder="e.g., Visit Website, Join Server, etc.",
        max_length=80,
        required=True
    )
    
    url = TextInput(
        label="Button URL",
        placeholder="https://example.com",
        max_length=512,
        required=True
    )
    
    emoji = TextInput(
        label="Button Emoji (optional)",
        placeholder="🔗",
        max_length=20,
        required=False
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        # Validate URL
        if not (self.url.value.startswith('http://') or self.url.value.startswith('https://')):
            await interaction.response.send_message("❌ Invalid URL! Must start with http:// or https://", ephemeral=True)
            return
            
        button_data = {
            'label': self.label.value,
            'url': self.url.value,
            'emoji': self.emoji.value if self.emoji.value else None,
            'style': discord.ButtonStyle.link
        }
        
        await self.callback_func(interaction, button_data)

class QuickLinksView(View):
    """Pre-built quick links for common use cases"""
    
    def __init__(self, user_id, embed_builder):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.embed_builder = embed_builder
        
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id
        
    @discord.ui.button(label="Discord Server", emoji="<:discord:1400000000000000000>", style=discord.ButtonStyle.secondary, row=0)
    async def discord_server(self, interaction: discord.Interaction, button: Button):
        modal = TextInput(
            label="Discord Server Invite URL",
            placeholder="https://discord.gg/yourserver",
            required=True
        )
        
        class ServerModal(Modal):
            def __init__(self, embed_builder):
                super().__init__(title="Add Discord Server Link")
                self.embed_builder = embed_builder
                self.add_item(modal)
                
            async def on_submit(self, modal_interaction: discord.Interaction):
                button_data = {
                    'label': 'Join Our Discord',
                    'url': modal.value,
                    'emoji': '🔗',
                    'style': discord.ButtonStyle.link
                }
                await self.embed_builder.add_button(modal_interaction, button_data)
        
        await interaction.response.send_modal(ServerModal(self.embed_builder))
        
    @discord.ui.button(label="Website", emoji="🌐", style=discord.ButtonStyle.secondary, row=0)
    async def website(self, interaction: discord.Interaction, button: Button):
        modal = LinkButtonModal(self.embed_builder.add_button)
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label="Support/Donate", emoji="💖", style=discord.ButtonStyle.secondary, row=0)
    async def support(self, interaction: discord.Interaction, button: Button):
        modal = TextInput(
            label="Support/Donation URL",
            placeholder="https://paypal.me/yourlink or https://ko-fi.com/yourname",
            required=True
        )
        
        class SupportModal(Modal):
            def __init__(self, embed_builder):
                super().__init__(title="Add Support Link")
                self.embed_builder = embed_builder
                self.add_item(modal)
                
            async def on_submit(self, modal_interaction: discord.Interaction):
                button_data = {
                    'label': 'Support Us',
                    'url': modal.value,
                    'emoji': '💖',
                    'style': discord.ButtonStyle.link
                }
                await self.embed_builder.add_button(modal_interaction, button_data)
        
        await interaction.response.send_modal(SupportModal(self.embed_builder))
        
    @discord.ui.button(label="Social Media", emoji="📱", style=discord.ButtonStyle.secondary, row=1)
    async def social_media(self, interaction: discord.Interaction, button: Button):
        # Create a dropdown for different social media platforms
        options = [
            discord.SelectOption(label="Twitter/X", emoji="🐦", value="twitter"),
            discord.SelectOption(label="Instagram", emoji="📸", value="instagram"), 
            discord.SelectOption(label="YouTube", emoji="📺", value="youtube"),
            discord.SelectOption(label="TikTok", emoji="🎵", value="tiktok"),
            discord.SelectOption(label="Twitch", emoji="🎮", value="twitch"),
            discord.SelectOption(label="Custom", emoji="🔗", value="custom")
        ]
        
        select = Select(placeholder="Choose a social media platform", options=options)
        
        async def social_callback(interaction):
            platform = select.values[0]
            
            platform_info = {
                'twitter': ('Follow on Twitter', '🐦'),
                'instagram': ('Follow on Instagram', '📸'),
                'youtube': ('Subscribe on YouTube', '📺'),
                'tiktok': ('Follow on TikTok', '🎵'),
                'twitch': ('Follow on Twitch', '🎮'),
                'custom': ('Custom Social Link', '📱')
            }
            
            label, emoji = platform_info[platform]
            
            url_input = TextInput(
                label=f"{platform.title()} URL",
                placeholder=f"https://{platform}.com/yourusername",
                required=True
            )
            
            class SocialModal(Modal):
                def __init__(self, embed_builder):
                    super().__init__(title=f"Add {platform.title()} Link")
                    self.embed_builder = embed_builder
                    self.add_item(url_input)
                    
                async def on_submit(self, modal_interaction: discord.Interaction):
                    button_data = {
                        'label': label,
                        'url': url_input.value,
                        'emoji': emoji,
                        'style': discord.ButtonStyle.link
                    }
                    await self.embed_builder.add_button(modal_interaction, button_data)
            
            await interaction.response.send_modal(SocialModal(self.embed_builder))
        
        select.callback = social_callback
        view = View()
        view.add_item(select)
        
        await interaction.response.send_message("Choose a social media platform:", view=view, ephemeral=True)
        
    @discord.ui.button(label="Custom Link", emoji="🔗", style=discord.ButtonStyle.primary, row=1)
    async def custom_link(self, interaction: discord.Interaction, button: Button):
        modal = LinkButtonModal(self.embed_builder.add_button)
        await interaction.response.send_modal(modal)

class EnhancedEmbedBuilder:
    """Enhanced embed builder with better routing and navigation buttons"""
    
    def __init__(self, ctx):
        self.ctx = ctx
        self.embed_data = {
            'title': None,
            'description': None,
            'color': 0x5865F2,
            'footer': None,
            'thumbnail': None,
            'image': None,
            'author': None,
            'fields': [],
            'buttons': []
        }
        
    async def add_button(self, interaction: discord.Interaction, button_data: dict):
        """Add a button to the embed"""
        if len(self.embed_data['buttons']) >= 25:  # Discord's limit
            await interaction.response.send_message("❌ Maximum of 25 buttons allowed!", ephemeral=True)
            return
            
        self.embed_data['buttons'].append(button_data)
        
        embed = discord.Embed(
            title="✅ Button Added Successfully!",
            description=f"**Label:** {button_data['label']}\n**URL:** {button_data['url']}",
            color=0x00ff00
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    def create_embed(self):
        """Create the actual embed with current data"""
        embed = discord.Embed(
            title=self.embed_data['title'] or "Example Embed",
            description=self.embed_data['description'] or "This is an example embed with routing buttons!",
            color=self.embed_data['color']
        )
        
        if self.embed_data['author']:
            embed.set_author(name=self.embed_data['author'])
        if self.embed_data['footer']:
            embed.set_footer(text=self.embed_data['footer'])
        if self.embed_data['thumbnail']:
            embed.set_thumbnail(url=self.embed_data['thumbnail'])
        if self.embed_data['image']:
            embed.set_image(url=self.embed_data['image'])
            
        for field in self.embed_data['fields']:
            embed.add_field(
                name=field['name'],
                value=field['value'],
                inline=field.get('inline', False)
            )
            
        return embed
        
    def create_button_view(self):
        """Create the view with all the routing buttons"""
        view = View(timeout=None)  # Persistent view
        
        for button_data in self.embed_data['buttons']:
            button = Button(
                label=button_data['label'],
                url=button_data['url'],
                emoji=button_data.get('emoji'),
                style=button_data['style']
            )
            view.add_item(button)
            
        return view

class EnhancedEmbeds(commands.Cog):
    """Enhanced embed system with routing buttons like Mimu bot"""
    
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot
        
    @commands.hybrid_command(name="enhanced-embed", aliases=["eembed", "routing-embed"])
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_messages=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def enhanced_embed(self, ctx):
        """Create embeds with enhanced routing buttons like Mimu bot"""
        
        builder = EnhancedEmbedBuilder(ctx)
        
        # Main setup embed
        setup_embed = discord.Embed(
            title="🚀 Enhanced Embed Builder",
            description="Create professional embeds with routing buttons!\n\n"
                       "**Features:**\n"
                       "• Link buttons for websites, social media, Discord servers\n"
                       "• Pre-built templates for common use cases\n"
                       "• Professional appearance like Mimu bot\n"
                       "• Persistent buttons that work forever",
            color=0x5865F2
        )
        
        # Main control view
        class MainView(View):
            def __init__(self):
                super().__init__(timeout=600)
                
            @discord.ui.button(label="Quick Links", emoji="⚡", style=discord.ButtonStyle.primary, row=0)
            async def quick_links(self, interaction: discord.Interaction, button: Button):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("❌ Only the command author can use this!", ephemeral=True)
                    return
                    
                quick_view = QuickLinksView(ctx.author.id, builder)
                
                embed = discord.Embed(
                    title="⚡ Quick Link Buttons",
                    description="Choose from pre-made button templates for common links:",
                    color=0x5865F2
                )
                
                await interaction.response.send_message(embed=embed, view=quick_view, ephemeral=True)
                
            @discord.ui.button(label="Custom Button", emoji="🔗", style=discord.ButtonStyle.secondary, row=0)
            async def custom_button(self, interaction: discord.Interaction, button: Button):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("❌ Only the command author can use this!", ephemeral=True)
                    return
                    
                modal = LinkButtonModal(builder.add_button)
                await interaction.response.send_modal(modal)
                
            @discord.ui.button(label="Edit Embed Content", emoji="✏️", style=discord.ButtonStyle.secondary, row=0)
            async def edit_content(self, interaction: discord.Interaction, button: Button):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("❌ Only the command author can use this!", ephemeral=True)
                    return
                
                # Create modal for editing embed content
                class ContentModal(Modal):
                    def __init__(self):
                        super().__init__(title="Edit Embed Content")
                        
                    title_input = TextInput(
                        label="Embed Title",
                        placeholder="Enter embed title...",
                        required=False,
                        max_length=256
                    )
                    
                    description_input = TextInput(
                        label="Embed Description", 
                        placeholder="Enter embed description...",
                        style=discord.TextStyle.paragraph,
                        required=False,
                        max_length=4000
                    )
                    
                    footer_input = TextInput(
                        label="Footer Text (optional)",
                        placeholder="Footer text...",
                        required=False,
                        max_length=2048
                    )
                    
                    async def on_submit(self, modal_interaction: discord.Interaction):
                        if self.title_input.value:
                            builder.embed_data['title'] = self.title_input.value
                        if self.description_input.value:
                            builder.embed_data['description'] = self.description_input.value
                        if self.footer_input.value:
                            builder.embed_data['footer'] = self.footer_input.value
                            
                        embed = discord.Embed(
                            title="✅ Embed Content Updated!",
                            description="Your embed content has been updated successfully.",
                            color=0x00ff00
                        )
                        await modal_interaction.response.send_message(embed=embed, ephemeral=True)
                
                modal = ContentModal()
                await interaction.response.send_modal(modal)
                
            @discord.ui.button(label="Preview", emoji="👀", style=discord.ButtonStyle.success, row=1)
            async def preview(self, interaction: discord.Interaction, button: Button):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("❌ Only the command author can use this!", ephemeral=True)
                    return
                    
                embed = builder.create_embed()
                view = builder.create_button_view()
                
                if view and builder.embed_data['buttons']:
                    await interaction.response.send_message(
                        "**🔍 Preview of your embed:**", 
                        embed=embed, 
                        view=view,
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        "**🔍 Preview of your embed:**", 
                        embed=embed,
                        ephemeral=True
                    )
                
            @discord.ui.button(label="Send to Channel", emoji="📤", style=discord.ButtonStyle.success, row=1)
            async def send_embed(self, interaction: discord.Interaction, button: Button):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("❌ Only the command author can use this!", ephemeral=True)
                    return
                    
                embed = builder.create_embed()
                view = builder.create_button_view()
                
                # Send to channel
                await ctx.send(embed=embed, view=view if builder.embed_data['buttons'] else None)
                
                success_embed = discord.Embed(
                    title="✅ Embed Sent Successfully!",
                    description="Your enhanced embed with routing buttons has been sent to the channel!",
                    color=0x00ff00
                )
                await interaction.response.send_message(embed=success_embed, ephemeral=True)
                
            @discord.ui.button(label="Templates", emoji="📋", style=discord.ButtonStyle.secondary, row=2)
            async def templates(self, interaction: discord.Interaction, button: Button):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("❌ Only the command author can use this!", ephemeral=True)
                    return
                
                # Template selection
                templates = [
                    {
                        'name': 'Server Info',
                        'title': f'Welcome to {ctx.guild.name}!',
                        'description': 'Join our community and stay connected!',
                        'buttons': [
                            {'label': 'Rules', 'url': 'https://discord.com', 'emoji': '📜'},
                            {'label': 'Support', 'url': 'https://discord.com', 'emoji': '🎫'}
                        ]
                    },
                    {
                        'name': 'Social Media Hub',
                        'title': 'Follow Us Everywhere!',
                        'description': 'Stay updated with our latest content across all platforms.',
                        'buttons': [
                            {'label': 'Twitter', 'url': 'https://twitter.com', 'emoji': '🐦'},
                            {'label': 'YouTube', 'url': 'https://youtube.com', 'emoji': '📺'},
                            {'label': 'Instagram', 'url': 'https://instagram.com', 'emoji': '📸'}
                        ]
                    }
                ]
                
                template_embed = discord.Embed(
                    title="📋 Embed Templates",
                    description="Choose a pre-made template to get started quickly:",
                    color=0x5865F2
                )
                
                for i, template in enumerate(templates):
                    template_embed.add_field(
                        name=f"{i+1}. {template['name']}",
                        value=template['description'][:100] + "...",
                        inline=False
                    )
                
                await interaction.response.send_message(embed=template_embed, ephemeral=True)
                
        main_view = MainView()
        
        await ctx.send(embed=setup_embed, view=main_view)

    @commands.hybrid_command(name="embed-examples")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def embed_examples(self, ctx):
        """Show examples of enhanced embeds with routing buttons"""
        
        # Example 1: Server Hub
        hub_embed = discord.Embed(
            title="🏠 Server Hub",
            description="Welcome to our community! Use the buttons below to navigate:",
            color=0x5865F2
        )
        
        hub_view = View(timeout=None)
        hub_view.add_item(Button(label="Rules", url="https://discord.com/guidelines", emoji="📜", style=discord.ButtonStyle.link))
        hub_view.add_item(Button(label="Support", url="https://discord.gg/discord-support", emoji="🎫", style=discord.ButtonStyle.link))
        hub_view.add_item(Button(label="Bot Invite", url="https://discord.com/oauth2/authorize?client_id=1414317652066832527&permissions=8&integration_type=0&scope=bot+applications.commands", emoji="🤖", style=discord.ButtonStyle.link))
        
        await ctx.send("**Example 1: Server Hub with Navigation Buttons**", embed=hub_embed, view=hub_view)
        
        # Example 2: Social Media Hub
        social_embed = discord.Embed(
            title="📱 Follow Us Everywhere!",
            description="Stay connected with our community across all platforms:",
            color=0xFF1493
        )
        
        social_view = View(timeout=None)
        social_view.add_item(Button(label="Discord Server", url="https://discord.gg/5wtjDkYbVh", emoji="<:discord:1400000000000000000>", style=discord.ButtonStyle.link))
        social_view.add_item(Button(label="Website", url="https://example.com", emoji="🌐", style=discord.ButtonStyle.link))
        social_view.add_item(Button(label="Support Us", url="https://ko-fi.com/example", emoji="💖", style=discord.ButtonStyle.link))
        
        await ctx.send("**Example 2: Social Media Hub**", embed=social_embed, view=social_view)

async def setup(bot):
    await bot.add_cog(EnhancedEmbeds(bot))