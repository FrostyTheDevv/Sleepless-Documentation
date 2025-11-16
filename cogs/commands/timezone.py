from utils.error_helpers import StandardErrorHandler
"""
Timezone Management Commands
"""

import discord
from discord.ext import commands
import asyncio
from utils.timezone_utils import get_timezone_utils
from datetime import datetime
import pytz
import re
from typing import Optional
from utils.Tools import blacklist_check, ignore_check

def parse_user_timezone_input(timezone_input: str) -> Optional[str]:
    """
    Parse user-friendly timezone input and convert to valid pytz timezone.
    
    Accepts formats like:
    - UTC+2, UTC-5, GMT+1, etc.
    - City names: London, New York, Tokyo, Bucharest, etc.
    - Country codes: US, GB, DE, RO, etc.
    - Full timezone names: Europe/London, America/New_York, etc.
    
    Returns valid pytz timezone string or None if not found.
    """
    timezone_input = timezone_input.strip()
    
    # First try direct pytz validation
    try:
        pytz.timezone(timezone_input)
        return timezone_input
    except:
        pass
    
    # Handle UTC/GMT offset formats (UTC+2, GMT-5, etc.)
    import re
    utc_pattern = r'^(UTC|GMT)([+-])(\d{1,2})(?::?(\d{2}))?$'
    match = re.match(utc_pattern, timezone_input.upper())
    if match:
        base, sign, hours, minutes = match.groups()
        hours = int(hours)
        minutes = int(minutes or 0)
        
        # Convert to Etc/GMT format (note: signs are reversed in Etc/GMT)
        total_hours = hours + (minutes / 60)
        if sign == '+':
            # UTC+2 becomes Etc/GMT-2
            tz_name = f"Etc/GMT-{int(total_hours)}"
        else:
            # UTC-5 becomes Etc/GMT+5
            tz_name = f"Etc/GMT+{int(total_hours)}"
        
        try:
            pytz.timezone(tz_name)
            return tz_name
        except:
            pass
    
    # City name mappings (common cities users might type)
    city_mappings = {
        'london': 'Europe/London',
        'paris': 'Europe/Paris',
        'berlin': 'Europe/Berlin',
        'madrid': 'Europe/Madrid',
        'rome': 'Europe/Rome',
        'amsterdam': 'Europe/Amsterdam',
        'stockholm': 'Europe/Stockholm',
        'oslo': 'Europe/Oslo',
        'copenhagen': 'Europe/Copenhagen',
        'helsinki': 'Europe/Helsinki',
        'prague': 'Europe/Prague',
        'budapest': 'Europe/Budapest',
        'athens': 'Europe/Athens',
        'sofia': 'Europe/Sofia',
        'zagreb': 'Europe/Zagreb',
        'bucharest': 'Europe/Bucharest',
        'kiev': 'Europe/Kiev',
        'moscow': 'Europe/Moscow',
        'warsaw': 'Europe/Warsaw',
        'istanbul': 'Europe/Istanbul',
        'new york': 'America/New_York',
        'los angeles': 'America/Los_Angeles',
        'chicago': 'America/Chicago',
        'denver': 'America/Denver',
        'phoenix': 'America/Phoenix',
        'toronto': 'America/Toronto',
        'vancouver': 'America/Vancouver',
        'tokyo': 'Asia/Tokyo',
        'seoul': 'Asia/Seoul',
        'shanghai': 'Asia/Shanghai',
        'hong kong': 'Asia/Hong_Kong',
        'singapore': 'Asia/Singapore',
        'mumbai': 'Asia/Kolkata',
        'dubai': 'Asia/Dubai',
        'bangkok': 'Asia/Bangkok',
        'sydney': 'Australia/Sydney',
        'melbourne': 'Australia/Melbourne',
        'perth': 'Australia/Perth',
        'auckland': 'Pacific/Auckland',
    }
    
    # Check city mappings
    input_lower = timezone_input.lower()
    if input_lower in city_mappings:
        return city_mappings[input_lower]
    
    # Search for partial matches in timezone names
    all_timezones = list(pytz.all_timezones)
    input_parts = input_lower.replace(' ', '_').split('_')
    
    # Look for timezones containing any of the input parts
    for tz in all_timezones:
        tz_lower = tz.lower()
        if any(part in tz_lower for part in input_parts if len(part) > 2):
            # Prefer exact matches
            if input_lower.replace(' ', '_') in tz_lower:
                return tz
    
    # If no exact match, return the first reasonable match
    for tz in all_timezones:
        tz_lower = tz.lower()
        if any(part in tz_lower for part in input_parts if len(part) > 2):
            return tz
    
    return None

