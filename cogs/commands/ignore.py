import discord
from discord.ext import commands
import aiosqlite
import os
import asyncio
from utils.Tools import *

class CategoryDropdown(discord.ui.Select):
    def __init__(self, categories, ignore_cog, guild_id, page=0):
        self.ignore_cog = ignore_cog
        self.guild_id = guild_id
        self.page = page
        self.total_pages = (len(categories) + 24) // 25  # 25 items per page
        
        # Get categories for this page
        start_idx = page * 25
        end_idx = start_idx + 25
        page_categories = categories[start_idx:end_idx]
        
        # Create options for the dropdown (max 25)
        options = []
        for category in page_categories:
            options.append(discord.SelectOption(
                label=category.title()[:100],  # Discord has a 100 char limit
                value=category,
                description=f"Ignore all commands in {category} category"[:100],
                emoji="🚫"
            ))
        
        # Add page info to placeholder
        placeholder = f"➕ Select categories to ignore... (Page {page + 1}/{self.total_pages})"
        
        super().__init__(
            placeholder=placeholder,
            min_values=1,
            max_values=min(len(options), 5),  # Allow selecting up to 5 at once
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        added_categories = []
        already_ignored = []
        
        async with aiosqlite.connect(self.ignore_cog.db_path) as db:
            for category in self.values:
                # Check if already ignored
                cursor = await db.execute(
                    "SELECT category_name FROM ignored_categories WHERE guild_id = ? AND category_name = ?", 
                    (self.guild_id, category)
                )
                if await cursor.fetchone():
                    already_ignored.append(category)
                else:
                    # Add to ignore list
                    await db.execute(
                        "INSERT INTO ignored_categories (guild_id, category_name) VALUES (?, ?)", 
                        (self.guild_id, category)
                    )
                    added_categories.append(category)
            
            await db.commit()
        
        # Create response
        embed = discord.Embed(color=self.ignore_cog.color)
        
        if added_categories:
            embed.add_field(
                name="✅ Added to Ignore List",
                value=", ".join([f"`{cat}`" for cat in added_categories]),
                inline=False
            )
        
        if already_ignored:
            embed.add_field(
                name="⚠️ Already Ignored",
                value=", ".join([f"`{cat}`" for cat in already_ignored]),
                inline=False
            )
        
        if not added_categories and not already_ignored:
            embed.description = "No categories were processed."
        
        await interaction.followup.send(embed=embed, ephemeral=True)

class CategoryRemoveDropdown(discord.ui.Select):
    def __init__(self, ignored_categories, ignore_cog, guild_id):
        self.ignore_cog = ignore_cog
        self.guild_id = guild_id
        
        # Create options for currently ignored categories
        options = []
        for category in ignored_categories[:25]:  # Discord limit is 25 options
            cat_name = category[0] if isinstance(category, tuple) else category
            options.append(discord.SelectOption(
                label=cat_name.title()[:100],
                value=cat_name,
                description=f"Remove {cat_name} from ignore list"[:100],
                emoji="✅"
            ))
        
        super().__init__(
            placeholder="➖ Select categories to remove from ignore list...",
            min_values=1,
            max_values=min(len(options), 5),
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        removed_categories = []
        
        async with aiosqlite.connect(self.ignore_cog.db_path) as db:
            for category in self.values:
                await db.execute(
                    "DELETE FROM ignored_categories WHERE guild_id = ? AND category_name = ?", 
                    (self.guild_id, category)
                )
                removed_categories.append(category)
            
            await db.commit()
        
        embed = discord.Embed(
            title="✅ Categories Removed",
            description=f"Removed {len(removed_categories)} categories from ignore list:\n" + 
                       ", ".join([f"`{cat}`" for cat in removed_categories]),
            color=self.ignore_cog.color
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)

class CategoryManagementView(discord.ui.View):
    def __init__(self, ignore_cog, guild_id, available_categories, ignored_categories, page=0):
        super().__init__(timeout=300)
        self.ignore_cog = ignore_cog
        self.guild_id = guild_id
        self.available_categories = available_categories
        self.ignored_categories = ignored_categories
        self.page = page
        self.total_pages = (len(available_categories) + 24) // 25
        
        # NOTE: Buttons are automatically added via @discord.ui.button decorators
        # They will be in row 0 by default
        
        # Add dropdown for adding categories (if there are available ones)
        # Place in row 1 to separate from buttons
        unignored_categories = [cat for cat in available_categories if cat not in [ig[0] if isinstance(ig, tuple) else ig for ig in ignored_categories]]
        if unignored_categories:
            add_dropdown = CategoryDropdown(unignored_categories, ignore_cog, guild_id, page)
            add_dropdown.placeholder = f"Add categories to ignore... (Page {page + 1}/{self.total_pages})"
            add_dropdown.row = 1  # Explicitly set row
            self.add_item(add_dropdown)
        
        # Add dropdown for removing categories (if there are ignored ones)
        # Place in row 2 to separate from add dropdown
        if ignored_categories:
            remove_dropdown = CategoryRemoveDropdown(ignored_categories, ignore_cog, guild_id)
            remove_dropdown.placeholder = "Remove categories from ignore list..."
            remove_dropdown.row = 2  # Explicitly set row
            self.add_item(remove_dropdown)
        
        # Update button states after adding all items
        self.update_button_states()

    def update_button_states(self):
        """Update the disabled state of pagination buttons based on current page"""
        # Find the previous and next buttons in the view
        for item in self.children:
            if isinstance(item, discord.ui.Button) and item.label:
                if "Previous" in item.label:
                    item.disabled = (self.page == 0)
                elif "Next" in item.label:
                    item.disabled = (self.page >= self.total_pages - 1)

    @discord.ui.button(label="Previous", emoji="<a:leftarrow:1436993536196083752>", style=discord.ButtonStyle.secondary, row=0)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            await self.update_view(interaction)

    @discord.ui.button(label="Next", emoji="<a:rightarrow:1436993512288817152>", style=discord.ButtonStyle.secondary, row=0)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < self.total_pages - 1:
            self.page += 1
            await self.update_view(interaction)

    @discord.ui.button(label="Refresh", emoji="<:refresh:1437499170087763968>", style=discord.ButtonStyle.secondary, row=0)
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        # Get updated data
        available_categories = self.ignore_cog.get_available_categories()
        
        async with aiosqlite.connect(self.ignore_cog.db_path) as db:
            cursor = await db.execute("SELECT category_name FROM ignored_categories WHERE guild_id = ?", (self.guild_id,))
            ignored_categories = await cursor.fetchall() if cursor else []
            ignored_categories = list(ignored_categories) if ignored_categories else []
        
        # Update stored data
        self.available_categories = available_categories
        self.ignored_categories = ignored_categories
        self.total_pages = (len(available_categories) + 24) // 25
        
        # Ensure page is within bounds after refresh
        if self.page >= self.total_pages:
            self.page = max(0, self.total_pages - 1)
        
        # Create updated embed
        embed = self.create_embed()
        
        # Create new view with updated data
        new_view = CategoryManagementView(self.ignore_cog, self.guild_id, available_categories, ignored_categories, self.page)
        
        await interaction.edit_original_response(embed=embed, view=new_view)

    async def update_view(self, interaction):
        await interaction.response.defer()
        
        # Update button states for current page
        self.update_button_states()
        
        # Create updated embed
        embed = self.create_embed()
        
        # Create new view with updated page
        new_view = CategoryManagementView(self.ignore_cog, self.guild_id, self.available_categories, self.ignored_categories, self.page)
        
        await interaction.edit_original_response(embed=embed, view=new_view)

    def create_embed(self):
        """Create the main embed with current page info"""
        start_idx = self.page * 25
        end_idx = start_idx + 25
        page_categories = self.available_categories[start_idx:end_idx]
        
        # Count dropdowns for debugging
        dropdown_info = []
        for item in self.children:
            if isinstance(item, discord.ui.Select) and item.placeholder:
                placeholder_lower = item.placeholder.lower()
                if "add" in placeholder_lower and "remove" not in placeholder_lower:
                    dropdown_info.append("<:plusu:1428164526884257852> Add Categories")
                elif "remove" in placeholder_lower:
                    dropdown_info.append("<a:wrong:1436956421110632489> Remove Categories")
        
        # Create description based on available actions
        actions_text = ', '.join(dropdown_info) if dropdown_info else 'None available'
        if not dropdown_info:
            if len(self.ignored_categories) == len(self.available_categories):
                actions_text = "All categories are ignored - use refresh to reload"
            elif not self.ignored_categories:
                actions_text = "No categories ignored yet - use the dropdown to add some"
        
        embed = discord.Embed(
            title=f"📋 Interactive Category Management (Page {self.page + 1}/{self.total_pages})",
            description=f"**Total Available Categories:** {len(self.available_categories)}\n"
                       f"**Currently Ignored:** {len(self.ignored_categories)}\n"
                       f"**Available Actions:** {actions_text}\n\n"
                       f"**Showing categories {start_idx + 1}-{min(end_idx, len(self.available_categories))} of {len(self.available_categories)}**\n"
                       f"Use the dropdowns below to manage categories.",
            color=self.ignore_cog.color
        )
        
        # Show categories on current page
        if page_categories:
            page_text = ", ".join([f"`{cat}`" for cat in page_categories[:15]])
            if len(page_categories) > 15:
                page_text += f"\n...and {len(page_categories) - 15} more on this page"
            
            embed.add_field(
                name=f"� Categories on Page {self.page + 1}",
                value=page_text,
                inline=False
            )
        
        if self.ignored_categories:
            ignored_text = ", ".join([f"`{cat[0]}`" for cat in self.ignored_categories[:8]])
            if len(self.ignored_categories) > 8:
                ignored_text += f"\n...and {len(self.ignored_categories) - 8} more"
            
            embed.add_field(
                name="🚫 Currently Ignored",
                value=ignored_text,
                inline=False
            )
        
        embed.set_footer(text=f"Sleepless Development • Page {self.page + 1}/{self.total_pages}")
        
        return embed

class Ignore(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        self.color = 0x185fe5
        self.db_path = "db/ignore.db"
        self.bot.loop.create_task(self.setup_database())
    
    async def setup_database(self):
        await asyncio.sleep(1)  # Small delay to ensure bot is ready
        os.makedirs('db', exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("CREATE TABLE IF NOT EXISTS ignored_commands (guild_id INTEGER, command_name TEXT)")
            await db.execute("CREATE TABLE IF NOT EXISTS ignored_channels (guild_id INTEGER, channel_id INTEGER)")
            await db.execute("CREATE TABLE IF NOT EXISTS ignored_users (guild_id INTEGER, user_id INTEGER)")
            await db.execute("CREATE TABLE IF NOT EXISTS bypassed_users (guild_id INTEGER, user_id INTEGER)")
            await db.execute("CREATE TABLE IF NOT EXISTS ignored_categories (guild_id INTEGER, category_name TEXT)")
            await db.execute("CREATE TABLE IF NOT EXISTS ignored_interactions (guild_id INTEGER, interaction_type TEXT)")
            await db.commit()

    @commands.group(name="ignore", help="Manage the ignore system for this guild.", invoke_without_command=True)
    @blacklist_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def _ignore(self, ctx):
        if ctx.subcommand_passed is None:
            await ctx.send_help(ctx.command)
            ctx.command.reset_cooldown(ctx)

    @_ignore.group(name="command", help="Manage ignored commands in this guild.", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def _command(self, ctx):
        if ctx.subcommand_passed is None:
            await ctx.send_help(ctx.command)
            ctx.command.reset_cooldown(ctx)

    @_command.command(name="add", help="Adds a command to the ignore list.")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    async def command_add(self, ctx: commands.Context, command_name: str):
        command_name_normalized = command_name.strip().lower()
        command = self.bot.get_command(command_name_normalized)
        if not command:
            embed = discord.Embed(title="<:feast_cross:1400143488695144609> Error", description=f"`{command_name}` is not a valid command.", color=self.color)
            await ctx.reply(embed=embed, mention_author=False)
            return
        if not ctx.guild:
            await ctx.reply("This command can only be used in a server.")
            return
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM ignored_commands WHERE guild_id = ?", (ctx.guild.id,))
            count = await cursor.fetchone() if cursor else (0,)
            if count and count[0] >= 25:
                embed = discord.Embed(description="You can only add up to 25 commands to the ignore list.", color=self.color)
                await ctx.reply(embed=embed)
                return
            cursor = await db.execute("SELECT command_name FROM ignored_commands WHERE guild_id = ? AND command_name = ?", (ctx.guild.id, command_name_normalized))
            result = await cursor.fetchone() if cursor else None
            if result:
                embed = discord.Embed(description=f"`{command_name}` is already in the ignore commands list.", color=self.color)
                await ctx.reply(embed=embed, mention_author=False)
            else:
                await db.execute("INSERT INTO ignored_commands (guild_id, command_name) VALUES (?, ?)", (ctx.guild.id, command_name_normalized))
                await db.commit()
                embed = discord.Embed(title="<:feast_tick:1400143469892210753> Success", description=f"Successfully added `{command_name}` to the ignore commands list.", color=self.color)
                await ctx.reply(embed=embed)

    @_command.command(name="remove", help="Removes a command from the ignore list.")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    async def command_remove(self, ctx: commands.Context, command_name: str):
        command_name_normalized = command_name.strip().lower()
        if not ctx.guild:
            await ctx.reply("This command can only be used in a server.")
            return
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT command_name FROM ignored_commands WHERE guild_id = ? AND command_name = ?", (ctx.guild.id, command_name_normalized))
            result = await cursor.fetchone() if cursor else None
            
            if not result:
                embed = discord.Embed(title="<:feast_cross:1400143488695144609> Error", description=f"`{command_name}` is not in the ignore commands list.", color=self.color)
                await ctx.reply(embed=embed)
            else:
                await db.execute("DELETE FROM ignored_commands WHERE guild_id = ? AND command_name = ?", (ctx.guild.id, command_name_normalized))
                await db.commit()
                embed = discord.Embed(title="<:feast_tick:1400143469892210753> Success", description=f"Successfully removed `{command_name}` from the ignore commands list.", color=self.color)
                await ctx.reply(embed=embed)

    @_command.command(name="show", help="Displays the list of ignored commands.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def command_show(self, ctx: commands.Context):
        if not ctx.guild:
            await ctx.reply("This command can only be used in a server.")
            return
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT command_name FROM ignored_commands WHERE guild_id = ?", (ctx.guild.id,))
            commands = await cursor.fetchall() if cursor else []
            
            if not commands:
                embed = discord.Embed(description="No commands are currently ignored in this server.", color=self.color)
                await ctx.reply(embed=embed, mention_author=False)
            else:
                entries = [f"`{command[0]}`" for command in commands]
                description = "\n".join(entries)
                embed = discord.Embed(title="Ignored Commands", description=description, color=self.color)
                await ctx.reply(embed=embed, mention_author=False)

    # Category management with exact help system categories
    def get_available_categories(self):
        """Get all available command categories from loaded cogs - matches help system exactly"""
        categories = set()
        
        # Exact categories from your help system
        exact_categories = [
            "Moderation Commands",
            "Sleepless Welcomer", 
            "VoiceMaster",
            "Voice Commands",
            "Vanity System",
            "Ticket System",
            "Ticket",
            "Sticky Messages", 
            "Server Commands",
            "Reaction Roles",
            "Enhanced Reaction Roles",
            "Music Commands",
            "Enhanced Music System",
            "Message Tracker", 
            "Message Tracking",
            "Logging",
            "Leveling Commands",
            "Global Leaderboard (GLB)",
            "Jail & Timeout",
            "Trackers",
            "Interactions",
            "Ignore Commands",
            "Giveaway Commands",
            "General Commands",
            "Games Commands",
            "Fun & AI Generation",
            "Last.fm (FM)",
            "Setup Guides"
        ]
        
        # Add all exact categories
        for category in exact_categories:
            categories.add(category.lower())
            
        # Also add cog names as categories for flexibility
        for cog_name in self.bot.cogs.keys():
            categories.add(cog_name.lower())
            
        # Add logical groupings for easier management
        logical_groups = [
            "moderation",
            "music", 
            "fun",
            "voice",
            "welcomer",
            "leveling",
            "tracking",
            "roles",
            "vanity",
            "tickets",
            "games",
            "utilities",
            "logging",
            "interactions"
        ]
        
        for group in logical_groups:
            categories.add(group)
            
        return sorted(list(categories))

    @_ignore.group(name="category", help="Manage ignored command categories in this guild.", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def _category(self, ctx):
        if ctx.subcommand_passed is None:
            await ctx.send_help(ctx.command)
            ctx.command.reset_cooldown(ctx)

    @_category.command(name="add", help="Adds a command category to the ignore list.")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    async def category_add(self, ctx: commands.Context, category_name: str):
        category_name_normalized = category_name.strip().lower()
        available_categories = self.get_available_categories()
        
        if category_name_normalized not in available_categories:
            embed = discord.Embed(
                title="<:feast_cross:1400143488695144609> Error", 
                description=f"`{category_name}` is not a valid category.\n\n**Available Categories:**\n" + 
                           ", ".join([f"`{cat}`" for cat in available_categories[:15]]) + 
                           (f"\n...and {len(available_categories)-15} more" if len(available_categories) > 15 else ""),
                color=self.color
            )
            await ctx.reply(embed=embed, mention_author=False)
            return
            
        if not ctx.guild:
            await ctx.reply("This command can only be used in a server.")
            return
            
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM ignored_categories WHERE guild_id = ?", (ctx.guild.id,))
            count = await cursor.fetchone() if cursor else (0,)
            if count and count[0] >= 15:
                embed = discord.Embed(description="You can only add up to 15 categories to the ignore list.", color=self.color)
                await ctx.reply(embed=embed)
                return
                
            cursor = await db.execute("SELECT category_name FROM ignored_categories WHERE guild_id = ? AND category_name = ?", (ctx.guild.id, category_name_normalized))
            result = await cursor.fetchone() if cursor else None
            if result:
                embed = discord.Embed(description=f"`{category_name}` category is already in the ignore list.", color=self.color)
                await ctx.reply(embed=embed, mention_author=False)
            else:
                await db.execute("INSERT INTO ignored_categories (guild_id, category_name) VALUES (?, ?)", (ctx.guild.id, category_name_normalized))
                await db.commit()
                embed = discord.Embed(title="<:feast_tick:1400143469892210753> Success", description=f"Successfully added `{category_name}` category to the ignore list.", color=self.color)
                await ctx.reply(embed=embed)

    @_category.command(name="remove", help="Removes a command category from the ignore list.")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    async def category_remove(self, ctx: commands.Context, category_name: str):
        category_name_normalized = category_name.strip().lower()
        if not ctx.guild:
            await ctx.reply("This command can only be used in a server.")
            return
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT category_name FROM ignored_categories WHERE guild_id = ? AND category_name = ?", (ctx.guild.id, category_name_normalized))
            result = await cursor.fetchone() if cursor else None
            
            if not result:
                embed = discord.Embed(title="<:feast_cross:1400143488695144609> Error", description=f"`{category_name}` category is not in the ignore list.", color=self.color)
                await ctx.reply(embed=embed)
            else:
                await db.execute("DELETE FROM ignored_categories WHERE guild_id = ? AND category_name = ?", (ctx.guild.id, category_name_normalized))
                await db.commit()
                embed = discord.Embed(title="<:feast_tick:1400143469892210753> Success", description=f"Successfully removed `{category_name}` category from the ignore list.", color=self.color)
                await ctx.reply(embed=embed)

    @_category.command(name="show", help="Displays the list of ignored categories.")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def category_show(self, ctx: commands.Context):
        if not ctx.guild:
            await ctx.reply("This command can only be used in a server.")
            return
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT category_name FROM ignored_categories WHERE guild_id = ?", (ctx.guild.id,))
            categories = await cursor.fetchall() if cursor else []
            
            if not categories:
                embed = discord.Embed(description="No categories are currently ignored in this server.", color=self.color)
                await ctx.reply(embed=embed, mention_author=False)
            else:
                entries = [f"`{category[0]}`" for category in categories]
                description = "\n".join(entries)
                embed = discord.Embed(title="Ignored Categories", description=description, color=self.color)
                await ctx.reply(embed=embed, mention_author=False)

    @_category.command(name="list", help="Shows all available categories with interactive management.")
    @blacklist_check()
    @ignore_check() 
    @commands.has_permissions(administrator=True)
    async def category_list(self, ctx: commands.Context):
        if not ctx.guild:
            await ctx.reply("This command can only be used in a server.")
            return
            
        available_categories = self.get_available_categories()
        
        # Get currently ignored categories
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT category_name FROM ignored_categories WHERE guild_id = ?", (ctx.guild.id,))
            ignored_categories = await cursor.fetchall() if cursor else []
            ignored_categories = list(ignored_categories) if ignored_categories else []
        
        # Create interactive view with pagination
        view = CategoryManagementView(self, ctx.guild.id, available_categories, ignored_categories, page=0)
        
        # Create initial embed
        embed = view.create_embed()
        
        # Check if there are any options available
        if not available_categories:
            embed.description = "No categories are available for management."
            await ctx.reply(embed=embed)
        else:
            await ctx.reply(embed=embed, view=view)

    @_ignore.command(name="status", help="Shows complete ignore status for this server.")
    @blacklist_check() 
    @ignore_check()
    @commands.has_permissions(administrator=True)
    async def ignore_status(self, ctx: commands.Context):
        if not ctx.guild:
            await ctx.reply("This command can only be used in a server.")
            return
            
        async with aiosqlite.connect(self.db_path) as db:
            # Get counts for each type
            stats = {}
            
            cursor = await db.execute("SELECT COUNT(*) FROM ignored_commands WHERE guild_id = ?", (ctx.guild.id,))
            result = await cursor.fetchone()
            stats['commands'] = result[0] if result else 0
            
            cursor = await db.execute("SELECT COUNT(*) FROM ignored_categories WHERE guild_id = ?", (ctx.guild.id,))
            result = await cursor.fetchone()
            stats['categories'] = result[0] if result else 0
            
            cursor = await db.execute("SELECT COUNT(*) FROM ignored_channels WHERE guild_id = ?", (ctx.guild.id,))
            result = await cursor.fetchone()
            stats['channels'] = result[0] if result else 0
            
            cursor = await db.execute("SELECT COUNT(*) FROM ignored_users WHERE guild_id = ?", (ctx.guild.id,))
            result = await cursor.fetchone()
            stats['users'] = result[0] if result else 0
            
            cursor = await db.execute("SELECT COUNT(*) FROM bypassed_users WHERE guild_id = ?", (ctx.guild.id,))
            result = await cursor.fetchone()
            stats['bypassed'] = result[0] if result else 0
            
        embed = discord.Embed(title="📊 Ignore System Status", color=self.color)
        
        status_text = f"""
        **Commands Ignored:** {stats['commands']}/25
        **Categories Ignored:** {stats['categories']}/15
        **Channels Ignored:** {stats['channels']}/30
        **Users Ignored:** {stats['users']}/30
        **Bypassed Users:** {stats['bypassed']}/30
        """
        
        embed.description = status_text
        
        total_ignored = sum([stats['commands'], stats['categories'], stats['channels'], stats['users']])
        if total_ignored > 0:
            embed.add_field(name="🔒 Total Active Restrictions", value=total_ignored, inline=True)
        else:
            embed.add_field(name="✅ Status", value="No restrictions active", inline=True)
            
        embed.set_footer(text="Use $ignore <type> show to see specific lists")
        await ctx.reply(embed=embed)

async def setup(bot):
    await bot.add_cog(Ignore(bot))