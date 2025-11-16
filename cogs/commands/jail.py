import discord
from discord.ext import commands, tasks
import sqlite3
from datetime import datetime, timedelta
import re
from typing import Optional
import json
import math
from utils.dynamic_dropdowns import DynamicChannelSelect, DynamicChannelView, PaginatedChannelView
from utils.timezone_helpers import get_timezone_helpers
from utils.custom_permissions import require_custom_permissions
from utils.member_state import member_state_manager, PunishmentType, MemberState
from utils.error_helpers import StandardErrorHandler

DB_FILE = "db/jail.db"

class JailChannelSelect(discord.ui.Select):
    """Paginated multi-select channel dropdown for jail system"""
    def __init__(self, guild, page=0, selected_channels=None):
        self.guild = guild
        self.page = page
        self.selected_channels = set(selected_channels or [])
        self.channels_per_page = 25
        
        # Get all text channels
        all_channels = [ch for ch in guild.text_channels 
                       if ch.name.lower() not in ['jail', 'jailed', 'timeout']]
        all_channels.sort(key=lambda c: (c.position, c.name.lower()))
        
        # Calculate pagination
        total_pages = max(1, math.ceil(len(all_channels) / self.channels_per_page))
        start_idx = page * self.channels_per_page
        end_idx = min(start_idx + self.channels_per_page, len(all_channels))
        page_channels = all_channels[start_idx:end_idx]
        
        # Create options
        options = []
        for channel in page_channels:
            label = f"#{channel.name}"
            if len(label) > 25:
                label = label[:22] + "..."
            
            description = f"Category: {channel.category.name}" if channel.category else f"ID: {channel.id}"
            if len(description) > 100:
                description = description[:97] + "..."
            
            # Mark selected channels with ✅
            if str(channel.id) in self.selected_channels:
                label = f"✅ {label}"
            
            options.append(discord.SelectOption(
                label=label,
                description=description,
                value=str(channel.id)
            ))
        
        if not options:
            options = [discord.SelectOption(
                label="No channels on this page",
                description="No channels available",
                value="none"
            )]
        
        # Update placeholder with page info
        placeholder = f"Select channels jailed users can access... (Page {page + 1}/{total_pages})"
        
        super().__init__(
            placeholder=placeholder,
            min_values=0,
            max_values=min(len(options), 25),
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        # Toggle selected channels
        for value in self.values:
            if value == "none":
                continue
            if value in self.selected_channels:
                self.selected_channels.remove(value)
            else:
                self.selected_channels.add(value)
        
        # Update embed to show selection
        embed = discord.Embed(
            title="<:file:1427471573304217651> Jail System - Channel Selection",
            color=0xFF6B6B,
            description=f"Selected {len(self.selected_channels)} channels for jailed users to access:"
        )
        
        if self.selected_channels:
            channel_list = []
            for channel_id in self.selected_channels:
                channel = self.guild.get_channel(int(channel_id))
                if channel:
                    channel_list.append(f"• #{channel.name}")
            
            embed.add_field(
                name="<:file:1427471573304217651> Allowed Channels",
                value="\n".join(channel_list) if channel_list else "None selected",
                inline=False
            )
        else:
            embed.add_field(
                name="<:warning:1427471923805925397> No Channels Selected",
                value="Jailed users will have no accessible channels",
                inline=False
            )
        
        embed.add_field(
            name="<:info:1427471892407484478> Next Step",
            value="Click **Apply Permissions** to configure channel access automatically",
            inline=False
        )
        
        # Update view with current selections
        view = JailSetupView(self.guild, list(self.selected_channels), self.page)
        await interaction.response.edit_message(embed=embed, view=view)

class JailSetupView(discord.ui.View):
    def __init__(self, guild, selected_channels=None, current_page=0):
        super().__init__(timeout=300)
        self.guild = guild
        self.selected_channels = selected_channels or []
        self.current_page = current_page
        
        # Get total pages for navigation
        all_channels = [ch for ch in guild.text_channels 
                       if ch.name.lower() not in ['jail', 'jailed', 'timeout']]
        self.total_pages = max(1, math.ceil(len(all_channels) / 25))
        
        # Add channel selector
        select = JailChannelSelect(guild, current_page, selected_channels)
        self.add_item(select)
        
        # Add navigation buttons if needed
        if self.total_pages > 1:
            # Previous button
            prev_button = discord.ui.Button(
                label="◀️ Previous",
                style=discord.ButtonStyle.secondary,
                disabled=(current_page == 0),
                custom_id="prev_page"
            )
            prev_button.callback = self._prev_page
            self.add_item(prev_button)
            
            # Page info button
            page_button = discord.ui.Button(
                label=f"Page {current_page + 1}/{self.total_pages}",
                style=discord.ButtonStyle.primary,
                disabled=True,
                custom_id="page_info"
            )
            self.add_item(page_button)
            
            # Next button
            next_button = discord.ui.Button(
                label="Next ▶️",
                style=discord.ButtonStyle.secondary,
                disabled=(current_page >= self.total_pages - 1),
                custom_id="next_page"
            )
            next_button.callback = self._next_page
            self.add_item(next_button)
    
    async def _prev_page(self, interaction: discord.Interaction):
        """Go to previous page"""
        if self.current_page > 0:
            new_page = self.current_page - 1
            view = JailSetupView(self.guild, self.selected_channels, new_page)
            await interaction.response.edit_message(view=view)
        else:
            await interaction.response.defer()
    
    async def _next_page(self, interaction: discord.Interaction):
        """Go to next page"""
        if self.current_page < self.total_pages - 1:
            new_page = self.current_page + 1
            view = JailSetupView(self.guild, self.selected_channels, new_page)
            await interaction.response.edit_message(view=view)
        else:
            await interaction.response.defer()
    
    @discord.ui.button(label="Apply Permissions", style=discord.ButtonStyle.green, emoji="<:check:1428163122710970508>")
    async def apply_permissions(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_channels:
            await interaction.response.send_message("<:stop:1427471993984389180> Please select channels first!", ephemeral=True)
            return
        
        await interaction.response.defer(thinking=True)
        
        try:
            # Get jail role from database
            conn = sqlite3.connect('./db/jail.db')
            cursor = conn.cursor()
            cursor.execute(
                "SELECT jail_role FROM jail_settings WHERE guild_id = ?",
                (str(self.guild.id),)
            )
            result = cursor.fetchone()
            
            if not result or not result[0]:
                await interaction.followup.send("<:stop:1427471993984389180> Jail role not configured. Run `/jailsetup` first!")
                return
            
            jail_role = self.guild.get_role(int(result[0]))
            if not jail_role:
                await interaction.followup.send("<:stop:1427471993984389180> Jail role not found. Please reconfigure jail system.")
                return
            
            # Apply permissions to all channels
            success_count = 0
            error_count = 0
            
            for channel in self.guild.channels:
                try:
                    if isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.CategoryChannel)):
                        if str(channel.id) in self.selected_channels:
                            # Allow access to selected channels (jail + appeal channels)
                            overwrites = channel.overwrites_for(jail_role)
                            overwrites.read_messages = True
                            overwrites.send_messages = True
                            overwrites.view_channel = True
                            await channel.set_permissions(jail_role, overwrite=overwrites, reason="Jail system - Allow access")
                        else:
                            # Deny access to all other channels - this is the key fix!
                            overwrites = channel.overwrites_for(jail_role)
                            overwrites.view_channel = False
                            overwrites.read_messages = False
                            overwrites.send_messages = False
                            await channel.set_permissions(jail_role, overwrite=overwrites, reason="Jail system - Deny access")
                        
                        success_count += 1
                
                except discord.Forbidden:
                    error_count += 1
                except Exception as e:
                    error_count += 1
                    print(f"Error setting permissions for {channel.name}: {e}")
            
            # Update database with allowed channels
            cursor.execute(
                "UPDATE jail_settings SET allowed_channels = ? WHERE guild_id = ?",
                (json.dumps(self.selected_channels), str(self.guild.id))
            )
            conn.commit()
            conn.close()
            
            # Success response
            embed = discord.Embed(
                title="<:check:1428163122710970508> Jail Permissions Configured",
                color=0x57F287,
                description="Channel permissions have been configured for the jail role!"
            )
            
            embed.add_field(
                name="<:mod:1427471611262537830> Configuration Applied",
                value=f"<:check:1428163122710970508> Processed: {success_count} channels\n<:stop:1427471993984389180> Errors: {error_count} channels",
                inline=True
            )
            
            embed.add_field(
                name="<:sleep_devs:1427471564860948490> How It Works",
                value=f"**Selected channels:** Jailed users CAN access\n**Other channels:** Jailed users CANNOT access\n**Total accessible:** {len(self.selected_channels)} channels",
                inline=True
            )
            
            selected_channel_list = []
            for channel_id in self.selected_channels:
                channel = self.guild.get_channel(int(channel_id))
                if channel:
                    selected_channel_list.append(f"• {channel.mention}")
            
            if selected_channel_list:
                embed.add_field(
                    name="<:right:1427471506287362068> Accessible Channels",
                    value="\n".join(selected_channel_list[:10]) + ("\n• ..." if len(selected_channel_list) > 10 else ""),
                    inline=False
                )
            
            if error_count > 0:
                embed.add_field(
                    name="<:woah:1428170830042632292> Note",
                    value="Some channels couldn't be configured due to permission restrictions",
                    inline=False
                )
            
            await interaction.edit_original_response(embed=embed, view=None)
            
        except Exception as e:
            error_embed = discord.Embed(
                title="<:woah:1428170830042632292> Permission Setup Failed",
                color=0xFF6B6B,
                description=f"Error: {str(e)}"
            )
            await interaction.edit_original_response(embed=error_embed, view=None)
    
    async def on_timeout(self):
        # View has timed out
        pass

