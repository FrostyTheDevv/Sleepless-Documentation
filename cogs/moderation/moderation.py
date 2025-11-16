# cogs/moderation.py
from __future__ import annotations

import asyncio
import re
from collections import Counter
from typing import Optional, Iterable, Tuple, Union, cast

import aiohttp
import discord
from discord.ext import commands
from discord.ui import Button, View

# ─────────────────────────────────────────────────────────────────────────────
# Helpers & Utilities
# ─────────────────────────────────────────────────────────────────────────────

DURATION_RE = re.compile(r"(\d+)([smhd])", re.I)
UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def parse_duration(spec: str) -> int:
    """
    Parse durations like "10s", "5m", "2h", "1d" (and combos like "1h30m").
    Returns total seconds (int). Raises commands.BadArgument on invalid input.
    """
    if not spec:
        raise commands.BadArgument("Duration cannot be empty.")
    total = 0
    for amount, unit in DURATION_RE.findall(spec.lower()):
        try:
            total += int(amount) * UNIT_SECONDS[unit]
        except KeyError:
            raise commands.BadArgument(f"Invalid unit '{unit}'. Use s|m|h|d.")
        except ValueError:
            raise commands.BadArgument(f"Invalid number '{amount}'.")
    if total <= 0:
        raise commands.BadArgument("Duration must be greater than zero.")
    return total


async def do_removal(
    ctx: commands.Context,
    limit: int,
    predicate,
    *,
    before: Optional[int] = None,
    after: Optional[int] = None,
):
    """
    Safe purge helper with feedback. `predicate(message) -> bool`.
    """
    if limit > 2000:
        return await ctx.reply(f"Too many messages to search given ({limit}/2000).")

    before_obj = ctx.message if before is None else discord.Object(id=before)
    after_obj = None if after is None else discord.Object(id=after)

    channel = getattr(ctx, "channel", None)
    if not isinstance(channel, discord.TextChannel):
        return await ctx.reply("This command can only be used in server text channels.")
    try:
        deleted = await channel.purge(
            limit=limit, before=before_obj, after=after_obj, check=predicate
        )
    except discord.Forbidden:
        return await ctx.reply("I lack permission to delete messages here.")
    except discord.HTTPException as e:
        return await ctx.reply(f"HTTP error: {e} (try a smaller search?)")

    spammers = Counter(m.author.display_name for m in deleted)
    count = len(deleted)

    lines = [f"✅ {count} message{' was' if count==1 else 's were'} removed."]
    if count:
        lines.append("")
        for name, c in sorted(spammers.items(), key=lambda t: t[1], reverse=True):
            lines.append(f"**{name}**: {c}")

    out = "\n".join(lines)
    if len(out) > 2000:
        await ctx.send(f"✅ Successfully removed {count} messages.", delete_after=7)
    else:
        await ctx.send(out, delete_after=7)


def can_manage_member(executor: discord.Member, target: discord.Member, *, allow_owner: bool = True) -> bool:
    """Hierarchy guard: returns True if executor can act on target."""
    if allow_owner and executor.guild and executor == executor.guild.owner:
        return True
    return executor.top_role > target.top_role


def bot_above_role(guild: discord.Guild, role: discord.Role) -> bool:
    me = guild.me
    return bool(me and me.top_role > role)


def default_role(guild: discord.Guild) -> discord.Role:
    return guild.default_role


# ─────────────────────────────────────────────────────────────────────────────
# Main Cog
# ─────────────────────────────────────────────────────────────────────────────

