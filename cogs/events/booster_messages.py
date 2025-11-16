import discord
import aiosqlite
import json
import re
import asyncio
from discord.ext import commands
from utils.timezone_helpers import get_timezone_helpers

class BoosterMessages(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tz_helpers = get_timezone_helpers(bot)

    async def safe_format(self, text, placeholders):
        """Safely format text with placeholders"""
        placeholders_lower = {k.lower(): v for k, v in placeholders.items()}
        def replace_var(match):
            var_name = match.group(1).lower()
            return str(placeholders_lower.get(var_name, f"{{{var_name}}}"))
        return re.sub(r"\{(\w+)\}", replace_var, text or "")

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        """Listen for member boost changes"""
        # Check if this is a boost event
        if not hasattr(before, 'premium_since') or not hasattr(after, 'premium_since'):
            return
        
        # Check if user started boosting (premium_since changed from None to a date)
        if before.premium_since is None and after.premium_since is not None:
            await self.send_boost_message(after)
        # Check if user stopped boosting (premium_since changed from a date to None)
        elif before.premium_since is not None and after.premium_since is None:
            # Could add unboost message here in the future
            pass

    async def send_boost_message(self, member):
        """Send booster message for new booster"""
        guild = member.guild
        
        # Get booster message configuration
        async with aiosqlite.connect("db/booster_messages.db") as db:
            async with db.execute("SELECT * FROM booster_messages WHERE guild_id = ?", (guild.id,)) as cursor:
                row = await cursor.fetchone()
        
        if not row:
            return  # No configuration set
        
        message_type, message_content, channel_id, embed_data, auto_delete_duration = row[1], row[2], row[3], row[4], row[5] if len(row) > 5 else None
        
        # Get the channel
        booster_channel = self.bot.get_channel(channel_id)
        if not booster_channel:
            return  # Channel doesn't exist
        
        # Format boost date with guild timezone
        user_boost_date = await self.tz_helpers.format_datetime_for_guild(
            member.premium_since, guild.id, "%a, %b %d, %Y"
        ) if member.premium_since else "Unknown"
        
        # Create placeholders for the message
        placeholders = {
            "user": member.mention,
            "user_avatar": member.avatar.url if member.avatar else member.default_avatar.url,
            "user_name": member.name,
            "user_id": member.id,
            "user_nick": member.display_name,
            "user_boost_date": user_boost_date,
            "server_name": guild.name,
            "server_id": guild.id,
            "server_boost_count": guild.premium_subscription_count,
            "server_boost_level": guild.premium_tier,
            "server_icon": guild.icon.url if guild.icon else "https://cdn.discordapp.com/embed/avatars/0.png",
            "timestamp": discord.utils.format_dt(discord.utils.utcnow())
        }
        
        try:
            if message_type == "simple" and message_content:
                content = await self.safe_format(message_content, placeholders)
                sent_message = await booster_channel.send(content=content)
                
            elif message_type == "embed" and embed_data:
                embed_info = json.loads(embed_data)
                color_value = embed_info.get("color", "#006fb9")
                
                # Parse color
                embed_color = 0x006fb9
                if color_value and isinstance(color_value, str) and color_value.startswith("#"):
                    try:
                        embed_color = discord.Color(int(color_value.lstrip("#"), 16))
                    except ValueError:
                        embed_color = 0x006fb9
                elif isinstance(color_value, int):
                    embed_color = discord.Color(color_value)
                
                # Format message content (above embed)
                content = await self.safe_format(embed_info.get("message", ""), placeholders) or None
                
                # Create embed
                embed = discord.Embed(
                    title=await self.safe_format(embed_info.get("title", ""), placeholders),
                    description=await self.safe_format(embed_info.get("description", ""), placeholders),
                    color=embed_color
                )
                embed.timestamp = discord.utils.utcnow()
                
                # Add optional embed elements
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
                
                sent_message = await booster_channel.send(content=content, embed=embed)
            
            else:
                return  # Invalid configuration
            
            # Auto-delete if configured
            if auto_delete_duration:
                await sent_message.delete(delay=auto_delete_duration)
                
        except discord.Forbidden:
            # No permissions to send message
            return
        except discord.HTTPException as e:
            # Rate limit or other HTTP error
            if e.code == 50035 or e.status == 429:
                await asyncio.sleep(1)
        except Exception as e:
            # Log any other errors but don't crash
            print(f"Error sending booster message in {guild.name} ({guild.id}): {e}")

async def setup(bot):
    await bot.add_cog(BoosterMessages(bot))