class JailInitialSetupView(discord.ui.View):
    def __init__(self, guild, jail_role):
        super().__init__(timeout=300)
        self.guild = guild
        self.jail_role = jail_role
        self.jail_channel_id = None
        self.log_channel_id = None
        
        # We'll handle channel selection with buttons since we need pagination
        self.current_step = "jail"  # "jail" or "log" or "complete"
        self._update_view()
    
    def _update_view(self):
        """Update view based on current step"""
        self.clear_items()
        
        if self.current_step == "jail":
            # Add button to select jail channel
            select_jail_btn = discord.ui.Button(
                label="Select Jail Channel",
                style=discord.ButtonStyle.primary,
                emoji="🔒"
            )
            select_jail_btn.callback = self._select_jail_channel
            self.add_item(select_jail_btn)
            
        elif self.current_step == "log":
            # Show selected jail channel
            jail_channel = self.guild.get_channel(int(self.jail_channel_id)) if self.jail_channel_id else None
            jail_info_btn = discord.ui.Button(
                label=f"Jail: #{jail_channel.name}" if jail_channel else "Jail: Unknown",
                style=discord.ButtonStyle.secondary,
                disabled=True
            )
            self.add_item(jail_info_btn)
            
            # Add button to select log channel
            select_log_btn = discord.ui.Button(
                label="Select Log Channel (Optional)",
                style=discord.ButtonStyle.primary,
                emoji="📝"
            )
            select_log_btn.callback = self._select_log_channel
            self.add_item(select_log_btn)
            
            # Add skip button
            skip_log_btn = discord.ui.Button(
                label="Skip Log Channel",
                style=discord.ButtonStyle.secondary,
                emoji="⏭️"
            )
            skip_log_btn.callback = self._skip_log_channel
            self.add_item(skip_log_btn)
            
        elif self.current_step == "complete":
            # Show both selections
            jail_channel = self.guild.get_channel(int(self.jail_channel_id)) if self.jail_channel_id else None
            jail_info_btn = discord.ui.Button(
                label=f"Jail: #{jail_channel.name}" if jail_channel else "Jail: Unknown",
                style=discord.ButtonStyle.secondary,
                disabled=True
            )
            self.add_item(jail_info_btn)
            
            if self.log_channel_id:
                log_info_btn = discord.ui.Button(
                    label=f"Log: #{self.guild.get_channel(int(self.log_channel_id)).name}",
                    style=discord.ButtonStyle.secondary,
                    disabled=True
                )
                self.add_item(log_info_btn)
            
            # Add complete setup button
            complete_btn = discord.ui.Button(
                label="Complete Setup",
                style=discord.ButtonStyle.green,
                emoji="<:check:1428163122710970508>"
            )
            complete_btn.callback = self._complete_setup
            self.add_item(complete_btn)
    
    async def _select_jail_channel(self, interaction: discord.Interaction):
        """Show jail channel selection"""
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in servers!", ephemeral=True)
            return
            
        async def jail_callback(interaction, select):
            self.jail_channel_id = select.values[0]
            self.current_step = "log"
            self._update_view()
            
            embed = discord.Embed(
                title="<:shield:1428163169846988941> Jail Setup - Step 2",
                description="Now select a log channel (optional) for jail events:",
                color=0xFF6B6B
            )
            await interaction.response.edit_message(embed=embed, view=self)
        
        view = PaginatedChannelView(
            interaction.guild,
            channel_types=[discord.ChannelType.text],
            custom_callback=jail_callback,
            timeout=300
        )
        
        embed = discord.Embed(
            title="<:shield:1428163169846988941> Jail Setup - Step 1",
            description="Select a channel to use as the jail channel:",
            color=0xFF6B6B
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def _select_log_channel(self, interaction: discord.Interaction):
        """Show log channel selection"""
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in servers!", ephemeral=True)
            return
            
        async def log_callback(interaction, select):
            self.log_channel_id = select.values[0]
            self.current_step = "complete"
            self._update_view()
            
            embed = discord.Embed(
                title="<:shield:1428163169846988941> Jail Setup - Complete",
                description="Review your selections and complete the setup:",
                color=0xFF6B6B
            )
            await interaction.response.edit_message(embed=embed, view=self)
        
        view = PaginatedChannelView(
            interaction.guild,
            channel_types=[discord.ChannelType.text],
            custom_callback=log_callback,
            timeout=300
        )
        
        embed = discord.Embed(
            title="<:shield:1428163169846988941> Jail Setup - Step 2",
            description="Select a channel for jail event logging:",
            color=0xFF6B6B
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def _skip_log_channel(self, interaction: discord.Interaction):
        """Skip log channel selection"""
        self.current_step = "complete"
        self._update_view()
        
        embed = discord.Embed(
            title="<:shield:1428163169846988941> Jail Setup - Complete",
            description="Review your selections and complete the setup:",
            color=0xFF6B6B
        )
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def _complete_setup(self, interaction: discord.Interaction):
        """Complete the jail setup"""
        if not self.jail_channel_id:
            await interaction.response.send_message("<:warn:1428163169846988941> Please select a jail channel first!", ephemeral=True)
            return
        
        await interaction.response.defer(thinking=True)
        
        try:
            # Save to database
            conn = sqlite3.connect('./db/jail.db')
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO jail_settings (guild_id, jail_role, jail_channel, log_channel)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET 
                jail_role = excluded.jail_role,
                jail_channel = excluded.jail_channel,
                log_channel = excluded.log_channel
            """, (str(self.guild.id), str(self.jail_role.id), self.jail_channel_id, self.log_channel_id))
            
            conn.commit()
            conn.close()
            
            jail_channel = self.guild.get_channel(int(self.jail_channel_id))
            log_channel = self.guild.get_channel(int(self.log_channel_id)) if self.log_channel_id else None
            
            # Create success embed
            embed = discord.Embed(
                title="<:check:1428163122710970508> Jail System Setup Complete",
                description="The jail system has been configured for this server.",
                color=discord.Color.green()
            )
            embed.add_field(name="Jail Role", value=self.jail_role.mention, inline=True)
            embed.add_field(name="Jail Channel", value=jail_channel.mention if jail_channel else "Error", inline=True)
            embed.add_field(name="Log Channel", value=log_channel.mention if log_channel else "Not Set", inline=True)
            
            embed.add_field(
                name="<:dotdot:1428168822887546930> Automatic Permission Setup",
                value="Select which channels jailed users can still access (like appeal channels) and click **Apply Permissions** to automatically configure all channel permissions.",
                inline=False
            )
            
            # Switch to permission setup view
            view = JailSetupView(self.guild)
            await interaction.edit_original_response(embed=embed, view=view)
            
        except Exception as e:
            error_embed = discord.Embed(
                title="<:warn:1428163169846988941> Setup Failed",
                description=f"Error during setup: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.edit_original_response(embed=error_embed, view=None)

class JailRemovalConfirmView(discord.ui.View):
    def __init__(self, guild, jail_role):
        super().__init__(timeout=30)
        self.guild = guild
        self.jail_role = jail_role
    
    @discord.ui.button(label="Confirm Removal", style=discord.ButtonStyle.danger, emoji="<:delete:1428162389907345459>")
    async def confirm_removal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True)
        
        try:
            # Remove jail role permissions from all channels
            success_count = 0
            error_count = 0
            
            if self.jail_role:
                for channel in self.guild.channels:
                    try:
                        if isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.CategoryChannel)):
                            # Remove jail role overwrite if it exists
                            if self.jail_role in channel.overwrites:
                                await channel.set_permissions(self.jail_role, overwrite=None, reason="Jail system removal")
                                success_count += 1
                    except discord.Forbidden:
                        error_count += 1
                    except Exception as e:
                        error_count += 1
                        print(f"Error removing permissions from {channel.name}: {e}")
            
            # Remove all jail settings from database
            conn = sqlite3.connect('./db/jail.db')
            cursor = conn.cursor()
            cursor.execute("DELETE FROM jail_settings WHERE guild_id = ?", (str(self.guild.id),))
            conn.commit()
            conn.close()
            
            # Create success embed
            embed = discord.Embed(
                title="<:woah:1428170830042632292> Jail System Removed",
                description="The jail system has been completely removed from this server.",
                color=discord.Color.green()
            )
            
            if self.jail_role:
                embed.add_field(
                    name="<:dotdot:1428168822887546930> Cleanup Results",
                    value=f"<:woah:1428170830042632292> Permissions removed from: {success_count} channels\n<:stop:1427471993984389180> Errors: {error_count} channels",
                    inline=True
                )
                
                embed.add_field(
                    name="<:check:1428163122710970508> Role Status",
                    value=f"{self.jail_role.mention} permissions cleared from all channels",
                    inline=True
                )
            else:
                embed.add_field(
                    name="<:file:1427471573304217651> Database",
                    value="<:woah:1428170830042632292> Configuration removed from database",
                    inline=True
                )
            
            embed.add_field(
                name="<:woah:1428170830042632292> Note",
                value="The jail role itself was not deleted. You can delete it manually if no longer needed.",
                inline=False
            )
            
            if error_count > 0:
                embed.add_field(
                    name="<:slash:1428164524372000879> Partial Success",
                    value="Some channels couldn't be modified due to permission restrictions.",
                    inline=False
                )
            
            await interaction.edit_original_response(embed=embed, view=None)
            
        except Exception as e:
            error_embed = discord.Embed(
                title="<:stop:1427471993984389180> Removal Failed",
                color=discord.Color.red(),
                description=f"Error during removal: {str(e)}"
            )
            await interaction.edit_original_response(embed=error_embed, view=None)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="<:stop:1427471993984389180>")
    async def cancel_removal(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="<:stop:1427471993984389180> Removal Cancelled",
            description="Jail system removal has been cancelled. No changes were made.",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=None)
    
    async def on_timeout(self):
        # View has timed out
        pass

class Jail(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect(DB_FILE)
        self.tz_helpers = get_timezone_helpers(bot)

    @commands.group()
    async def __JailSystem__(self, ctx: commands.Context):
        """`jail` , `unjail` , `jailsetup` , `jailconfig` , `jailhistory` , `jailcreaterole` , `jailpermissions` , `jailsr` , `jailremove` , `jailreset`"""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS jailed (
                guild_id TEXT,
                user_id TEXT,
                mod_id TEXT,
                reason TEXT,
                jailed_at TEXT,
                duration INTEGER,
                roles TEXT,
                PRIMARY KEY (guild_id, user_id)
            );
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS jail_settings (
                guild_id TEXT PRIMARY KEY,
                jail_role TEXT,
                jail_channel TEXT,
                mod_role TEXT,
                log_channel TEXT,
                allowed_channels TEXT
            );
        """)
        # Ensure roles and allowed_channels columns exist (safe migration)
        try:
            self.conn.execute("SELECT roles FROM jailed LIMIT 1;")
        except sqlite3.OperationalError:
            self.conn.execute("ALTER TABLE jailed ADD COLUMN roles TEXT;")
        
        try:
            self.conn.execute("SELECT allowed_channels FROM jail_settings LIMIT 1;")
        except sqlite3.OperationalError:
            self.conn.execute("ALTER TABLE jail_settings ADD COLUMN allowed_channels TEXT;")
        
        self.conn.commit()

        self.jail_check_loop.start()

    def cog_unload(self):
        self.jail_check_loop.cancel()
        self.conn.close()

    def get_setting(self, guild_id, field):
        cursor = self.conn.execute(f"SELECT {field} FROM jail_settings WHERE guild_id = ?", (str(guild_id),))
        row = cursor.fetchone()
        return row[0] if row else None

    def set_setting(self, guild_id, field, value):
        self.conn.execute(f"""
            INSERT INTO jail_settings (guild_id, {field})
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET {field} = excluded.{field}
        """, (str(guild_id), str(value)))
        self.conn.commit()

    def parse_duration(self, duration_str: str):
        pattern = re.compile(r'((?P<hours>\d+)h)?((?P<minutes>\d+)m)?')
        match = pattern.fullmatch(duration_str.lower())
        if not match:
            return None
        hours = int(match.group('hours') or 0)
        minutes = int(match.group('minutes') or 0)
        return (hours * 60 + minutes) * 60 if (hours or minutes) else None

    @tasks.loop(minutes=1)
    async def jail_check_loop(self):
        now = self.tz_helpers.get_utc_now()
        cursor = self.conn.execute("SELECT guild_id, user_id, duration, jailed_at, roles FROM jailed")
        for guild_id, user_id, duration, jailed_at, roles in cursor.fetchall():
            if not duration:
                continue
            jailed_time = datetime.fromisoformat(jailed_at)
            if (now - jailed_time).total_seconds() >= duration:
                guild = self.bot.get_guild(int(guild_id))
                if guild:
                    member = guild.get_member(int(user_id))
                    if member:
                        await self.unjail_member(guild, member)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        """Automatically apply jail role permissions to newly created channels"""
        try:
            # Only handle text and voice channels, not categories
            if not isinstance(channel, (discord.TextChannel, discord.VoiceChannel)):
                return
            
            # Get jail role for this guild
            jail_role_id = self.get_setting(channel.guild.id, "jail_role")
            if not jail_role_id:
                return  # No jail system configured for this guild
            
            jail_role = channel.guild.get_role(int(jail_role_id))
            if not jail_role:
                return  # Jail role not found
            
            # Get allowed channels list
            allowed_channels_str = self.get_setting(channel.guild.id, "allowed_channels")
            allowed_channels = json.loads(allowed_channels_str) if allowed_channels_str else []
            
            # For new channels, deny access by default (since they're not in the allowed list)
            # This ensures jailed users can't access newly created channels unless explicitly allowed
            try:
                await channel.set_permissions(
                    jail_role, 
                    view_channel=False,
                    read_messages=False,
                    send_messages=False,
                    reason="Auto-restriction: New channel created, jail role denied access"
                )
                print(f"[JAIL] New channel #{channel.name} - Automatically denied access to jail role")
            except discord.Forbidden:
                print(f"[JAIL] Missing permissions to set jail restrictions on new channel #{channel.name}")
            except Exception as perm_error:
                print(f"[JAIL] Error setting permissions on new channel #{channel.name}: {perm_error}")
            
        except Exception as e:
            print(f"[JAIL] Error handling new channel creation: {e}")
            # Don't raise the error to avoid disrupting other listeners

    async def unjail_member(self, guild, member):
        """Unjail a member and restore their roles"""
        jail_role_id = self.get_setting(guild.id, "jail_role")
        
        # Remove jail role
        if jail_role_id:
            jail_role = guild.get_role(int(jail_role_id))
            if jail_role in member.roles:
                await member.remove_roles(jail_role, reason="Unjailed")

        # Remove punishment from member state system
        member_state_manager.remove_punishment(guild.id, member.id, PunishmentType.JAIL)

        # Get saved roles from member state system (preferred) or fallback to old system
        saved_role_ids = member_state_manager.get_saved_roles(guild.id, member.id)
        
        if saved_role_ids:
            # Use member state system roles
            available_roles = {role.id: role for role in guild.roles}
            roles_to_restore = []
            
            for role_id in saved_role_ids:
                role = available_roles.get(role_id)
                if role and role != jail_role and role < guild.me.top_role:
                    roles_to_restore.append(role)
            
            if roles_to_restore:
                await member.add_roles(*roles_to_restore, reason="Restored roles after unjail")
                print(f"[JAIL] Restored {len(roles_to_restore)} roles from member state system")
            
            # Mark roles as restored
            member_state_manager.mark_roles_restored(guild.id, member.id)
        else:
            # Fallback to old jail database system
            cursor = self.conn.execute("SELECT roles FROM jailed WHERE guild_id = ? AND user_id = ?", (str(guild.id), str(member.id)))
            row = cursor.fetchone()
            if row and row[0]:
                role_ids = map(int, row[0].split(","))
                roles = [guild.get_role(rid) for rid in role_ids if guild.get_role(rid)]
                if roles:
                    await member.add_roles(*roles, reason="Restored previous roles after jail (legacy)")
                    print(f"[JAIL] Restored {len(roles)} roles from legacy jail system")

        # Clean up old jail database record
        self.conn.execute("DELETE FROM jailed WHERE guild_id = ? AND user_id = ?", (str(guild.id), str(member.id)))
        self.conn.commit()

        try:
            await member.send(f"🔓 You have been unjailed in **{guild.name}**.")
        except:
            pass

        log_channel_id = self.get_setting(guild.id, "log_channel")
        if log_channel_id:
            log_channel = guild.get_channel(int(log_channel_id))
            if log_channel:
                embed = discord.Embed(title="🔓 Member Unjailed", color=discord.Color.green())
                embed.add_field(name="User", value=member.mention)
                embed.timestamp = self.tz_helpers.get_utc_now()
                embed.set_footer(text=f"{guild.name}")
                await log_channel.send(embed=embed)

    @commands.command(name="jail", help="Jail a member (restrict their permissions)", usage="jail <member> [duration] [reason]")
    @require_custom_permissions('manage_roles')
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    async def jail(self, ctx, member: discord.Member, duration: Optional[str] = None, *, reason: Optional[str] = None):
        """
        Jail a member (restrict their permissions).
        Usage: jail <member> [duration] [reason]
        """
        reason = reason or "No reason provided"
        jail_role_id = self.get_setting(ctx.guild.id, "jail_role")
        jail_channel_id = self.get_setting(ctx.guild.id, "jail_channel")
        log_channel_id = self.get_setting(ctx.guild.id, "log_channel")

        if not jail_role_id or not jail_channel_id:
            return await ctx.send("⚠️ Jail system not fully configured.")

        jail_role = ctx.guild.get_role(int(jail_role_id))
        if not jail_role:
            return await ctx.send("⚠️ Jail role does not exist.")

        # Parse duration for member state system
        duration_secs = self.parse_duration(duration) if duration else None
        duration_timedelta = timedelta(seconds=duration_secs) if duration_secs else None
        
        jailed_at = self.tz_helpers.get_utc_now().isoformat()
        roles_str = ",".join(str(r.id) for r in member.roles if r != ctx.guild.default_role)

        # Save current roles to member state system before jailing
        current_roles = [role for role in member.roles if role != ctx.guild.default_role and role != jail_role]
        if current_roles:
            member_state_manager.save_member_roles(ctx.guild.id, member.id, current_roles)
            print(f"[JAIL] Saved {len(current_roles)} roles before jailing {member.display_name}")

        # Add punishment to member state system
        punishment_id = member_state_manager.add_punishment(
            ctx.guild.id, member.id, PunishmentType.JAIL, 
            ctx.author.id, reason, duration_timedelta,
            additional_data={
                'jail_role_id': jail_role.id,
                'jail_channel_id': int(jail_channel_id) if jail_channel_id else None
            }
        )

        # Keep existing jail database record for backward compatibility
        self.conn.execute("DELETE FROM jailed WHERE guild_id = ? AND user_id = ?", (str(ctx.guild.id), str(member.id)))
        self.conn.execute("""
            INSERT INTO jailed (guild_id, user_id, mod_id, reason, jailed_at, duration, roles)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (str(ctx.guild.id), str(member.id), str(ctx.author.id), reason, jailed_at, duration_secs, roles_str))
        self.conn.commit()

        try:
            await member.edit(roles=[jail_role], reason="Jailed")
        except discord.Forbidden:
            return await ctx.send("❌ I don't have permission to change roles.")

        jail_channel = ctx.guild.get_channel(int(jail_channel_id))
        if jail_channel:
            await jail_channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True)

        try:
            await member.send(f"🔒 You were jailed in **{ctx.guild.name}**.\n📝 Reason: {reason}\n⏰ Duration: {duration or 'Permanent'}")
        except:
            pass

        await ctx.send(f"🔒 {member.mention} has been jailed {'for ' + duration if duration else 'permanently'}.")

        if log_channel_id:
            log_channel = ctx.guild.get_channel(int(log_channel_id))
            if log_channel:
                embed = discord.Embed(title="🔒 Member Jailed", color=discord.Color.red())
                embed.add_field(name="User", value=member.mention, inline=False)
                embed.add_field(name="Moderator", value=ctx.author.mention, inline=False)
                embed.add_field(name="Reason", value=reason, inline=False)
                embed.add_field(name="Duration", value=duration or "Permanent", inline=False)
                embed.timestamp = self.tz_helpers.get_utc_now()
                await log_channel.send(embed=embed)

    @commands.command(name="unjail", help="Release a member from jail", usage="unjail <member>")
    @require_custom_permissions('manage_roles')
    @commands.has_permissions(manage_roles=True)
    async def unjail(self, ctx, member: discord.Member):
        await self.unjail_member(ctx.guild, member)
        await ctx.send(f"✅ {member.mention} has been unjailed.")

    @commands.command(name="jailhistory", help="View a member's jail history", usage="jailhistory <member>")
    async def jailhistory(self, ctx, member: discord.Member):
        cursor = self.conn.execute("""
            SELECT reason, jailed_at, duration, mod_id FROM jailed
            WHERE guild_id = ? AND user_id = ?
        """, (str(ctx.guild.id), str(member.id)))
        row = cursor.fetchone()
        if row:
            reason, jailed_at, duration, mod_id = row
            mod = ctx.guild.get_member(int(mod_id))
            jailed_time = datetime.fromisoformat(jailed_at)
            embed = discord.Embed(title="📄 Jail Record", color=discord.Color.orange())
            embed.add_field(name="User", value=member.mention)
            embed.add_field(name="Reason", value=reason)
            
            # Format jailed time in user's timezone
            jailed_time_formatted = await self.tz_helpers.format_datetime_for_user_custom(
                jailed_time, ctx.author, "%Y-%m-%d %H:%M:%S %Z"
            )
            embed.add_field(name="Jailed At", value=jailed_time_formatted)
            embed.add_field(name="Duration", value=f"{duration // 60} minutes" if duration else "Permanent")
            embed.add_field(name="Moderator", value=mod.mention if mod else "Unknown")
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❌ {member.mention} has no jail history.")

    @commands.command(name="jailsetup", help="Setup the jail system with role and channels", usage="jailsetup <jail_role>")
    @commands.has_permissions(administrator=True)
    async def jail_setup(self, ctx, jail_role: discord.Role):
        """
        Setup the jail system for this server using an existing role.
        Usage: jailsetup <jail_role>
        
        The jail_role should be a role that exists on your server.
        Create the role first if needed, then use it in this command.
        After providing the role, you'll be prompted to select channels.
        """
        # Create initial setup embed
        embed = discord.Embed(
            title="<:dotdot:1428168822887546930> Jail System Setup",
            description=f"Setting up jail system with role: {jail_role.mention}",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="<:check:1428163122710970508> Step 1: Role Selected",
            value=f"Using {jail_role.mention} as the jail role.",
            inline=False
        )
        embed.add_field(
            name="<:dotdot:1428168822887546930> Step 2: Select Channels",
            value="• Select a **jail channel** where jailed users will be sent\n• Optionally select a **log channel** for jail actions\n• Click **Complete Setup** when done",
            inline=False
        )
        
        # Add initial setup view
        view = JailInitialSetupView(ctx.guild, jail_role)
        await ctx.send(embed=embed, view=view)

    @commands.command(name="jailcreaterole")
    @commands.has_permissions(administrator=True)
    async def jail_create_role(self, ctx, *, role_name: str = "Jailed"):
        """
        Create a new role for the jail system.
        Usage: jailcreaterole [role_name]
        
        This creates a role with basic restrictions that can be used with jailsetup.
        """
        try:
            # Create the jail role with basic permissions
            jail_role = await ctx.guild.create_role(
                name=role_name,
                color=discord.Color.dark_red(),
                hoist=False,
                mentionable=False,
                reason=f"Jail role created by {ctx.author}",
                permissions=discord.Permissions(
                    # Basic permissions - very restricted
                    view_channel=False,  # Will be overridden per channel
                    send_messages=False,
                    send_messages_in_threads=False,
                    create_public_threads=False,
                    create_private_threads=False,
                    embed_links=False,
                    attach_files=False,
                    add_reactions=False,
                    use_external_emojis=False,
                    use_external_stickers=False,
                    mention_everyone=False,
                    manage_messages=False,
                    read_message_history=True,  # Can read old messages
                    connect=False,  # Can't join voice channels
                    speak=False,
                    stream=False,
                    use_voice_activation=False,
                    priority_speaker=False
                )
            )
            
            embed = discord.Embed(
                title="<:check:1428163122710970508> Jail Role Created",
                description=f"Successfully created jail role: {jail_role.mention}",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="<:dotdot:1428168822887546930> Role Settings",
                value=f"• **Name**: {role_name}\n• **Color**: Dark Red\n• **Permissions**: Heavily restricted\n• **Position**: Bottom of role list",
                inline=False
            )
            
            embed.add_field(
                name="<:right:1427471506287362068> Next Steps",
                value=f"Use `{ctx.prefix}jailsetup {jail_role.mention} #jail-channel` to complete the jail system setup.",
                inline=False
            )
            
            embed.add_field(
                name="<:sleep_dot:1427471567838777347> Tips",
                value="• Consider moving this role higher in the role hierarchy\n• Make sure it's below moderator roles\n• The role position affects permission overrides",
                inline=False
            )
            
            await ctx.send(embed=embed)
            
        except discord.Forbidden:
            embed = discord.Embed(
                title="<:stop:1427471993984389180> Permission Error",
                description="I don't have permission to create roles in this server.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="<:stop:1427471993984389180> Role Creation Failed",
                description=f"Failed to create jail role: {str(e)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @commands.command(name="jailconfig")
    @commands.has_permissions(manage_roles=True)
    async def jail_config(self, ctx):
        """View current jail system configuration."""
        jail_role_id = self.get_setting(ctx.guild.id, "jail_role")
        jail_channel_id = self.get_setting(ctx.guild.id, "jail_channel")
        log_channel_id = self.get_setting(ctx.guild.id, "log_channel")
        
        if not jail_role_id and not jail_channel_id:
            embed = discord.Embed(
                title="<:warning~1:1428163138322301018> Jail System Not Configured",
                description=f"Use `{ctx.prefix}jailsetup <jail_role> <jail_channel> [log_channel]` to set up the jail system.",
                color=discord.Color.orange()
            )
            return await ctx.send(embed=embed)
        
        jail_role = ctx.guild.get_role(int(jail_role_id)) if jail_role_id else None
        jail_channel = ctx.guild.get_channel(int(jail_channel_id)) if jail_channel_id else None
        log_channel = ctx.guild.get_channel(int(log_channel_id)) if log_channel_id else None
        
        embed = discord.Embed(
            title="<:mod:1427471611262537830> Jail System Configuration",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Jail Role", 
            value=jail_role.mention if jail_role else "<:woah:1428170830042632292> Role not found", 
            inline=True
        )
        embed.add_field(
            name="Jail Channel", 
            value=jail_channel.mention if jail_channel else "<:woah:1428170830042632292> Channel not found", 
            inline=True
        )
        embed.add_field(
            name="Log Channel", 
            value=log_channel.mention if log_channel else "<:woah:1428170830042632292> Not set", 
            inline=True
        )
        
        # Check for allowed channels
        allowed_channels_data = self.get_setting(ctx.guild.id, "allowed_channels")
        if allowed_channels_data:
            try:
                allowed_channels = json.loads(allowed_channels_data)
                channel_mentions = []
                for channel_id in allowed_channels:
                    channel = ctx.guild.get_channel(int(channel_id))
                    if channel:
                        channel_mentions.append(channel.mention)
                
                embed.add_field(
                    name="Allowed Channels", 
                    value="\n".join(channel_mentions) if channel_mentions else "None configured",
                    inline=False
                )
            except:
                embed.add_field(name="Allowed Channels", value="<:stop:1427471993984389180> Error reading data", inline=False)
        else:
            embed.add_field(name="Allowed Channels", value="Not configured", inline=False)
        
        # Add status indicators
        status = "<:check:1428163122710970508> Ready" if jail_role and jail_channel else "<:woah:1428170830042632292> Incomplete Setup"
        embed.add_field(name="Status", value=status, inline=False)
        
        if not jail_role or not jail_channel:
            embed.add_field(
                name="How to Fix",
                value=f"Run `{ctx.prefix}jailsetup <jail_role> <jail_channel> [log_channel]` to complete setup.",
                inline=False
            )
        
        await ctx.send(embed=embed)

    @commands.command(name="jailpermissions")
    @commands.has_permissions(administrator=True)
    async def jail_permissions(self, ctx):
        """
        Configure channel permissions for the jail system.
        Allows you to select which channels jailed users can access.
        """
        # Check if jail system is set up
        jail_role_id = self.get_setting(ctx.guild.id, "jail_role")
        if not jail_role_id:
            embed = discord.Embed(
                title="<:woah:1428170830042632292> Jail System Not Configured",
                description=f"Use `{ctx.prefix}jailsetup <jail_role> <jail_channel> [log_channel]` to set up the jail system first.",
                color=discord.Color.orange()
            )
            return await ctx.send(embed=embed)
        
        # Get existing allowed channels
        allowed_channels_data = self.get_setting(ctx.guild.id, "allowed_channels")
        existing_channels = json.loads(allowed_channels_data) if allowed_channels_data else []
        
        # Create permission setup embed
        embed = discord.Embed(
            title="<:mod:1427471611262537830> Jail Permission Setup",
            description="Select which channels jailed users should be able to access.",
            color=0xFF6B6B
        )
        embed.add_field(
            name="<:ar:1427471532841631855> How it works",
            value="• Select channels from the dropdown (like appeal channels)\n"
                  "• Click **Apply Permissions** to automatically configure all channels\n"
                  "• Jailed users will only see selected channels + jail channel",
            inline=False
        )
        
        if existing_channels:
            channel_list = []
            for channel_id in existing_channels:
                channel = ctx.guild.get_channel(int(channel_id))
                if channel:
                    channel_list.append(f"• #{channel.name}")
            
            embed.add_field(
                name="Currently Configured",
                value="\n".join(channel_list) if channel_list else "None",
                inline=False
            )
        
        # Add permission setup view
        view = JailSetupView(ctx.guild, existing_channels)
        await ctx.send(embed=embed, view=view)

    @commands.command(name="jailsr", aliases=["jailremove", "jailreset"])
    @commands.has_permissions(administrator=True)
    async def jail_setup_remove(self, ctx):
        """
        Completely remove jail system setup and clear all channel permissions.
        Usage: jailsr
        """
        # Get current jail role before removing
        jail_role_id = self.get_setting(ctx.guild.id, "jail_role")
        
        if not jail_role_id:
            embed = discord.Embed(
                title="<:woah:1428170830042632292> No Jail System Found",
                description="There is no jail system configured for this server.",
                color=discord.Color.orange()
            )
            return await ctx.send(embed=embed)
        
        jail_role = ctx.guild.get_role(int(jail_role_id))
        
        # Send confirmation message
        confirm_embed = discord.Embed(
            title="<:delete:1428162389907345459> Remove Jail System Setup",
            description="This will completely remove the jail system configuration and clear all channel permissions for the jail role.",
            color=discord.Color.red()
        )
        
        if jail_role:
            confirm_embed.add_field(
                name="<:woah:1428170830042632292> Warning",
                value=f"This will remove {jail_role.mention} permissions from **ALL** channels in this server and delete the jail system configuration.",
                inline=False
            )
        else:
            confirm_embed.add_field(
                name="<:woah:1428170830042632292> Warning", 
                value="This will delete the jail system configuration. The jail role was not found (may have been deleted).",
                inline=False
            )
        
        confirm_embed.add_field(
            name="<:file:1427471573304217651> What will be removed:",
            value="• Jail system database configuration\n• All channel permission overwrites for jail role\n• Allowed channels configuration\n• All jail-related settings",
            inline=False
        )
        
        # Add confirmation buttons
        view = JailRemovalConfirmView(ctx.guild, jail_role)
        await ctx.send(embed=confirm_embed, view=view)

    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()

async def setup(bot):
    await bot.add_cog(Jail(bot))
