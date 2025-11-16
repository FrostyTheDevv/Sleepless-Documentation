from utils.error_helpers import StandardErrorHandler
"""
Comprehensive Ping on Join System
Pings new members in selected channels with customizable messages and duration
"""

import discord
from discord.ext import commands
from discord.ui import Button, View, Select, Modal, TextInput
import aiosqlite
import asyncio
import json
import re
from datetime import datetime, timedelta
from typing import Optional, List
import time
from utils.Tools import blacklist_check, ignore_check
from utils.dynamic_dropdowns import PaginatedChannelView

# Database path
DB_PATH = "db/pingonjoin.db"

class POJMultiChannelSelect(discord.ui.Select):
    """Multi-select channel dropdown for POJ system"""
    
    def __init__(self, guild, all_channels, page=0, *, placeholder="Select channels...", custom_callback=None, view_parent=None):
        self.guild = guild
        self.all_channels = all_channels
        self.page = page
        self.custom_callback = custom_callback
        self.view_parent = view_parent
        self.channels_per_page = 25
        
        # Calculate page info
        start_idx = page * self.channels_per_page
        end_idx = min(start_idx + self.channels_per_page, len(all_channels))
        page_channels = all_channels[start_idx:end_idx]
        
        # Create options for this page
        options = []
        for channel in page_channels:
            label = f"#{channel.name}" if hasattr(channel, 'name') else str(channel)
            if len(label) > 25:
                label = label[:22] + "..."
            
            description = f"ID: {channel.id}"
            if hasattr(channel, 'category') and channel.category:
                description = f"Category: {channel.category.name}"
            if len(description) > 100:
                description = description[:97] + "..."
            
            options.append(discord.SelectOption(
                label=label,
                description=description,
                value=str(channel.id)
            ))
        
        # Handle empty page
        if not options:
            options = [discord.SelectOption(
                label="No channels on this page",
                description="No channels available",
                value="none"
            )]
        
        # Update placeholder with page info
        total_pages = max(1, len(all_channels) // self.channels_per_page + (1 if len(all_channels) % self.channels_per_page else 0))
        if total_pages > 1:
            placeholder = f"{placeholder} (Page {page + 1}/{total_pages})"
        
        # Allow multiple selections (up to 10)
        max_selectable = min(10, len([opt for opt in options if opt.value != "none"]))
        
        super().__init__(
            placeholder=placeholder,
            min_values=0,
            max_values=max_selectable if max_selectable > 0 else 1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle the multi-selection callback"""
        try:
            if self.custom_callback:
                await self.custom_callback(interaction, self)
            else:
                # Default behavior for multiple channels
                selected_channels = []
                for value in self.values:
                    if value != "none":
                        channel = self.guild.get_channel(int(value))
                        if channel:
                            selected_channels.append(channel.mention)
                
                if selected_channels:
                    await interaction.response.send_message(
                        f"✅ Selected: {', '.join(selected_channels)}",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        "❌ No valid channels selected",
                        ephemeral=True
                    )
                    
        except Exception as e:
            print(f"[ERROR] POJ Multi-channel dropdown error: {e}")
            try:
                await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
            except:
                pass

class POJMultiChannelView(discord.ui.View):
    """Multi-select channel view specifically for POJ system"""
    
    def __init__(self, guild, *, channel_types=None, exclude_channels=None, custom_callback=None, timeout=300):
        super().__init__(timeout=timeout)
        
        self.guild = guild
        self.channel_types = channel_types or [discord.ChannelType.text]
        self.exclude_channels = [name.lower() for name in (exclude_channels or [])]
        self.custom_callback = custom_callback
        self.current_page = 0
        
        # Get all eligible channels
        self.all_channels = self._get_channels()
        self.total_pages = max(1, len(self.all_channels) // 25 + (1 if len(self.all_channels) % 25 else 0))
        
        print(f"[DEBUG] POJMultiChannelView: Found {len(self.all_channels)} channels, {self.total_pages} pages")
        
        # Set up the view
        self._update_view()
    
    def _get_channels(self):
        """Get all channels that match the criteria"""
        channels = []
        
        try:
            print(f"[DEBUG] POJMultiChannelView._get_channels for guild: {self.guild.name}")
            print(f"[DEBUG] Looking for channel types: {self.channel_types}")
            print(f"[DEBUG] Excluding channels: {self.exclude_channels}")
            
            all_guild_channels = list(self.guild.channels)
            
            # First, let's find updates-sleepless specifically
            updates_sleepless = None
            for channel in all_guild_channels:
                if "updates-sleepless" in channel.name.lower():
                    updates_sleepless = channel
                    print(f"[DEBUG] 🎯 Found updates-sleepless: #{channel.name} (Type: {channel.type})")
                    break
            
            if not updates_sleepless:
                print(f"[DEBUG] ❌ updates-sleepless not found in guild channels")
            
            # Now process all channels
            for channel in all_guild_channels:
                # Log updates-sleepless specifically
                if "updates-sleepless" in channel.name.lower():
                    print(f"[DEBUG] Processing updates-sleepless: #{channel.name}")
                    print(f"  - Channel type: {channel.type}")
                    print(f"  - Type in search list: {channel.type in self.channel_types}")
                    print(f"  - Channel name lowercase: '{channel.name.lower()}'")
                    print(f"  - Name in exclude list: {channel.name.lower() in self.exclude_channels}")
                
                # Apply filters
                if channel.type not in self.channel_types:
                    if "updates-sleepless" in channel.name.lower():
                        print(f"  - ❌ EXCLUDED: Type {channel.type} not in {self.channel_types}")
                    continue
                    
                if channel.name.lower() in self.exclude_channels:
                    if "updates-sleepless" in channel.name.lower():
                        print(f"  - ❌ EXCLUDED: Name in exclude list")
                    continue
                
                # Add to results
                channels.append(channel)
                if "updates-sleepless" in channel.name.lower():
                    print(f"  - ✅ INCLUDED in final list!")
            
            # Sort by position and name
            channels.sort(key=lambda c: (c.position, c.name.lower()))
            
            print(f"[DEBUG] Final filtered list: {len(channels)} eligible channels")
            
            # List all included channels
            print(f"[DEBUG] Included channels:")
            for i, ch in enumerate(channels):
                marker = " 🎯" if "updates-sleepless" in ch.name.lower() else ""
                print(f"  {i+1}. #{ch.name} (Type: {ch.type}){marker}")
            
        except Exception as e:
            print(f"[ERROR] Could not get channels: {e}")
            import traceback
            traceback.print_exc()
        
        return channels
    
    def _update_view(self):
        """Update the view with current page"""
        # Clear all items
        self.clear_items()
        
        if not self.all_channels:
            # No channels found
            select = discord.ui.Select(
                placeholder="No channels available",
                options=[discord.SelectOption(label="No channels", value="none")],
                disabled=True
            )
            self.add_item(select)
            return
        
        # Add the multi-channel select for current page
        select = POJMultiChannelSelect(
            self.guild,
            self.all_channels,
            self.current_page,
            placeholder="Select channels (up to 10)...",
            custom_callback=self.custom_callback,
            view_parent=self
        )
        self.add_item(select)
        
        # Add navigation buttons if needed
        if self.total_pages > 1:
            # Previous button
            prev_button = discord.ui.Button(
                label="◀️ Previous",
                style=discord.ButtonStyle.secondary,
                disabled=(self.current_page == 0)
            )
            prev_button.callback = self._prev_page
            self.add_item(prev_button)
            
            # Page info button
            page_button = discord.ui.Button(
                label=f"Page {self.current_page + 1}/{self.total_pages}",
                style=discord.ButtonStyle.primary,
                disabled=True
            )
            self.add_item(page_button)
            
            # Next button
            next_button = discord.ui.Button(
                label="Next ▶️",
                style=discord.ButtonStyle.secondary,
                disabled=(self.current_page >= self.total_pages - 1)
            )
            next_button.callback = self._next_page
            self.add_item(next_button)
    
    async def _prev_page(self, interaction: discord.Interaction):
        """Go to previous page"""
        if self.current_page > 0:
            self.current_page -= 1
            self._update_view()
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.defer()
    
    async def _next_page(self, interaction: discord.Interaction):
        """Go to next page"""
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self._update_view()
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.defer()

# Custom feast emojis
EMOJIS = {
    "success": "<:feast_tick:1400143469892210753>",
    "error": "<:feast_cross:1400143488695144609>",
    "warning": "<:feast_warning:1400143131990560830>",
    "ping": "<:feast_piche:1400142845402284102>",
    "time": "<:feast_age:1400142030205878274>",
    "channel": "<:feast_next:1400141978095583322>",
    "member": "<:feast_mod:1400136216497623130>",
    "settings": "<:Feast_Utility:1400135926298185769>",
    "edit": "<:feast_plus:1400142875483836547>",
    "delete": "<:feast_delete:1400140670659989524>",
    "add": "<:feast_plus:1400142875483836547>",
    "list": "<:feast_prev:1400142835914637524>",
    "toggle": "<:feast_security:1400133995349676093>"
}

def get_duration_seconds(duration_str: str) -> int:
    """Convert duration string to seconds"""
    duration_str = duration_str.lower().strip()
    
    # Parse duration (e.g., "30s", "5m", "2h", "1d")
    duration_map = {
        's': 1, 'sec': 1, 'second': 1, 'seconds': 1,
        'm': 60, 'min': 60, 'minute': 60, 'minutes': 60,
        'h': 3600, 'hour': 3600, 'hours': 3600,
        'd': 86400, 'day': 86400, 'days': 86400
    }
    
    for unit, multiplier in duration_map.items():
        if duration_str.endswith(unit):
            try:
                number = int(duration_str[:-len(unit)])
                return number * multiplier
            except ValueError:
                continue
    
    # Try just a number (assume seconds)
    try:
        return int(duration_str)
    except ValueError:
        return 0

def format_duration(seconds: int) -> str:
    """Format seconds into human readable duration"""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    elif seconds < 86400:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"
    else:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        return f"{days}d {hours}h"

class PingDurationModal(Modal):
    """Modal for setting ping duration"""
    
    def __init__(self, setup_id: int):
        super().__init__(title="Set Ping Duration")
        self.setup_id = setup_id
        
        self.duration_input = TextInput(
            label="Ping Duration",
            placeholder="Enter duration (e.g., 30s, 5m, 2h, 1d)",
            required=True,
            max_length=10
        )
        self.add_item(self.duration_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        duration_str = self.duration_input.value
        duration_seconds = get_duration_seconds(duration_str)
        
        if duration_seconds == 0:
            await interaction.response.send_message(
                f"{EMOJIS['error']} Invalid duration format! Use formats like: 30s, 5m, 2h, 1d",
                ephemeral=True
            )
            return
        
        if duration_seconds > 86400 * 7:  # 7 days max
            await interaction.response.send_message(
                f"{EMOJIS['error']} Duration cannot exceed 7 days!",
                ephemeral=True
            )
            return
        
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE pingonjoin_setups SET ping_duration = ? WHERE id = ?",
                (duration_seconds, self.setup_id)
            )
            await db.commit()
        
        formatted_duration = format_duration(duration_seconds)
        await interaction.response.send_message(
            f"{EMOJIS['success']} Ping duration set to **{formatted_duration}**",
            ephemeral=True
        )

class PingMessageModal(Modal):
    """Modal for setting ping message"""
    
    def __init__(self, setup_id: int, current_message: str = ""):
        super().__init__(title="Set Ping Message")
        self.setup_id = setup_id
        
        self.message_input = TextInput(
            label="Ping Message",
            placeholder="Enter message to show with ping (use {user} for mention)",
            required=True,
            max_length=500,
            style=discord.TextStyle.paragraph,
            default=current_message
        )
        self.add_item(self.message_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        message = self.message_input.value.strip()
        
        if not message:
            await interaction.response.send_message(
                f"{EMOJIS['error']} Message cannot be empty!",
                ephemeral=True
            )
            return
        
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE pingonjoin_setups SET ping_message = ? WHERE id = ?",
                (message, self.setup_id)
            )
            await db.commit()
        
        await interaction.response.send_message(
            f"{EMOJIS['success']} Ping message updated!",
            ephemeral=True
        )

class PingSetupView(View):
    """Main setup view for ping on join configuration"""
    
    def __init__(self, author_id: int, setup_data: dict):
        super().__init__(timeout=300)
        self.author_id = author_id
        self.setup_data = setup_data
    
    @discord.ui.button(label="Set Channels", emoji=EMOJIS.get('channel', '📺'), style=discord.ButtonStyle.primary)
    async def set_channels(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("You cannot interact with this setup.", ephemeral=True)
            return
        
        async def channel_callback(channel_interaction, select):
            if not interaction.guild:
                return
            channel_id = int(select.values[0])
            channel = interaction.guild.get_channel(channel_id)
            
            if not channel:
                await channel_interaction.response.send_message(
                    f"{EMOJIS['error']} Channel not found!",
                    ephemeral=True
                )
                return
                
            # Check if channel is already added
            async with aiosqlite.connect(DB_PATH) as db:
                cursor = await db.execute(
                    "SELECT id FROM pingonjoin_channels WHERE setup_id = ? AND channel_id = ?",
                    (self.setup_data['id'], channel_id)
                )
                if await cursor.fetchone():
                    await channel_interaction.response.send_message(
                        f"{EMOJIS['warning']} {channel.mention} is already added to this setup!",
                        ephemeral=True
                    )
                    return
                
                # Add channel
                await db.execute(
                    "INSERT INTO pingonjoin_channels (setup_id, channel_id) VALUES (?, ?)",
                    (self.setup_data['id'], channel_id)
                )
                await db.commit()
            
            await channel_interaction.response.send_message(
                f"{EMOJIS['success']} Added {channel.mention} to ping channels!",
                ephemeral=True
            )
        
        if not interaction.guild:
            await interaction.response.send_message("Guild not found!", ephemeral=True)
            return
            
        view = PaginatedChannelView(
            interaction.guild,
            channel_types=[discord.ChannelType.text, discord.ChannelType.news, discord.ChannelType.forum],
            exclude_channels=[],
            custom_callback=channel_callback,
            timeout=60
        )
        
        await interaction.response.send_message(
            f"{EMOJIS['channel']} **Select Channel to Add:**",
            view=view,
            ephemeral=True
        )
    
    @discord.ui.button(label="Set Duration", emoji=EMOJIS.get('time', '⏰'), style=discord.ButtonStyle.secondary)
    async def set_duration(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("You cannot interact with this setup.", ephemeral=True)
            return
        
        modal = PingDurationModal(self.setup_data['id'])
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Set Message", emoji=EMOJIS.get('edit', '✏️'), style=discord.ButtonStyle.secondary)
    async def set_message(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("You cannot interact with this setup.", ephemeral=True)
            return
        
        modal = PingMessageModal(self.setup_data['id'], self.setup_data['ping_message'])
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Toggle Active", emoji=EMOJIS.get('toggle', '🔄'), style=discord.ButtonStyle.success)
    async def toggle_active(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("You cannot interact with this setup.", ephemeral=True)
            return
        
        new_status = not self.setup_data['is_active']
        
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE pingonjoin_setups SET is_active = ? WHERE id = ?",
                (new_status, self.setup_data['id'])
            )
            await db.commit()
        
        self.setup_data['is_active'] = new_status
        status_text = "enabled" if new_status else "disabled"
        status_emoji = EMOJIS['success'] if new_status else EMOJIS['warning']
        
        await interaction.response.send_message(
            f"{status_emoji} Ping on join **{status_text}**!",
            ephemeral=True
        )
    
    @discord.ui.button(label="View Config", emoji=EMOJIS.get('list', '📋'), style=discord.ButtonStyle.secondary, row=1)
    async def view_config(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("You cannot interact with this setup.", ephemeral=True)
            return
        
        # Get current setup data
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT * FROM pingonjoin_setups WHERE id = ?",
                (self.setup_data['id'],)
            )
            setup = await cursor.fetchone()
            
            cursor = await db.execute(
                "SELECT channel_id FROM pingonjoin_channels WHERE setup_id = ?",
                (self.setup_data['id'],)
            )
            channels = list(await cursor.fetchall())
        
        if not setup:
            await interaction.response.send_message("Setup not found!", ephemeral=True)
            return
            
        embed = discord.Embed(
            title=f"{EMOJIS['settings']} Ping on Join Configuration",
            color=0x00ff00 if setup[3] else 0xff9900  # is_active
        )
        
        # Status
        status = "🟢 Active" if setup[3] else "🟡 Inactive"
        embed.add_field(name="Status", value=status, inline=True)
        
        # Duration
        duration_text = format_duration(setup[4]) if setup[4] else "Not set"
        embed.add_field(name=f"{EMOJIS['time']} Duration", value=duration_text, inline=True)
        
        # Message
        message_preview = (setup[5][:50] + "...") if len(setup[5]) > 50 else setup[5]
        embed.add_field(name=f"{EMOJIS['edit']} Message", value=f"`{message_preview}`", inline=False)
        
        # Channels
        if channels and interaction.guild:
            channel_mentions = []
            for (channel_id,) in channels:
                channel = interaction.guild.get_channel(channel_id)
                if channel:
                    channel_mentions.append(channel.mention)
            
            channels_text = "\n".join(channel_mentions[:10])
            if len(channels) > 10:
                channels_text += f"\n... and {len(channels) - 10} more"
            
            embed.add_field(
                name=f"{EMOJIS['channel']} Ping Channels ({len(channels)})",
                value=channels_text,
                inline=False
            )
        else:
            embed.add_field(
                name=f"{EMOJIS['channel']} Ping Channels",
                value="No channels set",
                inline=False
            )
        
        embed.set_footer(text=f"Setup ID: {setup[0]} | Created: {setup[6]}")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Remove Channels", emoji=EMOJIS.get('delete', '🗑️'), style=discord.ButtonStyle.danger, row=1)
    async def remove_channels(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("You cannot interact with this setup.", ephemeral=True)
            return
        
        # Get channels for this setup
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT channel_id FROM pingonjoin_channels WHERE setup_id = ?",
                (self.setup_data['id'],)
            )
            channels = list(await cursor.fetchall())
        
        if not channels:
            await interaction.response.send_message(
                f"{EMOJIS['warning']} No channels to remove!",
                ephemeral=True
            )
            return
        
        if not interaction.guild:
            await interaction.response.send_message("Guild not found!", ephemeral=True)
            return
            
        # Create channel select for removal
        options = []
        for (channel_id,) in channels:
            channel = interaction.guild.get_channel(channel_id)
            if channel:
                options.append(discord.SelectOption(
                    label=f"#{channel.name}",
                    description=f"Remove {channel.name} from ping list",
                    value=str(channel_id)
                ))
        
        if not options:
            await interaction.response.send_message(
                f"{EMOJIS['warning']} No valid channels to remove!",
                ephemeral=True
            )
            return
        
        select = Select(placeholder="Select channel to remove...", options=options[:25])
        
        async def remove_callback(interaction):
            channel_id = int(select.values[0])
            if not interaction.guild:
                await interaction.response.send_message("Guild not found!", ephemeral=True)
                return
                
            channel = interaction.guild.get_channel(channel_id)
            if not channel:
                await interaction.response.send_message("Channel not found!", ephemeral=True)
                return
            
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "DELETE FROM pingonjoin_channels WHERE setup_id = ? AND channel_id = ?",
                    (self.setup_data['id'], channel_id)
                )
                await db.commit()
            
            await interaction.response.send_message(
                f"{EMOJIS['success']} Removed {channel.mention} from ping channels!",
                ephemeral=True
            )
        
        select.callback = remove_callback
        view = View()
        view.add_item(select)
        
        await interaction.response.send_message(
            f"{EMOJIS['delete']} **Select Channel to Remove:**",
            view=view,
            ephemeral=True
        )

class SetupWizardView(View):
    """Simple guided setup wizard for ping on join"""
    
    def __init__(self, author_id: int, guild_id: int):
        super().__init__(timeout=300)
        self.author_id = author_id
        self.guild_id = guild_id
        self.setup_data = {
            'name': None,
            'duration': 60,  # Default 60 seconds
            'message': 'Welcome {user}! 👋',  # Default message
            'channels': []
        }
        
    @discord.ui.button(label="Start Setup", emoji=EMOJIS.get('settings', '⚙️'), style=discord.ButtonStyle.primary)
    async def start_setup(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("You cannot start this setup.", ephemeral=True)
            return
        
        # Step 1: Get setup name
        modal = SetupNameModal(self.setup_data)
        await interaction.response.send_modal(modal)

class SetupNameModal(Modal):
    """Modal to get setup name"""
    
    def __init__(self, setup_data: dict):
        super().__init__(title="Step 1: Setup Name")
        self.setup_data = setup_data
        
        self.name_input = TextInput(
            label="Setup Name",
            placeholder="e.g., Welcome System, New Members, etc.",
            required=True,
            max_length=50,
            default=f"Welcome Setup"
        )
        self.add_item(self.name_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        self.setup_data['name'] = self.name_input.value
        
        # Step 2: Duration setup
        embed = discord.Embed(
            title=f"{EMOJIS['time']} Step 2: Ping Duration",
            description="How long should the ping message stay visible?",
            color=0x006fb9
        )
        embed.add_field(
            name="Current Setting",
            value=f"{format_duration(self.setup_data['duration'])}",
            inline=True
        )
        embed.add_field(
            name="Examples",
            value="30s, 5m, 2h, 1d",
            inline=True
        )
        
        view = SetupDurationView(self.setup_data)
        await interaction.response.edit_message(embed=embed, view=view)

class SetupDurationView(View):
    """View for setting duration"""
    
    def __init__(self, setup_data: dict):
        super().__init__(timeout=300)
        self.setup_data = setup_data
    
    @discord.ui.button(label="Change Duration", emoji=EMOJIS.get('edit', '✏️'), style=discord.ButtonStyle.secondary)
    async def change_duration(self, interaction: discord.Interaction, button: Button):
        modal = SetupDurationModal(self.setup_data)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Keep Default (60s)", emoji=EMOJIS.get('success', '✅'), style=discord.ButtonStyle.success)
    async def keep_default(self, interaction: discord.Interaction, button: Button):
        # Move to step 3: Message
        embed = discord.Embed(
            title=f"{EMOJIS['edit']} Step 3: Welcome Message",
            description="What message should be shown when new members are pinged?",
            color=0x006fb9
        )
        embed.add_field(
            name="Current Message",
            value=f"`{self.setup_data['message']}`",
            inline=False
        )
        embed.add_field(
            name="Available Placeholders",
            value="• `{user}` - Mentions the new member\n• `{user_name}` - Member's name (no ping)\n• `{server}` - Server name",
            inline=False
        )
        
        view = SetupMessageView(self.setup_data)
        await interaction.response.edit_message(embed=embed, view=view)

class SetupDurationModal(Modal):
    """Modal for custom duration"""
    
    def __init__(self, setup_data: dict):
        super().__init__(title="Custom Duration")
        self.setup_data = setup_data
        
        self.duration_input = TextInput(
            label="Duration",
            placeholder="e.g., 30s, 5m, 2h, 1d",
            required=True,
            max_length=10,
            default="60s"
        )
        self.add_item(self.duration_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        duration_str = self.duration_input.value
        duration_seconds = get_duration_seconds(duration_str)
        
        if duration_seconds == 0:
            await interaction.response.send_message(
                f"{EMOJIS['error']} Invalid duration format! Use formats like: 30s, 5m, 2h, 1d",
                ephemeral=True
            )
            return
        
        if duration_seconds > 86400 * 7:  # 7 days max
            await interaction.response.send_message(
                f"{EMOJIS['error']} Duration cannot exceed 7 days!",
                ephemeral=True
            )
            return
        
        self.setup_data['duration'] = duration_seconds
        
        # Move to step 3: Message
        embed = discord.Embed(
            title=f"{EMOJIS['edit']} Step 3: Welcome Message",
            description="What message should be shown when new members are pinged?",
            color=0x006fb9
        )
        embed.add_field(
            name="Current Message",
            value=f"`{self.setup_data['message']}`",
            inline=False
        )
        embed.add_field(
            name="Available Placeholders",
            value="• `{user}` - Mentions the new member\n• `{user_name}` - Member's name (no ping)\n• `{server}` - Server name",
            inline=False
        )
        
        view = SetupMessageView(self.setup_data)
        await interaction.response.edit_message(embed=embed, view=view)

class SetupMessageView(View):
    """View for setting welcome message"""
    
    def __init__(self, setup_data: dict):
        super().__init__(timeout=300)
        self.setup_data = setup_data
    
    @discord.ui.button(label="Change Message", emoji=EMOJIS.get('edit', '✏️'), style=discord.ButtonStyle.secondary)
    async def change_message(self, interaction: discord.Interaction, button: Button):
        modal = SetupMessageModal(self.setup_data)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Keep Default", emoji=EMOJIS.get('success', '✅'), style=discord.ButtonStyle.success)
    async def keep_default_message(self, interaction: discord.Interaction, button: Button):
        # Move to step 4: Channels
        embed = discord.Embed(
            title=f"{EMOJIS['channel']} Step 4: Select Channels",
            description="Choose which channels should ping new members.",
            color=0x006fb9
        )
        embed.add_field(
            name="Selected Channels",
            value="None yet - click the button below to add channels",
            inline=False
        )
        
        view = SetupChannelView(self.setup_data)
        await interaction.response.edit_message(embed=embed, view=view)

class SetupMessageModal(Modal):
    """Modal for custom message"""
    
    def __init__(self, setup_data: dict):
        super().__init__(title="Custom Welcome Message")
        self.setup_data = setup_data
        
        self.message_input = TextInput(
            label="Welcome Message",
            placeholder="Welcome {user}! Please read #rules",
            required=True,
            max_length=500,
            style=discord.TextStyle.paragraph,
            default=self.setup_data['message']
        )
        self.add_item(self.message_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        self.setup_data['message'] = self.message_input.value
        
        # Move to step 4: Channels
        embed = discord.Embed(
            title=f"{EMOJIS['channel']} Step 4: Select Channels",
            description="Choose which channels should ping new members.",
            color=0x006fb9
        )
        embed.add_field(
            name="Selected Channels",
            value="None yet - click the button below to add channels",
            inline=False
        )
        
        view = SetupChannelView(self.setup_data)
        await interaction.response.edit_message(embed=embed, view=view)

class SetupChannelView(View):
    """View for selecting channels"""
    
    def __init__(self, setup_data: dict):
        super().__init__(timeout=300)
        self.setup_data = setup_data
    
    @discord.ui.button(label="Add Channel", emoji=EMOJIS.get('add', '➕'), style=discord.ButtonStyle.primary)
    async def add_channel(self, interaction: discord.Interaction, button: Button):
        if not interaction.guild:
            await interaction.response.send_message("Guild not found!", ephemeral=True)
            return
            
        async def channel_callback(channel_interaction, select):
            added_channels = []
            skipped_channels = []
            
            for value in select.values:
                channel_id = int(value)
                if channel_id not in self.setup_data['channels']:
                    self.setup_data['channels'].append(channel_id)
                    channel = channel_interaction.guild.get_channel(channel_id)
                    if channel:
                        added_channels.append(channel.mention)
                else:
                    channel = channel_interaction.guild.get_channel(channel_id)
                    if channel:
                        skipped_channels.append(channel.name)
            
            # Build response message
            messages = []
            if added_channels:
                messages.append(f"{EMOJIS['success']} Added: {', '.join(added_channels)}")
            if skipped_channels:
                messages.append(f"{EMOJIS['warning']} Already added: {', '.join(skipped_channels)}")
            
            if not messages:
                messages.append(f"{EMOJIS['error']} No channels were processed!")
            
            await channel_interaction.response.send_message(
                "\n".join(messages),
                ephemeral=True
            )
        
        # Debug: Check channel count and details
        guild = interaction.guild
        
        # Search ALL channels for "updates-sleepless" specifically
        print(f"[DEBUG] === SEARCHING FOR 'updates-sleepless' CHANNEL ===")
        all_guild_channels = list(guild.channels)
        print(f"[DEBUG] Guild: {guild.name} has {len(all_guild_channels)} TOTAL channels")
        
        # Look for updates-sleepless specifically
        updates_sleepless_channels = [ch for ch in all_guild_channels if "updates-sleepless" in ch.name.lower()]
        if updates_sleepless_channels:
            print(f"[DEBUG] 🎯 FOUND 'updates-sleepless' channels:")
            for ch in updates_sleepless_channels:
                print(f"  ✅ #{ch.name} (ID: {ch.id}, Type: {ch.type}, Category: {ch.category.name if ch.category else 'None'})")
        else:
            print(f"[DEBUG] ❌ NO 'updates-sleepless' channels found!")
            print(f"[DEBUG] All channel names containing 'update':")
            update_channels = [ch for ch in all_guild_channels if "update" in ch.name.lower()]
            if update_channels:
                for ch in update_channels:
                    print(f"      - #{ch.name} (Type: {ch.type})")
            else:
                print(f"      - None found")
        
        # Show channel types breakdown
        channel_types = {}
        for ch in all_guild_channels:
            ch_type = str(ch.type)
            if ch_type not in channel_types:
                channel_types[ch_type] = []
            channel_types[ch_type].append(ch.name)
        
        print(f"[DEBUG] Channel types breakdown:")
        for ch_type, names in channel_types.items():
            print(f"  {ch_type}: {len(names)} channels")
            if "updates-sleepless" in [name.lower() for name in names]:
                print(f"    🎯 'updates-sleepless' is in this type!")
        
        # Filter channels we're actually looking for
        text_channels = [ch for ch in guild.channels if ch.type == discord.ChannelType.text]
        news_channels = [ch for ch in guild.channels if ch.type == discord.ChannelType.news]
        forum_channels = [ch for ch in guild.channels if ch.type == discord.ChannelType.forum]
        
        print(f"[DEBUG] Text channels: {len(text_channels)}")
        print(f"[DEBUG] News channels: {len(news_channels)}")
        print(f"[DEBUG] Forum channels: {len(forum_channels)}")
        
        total_eligible = len(text_channels) + len(news_channels) + len(forum_channels)
        if total_eligible > 25:
            # Add a debug message to user
            debug_msg = f"📊 **Debug Info:** Found {len(text_channels)} text, {len(news_channels)} news, and {len(forum_channels)} forum channels. Use navigation buttons to see all channels.\n🔍 Looking for updates-sleepless? Check the console for details!"
        else:
            debug_msg = f"📊 **Debug Info:** Found {len(text_channels)} text, {len(news_channels)} news, and {len(forum_channels)} forum channels."
        
        view = POJMultiChannelView(
            interaction.guild,
            channel_types=[discord.ChannelType.text, discord.ChannelType.news, discord.ChannelType.forum],  # Include text, news, and forum channels
            exclude_channels=[],
            custom_callback=channel_callback,
            timeout=60
        )
        
        await interaction.response.send_message(
            f"{EMOJIS['channel']} **Select Channels to Add:** (You can select up to 10 channels at once)\n{debug_msg}",
            view=view,
            ephemeral=True
        )
    
    @discord.ui.button(label="Finish Setup", emoji=EMOJIS.get('success', '✅'), style=discord.ButtonStyle.success)
    async def finish_setup(self, interaction: discord.Interaction, button: Button):
        if not self.setup_data['channels']:
            await interaction.response.send_message(
                f"{EMOJIS['error']} Please add at least one channel before finishing!",
                ephemeral=True
            )
            return
        
        # Create the setup in database
        if not interaction.guild:
            await interaction.response.send_message("Guild not found!", ephemeral=True)
            return
            
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "INSERT INTO pingonjoin_setups (guild_id, name, is_active, ping_duration, ping_message) VALUES (?, ?, ?, ?, ?)",
                (interaction.guild.id, self.setup_data['name'], 1, self.setup_data['duration'], self.setup_data['message'])
            )
            setup_id = cursor.lastrowid
            
            # Add channels
            for channel_id in self.setup_data['channels']:
                await db.execute(
                    "INSERT INTO pingonjoin_channels (setup_id, channel_id) VALUES (?, ?)",
                    (setup_id, channel_id)
                )
            
            await db.commit()
        
        # Success message
        channel_mentions = []
        for ch_id in self.setup_data['channels']:
            channel = interaction.guild.get_channel(ch_id)
            if channel:
                channel_mentions.append(channel.mention)
        
        embed = discord.Embed(
            title=f"{EMOJIS['success']} Setup Complete!",
            description=f"**{self.setup_data['name']}** is now active and ready to ping new members!",
            color=0x00ff00
        )
        embed.add_field(
            name="Settings Summary",
            value=f"**Duration:** {format_duration(self.setup_data['duration'])}\n**Message:** `{self.setup_data['message']}`\n**Channels:** {', '.join(channel_mentions)}",
            inline=False
        )
        embed.set_footer(text="New members will be automatically pinged when they join!")
        
        await interaction.response.edit_message(embed=embed, view=None)

class PingOnJoin(commands.Cog):
    """Comprehensive Ping on Join System"""
    
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot
        # Track active pings to avoid duplicates
        self.active_pings = {}
        # Track deletion tasks to prevent garbage collection
        self.deletion_tasks = set()
        # Initialize database
        asyncio.create_task(self._create_tables())
    
    async def _create_tables(self):
        """Create database tables for ping on join system"""
        async with aiosqlite.connect(DB_PATH) as db:
            # Main setups table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS pingonjoin_setups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    ping_duration INTEGER DEFAULT 60,
                    ping_message TEXT DEFAULT 'Welcome {user}! 👋',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Channels table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS pingonjoin_channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    setup_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    FOREIGN KEY (setup_id) REFERENCES pingonjoin_setups (id) ON DELETE CASCADE,
                    UNIQUE(setup_id, channel_id)
                )
            """)
            
            # Ping history table (for analytics)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS pingonjoin_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    setup_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    pinged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    duration INTEGER NOT NULL,
                    FOREIGN KEY (setup_id) REFERENCES pingonjoin_setups (id) ON DELETE CASCADE
                )
            """)
            
            await db.commit()
    
    def help_custom(self):
        emoji = '<:feast_ping:1400142845402284102>'
        label = "Ping on Join Commands"
        description = """`poj setup` , `poj list` , `poj edit` , `poj delete` , `poj stats` , `poj test` , `poj`"""
        return emoji, label, description
    
    @commands.group(invoke_without_command=True, name="poj", aliases=["pingonjoin"], help="Ping new members when they join the server")
    @blacklist_check()
    @ignore_check()
    async def poj(self, ctx: commands.Context):
        if ctx.subcommand_passed is None:
            await ctx.send_help(ctx.command)
            if ctx.command is not None and hasattr(ctx.command, 'reset_cooldown'):
                ctx.command.reset_cooldown(ctx)
    
    @poj.command(name="setup", help="Set up ping on join for your server")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(1, 10, commands.BucketType.guild)
    async def setup(self, ctx):
        """Complete guided setup for ping on join system"""
        
        # Check if setup already exists
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT * FROM pingonjoin_setups WHERE guild_id = ? LIMIT 1",
                (ctx.guild.id,)
            )
            existing_setup = await cursor.fetchone()
        
        if existing_setup:
            embed = discord.Embed(
                title=f"{EMOJIS['warning']} Setup Already Exists",
                description="Ping on join is already configured for this server.",
                color=0xff9900
            )
            embed.add_field(
                name="Current Status",
                value=f"**Status:** {'🟢 Active' if existing_setup[3] else '🔴 Inactive'}\n**Duration:** {format_duration(existing_setup[4])}\n**Message:** `{existing_setup[5][:50]}{'...' if len(existing_setup[5]) > 50 else ''}`",
                inline=False
            )
            embed.add_field(
                name="Options",
                value=f"• `{ctx.prefix}poj edit` - Modify existing setup\n• `{ctx.prefix}poj delete` - Remove and start over\n• `{ctx.prefix}poj list` - View all setups",
                inline=False
            )
            await ctx.send(embed=embed)
            return
        
        # Start guided setup
        embed = discord.Embed(
            title=f"{EMOJIS['settings']} Ping on Join Setup",
            description="Let's set up ping notifications for new members! This will guide you through the process step by step.",
            color=0x006fb9
        )
        embed.add_field(
            name="What this does:",
            value="• Automatically ping new members when they join\n• Customizable message and duration\n• Choose which channels to use\n• Can be toggled on/off anytime",
            inline=False
        )
        embed.add_field(
            name="Ready to start?",
            value="Click the button below to begin the setup process!",
            inline=False
        )
        
        view = SetupWizardView(ctx.author.id, ctx.guild.id)
        await ctx.send(embed=embed, view=view)
    
    @poj.command(name="list", help="List all ping setups for this server")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def list_setups(self, ctx):
        """List all ping setups for this server"""
        
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT * FROM pingonjoin_setups WHERE guild_id = ? ORDER BY created_at DESC",
                (ctx.guild.id,)
            )
            setups = list(await cursor.fetchall())
        
        if not setups:
            embed = discord.Embed(
                title=f"{EMOJIS['list']} No POJ Located",
                description="No ping on join system found for this server.",
                color=0xff9900
            )
            embed.add_field(
                name="Create One",
                value=f"Use `{ctx.prefix}pingonjoin setup ` to create your system.",
                inline=False
            )
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title=f"{EMOJIS['list']} Ping on Join Setups",
            description=f"Found {len(setups)} setup(s) for {ctx.guild.name}",
            color=0x006fb9
        )
        
        for setup in setups[:10]:  # Limit to 10 setups
            setup_id, guild_id, name, is_active, ping_duration, ping_message, created_at = setup
            
            # Get channel count
            async with aiosqlite.connect(DB_PATH) as db:
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM pingonjoin_channels WHERE setup_id = ?",
                    (setup_id,)
                )
                result = await cursor.fetchone()
                channel_count = result[0] if result else 0
            
            status = "🟢 Active" if is_active else "🔴 Inactive"
            duration_text = format_duration(ping_duration)
            
            embed.add_field(
                name=f"**{name}** (ID: {setup_id})",
                value=f"{status} • {EMOJIS['time']} {duration_text} • {EMOJIS['channel']} {channel_count} channels",
                inline=False
            )
        
        if len(setups) > 10:
            embed.set_footer(text=f"Showing 10 of {len(setups)} setups")
        
        await ctx.send(embed=embed)
    
    @poj.command(name="edit", help="Edit an existing ping setup")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def edit_setup(self, ctx, setup_id: int):
        """Edit an existing ping setup"""
        
        # Get setup
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT * FROM pingonjoin_setups WHERE id = ? AND guild_id = ?",
                (setup_id, ctx.guild.id)
            )
            setup = await cursor.fetchone()
        
        if not setup:
            await ctx.send(f"{EMOJIS['error']} Setup not found! Use `{ctx.prefix}pingonjoin list` to see available setups.")
            return
        
        setup_data = {
            'id': setup[0],
            'guild_id': setup[1],
            'name': setup[2],
            'is_active': setup[3],
            'ping_duration': setup[4],
            'ping_message': setup[5],
            'created_at': setup[6]
        }
        
        embed = discord.Embed(
            title=f"{EMOJIS['edit']} Edit Ping Setup",
            description=f"Editing setup: **{setup[2]}**",
            color=0x006fb9
        )
        
        status = "🟢 Active" if setup[3] else "🔴 Inactive"
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="Duration", value=format_duration(setup[4]), inline=True)
        embed.add_field(name="Message", value=f"`{setup[5][:50]}...`" if len(setup[5]) > 50 else f"`{setup[5]}`", inline=False)
        
        view = PingSetupView(ctx.author.id, setup_data)
        await ctx.send(embed=embed, view=view)
    
    @poj.command(name="delete", help="Delete a ping setup")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def delete_setup(self, ctx, setup_id: int):
        """Delete a ping setup"""
        
        # Get setup
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT name FROM pingonjoin_setups WHERE id = ? AND guild_id = ?",
                (setup_id, ctx.guild.id)
            )
            setup = await cursor.fetchone()
        
        if not setup:
            await ctx.send(f"{EMOJIS['error']} Setup not found!")
            return
        
        # Confirmation
        embed = discord.Embed(
            title=f"{EMOJIS['warning']} Confirm Deletion",
            description=f"Are you sure you want to delete setup: **{setup[0]}**?",
            color=0xff9900
        )
        embed.add_field(
            name="⚠️ Warning",
            value="This action cannot be undone. All channels and history will be removed.",
            inline=False
        )
        
        view = View()
        
        async def confirm_delete(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You cannot confirm this deletion.", ephemeral=True)
                return
            
            async with aiosqlite.connect(DB_PATH) as db:
                # Delete setup (cascades to channels and history)
                await db.execute(
                    "DELETE FROM pingonjoin_setups WHERE id = ?",
                    (setup_id,)
                )
                await db.commit()
            
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title=f"{EMOJIS['success']} Setup Deleted",
                    description=f"Successfully deleted setup: **{setup[0]}**",
                    color=0x00ff00
                ),
                view=None
            )
        
        async def cancel_delete(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You cannot cancel this deletion.", ephemeral=True)
                return
            
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title=f"{EMOJIS['success']} Deletion Cancelled",
                    description="The setup was not deleted.",
                    color=0x006fb9
                ),
                view=None
            )
        
        confirm_btn = Button(label="Delete", style=discord.ButtonStyle.danger, emoji=EMOJIS.get('delete', '🗑️'))
        cancel_btn = Button(label="Cancel", style=discord.ButtonStyle.secondary)
        
        confirm_btn.callback = confirm_delete
        cancel_btn.callback = cancel_delete
        
        view.add_item(confirm_btn)
        view.add_item(cancel_btn)
        
        await ctx.send(embed=embed, view=view)
    
    @poj.command(name="stats", help="View ping statistics")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    async def stats(self, ctx, setup_id: Optional[int] = None):
        """View ping statistics"""
        
        async with aiosqlite.connect(DB_PATH) as db:
            if setup_id:
                # Stats for specific setup
                cursor = await db.execute(
                    "SELECT name FROM pingonjoin_setups WHERE id = ? AND guild_id = ?",
                    (setup_id, ctx.guild.id)
                )
                setup = await cursor.fetchone()
                
                if not setup:
                    await ctx.send(f"{EMOJIS['error']} Setup not found!")
                    return
                
                cursor = await db.execute(
                    "SELECT COUNT(*), AVG(duration) FROM pingonjoin_history WHERE setup_id = ?",
                    (setup_id,)
                )
                result = await cursor.fetchone()
                total_pings, avg_duration = (result[0], result[1]) if result else (0, 0)
                
                # Recent pings
                cursor = await db.execute(
                    "SELECT user_id, pinged_at FROM pingonjoin_history WHERE setup_id = ? ORDER BY pinged_at DESC LIMIT 5",
                    (setup_id,)
                )
                recent_pings = await cursor.fetchall()
                
                embed = discord.Embed(
                    title=f"{EMOJIS['list']} Ping Statistics",
                    description=f"Stats for setup: **{setup[0]}**",
                    color=0x006fb9
                )
                
                embed.add_field(name="Total Pings", value=str(total_pings or 0), inline=True)
                embed.add_field(name="Avg Duration", value=format_duration(int(avg_duration or 0)), inline=True)
                
                if recent_pings:
                    recent_text = []
                    for user_id, pinged_at in recent_pings:
                        user = ctx.guild.get_member(user_id)
                        user_name = user.display_name if user else f"User {user_id}"
                        recent_text.append(f"• {user_name}")
                    
                    embed.add_field(
                        name="Recent Pings",
                        value="\n".join(recent_text),
                        inline=False
                    )
                
            else:
                # Overall server stats
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM pingonjoin_setups WHERE guild_id = ?",
                    (ctx.guild.id,)
                )
                result = await cursor.fetchone()
                total_setups = result[0] if result else 0
                
                cursor = await db.execute(
                    """
                    SELECT COUNT(*) FROM pingonjoin_history 
                    WHERE setup_id IN (
                        SELECT id FROM pingonjoin_setups WHERE guild_id = ?
                    )
                    """,
                    (ctx.guild.id,)
                )
                result = await cursor.fetchone()
                total_pings = result[0] if result else 0
                
                embed = discord.Embed(
                    title=f"{EMOJIS['list']} Server Ping Statistics",
                    description=f"Overall stats for {ctx.guild.name}",
                    color=0x006fb9
                )
                
                embed.add_field(name="Total Setups", value=str(total_setups), inline=True)
                embed.add_field(name="Total Pings", value=str(total_pings), inline=True)
        
        await ctx.send(embed=embed)
    
    @poj.command(name="test", help="Test the ping on join system")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(1, 30, commands.BucketType.guild)
    async def test_system(self, ctx):
        """Test the ping on join system by simulating a member join"""
        
        # Get active setups for this guild
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                """
                SELECT s.id, s.name, s.ping_duration, s.ping_message, COUNT(c.channel_id) as channel_count
                FROM pingonjoin_setups s
                LEFT JOIN pingonjoin_channels c ON s.id = c.setup_id
                WHERE s.guild_id = ? AND s.is_active = 1
                GROUP BY s.id
                """,
                (ctx.guild.id,)
            )
            setups = list(await cursor.fetchall())
        
        if not setups:
            embed = discord.Embed(
                title=f"{EMOJIS['error']} No Active Setups",
                description="No active ping on join setups found for this server.",
                color=0xff0000
            )
            embed.add_field(
                name="Create One",
                value=f"Use `{ctx.prefix}poj setup` to create a setup first.",
                inline=False
            )
            await ctx.send(embed=embed)
            return
        
        # Show test options
        embed = discord.Embed(
            title=f"{EMOJIS['settings']} Test Ping on Join System",
            description=f"Found {len(setups)} active setup(s). Testing will simulate {ctx.author.mention} joining the server.",
            color=0x006fb9
        )
        
        setup_info = []
        for setup_id, name, duration, message, channel_count in setups:
            setup_info.append(f"**{name}** (ID: {setup_id})\n└ {channel_count} channels • {format_duration(duration)} duration")
        
        embed.add_field(
            name=f"{EMOJIS['list']} Active Setups",
            value="\n\n".join(setup_info),
            inline=False
        )
        embed.add_field(
            name=f"{EMOJIS['warning']} Important",
            value="This will send actual messages that will be visible to everyone in the configured channels!",
            inline=False
        )
        
        # Create test confirmation view
        view = View()
        
        async def confirm_test(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You cannot run this test.", ephemeral=True)
                return
            
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title=f"{EMOJIS['settings']} Running Test...",
                    description="Simulating member join event...",
                    color=0xffaa00
                ),
                view=None
            )
            
            # Simulate the member join by calling the ping logic
            test_results = []
            
            async with aiosqlite.connect(DB_PATH) as db:
                cursor = await db.execute(
                    """
                    SELECT s.id, s.ping_duration, s.ping_message, c.channel_id
                    FROM pingonjoin_setups s
                    JOIN pingonjoin_channels c ON s.id = c.setup_id
                    WHERE s.guild_id = ? AND s.is_active = 1
                    """,
                    (ctx.guild.id,)
                )
                test_setups = await cursor.fetchall()
            
            # Group by setup_id
            setup_data = {}
            for setup_id, duration, message, channel_id in test_setups:
                if setup_id not in setup_data:
                    setup_data[setup_id] = {
                        'duration': duration,
                        'message': message,
                        'channels': []
                    }
                setup_data[setup_id]['channels'].append(channel_id)
            
            # Process each setup
            for setup_id, data in setup_data.items():
                for channel_id in data['channels']:
                    channel = ctx.bot.get_channel(channel_id)
                    if not channel:
                        test_results.append(f"❌ Channel {channel_id} not found")
                        continue
                    
                    # Process message placeholders
                    test_message = data['message'].replace('{user}', ctx.author.mention)
                    test_message = test_message.replace('{user_name}', ctx.author.display_name)
                    test_message = test_message.replace('{server}', ctx.guild.name)
                    test_message = f"🧪 **TEST:** {test_message}"
                    
                    try:
                        # Send test ping message
                        ping_msg = await channel.send(test_message)
                        test_results.append(f"✅ Sent test ping to {channel.mention} (will delete in {format_duration(data['duration'])})")
                        
                        # Create unique ping key for test
                        ping_key = f"test_{ctx.author.id}_{channel_id}_{setup_id}"
                        
                        # Get the cog instance to access active_pings and deletion method
                        poj_cog = ctx.bot.get_cog("PingOnJoin")
                        if poj_cog:
                            # Track active ping (same as real system)
                            poj_cog.active_pings[ping_key] = ping_msg
                            
                            # Schedule deletion if duration > 0 (same as real system, with task reference)
                            if data['duration'] > 0:
                                task = asyncio.create_task(poj_cog._delete_ping_after_delay(ping_key, data['duration']))
                                poj_cog.deletion_tasks.add(task)
                                task.add_done_callback(poj_cog.deletion_tasks.discard)
                        
                    except discord.Forbidden:
                        test_results.append(f"❌ No permission to send to {channel.mention}")
                    except discord.HTTPException as e:
                        test_results.append(f"❌ Failed to send to {channel.mention}: {e}")
            
            # Show results
            result_embed = discord.Embed(
                title=f"{EMOJIS['success']} Test Complete!",
                description="Ping on join test has been executed.",
                color=0x00ff00
            )
            
            if test_results:
                # Split results into success/failure
                success = [r for r in test_results if r.startswith('✅')]
                failed = [r for r in test_results if r.startswith('❌')]
                
                if success:
                    result_embed.add_field(
                        name=f"{EMOJIS['success']} Successful ({len(success)})",
                        value="\n".join(success),
                        inline=False
                    )
                
                if failed:
                    result_embed.add_field(
                        name=f"{EMOJIS['error']} Failed ({len(failed)})",
                        value="\n".join(failed),
                        inline=False
                    )
            else:
                result_embed.add_field(
                    name="No Results",
                    value="No test messages were attempted.",
                    inline=False
                )
            
            await interaction.edit_original_response(embed=result_embed)
        
        async def cancel_test(interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You cannot cancel this test.", ephemeral=True)
                return
            
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title=f"{EMOJIS['success']} Test Cancelled",
                    description="Ping on join test was cancelled.",
                    color=0x006fb9
                ),
                view=None
            )
        
        test_btn = discord.ui.Button(label="Run Test", style=discord.ButtonStyle.danger, emoji=EMOJIS.get('settings', '🧪'))
        cancel_btn = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary, emoji=EMOJIS.get('error', '❌'))
        
        test_btn.callback = confirm_test
        cancel_btn.callback = cancel_test
        
        view.add_item(test_btn)
        view.add_item(cancel_btn)
        
        await ctx.send(embed=embed, view=view)
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Handle member join events and send pings"""
        print(f"[POJ] 🔔 on_member_join triggered for {member.name} in {member.guild.name} (ID: {id(self)})")
        
        # Get all active setups for this guild
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                """
                SELECT s.id, s.ping_duration, s.ping_message, c.channel_id
                FROM pingonjoin_setups s
                JOIN pingonjoin_channels c ON s.id = c.setup_id
                WHERE s.guild_id = ? AND s.is_active = 1
                """,
                (member.guild.id,)
            )
            setups = await cursor.fetchall()
        
        if not setups:
            return
        
        # Group by setup_id
        setup_data = {}
        for setup_id, duration, message, channel_id in setups:
            if setup_id not in setup_data:
                setup_data[setup_id] = {
                    'duration': duration,
                    'message': message,
                    'channels': []
                }
            setup_data[setup_id]['channels'].append(channel_id)
        
        # Process each setup
        for setup_id, data in setup_data.items():
            for channel_id in data['channels']:
                channel = self.bot.get_channel(channel_id)
                if not channel:
                    continue
                
                # Create unique ping key
                ping_key = f"{member.id}_{channel_id}_{setup_id}"
                
                # Check if already pinging this member in this channel
                if ping_key in self.active_pings:
                    continue
                
                # Process message placeholders
                message = data['message'].replace('{user}', member.mention)
                message = message.replace('{user_name}', member.display_name)
                message = message.replace('{server}', member.guild.name)
                
                try:
                    # Send ping message
                    ping_msg = await channel.send(message)
                    print(f"[POJ] ✅ Sent ping message (ID: {ping_msg.id}) to channel {channel.name} for {member.name}")
                    
                    # Track active ping
                    self.active_pings[ping_key] = ping_msg
                    print(f"[POJ] 📝 Tracked ping with key: {ping_key}")
                    
                    # Record in history
                    async with aiosqlite.connect(DB_PATH) as db:
                        await db.execute(
                            "INSERT INTO pingonjoin_history (setup_id, user_id, channel_id, duration) VALUES (?, ?, ?, ?)",
                            (setup_id, member.id, channel_id, data['duration'])
                        )
                        await db.commit()
                    
                    # Schedule deletion (keep task reference to prevent garbage collection)
                    if data['duration'] > 0:
                        print(f"[POJ] ⏰ Scheduling deletion for {ping_key} in {data['duration']} seconds")
                        task = asyncio.create_task(self._delete_ping_after_delay(ping_key, data['duration']))
                        self.deletion_tasks.add(task)
                        print(f"[POJ] 📌 Added task to deletion_tasks set (total tasks: {len(self.deletion_tasks)})")
                        # Remove from set when done, but don't let it get garbage collected prematurely
                        task.add_done_callback(lambda t: self.deletion_tasks.discard(t))
                    else:
                        print(f"[POJ] ⚠️ Duration is 0, not scheduling deletion for {ping_key}")
                    
                except discord.Forbidden:
                    continue
                except discord.HTTPException:
                    continue
    
    async def _delete_ping_after_delay(self, ping_key: str, delay: int):
        """Delete ping message after specified delay"""
        try:
            print(f"[POJ] Ping deletion scheduled for {ping_key} in {delay} seconds")
            await asyncio.sleep(delay)
            
            if ping_key in self.active_pings:
                message = self.active_pings[ping_key]
                try:
                    print(f"[POJ] Attempting to delete ping message (ID: {message.id}) for key: {ping_key}")
                    await message.delete()
                    print(f"[POJ] ✅ Successfully deleted ping message for key: {ping_key}")
                except discord.NotFound:
                    print(f"[POJ] ⚠️ Message already deleted for key: {ping_key}")
                except discord.Forbidden:
                    print(f"[POJ] ❌ No permission to delete message for key: {ping_key}")
                except discord.HTTPException as e:
                    print(f"[POJ] ❌ HTTP error deleting message for key {ping_key}: {e}")
                except Exception as e:
                    print(f"[POJ] ❌ Unexpected error deleting message for key {ping_key}: {e}")
                    import traceback
                    traceback.print_exc()
                finally:
                    # Always remove from active pings
                    if ping_key in self.active_pings:
                        del self.active_pings[ping_key]
                        print(f"[POJ] Removed {ping_key} from active_pings")
            else:
                print(f"[POJ] ⚠️ Ping key {ping_key} no longer in active_pings (may have been manually deleted)")
        except Exception as e:
            print(f"[POJ] ❌ Fatal error in _delete_ping_after_delay for {ping_key}: {e}")
            import traceback
            traceback.print_exc()

async def setup(bot):
    await bot.add_cog(PingOnJoin(bot))