def sanitize_timezone_name(timezone_str: str) -> str:
    """
    Sanitize timezone name to remove location-specific information for privacy.
    Converts timezone names to generic format showing only time offset and abbreviation.
    
    Examples:
    - 'America/New_York' -> 'UTC-5 (EST)'
    - 'Europe/London' -> 'UTC+0 (GMT)'
    - 'US/Pacific' -> 'UTC-8 (PST)'
    """
    try:
        tz = pytz.timezone(timezone_str)
        now = datetime.now(tz)
        
        # Get timezone abbreviation (EST, PST, GMT, etc.)
        tz_abbr = now.strftime('%Z')
        
        # Get UTC offset
        offset = now.utcoffset()
        if offset:
            total_seconds = int(offset.total_seconds())
            hours, remainder = divmod(abs(total_seconds), 3600)
            minutes = remainder // 60
            
            # Format offset
            sign = '+' if total_seconds >= 0 else '-'
            if minutes == 0:
                offset_str = f"UTC{sign}{hours}"
            else:
                offset_str = f"UTC{sign}{hours}:{minutes:02d}"
        else:
            offset_str = "UTC"
        
        # Return sanitized format
        if tz_abbr and tz_abbr != timezone_str:
            return f"{offset_str} ({tz_abbr})"
        else:
            return offset_str
            
    except Exception:
        # Fallback for invalid timezone strings
        return timezone_str

