from utils.error_helpers import StandardErrorHandler
# cogs/commands/say.py
import discord
from discord.ext import commands
from utils.Tools import *
import re
import asyncio
from typing import Optional, Union
import aiosqlite

class Say(commands.Cog):
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot
        self.color = 0x006fb9
        asyncio.create_task(self.setup_database())

    async def setup_database(self):
        """Set up the database for say command logging"""
        async with aiosqlite.connect('db/say.db') as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS say_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    message_content TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            await db.commit()

    async def log_say_command(self, ctx, channel, message_content):
        """Log the say command usage for moderation purposes"""
        async with aiosqlite.connect('db/say.db') as db:
            await db.execute('''
                INSERT INTO say_logs (guild_id, user_id, channel_id, message_content)
                VALUES (?, ?, ?, ?)
            ''', (ctx.guild.id, ctx.author.id, channel.id, message_content))
            await db.commit()

    def clean_content(self, content: str) -> str:
        """Clean the content to prevent abuse"""
        # Remove @everyone and @here mentions for non-administrators
        content = re.sub(r'@(everyone|here)', '@\u200b\\1', content)
        
        # Limit message length
        if len(content) > 2000:
            content = content[:1997] + "..."
        
        return content

    @commands.group(invoke_without_command=True, 
                   aliases=["echo", "speak"], 
                   help="Make the bot say a message in the current or specified channel")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(send_messages=True)
    async def say(self, ctx, *, message: str):
        """Basic say command - sends message in current channel"""
        if not message.strip():
            return await ctx.send("❌ Please provide a message to send.")

        # Clean the content
        cleaned_message = self.clean_content(message)
        
        # Delete the command message
        try:
            await ctx.message.delete()
        except discord.NotFound:
            pass

        # Send the message
        try:
            await ctx.send(cleaned_message)
            
            # Log the command usage
            await self.log_say_command(ctx, ctx.channel, cleaned_message)
            
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to send messages in this channel.")
        except discord.HTTPException as e:
            await ctx.send(f"❌ Failed to send message: {e}")

    @say.command(name="channel", aliases=["ch"], help="Make the bot say a message in a specific channel")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(send_messages=True)
    async def say_channel(self, ctx, channel: discord.TextChannel, *, message: str):
        """Say command with specific channel target"""
        if not message.strip():
            return await ctx.send("❌ Please provide a message to send.")

        # Check if bot has permissions in target channel
        if not channel.permissions_for(ctx.guild.me).send_messages:
            return await ctx.send(f"❌ I don't have permission to send messages in {channel.mention}.")

        # Clean the content
        cleaned_message = self.clean_content(message)
        
        # Delete the command message
        try:
            await ctx.message.delete()
        except discord.NotFound:
            pass

        # Send the message
        try:
            await channel.send(cleaned_message)
            
            # Log the command usage
            await self.log_say_command(ctx, channel, cleaned_message)
            
            # Send confirmation to command author
            confirm_embed = discord.Embed(
                description=f"✅ Message sent to {channel.mention}",
                color=0x00ff00
            )
            try:
                await ctx.author.send(embed=confirm_embed)
            except discord.Forbidden:
                pass  # User has DMs disabled
                
        except discord.Forbidden:
            await ctx.send(f"❌ I don't have permission to send messages in {channel.mention}.")
        except discord.HTTPException as e:
            await ctx.send(f"❌ Failed to send message: {e}")

    @say.command(name="embed", aliases=["emb"], help="Make the bot say a message in an embed")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 8, commands.BucketType.user)
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    async def say_embed(self, ctx, channel: Optional[discord.TextChannel] = None, *, message: str):
        """Say command that sends message in an embed"""
        if not message.strip():
            return await ctx.send("❌ Please provide a message to send.")

        target_channel = channel or ctx.channel

        # Check permissions
        if not target_channel.permissions_for(ctx.guild.me).send_messages:
            return await ctx.send(f"❌ I don't have permission to send messages in {target_channel.mention}.")
        
        if not target_channel.permissions_for(ctx.guild.me).embed_links:
            return await ctx.send(f"❌ I don't have permission to send embeds in {target_channel.mention}.")

        # Clean the content
        cleaned_message = self.clean_content(message)
        
        # Create embed
        embed = discord.Embed(
            description=cleaned_message,
            color=self.color
        )
        embed.set_footer(
            text=f"Requested by {ctx.author}",
            icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
        )
        
        # Delete the command message
        try:
            await ctx.message.delete()
        except discord.NotFound:
            pass

        # Send the embed
        try:
            await target_channel.send(embed=embed)
            
            # Log the command usage
            await self.log_say_command(ctx, target_channel, f"[EMBED] {cleaned_message}")
            
            # Send confirmation if different channel
            if target_channel != ctx.channel:
                confirm_embed = discord.Embed(
                    description=f"✅ Embed sent to {target_channel.mention}",
                    color=0x00ff00
                )
                try:
                    await ctx.author.send(embed=confirm_embed)
                except discord.Forbidden:
                    pass
                    
        except discord.Forbidden:
            await ctx.send(f"❌ I don't have permission to send embeds in {target_channel.mention}.")
        except discord.HTTPException as e:
            await ctx.send(f"❌ Failed to send embed: {e}")

    @say.command(name="reply", aliases=["rep"], help="Make the bot reply to a specific message")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(send_messages=True)
    async def say_reply(self, ctx, message_id: int, *, message: str):
        """Reply to a specific message with the bot"""
        if not message.strip():
            return await ctx.send("❌ Please provide a message to send.")

        # Clean the content
        cleaned_message = self.clean_content(message)
        
        # Try to find the message
        try:
            target_message = await ctx.channel.fetch_message(message_id)
        except discord.NotFound:
            return await ctx.send("❌ Message not found in this channel.")
        except discord.Forbidden:
            return await ctx.send("❌ I don't have permission to read message history.")
        except discord.HTTPException:
            return await ctx.send("❌ Failed to fetch the message.")

        # Delete the command message
        try:
            await ctx.message.delete()
        except discord.NotFound:
            pass

        # Send the reply
        try:
            await target_message.reply(cleaned_message)
            
            # Log the command usage
            await self.log_say_command(ctx, ctx.channel, f"[REPLY to {message_id}] {cleaned_message}")
            
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to send messages in this channel.")
        except discord.HTTPException as e:
            await ctx.send(f"❌ Failed to send reply: {e}")

    @say.command(name="edit", aliases=["modify"], help="Edit a message sent by the bot")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(send_messages=True)
    async def say_edit(self, ctx, message_id: int, *, new_message: str):
        """Edit a message previously sent by the bot"""
        if not new_message.strip():
            return await ctx.send("❌ Please provide the new message content.")

        # Clean the content
        cleaned_message = self.clean_content(new_message)
        
        # Try to find the message
        try:
            target_message = await ctx.channel.fetch_message(message_id)
        except discord.NotFound:
            return await ctx.send("❌ Message not found in this channel.")
        except discord.Forbidden:
            return await ctx.send("❌ I don't have permission to read message history.")
        except discord.HTTPException:
            return await ctx.send("❌ Failed to fetch the message.")

        # Check if the message was sent by the bot
        if target_message.author != self.bot.user:
            return await ctx.send("❌ I can only edit messages that I sent.")

        # Delete the command message
        try:
            await ctx.message.delete()
        except discord.NotFound:
            pass

        # Edit the message
        try:
            await target_message.edit(content=cleaned_message)
            
            # Log the command usage
            await self.log_say_command(ctx, ctx.channel, f"[EDIT {message_id}] {cleaned_message}")
            
            # Send confirmation
            confirm_embed = discord.Embed(
                description="✅ Message edited successfully",
                color=0x00ff00
            )
            try:
                await ctx.author.send(embed=confirm_embed)
            except discord.Forbidden:
                pass
                
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to edit that message.")
        except discord.HTTPException as e:
            await ctx.send(f"❌ Failed to edit message: {e}")

    @say.command(name="logs", help="View recent say command usage (Administrator only)")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def say_logs(self, ctx, limit: int = 10):
        """View recent say command logs"""
        if limit > 50:
            limit = 50
        elif limit < 1:
            limit = 10

        async with aiosqlite.connect('db/say.db') as db:
            async with db.execute('''
                SELECT user_id, channel_id, message_content, timestamp 
                FROM say_logs 
                WHERE guild_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (ctx.guild.id, limit)) as cursor:
                logs = await cursor.fetchall()
                logs = list(logs)

        if not logs:
            return await ctx.send("❌ No say command logs found for this server.")

        embed = discord.Embed(
            title="📝 Say Command Logs",
            description=f"Showing last {len(logs)} entries",
            color=self.color
        )

        for log in logs[:10]:  # Limit to 10 for embed field limits
            user = self.bot.get_user(log[0])
            channel = self.bot.get_channel(log[1])
            user_name = user.mention if user else f"Unknown User ({log[0]})"
            channel_name = channel.mention if channel else f"Unknown Channel ({log[1]})"
            
            content = log[2]
            if len(content) > 100:
                content = content[:97] + "..."
            
            embed.add_field(
                name=f"{user_name} in {channel_name}",
                value=f"```{content}```\n*{log[3]}*",
                inline=False
            )

        embed.set_footer(
            text=f"Requested by {ctx.author}",
            icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
        )

        await ctx.send(embed=embed)

    @say.command(name="help", help="Show detailed help for say commands")
    @blacklist_check()
    @ignore_check()
    async def say_help(self, ctx):
        """Show help for say commands"""
        embed = discord.Embed(
            title="💬 Say Command Help",
            description="Make the bot send messages on your behalf",
            color=self.color
        )

        embed.add_field(
            name="📝 Basic Commands",
            value=(
                "`$say <message>` - Send message in current channel\n"
                "`$say channel <#channel> <message>` - Send message in specific channel\n"
                "`$say embed [#channel] <message>` - Send message in an embed\n"
                "`$say reply <message_id> <message>` - Reply to a specific message"
            ),
            inline=False
        )

        embed.add_field(
            name="🔧 Management Commands",
            value=(
                "`$say edit <message_id> <new_message>` - Edit bot's message\n"
                "`$say logs [limit]` - View command usage logs (Admin only)\n"
                "`$say help` - Show this help message"
            ),
            inline=False
        )

        embed.add_field(
            name="⚠️ Requirements",
            value=(
                "• `Manage Messages` permission required\n"
                "• Bot needs `Send Messages` permission in target channel\n"
                "• Some commands require `Administrator` permission\n"
                "• Messages are automatically logged for moderation"
            ),
            inline=False
        )

        embed.add_field(
            name="🛡️ Safety Features",
            value=(
                "• Automatic @everyone/@here prevention\n"
                "• Message length limits (2000 characters)\n"
                "• Comprehensive logging system\n"
                "• Permission checks for all actions"
            ),
            inline=False
        )

        embed.set_footer(
            text=f"Requested by {ctx.author}",
            icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
        )

        await ctx.send(embed=embed)

    # Error handlers
    @say.error
    async def say_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You need `Manage Messages` permission to use this command.")
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send("❌ I need `Send Messages` permission to use this command.")
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"❌ Command is on cooldown. Try again in {error.retry_after:.1f} seconds.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Missing required argument. Use `$say help` for usage information.")
        else:
            print(f"Say command error: {error}")

def setup(bot):
    bot.add_cog(Say(bot))

"""
@Author: Frosty
    + Discord: frosty.pyro
    + Community: https://discord.gg/5wtjDkYbVh (Sleepless Development)
    + for any queries reach out in the server; or send a dm.
"""