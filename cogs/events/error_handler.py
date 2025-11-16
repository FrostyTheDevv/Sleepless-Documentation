import discord
from discord.ext import commands
import traceback
import datetime
import sys
import sqlite3
from typing import Optional
from utils.dynamic_dropdowns import PaginatedChannelView

class ErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "logging.db"
        self.error_channel_id = 1416105067714449549  # Your error channel ID
        self.owner_id = 774922425548013609  # Your user ID
        self.setup_database()

    def setup_database(self):
        """Create errors table if it doesn't exist"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS error_channels (
                    guild_id INTEGER PRIMARY KEY,
                    channel_id INTEGER
                )
            """)

    def set_error_channel(self, guild_id: int, channel_id: int):
        """Set the error logging channel for a guild"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO error_channels (guild_id, channel_id)
                VALUES (?, ?)
            """, (guild_id, channel_id))

    def get_error_channel(self, guild_id: int) -> Optional[int]:
        """Get the error logging channel for a guild"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT channel_id FROM error_channels WHERE guild_id = ?
            """, (guild_id,))
            result = cursor.fetchone()
            return result[0] if result else None

    @commands.command(name="seterrors")
    @commands.has_permissions(administrator=True)
    async def set_error_channel_cmd(self, ctx):
        """Set the channel where bot errors will be logged"""
        # Get current error channel
        current_error_channel_id = self.get_error_channel(ctx.guild.id)
        current_error_channel = ctx.guild.get_channel(current_error_channel_id) if current_error_channel_id else None
            
        # Create paginated channel selector for error logging channel
        async def error_logging_callback(interaction, select):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You are not authorized to set the error logging channel.", ephemeral=True)
                return

            selected_channel_id = int(select.values[0])
            selected_channel = ctx.guild.get_channel(selected_channel_id)

            self.set_error_channel(ctx.guild.id, selected_channel_id)

            embed = discord.Embed(
                title="✅ Error Channel Set",
                description=f"Bot errors will now be logged to {selected_channel.mention}",
                color=0x00FF00
            )
            
            await interaction.response.edit_message(embed=embed, view=None)

        view = PaginatedChannelView(
            ctx.guild,
            channel_types=[discord.ChannelType.text],
            exclude_channels=[],
            custom_callback=error_logging_callback,
            timeout=300
        )

        total_channels = len(view.all_channels)
        
        embed = discord.Embed(
            title=f"Error Logging Channel for {ctx.guild.name}",
            description=f"Current Error Channel: {current_error_channel.mention if current_error_channel else 'None'}",
            color=0x5865F2
        )
        
        footer_text = "Use the dropdown menu to select an error logging channel."
        if total_channels > 25:
            footer_text += f" ({total_channels} channels - use ◀️ ▶️ buttons to navigate)"
        embed.set_footer(text=footer_text)

        await ctx.send(embed=embed, view=view)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Handle all command errors"""
        # Ignore these common errors
        if isinstance(error, (commands.CommandNotFound, commands.NotOwner)):
            return

        # Get the original error if it's wrapped
        original_error = getattr(error, 'original', error)
        
        # Handle user-facing errors with auto-deletion
        user_embed = None
        
        if isinstance(error, commands.MissingPermissions):
            user_embed = discord.Embed(
                title="❌ Missing Permissions",
                description=f"You don't have the required permissions: `{', '.join(error.missing_permissions)}`",
                color=0xFF6B6B
            )
        elif isinstance(error, commands.BotMissingPermissions):
            user_embed = discord.Embed(
                title="❌ Bot Missing Permissions",
                description=f"I don't have the required permissions: `{', '.join(error.missing_permissions)}`",
                color=0xFF6B6B
            )
        elif isinstance(original_error, discord.Forbidden):
            # Handle Discord API 403 Forbidden errors (Missing Permissions)
            user_embed = discord.Embed(
                title="❌ Missing Permissions",
                description="I don't have the necessary permissions to perform this action.\n\n"
                           "Please ensure I have the following permissions:\n"
                           "• Send Messages\n"
                           "• Embed Links\n"
                           "• Add Reactions\n"
                           "• Read Message History",
                color=0xFF6B6B
            )
            # Don't log to error channel - this is a common configuration issue
            try:
                error_msg = await ctx.send(embed=user_embed)
                await error_msg.delete(delay=5)
            except:
                pass
            return  # Exit early to avoid logging this as a bot error
        elif isinstance(error, commands.MissingRequiredArgument):
            user_embed = discord.Embed(
                title="❌ Missing Required Argument",
                description=f"Missing required argument: `{error.param.name}`\n\nUse `{ctx.prefix}help {ctx.command}` for usage information.",
                color=0xFF6B6B
            )
        elif isinstance(error, commands.BadArgument):
            user_embed = discord.Embed(
                title="❌ Invalid Argument",
                description=f"Invalid argument provided: {str(error)}",
                color=0xFF6B6B
            )
        elif isinstance(error, commands.CommandOnCooldown):
            user_embed = discord.Embed(
                title="⏰ Command On Cooldown",
                description=f"Command is on cooldown. Try again in **{error.retry_after:.1f}** seconds.",
                color=0xFF6B6B
            )
        elif isinstance(error, commands.MaxConcurrencyReached):
            user_embed = discord.Embed(
                title="⏳ Command Busy",
                description="This command is already being used. Please wait for it to finish.",
                color=0xFF6B6B
            )
        
        # Send user-facing error and auto-delete after 3 seconds
        if user_embed:
            try:
                error_msg = await ctx.send(embed=user_embed)
                await error_msg.delete(delay=3)
                return  # Don't log common user errors to error channel
            except:
                pass
        
        # For actual bot errors, send to error channel with ping
        error_channel = self.bot.get_channel(self.error_channel_id)
        if error_channel:
            # Create detailed error embed for bot errors
            embed = discord.Embed(
                title="🚨 Bot Error Detected",
                color=0xFF0000,
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )

            # Add command info
            embed.add_field(
                name="📍 Location",
                value=f"**Guild:** {ctx.guild.name if ctx.guild else 'DM'} (`{ctx.guild.id if ctx.guild else 'N/A'}`)\n"
                      f"**Channel:** {ctx.channel.mention if hasattr(ctx.channel, 'mention') else 'DM'}\n"
                      f"**User:** {ctx.author} (`{ctx.author.id}`)",
                inline=False
            )

            embed.add_field(
                name="⚙️ Command",
                value=f"**Command:** `{ctx.command}`\n**Message:** `{ctx.message.content[:100]}{'...' if len(ctx.message.content) > 100 else ''}`",
                inline=False
            )

            # Add error details
            error_type = type(original_error).__name__
            error_message = str(original_error)
            
            embed.add_field(
                name="❌ Error Details",
                value=f"**Type:** `{error_type}`\n**Message:** ```{error_message[:500]}{'...' if len(error_message) > 500 else ''}```",
                inline=False
            )

            # Add traceback if available
            if hasattr(error, '__traceback__'):
                tb = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
                if len(tb) > 1000:
                    tb = tb[:1000] + "..."
                embed.add_field(
                    name="📋 Traceback",
                    value=f"```python\n{tb}```",
                    inline=False
                )

            try:
                # Send error with ping
                await error_channel.send(f"<@{self.owner_id}>", embed=embed)
            except Exception as e:
                print(f"Failed to send error to channel: {e}")

        # Send generic error to user and auto-delete
        try:
            generic_embed = discord.Embed(
                title="❌ An Error Occurred",
                description="An unexpected error occurred while executing this command. The error has been logged for review.",
                color=0xFF6B6B
            )
            error_msg = await ctx.send(embed=generic_embed)
            await error_msg.delete(delay=3)
        except:
            pass

        # Print to console as well
        print(f"Error in {ctx.command}: {error}")
        traceback.print_exception(type(error), error, error.__traceback__)

    @commands.Cog.listener()
    async def on_error(self, event, *args, **kwargs):
        """Handle all other errors"""
        error_type, error_value, error_traceback = sys.exc_info()
        
        # Send to error channel with ping
        error_channel = self.bot.get_channel(self.error_channel_id)
        if error_channel:
            embed = discord.Embed(
                title="🚨 Bot Event Error Detected",
                color=0xFF0000,
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )

            embed.add_field(
                name="📍 Event",
                value=f"**Event:** `{event}`",
                inline=False
            )

            embed.add_field(
                name="❌ Error Details",
                value=f"**Type:** `{error_type.__name__ if error_type else 'Unknown'}`\n**Message:** ```{str(error_value)[:500]}{'...' if len(str(error_value)) > 500 else ''}```",
                inline=False
            )

            # Add traceback
            if error_traceback:
                tb = ''.join(traceback.format_exception(error_type, error_value, error_traceback))
                if len(tb) > 1000:
                    tb = tb[:1000] + "..."
                embed.add_field(
                    name="📋 Traceback",
                    value=f"```python\n{tb}```",
                    inline=False
                )

            try:
                # Send error with ping
                await error_channel.send(f"<@{self.owner_id}>", embed=embed)
            except Exception as e:
                print(f"Failed to send error to channel: {e}")

        # Print to console
        print(f"Error in event {event}: {error_value}")
        traceback.print_exception(error_type, error_value, error_traceback)

async def setup(bot):
    await bot.add_cog(ErrorHandler(bot))