class TimezoneCommands(commands.Cog):
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot
        self.tz_utils = get_timezone_utils(bot)
    
    async def cog_load(self):
        """Initialize timezone database when cog loads"""
        await self.tz_utils.ensure_timezone_db()
        print("<a:verify:1436953625384452106> Timezone management system initialized")

    @commands.group(name="timezone", aliases=["tz"], invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    async def timezone(self, ctx):
        """Timezone management commands"""
        if ctx.invoked_subcommand is None:
            # Show current timezone info (personal only)
            user_tz = await self.tz_utils.get_user_timezone(ctx.author.id)
            
            # Sanitize timezone names for privacy (remove location information)
            user_tz_display = sanitize_timezone_name(user_tz)
            
            embed = discord.Embed(
                title="<a:clock:1436953635731800178> Timezone Information",
                color=0x5865F2
            )
            
            embed.add_field(
                name="Your Timezone",
                value=f"`{user_tz_display}`",
                inline=True
            )
            
            # Show current time in user's timezone
            now = discord.utils.utcnow()
            user_time = await self.tz_utils.format_time_for_user(now, ctx.author.id, "%I:%M %p %Z")
            
            embed.add_field(
                name="Current Time (You)",
                value=f"`{user_time}`",
                inline=True
            )
            
            embed.add_field(
                name="Commands",
                value=f"`{ctx.prefix}tz set` - Set your timezone (sent to DMs)\n"
                      f"`{ctx.prefix}tz search <query>` - Search timezones (sent to DMs)\n"
                      f"`{ctx.prefix}tz list [search]` - List all timezones (sent to DMs)\n"
                      f"`{ctx.prefix}tz server` - Set server timezone (Admin only)",
                inline=False
            )
            
            
            await ctx.send(embed=embed)

    @timezone.command(name="set")
    @blacklist_check() 
    @ignore_check()
    async def timezone_set(self, ctx, *, timezone_name: Optional[str] = None):
        """Set your personal timezone"""
        if not timezone_name:
            # Show timezone selection menu in DMs
            view = TimezoneSelectView(self.tz_utils, ctx.author.id, is_guild=False)
            embed = discord.Embed(
                title="🌍 Select Your Timezone",
                description="Choose your timezone from the dropdown below:",
                color=0x5865F2
            )
            
            try:
                # Send to DMs
                await ctx.author.send(embed=embed, view=view)
                
                # Notify in server that DM was sent
                notification_embed = discord.Embed(
                    title="📬 Check Your DMs",
                    description=f"{ctx.author.mention}, I've sent you a timezone selection menu in your DMs!",
                    color=0x5865F2
                )
                await ctx.send(embed=notification_embed, delete_after=10)
                
            except discord.Forbidden:
                # If DMs are disabled, send in server with warning
                embed.add_field(
                    name="⚠️ Privacy Notice",
                    value="I couldn't send this to your DMs. Please enable DMs from server members for privacy.",
                    inline=False
                )
                await ctx.send(embed=embed, view=view)
            
            return
        
        # Parse and validate timezone using flexible parser
        parsed_timezone = parse_user_timezone_input(timezone_name)
        
        if parsed_timezone:
            try:
                # Double-check the parsed timezone is valid
                pytz.timezone(parsed_timezone)
                await self.tz_utils.set_user_timezone(ctx.author.id, parsed_timezone)
                
                # Sanitize timezone name for display (remove location information)
                sanitized_name = sanitize_timezone_name(parsed_timezone)
                
                embed = discord.Embed(
                    title="<a:verify:1436953625384452106> Timezone Updated",
                    description=f"Your timezone has been set to `{sanitized_name}`",
                    color=0x00FF00
                )
                
                # Show what input was recognized as
                if timezone_name.lower() != parsed_timezone.lower():
                    embed.add_field(
                        name="Recognized As",
                        value=f"Input `{timezone_name}` → `{parsed_timezone}`",
                        inline=False
                    )
                
                # Show current time in new timezone
                now = discord.utils.utcnow()
                current_time = await self.tz_utils.format_time_for_user(now, ctx.author.id)
                embed.add_field(name="Current Time", value=f"`{current_time}`", inline=False)
                
                try:
                    # Send confirmation to DMs
                    await ctx.author.send(embed=embed)
                    
                    # Notify in server
                    notification_embed = discord.Embed(
                        title="✅ Timezone Set Successfully",
                        description=f"{ctx.author.mention}, your timezone has been updated! Check your DMs for details.",
                        color=0x00FF00
                    )
                    await ctx.send(embed=notification_embed, delete_after=10)
                    
                except discord.Forbidden:
                    # If DMs are disabled, send in server
                    embed.add_field(
                        name="⚠️ Privacy Notice",
                        value="I couldn't send the confirmation to your DMs. Please enable DMs from server members.",
                        inline=False
                    )
                    await ctx.send(embed=embed)
                    
                return
                    
            except Exception as e:
                # This shouldn't happen if our parser works correctly
                print(f"Timezone validation error after parsing: {e}")
        
        # If we get here, the timezone couldn't be parsed
        embed = discord.Embed(
            title="<a:wrong:1436956421110632489> Invalid Timezone",
            description=f"Could not recognize timezone: `{timezone_name}`",
            color=0xFF0000
        )
        embed.add_field(
            name="Supported Formats:",
            value="• **UTC Offsets:** `UTC+2`, `UTC-5`, `GMT+1`\n"
                  "• **City Names:** `London`, `Bucharest`, `New York`\n"
                  "• **Full Names:** `Europe/London`, `America/New_York`\n"
                  "• **Short Names:** `EST`, `PST`, `CET`",
            inline=False
        )
        embed.add_field(
            name="Find Your Timezone:",
            value=f"`{ctx.prefix}tz search {timezone_name}` - Search for similar timezones\n"
                  f"`{ctx.prefix}tz list` - Browse all available timezones\n"
                  f"`{ctx.prefix}tz set` - Use interactive selection menu",
            inline=False
        )
        await ctx.send(embed=embed)

    @timezone.command(name="search")
    @blacklist_check()
    @ignore_check()
    async def timezone_search(self, ctx, *, query: str):
        """Search for timezones by name or region"""
        query_lower = query.lower()
        all_timezones = sorted(pytz.all_timezones)
        
        # Search in timezone names
        matching_timezones = [tz for tz in all_timezones if query_lower in tz.lower()]
        
        if not matching_timezones:
            embed = discord.Embed(
                title="🔍 No Timezones Found",
                description=f"No timezones found matching: `{query}`",
                color=0xFF0000
            )
            embed.add_field(
                name="Search Tips:",
                value="• Try country names: `america`, `europe`, `asia`\n"
                      "• Try city names: `london`, `tokyo`, `new_york`\n"
                      "• Try regions: `pacific`, `eastern`, `central`\n"
                      "• Use underscores: `new_york` instead of `new york`",
                inline=False
            )
            await ctx.send(embed=embed)
            return
        
        # If only a few results, show them directly with selection in DMs
        if len(matching_timezones) <= 25:
            view = TimezoneSelectView(self.tz_utils, ctx.author.id, is_guild=False)
            # Update the view with search results
            view.update_timezone_select(matching_timezones)
            
            embed = discord.Embed(
                title=f"🔍 Search Results for '{query}'",
                description=f"Found {len(matching_timezones)} matching timezones. Select one below:",
                color=0x5865F2
            )
            
            try:
                # Send to DMs
                await ctx.author.send(embed=embed, view=view)
                
                # Notify in server
                notification_embed = discord.Embed(
                    title="📬 Check Your DMs",
                    description=f"{ctx.author.mention}, I've sent your search results to your DMs!",
                    color=0x5865F2
                )
                await ctx.send(embed=notification_embed, delete_after=10)
                
            except discord.Forbidden:
                # If DMs are disabled, send in server with warning
                embed.add_field(
                    name="⚠️ Privacy Notice",
                    value="I couldn't send this to your DMs. Please enable DMs from server members for privacy.",
                    inline=False
                )
                await ctx.send(embed=embed, view=view)
        else:
            # Too many results, show paginated list in DMs
            view = TimezoneListPaginatedView(matching_timezones, ctx.prefix, query)
            embed = view.create_embed(0)
            
            try:
                # Send to DMs
                await ctx.author.send(embed=embed, view=view)
                
                # Notify in server
                notification_embed = discord.Embed(
                    title="📬 Check Your DMs",
                    description=f"{ctx.author.mention}, I've sent your timezone list to your DMs! (Found {len(matching_timezones)} results)",
                    color=0x5865F2
                )
                await ctx.send(embed=notification_embed, delete_after=10)
                
            except discord.Forbidden:
                # If DMs are disabled, send in server with warning
                embed.add_field(
                    name="⚠️ Privacy Notice",
                    value="I couldn't send this to your DMs. Please enable DMs from server members for privacy.",
                    inline=False
                )
                await ctx.send(embed=embed, view=view)

    @timezone.command(name="server")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def timezone_server(self, ctx, *, timezone_name: Optional[str] = None):
        """Set server default timezone (Admin only)"""
        if not timezone_name:
            # Show timezone selection menu
            view = TimezoneSelectView(self.tz_utils, ctx.guild.id, is_guild=True)
            embed = discord.Embed(
                title="<:clock1:1427471544409657354> Select Server Timezone",
                description="Choose the default timezone for this server:",
                color=0x5865F2
            )
            await ctx.send(embed=embed, view=view)
            return
        
        # Validate and set timezone
        try:
            pytz.timezone(timezone_name)  # Validate timezone
            await self.tz_utils.set_guild_timezone(ctx.guild.id, timezone_name)
            
            # Sanitize timezone name for display (remove location information)
            sanitized_name = sanitize_timezone_name(timezone_name)
            
            embed = discord.Embed(
                title="<a:verify:1436953625384452106> Server Timezone Updated",
                description=f"Server timezone has been set to `{sanitized_name}`",
                color=0x00FF00
            )
            
            # Show current time in new timezone
            now = discord.utils.utcnow()
            current_time = await self.tz_utils.format_time_for_guild(now, ctx.guild.id)
            embed.add_field(name="Current Server Time", value=f"`{current_time}`", inline=False)
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Invalid Timezone",
                description=f"Could not set timezone to `{timezone_name}`.",
                color=0xFF0000
            )
            embed.add_field(
                name="Find Your Timezone:",
                value=f"`{ctx.prefix}tz search {timezone_name}` - Search for similar timezones\n"
                      f"`{ctx.prefix}tz list` - Browse all available timezones\n"
                      f"`{ctx.prefix}tz server` - Use interactive selection menu",
                inline=False
            )
            await ctx.send(embed=embed)

    @timezone.command(name="list")
    @blacklist_check()
    @ignore_check()
    async def timezone_list(self, ctx, *, search: Optional[str] = None):
        """List all available timezones with pagination and search"""
        # Get all pytz timezones
        all_timezones = sorted(pytz.all_timezones)
        
        # Filter by search term if provided
        if search:
            search_lower = search.lower()
            all_timezones = [tz for tz in all_timezones if search_lower in tz.lower()]
            
            if not all_timezones:
                embed = discord.Embed(
                    title="🔍 No Timezones Found",
                    description=f"No timezones found matching: `{search}`",
                    color=0xFF0000
                )
                embed.add_field(
                    name="Try searching for:",
                    value="• Country names (e.g., `america`, `europe`, `asia`)\n"
                          "• City names (e.g., `london`, `tokyo`, `york`)\n"
                          "• Regions (e.g., `pacific`, `eastern`, `central`)",
                    inline=False
                )
                await ctx.send(embed=embed)
                return
        
        # Create paginated view
        view = TimezoneListPaginatedView(all_timezones, ctx.prefix, search)
        
        # Create initial embed
        embed = view.create_embed(0)
        
        try:
            # Send to DMs
            await ctx.author.send(embed=embed, view=view)
            
            # Notify in server
            search_text = f" (Search: {search})" if search else ""
            notification_embed = discord.Embed(
                title="📬 Check Your DMs",
                description=f"{ctx.author.mention}, I've sent the timezone list to your DMs!{search_text}\n"
                           f"Found {len(all_timezones)} timezones.",
                color=0x5865F2
            )
            await ctx.send(embed=notification_embed, delete_after=10)
            
        except discord.Forbidden:
            # If DMs are disabled, send in server with warning
            embed.add_field(
                name="⚠️ Privacy Notice",
                value="I couldn't send this to your DMs. Please enable DMs from server members for privacy.",
                inline=False
            )
            await ctx.send(embed=embed, view=view)

