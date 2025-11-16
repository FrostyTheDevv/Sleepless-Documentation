import discord
import traceback
import sys
from datetime import datetime, timezone
from discord.ext import commands
from utils.config import ERROR_LOG_CHANNEL_ID
from core import sleepless, Cog

class Errors(Cog):
    def __init__(self, client: sleepless):
        self.client = client

    async def send_error_to_channel(self, error_type: str, error_message: str, context_info: str = ""):
        try:
            if not hasattr(self.client, 'get_channel') or not ERROR_LOG_CHANNEL_ID:
                return
            channel = self.client.get_channel(ERROR_LOG_CHANNEL_ID)
            from discord.abc import Messageable
            if not channel or not isinstance(channel, Messageable):
                print(f"Error log channel {ERROR_LOG_CHANNEL_ID} not found or can't send!")
                return
            embed = discord.Embed(
                title=f"🚨 {error_type}"[:256],
                color=0xff0000,
                timestamp=datetime.now(timezone.utc)
            )
            if error_message:
                embed.add_field(name="Error Details", value=f"```{error_message[:1000]}```", inline=False)
            if context_info:
                embed.add_field(name="Context", value=f"```{context_info[:1000]}```", inline=False)
            embed.set_footer(text="Sleepless Error Logger")
            await channel.send(embed=embed)
        except Exception as e:
            print(f"Failed to send error to channel: {e}")
            traceback.print_exc()

    @commands.Cog.listener()
    async def on_error(self, event, *args, **kwargs):
        try:
            error_msg = ''.join(traceback.format_exception(*sys.exc_info()))
            context_info = f"Event: {event}\n"
            if args:
                context_info += f"Args: {str(args)[:500]}{'...' if len(str(args)) > 500 else ''}\n"
            if kwargs:
                context_info += f"Kwargs: {str(kwargs)[:500]}{'...' if len(str(kwargs)) > 500 else ''}"
            await self.send_error_to_channel("Event Error", error_msg, context_info)
        except Exception as e:
            print(f"Failed to handle on_error: {e}")
            traceback.print_exc()

