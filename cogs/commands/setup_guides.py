import discord
from discord.ext import commands
from discord.ui import View, Select, Button, Modal, TextInput
from typing import Optional, Dict, List
from utils.Tools import blacklist_check, ignore_check

class SetupGuideView(View):
    """Interactive setup guide selector"""
    
    def __init__(self, ctx):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.current_guide = None
        
    @discord.ui.select(
        placeholder="🛠️ Choose a feature to set up...",
        options=[
            discord.SelectOption(
                label="AntiNuke Protection",
                value="antinuke",
                description="Server security and raid protection",
                emoji="🔒"
            ),
            discord.SelectOption(
                label="Music System",
                value="music", 
                description="Music player with Spotify & Last.fm",
                emoji="🎵"
            ),
            discord.SelectOption(
                label="VoiceMaster",
                value="voicemaster",
                description="Temporary voice channel creation",
                emoji="🔊"
            ),
            discord.SelectOption(
                label="Moderation Tools",
                value="moderation",
                description="Logging, automod, and punishment",
                emoji="🛡️"
            ),
            discord.SelectOption(
                label="Global Leaderboard (GLB)",
                value="glb",
                description="Live chat & voice leaderboards",
                emoji="📊"
            ),
            discord.SelectOption(
                label="Reaction Roles",
                value="reactionroles",
                description="Interactive role assignment panels",
                emoji="🎭"
            ),
            discord.SelectOption(
                label="Leveling System",
                value="leveling",
                description="XP system with role rewards",
                emoji="📈"
            ),
            discord.SelectOption(
                label="AutoRole & Welcomer",
                value="autorole",
                description="Automatic role assignment & greetings",
                emoji="👋"
            ),
            discord.SelectOption(
                label="Ticket System",
                value="tickets",
                description="Support ticket creation system",
                emoji="🎫"
            ),
            discord.SelectOption(
                label="Fun & Interactions",
                value="fun",
                description="Games, AI generation, social commands",
                emoji="🎮"
            )
        ]
    )
    async def select_guide(self, interaction: discord.Interaction, select: Select):
        """Handle guide selection"""
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ Only the command user can interact with this!", ephemeral=True)
            return
            
        guide_value = select.values[0]
        self.current_guide = guide_value
        
        embed = await self.get_guide_embed(guide_value)
        view = SetupGuideDetailView(self.ctx, guide_value)
        
        await interaction.response.edit_message(embed=embed, view=view)
        
    async def get_guide_embed(self, guide_type: str) -> discord.Embed:
        """Get the setup guide embed for the selected feature"""
        
        guides = {
            "antinuke": {
                "title": "🔒 AntiNuke Protection Setup",
                "description": "Protect your server from raids and malicious attacks",
                "color": 0xFF6B6B,
                "steps": [
                    "**Step 1:** Enable protection\n`!antinuke enable`",
                    "**Step 2:** Configure punishment\n`!antinuke punishment ban`",
                    "**Step 3:** Add trusted users\n`!antinuke whitelist add @user`", 
                    "**Step 4:** Set thresholds\n`!antinuke threshold 3`",
                    "**Step 5:** Enable specific protections\n`!antinuke channel enable`"
                ],
                "footer": "💡 Tip: Add admins to whitelist before enabling to avoid accidental punishment"
            },
            "music": {
                "title": "🎵 Music System Setup", 
                "description": "Advanced music player with multi-platform support",
                "color": 0x1DB954,
                "steps": [
                    "**Step 1:** Join voice channel\n`!join`",
                    "**Step 2:** Play your first song\n`!play <song name>`",
                    "**Step 3:** Connect Spotify (optional)\n`!spotify connect`",
                    "**Step 4:** Link Last.fm account\n`!fm set <username>`",
                    "**Step 5:** Explore advanced features\n`!queue`, `!lyrics`, `!loop`"
                ],
                "footer": "🎶 Supports Spotify, YouTube, SoundCloud, and more!"
            },
            "voicemaster": {
                "title": "🔊 VoiceMaster Setup",
                "description": "Create temporary voice channels on demand",
                "color": 0x5865F2,
                "steps": [
                    "**Step 1:** Run setup wizard\n`!voicemaster setup`",
                    "**Step 2:** Configure defaults\n`!vm channelname Voice-{user}`",
                    "**Step 3:** Set user limits\n`!vm userlimit 5`",
                    "**Step 4:** Create interface panel\n`!vm interface`",
                    "**Step 5:** Test by joining the creation channel"
                ],
                "footer": "👥 Users get their own temporary channels that auto-delete when empty"
            },
            "moderation": {
                "title": "🛡️ Moderation Tools Setup",
                "description": "Comprehensive moderation and logging system",
                "color": 0xF39C12,
                "steps": [
                    "**Step 1:** Setup logging\n`!logging setup`",
                    "**Step 2:** Configure AutoMod\n`!automod setup`",
                    "**Step 3:** Setup jail system\n`!jail setup`",
                    "**Step 4:** Enable spam protection\n`!automod spam enable`",
                    "**Step 5:** Test with `!warn @user test`"
                ],
                "footer": "📝 All moderation actions are automatically logged with reasons"
            },
            "glb": {
                "title": "📊 Global Leaderboard (GLB) Setup",
                "description": "Live chat and voice activity leaderboards",
                "color": 0xE74C3C,
                "steps": [
                    "**Step 1:** Setup chat leaderboard\n`!glb #leaderboard-channel`",
                    "**Step 2:** Setup voice leaderboard\n`!gvclb #voice-leaderboard`",
                    "**Step 3:** Configure role rewards\n`!glb roles`",
                    "**Step 4:** View current rankings\n`!glb`",
                    "**Step 5:** Check streaks\n`!streaks`"
                ],
                "footer": "🏆 Features daily, weekly, monthly, and all-time statistics"
            },
            "reactionroles": {
                "title": "🎭 Reaction Roles Setup",
                "description": "Interactive role assignment with reactions & dropdowns",
                "color": 0x9B59B6,
                "steps": [
                    "**Step 1:** Start setup wizard\n`!reactionrole setup`",
                    "**Step 2:** Add roles to panel\n`!rr add 🎮 @Gamer Cool role for gamers`",
                    "**Step 3:** Create dropdown panel\n`!rr dropdown create`",
                    "**Step 4:** Customize panel design\n`!rr panel create`",
                    "**Step 5:** Test the panel functionality"
                ],
                "footer": "✨ Supports both emoji reactions and dropdown menus"
            },
            "leveling": {
                "title": "📈 Leveling System Setup",
                "description": "XP system with role rewards and leaderboards",
                "color": 0x3498DB,
                "steps": [
                    "**Step 1:** Enable leveling\n`!leveling enable`",
                    "**Step 2:** Set announcement channel\n`!leveling channel #level-ups`",
                    "**Step 3:** Add level roles\n`!levelroles add 10 @Level10`",
                    "**Step 4:** View leaderboard\n`!leaderboard`",
                    "**Step 5:** Check your rank\n`!rank`"
                ],
                "footer": "⭐ Members gain XP by chatting and can earn role rewards"
            },
            "autorole": {
                "title": "👋 AutoRole & Welcomer Setup",
                "description": "Automatic role assignment and welcome messages",
                "color": 0x2ECC71,
                "steps": [
                    "**Step 1:** Setup autorole\n`!autorole setup`",
                    "**Step 2:** Add roles to assign\n`!autorole add @Member`",
                    "**Step 3:** Setup welcomer\n`!welcomer setup`",
                    "**Step 4:** Set welcome channel\n`!welcomer channel #welcome`",
                    "**Step 5:** Customize welcome message"
                ],
                "footer": "🎉 New members automatically get roles and welcome messages"
            },
            "tickets": {
                "title": "🎫 Ticket System Setup",
                "description": "Support ticket creation and management",
                "color": 0x95A5A6,
                "steps": [
                    "**Step 1:** Run ticket setup\n`!ticket setup`",
                    "**Step 2:** Create ticket panel\n`!ticket panel`",
                    "**Step 3:** Set ticket category\n`!ticket category Support Tickets`",
                    "**Step 4:** Test ticket creation",
                    "**Step 5:** Practice ticket management\n`!ticket close`"
                ],
                "footer": "📞 Organized support system with automatic transcript saving"
            },
            "fun": {
                "title": "🎮 Fun & Interactions Setup",
                "description": "Games, AI generation, and social commands",
                "color": 0xE91E63,
                "steps": [
                    "**Step 1:** Try social interactions\n`!hug @user`",
                    "**Step 2:** Play games\n`!8ball Will this work?`",
                    "**Step 3:** Generate AI images\n`!imagine a cute cat`",
                    "**Step 4:** Check IP information\n`!iplookup 8.8.8.8`",
                    "**Step 5:** View interaction stats\n`!interactions stats`"
                ],
                "footer": "🎭 Over 50+ fun commands with AI integration and social features"
            }
        }
        
        guide = guides.get(guide_type, {})
        
        embed = discord.Embed(
            title=guide.get("title", "Setup Guide"),
            description=guide.get("description", "Setup guide for this feature"),
            color=guide.get("color", 0x00ff88)
        )
        
        steps = guide.get("steps", [])
        if steps:
            embed.add_field(
                name="📋 Setup Steps",
                value="\n\n".join(steps),
                inline=False
            )
        
        embed.set_footer(text=guide.get("footer", "Follow the steps above to complete setup"))
        
        return embed

