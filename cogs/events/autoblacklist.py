import discord
from core import sleepless, Cog
from discord.ext import commands
import aiosqlite
from datetime import datetime, timedelta
from utils.timezone_helpers import get_timezone_helpers

class AutoBlacklist(Cog):
    def __init__(self, client: sleepless):
        self.client = client
        self.tz_helpers = get_timezone_helpers(client)
        self.spam_cd_mapping = commands.CooldownMapping.from_cooldown(5, 5, commands.BucketType.member)
        self.spam_command_mapping = commands.CooldownMapping.from_cooldown(15, 30, commands.BucketType.member)  # Much more lenient
        self.last_spam = {}
        self.spam_threshold = 20  # Increased from 5 to 20
        self.spam_window = timedelta(minutes=30)  # Increased from 10 to 30 minutes
        self.db_path = 'db/block.db'
        self.bot_user_id = self.client.user.id if self.client.user else None
        self.guild_command_tracking = {}
        
        # More aggressive thresholds - only for extreme abuse
        self.guild_message_threshold = 50  # 50 messages in 10 seconds (way more lenient)
        self.guild_message_window = timedelta(seconds=10)  

    async def add_to_blacklist(self, user_id=None, guild_id=None, channel=None):
        try:
            async with aiosqlite.connect(self.db_path) as db:
                timestamp = self.tz_helpers.get_utc_now()
                if guild_id:
                    await db.execute('''
                        INSERT OR IGNORE INTO guild_blacklist (guild_id, timestamp) VALUES (?, ?)
                    ''', (guild_id, timestamp))
                    if channel:
                        embed = discord.Embed(
                            title="<:feast_warning:1400143131990560830> Guild Blacklisted",
                            description=(
                                f"This guild has been blacklisted due to spamming or automation. "
                                f"If you believe this is a mistake, please contact our [Support Server](https://discord.gg/5wtjDkYbVh) with any proof if possible."
                            ),
                            color=0x006fb9
                        )
                        await channel.send(embed=embed)
                elif user_id:
                    await db.execute('''
                        INSERT OR IGNORE INTO user_blacklist (user_id, blacklisted_at) VALUES (?, ?)
                    ''', (user_id, timestamp))
                await db.commit()
        except aiosqlite.Error as e:
            print(f"Database error: {e}")

    async def check_and_blacklist_guild(self, guild_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                '''
                SELECT COUNT(DISTINCT user_id) FROM user_blacklist 
                WHERE timestamp >= ?
                ''', 
                (self.tz_helpers.get_utc_now() - self.spam_window,)
            ) as cursor:
                count = await cursor.fetchone()
                if count is not None and count[0] is not None and count[0] >= self.spam_threshold:
                    async with db.execute('SELECT channel_id FROM guild_settings WHERE guild_id = ?', (guild_id,)) as cursor:
                        channel_id = await cursor.fetchone()
                        if channel_id:
                            channel = self.client.get_channel(channel_id[0])
                            if channel:
                                await self.add_to_blacklist(None, guild_id, channel)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        
        # Only track messages that could indicate spam/abuse
        # Skip normal conversation messages
        if not message.content:
            return
            
        # Only track if message looks like bot mentions or potential spam patterns
        is_bot_mention = self.bot_user_id and (
            f'<@{self.bot_user_id}>' in message.content or 
            f'<@!{self.bot_user_id}>' in message.content
        )
        
        # Track guild-level activity only for bot mentions or rapid repeated messages
        guild_id = message.guild.id if message.guild else None
        if guild_id and is_bot_mention:
            if guild_id not in self.guild_command_tracking:
                self.guild_command_tracking[guild_id] = []

            self.guild_command_tracking[guild_id].append(self.tz_helpers.get_utc_now())

            # Clean old timestamps - use the new window
            self.guild_command_tracking[guild_id] = [
                timestamp for timestamp in self.guild_command_tracking[guild_id] 
                if timestamp >= self.tz_helpers.get_utc_now() - self.guild_message_window
            ]

            # Only blacklist if there are an EXTREME number of bot mentions
            if len(self.guild_command_tracking[guild_id]) > self.guild_message_threshold:
                await self.add_to_blacklist(guild_id=guild_id, channel=message.channel)
                embed = discord.Embed(
                    title="<:feast_warning:1400143131990560830> Guild Blacklisted",
                    description=(
                        f"The guild has been blacklisted for excessive bot mentions/spam. "
                        f"If you believe this is a mistake, please contact our [Support Server](https://discord.gg/5wtjDkYbVh)."
                    ),
                    color=0x006fb9
                )
                try:
                    await message.channel.send(embed=embed)
                except:
                    pass  # Ignore if we can't send the message
                return

        # Individual user spam detection (much more lenient)
        bucket = self.spam_cd_mapping.get_bucket(message)
        retry = bucket.update_rate_limit() if bucket is not None else None

        if retry and is_bot_mention:  # Only trigger on bot mentions, not regular messages
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('SELECT user_id FROM user_blacklist WHERE user_id = ?', (message.author.id,)) as cursor:
                    if await cursor.fetchone():
                        return

                # Only blacklist after repeated bot mentions
                if message.content in (f'<@{self.bot_user_id}>', f'<@!{self.bot_user_id}>'):
                    if message.author.id not in self.last_spam:
                        self.last_spam[message.author.id] = []
                    self.last_spam[message.author.id].append(self.tz_helpers.get_utc_now())
                    recent_spam = [timestamp for timestamp in self.last_spam.get(message.author.id, []) if timestamp >= self.tz_helpers.get_utc_now() - self.spam_window]
                    self.last_spam[message.author.id] = recent_spam
                    
                    # Only blacklist after many bot mentions
                    if len(recent_spam) >= self.spam_threshold:
                        await self.add_to_blacklist(user_id=message.author.id)
                        embed = discord.Embed(
                            title="<:feast_warning:1400143131990560830> User Blacklisted",
                            description=f"**{message.author.mention} has been blacklisted for repeatedly mentioning me. If you believe this is a mistake, please contact our [Support Server](https://discord.gg/5wtjDkYbVh) with any proof if possible.**",
                            color=0x006fb9
                        )
                        try:
                            await message.channel.send(embed=embed)
                        except:
                            pass  # Ignore if we can't send the message
                        
                        # Check for guild blacklist after user blacklist
                        if message.guild and len(recent_spam) >= self.spam_threshold:
                            await self.check_and_blacklist_guild(message.guild.id)

    @commands.Cog.listener()
    async def on_command(self, ctx):
        if ctx.author.bot:
            return

        bucket = self.spam_command_mapping.get_bucket(ctx.message)
        retry = bucket.update_rate_limit() if bucket is not None else None

        if retry:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('SELECT user_id FROM user_blacklist WHERE user_id = ?', (ctx.author.id,)) as cursor:
                    if await cursor.fetchone():
                        return

                # Add warning before blacklisting - give users a chance
                embed = discord.Embed(
                    title="⚠️ Command Spam Warning",
                    description=f"**{ctx.author.mention}**, you're sending commands too quickly! Please slow down or you may be temporarily blacklisted.",
                    color=0xff9900
                )
                try:
                    await ctx.reply(embed=embed)
                except:
                    pass
                
                # Track command spam - only blacklist after multiple warnings
                if ctx.author.id not in self.last_spam:
                    self.last_spam[ctx.author.id] = []
                self.last_spam[ctx.author.id].append(self.tz_helpers.get_utc_now())
                recent_command_spam = [timestamp for timestamp in self.last_spam.get(ctx.author.id, []) if timestamp >= self.tz_helpers.get_utc_now() - timedelta(minutes=5)]
                self.last_spam[ctx.author.id] = recent_command_spam
                
                # Only blacklist after multiple command spam incidents
                if len(recent_command_spam) >= 5:  # 5 warnings within 5 minutes
                    await self.add_to_blacklist(user_id=ctx.author.id)
                    embed = discord.Embed(
                        title="<:feast_warning:1400143131990560830> User Blacklisted",
                        description=f"**{ctx.author.mention} has been blacklisted for spamming commands. If you believe this is a mistake, please contact our [Support Server](https://discord.gg/5wtjDkYbVh) with any proof if possible.**",
                        color=0x006fb9
                    )
                    try:
                        await ctx.reply(embed=embed)
                    except:
                        pass

    @commands.command(name="unblacklist")
    @commands.is_owner()
    async def unblacklist(self, ctx, guild_id: int = 0):
        """Remove a guild from the blacklist (Owner only)"""
        if guild_id == 0 and ctx.guild:
            guild_id = ctx.guild.id
        elif guild_id == 0:
            return await ctx.send("Please provide a guild ID or use this command in a server.")
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Remove from guild blacklist
                await db.execute("DELETE FROM guild_blacklist WHERE guild_id = ?", (str(guild_id),))
                await db.commit()
            
            embed = discord.Embed(
                title="✅ Guild Unblacklisted",
                description=f"Guild ID {guild_id} has been removed from the blacklist.",
                color=0x00ff00
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"Error removing guild from blacklist: {str(e)}")

    @commands.command(name="blacklist_status")
    @commands.is_owner()  
    async def blacklist_status(self, ctx):
        """Check blacklist status and settings (Owner only)"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Count users and guilds
                async with db.execute("SELECT COUNT(*) FROM user_blacklist") as cursor:
                    user_count = await cursor.fetchone()
                async with db.execute("SELECT COUNT(*) FROM guild_blacklist") as cursor:
                    guild_count = await cursor.fetchone()
            
            embed = discord.Embed(
                title="🛡️ Blacklist Status",
                color=0x0099ff
            )
            embed.add_field(name="Blacklisted Users", value=user_count[0] if user_count else 0, inline=True)
            embed.add_field(name="Blacklisted Guilds", value=guild_count[0] if guild_count else 0, inline=True)
            embed.add_field(name="Spam Threshold", value=f"{self.spam_threshold} mentions in {self.spam_window.total_seconds()/60:.0f}m", inline=False)
            embed.add_field(name="Guild Message Threshold", value=f"{self.guild_message_threshold} mentions in {self.guild_message_window.total_seconds()}s", inline=False)
            embed.add_field(name="Command Cooldown", value="15 commands per 30s", inline=False)
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"Error checking blacklist status: {str(e)}")
