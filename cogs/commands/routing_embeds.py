import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
import asyncio
from utils.Tools import *

from utils.error_helpers import StandardErrorHandler
class LinkButtonModal(Modal):
    """Modal for creating link buttons"""
    
    def __init__(self, embed_builder):
        super().__init__(title="Add Link Button")
        self.embed_builder = embed_builder
        
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
        if not (self.url.value.startswith('http://') or self.url.value.startswith('https://')):
            await interaction.response.send_message("❌ Invalid URL! Must start with http:// or https://", ephemeral=True)
            return
            
        button_data = {
            'label': self.label.value,
            'url': self.url.value,
            'emoji': self.emoji.value if self.emoji.value else None,
            'style': discord.ButtonStyle.link
        }
        
        await self.embed_builder.add_button(interaction, button_data)

class EnhancedEmbedBuilder:
    """Enhanced embed builder with routing buttons"""
    
    def __init__(self, ctx):
        self.ctx = ctx
        self.embed_data = {
            'title': None,
            'description': None,
            'color': 0x5865F2,
            'footer': None,
            'thumbnail': None,
            'image': None,
            'buttons': []
        }
        
    async def add_button(self, interaction: discord.Interaction, button_data: dict):
        if len(self.embed_data['buttons']) >= 25:
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
        embed = discord.Embed(
            title=self.embed_data['title'] or "Enhanced Embed with Routing Buttons",
            description=self.embed_data['description'] or "Use the buttons below to navigate to different links!",
            color=self.embed_data['color']
        )
        
        if self.embed_data['footer']:
            embed.set_footer(text=self.embed_data['footer'])
        if self.embed_data['thumbnail']:
            embed.set_thumbnail(url=self.embed_data['thumbnail'])
        if self.embed_data['image']:
            embed.set_image(url=self.embed_data['image'])
            
        return embed
        
    def create_button_view(self):
        if not self.embed_data['buttons']:
            return None
            
        view = View(timeout=None)
        
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
        
    @commands.hybrid_command(name="routing-embed", aliases=["rembeds", "linkembed"])
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_messages=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def routing_embed(self, ctx):
        """Create embeds with routing buttons like Mimu bot"""
        
        builder = EnhancedEmbedBuilder(ctx)
        
        setup_embed = discord.Embed(
            title="🚀 Enhanced Embed Builder with Routing Buttons",
            description="Create professional embeds with navigation buttons!\n\n"
                       "**Features like Mimu bot:**\n"
                       "• Link buttons for websites and servers\n"
                       "• Professional routing capabilities\n"
                       "• Custom buttons for any URL\n"
                       "• Persistent buttons that work forever",
            color=0x5865F2
        )
        
        class MainView(View):
            def __init__(self):
                super().__init__(timeout=600)
                
            @discord.ui.button(label="Add Custom Button", emoji="🔗", style=discord.ButtonStyle.primary, row=0)
            async def add_button(self, interaction: discord.Interaction, button: Button):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("❌ Only the command author can use this!", ephemeral=True)
                    return
                    
                modal = LinkButtonModal(builder)
                await interaction.response.send_modal(modal)
                
            @discord.ui.button(label="Quick Discord Server", emoji="🔗", style=discord.ButtonStyle.secondary, row=0)
            async def discord_server(self, interaction: discord.Interaction, button: Button):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("❌ Only the command author can use this!", ephemeral=True)
                    return
                
                class ServerModal(Modal):
                    def __init__(self):
                        super().__init__(title="Add Discord Server Button")
                        
                    invite_url = TextInput(
                        label="Discord Server Invite URL",
                        placeholder="https://discord.gg/yourserver",
                        required=True
                    )
                        
                    async def on_submit(self, modal_interaction: discord.Interaction):
                        button_data = {
                            'label': 'Join Our Discord',
                            'url': self.invite_url.value,
                            'emoji': '🔗',
                            'style': discord.ButtonStyle.link
                        }
                        await builder.add_button(modal_interaction, button_data)
                
                modal = ServerModal()
                await interaction.response.send_modal(modal)
                
            @discord.ui.button(label="Edit Embed Content", emoji="✏️", style=discord.ButtonStyle.secondary, row=1)
            async def edit_content(self, interaction: discord.Interaction, button: Button):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("❌ Only the command author can use this!", ephemeral=True)
                    return
                
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
                
                if view:
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
                
            @discord.ui.button(label="Send to Channel", emoji="📤", style=discord.ButtonStyle.success, row=2)
            async def send_embed(self, interaction: discord.Interaction, button: Button):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("❌ Only the command author can use this!", ephemeral=True)
                    return
                    
                embed = builder.create_embed()
                view = builder.create_button_view()
                
                # Send to channel
                if view:
                    await ctx.send(embed=embed, view=view)
                else:
                    await ctx.send(embed=embed)
                
                success_embed = discord.Embed(
                    title="✅ Embed Sent Successfully!",
                    description="Your enhanced embed with routing buttons has been sent to the channel!",
                    color=0x00ff00
                )
                await interaction.response.send_message(embed=success_embed, ephemeral=True)
                
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
            title="🏠 Server Navigation Hub",
            description="Welcome to our community! Use the buttons below to navigate quickly:",
            color=0x5865F2
        )
        
        hub_view = View(timeout=None)
        hub_view.add_item(Button(label="Server Rules", url="https://discord.com/guidelines", emoji="📜", style=discord.ButtonStyle.link))
        hub_view.add_item(Button(label="Get Support", url="https://discord.gg/discord-support", emoji="🎫", style=discord.ButtonStyle.link))
        hub_view.add_item(Button(label="Invite Bot", url="https://discord.com/oauth2/authorize?client_id=1414317652066832527&permissions=8&integration_type=0&scope=bot+applications.commands", emoji="🤖", style=discord.ButtonStyle.link))
        
        await ctx.send("**Example 1: Server Navigation Hub (Like Mimu Bot)**", embed=hub_embed, view=hub_view)
        
        # Example 2: Social Media Hub
        social_embed = discord.Embed(
            title="📱 Connect With Us",
            description="Follow us on all platforms and stay updated with the latest news!",
            color=0xFF1493
        )
        
        social_view = View(timeout=None)
        social_view.add_item(Button(label="Discord Community", url="https://discord.gg/5wtjDkYbVh", emoji="🔗", style=discord.ButtonStyle.link))
        social_view.add_item(Button(label="Website", url="https://sleepless.dev", emoji="🌐", style=discord.ButtonStyle.link))
        social_view.add_item(Button(label="Support Development", url="https://ko-fi.com/sleepless", emoji="💖", style=discord.ButtonStyle.link))
        
        await ctx.send("**Example 2: Social Media & Links Hub**", embed=social_embed, view=social_view)

async def setup(bot):
    await bot.add_cog(EnhancedEmbeds(bot))