class SetupGuideDetailView(View):
    """Detailed view for a specific setup guide with action buttons"""
    
    def __init__(self, ctx, guide_type: str):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.guide_type = guide_type
        
    @discord.ui.button(label="⬅️ Back to Menu", style=discord.ButtonStyle.secondary)
    async def back_to_menu(self, interaction: discord.Interaction, button: Button):
        """Go back to the main setup menu"""
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ Only the command user can interact with this!", ephemeral=True)
            return
            
        embed = discord.Embed(
            title="🛠️ SleeplessPY Setup Center",
            description=(
                "Welcome to the comprehensive setup center! Choose a feature below to get step-by-step "
                "setup instructions with all the commands you need.\n\n"
                "**Available Setup Guides:**\n"
                "🔒 **AntiNuke** - Server protection & security\n"
                "🎵 **Music System** - Advanced music player\n"
                "🔊 **VoiceMaster** - Temporary voice channels\n"
                "🛡️ **Moderation** - Logging & automod tools\n"
                "📊 **Global Leaderboard** - Activity tracking\n"
                "🎭 **Reaction Roles** - Interactive role panels\n"
                "📈 **Leveling System** - XP & role rewards\n"
                "👋 **AutoRole & Welcomer** - New member automation\n"
                "🎫 **Ticket System** - Support ticket management\n"
                "🎮 **Fun & Interactions** - Games & social features"
            ),
            color=0x00ff88
        )
        embed.set_footer(text="💡 Select a feature from the dropdown below to get started!")
        
        view = SetupGuideView(self.ctx)
        await interaction.response.edit_message(embed=embed, view=view)
        
    @discord.ui.button(label="🚀 Quick Setup", style=discord.ButtonStyle.primary)
    async def quick_setup(self, interaction: discord.Interaction, button: Button):
        """Provide quick setup commands for the current guide"""
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ Only the command user can interact with this!", ephemeral=True)
            return
            
        quick_commands = {
            "antinuke": [
                "!antinuke enable",
                "!antinuke punishment ban", 
                "!antinuke threshold 3"
            ],
            "music": [
                "!join",
                "!play your favorite song"
            ],
            "voicemaster": [
                "!voicemaster setup"
            ],
            "moderation": [
                "!logging setup",
                "!automod setup"
            ],
            "glb": [
                "!glb #your-leaderboard-channel"
            ],
            "reactionroles": [
                "!reactionrole setup"
            ],
            "leveling": [
                "!leveling enable"
            ],
            "autorole": [
                "!autorole setup",
                "!welcomer setup"
            ],
            "tickets": [
                "!ticket setup"
            ],
            "fun": [
                "!hug @someone",
                "!8ball Am I awesome?"
            ]
        }
        
        commands = quick_commands.get(self.guide_type, [])
        
        if commands:
            command_list = "\n".join([f"`{cmd}`" for cmd in commands])
            embed = discord.Embed(
                title=f"🚀 Quick Setup Commands",
                description=f"Here are the essential commands to get started quickly:\n\n{command_list}",
                color=0x00ff88
            )
            embed.set_footer(text="Copy and paste these commands to get started immediately!")
        else:
            embed = discord.Embed(
                title="❌ No Quick Setup Available",
                description="This feature doesn't have quick setup commands available.",
                color=0xff6b6b
            )
            
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    @discord.ui.button(label="📚 Full Documentation", style=discord.ButtonStyle.secondary)
    async def full_docs(self, interaction: discord.Interaction, button: Button):
        """Link to full documentation"""
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ Only the command user can interact with this!", ephemeral=True)
            return
            
        embed = discord.Embed(
            title="📚 Full Documentation",
            description=(
                "For complete documentation and advanced features:\n\n"
                "🔗 **[Setup Guides Document](https://github.com/your-repo/blob/main/SETUP_GUIDES.md)**\n"
                "🆘 **[Support Server](https://discord.gg/5wtjDkYbVh)**\n"
                f"❓ **Feature Help**: `!help {self.guide_type}`\n\n"
                "You can also use feature-specific help commands like:\n"
                "`!rr help`, `!fm help`, `!antinuke help`"
            ),
            color=0x3498db
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class SetupGuides(commands.Cog):
    """Setup guidance system for SleeplessPY bot features"""
    
    def __init__(self, bot):
        self.bot = bot
        
    @commands.command(name="setup", help="Interactive setup guides for all bot features")
    @blacklist_check()
    @ignore_check()
    async def setup_guides(self, ctx):
        """Main setup command that shows the setup center"""
        
        embed = discord.Embed(
            title="🛠️ SleeplessPY Setup Center",
            description=(
                "Welcome to the comprehensive setup center! Choose a feature below to get step-by-step "
                "setup instructions with all the commands you need.\n\n"
                "**Available Setup Guides:**\n"
                "🔒 **AntiNuke** - Server protection & security\n"
                "🎵 **Music System** - Advanced music player\n"
                "🔊 **VoiceMaster** - Temporary voice channels\n"
                "🛡️ **Moderation** - Logging & automod tools\n"
                "📊 **Global Leaderboard** - Activity tracking\n"
                "🎭 **Reaction Roles** - Interactive role panels\n"
                "📈 **Leveling System** - XP & role rewards\n"
                "👋 **AutoRole & Welcomer** - New member automation\n"
                "🎫 **Ticket System** - Support ticket management\n"
                "🎮 **Fun & Interactions** - Games & social features"
            ),
            color=0x00ff88
        )
        
        embed.add_field(
            name="🚀 Quick Start Essentials",
            value=(
                "**New to SleeplessPY?** Start with these:\n"
                "1️⃣ `!prefix <new_prefix>` - Set custom prefix\n"
                "2️⃣ `!antinuke enable` - Enable server protection\n"
                "3️⃣ `!logging setup` - Setup moderation logging\n"
                "4️⃣ `!setup` - Return to this menu anytime"
            ),
            inline=False
        )
        
        embed.set_footer(text="💡 Select a feature from the dropdown below to get started!")
        
        view = SetupGuideView(ctx)
        await ctx.send(embed=embed, view=view)
        
    @commands.command(name="quickstart", aliases=["qs"], help="Essential commands to get started quickly")
    @blacklist_check()
    @ignore_check()
    async def quick_start(self, ctx):
        """Quick start guide with essential commands"""
        
        embed = discord.Embed(
            title="🚀 SleeplessPY Quick Start Guide",
            description="Get your server up and running in minutes!",
            color=0x00ff88
        )
        
        embed.add_field(
            name="1️⃣ Essential Security (Required)",
            value=(
                "`!antinuke enable` - Enable server protection\n"
                "`!antinuke whitelist add @AdminRole` - Add trusted admins\n"
                "`!logging setup` - Setup moderation logging"
            ),
            inline=False
        )
        
        embed.add_field(
            name="2️⃣ Popular Features (Recommended)",
            value=(
                "`!voicemaster setup` - Temporary voice channels\n"
                "`!reactionrole setup` - Role assignment panels\n"
                "`!leveling enable` - XP system for members"
            ),
            inline=False
        )
        
        embed.add_field(
            name="3️⃣ Entertainment (Optional)",
            value=(
                "`!join` - Start using music features\n"
                "`!glb #channel` - Setup activity leaderboards\n"
                "`!hug @friend` - Try social interactions"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🆘 Need Help?",
            value=(
                "`!setup` - Interactive setup guides\n"
                "`!help` - Full command list\n"
                "[Support Server](https://discord.gg/5wtjDkYbVh) - Get help from our team"
            ),
            inline=False
        )
        
        embed.set_footer(text="💡 Use !setup for detailed guides on any feature")
        
        await ctx.send(embed=embed)

    def help_custom(self):
        return "🛠️", "Setup Guides", "Interactive setup guides for all bot features & quick start"

async def setup(bot):
    await bot.add_cog(SetupGuides(bot))