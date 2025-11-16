import discord
from discord.ext import commands
import sqlite3
import time
from datetime import datetime
from utils.timezone_helpers import get_timezone_helpers

from utils.error_helpers import StandardErrorHandler
DB_FILE = "logging.db"

# Rate limiting for logging events to prevent spam
LOG_COOLDOWNS = {}  # {(guild_id, log_type): last_sent_time}
LOG_COOLDOWN_SECONDS = 10  # Minimum seconds between similar log events
POSITION_CHANGE_COOLDOWNS = {}  # {guild_id: last_position_log_time}
POSITION_CHANGE_COOLDOWN = 30  # 30 seconds between position change logs

LOG_CHANNELS = {
    "channel-logs": "channel",
    "mod-logs": "mod", 
    "message-logs": "message",
    "role-logs": "role",
    "guild-logs": "guild",
    "invite-logs": "invite",
    "webhook-logs": "webhook",
    "emoji-logs": "emoji",
    "member-logs": "member",
    "voice-logs": "voice",
    "server-logs": "server",
    "punishment-logs": "punishment",
    "automod-logs": "automod",
    "thread-logs": "thread",
    "reaction-logs": "reaction",
    "nickname-logs": "nickname",
    "avatar-logs": "avatar",
    "boost-logs": "boost"
}

