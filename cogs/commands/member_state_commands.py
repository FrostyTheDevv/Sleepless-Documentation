import discord
from discord.ext import commands
from utils.member_state import member_state_manager, PunishmentType, MemberState
from utils.custom_permissions import require_custom_permissions
from utils.Tools import blacklist_check, ignore_check
from utils.error_helpers import StandardErrorHandler
from typing import Optional, List
import json
from datetime import datetime, timedelta

class MemberStateCommands(commands.Cog):
    """Comprehensive admin interface for member state and role persistence management"""
    
    def __init__(self, bot):
        self.bot = bot
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    # =================== ROLE PERSISTENCE COMMANDS ===================
    
    @commands.group(name="rolestate", aliases=["rs", "memberstate"])
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    async def role_state(self, ctx):
        """Manage role persistence and member state system"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="<:gear:1427471588915150900> Member State Management",
                description="Comprehensive role persistence and punishment tracking system",
                color=0x00ff88
            )
            
            embed.add_field(
                name="<:file:1427471573304217651> Role Persistence",
                value="`rolestate settings` - Configure role restoration\n"
                      "`rolestate restore <user>` - Manually restore roles\n"
                      "`rolestate saved <user>` - View saved roles\n"
                      "`rolestate excluded` - View excluded moderation roles",
                inline=False
            )
            
            embed.add_field(
                name="<:warning:1427471923805925397> Punishment Management", 
                value="`rolestate punishments <user>` - View active punishments\n"
                      "`rolestate state <user>` - View member state\n"
                      "`rolestate history <user>` - View member history",
                inline=False
            )
            
            embed.add_field(
                name="<:gear:1427471588915150900> Channel Permissions",
                value="`rolestate channel <channel> <command> <enabled>` - Channel overrides\n"
                      "`rolestate toggle <command> <enabled>` - Global toggles",
                inline=False
            )
            
            embed.add_field(
                name="<:info:1427471506287362068> System Status",
                value="`rolestate status` - View system statistics\n"
                      "`rolestate cleanup` - Clean expired data",
                inline=False
            )
            
            await ctx.send(embed=embed)
    
    @role_state.command(name="settings")
    @commands.has_permissions(administrator=True)
    async def role_settings(self, ctx, *, setting: Optional[str] = None):
        """Configure role restoration settings"""
        
        if not setting:
            # Show current settings
            settings = member_state_manager.get_restoration_settings(ctx.guild.id)
            
            embed = discord.Embed(
                title="<:gear:1427471588915150900> Role Restoration Settings",
                description=f"Current settings for {ctx.guild.name}",
                color=0x00ff88
            )
            
            embed.add_field(
                name="Restore Roles",
                value="✅ Enabled" if settings['restore_roles'] else "❌ Disabled",
                inline=True
            )
            
            embed.add_field(
                name="Restore During Punishment",
                value="✅ Enabled" if settings['restore_on_punishment'] else "❌ Disabled",
                inline=True
            )
            
            embed.add_field(
                name="Max Restore Days",
                value=f"{settings['max_restore_days']} days",
                inline=True
            )
            
            embed.add_field(
                name="Log Restorations",
                value="✅ Enabled" if settings['log_restorations'] else "❌ Disabled",
                inline=True
            )
            
            if settings['log_channel_id']:
                log_channel = ctx.guild.get_channel(settings['log_channel_id'])
                embed.add_field(
                    name="Log Channel",
                    value=log_channel.mention if log_channel else "Channel not found",
                    inline=True
                )
            
            if settings['excluded_roles']:
                excluded_roles = []
                for role_id in settings['excluded_roles']:
                    role = ctx.guild.get_role(role_id)
                    if role:
                        excluded_roles.append(role.mention)
                
                if excluded_roles:
                    embed.add_field(
                        name="Excluded Roles",
                        value="\n".join(excluded_roles[:10]) + 
                              (f"\n...and {len(excluded_roles)-10} more" if len(excluded_roles) > 10 else ""),
                        inline=False
                    )
            
            embed.add_field(
                name="Available Settings",
                value="• `enable/disable` - Toggle role restoration\n"
                      "• `punishment enable/disable` - Restore during punishment\n"
                      "• `days <number>` - Set max restore days\n"
                      "• `logging enable/disable` - Toggle logging\n"
                      "• `logchannel <channel>` - Set log channel\n"
                      "• `exclude <role>` - Exclude role from restoration\n"
                      "• `include <role>` - Include role in restoration",
                inline=False
            )
            
            await ctx.send(embed=embed)
            return
        
        # Process setting changes
        parts = setting.lower().split()
        
        if not parts:
            await ctx.send("❌ Please specify a setting to change.")
            return
        
        success = False
        message = ""
        
        if parts[0] == "enable":
            success = member_state_manager.set_restoration_settings(
                ctx.guild.id, restore_roles=True, moderator_id=ctx.author.id
            )
            message = "✅ Role restoration enabled."
        
        elif parts[0] == "disable":
            success = member_state_manager.set_restoration_settings(
                ctx.guild.id, restore_roles=False, moderator_id=ctx.author.id
            )
            message = "❌ Role restoration disabled."
        
        elif parts[0] == "punishment":
            if len(parts) < 2:
                await ctx.send("❌ Specify `enable` or `disable` for punishment restoration.")
                return
            
            enable = parts[1] == "enable"
            success = member_state_manager.set_restoration_settings(
                ctx.guild.id, restore_on_punishment=enable, moderator_id=ctx.author.id
            )
            message = f"{'✅ Enabled' if enable else '❌ Disabled'} role restoration during punishment."
        
        elif parts[0] == "days":
            if len(parts) < 2 or not parts[1].isdigit():
                await ctx.send("❌ Please specify a valid number of days (1-365).")
                return
            
            days = int(parts[1])
            if days < 1 or days > 365:
                await ctx.send("❌ Days must be between 1 and 365.")
                return
            
            success = member_state_manager.set_restoration_settings(
                ctx.guild.id, max_restore_days=days, moderator_id=ctx.author.id
            )
            message = f"✅ Max restore days set to {days}."
        
        elif parts[0] == "logging":
            if len(parts) < 2:
                await ctx.send("❌ Specify `enable` or `disable` for logging.")
                return
            
            enable = parts[1] == "enable"
            success = member_state_manager.set_restoration_settings(
                ctx.guild.id, log_restorations=enable, moderator_id=ctx.author.id
            )
            message = f"{'✅ Enabled' if enable else '❌ Disabled'} restoration logging."
        
        elif parts[0] == "logchannel":
            if len(parts) < 2:
                await ctx.send("❌ Please mention a channel or provide channel ID.")
                return
            
            # Try to find channel
            channel = None
            if ctx.message.channel_mentions:
                channel = ctx.message.channel_mentions[0]
            else:
                try:
                    channel_id = int(parts[1].strip('<>#'))
                    channel = ctx.guild.get_channel(channel_id)
                except ValueError:
                    pass
            
            if not channel:
                await ctx.send("❌ Channel not found.")
                return
            
            success = member_state_manager.set_restoration_settings(
                ctx.guild.id, log_channel_id=channel.id, moderator_id=ctx.author.id
            )
            message = f"✅ Log channel set to {channel.mention}."
        
        elif parts[0] in ["exclude", "include"]:
            await ctx.send(f"❌ Role exclusion/inclusion not yet implemented in this command. Use role management interface.")
            return
        
        else:
            await ctx.send("❌ Unknown setting. Use `rolestate settings` to see available options.")
            return
        
        if success:
            embed = discord.Embed(
                title="<:check:1428163122710970508> Settings Updated",
                description=message,
                color=0x00ff88
            )
        else:
            embed = discord.Embed(
                title="<:warning:1427471923805925397> Error",
                description="Failed to update settings.",
                color=0xff6b6b
            )
        
        await ctx.send(embed=embed)
    
    @role_state.command(name="restore")
    @commands.has_permissions(manage_roles=True)
    async def manual_restore(self, ctx, member: discord.Member):
        """Manually restore a member's saved roles"""
        
        # Get saved roles
        saved_role_ids = member_state_manager.get_saved_roles(ctx.guild.id, member.id)
        
        if not saved_role_ids:
            embed = discord.Embed(
                title="<:warning:1427471923805925397> No Saved Roles",
                description=f"No saved roles found for {member.mention}.",
                color=0xff6b6b
            )
            await ctx.send(embed=embed)
            return
        
        # Get available roles
        available_roles = {role.id: role for role in ctx.guild.roles}
        roles_to_restore = []
        roles_not_found = []
        
        for role_id in saved_role_ids:
            if role_id in available_roles:
                role = available_roles[role_id]
                if role < ctx.guild.me.top_role:  # Bot can manage this role
                    roles_to_restore.append(role)
                else:
                    roles_not_found.append(f"{role.name} (too high)")
            else:
                roles_not_found.append(f"Role ID {role_id} (deleted)")
        
        if not roles_to_restore:
            embed = discord.Embed(
                title="<:warning:1427471923805925397> Cannot Restore Roles",
                description="No roles can be restored (either deleted or too high for bot).",
                color=0xff6b6b
            )
            
            if roles_not_found:
                embed.add_field(
                    name="Issues",
                    value="\n".join(roles_not_found[:10]),
                    inline=False
                )
            
            await ctx.send(embed=embed)
            return
        
        try:
            # Add roles to member
            await member.add_roles(*roles_to_restore, reason=f"Manual restoration by {ctx.author}")
            
            # Mark as restored
            member_state_manager.mark_roles_restored(ctx.guild.id, member.id)
            
            embed = discord.Embed(
                title="<:check:1428163122710970508> Roles Restored",
                description=f"Successfully restored {len(roles_to_restore)} roles to {member.mention}.",
                color=0x00ff88
            )
            
            if len(roles_to_restore) <= 10:
                role_list = "\n".join([f"• {role.name}" for role in roles_to_restore])
                embed.add_field(
                    name="Restored Roles",
                    value=role_list,
                    inline=False
                )
            
            if roles_not_found:
                embed.add_field(
                    name="Could Not Restore",
                    value="\n".join(roles_not_found[:5]),
                    inline=False
                )
            
            await ctx.send(embed=embed)
        
        except discord.Forbidden:
            embed = discord.Embed(
                title="<:stop:1427471993984389180> Permission Error",
                description="I don't have permission to manage roles for this member.",
                color=0xff6b6b
            )
            await ctx.send(embed=embed)
        
        except discord.HTTPException as e:
            embed = discord.Embed(
                title="<:warning:1427471923805925397> Discord Error",
                description=f"Failed to restore roles: {e}",
                color=0xff6b6b
            )
            await ctx.send(embed=embed)
    
    @role_state.command(name="saved")
    async def view_saved_roles(self, ctx, member: discord.Member):
        """View saved roles for a member"""
        
        saved_role_ids = member_state_manager.get_saved_roles(ctx.guild.id, member.id)
        
        embed = discord.Embed(
            title="<:file:1427471573304217651> Saved Roles",
            description=f"Saved roles for {member.mention}",
            color=0x00ff88
        )
        
        embed.add_field(
            name="Member",
            value=f"{member.display_name} ({member.id})",
            inline=True
        )
        
        embed.add_field(
            name="Saved Roles Count",
            value=str(len(saved_role_ids)),
            inline=True
        )
        
        if saved_role_ids:
            available_roles = []
            deleted_roles = []
            
            for role_id in saved_role_ids:
                role = ctx.guild.get_role(role_id)
                if role:
                    available_roles.append(f"• {role.name}")
                else:
                    deleted_roles.append(f"• Role ID {role_id} (deleted)")
            
            if available_roles:
                embed.add_field(
                    name="Available Roles",
                    value="\n".join(available_roles[:15]) + 
                          (f"\n...and {len(available_roles)-15} more" if len(available_roles) > 15 else ""),
                    inline=False
                )
            
            if deleted_roles:
                embed.add_field(
                    name="Deleted Roles",
                    value="\n".join(deleted_roles[:10]),
                    inline=False
                )
        else:
            embed.add_field(
                name="Status",
                value="No saved roles found.",
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @role_state.command(name="excluded", aliases=["moderation", "dangerous"])
    async def view_excluded_roles(self, ctx):
        """View roles that are excluded from persistence (moderation/dangerous roles)"""
        
        embed = discord.Embed(
            title="<:warning:1427471923805925397> Excluded Roles Analysis",
            description="Roles excluded from persistence to protect server security",
            color=0xff9500
        )
        
        # Get all guild roles
        all_roles = ctx.guild.roles
        moderation_roles = []
        safe_roles = []
        
        # Analyze each role
        for role in all_roles:
            if role.name == "@everyone":
                continue
                
            if member_state_manager.is_moderation_role(role):
                moderation_roles.append(role)
            else:
                safe_roles.append(role)
        
        # Get restoration settings for explicitly excluded roles
        settings = member_state_manager.get_restoration_settings(ctx.guild.id)
        explicitly_excluded_ids = settings.get('excluded_roles', [])
        explicitly_excluded_roles = []
        
        for role_id in explicitly_excluded_ids:
            role = ctx.guild.get_role(role_id)
            if role and role not in moderation_roles:  # Don't double-count
                explicitly_excluded_roles.append(role)
        
        # Summary stats
        total_roles = len(all_roles) - 1  # Exclude @everyone
        excluded_count = len(moderation_roles) + len(explicitly_excluded_roles)
        safe_count = len(safe_roles) - len(explicitly_excluded_roles)
        
        embed.add_field(
            name="📊 Summary",
            value=f"**Total Roles:** {total_roles}\n"
                  f"**Safe for Persistence:** {safe_count}\n"
                  f"**Auto-Excluded (Dangerous):** {len(moderation_roles)}\n"
                  f"**Manually Excluded:** {len(explicitly_excluded_roles)}",
            inline=False
        )
        
        # Show dangerous permissions found
        dangerous_perms_found = set()
        for role in moderation_roles:
            perms = role.permissions
            dangerous_perms = [
                'administrator', 'manage_guild', 'manage_roles', 'manage_channels',
                'ban_members', 'kick_members', 'manage_messages', 'manage_nicknames'
            ]
            for perm in dangerous_perms:
                if hasattr(perms, perm) and getattr(perms, perm):
                    dangerous_perms_found.add(perm.replace('_', ' ').title())
        
        if dangerous_perms_found:
            embed.add_field(
                name="🚨 Dangerous Permissions Detected",
                value=", ".join(sorted(dangerous_perms_found)),
                inline=False
            )
        
        # Show auto-excluded roles (up to 10)
        if moderation_roles:
            role_list = []
            for role in sorted(moderation_roles, key=lambda r: r.position, reverse=True)[:10]:
                # Identify why this role was excluded
                reasons = []
                if hasattr(role.permissions, 'administrator') and role.permissions.administrator:
                    reasons.append("Admin")
                if hasattr(role.permissions, 'manage_roles') and role.permissions.manage_roles:
                    reasons.append("Manage Roles")
                if hasattr(role.permissions, 'ban_members') and role.permissions.ban_members:
                    reasons.append("Ban")
                if hasattr(role.permissions, 'kick_members') and role.permissions.kick_members:
                    reasons.append("Kick")
                if hasattr(role.permissions, 'manage_guild') and role.permissions.manage_guild:
                    reasons.append("Manage Server")
                
                # Check for keyword exclusion
                moderation_keywords = ['admin', 'mod', 'staff', 'jail', 'mute']
                role_name_lower = role.name.lower()
                for keyword in moderation_keywords:
                    if keyword in role_name_lower:
                        reasons.append(f"Keyword: {keyword}")
                        break
                
                reason_text = f" ({', '.join(reasons[:2])})" if reasons else ""
                role_list.append(f"• {role.name}{reason_text}")
            
            embed.add_field(
                name="🛡️ Auto-Excluded Roles",
                value="\n".join(role_list) + 
                      (f"\n...and {len(moderation_roles)-10} more" if len(moderation_roles) > 10 else ""),
                inline=False
            )
        
        # Show manually excluded roles
        if explicitly_excluded_roles:
            role_list = [f"• {role.name}" for role in explicitly_excluded_roles[:10]]
            embed.add_field(
                name="⚙️ Manually Excluded Roles",
                value="\n".join(role_list) +
                      (f"\n...and {len(explicitly_excluded_roles)-10} more" if len(explicitly_excluded_roles) > 10 else ""),
                inline=False
            )
        
        # Security notice
        embed.add_field(
            name="🔒 Security Notice",
            value="Moderation roles are automatically excluded to prevent unauthorized privilege escalation when members rejoin. "
                  "This protects your server from security risks.",
            inline=False
        )
        
        embed.set_footer(text=f"Use '{ctx.prefix}rolestate settings' to configure manual exclusions")
        await ctx.send(embed=embed)
    
    # =================== PUNISHMENT MANAGEMENT COMMANDS ===================
    
    @role_state.command(name="punishments", aliases=["punishment", "active"])
    async def view_punishments(self, ctx, member: discord.Member):
        """View active punishments for a member"""
        
        punishments = member_state_manager.get_active_punishments(ctx.guild.id, member.id)
        
        embed = discord.Embed(
            title="<:warning:1427471923805925397> Active Punishments",
            description=f"Active punishments for {member.mention}",
            color=0xff6b6b if punishments else 0x00ff88
        )
        
        embed.add_field(
            name="Member",
            value=f"{member.display_name} ({member.id})",
            inline=True
        )
        
        embed.add_field(
            name="Active Punishments",
            value=str(len(punishments)),
            inline=True
        )
        
        if punishments:
            for i, punishment in enumerate(punishments[:5], 1):
                moderator = ctx.guild.get_member(punishment['moderator_id'])
                moderator_name = moderator.display_name if moderator else f"ID: {punishment['moderator_id']}"
                
                end_time = punishment['end_time']
                if end_time:
                    end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                    time_left = end_time - datetime.utcnow()
                    if time_left.total_seconds() > 0:
                        duration = f"Expires in {time_left.days}d {time_left.seconds//3600}h"
                    else:
                        duration = "Expired"
                else:
                    duration = "Permanent"
                
                embed.add_field(
                    name=f"{punishment['type'].value.title()} #{punishment['id']}",
                    value=f"**Reason:** {punishment['reason'] or 'No reason'}\n"
                          f"**Moderator:** {moderator_name}\n"
                          f"**Duration:** {duration}",
                    inline=False
                )
            
            if len(punishments) > 5:
                embed.add_field(
                    name="Additional Punishments",
                    value=f"...and {len(punishments)-5} more. Use detailed view for complete list.",
                    inline=False
                )
        else:
            embed.add_field(
                name="Status",
                value="No active punishments.",
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @role_state.command(name="state", aliases=["info"])
    async def view_member_state(self, ctx, member: discord.Member):
        """View comprehensive member state information"""
        
        state = member_state_manager.get_member_state(ctx.guild.id, member.id)
        saved_roles = member_state_manager.get_saved_roles(ctx.guild.id, member.id)
        punishments = member_state_manager.get_active_punishments(ctx.guild.id, member.id)
        
        embed = discord.Embed(
            title="<:info:1427471506287362068> Member State",
            description=f"Complete state information for {member.mention}",
            color=0x00ff88
        )
        
        embed.add_field(
            name="Member",
            value=f"{member.display_name}\n({member.id})",
            inline=True
        )
        
        embed.add_field(
            name="Current State",
            value=state['state'].value.title(),
            inline=True
        )
        
        embed.add_field(
            name="Join Count",
            value=str(state['join_count']),
            inline=True
        )
        
        embed.add_field(
            name="Punishment Count",
            value=str(state['punishment_count']),
            inline=True
        )
        
        embed.add_field(
            name="Saved Roles",
            value=str(len(saved_roles)),
            inline=True
        )
        
        embed.add_field(
            name="Active Punishments",
            value=str(len(punishments)),
            inline=True
        )
        
        if state['last_seen']:
            last_seen = datetime.fromisoformat(state['last_seen'].replace('Z', '+00:00'))
            time_ago = datetime.utcnow() - last_seen
            embed.add_field(
                name="Last Seen",
                value=f"{time_ago.days} days ago",
                inline=True
            )
        
        if state['notes']:
            embed.add_field(
                name="Notes",
                value=state['notes'],
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    # =================== CHANNEL PERMISSION COMMANDS ===================
    
    @role_state.command(name="channel")
    @commands.has_permissions(manage_channels=True)
    async def channel_permissions(self, ctx, channel: discord.TextChannel, 
                                command_name: str, enabled: bool):
        """Set command permissions for a specific channel"""
        
        # Validate command exists
        command = self.bot.get_command(command_name.lower())
        if not command:
            embed = discord.Embed(
                title="<:warning:1427471923805925397> Command Not Found",
                description=f"Command `{command_name}` doesn't exist.",
                color=0xff6b6b
            )
            await ctx.send(embed=embed)
            return
        
        success = member_state_manager.set_channel_command_permission(
            ctx.guild.id, channel.id, command.name, enabled, moderator_id=ctx.author.id
        )
        
        if success:
            status = "enabled" if enabled else "disabled"
            embed = discord.Embed(
                title="<:check:1428163122710970508> Channel Permission Updated",
                description=f"Command `{command.name}` {status} in {channel.mention}.",
                color=0x00ff88
            )
        else:
            embed = discord.Embed(
                title="<:warning:1427471923805925397> Error",
                description="Failed to update channel permission.",
                color=0xff6b6b
            )
        
        await ctx.send(embed=embed)
    
    @role_state.command(name="toggle")
    @commands.has_permissions(administrator=True)
    async def command_toggle(self, ctx, command_name: str, enabled: bool):
        """Toggle command globally for the server"""
        
        command = self.bot.get_command(command_name.lower())
        if not command:
            embed = discord.Embed(
                title="<:warning:1427471923805925397> Command Not Found",
                description=f"Command `{command_name}` doesn't exist.",
                color=0xff6b6b
            )
            await ctx.send(embed=embed)
            return
        
        success = member_state_manager.set_command_toggle(
            ctx.guild.id, command.name, enabled, moderator_id=ctx.author.id
        )
        
        if success:
            status = "enabled" if enabled else "disabled"
            embed = discord.Embed(
                title="<:check:1428163122710970508> Command Toggle Updated",
                description=f"Command `{command.name}` {status} globally in this server.",
                color=0x00ff88
            )
        else:
            embed = discord.Embed(
                title="<:warning:1427471923805925397> Error",
                description="Failed to update command toggle.",
                color=0xff6b6b
            )
        
        await ctx.send(embed=embed)
    
    # =================== SYSTEM STATUS COMMANDS ===================
    
    @role_state.command(name="status")
    async def system_status(self, ctx):
        """View system statistics and status"""
        
        embed = discord.Embed(
            title="<:info:1427471506287362068> Member State System Status",
            description=f"Statistics for {ctx.guild.name}",
            color=0x00ff88,
            timestamp=datetime.utcnow()
        )
        
        # TODO: Implement statistics gathering from database
        embed.add_field(
            name="System Status",
            value="✅ Online and operational",
            inline=False
        )
        
        embed.add_field(
            name="Features Available",
            value="• Role persistence\n• Punishment tracking\n• Channel permissions\n• Command toggles",
            inline=True
        )
        
        settings = member_state_manager.get_restoration_settings(ctx.guild.id)
        embed.add_field(
            name="Role Restoration",
            value="✅ Enabled" if settings['restore_roles'] else "❌ Disabled",
            inline=True
        )
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(MemberStateCommands(bot))