import discord
from discord.ext import commands, tasks
import asyncio
import re
import datetime
from typing import Union, Optional
from collections import Counter
from utils.Tools import *
from discord.ui import Button, View
from io import BytesIO
import requests
import aiohttp
import time
from datetime import datetime, timezone, timedelta


time_regex = re.compile(r"(?:(\d{1,5})(h|s|m|d))+?")
time_dict = {"h": 3600, "s": 1, "m": 60, "d": 86400}


def convert(argument):
  args = argument.lower()
  matches = re.findall(time_regex, args)
  time = 0
  for key, value in matches:
    try:
      time += time_dict[value] * float(key)
    except KeyError:
      raise commands.BadArgument(
        f"{value} is an invalid time key! h|m|s|d are valid arguments")
    except ValueError:
      raise commands.BadArgument(f"{key} is not a number!")
  return round(time)

async def do_removal(ctx, limit, predicate, *, before=None, after=None):
  if limit > 2000:
      return await ctx.error(f"Too many messages to search given ({limit}/2000)")

  if before is None:
      before = ctx.message
  else:
      before = discord.Object(id=before)

  if after is not None:
      after = discord.Object(id=after)

  try:
      deleted = await ctx.channel.purge(limit=limit, before=before, after=after, check=predicate)
  except discord.Forbidden as e:
      return await ctx.error("I do not have permissions to delete messages.")
  except discord.HTTPException as e:
      return await ctx.error(f"Error: {e} (try a smaller search?)")

  spammers = Counter(m.author.display_name for m in deleted)
  deleted = len(deleted)
  messages = [f'<:feast_tick:1400143469892210753> | {deleted} message{" was" if deleted == 1 else "s were"} removed.']
  if deleted:
      messages.append("")
      spammers = sorted(spammers.items(), key=lambda t: t[1], reverse=True)
      messages.extend(f"**{name}**: {count}" for name, count in spammers)

  to_send = "\n".join(messages)

  if len(to_send) > 2000:
      await ctx.send(f"<:feast_tick:1400143469892210753> | Successfully removed {deleted} messages.", delete_after=7)
  else:
      await ctx.send(to_send, delete_after=7)
    

