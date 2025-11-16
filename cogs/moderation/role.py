import discord
from discord.ext import commands
from discord.ui import Button, View
import asyncio
import re
import traceback
from utils.Tools import blacklist_check, ignore_check

time_regex = re.compile(r"(?:(\d{1,5})(h|s|m|d))+?")
time_dict = {"h": 3600, "s": 1, "m": 60, "d": 86400}

class RoleConverter(commands.Converter):
    """Custom role converter that accepts role mentions, IDs, or names (case-insensitive)"""
    async def convert(self, ctx, argument) -> discord.Role:
        # Try default converter first (handles mentions and IDs)
        try:
            return await commands.RoleConverter().convert(ctx, argument)
        except commands.BadArgument:
            pass
        
        # Ensure guild exists
        if ctx.guild is None:
            raise commands.BadArgument("This command can only be used in a server.")
        
        # Search by name (case-insensitive)
        argument_lower = argument.lower()
        for role in ctx.guild.roles:
            if role.name.lower() == argument_lower:
                return role
        
        # Search by partial name match (case-insensitive)
        for role in ctx.guild.roles:
            if argument_lower in role.name.lower():
                return role
        
        raise commands.BadArgument(f'Role "{argument}" not found.')

def convert(argument):
    args = argument.lower()
    matches = re.findall(time_regex, args)
    time = 0
    for key, value in matches:
        try:
            time += time_dict[value] * float(key)
        except KeyError:
            raise commands.BadArgument(f"{value} is an invalid time key! h|m|s|d are valid arguments")
        except ValueError:
            raise commands.BadArgument(f"{key} is not a number!")
    return round(time)

