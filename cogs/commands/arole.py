






import discord
import aiosqlite
from discord.ext import commands
from utils.Tools import blacklist_check, ignore_check


from utils.error_helpers import StandardErrorHandler
AROLE_DB_PATH = 'db/arole.db'


class Arole(commands.Cog):
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot
        self.color = 0x006fb9

    async def _send_response(self, ctx, *args, **kwargs):
        try:
            if hasattr(ctx, 'interaction') and ctx.interaction is not None and not ctx.interaction.response.is_done():
                return await ctx.interaction.response.send_message(*args, **kwargs)
            elif hasattr(ctx, 'reply'):
                return await ctx.reply(*args, **kwargs)
            else:
                return await ctx.send(*args, **kwargs)
        except discord.Forbidden:
            # Try to send a simple message if we can't send embeds
            try:
                await ctx.send("❌ I don't have permission to send messages in this channel.")
            except:
                pass  # If we can't send any message, silently fail

    async def cog_load(self):
        await self.create_table()

    async def create_table(self):
        async with aiosqlite.connect(AROLE_DB_PATH) as db:
            await db.execute('''
            CREATE TABLE IF NOT EXISTS autorole (
                guild_id INTEGER PRIMARY KEY,
                bots TEXT NOT NULL,
                humans TEXT NOT NULL
            )
            ''')
            await db.commit()

    async def get_autorole(self, guild_id: int):
        async with aiosqlite.connect(AROLE_DB_PATH) as db:
            async with db.execute("SELECT bots, humans FROM autorole WHERE guild_id = ?", (guild_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    bots, humans = row
                    bots = [int(r) for r in bots.replace('[','').replace(']','').replace(' ','').split(',') if r]
                    humans = [int(r) for r in humans.replace('[','').replace(']','').replace(' ','').split(',') if r]
                    return {"bots": bots, "humans": humans}
                else:
                    return {"bots": [], "humans": []}

    async def set_autorole(self, guild_id: int, bots: list, humans: list):
        async with aiosqlite.connect(AROLE_DB_PATH) as db:
            await db.execute("INSERT OR REPLACE INTO autorole (guild_id, bots, humans) VALUES (?, ?, ?)", (guild_id, str(bots), str(humans)))
            await db.commit()

    @commands.group(name="arole", invoke_without_command=True, description="Manage autoroles for humans and bots.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def arole(self, ctx):
        if ctx.invoked_subcommand is None:
            await self._send_response(ctx, content=f"Use `{ctx.clean_prefix}help arole` to see all autorole commands.")
            if hasattr(ctx, 'message'):
                await ctx.message.add_reaction("❓")
            ctx.command.reset_cooldown(ctx)

    @arole.command(name="config", help="Shows the current arole configuration")
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def config(self, ctx):
        data = await self.get_autorole(ctx.guild.id)
        fetched_humans = [ctx.guild.get_role(role_id) for role_id in data["humans"] if ctx.guild.get_role(role_id)]
        fetched_bots = [ctx.guild.get_role(role_id) for role_id in data["bots"] if ctx.guild.get_role(role_id)]
        hums = "\n".join(role.mention for role in fetched_humans) or "None"
        bos = "\n".join(role.mention for role in fetched_bots) or "None"
        emb = discord.Embed(color=self.color, title=f"Autorole Configuration for {ctx.guild.name}")
        emb.add_field(name=" __Humans__", value=hums, inline=False)
        emb.add_field(name=" __Bots__", value=bos, inline=False)
        await self._send_response(ctx, embed=emb)

    @commands.group(name="reset", invoke_without_command=True, description="Reset autorole configuration.")
    async def reset(self, ctx):
        if ctx.invoked_subcommand is None:
            await self._send_response(ctx, content=f"Use `{ctx.clean_prefix}help arole reset` to see reset options.")
            if hasattr(ctx, 'message'):
                await ctx.message.add_reaction("❓")
            ctx.command.reset_cooldown(ctx)

    @arole.command(name="humansclear", help="Clear autorole configuration for humans")
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def _autorole_humans_reset(self, ctx):
        data = await self.get_autorole(ctx.guild.id)
        if data["humans"]:
            await self.set_autorole(ctx.guild.id, data["bots"], [])
            embed = discord.Embed(title="<:feast_tick:1400143469892210753> Success", description="Cleared all human autoroles in this Guild.", color=self.color)
        else:
            embed = discord.Embed(title="<:feast_cross:1400143488695144609> Error", description="No Autoroles set for humans in this Guild.", color=self.color)
        await self._send_response(ctx, embed=embed)

    @arole.command(name="botsclear", help="Clear autorole configuration for bots")
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def _autorole_bots_reset(self, ctx):
        data = await self.get_autorole(ctx.guild.id)
        if data["bots"]:
            await self.set_autorole(ctx.guild.id, [], data["humans"])
            embed = discord.Embed(title="<:feast_tick:1400143469892210753> Success", description="Cleared all bot autoroles in this Guild.", color=self.color)
        else:
            embed = discord.Embed(title="<:feast_cross:1400143488695144609> Error", description="No Autoroles set for Bots in this Guild.", color=self.color)
        await self._send_response(ctx, embed=embed)

    @arole.command(name="clearall", help="Clear all autorole configuration in the Guild")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def _autorole_reset_all(self, ctx):
        data = await self.get_autorole(ctx.guild.id)
        if data["humans"] or data["bots"]:
            await self.set_autorole(ctx.guild.id, [], [])
            embed = discord.Embed(title="<:feast_tick:1400143469892210753> Success", description="Cleared all autoroles in this Guild.", color=self.color)
        else:
            embed = discord.Embed(title="<:feast_cross:1400143488695144609> Error", description="No Autoroles set in this Guild.", color=self.color)
        await self._send_response(ctx, embed=embed)

    @commands.group(name="humans", invoke_without_command=True, description="Manage human autoroles.")
    async def humans(self, ctx):
        if ctx.invoked_subcommand is None:
            await self._send_response(ctx, content=f"Use `{ctx.clean_prefix}help arole humans` to see human autorole options.")
            if hasattr(ctx, 'message'):
                await ctx.message.add_reaction("❓")
            ctx.command.reset_cooldown(ctx)

    @humans.command(name="humansadd", help="Add role to list of human Autoroles.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def _autorole_humans_add(self, ctx, *, role: discord.Role):
        data = await self.get_autorole(ctx.guild.id)
        humans = data["humans"]
        if role.id in humans:
            embed = discord.Embed(title="<:feast_warning:1400143131990560830> Access Denied", description=f"{role.mention} is already in human autoroles.", color=self.color)
        elif len(humans) >= 10:
            embed = discord.Embed(title="<:feast_warning:1400143131990560830> Access Denied", description="You can only add up to 10 human autoroles.", color=self.color)
        else:
            humans.append(role.id)
            await self.set_autorole(ctx.guild.id, data["bots"], humans)
            embed = discord.Embed(title="<:feast_tick:1400143469892210753> Success", description=f"{role.mention} has been added to human autoroles.", color=self.color)
        await self._send_response(ctx, embed=embed)

    @humans.command(name="humansremove", help="Remove a role from human Autoroles.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def _autorole_humans_remove(self, ctx, *, role: discord.Role):
        data = await self.get_autorole(ctx.guild.id)
        humans = data["humans"]
        if role.id not in humans:
            embed = discord.Embed(title="<:feast_cross:1400143488695144609> Error", description=f"{role.mention} is not in human autoroles.", color=self.color)
        else:
            humans.remove(role.id)
            await self.set_autorole(ctx.guild.id, data["bots"], humans)
            embed = discord.Embed(title="<:feast_tick:1400143469892210753> Success", description=f"{role.mention} has been removed from human autoroles.", color=self.color)
        await self._send_response(ctx, embed=embed)

    @commands.group(name="bots", invoke_without_command=True, description="Manage bot autoroles.")
    async def bots(self, ctx):
        if ctx.invoked_subcommand is None:
            await self._send_response(ctx, content=f"Use `{ctx.clean_prefix}help arole bots` to see bot autorole options.")
            if hasattr(ctx, 'message'):
                try:
                    await ctx.message.add_reaction("❓")
                except discord.Forbidden:
                    pass  # Bot doesn't have permission to add reactions
            ctx.command.reset_cooldown(ctx)

    @bots.command(name="botsadd", help="Add role to bot Autoroles.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def _autorole_bots_add(self, ctx, *, role: discord.Role):
        data = await self.get_autorole(ctx.guild.id)
        bots = data["bots"]
        if role.id in bots:
            embed = discord.Embed(title="<:feast_warning:1400143131990560830> Access Denied", description=f"{role.mention} is already in bot autoroles.", color=self.color)
        elif len(bots) >= 10:
            embed = discord.Embed(title="<:feast_warning:1400143131990560830> Access Denied", description="You can only add up to 10 bot autoroles.", color=self.color)
        else:
            bots.append(role.id)
            await self.set_autorole(ctx.guild.id, bots, data["humans"])
            embed = discord.Embed(title="<:feast_tick:1400143469892210753> Success", description=f"{role.mention} has been added to bot autoroles.", color=self.color)
        await self._send_response(ctx, embed=embed)

    @bots.command(name="botsremove", help="Remove a role from bot Autoroles.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def _autorole_bots_remove(self, ctx, *, role: discord.Role):
        data = await self.get_autorole(ctx.guild.id)
        bots = data["bots"]
        if role.id not in bots:
            embed = discord.Embed(title="<:feast_cross:1400143488695144609> Error", description=f"{role.mention} is not in bot autoroles.", color=self.color)
        else:
            bots.remove(role.id)
            await self.set_autorole(ctx.guild.id, bots, data["humans"])
            embed = discord.Embed(title="<:feast_tick:1400143469892210753> Success", description=f"{role.mention} has been removed from bot autoroles.", color=self.color)
        await self._send_response(ctx, embed=embed)

    @arole.error
    async def arole_error(self, ctx, error):
        """Error handler for arole command group"""
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="<:feast_cross:1400143488695144609> Access Denied",
                description="You need **Administrator** permissions to use autorole commands.",
                color=0xFF0000
            )
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await self._send_response(ctx, embed=embed)
        elif isinstance(error, commands.BotMissingPermissions):
            embed = discord.Embed(
                title="<:feast_cross:1400143488695144609> Bot Missing Permissions",
                description=f"I need the following permissions: {', '.join(error.missing_permissions)}",
                color=0xFF0000
            )
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await self._send_response(ctx, embed=embed)
        else:
            # Handle other errors
            embed = discord.Embed(
                title="<:feast_cross:1400143488695144609> Error",
                description=f"An error occurred: {str(error)}",
                color=0xFF0000
            )
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await self._send_response(ctx, embed=embed)

async def setup(bot):
    await bot.add_cog(Arole(bot))