class Moderation(commands.Cog):
    """Moderation commands with safe checks & confirmations."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.color = 0x006FB9

    # ── Comprehensive Network Diagnostics Command ────────────────────────────────────
    @commands.command(name="ping", aliases=["latency", "network", "diagnostics"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def ping(self, ctx: commands.Context):
        """Comprehensive network diagnostics including websocket, API, and internet connectivity"""
        import aiohttp
        import time
        import asyncio
        import psutil
        from datetime import datetime, timezone
        
        # Initial response
        embed = discord.Embed(
            title="🔄 Running Network Diagnostics...",
            description="Testing connectivity and performance metrics",
            color=0xff9900
        )
        message = await ctx.reply(embed=embed)
        
        start_time = time.perf_counter()
        
        # Test results storage
        results = {}
        
        try:
            # 1. Discord WebSocket Latency
            ws_latency = round(self.bot.latency * 1000, 2) if self.bot.latency else 0
            results['websocket'] = ws_latency
            
            # 2. Bot Response Time (Edit Latency)
            edit_start = time.perf_counter()
            temp_embed = discord.Embed(title="🔄 Testing response time...", color=0xff9900)
            await message.edit(embed=temp_embed)
            edit_latency = round((time.perf_counter() - edit_start) * 1000, 2)
            results['response'] = edit_latency
            
            # 3. Database Latency Test
            db_start = time.perf_counter()
            try:
                import aiosqlite
                async with aiosqlite.connect("db/afk.db") as db:
                    cursor = await db.execute("SELECT 1")
                    await cursor.fetchone()
                db_latency = round((time.perf_counter() - db_start) * 1000, 2)
                results['database'] = db_latency
            except Exception as e:
                results['database'] = f"Error: {str(e)[:20]}..."
            
            # 4. Discord API Test (Get guild info)
            api_start = time.perf_counter()
            try:
                # This forces an API call
                if ctx.guild:
                    guild_data = await self.bot.http.get_guild(ctx.guild.id)
                    api_latency = round((time.perf_counter() - api_start) * 1000, 2)
                    results['discord_api'] = api_latency
                else:
                    results['discord_api'] = "DM Channel"
            except Exception as e:
                results['discord_api'] = f"Error: {str(e)[:20]}..."
            
            # 5. External Internet Test (Multiple endpoints)
            internet_tests = []
            test_urls = [
                ("Discord CDN", "https://cdn.discordapp.com/embed/avatars/0.png"),
                ("Google DNS", "https://dns.google/resolve?name=discord.com&type=A"),
                ("Cloudflare", "https://1.1.1.1/cdn-cgi/trace")
            ]
            
            async def test_url(name, url):
                try:
                    url_start = time.perf_counter()
                    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                        async with session.get(url) as response:
                            if response.status == 200:
                                latency = round((time.perf_counter() - url_start) * 1000, 2)
                                return (name, latency, "✅")
                            else:
                                return (name, f"HTTP {response.status}", "⚠️")
                except asyncio.TimeoutError:
                    return (name, "Timeout (>5s)", "❌")
                except Exception as e:
                    return (name, f"Error: {str(e)[:15]}...", "❌")
            
            # Run internet tests concurrently
            internet_results = await asyncio.gather(*[test_url(name, url) for name, url in test_urls])
            results['internet'] = internet_results
            
            # 6. System Performance Metrics
            try:
                cpu_percent = psutil.cpu_percent(interval=0.1)
                memory = psutil.virtual_memory()
                results['system'] = {
                    'cpu': cpu_percent,
                    'memory_used': round(memory.percent, 1),
                    'memory_available': round(memory.available / (1024**3), 2)  # GB
                }
            except ImportError:
                results['system'] = "psutil not available"
            
            total_time = round((time.perf_counter() - start_time) * 1000, 2)
            
            # Build comprehensive results embed
            final_embed = discord.Embed(
                title="📊 Network Diagnostics Complete",
                description=f"All tests completed in **{total_time}ms**",
                color=0x00ff00,
                timestamp=datetime.now(timezone.utc)
            )
            
            # Discord Connectivity
            discord_status = "🟢 Excellent" if ws_latency < 100 else "🟡 Good" if ws_latency < 200 else "🔴 Poor"
            final_embed.add_field(
                name="🔗 Discord Connectivity",
                value=f"**WebSocket:** {ws_latency}ms {discord_status}\n"
                      f"**API Response:** {results.get('discord_api', 'N/A')}ms\n"
                      f"**Edit Latency:** {edit_latency}ms",
                inline=True
            )
            
            # Database Performance
            db_info = results.get('database', 'N/A')
            db_status = "🟢" if isinstance(db_info, (int, float)) and db_info < 50 else "🟡" if isinstance(db_info, (int, float)) and db_info < 100 else "🔴"
            final_embed.add_field(
                name="💾 Database Performance",
                value=f"**Query Time:** {db_info}ms {db_status}",
                inline=True
            )
            
            # Internet Connectivity
            internet_text = ""
            for name, latency, status in internet_results:
                internet_text += f"**{name}:** {latency}ms {status}\n"
            final_embed.add_field(
                name="🌐 Internet Connectivity",
                value=internet_text,
                inline=True
            )
            
            # System Resources (if available)
            sys_info = results.get('system')
            if isinstance(sys_info, dict):
                cpu_status = "🟢" if sys_info['cpu'] < 50 else "🟡" if sys_info['cpu'] < 80 else "🔴"
                mem_status = "🟢" if sys_info['memory_used'] < 70 else "🟡" if sys_info['memory_used'] < 85 else "🔴"
                
                final_embed.add_field(
                    name="🖥️ System Performance",
                    value=f"**CPU Usage:** {sys_info['cpu']}% {cpu_status}\n"
                          f"**Memory:** {sys_info['memory_used']}% {mem_status}\n"
                          f"**Available:** {sys_info['memory_available']}GB",
                    inline=True
                )
            
            # Performance Summary
            avg_latency = ws_latency
            if avg_latency < 100:
                performance = "🚀 Excellent Performance"
                color = 0x00ff00
            elif avg_latency < 200:
                performance = "✅ Good Performance"
                color = 0xffff00
            else:
                performance = "⚠️ Poor Performance"
                color = 0xff0000
            
            final_embed.color = color
            final_embed.add_field(
                name="📈 Overall Status",
                value=f"{performance}\n**Average Response:** {avg_latency}ms",
                inline=False
            )
            
            final_embed.set_footer(
                text=f"Shard {ctx.guild.shard_id if ctx.guild else 0} • Tested from Unknown Region",
                icon_url=self.bot.user.display_avatar.url if self.bot.user else None
            )
            
            await message.edit(embed=final_embed)
            
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Diagnostics Failed",
                description=f"An error occurred during testing: {str(e)}",
                color=0xff0000
            )
            await message.edit(embed=error_embed)

    # ── Lock/Unlock all channels (confirm) ───────────────────────────────────
    @commands.hybrid_command(name="lockall", help="Lock all channels (deny @everyone from sending/connecting).")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 15, commands.BucketType.channel)
    async def lockall(self, ctx: commands.Context):
        guild = getattr(ctx, "guild", None)
        if not isinstance(guild, discord.Guild):
            return await ctx.reply("This command can only be used in a server.")
        me = getattr(guild, "me", None)
        author = ctx.author
        if not (isinstance(author, discord.Member) and isinstance(me, discord.Member) and hasattr(guild, "owner") and guild.owner and (author == guild.owner or (author.top_role and me.top_role and author.top_role > me.top_role))):
            return await ctx.reply("⚠️ Your top role must be above my top role to run this.", ephemeral=False)
        if not (me and me.guild_permissions and me.guild_permissions.manage_roles):
            return await ctx.reply("⚠️ I need **Manage Roles** to change permission overwrites.")
        confirm = Button(label="Confirm", style=discord.ButtonStyle.success)
        cancel = Button(label="Cancel", style=discord.ButtonStyle.danger)
        view = View(timeout=30)
        view.add_item(confirm)
        view.add_item(cancel)
        async def on_confirm(interaction: discord.Interaction):
            if interaction.user.id != author.id:
                return await interaction.response.send_message("This confirmation isn't for you.", ephemeral=True)
            await interaction.response.defer(thinking=True)
            changed = await self._apply_lock(guild, lock=True)
            await interaction.followup.send(f"✅ Locked {changed} channel{'s' if changed!=1 else ''}.", ephemeral=False)
            view.stop()
        async def on_cancel(interaction: discord.Interaction):
            if interaction.user.id != author.id:
                return await interaction.response.send_message("This confirmation isn't for you.", ephemeral=True)
            await interaction.response.edit_message(content="❎ Cancelled.", view=None)
            view.stop()
        confirm.callback = on_confirm
        cancel.callback = on_cancel
        embed = discord.Embed(
            color=self.color,
            description=f"**Lock all channels** in **{guild.name}**?\n"
                        f"- Text/Forum/Threads → deny `Send Messages`\n"
                        f"- Voice/Stage → deny `Connect`",
        )
        await ctx.reply(embed=embed, view=view, mention_author=False)

    @commands.hybrid_command(name="unlockall", help="Unlock all channels (restore @everyone send/connect).")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 15, commands.BucketType.channel)
    async def unlockall(self, ctx: commands.Context):
        guild = getattr(ctx, "guild", None)
        if not isinstance(guild, discord.Guild):
            return await ctx.reply("This command can only be used in a server.")
        me = getattr(guild, "me", None)
        author = ctx.author
        if not (isinstance(author, discord.Member) and isinstance(me, discord.Member) and hasattr(guild, "owner") and guild.owner and (author == guild.owner or (author.top_role and me.top_role and author.top_role > me.top_role))):
            return await ctx.reply("⚠️ Your top role must be above my top role to run this.")
        if not (me and me.guild_permissions and me.guild_permissions.manage_roles):
            return await ctx.reply("⚠️ I need **Manage Roles** to change permission overwrites.")
        confirm = Button(label="Confirm", style=discord.ButtonStyle.success)
        cancel = Button(label="Cancel", style=discord.ButtonStyle.danger)
        view = View(timeout=30)
        view.add_item(confirm)
        view.add_item(cancel)
        async def on_confirm(interaction: discord.Interaction):
            if interaction.user.id != author.id:
                return await interaction.response.send_message("This confirmation isn't for you.", ephemeral=True)
            await interaction.response.defer(thinking=True)
            changed = await self._apply_lock(guild, lock=False)
            await interaction.followup.send(f"✅ Unlocked {changed} channel{'s' if changed!=1 else ''}.")
            view.stop()
        async def on_cancel(interaction: discord.Interaction):
            if interaction.user.id != author.id:
                return await interaction.response.send_message("This confirmation isn't for you.", ephemeral=True)
            await interaction.response.edit_message(content="❎ Cancelled.", view=None)
            view.stop()
        confirm.callback = on_confirm
        cancel.callback = on_cancel
        embed = discord.Embed(
            color=self.color,
            description=f"**Unlock all channels** in **{guild.name}**?\n"
                        f"- Clears send/connect denies for **@everyone**.",
        )
        await ctx.reply(embed=embed, view=view, mention_author=False)

    async def _apply_lock(self, guild: discord.Guild, *, lock: bool) -> int:
        """
        lock=True  -> deny send/connect
        lock=False -> clear send/connect (set to None)
        """
        changed = 0
        everyone = default_role(guild)
        for ch in guild.channels:
            try:
                ow = ch.overwrites_for(everyone)
                if isinstance(ch, (discord.TextChannel, discord.ForumChannel, discord.Thread)):
                    ow.send_messages = False if lock else None
                elif isinstance(ch, (discord.VoiceChannel, discord.StageChannel)):
                    ow.connect = False if lock else None
                elif isinstance(ch, discord.CategoryChannel):
                    # Apply both for categories
                    ow.send_messages = False if lock else None
                    ow.connect = False if lock else None
                else:
                    continue
                await ch.set_permissions(everyone, overwrite=ow, reason="lockall/unlockall")
                changed += 1
            except Exception:
                continue
        return changed

    # ── Hide/Unhide all (view_channel) ───────────────────────────────────────
    @commands.hybrid_command(name="hideall", help="Hide all channels from @everyone.")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 15, commands.BucketType.channel)
    async def hideall(self, ctx: commands.Context):
        await self._toggle_visibility(ctx, hide=True)

    @commands.hybrid_command(name="unhideall", help="Unhide all channels for @everyone.")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 15, commands.BucketType.channel)
    async def unhideall(self, ctx: commands.Context):
        await self._toggle_visibility(ctx, hide=False)

    async def _toggle_visibility(self, ctx: commands.Context, *, hide: bool):
        guild = getattr(ctx, "guild", None)
        if not isinstance(guild, discord.Guild):
            return await ctx.reply("This command can only be used in a server.")
        me = getattr(guild, "me", None)
        author = ctx.author
        if not (isinstance(author, discord.Member) and isinstance(me, discord.Member) and hasattr(guild, "owner") and guild.owner and (author == guild.owner or (author.top_role and me.top_role and author.top_role > me.top_role))):
            return await ctx.reply("⚠️ Your top role must be above my top role to run this.")
        if not (me and me.guild_permissions and me.guild_permissions.manage_roles):
            return await ctx.reply("⚠️ I need **Manage Roles** to change permission overwrites.")
        action_text = "hide" if hide else "unhide"
        confirm = Button(label="Confirm", style=discord.ButtonStyle.success)
        cancel = Button(label="Cancel", style=discord.ButtonStyle.danger)
        view = View(timeout=30)
        view.add_item(confirm)
        view.add_item(cancel)
        async def on_confirm(interaction: discord.Interaction):
            if interaction.user.id != author.id:
                return await interaction.response.send_message("This confirmation isn't for you.", ephemeral=True)
            await interaction.response.defer(thinking=True)
            changed = 0
            everyone = default_role(guild)
            for ch in getattr(guild, "channels", []):
                try:
                    ow = ch.overwrites_for(everyone)
                    ow.view_channel = False if hide else None
                    await ch.set_permissions(everyone, overwrite=ow, reason=f"{action_text}all")
                    changed += 1
                except Exception:
                    continue
            await interaction.followup.send(f"✅ {action_text.capitalize()}d {changed} channel{'s' if changed!=1 else ''}.")
            view.stop()
        async def on_cancel(interaction: discord.Interaction):
            if interaction.user.id != author.id:
                return await interaction.response.send_message("This confirmation isn't for you.", ephemeral=True)
            await interaction.response.edit_message(content="❎ Cancelled.", view=None)
            view.stop()
        confirm.callback = on_confirm
        cancel.callback = on_cancel
        embed = discord.Embed(
            color=self.color,
            description=f"**{action_text.capitalize()} all channels** in **{guild.name}** for **@everyone**?",
        )
        await ctx.reply(embed=embed, view=view, mention_author=False)

    # ── Give/Remove role (toggle) ────────────────────────────────────────────
    @commands.hybrid_command(name="give", aliases=["addrole"], help="Toggle a role on a member.")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def give(self, ctx: commands.Context, member: discord.Member, *, role: discord.Role):
        guild = ctx.guild
        me = getattr(guild, "me", None)
        author = ctx.author
        if not (isinstance(me, discord.Member) and isinstance(author, discord.Member)):
            return await ctx.reply("This command can only be used in a server.")
        if not (hasattr(me, "top_role") and hasattr(role, "position") and me.top_role and role):
            return await ctx.reply("⚠️ I cannot manage that role (it's above or equal to my top role).")
        if role >= me.top_role:
            return await ctx.reply("⚠️ I cannot manage that role (it's above or equal to my top role).")
        if not can_manage_member(author, member):
            return await ctx.reply("⛔ You cannot manage a user with an equal or higher role than you.")
        if not (guild and bot_above_role(guild, role)):
            return await ctx.reply("⚠️ Move my top role **above** the target role first.")

        try:
            if role not in member.roles:
                await member.add_roles(role, reason=f"Added by {author} ({author.id})")
                return await ctx.reply(f"✅ Added **{role.name}** to {member.mention}.")
            else:
                await member.remove_roles(role, reason=f"Removed by {author} ({author.id})")
                return await ctx.reply(f"✅ Removed **{role.name}** from {member.mention}.")
        except discord.Forbidden:
            return await ctx.reply("⛔ I don't have permission to edit that member's roles.")
        except Exception as e:
            return await ctx.reply(f"⚠️ Unexpected error: `{e}`")

    # ── Clone channel ────────────────────────────────────────────────────────
    @commands.hybrid_command(name="clone", help="Clone a text/voice channel.")
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def clone(self, ctx: commands.Context, channel: Optional[Union[discord.TextChannel, discord.VoiceChannel]] = None):
        channel = channel or cast(Optional[Union[discord.TextChannel, discord.VoiceChannel]], ctx.channel)
        if not isinstance(channel, (discord.TextChannel, discord.VoiceChannel)):
            return await ctx.reply("This command can only clone text or voice channels.")
        try:
            new_ch = await channel.clone(reason=f"Cloned by {ctx.author}")
            await new_ch.edit(position=getattr(channel, "position", 0))
            await ctx.reply(f"✅ Cloned **#{getattr(channel, 'name', 'channel')}** → {getattr(new_ch, 'mention', '')}")
        except discord.Forbidden:
            await ctx.reply("⛔ I lack permission to clone channels.")
        except Exception as e:
            await ctx.reply(f"⚠️ Error cloning channel: `{e}`")

    # ── Change nickname ──────────────────────────────────────────────────────
    @commands.hybrid_command(name="nick", aliases=["setnick"], help="Change or clear someone's nickname.")
    @commands.guild_only()
    @commands.has_permissions(manage_nicknames=True)
    @commands.bot_has_permissions(manage_nicknames=True)
    async def nick(self, ctx: commands.Context, member: discord.Member, *, name: Optional[str] = None):
        guild = getattr(ctx, "guild", None)
        me = getattr(guild, "me", None) if guild else None
        author = ctx.author
        if not (isinstance(member, discord.Member) and isinstance(author, discord.Member) and isinstance(me, discord.Member)):
            return await ctx.reply("This command can only be used in a server.")
        if isinstance(guild, discord.Guild) and getattr(guild, "owner", None) and member == guild.owner:
            return await ctx.reply("⛔ I can't change the server owner's nickname.")
        if not (hasattr(member, "top_role") and hasattr(me, "top_role") and member.top_role and me.top_role):
            return await ctx.reply("⚠️ That user's top role is higher or equal to mine.")
        if member.top_role >= me.top_role:
            return await ctx.reply("⚠️ That user's top role is higher or equal to mine.")
        if not can_manage_member(author, member):
            return await ctx.reply("⛔ You cannot edit the nickname of someone with equal or higher role than you.")

        try:
            await member.edit(nick=name, reason=f"By {author} ({author.id})")
            if name:
                await ctx.reply(f"✅ Nickname for {member.mention} set to **{discord.utils.escape_markdown(name)}**.")
            else:
                await ctx.reply(f"✅ Cleared nickname for {member.mention}.")
        except discord.Forbidden:
            await ctx.reply("⛔ I don't have permission to change that nickname.")
        except Exception as e:
            await ctx.reply(f"⚠️ Error changing nickname: `{e}`")

    # ── Nuke channel (confirm) ───────────────────────────────────────────────
    @commands.hybrid_command(name="nuke", help="Clone the channel and delete the original.")
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    @commands.cooldown(1, 7, commands.BucketType.user)
    async def nuke(self, ctx: commands.Context):
        author = ctx.author
        confirm = Button(label="Confirm", style=discord.ButtonStyle.success)
        cancel = Button(label="Cancel", style=discord.ButtonStyle.danger)
        view = View(timeout=30)
        view.add_item(confirm)
        view.add_item(cancel)
        async def on_confirm(interaction: discord.Interaction):
            if interaction.user.id != author.id:
                return await interaction.response.send_message("This confirmation isn't for you.", ephemeral=True)
            await interaction.response.defer(thinking=True)
            ch = interaction.channel
            if not isinstance(ch, (discord.TextChannel, discord.VoiceChannel)):
                return await interaction.followup.send("This can only nuke text or voice channels.")
            try:
                new_ch = await ch.clone(reason=f"Nuked by {author}")
                await new_ch.edit(position=ch.position)
                await ch.delete()
                await new_ch.send(embed=discord.Embed(
                    description=f"💥 Channel nuked by **{author}**",
                    color=self.color
                ))
            except discord.Forbidden:
                await interaction.followup.send("⛔ I lack permission to manage/delete this channel.")
            except Exception as e:
                await interaction.followup.send(f"⚠️ Error nuking: `{e}`")
            view.stop()
        async def on_cancel(interaction: discord.Interaction):
            if interaction.user.id != author.id:
                return await interaction.response.send_message("This confirmation isn't for you.", ephemeral=True)
            await interaction.response.edit_message(content="❎ Cancelled.", view=None)
            view.stop()
        confirm.callback = on_confirm
        cancel.callback = on_cancel
        await ctx.reply(
            embed=discord.Embed(color=self.color, description="**Nuke this channel?**"),
            view=view,
            mention_author=False,
        )

    # ── Slowmode / Unslowmode ────────────────────────────────────────────────
    @commands.hybrid_command(name="slowmode", aliases=["slow"], help="Set slowmode delay (seconds, max 120).")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_channels=True)
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def slowmode(self, ctx: commands.Context, seconds: int = 0):
        if seconds < 0 or seconds > 120:
            return await ctx.reply("⚠️ Slowmode must be between 0 and 120 seconds.")
        channel = getattr(ctx, "channel", None)
        if not isinstance(channel, discord.TextChannel):
            return await ctx.reply("This command can only be used in a server text channel.")
        await channel.edit(slowmode_delay=seconds, reason=f"By {ctx.author}")
        if seconds == 0:
            await ctx.reply("✅ Slowmode disabled.")
        else:
            await ctx.reply(f"✅ Slowmode set to **{seconds}** seconds.")

    @commands.hybrid_command(name="unslowmode", aliases=["unslow"], help="Disable slowmode in this channel.")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_channels=True)
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def unslowmode(self, ctx: commands.Context):
        channel = getattr(ctx, "channel", None)
        if not isinstance(channel, discord.TextChannel):
            return await ctx.reply("This command can only be used in a server text channel.")
        await channel.edit(slowmode_delay=0, reason=f"By {ctx.author}")
        await ctx.reply("✅ Slowmode disabled.")

    # ── Delete sticker from replied message ──────────────────────────────────
    @commands.command(name="delsticker", aliases=["deletesticker", "removesticker"], help="Delete a sticker from the replied message.")
    @commands.guild_only()
    @commands.has_permissions(manage_emojis_and_stickers=True)
    @commands.bot_has_permissions(manage_emojis_and_stickers=True)
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def delsticker(self, ctx: commands.Context):
        if not ctx.message.reference:
            return await ctx.reply("Reply to a message that contains a sticker.")
        channel = getattr(ctx, "channel", None)
        if not isinstance(channel, discord.TextChannel):
            return await ctx.reply("This command can only be used in a server text channel.")
        msg_id = getattr(ctx.message.reference, "message_id", None)
        if not isinstance(msg_id, int):
            return await ctx.reply("Invalid replied message reference.")
        msg = await channel.fetch_message(msg_id)
        if not getattr(msg, "stickers", None):
            return await ctx.reply("No sticker found in the replied message.")
        deleted = 0
        for st in msg.stickers:
            try:
                if isinstance(ctx.guild, discord.Guild) and hasattr(ctx.guild, "delete_sticker"):
                    await ctx.guild.delete_sticker(st, reason=f"Deleted by {ctx.author}")
                    deleted += 1
            except Exception:
                continue
        if deleted:
            await ctx.reply(f"✅ Deleted {deleted} sticker{'s' if deleted!=1 else ''}.")
        else:
            await ctx.reply("⚠️ Could not delete the sticker(s).")

    # ── Delete emojis found in message content (or replied message) ──────────
    @commands.command(name="delemoji", aliases=["deleteemoji", "removeemoji"], help="Delete custom emojis mentioned in your message or a replied message.")
    @commands.guild_only()
    @commands.has_permissions(manage_emojis_and_stickers=True)
    @commands.bot_has_permissions(manage_emojis_and_stickers=True)
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def delemoji(self, ctx: commands.Context):
        source_text = None
        channel = getattr(ctx, "channel", None)
        if ctx.message.reference:
            msg_id = getattr(ctx.message.reference, "message_id", None)
            if isinstance(channel, discord.TextChannel) and isinstance(msg_id, int):
                ref = await channel.fetch_message(msg_id)
                source_text = getattr(ref, "content", "")
        else:
            source_text = getattr(ctx.message, "content", "")
        # Match <:name:123> or <a:name:123>
        ids = re.findall(r"<a?:\w+:(\d+)>", str(source_text))
        if not ids:
            return await ctx.reply("No custom emojis found to delete.")
        if len(ids) > 15:
            return await ctx.reply("⚠️ You can delete up to **15** emojis at a time.")

        deleted = 0
        for eid in ids:
            try:
                if isinstance(ctx.guild, discord.Guild) and hasattr(ctx.guild, "fetch_emoji"):
                    emoji = await ctx.guild.fetch_emoji(int(eid))
                    await emoji.delete(reason=f"Deleted by {ctx.author}")
                    deleted += 1
            except (discord.NotFound, discord.Forbidden):
                continue
        await ctx.reply(f"✅ Deleted {deleted}/{len(ids)} emoji(s).")

    # ── Role icon (upload/clear/from emoji/url) ──────────────────────────────
    @commands.command(name="roleicon", help="Set/clear a role's icon. Use: roleicon <@role> [emoji|url] or attach image; omit to clear.")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @commands.bot_has_guild_permissions(manage_roles=True)
    async def roleicon(self, ctx: commands.Context, role: discord.Role, *, icon: Optional[str] = None):
        me = getattr(ctx.guild, "me", None) if ctx.guild else None
        if not (isinstance(me, discord.Member) and hasattr(role, "position") and hasattr(me, "top_role") and me.top_role):
            return await ctx.reply("⚠️ That role is above or equal to my top role.")
        if role.position >= me.top_role.position:
            return await ctx.reply("⚠️ That role is above or equal to my top role.")
        if not (ctx.guild and bot_above_role(ctx.guild, role)):
            return await ctx.reply("⚠️ Move my top role above the target role first.")
        if (
            isinstance(ctx.guild, discord.Guild)
            and getattr(ctx.guild, "owner", None)
            and isinstance(ctx.author, discord.Member)
            and ctx.author != ctx.guild.owner
            and hasattr(ctx.author, "top_role")
            and ctx.author.top_role is not None
            and hasattr(ctx.author.top_role, "position")
            and ctx.author.top_role.position <= role.position
        ):
            return await ctx.reply("⛔ That role is equal/higher than your top role.")

        async def fetch_bytes(url: str) -> Optional[bytes]:
            try:
                async with aiohttp.ClientSession() as sess:
                    async with sess.get(url) as resp:
                        if resp.status == 200:
                            return await resp.read()
            except Exception:
                return None
            return None

        # Attachment
        if not icon:
            if ctx.message.attachments:
                data = await ctx.message.attachments[0].read()
                await role.edit(display_icon=data, reason=f"By {ctx.author}")
                return await ctx.reply(f"✅ Updated icon for {role.mention}.")
            # Clear
            await role.edit(display_icon=None, reason=f"Cleared by {ctx.author}")
            return await ctx.reply(f"✅ Removed icon for {role.mention}.")

        # Emoji input like <:name:id>
        m = re.match(r"<a?:\w+:(\d+)>", icon)
        if m:
            emoji_id = int(m.group(1))
            url = f"https://cdn.discordapp.com/emojis/{emoji_id}.png?quality=lossless"
            data = await fetch_bytes(url)
            if not data:
                return await ctx.reply("⚠️ Failed to fetch emoji image.")
            await role.edit(display_icon=data, reason=f"By {ctx.author}")
            return await ctx.reply(f"✅ Updated icon for {role.mention} from emoji.")

        # URL input
        if icon.startswith("http://") or icon.startswith("https://"):
            data = await fetch_bytes(icon)
            if not data:
                return await ctx.reply("⚠️ Failed to fetch the image from URL.")
            await role.edit(display_icon=data, reason=f"By {ctx.author}")
            return await ctx.reply(f"✅ Updated icon for {role.mention} from URL.")

        return await ctx.reply("❓ Provide an attached image, a custom emoji, or an image URL — or omit to clear.")

    # ── Unban all (confirm) ─────────────────────────────────────────────────
    @commands.hybrid_command(name="unbanall", aliases=["massunban"], help="Unban every banned member (use with care).")
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def unbanall(self, ctx: commands.Context):
        author = ctx.author

        confirm = Button(label="Confirm", style=discord.ButtonStyle.success)
        cancel = Button(label="Cancel", style=discord.ButtonStyle.danger)
        view = View(timeout=30)
        view.add_item(confirm)
        view.add_item(cancel)

        async def on_confirm(interaction: discord.Interaction):
            if interaction.user.id != author.id:
                return await interaction.response.send_message("This confirmation isn't for you.", ephemeral=True)
            await interaction.response.defer(thinking=True)
            count = 0
            try:
                guild = getattr(ctx, "guild", None)
                if isinstance(guild, discord.Guild) and hasattr(guild, "bans") and hasattr(guild, "unban"):
                    async for entry in guild.bans():
                        await guild.unban(entry.user, reason=f"Unbanall by {author}")
                        count += 1
                await interaction.followup.send(f"✅ Unbanned **{count}** member{'s' if count!=1 else ''}.")
            except discord.Forbidden:
                await interaction.followup.send("⛔ I lack permission to unban members.")
            except Exception as e:
                await interaction.followup.send(f"⚠️ Error unbanning: `{e}`")
            view.stop()

        async def on_cancel(interaction: discord.Interaction):
            if interaction.user.id != author.id:
                return await interaction.response.send_message("This confirmation isn't for you.", ephemeral=True)
            await interaction.response.edit_message(content="❎ Cancelled.", view=None)
            view.stop()

        confirm.callback = on_confirm
        cancel.callback = on_cancel

        guild = getattr(ctx, "guild", None)
        guild_name = getattr(guild, "name", "this server")
        await ctx.reply(
            embed=discord.Embed(color=self.color, description=f"**Unban ALL** banned users in **{guild_name}**?"),
            view=view,
            mention_author=False,
        )

    # ── Audit log viewer (limited) ───────────────────────────────────────────
    @commands.hybrid_command(name="audit", help="Show recent audit log entries (max 30).")
    @commands.guild_only()
    @commands.has_permissions(view_audit_log=True)
    @commands.bot_has_permissions(view_audit_log=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def audit(self, ctx: commands.Context, limit: int = 10):
        if limit <= 0 or limit > 30:
            return await ctx.reply("⚠️ Limit must be between 1 and 30.")
        lines = []
        guild = getattr(ctx, "guild", None)
        if not (isinstance(guild, discord.Guild) and hasattr(guild, "audit_logs")):
            return await ctx.reply("This command can only be used in a server.")
        try:
            async for entry in guild.audit_logs(limit=limit):
                action = str(entry.action).replace("AuditLogAction.", "")
                lines.append(
                    f"**User**: {entry.user}\n"
                    f"**Action**: `{action}`\n"
                    f"**Target**: {entry.target}\n"
                    f"**Reason**: {entry.reason}\n"
                )
        except discord.Forbidden:
            return await ctx.reply("⛔ I can't view the audit log here.")
        except Exception as e:
            return await ctx.reply(f"⚠️ Error reading audit log: `{e}`")

        description = ">>> " + ("\n".join(lines) if lines else "_No entries_")
        guild_name = getattr(guild, "name", "this server")
        embed = discord.Embed(
            title=f"Audit Log — {guild_name}",
            description=description[:4096],
            color=self.color,
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="prefix", aliases=["setprefix", "prefixset"], help="Allows you to change the prefix of the bot for this server")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def prefix(self, ctx: commands.Context, *, new_prefix: Optional[str] = None):
        """Change the bot's prefix for this server"""
        if not ctx.guild:
            return
            
        if not new_prefix:
            # Show current prefix
            current_prefix = ctx.prefix
            embed = discord.Embed(
                title="📋 Current Prefix",
                description=f"The current prefix for **{ctx.guild.name}** is: `{current_prefix}`",
                color=self.color
            )
            embed.add_field(
                name="Usage",
                value=f"`{current_prefix}prefix <new_prefix>` - Change the prefix\n`{current_prefix}setprefix <new_prefix>` - Alternative command",
                inline=False
            )
            await ctx.send(embed=embed)
            return

        # Validate the new prefix
        if len(new_prefix) > 10:
            embed = discord.Embed(
                title="❌ Invalid Prefix",
                description="Prefix cannot be longer than 10 characters.",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return

        if len(new_prefix.strip()) == 0:
            embed = discord.Embed(
                title="❌ Invalid Prefix",
                description="Prefix cannot be empty or just spaces.",
                color=0xFF0000
            )
            await ctx.send(embed=embed)
            return

        # Import and update the prefix in database
        try:
            from utils.config_utils import updateConfig
            await updateConfig(ctx.guild.id, {"prefix": new_prefix})
            
            embed = discord.Embed(
                title="✅ Prefix Updated",
                description=f"Server prefix has been changed from `{ctx.prefix}` to `{new_prefix}`",
                color=0x00E6A7
            )
            embed.add_field(
                name="New Usage",
                value=f"You can now use commands like: `{new_prefix}help`, `{new_prefix}play`, etc.",
                inline=False
            )
            embed.set_footer(text=f"Changed by {ctx.author}", icon_url=ctx.author.display_avatar.url)
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to update prefix: {str(e)}",
                color=0xFF0000
            )
            await ctx.send(embed=embed)


# ─────────────────────────────────────────────────────────────────────────────
# Cog Setup
# ─────────────────────────────────────────────────────────────────────────────

async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
