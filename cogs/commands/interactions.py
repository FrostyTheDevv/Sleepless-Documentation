from utils.error_helpers import StandardErrorHandler
# cogs/interactions.py

import discord
from discord.ext import commands
import random
import sqlite3
import os
from typing import Optional, Dict, Any
from utils.gif_list import gif_list
import asyncio
from datetime import datetime, timezone

class InteractionView(discord.ui.View):
    """View class for accept/decline interaction buttons"""
    
    def __init__(self, target_user: discord.Member, initiator: discord.Member, 
                 interaction_type: str, gif_url: str, timeout: float = 60.0):
        super().__init__(timeout=timeout)
        self.target_user = target_user
        self.initiator = initiator
        self.interaction_type = interaction_type
        self.gif_url = gif_url
        self.responded = False
        
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the target user can respond"""
        if interaction.user.id != self.target_user.id:
            await interaction.response.send_message(
                "❌ Only the person being interacted with can respond to this!", 
                ephemeral=True
            )
            return False
        return True
    
    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green, emoji="✅")
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle accept button press"""
        self.responded = True
        
        # Create accepted embed
        embed = discord.Embed(
            title=f"✨ {self.interaction_type.title()} Accepted! 💕",
            description=f"🎉 **{self.target_user.display_name}** accepted **{self.initiator.display_name}**'s {self.interaction_type}!",
            color=0x57F287
        )
        embed.set_image(url=self.gif_url)
        embed.set_footer(text="💖 Interaction accepted • SleeplessPY", 
                        icon_url="https://cdn.discordapp.com/emojis/1430203733593034893.gif")
        
        # Disable all buttons and update message
        for item in self.children:
            item.disabled = True  # type: ignore
        
        await interaction.response.edit_message(embed=embed, view=self)
        
        # Log the interaction
        cog = getattr(interaction.client, 'get_cog', lambda x: None)('Interactions')
        if cog and interaction.guild:
            await cog.log_interaction(
                interaction.guild.id, 
                self.initiator.id, 
                self.target_user.id, 
                self.interaction_type, 
                'accepted'
            )
    
    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red, emoji="<:cancel:1427471557055352892>")
    async def decline_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle decline button press"""
        self.responded = True
        
        # Create declined embed
        embed = discord.Embed(
            title=f"💔 {self.interaction_type.title()} Declined",
            description=f"😔 **{self.target_user.display_name}** declined **{self.initiator.display_name}**'s {self.interaction_type}.",
            color=0xED4245
        )
        embed.set_footer(text="💔 Interaction declined • Maybe next time!", 
                        icon_url="https://cdn.discordapp.com/emojis/1427471557055352892.png")
        
        # Disable all buttons and update message
        for item in self.children:
            item.disabled = True  # type: ignore
        
        await interaction.response.edit_message(embed=embed, view=self)
        
        # Log the interaction
        cog = getattr(interaction.client, 'get_cog', lambda x: None)('Interactions')
        if cog and interaction.guild:
            await cog.log_interaction(
                interaction.guild.id, 
                self.initiator.id, 
                self.target_user.id, 
                self.interaction_type, 
                'declined'
            )
    
    async def on_timeout(self):
        """Handle timeout - disable all buttons"""
        for item in self.children:
            item.disabled = True  # type: ignore

class Interactions(commands.Cog):
    """Comprehensive interactions system with accept/decline mechanics"""
    
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot
        self.db_path = 'databases/interactions.db'
        self.ensure_database()
    
    def ensure_database(self):
        """Create interactions database if it doesn't exist"""
        os.makedirs('databases', exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    initiator_id INTEGER NOT NULL,
                    target_id INTEGER NOT NULL,
                    interaction_type TEXT NOT NULL,
                    response TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS interaction_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    interaction_type TEXT NOT NULL,
                    given_count INTEGER DEFAULT 0,
                    received_count INTEGER DEFAULT 0,
                    accepted_given INTEGER DEFAULT 0,
                    accepted_received INTEGER DEFAULT 0,
                    UNIQUE(guild_id, user_id, interaction_type)
                )
            ''')
            conn.commit()
    
    async def log_interaction(self, guild_id: int, initiator_id: int, target_id: int, 
                            interaction_type: str, response: str):
        """Log interaction to database and update stats"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Log the interaction
            cursor.execute('''
                INSERT INTO interactions 
                (guild_id, initiator_id, target_id, interaction_type, response) 
                VALUES (?, ?, ?, ?, ?)
            ''', (guild_id, initiator_id, target_id, interaction_type, response))
            
            # Update stats for initiator (given)
            cursor.execute('''
                INSERT OR IGNORE INTO interaction_stats 
                (guild_id, user_id, interaction_type) 
                VALUES (?, ?, ?)
            ''', (guild_id, initiator_id, interaction_type))
            
            cursor.execute('''
                UPDATE interaction_stats 
                SET given_count = given_count + 1,
                    accepted_given = accepted_given + ?
                WHERE guild_id = ? AND user_id = ? AND interaction_type = ?
            ''', (1 if response == 'accepted' else 0, guild_id, initiator_id, interaction_type))
            
            # Update stats for target (received)
            cursor.execute('''
                INSERT OR IGNORE INTO interaction_stats 
                (guild_id, user_id, interaction_type) 
                VALUES (?, ?, ?)
            ''', (guild_id, target_id, interaction_type))
            
            cursor.execute('''
                UPDATE interaction_stats 
                SET received_count = received_count + 1,
                    accepted_received = accepted_received + ?
                WHERE guild_id = ? AND user_id = ? AND interaction_type = ?
            ''', (1 if response == 'accepted' else 0, guild_id, target_id, interaction_type))
            
            conn.commit()
    
    async def create_interaction(self, ctx, interaction_type: str, target: Optional[discord.Member] = None):
        """Create an interaction with accept/decline functionality"""
        
        # Validate interaction type
        if interaction_type not in gif_list:
            await ctx.send(f"❌ Unknown interaction type: `{interaction_type}`")
            return
        
        # Handle self-interaction or no target
        if target is None or target == ctx.author:
            # Self interaction - just show a random gif
            gif_url = random.choice(gif_list[interaction_type])
            embed = discord.Embed(
                title=f"💜 {ctx.author.display_name} {interaction_type}s themselves!",
                description=f"✨ *{ctx.author.display_name} gives themselves some love with a {interaction_type}!* 🥰",
                color=0x9370DB
            )
            embed.set_image(url=gif_url)
            embed.set_footer(text="💜 Self-care is important! • Sleepless.PY")
            
            await ctx.send(embed=embed)
            return
        
        # Check if target is a bot
        if target.bot:
            await ctx.send(f"❌ You can't {interaction_type} a bot!")
            return
        
        # Create interaction embed with buttons
        gif_url = random.choice(gif_list[interaction_type])
        
        # Add action-specific emojis
        action_emojis = {
            'hug': '🤗', 'kiss': '😘', 'pat': '👋', 'cuddle': '🥰', 'slap': '✋',
            'tickle': '😆', 'bite': '😈', 'poke': '👉', 'feed': '🍽️', 'dance': '💃',
            'wave': '👋', 'wink': '😉', 'handshake': '🤝', 'highfive': '✋',
            'glomp': '🤗', 'handhold': '💕', 'nuzzle': '🥰', 'salute': '🫡'
        }
        
        emoji = action_emojis.get(interaction_type, '💫')
        
        embed = discord.Embed(
            title=f"{emoji} {interaction_type.title()} Request",
            description=f"💖 **{ctx.author.display_name}** wants to {interaction_type} **{target.display_name}**!\n\n{target.mention}, do you accept this sweet interaction?",
            color=0x5865F2
        )
        embed.set_image(url=gif_url)
        embed.set_footer(text="⏰ Respond within 60 seconds • SleeplessPY")
        
        # Create view with accept/decline buttons
        view = InteractionView(target, ctx.author, interaction_type, gif_url)
        
        try:
            await ctx.send(embed=embed, view=view)
        except discord.Forbidden:
            try:
                await ctx.send("❌ I don't have permission to send messages or embeds in this channel.")
            except:
                pass  # If we can't send any message, silently fail
    
    # Individual interaction commands
    @commands.command(name='hug', help='Give someone a warm hug with interactive buttons', usage='hug [@user]')
    async def hug(self, ctx, target: Optional[discord.Member] = None):
        """Give someone a warm hug"""
        await self.create_interaction(ctx, 'hug', target)
    
    @commands.command(name='slap', help='Give someone a playful slap with animated GIFs', usage='slap [@user]')
    async def slap(self, ctx, target: Optional[discord.Member] = None):
        """Give someone a playful slap"""
        await self.create_interaction(ctx, 'slap', target)
    
    @commands.command(name='handshake', help='Shake hands with someone professionally', usage='handshake [@user]')
    async def handshake(self, ctx, target: Optional[discord.Member] = None):
        """Shake hands with someone"""
        await self.create_interaction(ctx, 'handshake', target)
    
    @commands.command(name='highfive', help='Give someone an energetic high five', usage='highfive [@user]')
    async def highfive(self, ctx, target: Optional[discord.Member] = None):
        """Give someone a high five"""
        await self.create_interaction(ctx, 'highfive', target)
    
    @commands.command(name='kiss', help='Give someone a sweet kiss with cute animations', usage='kiss [@user]')
    async def kiss(self, ctx, target: Optional[discord.Member] = None):
        """Give someone a kiss"""
        await self.create_interaction(ctx, 'kiss', target)
    
    @commands.command(name='pat', help='Pat someone gently on the head', usage='pat [@user]')
    async def pat(self, ctx, target: Optional[discord.Member] = None):
        """Pat someone on the head"""
        await self.create_interaction(ctx, 'pat', target)
    
    @commands.command(name='poke', help='Poke someone to get their attention', usage='poke [@user]')
    async def poke(self, ctx, target: Optional[discord.Member] = None):
        """Poke someone"""
        await self.create_interaction(ctx, 'poke', target)
    
    @commands.command(name='cuddle', help='Cuddle with someone for comfort', usage='cuddle [@user]')
    async def cuddle(self, ctx, target: Optional[discord.Member] = None):
        """Cuddle with someone"""
        await self.create_interaction(ctx, 'cuddle', target)
    
    @commands.command(name='tickle', help='Tickle someone playfully', usage='tickle [@user]')
    async def tickle(self, ctx, target: Optional[discord.Member] = None):
        """Tickle someone"""
        await self.create_interaction(ctx, 'tickle', target)
    
    @commands.command(name='bite', help='Give someone a gentle playful bite', usage='bite [@user]')
    async def bite(self, ctx, target: Optional[discord.Member] = None):
        """Give someone a gentle bite"""
        await self.create_interaction(ctx, 'bite', target)
    
    @commands.command(name='wink', help='Wink at someone flirtatiously', usage='wink [@user]')
    async def wink(self, ctx, target: Optional[discord.Member] = None):
        """Wink at someone"""
        await self.create_interaction(ctx, 'wink', target)
    
    @commands.command(name='wave', help='Wave hello or goodbye to someone', usage='wave [@user]')
    async def wave(self, ctx, target: Optional[discord.Member] = None):
        """Wave at someone"""
        await self.create_interaction(ctx, 'wave', target)
    
    @commands.command(name='feed', help='Feed someone something delicious', usage='feed [@user]')
    async def feed(self, ctx, target: Optional[discord.Member] = None):
        """Feed someone"""
        await self.create_interaction(ctx, 'feed', target)
    
    @commands.command(name='dance', help='Dance together with someone', usage='dance [@user]')
    async def dance(self, ctx, target: Optional[discord.Member] = None):
        """Dance with someone"""
        await self.create_interaction(ctx, 'dance', target)
    
    @commands.command(name='glomp', help='Give someone an enthusiastic tackle-hug', usage='glomp [@user]')
    async def glomp(self, ctx, target: Optional[discord.Member] = None):
        """Glomp someone"""
        await self.create_interaction(ctx, 'glomp', target)
    
    @commands.command(name='handhold', help='Hold hands with someone romantically', usage='handhold [@user]')
    async def handhold(self, ctx, target: Optional[discord.Member] = None):
        """Hold hands with someone"""
        await self.create_interaction(ctx, 'handhold', target)
    
    @commands.command(name='nuzzle', help='Nuzzle someone affectionately', usage='nuzzle [@user]')
    async def nuzzle(self, ctx, target: Optional[discord.Member] = None):
        """Nuzzle someone"""
        await self.create_interaction(ctx, 'nuzzle', target)
    
    @commands.command(name='salute', description='Salute someone')
    async def salute(self, ctx, target: Optional[discord.Member] = None):
        """Salute someone"""
        await self.create_interaction(ctx, 'salute', target)
    
    @commands.command(name='interactions', description='View your interaction statistics')
    async def interaction_stats(self, ctx, user: Optional[discord.Member] = None):
        """View interaction statistics for a user"""
        target_user = user or ctx.author
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT interaction_type, given_count, received_count, 
                       accepted_given, accepted_received
                FROM interaction_stats 
                WHERE guild_id = ? AND user_id = ?
                ORDER BY (given_count + received_count) DESC
            ''', (ctx.guild.id, target_user.id))
            
            stats = cursor.fetchall()
        
        if not stats:
            embed = discord.Embed(
                title="📊 Interaction Statistics",
                description=f"💔 **{target_user.display_name}** hasn't participated in any interactions yet!\n\n🌟 Start spreading love with some interactions!",
                color=0x9370DB
            )
            embed.set_thumbnail(url=target_user.display_avatar.url)
            embed.set_footer(text="💕 Use interaction commands to build your stats! • SleeplessPY")
            await ctx.send(embed=embed)
            return
        
        # Calculate total stats
        total_given = sum(stat[1] for stat in stats)
        total_received = sum(stat[2] for stat in stats)
        total_accepted_given = sum(stat[3] for stat in stats)
        total_accepted_received = sum(stat[4] for stat in stats)
        
        embed = discord.Embed(
            title=f"📊 {target_user.display_name}'s Interaction Statistics",
            description=f"💖 **Total Interactions:** {total_given + total_received}\n🎯 **Success Rate:** {round(((total_accepted_given + total_accepted_received) / max(1, total_given + total_received)) * 100, 1)}%",
            color=0x5865F2
        )
        embed.set_thumbnail(url=target_user.display_avatar.url)
        
        # Add action-specific emojis
        action_emojis = {
            'hug': '🤗', 'kiss': '😘', 'pat': '👋', 'cuddle': '🥰', 'slap': '✋',
            'tickle': '😆', 'bite': '😈', 'poke': '👉', 'feed': '🍽️', 'dance': '💃',
            'wave': '👋', 'wink': '😉', 'handshake': '🤝', 'highfive': '✋',
            'glomp': '🤗', 'handhold': '💕', 'nuzzle': '🥰', 'salute': '🫡'
        }
        
        for interaction_type, given, received, acc_given, acc_received in stats:
            emoji = action_emojis.get(interaction_type, '💫')
            
            # Calculate success rates as percentages
            given_success = round((acc_given / max(1, given)) * 100) if given > 0 else 0
            received_success = round((acc_received / max(1, received)) * 100) if received > 0 else 0
            
            # Create clean, visually appealing format
            given_display = f"📤 **{given}** ({given_success}% ✅)" if given > 0 else "📤 **0**"
            received_display = f"📥 **{received}** ({received_success}% ✅)" if received > 0 else "📥 **0**"
            
            embed.add_field(
                name=f"{emoji} **{interaction_type.title()}**",
                value=f"{given_display}\n{received_display}",
                inline=True
            )
        
        embed.set_footer(text="✅ = Accepted interactions • 💕 Keep spreading love! • SleeplessPY")
        await ctx.send(embed=embed)
    
    @commands.command(name='interaction_leaderboard', aliases=['ileaderboard'])
    async def interaction_leaderboard(self, ctx, interaction_type: Optional[str] = None):
        """Show interaction leaderboard for the server"""
        if interaction_type and interaction_type not in gif_list:
            await ctx.send(f"❌ Unknown interaction type: `{interaction_type}`\n"
                          f"Available types: `{', '.join(gif_list.keys())}`")
            return
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if interaction_type:
                cursor.execute('''
                    SELECT user_id, given_count + received_count as total,
                           given_count, received_count, 
                           accepted_given + accepted_received as total_accepted
                    FROM interaction_stats 
                    WHERE guild_id = ? AND interaction_type = ?
                    ORDER BY total DESC, total_accepted DESC
                    LIMIT 10
                ''', (ctx.guild.id, interaction_type))
                
                # Add action-specific emoji
                action_emojis = {
                    'hug': '🤗', 'kiss': '😘', 'pat': '👋', 'cuddle': '🥰', 'slap': '✋',
                    'tickle': '😆', 'bite': '😈', 'poke': '👉', 'feed': '🍽️', 'dance': '💃',
                    'wave': '👋', 'wink': '😉', 'handshake': '🤝', 'highfive': '✋',
                    'glomp': '🤗', 'handhold': '💕', 'nuzzle': '🥰', 'salute': '🫡'
                }
                emoji = action_emojis.get(interaction_type, '💫')
                title = f"🏆 {emoji} {interaction_type.title()} Leaderboard"
            else:
                cursor.execute('''
                    SELECT user_id, SUM(given_count + received_count) as total,
                           SUM(given_count) as given_total, SUM(received_count) as received_total,
                           SUM(accepted_given + accepted_received) as total_accepted
                    FROM interaction_stats 
                    WHERE guild_id = ?
                    GROUP BY user_id
                    ORDER BY total DESC, total_accepted DESC
                    LIMIT 10
                ''', (ctx.guild.id,))
                title = "🏆 💖 Overall Interaction Leaderboard"
            
            results = cursor.fetchall()
        
        if not results:
            embed = discord.Embed(
                title="💔 No Interaction Data",
                description="😢 No interaction statistics available for this server!\n\n🌟 Start using interaction commands to build the leaderboard!",
                color=0xED4245
            )
            embed.set_footer(text="💕 Use interaction commands to get started! • SleeplessPY")
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title=title, 
            description=f"🎯 **Top {len(results)} most interactive members in {ctx.guild.name}!**",
            color=0xFFD700
        )
        
        for i, (user_id, total, given, received, accepted) in enumerate(results, 1):
            user = ctx.guild.get_member(user_id)
            user_name = user.display_name if user else f"Unknown User ({user_id})"
            
            # Enhanced medal system with more emojis
            if i == 1:
                medal = "👑"
            elif i == 2:
                medal = "🥈"
            elif i == 3:
                medal = "🥉"
            elif i <= 5:
                medal = "⭐"
            else:
                medal = f"#{i}"
            
            # Calculate success rate
            success_rate = round((accepted / max(1, total)) * 100, 1)
            
            embed.add_field(
                name=f"{medal} {user_name}",
                value=f"💖 **Total:** {total} interactions\n✅ **Success Rate:** {success_rate}%\n📤 **Given:** {given} • 📥 **Received:** {received}",
                inline=False
            )
        
        embed.set_footer(text="💕 Keep spreading love and climb the leaderboard! • SleeplessPY")
        await ctx.send(embed=embed)

    def help_custom(self):
        return "💕", "Interactions", "Social interactions with hugs, kisses, slaps & more"

async def setup(bot):
    await bot.add_cog(Interactions(bot))