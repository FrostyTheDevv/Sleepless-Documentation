import discord
from discord.ext import commands
import sqlite3
import asyncio
import os

from utils.error_helpers import StandardErrorHandler

# Custom Emojis
EMOJIS = {
    "success": "<:feast_tick:1400143469892210753>",
    "error": "<:feast_cross:1400143488695144609>",
    "warning": "<:feast_warning:1400143131990560830>",
    "list": "<:web:1428162947187736679>",
    "settings": "<:Feast_Utility:1400135926298185769>",
    "welcome": "<:feast_plus:1400142875483836547>",
    "channel": "<:feast_piche:1400142845402284102>"
}

DB_PATH = "./db/fastgreet.db"

class FastGreet(commands.Cog):
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot
        os.makedirs("./db", exist_ok=True)
        self.init_db()

    def init_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS greet_channels (
                    guild_id INTEGER,
                    channel_id INTEGER,
                    PRIMARY KEY (guild_id, channel_id)
                )
            """)

    @commands.command(name="fastgreet_add")
    @commands.has_permissions(administrator=True)
    async def add_greet_channel(self, ctx, channel: discord.TextChannel):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                INSERT OR IGNORE INTO greet_channels (guild_id, channel_id)
                VALUES (?, ?)
            """, (ctx.guild.id, channel.id))
        
        embed = discord.Embed(
            title=f"{EMOJIS['success']} Greet Channel Added",
            description=f"{EMOJIS['channel']} {channel.mention} has been added as a greet channel.",
            color=0x00ff00
        )
        embed.set_footer(text="Members will receive a quick welcome message when they join")
        await ctx.send(embed=embed)

    @commands.command(name="fastgreet_remove")
    @commands.has_permissions(administrator=True)
    async def remove_greet_channel(self, ctx, channel: discord.TextChannel):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute("""
                DELETE FROM greet_channels WHERE guild_id = ? AND channel_id = ?
            """, (ctx.guild.id, channel.id))
            conn.commit()
            
        if cursor.rowcount > 0:
            embed = discord.Embed(
                title=f"{EMOJIS['success']} Greet Channel Removed",
                description=f"{EMOJIS['channel']} {channel.mention} has been removed from greet channels.",
                color=0xff6b6b
            )
        else:
            embed = discord.Embed(
                title=f"{EMOJIS['warning']} Channel Not Found",
                description=f"{EMOJIS['channel']} {channel.mention} was not configured as a greet channel.",
                color=0xffa500
            )
            
        await ctx.send(embed=embed)

    @commands.command(name="fastgreet_list")
    async def list_greet_channels(self, ctx):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute("""
                SELECT channel_id FROM greet_channels WHERE guild_id = ?
            """, (ctx.guild.id,))
            rows = cursor.fetchall()

        if not rows:
            embed = discord.Embed(
                title=f"{EMOJIS['warning']} No Greet Channels",
                description=f"{EMOJIS['settings']} No greet channels have been configured for this server.\n\n"
                           f"**Use:** `{ctx.prefix}fastgreet_add #channel` to add one.",
                color=0xffa500
            )
            await ctx.send(embed=embed)
            return

        channels = []
        for i, (cid,) in enumerate(rows, 1):
            channel = self.bot.get_channel(cid)
            if channel:
                channels.append(f"`{i}.` {EMOJIS['channel']} {channel.mention}")
            else:
                channels.append(f"`{i}.` {EMOJIS['error']} <#{cid}> *(Channel not found)*")
        
        embed = discord.Embed(
            title=f"{EMOJIS['list']} Greet Channels Configuration",
            description=f"**{len(rows)} channel{'s' if len(rows) != 1 else ''} configured:**\n\n" + "\n".join(channels),
            color=0x006fb9
        )
        embed.set_footer(text=f"Use {ctx.prefix}fastgreet_add or {ctx.prefix}fastgreet_remove to manage channels")
        await ctx.send(embed=embed)

    @commands.group(name="fastgreet", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def fastgreet_help(self, ctx):
        """FastGreet system - Quick welcome messages that auto-delete"""
        embed = discord.Embed(
            title=f"{EMOJIS['settings']} FastGreet System",
            description="Quick welcome messages that automatically delete after a few seconds.",
            color=0x006fb9
        )
        
        embed.add_field(
            name=f"{EMOJIS['welcome']} Commands",
            value=f"`{ctx.prefix}fastgreet_add #channel` - Add a greet channel\n"
                  f"`{ctx.prefix}fastgreet_remove #channel` - Remove a greet channel\n"
                  f"`{ctx.prefix}fastgreet_list` - List all greet channels\n"
                  f"`{ctx.prefix}fastgreet` - Show this help menu",
            inline=False
        )
        
        embed.add_field(
            name=f"{EMOJIS['channel']} How it works",
            value="• When someone joins the server, a welcome message appears in configured channels\n"
                  "• The message shows for 3 seconds then automatically deletes\n"
                  "• Perfect for busy servers where you want quick welcomes without spam",
            inline=False
        )
        
        # Get current channel count
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute("""
                SELECT COUNT(*) FROM greet_channels WHERE guild_id = ?
            """, (ctx.guild.id,))
            channel_count = cursor.fetchone()[0]
        
        embed.add_field(
            name=f"{EMOJIS['list']} Current Status",
            value=f"**{channel_count}** channel{'s' if channel_count != 1 else ''} configured",
            inline=True
        )
        
        embed.set_footer(text="💡 Requires Administrator permissions to manage")
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute("""
                SELECT channel_id FROM greet_channels WHERE guild_id = ?
            """, (member.guild.id,))
            channels = [row[0] for row in cursor.fetchall()]

        for channel_id in channels:
            channel = self.bot.get_channel(channel_id)
            if channel:
                try:
                    # Create a more welcoming message with custom emojis
                    welcome_embed = discord.Embed(
                        description=f"{EMOJIS['welcome']} {member.mention} **Welcome to {member.guild.name}!**",
                        color=0x00ff00
                    )
                    welcome_embed.set_thumbnail(url=member.display_avatar.url)
                    
                    msg = await channel.send(embed=welcome_embed)
                    await asyncio.sleep(3)  # Show for 3 seconds
                    await msg.delete()
                except discord.Forbidden:
                    continue  # Missing permissions
                except discord.NotFound:
                    continue  # Message was already deleted

async def setup(bot):
    await bot.add_cog(FastGreet(bot))
