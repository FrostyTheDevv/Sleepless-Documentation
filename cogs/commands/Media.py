import discord
import aiosqlite
from discord.ext import commands
from utils.Tools import blacklist_check, ignore_check
from collections import defaultdict
import time

from utils.error_helpers import StandardErrorHandler
class Media(commands.Cog):
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, client):
        self.client = client
        # Removed in-memory infractions: self.infractions = defaultdict(list)

    async def cleanup_deleted_roles(self, guild_id):
        """Remove deleted roles from the bypass list"""
        guild = self.client.get_guild(guild_id)
        if not guild:
            return
            
        async with aiosqlite.connect('db/media.db') as db:
            async with db.execute('SELECT role_id FROM media_role_bypass WHERE guild_id = ?', (guild_id,)) as cursor:
                role_results = await cursor.fetchall()
            
            deleted_roles = []
            for role_id, in role_results:
                if not guild.get_role(role_id):
                    deleted_roles.append(role_id)
            
            if deleted_roles:
                placeholders = ','.join('?' * len(deleted_roles))
                query = f'DELETE FROM media_role_bypass WHERE guild_id = ? AND role_id IN ({placeholders})'
                await db.execute(query, [guild_id] + deleted_roles)
                await db.commit()
                print(f"[MEDIA] Cleaned up {len(deleted_roles)} deleted roles from bypass list for guild {guild_id}")

    async def save_infraction(self, user_id, guild_id, infraction_type, timestamp=None):
        """Save an infraction to the database"""
        if timestamp is None:
            timestamp = time.time()
        
        async with aiosqlite.connect('db/media.db') as db:
            await db.execute('''
                INSERT INTO media_infractions (user_id, guild_id, infraction_type, timestamp)
                VALUES (?, ?, ?, ?)
            ''', (user_id, guild_id, infraction_type, timestamp))
            await db.commit()

    async def get_user_infractions(self, user_id, guild_id, infraction_type=None, time_window=3600):
        """Get user infractions within a time window"""
        cutoff_time = time.time() - time_window
        
        async with aiosqlite.connect('db/media.db') as db:
            if infraction_type:
                cursor = await db.execute('''
                    SELECT timestamp FROM media_infractions
                    WHERE user_id = ? AND guild_id = ? AND infraction_type = ? AND timestamp >= ?
                    ORDER BY timestamp DESC
                ''', (user_id, guild_id, infraction_type, cutoff_time))
            else:
                cursor = await db.execute('''
                    SELECT timestamp FROM media_infractions
                    WHERE user_id = ? AND guild_id = ? AND timestamp >= ?
                    ORDER BY timestamp DESC
                ''', (user_id, guild_id, cutoff_time))
            
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

    async def cleanup_old_infractions(self, max_age=86400):  # 24 hours
        """Clean up infractions older than max_age"""
        async with aiosqlite.connect('db/media.db') as db:
            # First create tables if they don't exist
            await db.execute('''
                CREATE TABLE IF NOT EXISTS media_infractions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    infraction_type TEXT NOT NULL,
                    timestamp REAL NOT NULL
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS media_channels (
                    guild_id INTEGER PRIMARY KEY,
                    channel_id INTEGER NOT NULL
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS media_bypass (
                    guild_id INTEGER,
                    user_id INTEGER,
                    PRIMARY KEY (guild_id, user_id)
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS media_role_bypass (
                    guild_id INTEGER,
                    role_id INTEGER,
                    PRIMARY KEY (guild_id, role_id)
                )
            ''')
            
            # Then clean up old infractions
            cutoff_time = time.time() - max_age
            await db.execute('DELETE FROM media_infractions WHERE timestamp < ?', (cutoff_time,))
            await db.commit()

    @commands.Cog.listener()
    async def on_ready(self):
        await self.cleanup_old_infractions()

    @commands.hybrid_group(name="media", help="Setup Media channel, Media channel will not allow users to send messages other than media files.", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def media(self, ctx):
        if ctx.subcommand_passed is None:
            await ctx.send_help(ctx.command)
            ctx.command.reset_cooldown(ctx)

    @media.command(name="setup", aliases=["set", "add"], help="Sets up a media-only channel for the server")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def setup(self, ctx, *, channel: discord.TextChannel):
        async with aiosqlite.connect('db/media.db') as db:
            async with db.execute('SELECT channel_id FROM media_channels WHERE guild_id = ?', (ctx.guild.id,)) as cursor:
                result = await cursor.fetchone()
                if result:
                    embed = discord.Embed(
                        title="<:feast_cross:1400143488695144609> Error",
                        description="A media channel is already set. Please remove it before setting a new one.",
                        color=0x006fb9
                    )
                    await ctx.reply(embed=embed)
                    return

            await db.execute('INSERT INTO media_channels (guild_id, channel_id) VALUES (?, ?)', (ctx.guild.id, channel.id))
            await db.commit()

        embed = discord.Embed(
            title="<:feast_tick:1400143469892210753> Success",
            description=f"Successfully set {channel.mention} as the media-only channel.",
            color=0x006fb9
        )
        embed.set_footer(text="Make sure to grant me \"Manage Messages\" permission for functioning of media channel.")
        await ctx.reply(embed=embed)

    @media.command(name="remove", aliases=["reset", "delete"], help="Removes the current media-only channel")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def remove(self, ctx):
        async with aiosqlite.connect('db/media.db') as db:
            async with db.execute('SELECT channel_id FROM media_channels WHERE guild_id = ?', (ctx.guild.id,)) as cursor:
                result = await cursor.fetchone()
                if not result:
                    embed = discord.Embed(
                        title="<:feast_cross:1400143488695144609> Error",
                        description="There is no media-only channel set for this server.",
                        color=0x006fb9
                    )
                    await ctx.reply(embed=embed)
                    return

            await db.execute('DELETE FROM media_channels WHERE guild_id = ?', (ctx.guild.id,))
            await db.commit()

        embed = discord.Embed(
            title="<:feast_tick:1400143469892210753> Success",
            description="Successfully removed the media-only channel.",
            color=0x006fb9
        )
        await ctx.reply(embed=embed)

    @media.command(name="config", aliases=["settings", "show"], help="Shows the configured media-only channel and bypass lists")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def config(self, ctx):
        async with aiosqlite.connect('db/media.db') as db:
            async with db.execute('SELECT channel_id FROM media_channels WHERE guild_id = ?', (ctx.guild.id,)) as cursor:
                channel_result = await cursor.fetchone()
                if not channel_result:
                    embed = discord.Embed(
                        title="<:feast_cross:1400143488695144609> Error",
                        description="There is no media-only channel set for this server.",
                        color=0x006fb9
                    )
                    await ctx.reply(embed=embed)
                    return
            
            # Get bypass counts
            async with db.execute('SELECT COUNT(*) FROM media_bypass WHERE guild_id = ?', (ctx.guild.id,)) as cursor:
                result = await cursor.fetchone()
                user_count = result[0] if result else 0
            
            async with db.execute('SELECT COUNT(*) FROM media_role_bypass WHERE guild_id = ?', (ctx.guild.id,)) as cursor:
                result = await cursor.fetchone()
                role_count = result[0] if result else 0

        channel = self.client.get_channel(channel_result[0])
        
        # Clean up deleted roles
        await self.cleanup_deleted_roles(ctx.guild.id)
        
        embed = discord.Embed(
            title="📸 Media Channel Configuration",
            color=0x006fb9
        )
        
        embed.add_field(
            name="📺 Media Channel", 
            value=f"{channel.mention}\n*Only media files are allowed*", 
            inline=False
        )
        
        embed.add_field(
            name="🔓 Bypass Summary",
            value=f"**Users:** {user_count}\n**Roles:** {role_count}",
            inline=True
        )
        
        if user_count > 0 or role_count > 0:
            embed.add_field(
                name="💡 Tip",
                value="Use `media bypass show` to see all bypassed users and roles",
                inline=True
            )
        
        embed.set_footer(text="Users with bypass can send messages without attachments in the media channel")
        await ctx.reply(embed=embed)

    @media.group(name="bypass", help="Add/Remove user to bypass in Media only channel, Bypassed users can send messages in Media channel.", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def bypass(self, ctx):
        if ctx.subcommand_passed is None:
            await ctx.send_help(ctx.command)
            ctx.command.reset_cooldown(ctx)

    @bypass.command(name="add", help="Adds a user to the bypass list")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def bypass_add(self, ctx, user: discord.Member):
        async with aiosqlite.connect('db/media.db') as db:
            async with db.execute('SELECT COUNT(*) FROM media_bypass WHERE guild_id = ?', (ctx.guild.id,)) as cursor:
                count = await cursor.fetchone()
                if count is not None and count[0] >= 25:
                    embed = discord.Embed(
                        title="<:feast_cross:1400143488695144609> Error",
                        description="The bypass list can only hold up to 25 users.",
                        color=0x006fb9
                    )
                    await ctx.reply(embed=embed)
                    return

            async with db.execute('SELECT 1 FROM media_bypass WHERE guild_id = ? AND user_id = ?', (ctx.guild.id, user.id)) as cursor:
                result = await cursor.fetchone()
                if result:
                    embed = discord.Embed(
                        title="<:feast_cross:1400143488695144609> Error",
                        description=f"{user.mention} is already in the bypass list.",
                        color=0x006fb9
                    )
                    await ctx.reply(embed=embed)
                    return

            await db.execute('INSERT INTO media_bypass (guild_id, user_id) VALUES (?, ?)', (ctx.guild.id, user.id))
            await db.commit()

        embed = discord.Embed(
            title="<:feast_tick:1400143469892210753> Success",
            description=f"{user.mention} has been added to the bypass list.",
            color=0x006fb9
        )
        await ctx.reply(embed=embed)

    @bypass.command(name="remove", help="Removes a user from the bypass list")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def bypass_remove(self, ctx, user: discord.Member):
        async with aiosqlite.connect('db/media.db') as db:
            async with db.execute('SELECT 1 FROM media_bypass WHERE guild_id = ? AND user_id = ?', (ctx.guild.id, user.id)) as cursor:
                result = await cursor.fetchone()
                if not result:
                    embed = discord.Embed(
                        title="<:feast_cross:1400143488695144609> Error",
                        description=f"{user.mention} is not in the bypass list.",
                        color=0x006fb9
                    )
                    await ctx.reply(embed=embed)
                    return

            await db.execute('DELETE FROM media_bypass WHERE guild_id = ? AND user_id = ?', (ctx.guild.id, user.id))
            await db.commit()

        embed = discord.Embed(
            title="<:feast_tick:1400143469892210753> Success",
            description=f"{user.mention} has been removed from the bypass list.",
            color=0x006fb9
        )
        await ctx.reply(embed=embed)

    @bypass.command(name="show", aliases=["list", "view"], help="Shows the bypass list")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def bypass_show(self, ctx):
        async with aiosqlite.connect('db/media.db') as db:
            # Get users
            async with db.execute('SELECT user_id FROM media_bypass WHERE guild_id = ?', (ctx.guild.id,)) as cursor:
                user_result = await cursor.fetchall()
            
            # Get roles  
            async with db.execute('SELECT role_id FROM media_role_bypass WHERE guild_id = ?', (ctx.guild.id,)) as cursor:
                role_result = await cursor.fetchall()
            
            if not user_result and not role_result:
                embed = discord.Embed(
                    title="Media Channel Bypass List",
                    description="There are no users or roles in the bypass list.",
                    color=0x006fb9
                )
                await ctx.reply(embed=embed)
                return

        embed = discord.Embed(
            title="Media Channel Bypass List",
            description="Users and roles that can send messages in media channels:",
            color=0x006fb9
        )

        # Add users section
        if user_result:
            users = []
            for user_id, in user_result:
                user = self.client.get_user(user_id)
                if user:
                    users.append(user.mention)
                else:
                    users.append(f"~~<@{user_id}>~~ *(user left)*")
            
            user_mentions = "\n".join(users)
            embed.add_field(name="👤 Bypassed Users", value=user_mentions, inline=False)

        # Add roles section
        if role_result:
            roles = []
            for role_id, in role_result:
                role = ctx.guild.get_role(role_id)
                if role:
                    roles.append(role.mention)
                else:
                    roles.append(f"~~<@&{role_id}>~~ *(deleted role)*")
            
            role_mentions = "\n".join(roles)
            embed.add_field(name="👥 Bypassed Roles", value=role_mentions, inline=False)

        embed.set_footer(text="💡 Use 'media bypass role-add <role>' to add roles or 'media bypass add <user>' to add users")
        await ctx.reply(embed=embed)

    @bypass.command(name="role-add", aliases=["addrole", "role_add"], help="Adds a role to the bypass list - users with this role can send messages in media channels")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def bypass_role_add(self, ctx, role: discord.Role):
        async with aiosqlite.connect('db/media.db') as db:
            # Check current role count
            async with db.execute('SELECT COUNT(*) FROM media_role_bypass WHERE guild_id = ?', (ctx.guild.id,)) as cursor:
                count = await cursor.fetchone()
                if count and count[0] >= 10:  # Limit to 10 roles
                    embed = discord.Embed(
                        title="<:feast_cross:1400143488695144609> Error",
                        description="The role bypass list can only hold up to 10 roles.",
                        color=0x006fb9
                    )
                    await ctx.reply(embed=embed)
                    return

            # Check if role is already in bypass list
            async with db.execute('SELECT 1 FROM media_role_bypass WHERE guild_id = ? AND role_id = ?', (ctx.guild.id, role.id)) as cursor:
                result = await cursor.fetchone()
                if result:
                    embed = discord.Embed(
                        title="<:feast_cross:1400143488695144609> Error",
                        description=f"{role.mention} is already in the role bypass list.",
                        color=0x006fb9
                    )
                    await ctx.reply(embed=embed)
                    return

            await db.execute('INSERT INTO media_role_bypass (guild_id, role_id) VALUES (?, ?)', (ctx.guild.id, role.id))
            await db.commit()

        embed = discord.Embed(
            title="<:feast_tick:1400143469892210753> Success",
            description=f"Role {role.mention} has been added to the bypass list. Users with this role can now send messages in media channels.",
            color=0x006fb9
        )
        await ctx.reply(embed=embed)

    @bypass.command(name="role-remove", aliases=["removerole", "role_remove"], help="Removes a role from the bypass list")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def bypass_role_remove(self, ctx, role: discord.Role):
        async with aiosqlite.connect('db/media.db') as db:
            async with db.execute('SELECT 1 FROM media_role_bypass WHERE guild_id = ? AND role_id = ?', (ctx.guild.id, role.id)) as cursor:
                result = await cursor.fetchone()
                if not result:
                    embed = discord.Embed(
                        title="<:feast_cross:1400143488695144609> Error",
                        description=f"{role.mention} is not in the role bypass list.",
                        color=0x006fb9
                    )
                    await ctx.reply(embed=embed)
                    return

            await db.execute('DELETE FROM media_role_bypass WHERE guild_id = ? AND role_id = ?', (ctx.guild.id, role.id))
            await db.commit()

        embed = discord.Embed(
            title="<:feast_tick:1400143469892210753> Success",
            description=f"Role {role.mention} has been removed from the bypass list.",
            color=0x006fb9
        )
        await ctx.reply(embed=embed)

    @bypass.command(name="roles", aliases=["role-list", "rolelist", "showroles"], help="Shows the role bypass list")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def bypass_roles_show(self, ctx):
        async with aiosqlite.connect('db/media.db') as db:
            async with db.execute('SELECT role_id FROM media_role_bypass WHERE guild_id = ?', (ctx.guild.id,)) as cursor:
                result = await cursor.fetchall()
                if not result:
                    embed = discord.Embed(
                        title="Role Bypass List",
                        description="There are no roles in the bypass list.",
                        color=0x006fb9
                    )
                    await ctx.reply(embed=embed)
                    return

        # Get role mentions, handle deleted roles gracefully
        roles = []
        for role_id, in result:
            role = ctx.guild.get_role(role_id)
            if role:
                roles.append(role.mention)
            else:
                roles.append(f"~~<@&{role_id}>~~ *(deleted role)*")
        
        role_mentions = "\n".join(roles)

        embed = discord.Embed(
            title="Role Bypass List",
            description=f"**Roles that can send messages in media channels:**\n{role_mentions}",
            color=0x006fb9
        )
        await ctx.reply(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        # Ignore direct messages
        if message.guild is None:
            return

        async with aiosqlite.connect('db/media.db') as db:
            async with db.execute('SELECT channel_id FROM media_channels WHERE guild_id = ?', (message.guild.id,)) as cursor:
                media_channel = await cursor.fetchone()

        if media_channel and message.channel.id == media_channel[0]:
            async with aiosqlite.connect('db/block.db') as block_db:
                async with block_db.execute('SELECT 1 FROM user_blacklist WHERE user_id = ?', (message.author.id,)) as cursor:
                    blacklisted = await cursor.fetchone()

            async with aiosqlite.connect('db/media.db') as db:
                # Check user bypass
                async with db.execute('SELECT 1 FROM media_bypass WHERE guild_id = ? AND user_id = ?', (message.guild.id, message.author.id)) as cursor:
                    user_bypassed = await cursor.fetchone()
                
                # Check role bypass
                role_bypassed = False
                if not user_bypassed:
                    user_role_ids = [role.id for role in message.author.roles]
                    if user_role_ids:
                        placeholders = ','.join('?' * len(user_role_ids))
                        query = f'SELECT 1 FROM media_role_bypass WHERE guild_id = ? AND role_id IN ({placeholders})'
                        params = [message.guild.id] + user_role_ids
                        async with db.execute(query, params) as cursor:
                            role_bypassed = await cursor.fetchone()

            if blacklisted or user_bypassed or role_bypassed:
                return

            if not message.attachments:
                try:
                    await message.delete()
                    await message.channel.send(f"{message.author.mention} This channel is configured for Media only. Please send only media files.",
                    delete_after=5
                )
                except discord.Forbidden:
                    pass
                except discord.HTTPException:
                    pass
                except Exception:
                    pass

                current_time = time.time()
                await self.save_infraction(message.author.id, message.guild.id, 'media_spam', current_time)

                # Get recent infractions within 5 seconds
                recent_infractions = await self.get_user_infractions(
                    message.author.id, 
                    message.guild.id, 
                    'media_spam', 
                    time_window=5
                )

                if len(recent_infractions) >= 5:  
                    async with aiosqlite.connect('db/block.db') as block_db:
                        await block_db.execute('INSERT OR IGNORE INTO user_blacklist (user_id) VALUES (?)', (message.author.id,))
                        
                        await block_db.commit()

                    embed = discord.Embed(
                        title="You Have Been Blacklisted",
                        description=(
                            "<:feast_warning:1400143131990560830> You are blacklisted from using my commands due to spamming in the media channel. "
                            "If you believe this is a mistake, please reach out to the support server with proof."
                        ),
                        color=0x006fb9
                    )
                    await message.channel.send(f"{message.author.mention}", embed=embed)

"""
@Author: Frosty
    + Discord: frosty.pyro
    + Community: https://discord.gg/5wtjDkYbVh (Sleepless Development)
    + for any queries reach out in the server; or send a dm.
"""