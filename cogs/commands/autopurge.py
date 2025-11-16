import discord
from discord.ext import commands, tasks
from datetime import datetime, timezone
import asyncio
import json
import os

from utils.error_helpers import StandardErrorHandler
DB_PATH = "db/autopurge.db"  # Changed file extension as requested

def load_data():
    if not os.path.exists(DB_PATH):
        return {}
    with open(DB_PATH, "r") as f:
        return json.load(f)

def save_data(data):
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with open(DB_PATH, "w") as f:
        json.dump(data, f, indent=4)

class AutoPurge(commands.Cog):
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot
        self.purging_channels = {int(k): v for k, v in load_data().items()}
        self.auto_purge_loop.start()

    def cog_unload(self):
        self.auto_purge_loop.cancel()

    async def update_data_file(self):
        save_data({str(k): v for k, v in self.purging_channels.items()})

    @commands.group(name="autopurge", invoke_without_command=True)
    async def autopurge(self, ctx):
        prefix = (await self.bot.get_prefix(ctx.message))[0]
        await ctx.send(f"Use `{prefix}autopurge start <seconds>`, `{prefix}autopurge stop`, or `{prefix}autopurge list`.")

    @autopurge.command(name="start")
    async def autopurge_start(self, ctx, seconds: int):
        if seconds < 5:
            await ctx.send("❌ Time must be at least 5 seconds.")
            return

        old_channel = ctx.channel
        try:
            new_channel = await old_channel.clone(reason=f"Autopurge start by {ctx.author}")
        except discord.Forbidden:
            return await ctx.send("❌ I don't have permission to clone this channel.")
        except Exception as e:
            return await ctx.send(f"❌ Error cloning channel: {e}")

        try:
            if old_channel.category:
                await new_channel.edit(category=old_channel.category, position=old_channel.position)
            else:
                await new_channel.edit(position=old_channel.position)
        except:
            pass

        try:
            await old_channel.delete(reason=f"Autopurge start - channel replaced by bot")
        except discord.Forbidden:
            return await ctx.send("❌ I don't have permission to delete the old channel.")
        except Exception as e:
            return await ctx.send(f"❌ Error deleting old channel: {e}")

        self.purging_channels[new_channel.id] = seconds
        await self.update_data_file()

        embed = discord.Embed(
            title="Autopurge started",
            description=f"The channel will autopurge messages older than **{seconds} seconds**.",
            color=discord.Color.green()
        )
        await new_channel.send(embed=embed)

    @autopurge.command(name="stop")
    async def autopurge_stop(self, ctx):
        channel_id = ctx.channel.id
        if channel_id in self.purging_channels:
            del self.purging_channels[channel_id]
            await self.update_data_file()
            await ctx.send("🛑 Autopurge stopped in this channel.")
        else:
            await ctx.send("⚠️ Autopurge is not active in this channel.")

    @autopurge.command(name="list")
    async def autopurge_list(self, ctx):
        if not self.purging_channels:
            await ctx.send("📭 No channels currently have autopurge enabled.")
            return

        lines = []
        for channel_id, seconds in self.purging_channels.items():
            channel = self.bot.get_channel(channel_id)
            if channel:
                lines.append(f"🔹 {channel.mention}: messages older than {seconds} seconds")
            else:
                lines.append(f"🔸 Unknown Channel ID {channel_id}: {seconds} seconds")

        await ctx.send("\n".join(lines))

    @tasks.loop(seconds=10)
    async def auto_purge_loop(self):
        for channel_id, seconds in list(self.purging_channels.items()):
            channel = self.bot.get_channel(channel_id)
            if not channel:
                del self.purging_channels[channel_id]
                await self.update_data_file()
                continue

            try:
                async for message in channel.history(limit=100):
                    if message.pinned:
                        continue
                    if (datetime.now(timezone.utc) - message.created_at).total_seconds() > seconds:
                        await message.delete()
                        await asyncio.sleep(1)
            except discord.Forbidden:
                print(f"❌ Missing permissions to delete messages in channel {channel_id}")
            except Exception as e:
                print(f"⚠️ Error autopurging in {channel_id}: {e}")

async def setup(bot):
    await bot.add_cog(AutoPurge(bot))
