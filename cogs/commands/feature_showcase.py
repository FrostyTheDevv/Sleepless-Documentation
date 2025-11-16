import discord
from discord.ext import commands
from utils.Tools import *

class FeatureShowcase(commands.Cog):
    """Interactive feature showcase with practical examples and tutorials"""
    
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="showcase", aliases=["examples", "tutorials"], help="View practical examples and tutorials for bot features")
    async def showcase(self, ctx):
        """Main showcase command with category selection"""
        if ctx.invoked_subcommand is None:
            prefix = ctx.prefix
            embed = discord.Embed(
                title="🌟 Feature Showcase & Examples",
                description="Choose a category to see practical examples and step-by-step tutorials:",
                color=0x3498db
            )
            
            embed.add_field(
                name="🚀 Quick Start",
                value=f"`{prefix}showcase quickstart`\nEssential 3-step setups for immediate use",
                inline=True
            )
            
            embed.add_field(
                name="🎮 Gaming Server",
                value=f"`{prefix}showcase gaming`\nComplete gaming community setup guide",
                inline=True
            )
            
            embed.add_field(
                name="🏢 Professional",
                value=f"`{prefix}showcase professional`\nBusiness/corporate server configuration",
                inline=True
            )
            
            embed.add_field(
                name="🎉 Entertainment",
                value=f"`{prefix}showcase entertainment`\nEvent and fun-focused server setup",
                inline=True
            )
            
            embed.add_field(
                name="🛡️ Security",
                value=f"`{prefix}showcase security`\nMaximum protection configuration",
                inline=True
            )
            
            embed.add_field(
                name="🎵 Music",
                value=f"`{prefix}showcase music`\nProfessional music bot setup",
                inline=True
            )
            
            embed.add_field(
                name="📊 Analytics",
                value=f"`{prefix}showcase analytics`\nTracking and engagement systems",
                inline=True
            )
            
            embed.add_field(
                name="🔧 Advanced",
                value=f"`{prefix}showcase advanced`\nComplex configurations and integrations",
                inline=True
            )
            
            embed.add_field(
                name="🆘 Troubleshooting",
                value=f"`{prefix}showcase troubleshoot`\nCommon issues and solutions",
                inline=True
            )
            
            embed.set_footer(text=f"💡 Tip: Use {prefix}setup guides for interactive setup assistance")
            
            await ctx.send(embed=embed)

    @showcase.command(name="quickstart", help="Essential 3-step setups for immediate use")
    async def quickstart(self, ctx):
        """Quick start examples for immediate setup"""
        prefix = ctx.prefix
        embed = discord.Embed(
            title="🚀 Quick Start Examples",
            description="Get started with these essential 3-step setups:",
            color=0xe74c3c
        )
        
        embed.add_field(
            name="🎵 Set Up Music in 3 Steps",
            value=f"```\n1. {prefix}play https://youtube.com/watch?v=...\n2. {prefix}queue\n3. {prefix}volume 75```\n✅ **Result**: Bot plays music with queue management",
            inline=False
        )
        
        embed.add_field(
            name="🔒 Server Protection in 5 Minutes",
            value=f"```\n1. {prefix}antinuke enable\n2. {prefix}antinuke whitelist @TrustedMod\n3. {prefix}antinuke punishment tempban\n4. {prefix}automod enable\n5. {prefix}automod setup```\n✅ **Result**: Server protected against raids and spam",
            inline=False
        )
        
        embed.add_field(
            name="🎭 Temporary Voice Channels",
            value=f"```\n1. {prefix}voicemaster setup #voice-category\n2. {prefix}voicemaster interface #vc-controls\n3. Users join 'Join to Create' channel\n4. Private channels created automatically```\n✅ **Result**: Members create their own voice channels",
            inline=False
        )
        
        embed.add_field(
            name="🎯 Self-Assignable Roles",
            value=f"```\n1. {prefix}reactionrole create #roles 'Pick your roles!'\n2. {prefix}rr add @Gamer 🎮\n3. {prefix}rr add @Music Lover 🎵```\n✅ **Result**: Members can self-assign roles with reactions",
            inline=False
        )
        
        embed.set_footer(text=f"Use {prefix}showcase [category] for more detailed examples")
        
        await ctx.send(embed=embed)

    @showcase.command(name="gaming", help="Complete gaming community setup guide")
    async def gaming(self, ctx):
        """Gaming server setup example"""
        prefix = ctx.prefix
        embed = discord.Embed(
            title="🎮 Gaming Community Setup",
            description="Transform your Discord into the ultimate gaming hub:",
            color=0x9b59b6
        )
        
        embed.add_field(
            name="🎵 Step 1: Music System",
            value=f"```\n{prefix}play setup\n{prefix}volume 50\n{prefix}24/7 enable```\n*24/7 background music for your community*",
            inline=False
        )
        
        embed.add_field(
            name="🎮 Step 2: Game Roles",
            value=f"```\n{prefix}autorole setup\n{prefix}rr create #roles 'React for your main game!'\n{prefix}rr add @Valorant 🎯\n{prefix}rr add @Minecraft ⛏️\n{prefix}rr add @Fortnite 🏗️```\n*Self-assignable game roles*",
            inline=False
        )
        
        embed.add_field(
            name="🔊 Step 3: Voice Channels",
            value=f"```\n{prefix}voicemaster setup #Gaming\n{prefix}vm interface #voice-controls```\n*Private team channels on demand*",
            inline=False
        )
        
        embed.add_field(
            name="🛡️ Step 4: Protection",
            value=f"```\n{prefix}antinuke enable\n{prefix}automod enable spamprotection```\n*Keep trolls and raids away*",
            inline=False
        )
        
        embed.add_field(
            name="🏆 Step 5: Engagement",
            value=f"```\n{prefix}leveling enable\n{prefix}leveling rewards add 10 @Active Gamer```\n*Reward active community members*",
            inline=False
        )
        
        embed.add_field(
            name="🎯 Expected Results",
            value="✅ 24/7 music bot ready\n✅ Self-assignable game roles\n✅ Private voice channels for teams\n✅ Anti-spam protection\n✅ Member engagement through leveling",
            inline=False
        )
        
        await ctx.send(embed=embed)

    @showcase.command(name="professional", help="Business/corporate server configuration")  
    async def professional(self, ctx):
        """Professional server setup example"""
        prefix = ctx.prefix
        embed = discord.Embed(
            title="🏢 Professional Discord Server",
            description="Create a corporate-grade Discord environment:",
            color=0x34495e
        )
        
        embed.add_field(
            name="🔨 Advanced Moderation",
            value=f"```\n{prefix}jail setup #verification\n{prefix}automod enable all\n{prefix}automod strict enable\n{prefix}logging setup #mod-logs```",
            inline=False
        )
        
        embed.add_field(
            name="📊 Analytics & Tracking",
            value=f"```\n{prefix}leveling enable\n{prefix}tracker setup #member-stats\n{prefix}glb setup```",
            inline=False
        )
        
        embed.add_field(
            name="👋 Professional Welcome",
            value=f"```\n{prefix}welcome enable\n{prefix}welcome message 'Welcome to {{server}}! Please read #rules.'```",
            inline=False
        )
        
        embed.add_field(
            name="🔒 Maximum Security",
            value=f"```\n{prefix}antinuke enable\n{prefix}antinuke punishment kick\n{prefix}antinuke whitelist @Management```",
            inline=False
        )
        
        embed.add_field(
            name="🌐 Professional Features",
            value=f"```\n{prefix}vanity set company-discord\n{prefix}slowmode 5 #general\n{prefix}setup guides```",
            inline=False
        )
        
        embed.set_footer(text="Perfect for businesses, organizations, and professional communities")
        
        await ctx.send(embed=embed)

    @showcase.command(name="music", help="Professional music bot setup")
    async def music(self, ctx):
        """Music-focused server setup"""
        prefix = ctx.prefix
        embed = discord.Embed(
            title="🎵 Professional Music Setup",
            description="Create the ultimate music experience:",
            color=0x1abc9c
        )
        
        embed.add_field(
            name="🎶 Core Music System",
            value=f"```\n{prefix}play setup\n{prefix}24/7 enable\n{prefix}volume 75\n{prefix}bass boost 25```",
            inline=False
        )
        
        embed.add_field(
            name="🎧 DJ Permissions",
            value=f"```\n{prefix}dj setup @DJ\n{prefix}dj perms skip queue clear\n{prefix}music vote enable skip```",
            inline=False
        )
        
        embed.add_field(
            name="📻 Last.fm Integration",
            value=f"```\n{prefix}fm setup #now-playing\n{prefix}fm auto-announce enable\n{prefix}fm leaderboard setup```",
            inline=False
        )
        
        embed.add_field(
            name="📈 Music Analytics",
            value=f"```\n{prefix}glb music setup\n{prefix}tracker music enable\n{prefix}leveling music-xp 2x```",
            inline=False
        )
        
        embed.set_footer(text="Perfect for music communities and listening parties")
        
        await ctx.send(embed=embed)

    @showcase.command(name="troubleshoot", help="Common issues and solutions")
    async def troubleshoot(self, ctx):
        """Troubleshooting guide"""
        prefix = ctx.prefix
        embed = discord.Embed(
            title="🆘 Troubleshooting Common Issues",
            description="Quick fixes for the most common problems:",
            color=0xe67e22
        )
        
        embed.add_field(
            name="🎵 Music Not Working",
            value=f"**Problem**: Bot won't play music\n**Solution**:\n```\n{prefix}music status\n{prefix}lavalink restart\n{prefix}music reset\n{prefix}play setup```",
            inline=False
        )
        
        embed.add_field(
            name="🔊 VoiceMaster Issues",
            value=f"**Problem**: Voice channels not creating\n**Solution**:\n```\n{prefix}vm status\n{prefix}vm reset\n{prefix}vm setup #Voice-Category```",
            inline=False
        )
        
        embed.add_field(
            name="⚠️ AntiNuke False Positives",
            value=f"**Problem**: Legitimate actions being blocked\n**Solution**:\n```\n{prefix}antinuke limit channels 10\n{prefix}antinuke whitelist @TrustedMod```",
            inline=False
        )
        
        embed.add_field(
            name="🔧 Permission Issues",
            value=f"**Problem**: Bot lacks permissions\n**Solution**:\n```\n{prefix}permissions check\n{prefix}setup permissions\n(Give bot Administrator role)```",
            inline=False
        )
        
        embed.set_footer(text=f"Still having issues? Use {prefix}help or join our support server")
        
        await ctx.send(embed=embed)

    @commands.command(name="examples", help="Quick access to practical examples")
    async def examples_shortcut(self, ctx, category: str | None = None):
        """Shortcut command for examples"""
        if category:
            # Redirect to appropriate showcase subcommand
            subcommands = {
                'quick': 'quickstart',
                'gaming': 'gaming', 
                'game': 'gaming',
                'professional': 'professional',
                'business': 'professional',
                'music': 'music',
                'audio': 'music',
                'security': 'security',
                'protection': 'security',
                'help': 'troubleshoot',
                'troubleshoot': 'troubleshoot',
                'issues': 'troubleshoot'
            }
            
            target = subcommands.get(category.lower())
            if target:
                # Call the appropriate subcommand
                command = self.bot.get_command(f'showcase {target}')
                if command:
                    await command.invoke(ctx)
                    return
        
        # Default to main showcase menu
        command = self.bot.get_command('showcase')
        await command.invoke(ctx)

def setup(bot):
    bot.add_cog(FeatureShowcase(bot))