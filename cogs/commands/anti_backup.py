"""
Antinuke Backup Commands
Allows server owners to create and restore backups
"""

import discord
from discord.ext import commands
from utils.backup_manager import BackupManager
from datetime import datetime
import time

class AntiBackup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(self.initialize())
    
    async def initialize(self):
        """Initialize backup database"""
        await self.bot.wait_until_ready()
        await BackupManager.initialize_database()
        print("✅ Backup system initialized")
    
    @commands.group(name="backup", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def backup(self, ctx):
        """Backup system for server protection"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="🗄️ Backup System",
                description="Create and restore server backups for antinuke protection",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="📦 Create Backups",
                value=(
                    "`$backup create` - Create full server backup\n"
                    "`$backup channels` - Backup all channels\n"
                    "`$backup roles` - Backup all roles"
                ),
                inline=False
            )
            embed.add_field(
                name="🔄 Restore Backups",
                value=(
                    "`$backup list` - List available backups\n"
                    "`$backup restore <id>` - Restore from backup\n"
                    "`$backup info <id>` - View backup details"
                ),
                inline=False
            )
            embed.add_field(
                name="🗑️ Manage Backups",
                value=(
                    "`$backup clean` - Delete old backups (keep 20 most recent)\n"
                    "`$backup delete <id>` - Delete specific backup"
                ),
                inline=False
            )
            embed.set_footer(text="⚠️ Administrator permission required")
            await ctx.send(embed=embed)
    
    @backup.command(name="create")
    @commands.has_permissions(administrator=True)
    async def backup_create(self, ctx, *, reason: str = "Manual backup"):
        """Create a full server backup"""
        try:
            msg = await ctx.send("🗄️ Creating full server backup...")
            
            start_time = time.time()
            backup_id = await BackupManager.create_full_backup(
                guild=ctx.guild,
                reason=reason,
                created_by=ctx.author
            )
            duration = time.time() - start_time
            
            # Cleanup old backups automatically
            deleted = await BackupManager.delete_old_backups(ctx.guild.id, keep_count=20)
            
            embed = discord.Embed(
                title="✅ Backup Created Successfully",
                description=f"Full server backup has been created",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Backup ID", value=f"`{backup_id}`", inline=True)
            embed.add_field(name="Duration", value=f"{duration:.2f}s", inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(
                name="📊 Backed Up",
                value=(
                    f"• Channels: {len(ctx.guild.channels)}\n"
                    f"• Roles: {len(ctx.guild.roles)}\n"
                    f"• Members: {len(ctx.guild.members)}"
                ),
                inline=False
            )
            
            if deleted > 0:
                embed.set_footer(text=f"Cleaned up {deleted} old backup(s)")
            
            await msg.edit(content=None, embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Failed to create backup: {e}")
    
    @backup.command(name="channels")
    @commands.has_permissions(administrator=True)
    async def backup_channels(self, ctx, *, reason: str = "Channel backup"):
        """Backup all channels"""
        try:
            msg = await ctx.send("🗄️ Backing up all channels...")
            
            backup_id = await BackupManager.create_channel_backup(
                guild=ctx.guild,
                channels=ctx.guild.channels,
                reason=reason,
                created_by=ctx.author
            )
            
            embed = discord.Embed(
                title="✅ Channels Backed Up",
                description=f"All channels have been backed up",
                color=discord.Color.green()
            )
            embed.add_field(name="Backup ID", value=f"`{backup_id}`", inline=True)
            embed.add_field(name="Channels", value=str(len(ctx.guild.channels)), inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            
            await msg.edit(content=None, embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Failed to backup channels: {e}")
    
    @backup.command(name="roles")
    @commands.has_permissions(administrator=True)
    async def backup_roles(self, ctx, *, reason: str = "Role backup"):
        """Backup all roles"""
        try:
            msg = await ctx.send("🗄️ Backing up all roles...")
            
            backup_id = await BackupManager.create_role_backup(
                guild=ctx.guild,
                roles=ctx.guild.roles,
                reason=reason,
                created_by=ctx.author
            )
            
            embed = discord.Embed(
                title="✅ Roles Backed Up",
                description=f"All roles have been backed up",
                color=discord.Color.green()
            )
            embed.add_field(name="Backup ID", value=f"`{backup_id}`", inline=True)
            embed.add_field(name="Roles", value=str(len(ctx.guild.roles)), inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            
            await msg.edit(content=None, embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Failed to backup roles: {e}")
    
    @backup.command(name="list")
    @commands.has_permissions(administrator=True)
    async def backup_list(self, ctx, limit: int = 10):
        """List available backups"""
        try:
            backups = await BackupManager.get_backups(ctx.guild.id, limit=limit)
            
            if not backups:
                await ctx.send("📭 No backups found for this server.")
                return
            
            embed = discord.Embed(
                title="🗄️ Available Backups",
                description=f"Showing {len(backups)} most recent backup(s)",
                color=discord.Color.blue()
            )
            
            for backup in backups:
                created_at = datetime.fromtimestamp(backup['created_at'])
                time_str = created_at.strftime("%Y-%m-%d %H:%M:%S")
                
                creator = ctx.guild.get_member(backup['created_by'])
                creator_name = creator.display_name if creator else f"User {backup['created_by']}"
                
                metadata = backup.get('metadata', {})
                details = []
                if 'guild_name' in metadata:
                    details.append(f"Server: {metadata['guild_name']}")
                if 'channel_count' in metadata:
                    details.append(f"Channels: {metadata['channel_count']}")
                if 'role_count' in metadata:
                    details.append(f"Roles: {metadata['role_count']}")
                if 'member_count' in metadata:
                    details.append(f"Members: {metadata['member_count']}")
                
                value = (
                    f"**Type:** {backup['type'].title()}\n"
                    f"**Created:** {time_str}\n"
                    f"**By:** {creator_name}\n"
                    f"**Reason:** {backup['reason']}\n"
                )
                if details:
                    value += f"**Details:** {', '.join(details)}"
                
                embed.add_field(
                    name=f"ID: {backup['id']}",
                    value=value,
                    inline=False
                )
            
            embed.set_footer(text="Use $backup restore <id> to restore a backup")
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Failed to list backups: {e}")
    
    @backup.command(name="restore")
    @commands.has_permissions(administrator=True)
    async def backup_restore(self, ctx, backup_id: int):
        """Restore from a backup"""
        try:
            # Confirm restoration
            embed = discord.Embed(
                title="⚠️ Confirm Backup Restoration",
                description=(
                    f"Are you sure you want to restore from backup ID `{backup_id}`?\n\n"
                    "This will attempt to restore:\n"
                    "• Channel names and settings\n"
                    "• Role names and permissions\n\n"
                    "**Note:** This will NOT recreate deleted channels/roles, "
                    "only restore settings for existing ones."
                ),
                color=discord.Color.orange()
            )
            embed.set_footer(text="React with ✅ to confirm or ❌ to cancel")
            
            msg = await ctx.send(embed=embed)
            await msg.add_reaction("✅")
            await msg.add_reaction("❌")
            
            def check(reaction, user):
                return user == ctx.author and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == msg.id
            
            reaction, user = await self.bot.wait_for('reaction_add', timeout=30.0, check=check)
            
            if str(reaction.emoji) == "❌":
                await msg.edit(content="❌ Restoration cancelled.", embed=None)
                return
            
            # Proceed with restoration
            await msg.clear_reactions()
            await msg.edit(content="🔄 Restoring from backup...", embed=None)
            
            # Restore channels
            channel_success, channel_failed = await BackupManager.restore_channels(ctx.guild, backup_id)
            
            # Restore roles
            role_success, role_failed = await BackupManager.restore_roles(ctx.guild, backup_id)
            
            result_embed = discord.Embed(
                title="✅ Backup Restoration Complete",
                description=f"Restored from backup ID `{backup_id}`",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            result_embed.add_field(
                name="📊 Channels",
                value=f"✅ Restored: {channel_success}\n❌ Failed: {channel_failed}",
                inline=True
            )
            result_embed.add_field(
                name="🎭 Roles",
                value=f"✅ Restored: {role_success}\n❌ Failed: {role_failed}",
                inline=True
            )
            
            if channel_failed > 0 or role_failed > 0:
                result_embed.add_field(
                    name="⚠️ Note",
                    value="Failed items were likely deleted and cannot be automatically recreated.",
                    inline=False
                )
            
            await msg.edit(content=None, embed=result_embed)
            
        except TimeoutError:
            await ctx.send("⏱️ Restoration cancelled - timed out.")
        except Exception as e:
            await ctx.send(f"❌ Failed to restore backup: {e}")
    
    @backup.command(name="clean")
    @commands.has_permissions(administrator=True)
    async def backup_clean(self, ctx):
        """Delete old backups (keep 20 most recent)"""
        try:
            msg = await ctx.send("🗑️ Cleaning old backups...")
            
            deleted = await BackupManager.delete_old_backups(ctx.guild.id, keep_count=20)
            
            if deleted > 0:
                await msg.edit(content=f"✅ Deleted {deleted} old backup(s). Kept 20 most recent.")
            else:
                await msg.edit(content="✅ No old backups to delete. All backups are within the limit.")
            
        except Exception as e:
            await ctx.send(f"❌ Failed to clean backups: {e}")
    
    @backup.command(name="info")
    @commands.has_permissions(administrator=True)
    async def backup_info(self, ctx, backup_id: int):
        """View detailed backup information"""
        try:
            backups = await BackupManager.get_backups(ctx.guild.id, limit=100)
            backup = next((b for b in backups if b['id'] == backup_id), None)
            
            if not backup:
                await ctx.send(f"❌ Backup ID `{backup_id}` not found.")
                return
            
            created_at = datetime.fromtimestamp(backup['created_at'])
            creator = ctx.guild.get_member(backup['created_by'])
            
            embed = discord.Embed(
                title=f"🗄️ Backup Information - ID {backup_id}",
                description=f"Details for backup created on {created_at.strftime('%Y-%m-%d at %H:%M:%S')}",
                color=discord.Color.blue(),
                timestamp=created_at
            )
            
            embed.add_field(name="Type", value=backup['type'].title(), inline=True)
            embed.add_field(
                name="Created By",
                value=creator.mention if creator else f"User {backup['created_by']}",
                inline=True
            )
            embed.add_field(name="Reason", value=backup['reason'], inline=False)
            
            metadata = backup.get('metadata', {})
            if metadata:
                details = []
                for key, value in metadata.items():
                    formatted_key = key.replace('_', ' ').title()
                    details.append(f"**{formatted_key}:** {value}")
                embed.add_field(name="📊 Metadata", value="\n".join(details), inline=False)
            
            embed.set_footer(text=f"Use $backup restore {backup_id} to restore this backup")
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Failed to get backup info: {e}")

async def setup(bot):
    await bot.add_cog(AntiBackup(bot))
