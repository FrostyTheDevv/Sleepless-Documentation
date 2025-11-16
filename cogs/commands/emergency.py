import discord
from discord.ext import commands
import aiosqlite
from utils.Tools import *

from utils.error_helpers import StandardErrorHandler
class EmergencyRestoreView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.value = None

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("Only the Server Owner can use this button.", ephemeral=True)
        self.value = True
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label="No", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("Only the Server Owner can use this button.", ephemeral=True)
        self.value = False
        await interaction.response.defer()
        self.stop()



class Emergency(commands.Cog):

    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "db/emergency.db"
        # Removed loop access from __init__

    async def setup_hook(self):
        """Called when the cog is loaded"""
        await self.initialize_database()

    async def initialize_database(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS authorised_users (
                    guild_id INTEGER,
                    user_id INTEGER
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS emergency_roles (
                    guild_id INTEGER,
                    role_id INTEGER
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS restore_roles (
                    guild_id INTEGER NOT NULL,
                    role_id INTEGER NOT NULL,
                    disabled_perms TEXT NOT NULL,
                    PRIMARY KEY (guild_id, role_id)
                )
            """)
            await db.execute("""
            CREATE TABLE IF NOT EXISTS role_positions (
    guild_id INTEGER,
    role_id INTEGER,
    previous_position INTEGER
)
""")
            await db.execute("""
                CREATE TABLE IF NOT EXISTS lockdown_state (
                    guild_id INTEGER PRIMARY KEY,
                    is_locked INTEGER DEFAULT 0,
                    locked_by INTEGER,
                    locked_at INTEGER,
                    reason TEXT
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS lockdown_permissions (
                    guild_id INTEGER,
                    role_id INTEGER,
                    permissions TEXT,
                    PRIMARY KEY (guild_id, role_id)
                )
            """)
            await db.commit()

    async def is_guild_owner(self, ctx):
        return ctx.guild and ctx.author.id == ctx.guild.owner_id

    async def is_guild_owner_or_authorised(self, ctx):
        if await self.is_guild_owner(ctx):
            return True
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT 1 FROM authorised_users WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, ctx.author.id)) as cursor:
                return await cursor.fetchone() is not None

    @commands.group(name="emergency", aliases=["emg"], help="Lists all the commands in the emergency group.", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 4, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    async def emergency(self, ctx):
        embed = discord.Embed(
            title="__Emergency Situation__",
            description="The `emergency` command group is designed to protect your server from malicious activity or accidental damage. It allows server owners and authorized users to disable dangerous permissions from roles by executing `emergencysituation` or `emgs` command and prevent potential risks.\n\n__**The command group has several subcommands**__:",
            color=0x006fb9
        )
        embed.add_field(name=f"`{ctx.prefix}emergency enable`", value="> Enable emergency mode, it adds all roles with dangerous permissions in the emergency role list.", inline=False)
        embed.add_field(name=f"`{ctx.prefix}emergency disable`", value="> Disable emergency mode and clear the emergency role list.", inline=False)
        embed.add_field(name=f"`{ctx.prefix}emergency lock [reason]`", value="> 🔒 **Complete server lockdown** - Strips all dangerous permissions from all roles. Use during raids or attacks.", inline=False)
        embed.add_field(name=f"`{ctx.prefix}emergency unlock`", value="> 🔓 **Unlock server** - Restores all permissions that were removed during lockdown.", inline=False)
        embed.add_field(name=f"`{ctx.prefix}emergency status`", value="> 📊 **Check lockdown status** - View current lockdown state and details.", inline=False)
        embed.add_field(name=f"`{ctx.prefix}emergency authorise`", value="> Manage authorized users for executing `emergencysituation` command.", inline=False)
        embed.add_field(name=f"`{ctx.prefix}emergency role`", value="> Manage roles added to the emergency list. You can add/remove/list roles by emergency role group.", inline=False)
        embed.add_field(name=f"`{ctx.prefix}emergency-situation` or `{ctx.prefix}emgs`", value="> Execute emergency situation which disables dangerous permissions from roles in the emergency list & move the role with maximum member to top position below the bot top role. Restore disabled permissions of role using `emgrestore`.", inline=False)
        embed.set_footer(text="Use \"help emergency <subcommand>\" for more information.", icon_url=self.bot.user.avatar.url)
        await ctx.reply(embed=embed)


    @emergency.command(name="enable", help="Enable emergency mode and add all roles with dangerous permissions.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 4, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    async def enable(self, ctx):
        Sleepless = ['1385303636766359612', '1385303636766359612']
        if ctx.author.id != ctx.guild.owner_id and str(ctx.author.id) not in Sleepless:
            embed = discord.Embed(title="<:feast_cross:1400143488695144609> Error", description="Only the server owner can enable emergency mode.", color=0x006fb9)
            return await ctx.reply(embed=embed)

        dangerous_permissions = ["administrator", "ban_members", "kick_members", "manage_channels", "manage_roles", "manage_guild"]
        roles_added = []

        async with aiosqlite.connect(self.db_path) as db:
            for role in ctx.guild.roles:
                
                if role.managed or role.is_bot_managed():
                    continue

                if role.position >= ctx.guild.me.top_role.position:
                    continue
                
                
                if any(getattr(role.permissions, perm, False) for perm in dangerous_permissions):
                    async with db.execute("SELECT 1 FROM emergency_roles WHERE guild_id = ? AND role_id = ?", (ctx.guild.id, role.id)) as cursor:
                        if not await cursor.fetchone():
                            await db.execute("INSERT INTO emergency_roles (guild_id, role_id) VALUES (?, ?)", (ctx.guild.id, role.id))
                            roles_added.append(role)

            await db.commit()

        
        if roles_added:
            description = "\n".join([f"{role.mention}" for role in roles_added])
            embed = discord.Embed(title="<:feast_tick:1400143469892210753> Success", description=f"The following roles with dangerous permissions have been added to the **emergency list**:\n{description}", color=0x006fb9)
            embed.set_footer(text="Roles having greater or equal position than my top role is not added in the emergency list.", icon_url=self.bot.user.display_avatar.url)
        else:
            embed = discord.Embed(title="<:feast_cross:1400143488695144609> Error", description="No new roles with dangerous permissions were found.", color=0x006fb9)
        
        await ctx.reply(embed=embed)
        

    @emergency.command(name="disable", help="Disable emergency mode and clear the emergency role list.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 4, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    async def disable(self, ctx):
        Sleepless = ['1385303636766359612', '1385303636766359612']
        if ctx.author.id != ctx.guild.owner_id and str(ctx.author.id) not in Sleepless:
            embed = discord.Embed(title="<:feast_cross:1400143488695144609> Error", description="Only the server owner can disable emergency mode.", color=0x006fb9)
            return await ctx.reply(embed=embed)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM emergency_roles WHERE guild_id = ?", (ctx.guild.id,))
            await db.commit()

        embed = discord.Embed(title="<:feast_tick:1400143469892210753> Success", description="Emergency mode has been disabled, and all emergency roles have been cleared.", color=0x006fb9)
        await ctx.reply(embed=embed)

    


    @emergency.group(name="authorise", aliases=["ath"], help="Lists all the commands in the emergency authorise group.", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 4, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    async def authorise(self, ctx):
        if ctx.subcommand_passed is None:
            await ctx.send_help(ctx.command)
            ctx.command.reset_cooldown(ctx)

    @authorise.command(name="add", help="Adds a user to the authorised group.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 4, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    async def authorise_add(self, ctx, member: discord.Member):
        if not await self.is_guild_owner(ctx):
            embed = discord.Embed(title="<:feast_cross:1400143488695144609> Error", description="Only the server owner can add authorised users for executing emergency situation.", color=0x006fb9)
            return await ctx.reply(embed=embed)

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM authorised_users WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()
                count = row[0] if row is not None else 0
            if count >= 5:
                embed = discord.Embed(title="<:feast_warning:1400143131990560830> Access Denied", description="Only up to 5 authorised users can be added.", color=0x006fb9)
                return await ctx.reply(embed=embed)

            async with db.execute("SELECT 1 FROM authorised_users WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, member.id)) as cursor:
                if await cursor.fetchone():
                    embed = discord.Embed(title="<:feast_cross:1400143488695144609> Error", description="This user is already authorised.", color=0x006fb9)
                    return await ctx.reply(embed=embed)

            await db.execute("INSERT INTO authorised_users (guild_id, user_id) VALUES (?, ?)", (ctx.guild.id, member.id))
            await db.commit()

        embed = discord.Embed(title="<:feast_tick:1400143469892210753> Success", description=f"**{member.display_name}** has been authorised to use `emergency-situation` command.", color=0x006fb9)
        await ctx.reply(embed=embed)

    @authorise.command(name="remove", help="Removes a user from the authorised group")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 4, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    async def authorise_remove(self, ctx, member: discord.Member):
        if not await self.is_guild_owner(ctx):
            embed = discord.Embed(title="<:feast_warning:1400143131990560830> Access Denied", description="Only the server owner can remove authorised users for emergency situation.", color=0x006fb9)
            return await ctx.reply(embed=embed)

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT 1 FROM authorised_users WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, member.id)) as cursor:
                if not await cursor.fetchone():
                    embed = discord.Embed(title="<:feast_cross:1400143488695144609> Error", description="This user is not authorised.", color=0x006fb9)
                    return await ctx.reply(embed=embed)

            await db.execute("DELETE FROM authorised_users WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, member.id))
            await db.commit()

        embed = discord.Embed(title="<:feast_tick:1400143469892210753> Success", description=f"**{member.display_name}** has been removed from the authorised list and can no more use `emergency-situation` command.", color=0x006fb9)
        await ctx.reply(embed=embed)

    @authorise.command(name="list", aliases=["view", "config"], help="Lists all authorised users for emergency actions.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 4, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    async def list_authorized(self, ctx):
        if not await self.is_guild_owner(ctx):
            embed = discord.Embed(title="<:feast_warning:1400143131990560830> Access Denied", description="Only the server owner can view the list of authorised users for emergency situation.", color=0x006fb9)
            return await ctx.reply(embed=embed)

        
        async with aiosqlite.connect('db/emergency.db') as db:
            cursor = await db.execute("SELECT user_id FROM authorised_users WHERE guild_id = ?", (ctx.guild.id,))
            authorized_users = await cursor.fetchall()
            
        if not authorized_users:
            await ctx.reply(embed=discord.Embed(
                title="Authorized Users",
                description="No authorized users found.",
                color=0x006fb9))
            return
                
        description = "\n".join([f"{index + 1}. [{ctx.guild.get_member(user[0]).name}](https://discord.com/users/{user[0]}) - {user[0]}" for index, user in enumerate(authorized_users)])
        await ctx.reply(embed=discord.Embed(
            title="Authorized Users",
            description=description,
            color=0x006fb9))

    @emergency.group(name="role", help="Lists all the commands in the emergency role group.", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 4, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    async def role(self, ctx):
        if ctx.subcommand_passed is None:
            await ctx.send_help(ctx.command)
            ctx.command.reset_cooldown(ctx)

    @role.command(name="add", help="Adds a role to the emergency role list")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 4, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    async def role_add(self, ctx, role: discord.Role):
        if not await self.is_guild_owner(ctx):
            embed = discord.Embed(title="<:feast_warning:1400143131990560830> Access Denied", description="Only the server owner can add role for emergency situation.", color=0x006fb9)
            return await ctx.reply(embed=embed)


        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM emergency_roles WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                row = await cursor.fetchone()
                count = row[0] if row is not None else 0
            if count >= 25:
                embed = discord.Embed(title="<:feast_warning:1400143131990560830> Error", description="Only up to 25 roles can be added.", color=0x006fb9)
                return await ctx.reply(embed=embed)

            async with db.execute("SELECT 1 FROM emergency_roles WHERE guild_id = ? AND role_id = ?", (ctx.guild.id, role.id)) as cursor:
                if await cursor.fetchone():
                    embed = discord.Embed(title="<:feast_cross:1400143488695144609> Error", description="This role is already in the emergency list.", color=0x006fb9)
                    return await ctx.reply(embed=embed)

            await db.execute("INSERT INTO emergency_roles (guild_id, role_id) VALUES (?, ?)", (ctx.guild.id, role.id))
            await db.commit()

        embed = discord.Embed(title="<:feast_tick:1400143469892210753> Success", description=f"**{role.name}** has been **added** to the emergency list.", color=0x006fb9)
        await ctx.reply(embed=embed)

    @role.command(name="remove", help="Removes a role from the emergency role list.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 4, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    async def role_remove(self, ctx, role: discord.Role):
        if not await self.is_guild_owner(ctx):
            embed = discord.Embed(title="<:feast_warning:1400143131990560830> Access Denied", description="Only the server owner can remove roles from emergency list.", color=0x006fb9)
            return await ctx.reply(embed=embed)

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT 1 FROM emergency_roles WHERE guild_id = ? AND role_id = ?", (ctx.guild.id, role.id)) as cursor:
                if not await cursor.fetchone():
                    embed = discord.Embed(title="<:feast_cross:1400143488695144609> Error", description="This role is not in the emergency list.", color=0x006fb9)
                    return await ctx.reply(embed=embed)

            await db.execute("DELETE FROM emergency_roles WHERE guild_id = ? AND role_id = ?", (ctx.guild.id, role.id))
            await db.commit()

        embed = discord.Embed(title="<:feast_tick:1400143469892210753> Success", description=f"**{role.name}** has been removed from the emergency list.", color=0x006fb9)
        await ctx.reply(embed=embed)

    @role.command(name="list", aliases=["view", "config"], help="Lists all roles added to the emergency list.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 4, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    async def list_roles(self, ctx):
        if not await self.is_guild_owner_or_authorised(ctx):
            embed = discord.Embed(title="<:feast_warning:1400143131990560830> Access Denied", description="You are not authorised to view list of roles for emergency situation.", color=0x006fb9)
            return await ctx.reply(embed=embed)

        
        async with aiosqlite.connect('db/emergency.db') as db:
            cursor = await db.execute("SELECT role_id FROM emergency_roles WHERE guild_id = ?", (ctx.guild.id,))
            roles = await cursor.fetchall()

        if not roles:
            
            await ctx.reply(embed=discord.Embed(
                title="Emergency Roles",
                description="No roles added for emergency situation.",
                color=0x006fb9))
            return

        description = "\n".join([f"{index + 1}. <@&{role[0]}> - {role[0]}" for index, role in enumerate(roles)])

        await ctx.reply(embed=discord.Embed(
            title="Emergency Roles",
            description=description,
            color=0x006fb9))


    @commands.command(name="emergencysituation", help="Disable dangerous permissions from roles in the emergency list.", aliases=["emergency-situation", "emgs"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 40, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.bot_has_permissions(manage_roles=True)
    async def emergencysituation(self, ctx):
        Sleepless = ['1385303636766359612', '1385303636766359612']
        guild_id = ctx.guild.id

        if not await self.is_guild_owner_or_authorised(ctx) and str(ctx.author.id) not in Sleepless:
            return await ctx.reply(embed=discord.Embed(
                title="<:feast_warning:1400143131990560830> Access Denied", 
                description="You are not authorised to execute the emergency situation.", 
                color=0x006fb9))

        processing_message = await ctx.send(embed=discord.Embed(title=" Processing Emergency Situation, wait for a while...", color=0x006fb9))

        antinuke_enabled = False
        async with aiosqlite.connect('db/anti.db') as anti:
            async with anti.execute("SELECT status FROM antinuke WHERE guild_id = ?", (guild_id,)) as cursor:
                antinuke_status = await cursor.fetchone()
            if antinuke_status:
                antinuke_enabled = True
                await anti.execute('DELETE FROM antinuke WHERE guild_id = ?', (guild_id,))
                await anti.commit()
                
                
                

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM restore_roles WHERE guild_id = ?", (ctx.guild.id,))
            await db.commit()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT role_id FROM emergency_roles WHERE guild_id = ?", (ctx.guild.id,))
            emergency_roles = await cursor.fetchall()

        if not emergency_roles:
            await processing_message.delete()
            return await ctx.reply(embed=discord.Embed(
                title="<:feast_cross:1400143488695144609> Error",
                description="No roles have been added for the emergency situation.",
                color=0x006fb9))

        bot_highest_role = ctx.guild.me.top_role
        dangerous_permissions = [
            "administrator", "ban_members", "kick_members", 
            "manage_channels", "manage_roles", "manage_guild"
        ]

        modified_roles = []
        unchanged_roles = []

        async with aiosqlite.connect(self.db_path) as db:
            for role_data in emergency_roles:
                role = ctx.guild.get_role(role_data[0])

                if not role:
                    continue

                if role.position >= bot_highest_role.position or role.managed:
                    unchanged_roles.append(role)
                    continue

                permissions_changed = False
                role_permissions = role.permissions
                disabled_perms = []

                for perm in dangerous_permissions:
                    if getattr(role_permissions, perm, False):
                        setattr(role_permissions, perm, False)
                        permissions_changed = True
                        disabled_perms.append(perm)

                if permissions_changed:
                    try:
                        await role.edit(permissions=role_permissions, reason="Emergency Situation: Disabled dangerous permissions")
                        modified_roles.append(role)

                        await db.execute("INSERT INTO restore_roles (guild_id, role_id, disabled_perms) VALUES (?, ?, ?)", 
                                         (ctx.guild.id, role.id, ','.join(disabled_perms)))
                        await db.commit()

                    except discord.Forbidden:
                        unchanged_roles.append(role)

        if modified_roles:
            success_message = "\n".join([f"{role.mention}" for role in modified_roles])
        else:
            success_message = "No roles were modified."

        if unchanged_roles:
            error_message = "\n".join([f"{role.mention}" for role in unchanged_roles])
        else:
            error_message = "No roles had permission errors."

        most_mem = max(
            [role for role in ctx.guild.roles if not role.managed and role.position < bot_highest_role.position and role != ctx.guild.default_role],
            key=lambda role: len(role.members),
            default=None
        )

        if most_mem:
            target_position = bot_highest_role.position - 1 
            try:
                await most_mem.edit(position=target_position, reason="Emergency Situation: Role moved for safety")
                await ctx.reply(embed=discord.Embed(
                    title="Emergency Situation",
                    description=f"**<:feast_tick:1400143469892210753> Roles Modified (Denied Dangerous Permissions)**:\n{success_message}\n\n**<:feast_warning:1400143131990560830>  Role Moved**: {most_mem.mention} moved to a position below the bot's highest role.\n**Move back to its previous position soon after the server is not in risk.**\n\n** Errors**:\n{error_message}",
                    color=0x006fb9))
            except discord.Forbidden:
                await ctx.reply(embed=discord.Embed(
                    title="Emergency Situation",
                    description=f"**<:feast_tick:1400143469892210753> Roles Modified (Denied Dangerous Permissions)**:\n{success_message}\n\n**ℹ️ Role Couldn't Moved**: Failed to move the role {most_mem.mention} below the bot's highest role due to permissions error.\n**Move back to its previous position soon after the server is not in risk.**\n\n**Errors**:\n{error_message}",
                    color=0x006fb9))

            except Exception as e:
                await ctx.reply(embed=discord.Embed(
                    title="Emergency Situation",
                    description=f"**<:feast_tick:1400143469892210753> Roles Modified (Denied Dangerous Permissions)**:\n{success_message}\n\n**ℹ️ Role Couldn't Moved**: An unexpected error occurred while moving the role: {str(e)}.\n**Move back to its previous position soon after the server is not in risk.**\n\n** Errors**:\n{error_message}",
                    color=0x006fb9)) 
        else:
            await ctx.reply(embed=discord.Embed(
                title="Emergency Situation",
                description=f"**<:feast_tick:1400143469892210753> Roles Modified (Denied Dangerous Permissions)**:\n{success_message}\n\n**<Errors**:\n{error_message}",
                color=0x006fb9))

        if antinuke_enabled:
            async with aiosqlite.connect('db/anti.db') as anti:
                await anti.execute("INSERT INTO antinuke (guild_id, status) VALUES (?, 1)", (guild_id,))
                await anti.commit()

        await processing_message.delete()


    
    @commands.command(name="emergencyrestore", aliases=["...", "emgrestore", "emgsrestore", "emgbackup"], help="Restore disabled permissions to roles.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 30, commands.BucketType.user)
    @commands.guild_only()
    @commands.bot_has_permissions(manage_roles=True)
    async def emergencyrestore(self, ctx):
        Sleepless = ['1385303636766359612', '1385303636766359612']
        if ctx.author.id != ctx.guild.owner_id and str(ctx.author.id) not in Sleepless:
            return await ctx.reply(embed=discord.Embed(
                title="<:feast_warning:1400143131990560830> Access Denied", 
                description="Only the server owner can execute the emergency restore command.", 
                color=0x006fb9))

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT role_id, disabled_perms FROM restore_roles WHERE guild_id = ?", (ctx.guild.id,))
            restore_roles = await cursor.fetchall()

        if not restore_roles:
            return await ctx.reply(embed=discord.Embed(
                title="<:feast_cross:1400143488695144609> Error",
                description="No roles were found with disabled permissions for restore.",
                color=0x006fb9))

        confirmation_embed = discord.Embed(
            title="Confirm Restoration",
            description="This will restore previously disabled permissions for emergency roles. Do you want to proceed?",
            color=0x006fb9
        )
        view = EmergencyRestoreView(ctx)
        await ctx.send(embed=confirmation_embed, view=view)

        await view.wait()

        if view.value is None:
            return await ctx.reply(embed=discord.Embed(
                title="Restore Cancelled",
                description="The restore process timed out.",
                color=0x006fb9))

        if view.value is False:
            return await ctx.reply(embed=discord.Embed(
                title="Restore Cancelled",
                description="Restoring permissions to roles has been cancelled.",
                color=0x006fb9))

        modified_roles = []
        unchanged_roles = []

        async with aiosqlite.connect(self.db_path) as db:
            for role_id, disabled_perms in restore_roles:
                role = ctx.guild.get_role(role_id)

                if not role:
                    continue

                role_permissions = role.permissions
                permissions_restored = False

                for perm in disabled_perms.split(','):
                    if hasattr(role_permissions, perm):
                        setattr(role_permissions, perm, True)
                        permissions_restored = True

                if permissions_restored:
                    try:
                        await role.edit(permissions=role_permissions, reason="Emergency Restore: Restored permissions")
                        modified_roles.append(role)
                    except discord.Forbidden:
                        unchanged_roles.append(role)

            await db.execute("DELETE FROM restore_roles WHERE guild_id = ?", (ctx.guild.id,))
            await db.commit()

        if modified_roles:
            success_message = "\n".join([f"{role.mention}" for role in modified_roles])
        else:
            success_message = "No roles were restored."

        if unchanged_roles:
            error_message = "\n".join([f"{role.mention}" for role in unchanged_roles])
        else:
            error_message = "No roles had permission errors."

        await ctx.reply(embed=discord.Embed(
            title="Emergency Restore",
            description=f"**<:feast_tick:1400143469892210753> Permissions Restored**:\n{success_message}\n\n**<:ml_cross:1204106928675102770> Errors**:\n{error_message}\n\n Database of previously disabled permissions has been cleared.",
            color=0x006fb9))


    @emergency.command(name="lock", help="Complete server lockdown - freeze all role permissions during raid/attack.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 60, commands.BucketType.guild)
    @commands.guild_only()
    @commands.bot_has_permissions(manage_roles=True)
    async def lockdown_lock(self, ctx, *, reason: str = "Emergency raid protection"):
        """Lock down the server by stripping dangerous permissions from all roles"""
        Sleepless = ['1385303636766359612', '1385303636766359612']
        if ctx.author.id != ctx.guild.owner_id and str(ctx.author.id) not in Sleepless:
            return await ctx.reply(embed=discord.Embed(
                title="<:feast_cross:1400143488695144609> Access Denied", 
                description="Only the server owner can initiate emergency lockdown.", 
                color=0xFF0000))

        # Check if already locked
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT is_locked FROM lockdown_state WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                result = await cursor.fetchone()
                if result and result[0] == 1:
                    return await ctx.reply(embed=discord.Embed(
                        title="<:feast_warning:1400143131990560830> Already Locked",
                        description="Server is already in lockdown mode. Use `emergency unlock` to restore.",
                        color=0xFF6B6B))

        processing = await ctx.reply(embed=discord.Embed(
            title="<a:feast_loading:1400143445710098513> Initiating Lockdown...",
            description="Saving current permissions and locking down the server...",
            color=0xFFA500))

        bot_highest_role = ctx.guild.me.top_role
        dangerous_permissions = [
            "administrator", "ban_members", "kick_members", "manage_channels",
            "manage_roles", "manage_guild", "manage_webhooks", "manage_emojis",
            "manage_messages", "mention_everyone", "create_instant_invite"
        ]

        locked_roles = []
        failed_roles = []
        import time as time_module
        
        async with aiosqlite.connect(self.db_path) as db:
            for role in ctx.guild.roles:
                # Skip @everyone, managed roles, and roles above bot
                if role == ctx.guild.default_role or role.managed or role.position >= bot_highest_role.position:
                    continue

                # Check if role has any dangerous permissions
                has_dangerous = any(getattr(role.permissions, perm, False) for perm in dangerous_permissions)
                
                if has_dangerous:
                    # Save current permissions
                    current_perms = role.permissions.value
                    await db.execute(
                        "INSERT OR REPLACE INTO lockdown_permissions (guild_id, role_id, permissions) VALUES (?, ?, ?)",
                        (ctx.guild.id, role.id, str(current_perms))
                    )

                    # Create new permissions with dangerous ones stripped
                    new_perms = role.permissions
                    for perm in dangerous_permissions:
                        if hasattr(new_perms, perm):
                            setattr(new_perms, perm, False)

                    try:
                        await role.edit(permissions=new_perms, reason=f"Emergency Lockdown by {ctx.author}")
                        locked_roles.append(role)
                    except discord.Forbidden:
                        failed_roles.append(role)
                    except Exception as e:
                        failed_roles.append(role)

            # Save lockdown state
            await db.execute("""
                INSERT OR REPLACE INTO lockdown_state (guild_id, is_locked, locked_by, locked_at, reason)
                VALUES (?, 1, ?, ?, ?)
            """, (ctx.guild.id, ctx.author.id, int(time_module.time()), reason))
            await db.commit()

        # Build response embed
        embed = discord.Embed(
            title="🔒 Server Lockdown Activated",
            description=f"**Reason:** {reason}\n**Initiated by:** {ctx.author.mention}\n**Time:** {discord.utils.format_dt(discord.utils.utcnow(), style='F')}",
            color=0xFF0000
        )

        if locked_roles:
            roles_text = ", ".join([r.mention for r in locked_roles[:10]])
            if len(locked_roles) > 10:
                roles_text += f"\n*...and {len(locked_roles) - 10} more*"
            embed.add_field(
                name=f"🔒 Locked Roles ({len(locked_roles)})",
                value=roles_text,
                inline=False
            )

        if failed_roles:
            failed_text = ", ".join([r.mention for r in failed_roles[:5]])
            if len(failed_roles) > 5:
                failed_text += f"\n*...and {len(failed_roles) - 5} more*"
            embed.add_field(
                name=f"⚠️ Failed to Lock ({len(failed_roles)})",
                value=failed_text,
                inline=False
            )

        embed.add_field(
            name="ℹ️ Next Steps",
            value=f"• All dangerous permissions have been stripped\n• Use `{ctx.prefix}emergency unlock` to restore\n• Use `{ctx.prefix}emergency status` to check lockdown state",
            inline=False
        )

        await processing.delete()
        await ctx.reply(embed=embed)


    @emergency.command(name="unlock", help="Restore all permissions and unlock the server.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 60, commands.BucketType.guild)
    @commands.guild_only()
    @commands.bot_has_permissions(manage_roles=True)
    async def lockdown_unlock(self, ctx):
        """Unlock the server and restore all saved permissions"""
        Sleepless = ['1385303636766359612', '1385303636766359612']
        if ctx.author.id != ctx.guild.owner_id and str(ctx.author.id) not in Sleepless:
            return await ctx.reply(embed=discord.Embed(
                title="<:feast_cross:1400143488695144609> Access Denied", 
                description="Only the server owner can unlock the server.", 
                color=0xFF0000))

        # Check if server is locked
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT is_locked, locked_by, locked_at, reason FROM lockdown_state WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                lockdown = await cursor.fetchone()

            if not lockdown or lockdown[0] == 0:
                return await ctx.reply(embed=discord.Embed(
                    title="<:feast_cross:1400143488695144609> Not Locked",
                    description="Server is not currently in lockdown mode.",
                    color=0xFF6B6B))

        # Confirmation view
        class UnlockConfirmView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=30)
                self.value = None

            @discord.ui.button(label="Unlock Server", style=discord.ButtonStyle.green, emoji="🔓")
            async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != ctx.author.id:
                    return await interaction.response.send_message("Only the command author can confirm.", ephemeral=True)
                self.value = True
                await interaction.response.defer()
                self.stop()

            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji="❌")
            async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != ctx.author.id:
                    return await interaction.response.send_message("Only the command author can cancel.", ephemeral=True)
                self.value = False
                await interaction.response.defer()
                self.stop()

        view = UnlockConfirmView()
        confirm_embed = discord.Embed(
            title="⚠️ Confirm Server Unlock",
            description="This will restore all permissions that were removed during lockdown. Are you sure?",
            color=0xFFA500
        )
        msg = await ctx.reply(embed=confirm_embed, view=view)
        await view.wait()

        if view.value is None or view.value is False:
            return await msg.edit(embed=discord.Embed(
                title="❌ Unlock Cancelled",
                description="Server remains in lockdown mode.",
                color=0xFF6B6B
            ), view=None)

        # Start unlocking
        processing = await msg.edit(embed=discord.Embed(
            title="<a:feast_loading:1400143445710098513> Unlocking Server...",
            description="Restoring permissions...",
            color=0xFFA500
        ), view=None)

        restored_roles = []
        failed_roles = []

        async with aiosqlite.connect(self.db_path) as db:
            # Get saved permissions
            async with db.execute("SELECT role_id, permissions FROM lockdown_permissions WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                saved_perms = await cursor.fetchall()

            for role_id, perms_value in saved_perms:
                role = ctx.guild.get_role(role_id)
                if not role:
                    continue

                try:
                    # Restore original permissions
                    original_perms = discord.Permissions(int(perms_value))
                    await role.edit(permissions=original_perms, reason=f"Lockdown lifted by {ctx.author}")
                    restored_roles.append(role)
                except Exception as e:
                    failed_roles.append(role)

            # Clear lockdown state
            await db.execute("UPDATE lockdown_state SET is_locked = 0 WHERE guild_id = ?", (ctx.guild.id,))
            await db.execute("DELETE FROM lockdown_permissions WHERE guild_id = ?", (ctx.guild.id,))
            await db.commit()

        # Build response
        embed = discord.Embed(
            title="🔓 Server Unlocked",
            description=f"**Unlocked by:** {ctx.author.mention}\n**Time:** {discord.utils.format_dt(discord.utils.utcnow(), style='F')}",
            color=0x00FF00
        )

        if restored_roles:
            roles_text = ", ".join([r.mention for r in restored_roles[:10]])
            if len(restored_roles) > 10:
                roles_text += f"\n*...and {len(restored_roles) - 10} more*"
            embed.add_field(
                name=f"✅ Restored Roles ({len(restored_roles)})",
                value=roles_text,
                inline=False
            )

        if failed_roles:
            failed_text = ", ".join([r.mention for r in failed_roles[:5]])
            if len(failed_roles) > 5:
                failed_text += f"\n*...and {len(failed_roles) - 5} more*"
            embed.add_field(
                name=f"⚠️ Failed to Restore ({len(failed_roles)})",
                value=failed_text,
                inline=False
            )

        embed.set_footer(text="Server is now fully operational")
        await processing.edit(embed=embed)


    @emergency.command(name="status", help="Check current lockdown status.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.guild_only()
    async def lockdown_status(self, ctx):
        """Check if server is in lockdown and get details"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT is_locked, locked_by, locked_at, reason FROM lockdown_state WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                lockdown = await cursor.fetchone()

            # Get count of locked roles
            async with db.execute("SELECT COUNT(*) FROM lockdown_permissions WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
                result = await cursor.fetchone()
                locked_roles_count = result[0] if result else 0

        if not lockdown or lockdown[0] == 0:
            embed = discord.Embed(
                title="🔓 Server Status: Unlocked",
                description="Server is operating normally. No lockdown is active.",
                color=0x00FF00
            )
            embed.add_field(
                name="ℹ️ Lockdown Commands",
                value=f"`{ctx.prefix}emergency lock [reason]` - Activate emergency lockdown\n`{ctx.prefix}emergency unlock` - Lift lockdown",
                inline=False
            )
        else:
            is_locked, locked_by, locked_at, reason = lockdown
            locker = ctx.guild.get_member(locked_by) or await self.bot.fetch_user(locked_by)
            
            embed = discord.Embed(
                title="🔒 Server Status: LOCKED DOWN",
                description=f"**Reason:** {reason or 'No reason provided'}",
                color=0xFF0000
            )
            embed.add_field(name="🔒 Locked By", value=locker.mention if locker else f"User ID: {locked_by}", inline=True)
            embed.add_field(name="⏰ Locked At", value=discord.utils.format_dt(discord.utils.utcnow().replace(second=locked_at % 60), style='R'), inline=True)
            embed.add_field(name="📊 Locked Roles", value=str(locked_roles_count), inline=True)
            embed.add_field(
                name="⚠️ Active Restrictions",
                value="• All dangerous permissions stripped\n• Role management locked\n• Server modifications limited",
                inline=False
            )
            embed.add_field(
                name="🔓 Unlock Command",
                value=f"Use `{ctx.prefix}emergency unlock` to restore normal operations",
                inline=False
            )

        await ctx.reply(embed=embed)


async def setup(bot):
    cog = Emergency(bot)
    await cog.initialize_database()
    await bot.add_cog(cog)


"""
@Author: Frosty
    + Discord: frosty.pyro
    + Community: https://discord.gg/5wtjDkYbVh (Sleepless Development)
    + for any queries reach out in the server; or send a dm.
"""