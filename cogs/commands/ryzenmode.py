import discord
from discord.ext import commands
import aiosqlite
import os
from utils.Tools import *

from utils.error_helpers import StandardErrorHandler
# Database setup
db_folder = 'db'
db_file = 'anti.db'
db_path = os.path.join(db_folder, db_file)

class ryzenmode(commands.Cog):

    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot
        self.ryzen = ['1385303636766359612',]
        self.color = 0x006fb9
        # Removed loop access from __init__

    async def setup_hook(self):
        """Called when the cog is loaded"""
        await self.initialize_db()  

    async def initialize_db(self):
        self.db = await aiosqlite.connect(db_path)
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS ryzenmode (
                guildId TEXT,
                roleId TEXT,
                adminPermissions INTEGER
            )
        ''')
        await self.db.commit()

    async def is_extra_owner(self, user, guild):
        async with self.db.execute('''
            SELECT owner_id FROM extraowners WHERE guild_id = ? AND owner_id = ?
        ''', (guild.id, user.id)) as cursor:
            extra_owner = await cursor.fetchone()
        return extra_owner is not None

    @commands.hybrid_group(name="ryzenmode", aliases=[], help="Manages ryzenmode feature", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    async def ryzenmode(self, ctx):
        ryzenmode_embed = discord.Embed(
            title='__**ryzenmode**__',
            color=self.color,
            description=(
                'ryzenmode swiftly disables dangerous permissions for roles, like stripping `ADMINISTRATION` rights, while preserving original settings for seamless restoration.\n\n**Make sure to keep my ROLE above all roles you want to protect.**'
            )
        )
        ryzenmode_embed.add_field(
            name="Usage",
            value=" `ryzenmode enable`\n `ryzenmode disable`",
            inline=False
        )
        ryzenmode_embed.set_thumbnail(url=self.bot.user.avatar.url)
        await ctx.send(embed=ryzenmode_embed)

    @ryzenmode.command(name="enable", help="Enable ryzenmode")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def enable_ryzenmode(self, ctx):
        if ctx.guild.member_count < 50:  
            return await ctx.send(embed=discord.Embed(title="<:feast_cross:1400143488695144609> Access Denied",
                color=self.color,
                description='Your Server Doesn\'t Meet My 50 Member Criteria'
            ))

        own = ctx.author.id == ctx.guild.owner_id
        check = await self.is_extra_owner(ctx.author, ctx.guild)
        if not own and not check and ctx.author.id not in self.ryzen:
            return await ctx.send(embed=discord.Embed(title="<:feast_cross:1400143488695144609> Access Denied",
                color=self.color,
                description='Only Server Owner Or Extraowner Can Run This Command.!'
            ))

        if not own and not (
            ctx.guild.me.top_role.position <= ctx.author.top_role.position
        ) and ctx.author.id not in self.ryzen:
            return await ctx.send(embed=discord.Embed(title="<:feast_warning:1400143131990560830> Access Denied",
                color=self.color,
                description='Only Server Owner or Extraowner Having **Higher role than me can run this command**'
            ))

        bot_highest_role = ctx.guild.me.top_role
        manageable_roles = [
            role for role in ctx.guild.roles
            if role.position < bot_highest_role.position 
            and role.name != '@everyone' 
            and role.permissions.administrator
            and not role.managed  
        ]

        if not manageable_roles:
            return await ctx.send(embed=discord.Embed(title="<:feast_cross:1400143488695144609>  Error",
                color=self.color,
                description='No Roles Found With Admin Permissions'
            ))

        async with self.db.execute('SELECT guildId FROM ryzenmode WHERE guildId = ?', (str(ctx.guild.id),)) as cursor:
            if await cursor.fetchone():
                return await ctx.send(embed=discord.Embed(title="<:feast_cross:1400143488695144609>  Error",
                    color=self.color,
                    description='ryzenmode is already enabled.'
                ))

        async with self.db.cursor() as cursor:
            for role in manageable_roles:
                admin_permissions = discord.Permissions(administrator=True)
                if role.permissions.administrator:
                    permissions = role.permissions
                    permissions.administrator = False

                    await role.edit(permissions=permissions, reason='ryzenmode ENABLED')

                    await cursor.execute('''
                    INSERT OR REPLACE INTO ryzenmode (guildId, roleId, adminPermissions)
                    VALUES (?, ?, ?)
                    ''', (str(ctx.guild.id), str(role.id), int(admin_permissions.value)))
            await self.db.commit()

        await ctx.send(embed=discord.Embed(title="<:feast_tick:1400143469892210753> Success",
            color=self.color,
            description='ryzenmode enabled! Dangerous Permissions Disabled For Manageable Roles.'
        ))

    @ryzenmode.command(name="disable", help="Disable ryzenmode")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def disable_ryzenmode(self, ctx):
        if ctx.guild.member_count < 50:  
            return await ctx.send(embed=discord.Embed(title="<:feast_warning:1400143131990560830> Access Denied",
                color=self.color,
                description='Your Server Doesn\'t Meet My 50 Member Criteria'
            ))

        own = ctx.author.id == ctx.guild.owner_id
        check = await self.is_extra_owner(ctx.author, ctx.guild)
        if not own and not check and ctx.author.id not in self.ryzen:
            return await ctx.send(embed=discord.Embed(title="<:feast_warning:1400143131990560830> Access Denied",
                color=self.color,
                description='Only Server Owner Or Extraowner Can Run This Command.!'
            ))

        if not own and not (
            ctx.guild.me.top_role.position <= ctx.author.top_role.position
        ) and ctx.author.id not in self.ryzen:
            return await ctx.send(embed=discord.Embed(title="<:feast_warning:1400143131990560830> Access Denied",
                color=self.color,
                description='Only Server Owner or Extraowner Having **Higher role than me can run this command**'
            ))

        async with self.db.execute('SELECT roleId, adminPermissions FROM ryzenmode WHERE guildId = ?', (str(ctx.guild.id),)) as cursor:
            stored_roles = await cursor.fetchall()

        if not stored_roles:
            return await ctx.send(embed=discord.Embed(title="<:feast_cross:1400143488695144609> Error",
                color=self.color,
                description='ryzenmode is not enabled.'
            ))

        async with self.db.cursor() as cursor:
            for role_id, admin_permissions in stored_roles:
                role = ctx.guild.get_role(int(role_id))
                if role:
                    permissions = discord.Permissions(administrator=bool(admin_permissions))
                    await role.edit(permissions=permissions, reason='ryzenmode DISABLED')

                    await cursor.execute('DELETE FROM ryzenmode WHERE guildId = ? AND roleId = ?', (str(ctx.guild.id), role_id))
            await self.db.commit()

        await ctx.send(embed=discord.Embed(title="<:feast_tick:1400143469892210753> Success",
            color=self.color,
            description='ryzenmode disabled! Restored Permissions For Manageable Roles.'
        ))

"""
@Author: Frosty
    + Discord: frosty.pyro
    + Community: https://discord.gg/5wtjDkYbVh (Sleepless Development)
    + for any queries reach out in the server; or send a dm.
"""