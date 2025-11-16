import discord 
from discord.ext import commands
import sqlite3
import os
from datetime import datetime, timezone
from typing import Optional
from utils.timezone_helpers import get_timezone_helpers

from utils.error_helpers import StandardErrorHandler
DB_PATH = "db/messages.db"
os.makedirs("db", exist_ok=True)  # Ensure 'db/' folder exists


class MessageLeaderboardPaginator(discord.ui.View):
    def __init__(self, ctx, rows, per_page: int = 10, timeout: int = 120):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.rows = rows  # list of (user_id:int, total:int)
        self.per_page = per_page
        self.current_page = 0
        self.max_pages = (len(rows) - 1) // per_page + 1 if rows else 1
        self.message = None  # Initialize message attribute
        self.update_button_states()

    def update_button_states(self):
        self.first_button.disabled = self.current_page == 0
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page >= self.max_pages - 1
        self.last_button.disabled = self.current_page >= self.max_pages - 1

    def format_embed(self):
        start = self.current_page * self.per_page
        end = start + self.per_page
        chunk = self.rows[start:end]

        lines = []
        for idx, (user_id, total) in enumerate(chunk):
            overall_index = start + idx + 1
            member = self.ctx.guild.get_member(user_id)
            if member:
                name = f"{member.name}#{member.discriminator}"
            else:
                name = f"<@{user_id}>"
            lines.append(f"**{overall_index}. {name}** — {total} messages")

        description = "\n".join(lines) if lines else "<:feast_cross:1400143488695144609> No data."
        embed = discord.Embed(
            title=f"<:feast_trophy:1401572811159371808> Message Leaderboard",
            description=description,
            color=discord.Color.blurple()
        )
        embed.set_footer(text=f"Page {self.current_page + 1}/{self.max_pages} • {len(self.rows)} users total")
        return embed

    @discord.ui.button(label="First", style=discord.ButtonStyle.secondary, custom_id="msglb_first",
                       emoji=discord.PartialEmoji(name="feast_next", id=1400141978095583322))
    async def first_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.defer()
        self.current_page = 0
        self.update_button_states()
        await interaction.response.edit_message(embed=self.format_embed(), view=self)

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary, custom_id="msglb_prev",
                       emoji=discord.PartialEmoji(name="feast_piche", id=1400142845402284102))
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.defer()
        self.current_page = max(0, self.current_page - 1)
        self.update_button_states()
        await interaction.response.edit_message(embed=self.format_embed(), view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary, custom_id="msglb_next",
                       emoji=discord.PartialEmoji(name="feast_age", id=1400142030205878274))
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.defer()
        self.current_page = min(self.max_pages - 1, self.current_page + 1)
        self.update_button_states()
        await interaction.response.edit_message(embed=self.format_embed(), view=self)

    @discord.ui.button(label="Last", style=discord.ButtonStyle.secondary, custom_id="msglb_last",
                       emoji=discord.PartialEmoji(name="feast_prev", id=1400142835914637524))
    async def last_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.defer()
        self.current_page = self.max_pages - 1
        self.update_button_states()
        await interaction.response.edit_message(embed=self.format_embed(), view=self)

    async def on_timeout(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        try:
            if self.message is not None:
                edit_func = getattr(self.message, "edit", None)
                if edit_func:
                    import inspect
                    if inspect.iscoroutinefunction(edit_func):
                        await edit_func(view=self)
                    else:
                        edit_func(view=self)
        except Exception:
            pass


class Messagespack(commands.Cog):
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot
        self.tz_helpers = get_timezone_helpers(bot)
        os.makedirs("db", exist_ok=True)
        self.create_table()

    def create_table(self):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                guild_id INTEGER,
                user_id INTEGER,
                date TEXT,
                count INTEGER,
                PRIMARY KEY (guild_id, user_id, date)
            )
        """)
        conn.commit()
        conn.close()

    @commands.command(name="addmessages", aliases=["addmsg"], help="Add messages to a user's count", usage="addmessages <member> <amount>")
    @commands.has_permissions(manage_messages=True)
    async def addmessages(self, ctx, member: discord.Member, amount: int):
        if amount <= 0:
            return await ctx.send("<:feast_cross:1400143488695144609> Amount must be greater than 0.")

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()

            c.execute("SELECT count FROM messages WHERE guild_id = ? AND user_id = ? AND date = ?",
                      (ctx.guild.id, member.id, today))
            result = c.fetchone()

            if result:
                c.execute("UPDATE messages SET count = count + ? WHERE guild_id = ? AND user_id = ? AND date = ?",
                          (amount, ctx.guild.id, member.id, today))
            else:
                c.execute("INSERT INTO messages (guild_id, user_id, date, count) VALUES (?, ?, ?, ?)",
                          (ctx.guild.id, member.id, today, amount))

            conn.commit()
            await ctx.send(f"<:feast_tick:1400143469892210753> Added {amount} messages to {member.mention} for today.")
        except sqlite3.Error as e:
            await ctx.send("<:feast_cross:1400143488695144609> Database error occurred.")
            print(f"[DB Error] {e}")
        finally:
            conn.close()

    @commands.command(name="removemessages", aliases=["removemsg"], help="Remove messages from a user's count", usage="removemessages <member> <amount>")
    @commands.has_permissions(manage_messages=True)
    async def removemessages(self, ctx, member: discord.Member, amount: int):
        if amount <= 0:
            return await ctx.send("<:feast_cross:1400143488695144609> Amount must be greater than 0.")

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()

            c.execute("SELECT count FROM messages WHERE guild_id = ? AND user_id = ? AND date = ?",
                      (ctx.guild.id, member.id, today))
            result = c.fetchone()

            if result:
                new_count = max(0, result[0] - amount)
                c.execute("UPDATE messages SET count = ? WHERE guild_id = ? AND user_id = ? AND date = ?",
                          (new_count, ctx.guild.id, member.id, today))
                conn.commit()
                await ctx.send(f"<:feast_tick:1400143469892210753> Removed {amount} messages from {member.mention} for today.")
            else:
                await ctx.send(f"<:feast_cross:1400143488695144609> {member.mention} has no messages recorded for today.")
        except sqlite3.Error as e:
            await ctx.send("<:feast_cross:1400143488695144609> Database error occurred.")
            print(f"[DB Error] {e}")
        finally:
            conn.close()

    @commands.group(name="clearmessage", aliases=["clearmessages", "clrmsg"], invoke_without_command=True)
    @commands.has_permissions(manage_messages=True)
    async def clearmessage(self, ctx, member: Optional[discord.Member] = None):
        """Clear message data. Use subcommands for specific options."""
        if member:
            # Original functionality - clear all messages for a member
            try:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("DELETE FROM messages WHERE guild_id = ? AND user_id = ?",
                          (ctx.guild.id, member.id))
                conn.commit()
                await ctx.send(f"<:feast_tick:1400143469892210753> All messages cleared for {member.mention}.")
            except sqlite3.Error as e:
                await ctx.send("<:feast_cross:1400143488695144609> Database error occurred.")
                print(f"[DB Error] {e}")
            finally:
                conn.close()
        else:
            # Show help
            embed = discord.Embed(
                title="<:feast_info:1400143450330300518> Clear Message Commands",
                description="Clear specific message data from the database:",
                color=0x5865F2
            )
            embed.add_field(
                name="**Basic Usage**",
                value=(
                    "`clrmsg @member` - Clear all messages for a member\n"
                    "`clrmsg today @member` - Clear today's messages for a member\n"
                    "`clrmsg range @member <days>` - Clear messages from last X days\n"
                    "`clrmsg word <word> [count] [#channel]` - Clear messages containing word\n"
                    "`clrmsg channel` - Clear all data from current channel\n"
                    "`clrmsg all` - Clear all message data (Admin only)"
                ),
                inline=False
            )
            embed.add_field(
                name="**Examples**",
                value=(
                    "`clrmsg today @john` - Clear John's messages from today\n"
                    "`clrmsg range @jane 7` - Clear Jane's messages from last 7 days\n"
                    "`clrmsg word spam` - Clear all messages containing 'spam'\n"
                    "`clrmsg word hello 10` - Clear last 10 messages containing 'hello'\n"
                    "`clrmsg word test 5 #general` - Clear 5 messages with 'test' from #general\n"
                    "`clrmsg channel` - Clear all tracked messages from this channel"
                ),
                inline=False
            )
            embed.set_footer(text="💡 Use manage_messages permission required")
            await ctx.send(embed=embed)

    @clearmessage.command(name="today")
    @commands.has_permissions(manage_messages=True)
    async def clear_today(self, ctx, member: discord.Member):
        """Clear today's messages for a specific member"""
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("""
                DELETE FROM messages 
                WHERE guild_id = ? AND user_id = ? AND date = date('now')
            """, (ctx.guild.id, member.id))
            deleted_count = c.rowcount
            conn.commit()
            
            if deleted_count > 0:
                await ctx.send(f"<:feast_tick:1400143469892210753> Cleared {deleted_count} message record(s) from today for {member.mention}.")
            else:
                await ctx.send(f"<:feast_cross:1400143488695144609> No message records found for today for {member.mention}.")
        except sqlite3.Error as e:
            await ctx.send("<:feast_cross:1400143488695144609> Database error occurred.")
            print(f"[DB Error] {e}")
        finally:
            conn.close()

    @clearmessage.command(name="range")
    @commands.has_permissions(manage_messages=True) 
    async def clear_range(self, ctx, member: discord.Member, days: int):
        """Clear messages from the last X days for a member"""
        if days < 1 or days > 365:
            await ctx.send("<:feast_cross:1400143488695144609> Days must be between 1 and 365.")
            return
            
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("""
                DELETE FROM messages 
                WHERE guild_id = ? AND user_id = ? 
                AND date >= date('now', '-{} days')
            """.format(days), (ctx.guild.id, member.id))
            deleted_count = c.rowcount
            conn.commit()
            
            if deleted_count > 0:
                await ctx.send(f"<:feast_tick:1400143469892210753> Cleared {deleted_count} message record(s) from the last {days} days for {member.mention}.")
            else:
                await ctx.send(f"<:feast_cross:1400143488695144609> No message records found in the last {days} days for {member.mention}.")
        except sqlite3.Error as e:
            await ctx.send("<:feast_cross:1400143488695144609> Database error occurred.")
            print(f"[DB Error] {e}")
        finally:
            conn.close()

    @clearmessage.command(name="channel")
    @commands.has_permissions(manage_messages=True)
    async def clear_channel(self, ctx):
        """Clear all message data from the current channel"""
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("""
                DELETE FROM messages 
                WHERE guild_id = ? AND channel_id = ?
            """, (ctx.guild.id, ctx.channel.id))
            deleted_count = c.rowcount
            conn.commit()
            
            if deleted_count > 0:
                await ctx.send(f"<:feast_tick:1400143469892210753> Cleared {deleted_count} message record(s) from {ctx.channel.mention}.")
            else:
                await ctx.send(f"<:feast_cross:1400143488695144609> No message records found for {ctx.channel.mention}.")
        except sqlite3.Error as e:
            await ctx.send("<:feast_cross:1400143488695144609> Database error occurred.")
            print(f"[DB Error] {e}")
        finally:
            conn.close()

    @clearmessage.command(name="word", aliases=["containing", "with"])
    @commands.has_permissions(manage_messages=True)
    async def clear_word(self, ctx, word: str, count: Optional[int] = None, channel: Optional[discord.TextChannel] = None):
        """Clear messages containing a specific word/phrase
        
        Usage: 
        clrmsg word <word> - Clear all messages containing the word
        clrmsg word <word> <count> - Clear last X messages containing the word  
        clrmsg word <word> <count> <#channel> - Clear from specific channel
        """
        if count and (count < 1 or count > 1000):
            await ctx.send("<:feast_cross:1400143488695144609> Count must be between 1 and 1000.")
            return
        
        target_channel = channel or ctx.channel
        
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            
            # Build query based on parameters
            if count:
                # Get recent messages containing the word, limited by count
                query = """
                    DELETE FROM messages 
                    WHERE guild_id = ? AND channel_id = ? 
                    AND id IN (
                        SELECT id FROM messages 
                        WHERE guild_id = ? AND channel_id = ? 
                        AND (content LIKE ? OR content LIKE ? OR content LIKE ?)
                        ORDER BY date DESC, timestamp DESC 
                        LIMIT ?
                    )
                """
                params = (
                    ctx.guild.id, target_channel.id,
                    ctx.guild.id, target_channel.id,
                    f"%{word}%", f"%{word.lower()}%", f"%{word.upper()}%",
                    count
                )
            else:
                # Clear all messages containing the word
                if channel:
                    query = """
                        DELETE FROM messages 
                        WHERE guild_id = ? AND channel_id = ? 
                        AND (content LIKE ? OR content LIKE ? OR content LIKE ?)
                    """
                    params = (
                        ctx.guild.id, target_channel.id,
                        f"%{word}%", f"%{word.lower()}%", f"%{word.upper()}%"
                    )
                else:
                    query = """
                        DELETE FROM messages 
                        WHERE guild_id = ? AND channel_id = ?
                        AND (content LIKE ? OR content LIKE ? OR content LIKE ?)
                    """
                    params = (
                        ctx.guild.id, target_channel.id,
                        f"%{word}%", f"%{word.lower()}%", f"%{word.upper()}%"
                    )
            
            c.execute(query, params)
            deleted_count = c.rowcount
            conn.commit()
            
            # Build response message
            location = f"in {target_channel.mention}" if channel else f"in {ctx.channel.mention}"
            count_text = f"last {count} " if count else "all "
            
            if deleted_count > 0:
                await ctx.send(f"<:feast_tick:1400143469892210753> Cleared {deleted_count} message record(s) containing **\"{word}\"** ({count_text}messages {location}).")
            else:
                await ctx.send(f"<:feast_cross:1400143488695144609> No message records found containing **\"{word}\"** {location}.")
                
        except sqlite3.Error as e:
            await ctx.send("<:feast_cross:1400143488695144609> Database error occurred.")
            print(f"[DB Error] {e}")
        finally:
            conn.close()

    @clearmessage.command(name="all")
    @commands.has_permissions(administrator=True)
    async def clear_all(self, ctx):
        """Clear ALL message data for the server (Admin only)"""
        # Confirmation check
        embed = discord.Embed(
            title="⚠️ **DANGER ZONE**",
            description="This will **permanently delete ALL message tracking data** for this server!\n\nType `CONFIRM DELETE` to proceed:",
            color=0xFF0000
        )
        await ctx.send(embed=embed)
        
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content == "CONFIRM DELETE"
        
        try:
            confirmation = await ctx.bot.wait_for('message', timeout=30.0, check=check)
        except:
            await ctx.send("<:feast_cross:1400143488695144609> Confirmation timeout. Operation cancelled.")
            return
        
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("DELETE FROM messages WHERE guild_id = ?", (ctx.guild.id,))
            deleted_count = c.rowcount
            conn.commit()
            
            await ctx.send(f"<:feast_tick:1400143469892210753> **DELETED** {deleted_count} message records for the entire server.")
        except sqlite3.Error as e:
            await ctx.send("<:feast_cross:1400143488695144609> Database error occurred.")
            print(f"[DB Error] {e}")
        finally:
            conn.close()

    @commands.command(name="messageleaderboard", aliases=["msglb"], help="View the server message leaderboard", usage="messageleaderboard")
    async def messageleaderboard(self, ctx):
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("""
                SELECT user_id, SUM(count) as total FROM messages
                WHERE guild_id = ?
                GROUP BY user_id
                ORDER BY total DESC
            """, (ctx.guild.id,))
            rows = c.fetchall()
        except sqlite3.Error as e:
            await ctx.send("<:feast_cross:1400143488695144609> Database error occurred while fetching leaderboard.")
            print(f"[DB Error] {e}")
            return
        finally:
            conn.close()

        if not rows:
            return await ctx.send("<:feast_cross:1400143488695144609> No message data found for this server.")

        paginator = MessageLeaderboardPaginator(ctx, rows, per_page=10)
        embed = paginator.format_embed()
        message = await ctx.send(embed=embed, view=paginator)
        paginator.message = message

    def help_custom(self):
        return "📊", "Message Tracking", "Track, manage & view message statistics per user"

async def setup(bot):
    await bot.add_cog(Messagespack(bot))