class TimezoneListPaginatedView(discord.ui.View):
    def __init__(self, timezones, prefix, search=None):
        super().__init__(timeout=300)
        self.timezones = timezones
        self.prefix = prefix
        self.search = search
        self.per_page = 15
        self.current_page = 0
        self.max_pages = (len(timezones) - 1) // self.per_page + 1
        
        # Update button states
        self.update_buttons()
    
    def update_buttons(self):
        """Update button states based on current page"""
        # Clear all items first
        self.clear_items()
        
        # Add navigation buttons
        if self.max_pages > 1:
            # First page button
            first_button = discord.ui.Button(
                emoji="<:left_arrow:1428164516595630193>",
                disabled=self.current_page == 0,
                style=discord.ButtonStyle.secondary
            )
            first_button.callback = self.first_page
            self.add_item(first_button)
            
            # Previous page button
            prev_button = discord.ui.Button(
                emoji="<a:leftarrow:1436993536196083752>",
                disabled=self.current_page == 0,
                style=discord.ButtonStyle.secondary
            )
            prev_button.callback = self.previous_page
            self.add_item(prev_button)
            
            # Page indicator (disabled button)
            page_button = discord.ui.Button(
                label=f"{self.current_page + 1}/{self.max_pages}",
                disabled=True,
                style=discord.ButtonStyle.secondary
            )
            self.add_item(page_button)
            
            # Next page button
            next_button = discord.ui.Button(
                emoji="<a:rightarrow:1436993512288817152>",
                disabled=self.current_page >= self.max_pages - 1,
                style=discord.ButtonStyle.secondary
            )
            next_button.callback = self.next_page
            self.add_item(next_button)
            
            # Last page button
            last_button = discord.ui.Button(
                emoji="<:right_arrow:1427472847294566513>",
                disabled=self.current_page >= self.max_pages - 1,
                style=discord.ButtonStyle.secondary
            )
            last_button.callback = self.last_page
            self.add_item(last_button)
    
    def create_embed(self, page):
        """Create embed for the current page"""
        start_idx = page * self.per_page
        end_idx = start_idx + self.per_page
        page_timezones = self.timezones[start_idx:end_idx]
        
        # Create title
        title = "🌍 All Available Timezones"
        if self.search:
            title += f" (Search: {self.search})"
        
        embed = discord.Embed(
            title=title,
            color=0x5865F2
        )
        
        # Add timezone list
        timezone_list = []
        for tz in page_timezones:
            # Get current time in this timezone for reference
            try:
                tz_obj = pytz.timezone(tz)
                now = datetime.now(tz_obj)
                time_str = now.strftime('%H:%M')
                sanitized_name = sanitize_timezone_name(tz)
                timezone_list.append(f"`{tz}` - {sanitized_name} ({time_str})")
            except:
                timezone_list.append(f"`{tz}`")
        
        embed.description = "\n".join(timezone_list)
        
        # Add footer with usage info
        embed.set_footer(
            text=f"Page {page + 1}/{self.max_pages} • Total: {len(self.timezones)} timezones • Use {self.prefix}tz set <timezone>"
        )
        
        return embed
    
    async def first_page(self, interaction):
        self.current_page = 0
        self.update_buttons()
        embed = self.create_embed(self.current_page)
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def previous_page(self, interaction):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            embed = self.create_embed(self.current_page)
            await interaction.response.edit_message(embed=embed, view=self)
    
    async def next_page(self, interaction):
        if self.current_page < self.max_pages - 1:
            self.current_page += 1
            self.update_buttons()
            embed = self.create_embed(self.current_page)
            await interaction.response.edit_message(embed=embed, view=self)
    
    async def last_page(self, interaction):
        self.current_page = self.max_pages - 1
        self.update_buttons()
        embed = self.create_embed(self.current_page)
        await interaction.response.edit_message(embed=embed, view=self)


