import discord
from discord.ext import commands
from discord.ui import View, Button
import requests
from io import BytesIO
import re
from utils.Tools import *
from PIL import Image, ImageSequence
import math
from typing import Optional

from utils.error_helpers import StandardErrorHandler
class Steal(commands.Cog):
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot

    def compress_image_for_emoji(self, image_data, max_size_kb=256, target_resolution=(128, 128)):
        """
        Compress image data to fit Discord emoji requirements
        - Max file size: 256KB
        - Recommended resolution: 128x128
        """
        return self._compress_image(image_data, max_size_kb, target_resolution, is_emoji=True)
    
    def compress_image_for_sticker(self, image_data, max_size_kb=512, target_resolution=(320, 320)):
        """
        Compress image data to fit Discord sticker requirements
        - Max file size: 512KB
        - Max resolution: 320x320
        """
        return self._compress_image(image_data, max_size_kb, target_resolution, is_emoji=False)
    
    def _compress_image(self, image_data, max_size_kb, target_resolution, is_emoji=True):
        """
        Internal method to compress images with various strategies
        """
        max_size_bytes = max_size_kb * 1024
        
        # Check if image is already within limits
        if len(image_data) <= max_size_bytes:
            try:
                img = Image.open(BytesIO(image_data))
                if img.size[0] <= target_resolution[0] and img.size[1] <= target_resolution[1]:
                    return image_data, False  # No compression needed
            except Exception:
                pass
        
        try:
            img = Image.open(BytesIO(image_data))
            original_format = img.format
            is_animated = getattr(img, 'is_animated', False)
            
            # Start with the target resolution
            new_size = self._calculate_resize_dimensions(img.size, target_resolution)
            
            compressed_data = None
            was_compressed = True
            
            # Strategy 1: Resize to target resolution with high quality
            compressed_data = self._resize_and_compress(img, new_size, quality=95, is_animated=is_animated, is_emoji=is_emoji)
            
            # Strategy 2: If still too large, reduce quality
            if len(compressed_data) > max_size_bytes:
                for quality in [85, 75, 65, 55, 45]:
                    compressed_data = self._resize_and_compress(img, new_size, quality=quality, is_animated=is_animated, is_emoji=is_emoji)
                    if len(compressed_data) <= max_size_bytes:
                        break
            
            # Strategy 3: If still too large, reduce size further
            if len(compressed_data) > max_size_bytes:
                for scale in [0.8, 0.6, 0.5, 0.4]:
                    smaller_size = (int(new_size[0] * scale), int(new_size[1] * scale))
                    if smaller_size[0] < 32 or smaller_size[1] < 32:  # Don't go too small
                        break
                    compressed_data = self._resize_and_compress(img, smaller_size, quality=75, is_animated=is_animated, is_emoji=is_emoji)
                    if len(compressed_data) <= max_size_bytes:
                        break
            
            # Strategy 4: For animated images, reduce frame count if still too large
            if is_animated and len(compressed_data) > max_size_bytes:
                compressed_data = self._reduce_animation_frames(img, new_size, max_size_bytes, is_emoji=is_emoji)
            
            return compressed_data, was_compressed
            
        except Exception as e:
            print(f"[STEAL] Compression failed: {e}")
            # Return original data if compression fails
            return image_data, False
    
    def _calculate_resize_dimensions(self, original_size, target_size):
        """Calculate new dimensions while maintaining aspect ratio"""
        original_w, original_h = original_size
        target_w, target_h = target_size
        
        # If already smaller than target, don't upscale
        if original_w <= target_w and original_h <= target_h:
            return original_size
        
        # Calculate scaling factor to fit within target dimensions
        scale_w = target_w / original_w
        scale_h = target_h / original_h
        scale = min(scale_w, scale_h)
        
        new_w = int(original_w * scale)
        new_h = int(original_h * scale)
        
        return (new_w, new_h)
    
    def _resize_and_compress(self, img, new_size, quality, is_animated, is_emoji):
        """Resize and compress image with specified parameters"""
        output = BytesIO()
        
        if is_animated and img.format == 'GIF':
            # Handle animated GIF
            frames = []
            try:
                for frame in ImageSequence.Iterator(img):
                    frame = frame.convert('RGBA')
                    frame = frame.resize(new_size, Image.Resampling.LANCZOS)
                    frames.append(frame)
                
                if frames:
                    # Save as GIF with compression
                    frames[0].save(
                        output, 
                        format='GIF', 
                        save_all=True, 
                        append_images=frames[1:], 
                        loop=0, 
                        disposal=2,
                        optimize=True
                    )
                else:
                    # Fallback to static image
                    resized = img.resize(new_size, Image.Resampling.LANCZOS).convert('RGBA')
                    resized.save(output, format='PNG', optimize=True)
            except Exception:
                # Fallback to static image
                resized = img.resize(new_size, Image.Resampling.LANCZOS).convert('RGBA')
                resized.save(output, format='PNG', optimize=True)
        else:
            # Handle static image
            resized = img.resize(new_size, Image.Resampling.LANCZOS)
            
            if is_emoji:
                # For emojis, use PNG with transparency support
                resized = resized.convert('RGBA')
                resized.save(output, format='PNG', optimize=True)
            else:
                # For stickers, always use PNG for best Discord compatibility
                # Convert to RGBA to preserve transparency if present
                if resized.mode in ('RGBA', 'LA') or 'transparency' in resized.info:
                    resized = resized.convert('RGBA')
                else:
                    # Even for RGB images, convert to RGBA for consistency
                    resized = resized.convert('RGBA')
                resized.save(output, format='PNG', optimize=True)
        
        return output.getvalue()
    
    def _reduce_animation_frames(self, img, size, max_size_bytes, is_emoji):
        """Reduce animation frame count to fit size limit"""
        if not getattr(img, 'is_animated', False):
            return self._resize_and_compress(img, size, 75, False, is_emoji)
        
        try:
            frames = list(ImageSequence.Iterator(img))
            original_frame_count = len(frames)
            
            # Try reducing frame count
            for frame_skip in [2, 3, 4, 5]:  # Skip every nth frame
                selected_frames = []
                for i in range(0, len(frames), frame_skip):
                    frame = frames[i].convert('RGBA')
                    frame = frame.resize(size, Image.Resampling.LANCZOS)
                    selected_frames.append(frame)
                
                if selected_frames:
                    output = BytesIO()
                    selected_frames[0].save(
                        output,
                        format='GIF',
                        save_all=True,
                        append_images=selected_frames[1:],
                        loop=0,
                        disposal=2,
                        optimize=True
                    )
                    
                    compressed_data = output.getvalue()
                    if len(compressed_data) <= max_size_bytes:
                        print(f"[STEAL] Reduced frames from {original_frame_count} to {len(selected_frames)}")
                        return compressed_data
            
            # If still too large, convert to static image
            first_frame = frames[0].convert('RGBA')
            first_frame = first_frame.resize(size, Image.Resampling.LANCZOS)
            output = BytesIO()
            first_frame.save(output, format='PNG', optimize=True)
            print(f"[STEAL] Converted animated image to static (too large)")
            return output.getvalue()
            
        except Exception as e:
            print(f"[STEAL] Frame reduction failed: {e}")
            return self._resize_and_compress(img, size, 75, False, is_emoji)



    @commands.hybrid_command(name="steal", help="Steal an emoji or sticker", usage="steal <emoji>", aliases=["eadd"], with_app_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def steal(self, ctx, emote=None):
        print(f"[STEAL] Command started - emote parameter: {emote}")
        print(f"[STEAL] Message content: {repr(ctx.message.content)}")
        print(f"[STEAL] Message reference: {ctx.message.reference}")
        print(f"[STEAL] Message embeds: {len(ctx.message.embeds)}")
        print(f"[STEAL] Message attachments: {len(ctx.message.attachments)}")
        print(f"[STEAL] Message stickers: {len(ctx.message.stickers)}")
        
        # Check user permissions and provide helpful error message
        if not ctx.author.guild_permissions.manage_emojis:
            embed = discord.Embed(
                title="❌ Missing Permissions",
                description="You need the **Manage Emojis** permission to use this command.",
                color=0xFF0000
            )
            await ctx.reply(embed=embed)
            return
            
        # Check bot permissions
        if not ctx.guild.me.guild_permissions.manage_emojis:
            embed = discord.Embed(
                title="❌ Bot Missing Permissions",
                description="I need the **Manage Emojis** permission to steal emojis and stickers.",
                color=0xFF0000
            )
            await ctx.reply(embed=embed)
            return
        
        # Quick check: does the command message itself have emojis, attachments, or stickers?
        quick_emojis = await self.extract_emojis_from_text(ctx.message.content)
        if ctx.message.attachments or ctx.message.stickers or quick_emojis:
            print(f"[STEAL] Found content in command message itself!")
            await self.create_buttons(ctx, ctx.message.attachments, ctx.message.stickers, quick_emojis)
            return
            
        # Handle replied messages
        if ctx.message.reference:
            print(f"[STEAL] Processing replied message: {ctx.message.reference.message_id}")
            ref_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            print(f"[STEAL] Reply message content: {repr(ref_message.content)}")
            print(f"[STEAL] Reply message embeds: {len(ref_message.embeds)}")
            print(f"[STEAL] Reply message attachments: {len(ref_message.attachments)}")
            print(f"[STEAL] Reply message stickers: {len(ref_message.stickers)}")
            print(f"[STEAL] Reply message author: {ref_message.author}")
            print(f"[STEAL] Reply message type: {ref_message.type}")
            print(f"[STEAL] Reply message flags: {ref_message.flags}")
            
            # Check if this message has its own reference (forwarded messages might chain references)
            if ref_message.reference:
                print(f"[STEAL] Reply message has its own reference: {ref_message.reference.message_id}")
                try:
                    # Try to fetch from the same channel first
                    try:
                        orig_message = await ctx.channel.fetch_message(ref_message.reference.message_id)
                        print(f"[STEAL] Found original message in same channel")
                    except discord.NotFound:
                        # Message might be in a different channel, try to get the channel
                        if ref_message.reference.channel_id:
                            orig_channel = self.bot.get_channel(ref_message.reference.channel_id)
                            if orig_channel:
                                orig_message = await orig_channel.fetch_message(ref_message.reference.message_id)
                                print(f"[STEAL] Found original message in different channel: {orig_channel.name}")
                            else:
                                print(f"[STEAL] Cannot access channel {ref_message.reference.channel_id}")
                                raise Exception("Channel not accessible")
                        else:
                            raise Exception("No channel info in reference")
                    
                    print(f"[STEAL] Original message content: {repr(orig_message.content)}")
                    print(f"[STEAL] Original message embeds: {len(orig_message.embeds)}")
                    print(f"[STEAL] Original message attachments: {len(orig_message.attachments)}")
                    print(f"[STEAL] Original message stickers: {len(orig_message.stickers)}")
                    
                    # Check for emojis in original message content
                    orig_emojis = await self.extract_emojis_from_text(orig_message.content)
                    print(f"[STEAL] Original message emojis: {orig_emojis}")
                    
                    # If original message has content, use it instead of the forwarded wrapper
                    if orig_message.content or orig_message.embeds or orig_message.attachments or orig_message.stickers or orig_emojis:
                        print(f"[STEAL] Using original message content instead of forwarded wrapper")
                        ref_message = orig_message  # Use the original message instead
                except Exception as e:
                    print(f"[STEAL] Could not fetch original message: {e}")
            
            attachments = list(ref_message.attachments)
            stickers = list(ref_message.stickers)
            # Extract emojis using regex to catch all custom emojis, even from inaccessible servers
            emojis = await self.extract_emojis_from_text(ref_message.content)
            
            # Also check embeds in the replied message for emojis (this is key for forwarded messages!)
            for i, embed in enumerate(ref_message.embeds):
                print(f"[STEAL] Reply embed {i}: type={embed.type}")
                if embed.description:
                    print(f"[STEAL] Reply embed description: {repr(embed.description[:200])}")
                    embed_emojis = await self.extract_emojis_from_text(embed.description)
                    emojis.extend(embed_emojis)
                    print(f"[STEAL] Emojis found in reply embed: {embed_emojis}")
                
                if embed.title:
                    title_emojis = await self.extract_emojis_from_text(embed.title)
                    emojis.extend(title_emojis)
                
                for j, field in enumerate(embed.fields):
                    if field.value:
                        field_emojis = await self.extract_emojis_from_text(field.value)
                        emojis.extend(field_emojis)
            
            print(f"[STEAL] Total items found in reply: {len(attachments)} attachments, {len(stickers)} stickers, {len(emojis)} emojis")
            if attachments or stickers or emojis:
                await self.create_buttons(ctx, attachments, stickers, emojis)
                return
        
        # Handle forwarded messages (check for Discord message URLs or embeds)
        print(f"[STEAL] Checking for forwarded content...")
        forwarded_content = await self.check_for_forwarded_content(ctx.message)
        if forwarded_content:
            attachments, stickers, emojis = forwarded_content
            print(f"[STEAL] Forwarded content found: {len(attachments)} attachments, {len(stickers)} stickers, {len(emojis)} emojis")
            if attachments or stickers or emojis:
                await self.create_buttons(ctx, attachments, stickers, emojis)
                return
        else:
            print(f"[STEAL] No forwarded content found")

        if emote:
            await self.process_emoji(ctx, emote)
        else:
            # Last resort: check if user sent the steal command in a message that contains emojis
            print(f"[STEAL DEBUG] Checking command message itself for content...")
            cmd_emojis = await self.extract_emojis_from_text(ctx.message.content)
            if cmd_emojis:
                print(f"[STEAL DEBUG] Found emojis in command message: {cmd_emojis}")
                await self.create_buttons(ctx, [], [], cmd_emojis)
                return
            
            embed = discord.Embed(
                title="Steal", 
                description="No emoji, sticker, or attachment found to steal.\n\n"
                          "**💡 How to use:**\n"
                          "• Reply to a message with emojis/stickers\n"
                          "• Include emojis in your steal command\n"
                          "• Use `steal <emoji>` directly\n"
                          "• Send Discord message URLs with steal command\n\n"
                          "**🔍 Debug info sent to console**",
                color=0x006fb9
            )
            await ctx.send(embed=embed)

    async def extract_emojis_from_text(self, text):
        """Extract custom emojis from text using regex - works even for inaccessible servers"""
        import re
        emoji_pattern = r'<(a?):([^:]+):(\d+)>'
        matches = re.findall(emoji_pattern, text)
        
        emojis = []
        for animated, name, emoji_id in matches:
            emoji_str = f"<{'a' if animated else ''}:{name}:{emoji_id}>"
            emojis.append(emoji_str)
        
        return emojis
    
    async def check_for_forwarded_content(self, message):
        """
        Check if a message contains forwarded content (Discord message URLs, embeds with emoji/attachments)
        Returns tuple of (attachments, stickers, emojis) if found, None otherwise
        """
        attachments = []
        stickers = []
        emojis = []
        
        # Debug: Print message details
        print(f"[STEAL DEBUG] Checking message:")
        print(f"  - Content: {repr(message.content)}")
        print(f"  - Embeds: {len(message.embeds)}")
        print(f"  - Attachments: {len(message.attachments)}")
        print(f"  - Stickers: {len(message.stickers)}")
        
        # Check message content for emojis first
        content_emojis = await self.extract_emojis_from_text(message.content)
        emojis.extend(content_emojis)
        print(f"  - Emojis in content: {content_emojis}")
        
        # Check message embeds for forwarded content
        for i, embed in enumerate(message.embeds):
            print(f"  - Embed {i}: type={embed.type}, title={embed.title}")
            if embed.description:
                print(f"    Description: {repr(embed.description[:200])}")
                embed_emojis = await self.extract_emojis_from_text(embed.description)
                emojis.extend(embed_emojis)
                print(f"    Emojis in description: {embed_emojis}")
            
            if embed.title:
                title_emojis = await self.extract_emojis_from_text(embed.title)
                emojis.extend(title_emojis)
            
            for j, field in enumerate(embed.fields):
                if field.value:
                    field_emojis = await self.extract_emojis_from_text(field.value)
                    emojis.extend(field_emojis)
                    print(f"    Field {j} emojis: {field_emojis}")
        
        # Check for Discord message URLs in content
        discord_url_pattern = r'https://(?:ptb\.|canary\.)?discord(?:app)?\.com/channels/(\d+)/(\d+)/(\d+)'
        url_matches = re.findall(discord_url_pattern, message.content)
        print(f"  - Discord URLs found: {len(url_matches)}")
        
        for guild_id, channel_id, message_id in url_matches:
            try:
                # Try to fetch the linked message
                target_guild = self.bot.get_guild(int(guild_id))
                if target_guild:
                    target_channel = target_guild.get_channel(int(channel_id))
                    if target_channel:
                        try:
                            target_message = await target_channel.fetch_message(int(message_id))
                            attachments.extend(target_message.attachments)
                            stickers.extend(target_message.stickers)
                            emojis.extend(await self.extract_emojis_from_text(target_message.content))
                        except discord.NotFound:
                            pass
                        except discord.Forbidden:
                            # Bot doesn't have access - try to join the server if possible
                            await self.attempt_guild_join(guild_id)
                else:
                    # Bot is not in the guild - try to join if possible
                    await self.attempt_guild_join(guild_id)
            except Exception as e:
                print(f"[STEAL] Error processing forwarded URL: {e}")
                continue
        
        # Also check if the message itself has attachments or stickers (forwarded content)
        attachments.extend(message.attachments)
        stickers.extend(message.stickers)
        print(f"  - Message attachments: {len(message.attachments)}")
        print(f"  - Message stickers: {len(message.stickers)}")
        
        # Remove duplicates while preserving order
        unique_emojis = []
        seen = set()
        for emoji in emojis:
            if emoji not in seen:
                unique_emojis.append(emoji)
                seen.add(emoji)
        
        print(f"[STEAL DEBUG] Final results:")
        print(f"  - Total attachments: {len(attachments)}")
        print(f"  - Total stickers: {len(stickers)}")
        print(f"  - Total unique emojis: {len(unique_emojis)}")
        
        if attachments or stickers or unique_emojis:
            return (attachments, stickers, unique_emojis)
        return None
    
    async def attempt_guild_join(self, guild_id):
        """
        Attempt to join a guild using various methods
        """
        try:
            guild_id = int(guild_id)
            # Check if bot is already in the guild
            if self.bot.get_guild(guild_id):
                return True
            
            # Method 1: Try to find a public invite link
            invite_found = await self.try_public_invite(guild_id)
            if invite_found:
                return True
            
            # Method 2: Check if any mutual users can provide an invite
            mutual_invite = await self.request_mutual_invite(guild_id)
            if mutual_invite:
                return True
                
            # Method 3: For bot owners, log the request for manual handling
            await self.log_join_request(guild_id)
            
            return False
                
        except Exception as e:
            print(f"[STEAL] Error attempting to join guild {guild_id}: {e}")
            return False
    
    async def try_public_invite(self, guild_id):
        """Try to find and use a public invite for the guild"""
        try:
            # This would require external APIs or databases of public invites
            # For now, we'll just log the attempt
            print(f"[STEAL] Attempting to find public invite for guild {guild_id}")
            # You could integrate with Discord invite APIs or databases here
            return False
        except Exception:
            return False
    
    async def request_mutual_invite(self, guild_id):
        """Check if any mutual server members can provide an invite"""
        try:
            # Find users who are in both current server and target server
            # This is complex and would require checking user mutual guilds
            print(f"[STEAL] Checking for mutual users who could invite to guild {guild_id}")
            return False
        except Exception:
            return False
    
    async def log_join_request(self, guild_id):
        """Log join requests for manual handling by bot owners"""
        try:
            # You could implement a database or file logging system here
            # Or send a message to bot owners about the join request
            owner_ids = [848701010397962251]  # Replace with actual owner IDs
            
            for owner_id in owner_ids:
                try:
                    owner = await self.bot.fetch_user(owner_id)
                    if owner:
                        embed = discord.Embed(
                            title="🔒 Private Server Access Request",
                            description=f"Bot needs access to guild ID: `{guild_id}` to steal emojis from forwarded messages.\n\n"
                                      f"Please consider:\n"
                                      f"• Joining the server manually\n"
                                      f"• Getting an invite link\n"
                                      f"• Adding the bot to that server",
                            color=0x006fb9
                        )
                        await owner.send(embed=embed)
                        break
                except Exception:
                    continue
        except Exception as e:
            print(f"[STEAL] Error logging join request: {e}")

    async def process_emoji(self, ctx, emote):
        try:
            if emote[0] == '<':
                parts = emote.split(':')
                if len(parts) < 3:
                    await ctx.send(embed=discord.Embed(title="Steal", description="Invalid emoji format", color=0x006fb9))
                    return
                    
                name = parts[1]
                emoji_id = parts[2][:-1]  # Remove the closing >
                anim = parts[0]
                
                if not emoji_id or not emoji_id.isdigit():
                    await ctx.send(embed=discord.Embed(title="Steal", description="Invalid emoji ID", color=0x006fb9))
                    return
                    
                # Generate multiple possible URLs for the emoji
                urls_to_try = [
                    f'https://cdn.discordapp.com/emojis/{emoji_id}.gif' if anim == '<a' else f'https://cdn.discordapp.com/emojis/{emoji_id}.png',
                    f'https://cdn.discordapp.com/emojis/{emoji_id}.webp',  # Alternative format
                ]
                
                success = False
                for url in urls_to_try:
                    try:
                        await self.add_emoji(ctx, url, name, animated=(anim == '<a'))
                        success = True
                        break
                    except Exception as e:
                        print(f"[STEAL] Failed with URL {url}: {e}")
                        continue
                
                if not success:
                    await ctx.send(embed=discord.Embed(
                        title="Steal", 
                        description=f"Failed to steal emoji `{name}` - all download methods failed. The emoji may be deleted or corrupted.",
                        color=0x006fb9
                    ))
            else:
                await ctx.send(embed=discord.Embed(title="Steal", description="Invalid emoji", color=0x006fb9))
        except Exception as e:
            await ctx.send(embed=discord.Embed(title="Steal", description=f"Failed to add emoji: {str(e)}", color=0x006fb9))

    async def download_emoji_robust(self, url, animated):
        """
        Try multiple methods to download emoji, including proxies and alternative CDN endpoints
        """
        methods = [
            self.download_direct,
            self.download_with_user_agent,
            self.download_via_proxy_headers,
        ]
        
        for method in methods:
            try:
                result = await method(url)
                if result:
                    return result
            except Exception as e:
                print(f"[STEAL] Method {method.__name__} failed: {e}")
                continue
        
        return None
    
    async def download_direct(self, url):
        """Direct download attempt"""
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            return response.content
        return None
    
    async def download_with_user_agent(self, url):
        """Download with browser user agent"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.content
        return None
    
    async def download_via_proxy_headers(self, url):
        """Download with additional headers that might bypass restrictions"""
        headers = {
            'User-Agent': 'DiscordBot (https://discord.com, 1.0)',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        }
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.content
        return None

    async def add_emoji(self, ctx, url, name, animated):
        try:
            if not self.has_emoji_slot(ctx.guild, animated):
                await ctx.send(embed=discord.Embed(title="Steal", description="No more emoji slots available", color=0x2f3136))
                return

            sanitized_name = self.sanitize_name(name)
            
            # Try multiple methods to download the emoji
            raw_bytes = await self.download_emoji_robust(url, animated)
            if not raw_bytes:
                raise Exception("Failed to download emoji from all available sources")

            # Check if image needs compression
            original_size_kb = len(raw_bytes) / 1024
            print(f"[STEAL] Original image size: {original_size_kb:.1f}KB")
            
            # Compress image if needed for emoji requirements
            compressed_bytes, was_compressed = self.compress_image_for_emoji(raw_bytes)
            final_size_kb = len(compressed_bytes) / 1024
            
            if was_compressed:
                print(f"[STEAL] Compressed image from {original_size_kb:.1f}KB to {final_size_kb:.1f}KB")
                
                # Notify user about compression
                if original_size_kb > 256:
                    compression_msg = f" (compressed from {original_size_kb:.1f}KB to {final_size_kb:.1f}KB)"
                else:
                    compression_msg = f" (resized for optimal quality)"
            else:
                compression_msg = ""

            # Validate final image is still reasonable for emoji
            if len(compressed_bytes) > 256 * 1024:  # 256KB limit
                raise Exception(f"Image too large even after compression ({final_size_kb:.1f}KB). Try a smaller or simpler image.")

            # Validate the compressed image is still valid
            try:
                img_obj = Image.open(BytesIO(compressed_bytes))
                print(f"[STEAL] Final image dimensions: {img_obj.size}")
            except Exception:
                raise Exception("Compressed image is corrupted or invalid")

            # Handle animated images: if animated requested and source has multiple frames, preserve animation
            final_bytes = compressed_bytes
            if animated:
                try:
                    img_obj = Image.open(BytesIO(compressed_bytes))
                    if not getattr(img_obj, 'is_animated', False):
                        # Image was converted to static during compression
                        animated = False
                        print(f"[STEAL] Image converted to static during compression")
                except Exception:
                    animated = False

            emote = await ctx.guild.create_custom_emoji(name=sanitized_name, image=final_bytes)
            
            # Success message with compression info
            success_msg = f"Added emoji \"**{emote}**\"!{compression_msg}"
            await ctx.send(embed=discord.Embed(title="Steal", description=success_msg, color=0x006fb9))
            
        except Exception as e:
            # Give a helpful error message for common issues
            msg = str(e)
            if 'Unsupported image type' in msg or 'could not be parsed' in msg.lower():
                msg = "Unsupported image type — make sure the source is PNG/JPEG or an animated GIF. WebP/APNG will be converted when possible."
            elif 'too large' in msg.lower():
                msg = f"Image too large for emoji: {msg}"
            await ctx.send(embed=discord.Embed(title="Steal", description=f"Failed to add emoji: {msg}", color=0x2f3136))

    async def add_sticker(self, ctx, url, name):
        try:
            if len(ctx.guild.stickers) >= self.get_max_sticker_count(ctx.guild):
                await ctx.send(embed=discord.Embed(title="Steal", description="No more sticker slots available", color=0x006fb9))
                return

            sanitized_name = self.sanitize_name(name)
            
            # Download the image using robust methods (same as emoji)
            raw_bytes = await self.download_emoji_robust(url, False)  # Use the same robust download
            if not raw_bytes:
                raise Exception("Failed to download image from all available sources")
            
            original_size_kb = len(raw_bytes) / 1024
            print(f"[STEAL] Original sticker size: {original_size_kb:.1f}KB")
            
            # Detect if this is an animated format
            is_animated = False
            original_format = None
            
            # Check if it's a Lottie JSON sticker (animated)
            if url.endswith('.json') or b'"tgs":' in raw_bytes[:100] or b'"lottie"' in raw_bytes[:100]:
                is_animated = True
                original_format = 'lottie'
                print(f"[STEAL] Detected Lottie/animated sticker")
            else:
                # Validate that we can read the image first
                try:
                    img_obj = Image.open(BytesIO(raw_bytes))
                    original_format = img_obj.format.lower() if img_obj.format else 'unknown'
                    print(f"[STEAL] Original format: {img_obj.format}, Size: {img_obj.size}")
                    
                    # Check if it's APNG (animated PNG) - better detection
                    if original_format == 'png':
                        # Check for APNG signature in the file
                        if b'acTL' in raw_bytes:  # APNG animation control chunk
                            is_animated = True
                            original_format = 'apng'
                            print(f"[STEAL] Detected APNG (animated PNG) sticker")
                        elif getattr(img_obj, 'is_animated', False):
                            is_animated = True
                            original_format = 'apng'
                            print(f"[STEAL] Detected APNG (animated PNG) sticker via Pillow")
                        
                except Exception:
                    raise Exception("Unsupported image type - make sure the source is a valid image format")
            
            # Handle animated stickers differently to preserve animation
            if is_animated and original_format in ['lottie', 'apng']:
                # For animated stickers, preserve original format
                if len(raw_bytes) > 512 * 1024:  # 512KB limit
                    raise Exception(f"Animated sticker too large ({original_size_kb:.1f}KB). Discord animated stickers must be under 512KB.")
                
                compressed_bytes = raw_bytes
                final_size_kb = original_size_kb
                compression_msg = " (animated format preserved)"
                
                # Set proper file extension for animated formats
                if original_format == 'lottie':
                    file_extension = "json"
                elif original_format == 'apng':
                    file_extension = "png"
                    
                print(f"[STEAL] Preserving animated format: {original_format}")
                
            else:
                # For static stickers, compress if needed
                compressed_bytes, was_compressed = self.compress_image_for_sticker(raw_bytes)
                final_size_kb = len(compressed_bytes) / 1024
                
                if was_compressed:
                    print(f"[STEAL] Compressed sticker from {original_size_kb:.1f}KB to {final_size_kb:.1f}KB")
                    
                    # Notify user about compression
                    if original_size_kb > 512:
                        compression_msg = f" (compressed from {original_size_kb:.1f}KB to {final_size_kb:.1f}KB)"
                    else:
                        compression_msg = f" (optimized for quality)"
                else:
                    compression_msg = ""

                # Validate final image size
                if len(compressed_bytes) > 512 * 1024:  # 512KB limit for stickers
                    raise Exception(f"Image too large even after compression ({final_size_kb:.1f}KB). Try a smaller or simpler image.")

                # Validate and ensure proper format for Discord stickers
                try:
                    img_obj = Image.open(BytesIO(compressed_bytes))
                    print(f"[STEAL] Final sticker format: {img_obj.format}, dimensions: {img_obj.size}")
                    
                    # Check dimensions for stickers (max 320x320)
                    if img_obj.size[0] > 320 or img_obj.size[1] > 320:
                        print(f"[STEAL] Warning: Sticker dimensions {img_obj.size} exceed recommended 320x320")
                    
                    # For static stickers, ensure PNG format for best compatibility
                    if img_obj.format not in ['PNG', 'JPEG']:
                        print(f"[STEAL] Converting {img_obj.format} to PNG for Discord compatibility")
                        # Convert to PNG for better Discord compatibility
                        if img_obj.mode not in ('RGBA', 'RGB'):
                            img_obj = img_obj.convert('RGBA')
                        
                        output = BytesIO()
                        img_obj.save(output, format='PNG', optimize=True)
                        compressed_bytes = output.getvalue()
                        final_size_kb = len(compressed_bytes) / 1024
                        print(f"[STEAL] Converted to PNG, new size: {final_size_kb:.1f}KB")
                    
                except Exception as e:
                    raise Exception(f"Image validation failed: {str(e)}")

                # Set file extension for static stickers
                file_extension = "png"

            # Create Discord File object with proper filename extension
            img_file = discord.File(BytesIO(compressed_bytes), filename=f"sticker.{file_extension}")
            emoji = "⭐"  
            
            sticker = await ctx.guild.create_sticker(
                name=sanitized_name, 
                description="Added by bot", 
                file=img_file, 
                emoji=emoji
            )
            
            # Success message with format info
            format_info = ""
            if is_animated:
                format_info = f" <a:yes:1431909187247673464> **Animated** ({original_format.upper()})"
            
            success_msg = f"Added sticker \"**{sanitized_name}**\"{format_info}!{compression_msg}"
            await ctx.send(embed=discord.Embed(title="Steal", description=success_msg, color=0x006fb9))
            
        except Exception as e:
            # Give helpful error messages
            msg = str(e)
            if 'too large' in msg.lower():
                msg = f"Image too large for sticker: {msg}"
            elif 'unsupported' in msg.lower() or 'invalid' in msg.lower():
                msg = f"Invalid or unsupported image format: {msg}"
            elif 'download' in msg.lower():
                msg = f"Could not download image: {msg}"
            elif 'validation failed' in msg.lower():
                msg = f"Image processing error: {msg}"
            await ctx.send(embed=discord.Embed(title="Steal", description=f"Failed to add sticker: {msg}", color=0x006fb9))

    def sanitize_name(self, name):
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        return sanitized[:32]  

    def has_emoji_slot(self, guild, animated):
        normal_emojis = [emoji for emoji in guild.emojis if not emoji.animated]
        animated_emojis = [emoji for emoji in guild.emojis if emoji.animated]
        max_normal, max_animated = self.get_max_emoji_count(guild)

        if animated:
            return len(animated_emojis) < max_animated
        else:
            return len(normal_emojis) < max_normal

    def get_max_emoji_count(self, guild):
        if guild.premium_tier == 3:
            return 250, 250
        elif guild.premium_tier == 2:
            return 150, 150
        elif guild.premium_tier == 1:
            return 100, 100
        else:
            return 50, 50

    def get_max_sticker_count(self, guild):
        if guild.premium_tier == 3:
            return 60
        elif guild.premium_tier == 2:
            return 30
        elif guild.premium_tier == 1:
            return 15
        else:
            return 5

    async def create_buttons(self, ctx, attachments, stickers, emojis):
        class StealView(View):
            def __init__(self, bot, ctx, attachments, stickers, emojis):
                super().__init__()
                self.bot = bot
                self.ctx = ctx
                self.attachments = attachments
                self.stickers = stickers
                self.emojis = emojis

            @discord.ui.button(label="Steal as Emoji", style=discord.ButtonStyle.primary)
            async def steal_as_emoji(self, interaction: discord.Interaction, button: discord.ui.Button):
                
                if interaction.user.id != self.ctx.author.id:
                    await interaction.response.send_message("This interaction is not for you.", ephemeral=True)
                    return
                await interaction.response.defer()
                for sticker in self.stickers:
                    
                    if sticker.format in [discord.StickerFormatType.png, discord.StickerFormatType.apng, discord.StickerFormatType.lottie]:
                        animated = sticker.format == discord.StickerFormatType.apng
                        await self.bot.cogs['Steal'].add_emoji(self.ctx, sticker.url, sticker.name.replace(' ', '_'), animated=animated)
                    else:
                        await self.ctx.send(embed=discord.Embed(title="Steal", description=f"Unsupported sticker format for {sticker.name}", color=0x006fb9))
                for attachment in self.attachments:
                    await self.bot.cogs['Steal'].add_emoji(self.ctx, attachment.url, attachment.filename.split('.')[0].replace(' ', '_'), animated=False)
                for emote in self.emojis:
                    name = emote.split(':')[1]
                    emoji_id = emote.split(':')[2][:-1]
                    anim = emote.split(':')[0]
                    if anim == '<a':
                        url = f'https://cdn.discordapp.com/emojis/{emoji_id}.gif'
                    else:
                        url = f'https://cdn.discordapp.com/emojis/{emoji_id}.png'
                    await self.bot.cogs['Steal'].add_emoji(self.ctx, url, name, animated=(anim == '<a'))

            @discord.ui.button(label="Steal as Sticker", style=discord.ButtonStyle.success)
            async def steal_as_sticker(self, interaction: discord.Interaction, button: discord.ui.Button):
                
                if interaction.user.id != self.ctx.author.id:
                    await interaction.response.send_message("This interaction is not for you.", ephemeral=True)
                    return
                await interaction.response.defer()
                for sticker in self.stickers:
                    await self.bot.cogs['Steal'].add_sticker(self.ctx, sticker.url, sticker.name)
                for attachment in self.attachments:
                    await self.bot.cogs['Steal'].add_sticker(self.ctx, attachment.url, attachment.filename.split('.')[0])
                for emote in self.emojis:
                    name = emote.split(':')[1]
                    emoji_id = emote.split(':')[2][:-1]
                    anim = emote.split(':')[0]
                    if anim == '<a':
                        url = f'https://cdn.discordapp.com/emojis/{emoji_id}.gif'
                    else:
                        url = f'https://cdn.discordapp.com/emojis/{emoji_id}.png'
                    await self.bot.cogs['Steal'].add_sticker(self.ctx, url, name)

        embed = discord.Embed(description="Choose what to steal:", color=0x006fb9)
        if attachments:
            embed.set_image(url=attachments[0].url)
        elif stickers:
            embed.set_image(url=stickers[0].url)
        elif emojis:
            for emote in emojis:
                emoji_id = emote.split(':')[2][:-1]
                url = f"https://cdn.discordapp.com/emojis/{emoji_id}.png"
                embed.set_image(url=url)

        view = StealView(self.bot, ctx, attachments, stickers, emojis)
        await ctx.send(embed=embed, view=view)
    
    @commands.command(name="forcejoin", help="(Owner only) Attempt to join a server by ID for emoji access", hidden=True)
    @commands.is_owner()
    async def force_join_guild(self, ctx, guild_id: Optional[int] = None, *, invite_code: Optional[str] = None):
        """Allow bot owners to manually attempt joining servers for emoji access"""
        if not guild_id and not invite_code:
            embed = discord.Embed(
                title="❌ Missing Parameters",
                description="Usage: `forcejoin <guild_id>` or `forcejoin invite:<invite_code>`",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return
        
        if invite_code:
            try:
                invite = await self.bot.fetch_invite(invite_code)
                embed = discord.Embed(
                    title="🔗 Joining Server via Invite",
                    description=f"Attempting to join **{invite.guild.name}** (ID: {invite.guild.id})",
                    color=0x006fb9
                )
                await ctx.send(embed=embed)
                
                # Join using invite
                await invite.accept()
                
                success_embed = discord.Embed(
                    title="✅ Successfully Joined!",
                    description=f"Bot has joined **{invite.guild.name}**\nYou can now steal emojis from this server!",
                    color=0x00FF00
                )
                await ctx.send(embed=success_embed)
                
            except discord.NotFound:
                await ctx.send(embed=discord.Embed(title="❌ Invalid Invite", description="The invite code is invalid or expired.", color=0xFF0000))
            except discord.HTTPException as e:
                await ctx.send(embed=discord.Embed(title="❌ Join Failed", description=f"Could not join server: {str(e)}", color=0xFF0000))
        
        elif guild_id:
            # Check if already in guild
            guild = self.bot.get_guild(guild_id)
            if guild:
                embed = discord.Embed(
                    title="✅ Already in Server",
                    description=f"Bot is already in **{guild.name}** (ID: {guild_id})",
                    color=0x00FF00
                )
                await ctx.send(embed=embed)
                return
            
            # Log the manual join request
            embed = discord.Embed(
                title="🔍 Manual Join Requested",
                description=f"Guild ID: `{guild_id}`\n\n"
                          f"**Next Steps:**\n"
                          f"• Find an invite link for this server\n"
                          f"• Use `{ctx.prefix}forcejoin invite:<code>` to join\n"
                          f"• Or manually add the bot to that server",
                color=0x006fb9
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="stealdebug", help="Debug forwarded message content", hidden=True)
    async def steal_debug(self, ctx):
        """Debug command to see what's in a message"""
        msg = ctx.message
        
        debug_info = []
        debug_info.append(f"**Message Content:** {repr(msg.content)}")
        debug_info.append(f"**Reference:** {msg.reference}")
        debug_info.append(f"**Embeds:** {len(msg.embeds)}")
        debug_info.append(f"**Attachments:** {len(msg.attachments)}")
        debug_info.append(f"**Stickers:** {len(msg.stickers)}")
        
        # Check for emojis in content
        emojis = await self.extract_emojis_from_text(msg.content)
        debug_info.append(f"**Emojis in Content:** {emojis}")
        
        # Check embeds
        for i, embed in enumerate(msg.embeds):
            debug_info.append(f"**Embed {i}:**")
            debug_info.append(f"  - Type: {embed.type}")
            debug_info.append(f"  - Title: {embed.title}")
            debug_info.append(f"  - Description: {repr(embed.description[:100]) if embed.description else None}")
            if embed.description:
                embed_emojis = await self.extract_emojis_from_text(embed.description)
                debug_info.append(f"  - Emojis: {embed_emojis}")
        
        embed_msg = discord.Embed(
            title="🔍 Message Debug Info",
            description="\n".join(debug_info),
            color=0x006fb9
        )
        
        await ctx.send(embed=embed_msg)
    
    @commands.command(name="msginfo", help="Get detailed info about a message (reply to use)", hidden=True)
    async def message_info(self, ctx):
        """Debug command to get detailed message information"""
        target_msg = ctx.message
        
        if ctx.message.reference:
            target_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            info_title = "📋 Replied Message Info"
        else:
            info_title = "📋 Command Message Info"
        
        info_lines = []
        info_lines.append(f"**ID:** {target_msg.id}")
        info_lines.append(f"**Author:** {target_msg.author}")
        info_lines.append(f"**Type:** {target_msg.type}")
        info_lines.append(f"**Flags:** {target_msg.flags}")
        info_lines.append(f"**Content:** {repr(target_msg.content)}")
        info_lines.append(f"**Embeds:** {len(target_msg.embeds)}")
        info_lines.append(f"**Attachments:** {len(target_msg.attachments)}")
        info_lines.append(f"**Stickers:** {len(target_msg.stickers)}")
        
        if target_msg.reference:
            info_lines.append(f"**Has Reference:** Yes ({target_msg.reference.message_id})")
            # Try to get info about the referenced message too
            try:
                try:
                    ref_msg = await ctx.channel.fetch_message(target_msg.reference.message_id)
                except discord.NotFound:
                    if target_msg.reference.channel_id:
                        ref_channel = self.bot.get_channel(target_msg.reference.channel_id)
                        if ref_channel:
                            ref_msg = await ref_channel.fetch_message(target_msg.reference.message_id)
                        else:
                            raise Exception("Cannot access reference channel")
                    else:
                        raise Exception("No channel in reference")
                
                ref_emojis = await self.extract_emojis_from_text(ref_msg.content)
                info_lines.append(f"**Referenced Message:**")
                info_lines.append(f"  - Content: {repr(ref_msg.content[:50])}")
                info_lines.append(f"  - Emojis: {ref_emojis}")
                info_lines.append(f"  - Embeds: {len(ref_msg.embeds)}")
                
            except Exception as e:
                info_lines.append(f"**Referenced Message:** Could not fetch ({e})")
        else:
            info_lines.append(f"**Has Reference:** No")
        
        # Check for emojis
        emojis = await self.extract_emojis_from_text(target_msg.content)
        info_lines.append(f"**Emojis in Content:** {emojis}")
        
        # Check embeds in detail
        for i, embed in enumerate(target_msg.embeds):
            info_lines.append(f"**Embed {i}:**")
            info_lines.append(f"  - Type: {embed.type}")
            info_lines.append(f"  - Title: {embed.title}")
            info_lines.append(f"  - Description: {repr(embed.description[:100]) if embed.description else None}")
            if embed.description:
                embed_emojis = await self.extract_emojis_from_text(embed.description)
                info_lines.append(f"  - Emojis: {embed_emojis}")
        
        embed_msg = discord.Embed(
            title=info_title,
            description="\n".join(info_lines),
            color=0x006fb9
        )
        
        await ctx.send(embed=embed_msg)



"""
@Author: Frosty
    + Discord: frosty.pyro
    + Community: https://discord.gg/5wtjDkYbVh (Sleepless Development)
    + for any queries reach out in the server; or send a dm.
"""