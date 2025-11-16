from utils.error_helpers import StandardErrorHandler
# Extension loader for Discord.py
async def setup(bot):
    await bot.add_cog(Unwhitelist(bot))
import discord
from discord.ext import commands
import aiosqlite
from utils.Tools import *
from typing import Optional


class Unwhitelist(commands.Cog):
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot
        # Removed loop access from __init__

    async def setup_hook(self):
        """Called when the cog is loaded"""
        await self.initialize_db()

    #@commands.Cog.listener()
    async def initialize_db(self):
        self.db = await aiosqlite.connect('db/anti.db')
    
    async def log_whitelist_action(self, guild_id: int, target_id: int, target_type: str, 
                                   actor_id: int, action: str, permissions: Optional[str] = None, reason: Optional[str] = None):
        """Log whitelist add/remove actions to audit log"""
        import time
        try:
            if self.db is not None:
                await self.db.execute('''
                    INSERT INTO whitelist_audit_log 
                    (guild_id, target_id, target_type, actor_id, action, permissions, reason, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (guild_id, target_id, target_type, actor_id, action, permissions, reason, int(time.time())))
                await self.db.commit()
        except Exception as e:
            print(f"Error logging whitelist action: {e}")

    @commands.hybrid_command(name='unwhitelist', aliases=['unwl'], help="Unwhitelist a user from antinuke")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def unwhitelist(self, ctx, member: Optional[discord.Member] = None):
        if ctx.guild.member_count < 2:
            embed = discord.Embed(
                color=0x08ff00,
                description="<:feast_cross:1400143488695144609> | Your Server Doesn't Meet My 30 Member Criteria"
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
                color=0x08ff00,
                description="Only Server Owner or Extra Owner can Run this Command!"
            )
            return await ctx.send(embed=embed)

        if not antinuke or not antinuke[0]:
            embed = discord.Embed(
                color=0x08ff00,
                description=(
                    f"**{ctx.guild.name} Security Settings <:mod:1327845044182585407>\n"
                    "Ohh NO! looks like your server doesn't enabled security\n\n"
                    "Current Status : <a:disabled1:1329022921427128321>\n\n"
                    "To enable use `antinuke enable` **"
                )
            )
            return await ctx.send(embed=embed)

        if not member:
            embed = discord.Embed(
                color=0x08ff00,
                title="__**Unwhitelist Commands**__",
                description="**Removes user from whitelisted users which means that the antinuke module will now take actions on them if they trigger it.**"
            )
            embed.add_field(name="__**Usage**__", value="<:red_dot:1222796144996777995> `unwhitelist @user/id`\n<:red_dot:1222796144996777995> `unwl @user`")
            return await ctx.send(embed=embed)

        async with self.db.execute(
            "SELECT * FROM whitelisted_users WHERE guild_id = ? AND user_id = ?",
            (ctx.guild.id, member.id)
        ) as cursor:
            data = await cursor.fetchone()

        if not data:
            embed = discord.Embed(title="<:feast_cross:1400143488695144609> Error",
                color=0x006fb9,
                description=f"<@{member.id}> is not a whitelisted member."
            )
            return await ctx.send(embed=embed)

        await self.db.execute(
            "DELETE FROM whitelisted_users WHERE guild_id = ? AND user_id = ?",
            (ctx.guild.id, member.id)
        )
        await self.db.commit()
        
        # Log the whitelist remove action
        await self.log_whitelist_action(
            guild_id=ctx.guild.id,
            target_id=member.id,
            target_type="user",
            actor_id=ctx.author.id,
            action="remove",
            reason="User removed from whitelist"
        )

        embed = discord.Embed(title="<:feast_tick:1400143469892210753> Success",
            color=0x006fb9,
            description=f"User <@!{member.id}> has been removed from the whitelist."
        )
        await ctx.send(embed=embed)


"""
@Author: Frosty
    + Discord: frosty.pyro
    + Community: https://discord.gg/5wtjDkYbVh (Sleepless Development)
    + for any queries reach out in the server; or send a dm.
"""