class Message(commands.Cog):

  def __init__(self, bot):
    self.bot = bot
    self.color = 0x006fb9


  @commands.group(invoke_without_command=True, aliases=["purge"], help="Clears the messages")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  @commands.has_permissions(manage_messages=True)
  @commands.bot_has_permissions(manage_messages=True)
  async def clearmsg(self, ctx, Choice: Union[discord.Member, int], Amount: Optional[int] = None):
        await ctx.message.delete()

        if isinstance(Choice, discord.Member):
            search = Amount or 5
            return await do_removal(ctx, search, lambda e: e.author == Choice)

        elif isinstance(Choice, int):
            return await do_removal(ctx, Choice, lambda e: True)



  @clearmsg.command(help="Clears the messages having embeds")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  @commands.has_permissions(manage_messages=True)
  @commands.bot_has_permissions(manage_messages=True)
  async def embeds(self, ctx, search=100):
        await ctx.message.delete()
        await do_removal(ctx, search, lambda e: len(e.embeds))


  @clearmsg.command(help="Clears the messages having files")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  @commands.has_permissions(manage_messages=True)
  @commands.bot_has_permissions(manage_messages=True)
  async def files(self, ctx, search=100):

        await ctx.message.delete()
        await do_removal(ctx, search, lambda e: len(e.attachments))

  @clearmsg.command(help="Clears the messages having images")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  @commands.has_permissions(manage_messages=True)
  @commands.bot_has_permissions(manage_messages=True)
  async def images(self, ctx, search=100):

        await ctx.message.delete()
        await do_removal(ctx, search, lambda e: len(e.embeds) or len(e.attachments))


  @clearmsg.command(name="all", help="Clears all messages")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  @commands.has_permissions(manage_messages=True)
  @commands.bot_has_permissions(manage_messages=True)
  async def _remove_all(self, ctx, search=100):

        await ctx.message.delete()
        await do_removal(ctx, search, lambda e: True)

  @clearmsg.command(help="Clears the messages of a specific user")
  @commands.has_permissions(manage_messages=True)
  @commands.bot_has_permissions(manage_messages=True)
  async def user(self, ctx, member: discord.Member, search=100):

        await ctx.message.delete()
        await do_removal(ctx, search, lambda e: e.author == member)



  @clearmsg.command(help="Clears the messages containing a specifix string")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  @commands.has_permissions(manage_messages=True)
  @commands.bot_has_permissions(manage_messages=True)
  async def contains(self, ctx, *, string: str):

        await ctx.message.delete()
        if len(string) < 3:
            await ctx.error("The substring length must be at least 3 characters.")
        else:
            await do_removal(ctx, 100, lambda e: string in e.content)

  @clearmsg.command(name="bot", aliases=["bots","b"], help="Clears the messages sent by bot")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  @commands.has_permissions(manage_messages=True)
  @commands.bot_has_permissions(manage_messages=True)
  async def _bot(self, ctx, prefix=None, search=100):

        await ctx.message.delete()

        def predicate(m):
            return (m.webhook_id is None and m.author.bot) or (prefix and m.content.startswith(prefix))

        await do_removal(ctx, search, predicate)

  @clearmsg.command(name="emoji", aliases=["emojis"], help="Clears the messages having emojis")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  @commands.has_permissions(manage_messages=True)
  @commands.bot_has_permissions(manage_messages=True)

  async def _emoji(self, ctx, search=100):

        await ctx.message.delete()
        custom_emoji = re.compile(r"<a?:[a-zA-Z0-9\_]+:([0-9]+)>")

        def predicate(m):
            return custom_emoji.search(m.content)

        await do_removal(ctx, search, predicate)

  @clearmsg.command(name="reactions", help="Clears the reaction from the messages")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  @commands.has_permissions(manage_messages=True)
  @commands.bot_has_permissions(manage_messages=True)
  async def _reactions(self, ctx, search=100):

        await ctx.message.delete()

        if search > 2000:
            return await ctx.send(f"Too many messages to search for ({search}/2000)")

        total_reactions = 0
        async for message in ctx.history(limit=search, before=ctx.message):
            if len(message.reactions):
                total_reactions += sum(r.count for r in message.reactions)
                await message.clear_reactions()

        await ctx.success(f"<:feast_tick:1400143469892210753> | Successfully removed {total_reactions} reactions.")
            



  @commands.command(name="purgebots",
                    aliases=["cleanup", "pb", "clearbot", "clearbots"],
                    help="Clear recently bot messages in channel")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  @commands.has_permissions(manage_messages=True)
  @commands.bot_has_permissions(manage_messages=True)
  async def _purgebot(self, ctx, prefix=None, search=100):

    await ctx.message.delete()

    def predicate(m):
        return (m.webhook_id is None and m.author.bot) or (prefix and m.content.startswith(prefix))
      
    await do_removal(ctx, search, predicate)

  @commands.group(name="purgebots-all", aliases=["purgebotsguild", "clearbotsall"], invoke_without_command=True)
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 30, commands.BucketType.guild)  # Longer cooldown for server-wide
  @commands.has_permissions(administrator=True)  # Require admin for server-wide
  @commands.bot_has_permissions(manage_messages=True)
  async def purgebots_all(self, ctx, search_per_channel: int = 100):
    """Clear bot messages from ALL channels in the server
    
    This is a powerful command that purges bot messages from every channel.
    Requires Administrator permission due to its scope.
    
    Usage:
    purgebots-all - Remove last 100 bot messages from each channel
    purgebots-all 50 - Remove last 50 bot messages from each channel
    """
    
    if search_per_channel < 1 or search_per_channel > 500:
        return await ctx.error("Search limit per channel must be between 1 and 500.")
    
    # Confirmation for safety
    confirm_msg = await ctx.send(
        f"⚠️ **Server-wide Bot Purge Confirmation**\n"
        f"This will search up to **{search_per_channel}** messages in **every channel** and delete bot messages.\n"
        f"This action affects the entire server and cannot be undone.\n\n"
        f"React with ✅ to confirm or ❌ to cancel."
    )
    
    await confirm_msg.add_reaction("✅")
    await confirm_msg.add_reaction("❌")
    
    def check(reaction, user):
        return (user == ctx.author and 
                str(reaction.emoji) in ["✅", "❌"] and 
                reaction.message.id == confirm_msg.id)
    
    try:
        reaction, user = await self.bot.wait_for('reaction_add', timeout=30.0, check=check)
    except asyncio.TimeoutError:
        await confirm_msg.edit(content="❌ Confirmation timeout. Server-wide purge cancelled.")
        return
    
    if str(reaction.emoji) == "❌":
        await confirm_msg.edit(content="❌ Server-wide purge cancelled.")
        return
    
    # Start the purge process
    await confirm_msg.edit(content="🗑️ Starting server-wide bot message purge...")
    
    total_deleted = 0
    channels_processed = 0
    channels_skipped = 0
    errors = 0
    
    # Get all text channels
    text_channels = [ch for ch in ctx.guild.channels if isinstance(ch, discord.TextChannel)]
    
    progress_msg = await ctx.send(f"📊 **Progress**: 0/{len(text_channels)} channels processed...")
    
    for channel in text_channels:
        try:
            # Check if bot has permissions in this channel
            if not channel.permissions_for(ctx.guild.me).manage_messages:
                channels_skipped += 1
                continue
            
            # Check if bot can read message history
            if not channel.permissions_for(ctx.guild.me).read_message_history:
                channels_skipped += 1
                continue
            
            # Create predicate for bot messages only (no prefix option for safety)
            def predicate(m):
                return m.webhook_id is None and m.author.bot
            
            # Get messages to delete
            messages_to_delete = []
            async for message in channel.history(limit=search_per_channel):
                if predicate(message):
                    messages_to_delete.append(message)
            
            if messages_to_delete:
                # Separate by age for bulk delete
                two_weeks_ago = datetime.now(timezone.utc) - timedelta(days=14)
                bulk_messages = [msg for msg in messages_to_delete if msg.created_at > two_weeks_ago]
                old_messages = [msg for msg in messages_to_delete if msg.created_at <= two_weeks_ago]
                
                # Bulk delete newer messages
                if bulk_messages:
                    for i in range(0, len(bulk_messages), 100):
                        batch = bulk_messages[i:i + 100]
                        try:
                            if len(batch) == 1:
                                await batch[0].delete()
                            else:
                                await channel.delete_messages(batch)
                            total_deleted += len(batch)
                        except discord.HTTPException:
                            # If bulk fails, try individual
                            for msg in batch:
                                try:
                                    await msg.delete()
                                    total_deleted += 1
                                    await asyncio.sleep(0.1)
                                except:
                                    pass
                        
                        # Small delay between batches
                        if i + 100 < len(bulk_messages):
                            await asyncio.sleep(0.5)
                
                # Individual delete for old messages
                for msg in old_messages:
                    try:
                        await msg.delete()
                        total_deleted += 1
                        await asyncio.sleep(0.1)
                    except:
                        pass
            
            channels_processed += 1
            
            # Update progress every 5 channels
            if channels_processed % 5 == 0:
                try:
                    await progress_msg.edit(
                        content=f"📊 **Progress**: {channels_processed}/{len(text_channels)} channels processed\n"
                                f"🗑️ **Deleted**: {total_deleted} bot messages so far"
                    )
                except:
                    pass
            
            # Rate limiting between channels
            await asyncio.sleep(1)
            
        except Exception as e:
            errors += 1
            print(f"Error processing channel {channel.name}: {e}")
            continue
    
    # Final summary
    embed = discord.Embed(
        title="🗑️ Server-wide Bot Purge Complete",
        color=0x00ff00,
        timestamp=datetime.now(timezone.utc)
    )
    
    embed.add_field(
        name="📊 Summary",
        value=f"**Channels Processed**: {channels_processed}/{len(text_channels)}\n"
              f"**Channels Skipped**: {channels_skipped} (no permissions)\n"
              f"**Bot Messages Deleted**: {total_deleted}\n"
              f"**Errors**: {errors}",
        inline=False
    )
    
    embed.add_field(
        name="⚙️ Settings Used",
        value=f"**Search Limit per Channel**: {search_per_channel} messages\n"
              f"**Total Channels**: {len(text_channels)}",
        inline=False
    )
    
    embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
    
    try:
        await progress_msg.edit(content=None, embed=embed)
    except:
        await ctx.send(embed=embed)
    
    # Clean up confirmation message
    try:
        await confirm_msg.delete()
    except:
        pass


  @commands.command(name="purgeuser",
                    aliases=["pu", "cu", "clearuser"],
                    help="Clear recent messages of a user in channel")
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 3, commands.BucketType.user)
  @commands.has_permissions(manage_messages=True)
  @commands.bot_has_permissions(manage_messages=True)
  async def purguser(self, ctx, member: discord.Member, search=100):
      
      await ctx.message.delete()
      await do_removal(ctx, search, lambda e: e.author == member)

  @commands.group(name="purgemsg", aliases=["purgemessages"], invoke_without_command=True)
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 5, commands.BucketType.user)
  @commands.has_permissions(manage_messages=True)
  @commands.bot_has_permissions(manage_messages=True)
  async def purge_messages(self, ctx, count: int = 10):
      """Purge a number of messages from the current channel"""
      if count < 1 or count > 2000:
          return await ctx.error("Count must be between 1 and 2000.")
      
      await ctx.message.delete()
      await do_removal(ctx, count, lambda m: True)

  @purge_messages.command(name="word", aliases=["containing", "with", "content"])
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 5, commands.BucketType.user)
  @commands.has_permissions(manage_messages=True)
  @commands.bot_has_permissions(manage_messages=True)
  async def purge_word(self, ctx, word: str, count_or_all: Union[int, str] = 100):
      """Purge messages containing a specific word/phrase
      
      Usage:
      purge word <word> - Search last 100 messages for word
      purge word <word> <count> - Search last X messages for word
      purge word <word> all - Search ALL messages in channel
      """
      
      # Handle "all" parameter
      if isinstance(count_or_all, str) and count_or_all.lower() == "all":
          count = None  # None means search all messages
      else:
          try:
              count = int(count_or_all) if isinstance(count_or_all, str) else count_or_all
              if count < 1 or count > 2000:
                  return await ctx.error("Count must be between 1 and 2000, or use 'all'.")
          except ValueError:
              return await ctx.error("Count must be a number between 1-2000, or use 'all'.")
      
      # Delete the command message
      await ctx.message.delete()
      
      # Create predicate to match messages containing the word (case insensitive)
      def predicate(message):
          contains_word = word.lower() in message.content.lower()
          if contains_word:
              print(f"DEBUG: Match found - '{word}' in '{message.content[:30]}...'")
          return contains_word
      
      # If searching all messages
      if count is None:
          try:
              messages_to_delete = []
              total_checked = 0
              
              # Search through messages
              async for message in ctx.channel.history(limit=None):
                  total_checked += 1
                  if predicate(message):
                      messages_to_delete.append(message)
                      print(f"Found message to delete: {message.content[:50]}...")  # Debug
              
              print(f"Debug: Checked {total_checked} messages, found {len(messages_to_delete)} matches for '{word}'")  # Debug
              
              if messages_to_delete:
                  deleted_count = 0
                  
                  # Send progress message
                  progress_msg = await ctx.send(f"🗑️ Deleting {len(messages_to_delete)} messages containing **'{word}'**...")
                  
                  # Separate messages by age (bulk delete only works for messages < 14 days old)
                  import datetime
                  two_weeks_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=14)
                  
                  bulk_messages = [msg for msg in messages_to_delete if msg.created_at > two_weeks_ago]
                  old_messages = [msg for msg in messages_to_delete if msg.created_at <= two_weeks_ago]
                  
                  # Bulk delete newer messages (much faster)
                  if bulk_messages:
                      for i in range(0, len(bulk_messages), 100):
                          batch = bulk_messages[i:i + 100]
                          try:
                              if len(batch) == 1:
                                  await batch[0].delete()
                              else:
                                  await ctx.channel.delete_messages(batch)
                              deleted_count += len(batch)
                              
                              # Update progress
                              try:
                                  await progress_msg.edit(content=f"🗑️ Deleted {deleted_count}/{len(messages_to_delete)} messages...")
                              except:
                                  pass
                              
                              # Rate limit protection - wait between batches
                              if i + 100 < len(bulk_messages):
                                  await asyncio.sleep(1)
                                  
                          except discord.HTTPException as e:
                              print(f"Bulk delete error: {e}")
                              # If bulk delete fails, fall back to individual
                              for msg in batch:
                                  try:
                                      await msg.delete()
                                      deleted_count += 1
                                      await asyncio.sleep(0.5)  # Slower for individual deletes
                                  except:
                                      pass
                  
                  # Individual delete for old messages (slower but necessary)
                  if old_messages:
                      for msg in old_messages:
                          try:
                              await msg.delete()
                              deleted_count += 1
                              
                              # Update progress every 10 deletions
                              if deleted_count % 10 == 0:
                                  try:
                                      await progress_msg.edit(content=f"🗑️ Deleted {deleted_count}/{len(messages_to_delete)} messages...")
                                  except:
                                      pass
                              
                              # Rate limit protection for individual deletes
                              await asyncio.sleep(0.5)
                              
                          except Exception as e:
                              print(f"Individual delete error: {e}")
                              continue
                  
                  # Clean up progress message
                  try:
                      await progress_msg.delete()
                  except:
                      pass
                  
                  print(f"Debug: Successfully deleted {deleted_count} messages")  # Debug
                  
                  # React with checkmark
                  try:
                      # Find a recent message to react to (since command was deleted)
                      async for msg in ctx.channel.history(limit=1):
                          await msg.add_reaction("✅")
                          break
                  except:
                      pass
              else:
                  print(f"Debug: No messages found containing '{word}' (case insensitive)")  # Debug
                  # Send feedback that nothing was found
                  await ctx.send(f"No messages containing **'{word}'** found in this channel.", delete_after=5)
              
          except Exception as e:
              print(f"Debug: Exception occurred: {e}")  # Debug
              await ctx.send(f"Error: {e}", delete_after=5)
      else:
          # Use existing do_removal function for limited search
          await do_removal(ctx, count, predicate)
          
          # React with checkmark
          try:
              async for msg in ctx.channel.history(limit=1):
                  await msg.add_reaction("✅")
                  break
          except:
              pass

  @purge_messages.command(name="user", aliases=["member", "from"])
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 5, commands.BucketType.user)
  @commands.has_permissions(manage_messages=True)
  @commands.bot_has_permissions(manage_messages=True)
  async def purge_user_messages(self, ctx, member: discord.Member, count: int = 100, channel: Optional[discord.TextChannel] = None):
      """Purge messages from a specific user
      
      Usage:
      purge user @member - Remove last 100 messages from user
      purge user @member 50 - Remove last 50 messages from user  
      purge user @member 25 #general - Remove 25 messages from user in #general
      """
      if count < 1 or count > 2000:
          return await ctx.error("Count must be between 1 and 2000.")
      
      target_channel = channel or ctx.channel
      await ctx.message.delete()
      
      if channel and channel != ctx.channel:
          # Handle different channel
          try:
              messages_to_delete = []
              async for message in channel.history(limit=count):
                  if message.author == member:
                      messages_to_delete.append(message)
              
              if not messages_to_delete:
                  return await ctx.send(f"<:feast_cross:1400143488695144609> | No messages from {member.mention} found in {channel.mention}.", delete_after=7)
              
              deleted_count = len(messages_to_delete)
              await channel.delete_messages(messages_to_delete)
              
              await ctx.send(f"<:feast_tick:1400143469892210753> | Successfully removed {deleted_count} message{'s' if deleted_count != 1 else ''} from {member.mention} in {channel.mention}.", delete_after=7)
              
          except discord.Forbidden:
              return await ctx.error("I do not have permissions to delete messages in that channel.")
          except discord.HTTPException as e:
              return await ctx.error(f"Error: {e}")
      else:
          # Use existing function for current channel
          await do_removal(ctx, count, lambda m: m.author == member)

  @purge_messages.command(name="bots", aliases=["bot"])
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 5, commands.BucketType.user)
  @commands.has_permissions(manage_messages=True)
  @commands.bot_has_permissions(manage_messages=True)
  async def purge_bot_messages(self, ctx, count: int = 100):
      """Purge bot messages from the current channel"""
      if count < 1 or count > 2000:
          return await ctx.error("Count must be between 1 and 2000.")
      
      await ctx.message.delete()
      await do_removal(ctx, count, lambda m: m.author.bot)

"""
@Author: Frosty
    + Discord: frosty.pyro
    + Community: https://discord.gg/5wtjDkYbVh (Sleepless Development)
    + for any queries reach out in the server; or send a dm.
"""