class Role(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = 0x2B2D31

    async def _safe_interaction_response(self, interaction, content=None, embed=None, edit=True):
        """Safely handle interaction responses with proper error handling"""
        try:
            if interaction.response.is_done():
                # Already responded, use followup
                if edit:
                    return  # Can't edit if already responded
                else:
                    return await interaction.followup.send(content=content, embed=embed, ephemeral=True)
            else:
                # First response
                if edit:
                    return await interaction.response.edit_message(content=content, embed=embed, view=None)
                else:
                    return await interaction.response.send_message(content=content, embed=embed, ephemeral=True)
        except discord.NotFound:
            # Interaction expired/deleted
            pass
        except discord.InteractionResponded:
            # Already responded, try followup
            try:
                if not edit:
                    await interaction.followup.send(content=content, embed=embed, ephemeral=True)
            except:
                pass
        except Exception as e:
            # Last resort error handling
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(f"Error: {str(e)}", ephemeral=True)
                else:
                    await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)
            except:
                pass

    @commands.command(name="humans", help="Gives role to all humans in the guild")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 15, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def role_humans(self, ctx, *, role: discord.Role = commands.parameter(converter=RoleConverter)):
        # Validate bot permissions
        if not ctx.guild.me.guild_permissions.manage_roles:
            return await self._send_response(ctx, embed=discord.Embed(
                description="<:feast_warning:1400143131990560830> I don't have permission to manage roles!",
                color=self.color
            ))
        
        # Validate role hierarchy
        if role >= ctx.guild.me.top_role:
            return await self._send_response(ctx, embed=discord.Embed(
                description=f"<:feast_warning:1400143131990560830> I can't manage {role.mention} because it's higher than or equal to my highest role!",
                color=self.color
            ))
        
        # Validate user can manage this role (unless they're the owner)
        if ctx.author != ctx.guild.owner and role >= ctx.author.top_role:
            return await self._send_response(ctx, embed=discord.Embed(
                description=f"<:feast_warning:1400143131990560830> You can't manage {role.mention} because it's higher than or equal to your highest role!",
                color=self.color
            ))
        
        humans = [m for m in ctx.guild.members if not m.bot and role not in m.roles]
        if not humans:
            return await self._send_response(ctx, embed=discord.Embed(description=f"All humans already have {role.mention}.", color=self.color))
        view = View(timeout=60.0)  # 60 second timeout
        
        async def on_timeout():
            # View will automatically become unresponsive after timeout
            pass
        
        view.on_timeout = on_timeout
        confirm = Button(label="Confirm", style=discord.ButtonStyle.green)
        cancel = Button(label="Cancel", style=discord.ButtonStyle.red)
        async def confirm_cb(interaction):
            try:
                if interaction.user != ctx.author:
                    return await interaction.response.send_message("Not for you!", ephemeral=True)
                
                # Check if interaction is still valid
                if interaction.response.is_done():
                    return
                
                count = 0
                for m in humans:
                    try:
                        await m.add_roles(role, reason=f"Bulk role by {ctx.author}")
                        count += 1
                    except Exception:
                        pass
                
                await interaction.response.edit_message(
                    embed=discord.Embed(description=f"Added {role.mention} to {count} humans.", color=self.color), 
                    view=None
                )
            except discord.NotFound:
                # Interaction expired/deleted
                pass
            except discord.InteractionResponded:
                # Already responded to interaction
                try:
                    await interaction.followup.send(f"Added {role.mention} to {count} humans.", ephemeral=True)
                except:
                    pass
            except Exception as e:
                try:
                    if not interaction.response.is_done():
                        await interaction.response.send_message(f"Error: {str(e)}", ephemeral=True)
                    else:
                        await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)
                except:
                    pass
                    
        async def cancel_cb(interaction):
            try:
                if interaction.user != ctx.author:
                    return await interaction.response.send_message("Not for you!", ephemeral=True)
                
                if interaction.response.is_done():
                    return
                    
                await interaction.response.edit_message(
                    embed=discord.Embed(description="Action cancelled.", color=self.color), 
                    view=None
                )
            except discord.NotFound:
                # Interaction expired/deleted
                pass
            except discord.InteractionResponded:
                # Already responded to interaction
                try:
                    await interaction.followup.send("Action cancelled.", ephemeral=True)
                except:
                    pass
            except Exception as e:
                try:
                    if not interaction.response.is_done():
                        await interaction.response.send_message(f"Error: {str(e)}", ephemeral=True)
                    else:
                        await interaction.followup.send(f"Error: {str(e)}", ephemeral=True)
                except:
                    pass
        confirm.callback = confirm_cb
        cancel.callback = cancel_cb
        view.add_item(confirm)
        view.add_item(cancel)
        await self._send_response(ctx, embed=discord.Embed(description=f"Assign {role.mention} to {len(humans)} humans?", color=self.color), view=view)

    @commands.command(name="bots", help="Gives role to all bots in the guild")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def role_bots(self, ctx, *, role: discord.Role = commands.parameter(converter=RoleConverter)):
        # Validate bot permissions
        if not ctx.guild.me.guild_permissions.manage_roles:
            return await self._send_response(ctx, embed=discord.Embed(
                description="<:feast_warning:1400143131990560830> I don't have permission to manage roles!",
                color=self.color
            ))
        
        # Validate role hierarchy
        if role >= ctx.guild.me.top_role:
            return await self._send_response(ctx, embed=discord.Embed(
                description=f"<:feast_warning:1400143131990560830> I can't manage {role.mention} because it's higher than or equal to my highest role!",
                color=self.color
            ))
        
        # Validate user can manage this role (unless they're the owner)
        if ctx.author != ctx.guild.owner and role >= ctx.author.top_role:
            return await self._send_response(ctx, embed=discord.Embed(
                description=f"<:feast_warning:1400143131990560830> You can't manage {role.mention} because it's higher than or equal to your highest role!",
                color=self.color
            ))
        
        bots = [m for m in ctx.guild.members if m.bot and role not in m.roles]
        if not bots:
            return await self._send_response(ctx, embed=discord.Embed(description=f"All bots already have {role.mention}.", color=self.color))
        view = View()
        confirm = Button(label="Confirm", style=discord.ButtonStyle.green)
        cancel = Button(label="Cancel", style=discord.ButtonStyle.red)
        async def confirm_cb(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("Not for you!", ephemeral=True)
            count = 0
            for m in bots:
                try:
                    await m.add_roles(role, reason=f"Bulk role by {ctx.author}")
                    count += 1
                except Exception:
                    pass
            await interaction.response.edit_message(embed=discord.Embed(description=f"Added {role.mention} to {count} bots.", color=self.color), view=None)
        async def cancel_cb(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("Not for you!", ephemeral=True)
            await interaction.response.edit_message(embed=discord.Embed(description="Action cancelled.", color=self.color), view=None)
        confirm.callback = confirm_cb
        cancel.callback = cancel_cb
        view.add_item(confirm)
        view.add_item(cancel)
        await self._send_response(ctx, embed=discord.Embed(description=f"Assign {role.mention} to {len(bots)} bots?", color=self.color), view=view)

    @commands.command(name="unverified", help="Gives role to all unverified members in the guild")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def role_unverified(self, ctx, *, role: discord.Role = commands.parameter(converter=RoleConverter)):
        # Validate bot permissions
        if not ctx.guild.me.guild_permissions.manage_roles:
            return await self._send_response(ctx, embed=discord.Embed(
                description="<:feast_warning:1400143131990560830> I don't have permission to manage roles!",
                color=self.color
            ))
        
        # Validate role hierarchy
        if role >= ctx.guild.me.top_role:
            return await self._send_response(ctx, embed=discord.Embed(
                description=f"<:feast_warning:1400143131990560830> I can't manage {role.mention} because it's higher than or equal to my highest role!",
                color=self.color
            ))
        
        # Validate user can manage this role (unless they're the owner)
        if ctx.author != ctx.guild.owner and role >= ctx.author.top_role:
            return await self._send_response(ctx, embed=discord.Embed(
                description=f"<:feast_warning:1400143131990560830> You can't manage {role.mention} because it's higher than or equal to your highest role!",
                color=self.color
            ))
        
        unverified = [m for m in ctx.guild.members if m.avatar is None and role not in m.roles]
        if not unverified:
            return await self._send_response(ctx, embed=discord.Embed(description=f"All unverified members already have {role.mention}.", color=self.color))
        view = View()
        confirm = Button(label="Confirm", style=discord.ButtonStyle.green)
        cancel = Button(label="Cancel", style=discord.ButtonStyle.red)
        async def confirm_cb(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("Not for you!", ephemeral=True)
            count = 0
            for m in unverified:
                try:
                    await m.add_roles(role, reason=f"Bulk role by {ctx.author}")
                    count += 1
                except Exception:
                    pass
            await interaction.response.edit_message(embed=discord.Embed(description=f"Added {role.mention} to {count} unverified members.", color=self.color), view=None)
        async def cancel_cb(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("Not for you!", ephemeral=True)
            await interaction.response.edit_message(embed=discord.Embed(description="Action cancelled.", color=self.color), view=None)
        confirm.callback = confirm_cb
        cancel.callback = cancel_cb
        view.add_item(confirm)
        view.add_item(cancel)
        await self._send_response(ctx, embed=discord.Embed(description=f"Assign {role.mention} to {len(unverified)} unverified members?", color=self.color), view=view)

    @commands.command(name="all", help="Gives role to all members in the guild")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 15, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def role_all(self, ctx, *, role: discord.Role = commands.parameter(converter=RoleConverter)):
        # Validate bot permissions
        if not ctx.guild.me.guild_permissions.manage_roles:
            return await self._send_response(ctx, embed=discord.Embed(
                description="<:feast_warning:1400143131990560830> I don't have permission to manage roles!",
                color=self.color
            ))
        
        # Validate role hierarchy
        if role >= ctx.guild.me.top_role:
            return await self._send_response(ctx, embed=discord.Embed(
                description=f"<:feast_warning:1400143131990560830> I can't manage {role.mention} because it's higher than or equal to my highest role!",
                color=self.color
            ))
        
        # Validate user can manage this role (unless they're the owner)
        if ctx.author != ctx.guild.owner and role >= ctx.author.top_role:
            return await self._send_response(ctx, embed=discord.Embed(
                description=f"<:feast_warning:1400143131990560830> You can't manage {role.mention} because it's higher than or equal to your highest role!",
                color=self.color
            ))
        
        everyone = [m for m in ctx.guild.members if role not in m.roles]
        if not everyone:
            return await self._send_response(ctx, embed=discord.Embed(description=f"All members already have {role.mention}.", color=self.color))
        view = View()
        confirm = Button(label="Confirm", style=discord.ButtonStyle.green)
        cancel = Button(label="Cancel", style=discord.ButtonStyle.red)
        async def confirm_cb(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("Not for you!", ephemeral=True)
            count = 0
            for m in everyone:
                try:
                    await m.add_roles(role, reason=f"Bulk role by {ctx.author}")
                    count += 1
                except Exception:
                    pass
            await interaction.response.edit_message(embed=discord.Embed(description=f"Added {role.mention} to {count} members.", color=self.color), view=None)
        async def cancel_cb(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("Not for you!", ephemeral=True)
            await interaction.response.edit_message(embed=discord.Embed(description="Action cancelled.", color=self.color), view=None)
        confirm.callback = confirm_cb
        cancel.callback = cancel_cb
        view.add_item(confirm)
        view.add_item(cancel)
        await self._send_response(ctx, embed=discord.Embed(description=f"Assign {role.mention} to {len(everyone)} members?", color=self.color), view=view)

    def cog_load(self):
        # Register advanced subcommands to the role group
        self.role.add_command(self.role_humans)
        self.role.add_command(self.role_bots)
        self.role.add_command(self.role_unverified)
        self.role.add_command(self.role_all)

    @commands.group(name="removerole", invoke_without_command=True, aliases=["rrole"], help="Remove a role from all members.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def rrole(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @rrole.command(name="humans", help="Removes a role from all humans in the server.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def rrole_humans(self, ctx, *, role: discord.Role):
        humans = [m for m in ctx.guild.members if not m.bot and role in m.roles]
        if not humans:
            return await self._send_response(ctx, embed=discord.Embed(description=f"No humans have {role.mention}.", color=self.color))
        view = View()
        confirm = Button(label="Confirm", style=discord.ButtonStyle.green)
        cancel = Button(label="Cancel", style=discord.ButtonStyle.red)
        async def confirm_cb(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("Not for you!", ephemeral=True)
            count = 0
            for m in humans:
                try:
                    await m.remove_roles(role, reason=f"Bulk remove by {ctx.author}")
                    count += 1
                except Exception:
                    pass
            await interaction.response.edit_message(embed=discord.Embed(description=f"Removed {role.mention} from {count} humans.", color=self.color), view=None)
        async def cancel_cb(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("Not for you!", ephemeral=True)
            await interaction.response.edit_message(embed=discord.Embed(description="Action cancelled.", color=self.color), view=None)
        confirm.callback = confirm_cb
        cancel.callback = cancel_cb
        view.add_item(confirm)
        view.add_item(cancel)
        await self._send_response(ctx, embed=discord.Embed(description=f"Remove {role.mention} from {len(humans)} humans?", color=self.color), view=view)

    @rrole.command(name="bots", help="Removes a role from all bots in the server.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def rrole_bots(self, ctx, *, role: discord.Role):
        bots = [m for m in ctx.guild.members if m.bot and role in m.roles]
        if not bots:
            return await self._send_response(ctx, embed=discord.Embed(description=f"No bots have {role.mention}.", color=self.color))
        view = View()
        confirm = Button(label="Confirm", style=discord.ButtonStyle.green)
        cancel = Button(label="Cancel", style=discord.ButtonStyle.red)
        async def confirm_cb(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("Not for you!", ephemeral=True)
            count = 0
            for m in bots:
                try:
                    await m.remove_roles(role, reason=f"Bulk remove by {ctx.author}")
                    count += 1
                except Exception:
                    pass
            await interaction.response.edit_message(embed=discord.Embed(description=f"Removed {role.mention} from {count} bots.", color=self.color), view=None)
        async def cancel_cb(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("Not for you!", ephemeral=True)
            await interaction.response.edit_message(embed=discord.Embed(description="Action cancelled.", color=self.color), view=None)
        confirm.callback = confirm_cb
        cancel.callback = cancel_cb
        view.add_item(confirm)
        view.add_item(cancel)
        await self._send_response(ctx, embed=discord.Embed(description=f"Remove {role.mention} from {len(bots)} bots?", color=self.color), view=view)

    @rrole.command(name="all", help="Removes a role from all members in the server.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def rrole_all(self, ctx, *, role: discord.Role):
        everyone = [m for m in ctx.guild.members if role in m.roles]
        if not everyone:
            return await self._send_response(ctx, embed=discord.Embed(description=f"No members have {role.mention}.", color=self.color))
        view = View()
        confirm = Button(label="Confirm", style=discord.ButtonStyle.green)
        cancel = Button(label="Cancel", style=discord.ButtonStyle.red)
        async def confirm_cb(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("Not for you!", ephemeral=True)
            count = 0
            for m in everyone:
                try:
                    await m.remove_roles(role, reason=f"Bulk remove by {ctx.author}")
                    count += 1
                except Exception:
                    pass
            await interaction.response.edit_message(embed=discord.Embed(description=f"Removed {role.mention} from {count} members.", color=self.color), view=None)
        async def cancel_cb(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("Not for you!", ephemeral=True)
            await interaction.response.edit_message(embed=discord.Embed(description="Action cancelled.", color=self.color), view=None)
        confirm.callback = confirm_cb
        cancel.callback = cancel_cb
        view.add_item(confirm)
        view.add_item(cancel)
        await self._send_response(ctx, embed=discord.Embed(description=f"Remove {role.mention} from {len(everyone)} members?", color=self.color), view=view)

    @rrole.command(name="unverified", help="Removes a role from all unverified members in the server.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def rrole_unverified(self, ctx, *, role: discord.Role):
        unverified = [m for m in ctx.guild.members if m.avatar is None and role in m.roles]
        if not unverified:
            return await self._send_response(ctx, embed=discord.Embed(description=f"No unverified members have {role.mention}.", color=self.color))
        view = View()
        confirm = Button(label="Confirm", style=discord.ButtonStyle.green)
        cancel = Button(label="Cancel", style=discord.ButtonStyle.red)
        async def confirm_cb(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("Not for you!", ephemeral=True)
            count = 0
            for m in unverified:
                try:
                    await m.remove_roles(role, reason=f"Bulk remove by {ctx.author}")
                    count += 1
                except Exception:
                    pass
            await interaction.response.edit_message(embed=discord.Embed(description=f"Removed {role.mention} from {count} unverified members.", color=self.color), view=None)
        async def cancel_cb(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("Not for you!", ephemeral=True)
            await interaction.response.edit_message(embed=discord.Embed(description="Action cancelled.", color=self.color), view=None)
        confirm.callback = confirm_cb
        cancel.callback = cancel_cb
        view.add_item(confirm)
        view.add_item(cancel)
        await self._send_response(ctx, embed=discord.Embed(description=f"Remove {role.mention} from {len(unverified)} unverified members?", color=self.color), view=view)

    async def _send_response(self, ctx, *args, **kwargs):
        if hasattr(ctx, 'interaction') and ctx.interaction is not None and not ctx.interaction.response.is_done():
            return await ctx.interaction.response.send_message(*args, **kwargs)
        elif hasattr(ctx, 'reply'):
            return await ctx.reply(*args, **kwargs)
        else:
            return await ctx.send(*args, **kwargs)

    @commands.group(name="role", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(manage_roles=True)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    async def role(self, ctx, member: discord.Member, *, role: discord.Role):
        try:
            if not ctx.guild.me.guild_permissions.manage_roles:
                return await self._send_response(ctx, "<:feast_warning:1400143131990560830> I don't have permission to manage roles!")
            if role >= ctx.guild.me.top_role:
                error = discord.Embed(color=self.color, description="I can't manage roles for a user with a higher or equal role!")
                error.set_author(name="Error")
                error.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
                return await self._send_response(ctx, embed=error)
            if ctx.author != ctx.guild.owner and ctx.author.top_role <= member.top_role:
                error = discord.Embed(color=self.color, description="You can't manage roles for a user with a higher or equal role than yours!")
                error.set_author(name="Access Denied")
                error.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
                return await self._send_response(ctx, embed=error)
            
            if role not in member.roles:
                await member.add_roles(role, reason=f"Role added by {ctx.author} (ID: {ctx.author.id})")
                success = discord.Embed(color=self.color, description=f"Successfully **added** role {role.name} to {member.mention}.")
                success.set_author(name="Role Added")
                success.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            else:
                await member.remove_roles(role, reason=f"Role removed by {ctx.author} (ID: {ctx.author.id})")
                success = discord.Embed(color=self.color, description=f"Successfully **removed** role {role.name} from {member.mention}.")
                success.set_author(name="Role Removed")
                success.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await self._send_response(ctx, embed=success)
        except discord.Forbidden:
            error = discord.Embed(color=self.color, description="<:feast_warning:1400143131990560830> I don't have permission to manage roles for this user!")
            await self._send_response(ctx, embed=error)
        except Exception as e:
            error = discord.Embed(color=self.color, description=f"<:feast_warning:1400143131990560830> An unexpected error occurred: {str(e)}")
            await self._send_response(ctx, embed=error)

    @role.command(help="Give role to member for particular time")
    @commands.bot_has_permissions(manage_roles=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 7, commands.BucketType.user)
    @commands.has_permissions(manage_roles=True)
    async def temp(self, ctx, role: discord.Role, time, *, user: discord.Member):
        if ctx.author != ctx.guild.owner and role.position >= ctx.author.top_role.position:
            embed = discord.Embed(description=f"You can't manage a role that is higher or equal to your top role!", color=self.color)
            embed.set_author(name="Error")
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            return await self._send_response(ctx, embed=embed)
        if role.position >= ctx.guild.me.top_role.position:
            embed1 = discord.Embed(description=f"{role} is higher than my top role, move my role above {role}.", color=self.color)
            embed1.set_author(name="Error")
            embed1.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            return await self._send_response(ctx, embed=embed1)
        seconds = convert(time)
        await user.add_roles(role, reason=None)
        success = discord.Embed(description=f"Successfully added {role.mention} to {user.mention} .", color=self.color)
        success.set_author(name="Success")
        success.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        await self._send_response(ctx, embed=success)
        await asyncio.sleep(seconds)
        await user.remove_roles(role)

    @role.command(help="Delete a role in the guild")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 7, commands.BucketType.user)
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def delete(self, ctx, *, role: discord.Role):
        if ctx.author != ctx.guild.owner and role.position >= ctx.author.top_role.position:
            embed = discord.Embed(description=f"You cannot delete a role that is higher or equal to your top role!", color=self.color)
            embed.set_author(name="Error")
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            return await self._send_response(ctx, embed=embed)
        if role.position >= ctx.guild.me.top_role.position:
            embed = discord.Embed(description=f"I cannot delete {role} because it is higher than my top role. Please move my role above {role}.", color=self.color)
            embed.set_author(name="Error")
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            return await self._send_response(ctx, embed=embed)
        if role is None:
            embed = discord.Embed(description=f"No role named {role} found in this server.", color=self.color)
            embed.set_author(name="Error")
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            return await self._send_response(ctx, embed=embed)
        try:
            await role.delete(reason=f"Role deleted by {ctx.author} (ID: {ctx.author.id})")
            embed = discord.Embed(description=f"Successfully deleted role {role.name}.", color=self.color)
            embed.set_author(name="Role Deleted")
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await self._send_response(ctx, embed=embed)
        except discord.Forbidden:
            embed = discord.Embed(description=f"I don't have permission to delete this role!", color=self.color)
            embed.set_author(name="Error")
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await self._send_response(ctx, embed=embed)
        except Exception as e:
            embed = discord.Embed(description=f"An unexpected error occurred: {str(e)}", color=self.color)
            embed.set_author(name="Error")
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await self._send_response(ctx, embed=embed)

    @role.command(help="Create a role in the guild")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 7, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def create(self, ctx, *, name):
        embed = discord.Embed(description=f"Successfully created a role named {name}.", color=self.color)
        embed.set_author(name="Success")
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        await ctx.guild.create_role(name=name, color=discord.Color.default())
        await self._send_response(ctx, embed=embed)

    @role.command(help="Renames a role in the server.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def rename(self, ctx, role: discord.Role, *, newname):
        if role.position >= ctx.author.top_role.position:
            embed = discord.Embed(description=f"You can't manage the role {role.mention} because it is higher or equal to your top role.", color=self.color)
            embed.set_author(name="Error")
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            return await self._send_response(ctx, embed=embed)
        if role.position >= ctx.guild.me.top_role.position:
            embed = discord.Embed(description=f"I can't manage the role {role.mention} because it is higher than my top role.", color=self.color)
            embed.set_author(name="Error")
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            return await self._send_response(ctx, embed=embed)
        await role.edit(name=newname)
        embed = discord.Embed(description=f"Role {role.name} has been renamed to {newname}.", color=self.color)
        embed.set_author(name="Success")
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        await self._send_response(ctx, embed=embed)

    @role.error
    async def role_error(self, ctx, error):
        """Error handler for role command group"""
        try:
            if isinstance(error, commands.MissingRequiredArgument):
                # Handle missing arguments
                if error.param.name == "member":
                    embed = discord.Embed(
                        color=self.color, 
                        description="<:feast_warning:1400143131990560830> Please specify a member to manage roles for!\n\n**Usage:** `role <member> <role>`\n**Example:** `role @user Admin`"
                    )
                    embed.set_author(name="Missing Member")
                elif error.param.name == "role":
                    embed = discord.Embed(
                        color=self.color, 
                        description="<:feast_warning:1400143131990560830> Please specify a role to add/remove!\n\n**Usage:** `role <member> <role>`\n**Example:** `role @user Admin`"
                    )
                    embed.set_author(name="Missing Role")
                else:
                    embed = discord.Embed(
                        color=self.color, 
                        description=f"<:feast_warning:1400143131990560830> Missing required argument: `{error.param.name}`\n\n**Usage:** `role <member> <role>`"
                    )
                    embed.set_author(name="Missing Argument")
                
                embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
                await self._send_response(ctx, embed=embed)
            elif isinstance(error, commands.RoleNotFound):
                embed = discord.Embed(
                    color=self.color, 
                    description=f"<:feast_warning:1400143131990560830> Role `{error.argument}` not found! Please check the role name and try again."
                )
                embed.set_author(name="Role Not Found")
                embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
                await self._send_response(ctx, embed=embed)
            elif isinstance(error, commands.MemberNotFound):
                embed = discord.Embed(
                    color=self.color, 
                    description=f"<:feast_warning:1400143131990560830> Member `{error.argument}` not found! Please check the member and try again."
                )
                embed.set_author(name="Member Not Found")
                embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
                await self._send_response(ctx, embed=embed)
            elif isinstance(error, commands.CommandOnCooldown):
                embed = discord.Embed(
                    color=self.color, 
                    description=f"<:feast_warning:1400143131990560830> Command is on cooldown! Try again in {error.retry_after:.1f} seconds."
                )
                embed.set_author(name="Command Cooldown")
                embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
                await self._send_response(ctx, embed=embed)
            elif isinstance(error, commands.MissingPermissions):
                embed = discord.Embed(
                    color=self.color, 
                    description=f"<:feast_warning:1400143131990560830> You don't have permission to use this command! Missing: {', '.join(error.missing_permissions)}"
                )
                embed.set_author(name="Missing Permissions")
                embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
                await self._send_response(ctx, embed=embed)
            elif isinstance(error, commands.BotMissingPermissions):
                embed = discord.Embed(
                    color=self.color, 
                    description=f"<:feast_warning:1400143131990560830> I don't have the required permissions! Missing: {', '.join(error.missing_permissions)}"
                )
                embed.set_author(name="Bot Missing Permissions")
                embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
                await self._send_response(ctx, embed=embed)
            elif isinstance(error, commands.MaxConcurrencyReached):
                embed = discord.Embed(
                    color=self.color, 
                    description="<:feast_warning:1400143131990560830> Another role operation is already in progress! Please wait for it to complete."
                )
                embed.set_author(name="Operation In Progress")
                embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
                await self._send_response(ctx, embed=embed)
            else:
                # Handle any other errors
                embed = discord.Embed(
                    color=self.color, 
                    description=f"<:feast_warning:1400143131990560830> An unexpected error occurred: {str(error)}"
                )
                embed.set_author(name="Error")
                embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
                await self._send_response(ctx, embed=embed)
                # Log the error for debugging
                print(f"Role command error: {error}")
                traceback.print_exception(type(error), error, error.__traceback__)
        except Exception as e:
            # Fallback error handling
            try:
                await ctx.send(f"<:feast_warning:1400143131990560830> An error occurred while handling the error: {str(e)}")
            except:
                pass  # If we can't even send this, there's nothing more we can do

    @role_all.error
    async def role_all_error(self, ctx, error):
        """Error handler for role all command"""
        await self._handle_role_command_error(ctx, error)

    @role_humans.error
    async def role_humans_error(self, ctx, error):
        """Error handler for role humans command"""
        await self._handle_role_command_error(ctx, error)

    @role_bots.error
    async def role_bots_error(self, ctx, error):
        """Error handler for role bots command"""
        await self._handle_role_command_error(ctx, error)

    @role_unverified.error
    async def role_unverified_error(self, ctx, error):
        """Error handler for role unverified command"""
        await self._handle_role_command_error(ctx, error)

    async def _handle_role_command_error(self, ctx, error):
        """Shared error handler for all role subcommands"""
        try:
            if isinstance(error, commands.CommandOnCooldown):
                embed = discord.Embed(
                    color=self.color, 
                    description=f"<:feast_warning:1400143131990560830> Command is on cooldown! Try again in {error.retry_after:.1f} seconds."
                )
                embed.set_author(name="Command Cooldown")
                embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
                await self._send_response(ctx, embed=embed)
            elif isinstance(error, commands.MissingPermissions):
                embed = discord.Embed(
                    color=self.color, 
                    description=f"<:feast_warning:1400143131990560830> You don't have permission to use this command! Missing: {', '.join(error.missing_permissions)}"
                )
                embed.set_author(name="Missing Permissions")
                embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
                await self._send_response(ctx, embed=embed)
            elif isinstance(error, commands.BotMissingPermissions):
                embed = discord.Embed(
                    color=self.color, 
                    description=f"<:feast_warning:1400143131990560830> I don't have the required permissions! Missing: {', '.join(error.missing_permissions)}"
                )
                embed.set_author(name="Bot Missing Permissions")
                embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
                await self._send_response(ctx, embed=embed)
            elif isinstance(error, commands.MaxConcurrencyReached):
                embed = discord.Embed(
                    color=self.color, 
                    description="<:feast_warning:1400143131990560830> Another role operation is already in progress! Please wait for it to complete."
                )
                embed.set_author(name="Operation In Progress")
                embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
                await self._send_response(ctx, embed=embed)
            elif isinstance(error, commands.RoleNotFound):
                embed = discord.Embed(
                    color=self.color, 
                    description=f"<:feast_warning:1400143131990560830> Role `{error.argument}` not found! Please check the role name and try again."
                )
                embed.set_author(name="Role Not Found")
                embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
                await self._send_response(ctx, embed=embed)
            elif isinstance(error, commands.MissingRequiredArgument):
                embed = discord.Embed(
                    color=self.color, 
                    description=f"<:feast_warning:1400143131990560830> Missing required argument: `{error.param.name}`\n\nPlease specify a role to assign."
                )
                embed.set_author(name="Missing Argument")
                embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
                await self._send_response(ctx, embed=embed)
            else:
                # Handle any other errors
                embed = discord.Embed(
                    color=self.color, 
                    description=f"<:feast_warning:1400143131990560830> An unexpected error occurred: {str(error)}"
                )
                embed.set_author(name="Error")
                embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
                await self._send_response(ctx, embed=embed)
                # Log the error for debugging
                print(f"Role subcommand error: {error}")
        except Exception as e:
            # Fallback error handling
            try:
                await ctx.send(f"<:feast_warning:1400143131990560830> An error occurred while handling the error: {str(e)}")
            except:
                pass  # If we can't even send this, there's nothing more we can do

    @role.command(help="Edit role permissions using dropdown menus")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def permissions(self, ctx, *, role: discord.Role):
        """Edit a role's permissions using interactive dropdown menus"""
        # Check role hierarchy
        if role.position >= ctx.author.top_role.position:
            embed = discord.Embed(description=f"You can't manage the role {role.mention} because it is higher or equal to your top role.", color=self.color)
            embed.set_author(name="Error")
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            return await self._send_response(ctx, embed=embed)
        
        if role.position >= ctx.guild.me.top_role.position:
            embed = discord.Embed(description=f"I can't manage the role {role.mention} because it is higher than my top role.", color=self.color)
            embed.set_author(name="Error")
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            return await self._send_response(ctx, embed=embed)
        
        # Create the permission editor view
        view = RolePermissionEditor(role, ctx.author, self.color)
        embed = view.create_embed()
        
        await self._send_response(ctx, embed=embed, view=view)


class RolePermissionEditor(discord.ui.View):
    def __init__(self, role: discord.Role, author: discord.Member, color: int):
        super().__init__(timeout=300)
        self.role = role
        self.author = author
        self.color = color
        
        # Common permissions grouped by category
        self.permission_categories = {
            "General": [
                ("view_channel", "View Channels"),
                ("send_messages", "Send Messages"),
                ("read_message_history", "Read Message History"),
                ("use_external_emojis", "Use External Emojis"),
                ("add_reactions", "Add Reactions"),
                ("embed_links", "Embed Links"),
                ("attach_files", "Attach Files"),
                ("mention_everyone", "Mention @everyone"),
            ],
            "Voice": [
                ("connect", "Connect to Voice"),
                ("speak", "Speak in Voice"),
                ("use_voice_activation", "Use Voice Activity"),
                ("mute_members", "Mute Members"),
                ("deafen_members", "Deafen Members"),
                ("move_members", "Move Members"),
            ],
            "Management": [
                ("manage_channels", "Manage Channels"),
                ("manage_guild", "Manage Server"),
                ("manage_messages", "Manage Messages"),
                ("manage_nicknames", "Manage Nicknames"),
                ("manage_roles", "Manage Roles"),
                ("kick_members", "Kick Members"),
                ("ban_members", "Ban Members"),
                ("administrator", "Administrator"),
            ]
        }
        
        # Add dropdowns for each category
        for category, perms in self.permission_categories.items():
            self.add_item(PermissionDropdown(category, perms, role, self))
    
    def create_embed(self):
        """Create the main embed showing current permissions"""
        embed = discord.Embed(
            title=f"🔧 Editing Permissions for {self.role.name}",
            description=f"Use the dropdowns below to add or remove permissions.\n\n**Current Permissions:**",
            color=self.color
        )
        
        # Show current permissions by category
        for category, perms in self.permission_categories.items():
            current_perms = []
            for perm_name, perm_display in perms:
                if getattr(self.role.permissions, perm_name, False):
                    current_perms.append(f"✅ {perm_display}")
                else:
                    current_perms.append(f"❌ {perm_display}")
            
            embed.add_field(
                name=f"**{category}**",
                value="\n".join(current_perms[:8]),  # Limit to prevent embed size issues
                inline=True
            )
        
        embed.set_footer(text=f"Requested by {self.author}", icon_url=self.author.avatar.url if self.author.avatar else self.author.default_avatar.url)
        return embed
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow the command author to use the buttons"""
        if interaction.user != self.author:
            await interaction.response.send_message("Only the command author can use these buttons!", ephemeral=True)
            return False
        return True
    
    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary, emoji="🔄")
    async def refresh_view(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Refresh the embed to show updated permissions"""
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)


class PermissionDropdown(discord.ui.Select):
    def __init__(self, category: str, permissions: list, role: discord.Role, parent_view):
        self.role = role
        self.parent_view = parent_view
        
        # Create options for each permission in this category
        options = []
        for perm_name, perm_display in permissions:
            current_value = getattr(role.permissions, perm_name, False)
            emoji = "✅" if current_value else "❌"
            action = "Remove" if current_value else "Add"
            
            options.append(discord.SelectOption(
                label=f"{action} {perm_display}",
                description=f"Current: {'Enabled' if current_value else 'Disabled'}",
                value=f"{perm_name}:{not current_value}",  # Toggle the current state
                emoji=emoji
            ))
        
        super().__init__(
            placeholder=f"Select {category} permissions to modify...",
            options=options,
            max_values=len(options),  # Allow multiple selections
            min_values=0
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle permission changes"""
        if not self.values:
            await interaction.response.send_message("No permissions selected!", ephemeral=True)
            return
        
        try:
            # Get current permissions
            current_perms = self.role.permissions
            
            # Apply changes
            changes = []
            for value in self.values:
                perm_name, new_value = value.split(":")
                new_value = new_value == "True"
                
                # Set the permission
                setattr(current_perms, perm_name, new_value)
                
                # Track changes for feedback
                action = "Added" if new_value else "Removed"
                perm_display = next(p[1] for p in sum(self.parent_view.permission_categories.values(), []) if p[0] == perm_name)
                changes.append(f"{action} **{perm_display}**")
            
            # Update the role
            await self.role.edit(permissions=current_perms, reason=f"Permissions edited by {interaction.user}")
            
            # Update the view
            embed = self.parent_view.create_embed()
            
            # Update all dropdowns with new permission states
            for item in self.parent_view.children:
                if isinstance(item, PermissionDropdown):
                    # Recreate options with updated states
                    new_options = []
                    category_perms = None
                    for cat, perms in self.parent_view.permission_categories.items():
                        if item.placeholder and item.placeholder.startswith(f"Select {cat}"):
                            category_perms = perms
                            break
                    
                    if category_perms:
                        for perm_name, perm_display in category_perms:
                            current_value = getattr(self.role.permissions, perm_name, False)
                            emoji = "✅" if current_value else "❌"
                            action = "Remove" if current_value else "Add"
                            
                            new_options.append(discord.SelectOption(
                                label=f"{action} {perm_display}",
                                description=f"Current: {'Enabled' if current_value else 'Disabled'}",
                                value=f"{perm_name}:{not current_value}",
                                emoji=emoji
                            ))
                        item.options = new_options
            
            # Send success message
            success_embed = discord.Embed(
                title="✅ Permissions Updated",
                description="\n".join(changes),
                color=0x00ff00
            )
            
            await interaction.response.edit_message(embed=embed, view=self.parent_view)
            await interaction.followup.send(embed=success_embed, ephemeral=True)
            
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to edit this role's permissions!", 
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}", 
                ephemeral=True
            )


def setup(bot):
    bot.add_cog(Role(bot))