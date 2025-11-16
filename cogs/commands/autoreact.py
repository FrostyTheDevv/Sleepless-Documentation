import discord
from discord.ext import commands
import aiosqlite
import re
from utils.Tools import *

from utils.error_helpers import StandardErrorHandler
class AutoReaction(commands.Cog):
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot
        self.db_path = 'db/autoreact.db'
        # Removed loop access from __init__

    async def setup_hook(self):
        """Called when the cog is loaded"""
        await self.setup_database()

    async def setup_database(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS autoreact (
                    guild_id INTEGER,
                    trigger TEXT,
                    emojis TEXT
                )
            """)
            await db.commit()

    async def get_triggers(self, guild_id):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT trigger, emojis FROM autoreact WHERE guild_id = ?", (guild_id,))
            return await cursor.fetchall()

    async def trigger_exists(self, guild_id, trigger):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT 1 FROM autoreact WHERE guild_id = ? AND trigger = ?", (guild_id, trigger))
            return await cursor.fetchone()

    @commands.group(name="react", aliases=["autoreact"], help="Lists all subcommands of autoreact group.", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 4, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def react(self, ctx):
        if ctx.subcommand_passed is None:
            await ctx.send_help(ctx.command)
            ctx.command.reset_cooldown(ctx)

    @react.command(name="add", aliases=["set", "create"], help="Adds a trigger and its emojis to the autoreact.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 4, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def add(self, ctx, trigger: str, *, emojis: str):
        # DEBUG: Print what we received
        print(f"[DEBUG] react add called with trigger='{trigger}', emojis='{emojis}'")
        print(f"[DEBUG] emojis length: {len(emojis)}")
        print(f"[DEBUG] emojis bytes: {emojis.encode('utf-8')}")
        
        if len(trigger.split()) > 1:
            embed = discord.Embed(
                title="<:feast_cross:1400143488695144609> Invalid Trigger",
                description="Triggers can only be one word.",
                color=0x006fb9
            )
            embed.set_footer(text=f"Requested By {ctx.author}",
                   icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            return await ctx.reply(embed=embed)

        # Extract emojis using a more comprehensive approach
        emoji_list = []
        
        # First, find all custom Discord emojis
        discord_emojis = re.findall(r"<a?:\w+:\d+>", emojis)
        emoji_list.extend(discord_emojis)
        
        # Remove Discord emojis from the string to process Unicode emojis
        temp_text = emojis
        for discord_emoji in discord_emojis:
            temp_text = temp_text.replace(discord_emoji, "")
        
        # Extract Unicode emojis by checking each character
        for char in temp_text:
            # Check if character is in emoji ranges (more comprehensive)
            code_point = ord(char)
            if (0x1F600 <= code_point <= 0x1F64F or    # Emoticons
                0x1F300 <= code_point <= 0x1F5FF or    # Misc Symbols and Pictographs
                0x1F680 <= code_point <= 0x1F6FF or    # Transport and Map
                0x1F1E0 <= code_point <= 0x1F1FF or    # Regional indicators
                0x2600 <= code_point <= 0x27BF or      # Misc symbols
                0x1F900 <= code_point <= 0x1F9FF or    # Supplemental Symbols
                0x1F018 <= code_point <= 0x1F270 or    # Various symbols
                0x1FA00 <= code_point <= 0x1FAFF or    # Extended-A (includes 🪻)
                0x1FAB0 <= code_point <= 0x1FABF or    # Extended-A subset
                0x1FAC0 <= code_point <= 0x1FAFF or    # Extended-A subset
                0x1F000 <= code_point <= 0x1F02F or    # Mahjong Tiles
                0x1F0A0 <= code_point <= 0x1F0FF or    # Playing Cards
                char in "❤️💕💖💗💘💝💞💟💌💍💎💐🌹🪻"):  # Common emojis + your specific one
                if char not in emoji_list and char.strip():  # Avoid duplicates and whitespace
                    emoji_list.append(char)
        
        print(f"[DEBUG] Final emoji list: {emoji_list}")
        print(f"[DEBUG] Emoji list length: {len(emoji_list)}")
        
        if len(emoji_list) == 0:
            embed = discord.Embed(
                title="<:feast_cross:1400143488695144609> No Emojis Found",
                description="No valid emojis were detected in your input. Please make sure you're using actual emojis.",
                color=0x006fb9
            )
            embed.set_footer(text=f"Requested By {ctx.author}",
                   icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            return await ctx.reply(embed=embed)
        
        if len(emoji_list) > 10:
            embed = discord.Embed(
                title="<:feast_cross:1400143488695144609> Too Many Emojis",
                description="You can only set up to **10** emojis per trigger.",
                color=0x006fb9
            )
            embed.set_footer(text=f"Requested By {ctx.author}",
                   icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            return await ctx.reply(embed=embed)

        triggers = list(await self.get_triggers(ctx.guild.id))
        if len(triggers) >= 10:
            embed = discord.Embed(
                title="<:feast_warning:1400143131990560830> Trigger Limit Reached",
                description="You can only set up to 10 triggers for auto-reactions in this guild.",
                color=0x006fb9
            )
            embed.set_footer(text=f"Requested By {ctx.author}",
                   icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            return await ctx.reply(embed=embed)

        if await self.trigger_exists(ctx.guild.id, trigger):
            embed = discord.Embed(
                title="<:feast_warning:1400143131990560830> Trigger Exists",
                description=f"The trigger '{trigger}' already exists. Remove it before adding it again.",
                color=0x006fb9
            )
            embed.set_footer(text=f"Requested By {ctx.author}",
                   icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            return await ctx.reply(embed=embed)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT INTO autoreact (guild_id, trigger, emojis) VALUES (?, ?, ?)", 
                             (ctx.guild.id, trigger, " ".join(emoji_list)))
            await db.commit()

        embed = discord.Embed(
            title="<:feast_tick:1400143469892210753> Trigger Added",
            description=f"Successfully added trigger `{trigger}` with emojis: {', '.join(emoji_list)}",
            color=0x006fb9
        )
        embed.set_footer(text=f"Requested By {ctx.author}",
               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        await ctx.reply(embed=embed)

    @react.command(name="remove", aliases=["clear", "delete"], help="Removes a trigger and its emojis from the autoreact.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 4, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def remove(self, ctx, trigger: str):
        if not await self.trigger_exists(ctx.guild.id, trigger):
            embed = discord.Embed(
                title="<:feast_cross:1400143488695144609> Trigger Not Found",
                description=f"The trigger '{trigger}' does not exist.",
                color=0x006fb9
            )
            embed.set_footer(text=f"Requested By {ctx.author}",
                   icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            return await ctx.reply(embed=embed)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM autoreact WHERE guild_id = ? AND trigger = ?", (ctx.guild.id, trigger))
            await db.commit()

        embed = discord.Embed(
            title="<:feast_tick:1400143469892210753> Trigger Removed",
            description=f"Successfully removed trigger '{trigger}'.",
            color=0x006fb9
        )
        embed.set_footer(text=f"Requested By {ctx.author}",
               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        await ctx.reply(embed=embed)

    @react.command(name="list", aliases=["show", "config"], help="Lists all the triggers and their emojis in the autoreact module.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 4, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def list(self, ctx):
        triggers = await self.get_triggers(ctx.guild.id)
        if not triggers:
            embed = discord.Embed(
                title="No Triggers Set",
                description="There are no auto-reaction triggers set in this guild.",
                color=0x006fb9
            )
            return await ctx.reply(embed=embed)

        trigger_list = "\n".join([f"{t[0]}: {t[1]}" for t in triggers])
        embed = discord.Embed(
            title="Auto-Reaction Triggers",
            description=trigger_list,
            color=0x006fb9
        )
        embed.set_footer(text=f"Requested By {ctx.author}",
               icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        await ctx.reply(embed=embed)

    @react.command(name="reset", help="Resets all the triggers and their emojis in the autoreact module.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 4, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def reset(self, ctx):
        triggers = await self.get_triggers(ctx.guild.id)
        if not triggers:
            embed = discord.Embed(
                title="<:feast_cross:1400143488695144609> No Triggers Set",
                description="There are no auto-reaction triggers set to reset.",
                color=0x006fb9
            )
            embed.set_footer(text=f"Requested By {ctx.author}",
                   icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            return await ctx.reply(embed=embed)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM autoreact WHERE guild_id = ?", (ctx.guild.id,))
            await db.commit()

        embed = discord.Embed(
            title="<:feast_tick:1400143469892210753> All Triggers Reset",
            description="Successfully removed all auto-reaction triggers.",
            color=0x006fb9
        )
        embed.set_footer(text=f"Requested By {ctx.author}",
                       icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        await ctx.reply(embed=embed)

    @react.error
    async def react_error(self, ctx, error):
        """Error handler for react command group"""
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="<:feast_cross:1400143488695144609> Access Denied",
                description="You need **Administrator** permissions to use autoreact commands.",
                color=0xFF0000
            )
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await ctx.reply(embed=embed)
        elif isinstance(error, commands.BotMissingPermissions):
            embed = discord.Embed(
                title="<:feast_cross:1400143488695144609> Bot Missing Permissions",
                description=f"I need the following permissions: {', '.join(error.missing_permissions)}",
                color=0xFF0000
            )
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await ctx.reply(embed=embed)
        else:
            # Handle other errors
            embed = discord.Embed(
                title="<:feast_cross:1400143488695144609> Error",
                description=f"An error occurred: {str(error)}",
                color=0xFF0000
            )
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await ctx.reply(embed=embed)

async def setup(bot):
    await bot.add_cog(AutoReaction(bot))

"""
@Author: Frosty
    + Discord: frosty.pyro
    + Community: https://discord.gg/5wtjDkYbVh (Sleepless Development)
    + for any queries reach out in the server; or send a dm.
"""