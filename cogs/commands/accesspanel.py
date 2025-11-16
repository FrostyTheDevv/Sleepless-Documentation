import discord
from discord.ext import commands
import aiosqlite

VERIFY_DB_PATH = 'db/verify.db'

class AccessPanel(commands.Cog):
    @commands.Cog.listener()
    async def on_member_join(self, member):
        config = await self.get_config(member.guild.id)
        if not config or not config["enabled"]:
            return
        # Bypass check
        bypass_roles = [int(r) for r in (config["bypass_roles"] or "").split(",") if r]
        if any(role.id in bypass_roles for role in member.roles):
            return
        # Remove access role if present (not verified yet)
        access_role = member.guild.get_role(config["access_role"]) if config["access_role"] else None
        if access_role and access_role in member.roles:
            try:
                await member.remove_roles(access_role, reason="Verification required")
            except Exception:
                pass
        # Optionally DM user with instructions
        try:
            await member.send(f"Welcome to {member.guild.name}! Please verify in the verification channel to gain access.")
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        config = await self.get_config(member.guild.id)
        if not config or not config["enabled"]:
            return
        await self.log_event(member.guild.id, member.id, "left")

    async def verify_captcha(self, interaction: discord.Interaction):
        guild = interaction.guild
        member = guild.get_member(interaction.user.id) if guild else None
        if not guild or not member:
            await interaction.response.send_message("Could not resolve your member context.", ephemeral=True)
            return
        config = await self.get_config(guild.id)
        if not config or not config["enabled"]:
            await interaction.response.send_message("Verification is not enabled.", ephemeral=True)
            return
        # Placeholder: In a real implementation, present a captcha challenge here
        # For now, just grant the role as if captcha was solved
        bypass_roles = [int(r) for r in (config["bypass_roles"] or "").split(",") if r]
        if any(role.id in bypass_roles for role in member.roles):
            await interaction.response.send_message("You are already verified.", ephemeral=True)
            return
        access_role = guild.get_role(config["access_role"]) if config["access_role"] else None
        if not access_role:
            await interaction.response.send_message("Access role is not set. Please contact an admin.", ephemeral=True)
            return
        try:
            # TODO: Implement actual captcha challenge and validation here
            await member.add_roles(access_role, reason="Verified via Captcha")
            await self.log_event(guild.id, member.id, "verified_captcha")
            await interaction.response.send_message(f"Captcha solved! You have been verified and given {access_role.mention}.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("I lack permission to give you the access role. Please contact an admin.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Verification failed: {e}", ephemeral=True)

    async def log_event(self, guild_id, user_id, action):
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        async with aiosqlite.connect(VERIFY_DB_PATH) as db:
            await db.execute("INSERT INTO verify_logs (guild_id, user_id, action, timestamp) VALUES (?, ?, ?, ?)", (guild_id, user_id, action, now))
            await db.commit()
        config = await self.get_config(guild_id)
        if config and config["log_channel"]:
            guild = self.bot.get_guild(guild_id)
            channel = guild.get_channel(config["log_channel"])
            if channel:
                try:
                    user = guild.get_member(user_id)
                    await channel.send(f"[Verification] {user.mention if user else user_id} {action} at {now}")
                except Exception:
                    pass
    @commands.group(name="verifyconfig", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def verifyconfig(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @verifyconfig.command(name="enable")
    @commands.has_permissions(administrator=True)
    async def enable(self, ctx):
        await self.set_config(ctx.guild.id, enabled=1)
        await ctx.send(":white_check_mark: Verification system enabled.")

    @verifyconfig.command(name="disable")
    @commands.has_permissions(administrator=True)
    async def disable(self, ctx):
        await self.set_config(ctx.guild.id, enabled=0)
        await ctx.send(":x: Verification system disabled.")

    @verifyconfig.command(name="type")
    @commands.has_permissions(administrator=True)
    async def set_type(self, ctx, verify_type: str):
        if verify_type not in ("button", "captcha"):
            await ctx.send("Type must be 'button' or 'captcha'.")
            return
        await self.set_config(ctx.guild.id, verify_type=verify_type)
        await ctx.send(f"Verification type set to `{verify_type}`.")

    @verifyconfig.command(name="role")
    @commands.has_permissions(administrator=True)
    async def set_role(self, ctx, role: discord.Role):
        await self.set_config(ctx.guild.id, access_role=role.id)
        await ctx.send(f"Access role set to {role.mention}.")

    @verifyconfig.command(name="bypass")
    @commands.has_permissions(administrator=True)
    async def set_bypass(self, ctx, *roles: discord.Role):
        role_ids = [str(r.id) for r in roles]
        await self.set_config(ctx.guild.id, bypass_roles=",".join(role_ids))
        await ctx.send(f"Bypass roles set: {' '.join(r.mention for r in roles)}")

    @verifyconfig.command(name="log")
    @commands.has_permissions(administrator=True)
    async def set_log(self, ctx, channel: discord.TextChannel):
        await self.set_config(ctx.guild.id, log_channel=channel.id)
        await ctx.send(f"Log channel set to {channel.mention}.")

    @commands.command(name="verifypanel")
    @commands.has_permissions(administrator=True)
    async def verifypanel(self, ctx):
        config = await self.get_config(ctx.guild.id)
        if not config or not config["enabled"]:
            await ctx.send("Verification system is not enabled.")
            return
        verify_type = config["verify_type"]
        if verify_type == "button":
            view = self.VerificationButtonView(self)
            await ctx.send("Click the button below to verify:", view=view)
        elif verify_type == "captcha":
            view = self.VerificationCaptchaView(self)
            await ctx.send("Solve the captcha below to verify:", view=view)

    async def set_config(self, guild_id, **kwargs):
        async with aiosqlite.connect(VERIFY_DB_PATH) as db:
            # Get current config
            async with db.execute("SELECT * FROM verify_config WHERE guild_id = ?", (guild_id,)) as cursor:
                row = await cursor.fetchone()
            # Build update
            columns = []
            values = []
            for k, v in kwargs.items():
                columns.append(f"{k} = ?")
                values.append(v)
            if row:
                await db.execute(f"UPDATE verify_config SET {', '.join(columns)} WHERE guild_id = ?", (*values, guild_id))
            else:
                # Insert with defaults, then update
                await db.execute("INSERT INTO verify_config (guild_id) VALUES (?)", (guild_id,))
                await db.execute(f"UPDATE verify_config SET {', '.join(columns)} WHERE guild_id = ?", (*values, guild_id))
            await db.commit()

    async def get_config(self, guild_id):
        async with aiosqlite.connect(VERIFY_DB_PATH) as db:
            async with db.execute("SELECT enabled, verify_type, access_role, bypass_roles, log_channel FROM verify_config WHERE guild_id = ?", (guild_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        "enabled": row[0],
                        "verify_type": row[1],
                        "access_role": row[2],
                        "bypass_roles": row[3],
                        "log_channel": row[4],
                    }
                return None

    # Placeholder views for verification (to be implemented next)
    class VerificationButtonView(discord.ui.View):
        def __init__(self, cog):
            super().__init__(timeout=None)
            self.cog = cog
            self.add_item(self.VerifyButton(self))

        class VerifyButton(discord.ui.Button):
            def __init__(self, parent_view):
                super().__init__(label="Verify", style=discord.ButtonStyle.success)
                self.parent_view = parent_view
            async def callback(self, interaction: discord.Interaction):
                # Call verify_user if it exists, else fallback to verify_captcha for now
                if hasattr(self.parent_view.cog, "verify_user"):
                    await self.parent_view.cog.verify_user(interaction)
                else:
                    await self.parent_view.cog.verify_captcha(interaction)

    class VerificationCaptchaView(discord.ui.View):
        def __init__(self, cog):
            super().__init__(timeout=None)
            self.cog = cog
            self.add_item(self.CaptchaButton(self))

        class CaptchaButton(discord.ui.Button):
            def __init__(self, parent_view):
                super().__init__(label="Solve Captcha", style=discord.ButtonStyle.primary)
                self.parent_view = parent_view
            async def callback(self, interaction: discord.Interaction):
                await self.parent_view.cog.verify_captcha(interaction)
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        await self.create_tables()

    async def create_tables(self):
        async with aiosqlite.connect(VERIFY_DB_PATH) as db:
            await db.execute('''
            CREATE TABLE IF NOT EXISTS verify_config (
                guild_id INTEGER PRIMARY KEY,
                enabled INTEGER NOT NULL DEFAULT 0,
                verify_type TEXT NOT NULL DEFAULT 'button',
                access_role INTEGER,
                bypass_roles TEXT,
                log_channel INTEGER
            )
            ''')
            await db.execute('''
            CREATE TABLE IF NOT EXISTS verify_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                user_id INTEGER,
                action TEXT,
                timestamp TEXT
            )
            ''')
            await db.commit()

    # ...admin commands, verification panel, event listeners, and verification logic will be added here...

async def setup(bot):
    await bot.add_cog(AccessPanel(bot))