class TimezoneSelectView(discord.ui.View):
    def __init__(self, tz_utils, target_id, is_guild=False):
        super().__init__(timeout=300)
        self.tz_utils = tz_utils
        self.target_id = target_id
        self.is_guild = is_guild
        self.current_page = 0
        
        # Get all timezones and organize them
        self.all_timezones = sorted(pytz.all_timezones)
        self.organize_timezones()
        
        # Add region selector first
        self.add_item(TimezoneRegionSelect(self))
        
        # Add common timezones by default
        self.add_item(TimezoneSelect(tz_utils, target_id, is_guild, self.common_timezones))
    
    def organize_timezones(self):
        """Organize timezones by region"""
        self.regions = {
            'Common': [
                'UTC', 'US/Eastern', 'US/Central', 'US/Mountain', 'US/Pacific',
                'Europe/London', 'Europe/Paris', 'Europe/Berlin', 'Asia/Tokyo',
                'Asia/Shanghai', 'Australia/Sydney'
            ],
            'Africa': [tz for tz in self.all_timezones if tz.startswith('Africa/')],
            'America': [tz for tz in self.all_timezones if tz.startswith('America/')],
            'Antarctica': [tz for tz in self.all_timezones if tz.startswith('Antarctica/')],
            'Arctic': [tz for tz in self.all_timezones if tz.startswith('Arctic/')],
            'Asia': [tz for tz in self.all_timezones if tz.startswith('Asia/')],
            'Atlantic': [tz for tz in self.all_timezones if tz.startswith('Atlantic/')],
            'Australia': [tz for tz in self.all_timezones if tz.startswith('Australia/')],
            'Europe': [tz for tz in self.all_timezones if tz.startswith('Europe/')],
            'Indian': [tz for tz in self.all_timezones if tz.startswith('Indian/')],
            'Pacific': [tz for tz in self.all_timezones if tz.startswith('Pacific/')],
            'US': [tz for tz in self.all_timezones if tz.startswith('US/')],
            'Other': [tz for tz in self.all_timezones if '/' not in tz or not any(tz.startswith(region + '/') for region in ['Africa', 'America', 'Antarctica', 'Arctic', 'Asia', 'Atlantic', 'Australia', 'Europe', 'Indian', 'Pacific', 'US'])]
        }
        
        # Remove empty regions
        self.regions = {k: v for k, v in self.regions.items() if v}
        
        # Set default to common
        self.common_timezones = self.regions['Common']
    
    def update_timezone_select(self, region_timezones):
        """Update the timezone selector with new region"""
        # Remove old timezone select (item at index 1)
        if len(self.children) > 1:
            self.children.pop(1)
        
        # Add new timezone select
        self.add_item(TimezoneSelect(self.tz_utils, self.target_id, self.is_guild, region_timezones))


