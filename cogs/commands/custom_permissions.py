import discord
from discord.ext import commands
from utils.custom_permissions import permission_manager, require_custom_permissions
from utils.Tools import blacklist_check, ignore_check
from utils.error_helpers import StandardErrorHandler
from typing import Optional

class CustomPermissions(commands.Cog):
    """Manage custom role-based permissions for commands"""
    
    def __init__(self, bot):
        self.bot = bot
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    @commands.group(name="cmdperm", aliases=["commandperm", "customperm"])
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    async def command_permissions(self, ctx):
        """Manage custom role-based permissions for commands"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="<:gear:1427471588915150900> Custom Command Permissions",
                description="Manage which roles can use specific commands",
                color=0x00ff88
            )
            
            embed.add_field(
                name="<:plus:1427471506287362068> Add Role to Command",
                value="`cmdperm add <command> <role>` - Allow a role to use a command",
                inline=False
            )
            
            embed.add_field(
                name="<:minus:1427471506287362068> Remove Role from Command", 
                value="`cmdperm remove <command> <role>` - Remove a role from a command",
                inline=False
            )
            
            embed.add_field(
                name="<:list:1427471506287362068> View Permissions",
                value="`cmdperm list [command]` - View custom permissions",
                inline=False
            )
            
            embed.add_field(
                name="<:toggle:1427471506287362068> Toggle Custom Permissions",
                value="`cmdperm enable/disable <command>` - Enable/disable custom perms",
                inline=False
            )
            
            embed.add_field(
                name="<:info:1427471506287362068> How it Works",
                value="• Add roles to commands to override Discord permissions\n"
                      "• Only users with specified roles can use the command\n"
                      "• Falls back to Discord permissions if disabled\n"
                      "• Administrators can always manage permissions",
                inline=False
            )
            
            await ctx.send(embed=embed)
    
    @command_permissions.command(name="add")
    @commands.has_permissions(administrator=True)
    async def add_command_role(self, ctx, command_name: str, role: discord.Role):
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
        
        # Check if role is higher than user's highest role (unless they're owner)
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
                title="<:check:1428163122710970508> Role Added Successfully",
                description=f"Role {role.mention} can now use `{command.name}` command.",
                color=0x00ff88
            )
            
            # Show other roles that can use this command
            other_roles = permission_manager.get_command_roles(ctx.guild.id, command.name)
            other_roles = [r for r in other_roles if r != role.id]
            
            if other_roles:
                role_mentions = []
                for role_id in other_roles:
                    guild_role = ctx.guild.get_role(role_id)
                    if guild_role:
                        role_mentions.append(guild_role.mention)
                
                if role_mentions:
                    embed.add_field(
                        name="Other Authorized Roles",
                        value="\n".join(role_mentions),
                        inline=False
                    )
        else:
            embed = discord.Embed(
                title="<:warning:1427471923805925397> Failed to Add Role",
                description="There was an error adding the role permission.",
                color=0xff6b6b
            )
        
        await ctx.send(embed=embed)
    
    @command_permissions.command(name="remove", aliases=["rm", "del"])
    @commands.has_permissions(administrator=True)
    async def remove_command_role(self, ctx, command_name: str, role: discord.Role):
        """Remove a role from a specific command"""
        
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
        
        success = permission_manager.remove_command_role(
            ctx.guild.id,
            command.name,
            role.id
        )
        
        if success:
            embed = discord.Embed(
                title="<:check:1428163122710970508> Role Removed Successfully",
                description=f"Role {role.mention} can no longer use `{command.name}` command.",
                color=0x00ff88
            )
        else:
            embed = discord.Embed(
                title="<:warning:1427471923805925397> Role Not Found",
                description=f"Role {role.mention} wasn't authorized to use `{command.name}`.",
                color=0xff6b6b
            )
        
        await ctx.send(embed=embed)
    
    @command_permissions.command(name="list", aliases=["show", "view"])
    async def list_command_permissions(self, ctx, command_name: Optional[str] = None):
        """List custom permissions for commands"""
        
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
                title=f"<:list:1427471506287362068> Permissions for `{command.name}`",
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
            # Show all custom permissions
            all_permissions = permission_manager.list_command_permissions(ctx.guild.id)
            
            embed = discord.Embed(
                title="<:list:1427471506287362068> All Custom Command Permissions",
                description=f"Custom permissions configured in {ctx.guild.name}",
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
    
    @command_permissions.command(name="enable")
    @commands.has_permissions(administrator=True)
    async def enable_custom_permissions(self, ctx, command_name: str):
        """Enable custom permissions for a command"""
        
        command = self.bot.get_command(command_name.lower())
        if not command:
            embed = discord.Embed(
                title="<:warning:1427471923805925397> Command Not Found",
                description=f"Command `{command_name}` doesn't exist.",
                color=0xff6b6b
            )
            await ctx.send(embed=embed)
            return
        
        success = permission_manager.enable_custom_permissions(ctx.guild.id, command.name)
        
        if success:
            embed = discord.Embed(
                title="<:check:1428163122710970508> Custom Permissions Enabled",
                description=f"Custom role permissions are now active for `{command.name}`.",
                color=0x00ff88
            )
        else:
            embed = discord.Embed(
                title="<:warning:1427471923805925397> Failed to Enable",
                description="There was an error enabling custom permissions.",
                color=0xff6b6b
            )
        
        await ctx.send(embed=embed)
    
    @command_permissions.command(name="disable")
    @commands.has_permissions(administrator=True)
    async def disable_custom_permissions(self, ctx, command_name: str):
        """Disable custom permissions for a command (fall back to Discord permissions)"""
        
        command = self.bot.get_command(command_name.lower())
        if not command:
            embed = discord.Embed(
                title="<:warning:1427471923805925397> Command Not Found",
                description=f"Command `{command_name}` doesn't exist.",
                color=0xff6b6b
            )
            await ctx.send(embed=embed)
            return
        
        success = permission_manager.disable_custom_permissions(ctx.guild.id, command.name)
        
        if success:
            embed = discord.Embed(
                title="<:check:1428163122710970508> Custom Permissions Disabled",
                description=f"Command `{command.name}` now uses Discord permissions.",
                color=0x00ff88
            )
        else:
            embed = discord.Embed(
                title="<:warning:1427471923805925397> Failed to Disable",
                description="There was an error disabling custom permissions.",
                color=0xff6b6b
            )
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(CustomPermissions(bot))