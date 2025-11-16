import discord
from discord.ext import commands
import aiosqlite

from utils.error_helpers import StandardErrorHandler
VOICEMASTER_DB_PATH = 'db/voicemaster.db'

class VoiceMasterConfig(commands.Cog):
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="vmconfig", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def vmconfig(self, ctx):
        """VoiceMaster configuration commands."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @vmconfig.command(name="panel")
    @commands.has_permissions(administrator=True)
    async def set_panel_channel(self, ctx, channel: discord.TextChannel):
        await self.set_config(ctx.guild.id, panel_channel=channel.id)
        await ctx.send(f"VoiceMaster panel channel set to {channel.mention}.")

    @vmconfig.command(name="voicecat")
    @commands.has_permissions(administrator=True)
    async def set_voice_category(self, ctx, category: discord.CategoryChannel):
        await self.set_config(ctx.guild.id, default_voice_category=category.id)
        await ctx.send(f"Default voice channel category set to {category.name}.")

    @vmconfig.command(name="textcat")
    @commands.has_permissions(administrator=True)
    async def set_text_category(self, ctx, category: discord.CategoryChannel):
        await self.set_config(ctx.guild.id, default_text_category=category.id)
        await ctx.send(f"Default text channel category set to {category.name}.")

    @vmconfig.command(name="features")
    @commands.has_permissions(administrator=True)
    async def set_features(self, ctx, *, features: str):
        await self.set_config(ctx.guild.id, features=features)
        await ctx.send(f"VoiceMaster features set: `{features}`.")

    async def set_config(self, guild_id, **kwargs):
        async with aiosqlite.connect(VOICEMASTER_DB_PATH) as db:
            # Get current config
            async with db.execute("SELECT * FROM vm_config WHERE guild_id = ?", (guild_id,)) as cursor:
                row = await cursor.fetchone()
            columns = []
            values = []
            for k, v in kwargs.items():
                columns.append(f"{k} = ?")
                values.append(v)
            if row:
                await db.execute(f"UPDATE vm_config SET {', '.join(columns)} WHERE guild_id = ?", (*values, guild_id))
            else:
                await db.execute("INSERT INTO vm_config (guild_id) VALUES (?)", (guild_id,))
                await db.execute(f"UPDATE vm_config SET {', '.join(columns)} WHERE guild_id = ?", (*values, guild_id))
            await db.commit()

    async def get_config(self, guild_id):
        async with aiosqlite.connect(VOICEMASTER_DB_PATH) as db:
            async with db.execute("SELECT * FROM vm_config WHERE guild_id = ?", (guild_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        "guild_id": row[0],
                        "panel_channel": row[1],
                        "default_voice_category": row[2],
                        "default_text_category": row[3],
                        "default_voice_perms": row[4],
                        "default_text_perms": row[5],
                        "features": row[6],
                    }
                return None

async def setup(bot):
    await bot.add_cog(VoiceMasterConfig(bot))
