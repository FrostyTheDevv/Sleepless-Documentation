import discord
from discord.ext import commands
import sqlite3
import os

from utils.error_helpers import StandardErrorHandler
class ButtonRoles(commands.Cog):
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot
        os.makedirs("db", exist_ok=True)
        self.db = "db/br.db"
        self._create_table()

    def _create_table(self):
        with sqlite3.connect(self.db) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS button_roles (
                    guild_id INTEGER,
                    message_id INTEGER,
                    custom_id TEXT,
                    role_id INTEGER
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS br_settings (
                    guild_id INTEGER PRIMARY KEY,
                    dm_enabled INTEGER DEFAULT 1
                )
            """)

    def add_button_role(self, guild_id, message_id, custom_id, role_id):
        with sqlite3.connect(self.db) as conn:
            conn.execute(
                "INSERT INTO button_roles (guild_id, message_id, custom_id, role_id) VALUES (?, ?, ?, ?)",
                (guild_id, message_id, custom_id, role_id)
            )
            conn.commit()

    def get_dm_setting(self, guild_id):
        with sqlite3.connect(self.db) as conn:
            cur = conn.execute("SELECT dm_enabled FROM br_settings WHERE guild_id = ?", (guild_id,))
            row = cur.fetchone()
            return row[0] == 1 if row else True

    def set_dm_setting(self, guild_id, value):
        with sqlite3.connect(self.db) as conn:
            conn.execute("REPLACE INTO br_settings (guild_id, dm_enabled) VALUES (?, ?)", (guild_id, value))
            conn.commit()

    @commands.command(
        name="createbr",
        help="Create a button role or add a button to an existing message.",
        usage="createbr <label> <role> <channel> [message_id]"
    )
    @commands.has_permissions(manage_roles=True)
    async def createbr(self, ctx, label: str, role: discord.Role, channel: discord.TextChannel, message_id: int | None = None):
        dm_enabled = self.get_dm_setting(ctx.guild.id)
        custom_id = f"br_{ctx.guild.id}_{role.id}"

        class RoleButton(discord.ui.Button):
            def __init__(self, custom_id, label, role, dm_enabled):
                super().__init__(style=discord.ButtonStyle.primary, label=label, custom_id=custom_id)
                self.role = role
                self.dm_enabled = dm_enabled

            async def callback(self, interaction: discord.Interaction):
                member = interaction.user
                # Ensure member is a discord.Member, not just a User
                if not isinstance(member, discord.Member):
                    if interaction.guild is not None:
                        member = await interaction.guild.fetch_member(member.id)
                    else:
                        await interaction.response.send_message("<:feast_cross:1400143488695144609> Guild not found.", ephemeral=True)
                        return
                role_obj = interaction.guild.get_role(self.role.id) if interaction.guild else None
                if role_obj is None:
                    await interaction.response.send_message("<:feast_cross:1400143488695144609> Role not found.", ephemeral=True)
                    return
                if hasattr(member, "roles") and role_obj in getattr(member, "roles", []):
                    await member.remove_roles(role_obj, reason="Button role removed")
                    action = "removed from"
                else:
                    await member.add_roles(role_obj, reason="Button role added")
                    action = "added to"

                if self.dm_enabled:
                    try:
                        guild_name = interaction.guild.name if interaction.guild else "the server"
                        await member.send(f"<:feast_tick:1400143469892210753> Role **{role_obj.name}** has been {action} you in {guild_name}.")
                    except discord.Forbidden:
                        pass

                await interaction.response.send_message(f"<:feast_tick:1400143469892210753> Role **{role_obj.name}** {action} you.", ephemeral=True)

        view = discord.ui.View(timeout=None)
        view.add_item(RoleButton(custom_id, label, role, dm_enabled))

        if message_id:
            try:
                message = await channel.fetch_message(message_id)
                if message.components:
                    existing_view = discord.ui.View.from_message(message)
                    for item in view.children:
                        existing_view.add_item(item)
                    view = existing_view
                await message.edit(view=view)
            except discord.NotFound:
                await ctx.send("<:feast_cross:1400143488695144609> Message not found.")
                return
        else:
            message = await channel.send(f"Click the button to get the **{role.name}** role!", view=view)

        self.add_button_role(ctx.guild.id, message.id, custom_id, role.id)
        await ctx.send(f"<:feast_tick:1400143469892210753> Button role **{role.name}** added.", delete_after=5)

    @commands.command(
        name="dmbr",
        help="Enable or disable DM messages for button roles.",
        usage="dmbr <enable|disable>"
    )
    @commands.has_permissions(manage_guild=True)
    async def dmbr(self, ctx, mode: str):
        if mode.lower() not in ["enable", "disable"]:
            await ctx.send("<:feast_cross:1400143488695144609> Use `enable` or `disable`.")
            return

        value = 1 if mode.lower() == "enable" else 0
        self.set_dm_setting(ctx.guild.id, value)
        await ctx.send(f"<:feast_tick:1400143469892210753> DM messages for button roles {'enabled' if value else 'disabled'}.")

async def setup(bot):
    await bot.add_cog(ButtonRoles(bot))
