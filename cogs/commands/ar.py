



import discord
import aiosqlite
from discord.ext import commands
from utils.Tools import blacklist_check, ignore_check

AR_DB_PATH = 'db/ar.db'


class ARL(commands.Cog):
    @commands.Cog.listener()
    async def on_member_join(self, member):
        # Fetch custom autoroles for this guild from persistent DB
        role_ids = await self.get_custom_autoroles(member.guild.id)
        roles_to_add = [member.guild.get_role(rid) for rid in role_ids if member.guild.get_role(rid)]
        if roles_to_add:
            try:
                await member.add_roles(*roles_to_add, reason="Sleepless Custom Autoroles (arl)")
            except discord.Forbidden:
                print(f"[ARL] Missing permissions to add custom autoroles in guild {member.guild.id}.")
            except discord.HTTPException as e:
                print(f"[ARL] Failed to add custom autoroles: {e}")
    def __init__(self, bot):
        self.bot = bot
        self.color = 0x006fb9

    async def cog_load(self):
        await self.create_table()

    async def create_table(self):
        async with aiosqlite.connect(AR_DB_PATH) as db:
            await db.execute('''
            CREATE TABLE IF NOT EXISTS autorole_custom (
                guild_id INTEGER PRIMARY KEY,
                roles TEXT NOT NULL
            )
            ''')
            await db.commit()

    async def get_custom_autoroles(self, guild_id: int):
        async with aiosqlite.connect(AR_DB_PATH) as db:
            async with db.execute("SELECT roles FROM autorole_custom WHERE guild_id = ?", (guild_id,)) as cursor:
                row = await cursor.fetchone()
                if row and row[0]:
                    return [int(role_id) for role_id in row[0].replace('[','').replace(']','').replace(' ','').split(',') if role_id]
                else:
                    return []

    async def set_custom_autoroles(self, guild_id: int, roles: list):
        async with aiosqlite.connect(AR_DB_PATH) as db:
            await db.execute("INSERT OR REPLACE INTO autorole_custom (guild_id, roles) VALUES (?, ?)", (guild_id, str(roles)))
            await db.commit()

    @commands.group(name="arl", invoke_without_command=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def arl(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)
            await ctx.message.add_reaction("❓")
            ctx.command.reset_cooldown(ctx)

    @arl.group(name="custom", invoke_without_command=True)
    async def custom(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)
            await ctx.message.add_reaction("❓")
            ctx.command.reset_cooldown(ctx)

    @custom.command(name="add", help="Add one or more roles to custom autoroles.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def _autorole_custom_add(self, ctx, *roles: discord.Role):
        if not roles:
            await ctx.reply("Please mention at least one role to add.")
            return
        current = await self.get_custom_autoroles(ctx.guild.id)
        added = []
        for role in roles:
            if role.id not in current:
                current.append(role.id)
                added.append(role.mention)
        await self.set_custom_autoroles(ctx.guild.id, current)
        if added:
            embed = discord.Embed(title=":white_check_mark: Success", description=f"Added to custom autoroles: {' '.join(added)}", color=self.color)
        else:
            embed = discord.Embed(title=":warning: No Change", description="No new roles were added.", color=self.color)
        await ctx.reply(embed=embed)

    @custom.command(name="remove", help="Remove one or more roles from custom autoroles.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def _autorole_custom_remove(self, ctx, *roles: discord.Role):
        if not roles:
            await ctx.reply("Please mention at least one role to remove.")
            return
        current = await self.get_custom_autoroles(ctx.guild.id)
        removed = []
        for role in roles:
            if role.id in current:
                current.remove(role.id)
                removed.append(role.mention)
        await self.set_custom_autoroles(ctx.guild.id, current)
        if removed:
            embed = discord.Embed(title=":white_check_mark: Success", description=f"Removed from custom autoroles: {' '.join(removed)}", color=self.color)
        else:
            embed = discord.Embed(title=":warning: No Change", description="No roles were removed.", color=self.color)
        await ctx.reply(embed=embed)

    @custom.command(name="list", help="List all custom autoroles for this server.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def _autorole_custom_list(self, ctx):
        current = await self.get_custom_autoroles(ctx.guild.id)
        if not current:
            await ctx.reply("No custom autoroles set for this server.")
            return
        roles = [ctx.guild.get_role(rid) for rid in current if ctx.guild.get_role(rid)]
        if not roles:
            await ctx.reply("No valid roles found in custom autoroles.")
            return
        embed = discord.Embed(title="Custom Autoroles", description="\n".join(role.mention for role in roles), color=self.color)
        await ctx.reply(embed=embed)

    @arl.error
    async def arl_error(self, ctx, error):
        """Error handler for arl command group"""
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="<:feast_cross:1400143488695144609> Access Denied",
                description="You need **Administrator** permissions to use custom autorole commands.",
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
    await bot.add_cog(ARL(bot))
