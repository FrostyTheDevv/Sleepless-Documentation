import discord
from discord.ext import commands
from utils.member_state import member_state_manager, PunishmentType, MemberState
from utils.error_helpers import StandardErrorHandler
from utils.Tools import blacklist_check, ignore_check
from datetime import datetime, timedelta
import asyncio
import logging

class RoleRestoration(commands.Cog):
    """Handles automatic role restoration when members rejoin"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        
        # Rate limiting to prevent spam
        self.restoration_cooldown = {}
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Save member's roles when they leave"""
        try:
            # Don't save roles for bots
            if member.bot:
                return
            
            # Get restoration settings
            settings = member_state_manager.get_restoration_settings(member.guild.id)
            if not settings['restore_roles']:
                return
            
            # Save member's roles
            roles_to_save = []
            excluded_roles = settings.get('excluded_roles', [])
            
            for role in member.roles:
                if role.name != "@everyone" and role.id not in excluded_roles:
                    roles_to_save.append(role)
            
            success = member_state_manager.save_member_roles(
                member.guild.id, 
                member.id, 
                roles_to_save
            )
            
            if success:
                # Update member state to "left"
                member_state_manager.update_member_state(
                    member.guild.id, 
                    member.id, 
                    MemberState.LEFT,
                    f"Left server with {len(roles_to_save)} roles saved"
                )
                
                # Log if enabled
                if settings['log_restorations'] and settings['log_channel_id']:
                    await self.log_member_leave(member, len(roles_to_save), settings['log_channel_id'])
                
                self.logger.info(f"[ROLE_RESTORE] Saved {len(roles_to_save)} roles for {member} ({member.id})")
            
        except Exception as e:
            self.logger.error(f"[ROLE_RESTORE] Error in on_member_remove: {e}")
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Restore member's roles when they rejoin"""
        try:
            # Don't restore roles for bots
            if member.bot:
                return
            
            # Rate limiting check
            cooldown_key = f"{member.guild.id}:{member.id}"
            if cooldown_key in self.restoration_cooldown:
                if datetime.utcnow() < self.restoration_cooldown[cooldown_key]:
                    return
            
            # Set cooldown (5 minutes)
            self.restoration_cooldown[cooldown_key] = datetime.utcnow() + timedelta(minutes=5)
            
            # Get restoration settings
            settings = member_state_manager.get_restoration_settings(member.guild.id)
            if not settings['restore_roles']:
                return
            
            # Get member's previous state
            member_state = member_state_manager.get_member_state(member.guild.id, member.id)
            
            # Check if member has active punishments
            active_punishments = member_state_manager.get_active_punishments(member.guild.id, member.id)
            has_jail = any(p['type'] == PunishmentType.JAIL for p in active_punishments)
            
            # Get saved roles
            saved_role_ids = member_state_manager.get_saved_roles(member.guild.id, member.id)
            
            if not saved_role_ids:
                self.logger.info(f"[ROLE_RESTORE] No saved roles found for {member} ({member.id})")
                return
            
            # Restore roles
            restored_roles = []
            failed_roles = []
            excluded_roles = settings.get('excluded_roles', [])
            
            for role_id in saved_role_ids:
                try:
                    # Skip excluded roles
                    if role_id in excluded_roles:
                        continue
                    
                    role = member.guild.get_role(role_id)
                    if role is None:
                        failed_roles.append(role_id)
                        continue
                    
                    # Check if role still exists and bot can assign it
                    if role >= member.guild.me.top_role:
                        failed_roles.append(role_id)
                        continue
                    
                    # Don't restore certain roles if user is jailed
                    if has_jail and self.is_restricted_role(role):
                        continue
                    
                    await member.add_roles(role, reason="Automatic role restoration")
                    restored_roles.append(role)
                    
                    # Small delay to prevent rate limits
                    await asyncio.sleep(0.1)
                    
                except discord.HTTPException as e:
                    failed_roles.append(role_id)
                    self.logger.warning(f"[ROLE_RESTORE] Failed to restore role {role_id}: {e}")
                except Exception as e:
                    failed_roles.append(role_id)
                    self.logger.error(f"[ROLE_RESTORE] Error restoring role {role_id}: {e}")
            
            # Mark roles as restored
            if restored_roles:
                member_state_manager.mark_roles_restored(member.guild.id, member.id)
            
            # Update member state
            member_state_manager.update_member_state(
                member.guild.id, 
                member.id, 
                MemberState.PUNISHED if active_punishments else MemberState.NORMAL,
                f"Rejoined - restored {len(restored_roles)} roles"
            )
            
            # Apply active punishments
            await self.apply_active_punishments(member, active_punishments)
            
            # Log restoration
            if settings['log_restorations'] and settings['log_channel_id']:
                await self.log_member_restoration(
                    member, 
                    restored_roles, 
                    failed_roles, 
                    active_punishments,
                    settings['log_channel_id']
                )
            
            self.logger.info(f"[ROLE_RESTORE] Restored {len(restored_roles)} roles for {member} ({member.id})")
            
        except Exception as e:
            self.logger.error(f"[ROLE_RESTORE] Error in on_member_join: {e}")
    
    def is_restricted_role(self, role: discord.Role) -> bool:
        """Check if role should be restricted during punishments"""
        restricted_keywords = [
            'mod', 'admin', 'staff', 'helper', 'support', 
            'vip', 'premium', 'trusted', 'verified'
        ]
        
        role_name_lower = role.name.lower()
        return any(keyword in role_name_lower for keyword in restricted_keywords)
    
    async def apply_active_punishments(self, member: discord.Member, punishments: list):
        """Apply active punishments to rejoining member"""
        try:
            for punishment in punishments:
                if punishment['type'] == PunishmentType.JAIL:
                    # Apply jail punishment
                    await self.apply_jail_punishment(member, punishment)
                elif punishment['type'] == PunishmentType.MUTE:
                    # Apply mute punishment
                    await self.apply_mute_punishment(member, punishment)
                # Add other punishment types as needed
                
        except Exception as e:
            self.logger.error(f"[ROLE_RESTORE] Error applying punishments: {e}")
    
    async def apply_jail_punishment(self, member: discord.Member, punishment: dict):
        """Apply jail punishment to member"""
        try:
            # Get jail cog
            jail_cog = self.bot.get_cog('Jail')
            if not jail_cog:
                return
            
            # Get jail settings from database
            cursor = jail_cog.conn.execute("""
                SELECT jail_role_id FROM jail_config WHERE guild_id = ?
            """, (str(member.guild.id),))
            
            result = cursor.fetchone()
            if not result:
                return
            
            jail_role_id = int(result[0])
            jail_role = member.guild.get_role(jail_role_id)
            
            if jail_role:
                await member.add_roles(jail_role, reason="Reapplying jail punishment")
                
                # Remove other roles except jail role
                roles_to_remove = [r for r in member.roles if r != jail_role and r.name != "@everyone"]
                if roles_to_remove:
                    await member.remove_roles(*roles_to_remove, reason="Jail punishment active")
                
                self.logger.info(f"[ROLE_RESTORE] Reapplied jail to {member}")
            
        except Exception as e:
            self.logger.error(f"[ROLE_RESTORE] Error applying jail: {e}")
    
    async def apply_mute_punishment(self, member: discord.Member, punishment: dict):
        """Apply mute punishment to member"""
        try:
            # Apply timeout if supported
            if punishment.get('end_time'):
                end_time = datetime.fromisoformat(punishment['end_time'])
                if end_time > datetime.utcnow():
                    duration = end_time - datetime.utcnow()
                    await member.timeout(duration, reason="Reapplying mute punishment")
                    self.logger.info(f"[ROLE_RESTORE] Reapplied timeout to {member}")
            
        except Exception as e:
            self.logger.error(f"[ROLE_RESTORE] Error applying mute: {e}")
    
    async def log_member_leave(self, member: discord.Member, roles_saved: int, log_channel_id: int):
        """Log member leaving with role saving"""
        try:
            channel = self.bot.get_channel(log_channel_id)
            if not channel:
                return
            
            embed = discord.Embed(
                title="<:leave:1427471506287362068> Member Left - Roles Saved",
                color=0xff9500
            )
            
            embed.add_field(name="Member", value=f"{member.mention} ({member})", inline=False)
            embed.add_field(name="Roles Saved", value=str(roles_saved), inline=True)
            embed.add_field(name="Left At", value=f"<t:{int(datetime.utcnow().timestamp())}:F>", inline=True)
            
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"ID: {member.id}")
            
            await channel.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"[ROLE_RESTORE] Error logging member leave: {e}")
    
    async def log_member_restoration(self, member: discord.Member, restored_roles: list, 
                                   failed_roles: list, punishments: list, log_channel_id: int):
        """Log member role restoration"""
        try:
            channel = self.bot.get_channel(log_channel_id)
            if not channel:
                return
            
            embed = discord.Embed(
                title="<:join:1427471506287362068> Member Rejoined - Roles Restored",
                color=0x00ff88 if not punishments else 0xff6b6b
            )
            
            embed.add_field(name="Member", value=f"{member.mention} ({member})", inline=False)
            embed.add_field(name="Roles Restored", value=str(len(restored_roles)), inline=True)
            
            if failed_roles:
                embed.add_field(name="Failed Roles", value=str(len(failed_roles)), inline=True)
            
            if punishments:
                punishment_types = [p['type'].value for p in punishments]
                embed.add_field(
                    name="Active Punishments", 
                    value=", ".join(punishment_types), 
                    inline=True
                )
            
            embed.add_field(name="Rejoined At", value=f"<t:{int(datetime.utcnow().timestamp())}:F>", inline=True)
            
            if restored_roles:
                role_names = [role.name for role in restored_roles[:10]]  # Limit to 10 roles
                if len(restored_roles) > 10:
                    role_names.append(f"... and {len(restored_roles) - 10} more")
                
                embed.add_field(
                    name="Restored Roles",
                    value="\n".join(f"• {name}" for name in role_names),
                    inline=False
                )
            
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"ID: {member.id}")
            
            await channel.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"[ROLE_RESTORE] Error logging restoration: {e}")
    
    @commands.group(name="rolebackup", aliases=["rb", "restore"])
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    async def role_backup(self, ctx):
        """Manage role backup and restoration system"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="<:backup:1427471506287362068> Role Backup & Restoration System",
                description="Automatically save and restore member roles when they leave/rejoin",
                color=0x00ff88
            )
            
            embed.add_field(
                name="<:gear:1427471588915150900> Settings",
                value="`rolebackup settings` - View/configure restoration settings",
                inline=False
            )
            
            embed.add_field(
                name="<:save:1427471506287362068> Manual Operations",
                value="`rolebackup save <member>` - Manually save member's roles\n"
                      "`rolebackup restore <member>` - Manually restore member's roles",
                inline=False
            )
            
            embed.add_field(
                name="<:list:1427471506287362068> Information",
                value="`rolebackup status <member>` - Check member's restoration status\n"
                      "`rolebackup excluded` - View excluded roles",
                inline=False
            )
            
            await ctx.send(embed=embed)
    
    @role_backup.command(name="settings")
    @commands.has_permissions(administrator=True)
    async def restoration_settings(self, ctx):
        """View and configure restoration settings"""
        settings = member_state_manager.get_restoration_settings(ctx.guild.id)
        
        embed = discord.Embed(
            title="<:gear:1427471588915150900> Role Restoration Settings",
            color=0x00ff88
        )
        
        embed.add_field(
            name="Auto Restore Roles",
            value="✅ Enabled" if settings['restore_roles'] else "❌ Disabled",
            inline=True
        )
        
        embed.add_field(
            name="Restore During Punishment",
            value="✅ Yes" if settings['restore_on_punishment'] else "❌ No",
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
            channel = ctx.guild.get_channel(settings['log_channel_id'])
            embed.add_field(
                name="Log Channel",
                value=channel.mention if channel else "Channel not found",
                inline=True
            )
        
        if settings['excluded_roles']:
            excluded_names = []
            for role_id in settings['excluded_roles'][:5]:  # Show max 5
                role = ctx.guild.get_role(role_id)
                if role:
                    excluded_names.append(role.name)
            
            if excluded_names:
                embed.add_field(
                    name="Excluded Roles",
                    value="\n".join(f"• {name}" for name in excluded_names),
                    inline=False
                )
        
        await ctx.send(embed=embed)
    
    @role_backup.command(name="save")
    @commands.has_permissions(manage_roles=True)
    async def save_member_roles(self, ctx, member: discord.Member):
        """Manually save a member's roles"""
        settings = member_state_manager.get_restoration_settings(ctx.guild.id)
        excluded_roles = settings.get('excluded_roles', [])
        
        roles_to_save = []
        for role in member.roles:
            if role.name != "@everyone" and role.id not in excluded_roles:
                roles_to_save.append(role)
        
        success = member_state_manager.save_member_roles(
            ctx.guild.id, 
            member.id, 
            roles_to_save
        )
        
        if success:
            embed = discord.Embed(
                title="<:check:1428163122710970508> Roles Saved Successfully",
                description=f"Saved {len(roles_to_save)} roles for {member.mention}",
                color=0x00ff88
            )
        else:
            embed = discord.Embed(
                title="<:warning:1427471923805925397> Failed to Save Roles",
                description="There was an error saving the member's roles.",
                color=0xff6b6b
            )
        
        await ctx.send(embed=embed)
    
    @role_backup.command(name="restore")
    @commands.has_permissions(manage_roles=True)
    async def restore_member_roles(self, ctx, member: discord.Member):
        """Manually restore a member's roles"""
        saved_role_ids = member_state_manager.get_saved_roles(ctx.guild.id, member.id)
        
        if not saved_role_ids:
            embed = discord.Embed(
                title="<:warning:1427471923805925397> No Saved Roles",
                description=f"No saved roles found for {member.mention}",
                color=0xff6b6b
            )
            await ctx.send(embed=embed)
            return
        
        # Restore roles
        restored_roles = []
        failed_roles = []
        
        for role_id in saved_role_ids:
            try:
                role = ctx.guild.get_role(role_id)
                if role is None:
                    failed_roles.append(role_id)
                    continue
                
                if role >= ctx.guild.me.top_role:
                    failed_roles.append(role_id)
                    continue
                
                await member.add_roles(role, reason=f"Manual restoration by {ctx.author}")
                restored_roles.append(role)
                
            except discord.HTTPException:
                failed_roles.append(role_id)
        
        # Mark as restored
        if restored_roles:
            member_state_manager.mark_roles_restored(ctx.guild.id, member.id)
        
        embed = discord.Embed(
            title="<:check:1428163122710970508> Role Restoration Complete",
            color=0x00ff88
        )
        
        embed.add_field(name="Member", value=member.mention, inline=False)
        embed.add_field(name="Roles Restored", value=str(len(restored_roles)), inline=True)
        
        if failed_roles:
            embed.add_field(name="Failed Roles", value=str(len(failed_roles)), inline=True)
        
        if restored_roles:
            role_names = [role.name for role in restored_roles[:10]]
            if len(restored_roles) > 10:
                role_names.append(f"... and {len(restored_roles) - 10} more")
            
            embed.add_field(
                name="Restored Roles",
                value="\n".join(f"• {name}" for name in role_names),
                inline=False
            )
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(RoleRestoration(bot))