class TimezoneRegionSelect(discord.ui.Select):
    def __init__(self, parent_view):
        self.parent_view = parent_view
        
        options = []
        for region, timezones in parent_view.regions.items():
            # Limit description length
            sample_zones = timezones[:3]
            description = ", ".join([tz.split('/')[-1] if '/' in tz else tz for tz in sample_zones])
            if len(timezones) > 3:
                description += f" (+{len(timezones) - 3} more)"
            
            options.append(discord.SelectOption(
                label=f"{region} ({len(timezones)} zones)",
                value=region,
                description=description[:100],  # Discord limit
                emoji="🌍" if region == "Common" else "🌏"
            ))
        
        super().__init__(
            placeholder="Choose a region to see timezones...",
            options=options,
            min_values=1,
            max_values=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        selected_region = self.values[0]
        region_timezones = self.parent_view.regions[selected_region]
        
        # Update the parent view
        self.parent_view.update_timezone_select(region_timezones)
        
        # Update the embed to show selected region
        embed = discord.Embed(
            title=f"🌍 Select Timezone - {selected_region}",
            description=f"Choose from {len(region_timezones)} timezones in the **{selected_region}** region:",
            color=0x5865F2
        )
        
        await interaction.response.edit_message(embed=embed, view=self.parent_view)

class TimezoneSelect(discord.ui.Select):
    def __init__(self, tz_utils, target_id, is_guild=False, timezones=None):
        self.tz_utils = tz_utils
        self.target_id = target_id
        self.is_guild = is_guild
        
        # Use provided timezones or default common ones
        if timezones:
            timezone_list = timezones
        else:
            timezone_list = [
                'UTC', 'US/Eastern', 'US/Central', 'US/Mountain', 'US/Pacific',
                'Europe/London', 'Europe/Paris', 'Europe/Berlin', 'Europe/Rome',
                'Asia/Tokyo', 'Asia/Seoul', 'Asia/Shanghai', 'Asia/Kolkata',
                'Australia/Sydney', 'America/Toronto', 'America/Sao_Paulo'
            ]
        
        # Create options from timezone list (limit to 25 for Discord)
        options = []
        for tz in timezone_list[:25]:  # Discord limit
            try:
                # Create a friendly description
                if '/' in tz:
                    region, city = tz.split('/', 1)
                    city_name = city.replace('_', ' ')
                    label = f"{city_name} ({region})"
                else:
                    label = tz
                
                # Get current time for this timezone
                tz_obj = pytz.timezone(tz)
                now = datetime.now(tz_obj)
                time_str = now.strftime('%H:%M')
                
                options.append(discord.SelectOption(
                    label=label[:100],  # Discord limit
                    value=tz,
                    description=f"{sanitize_timezone_name(tz)} - {time_str}"[:100]
                ))
            except:
                # Fallback for problematic timezones
                options.append(discord.SelectOption(
                    label=tz[:100],
                    value=tz,
                    description=f"Timezone: {tz}"[:100]
                ))
        
        super().__init__(
            placeholder="Choose your timezone...",
            options=options,
            min_values=1,
            max_values=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        selected_tz = self.values[0]
        
        # Sanitize timezone name for display (remove location information)
        sanitized_name = sanitize_timezone_name(selected_tz)
        
        try:
            if self.is_guild:
                await self.tz_utils.set_guild_timezone(self.target_id, selected_tz)
                embed = discord.Embed(
                    title="<a:verify:1436953625384452106> Server Timezone Updated",
                    description=f"Server timezone has been set to `{sanitized_name}`",
                    color=0x00FF00
                )
                # Show current time
                now = discord.utils.utcnow()
                current_time = await self.tz_utils.format_time_for_guild(now, self.target_id)
                embed.add_field(name="Current Server Time", value=f"`{current_time}`", inline=False)
            else:
                await self.tz_utils.set_user_timezone(self.target_id, selected_tz)
                embed = discord.Embed(
                    title="<a:verify:1436953625384452106> Timezone Updated",
                    description=f"Your timezone has been set to `{sanitized_name}`",
                    color=0x00FF00
                )
                # Show current time
                now = discord.utils.utcnow()
                current_time = await self.tz_utils.format_time_for_user(now, self.target_id)
                embed.add_field(name="Current Time", value=f"`{current_time}`", inline=False)
            
            await interaction.response.edit_message(embed=embed, view=None)
            
        except Exception as e:
            embed = discord.Embed(
                title="<a:wrong:1436953625384452106> Error",
                description=f"Failed to set timezone: {str(e)}",
                color=0xFF0000
            )
            await interaction.response.edit_message(embed=embed, view=None)

async def setup(bot):
    await bot.add_cog(TimezoneCommands(bot))