import discord
from discord.ext import commands, tasks
import sqlite3
import os

from utils.error_helpers import StandardErrorHandler
DB_PATH = "db/bvanityroles.db"

class BVanityRoles(commands.Cog):
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot
        self.conn = self.connect_db()
        self.check_vanity.start()

    def cog_unload(self):
        self.check_vanity.cancel()
        self.conn.close()

    def connect_db(self):
        os.makedirs("db", exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vanity_roles (
                guild_id INTEGER PRIMARY KEY,
                log_channel_id INTEGER,
                role_id INTEGER
            )
        """)
        conn.commit()
        return conn

    def set_config(self, guild_id, log_channel_id, role_id):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO vanity_roles (guild_id, log_channel_id, role_id)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                log_channel_id=excluded.log_channel_id,
                role_id=excluded.role_id
        """, (guild_id, log_channel_id, role_id))
        self.conn.commit()

    def get_config(self, guild_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT log_channel_id, role_id FROM vanity_roles WHERE guild_id=?", (guild_id,))
        return cursor.fetchone()

    def delete_config(self, guild_id):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM vanity_roles WHERE guild_id=?", (guild_id,))
        self.conn.commit()

    @commands.group(name="bvanityroles", invoke_without_command=True)
    async def bvanityroles(self, ctx):
        await ctx.send("Available subcommands: `setup`, `reset`, `show`")

    @bvanityroles.command()
    async def setup(self, ctx, log_channel: discord.TextChannel, role: discord.Role):
        self.set_config(ctx.guild.id, log_channel.id, role.id)
        await ctx.send("✅ Vanity role setup complete.")

    @bvanityroles.command()
    async def reset(self, ctx):
        if self.get_config(ctx.guild.id):
            self.delete_config(ctx.guild.id)
            await ctx.send("✅ Vanity role setup has been reset.")
        else:
            await ctx.send("⚠️ No vanity setup found for this server.")

    @bvanityroles.command()
    async def show(self, ctx):
        config = self.get_config(ctx.guild.id)
        if config:
            log_channel = self.bot.get_channel(config[0])
            role = ctx.guild.get_role(config[1])
            embed = discord.Embed(title="Vanity Role Settings", color=discord.Color.blue())
            embed.add_field(name="Log Channel", value=log_channel.mention if log_channel else "Not Found", inline=False)
            embed.add_field(name="Role", value=role.mention if role else "Not Found", inline=False)
            await ctx.send(embed=embed)
        else:
            await ctx.send("⚠️ No vanity setup found for this server.")

    @tasks.loop(minutes=10)
    async def check_vanity(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT guild_id, log_channel_id, role_id FROM vanity_roles")
        rows = cursor.fetchall()

        for guild_id, log_channel_id, role_id in rows:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue

            role = guild.get_role(role_id)
            log_channel = self.bot.get_channel(log_channel_id)

            for member in guild.members:
                try:
                    bio_data = await self.bot.http.get_user_profile(member.id)
                    bio = bio_data.get("bio", "")
                    if "#vanity" in bio and role not in member.roles:
                        await member.add_roles(role, reason="Bio contains #vanity")
                        if log_channel:
                            await log_channel.send(f"✅ Gave {member.mention} the role for having `#vanity` in their bio.")
                    elif "#vanity" not in bio and role in member.roles:
                        await member.remove_roles(role, reason="Removed #vanity from bio")
                        if log_channel:
                            await log_channel.send(f"❌ Removed {member.mention}'s role (no `#vanity` in bio).")
                except Exception:
                    continue  # silently fail to avoid API spam

def setup(bot):
    bot.add_cog(BVanityRoles(bot))
