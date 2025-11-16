import discord
from discord.ext import commands, tasks
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from utils.member_state import member_state_manager, PunishmentType, MemberState
from utils.error_helpers import StandardErrorHandler

class MemberStateHandler(commands.Cog):
    """Handles member join/leave events and role persistence"""
    
    def __init__(self, bot):
        self.bot = bot
        self.restoration_queue = {}  # Guild-specific restoration queues
        self.cleanup_expired_punishments.start()
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def cog_unload(self):
        """Clean up when cog is unloaded"""
        self.cleanup_expired_punishments.cancel()
    
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Handle member leaving - save their roles and state"""
        try:
            # Don't save roles for bots
            if member.bot:
                return
            
            guild_id = member.guild.id
            user_id = member.id
            
            # Get restoration settings
            settings = member_state_manager.get_restoration_settings(guild_id)
            
            if not settings['restore_roles']:
                return  # Role restoration disabled
            
            # Save member roles (excluding moderation roles and excluded roles)
            settings = member_state_manager.get_restoration_settings(guild_id)
            excluded_role_ids = settings.get('excluded_roles', [])
            
            # Filter roles to exclude moderation roles and explicitly excluded roles  
            safe_roles = member_state_manager.get_safe_roles_for_persistence(member.roles, excluded_role_ids)
            
            if safe_roles:
                # Save roles to database
                success = member_state_manager.save_member_roles(guild_id, user_id, member.roles)
                
                if success:
                    # Update member state to "left"
                    member_state_manager.update_member_state(
                        guild_id, user_id, MemberState.LEFT,
                        f"Left server with {len(safe_roles)} safe roles saved"
                    )
                    
                    # Log if enabled
                    if settings['log_restorations'] and settings.get('log_channel_id'):
                        await self.log_role_save(member, safe_roles, settings['log_channel_id'])
                    
                    print(f"[MEMBER_STATE] Saved {len(safe_roles)} safe roles for {member.display_name}")
                    
                    # Log any excluded roles for transparency
                    total_roles = len([r for r in member.roles if r.name != "@everyone"])
                    excluded_count = total_roles - len(safe_roles)
                    if excluded_count > 0:
                        print(f"[MEMBER_STATE] Excluded {excluded_count} moderation/dangerous roles from {member.display_name}'s persistence")
            else:
                print(f"[MEMBER_STATE] No safe roles to save for {member.display_name} - all roles were moderation/excluded roles")
        
        except Exception as e:
            print(f"[MEMBER_STATE] Error handling member leave: {e}")
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Handle member joining - restore roles and handle punishments"""
        try:
            # Don't process bots
            if member.bot:
                return
            
            guild_id = member.guild.id
            user_id = member.id
            
            # Get restoration settings
            settings = member_state_manager.get_restoration_settings(guild_id)
            
            if not settings['restore_roles']:
                return  # Role restoration disabled
            
            # Check if this is within the restoration time limit
            member_state = member_state_manager.get_member_state(guild_id, user_id)
            
            if member_state['last_seen']:
                last_seen = datetime.fromisoformat(member_state['last_seen'].replace('Z', '+00:00'))
                time_away = datetime.utcnow() - last_seen
                
                if time_away.days > settings['max_restore_days']:
                    print(f"[MEMBER_STATE] Member {member.display_name} exceeded max restore days ({time_away.days})")
                    return
            
            # Check for active punishments
            active_punishments = member_state_manager.get_active_punishments(guild_id, user_id)
            has_jail = any(p['type'] == PunishmentType.JAIL for p in active_punishments)
            has_mute = any(p['type'] == PunishmentType.MUTE for p in active_punishments)
            
            # Get saved roles
            saved_role_ids = member_state_manager.get_saved_roles(guild_id, user_id)
            
            if saved_role_ids:
                # Add member to restoration queue (prevent race conditions)
                await self.queue_role_restoration(member, saved_role_ids, active_punishments, settings)
            
            # Update member state
            join_count = member_state['join_count'] + 1
            state = MemberState.PUNISHED if active_punishments else MemberState.NORMAL
            
            member_state_manager.update_member_state(
                guild_id, user_id, state,
                f"Rejoined (attempt #{join_count}). Active punishments: {len(active_punishments)}"
            )
            
        except Exception as e:
            print(f"[MEMBER_STATE] Error handling member join: {e}")
    
    async def queue_role_restoration(self, member: discord.Member, saved_role_ids: List[int], 
                                   active_punishments: List[Dict], settings: Dict):
        """Queue role restoration to prevent conflicts"""
        guild_id = member.guild.id
        
        if guild_id not in self.restoration_queue:
            self.restoration_queue[guild_id] = []
        
        restoration_data = {
            'member': member,
            'saved_role_ids': saved_role_ids,
            'active_punishments': active_punishments,
            'settings': settings,
            'timestamp': datetime.utcnow()
        }
        
        self.restoration_queue[guild_id].append(restoration_data)
        
        # Process the queue
        await self.process_restoration_queue(guild_id)
    
    async def process_restoration_queue(self, guild_id: int):
        """Process pending role restorations for a guild"""
        if guild_id not in self.restoration_queue or not self.restoration_queue[guild_id]:
            return
        
        while self.restoration_queue[guild_id]:
            restoration = self.restoration_queue[guild_id].pop(0)
            
            try:
                await self.restore_member_roles(
                    restoration['member'],
                    restoration['saved_role_ids'],
                    restoration['active_punishments'],
                    restoration['settings']
                )
                
                # Small delay to prevent rate limits
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"[MEMBER_STATE] Error processing restoration queue: {e}")
    
    async def restore_member_roles(self, member: discord.Member, saved_role_ids: List[int],
                                 active_punishments: List[Dict], settings: Dict):
        """Restore roles to a member with punishment considerations"""
        try:
            guild = member.guild
            user_id = member.id
            guild_id = guild.id
            
            # Get available roles from the guild
            available_roles = {role.id: role for role in guild.roles}
            roles_to_restore = []
            roles_not_found = []
            roles_skipped = []
            
            # Check each saved role
            for role_id in saved_role_ids:
                if role_id not in available_roles:
                    roles_not_found.append(role_id)
                    continue
                
                role = available_roles[role_id]
                
                # Skip if role is in excluded list
                if role_id in settings.get('excluded_roles', []):
                    roles_skipped.append(role.name)
                    continue
                
                # Skip if role is higher than bot's highest role
                if role >= guild.me.top_role:
                    roles_skipped.append(f"{role.name} (higher than bot)")
                    continue
                
                roles_to_restore.append(role)
            
            # Handle punishment-specific role restoration
            if active_punishments:
                if not settings.get('restore_on_punishment', False):
                    # Don't restore roles if punished and setting is disabled
                    await self.apply_punishments_on_join(member, active_punishments)
                    return
                else:
                    # Restore roles but apply punishments afterwards
                    if roles_to_restore:
                        try:
                            await member.add_roles(*roles_to_restore, reason="Auto role restoration (with punishment)")
                            print(f"[MEMBER_STATE] Restored {len(roles_to_restore)} roles to {member.display_name} (punished)")
                        except discord.Forbidden:
                            print(f"[MEMBER_STATE] Missing permissions to restore roles to {member.display_name}")
                        except discord.HTTPException as e:
                            print(f"[MEMBER_STATE] Failed to restore roles to {member.display_name}: {e}")
                    
                    # Apply punishments after role restoration
                    await self.apply_punishments_on_join(member, active_punishments)
            else:
                # Normal role restoration (no punishments)
                if roles_to_restore:
                    try:
                        await member.add_roles(*roles_to_restore, reason="Auto role restoration")
                        print(f"[MEMBER_STATE] Restored {len(roles_to_restore)} roles to {member.display_name}")
                    except discord.Forbidden:
                        print(f"[MEMBER_STATE] Missing permissions to restore roles to {member.display_name}")
                    except discord.HTTPException as e:
                        print(f"[MEMBER_STATE] Failed to restore roles to {member.display_name}: {e}")
            
            # Mark roles as restored
            member_state_manager.mark_roles_restored(guild_id, user_id)
            
            # Log restoration if enabled
            if settings['log_restorations'] and settings.get('log_channel_id'):
                await self.log_role_restoration(member, roles_to_restore, roles_not_found, 
                                              roles_skipped, active_punishments, settings['log_channel_id'])
        
        except Exception as e:
            print(f"[MEMBER_STATE] Error restoring member roles: {e}")
    
    async def apply_punishments_on_join(self, member: discord.Member, active_punishments: List[Dict]):
        """Apply active punishments when member rejoins"""
        try:
            guild = member.guild
            
            for punishment in active_punishments:
                punishment_type = punishment['type']
                
                if punishment_type == PunishmentType.JAIL:
                    # Apply jail role and permissions
                    await self.apply_jail_punishment(member, punishment)
                
                elif punishment_type == PunishmentType.MUTE:
                    # Apply mute role or timeout
                    await self.apply_mute_punishment(member, punishment)
                
                elif punishment_type == PunishmentType.BAN:
                    # This shouldn't happen as banned users can't join
                    print(f"[MEMBER_STATE] Warning: User {member.id} has active ban but joined server")
                
                # Note: Other punishment types (warn, kick) don't require active enforcement
        
        except Exception as e:
            print(f"[MEMBER_STATE] Error applying punishments on join: {e}")
    
    async def apply_jail_punishment(self, member: discord.Member, punishment: Dict):
        """Apply jail punishment to member"""
        try:
            # Try to find jail role
            jail_role = None
            for role in member.guild.roles:
                if role.name.lower() in ['jailed', 'jail']:
                    jail_role = role
                    break
            
            if jail_role:
                await member.add_roles(jail_role, reason=f"Auto-applied jail: {punishment['reason']}")
                print(f"[MEMBER_STATE] Applied jail role to {member.display_name}")
            else:
                print(f"[MEMBER_STATE] Jail role not found for {member.guild.name}")
        
        except Exception as e:
            print(f"[MEMBER_STATE] Error applying jail punishment: {e}")
    
    async def apply_mute_punishment(self, member: discord.Member, punishment: Dict):
        """Apply mute punishment to member"""
        try:
            # Check if timeout is still valid
            if punishment.get('end_time'):
                end_time = datetime.fromisoformat(punishment['end_time'].replace('Z', '+00:00'))
                if datetime.utcnow() >= end_time:
                    # Punishment expired, remove it
                    member_state_manager.remove_punishment(
                        member.guild.id, member.id, punishment_id=punishment['id']
                    )
                    return
                
                # Apply timeout for remaining duration
                remaining_time = end_time - datetime.utcnow()
                if remaining_time.total_seconds() > 0:
                    await member.timeout(remaining_time, reason=f"Auto-applied mute: {punishment['reason']}")
                    print(f"[MEMBER_STATE] Applied timeout to {member.display_name} for {remaining_time}")
            else:
                # Permanent mute - try to find mute role
                mute_role = None
                for role in member.guild.roles:
                    if role.name.lower() in ['muted', 'mute']:
                        mute_role = role
                        break
                
                if mute_role:
                    await member.add_roles(mute_role, reason=f"Auto-applied mute: {punishment['reason']}")
                    print(f"[MEMBER_STATE] Applied mute role to {member.display_name}")
        
        except Exception as e:
            print(f"[MEMBER_STATE] Error applying mute punishment: {e}")
    
    async def log_role_save(self, member: discord.Member, roles: List[discord.Role], log_channel_id: int):
        """Log role saving to specified channel"""
        try:
            channel = member.guild.get_channel(log_channel_id)
            if not channel:
                return
            
            embed = discord.Embed(
                title="🗃️ Roles Saved",
                description=f"Saved roles for {member.mention} who left the server",
                color=0xffa500,
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(
                name="Member",
                value=f"{member.display_name} ({member.id})",
                inline=True
            )
            
            embed.add_field(
                name="Roles Saved",
                value=str(len(roles)),
                inline=True
            )
            
            if len(roles) <= 10:
                role_list = "\n".join([f"• {role.name}" for role in roles])
                embed.add_field(
                    name="Role List",
                    value=role_list,
                    inline=False
                )
            
            # Only send to text channels
            if isinstance(channel, discord.TextChannel):
                await channel.send(embed=embed)
        
        except Exception as e:
            print(f"[MEMBER_STATE] Error logging role save: {e}")
    
    async def log_role_restoration(self, member: discord.Member, restored_roles: List[discord.Role],
                                 not_found: List[int], skipped: List[str], punishments: List[Dict],
                                 log_channel_id: int):
        """Log role restoration to specified channel"""
        try:
            channel = member.guild.get_channel(log_channel_id)
            if not channel:
                return
            
            color = 0x00ff00 if not punishments else 0xff6b6b
            title = "✅ Roles Restored" if not punishments else "⚠️ Roles Restored (Punished)"
            
            embed = discord.Embed(
                title=title,
                description=f"Restored roles for {member.mention} who rejoined the server",
                color=color,
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(
                name="Member",
                value=f"{member.display_name} ({member.id})",
                inline=True
            )
            
            embed.add_field(
                name="Roles Restored",
                value=str(len(restored_roles)),
                inline=True
            )
            
            if punishments:
                punishment_types = [p['type'].value for p in punishments]
                embed.add_field(
                    name="Active Punishments",
                    value=", ".join(punishment_types),
                    inline=True
                )
            
            if len(restored_roles) <= 10:
                role_list = "\n".join([f"• {role.name}" for role in restored_roles])
                if role_list:
                    embed.add_field(
                        name="Restored Roles",
                        value=role_list,
                        inline=False
                    )
            
            if not_found:
                embed.add_field(
                    name="Roles Not Found",
                    value=f"{len(not_found)} roles no longer exist",
                    inline=True
                )
            
            if skipped:
                embed.add_field(
                    name="Roles Skipped",
                    value="\n".join(skipped[:5]) + (f"\n...and {len(skipped)-5} more" if len(skipped) > 5 else ""),
                    inline=True
                )
            
            # Only send to text channels
            if isinstance(channel, discord.TextChannel):
                await channel.send(embed=embed)
        
        except Exception as e:
            print(f"[MEMBER_STATE] Error logging role restoration: {e}")
    
    @tasks.loop(minutes=30)
    async def cleanup_expired_punishments(self):
        """Clean up expired punishments"""
        try:
            # This would be implemented to check for expired punishments
            # and automatically remove them
            print("[MEMBER_STATE] Checking for expired punishments...")
            
            # TODO: Implement expired punishment cleanup
            
        except Exception as e:
            print(f"[MEMBER_STATE] Error in punishment cleanup: {e}")
    
    @cleanup_expired_punishments.before_loop
    async def before_cleanup(self):
        """Wait for bot to be ready before starting cleanup loop"""
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(MemberStateHandler(bot))