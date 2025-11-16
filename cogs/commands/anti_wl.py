from utils.error_helpers import StandardErrorHandler
# Extension loader for Discord.py
async def setup(bot):
    cog = Whitelist(bot)
    await cog.initialize_db()
    await bot.add_cog(cog)
import discord
from discord.ext import commands
import aiosqlite
import asyncio
from utils.Tools import *
from typing import Optional


class Whitelist(commands.Cog):
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot
        self.db = None
        # Initialize database when the cog is created
        asyncio.create_task(self.initialize_db())

    async def initialize_db(self):
        """Initialize the database connection"""
        try:
            if self.db is None:
                self.db = await aiosqlite.connect('db/anti.db')
                # Create whitelisted_users table
                await self.db.execute('''
                    CREATE TABLE IF NOT EXISTS whitelisted_users (
                    guild_id INTEGER,
                    user_id INTEGER,
                    ban BOOLEAN DEFAULT FALSE,
                    kick BOOLEAN DEFAULT FALSE,
                    prune BOOLEAN DEFAULT FALSE,
                    botadd BOOLEAN DEFAULT FALSE,
                    serverup BOOLEAN DEFAULT FALSE,
                    memup BOOLEAN DEFAULT FALSE,
                    chcr BOOLEAN DEFAULT FALSE,
                    chdl BOOLEAN DEFAULT FALSE,
                    chup BOOLEAN DEFAULT FALSE,
                    rlcr BOOLEAN DEFAULT FALSE,
                    rlup BOOLEAN DEFAULT FALSE,
                    rldl BOOLEAN DEFAULT FALSE,
                    meneve BOOLEAN DEFAULT FALSE,
                    mngweb BOOLEAN DEFAULT FALSE,
                    mngstemo BOOLEAN DEFAULT FALSE,
                    PRIMARY KEY (guild_id, user_id)
                )
            ''')
                # Create whitelisted_roles table (same structure as users)
                await self.db.execute('''
                    CREATE TABLE IF NOT EXISTS whitelisted_roles (
                    guild_id INTEGER,
                    role_id INTEGER,
                    ban BOOLEAN DEFAULT FALSE,
                    kick BOOLEAN DEFAULT FALSE,
                    prune BOOLEAN DEFAULT FALSE,
                    botadd BOOLEAN DEFAULT FALSE,
                    serverup BOOLEAN DEFAULT FALSE,
                    memup BOOLEAN DEFAULT FALSE,
                    chcr BOOLEAN DEFAULT FALSE,
                    chdl BOOLEAN DEFAULT FALSE,
                    chup BOOLEAN DEFAULT FALSE,
                    rlcr BOOLEAN DEFAULT FALSE,
                    rlup BOOLEAN DEFAULT FALSE,
                    rldl BOOLEAN DEFAULT FALSE,
                    meneve BOOLEAN DEFAULT FALSE,
                    mngweb BOOLEAN DEFAULT FALSE,
                    mngstemo BOOLEAN DEFAULT FALSE,
                    PRIMARY KEY (guild_id, role_id)
                )
            ''')
                # Create whitelist audit log table
                await self.db.execute('''
                    CREATE TABLE IF NOT EXISTS whitelist_audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    target_id INTEGER NOT NULL,
                    target_type TEXT NOT NULL,
                    actor_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    permissions TEXT,
                    reason TEXT,
                    timestamp INTEGER NOT NULL
                )
            ''')
                await self.db.commit()
        except Exception as e:
            print(f"Error initializing anti_wl database: {e}")
            self.db = None

    async def cog_load(self):
        """Called when the cog is loaded"""
        await self.initialize_db()

    async def setup_hook(self):
        """Called when the cog is loaded"""
        await self.initialize_db()

    async def ensure_db(self):
        """Ensure database connection exists"""
        try:
            if self.db is None:
                await self.initialize_db()
            # Test the connection
            if self.db is not None:
                await self.db.execute('SELECT 1')
        except Exception as e:
            print(f"Database connection error in anti_wl: {e}")
            try:
                await self.initialize_db()
            except Exception as e2:
                print(f"Failed to reinitialize database: {e2}")
                self.db = None
    
    async def log_whitelist_action(self, guild_id: int, target_id: int, target_type: str, 
                                   actor_id: int, action: str, permissions: Optional[str] = None, reason: Optional[str] = None):
        """Log whitelist add/remove actions to audit log"""
        import time
        try:
            await self.ensure_db()
            if self.db is not None:
                await self.db.execute('''
                    INSERT INTO whitelist_audit_log 
                    (guild_id, target_id, target_type, actor_id, action, permissions, reason, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (guild_id, target_id, target_type, actor_id, action, permissions, reason, int(time.time())))
                await self.db.commit()
        except Exception as e:
            print(f"Error logging whitelist action: {e}")

    @commands.command(name='whitelist', aliases=['wl'], help="Whitelists a user from antinuke for a specific action.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def whitelist(self, ctx, *, user_input: Optional[str] = None):
        # Debug: Log what we received
        print(f"DEBUG - Whitelist command called with user_input: {user_input}")
        print(f"DEBUG - Raw args: {ctx.message.content}")
        
        if ctx.guild.member_count < 2:
            embed = discord.Embed(
                color=0x006fb9,
                description="<:feast_cross:1400143488695144609> | Your Server Doesn't Meet My 30 Member Criteria"
            )
            return await ctx.send(embed=embed)

        prefix = ctx.prefix

        await self.ensure_db()
        if self.db is None:
            embed = discord.Embed(
                color=0xff0000,
                description="❌ Database connection failed. Please try again later."
            )
            return await ctx.send(embed=embed)
            
        async with self.db.execute(
            "SELECT owner_id FROM extraowners WHERE guild_id = ? AND owner_id = ?",
            (ctx.guild.id, ctx.author.id)
        ) as cursor:
            owner_check = await cursor.fetchone()

        async with self.db.execute(
            "SELECT status FROM antinuke WHERE guild_id = ?",
            (ctx.guild.id,)
        ) as cursor:
            antinuke = await cursor.fetchone()

        is_owner = ctx.author.id == ctx.guild.owner_id
        if not is_owner and not owner_check:
            embed = discord.Embed(title="<:feast_cross:1400143488695144609> Access Denied",
                color=0x006fb9,
                description="Only Server Owner or Extra Owner can Run this Command!"
            )
            return await ctx.send(embed=embed)

        if not antinuke or not antinuke[0]:
            embed = discord.Embed(
                color=0x006fb9,
                description=(
                    f"**{ctx.guild.name} Security Settings <:mod:1327845044182585407>\n"
                    "Ohh No! looks like your server doesn't enabled Antinuke\n\n"
                    "Current Status : <a:disabled1:1329022921427128321>\n\n"
                    f"To enable use `{prefix}antinuke enable` **"
                )
            )
            embed.set_thumbnail(url=ctx.bot.user.avatar.url)
            return await ctx.send(embed=embed)

        if not user_input:
            embed = discord.Embed(
                color=0x006fb9,
                title="__**Whitelist Commands**__",
                description="**Adding a user to the whitelist means that no actions will be taken against them if they trigger the Anti-Nuke Module.**"
            )
            embed.add_field(name="__**Usage**__", value=f"<:iconArrowRight:1327829310962401331> `{prefix}whitelist @user/id`\n<:iconArrowRight:1327829310962401331> `{prefix}wl @user`")
            embed.set_thumbnail(url=ctx.bot.user.avatar.url)
            return await ctx.send(embed=embed)

        # Check if user is trying to whitelist a role
        role = None
        member = None
        target_type = None
        target_id = None
        target_mention = None
        
        try:
            role_converter = commands.RoleConverter()
            role = await role_converter.convert(ctx, user_input.strip())
            target_type = "role"
            target_id = role.id
            target_mention = role.mention
        except commands.BadArgument:
            pass
        
        # If not a role, try to convert to member
        if not role:
            try:
                # Try direct member conversion
                member_converter = commands.MemberConverter()
                member = await member_converter.convert(ctx, user_input.strip())
                target_type = "user"
                target_id = member.id
                target_mention = member.mention
            except commands.BadArgument:
                try:
                    # Try user ID conversion - strip spaces and mention characters
                    user_id = int(user_input.strip().strip('<@!>'))
                    member = ctx.guild.get_member(user_id)
                    if member:
                        target_type = "user"
                        target_id = member.id
                        target_mention = member.mention
                except ValueError:
                    pass
        
        if not member and not role:
            embed = discord.Embed(
                color=0xff0000,
                title="❌ Member or Role Not Found",
                description=f"Could not find member or role: `{user_input}`\n\nPlease mention a valid member/role or use their ID."
            )
            return await ctx.send(embed=embed)

        await self.ensure_db()
        if self.db is None:
            embed = discord.Embed(title="❌ Database Error",
                color=0xff0000,
                description="Database connection failed. Please try again later."
            )
            return await ctx.send(embed=embed)
        
        # Check if already whitelisted based on type
        if target_type == "user":
            async with self.db.execute(
                "SELECT * FROM whitelisted_users WHERE guild_id = ? AND user_id = ?",
                (ctx.guild.id, target_id)
            ) as cursor:
                data = await cursor.fetchone()
        else:  # role
            async with self.db.execute(
                "SELECT * FROM whitelisted_roles WHERE guild_id = ? AND role_id = ?",
                (ctx.guild.id, target_id)
            ) as cursor:
                data = await cursor.fetchone()

        if data:
            entity_type = "member" if target_type == "user" else "role"
            embed = discord.Embed(title="<:feast_cross:1400143488695144609> Error",
                color=0x006fb9,
                description=f"{target_mention} is already a whitelisted {entity_type}, **Unwhitelist** them and try again."
            )
            return await ctx.send(embed=embed)

        # Insert into appropriate table
        if target_type == "user":
            await self.db.execute(
                "INSERT INTO whitelisted_users (guild_id, user_id) VALUES (?, ?)",
                (ctx.guild.id, target_id)
            )
        else:  # role
            await self.db.execute(
                "INSERT INTO whitelisted_roles (guild_id, role_id) VALUES (?, ?)",
                (ctx.guild.id, target_id)
            )
        await self.db.commit()
        
        # Log the whitelist add action (assert types for type checker)
        assert target_id is not None
        assert target_type is not None
        await self.log_whitelist_action(
            guild_id=ctx.guild.id,
            target_id=target_id,
            target_type=target_type,
            actor_id=ctx.author.id,
            action="add",
            reason=f"{target_type.title()} added to whitelist (permissions to be configured)"
        )

        options = [
            discord.SelectOption(label="Ban", description="Whitelist a member with ban permission", value="ban"),
            discord.SelectOption(label="Kick", description="Whitelist a member with kick permission", value="kick"),
            discord.SelectOption(label="Prune", description="Whitelist a member with prune permission", value="prune"),
            discord.SelectOption(label="Bot Add", description="Whitelist a member with bot add permission", value="botadd"),
            discord.SelectOption(label="Server Update", description="Whitelist a member with server update permission", value="serverup"),
            discord.SelectOption(label="Member Update", description="Whitelist a member with member update permission", value="memup"),
            discord.SelectOption(label="Channel Create", description="Whitelist a member with channel create permission", value="chcr"),
            discord.SelectOption(label="Channel Delete", description="Whitelist a member with channel delete permission", value="chdl"),
            discord.SelectOption(label="Channel Update", description="Whitelist a member with channel update permission", value="chup"),
            discord.SelectOption(label="Role Create", description="Whitelist a member with role create permission", value="rlcr"),
            discord.SelectOption(label="Role Update", description="Whitelist a member with role update permission", value="rlup"),
            discord.SelectOption(label="Role Delete", description="Whitelist a member with role delete permission", value="rldl"),
            discord.SelectOption(label="Mention Everyone", description="Whitelist a member with mention everyone permission", value="meneve"),
            discord.SelectOption(label="Manage Webhook", description="Whitelist a member with manage webhook permission", value="mngweb")
        ]

        select = discord.ui.Select(placeholder="Choose Your Options", min_values=1, max_values=len(options), options=options, custom_id="wl")
        button = discord.ui.Button(label="Add This User To All Categories", style=discord.ButtonStyle.primary, custom_id="catWl")

        view = discord.ui.View()
        view.add_item(select)
        view.add_item(button)

        embed = discord.Embed(
            title=ctx.guild.name,
            color=0x006fb9,
            description=(
                f"<:feast_cross:1400143488695144609><:feast_tick:1400143469892210753> : **Ban**\n"
                f"<:feast_cross:1400143488695144609><:feast_tick:1400143469892210753> : **Kick**\n"
                f"<:feast_cross:1400143488695144609><:feast_tick:1400143469892210753> : **Prune**\n"
                f"<:feast_cross:1400143488695144609><:feast_tick:1400143469892210753> : **Bot Add**\n"
                f"<:feast_cross:1400143488695144609><:feast_tick:1400143469892210753> : **Server Update**\n"
                f"<:feast_cross:1400143488695144609><:feast_tick:1400143469892210753> : **Member Update**\n"
                f"<:feast_cross:1400143488695144609><:feast_tick:1400143469892210753> : **Channel Create**\n"
                f"<:feast_cross:1400143488695144609><:feast_tick:1400143469892210753> : **Channel Delete**\n"
                f"<:feast_cross:1400143488695144609><:feast_tick:1400143469892210753>: **Channel Update**\n"
                f"<:feast_cross:1400143488695144609><:feast_tick:1400143469892210753> : **Role Create**\n"
                f"<:feast_cross:1400143488695144609><:feast_tick:1400143469892210753> : **Role Delete**\n"
                f"<:feast_cross:1400143488695144609><:feast_tick:1400143469892210753> : **Role Update**\n"
                f"<:feast_cross:1400143488695144609><:feast_tick:1400143469892210753> : **Mention** @everyone\n"
                f"<:feast_cross:1400143488695144609><:feast_tick:1400143469892210753> : **Webhook Management**"
                
            )
        )
        embed.add_field(name="**Executor**", value=f"<@!{ctx.author.id}>", inline=True)
        embed.add_field(name="**Target**", value=target_mention, inline=True)
        embed.set_thumbnail(url=self.bot.user.avatar.url)
        embed.set_footer(text=f"Developed by Sleepless  Development™")

        msg = await ctx.send(embed=embed, view=view)

        def check(interaction):
            return interaction.user.id == ctx.author.id and interaction.message.id == msg.id

        try:
            interaction = await self.bot.wait_for("interaction", check=check, timeout=60.0)
            if interaction.data["custom_id"] == "catWl":
                
                await self.ensure_db()
                if self.db is not None:
                    if target_type == "user":
                        await self.db.execute(
                            "UPDATE whitelisted_users SET ban = ?, kick = ?, prune = ?, botadd = ?, serverup = ?, memup = ?, chcr = ?, chdl = ?, chup = ?, rlcr = ?, rldl = ?, rlup = ?, meneve = ?, mngweb = ?, mngstemo = ? WHERE guild_id = ? AND user_id = ?",
                            (True, True, True, True, True, True, True, True, True, True, True, True, True, True, True, ctx.guild.id, target_id)
                        )
                    else:  # role
                        await self.db.execute(
                            "UPDATE whitelisted_roles SET ban = ?, kick = ?, prune = ?, botadd = ?, serverup = ?, memup = ?, chcr = ?, chdl = ?, chup = ?, rlcr = ?, rldl = ?, rlup = ?, meneve = ?, mngweb = ?, mngstemo = ? WHERE guild_id = ? AND role_id = ?",
                            (True, True, True, True, True, True, True, True, True, True, True, True, True, True, True, ctx.guild.id, target_id)
                        )
                    await self.db.commit()

                
                embed = discord.Embed(
                    title=ctx.guild.name,
                    color=0x006fb9,
                    description=(
                         f"<:feast_cross:1400143488695144609><:feast_tick:1400143469892210753> : **Ban**\n"
                f"<:feast_cross:1400143488695144609><:feast_tick:1400143469892210753> : **Kick**\n"
                f"<:feast_cross:1400143488695144609><:feast_tick:1400143469892210753> : **Prune**\n"
                f"<:feast_cross:1400143488695144609><:feast_tick:1400143469892210753> : **Bot Add**\n"
                f"<:feast_cross:1400143488695144609><:feast_tick:1400143469892210753> : **Server Update**\n"
                f"<:feast_cross:1400143488695144609><:feast_tick:1400143469892210753> : **Member Update**\n"
                f"<:feast_cross:1400143488695144609><:feast_tick:1400143469892210753> : **Channel Create**\n"
                f"<:feast_cross:1400143488695144609><:feast_tick:1400143469892210753> : **Channel Delete**\n"
                f"<:feast_cross:1400143488695144609><:feast_tick:1400143469892210753>: **Channel Update**\n"
                f"<:feast_cross:1400143488695144609><:feast_tick:1400143469892210753> : **Role Create**\n"
                f"<:feast_cross:1400143488695144609><:feast_tick:1400143469892210753> : **Role Delete**\n"
                f"<:feast_cross:1400143488695144609><:feast_tick:1400143469892210753> : **Role Update**\n"
                f"<:feast_cross:1400143488695144609><:feast_tick:1400143469892210753> : **Mention** @everyone\n"
                f"<:feast_cross:1400143488695144609><:feast_tick:1400143469892210753> : **Webhook Management**"
                    )
                )
                embed.add_field(name="**Executor**", value=f"<@!{ctx.author.id}>", inline=True)
                embed.add_field(name="**Target**", value=target_mention, inline=True)
                embed.set_thumbnail(url=self.bot.user.avatar.url)
                embed.set_footer(text=f"Developed by Sleepless  Development™")

                await interaction.response.edit_message(embed=embed, view=None)
            else:
                
                fields = {
                    'ban': 'Ban',
                    'kick': 'Kick',
                    'prune': 'Prune',
                    'botadd': 'Bot Add',
                    'serverup': 'Server Update',
                    'memup': 'Member Update',
                    'chcr': 'Channel Create',
                    'chdl': 'Channel Delete',
                    'chup': 'Channel Update',
                    'rlcr': 'Role Create',
                    'rldl': 'Role Delete',
                    'rlup': 'Role Update',
                    'meneve': 'Mention Everyone',
                    'mngweb': 'Manage Webhooks'
                }

                
                embed_description = "\n".join(f"<:feast_cross:1400143488695144609><:feast_tick:1400143469892210753> : **{name}**" for key, name in fields.items())

                await self.ensure_db()
                if self.db is not None:
                    table_name = "whitelisted_users" if target_type == "user" else "whitelisted_roles"
                    id_column = "user_id" if target_type == "user" else "role_id"
                    
                    for value in interaction.data["values"]:
                        await self.db.execute(
                            f"UPDATE {table_name} SET {value} = ? WHERE guild_id = ? AND {id_column} = ?",
                            (True, ctx.guild.id, target_id)
                        )
                        embed_description = embed_description.replace(f"<:feast_cross:1400143488695144609><:feast_tick:1400143469892210753> : **{fields[value]}**", f"<:feast_cross:1400143488695144609><:feast_tick:1400143469892210753> : **{fields[value]}**")

                    await self.db.commit()

                
                embed = discord.Embed(
                    title=ctx.guild.name,
                    color=0x006fb9,
                    description=embed_description
                )
                embed.add_field(name="**Executor**", value=f"<@!{ctx.author.id}>", inline=True)
                embed.add_field(name="**Target**", value=target_mention, inline=True)
                embed.set_thumbnail(url=self.bot.user.avatar.url)
                embed.set_footer(text=f"Developed by Sleepless  Development™")

                await interaction.response.edit_message(embed=embed, view=None)
        except TimeoutError:
            await msg.edit(view=None)


    @commands.command(name='whitelisted', aliases=['wlist'], help="Shows the list of whitelisted users.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def whitelisted(self, ctx):
        if ctx.guild.member_count < 2:
            embed = discord.Embed(
                color=0x006fb9,
                description="<:feast_cross:1400143488695144609> | Your Server Doesn't Meet My 30 Member Criteria"
            )
            return await ctx.send(embed=embed)

        pre=ctx.prefix

        await self.ensure_db()
        if self.db is None:
            embed = discord.Embed(
                color=0xff0000,
                description="❌ Database connection failed. Please try again later."
            )
            return await ctx.send(embed=embed)
            
        async with self.db.execute(
            "SELECT owner_id FROM extraowners WHERE guild_id = ? AND owner_id = ?",
            (ctx.guild.id, ctx.author.id)
        ) as cursor:
            check = await cursor.fetchone()

        async with self.db.execute(
            "SELECT status FROM antinuke WHERE guild_id = ?",
            (ctx.guild.id,)
        ) as cursor:
            antinuke = await cursor.fetchone()

        is_owner = ctx.author.id == ctx.guild.owner_id
        if not is_owner and not check:
            embed = discord.Embed(title="<:feast_cross:1400143488695144609> Access Denied",
                color=0x006fb9,
                description="Only Server Owner or Extra Owner can Run this Command!"
            )
            return await ctx.send(embed=embed)

        if not antinuke or not antinuke[0]:
            embed = discord.Embed(
                color=0x006fb9,
                description=(
                    f"**{ctx.guild.name} security settings <:mod:1327845044182585407>\n"
                    "Ohh NO! looks like your server doesn't enabled security\n\n"
                    "Current Status : <a:disabled1:1329022921427128321>\n\n"
                    f"To enable use `{pre}antinuke enable` **"
                )
            )
            return await ctx.send(embed=embed)


        async with self.db.execute(
            "SELECT user_id FROM whitelisted_users WHERE guild_id = ?",
            (ctx.guild.id,)
        ) as cursor:
            data = await cursor.fetchall()

        if not data:
            embed = discord.Embed(title="<:feast_cross:1400143488695144609> Error",
                color=0x006fb9,
                description="No whitelisted users found."
            )
            return await ctx.send(embed=embed)

        whitelisted_users = [self.bot.get_user(user_id[0]) for user_id in data]
        whitelisted_users_str = ", ".join(f"<@!{user.id}>" for user in whitelisted_users if user)

        embed = discord.Embed(
            color=0x006fb9,
            title=f"__Whitelisted Users for {ctx.guild.name}__",
            description=whitelisted_users_str
        )
        await ctx.send(embed=embed)


    @commands.command(name="whitelistreset", aliases=['wlreset'], help="Resets the whitelisted users.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def whitelistreset(self, ctx):
        if ctx.guild.member_count < 2:
            embed = discord.Embed(
                color=0x006fb9,
                description="<:feast_cross:1400143488695144609> | Your Server Doesn't Meet My 30 Member Criteria"
            )
            return await ctx.send(embed=embed)

        pre=ctx.prefix

        await self.ensure_db()
        if self.db is None:
            embed = discord.Embed(
                color=0xff0000,
                description="❌ Database connection failed. Please try again later."
            )
            return await ctx.send(embed=embed)
            
        async with self.db.execute(
            "SELECT owner_id FROM extraowners WHERE guild_id = ? AND owner_id = ?",
            (ctx.guild.id, ctx.author.id)
        ) as cursor:
            check = await cursor.fetchone()

        async with self.db.execute(
            "SELECT status FROM antinuke WHERE guild_id = ?",
            (ctx.guild.id,)
        ) as cursor:
            antinuke = await cursor.fetchone()

        is_owner = ctx.author.id == ctx.guild.owner_id
        if not is_owner and not check:
            embed = discord.Embed(title="<:feast_cross:1400143488695144609> Access Denied",
                color=0x006fb9,
                description="Only Server Owner or Extra Owner can Run this Command!"
            )
            return await ctx.send(embed=embed)

        if not antinuke or not antinuke[0]:
            embed = discord.Embed(
                color=0x006fb9,
                description=(
                    f"**{ctx.guild.name} Security Settings <:mod:1327845044182585407>\n"
                    "Ohh NO! looks like your server doesn't enabled security\n\n"
                    "Current Status : <a:disabled1:1329022921427128321>\n\n"
                    f"To enable use `{pre}antinuke enable` **"
                )
            )
            return await ctx.send(embed=embed)

        await self.ensure_db()
        async with self.db.execute(
            "SELECT user_id FROM whitelisted_users WHERE guild_id = ?",
            (ctx.guild.id,)
        ) as cursor:
            data = await cursor.fetchall()


        if not data:
            embed = discord.Embed(title="<:feast_cross:1400143488695144609> Error",
                color=0x006fb9,
                description="No whitelisted users found."
            )
            return await ctx.send(embed=embed)

        await self.ensure_db()
        if self.db is not None:
            await self.db.execute("DELETE FROM whitelisted_users WHERE guild_id = ?", (ctx.guild.id,))
            await self.db.commit()
        embed = discord.Embed(title="<:feast_tick:1400143469892210753> Success",
            color=0x006fb9,
            description=f"Removed all whitelisted members from {ctx.guild.name}"
        )
        await ctx.send(embed=embed)


    @commands.command(name="whitelistinfo", aliases=['wlinfo', 'wldetails'], help="Show detailed whitelist permissions for users")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def whitelistinfo(self, ctx, user: Optional[discord.Member] = None):
        """Show detailed whitelist information with all permissions"""
        if ctx.guild.member_count < 2:
            embed = discord.Embed(
                color=0x006fb9,
                description="<:feast_cross:1400143488695144609> | Your Server Doesn't Meet My 30 Member Criteria"
            )
            return await ctx.send(embed=embed)

        pre = ctx.prefix

        await self.ensure_db()
        if self.db is None:
            embed = discord.Embed(
                color=0xff0000,
                description="❌ Database connection failed. Please try again later."
            )
            return await ctx.send(embed=embed)

        # Check permissions
        async with self.db.execute(
            "SELECT owner_id FROM extraowners WHERE guild_id = ? AND owner_id = ?",
            (ctx.guild.id, ctx.author.id)
        ) as cursor:
            check = await cursor.fetchone()

        is_owner = ctx.author.id == ctx.guild.owner_id
        if not is_owner and not check:
            embed = discord.Embed(
                title="<:feast_cross:1400143488695144609> Access Denied",
                color=0x006fb9,
                description="Only Server Owner or Extra Owner can view whitelist details!"
            )
            return await ctx.send(embed=embed)

        # Check if antinuke is enabled
        async with self.db.execute(
            "SELECT status FROM antinuke WHERE guild_id = ?",
            (ctx.guild.id,)
        ) as cursor:
            antinuke = await cursor.fetchone()

        if not antinuke or not antinuke[0]:
            embed = discord.Embed(
                color=0x006fb9,
                description=(
                    f"**{ctx.guild.name} security settings <:mod:1327845044182585407>**\n"
                    "Ohh NO! looks like your server doesn't enabled security\n\n"
                    "Current Status : <a:disabled1:1329022921427128321>\n\n"
                    f"To enable use `{pre}antinuke enable`"
                )
            )
            return await ctx.send(embed=embed)

        # Permission mapping
        perm_map = {
            'ban': 'Ban Members',
            'kick': 'Kick Members',
            'prune': 'Member Prune',
            'botadd': 'Bot Add',
            'serverup': 'Server Update',
            'memup': 'Member Update',
            'chcr': 'Channel Create',
            'chdl': 'Channel Delete',
            'chup': 'Channel Update',
            'rlcr': 'Role Create',
            'rldl': 'Role Delete',
            'rlup': 'Role Update',
            'meneve': 'Mention Everyone',
            'mngweb': 'Manage Webhooks',
            'mngstemo': 'Manage Emojis/Stickers'
        }

        if user:
            # Show specific user's permissions
            async with self.db.execute(
                "SELECT * FROM whitelisted_users WHERE guild_id = ? AND user_id = ?",
                (ctx.guild.id, user.id)
            ) as cursor:
                data = await cursor.fetchone()

            if not data:
                embed = discord.Embed(
                    title="<:feast_cross:1400143488695144609> Not Whitelisted",
                    color=0x006fb9,
                    description=f"{user.mention} is not whitelisted for any actions."
                )
                return await ctx.send(embed=embed)

            # Parse permissions (skip guild_id and user_id columns)
            columns = ['guild_id', 'user_id'] + list(perm_map.keys())
            permissions = dict(zip(columns, data))

            # Build permission list
            enabled_perms = []
            disabled_perms = []
            
            for key, name in perm_map.items():
                if permissions.get(key):
                    enabled_perms.append(f"<a:enabled_:1329022799708160063> {name}")
                else:
                    disabled_perms.append(f"<a:disabled1:1329022921427128321> {name}")

            embed = discord.Embed(
                title=f"<:feast_settings:1400425884980088874> Whitelist Details: {user.display_name}",
                description=f"**User:** {user.mention}\n**ID:** `{user.id}`",
                color=0x006fb9
            )

            if enabled_perms:
                embed.add_field(
                    name="__**Enabled Permissions**__",
                    value="\n".join(enabled_perms),
                    inline=False
                )

            if disabled_perms:
                embed.add_field(
                    name="__**Disabled Permissions**__",
                    value="\n".join(disabled_perms[:10]) + (f"\n*... and {len(disabled_perms) - 10} more*" if len(disabled_perms) > 10 else ""),
                    inline=False
                )

            embed.set_thumbnail(url=user.display_avatar.url)
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
            await ctx.send(embed=embed)

        else:
            # Show all whitelisted users with summary
            async with self.db.execute(
                "SELECT * FROM whitelisted_users WHERE guild_id = ?",
                (ctx.guild.id,)
            ) as cursor:
                rows = await cursor.fetchall()
                all_data = list(rows) if rows else []

            if not all_data:
                embed = discord.Embed(
                    title="<:feast_cross:1400143488695144609> No Whitelisted Users",
                    color=0x006fb9,
                    description=f"No users are whitelisted in {ctx.guild.name}.\n\nUse `{pre}whitelist add @user` to whitelist someone."
                )
                return await ctx.send(embed=embed)

            # Build summary for all users
            embed = discord.Embed(
                title=f"<:feast_settings:1400425884980088874> Whitelisted Users in {ctx.guild.name}",
                description=f"**Total Whitelisted:** {len(all_data)} users\n\nUse `{pre}wlinfo @user` for detailed permissions",
                color=0x006fb9
            )

            columns = ['guild_id', 'user_id'] + list(perm_map.keys())
            
            # Show up to 15 users
            for idx, row in enumerate(all_data[:15]):
                permissions = dict(zip(columns, row))
                user_id = permissions['user_id']
                member = ctx.guild.get_member(user_id) or await self.bot.fetch_user(user_id)
                
                # Count enabled permissions
                enabled_count = sum(1 for key in perm_map.keys() if permissions.get(key))
                total_perms = len(perm_map)
                
                # Get top 3 enabled permissions
                top_perms = [perm_map[key] for key in perm_map.keys() if permissions.get(key)][:3]
                perms_str = ", ".join(top_perms) if top_perms else "None"
                if len(top_perms) < enabled_count:
                    perms_str += f" +{enabled_count - len(top_perms)} more"

                embed.add_field(
                    name=f"{idx + 1}. {member.display_name if member else 'Unknown User'}",
                    value=f"**Permissions:** {enabled_count}/{total_perms}\n**Top:** {perms_str}",
                    inline=True
                )

            if len(all_data) > 15:
                embed.set_footer(text=f"Showing 15 of {len(all_data)} whitelisted users • Requested by {ctx.author}")
            else:
                embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)

            embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else self.bot.user.avatar.url)
            await ctx.send(embed=embed)

    # ============================================================================
    # ROLE-BASED WHITELIST COMMANDS
    # ============================================================================

    @commands.command(name="whitelistrole", aliases=['wlrole'], help="Whitelist an entire role for antinuke actions")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def whitelistrole(self, ctx, role: Optional[discord.Role] = None, *, permissions: Optional[str] = None):
        """
        Whitelist a role for specific antinuke permissions.
        All members with this role will be whitelisted for specified actions.
        
        Usage: 
        $whitelistrole @Admin ban kick
        $whitelistrole @Moderator all
        """
        if ctx.guild.member_count < 2:
            embed = discord.Embed(
                color=0x006fb9,
                description="<:feast_cross:1400143488695144609> | Your Server Doesn't Meet My 30 Member Criteria"
            )
            return await ctx.send(embed=embed)

        pre = ctx.prefix

        if not role:
            embed = discord.Embed(
                color=0x006fb9,
                description=(
                    f"**Role Whitelist System**\n\n"
                    f"**Usage:** `{pre}whitelistrole <role> <permissions>`\n\n"
                    f"**Example:**\n"
                    f"`{pre}whitelistrole @Admin all` - All permissions\n"
                    f"`{pre}whitelistrole @Mod ban kick` - Specific permissions\n\n"
                    f"**Available Permissions:**\n"
                    f"`all`, `ban`, `kick`, `prune`, `botadd`, `serverup`, `memup`,\n"
                    f"`chcr`, `chdl`, `chup`, `rlcr`, `rldl`, `rlup`,\n"
                    f"`meneve`, `mngweb`, `mngstemo`"
                )
            )
            return await ctx.send(embed=embed)

        if not permissions:
            embed = discord.Embed(
                color=0x006fb9,
                description=f"<:feast_cross:1400143488695144609> Please specify permissions to whitelist.\n\nExample: `{pre}whitelistrole @{role.name} all`"
            )
            return await ctx.send(embed=embed)

        # Check ownership
        await self.ensure_db()
        assert self.db is not None
        async with self.db.execute(
            "SELECT owner_id, extraownerallow FROM antinuke WHERE guild_id = ?",
            (ctx.guild.id,)
        ) as cursor:
            data = await cursor.fetchone()

        if not data:
            embed = discord.Embed(
                color=0x006fb9,
                description=(
                    f"**{ctx.guild.name} Security Settings <:mod:1327845044182585407>\n"
                    "Ohh NO! looks like your server doesn't enabled security\n\n"
                    "Current Status : <a:disabled1:1329022921427128321>\n\n"
                    f"To enable use `{pre}antinuke enable`**"
                )
            )
            return await ctx.send(embed=embed)

        owner_id = data[0]
        extraownerallow = data[1] if len(data) > 1 else 0

        is_owner = ctx.author.id == ctx.guild.owner_id or ctx.author.id == owner_id
        is_extra_owner = extraownerallow and ctx.author.id in [
            int(x) for x in str(extraownerallow).split(",") if x.isdigit()
        ]

        if not (is_owner or is_extra_owner):
            embed = discord.Embed(
                color=0x006fb9,
                description="Only Server Owner or Extra Owner can Run this Command!"
            )
            return await ctx.send(embed=embed)

        # Parse permissions
        perm_list = [p.lower().strip() for p in permissions.split()]
        valid_perms = ['ban', 'kick', 'prune', 'botadd', 'serverup', 'memup', 
                      'chcr', 'chdl', 'chup', 'rlcr', 'rldl', 'rlup', 
                      'meneve', 'mngweb', 'mngstemo']
        
        if 'all' in perm_list:
            perms_to_set = {p: True for p in valid_perms}
            perm_display = "All Permissions"
        else:
            perms_to_set = {p: (p in perm_list) for p in valid_perms}
            invalid = [p for p in perm_list if p not in valid_perms and p != 'all']
            if invalid:
                embed = discord.Embed(
                    color=0x006fb9,
                    description=f"<:feast_cross:1400143488695144609> Invalid permissions: {', '.join(invalid)}"
                )
                return await ctx.send(embed=embed)
            perm_display = ", ".join([p.upper() for p in perm_list])

        # Insert or update role whitelist
        assert self.db is not None
        columns = ", ".join(valid_perms)
        placeholders = ", ".join(["?" for _ in valid_perms])
        values = [perms_to_set[p] for p in valid_perms]

        await self.db.execute(
            f"""
            INSERT INTO whitelisted_roles (guild_id, role_id, {columns})
            VALUES (?, ?, {placeholders})
            ON CONFLICT(guild_id, role_id) DO UPDATE SET
            {', '.join([f"{p}=excluded.{p}" for p in valid_perms])}
            """,
            (ctx.guild.id, role.id, *values)
        )
        await self.db.commit()

        # Log the whitelist action
        await self.log_whitelist_action(
            guild_id=ctx.guild.id,
            target_id=role.id,
            target_type="role",
            actor_id=ctx.author.id,
            action="add",
            permissions=perm_display,
            reason=f"Role whitelisted with permissions: {perm_display}"
        )

        # Count members with this role
        member_count = len(role.members)

        embed = discord.Embed(
            title="<:feast_tick:1400143469892210753> Role Whitelisted",
            color=0x006fb9,
            description=(
                f"**Role:** {role.mention}\n"
                f"**Members Affected:** {member_count}\n"
                f"**Permissions:** {perm_display}\n\n"
                f"All members with this role now have these antinuke permissions."
            )
        )
        embed.set_footer(text=f"Added by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name="unwhitelistrole", aliases=['unwlrole'], help="Remove role from whitelist")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def unwhitelistrole(self, ctx, role: Optional[discord.Role] = None):
        """Remove a role from the whitelist"""
        if ctx.guild.member_count < 2:
            embed = discord.Embed(
                color=0x006fb9,
                description="<:feast_cross:1400143488695144609> | Your Server Doesn't Meet My 30 Member Criteria"
            )
            return await ctx.send(embed=embed)

        pre = ctx.prefix

        if not role:
            embed = discord.Embed(
                color=0x006fb9,
                description=f"**Usage:** `{pre}unwhitelistrole <role>`\n\nRemoves a role from the antinuke whitelist."
            )
            return await ctx.send(embed=embed)

        # Check ownership
        await self.ensure_db()
        assert self.db is not None
        async with self.db.execute(
            "SELECT owner_id, extraownerallow FROM antinuke WHERE guild_id = ?",
            (ctx.guild.id,)
        ) as cursor:
            data = await cursor.fetchone()

        if not data:
            embed = discord.Embed(
                color=0x006fb9,
                description=(
                    f"**{ctx.guild.name} Security Settings <:mod:1327845044182585407>\n"
                    "Ohh NO! looks like your server doesn't enabled security\n\n"
                    "Current Status : <a:disabled1:1329022921427128321>\n\n"
                    f"To enable use `{pre}antinuke enable`**"
                )
            )
            return await ctx.send(embed=embed)

        owner_id = data[0]
        extraownerallow = data[1] if len(data) > 1 else 0

        is_owner = ctx.author.id == ctx.guild.owner_id or ctx.author.id == owner_id
        is_extra_owner = extraownerallow and ctx.author.id in [
            int(x) for x in str(extraownerallow).split(",") if x.isdigit()
        ]

        if not (is_owner or is_extra_owner):
            embed = discord.Embed(
                color=0x006fb9,
                description="Only Server Owner or Extra Owner can Run this Command!"
            )
            return await ctx.send(embed=embed)

        # Check if role is whitelisted
        async with self.db.execute(
            "SELECT * FROM whitelisted_roles WHERE guild_id = ? AND role_id = ?",
            (ctx.guild.id, role.id)
        ) as cursor:
            role_data = await cursor.fetchone()

        if not role_data:
            embed = discord.Embed(
                color=0x006fb9,
                description=f"<:feast_cross:1400143488695144609> {role.mention} is not whitelisted."
            )
            return await ctx.send(embed=embed)

        # Remove role from whitelist
        await self.db.execute(
            "DELETE FROM whitelisted_roles WHERE guild_id = ? AND role_id = ?",
            (ctx.guild.id, role.id)
        )
        await self.db.commit()

        # Log the whitelist action
        await self.log_whitelist_action(
            guild_id=ctx.guild.id,
            target_id=role.id,
            target_type="role",
            actor_id=ctx.author.id,
            action="remove",
            reason="Role removed from whitelist"
        )

        embed = discord.Embed(
            title="<:feast_tick:1400143469892210753> Role Removed",
            color=0x006fb9,
            description=f"**{role.mention}** has been removed from the whitelist."
        )
        embed.set_footer(text=f"Removed by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name="whitelistroles", aliases=['wlroles'], help="List all whitelisted roles")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def whitelistroles(self, ctx):
        """Show all whitelisted roles with their permissions"""
        if ctx.guild.member_count < 2:
            embed = discord.Embed(
                color=0x006fb9,
                description="<:feast_cross:1400143488695144609> | Your Server Doesn't Meet My 30 Member Criteria"
            )
            return await ctx.send(embed=embed)

        await self.ensure_db()
        assert self.db is not None
        
        # Get all whitelisted roles
        async with self.db.execute(
            "SELECT * FROM whitelisted_roles WHERE guild_id = ?",
            (ctx.guild.id,)
        ) as cursor:
            rows = await cursor.fetchall()
            roles_data = list(rows) if rows else []

        if not roles_data:
            embed = discord.Embed(
                color=0x006fb9,
                description="<:feast_cross:1400143488695144609> No roles are currently whitelisted."
            )
            return await ctx.send(embed=embed)

        perm_map = {
            'ban': 'Ban Members', 'kick': 'Kick Members', 'prune': 'Prune Members',
            'botadd': 'Add Bots', 'serverup': 'Server Update', 'memup': 'Member Update',
            'chcr': 'Channel Create', 'chdl': 'Channel Delete', 'chup': 'Channel Update',
            'rlcr': 'Role Create', 'rldl': 'Role Delete', 'rlup': 'Role Update',
            'meneve': 'Mention Everyone', 'mngweb': 'Manage Webhooks', 'mngstemo': 'Manage Emojis/Stickers'
        }

        embed = discord.Embed(
            title=f"🛡️ Whitelisted Roles - {ctx.guild.name}",
            color=0x006fb9,
            description=f"**Total Whitelisted Roles:** {len(roles_data)}\n"
        )

        for role_entry in roles_data[:10]:  # Show first 10 roles
            role_id = role_entry[1]
            role = ctx.guild.get_role(role_id)
            
            if not role:
                continue  # Skip deleted roles

            # Extract permissions from database row
            permissions = {
                'ban': role_entry[2], 'kick': role_entry[3], 'prune': role_entry[4],
                'botadd': role_entry[5], 'serverup': role_entry[6], 'memup': role_entry[7],
                'chcr': role_entry[8], 'chdl': role_entry[9], 'chup': role_entry[10],
                'rlcr': role_entry[11], 'rlup': role_entry[12], 'rldl': role_entry[13],
                'meneve': role_entry[14], 'mngweb': role_entry[15], 'mngstemo': role_entry[16]
            }

            enabled_count = sum(1 for val in permissions.values() if val)
            total_perms = len(permissions)
            
            # Get top 3 enabled permissions
            top_perms = [perm_map[key] for key, val in permissions.items() if val][:3]
            perms_str = ", ".join(top_perms) if top_perms else "None"
            if len(top_perms) < enabled_count:
                perms_str += f" +{enabled_count - len(top_perms)} more"

            embed.add_field(
                name=f"{role.name}",
                value=f"**Members:** {len(role.members)}\n**Permissions:** {enabled_count}/{total_perms}\n**Top:** {perms_str}",
                inline=False
            )

        if len(roles_data) > 10:
            embed.set_footer(text=f"Showing 10 of {len(roles_data)} whitelisted roles • Requested by {ctx.author}")
        else:
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)

        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else self.bot.user.avatar.url)
        await ctx.send(embed=embed)


    @commands.command(name="whitelisthistory", aliases=['wlhistory', 'wlaudit'], help="View whitelist audit history")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def whitelist_history(self, ctx, target: Optional[discord.Member] = None, limit: int = 10):
        """View whitelist audit log history"""
        await self.ensure_db()
        if self.db is None:
            return await ctx.send(embed=discord.Embed(
                title="❌ Database Error",
                description="Database connection failed. Please try again later.",
                color=0xFF0000
            ))
        
        # Check permissions
        async with self.db.execute(
            "SELECT owner_id FROM extraowners WHERE guild_id = ? AND owner_id = ?",
            (ctx.guild.id, ctx.author.id)
        ) as cursor:
            owner_check = await cursor.fetchone()

        is_owner = ctx.author.id == ctx.guild.owner_id
        if not is_owner and not owner_check:
            return await ctx.send(embed=discord.Embed(
                title="<:feast_cross:1400143488695144609> Access Denied",
                color=0x006fb9,
                description="Only Server Owner or Extra Owner can view whitelist history!"
            ))
        
        # Build query based on target filter
        if target:
            query = '''
                SELECT target_id, target_type, actor_id, action, permissions, reason, timestamp
                FROM whitelist_audit_log
                WHERE guild_id = ? AND target_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            '''
            params = (ctx.guild.id, target.id, limit)
        else:
            query = '''
                SELECT target_id, target_type, actor_id, action, permissions, reason, timestamp
                FROM whitelist_audit_log
                WHERE guild_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            '''
            params = (ctx.guild.id, limit)
        
        async with self.db.execute(query, params) as cursor:
            logs = await cursor.fetchall()
        
        # Convert to list to use len() and index()
        logs_list = list(logs) if logs else []
        
        if not logs_list:
            return await ctx.send(embed=discord.Embed(
                title="📋 Whitelist Audit Log",
                description="No whitelist history found." + (f" for {target.mention}" if target else ""),
                color=0x006fb9
            ))
        
        embed = discord.Embed(
            title=f"📋 Whitelist Audit Log - {ctx.guild.name}",
            description=f"**Total Entries:** {len(logs_list)}" + (f"\n**Filtered by:** {target.mention}" if target else ""),
            color=0x006fb9
        )
        
        for log_entry in logs_list:
            target_id, target_type, actor_id, action, permissions, reason, timestamp = log_entry
            
            # Get user/role objects
            if target_type == "user":
                target_obj = ctx.guild.get_member(target_id) or await self.bot.fetch_user(target_id)
                target_mention = target_obj.mention if target_obj else f"User ID: {target_id}"
            else:
                target_obj = ctx.guild.get_role(target_id)
                target_mention = target_obj.mention if target_obj else f"Role ID: {target_id}"
            
            actor = ctx.guild.get_member(actor_id) or await self.bot.fetch_user(actor_id)
            actor_mention = actor.mention if actor else f"User ID: {actor_id}"
            
            # Format action emoji
            action_emoji = "➕" if action == "add" else "➖"
            
            # Format timestamp
            time_str = discord.utils.format_dt(discord.utils.utcnow().replace(second=timestamp % 60), style='R')
            
            field_value = f"{action_emoji} **Action:** {action.title()}\n"
            field_value += f"👤 **Actor:** {actor_mention}\n"
            field_value += f"🎯 **Target:** {target_mention} ({target_type})\n"
            if permissions:
                field_value += f"🔑 **Permissions:** {permissions}\n"
            if reason:
                field_value += f"📝 **Reason:** {reason}\n"
            field_value += f"⏰ **Time:** {time_str}"
            
            embed.add_field(
                name=f"Entry #{logs_list.index(log_entry) + 1}",
                value=field_value,
                inline=False
            )
        
        embed.set_footer(text=f"Requested by {ctx.author} • Showing {len(logs_list)} of last {limit} entries")
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else self.bot.user.avatar.url)
        
        await ctx.send(embed=embed)


"""
@Author: Frosty
    + Discord: frosty.pyro
    + Community: https://discord.gg/5wtjDkYbVh (Sleepless Development)
    + for any queries reach out in the server; or send a dm.
"""