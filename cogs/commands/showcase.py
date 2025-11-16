import discord
from discord.ext import commands
from core import Context
from core.sleepless import sleepless
from core.Cog import Cog
from utils.Tools import *
from utils import Paginator, FieldPagePaginator
import asyncio

class ShowcaseView(discord.ui.View):
    def __init__(self, pages, user_id):
        super().__init__(timeout=300)
        self.pages = pages
        self.current_page = 0
        self.user_id = user_id
        self.max_page = len(pages) - 1
        
        # Update button states
        self.update_buttons()
    
    def update_buttons(self):
        # Update button states based on current page
        if hasattr(self, 'prev_button'):
            self.prev_button.disabled = self.current_page == 0
        if hasattr(self, 'next_button'):
            self.next_button.disabled = self.current_page == self.max_page
    
    @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("You can't interact with this menu.", ephemeral=True)
            return
        
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    @discord.ui.button(label="▶️ Next", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("You can't interact with this menu.", ephemeral=True)
            return
        
        if self.current_page < self.max_page:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    @discord.ui.button(label="🏠 Home", style=discord.ButtonStyle.primary)
    async def home_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("You can't interact with this menu.", ephemeral=True)
            return
        
        self.current_page = 0
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    @discord.ui.button(label="❌ Close", style=discord.ButtonStyle.danger)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("You can't interact with this menu.", ephemeral=True)
            return
        
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

class Showcase(Cog):
    def __init__(self, client: sleepless):
        self.client = client

    @commands.group(
        name="showcase", 
        aliases=["examples", "demo"],
        help="Showcase server setup examples and feature demonstrations"
    )
    @commands.cooldown(1, 5, commands.BucketType.user)
    @blacklist_check()
    @ignore_check()
    async def showcase(self, ctx: Context):
        """🌟 Showcase server setup examples and feature demonstrations"""
        if ctx.invoked_subcommand is None:
            await self.show_main_showcase(ctx)

    async def show_main_showcase(self, ctx: Context):
        """Display the main showcase menu"""
        
        # Main showcase page
        main_embed = discord.Embed(
            title="🌟 Sleepless Server Setup Showcase",
            description=(
                "**Welcome to the Sleepless Bot Showcase!**\n\n"
                "This showcase demonstrates various server setup configurations and "
                "shows you how to get the most out of Sleepless Bot's features.\n\n"
                "**📋 Available Showcases:**\n"
                f"• `{ctx.prefix}showcase quickstart` - Essential 3-step server setup\n"
                f"• `{ctx.prefix}showcase gaming` - Complete gaming server configuration\n"
                f"• `{ctx.prefix}showcase professional` - Business/professional server setup\n"
                f"• `{ctx.prefix}showcase music` - Advanced music features setup\n"
                f"• `{ctx.prefix}showcase security` - Comprehensive security configuration\n"
                f"• `{ctx.prefix}showcase community` - Community engagement features\n"
                f"• `{ctx.prefix}showcase troubleshoot` - Common solutions and fixes\n\n"
                "**💡 Quick Tips:**\n"
                "• Use the navigation buttons to explore different sections\n"
                "• Each showcase includes step-by-step setup instructions\n"
                "• Commands are ready to copy and paste\n"
                "• Ask in our support server if you need help!"
            ),
            color=0x185fe5
        )
        
        main_embed.add_field(
            name="🚀 Recent Features",
            value=(
                "🎵 **Enhanced Music System** - Multi-platform support\n"
                "🎭 **Improved Reaction Roles** - Interactive panels\n"
                "📊 **Last.fm Integration** - Music tracking\n"
                "🏆 **Global Leaderboard** - Cross-server stats\n"
                "🌐 **Enhanced IP Lookup** - Comprehensive info\n"
                "🤖 **Interactions System** - Advanced social features"
            ),
            inline=True
        )
        
        main_embed.add_field(
            name="🛠️ Popular Setups",
            value=(
                "🎮 Gaming servers with leveling\n"
                "🏢 Professional servers with tickets\n"
                "🎵 Music bots with playlists\n"
                "🔒 High-security servers\n"
                "👥 Community servers with events\n"
                "📊 Analytics and tracking"
            ),
            inline=True
        )
        
        main_embed.set_footer(
            text=f"Requested by {ctx.author} • Use subcommands to see specific showcases",
            icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
        )
        
        await ctx.reply(embed=main_embed)

    @showcase.command(name="quickstart", aliases=["quick", "start"])
    async def quickstart(self, ctx: Context):
        """Essential 3-step server setup guide"""
        
        pages = []
        
        # Page 1: Security Setup
        page1 = discord.Embed(
            title="🔒 Step 1: Security Foundation",
            description="**Start with security to protect your server**",
            color=0x185fe5
        )
        page1.add_field(
            name="🛡️ Enable AntiNuke Protection",
            value=(
                f"`{ctx.prefix}antinuke enable`\n"
                f"`{ctx.prefix}antinuke config`\n"
                f"`{ctx.prefix}antinuke whitelist @trusted_admin`"
            ),
            inline=False
        )
        page1.add_field(
            name="🚨 Basic Moderation",
            value=(
                f"`{ctx.prefix}automod enable`\n"
                f"`{ctx.prefix}automod spam on`\n"
                f"`{ctx.prefix}logging setup`"
            ),
            inline=False
        )
        page1.set_footer(text="Page 1/3 • Essential Security Setup")
        pages.append(page1)
        
        # Page 2: Member Experience
        page2 = discord.Embed(
            title="👋 Step 2: Member Experience",
            description="**Create a welcoming environment for new members**",
            color=0x185fe5
        )
        page2.add_field(
            name="🎉 Welcome System",
            value=(
                f"`{ctx.prefix}welcomer enable`\n"
                f"`{ctx.prefix}welcomer channel #general`\n"
                f"`{ctx.prefix}welcomer message Welcome {{user}} to {{server}}!`"
            ),
            inline=False
        )
        page2.add_field(
            name="🎭 Auto Roles",
            value=(
                f"`{ctx.prefix}autorole add @Member`\n"
                f"`{ctx.prefix}reactionroles create`\n"
                f"`{ctx.prefix}leveling enable`"
            ),
            inline=False
        )
        page2.set_footer(text="Page 2/3 • Member Experience Setup")
        pages.append(page2)
        
        # Page 3: Engagement Features
        page3 = discord.Embed(
            title="🎮 Step 3: Engagement Features",
            description="**Add fun and interactive features**",
            color=0x185fe5
        )
        page3.add_field(
            name="🎵 Music & Entertainment",
            value=(
                f"`{ctx.prefix}music setup`\n"
                f"`{ctx.prefix}play [song name]`\n"
                f"`{ctx.prefix}games enable`"
            ),
            inline=False
        )
        page3.add_field(
            name="📊 Analytics & Growth",
            value=(
                f"`{ctx.prefix}stats enable`\n"
                f"`{ctx.prefix}giveaway create`\n"
                f"`{ctx.prefix}ticket setup`"
            ),
            inline=False
        )
        page3.add_field(
            name="✅ You're All Set!",
            value=(
                "Your server now has:\n"
                "• Security protection\n"
                "• Welcome system\n"
                "• Member roles\n"
                "• Music & games\n"
                "• Growth tools\n\n"
                f"Use `{ctx.prefix}help` to explore more features!"
            ),
            inline=False
        )
        page3.set_footer(text="Page 3/3 • Engagement Features Setup")
        pages.append(page3)
        
        view = ShowcaseView(pages, ctx.author.id)
        await ctx.reply(embed=pages[0], view=view)

    @showcase.command(name="gaming", aliases=["game", "esports"])
    async def gaming(self, ctx: Context):
        """Complete gaming server configuration showcase"""
        
        pages = []
        
        # Gaming showcase pages
        page1 = discord.Embed(
            title="🎮 Gaming Server Showcase",
            description="**Complete setup for gaming communities**",
            color=0x185fe5
        )
        page1.add_field(
            name="🏆 Leveling & Ranks",
            value=(
                f"`{ctx.prefix}leveling enable`\n"
                f"`{ctx.prefix}leveling rewards add 10 @Gamer`\n"
                f"`{ctx.prefix}leveling rewards add 25 @Pro Gamer`\n"
                f"`{ctx.prefix}levels leaderboard`"
            ),
            inline=False
        )
        page1.add_field(
            name="🎵 Music for Gaming",
            value=(
                f"`{ctx.prefix}music setup`\n"
                f"`{ctx.prefix}autoplay on`\n"
                f"`{ctx.prefix}queue gaming playlist`"
            ),
            inline=False
        )
        page1.set_footer(text="Gaming Server • Competition & Music")
        pages.append(page1)
        
        view = ShowcaseView(pages, ctx.author.id)
        await ctx.reply(embed=pages[0], view=view)

    @showcase.command(name="professional", aliases=["business", "work"])
    async def professional(self, ctx: Context):
        """Business/professional server setup showcase"""
        
        pages = []
        
        page1 = discord.Embed(
            title="🏢 Professional Server Showcase",
            description="**Business and professional server configuration**",
            color=0x185fe5
        )
        page1.add_field(
            name="🎫 Support System",
            value=(
                f"`{ctx.prefix}ticket setup`\n"
                f"`{ctx.prefix}ticket category @Support Team`\n"
                f"`{ctx.prefix}ticket message Click to open a ticket`"
            ),
            inline=False
        )
        page1.add_field(
            name="📋 Professional Moderation",
            value=(
                f"`{ctx.prefix}automod enable`\n"
                f"`{ctx.prefix}automod profanity strict`\n"
                f"`{ctx.prefix}logging all #mod-logs`"
            ),
            inline=False
        )
        page1.set_footer(text="Professional Server • Support & Moderation")
        pages.append(page1)
        
        view = ShowcaseView(pages, ctx.author.id)
        await ctx.reply(embed=pages[0], view=view)

    @showcase.command(name="music", aliases=["audio", "playlist"])
    async def music(self, ctx: Context):
        """Advanced music features setup showcase"""
        
        pages = []
        
        page1 = discord.Embed(
            title="🎵 Music Server Showcase",
            description="**Advanced music features and setup**",
            color=0x185fe5
        )
        page1.add_field(
            name="🎼 Music Setup",
            value=(
                f"`{ctx.prefix}music setup #music-commands`\n"
                f"`{ctx.prefix}autoplay enable`\n"
                f"`{ctx.prefix}247 enable`\n"
                f"`{ctx.prefix}volume 50`"
            ),
            inline=False
        )
        page1.add_field(
            name="📊 Last.fm Integration",
            value=(
                f"`{ctx.prefix}fm set username`\n"
                f"`{ctx.prefix}fm nowplaying`\n"
                f"`{ctx.prefix}fm top artists`\n"
                f"`{ctx.prefix}fm compatibility @user`"
            ),
            inline=False
        )
        page1.set_footer(text="Music Server • Advanced Audio Features")
        pages.append(page1)
        
        view = ShowcaseView(pages, ctx.author.id)
        await ctx.reply(embed=pages[0], view=view)

    @showcase.command(name="troubleshoot", aliases=["help", "fix", "issues"])
    async def troubleshoot(self, ctx: Context):
        """Common solutions and troubleshooting guide"""
        
        pages = []
        
        page1 = discord.Embed(
            title="🔧 Troubleshooting Guide",
            description="**Common issues and solutions**",
            color=0x185fe5
        )
        page1.add_field(
            name="❌ Bot Not Responding",
            value=(
                "• Check bot permissions in channel\n"
                "• Verify bot has required roles\n"
                f"• Try `{ctx.prefix}ping` to test connection\n"
                "• Check if channel is ignored"
            ),
            inline=False
        )
        page1.add_field(
            name="🎵 Music Not Working",
            value=(
                "• Bot needs 'Connect' and 'Speak' permissions\n"
                "• Join voice channel before playing music\n"
                f"• Use `{ctx.prefix}music setup` to configure\n"
                "• Check if Lavalink is running"
            ),
            inline=False
        )
        page1.add_field(
            name="🎭 Reaction Roles Issues",
            value=(
                "• Bot needs 'Manage Roles' permission\n"
                "• Bot role must be above managed roles\n"
                f"• Use `{ctx.prefix}reactionroles debug` to check\n"
                "• Verify emoji permissions"
            ),
            inline=False
        )
        page1.set_footer(text="Troubleshooting • Common Solutions")
        pages.append(page1)
        
        view = ShowcaseView(pages, ctx.author.id)
        await ctx.reply(embed=pages[0], view=view)

async def setup(client: sleepless):
    await client.add_cog(Showcase(client))