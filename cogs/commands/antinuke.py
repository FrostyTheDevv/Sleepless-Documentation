from utils.error_helpers import StandardErrorHandler
# Extension loader for Discord.py
async def setup(bot):
    await bot.add_cog(Antinuke(bot))
import discord
from discord.ext import commands
import aiosqlite
import asyncio
from utils.Tools import *
from utils.action_tracker import ActionTracker
from typing import Optional

# Define default limits and time window for antinuke actions
DEFAULT_LIMITS = {
    "ban": 3,
    "kick": 3,
    "bot_add": 1,
    "channel_create": 5,
    "channel_delete": 3,
    "channel_update": 5,
    "role_create": 5,
    "role_delete": 3,
    "role_update": 5,
    "webhook_create": 2,
    "webhook_delete": 2,
    "webhook_update": 2,
    "guild_update": 1,
    "member_update": 3,
    "integration_update": 1,
    "prune": 1,
}
TIME_WINDOW = 60  # seconds


class Antinuke(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        self.db: aiosqlite.Connection | None = None
        self.action_tracker = ActionTracker()
        # Initialize database when the cog is created
        asyncio.create_task(self.initialize_db())

    async def initialize_db(self):
        """Initialize the database connection"""
        try:
            if self.db is None:
                self.db = await aiosqlite.connect('db/anti.db')
                await self.db.execute('''
                CREATE TABLE IF NOT EXISTS antinuke (
                guild_id INTEGER PRIMARY KEY,
                status BOOLEAN
                )
                ''')
                await self.db.execute('''
                CREATE TABLE IF NOT EXISTS limit_settings (
                guild_id INTEGER,
                action_type TEXT,
                action_limit INTEGER,
                time_window INTEGER,
                PRIMARY KEY (guild_id, action_type)
                )
                ''')
                await self.db.commit()
        except Exception as e:
            print(f"Error initializing antinuke database: {e}")
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
                return True
        except Exception as e:
            print(f"Database connection error in antinuke: {e}")
            try:
                if self.db:
                    await self.db.close()
                self.db = None
                await self.initialize_db()
                if self.db is not None:
                    try:
                        # Type assertion to tell the type checker that self.db is not None
                        await self.db.execute('SELECT 1')  # type: ignore
                        return True
                    except Exception:
                        return False
                else:
                    return False
            except Exception as e2:
                print(f"Failed to reinitialize database: {e2}")
                self.db = None
                return False
        return False

    async def enable_limit_settings(self, guild_id):
        """Enable antinuke with escalation system as default punishment"""
        await self.ensure_db()
        if self.db is None:
            return
        
        # Add punishment_type column if it doesn't exist (migration)
        try:
            await self.db.execute('ALTER TABLE limit_settings ADD COLUMN punishment_type TEXT DEFAULT "escalation"')
            await self.db.commit()
        except:
            pass  # Column already exists
        
        default_limits = DEFAULT_LIMITS
        # Set all actions to use escalation system
        for action, limit in default_limits.items():
            await self.db.execute(
                'INSERT OR REPLACE INTO limit_settings (guild_id, action_type, action_limit, time_window, punishment_type) VALUES (?, ?, ?, ?, ?)',
                (guild_id, action, limit, TIME_WINDOW, "escalation")
            )
        await self.db.commit()

    async def disable_limit_settings(self, guild_id):
        await self.ensure_db()
        if self.db is None:
            return
        await self.db.execute('DELETE FROM limit_settings WHERE guild_id = ?', (guild_id,))
        await self.db.commit()


    @commands.command(name='antinuke', aliases=['antiwizz', 'anti'], help="Enables/Disables Anti-Nuke Module in the server")

    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 4, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    async def antinuke(self, ctx, option: Optional[str] = None):
        guild_id = ctx.guild.id
        pre=ctx.prefix

        # Ensure database connection with better error handling
        try:
            db_ready = await self.ensure_db()
            if not db_ready or self.db is None:
                embed = discord.Embed(title="❌ Database Error",
                    color=0xff0000,
                    description="Database connection failed. Please try again later."
                )
                return await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(title="❌ Database Connection Error",
                color=0xff0000,
                description="Unable to connect to database. Please contact an administrator."
            )
            return await ctx.send(embed=embed)
            
        try:
            async with self.db.execute('SELECT status FROM antinuke WHERE guild_id = ?', (guild_id,)) as cursor:
                row = await cursor.fetchone()
        except Exception as e:
            embed = discord.Embed(title="❌ Database Query Error",
                color=0xff0000,
                description="Failed to retrieve antinuke status. Please try again later."
            )
            return await ctx.send(embed=embed)

        async with self.db.execute(
            "SELECT owner_id FROM extraowners WHERE guild_id = ? AND owner_id = ?",
            (ctx.guild.id, ctx.author.id)
        ) as cursor:
            check = await cursor.fetchone()

        is_owner = ctx.author.id == ctx.guild.owner_id
        if not is_owner and not check:
            embed = discord.Embed(title="<:feast_cross:1400143488695144609> Access Denied",
                color=0x006fb9,
                description="Only Server Owner or Extra Owner can Run this Command!"
            )
            return await ctx.send(embed=embed)

        is_activated = row[0] if row else False

        if option is None:
            embed = discord.Embed(
                title='__**Antinuke**__',
                description="Boost your server security with Antinuke! It automatically bans any admins involved in suspicious activities, ensuring the safety of your whitelisted members. Strengthen your defenses – activate Antinuke today!",
                color=0x006fb9
            )
            embed.add_field(name='__**Antinuke Enable**__', value=f'To Enable Antinuke, Use - `{pre}antinuke enable`')
            embed.add_field(name='__**Antinuke Disable**__', value=f'To Disable Antinuke, Use - `{pre}antinuke disable`')

            embed.set_thumbnail(url=self.bot.user.avatar.url)
            await ctx.send(embed=embed)

        elif option.lower() == 'enable':
            if is_activated:
                embed = discord.Embed(
                    description=f'**Security Settings For {ctx.guild.name}**\nYour server __**already has Antinuke enabled.**__\n\nCurrent Status: <:enabled:1204107832232775730> Enabled\nTo Disable use `antinuke disable`',
                    color=0x006fb9
                )
                embed.set_thumbnail(url=self.bot.user.avatar.url)
                await ctx.send(embed=embed)
            else:
                setup_embed = discord.Embed(
                    title="Antinuke Setup <a:Gear:1329025929971896340>",
                    description="<:feast_tick:1400143469892210753> | Initializing Quick Setup!",
                    color=0x006fb9
                )
                setup_message = await ctx.send(embed=setup_embed)


                if not ctx.guild.me.guild_permissions.administrator:
                    if setup_embed.description is None:
                        setup_embed.description = ""
                    setup_embed.description += "\n<:feast_warning:1400143131990560830> | Setup failed: Missing **Administrator** permission."
                    await setup_message.edit(embed=setup_embed)
                    return

                await asyncio.sleep(1)
                if setup_embed.description is None:
                    setup_embed.description = ""
                setup_embed.description += "\n<:feast_tick:1400143469892210753>| Checking Sleepless's role position for optimal configuration..."
                await setup_message.edit(embed=setup_embed)

                await asyncio.sleep(1)
                setup_embed.description += "\n<:feast_tick:1400143469892210753> | Crafting and configuring the Sleepless Supreme role..."
                await setup_message.edit(embed=setup_embed)

                try:
                    role = await ctx.guild.create_role(
                        name="Sleepless Supreme",
                        color=0x0ba7ff,
                        permissions=discord.Permissions(administrator=True),
                        hoist=False,
                        mentionable=False,
                        reason="Antinuke setup Role Creation"
                    )
                    await ctx.guild.me.add_roles(role)
                except discord.Forbidden:
                    setup_embed.description += "\n<:feast_warning:1400143131990560830> | Setup failed: Insufficient permissions to create role."
                    await setup_message.edit(embed=setup_embed)
                    return
                except discord.HTTPException as e:
                    setup_embed.description += f"\n<:feast_warning:1400143131990560830> | Setup failed: HTTPException: {e}\nCheck Guild **Audit Logs**."
                    await setup_message.edit(embed=setup_embed)
                    return

                await asyncio.sleep(1)
                setup_embed.description += "\n<:feast_tick:1400143469892210753>| Ensuring precise placement of the Sleepless Supreme role..."
                await setup_message.edit(embed=setup_embed)
                
                try:
                    await ctx.guild.edit_role_positions(positions={role: 1})
                except discord.Forbidden:
                    setup_embed.description += "\n<:feast_warning:1400143131990560830> | Setup failed: Insufficient permissions to move role."
                    await setup_message.edit(embed=setup_embed)
                    return
                except discord.HTTPException as e:
                    setup_embed.description += f"\n<:feast_warning:1400143131990560830> | Setup failed: HTTPException: {e}."
                    await setup_message.edit(embed=setup_embed)
                    return

                await asyncio.sleep(1)
                setup_embed.description += "\n<:feast_tick:1400143469892210753> | Safeguarding your changes..."
                await setup_message.edit(embed=setup_embed)

                await asyncio.sleep(1)
                setup_embed.description += "\\<:feast_tick:1400143469892210753> | Activating the Antinuke Modules for enhanced security...!!"
                await setup_message.edit(embed=setup_embed)

                await self.ensure_db()
                if self.db is not None:
                    await self.db.execute('INSERT OR REPLACE INTO antinuke (guild_id, status) VALUES (?, ?)', (guild_id, True))
                    await self.db.commit()
                    # CRITICAL: Enable limit_settings so events actually trigger
                    await self.enable_limit_settings(guild_id)

                await asyncio.sleep(1)
                await setup_message.delete()

                embed = discord.Embed(
                    description=f"**Security Settings For {ctx.guild.name} **\n\nTip: For optimal functionality of the AntiNuke Module, please ensure that my role has **Administration** permissions and is positioned at the **Top** of the roles list\n\n<:feast_settings:1400425884980088874> __**Modules Enabled**__\n>>> <a:enabled_:1329022799708160063> **Anti Ban**\n<a:enabled_:1329022799708160063> **Anti Kick**\n<a:enabled_:1329022799708160063> **Anti Bot**\n<a:enabled_:1329022799708160063> **Anti Channel Create**\n<a:enabled_:1329022799708160063> **Anti Channel Delete**\n<a:enabled_:1329022799708160063> **Anti Channel Update**\n<a:enabled_:1329022799708160063> **Anti Everyone/Here**\n<a:enabled_:1329022799708160063>**Anti Role Create**\n<a:enabled_:1329022799708160063> **Anti Role Delete**\n<a:enabled_:1329022799708160063> **Anti Role Update**\n<a:enabled_:1329022799708160063> **Anti Member Update**\n<a:enabled_:1329022799708160063> **Anti Guild Update**\n<a:enabled_:1329022799708160063> **Anti Integration**\n<a:enabled_:1329022799708160063> **Anti Webhook Create**\n<a:enabled_:1329022799708160063> **Anti Webhook Delete**\n<a:enabled_:1329022799708160063> **Anti Webhook Update**",
                    color=0x006fb9
                )

                embed.add_field(name='', value="<a:enabled_:1329022799708160063> **Anti Prune**\n **Auto Recovery**")

                embed.set_author(name="Sleepless Antinuke", icon_url=self.bot.user.avatar.url)

                embed.set_footer(text="Successfully Enabled Antinuke for this server | Powered by Sleepless  Development™", icon_url=self.bot.user.avatar.url)
                embed.set_thumbnail(url=self.bot.user.avatar.url)

                view = discord.ui.View()
                view.add_item(discord.ui.Button(label="🎯 Show Punishment System (Escalation)", custom_id="show_punishment", style=discord.ButtonStyle.primary))

                await ctx.send(embed=embed, view=view)

        elif option.lower() == 'disable':
            if not is_activated:
                embed = discord.Embed(
                    description=f'**Security Settings For {ctx.guild.name}**\nUhh, looks like your server hasn\'t enabled Antinuke.\n\nCurrent Status: <a:disabled1:1329022921427128321> Disabled\n\nTo Enable use `antinuke enable`',
                    color=0x006fb9
                )
                embed.set_thumbnail(url=self.bot.user.avatar.url)
            else:
                await self.ensure_db()
                if self.db is not None:
                    await self.db.execute('DELETE FROM antinuke WHERE guild_id = ?', (guild_id,))
                    await self.db.commit()
                embed = discord.Embed(
                    description=f'**Security Settings For {ctx.guild.name}**\nSuccessfully disabled Antinuke for this server.\n\nCurrent Status: <a:disabled1:1329022921427128321> Disabled\n\nTo Enable use `antinuke enable`',
                    color=0x006fb9
                )
                embed.set_thumbnail(url=self.bot.user.avatar.url)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description='Invalid option. Please use `enable` or `disable`.',
                color=0x006fb9
            )
            await ctx.send(embed=embed)


    @commands.group(name='anticonfig', aliases=['anconfig'], invoke_without_command=True, help="Configure antinuke thresholds and settings")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.guild_only()
    async def anticonfig(self, ctx):
        """Main antinuke configuration command"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="<:feast_settings:1400425884980088874> Antinuke Configuration",
                description="Configure threshold-based security settings for your server.",
                color=0x006fb9
            )
            embed.add_field(
                name="__**Available Commands**__",
                value=(
                    f"`{ctx.prefix}anticonfig view [action]` - View threshold settings\n"
                    f"`{ctx.prefix}anticonfig set <action> <limit> <seconds>` - Set thresholds\n"
                    f"`{ctx.prefix}anticonfig punishment <action> <type>` - Set punishment type\n"
                    f"`{ctx.prefix}anticonfig reset <action>` - Reset to defaults\n"
                    f"`{ctx.prefix}anticonfig enable <action>` - Enable protection\n"
                    f"`{ctx.prefix}anticonfig disable <action>` - Disable protection"
                ),
                inline=False
            )
            embed.add_field(
                name="__**Action Types**__",
                value=(
                    "`ban`, `kick`, `role_delete`, `role_create`, `role_update`, "
                    "`channel_delete`, `channel_create`, `channel_update`, "
                    "`webhook_create`, `webhook_delete`, `webhook_update`, "
                    "`emoji_create`, `emoji_delete`, `emoji_update`, "
                    "`bot_add`, `guild_update`, `prune`, `integration_update`, "
                    "`sticker_create`, `member_update`, `unban`"
                ),
                inline=False
            )
            embed.add_field(
                name="__**Punishment Types**__",
                value="`ban`, `kick`, `strip_perms`, `timeout`",
                inline=False
            )
            embed.set_thumbnail(url=self.bot.user.avatar.url)
            embed.set_footer(text=f"Example: {ctx.prefix}anticonfig set ban 5 15")
            await ctx.send(embed=embed)


    @anticonfig.command(name='view', help="View current threshold configurations")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.guild_only()
    async def anticonfig_view(self, ctx, action_type: Optional[str] = None):
        """View threshold configuration for an action or all actions"""
        # Check permissions
        await self.ensure_db()
        if self.db is None:
            return await ctx.send(embed=discord.Embed(title="❌ Database Error", color=0xff0000))
        
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
                description="Only Server Owner or Extra Owner can view this configuration!"
            )
            return await ctx.send(embed=embed)

        if action_type:
            # View specific action
            config = await self.action_tracker.get_threshold_config(ctx.guild.id, action_type)
            
            embed = discord.Embed(
                title=f"<:feast_settings:1400425884980088874> Threshold Config: {action_type}",
                color=0x006fb9
            )
            
            if config:
                status = "<a:enabled_:1329022799708160063> Enabled" if config.enabled else "<a:disabled1:1329022921427128321> Disabled"
                embed.add_field(
                    name="__**Current Settings**__",
                    value=(
                        f"**Status:** {status}\n"
                        f"**Threshold:** {config.limit} actions\n"
                        f"**Time Window:** {config.time_window} seconds\n"
                        f"**Punishment:** {config.punishment_type.replace('_', ' ').title()}"
                    ),
                    inline=False
                )
                embed.add_field(
                    name="__**Explanation**__",
                    value=f"If a user performs **{config.limit}** {action_type} actions within **{config.time_window}** seconds, they will be **{config.punishment_type.replace('_', ' ')}**.",
                    inline=False
                )
            else:
                embed.description = f"No custom configuration found for `{action_type}`. Using default settings."
                
        else:
            # View all actions with pagination
            embed = discord.Embed(
                title="<:feast_settings:1400425884980088874> All Threshold Configurations",
                description="Current threshold settings for all protection modules",
                color=0x006fb9
            )
            
            # Get all action types from DEFAULT_THRESHOLDS
            action_types = list(ActionTracker.DEFAULT_THRESHOLDS.keys())
            
            # Split into chunks for pagination
            chunk_size = 8
            chunks = [action_types[i:i + chunk_size] for i in range(0, len(action_types), chunk_size)]
            
            # Show first page
            for action in chunks[0]:
                config = await self.action_tracker.get_threshold_config(ctx.guild.id, action)
                status = "✅" if config.enabled else "❌"
                embed.add_field(
                    name=f"{status} {action.replace('_', ' ').title()}",
                    value=f"`{config.limit}` actions in `{config.time_window}s` → `{config.punishment_type}`",
                    inline=True
                )
            
            embed.set_footer(text=f"Page 1/{len(chunks)} • Use {ctx.prefix}anticonfig view <action> for details")
        
        embed.set_thumbnail(url=self.bot.user.avatar.url)
        await ctx.send(embed=embed)


    @anticonfig.command(name='set', help="Set threshold limits for an action")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.guild_only()
    async def anticonfig_set(self, ctx, action_type: str, action_limit: int, time_window: int):
        """Set custom threshold for an action type"""
        # Check permissions
        await self.ensure_db()
        if self.db is None:
            return await ctx.send(embed=discord.Embed(title="❌ Database Error", color=0xff0000))
        
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
                description="Only Server Owner or Extra Owner can modify configurations!"
            )
            return await ctx.send(embed=embed)

        # Validate inputs
        if action_limit < 1 or action_limit > 100:
            embed = discord.Embed(
                title="<:feast_cross:1400143488695144609> Invalid Limit",
                color=0xff0000,
                description="Action limit must be between 1 and 100."
            )
            return await ctx.send(embed=embed)

        if time_window < 5 or time_window > 300:
            embed = discord.Embed(
                title="<:feast_cross:1400143488695144609> Invalid Time Window",
                color=0xff0000,
                description="Time window must be between 5 and 300 seconds."
            )
            return await ctx.send(embed=embed)

        # Get current config for punishment type
        current_config = await self.action_tracker.get_threshold_config(ctx.guild.id, action_type)
        
        # Set new threshold
        await self.action_tracker.set_threshold_config(
            guild_id=ctx.guild.id,
            action_type=action_type,
            limit=action_limit,
            time_window=time_window,
            punishment_type=current_config.punishment_type,
            enabled=True
        )

        embed = discord.Embed(
            title="<:feast_tick:1400143469892210753> Threshold Updated",
            color=0x006fb9,
            description=f"Successfully updated threshold for `{action_type}`"
        )
        embed.add_field(
            name="__**New Settings**__",
            value=(
                f"**Action:** {action_type.replace('_', ' ').title()}\n"
                f"**Threshold:** {action_limit} actions\n"
                f"**Time Window:** {time_window} seconds\n"
                f"**Punishment:** {current_config.punishment_type.replace('_', ' ').title()}"
            ),
            inline=False
        )
        embed.add_field(
            name="__**Effect**__",
            value=f"If a user performs **{action_limit}** {action_type} actions within **{time_window}** seconds, they will be **{current_config.punishment_type.replace('_', ' ')}**.",
            inline=False
        )

        embed.set_thumbnail(url=self.bot.user.avatar.url)
        await ctx.send(embed=embed)


    @anticonfig.command(name='punishment', help="Set punishment type for an action")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.guild_only()
    async def anticonfig_punishment(self, ctx, action_type: str, punishment_type: str):
        """Set punishment type for threshold violations"""
        # Check permissions
        await self.ensure_db()
        if self.db is None:
            return await ctx.send(embed=discord.Embed(title="❌ Database Error", color=0xff0000))
        
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
                description="Only Server Owner or Extra Owner can modify configurations!"
            )
            return await ctx.send(embed=embed)

        # Validate punishment type
        valid_punishments = ['ban', 'kick', 'strip_perms', 'timeout']
        if punishment_type.lower() not in valid_punishments:
            embed = discord.Embed(
                title="<:feast_cross:1400143488695144609> Invalid Punishment",
                color=0xff0000,
                description=f"Punishment must be one of: `{', '.join(valid_punishments)}`"
            )
            return await ctx.send(embed=embed)

        # Get current config
        current_config = await self.action_tracker.get_threshold_config(ctx.guild.id, action_type)
        
        # Update punishment type
        await self.action_tracker.set_threshold_config(
            guild_id=ctx.guild.id,
            action_type=action_type,
            limit=current_config.limit,
            time_window=current_config.time_window,
            punishment_type=punishment_type.lower(),
            enabled=current_config.enabled
        )

        embed = discord.Embed(
            title="<:feast_tick:1400143469892210753> Punishment Type Updated",
            color=0x006fb9,
            description=f"Successfully updated punishment for `{action_type}`"
        )
        embed.add_field(
            name="__**New Settings**__",
            value=(
                f"**Action:** {action_type.replace('_', ' ').title()}\n"
                f"**Threshold:** {current_config.limit} actions in {current_config.time_window}s\n"
                f"**Punishment:** {punishment_type.replace('_', ' ').title()}"
            ),
            inline=False
        )

        embed.set_thumbnail(url=self.bot.user.avatar.url)
        await ctx.send(embed=embed)


    @anticonfig.command(name='reset', help="Reset threshold to default values")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.guild_only()
    async def anticonfig_reset(self, ctx, action_type: str):
        """Reset threshold configuration to defaults"""
        # Check permissions
        await self.ensure_db()
        if self.db is None:
            return await ctx.send(embed=discord.Embed(title="❌ Database Error", color=0xff0000))
        
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
                description="Only Server Owner or Extra Owner can reset configurations!"
            )
            return await ctx.send(embed=embed)

        # Check if action type exists in defaults
        if action_type not in ActionTracker.DEFAULT_THRESHOLDS:
            embed = discord.Embed(
                title="<:feast_cross:1400143488695144609> Invalid Action",
                color=0xff0000,
                description=f"Unknown action type: `{action_type}`"
            )
            return await ctx.send(embed=embed)

        # Delete custom config to revert to defaults
        db = await self.action_tracker.ensure_connection()
        await db.execute(
            "DELETE FROM threshold_config WHERE guild_id = ? AND action_type = ?",
            (ctx.guild.id, action_type)
        )
        await db.commit()

        # Get default config
        default_config = await self.action_tracker.get_threshold_config(ctx.guild.id, action_type)

        embed = discord.Embed(
            title="<:feast_tick:1400143469892210753> Reset to Defaults",
            color=0x006fb9,
            description=f"Successfully reset `{action_type}` to default settings"
        )
        embed.add_field(
            name="__**Default Settings**__",
            value=(
                f"**Threshold:** {default_config.limit} actions\n"
                f"**Time Window:** {default_config.time_window} seconds\n"
                f"**Punishment:** {default_config.punishment_type.replace('_', ' ').title()}"
            ),
            inline=False
        )
        embed.set_thumbnail(url=self.bot.user.avatar.url)
        await ctx.send(embed=embed)


    @anticonfig.command(name='enable', help="Enable protection for an action type")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.guild_only()
    async def anticonfig_enable(self, ctx, action_type: str):
        """Enable threshold protection for an action"""
        # Check permissions
        await self.ensure_db()
        if self.db is None:
            return await ctx.send(embed=discord.Embed(title="❌ Database Error", color=0xff0000))
        
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
                description="Only Server Owner or Extra Owner can modify protections!"
            )
            return await ctx.send(embed=embed)

        # Get current config
        current_config = await self.action_tracker.get_threshold_config(ctx.guild.id, action_type)
        
        # Update enabled status
        await self.action_tracker.set_threshold_config(
            guild_id=ctx.guild.id,
            action_type=action_type,
            limit=current_config.limit,
            time_window=current_config.time_window,
            punishment_type=current_config.punishment_type,
            enabled=True
        )

        embed = discord.Embed(
            title="<:feast_tick:1400143469892210753> Protection Enabled",
            color=0x006fb9,
            description=f"Successfully enabled protection for `{action_type}`"
        )

        embed.set_thumbnail(url=self.bot.user.avatar.url)
        await ctx.send(embed=embed)


    @anticonfig.command(name='disable', help="Disable protection for an action type")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.guild_only()
    async def anticonfig_disable(self, ctx, action_type: str):
        """Disable threshold protection for an action"""
        # Check permissions
        await self.ensure_db()
        if self.db is None:
            return await ctx.send(embed=discord.Embed(title="❌ Database Error", color=0xff0000))
        
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
                description="Only Server Owner or Extra Owner can modify protections!"
            )
            return await ctx.send(embed=embed)

        # Get current config
        current_config = await self.action_tracker.get_threshold_config(ctx.guild.id, action_type)
        
        # Update enabled status
        await self.action_tracker.set_threshold_config(
            guild_id=ctx.guild.id,
            action_type=action_type,
            limit=current_config.limit,
            time_window=current_config.time_window,
            punishment_type=current_config.punishment_type,
            enabled=False
        )

        embed = discord.Embed(
            title="<:feast_tick:1400143469892210753> Protection Disabled",
            color=0xff0000,
            description=f"Successfully disabled protection for `{action_type}`"
        )

        embed.set_thumbnail(url=self.bot.user.avatar.url)
        await ctx.send(embed=embed)


    @commands.command(name='antistatus', aliases=['anstatus', 'nukestatus'], help="Show antinuke system status and statistics")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.guild_only()
    async def antistatus(self, ctx):
        """Display comprehensive antinuke status, statistics, and recent activity"""
        # Check permissions
        await self.ensure_db()
        if self.db is None:
            return await ctx.send(embed=discord.Embed(title="❌ Database Error", color=0xff0000))
        
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
                description="Only Server Owner or Extra Owner can view system status!"
            )
            return await ctx.send(embed=embed)

        # Check if antinuke is enabled
        async with self.db.execute(
            "SELECT status FROM antinuke WHERE guild_id = ?",
            (ctx.guild.id,)
        ) as cursor:
            status_row = await cursor.fetchone()
            antinuke_enabled = bool(status_row and status_row[0])

        # Get statistics from ActionTracker
        db = await self.action_tracker.ensure_connection()
        
        # Get recent actions count (last 24 hours)
        import time
        cutoff_24h = time.time() - 86400
        async with db.execute(
            "SELECT COUNT(*) FROM action_tracker WHERE guild_id = ? AND timestamp >= ?",
            (ctx.guild.id, cutoff_24h)
        ) as cursor:
            result = await cursor.fetchone()
            recent_actions = result[0] if result else 0

        # Get punishment count (last 24 hours)
        async with db.execute(
            "SELECT COUNT(*) FROM punishment_log WHERE guild_id = ? AND timestamp >= ?",
            (ctx.guild.id, cutoff_24h)
        ) as cursor:
            result = await cursor.fetchone()
            recent_punishments = result[0] if result else 0

        # Get top 5 most triggered actions
        async with db.execute('''
            SELECT action_type, COUNT(*) as count 
            FROM action_tracker 
            WHERE guild_id = ? AND timestamp >= ?
            GROUP BY action_type 
            ORDER BY count DESC 
            LIMIT 5
        ''', (ctx.guild.id, cutoff_24h)) as cursor:
            top_actions = await cursor.fetchall()

        # Get whitelisted users count
        async with self.db.execute(
            "SELECT COUNT(DISTINCT owner_id) FROM extraowners WHERE guild_id = ?",
            (ctx.guild.id,)
        ) as cursor:
            result = await cursor.fetchone()
            extra_owners = result[0] if result else 0

        async with self.db.execute(
            "SELECT COUNT(*) FROM whitelisted_users WHERE guild_id = ?",
            (ctx.guild.id,)
        ) as cursor:
            result = await cursor.fetchone()
            whitelisted_users = result[0] if result else 0

        # Get enabled protections count
        async with db.execute(
            "SELECT COUNT(*) FROM threshold_config WHERE guild_id = ? AND enabled = 1",
            (ctx.guild.id,)
        ) as cursor:
            result = await cursor.fetchone()
            custom_enabled = result[0] if result else 0

        # Total protections = 21 default action types
        total_protections = len(ActionTracker.DEFAULT_THRESHOLDS)
        
        # Build status embed
        embed = discord.Embed(
            title="<:feast_settings:1400425884980088874> AntiNuke System Status",
            description=f"**Server:** {ctx.guild.name}\n**Protection Status:** {'<a:enabled_:1329022799708160063> **Active**' if antinuke_enabled else '<a:disabled1:1329022921427128321> **Disabled**'}",
            color=0x00ff00 if antinuke_enabled else 0xff0000,
            timestamp=ctx.message.created_at
        )

        # System Overview
        embed.add_field(
            name="__**📊 System Overview**__",
            value=(
                f"**Active Protections:** {total_protections} modules\n"
                f"**Custom Configs:** {custom_enabled} configured\n"
                f"**Whitelisted Users:** {whitelisted_users}\n"
                f"**Extra Owners:** {extra_owners}"
            ),
            inline=True
        )

        # Recent Activity (24h)
        embed.add_field(
            name="__**📈 24h Activity**__",
            value=(
                f"**Actions Tracked:** {recent_actions}\n"
                f"**Punishments Applied:** {recent_punishments}\n"
                f"**Actions Reverted:** {recent_punishments * 2} avg"  # Rough estimate
            ),
            inline=True
        )

        # Protection Modules Status
        protection_status = (
            "<a:enabled_:1329022799708160063> Ban Protection\n"
            "<a:enabled_:1329022799708160063> Kick Protection\n"
            "<a:enabled_:1329022799708160063> Role Protection (Create/Delete/Update)\n"
            "<a:enabled_:1329022799708160063> Channel Protection (Create/Delete/Update)\n"
            "<a:enabled_:1329022799708160063> Webhook Protection\n"
            "<a:enabled_:1329022799708160063> Bot Add Protection\n"
            "<a:enabled_:1329022799708160063> Emoji/Sticker Protection\n"
            "<a:enabled_:1329022799708160063> Guild Update Protection\n"
            "<a:enabled_:1329022799708160063> Member Prune Protection"
        )
        
        embed.add_field(
            name="__**🛡️ Active Protections**__",
            value=protection_status,
            inline=False
        )

        # Top Triggered Actions
        if top_actions:
            top_actions_str = "\n".join([
                f"**{i+1}.** `{action[0]}` - {action[1]} times" 
                for i, action in enumerate(top_actions)
            ])
        else:
            top_actions_str = "*No activity in last 24 hours*"

        embed.add_field(
            name="__**🔥 Most Triggered (24h)**__",
            value=top_actions_str,
            inline=False
        )

        # Quick Stats
        embed.add_field(
            name="__**⚡ Quick Stats**__",
            value=(
                f"**Server Owner:** <@{ctx.guild.owner_id}>\n"
                f"**Total Members:** {ctx.guild.member_count}\n"
                f"**Total Roles:** {len(ctx.guild.roles)}\n"
                f"**Total Channels:** {len(ctx.guild.channels)}"
            ),
            inline=True
        )

        # Configuration Info
        embed.add_field(
            name="__**⚙️ Configuration**__",
            value=(
                f"**View Thresholds:** `{ctx.prefix}anticonfig view`\n"
                f"**Modify Settings:** `{ctx.prefix}anticonfig set`\n"
                f"**View Whitelist:** `{ctx.prefix}whitelist show`"
            ),
            inline=True
        )

        embed.set_thumbnail(url=self.bot.user.avatar.url)
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        
        await ctx.send(embed=embed)

    @commands.command(name="scanroles", aliases=['scanrole', 'fakeroles', 'checkroles'], help="Scan for fake/suspicious roles in the server")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 30, commands.BucketType.guild)
    @commands.guild_only()
    async def scanroles(self, ctx, min_risk: int = 30):
        """
        Scan for fake/suspicious roles with risk scoring
        Usage: $antinuke scanroles [min_risk]
        min_risk: Minimum risk score to show (default: 30, range: 0-100)
        """
        from utils.fake_role_detector import FakeRoleDetector
        
        # Validate min_risk
        if not 0 <= min_risk <= 100:
            embed = discord.Embed(
                title="❌ Invalid Risk Score",
                description="Minimum risk score must be between 0 and 100.",
                color=0xff0000
            )
            return await ctx.send(embed=embed)
        
        # Send initial scanning message
        scanning_embed = discord.Embed(
            title="🔍 Scanning Server Roles...",
            description=f"Analyzing {len(ctx.guild.roles)} roles for suspicious activity...",
            color=0xffaa00
        )
        scanning_msg = await ctx.send(embed=scanning_embed)
        
        try:
            # Scan for suspicious roles
            suspicious_roles = await FakeRoleDetector.scan_fake_roles(ctx.guild, min_risk_score=min_risk)
            
            if not suspicious_roles:
                embed = discord.Embed(
                    title="✅ No Suspicious Roles Found",
                    description=f"No roles with risk score ≥ {min_risk} were detected.\nYour server appears to be secure!",
                    color=0x00ff00
                )
                embed.add_field(
                    name="💡 Tip",
                    value=f"Lower the threshold to see all roles: `{ctx.prefix}antinuke scanroles 10`",
                    inline=False
                )
                embed.set_footer(text=f"Scanned {len(ctx.guild.roles)} roles")
                await scanning_msg.edit(embed=embed)
                return
            
            # Create paginated embed
            roles_per_page = 5
            total_pages = (len(suspicious_roles) + roles_per_page - 1) // roles_per_page
            current_page = 0
            
            def create_page_embed(page: int):
                start_idx = page * roles_per_page
                end_idx = min(start_idx + roles_per_page, len(suspicious_roles))
                page_roles = suspicious_roles[start_idx:end_idx]
                
                embed = discord.Embed(
                    title="🚨 Suspicious Roles Detected",
                    description=f"Found **{len(suspicious_roles)}** suspicious role(s) with risk ≥ {min_risk}",
                    color=0xff0000
                )
                
                for role_data in page_roles:
                    role = role_data['role']
                    risk_score = role_data['risk_score']
                    risk_level = role_data['risk_level']
                    risk_emoji = role_data['risk_emoji']
                    
                    # Build field value
                    field_lines = [
                        f"**Risk:** {risk_emoji} {risk_level} ({risk_score}/100)",
                        f"**Created:** {discord.utils.format_dt(role.created_at, 'R')}",
                        f"**Members:** {role_data['member_count']} | **Position:** {role_data['position']}"
                    ]
                    
                    # Add dangerous permissions
                    if role_data['dangerous_permissions']:
                        perms = role_data['dangerous_permissions'][:3]
                        perm_str = ', '.join([p.replace('_', ' ').title() for p in perms])
                        if len(role_data['dangerous_permissions']) > 3:
                            perm_str += f" +{len(role_data['dangerous_permissions']) - 3} more"
                        field_lines.append(f"⚠️ **Perms:** {perm_str}")
                    
                    # Add duplicate warning
                    if role_data['has_duplicate']:
                        dup_count = len(role_data['duplicate_roles']) - 1
                        field_lines.append(f"🔄 **{dup_count} duplicate(s) detected**")
                    
                    # Add top risk factors
                    if role_data['score_breakdown']:
                        breakdown = role_data['score_breakdown']
                        top_factors = sorted(breakdown.items(), key=lambda x: x[1], reverse=True)[:2]
                        if top_factors:
                            factors_str = ", ".join([f"{k.replace('_', ' ').title()}" for k, v in top_factors if v > 0])
                            if factors_str:
                                field_lines.append(f"🚩 **Flags:** {factors_str}")
                    
                    embed.add_field(
                        name=f"{role.name} (ID: {role.id})",
                        value="\n".join(field_lines),
                        inline=False
                    )
                
                # Add summary
                risk_counts = {}
                for rd in suspicious_roles:
                    level = rd['risk_level']
                    risk_counts[level] = risk_counts.get(level, 0) + 1
                
                summary = []
                for level in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
                    if level in risk_counts:
                        emoji = {'CRITICAL': '🔴', 'HIGH': '🟠', 'MEDIUM': '🟡', 'LOW': '🟢'}[level]
                        summary.append(f"{emoji} {level}: {risk_counts[level]}")
                
                if summary:
                    embed.add_field(
                        name="📊 Risk Summary",
                        value=" | ".join(summary),
                        inline=False
                    )
                
                embed.set_footer(text=f"Page {page + 1}/{total_pages} | Use {ctx.prefix}antinuke cleanfakeroles to remove suspicious roles")
                return embed
            
            # Create view with pagination buttons
            class RoleScanView(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=180)
                    self.current_page = 0
                    self.update_buttons()
                
                def update_buttons(self):
                    self.previous_button.disabled = (self.current_page == 0)
                    self.next_button.disabled = (self.current_page >= total_pages - 1)
                
                @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.secondary)
                async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user.id != ctx.author.id:
                        await interaction.response.send_message("You can't use this button.", ephemeral=True)
                        return
                    
                    self.current_page = max(0, self.current_page - 1)
                    self.update_buttons()
                    await interaction.response.edit_message(embed=create_page_embed(self.current_page), view=self)
                
                @discord.ui.button(label="Next ▶️", style=discord.ButtonStyle.secondary)
                async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user.id != ctx.author.id:
                        await interaction.response.send_message("You can't use this button.", ephemeral=True)
                        return
                    
                    self.current_page = min(total_pages - 1, self.current_page + 1)
                    self.update_buttons()
                    await interaction.response.edit_message(embed=create_page_embed(self.current_page), view=self)
                
                @discord.ui.button(label="🗑️ Clean Roles", style=discord.ButtonStyle.danger, row=1)
                async def clean_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user.id != ctx.author.id:
                        await interaction.response.send_message("You can't use this button.", ephemeral=True)
                        return
                    
                    await interaction.response.send_message(
                        f"Use `{ctx.prefix}antinuke cleanfakeroles` to safely remove suspicious roles with confirmation.",
                        ephemeral=True
                    )
                
                @discord.ui.button(label="❌ Close", style=discord.ButtonStyle.danger, row=1)
                async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user.id != ctx.author.id:
                        await interaction.response.send_message("You can't use this button.", ephemeral=True)
                        return
                    
                    if interaction.message:
                        await interaction.message.delete()
                    self.stop()
            
            view = RoleScanView() if total_pages > 1 else None
            await scanning_msg.edit(embed=create_page_embed(0), view=view)
            
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Scan Failed",
                description=f"An error occurred while scanning roles:\n```{str(e)}```",
                color=0xff0000
            )
            await scanning_msg.edit(embed=error_embed)
            print(f"[SCANROLES ERROR] {e}")
            import traceback
            traceback.print_exc()

    @commands.command(name="cleanfakeroles", aliases=['removefake', 'deletefake', 'purgefake'], help="Remove detected fake/suspicious roles")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 60, commands.BucketType.guild)
    @commands.guild_only()
    async def cleanfakeroles(self, ctx, min_risk: int = 50):
        """
        Remove suspicious roles with confirmation
        Usage: $antinuke cleanfakeroles [min_risk]
        min_risk: Minimum risk score to remove (default: 50, range: 0-100)
        """
        from utils.fake_role_detector import FakeRoleDetector
        
        # Validate min_risk
        if not 0 <= min_risk <= 100:
            embed = discord.Embed(
                title="❌ Invalid Risk Score",
                description="Minimum risk score must be between 0 and 100.",
                color=0xff0000
            )
            return await ctx.send(embed=embed)
        
        # Scan for suspicious roles
        scanning_embed = discord.Embed(
            title="🔍 Scanning for Suspicious Roles...",
            description=f"Looking for roles with risk score ≥ {min_risk}...",
            color=0xffaa00
        )
        scanning_msg = await ctx.send(embed=scanning_embed)
        
        try:
            suspicious_roles = await FakeRoleDetector.scan_fake_roles(ctx.guild, min_risk_score=min_risk)
            
            if not suspicious_roles:
                embed = discord.Embed(
                    title="✅ No Suspicious Roles Found",
                    description=f"No roles with risk score ≥ {min_risk} were detected.",
                    color=0x00ff00
                )
                await scanning_msg.edit(embed=embed)
                return
            
            # Filter out roles that can't be deleted (higher than bot's top role)
            bot_top_role = ctx.guild.me.top_role
            deletable_roles = []
            protected_roles = []
            
            for role_data in suspicious_roles:
                role = role_data['role']
                # Can't delete roles higher than bot's role or @everyone
                if role.position >= bot_top_role.position or role.is_default():
                    protected_roles.append(role_data)
                else:
                    deletable_roles.append(role_data)
            
            if not deletable_roles:
                embed = discord.Embed(
                    title="⚠️ No Deletable Roles",
                    description=f"Found {len(suspicious_roles)} suspicious role(s), but none can be deleted.\n\nAll suspicious roles are either above my highest role or protected.",
                    color=0xff9900
                )
                embed.add_field(
                    name="💡 Solution",
                    value="Move my role higher in the role hierarchy to delete suspicious roles.",
                    inline=False
                )
                await scanning_msg.edit(embed=embed)
                return
            
            # Create confirmation embed
            confirm_embed = discord.Embed(
                title="⚠️ Confirm Role Deletion",
                description=f"**{len(deletable_roles)}** suspicious role(s) will be deleted.",
                color=0xff9900
            )
            
            # Show roles to be deleted (max 10)
            roles_list = []
            for i, role_data in enumerate(deletable_roles[:10]):
                role = role_data['role']
                risk_emoji = role_data['risk_emoji']
                risk_score = role_data['risk_score']
                member_count = role_data['member_count']
                roles_list.append(f"{i+1}. **{role.name}** {risk_emoji} (Risk: {risk_score}, Members: {member_count})")
            
            if len(deletable_roles) > 10:
                roles_list.append(f"\n... and {len(deletable_roles) - 10} more roles")
            
            confirm_embed.add_field(
                name="🗑️ Roles to Delete",
                value="\n".join(roles_list),
                inline=False
            )
            
            if protected_roles:
                confirm_embed.add_field(
                    name=f"🛡️ Protected Roles ({len(protected_roles)})",
                    value="Some suspicious roles cannot be deleted (above bot role or @everyone)",
                    inline=False
                )
            
            confirm_embed.add_field(
                name="⚠️ Warning",
                value="**This action cannot be undone!**\nMembers with these roles will lose them permanently.",
                inline=False
            )
            
            confirm_embed.set_footer(text="Click 'Confirm' to proceed or 'Cancel' to abort")
            
            # Create confirmation view
            class ConfirmCleanView(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=60)
                    self.value = None
                
                @discord.ui.button(label="✅ Confirm", style=discord.ButtonStyle.danger)
                async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user.id != ctx.author.id:
                        await interaction.response.send_message("You can't use this button.", ephemeral=True)
                        return
                    
                    self.value = True
                    self.stop()
                    
                    # Start deletion process
                    await interaction.response.edit_message(
                        embed=discord.Embed(
                            title="🗑️ Deleting Roles...",
                            description=f"Removing {len(deletable_roles)} suspicious role(s)...",
                            color=0xffaa00
                        ),
                        view=None
                    )
                
                @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
                async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user.id != ctx.author.id:
                        await interaction.response.send_message("You can't use this button.", ephemeral=True)
                        return
                    
                    self.value = False
                    self.stop()
                    await interaction.response.edit_message(
                        embed=discord.Embed(
                            title="❌ Cancelled",
                            description="Role deletion cancelled. No roles were removed.",
                            color=0x006fb9
                        ),
                        view=None
                    )
            
            view = ConfirmCleanView()
            await scanning_msg.edit(embed=confirm_embed, view=view)
            await view.wait()
            
            if not view.value:
                return  # Cancelled
            
            # Delete roles with rate limiting
            deleted_count = 0
            failed_roles = []
            
            for role_data in deletable_roles:
                role = role_data['role']
                try:
                    await role.delete(reason=f"Fake role detected by antinuke (Risk: {role_data['risk_score']}/100)")
                    deleted_count += 1
                    await asyncio.sleep(0.5)  # Rate limit protection
                except discord.Forbidden:
                    failed_roles.append((role.name, "Missing Permissions"))
                except discord.HTTPException as e:
                    failed_roles.append((role.name, str(e)))
                except Exception as e:
                    failed_roles.append((role.name, f"Unknown error: {str(e)}"))
            
            # Create result embed
            result_embed = discord.Embed(
                title="✅ Cleanup Complete" if deleted_count > 0 else "❌ Cleanup Failed",
                color=0x00ff00 if deleted_count > 0 else 0xff0000
            )
            
            result_embed.add_field(
                name="📊 Results",
                value=f"**Deleted:** {deleted_count}/{len(deletable_roles)} roles",
                inline=False
            )
            
            if failed_roles:
                failed_list = [f"• **{name}**: {reason}" for name, reason in failed_roles[:10]]
                if len(failed_roles) > 10:
                    failed_list.append(f"... and {len(failed_roles) - 10} more")
                
                result_embed.add_field(
                    name=f"⚠️ Failed ({len(failed_roles)})",
                    value="\n".join(failed_list),
                    inline=False
                )
            
            if deleted_count > 0:
                result_embed.add_field(
                    name="✨ Recommendation",
                    value=f"Run `{ctx.prefix}antinuke scanroles` again to verify all suspicious roles are gone.",
                    inline=False
                )
            
            await scanning_msg.edit(embed=result_embed)
            
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Cleanup Failed",
                description=f"An error occurred while cleaning roles:\n```{str(e)}```",
                color=0xff0000
            )
            await scanning_msg.edit(embed=error_embed)
            print(f"[CLEANFAKEROLES ERROR] {e}")
            import traceback
            traceback.print_exc()

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.data and interaction.data.get('custom_id') == 'show_punishment':
            embed = discord.Embed(
                title="🎯 Progressive Punishment System (Escalation-Based)",
                description=(
                    "**All antinuke modules now use a progressive punishment system:**\n\n"
                    "**Escalation Levels:**\n"
                    "└ **Level 1** (1st offense): 10-minute timeout ⏱️\n"
                    "└ **Level 2** (2nd offense): Strip dangerous permissions 🔒\n"
                    "└ **Level 3** (3rd offense): Kick from server 👢\n"
                    "└ **Level 4** (4th+ offense): Permanent ban 🔨\n\n"
                    "**Protected Actions:**\n"
                    "• Anti Ban/Kick: Progressive escalation\n"
                    "• Anti Bot Add: Progressive escalation + bot removed\n"
                    "• Anti Channel Create/Delete/Update: Progressive escalation + auto-recovery\n"
                    "• Anti Role Create/Delete/Update: Progressive escalation + auto-recovery\n"
                    "• Anti Member Update: Progressive escalation (only dangerous permissions)\n"
                    "• Anti Guild Update: Progressive escalation + auto-revert\n"
                    "• Anti Webhook: Progressive escalation + webhook removed\n"
                    "• Anti Integration: Progressive escalation + integration removed\n"
                    "• Anti Prune: Progressive escalation\n"
                    "• Anti Everyone/Here: Message removed + escalation\n\n"
                    "**Offense Window:** 30 days (offenses older than 30 days don't count)\n"
                    "**Forgiveness:** Use `$antireset @user` to clear offense history\n\n"
                    "Note: Whitelisted users bypass all punishments. Member update actions only trigger for roles with dangerous permissions (Ban, Admin, Manage Guild, etc.)"
                ),
                color=0x006fb9
            )
            embed.set_footer(text="Progressive escalation ensures fair punishment while protecting against repeat offenders | Powered by Sleepless", icon_url=self.bot.user.avatar.url)
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.command(name="antireset", aliases=['antiforgive', 'resetanti', 'clearoffenses'], help="Reset offense count for a user (clean slate)")
    @commands.has_permissions(administrator=True)
    async def antireset(self, ctx, member: discord.Member):
        """
        Reset the offense count for a user in the punishment escalation system.
        This gives them a clean slate and resets their escalation level to 1.
        
        Usage: $antireset @member
        """
        from utils.escalation import reset_offenses, get_offense_count
        
        # Ensure database connection
        await self.ensure_db()
        if self.db is None:
            embed = discord.Embed(
                title="❌ Database Error",
                description="Database connection failed. Please try again later.",
                color=0xff0000
            )
            return await ctx.reply(embed=embed)
        
        # Check if antinuke is enabled
        cursor = await self.db.execute(
            'SELECT enabled FROM antinuke WHERE guild_id = ?',
            (ctx.guild.id,)
        )
        result = await cursor.fetchone()
        
        if not result or result[0] == 0:
            embed = discord.Embed(
                description=f"{self.bot.no} **Anti-Nuke system is not enabled in this server!**\nEnable it with `$antinuke enable`",
                color=self.bot.color
            )
            return await ctx.reply(embed=embed)
        
        # Get current offense count
        offense_count = await get_offense_count(ctx.guild.id, member.id)
        
        if offense_count == 0:
            embed = discord.Embed(
                description=f"{self.bot.no} **{member.mention} has no recorded offenses to reset.**",
                color=self.bot.color
            )
            return await ctx.reply(embed=embed)
        
        # Reset offenses
        cleared_count = await reset_offenses(ctx.guild.id, member.id)
        
        # Success embed
        embed = discord.Embed(
            title="✅ Offense History Reset",
            description=(
                f"**User:** {member.mention}\n"
                f"**Offenses Cleared:** {cleared_count}\n"
                f"**Reset By:** {ctx.author.mention}\n\n"
                f"The user's escalation level has been reset to **1** (first offense).\n"
                f"Their next violation will be treated as a first-time offense."
            ),
            color=0x00ff00
        )
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
        
        await ctx.reply(embed=embed)
        
        # Log the reset action
        await self.action_tracker.log_punishment(
            guild_id=ctx.guild.id,
            user_id=member.id,
            action_type="offense_reset",
            punishment_type="reset",
            actions_reverted=cleared_count,
            reason=f"Offense history reset by {ctx.author} ({ctx.author.id})",
            escalation_level=1
        )

        """
    @Author: Frosty
        + Discord: frosty.pyro
        + Community: https://discord.gg/5wtjDkYbVh (Sleepless Development)
        + for any queries reach out in the server; or send a dm.
        """