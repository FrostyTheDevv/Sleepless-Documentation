import discord, random, asyncio, datetime, logging, aiosqlite
from discord.ext import commands, tasks
from discord.utils import get
from typing import Optional
from utils.timezone_helpers import get_timezone_helpers

from utils.error_helpers import StandardErrorHandler
db_path = "db/giveaways.db"

class Giveaway(commands.Cog):
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot
        self.tz_helpers = get_timezone_helpers(bot)

    async def cog_load(self) -> None:
        self.connection = await aiosqlite.connect(db_path)
        self.cursor = await self.connection.cursor()
        await self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS Giveaway (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                host_id INTEGER,
                start_time TEXT,
                ends_at TEXT,
                prize TEXT,
                winners INTEGER,
                message_id INTEGER,
                channel_id INTEGER
            )
        """)
        
        # Create giveaway permissions table
        await self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS giveaway_permissions (
                guild_id INTEGER PRIMARY KEY,
                allowed_roles TEXT DEFAULT '[]',
                allowed_users TEXT DEFAULT '[]',
                admin_only INTEGER DEFAULT 1
            )
        """)
        await self.connection.commit()
        await self.check_for_ended_giveaways()
        self.giveaway_task.start()

    async def cog_unload(self) -> None:
        self.giveaway_task.stop()
        await self.connection.close()
    
    async def can_manage_giveaways(self, ctx):
        """Check if user can manage giveaways"""
        # Guild owner always can
        if ctx.author == ctx.guild.owner:
            return True
            
        # Administrator permission always works
        if ctx.author.guild_permissions.administrator:
            return True
            
        # Check custom permissions from database
        await self.cursor.execute(
            "SELECT allowed_roles, allowed_users, admin_only FROM giveaway_permissions WHERE guild_id = ?",
            (ctx.guild.id,)
        )
        result = await self.cursor.fetchone()
        
        if not result:
            # Default: admin only
            return False
            
        allowed_roles_json, allowed_users_json, admin_only = result
        
        # Check if user is in allowed users list
        import json
        try:
            allowed_users = json.loads(allowed_users_json or '[]')
            if ctx.author.id in allowed_users:
                return True
        except:
            pass
            
        # Check if user has any allowed roles
        try:
            allowed_roles = json.loads(allowed_roles_json or '[]')
            user_role_ids = [role.id for role in ctx.author.roles]
            if any(role_id in user_role_ids for role_id in allowed_roles):
                return True
        except:
            pass
        
        # If admin_only is enabled and user isn't admin and doesn't have explicit permissions
        if admin_only:
            return False
            
        return False

    # ---- Time converter ----
    def convert(self, time: str) -> int:
        pos = ["s", "m", "h", "d"]
        time_dict = {"s": 1, "m": 60, "h": 3600, "d": 86400}

        unit = time[-1]
        if unit not in pos:
            return -1
        try:
            val = int(time[:-1])
        except ValueError:
            return -2
        return val * time_dict[unit]

    # ---- Giveaway ending checks ----
    async def check_for_ended_giveaways(self):
        await self.cursor.execute(
            "SELECT ends_at, guild_id, message_id, host_id, winners, prize, channel_id "
            "FROM Giveaway WHERE ends_at <= ?", 
            (self.tz_helpers.get_utc_now().timestamp(),)
        )
        ended = await self.cursor.fetchall()
        for g in ended:
            await self.end_giveaway(g)

    async def end_giveaway(self, giveaway):
        try:
            current_time = datetime.datetime.now(datetime.timezone.utc).timestamp()
            guild = self.bot.get_guild(int(giveaway[1]))
            if guild is None:
                await self.cursor.execute("DELETE FROM Giveaway WHERE message_id = ? AND guild_id = ?", (giveaway[2], giveaway[1]))
                await self.connection.commit()
                return

            channel = self.bot.get_channel(int(giveaway[6]))
            if not channel:
                return

            try:
                message = await channel.fetch_message(int(giveaway[2]))
            except discord.NotFound:
                await self.cursor.execute("DELETE FROM Giveaway WHERE message_id = ? AND guild_id = ?", (giveaway[2], giveaway[1]))
                await self.connection.commit()
                return

            # get participants from 🎉 reaction
            users = []
            for reaction in message.reactions:
                if str(reaction.emoji) == "<:feast_tada:1400157685118406656>":
                    users = [u.id async for u in reaction.users()]
            if self.bot.user.id in users:
                users.remove(self.bot.user.id)

            if not users:
                await message.reply(f"No one won the **{giveaway[5]}** giveaway, not enough participants.")
                await self.cursor.execute("DELETE FROM Giveaway WHERE message_id = ? AND guild_id = ?", (message.id, message.guild.id))
                await self.connection.commit()
                return

            winners_count = min(len(users), int(giveaway[4]))
            winner = ', '.join(f'<@{i}>' for i in random.sample(users, k=winners_count))

            embed = discord.Embed(
                title=f"{giveaway[5]}",
                description=f"Ended <t:{int(current_time)}:R>\nHosted by <@{int(giveaway[3])}>\nWinner(s): {winner}",
                color=0x006fb9
            )
            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            embed.set_footer(text="Ended")

            await message.edit(content="<:feast_gwy:1400134863058898976> **GIVEAWAY ENDED** <:feast_gwy:1400134863058898976>", embed=embed)
            await message.reply(f"<:feast_tada:1400157685118406656> Congrats {winner}, you won **{giveaway[5]}!**")

            await self.cursor.execute("DELETE FROM Giveaway WHERE message_id = ? AND guild_id = ?", (message.id, message.guild.id))
            await self.connection.commit()

        except Exception as e:
            logging.error(f"Error ending giveaway: {e}")

    @tasks.loop(seconds=5)
    async def giveaway_task(self):
        await self.cursor.execute(
            "SELECT ends_at, guild_id, message_id, host_id, winners, prize, channel_id "
            "FROM Giveaway WHERE ends_at <= ?", 
            (self.tz_helpers.get_utc_now().timestamp(),)
        )
        ended = await self.cursor.fetchall()
        for g in ended:
            await self.end_giveaway(g)

    # ---- Commands ----
    @commands.group(name="giveaway", aliases=["gw"], invoke_without_command=True)
    async def giveaway(self, ctx):
        """Giveaway commands help"""
        embed = discord.Embed(
            title="🎉 Giveaway System",
            description="Complete giveaway management system with role-based permissions",
            color=0x006fb9
        )
        
        embed.add_field(
            name="🚀 **Basic Commands**",
            value=(
                "`gw start <time> <winners> <prize>` - Create a giveaway\n"
                "`gw end <message_id>` - End giveaway early\n"
                "`gw reroll <message_id>` - Reroll winners\n"
                "`gw list` - Show active giveaways"
            ),
            inline=False
        )
        
        embed.add_field(
            name="⚙️ **Permission Management** (Admin Only)",
            value=(
                "`gw role add <role>` - Grant role giveaway access\n"
                "`gw role remove <role>` - Remove role access\n"
                "`gw user add <user>` - Grant user giveaway access\n"
                "`gw user remove <user>` - Remove user access\n"
                "`gw adminonly <on/off>` - Toggle admin-only mode\n"
                "`gw config` - View current permissions"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📋 **Usage Examples**",
            value=(
                "• `gw start 1h 3 Discord Nitro` - 1 hour, 3 winners\n"
                "• `gw start 30m 1 $50 Steam Card` - 30 minutes, 1 winner\n"
                "• `gw role add @Booster` - Let boosters create giveaways\n"
                "• `gw adminonly off` - Allow configured users/roles"
            ),
            inline=False
        )
        
        embed.add_field(
            name="⏰ **Time Formats**",
            value="`10s` (seconds) • `5m` (minutes) • `2h` (hours) • `3d` (days)",
            inline=False
        )
        
        embed.set_footer(text="💡 Tip: Use 'gw' as a shortcut for all giveaway commands!")
        await ctx.send(embed=embed)

    @giveaway.command(name="start", aliases=["gstart"], description="Start a giveaway")
    async def gstart(self, ctx, time: Optional[str] = None, winners: Optional[int] = None, *, prize: Optional[str] = None):
        # Check permissions first
        if not await self.can_manage_giveaways(ctx):
            embed = discord.Embed(
                title="<:feast_cross:1400143488695144609> Permission Denied",
                description="You don't have permission to create giveaways. Only administrators or users with giveaway permissions can use this command.",
                color=0xff4757
            )
            return await ctx.reply(embed=embed)
        
        # Show help if no arguments provided
        if time is None:
            embed = discord.Embed(
                title="<:feast_gwy:1400134863058898976> Giveaway Start Command",
                description="""
                **Usage:** `gstart <time> <winners> <prize>`
                
                **Parameters:**
                • `time` - Duration of the giveaway
                • `winners` - Number of winners (max 15)
                • `prize` - What the winners will receive
                
                **Time formats:**
                • `10s` - 10 seconds
                • `5m` - 5 minutes  
                • `2h` - 2 hours
                • `3d` - 3 days
                
                **Example:**
                `gstart 1h 1 Discord Nitro`
                
                **Other giveaway commands:**
                • `gend <message_id>` - End a giveaway early
                • `greroll <message_id>` - Reroll a giveaway
                • `glist` - List ongoing giveaways
                """,
                color=0x006fb9
            )
            embed.set_footer(text="Need help? Use the examples above!")
            return await ctx.send(embed=embed)
        
        # Check if all required parameters are provided
        if winners is None or prize is None:
            return await ctx.send("<:feast_cross:1400143488695144609> Missing required parameters. Use `gstart` without arguments to see help.")
        
        converted = self.convert(time)
        if converted in (-1, -2):
            return await ctx.send("<:feast_cross:1400143488695144609> Invalid time format. Use `10s`, `5m`, `2h`, or `3d`.")

        if winners > 15:
            return await ctx.send("<:feast_cross:1400143488695144609> You can’t have more than 15 winners.")

        ends = self.tz_helpers.get_utc_now().timestamp() + converted
        embed = discord.Embed(
            title=f"{prize}",
            description=f"Winner(s): **{winners}**\nReact with <:feast_tada:1400157685118406656> to participate!\nEnds <t:{round(ends)}:R>\n\nHosted by {ctx.author.mention}",
            color=0x006fb9
        )
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        embed.set_footer(text="Ends at")

        msg = await ctx.send("<:feast_gwy:1400134863058898976> **GIVEAWAY** <:feast_gwy:1400134863058898976>", embed=embed)
        await msg.add_reaction("<:feast_tada:1400157685118406656>")

        await self.cursor.execute(
            "INSERT INTO Giveaway(guild_id, host_id, start_time, ends_at, prize, winners, message_id, channel_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (ctx.guild.id, ctx.author.id, self.tz_helpers.get_utc_now().timestamp(), ends, prize, winners, msg.id, ctx.channel.id)
        )
        await self.connection.commit()

    @giveaway.command(name="end", aliases=["gend"], description="End a giveaway early")
    async def gend(self, ctx, message_id: int):
        # Check permissions
        if not await self.can_manage_giveaways(ctx):
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="You don't have permission to manage giveaways.",
                color=0xff4757
            )
            return await ctx.send(embed=embed)
            
        await self.cursor.execute("SELECT * FROM Giveaway WHERE message_id = ?", (message_id,))
        g = await self.cursor.fetchone()
        if not g:
            return await ctx.send("❌ Giveaway not found.")
        await self.end_giveaway(g)
        await ctx.send("✅ Giveaway ended successfully!")

    @giveaway.command(name="reroll", aliases=["greroll"], description="Reroll a giveaway")
    async def greroll(self, ctx, message_id: int):
        # Check permissions
        if not await self.can_manage_giveaways(ctx):
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="You don't have permission to manage giveaways.",
                color=0xff4757
            )
            return await ctx.send(embed=embed)
            
        try:
            msg = await ctx.channel.fetch_message(message_id)
        except discord.NotFound:
            return await ctx.send("❌ Message not found.")

        users = []
        for reaction in msg.reactions:
            if str(reaction.emoji) == "<:feast_tada:1400157685118406656>":
                users = [u.id async for u in reaction.users()]
        if self.bot.user.id in users:
            users.remove(self.bot.user.id)

        if not users:
            return await ctx.send("❌ No participants to reroll.")

        winner = random.choice(users)
        await ctx.send(f"🎉 New winner: <@{winner}>! Congratulations!")

    @giveaway.command(name="list", aliases=["glist"], description="List ongoing giveaways")
    async def glist(self, ctx):
        await self.cursor.execute("SELECT prize, ends_at, winners, message_id, channel_id FROM Giveaway WHERE guild_id = ?", (ctx.guild.id,))
        giveaways = await self.cursor.fetchall()
        if not giveaways:
            return await ctx.send(embed=discord.Embed(description="No ongoing giveaways.", color=0x006fb9))

        embed = discord.Embed(title="Ongoing Giveaways", color=0x006fb9)
        for prize, ends_at, winners, msg_id, ch_id in giveaways:
            embed.add_field(
                name=prize,
                value=f"Ends: <t:{int(ends_at)}:R>\nWinners: {winners}\n[Jump to Message](https://discord.com/channels/{ctx.guild.id}/{ch_id}/{msg_id})",
                inline=False
            )
        await ctx.send(embed=embed)

    # ---- Giveaway Permission Management ----
    @giveaway.command(name="permissions", aliases=["perms"])
    @commands.has_permissions(administrator=True)
    async def giveaway_permissions(self, ctx):
        """Manage giveaway permissions"""
        embed = discord.Embed(
            title="<:feast_gwy:1400134863058898976> Giveaway Permissions",
            description="""
            **Permission Commands:**
            `giveaway role add <role>` - Add role that can create giveaways
            `giveaway role remove <role>` - Remove role permission
            `giveaway user add <user>` - Add user that can create giveaways
            `giveaway user remove <user>` - Remove user permission
            `giveaway adminonly <on/off>` - Toggle admin-only mode
            `giveaway config` - View current permissions
            
            **Note:** Server administrators always have giveaway permissions.
            """,
            color=0x006fb9
        )
        await ctx.send(embed=embed)

    @giveaway.group(name="role", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def giveaway_role(self, ctx):
        """Manage giveaway role permissions"""
        await ctx.send_help(ctx.command)

    @giveaway_role.command(name="add")
    @commands.has_permissions(administrator=True)
    async def giveaway_role_add(self, ctx, role: discord.Role):
        """Add a role that can create giveaways"""
        import json
        
        # Get current permissions
        await self.cursor.execute(
            "SELECT allowed_roles FROM giveaway_permissions WHERE guild_id = ?",
            (ctx.guild.id,)
        )
        result = await self.cursor.fetchone()
        
        if result:
            allowed_roles = json.loads(result[0] or '[]')
        else:
            allowed_roles = []
            
        if role.id not in allowed_roles:
            allowed_roles.append(role.id)
            
            # Update or insert
            await self.cursor.execute("""
                INSERT OR REPLACE INTO giveaway_permissions (guild_id, allowed_roles, allowed_users, admin_only)
                VALUES (?, ?, 
                    COALESCE((SELECT allowed_users FROM giveaway_permissions WHERE guild_id = ?), '[]'),
                    COALESCE((SELECT admin_only FROM giveaway_permissions WHERE guild_id = ?), 1))
            """, (ctx.guild.id, json.dumps(allowed_roles), ctx.guild.id, ctx.guild.id))
            await self.connection.commit()
            
            embed = discord.Embed(
                title="✅ Role Added",
                description=f"{role.mention} can now create giveaways.",
                color=0x00ff00
            )
        else:
            embed = discord.Embed(
                title="❌ Role Already Added",
                description=f"{role.mention} already has giveaway permissions.",
                color=0xff4757
            )
        await ctx.send(embed=embed)

    @giveaway_role.command(name="remove")
    @commands.has_permissions(administrator=True)
    async def giveaway_role_remove(self, ctx, role: discord.Role):
        """Remove giveaway permissions from a role"""
        import json
        
        await self.cursor.execute(
            "SELECT allowed_roles FROM giveaway_permissions WHERE guild_id = ?",
            (ctx.guild.id,)
        )
        result = await self.cursor.fetchone()
        
        if result:
            allowed_roles = json.loads(result[0] or '[]')
            if role.id in allowed_roles:
                allowed_roles.remove(role.id)
                
                await self.cursor.execute(
                    "UPDATE giveaway_permissions SET allowed_roles = ? WHERE guild_id = ?",
                    (json.dumps(allowed_roles), ctx.guild.id)
                )
                await self.connection.commit()
                
                embed = discord.Embed(
                    title="✅ Role Removed",
                    description=f"{role.mention} can no longer create giveaways.",
                    color=0x00ff00
                )
            else:
                embed = discord.Embed(
                    title="❌ Role Not Found",
                    description=f"{role.mention} doesn't have giveaway permissions.",
                    color=0xff4757
                )
        else:
            embed = discord.Embed(
                title="❌ No Permissions Set",
                description="No giveaway permissions are configured.",
                color=0xff4757
            )
        await ctx.send(embed=embed)

    @giveaway.group(name="user", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def giveaway_user(self, ctx):
        """Manage giveaway user permissions"""
        await ctx.send_help(ctx.command)

    @giveaway_user.command(name="add")
    @commands.has_permissions(administrator=True)
    async def giveaway_user_add(self, ctx, user: discord.Member):
        """Add a user that can create giveaways"""
        import json
        
        await self.cursor.execute(
            "SELECT allowed_users FROM giveaway_permissions WHERE guild_id = ?",
            (ctx.guild.id,)
        )
        result = await self.cursor.fetchone()
        
        if result:
            allowed_users = json.loads(result[0] or '[]')
        else:
            allowed_users = []
            
        if user.id not in allowed_users:
            allowed_users.append(user.id)
            
            await self.cursor.execute("""
                INSERT OR REPLACE INTO giveaway_permissions (guild_id, allowed_users, allowed_roles, admin_only)
                VALUES (?, ?, 
                    COALESCE((SELECT allowed_roles FROM giveaway_permissions WHERE guild_id = ?), '[]'),
                    COALESCE((SELECT admin_only FROM giveaway_permissions WHERE guild_id = ?), 1))
            """, (ctx.guild.id, json.dumps(allowed_users), ctx.guild.id, ctx.guild.id))
            await self.connection.commit()
            
            embed = discord.Embed(
                title="✅ User Added",
                description=f"{user.mention} can now create giveaways.",
                color=0x00ff00
            )
        else:
            embed = discord.Embed(
                title="❌ User Already Added",
                description=f"{user.mention} already has giveaway permissions.",
                color=0xff4757
            )
        await ctx.send(embed=embed)

    @giveaway_user.command(name="remove")
    @commands.has_permissions(administrator=True)
    async def giveaway_user_remove(self, ctx, user: discord.Member):
        """Remove giveaway permissions from a user"""
        import json
        
        await self.cursor.execute(
            "SELECT allowed_users FROM giveaway_permissions WHERE guild_id = ?",
            (ctx.guild.id,)
        )
        result = await self.cursor.fetchone()
        
        if result:
            allowed_users = json.loads(result[0] or '[]')
            if user.id in allowed_users:
                allowed_users.remove(user.id)
                
                await self.cursor.execute(
                    "UPDATE giveaway_permissions SET allowed_users = ? WHERE guild_id = ?",
                    (json.dumps(allowed_users), ctx.guild.id)
                )
                await self.connection.commit()
                
                embed = discord.Embed(
                    title="✅ User Removed",
                    description=f"{user.mention} can no longer create giveaways.",
                    color=0x00ff00
                )
            else:
                embed = discord.Embed(
                    title="❌ User Not Found",
                    description=f"{user.mention} doesn't have giveaway permissions.",
                    color=0xff4757
                )
        else:
            embed = discord.Embed(
                title="❌ No Permissions Set",
                description="No giveaway permissions are configured.",
                color=0xff4757
            )
        await ctx.send(embed=embed)

    @giveaway.command(name="adminonly")
    @commands.has_permissions(administrator=True)
    async def giveaway_adminonly(self, ctx, setting: Optional[str] = None):
        """Toggle admin-only mode for giveaways"""
        if setting is None:
            await ctx.send("Usage: `giveaway adminonly <on/off>`")
            return
            
        setting = setting.lower()
        if setting not in ['on', 'off', 'true', 'false', '1', '0']:
            await ctx.send("Use `on` or `off` to toggle admin-only mode.")
            return
            
        admin_only = setting in ['on', 'true', '1']
        
        await self.cursor.execute("""
            INSERT OR REPLACE INTO giveaway_permissions (guild_id, admin_only, allowed_roles, allowed_users)
            VALUES (?, ?, 
                COALESCE((SELECT allowed_roles FROM giveaway_permissions WHERE guild_id = ?), '[]'),
                COALESCE((SELECT allowed_users FROM giveaway_permissions WHERE guild_id = ?), '[]'))
        """, (ctx.guild.id, int(admin_only), ctx.guild.id, ctx.guild.id))
        await self.connection.commit()
        
        status = "enabled" if admin_only else "disabled"
        embed = discord.Embed(
            title="✅ Admin-Only Mode Updated",
            description=f"Admin-only mode has been **{status}**.\n\n"
                       f"{'Only administrators can create giveaways.' if admin_only else 'Users with giveaway permissions can create giveaways.'}",
            color=0x00ff00
        )
        await ctx.send(embed=embed)

    @giveaway.command(name="config")
    @commands.has_permissions(administrator=True)
    async def giveaway_config(self, ctx):
        """View current giveaway permissions"""
        import json
        
        await self.cursor.execute(
            "SELECT allowed_roles, allowed_users, admin_only FROM giveaway_permissions WHERE guild_id = ?",
            (ctx.guild.id,)
        )
        result = await self.cursor.fetchone()
        
        embed = discord.Embed(
            title="<:feast_gwy:1400134863058898976> Giveaway Configuration",
            color=0x006fb9
        )
        
        if result:
            allowed_roles_json, allowed_users_json, admin_only = result
            allowed_roles = json.loads(allowed_roles_json or '[]')
            allowed_users = json.loads(allowed_users_json or '[]')
            
            embed.add_field(
                name="Admin-Only Mode",
                value="✅ Enabled" if admin_only else "❌ Disabled",
                inline=True
            )
            
            # Show allowed roles
            if allowed_roles:
                role_mentions = []
                for role_id in allowed_roles:
                    role = ctx.guild.get_role(role_id)
                    if role:
                        role_mentions.append(role.mention)
                embed.add_field(
                    name="Allowed Roles",
                    value="\n".join(role_mentions) if role_mentions else "None",
                    inline=False
                )
            else:
                embed.add_field(name="Allowed Roles", value="None", inline=False)
                
            # Show allowed users  
            if allowed_users:
                user_mentions = []
                for user_id in allowed_users:
                    user = ctx.guild.get_member(user_id)
                    if user:
                        user_mentions.append(user.mention)
                embed.add_field(
                    name="Allowed Users",
                    value="\n".join(user_mentions) if user_mentions else "None",
                    inline=False
                )
            else:
                embed.add_field(name="Allowed Users", value="None", inline=False)
        else:
            embed.add_field(
                name="Status",
                value="No permissions configured. Only administrators can create giveaways.",
                inline=False
            )
            
        await ctx.send(embed=embed)

    # Legacy standalone commands for backward compatibility
    @commands.command(name="gstart", description="Start a giveaway (legacy)")
    async def gstart_legacy(self, ctx, time: Optional[str] = None, winners: Optional[int] = None, *, prize: Optional[str] = None):
        """Legacy gstart command - redirects to gw start"""
        await self.gstart(ctx, time, winners, prize=prize)

    @commands.command(name="gend", description="End a giveaway (legacy)")  
    async def gend_legacy(self, ctx, message_id: int):
        """Legacy gend command - redirects to gw end"""
        await self.gend(ctx, message_id)

    @commands.command(name="greroll", description="Reroll a giveaway (legacy)")
    async def greroll_legacy(self, ctx, message_id: int):
        """Legacy greroll command - redirects to gw reroll"""
        await self.greroll(ctx, message_id)

    @commands.command(name="glist", description="List giveaways (legacy)")
    async def glist_legacy(self, ctx):
        """Legacy glist command - redirects to gw list"""
        await self.glist(ctx)
       
async def setup(bot):
    await bot.add_cog(Giveaway(bot))


