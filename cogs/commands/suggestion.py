import discord
from discord.ext import commands
import datetime
from utils.timezone_helpers import get_timezone_helpers

from utils.error_helpers import StandardErrorHandler
class Suggestion(commands.Cog):
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot
        self.tz_helpers = get_timezone_helpers(bot)
        # This is the channel where suggestions will be sent
        self.suggestion_channel_id = 1396762457342738467

    async def send_suggestion_embed(self, ctx, suggestion_content):
        """
        Helper function to send a suggestion embed to the designated channel.
        """
        channel = self.bot.get_channel(self.suggestion_channel_id)
        if channel:
            embed = discord.Embed(
                title="New Suggestion!",
                description=suggestion_content,
                color=discord.Color.blue()
            )
            embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
            
            # Format time in user's timezone
            time_formatted = await self.tz_helpers.format_datetime_for_user_custom(
                datetime.datetime.now(datetime.timezone.utc), ctx.author, '%Y-%m-%d %H:%M:%S %Z'
            )
            embed.set_footer(text=f"Time: {time_formatted}")

            message = await channel.send(embed=embed)
            # Add reactions for voting
            await message.add_reaction('⬆️')  # Up arrow
            await message.add_reaction('⬇️')  # Green checkmark (for approval/implementation)
        else:
            print(f"Error: Could not find the suggestion channel with ID {self.suggestion_channel_id}.")
            await ctx.send(f"I couldn't find the designated suggestion channel. Please contact an admin.")

    @commands.hybrid_command(
        name="suggest",
        aliases=["suggestion"], # Allows both $suggest and $suggestion
        usage='suggest <your suggestion>',
        description='Submit a suggestion for the bot or server.',
        help='Submit a suggestion to the development team or server staff.',
        with_app_command=True # Enables it as a slash command too
    )
    @commands.cooldown(1, 60, commands.BucketType.user) # Cooldown: 1 use per user per 60 seconds
    async def suggest(self, ctx, *, suggestion_content: str):
        """
        Sends a suggestion to the designated suggestion channel.
        """
        await self.send_suggestion_embed(ctx, suggestion_content)
        await ctx.send("<:feast_dot:1400140945617588264>Thanks for your suggestion! We will review it soon.")

async def setup(bot):
    await bot.add_cog(Suggestion(bot))