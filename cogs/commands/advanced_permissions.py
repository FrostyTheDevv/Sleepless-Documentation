import discord
from discord.ext import commands
from utils.member_state import member_state_manager, PunishmentType, MemberState
from utils.custom_permissions import permission_manager, require_custom_permissions
from utils.Tools import blacklist_check, ignore_check
from utils.error_helpers import StandardErrorHandler
from typing import Optional, Union
import json

class AdvancedPermissions(commands.Cog):
    """Advanced permission management with channel-specific and server-wide controls"""
    
    def __init__(self, bot):
        self.bot = bot
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    @commands.group(name="permsys", aliases=["psys", "advperms"])
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    async def permissions(self, ctx):
        """Advanced permission management system"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="<:gear:1427471588915150900> Advanced Permission Management",
                description="Comprehensive control over command permissions and access",
                color=0x00ff88
            )
            
            embed.add_field(
                name="<:role:1427471506287362068> Role Permissions",
                value="`permsys role` - Manage role-based command permissions",
                inline=False
            )
            
            embed.add_field(
                name="<:channel:1427471506287362068> Channel Permissions",
                value="`permsys channel` - Manage channel-specific permissions",
                inline=False
            )
            
            embed.add_field(
                name="<:toggle:1427471506287362068> Command Toggles",
                value="`permsys toggle` - Enable/disable commands globally or per channel",
                inline=False
            )
            
            embed.add_field(
                name="<:backup:1427471506287362068> Role Restoration",
                value="`permsys restore` - Configure automatic role restoration",
                inline=False
            )
            
            embed.add_field(
                name="<:list:1427471506287362068> View Settings",
                value="`permsys status` - View all permission settings",
                inline=False
            )
            
            await ctx.send(embed=embed)
    
    # =================== ROLE PERMISSIONS ===================
    
    @permissions.group(name="role", aliases=["roles"])
    async def role_permissions(self, ctx):
        """Manage role-based command permissions"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="<:role:1427471506287362068> Role Permission Management",
                color=0x00ff88
            )
            
            embed.add_field(
                name="Add Role Permission",
                value="`permsys role add <command> <role>` - Allow role to use command",
                inline=True
            )
            
            embed.add_field(
                name="Remove Role Permission", 
                value="`permsys role remove <command> <role>` - Remove role permission",
                inline=True
            )
            
            embed.add_field(
                name="List Role Permissions",
                value="`permsys role list [command]` - View role permissions",
                inline=True
            )
            
            await ctx.send(embed=embed)
    
    @role_permissions.command(name="add")
    async def add_role_permission(self, ctx, command_name: str, role: discord.Role):
        """Add a role that can use a specific command"""
        
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
        
        # Check role hierarchy
        if ctx.author != ctx.guild.owner and role >= ctx.author.top_role:
            embed = discord.Embed(
                title="<:stop:1427471993984389180> Permission Denied",
                description="You can't assign permissions to a role higher than or equal to your highest role.",
                color=0xff6b6b
            )
            await ctx.send(embed=embed)
            return
        
        success = permission_manager.add_command_role(
            ctx.guild.id, 
            command.name, 
            role.id, 
            ctx.author.id
        )
        
        if success:
            embed = discord.Embed(
                title="<:check:1428163122710970508> Role Permission Added",
                description=f"Role {role.mention} can now use `{command.name}` command.",
                color=0x00ff88
            )
        else:
            embed = discord.Embed(
                title="<:warning:1427471923805925397> Failed to Add Permission",
                description="There was an error adding the role permission.",
                color=0xff6b6b
            )
        
        await ctx.send(embed=embed)
    
    @role_permissions.command(name="remove", aliases=["rm"])
    async def remove_role_permission(self, ctx, command_name: str, role: discord.Role):
        """Remove a role from a specific command"""
        
        command = self.bot.get_command(command_name.lower())
        if not command:
            embed = discord.Embed(
                title="<:warning:1427471923805925397> Command Not Found",
                description=f"Command `{command_name}` doesn't exist.",
                color=0xff6b6b
            )
            await ctx.send(embed=embed)
            return
        
        success = permission_manager.remove_command_role(
            ctx.guild.id,
            command.name,
            role.id
        )
        
        if success:
            embed = discord.Embed(
                title="<:check:1428163122710970508> Role Permission Removed",
                description=f"Role {role.mention} can no longer use `{command.name}` command.",
                color=0x00ff88
            )
        else:
            embed = discord.Embed(
                title="<:warning:1427471923805925397> Permission Not Found",
                description=f"Role {role.mention} wasn't authorized to use `{command.name}`.",
                color=0xff6b6b
            )
        
        await ctx.send(embed=embed)
    
    @role_permissions.command(name="list", aliases=["show"])
    async def list_role_permissions(self, ctx, command_name: Optional[str] = None):
        """List role permissions for commands"""
        
        if command_name:
            # Show permissions for specific command
            command = self.bot.get_command(command_name.lower())
            if not command:
                embed = discord.Embed(
                    title="<:warning:1427471923805925397> Command Not Found",
                    description=f"Command `{command_name}` doesn't exist.",
                    color=0xff6b6b
                )
                await ctx.send(embed=embed)
                return
            
            roles = permission_manager.get_command_roles(ctx.guild.id, command.name)
            
            embed = discord.Embed(
                title=f"<:role:1427471506287362068> Role Permissions for `{command.name}`",
                color=0x00ff88
            )
            
            if roles:
                role_list = []
                for role_id in roles:
                    role = ctx.guild.get_role(role_id)
                    if role:
                        role_list.append(f"• {role.mention}")
                
                embed.add_field(
                    name="Authorized Roles",
                    value="\n".join(role_list) if role_list else "No valid roles found",
                    inline=False
                )
            else:
                embed.add_field(
                    name="Status",
                    value="No custom permissions set (uses Discord permissions)",
                    inline=False
                )
        
        else:
            # Show all role permissions
            all_permissions = permission_manager.list_command_permissions(ctx.guild.id)
            
            embed = discord.Embed(
                title="<:role:1427471506287362068> All Role Permissions",
                description=f"Custom role permissions in {ctx.guild.name}",
                color=0x00ff88
            )
            
            if all_permissions:
                for command_name, roles_data in all_permissions.items():
                    role_mentions = []
                    for role_data in roles_data:
                        role = ctx.guild.get_role(role_data['role_id'])
                        if role:
                            role_mentions.append(role.mention)
                    
                    if role_mentions:
                        embed.add_field(
                            name=f"`{command_name}`",
                            value="\n".join(role_mentions),
                            inline=True
                        )
            else:
                embed.add_field(
                    name="No Custom Permissions",
                    value="No commands have custom role permissions set.",
                    inline=False
                )
        
        await ctx.send(embed=embed)
    
    # =================== CHANNEL PERMISSIONS ===================
    
    @permissions.group(name="channel", aliases=["ch"])
    async def channel_permissions(self, ctx):
        """Manage channel-specific command permissions"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="<:channel:1427471506287362068> Channel Permission Management",
                color=0x00ff88
            )
            
            embed.add_field(
                name="Set Channel Permission",
                value="`permsys channel set <command> <channel> <enabled>` - Enable/disable command in channel",
                inline=False
            )
            
            embed.add_field(
                name="Allow Roles in Channel",
                value="`permsys channel allow <command> <channel> <roles...>` - Allow specific roles",
                inline=False
            )
            
            embed.add_field(
                name="Deny Roles in Channel",
                value="`permsys channel deny <command> <channel> <roles...>` - Deny specific roles",
                inline=False
            )
            
            embed.add_field(
                name="List Channel Permissions",
                value="`permsys channel list [channel]` - View channel permissions",
                inline=False
            )
            
            await ctx.send(embed=embed)
    
    @channel_permissions.command(name="set")
    async def set_channel_permission(self, ctx, command_name: str, 
                                   channel: discord.TextChannel, enabled: bool):
        """Enable or disable a command in a specific channel"""
        
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
            ctx.guild.id,
            channel.id,
            command.name,
            enabled,
            moderator_id=ctx.author.id
        )
        
        if success:
            status = "enabled" if enabled else "disabled"
            embed = discord.Embed(
                title="<:check:1428163122710970508> Channel Permission Updated",
                description=f"Command `{command.name}` is now **{status}** in {channel.mention}.",
                color=0x00ff88
            )
        else:
            embed = discord.Embed(
                title="<:warning:1427471923805925397> Failed to Update Permission",
                description="There was an error updating the channel permission.",
                color=0xff6b6b
            )
        
        await ctx.send(embed=embed)
    
    @channel_permissions.command(name="allow")
    async def allow_roles_in_channel(self, ctx, command_name: str, 
                                   channel: discord.TextChannel, *roles: discord.Role):
        """Allow specific roles to use a command in a channel"""
        
        command = self.bot.get_command(command_name.lower())
        if not command:
            embed = discord.Embed(
                title="<:warning:1427471923805925397> Command Not Found",
                description=f"Command `{command_name}` doesn't exist.",
                color=0xff6b6b
            )
            await ctx.send(embed=embed)
            return
        
        if not roles:
            embed = discord.Embed(
                title="<:warning:1427471923805925397> No Roles Specified",
                description="You must specify at least one role.",
                color=0xff6b6b
            )
            await ctx.send(embed=embed)
            return
        
        role_ids = [role.id for role in roles]
        success = member_state_manager.set_channel_command_permission(
            ctx.guild.id,
            channel.id,
            command.name,
            True,
            allowed_roles=role_ids,
            moderator_id=ctx.author.id
        )
        
        if success:
            role_mentions = [role.mention for role in roles]
            embed = discord.Embed(
                title="<:check:1428163122710970508> Channel Roles Allowed",
                description=f"The following roles can now use `{command.name}` in {channel.mention}:",
                color=0x00ff88
            )
            embed.add_field(
                name="Allowed Roles",
                value="\n".join(f"• {mention}" for mention in role_mentions),
                inline=False
            )
        else:
            embed = discord.Embed(
                title="<:warning:1427471923805925397> Failed to Update Permission",
                description="There was an error updating the channel permission.",
                color=0xff6b6b
            )
        
        await ctx.send(embed=embed)
    
    @channel_permissions.command(name="deny")
    async def deny_roles_in_channel(self, ctx, command_name: str, 
                                  channel: discord.TextChannel, *roles: discord.Role):
        """Deny specific roles from using a command in a channel"""
        
        command = self.bot.get_command(command_name.lower())
        if not command:
            embed = discord.Embed(
                title="<:warning:1427471923805925397> Command Not Found",
                description=f"Command `{command_name}` doesn't exist.",
                color=0xff6b6b
            )
            await ctx.send(embed=embed)
            return
        
        if not roles:
            embed = discord.Embed(
                title="<:warning:1427471923805925397> No Roles Specified",
                description="You must specify at least one role.",
                color=0xff6b6b
            )
            await ctx.send(embed=embed)
            return
        
        role_ids = [role.id for role in roles]
        success = member_state_manager.set_channel_command_permission(
            ctx.guild.id,
            channel.id,
            command.name,
            True,
            denied_roles=role_ids,
            moderator_id=ctx.author.id
        )
        
        if success:
            role_mentions = [role.mention for role in roles]
            embed = discord.Embed(
                title="<:check:1428163122710970508> Channel Roles Denied",
                description=f"The following roles are now denied from using `{command.name}` in {channel.mention}:",
                color=0x00ff88
            )
            embed.add_field(
                name="Denied Roles",
                value="\n".join(f"• {mention}" for mention in role_mentions),
                inline=False
            )
        else:
            embed = discord.Embed(
                title="<:warning:1427471923805925397> Failed to Update Permission",
                description="There was an error updating the channel permission.",
                color=0xff6b6b
            )
        
        await ctx.send(embed=embed)
    
    # =================== COMMAND TOGGLES ===================
    
    @permissions.group(name="toggle", aliases=["cmd"])
    async def command_toggles(self, ctx):
        """Manage global and channel-specific command toggles"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="<:toggle:1427471506287362068> Command Toggle Management",
                color=0x00ff88
            )
            
            embed.add_field(
                name="Global Toggle",
                value="`permsys toggle global <command> <enabled>` - Enable/disable command server-wide",
                inline=False
            )
            
            embed.add_field(
                name="Channel Enable",
                value="`permsys toggle enable <command> <channels...>` - Enable command in specific channels",
                inline=False
            )
            
            embed.add_field(
                name="Channel Disable",
                value="`permsys toggle disable <command> <channels...>` - Disable command in specific channels",
                inline=False
            )
            
            embed.add_field(
                name="View Toggles",
                value="`permsys toggle list [command]` - View command toggle settings",
                inline=False
            )
            
            await ctx.send(embed=embed)
    
    @command_toggles.command(name="global")
    async def global_toggle(self, ctx, command_name: str, enabled: bool):
        """Enable or disable a command globally in the server"""
        
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
            ctx.guild.id,
            command.name,
            enabled_globally=enabled,
            moderator_id=ctx.author.id
        )
        
        if success:
            status = "enabled" if enabled else "disabled"
            embed = discord.Embed(
                title="<:check:1428163122710970508> Global Command Toggle Updated",
                description=f"Command `{command.name}` is now **{status}** server-wide.",
                color=0x00ff88
            )
        else:
            embed = discord.Embed(
                title="<:warning:1427471923805925397> Failed to Update Toggle",
                description="There was an error updating the command toggle.",
                color=0xff6b6b
            )
        
        await ctx.send(embed=embed)
    
    @command_toggles.command(name="enable")
    async def enable_in_channels(self, ctx, command_name: str, *channels: discord.TextChannel):
        """Enable a command in specific channels only"""
        
        command = self.bot.get_command(command_name.lower())
        if not command:
            embed = discord.Embed(
                title="<:warning:1427471923805925397> Command Not Found",
                description=f"Command `{command_name}` doesn't exist.",
                color=0xff6b6b
            )
            await ctx.send(embed=embed)
            return
        
        if not channels:
            embed = discord.Embed(
                title="<:warning:1427471923805925397> No Channels Specified",
                description="You must specify at least one channel.",
                color=0xff6b6b
            )
            await ctx.send(embed=embed)
            return
        
        channel_ids = [channel.id for channel in channels]
        success = member_state_manager.set_command_toggle(
            ctx.guild.id,
            command.name,
            enabled_globally=False,
            enabled_channels=channel_ids,
            moderator_id=ctx.author.id
        )
        
        if success:
            channel_mentions = [channel.mention for channel in channels]
            embed = discord.Embed(
                title="<:check:1428163122710970508> Command Enabled in Channels",
                description=f"Command `{command.name}` is now enabled only in:",
                color=0x00ff88
            )
            embed.add_field(
                name="Enabled Channels",
                value="\n".join(f"• {mention}" for mention in channel_mentions),
                inline=False
            )
        else:
            embed = discord.Embed(
                title="<:warning:1427471923805925397> Failed to Update Toggle",
                description="There was an error updating the command toggle.",
                color=0xff6b6b
            )
        
        await ctx.send(embed=embed)
    
    @command_toggles.command(name="disable")
    async def disable_in_channels(self, ctx, command_name: str, *channels: discord.TextChannel):
        """Disable a command in specific channels"""
        
        command = self.bot.get_command(command_name.lower())
        if not command:
            embed = discord.Embed(
                title="<:warning:1427471923805925397> Command Not Found",
                description=f"Command `{command_name}` doesn't exist.",
                color=0xff6b6b
            )
            await ctx.send(embed=embed)
            return
        
        if not channels:
            embed = discord.Embed(
                title="<:warning:1427471923805925397> No Channels Specified",
                description="You must specify at least one channel.",
                color=0xff6b6b
            )
            await ctx.send(embed=embed)
            return
        
        channel_ids = [channel.id for channel in channels]
        success = member_state_manager.set_command_toggle(
            ctx.guild.id,
            command.name,
            enabled_globally=True,
            disabled_channels=channel_ids,
            moderator_id=ctx.author.id
        )
        
        if success:
            channel_mentions = [channel.mention for channel in channels]
            embed = discord.Embed(
                title="<:check:1428163122710970508> Command Disabled in Channels",
                description=f"Command `{command.name}` is now disabled in:",
                color=0x00ff88
            )
            embed.add_field(
                name="Disabled Channels",
                value="\n".join(f"• {mention}" for mention in channel_mentions),
                inline=False
            )
        else:
            embed = discord.Embed(
                title="<:warning:1427471923805925397> Failed to Update Toggle",
                description="There was an error updating the command toggle.",
                color=0xff6b6b
            )
        
        await ctx.send(embed=embed)
    
    # =================== STATUS AND OVERVIEW ===================
    
    @permissions.command(name="status", aliases=["overview", "info"])
    async def permission_status(self, ctx):
        """View comprehensive permission status for the server"""
        
        embed = discord.Embed(
            title="<:gear:1427471588915150900> Permission System Status",
            description=f"Comprehensive overview for {ctx.guild.name}",
            color=0x00ff88
        )
        
        # Role permissions summary
        all_role_perms = permission_manager.list_command_permissions(ctx.guild.id)
        embed.add_field(
            name="<:role:1427471506287362068> Role Permissions",
            value=f"{len(all_role_perms)} commands have custom role permissions",
            inline=True
        )
        
        # Restoration settings
        restore_settings = member_state_manager.get_restoration_settings(ctx.guild.id)
        restore_status = "✅ Enabled" if restore_settings['restore_roles'] else "❌ Disabled"
        embed.add_field(
            name="<:backup:1427471506287362068> Role Restoration",
            value=restore_status,
            inline=True
        )
        
        # Member state summary
        embed.add_field(
            name="<:database:1427471506287362068> System Status",
            value="✅ All systems operational",
            inline=True
        )
        
        if all_role_perms:
            perm_summary = []
            for cmd, roles in list(all_role_perms.items())[:5]:  # Show first 5
                perm_summary.append(f"• `{cmd}` - {len(roles)} roles")
            
            if len(all_role_perms) > 5:
                perm_summary.append(f"... and {len(all_role_perms) - 5} more")
            
            embed.add_field(
                name="Recent Role Permissions",
                value="\n".join(perm_summary),
                inline=False
            )
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(AdvancedPermissions(bot))