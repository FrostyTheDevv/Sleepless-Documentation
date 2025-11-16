import discord
from discord import app_commands
from discord.ext import commands
from discord.ext.commands import Context
import aiosqlite
import asyncio
from utils.Tools import *
from typing import List, Tuple

from utils.error_helpers import StandardErrorHandler
DATABASE_PATH = 'db/customrole.db'
DATABASE_PATH2 = 'db/np.db'


class Customrole(commands.Cog):

    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot
        self.cooldown = {}
        self.rate_limit = {}
        self.rate_limit_timeout = 5
        # Removed loop access from __init__

    async def setup_hook(self):
        """Called when the cog is loaded"""
        await self.create_tables()


    async def reset_rate_limit(self, user_id):
        await asyncio.sleep(self.rate_limit_timeout)
        self.rate_limit.pop(user_id, None)
        



    async def add_role(self, *, role_id: int, member: discord.Member):
        if member.guild.me.guild_permissions.manage_roles:
            role = discord.Object(id=role_id)
            await member.add_roles(role, reason="Sleepless Customrole | Role Added")
        else:
            raise commands.CheckFailure("Bot does not have permission to manage roles.")



    async def remove_role(self, *, role_id: int, member: discord.Member):
        if member.guild.me.guild_permissions.manage_roles:
            role = discord.Object(id=role_id)
            await member.remove_roles(role, reason="Sleepless Customrole | Role Removed")
        else:
            raise commands.CheckFailure("Bot does not have permission to manage roles.")
            


    async def add_role2(self, *, role: discord.Role, member: discord.Member):
        if member.guild.me.guild_permissions.manage_roles:
            await member.add_roles(role, reason="Sleepless Customrole | Role Added ")

    async def remove_role2(self, *, role: discord.Role, member: discord.Member):
        if member.guild.me.guild_permissions.manage_roles:
            await member.remove_roles(role, reason="Sleepless Customrole| Role Removed")

    

    async def handle_role_command(self, context: Context, member: discord.Member, role_type: str):
        async with aiosqlite.connect('db/customrole.db') as db:
            if context.guild is None:
                embed = discord.Embed(title="<:feast_cross:1400143488695144609> Error",
                    description="This command can only be used in a server.",
                    color=0x006fb9)
                await context.reply(embed=embed)
                return

            async with db.execute(f"SELECT reqrole, {role_type} FROM roles WHERE guild_id = ?", (context.guild.id,)) as cursor:
                data = await cursor.fetchone()
                if data:
                    reqrole_id, role_id = data
                    reqrole = context.guild.get_role(reqrole_id) if reqrole_id is not None else None
                    role = context.guild.get_role(role_id) if role_id is not None else None

                    if reqrole is None:
                        embed = discord.Embed(title="<:feast_warning:1400143131990560830> Access Denied",
                            description=f"Required role is not set up in {context.guild.name}",
                            color=0x006fb9)
                        await context.reply(embed=embed)
                        return

                    author = context.author
                    if isinstance(author, discord.User) and context.guild is not None and hasattr(context.guild, 'get_member'):
                        author = context.guild.get_member(author.id)
                    if context.guild is not None and (
                        author == getattr(context.guild, 'owner', None)
                        or (isinstance(author, discord.Member) and hasattr(author, 'roles') and reqrole in author.roles)
                    ):
                        if role is not None:
                            if role not in member.roles:
                                await self.add_role2(role=role, member=member)
                                embed = discord.Embed(title="<:feast_tick:1400143469892210753> Success",
                                    description=f"**Given** <@&{role.id}> To {member.mention}",
                                    color=0x006fb9)
                            else:
                                await self.remove_role2(role=role, member=member)
                                embed = discord.Embed(title="<:feast_tick:1400143469892210753> Success",
                                    description=f"**Removed** <@&{role.id}> From {member.mention}",
                                    color=0x006fb9)
                            await context.reply(embed=embed)
                        else:
                            embed = discord.Embed(title="<:feast_cross:1400143488695144609> Error",
                                description=f"{role_type.capitalize()} role is not set up in {context.guild.name}",
                                color=0x006fb9)
                            await context.reply(embed=embed)
                    else:
                        embed = discord.Embed(title="<:feast_warning:1400143131990560830> Access Denied",
                            description=f"You need {reqrole.mention if reqrole else 'the required role'} to run this command.",
                            color=0x006fb9)
                        await context.reply(embed=embed)
                else:
                    embed = discord.Embed(title="<:feast_cross:1400143488695144609> Error",
                        description=f"Roles configuration is not set up in {context.guild.name}",
                        color=0x006fb9)
                    await context.reply(embed=embed)

    


    async def create_tables(self):
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS roles (
                    guild_id INTEGER PRIMARY KEY,
                    staff INTEGER,
                    girl INTEGER,
                    vip INTEGER,
                    guest INTEGER,
                    frnd INTEGER,
                    reqrole INTEGER
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS custom_roles (
                    guild_id INTEGER,
                    name TEXT,
                    role_id INTEGER,
                    PRIMARY KEY (guild_id, name)
                )
            ''')
            await db.commit()

    
    @commands.hybrid_group(name="setup",
                           description="Setups custom roles for the server.",
                           help="Setups custom roles for the server.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def set(self, context: Context):
        if context.subcommand_passed is None:
            await context.send_help(context.command)
            if context.command is not None:
                context.command.reset_cooldown(context)

    async def fetch_role_data(self, guild_id):
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute("SELECT staff, girl, vip, guest, frnd, reqrole FROM roles WHERE guild_id = ?", (guild_id,)) as cursor:
                return await cursor.fetchone()




    async def update_role_data(self, guild_id, column, value):
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                await db.execute(f"INSERT OR REPLACE INTO roles (guild_id, {column}) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET {column} = ?",
                                 (guild_id, value, value))
                await db.commit()
        except Exception as e:
            print(f"Error updating role data: {e}")
            

    async def fetch_custom_role_data(self, guild_id):
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute("SELECT name, role_id FROM custom_roles WHERE guild_id = ?", (guild_id,)) as cursor:
                return await cursor.fetchall()


    @set.command(name="staff",
                 description="Setup staff role in guild",
                 help="Setup staff role in Guild")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    @app_commands.describe(role="Role to be added")
    async def staff(self, context: Context, role: discord.Role) -> None:
        author = context.author
        guild = getattr(context, 'guild', None)
        guild_owner = getattr(guild, 'owner', None)
        guild_me = getattr(guild, 'me', None)
        author_top_role = getattr(author, 'top_role', None)
        me_top_role = getattr(guild_me, 'top_role', None)
        if (author == guild_owner or (author_top_role and me_top_role and author_top_role.position > me_top_role.position)):
            await self.update_role_data(getattr(guild, 'id', 0), 'staff', getattr(role, 'id', None))
            embed = discord.Embed(title="<:feast_tick:1400143469892210753> Success",
                description=f"Added {getattr(role, 'mention', str(role))} to `Staff` Role\n\n__**How to Use?**__\nUse `staff <user>` Command to **Add {getattr(role, 'mention', str(role))}** role to User & use again to the same user to **Remove role**. ",
                color=0x006fb9)
            await context.reply(embed=embed)
        else:
            embed = discord.Embed(title="<:feast_warning:1400143131990560830> Access Denied",
                                  description="Your role should be above my top role.",
                                  color=0x006fb9)
            await context.reply(embed=embed)

    @set.command(name="girl",
                 description="Setup girl role in the Guild",
                 help="Setup girl role in the Guild")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    @app_commands.describe(role="Role to be added")
    async def girl(self, context: Context, role: discord.Role) -> None:
        guild_owner = getattr(context.guild, 'owner', None)
        guild_me = getattr(context.guild, 'me', None)
        author_top_role = getattr(context.author, 'top_role', None)
        me_top_role = getattr(guild_me, 'top_role', None)
        if (context.author == guild_owner or (author_top_role and me_top_role and author_top_role.position > me_top_role.position)):
            await self.update_role_data(getattr(context.guild, 'id', 0), 'girl', getattr(role, 'id', None))
            embed = discord.Embed(title="<:feast_tick:1400143469892210753> Success",
                description=f"Added {role.mention} to `Girl` Role\n\n__**How to Use?**__\nUse `girl <user>` Command to **Add {role.mention}** role to User & use again to the same user to **Remove role**.  ",
                color=0x006fb9)
            await context.reply(embed=embed)
        else:
            embed = discord.Embed(title="<:feast_warning:1400143131990560830> Access Denied",
                  description="Your role should be above my top role.",
                  color=0x006fb9)
            await context.reply(embed=embed)

    @set.command(name="vip",
                 description="Setups vip role in the Guild",
                 help="Setups vip role in the Guild")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    @app_commands.describe(role="Role to be added")
    async def vip(self, context: Context, role: discord.Role) -> None:
        guild_owner = getattr(context.guild, 'owner', None)
        guild_me = getattr(context.guild, 'me', None)
        author_top_role = getattr(context.author, 'top_role', None)
        me_top_role = getattr(guild_me, 'top_role', None)
        if (context.author == guild_owner or (author_top_role and me_top_role and author_top_role.position > me_top_role.position)):
            await self.update_role_data(getattr(context.guild, 'id', 0), 'vip', getattr(role, 'id', None))
            embed = discord.Embed(
                description=f"Added {role.mention} to `VIP` Role\n\n__**How to Use?**__\nUse `vip <user>` Command to **Add {role.mention}** role to User & use again to the same user to **Remove role**. ",
                color=0x006fb9)
            await context.reply(embed=embed)
        else:
            embed = discord.Embed(title="<:feast_warning:1400143131990560830>Access Denied",
                                  description="Your role should be above my top role.",
                                  color=0x006fb9)
            await context.reply(embed=embed)

    @set.command(name="guest",
                 description="Setup guest role in the Guild",
                 help="Setup guest role in the Guild")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    @app_commands.describe(role="Role to be added")
    async def guest(self, context: Context, role: discord.Role) -> None:
        guild_owner = getattr(context.guild, 'owner', None)
        guild_me = getattr(context.guild, 'me', None)
        author_top_role = getattr(context.author, 'top_role', None)
        me_top_role = getattr(guild_me, 'top_role', None)
        if (context.author == guild_owner or (author_top_role and me_top_role and author_top_role.position > me_top_role.position)):
            await self.update_role_data(getattr(context.guild, 'id', 0), 'guest', getattr(role, 'id', None))
            embed = discord.Embed(
                description=f"Added {role.mention} to `Guest` Role\n\n__**How to Use?**__\nUse `guest <user>` Command to **Add {role.mention}** role to User & use again to the same user to **Remove role**. ",
                color=0x006fb9)
            await context.reply(embed=embed)
        else:
            embed = discord.Embed(title="<:feast_warning:1400143131990560830> Access Denied",
                                  description="Your role should be above my top role.",
                                  color=0x006fb9)
            await context.reply(embed=embed)

    @set.command(name="friend",
                 description="Setup friend role in the Guild",
                 help="Setup friend role in the Guild")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    @app_commands.describe(role="Role to be added")
    async def friend(self, context: Context, role: discord.Role) -> None:
        guild_owner = getattr(context.guild, 'owner', None)
        guild_me = getattr(context.guild, 'me', None)
        author_top_role = getattr(context.author, 'top_role', None)
        me_top_role = getattr(guild_me, 'top_role', None)
        if (context.author == guild_owner or (author_top_role and me_top_role and author_top_role.position > me_top_role.position)):
            await self.update_role_data(getattr(context.guild, 'id', 0), 'frnd', getattr(role, 'id', None))
            embed = discord.Embed(
                description=f"Added {role.mention} to `Friend` Role\n\n__**How to Use?**__\nUse `friend <user>` Command to **Add {role.mention}** role to User & use again to the same user to **Remove role**. ",
                color=0x006fb9)
            await context.reply(embed=embed)
        else:
            embed = discord.Embed(title="<:feast_warning:1400143131990560830> Access Denied",
                                  description="Your role should be above my top role.",
                                  color=0x006fb9)
            await context.reply(embed=embed)

    @set.command(name="reqrole",
                 description="Setup required role for custom role commands",
                 help="Setup required role for custom role commands")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 4, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    @app_commands.describe(role="Role to be added")
    async def req_role(self, context: Context, role: discord.Role) -> None:
        guild = getattr(context, 'guild', None)
        guild_owner = getattr(guild, 'owner', None)
        guild_me = getattr(guild, 'me', None)
        author_top_role = getattr(context.author, 'top_role', None)
        me_top_role = getattr(guild_me, 'top_role', None)
        if (context.author == guild_owner or (author_top_role and me_top_role and author_top_role.position > me_top_role.position)):
            await self.update_role_data(getattr(guild, 'id', 0), 'reqrole', getattr(role, 'id', None))
            embed = discord.Embed(title="<:feast_tick:1400143469892210753> Success",
                color=0x006fb9,
                description=f"Added {getattr(role, 'mention', str(role))} for Required role to run custom role commands in {getattr(guild, 'name', 'this server')}"
            )
            await context.reply(embed=embed)
        else:
            embed = discord.Embed(title="<:feast_warning:1400143131990560830> Access Denied",
                                  description="Your role should be above my top role.",
                                  color=0x006fb9)
            await context.reply(embed=embed)

    

    @set.command(name="config",
                 description="Shows the current custom role configuration in the Guild.",
                 help="Shows the current custom role configuration in the Guild.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def config(self, context: Context) -> None:
        guild = getattr(context, 'guild', None)
        role_data = await self.fetch_role_data(getattr(guild, 'id', 0))
        if role_data and hasattr(guild, 'get_role'):
            embed = discord.Embed(
                title="Custom Role Configuration",
                color=0x006fb9
            )
            labels = ["Staff Role", "Girl Role", "VIP Role", "Guest Role", "Friend Role", "Required Role for Commands"]
            for idx, label in enumerate(labels):
                role_id = role_data[idx] if idx < len(role_data) else None
                role = guild.get_role(role_id) if guild is not None and hasattr(guild, 'get_role') and role_id else None
                embed.add_field(name=label, value=getattr(role, 'mention', 'None') if role else "None", inline=False)
            embed.set_footer(text="Use Commands to assign role & use again to the same user to remove role.")
            await context.reply(embed=embed)
        else:
            embed = discord.Embed(title="<:feast_cross:1400143488695144609> Error",
                description="No custom role configuration found in this Guild.",
                color=0x006fb9
            )
            await context.reply(embed=embed)



            


    @set.command(name="create",
                 description="Creates a custom role command.",
                 help="Creates a custom role command")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    @app_commands.describe(name="Command name", role="Role to be assigned")
    async def create(self, context: Context, name: str, role: discord.Role) -> None:
        guild = getattr(context, 'guild', None)
        guild_id = getattr(guild, 'id', 0)
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute("SELECT COUNT(*) FROM custom_roles WHERE guild_id = ?", (guild_id,)) as cursor:
                count = await cursor.fetchone()
                if count and count[0] >= 56:
                    embed = discord.Embed(title="<:feast_warning:1400143131990560830> Access Denied",
                        description="You have reached the maximum limit of 56 custom role commands for this guild.",
                        color=0x006fb9
                    )
                    await context.reply(embed=embed)
                    return

            async with db.execute("SELECT name FROM custom_roles WHERE guild_id = ?", (guild_id,)) as cursor:
                existing_role = await cursor.fetchall()
                if any(name == row[0] for row in existing_role):
                    embed = discord.Embed(title="<:feast_cross:1400143488695144609> Error",
                        description=f"A custom role command with the name `{name}` already exists in this guild. Remove it before creating a new one.",
                        color=0x006fb9
                    )
                    await context.reply(embed=embed)
                    return

            await db.execute("INSERT INTO custom_roles (guild_id, name, role_id) VALUES (?, ?, ?)",
                             (guild_id, name, getattr(role, 'id', None)))
            await db.commit()

        embed = discord.Embed(title="<:feast_tick:1400143469892210753> Success",
            description=f"Custom role command `{name}` created to assign the role {getattr(role, 'mention', str(role))}.\n\n__**How to Use?**__\nUse `{name} <user>` Command to Assign/Remove {getattr(role, 'mention', str(role))} role to User.\n> This will work for the users having `Manage Roles` permissions.",
            color=0x006fb9
        )
        await context.reply(embed=embed)
        

    @set.command(name="delete", aliases=["remove"],
                 description="Deletes a custom role command.",
                 help="Deletes a custom role command.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    @app_commands.describe(name="Command name to be deleted")
    async def delete(self, context: Context, name: str) -> None:
        guild = getattr(context, 'guild', None)
        guild_id = getattr(guild, 'id', 0)
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute("SELECT name FROM custom_roles WHERE guild_id = ? AND name = ?", (guild_id, name)) as cursor:
                existing_role = await cursor.fetchone()

        if not existing_role:
            embed = discord.Embed(title="<:feast_cross:1400143488695144609> Error",
                description=f"No custom role command with the name `{name}` was found in this guild.",
                color=0x006fb9
            )
            await context.reply(embed=embed)
            return

        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute("DELETE FROM custom_roles WHERE guild_id = ? AND name = ?", (guild_id, name))
            await db.commit()

        embed = discord.Embed(title="<:feast_tick:1400143469892210753> Success",
            description=f"Custom role command `{name}` has been deleted.",
            color=0x006fb9
        )
        await context.reply(embed=embed)
        

    @set.command(
        name="list",
        description="List all the custom roles setup for the server.",
        help="List all the custom roles setup for the server."
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def list(self, context: Context) -> None:
        guild = getattr(context, 'guild', None)
        guild_id = getattr(guild, 'id', 0)
        custom_roles = await self.fetch_custom_role_data(guild_id)

        if not custom_roles:
            embed = discord.Embed(
                title="<:feast_cross:1400143488695144609> Error",
                description="No custom roles have been created for this server.",
                color=0x006fb9
            )
            await context.reply(embed=embed)
            return

        def chunk_list(data: List[Tuple[str, int]], chunk_size: int):
            """Yield successive chunks of `chunk_size` from `data`."""
            for i in range(0, len(data), chunk_size):
                yield data[i:i + chunk_size]

        guild = getattr(context, 'guild', None)
        custom_roles_list = [(row[0], row[1]) for row in custom_roles]
        chunks = list(chunk_list(custom_roles_list, 7))

        for i, chunk in enumerate(chunks):
            embed = discord.Embed(
                title="Custom Roles",
                color=0x006fb9
            )
            for name, role_id in chunk:
                role = guild.get_role(role_id) if guild is not None and hasattr(guild, 'get_role') and role_id else None
                if role:
                    embed.add_field(name=f"Name: {name}", value=f"Role: {getattr(role, 'mention', str(role))}", inline=False)

            embed.set_footer(text=f"Page {i+1}/{len(chunks)} | These commands are usable by Members having Manage Role permissions.")
            await context.reply(embed=embed)



    @set.command(name="reset",
                 description="Resets custom role configuration for the server.",
                 help="Resets custom role configuration for the server.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 4, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def reset(self, context: Context) -> None:
        guild = getattr(context, 'guild', None)
        guild_owner = getattr(guild, 'owner', None)
        guild_me = getattr(guild, 'me', None)
        author_top_role = getattr(context.author, 'top_role', None)
        me_top_role = getattr(guild_me, 'top_role', None)
        if (context.author == guild_owner or (author_top_role and me_top_role and author_top_role.position > me_top_role.position)):
            removed_roles = []
            role_data = await self.fetch_role_data(getattr(guild, 'id', 0))
            if role_data and hasattr(guild, 'get_role'):
                roles = ["staff", "girl", "vip", "guest", "frnd", "reqrole"]
                for i, role_name in enumerate(roles):
                    role_id = role_data[i] if i < len(role_data) else None
                    role = guild.get_role(role_id) if guild is not None and hasattr(guild, 'get_role') and role_id else None
                    if role:
                        removed_roles.append(f"**{role_name.capitalize()}:** {getattr(role, 'mention', str(role))}")
                        await self.update_role_data(getattr(guild, 'id', 0), role_name, None)
                async with aiosqlite.connect(DATABASE_PATH) as db:
                    await db.execute("DELETE FROM custom_roles WHERE guild_id = ?", (getattr(guild, 'id', 0),))
                    await db.commit()
                    embed = discord.Embed(
                        title="Custom Role Configuration Reset",
                        description=f"Deleted All Custom Role commands <:Feast_tick:1227866641027698792>\n\n**Removed Roles:**\n" + "\n".join(removed_roles) if removed_roles else "No roles were previously set.",
                        color=0x006fb9
                    )
                    await context.reply(embed=embed)
            else:
                embed = discord.Embed(description="No configuration found for this server.", color=0x006fb9)
                await context.reply(embed=embed)
        else:
            embed = discord.Embed(title="<:feast_warning:1400143131990560830> Access Denied",
                                  description="Your role should be above my top role.",
                                  color=0x006fb9)
            await context.reply(embed=embed)

        
            

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.content:
            return

        prefixes = await self.bot.get_prefix(message)
        if not prefixes:
            return
        if not any(message.content.startswith(prefix) for prefix in prefixes):
            return
        for prefix in prefixes:
            if message.content.startswith(prefix):
                command_name = message.content[len(prefix):].split()[0]
                break
        else:
            return

        guild = getattr(message, 'guild', None)
        guild_id = getattr(guild, 'id', 0)
        if guild is None or not hasattr(guild, 'get_role'):
            return

        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute("SELECT role_id FROM custom_roles WHERE guild_id = ? AND name = ?", (guild_id, command_name)) as cursor:
                result = await cursor.fetchone()

        if result:
            role_id = result[0]
            role = guild.get_role(role_id) if role_id else None

            async with aiosqlite.connect(DATABASE_PATH) as db:
                async with db.execute("SELECT reqrole FROM roles WHERE guild_id = ?", (guild_id,)) as cursor:
                    reqrole_result = await cursor.fetchone()

            reqrole_id = reqrole_result[0] if reqrole_result else None
            reqrole = guild.get_role(reqrole_id) if reqrole_id else None

            if reqrole is None:
                await message.channel.send("<:feast_warning:1400143131990560830> The required role is not set up in this server. Please set it up using `setup reqrole`.")
                return

            author = message.author
            author_roles = getattr(author, 'roles', []) if isinstance(author, discord.Member) else []
            if not author_roles or reqrole not in author_roles:
                await message.channel.send(embed=discord.Embed(description=f"<:feast_warning:1400143131990560830> You need the {getattr(reqrole, 'mention', str(reqrole))} role to use this command.", color=0x006fb9))
                return

            member = message.mentions[0] if message.mentions and isinstance(message.mentions[0], discord.Member) else None
            if not member:
                await message.channel.send("Please mention a user to assign the role.")
                return

            now = asyncio.get_event_loop().time()
            if guild_id not in self.cooldown or now - self.cooldown[guild_id] >= 10:
                self.cooldown[guild_id] = now
            else:
                await message.channel.send("You're on a cooldown of 5 seconds. Please wait before sending another command.", delete_after=5)
                return

            try:
                if hasattr(member, 'roles') and role in member.roles:
                    await self.remove_role(role_id=role_id, member=member)
                    await message.channel.send(embed=discord.Embed(
                        title="<:feast_tick:1400143469892210753> Success",
                        description=f"**Removed** the role {getattr(role, 'mention', str(role))} from {getattr(member, 'mention', str(member))}.",
                        color=0x006fb9
                    ))
                else:
                    await self.add_role(role_id=role_id, member=member)
                    await message.channel.send(embed=discord.Embed(
                        title="<:feast_tick:1400143469892210753> Success",
                        description=f"**Added** the role {getattr(role, 'mention', str(role))} to {getattr(member, 'mention', str(member))}.",
                        color=0x006fb9
                    ))
            except discord.Forbidden as e:
                await message.channel.send("I do not have permission to manage this role to the given user.")
                print(f"Error: {e}")
        else:
            return

    

    @commands.hybrid_command(name="staff",
         description="Gives the staff role to the user.",
         aliases=['official'],
         help="Gives the staff role to the user.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    #@commands.has_permissions(manage_roles=True)
    async def _staff(self, context: Context, member: discord.Member) -> None:
        await self.handle_role_command(context, member, 'staff')

    @commands.hybrid_command(name="girl",
         description="Gives the girl role to the user.",
         aliases=['qt'],
         help="Gives the girl role to the user.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    #@commands.has_permissions(manage_roles=True)
    async def _girl(self, context: Context, member: discord.Member) -> None:
        await self.handle_role_command(context, member, 'girl')

    @commands.hybrid_command(name="vip",
         description="Gives the VIP role to the user.",
         help="Gives the VIP role to the user.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    #@commands.has_permissions(manage_roles=True)
    async def _vip(self, context: Context, member: discord.Member) -> None:
        await self.handle_role_command(context, member, 'vip')

    @commands.hybrid_command(name="guest",
         description="Gives the guest role to the user.",
         help="Gives the guest role to the user.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    #@commands.has_permissions(manage_roles=True)
    async def _guest(self, context: Context, member: discord.Member) -> None:
        await self.handle_role_command(context, member, 'guest')

    @commands.hybrid_command(name="friend",
         description="Gives the friend role to the user.",
         aliases=['frnd'],
         help="Gives the friend role to the user.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    #@commands.has_permissions(manage_roles=True)
    async def _friend(self, context: Context, member: discord.Member) -> None:
        await self.handle_role_command(context, member, 'frnd')


"""
@Author: Frosty
    + Discord: frosty.pyro
    + Community: https://discord.gg/5wtjDkYbVh (Sleepless Development)
    + for any queries reach out in the server; or send a dm.
"""