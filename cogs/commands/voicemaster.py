import discord
from discord.ext import commands, tasks
import aiosqlite
from typing import Optional
from utils.Tools import blacklist_check, ignore_check

VOICEMASTER_DB_PATH = 'db/voicemaster.db'


class VoiceMaster(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._start_tasks = True
        bot.loop.create_task(self.ensure_tables())

    async def cog_command_error(self, ctx, error):
        """Handle errors for VoiceMaster commands"""
        if isinstance(error, commands.CommandOnCooldown):
            embed = discord.Embed(
                title="<a:clock:1436953635731800178> Command On Cooldown",
                description=f"You're using this command too quickly! Please wait **{error.retry_after:.1f}** seconds.",
                color=0xFF6B6B
            )
            await ctx.send(embed=embed, ephemeral=True)
        elif isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="<a:wrong:1436956421110632489> Missing Permissions",
                description="You don't have permission to use this command!",
                color=0xFF6B6B
            )
            await ctx.send(embed=embed, ephemeral=True)
        else:
            raise error

    async def ensure_tables(self):
        """Initialize database tables"""
        await self.bot.wait_until_ready()
        async with aiosqlite.connect(VOICEMASTER_DB_PATH) as db:
            # Temp channels table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS vm_temp_channels (
                    channel_id INTEGER PRIMARY KEY,
                    guild_id INTEGER NOT NULL,
                    owner_id INTEGER NOT NULL,
                    created_at TEXT,
                    panel_message_id INTEGER
                )
            """)
            
            # Guild configuration table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS vm_guild_config (
                    guild_id INTEGER PRIMARY KEY,
                    create_channel_id INTEGER,
                    category_id INTEGER,
                    enabled INTEGER DEFAULT 1,
                    channel_name_format TEXT DEFAULT "{username}'s Channel",
                    channel_limit INTEGER DEFAULT 0,
                    delete_empty INTEGER DEFAULT 1,
                    use_cv2 INTEGER DEFAULT 1
                )
            """)
            
            await db.commit()
        print("[VoiceMaster] Database tables initialized successfully!")
        
        # Start cleanup tasks
        if self._start_tasks:
            self.cleanup_old_temp_roles.start()

    @tasks.loop(hours=1)
    async def cleanup_old_temp_roles(self):
        """Clean up old temporary roles that weren't deleted properly"""
        try:
            async with aiosqlite.connect(VOICEMASTER_DB_PATH) as db:
                # Get all temp channels with roles
                async with db.execute(
                    "SELECT channel_id, guild_id, temp_role_id FROM vm_temp_channels WHERE temp_role_id IS NOT NULL"
                ) as cursor:
                    temp_channels = await cursor.fetchall()
                
                roles_cleaned = 0
                for channel_id, guild_id, role_id in temp_channels:
                    guild = self.bot.get_guild(guild_id)
                    if not guild:
                        continue
                    
                    # Check if channel still exists
                    channel = guild.get_channel(channel_id)
                    if not channel:
                        # Channel gone, clean up role and database entry
                        role = guild.get_role(role_id)
                        if role:
                            try:
                                await role.delete(reason="VoiceMaster: Cleaning up orphaned temp role")
                                roles_cleaned += 1
                            except Exception:
                                pass
                        
                        await db.execute("DELETE FROM vm_temp_channels WHERE channel_id = ?", (channel_id,))
                
                await db.commit()
                if roles_cleaned > 0:
                    print(f"[VoiceMaster] 🧹 Cleaned up {roles_cleaned} orphaned temp roles")
                    
        except Exception as e:
            print(f"[VoiceMaster] <a:wrong:1436956421110632489> Error during cleanup: {e}")

    @cleanup_old_temp_roles.before_loop
    async def before_cleanup_old_temp_roles(self):
        """Wait for bot to be ready before cleanup"""
        await self.bot.wait_until_ready()

    async def delete_temp_channel(self, channel_id: int):
        """Safely delete a temp channel and clean up database/roles"""
        try:
            async with aiosqlite.connect(VOICEMASTER_DB_PATH) as db:
                # Get temp channel info
                async with db.execute(
                    "SELECT guild_id, temp_role_id FROM vm_temp_channels WHERE channel_id = ?",
                    (channel_id,)
                ) as cursor:
                    result = await cursor.fetchone()
                
                if result:
                    guild_id, role_id = result
                    
                    # Delete from database first
                    await db.execute("DELETE FROM vm_temp_channels WHERE channel_id = ?", (channel_id,))
                    await db.commit()
                    
                    # Clean up temp role if exists (legacy channels only)
                    if role_id:
                        guild = self.bot.get_guild(guild_id)
                        if guild:
                            role = guild.get_role(role_id)
                            if role:
                                try:
                                    await role.delete(reason="VoiceMaster: Cleaning up legacy temp role")
                                    print(f"[VM] 🧹 Cleaned up legacy role for channel {channel_id}")
                                except Exception:
                                    pass
                    
                    print(f"[VoiceMaster] 🗑️ Cleaned up temp channel {channel_id}")
                    
        except Exception as e:
            print(f"[VoiceMaster] <a:wrong:1436956421110632489> Error deleting temp channel {channel_id}: {e}")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Handle voice channel join/leave events"""
        if member.bot:
            return

        # Handle joining create channel
        if after.channel:
            await self.handle_channel_join(member, after.channel)
        
        # Handle leaving temp channel
        if before.channel:
            await self.handle_channel_leave(member, before.channel)

    async def handle_channel_join(self, member, channel):
        """Handle member joining a voice channel"""
        async with aiosqlite.connect(VOICEMASTER_DB_PATH) as db:
            # Check if this is a create channel
            async with db.execute(
                "SELECT category_id, channel_name_format, channel_limit FROM vm_guild_config WHERE guild_id = ? AND create_channel_id = ? AND enabled = 1",
                (channel.guild.id, channel.id)
            ) as cursor:
                config = await cursor.fetchone()
            
            if config:
                await self.create_temp_channel(member, config)

    async def handle_channel_leave(self, member, channel):
        """Handle member leaving a voice channel"""
        async with aiosqlite.connect(VOICEMASTER_DB_PATH) as db:
            # Check if this is a temp channel
            async with db.execute(
                "SELECT owner_id FROM vm_temp_channels WHERE channel_id = ?",
                (channel.id,)
            ) as cursor:
                result = await cursor.fetchone()
            
            if result and len(channel.members) == 0:
                # Empty temp channel - delete it
                try:
                    await db.execute("DELETE FROM vm_temp_channels WHERE channel_id = ?", (channel.id,))
                    await db.commit()
                    await channel.delete(reason="VoiceMaster: Empty temp channel cleanup")
                    print(f"[VM] 🧹 Deleted empty temp channel: {channel.name}")
                except Exception as e:
                    print(f"[VM] <a:wrong:1436956421110632489> Error deleting temp channel: {e}")

    async def create_temp_channel(self, member, config):
        """Create a temporary voice channel with enhanced features"""
        try:
            category_id, name_format, channel_limit = config[:3]
            category = self.bot.get_channel(category_id) if category_id else None
            
            # Generate unique channel name with multiple format support
            channel_name = name_format.replace("{username}", member.display_name).replace("{user}", member.display_name)
            channel_name = channel_name.replace("{mention}", f"@{member.display_name}")
            counter = 1
            original_name = channel_name
            while any(ch.name == channel_name for ch in member.guild.voice_channels):
                channel_name = f"{original_name} ({counter})"
                counter += 1
            
            # Check category channel limit (Discord limit is 40 channels per category)
            if category and len(category.channels) >= 39:  # Leave room for the create channel
                print(f"[VM] <a:wrong:1436956421110632489> Category {category.name} is nearly full ({len(category.channels)}/40 channels)")
                return
            
            # Create the temp channel with direct member permissions (no role needed)
            overwrites = {
                member.guild.default_role: discord.PermissionOverwrite(
                    view_channel=True,
                    connect=True,
                    speak=True,
                    use_voice_activation=True
                ),
                member: discord.PermissionOverwrite(
                    view_channel=True,
                    connect=True,
                    speak=True,
                    use_voice_activation=True,
                    mute_members=True,
                    deafen_members=True,
                    move_members=True,
                    manage_channels=True
                )
            }
            
            temp_channel = await member.guild.create_voice_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                user_limit=channel_limit if channel_limit > 0 else None,
                reason=f"VoiceMaster: Created by {member.display_name}"
            )
            
            # No role needed - owner gets direct channel permissions
            
            # Move member to the new channel
            await member.move_to(temp_channel, reason="VoiceMaster: Moved to created channel")
            
            # Store in database (no role ID needed)
            async with aiosqlite.connect(VOICEMASTER_DB_PATH) as db:
                await db.execute(
                    """INSERT INTO vm_temp_channels 
                       (channel_id, guild_id, owner_id, type, created_at) 
                       VALUES (?, ?, ?, ?, datetime('now'))""",
                    (temp_channel.id, member.guild.id, member.id, 'voice')
                )
                await db.commit()
            
            print(f"[VM] <a:yes:1431909187247673464> Created temp channel: {temp_channel.name} for {member.display_name} (No role spam!)")
            
            # Send control panel
            await self.send_control_panel(temp_channel, member)
            
        except discord.Forbidden:
            print(f"[VM] <a:wrong:1436956421110632489> No permission to create channel in guild {member.guild.name}")
        except Exception as e:
            print(f"[VM] <a:wrong:1436956421110632489> Error creating temp channel: {e}")
            import traceback
            traceback.print_exc()

    async def send_control_panel(self, channel, owner):
        """Send beautiful Components v2 VoiceMaster control panel with background styling"""
        member_count = len(channel.members)
        limit_text = "∞" if channel.user_limit == 0 else str(channel.user_limit)
        
        print(f"[VM] Sending Components v2 control panel with background for {channel.name} (ID: {channel.id})")
        
        try:
            # Determine toggle state labels first
            locked = channel.overwrites_for(channel.guild.default_role).connect == False
            hidden = channel.overwrites_for(channel.guild.default_role).view_channel == False
            muted_members = [m for m in channel.members if m.voice and m.voice.mute]
            all_muted = len(muted_members) > 0 and len(muted_members) == len([m for m in channel.members if m.voice])

            # Components v2 - embed AND buttons wrapped together as one integrated unit
            from discord.ui import LayoutView, Container, Section, TextDisplay, Separator
            
            # Build all items for Container FIRST
            container_items = []
            
            # Header text display
            header_text = TextDisplay(
                f"<a:sound:1437493915677626388> **VoiceMaster Interface**\n\n"
                f"Use the buttons below to control your voice channel."
            )
            container_items.append(header_text)
            
            # Separator
            container_items.append(Separator())
            
            # Button usage guide
            button_guide = TextDisplay(
                f"**Button Usage**\n"
                f"<a:lock:1437496504955699402> — **{'Unlock' if locked else 'Lock'}** the voice channel\n"
                f"<a:online:1431491381817380985> — **{'Reveal' if hidden else 'Ghost'}** the voice channel\n"
                f"<:speaker:1428183066311921804> — **Claim** the voice channel\n"
                f"<:offline:1431491401195061393> — **Disconnect** a member\n"
                f"<:game:1437833296477294847> — **Start** an activity\n"
                f"<a:mark:1436953593923244113> — **View** channel information\n"
                f"<:plusu:1428164526884257852> — **Set** user limit\n"
                f"<a:wrong:1436956421110632489> — **End** and delete channel"
            )
            container_items.append(button_guide)
            
            # Separator before buttons
            container_items.append(Separator())
            
            # Row 1: Lock/Unlock Toggle, Ghost/Reveal Toggle, Claim, Disconnect, Activity, Info, Limit (5 buttons max, so split across 2 action rows)
            from discord.ui import ActionRow
            row1 = ActionRow(
                discord.ui.Button(
                    emoji="<a:lock:1437496504955699402>" if locked else "<a:lock:1437496504955699402>",
                    style=discord.ButtonStyle.gray,
                    custom_id=f"vm_lock_toggle_{channel.id}_{owner.id}"
                ),
                discord.ui.Button(
                    emoji="<a:online:1431491381817380985>" if hidden else "<:offline:1431491401195061393>",
                    style=discord.ButtonStyle.gray,
                    custom_id=f"vm_hide_toggle_{channel.id}_{owner.id}"
                ),
                discord.ui.Button(
                    emoji="<:speaker:1428183066311921804>",
                    style=discord.ButtonStyle.gray,
                    custom_id=f"vm_claim_{channel.id}_{owner.id}"
                ),
                discord.ui.Button(
                    emoji="<:offline:1431491401195061393>",
                    style=discord.ButtonStyle.gray,
                    custom_id=f"vm_disconnect_{channel.id}_{owner.id}"
                ),
                discord.ui.Button(
                    emoji="<:game:1437833296477294847>",
                    style=discord.ButtonStyle.gray,
                    custom_id=f"vm_activity_{channel.id}_{owner.id}"
                )
            )
            container_items.append(row1)
            
            # Row 1b: Info and Limit (continuing first row actions)
            row1b = ActionRow(
                discord.ui.Button(
                    emoji="<a:mark:1436953593923244113?",
                    style=discord.ButtonStyle.gray,
                    custom_id=f"vm_info_{channel.id}_{owner.id}"
                ),
                discord.ui.Button(
                    emoji="<:plusu:1428164526884257852>",
                    style=discord.ButtonStyle.gray,
                    custom_id=f"vm_limit_{channel.id}_{owner.id}"
                )
            )
            container_items.append(row1b)
            
            # Row 2: End/Close button (1 button)
            row2 = ActionRow(
                discord.ui.Button(
                    emoji="<a:wrong:1436956421110632489>",
                    label="End",
                    style=discord.ButtonStyle.danger,
                    custom_id=f"vm_close_{channel.id}_{owner.id}"
                )
            )
            container_items.append(row2)

            # NOW wrap all items in a Container for embed-like appearance
            # Pass items directly to Container constructor (correct pattern)
            container = Container(
                *container_items,  # Unpack all items we built
                accent_color=discord.Color.from_rgb(88, 101, 242)  # Discord blurple for voice
            )
            
            # Create final layout with container
            final_layout = LayoutView()
            final_layout.add_item(container)
            
            # Send with Components v2 LayoutView - everything wrapped together  
            message = await channel.send(view=final_layout)

            # Store panel message ID
            async with aiosqlite.connect(VOICEMASTER_DB_PATH) as db:
                await db.execute(
                    "UPDATE vm_temp_channels SET panel_message_id = ? WHERE channel_id = ?",
                    (message.id, channel.id)
                )
                await db.commit()

            print(f"[VM] <a:yes:1431909187247673464> Horizontal CV2 panel sent successfully! Message ID: {message.id}")
            
        except Exception as e:
            print(f"[VM] <a:wrong:1436956421110632489> Components v2 panel failed: {e}")
            import traceback
            traceback.print_exc()

    @commands.Cog.listener()
    async def on_interaction(self, interaction):
        """Handle Components v2 button interactions"""
        if not interaction.data or interaction.data.get("component_type") != 2:  # Button
            return
        
        custom_id = interaction.data.get("custom_id", "")
        if not (custom_id.startswith("cv2_") or custom_id.startswith("vm_")):
            return
        
        # Parse custom_id: vm_action_channelid_ownerid or vm_action_toggle_channelid_ownerid
        try:
            parts = custom_id.split("_")
            if len(parts) == 4:
                _, action, channel_id, owner_id = parts
            elif len(parts) == 5 and parts[2] == "toggle":
                _, action, _, channel_id, owner_id = parts
                action = f"{action}_toggle"
            else:
                return await interaction.response.send_message("<a:wrong:1436956421110632489> Invalid button format!", ephemeral=True)
            
            channel_id = int(channel_id)
            owner_id = int(owner_id)
        except (ValueError, IndexError):
            return await interaction.response.send_message("<a:wrong:1436956421110632489> Invalid button!", ephemeral=True)
        
        # Check permissions (allow claim button for anyone if owner left)
        if interaction.user.id != owner_id and action != "claim":
            return await interaction.response.send_message("<a:wrong:1436956421110632489> Only the channel owner can use this!", ephemeral=True)
        
        channel = interaction.guild.get_channel(channel_id) if interaction.guild else None
        if not channel:
            return await interaction.response.send_message("<a:wrong:1436956421110632489> Channel not found!", ephemeral=True)
        
        # Handle different CV2 actions using channel permissions (not roles)
        try:
            if action == "lock_toggle":
                # Toggle lock/unlock
                current_perms = channel.overwrites_for(channel.guild.default_role)
                is_locked = current_perms.connect == False
                
                if is_locked:
                    await channel.set_permissions(channel.guild.default_role, connect=None)
                    await interaction.response.send_message("<a:lock:1437496504955699402> Channel unlocked!", ephemeral=True)
                else:
                    await channel.set_permissions(channel.guild.default_role, connect=False)
                    await interaction.response.send_message("<a:lock:1437496504955699402> Channel locked!", ephemeral=True)
            
            elif action == "hide_toggle":
                # Toggle hide/reveal
                current_perms = channel.overwrites_for(channel.guild.default_role)
                is_hidden = current_perms.view_channel == False
                
                if is_hidden:
                    await channel.set_permissions(channel.guild.default_role, view_channel=None)
                    await interaction.response.send_message("🔍 Channel revealed!", ephemeral=True)
                else:
                    await channel.set_permissions(channel.guild.default_role, view_channel=False)
                    await interaction.response.send_message("🔍 Channel hidden!", ephemeral=True)
            
            elif action == "limit":
                # Show user limit modal
                from discord.ui import Modal, TextInput
                
                class LimitModal(Modal):
                    def __init__(self):
                        super().__init__(title="Set User Limit")
                        self.limit_input = TextInput(
                            label="User Limit (0 = unlimited)",
                            placeholder="Enter number between 0-99",
                            default=str(channel.user_limit) if channel.user_limit else "0",
                            max_length=2
                        )
                        self.add_item(self.limit_input)
                    
                    async def on_submit(self, modal_interaction):
                        try:
                            limit = int(self.limit_input.value)
                            if limit < 0 or limit > 99:
                                return await modal_interaction.response.send_message("<a:wrong:1436956421110632489> Limit must be between 0-99!", ephemeral=True)
                            
                            await channel.edit(user_limit=limit if limit > 0 else None)
                            limit_text = "∞" if limit == 0 else str(limit)
                            await modal_interaction.response.send_message(f"<a:yes:1431909187247673464> User limit set to {limit_text}!", ephemeral=True)
                        except ValueError:
                            await modal_interaction.response.send_message("<a:wrong:1436956421110632489> Please enter a valid number!", ephemeral=True)
                        except Exception as e:
                            await modal_interaction.response.send_message(f"<a:wrong:1436956421110632489> Error: {e}", ephemeral=True)
                
                await interaction.response.send_modal(LimitModal())
            
            elif action == "mute_toggle":
                # Toggle mute all/unmute all
                voice_members = [m for m in channel.members if m.voice]
                if not voice_members:
                    return await interaction.response.send_message("<a:wrong:1436956421110632489> No members in voice channel!", ephemeral=True)
                
                # Check current state
                muted_members = [m for m in voice_members if m.voice.mute]
                all_muted = len(muted_members) > 0 and len(muted_members) == len(voice_members)
                
                success_count = 0
                if all_muted:
                    # Unmute all
                    for member in voice_members:
                        try:
                            await member.edit(mute=False)
                            success_count += 1
                        except:
                            pass
                    await interaction.response.send_message(f"<:speaker:1428183066311921804> Unmuted {success_count} members!", ephemeral=True)
                else:
                    # Mute all
                    for member in voice_members:
                        if member.id != owner_id:  # Don't mute the owner
                            try:
                                await member.edit(mute=True)
                                success_count += 1
                            except:
                                pass
                    await interaction.response.send_message(f"<:speaker:1428183066311921804> Muted {success_count} members!", ephemeral=True)
            
            elif action == "claim":
                # Check if original owner is still in the channel
                original_owner = interaction.guild.get_member(owner_id)
                if original_owner and original_owner in channel.members:
                    return await interaction.response.send_message("<a:wrong:1436956421110632489> The original owner is still in the channel!", ephemeral=True)
                
                # Update ownership in database
                async with aiosqlite.connect(VOICEMASTER_DB_PATH) as db:
                    await db.execute(
                        "UPDATE vm_temp_channels SET owner_id = ? WHERE channel_id = ?",
                        (interaction.user.id, channel.id)
                    )
                    await db.commit()
                
                # Transfer temp role if it exists
                async with aiosqlite.connect(VOICEMASTER_DB_PATH) as db:
                    async with db.execute(
                        "SELECT temp_role_id FROM vm_temp_channels WHERE channel_id = ?",
                        (channel.id,)
                    ) as cursor:
                        result = await cursor.fetchone()
                        if result and result[0]:
                            temp_role = channel.guild.get_role(result[0])
                            if temp_role:
                                try:
                                    # Remove role from old owner
                                    if original_owner:
                                        await original_owner.remove_roles(temp_role)
                                    # Give role to new owner
                                    await interaction.user.add_roles(temp_role)
                                except Exception:
                                    pass
                
                await interaction.response.send_message("<a:crown:1437503143591153756> Channel ownership claimed successfully!", ephemeral=True)
            
            elif action == "close":
                # Confirm channel deletion
                from discord.ui import View, Button
                
                class ConfirmDeleteView(View):
                    def __init__(self):
                        super().__init__(timeout=30)
                    
                    @discord.ui.button(label="<a:yes:1431909187247673464> Confirm Delete", style=discord.ButtonStyle.danger)
                    async def confirm_delete(self, button_interaction, button):
                        if button_interaction.user.id != interaction.user.id:
                            return await button_interaction.response.send_message("<a:wrong:1436956421110632489> Only the command user can confirm!", ephemeral=True)
                        
                        try:
                            # Clean up temp role
                            async with aiosqlite.connect(VOICEMASTER_DB_PATH) as db:
                                # Clean up legacy roles if they exist
                                async with db.execute(
                                    "SELECT temp_role_id FROM vm_temp_channels WHERE channel_id = ?",
                                    (channel.id,)
                                ) as cursor:
                                    result = await cursor.fetchone()
                                    if result and result[0]:
                                        temp_role = channel.guild.get_role(result[0])
                                        if temp_role:
                                            await temp_role.delete(reason="VoiceMaster: Cleaning up legacy role")
                                            print(f"[VM] 🧹 Cleaned up legacy role on channel close")
                                
                                # Remove from database
                                await db.execute("DELETE FROM vm_temp_channels WHERE channel_id = ?", (channel.id,))
                                await db.commit()
                            
                            # Delete the channel
                            await channel.delete(reason=f"VoiceMaster: Closed by {interaction.user.display_name}")
                            await button_interaction.response.send_message("<a:wrong:1436956421110632489> Channel deleted successfully!", ephemeral=True)
                        
                        except Exception as e:
                            await button_interaction.response.send_message(f"<a:wrong:1436956421110632489> Error deleting channel: {e}", ephemeral=True)
                    
                    @discord.ui.button(label="<a:wrong:1436956421110632489> Cancel", style=discord.ButtonStyle.secondary)
                    async def cancel_delete(self, button_interaction, button):
                        if button_interaction.user.id != interaction.user.id:
                            return await button_interaction.response.send_message("<a:wrong:1436956421110632489> Only the command user can cancel!", ephemeral=True)
                        
                        await button_interaction.response.send_message("<a:yes:1431909187247673464> Channel deletion cancelled.", ephemeral=True)
                
                embed = discord.Embed(
                    title="<a:wrong:1436956421110632489> Confirm Channel Deletion",
                    description=f"Are you sure you want to **permanently delete** `{channel.name}`?\n\n⚠️ **This action cannot be undone!**",
                    color=0xFF6B6B
                )
                await interaction.response.send_message(embed=embed, view=ConfirmDeleteView(), ephemeral=True)
            
            elif action == "disconnect":
                # Show member selection modal to disconnect
                voice_members = [m for m in channel.members if m.voice and m.id != owner_id]
                if not voice_members:
                    return await interaction.response.send_message("<a:wrong:1436956421110632489> No members to disconnect!", ephemeral=True)
                
                # Create a select menu to choose member
                from discord.ui import View, Select
                
                class DisconnectView(View):
                    def __init__(self, members):
                        super().__init__(timeout=60)
                        options = [
                            discord.SelectOption(
                                label=m.display_name,
                                value=str(m.id),
                                description=f"Disconnect {m.display_name}"
                            )
                            for m in members[:25]  # Discord limit
                        ]
                        self.member_select = Select(
                            placeholder="Choose a member to disconnect",
                            options=options
                        )
                        self.member_select.callback = self.select_callback
                        self.add_item(self.member_select)
                    
                    async def select_callback(self, interaction):
                        if interaction.user.id != owner_id:
                            return await interaction.response.send_message("<a:wrong:1436956421110632489> Only the channel owner can do this!", ephemeral=True)
                        
                        member_id = int(self.member_select.values[0])
                        member = interaction.guild.get_member(member_id)
                        if member and member.voice and member.voice.channel == channel:
                            try:
                                await member.move_to(None)
                                await interaction.response.send_message(f"🚪 Disconnected {member.mention}!", ephemeral=True)
                            except Exception as e:
                                await interaction.response.send_message(f"<a:wrong:1436956421110632489> Error: {e}", ephemeral=True)
                        else:
                            await interaction.response.send_message("<a:wrong:1436956421110632489> Member not found or not in voice!", ephemeral=True)
                
                await interaction.response.send_message("🚪 Select a member to disconnect:", view=DisconnectView(voice_members), ephemeral=True)
            
            elif action == "activity":
                # Show activity selection
                from discord.ui import View, Select
                
                activities = {
                    "poker": "Poker Night",
                    "betrayal": "Betrayal.io",
                    "fishing": "Fishington.io",
                    "youtube": "Watch Together",
                    "chess": "Chess in the Park",
                    "checkers": "Checkers in the Park",
                    "doodle": "Doodle Crew",
                    "letter": "Letter League",
                    "word": "Word Snacks",
                    "sketch": "Sketch Heads"
                }
                
                class ActivityView(View):
                    def __init__(self):
                        super().__init__(timeout=60)
                        options = [
                            discord.SelectOption(label=name, value=key)
                            for key, name in list(activities.items())[:25]
                        ]
                        self.activity_select = Select(
                            placeholder="Choose an activity",
                            options=options
                        )
                        self.activity_select.callback = self.select_callback
                        self.add_item(self.activity_select)
                    
                    async def select_callback(self, interaction):
                        if interaction.user.id != owner_id:
                            return await interaction.response.send_message("<a:wrong:1436956421110632489> Only the channel owner can do this!", ephemeral=True)
                        
                        activity_key = self.activity_select.values[0]
                        activity_name = activities[activity_key]
                        try:
                            # Create activity invite
                            invite = await channel.create_invite(
                                target_type=discord.InviteTarget.embedded_application,
                                target_application_id=self.get_activity_id(activity_key),
                                max_age=3600
                            )
                            await interaction.response.send_message(
                                f"🎮 **{activity_name}** started!\n{invite.url}",
                                ephemeral=False
                            )
                        except Exception as e:
                            await interaction.response.send_message(f"<a:wrong:1436956421110632489> Error: {e}", ephemeral=True)
                    
                    def get_activity_id(self, key):
                        """Get Discord activity application ID"""
                        ids = {
                            "poker": 755827207812677713,
                            "betrayal": 773336526917861400,
                            "fishing": 814288819477020702,
                            "youtube": 880218394199220334,
                            "chess": 832012774040141894,
                            "checkers": 832013003968348200,
                            "doodle": 878067389634314250,
                            "letter": 879863686565621790,
                            "word": 879863976006127627,
                            "sketch": 902271654783242291
                        }
                        return ids.get(key, 755827207812677713)
                
                await interaction.response.send_message("<:game:1437833296477294847> Select an activity to start:", view=ActivityView(), ephemeral=True)
            
            elif action == "info":
                # Show channel information
                member_count = len(channel.members)
                limit_text = "∞" if channel.user_limit == 0 else str(channel.user_limit)
                bitrate_kbps = channel.bitrate // 1000
                
                locked = channel.overwrites_for(channel.guild.default_role).connect == False
                hidden = channel.overwrites_for(channel.guild.default_role).view_channel == False
                
                status_emojis = []
                if locked:
                    status_emojis.append("<a:lock:1437496504955699402> Locked")
                if hidden:
                    status_emojis.append("<:offline:1431491401195061393> Hidden")
                
                status_text = " • ".join(status_emojis) if status_emojis else "🔓 Open"
                
                embed = discord.Embed(
                    title=f"<a:mark:1436953593923244113> {channel.name}",
                    color=discord.Color.from_rgb(88, 101, 242)
                )
                embed.add_field(name="<:ppl:1427471598578958386> Members", value=f"{member_count}/{limit_text}", inline=True)
                embed.add_field(name="<a:loading:1430203733593034893> Bitrate", value=f"{bitrate_kbps} kbps", inline=True)
                embed.add_field(name="<:like:1428199620554657842> Status", value=status_text, inline=True)
                embed.add_field(name="<a:crown:1437503143591153756> Owner", value=f"<@{owner_id}>", inline=True)
                embed.add_field(name="<a:bookmark:1436953655348691024> Created", value=f"<t:{int(channel.created_at.timestamp())}:R>", inline=True)
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
            
            elif action == "settings":
                # Show enhanced settings panel with more CV2 controls
                await self.show_advanced_settings(interaction, channel, owner_id)
                return  # Method handles its own response
            
            else:
                await interaction.response.send_message("<a:wrong:1436956421110632489> Unknown action!", ephemeral=True)
                
        except Exception as e:
            await interaction.response.send_message(f"<a:wrong:1436956421110632489> Error: {e}", ephemeral=True)

    async def show_advanced_settings(self, interaction, channel, owner_id):
        """Show advanced channel settings with Components v2 controls"""
        from discord.ui import View, Button, Select, Modal, TextInput
        
        limit_text = "∞" if channel.user_limit == 0 else str(channel.user_limit)
        locked = channel.overwrites_for(channel.guild.default_role).connect == False
        hidden = channel.overwrites_for(channel.guild.default_role).view_channel == False
        
        embed = discord.Embed(
            title="<a:gear:1430203750324240516> Advanced Channel Settings",
            description=f"Managing **{channel.name}** • Owner: <@{owner_id}>",
            color=0x5865F2
        )
        embed.add_field(name="<:ppl:1427471598578958386> User Limit", value=limit_text, inline=True)
        embed.add_field(name="<a:lock:1437496504955699402> Status", value="Locked" if locked else "Unlocked", inline=True)
        embed.add_field(name="<:offline:1431491401195061393> Visibility", value="Hidden" if hidden else "Visible", inline=True)
        embed.add_field(name="🎤 Bitrate", value=f"{channel.bitrate // 1000}kbps", inline=True)
        embed.add_field(name="📊 Members", value=f"{len(channel.members)}/{limit_text}", inline=True)
        embed.add_field(name="<:game:1437833296477294847> Activities", value="Click below to start!", inline=True)
        
        class AdvancedSettingsView(View):
            def __init__(self):
                super().__init__(timeout=300)
            
            @discord.ui.button(label="Set User Limit", emoji="<:ppl:1427471598578958386>", style=discord.ButtonStyle.primary)
            async def set_limit(self, interaction, button):
                if interaction.user.id != owner_id:
                    return await interaction.response.send_message("<a:wrong:1436956421110632489> Only channel owner can use this!", ephemeral=True)
                
                class LimitModal(Modal):
                    def __init__(self):
                        super().__init__(title="Set User Limit")
                        self.limit_input = TextInput(
                            label="User Limit (0 = unlimited)",
                            placeholder="Enter number between 0-99",
                            default=str(channel.user_limit),
                            max_length=2
                        )
                        self.add_item(self.limit_input)
                    
                    async def on_submit(self, interaction):
                        try:
                            limit = int(self.limit_input.value)
                            if limit < 0 or limit > 99:
                                return await interaction.response.send_message("<a:wrong:1436956421110632489> Limit must be between 0-99!", ephemeral=True)
                            
                            await channel.edit(user_limit=limit if limit > 0 else None)
                            limit_text = "∞" if limit == 0 else str(limit)
                            await interaction.response.send_message(f"<a:yes:1431909187247673464> User limit set to {limit_text}!", ephemeral=True)
                        except ValueError:
                            await interaction.response.send_message("<a:wrong:1436956421110632489> Please enter a valid number!", ephemeral=True)
                        except Exception as e:
                            await interaction.response.send_message(f"<a:wrong:1436956421110632489> Error: {e}", ephemeral=True)
                
                await interaction.response.send_modal(LimitModal())
            
            @discord.ui.button(label="Change Name", emoji="✏️", style=discord.ButtonStyle.secondary)
            async def change_name(self, interaction, button):
                if interaction.user.id != owner_id:
                    return await interaction.response.send_message("<a:wrong:1436956421110632489> Only channel owner can use this!", ephemeral=True)
                
                class NameModal(Modal):
                    def __init__(self):
                        super().__init__(title="Change Channel Name")
                        self.name_input = TextInput(
                            label="New Channel Name",
                            placeholder="Enter new channel name",
                            default=channel.name,
                            max_length=100
                        )
                        self.add_item(self.name_input)
                    
                    async def on_submit(self, interaction):
                        try:
                            await channel.edit(name=self.name_input.value)
                            await interaction.response.send_message(f"<a:yes:1431909187247673464> Channel renamed to **{self.name_input.value}**!", ephemeral=True)
                        except Exception as e:
                            await interaction.response.send_message(f"<a:wrong:1436956421110632489> Error: {e}", ephemeral=True)
                
                await interaction.response.send_modal(NameModal())
            
            @discord.ui.button(label="Transfer Ownership", emoji="<a:crown:1437503143591153756>", style=discord.ButtonStyle.danger)
            async def transfer_ownership(self, interaction, button):
                if interaction.user.id != owner_id:
                    return await interaction.response.send_message("<a:wrong:1436956421110632489> Only channel owner can use this!", ephemeral=True)
                
                if len(channel.members) < 2:
                    return await interaction.response.send_message("<a:wrong:1436956421110632489> No other members to transfer to!", ephemeral=True)
                
                # Create user selection dropdown
                user_options = []
                for member in channel.members[:20]:  # Discord limit
                    if member.id != owner_id and not member.bot:
                        user_options.append(discord.SelectOption(
                            label=member.display_name[:100],
                            description=f"@{member.name}",
                            value=str(member.id),
                            emoji="<:ar:1427471532841631855>"
                        ))
                
                if not user_options:
                    return await interaction.response.send_message("<a:wrong:1436956421110632489> No valid members to transfer to!", ephemeral=True)
                
                class TransferView(View):
                    def __init__(self):
                        super().__init__(timeout=60)
                        self.add_item(discord.ui.Select(
                            placeholder="Select new channel owner...",
                            options=user_options,
                            custom_id="transfer_select"
                        ))
                    
                    @discord.ui.select(custom_id="transfer_select")
                    async def transfer_select(self, interaction, select):
                        new_owner_id = int(select.values[0])
                        new_owner = channel.guild.get_member(new_owner_id)
                        
                        # Update database
                        async with aiosqlite.connect(VOICEMASTER_DB_PATH) as db:
                            await db.execute(
                                "UPDATE vm_temp_channels SET owner_id = ? WHERE channel_id = ?",
                                (new_owner_id, channel.id)
                            )
                            await db.commit()
                        
                        # Update channel permissions if temp role exists
                        async with aiosqlite.connect(VOICEMASTER_DB_PATH) as db:
                            async with db.execute(
                                "SELECT temp_role_id FROM vm_temp_channels WHERE channel_id = ?",
                                (channel.id,)
                            ) as cursor:
                                result = await cursor.fetchone()
                                if result and result[0]:
                                    temp_role = channel.guild.get_role(result[0])
                                    if temp_role:
                                        try:
                                            # Remove role from old owner
                                            old_owner = channel.guild.get_member(owner_id)
                                            if old_owner:
                                                await old_owner.remove_roles(temp_role)
                                            
                                            # Give role to new owner
                                            await new_owner.add_roles(temp_role)
                                        except Exception:
                                            pass  # Continue even if role management fails
                        
                        await interaction.response.send_message(
                            f"<a:yes:1431909187247673464> Channel ownership transferred to **{new_owner.display_name}**!",
                            ephemeral=True
                        )
                
                await interaction.response.send_message(
                    "👑 **Transfer Channel Ownership**\nSelect the new owner from the dropdown below:",
                    view=TransferView(),
                    ephemeral=True
                )
            
            @discord.ui.select(
                placeholder=" Start a Discord Activity...",
                options=[
                    discord.SelectOption(label="YouTube Together", description="Watch videos together", value="youtube", emoji="📺"),
                    discord.SelectOption(label="Poker Night", description="Play poker with friends", value="poker", emoji="🃏"),
                    discord.SelectOption(label="Chess In The Park", description="Play chess together", value="chess", emoji="♟️"),
                    discord.SelectOption(label="Betrayal.io", description="Social deduction game", value="betrayal", emoji="🕵️"),
                    discord.SelectOption(label="Fishington.io", description="Go fishing together", value="fishington", emoji="🎣"),
                    discord.SelectOption(label="Sketch Heads", description="Drawing and guessing", value="sketchheads", emoji="🎨"),
                    discord.SelectOption(label="Letter League", description="Word game challenge", value="letterleague", emoji="📝"),
                    discord.SelectOption(label="SpellCast", description="Spelling game", value="spellcast", emoji="✨"),
                    discord.SelectOption(label="Checkers In The Park", description="Classic checkers", value="checkers", emoji="🔴"),
                    discord.SelectOption(label="Blazing 8s", description="Card game fun", value="blazing8s", emoji="🎴")
                ],
                custom_id="activity_select"
            )
            async def activity_select(self, interaction, select):
                if interaction.user.id != owner_id:
                    return await interaction.response.send_message("<a:wrong:1436956421110632489> Only channel owner can start activities!", ephemeral=True)
                
                activity_map = {
                    "youtube": "880218394199220334",
                    "poker": "755827207812677713", 
                    "chess": "832012774040141894",
                    "betrayal": "773336526917861400",
                    "fishington": "814288819477020702",
                    "sketchheads": "902271654783242291",
                    "letterleague": "879863686565621790",
                    "spellcast": "852509694341283871",
                    "checkers": "832013003968348200",
                    "blazing8s": "832025144389533716"
                }
                
                activity_id = activity_map.get(select.values[0])
                if not activity_id:
                    return await interaction.response.send_message("<a:wrong:1436956421110632489> Activity not found!", ephemeral=True)
                
                try:
                    invite = await channel.create_activity_invite(
                        activity_id,
                        max_age=3600,  # 1 hour
                        max_uses=0     # Unlimited uses
                    )
                    
                    activity_name = next((opt.label for opt in select.options if opt.value == select.values[0]), "Unknown Activity")
                    
                    embed = discord.Embed(
                        title=f" {activity_name} Started!",
                        description=f"[**Click here to join the activity!**]({invite.url})",
                        color=0x5865F2
                    )
                    embed.add_field(
                        name=" Activity Info",
                        value=f"**Channel:** {channel.name}\n**Started by:** {interaction.user.mention}\n**Expires:** <t:{int((interaction.created_at.timestamp() + 3600))}:R>",
                        inline=False
                    )
                    
                    await interaction.response.send_message(embed=embed)
                    
                except Exception as e:
                    await interaction.response.send_message(f"<a:wrong:1436956421110632489> Failed to start activity: {e}", ephemeral=True)
        
        await interaction.response.send_message(embed=embed, view=AdvancedSettingsView(), ephemeral=True)

    @commands.group(name="voicemaster", aliases=["vm"], invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    async def voicemaster_setup(self, ctx):
        """VoiceMaster main command"""
        embed = discord.Embed(
            title=" VoiceMaster System",
            description="Create and manage temporary voice channels with beautiful Components v2 interface!",
            color=0x5865F2
        )
        embed.add_field(
            name=" Available Commands",
            value=(
                "`!vm setup` - Set up VoiceMaster for your server\n"
                "`!vm panel` - Resend control panel in current voice channel\n"
                "`!vm config` - View current configuration"
            ),
            inline=False
        )
        embed.set_footer(text="VoiceMaster - Beautiful Components v2 Implementation")
        await ctx.send(embed=embed)

    @voicemaster_setup.command(name="setup")
    @commands.has_permissions(administrator=True)
    async def vm_setup(self, ctx):
        """Complete VoiceMaster setup with Components v2 interface"""
        embed = discord.Embed(
            title=" VoiceMaster Setup",
            description="Let's set up VoiceMaster for your server! Follow the interactive setup.",
            color=0x5865F2
        )
        embed.add_field(
            name=" Setup Steps",
            value=(
                "1️⃣ **Select Category** - Choose where temp channels will be created\n"
                "2️⃣ **Select Create Channel** - Choose the 'Join to Create' channel\n"
                "3️⃣ **Configure Settings** - Set name format, limits, and options"
            ),
            inline=False
        )
        
        from discord.ui import View, Select, Button
        
        # Category Selection Dropdown
        category_options = []
        for category in ctx.guild.categories[:25]:  # Discord limit
            category_options.append(discord.SelectOption(
                label=category.name[:100],
                description=f"ID: {category.id} • {len(category.channels)} channels",
                value=str(category.id),
                emoji="📁"
            ))
        
        if not category_options:
            embed.add_field(name="<a:wrong:1436956421110632489> No Categories", value="Please create a category first!", inline=False)
            return await ctx.send(embed=embed)
        
        class SetupView(View):
            def __init__(self):
                super().__init__(timeout=300)
                self.category_id = None
                self.create_channel_id = None
        
            @discord.ui.select(
                placeholder=" Select a category for temp channels...",
                options=category_options,
                custom_id="setup_category"
            )
            async def category_select(self, interaction, select):
                if interaction.user != ctx.author:
                    return await interaction.response.send_message("<a:wrong:1436956421110632489> Only the command author can use this!", ephemeral=True)
                
                self.category_id = int(select.values[0])
                category = ctx.guild.get_channel(self.category_id)
                
                await interaction.response.edit_message(
                    embed=discord.Embed(
                        title="<a:yes:1431909187247673464> Category Selected",
                        description=f"Selected: **{category.name}**\n\nNow select the 'Join to Create' voice channel:",
                        color=0x5865F2
                    ),
                    view=ChannelSelectView(self.category_id)
                )
        
        class ChannelSelectView(View):
            def __init__(self, category_id):
                super().__init__(timeout=300)
                self.category_id = category_id
                
                # Voice channel options
                channel_options = []
                category = ctx.guild.get_channel(category_id)
                for channel in category.voice_channels[:25]:
                    channel_options.append(discord.SelectOption(
                        label=channel.name[:100],
                        description=f"Members: {len(channel.members)} • Bitrate: {channel.bitrate//1000}kbps",
                        value=str(channel.id),
                        emoji="🎤"
                    ))
                
                if channel_options:
                    self.add_item(discord.ui.Select(
                        placeholder="🎤 Select the 'Join to Create' voice channel...",
                        options=channel_options,
                        custom_id="setup_channel"
                    ))
            
            @discord.ui.select(custom_id="setup_channel")
            async def channel_select(self, interaction, select):
                if interaction.user != ctx.author:
                    return await interaction.response.send_message("<a:wrong:1436956421110632489> Only the command author can use this!", ephemeral=True)
                
                create_channel_id = int(select.values[0])
                create_channel = ctx.guild.get_channel(create_channel_id)
                category = ctx.guild.get_channel(self.category_id)
                
                # Save configuration
                async with aiosqlite.connect(VOICEMASTER_DB_PATH) as db:
                    await db.execute("""
                        INSERT OR REPLACE INTO vm_guild_config 
                        (guild_id, create_channel_id, category_id, enabled, use_cv2)
                        VALUES (?, ?, ?, 1, 1)
                    """, (ctx.guild.id, create_channel_id, self.category_id))
                    await db.commit()
                
                success_embed = discord.Embed(
                    title=" VoiceMaster Setup Complete!",
                    description="Your VoiceMaster system is now ready to use!",
                    color=0x00FF00
                )
                success_embed.add_field(
                    name=" Configuration",
                    value=(
                        f"**Category:** {category.name}\n"
                        f"**Create Channel:** {create_channel.name}\n"
                        f"**Interface:** Components v2 ✨\n"
                        f"**Status:** Enabled <a:yes:1431909187247673464>"
                    ),
                    inline=False
                )
                success_embed.add_field(
                    name=" Next Steps",
                    value=(
                        f"• Users can now join **{create_channel.name}** to create temp channels\n"
                        f"• Use `!vm config` to customize settings\n"
                        f"• Use `!vm panel` in temp channels for controls"
                    ),
                    inline=False
                )
                
                await interaction.response.edit_message(embed=success_embed, view=None)
        
        await ctx.send(embed=embed, view=SetupView())

    @voicemaster_setup.command(name="config")
    @commands.has_permissions(manage_guild=True)
    async def vm_config(self, ctx):
        """View and manage VoiceMaster configuration"""
        async with aiosqlite.connect(VOICEMASTER_DB_PATH) as db:
            async with db.execute(
                "SELECT * FROM vm_guild_config WHERE guild_id = ?",
                (ctx.guild.id,)
            ) as cursor:
                config = await cursor.fetchone()
        
        if not config:
            embed = discord.Embed(
                title="<a:wrong:1436956421110632489> VoiceMaster Not Setup",
                description="VoiceMaster is not set up in this server!\n\nUse `!vm setup` to get started.",
                color=0xFF6B6B
            )
            return await ctx.send(embed=embed)
        
        (guild_id, create_channel_id, category_id, enabled, channel_name_format, 
         channel_limit, delete_empty, use_cv2) = config
        
        create_channel = ctx.guild.get_channel(create_channel_id)
        category = ctx.guild.get_channel(category_id)
        
        embed = discord.Embed(
            title=" VoiceMaster Configuration",
            description=f"Current configuration for **{ctx.guild.name}**",
            color=0x5865F2
        )
        
        embed.add_field(
            name=" Basic Settings",
            value=(
                f"**Status:** {'<a:yes:1431909187247673464> Enabled' if enabled else '<a:wrong:1436956421110632489> Disabled'}\n"
                f"**Category:** {category.name if category else '<a:wrong:1436956421110632489> Missing'}\n"
                f"**Create Channel:** {create_channel.name if create_channel else '<a:wrong:1436956421110632489> Missing'}\n"
                f"**Interface:** {'Components v2 ✨' if use_cv2 else 'Traditional'}"
            ),
            inline=False
        )
        
        embed.add_field(
            name=" Channel Settings",
            value=(
                f"**Name Format:** `{channel_name_format}`\n"
                f"**Channel Limit:** {channel_limit if channel_limit > 0 else 'Unlimited'}\n"
                f"**Delete Empty:** {'<a:yes:1431909187247673464> Yes' if delete_empty else '<a:wrong:1436956421110632489> No'}"
            ),
            inline=False
        )
        
        # Get temp channel statistics
        async with aiosqlite.connect(VOICEMASTER_DB_PATH) as db:
            async with db.execute(
                "SELECT COUNT(*) FROM vm_temp_channels WHERE guild_id = ?",
                (ctx.guild.id,)
            ) as cursor:
                result = await cursor.fetchone()
                temp_count = result[0] if result else 0
        
        embed.add_field(
            name=" Statistics",
            value=(
                f"**Active Temp Channels:** {temp_count}\n"
                f"**Category Usage:** {len(category.channels) if category else 0}/40 channels"
            ),
            inline=False
        )
        
        embed.set_footer(text="Use buttons below to modify settings")
        
        from discord.ui import View, Button
        
        class ConfigView(View):
            def __init__(self):
                super().__init__(timeout=180)
            
            @discord.ui.button(label="Toggle Status", emoji="🔄", style=discord.ButtonStyle.primary)
            async def toggle_status(self, interaction, button):
                if interaction.user != ctx.author:
                    return await interaction.response.send_message("<a:wrong:1436956421110632489> Only the command author can use this!", ephemeral=True)
                
                new_status = not enabled
                async with aiosqlite.connect(VOICEMASTER_DB_PATH) as db:
                    await db.execute(
                        "UPDATE vm_guild_config SET enabled = ? WHERE guild_id = ?",
                        (new_status, ctx.guild.id)
                    )
                    await db.commit()
                
                await interaction.response.send_message(
                    f"<a:yes:1431909187247673464> VoiceMaster {'enabled' if new_status else 'disabled'} successfully!",
                    ephemeral=True
                )
            
            @discord.ui.button(label="Change Name Format", emoji="✏️", style=discord.ButtonStyle.secondary)
            async def change_name_format(self, interaction, button):
                if interaction.user != ctx.author:
                    return await interaction.response.send_message("<a:wrong:1436956421110632489> Only the command author can use this!", ephemeral=True)
                
                from discord.ui import Modal, TextInput
                
                class NameFormatModal(Modal):
                    def __init__(self):
                        super().__init__(title="Change Channel Name Format")
                        
                        self.name_format = TextInput(
                            label="Channel Name Format",
                            placeholder="Available variables: {username}, {user}, {mention}",
                            default=channel_name_format,
                            max_length=100
                        )
                        self.add_item(self.name_format)
                    
                    async def on_submit(self, interaction):
                        async with aiosqlite.connect(VOICEMASTER_DB_PATH) as db:
                            await db.execute(
                                "UPDATE vm_guild_config SET channel_name_format = ? WHERE guild_id = ?",
                                (self.name_format.value, ctx.guild.id)
                            )
                            await db.commit()
                        
                        await interaction.response.send_message(
                            f"<a:yes:1431909187247673464> Name format updated to: `{self.name_format.value}`",
                            ephemeral=True
                        )
                
                await interaction.response.send_modal(NameFormatModal())
        
        await ctx.send(embed=embed, view=ConfigView())

    @voicemaster_setup.command(name="stats")
    @commands.has_permissions(manage_guild=True)
    async def vm_stats(self, ctx):
        """View detailed VoiceMaster statistics"""
        async with aiosqlite.connect(VOICEMASTER_DB_PATH) as db:
            # Get configuration
            async with db.execute(
                "SELECT * FROM vm_guild_config WHERE guild_id = ?",
                (ctx.guild.id,)
            ) as cursor:
                config = await cursor.fetchone()
            
            if not config:
                embed = discord.Embed(
                    title="<a:wrong:1436956421110632489> VoiceMaster Not Setup",
                    description="Use `!vm setup` to configure VoiceMaster first!",
                    color=0xFF6B6B
                )
                return await ctx.send(embed=embed)
            
            # Get current temp channels
            async with db.execute(
                "SELECT channel_id, owner_id, created_at FROM vm_temp_channels WHERE guild_id = ? ORDER BY created_at DESC LIMIT 10",
                (ctx.guild.id,)
            ) as cursor:
                temp_channels = list(await cursor.fetchall())
            
            # Get total channel count
            async with db.execute(
                "SELECT COUNT(*) FROM vm_temp_channels WHERE guild_id = ?",
                (ctx.guild.id,)
            ) as cursor:
                result = await cursor.fetchone()
                total_channels = result[0] if result else 0
            
            # Get most active users
            async with db.execute("""
                SELECT owner_id, COUNT(*) as channel_count 
                FROM vm_temp_channels 
                WHERE guild_id = ? 
                GROUP BY owner_id 
                ORDER BY channel_count DESC 
                LIMIT 5
            """, (ctx.guild.id,)) as cursor:
                top_users = list(await cursor.fetchall())
        
        category = ctx.guild.get_channel(config[2])
        create_channel = ctx.guild.get_channel(config[1])
        
        embed = discord.Embed(
            title=" VoiceMaster Statistics",
            description=f"Detailed statistics for **{ctx.guild.name}**",
            color=0x5865F2
        )
        
        embed.add_field(
            name=" System Status",
            value=(
                f"**Status:** {'<a:yes:1431909187247673464> Active' if config[3] else '<a:wrong:1436956421110632489> Disabled'}\n"
                f"**Category:** {category.name if category else '<a:wrong:1436956421110632489> Missing'}\n"
                f"**Create Channel:** {create_channel.name if create_channel else '<a:wrong:1436956421110632489> Missing'}\n"
                f"**Total Channels Created:** {total_channels}"
            ),
            inline=False
        )
        
        # Current active channels
        active_channels_text = ""
        active_count = 0
        for channel_id, owner_id, created_at in temp_channels:
            channel = ctx.guild.get_channel(channel_id)
            if channel:
                owner = ctx.guild.get_member(owner_id)
                member_count = len(channel.members)
                active_channels_text += f"🎤 **{channel.name}** • {member_count} members • <@{owner_id}>\n"
                active_count += 1
            
            if active_count >= 5:  # Limit display
                break
        
        if not active_channels_text:
            active_channels_text = "No active temp channels"
        elif len(temp_channels) > 5:
            active_channels_text += f"... and {len(temp_channels) - 5} more"
        
        embed.add_field(
            name=f" Active Channels ({len(temp_channels)})",
            value=active_channels_text,
            inline=False
        )
        
        # Top users
        if top_users:
            top_users_text = ""
            for user_id, count in top_users:
                user = ctx.guild.get_member(user_id)
                if user:
                    top_users_text += f"👤 **{user.display_name}** • {count} channels\n"
                else:
                    top_users_text += f"👤 Unknown User • {count} channels\n"
            
            embed.add_field(
                name=" Top Channel Creators",
                value=top_users_text or "No data available",
                inline=False
            )
        
        # Category usage
        if category:
            embed.add_field(
                name=" Category Usage",
                value=f"**Channels:** {len(category.channels)}/40\n**Usage:** {(len(category.channels)/40)*100:.1f}%",
                inline=True
            )
        
        embed.set_footer(text="Statistics update in real-time")
        await ctx.send(embed=embed)

    @voicemaster_setup.command(name="cleanup")
    @commands.has_permissions(administrator=True)
    async def vm_cleanup(self, ctx):
        """Clean up orphaned temp channels and roles"""
        async with aiosqlite.connect(VOICEMASTER_DB_PATH) as db:
            # Get all temp channels for this guild
            async with db.execute(
                "SELECT channel_id, temp_role_id FROM vm_temp_channels WHERE guild_id = ?",
                (ctx.guild.id,)
            ) as cursor:
                channels_data = list(await cursor.fetchall())
        
        cleaned_channels = 0
        cleaned_roles = 0
        
        for channel_id, role_id in channels_data:
            channel = ctx.guild.get_channel(channel_id)
            
            # Check if channel still exists
            if not channel:
                # Clean up database entry
                async with aiosqlite.connect(VOICEMASTER_DB_PATH) as db:
                    await db.execute("DELETE FROM vm_temp_channels WHERE channel_id = ?", (channel_id,))
                    await db.commit()
                cleaned_channels += 1
                
                # Clean up associated role
                if role_id:
                    role = ctx.guild.get_role(role_id)
                    if role:
                        try:
                            await role.delete(reason="VoiceMaster: Cleaning up orphaned role")
                            cleaned_roles += 1
                        except Exception:
                            pass
            else:
                # Channel exists, check if it's empty and should be deleted
                if len(channel.members) == 0:
                    async with aiosqlite.connect(VOICEMASTER_DB_PATH) as db:
                        async with db.execute(
                            "SELECT delete_empty FROM vm_guild_config WHERE guild_id = ?",
                            (ctx.guild.id,)
                        ) as cursor:
                            config = await cursor.fetchone()
                        
                        if config and config[0]:  # delete_empty is enabled
                            try:
                                # Clean up role first
                                if role_id:
                                    role = ctx.guild.get_role(role_id)
                                    if role:
                                        await role.delete(reason="VoiceMaster: Empty channel cleanup")
                                        cleaned_roles += 1
                                
                                # Delete empty channel
                                await channel.delete(reason="VoiceMaster: Auto-cleanup empty channel")
                                
                                # Remove from database
                                await db.execute("DELETE FROM vm_temp_channels WHERE channel_id = ?", (channel_id,))
                                await db.commit()
                                cleaned_channels += 1
                            except Exception:
                                pass
        
        embed = discord.Embed(
            title=" Cleanup Complete",
            description="VoiceMaster cleanup has finished!",
            color=0x00FF00
        )
        embed.add_field(
            name=" Cleanup Results",
            value=(
                f"**Channels Cleaned:** {cleaned_channels}\n"
                f"**Roles Cleaned:** {cleaned_roles}\n"
                f"**Status:** <a:yes:1431909187247673464> Complete"
            ),
            inline=False
        )
        
        await ctx.send(embed=embed)

    @voicemaster_setup.command(name="list")
    @commands.has_permissions(manage_channels=True)
    async def vm_list(self, ctx):
        """List all current temp channels with management options"""
        async with aiosqlite.connect(VOICEMASTER_DB_PATH) as db:
            async with db.execute(
                "SELECT channel_id, owner_id, created_at, temp_role_id FROM vm_temp_channels WHERE guild_id = ? ORDER BY created_at DESC",
                (ctx.guild.id,)
            ) as cursor:
                channels = list(await cursor.fetchall())
        
        if not channels:
            embed = discord.Embed(
                title=" No Temp Channels",
                description="There are currently no active temporary channels.",
                color=0x5865F2
            )
            return await ctx.send(embed=embed)
        
        # Paginate results
        from math import ceil
        per_page = 10
        total_pages = ceil(len(channels) / per_page)
        current_page = 1
        
        def create_page_embed(page):
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            page_channels = channels[start_idx:end_idx]
            
            embed = discord.Embed(
                title=" Active Temp Channels",
                description=f"Page {page}/{total_pages} • Total: {len(channels)} channels",
                color=0x5865F2
            )
            
            for channel_id, owner_id, created_at, role_id in page_channels:
                channel = ctx.guild.get_channel(channel_id)
                if channel:
                    owner = ctx.guild.get_member(owner_id)
                    member_count = len(channel.members)
                    
                    # Calculate channel age
                    from datetime import datetime
                    try:
                        created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        age = datetime.now().replace(tzinfo=created_dt.tzinfo) - created_dt
                        age_text = f"{age.seconds // 3600}h {(age.seconds % 3600) // 60}m"
                    except:
                        age_text = "Unknown"
                    
                    embed.add_field(
                        name=f"🎤 {channel.name}",
                        value=(
                            f"**Owner:** {owner.mention if owner else 'Unknown'}\n"
                            f"**Members:** {member_count}\n"
                            f"**Age:** {age_text}\n"
                            f"**ID:** `{channel_id}`"
                        ),
                        inline=True
                    )
            
            return embed
        
        from discord.ui import View, Button
        
        class ChannelListView(View):
            def __init__(self):
                super().__init__(timeout=300)
                self.current_page = 1
                self.message: Optional[discord.Message] = None
                self.update_buttons()
            
            def update_buttons(self):
                self.clear_items()
                
                if total_pages > 1:
                    self.add_item(Button(
                        label="◀ Previous",
                        disabled=self.current_page == 1,
                        custom_id="prev_page"
                    ))
                    self.add_item(Button(
                        label=f"Page {self.current_page}/{total_pages}",
                        disabled=True,
                        custom_id="current_page"
                    ))
                    self.add_item(Button(
                        label="Next ▶",
                        disabled=self.current_page == total_pages,
                        custom_id="next_page"
                    ))
                
                self.add_item(Button(
                    label=" Refresh",
                    style=discord.ButtonStyle.secondary,
                    custom_id="refresh"
                ))
                
                if ctx.author.guild_permissions.administrator:
                    self.add_item(Button(
                        label=" Cleanup",
                        style=discord.ButtonStyle.danger,
                        custom_id="cleanup"
                    ))
            
            async def interaction_check(self, interaction):
                return interaction.user == ctx.author
            
            async def on_timeout(self):
                # Disable the view when timeout occurs
                self.clear_items()
                try:
                    if self.message:
                        timeout_embed = discord.Embed(
                            title=" Session Expired",
                            description="This interaction has timed out. Please run the command again.",
                            color=0xFF6B6B
                        )
                        await self.message.edit(embed=timeout_embed, view=None)
                except:
                    pass
            
            @discord.ui.button(custom_id="prev_page")
            async def previous_page(self, interaction, button):
                self.current_page = max(1, self.current_page - 1)
                self.update_buttons()
                embed = create_page_embed(self.current_page)
                await interaction.response.edit_message(embed=embed, view=self)
            
            @discord.ui.button(custom_id="next_page")
            async def next_page(self, interaction, button):
                self.current_page = min(total_pages, self.current_page + 1)
                self.update_buttons()
                embed = create_page_embed(self.current_page)
                await interaction.response.edit_message(embed=embed, view=self)
            
            @discord.ui.button(custom_id="refresh")
            async def refresh_list(self, interaction, button):
                # Re-fetch data
                async with aiosqlite.connect(VOICEMASTER_DB_PATH) as db:
                    async with db.execute(
                        "SELECT channel_id, owner_id, created_at, temp_role_id FROM vm_temp_channels WHERE guild_id = ? ORDER BY created_at DESC",
                        (ctx.guild.id,)
                    ) as cursor:
                        nonlocal channels
                        channels = list(await cursor.fetchall())
                
                embed = create_page_embed(self.current_page)
                await interaction.response.edit_message(embed=embed, view=self)
            
            @discord.ui.button(custom_id="cleanup")
            async def force_cleanup(self, interaction, button):
                if not interaction.user.guild_permissions.administrator:
                    return await interaction.response.send_message("<a:wrong:1436956421110632489> Administrator permission required!", ephemeral=True)
                
                # Perform cleanup
                cleaned = 0
                for channel_id, owner_id, created_at, role_id in channels:
                    channel = ctx.guild.get_channel(channel_id)
                    if not channel or len(channel.members) == 0:
                        # Clean up database
                        async with aiosqlite.connect(VOICEMASTER_DB_PATH) as db:
                            await db.execute("DELETE FROM vm_temp_channels WHERE channel_id = ?", (channel_id,))
                            await db.commit()
                        
                        # Clean up channel
                        if channel:
                            try:
                                await channel.delete(reason="Admin force cleanup")
                            except:
                                pass
                        
                        # Clean up role
                        if role_id:
                            role = ctx.guild.get_role(role_id)
                            if role:
                                try:
                                    await role.delete(reason="Admin force cleanup")
                                except:
                                    pass
                        
                        cleaned += 1
                
                await interaction.response.send_message(f"<a:yes:1431909187247673464> Cleaned up {cleaned} channels!", ephemeral=True)
        
        view = ChannelListView()
        embed = create_page_embed(1)
        message = await ctx.send(embed=embed, view=view)
        view.message = message

    @voicemaster_setup.command(name="panel")
    async def vm_panel(self, ctx):
        """Resend control panel in current voice channel"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            embed = discord.Embed(
                title="<a:wrong:1436956421110632489> Not in Voice Channel",
                description="You must be in a voice channel to use this command!",
                color=0xFF6B6B
            )
            return await ctx.send(embed=embed)
        
        channel = ctx.author.voice.channel
        
        # Check if user owns this temp channel
        async with aiosqlite.connect(VOICEMASTER_DB_PATH) as db:
            async with db.execute(
                "SELECT owner_id FROM vm_temp_channels WHERE channel_id = ?",
                (channel.id,)
            ) as cursor:
                result = await cursor.fetchone()
        
        if not result:
            embed = discord.Embed(
                title="<a:wrong:1436956421110632489> Not a VoiceMaster Channel",
                description="This is not a VoiceMaster temporary channel!",
                color=0xFF6B6B
            )
            return await ctx.send(embed=embed)
        
        if result[0] != ctx.author.id:
            embed = discord.Embed(
                title="<a:wrong:1436956421110632489> Permission Denied", 
                description="You are not the owner of this channel!",
                color=0xFF6B6B
            )
            return await ctx.send(embed=embed)
        
        await self.send_control_panel(channel, ctx.author)
        
        embed = discord.Embed(
            title="<a:yes:1431909187247673464> Panel Sent",
            description=" V2 control panel has been sent!",
            color=0x5865F2
        )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(VoiceMaster(bot))

