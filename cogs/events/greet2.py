import discord
import aiosqlite
import json
import re
import asyncio
from discord.ext import commands
from discord.ui import View, Button
from utils.timezone_helpers import get_timezone_helpers
from utils.enhanced_button_manager import EnhancedButtonManager
from utils.button_integration import ButtonIntegrationHelper
from utils.button_database import load_embed_buttons, track_button_interaction

class greet(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.join_queue = {}
        self.processing = set()
        self.tz_helpers = get_timezone_helpers(bot)

    async def safe_format(self, text, placeholders):
        placeholders_lower = {k.lower(): v for k, v in placeholders.items()}
        def replace_var(match):
            var_name = match.group(1).lower()
            return str(placeholders_lower.get(var_name, f"{{{var_name}}}"))
        return re.sub(r"\{(\w+)\}", replace_var, text or "")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        print(f"[DEBUG GREET] Member {member} ({member.id}) joined guild {member.guild.name} ({member.guild.id})")
        
        # Skip bots to reduce processing load
        if member.bot:
            print(f"[DEBUG GREET] Skipping bot {member}")
            return
        
        # Check if guild is very large (>10k members) and implement special handling
        if member.guild.member_count and member.guild.member_count > 10000:
            print(f"[DEBUG GREET] Large guild detected ({member.guild.member_count} members), using optimized processing")
            await self.handle_large_guild_join(member)
            return
        
        # Normal processing for smaller guilds
        if member.guild.id not in self.join_queue:
            self.join_queue[member.guild.id] = []
        
        # Limit queue size to prevent memory issues
        if len(self.join_queue[member.guild.id]) > 50:
            print(f"[DEBUG GREET] Queue full for guild {member.guild.id}, processing oldest member")
            old_member = self.join_queue[member.guild.id].pop(0)
            print(f"[DEBUG GREET] Removed {old_member} from queue due to overflow")
        
        self.join_queue[member.guild.id].append(member)
        print(f"[DEBUG GREET] Added {member} to join queue for guild {member.guild.id}")
        
        if member.guild.id not in self.processing:
            self.processing.add(member.guild.id)
            print(f"[DEBUG GREET] Starting queue processing for guild {member.guild.id}")
            await self.process_queue(member.guild)

    async def handle_large_guild_join(self, member):
        """Special handling for large guilds to avoid rate limits and performance issues"""
        try:
            # Direct processing for large guilds - no queue to avoid memory issues
            async with aiosqlite.connect("db/welcome.db") as db:
                async with db.execute("SELECT welcome_type, welcome_message, channel_id, embed_data, auto_delete_duration, button_data FROM welcome WHERE guild_id = ?", (member.guild.id,)) as cursor:
                    row = await cursor.fetchone()
                    
            if row is None:
                print(f"[DEBUG GREET] No welcome configuration found for large guild {member.guild.id}")
                return
                
            await self.send_welcome_message(member, row, is_large_guild=True)
            
        except Exception as e:
            print(f"[DEBUG GREET] Error handling large guild join for {member}: {e}")

    async def send_welcome_message(self, member, config_row, is_large_guild=False):
        """Send welcome message with enhanced error handling"""
        welcome_type, welcome_message, channel_id, embed_data, auto_delete_duration, button_data = config_row
        guild = member.guild
        
        print(f"[DEBUG GREET] Found config: type={welcome_type}, channel={channel_id}")
        welcome_channel = self.bot.get_channel(channel_id)
        if not welcome_channel:
            print(f"[DEBUG GREET] Welcome channel {channel_id} not found or bot has no access")
            return
        
        print(f"[DEBUG GREET] Sending welcome message to {welcome_channel.name} for {member}")
        
        # Create enhanced buttons view if button data exists
        view = None
        if button_data:
            try:
                # Try loading from enhanced button database first
                enhanced_manager = await load_embed_buttons(guild.id, "welcome", "main")
                
                if enhanced_manager and enhanced_manager.buttons:
                    # Use enhanced button manager
                    view = enhanced_manager.create_view(guild)
                    print(f"[DEBUG GREET] Using enhanced buttons: {len(enhanced_manager.buttons)} buttons")
                else:
                    # Fall back to legacy button data
                    legacy_buttons = json.loads(button_data) if isinstance(button_data, str) else button_data
                    if legacy_buttons:
                        # Migrate legacy buttons to enhanced format
                        enhanced_manager = ButtonIntegrationHelper.create_button_manager_from_data(legacy_buttons)
                        view = enhanced_manager.create_view(guild)
                        print(f"[DEBUG GREET] Using migrated legacy buttons: {len(legacy_buttons)} buttons")
                        
            except (json.JSONDecodeError, Exception) as e:
                print(f"[DEBUG GREET] Error creating button view: {e}")
                view = None
        
        # Format join and create dates with guild timezone
        try:
            user_joindate = await self.tz_helpers.format_datetime_for_guild(
                member.joined_at, guild, "%a, %b %d, %Y"
            ) if member.joined_at else "Unknown"
            
            user_createdate = await self.tz_helpers.format_datetime_for_guild(
                member.created_at, guild, "%a, %b %d, %Y"
            )
        except Exception as e:
            print(f"[DEBUG GREET] Error formatting dates: {e}")
            user_joindate = "Unknown"
            user_createdate = "Unknown"
        
        placeholders = {
            "user": member.mention,
            "user_avatar": member.avatar.url if member.avatar else member.default_avatar.url,
            "user_name": member.name,
            "user_id": member.id,
            "user_nick": member.display_name,
            "user_joindate": user_joindate,
            "user_createdate": user_createdate,
            "server_name": guild.name,
            "server_id": guild.id,
            "server_membercount": guild.member_count,
            "server_icon": guild.icon.url if guild.icon else "https://cdn.discordapp.com/embed/avatars/0.png",
            "timestamp": discord.utils.format_dt(discord.utils.utcnow())
        }
        
        max_retries = 3 if is_large_guild else 1
        retry_delay = 5 if is_large_guild else 2
        
        for attempt in range(max_retries):
            try:
                if welcome_type == "simple" and welcome_message:
                    content = await self.safe_format(welcome_message, placeholders)
                    sent_message = await welcome_channel.send(content=content, view=view)
                elif welcome_type == "embed" and embed_data:
                    embed_info = json.loads(embed_data)
                    color_value = embed_info.get("color", None)
                    embed_color = 0x2f3136
                    if color_value and isinstance(color_value, str) and color_value.startswith("#"):
                        embed_color = discord.Color(int(color_value.lstrip("#"), 16))
                    elif isinstance(color_value, int):
                        embed_color = discord.Color(color_value)
                    content = await self.safe_format(embed_info.get("message", ""), placeholders) or None
                    embed = discord.Embed(
                        title=await self.safe_format(embed_info.get("title", ""), placeholders),
                        description=await self.safe_format(embed_info.get("description", ""), placeholders),
                        color=embed_color
                    )
                    embed.timestamp = discord.utils.utcnow()
                    if embed_info.get("footer_text"):
                        embed.set_footer(
                            text=await self.safe_format(embed_info["footer_text"], placeholders),
                            icon_url=await self.safe_format(embed_info.get("footer_icon", ""), placeholders)
                        )
                    if embed_info.get("author_name"):
                        embed.set_author(
                            name=await self.safe_format(embed_info["author_name"], placeholders),
                            icon_url=await self.safe_format(embed_info.get("author_icon", ""), placeholders)
                        )
                    if embed_info.get("thumbnail"):
                        embed.set_thumbnail(url=await self.safe_format(embed_info["thumbnail"], placeholders))
                    if embed_info.get("image"):
                        embed.set_image(url=await self.safe_format(embed_info["image"], placeholders))
                    sent_message = await welcome_channel.send(content=content, embed=embed, view=view)
                
                # Schedule auto-delete if configured
                if auto_delete_duration and sent_message:
                    await sent_message.delete(delay=auto_delete_duration)
                    
                print(f"[DEBUG GREET] Successfully sent welcome message for {member}")
                return  # Success, exit retry loop
                
            except discord.Forbidden:
                print(f"[DEBUG GREET] Forbidden: Bot lacks permissions in {welcome_channel.name}")
                return  # Don't retry on permission errors
                
            except discord.HTTPException as e:
                if e.status == 429:  # Rate limited
                    print(f"[DEBUG GREET] Rate limited (attempt {attempt + 1}/{max_retries}), waiting {retry_delay * (attempt + 1)} seconds")
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                elif e.code == 50035:  # Invalid form body
                    print(f"[DEBUG GREET] Invalid message content for {member}")
                    return  # Don't retry on content errors
                else:
                    print(f"[DEBUG GREET] HTTP Exception: {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                        continue
                    return
                    
            except Exception as e:
                print(f"[DEBUG GREET] Unexpected error sending welcome for {member}: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    continue
                return
        
        print(f"[DEBUG GREET] Failed to send welcome message for {member} after {max_retries} attempts")

    async def process_queue(self, guild):
        print(f"[DEBUG GREET] Processing queue for guild {guild.name} ({guild.id})")
        
        while self.join_queue.get(guild.id):
            member = self.join_queue[guild.id].pop(0)
            print(f"[DEBUG GREET] Processing member {member} from queue")
            
            try:
                async with aiosqlite.connect("db/welcome.db") as db:
                    async with db.execute("SELECT welcome_type, welcome_message, channel_id, embed_data, auto_delete_duration, button_data FROM welcome WHERE guild_id = ?", (guild.id,)) as cursor:
                        row = await cursor.fetchone()
                        
                if row is None:
                    print(f"[DEBUG GREET] No welcome configuration found for guild {guild.id}")
                    continue
                
                await self.send_welcome_message(member, row, is_large_guild=False)
                
                # Add delay between processing to avoid rate limits
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"[DEBUG GREET] Error processing {member} in queue: {e}")
                continue
        
        # Remove guild from processing set
        if guild.id in self.processing:
            self.processing.remove(guild.id)
        print(f"[DEBUG GREET] Finished processing queue for guild {guild.id}")

async def setup(bot):
    await bot.add_cog(greet(bot))