class Logging(commands.Cog):
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot
        self.db_path = DB_FILE
        self.tz_helpers = get_timezone_helpers(bot)
        self.create_table()

    def create_table(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS log_channels (
                    guild_id INTEGER,
                    log_type TEXT,
                    channel_id INTEGER
                )
            """)

    def set_log_channel(self, guild_id, log_type, channel_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "REPLACE INTO log_channels (guild_id, log_type, channel_id) VALUES (?, ?, ?)",
                (guild_id, log_type, channel_id)
            )

    def get_log_channel(self, guild_id, log_type):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT channel_id FROM log_channels WHERE guild_id = ? AND log_type = ?",
                (guild_id, log_type)
            )
            result = cursor.fetchone()
            return result[0] if result else None

    async def send_log(self, guild, log_type, embed, bypass_cooldown=False):
        """Send log message with rate limiting to prevent spam"""
        embed.timestamp = self.tz_helpers.get_utc_now()
        channel_id = self.get_log_channel(guild.id, log_type)
        if not channel_id:
            return
            
        channel = guild.get_channel(channel_id)
        if not channel:
            return
            
        # Rate limiting check (unless bypassed)
        if not bypass_cooldown:
            current_time = time.time()
            cooldown_key = (guild.id, log_type)
            
            if cooldown_key in LOG_COOLDOWNS:
                if current_time - LOG_COOLDOWNS[cooldown_key] < LOG_COOLDOWN_SECONDS:
                    return  # Still in cooldown, skip this log
                    
            LOG_COOLDOWNS[cooldown_key] = current_time
        
        try:
            await channel.send(embed=embed)
        except discord.HTTPException as e:
            if e.status == 429:  # Rate limited
                print(f"[LOGGING] Rate limited in guild {guild.id}, log type {log_type}")
                # Increase cooldown for this guild/log type
                LOG_COOLDOWNS[(guild.id, log_type)] = time.time() + 60  # 1 minute penalty
            else:
                print(f"[LOGGING] HTTP error in guild {guild.id}: {e}")
        except Exception as e:
            print(f"[LOGGING] Error sending log: {e}")

    @commands.command(name="loggingsetup")
    @commands.has_permissions(administrator=True)
    async def setlogsetup(self, ctx):
        """Creates sleepless-logging category and log channels with private permissions"""
        guild = ctx.guild

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }

        category = discord.utils.get(guild.categories, name="sleepless-logging")
        if not category:
            category = await guild.create_category("sleepless-logging", overwrites=overwrites)

        for name, log_type in LOG_CHANNELS.items():
            channel = discord.utils.get(guild.text_channels, name=name)
            if not channel:
                channel = await guild.create_text_channel(name=name, category=category, overwrites=overwrites)
            self.set_log_channel(guild.id, log_type, channel.id)

        await ctx.send("✅ Logging channels created privately under 'sleepless-logging' category.")

    @commands.command(name="removelogs")
    @commands.has_permissions(administrator=True)
    async def removelogs(self, ctx):
        """Removes sleepless-logging channels and logging DB config"""
        guild = ctx.guild

        # Remove DB entries
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("DELETE FROM log_channels WHERE guild_id = ?", (guild.id,))
            conn.commit()

        # Delete channels and category
        category = discord.utils.get(guild.categories, name="sleepless-logging")
        if category:
            for channel in category.channels:
                await channel.delete()
            await category.delete()

        await ctx.send("🗑️ Logging channels and category 'sleepless-logging' have been removed.")

    # === Events ===

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.guild and not message.author.bot:
            embed = discord.Embed(title="🗑️ Message Deleted", color=discord.Color.red())
            embed.add_field(name="User", value=message.author.mention)
            embed.add_field(name="Channel", value=message.channel.mention)
            embed.add_field(name="Content", value=message.content or "None", inline=False)
            await self.send_log(message.guild, "message", embed)
            # Log message delete event
            try:
                from utils.activity_logger import ActivityLogger
                activity_logger = ActivityLogger()
                await activity_logger.log(
                    guild_id=message.guild.id,
                    user_id=message.author.id,
                    username=str(message.author),
                    action="Message Deleted",
                    type_="message",
                    details=f"Channel: {message.channel}, Content: {message.content or 'None'}"
                )
            except Exception as e:
                print(f"[ACTIVITY LOG] Failed to log message delete: {e}")

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.guild and not before.author.bot and before.content != after.content:
            embed = discord.Embed(title="✏️ Message Edited", color=discord.Color.orange())
            embed.add_field(name="User", value=before.author.mention)
            embed.add_field(name="Channel", value=before.channel.mention)
            embed.add_field(name="Before", value=before.content or "None", inline=False)
            embed.add_field(name="After", value=after.content or "None", inline=False)
            await self.send_log(before.guild, "message", embed)
            # Log message edit event
            try:
                from utils.activity_logger import ActivityLogger
                activity_logger = ActivityLogger()
                await activity_logger.log(
                    guild_id=before.guild.id,
                    user_id=before.author.id,
                    username=str(before.author),
                    action="Message Edited",
                    type_="message",
                    details=f"Channel: {before.channel}, Before: {before.content or 'None'}, After: {after.content or 'None'}"
                )
            except Exception as e:
                print(f"[ACTIVITY LOG] Failed to log message edit: {e}")

    # ========== MEMBER EVENTS ==========
    @commands.Cog.listener()
    async def on_member_join(self, member):
        embed = discord.Embed(title="👋 Member Joined", color=discord.Color.green())
        embed.add_field(name="User", value=f"{member.mention} ({member})")
        embed.add_field(name="Account Created", value=f"<t:{int(member.created_at.timestamp())}:R>")
        embed.add_field(name="Member Count", value=f"{member.guild.member_count}")
        embed.set_thumbnail(url=member.display_avatar.url)
        await self.send_log(member.guild, "member", embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        embed = discord.Embed(title="👋 Member Left", color=discord.Color.red())
        embed.add_field(name="User", value=f"{member} ({member.id})")
        embed.add_field(name="Joined", value=f"<t:{int(member.joined_at.timestamp())}:R>" if member.joined_at else "Unknown")
        embed.add_field(name="Member Count", value=f"{member.guild.member_count}")
        roles = [role.mention for role in member.roles[1:]] if len(member.roles) > 1 else ["None"]
        if roles != ["None"]:
            embed.add_field(name="Roles", value=", ".join(roles[:10]), inline=False)
        embed.set_thumbnail(url=member.display_avatar.url)
        await self.send_log(member.guild, "member", embed)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        # Nickname changes
        if before.nick != after.nick:
            embed = discord.Embed(title="📝 Nickname Changed", color=discord.Color.blue())
            embed.add_field(name="User", value=after.mention)
            embed.add_field(name="Before", value=before.nick or before.name)
            embed.add_field(name="After", value=after.nick or after.name)
            await self.send_log(after.guild, "nickname", embed)

        # Role changes
        added_roles = [role for role in after.roles if role not in before.roles]
        removed_roles = [role for role in before.roles if role not in after.roles]
        
        if added_roles:
            embed = discord.Embed(title="➕ Roles Added", color=discord.Color.green())
            embed.add_field(name="User", value=after.mention)
            embed.add_field(name="Roles Added", value=", ".join([role.mention for role in added_roles]), inline=False)
            await self.send_log(after.guild, "role", embed)
            
        if removed_roles:
            embed = discord.Embed(title="➖ Roles Removed", color=discord.Color.red())
            embed.add_field(name="User", value=after.mention)
            embed.add_field(name="Roles Removed", value=", ".join([role.mention for role in removed_roles]), inline=False)
            await self.send_log(after.guild, "role", embed)

        # Server boost events
        if before.premium_since != after.premium_since:
            if after.premium_since and not before.premium_since:
                # User started boosting
                embed = discord.Embed(title="💎 Server Boosted!", color=discord.Color.magenta())
                embed.add_field(name="User", value=after.mention)
                embed.add_field(name="Boost Level", value=f"Level {after.guild.premium_tier}")
                embed.add_field(name="Total Boosts", value=f"{after.guild.premium_subscription_count}")
                embed.set_thumbnail(url=after.display_avatar.url)
                await self.send_log(after.guild, "boost", embed)
            elif before.premium_since and not after.premium_since:
                # User stopped boosting
                embed = discord.Embed(title="💔 Boost Removed", color=discord.Color.red())
                embed.add_field(name="User", value=after.mention)
                embed.add_field(name="Boost Level", value=f"Level {after.guild.premium_tier}")
                embed.add_field(name="Total Boosts", value=f"{after.guild.premium_subscription_count}")
                embed.set_thumbnail(url=after.display_avatar.url)
                await self.send_log(after.guild, "boost", embed)

    @commands.Cog.listener()
    async def on_user_update(self, before, after):
        # Avatar changes (check if user is in any mutual guilds)
        if before.avatar != after.avatar:
            for guild in self.bot.guilds:
                if guild.get_member(after.id):
                    embed = discord.Embed(title="🖼️ Avatar Changed", color=discord.Color.blue())
                    embed.add_field(name="User", value=f"{after.mention} ({after})")
                    if before.avatar:
                        embed.set_thumbnail(url=before.avatar.url)
                        embed.add_field(name="Previous Avatar", value=f"[View]({before.avatar.url})")
                    if after.avatar:
                        embed.set_image(url=after.avatar.url)
                        embed.add_field(name="New Avatar", value=f"[View]({after.avatar.url})")
                    await self.send_log(guild, "avatar", embed)
                    break  # Only log once

        # Username changes
        if before.name != after.name:
            for guild in self.bot.guilds:
                if guild.get_member(after.id):
                    embed = discord.Embed(title="👤 Username Changed", color=discord.Color.blue())
                    embed.add_field(name="User", value=after.mention)
                    embed.add_field(name="Before", value=before.name)
                    embed.add_field(name="After", value=after.name)
                    await self.send_log(guild, "member", embed)
                    break

    # ========== VOICE EVENTS ==========
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # User joined voice channel
        if before.channel is None and after.channel is not None:
            embed = discord.Embed(title="🔊 Voice Channel Joined", color=discord.Color.green())
            embed.add_field(name="User", value=member.mention)
            embed.add_field(name="Channel", value=after.channel.mention)
            await self.send_log(member.guild, "voice", embed)
            
        # User left voice channel
        elif before.channel is not None and after.channel is None:
            embed = discord.Embed(title="🔇 Voice Channel Left", color=discord.Color.red())
            embed.add_field(name="User", value=member.mention)
            embed.add_field(name="Channel", value=before.channel.mention)
            await self.send_log(member.guild, "voice", embed)
            
        # User moved voice channels
        elif before.channel != after.channel and before.channel is not None and after.channel is not None:
            embed = discord.Embed(title="🔄 Voice Channel Moved", color=discord.Color.blue())
            embed.add_field(name="User", value=member.mention)
            embed.add_field(name="From", value=before.channel.mention)
            embed.add_field(name="To", value=after.channel.mention)
            await self.send_log(member.guild, "voice", embed)
            
        # Mute/unmute events
        if before.self_mute != after.self_mute:
            action = "Muted" if after.self_mute else "Unmuted"
            embed = discord.Embed(title=f"🔇 Self {action}", color=discord.Color.orange())
            embed.add_field(name="User", value=member.mention)
            if after.channel:
                embed.add_field(name="Channel", value=after.channel.mention)
            await self.send_log(member.guild, "voice", embed)
            
        if before.self_deaf != after.self_deaf:
            action = "Deafened" if after.self_deaf else "Undeafened"
            embed = discord.Embed(title=f"🔇 Self {action}", color=discord.Color.orange())
            embed.add_field(name="User", value=member.mention)
            if after.channel:
                embed.add_field(name="Channel", value=after.channel.mention)
            await self.send_log(member.guild, "voice", embed)

    # ========== SERVER EVENTS ==========
    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        changes = []
        
        if before.name != after.name:
            changes.append(f"**Name:** {before.name} → {after.name}")
        if before.description != after.description:
            changes.append(f"**Description:** {before.description or 'None'} → {after.description or 'None'}")
        if before.icon != after.icon:
            changes.append("**Icon:** Changed")
        if before.banner != after.banner:
            changes.append("**Banner:** Changed")
        if before.verification_level != after.verification_level:
            changes.append(f"**Verification Level:** {before.verification_level} → {after.verification_level}")
        if before.explicit_content_filter != after.explicit_content_filter:
            changes.append(f"**Content Filter:** {before.explicit_content_filter} → {after.explicit_content_filter}")
        if before.default_notifications != after.default_notifications:
            changes.append(f"**Default Notifications:** {before.default_notifications} → {after.default_notifications}")
            
        if changes:
            embed = discord.Embed(title="⚙️ Server Updated", color=discord.Color.blue())
            embed.add_field(name="Changes", value="\n".join(changes), inline=False)
            if after.icon:
                embed.set_thumbnail(url=after.icon.url)
            await self.send_log(after, "server", embed)

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        embed = discord.Embed(title="🔨 Member Banned", color=discord.Color.red())
        embed.add_field(name="User", value=f"{user} ({user.id})")
        embed.set_thumbnail(url=user.display_avatar.url)
        
        # Try to get ban reason from audit logs
        try:
            async for entry in guild.audit_logs(action=discord.AuditLogAction.ban, limit=1):
                if entry.target == user:
                    if entry.user:
                        embed.add_field(name="Banned By", value=entry.user.mention)
                    if entry.reason:
                        embed.add_field(name="Reason", value=entry.reason, inline=False)
                    break
        except:
            pass
            
        await self.send_log(guild, "punishment", embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        embed = discord.Embed(title="⚖️ Member Unbanned", color=discord.Color.green())
        embed.add_field(name="User", value=f"{user} ({user.id})")
        embed.set_thumbnail(url=user.display_avatar.url)
        
        # Try to get unban reason from audit logs
        try:
            async for entry in guild.audit_logs(action=discord.AuditLogAction.unban, limit=1):
                if entry.target == user:
                    if entry.user:
                        embed.add_field(name="Unbanned By", value=entry.user.mention)
                    if entry.reason:
                        embed.add_field(name="Reason", value=entry.reason, inline=False)
                    break
        except:
            pass
            
        await self.send_log(guild, "punishment", embed)

    # ========== THREAD EVENTS ==========
    @commands.Cog.listener()
    async def on_thread_create(self, thread):
        embed = discord.Embed(title="🧵 Thread Created", color=discord.Color.green())
        embed.add_field(name="Thread", value=thread.mention)
        embed.add_field(name="Parent Channel", value=thread.parent.mention if thread.parent else "Unknown")
        if thread.owner:
            embed.add_field(name="Created By", value=thread.owner.mention)
        await self.send_log(thread.guild, "thread", embed)

    @commands.Cog.listener()
    async def on_thread_delete(self, thread):
        embed = discord.Embed(title="🗑️ Thread Deleted", color=discord.Color.red())
        embed.add_field(name="Thread", value=thread.name)
        embed.add_field(name="Parent Channel", value=thread.parent.mention if thread.parent else "Unknown")
        await self.send_log(thread.guild, "thread", embed)

    @commands.Cog.listener()
    async def on_thread_update(self, before, after):
        if before.name != after.name:
            embed = discord.Embed(title="✏️ Thread Renamed", color=discord.Color.blue())
            embed.add_field(name="Thread", value=after.mention)
            embed.add_field(name="Before", value=before.name)
            embed.add_field(name="After", value=after.name)
            await self.send_log(after.guild, "thread", embed)
            
        if before.archived != after.archived:
            status = "Archived" if after.archived else "Unarchived"
            embed = discord.Embed(title=f"📦 Thread {status}", color=discord.Color.orange())
            embed.add_field(name="Thread", value=after.mention)
            await self.send_log(after.guild, "thread", embed)

    # ========== REACTION EVENTS ==========
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.guild_id and payload.user_id != self.bot.user.id:
            guild = self.bot.get_guild(payload.guild_id)
            if guild:
                channel = guild.get_channel(payload.channel_id)
                if channel:
                    user = guild.get_member(payload.user_id)
                    if user and not user.bot:
                        embed = discord.Embed(title="➕ Reaction Added", color=discord.Color.green())
                        embed.add_field(name="User", value=user.mention)
                        embed.add_field(name="Channel", value=channel.mention)
                        embed.add_field(name="Emoji", value=str(payload.emoji))
                        embed.add_field(name="Message", value=f"[Jump to Message](https://discord.com/channels/{guild.id}/{channel.id}/{payload.message_id})")
                        await self.send_log(guild, "reaction", embed)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        if payload.guild_id and payload.user_id != self.bot.user.id:
            guild = self.bot.get_guild(payload.guild_id)
            if guild:
                channel = guild.get_channel(payload.channel_id)
                if channel:
                    user = guild.get_member(payload.user_id)
                    if user and not user.bot:
                        embed = discord.Embed(title="➖ Reaction Removed", color=discord.Color.red())
                        embed.add_field(name="User", value=user.mention)
                        embed.add_field(name="Channel", value=channel.mention)
                        embed.add_field(name="Emoji", value=str(payload.emoji))
                        embed.add_field(name="Message", value=f"[Jump to Message](https://discord.com/channels/{guild.id}/{channel.id}/{payload.message_id})")
                        await self.send_log(guild, "reaction", embed)

    # ========== ADDITIONAL CHANNEL EVENTS ==========
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        embed = discord.Embed(title="📁 Channel Created", color=discord.Color.green())
        embed.add_field(name="Channel", value=channel.mention)
        embed.add_field(name="Type", value=str(channel.type).title())
        if hasattr(channel, 'category') and channel.category:
            embed.add_field(name="Category", value=channel.category.name)
        await self.send_log(channel.guild, "channel", embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        embed = discord.Embed(title="🗑️ Channel Deleted", color=discord.Color.red())
        embed.add_field(name="Channel", value=f"#{channel.name}")
        embed.add_field(name="Type", value=str(channel.type).title())
        if hasattr(channel, 'category') and channel.category:
            embed.add_field(name="Category", value=channel.category.name)
        await self.send_log(channel.guild, "channel", embed)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        changes = []
        position_only = True
        
        if before.name != after.name:
            changes.append(f"**Name:** {before.name} → {after.name}")
            position_only = False
        if hasattr(before, 'topic') and hasattr(after, 'topic') and before.topic != after.topic:
            changes.append(f"**Topic:** {before.topic or 'None'} → {after.topic or 'None'}")
            position_only = False
        if hasattr(before, 'slowmode_delay') and hasattr(after, 'slowmode_delay') and before.slowmode_delay != after.slowmode_delay:
            changes.append(f"**Slowmode:** {before.slowmode_delay}s → {after.slowmode_delay}s")
            position_only = False
        if hasattr(before, 'nsfw') and hasattr(after, 'nsfw') and before.nsfw != after.nsfw:
            changes.append(f"**NSFW:** {before.nsfw} → {after.nsfw}")
            position_only = False
            
        # Handle position changes with heavy rate limiting
        if before.position != after.position:
            changes.append(f"**Position:** {before.position} → {after.position}")
            
            # If only position changed, apply heavy rate limiting
            if position_only:
                current_time = time.time()
                if after.guild.id in POSITION_CHANGE_COOLDOWNS:
                    if current_time - POSITION_CHANGE_COOLDOWNS[after.guild.id] < POSITION_CHANGE_COOLDOWN:
                        return  # Skip position-only changes during cooldown
                POSITION_CHANGE_COOLDOWNS[after.guild.id] = current_time
            
        if changes:
            embed = discord.Embed(title="✏️ Channel Updated", color=discord.Color.blue())
            embed.add_field(name="Channel", value=after.mention)
            embed.add_field(name="Changes", value="\n".join(changes[:10]), inline=False)
            
            # Use bypass_cooldown=True for important changes (non-position)
            await self.send_log(after.guild, "channel", embed, bypass_cooldown=not position_only)

    # ========== ADDITIONAL ROLE EVENTS ==========
    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        embed = discord.Embed(title="➕ Role Created", color=discord.Color.green())
        embed.add_field(name="Role", value=role.mention)
        embed.add_field(name="Color", value=str(role.color))
        embed.add_field(name="Mentionable", value=role.mentionable)
        embed.add_field(name="Hoisted", value=role.hoist)
        await self.send_log(role.guild, "role", embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        embed = discord.Embed(title="➖ Role Deleted", color=discord.Color.red())
        embed.add_field(name="Role", value=f"@{role.name}")
        embed.add_field(name="Color", value=str(role.color))
        embed.add_field(name="Members", value=len(role.members))
        await self.send_log(role.guild, "role", embed)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        changes = []
        position_only = True
        
        if before.name != after.name:
            changes.append(f"**Name:** {before.name} → {after.name}")
            position_only = False
        if before.color != after.color:
            changes.append(f"**Color:** {before.color} → {after.color}")
            position_only = False
        if before.mentionable != after.mentionable:
            changes.append(f"**Mentionable:** {before.mentionable} → {after.mentionable}")
            position_only = False
        if before.hoist != after.hoist:
            changes.append(f"**Hoisted:** {before.hoist} → {after.hoist}")
            position_only = False
            
        # Handle position changes with heavy rate limiting
        if before.position != after.position:
            changes.append(f"**Position:** {before.position} → {after.position}")
            
            # If only position changed, apply heavy rate limiting
            if position_only:
                current_time = time.time()
                if after.guild.id in POSITION_CHANGE_COOLDOWNS:
                    if current_time - POSITION_CHANGE_COOLDOWNS[after.guild.id] < POSITION_CHANGE_COOLDOWN:
                        return  # Skip position-only changes during cooldown
                POSITION_CHANGE_COOLDOWNS[after.guild.id] = current_time
            
        if changes:
            embed = discord.Embed(title="✏️ Role Updated", color=discord.Color.blue())
            embed.add_field(name="Role", value=after.mention)
            embed.add_field(name="Changes", value="\n".join(changes[:10]), inline=False)
            
            # Use bypass_cooldown=True for important changes (non-position)
            await self.send_log(after.guild, "role", embed, bypass_cooldown=not position_only)

    # ========== INVITE EVENTS ==========
    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        embed = discord.Embed(title="📨 Invite Created", color=discord.Color.green())
        embed.add_field(name="Code", value=f"`{invite.code}`")
        embed.add_field(name="Channel", value=invite.channel.mention)
        embed.add_field(name="Max Uses", value=invite.max_uses or "Unlimited")
        embed.add_field(name="Expires", value=f"<t:{int(invite.expires_at.timestamp())}:R>" if invite.expires_at else "Never")
        if invite.inviter:
            embed.add_field(name="Created By", value=invite.inviter.mention)
        await self.send_log(invite.guild, "invite", embed)

    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        embed = discord.Embed(title="❌ Invite Deleted", color=discord.Color.red())
        embed.add_field(name="Code", value=f"`{invite.code}`")
        embed.add_field(name="Channel", value=invite.channel.mention)
        embed.add_field(name="Uses", value=f"{invite.uses}/{invite.max_uses or '∞'}")
        await self.send_log(invite.guild, "invite", embed)

    # ========== WEBHOOK EVENTS ==========
    @commands.Cog.listener()
    async def on_webhooks_update(self, channel):
        embed = discord.Embed(title="🔄 Webhooks Updated", color=discord.Color.blurple())
        embed.add_field(name="Channel", value=channel.mention)
        embed.add_field(name="Info", value="Webhooks in this channel have been modified")
        await self.send_log(channel.guild, "webhook", embed)

    # ========== EMOJI EVENTS ==========
    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild, before, after):
        added = [e for e in after if e not in before]
        removed = [e for e in before if e not in after]

        for emoji in added:
            embed = discord.Embed(title="✨ Emoji Created", color=discord.Color.green())
            embed.add_field(name="Name", value=f":{emoji.name}:")
            embed.add_field(name="Animated", value=emoji.animated)
            embed.add_field(name="ID", value=emoji.id)
            embed.set_thumbnail(url=emoji.url)
            await self.send_log(guild, "emoji", embed)

        for emoji in removed:
            embed = discord.Embed(title="❌ Emoji Deleted", color=discord.Color.red())
            embed.add_field(name="Name", value=f":{emoji.name}:")
            embed.add_field(name="Animated", value=emoji.animated)
            embed.add_field(name="ID", value=emoji.id)
            await self.send_log(guild, "emoji", embed)

# Setup
async def setup(bot):
    await bot.add_cog(Logging(bot))
