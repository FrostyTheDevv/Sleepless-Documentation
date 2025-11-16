import discord
from discord.ext import commands
from datetime import datetime
from utils.Tools import blacklist_check, ignore_check
from utils.timezone_helpers import get_timezone_helpers
import aiosqlite
import json

class SnipeView(discord.ui.View):
    def __init__(self, bot, snipes, user_id):
        super().__init__(timeout=120)
        self.bot = bot
        self.snipes = snipes
        self.index = 0
        self.user_id = user_id
        self.update_buttons()

    def update_buttons(self):
        # Safely update button states if buttons exist
        if hasattr(self, 'first_button'):
            self.first_button.disabled = self.index == 0 or len(self.snipes) == 1
        if hasattr(self, 'prev_button'):
            self.prev_button.disabled = self.index == 0 or len(self.snipes) == 1
        if hasattr(self, 'next_button'):
            self.next_button.disabled = self.index == len(self.snipes) - 1 or len(self.snipes) == 1
        if hasattr(self, 'last_button'):
            self.last_button.disabled = self.index == len(self.snipes) - 1 or len(self.snipes) == 1

    async def send_snipe_embed(self, interaction: discord.Interaction):
        snipe = self.snipes[self.index]
        embed = discord.Embed(color=0x006fb9)
        embed.set_author(name=f"Deleted Message {self.index + 1}/{len(self.snipes)}", icon_url=snipe['author_avatar'])
        uid = snipe['author_id']
        display_name = snipe['author_name']
        embed.description = (
            f"**Author:** **[{display_name}](https://discord.com/users/{uid})**\n"
            f" **Author ID:** `{snipe['author_id']}`\n"
            f" **Author Mention:** <@{snipe['author_id']}>\n"
            f"**Deleted:** <t:{snipe['deleted_at']}:R>\n"
        )

        if snipe['content']:
            embed.add_field(name="<:feast_delete:1400140670659989524> **Content:**", value=snipe['content'])
        if snipe['attachments']:
            attachment_links = "\n".join([f"[{attachment['name']}]({attachment['url']})" for attachment in snipe['attachments']])
            embed.add_field(name="**Attachments:**", value=attachment_links)

        avatar_url = None
        if interaction.user and getattr(interaction.user, "avatar", None):
            avatar = interaction.user.avatar
            if avatar:
                avatar_url = avatar.url
        elif interaction.user and getattr(interaction.user, "default_avatar", None):
            avatar_url = interaction.user.default_avatar.url
        embed.set_footer(text=f"Total Deleted Messages: {len(self.snipes)} | Requested by {interaction.user}", icon_url=avatar_url)
        await interaction.response.edit_message(embed=embed, view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    @discord.ui.button(emoji="<:feast_next:1400141978095583322>", style=discord.ButtonStyle.secondary, custom_id="first")
    async def first_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = 0
        self.update_buttons()
        await self.send_snipe_embed(interaction)

    @discord.ui.button(emoji="<:feast_prev:1400142835914637524>", style=discord.ButtonStyle.secondary, custom_id="previous")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index > 0:
            self.index -= 1
        self.update_buttons()
        await self.send_snipe_embed(interaction)

    @discord.ui.button(emoji="<:feast_delete:1400140670659989524>", style=discord.ButtonStyle.danger, custom_id="delete")
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if hasattr(interaction, "message") and interaction.message and hasattr(interaction.message, "delete"):
            await interaction.message.delete()

    @discord.ui.button(emoji="<:feast_next:1400141978095583322>", style=discord.ButtonStyle.secondary, custom_id="next")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index < len(self.snipes) - 1:
            self.index += 1
        self.update_buttons()
        await self.send_snipe_embed(interaction)

    @discord.ui.button(emoji="<:feast_prev:1400142835914637524>", style=discord.ButtonStyle.secondary, custom_id="last")
    async def last_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = len(self.snipes) - 1
        self.update_buttons()
        await self.send_snipe_embed(interaction)

    async def on_timeout(self):
        for child in self.children:
            # Only set .disabled for Button or Select, not ActionRow
            if isinstance(child, (discord.ui.Button, discord.ui.Select)):
                child.disabled = True
        msg_ref = getattr(self, "_message_ref", None)
        if msg_ref:
            try:
                await msg_ref.edit(view=self)
            except discord.NotFound:
                # Message was deleted, nothing we can do
                pass


class Snipe(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tz_helpers = get_timezone_helpers(bot)
        # No longer need in-memory storage - using database

    async def save_snipe(self, channel_id, snipe_data):
        """Save a snipe to the database"""
        async with aiosqlite.connect('db/snipe.db') as db:
            await db.execute('''
                INSERT INTO snipes (channel_id, author_name, author_avatar, author_id, content, deleted_at, attachments)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                channel_id,
                snipe_data['author_name'],
                snipe_data['author_avatar'],
                snipe_data['author_id'],
                snipe_data['content'],
                snipe_data['deleted_at'],
                json.dumps(snipe_data['attachments']) if snipe_data['attachments'] else None
            ))

            # Keep only the last 10 snipes per channel
            await db.execute('''
                DELETE FROM snipes
                WHERE channel_id = ? AND id NOT IN (
                    SELECT id FROM snipes
                    WHERE channel_id = ?
                    ORDER BY deleted_at DESC
                    LIMIT 10
                )
            ''', (channel_id, channel_id))

            await db.commit()

    async def get_channel_snipes(self, channel_id):
        """Get snipes for a channel from the database"""
        async with aiosqlite.connect('db/snipe.db') as db:
            cursor = await db.execute('''
                SELECT author_name, author_avatar, author_id, content, deleted_at, attachments
                FROM snipes
                WHERE channel_id = ?
                ORDER BY deleted_at DESC
                LIMIT 10
            ''', (channel_id,))

            rows = await cursor.fetchall()

            snipes = []
            for row in rows:
                author_name, author_avatar, author_id, content, deleted_at, attachments_json = row
                attachments = json.loads(attachments_json) if attachments_json else []

                snipes.append({
                    'author_name': author_name,
                    'author_avatar': author_avatar,
                    'author_id': author_id,
                    'content': content,
                    'deleted_at': deleted_at,
                    'attachments': attachments
                })

            return snipes

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if not message.guild or message.author.bot:
            return

        attachments = []
        if message.attachments:
            attachments = [{'name': attachment.filename, 'url': attachment.url} for attachment in message.attachments]

        snipe_data = {
            'author_name': message.author.name,
            'author_avatar': message.author.avatar.url if message.author.avatar else message.author.default_avatar.url,
            'author_id': message.author.id,
            'content': message.content or None,
            'deleted_at': int(self.tz_helpers.get_utc_now().timestamp()),
            'attachments': attachments
        }

        await self.save_snipe(message.channel.id, snipe_data)

    @commands.hybrid_command(name='snipe', help="Shows the recently deleted messages in the channel.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(manage_messages=True)
    async def snipe(self, ctx):
        channel_snipes = await self.get_channel_snipes(ctx.channel.id)
        if not channel_snipes:
            await ctx.send("No recently deleted messages found in this channel.")
            return

        first_snipe = channel_snipes[0]
        embed = discord.Embed(color=0x006fb9)
        embed.set_author(name="Last Deleted Message", icon_url=first_snipe['author_avatar'])
        uid = first_snipe['author_id']
        display_name = first_snipe['author_name']
        embed.description = (
            f" **Author:** **[{display_name}](https://discord.com/users/{uid})**\n"
            f"**Author ID:** `{first_snipe['author_id']}`\n"
            f"**Author Mention:** <@{first_snipe['author_id']}>\n"
            f" **Deleted:** <t:{first_snipe['deleted_at']}:R>\n"
        )

        if first_snipe['content']:
            embed.add_field(name="<:feast_delete:1400140670659989524> **Content:**", value=first_snipe['content'])
        if first_snipe['attachments']:
            attachment_links = "\n".join([f"[{attachment['name']}]({attachment['url']})" for attachment in first_snipe['attachments']])
            embed.add_field(name="**Attachments:**", value=attachment_links)

        embed.set_footer(text=f"Total Deleted Messages: {len(channel_snipes)} | Requested by {ctx.author}", icon_url=ctx.author.avatar.url)

        view = SnipeView(self.bot, channel_snipes, ctx.author.id)

        message = await ctx.send(embed=embed, view=view)
        setattr(view, "_message_ref", message)
        # Disable navigation buttons if only one snipe
        if len(channel_snipes) <= 1:
            if hasattr(view, 'first_button'):
                view.first_button.disabled = True
            if hasattr(view, 'prev_button'):
                view.prev_button.disabled = True
            if hasattr(view, 'next_button'):
                view.next_button.disabled = True
            if hasattr(view, 'last_button'):
                view.last_button.disabled = True

"""
@Author: Frosty
    + Discord: frosty.pyro
    + Community: https://discord.gg/5wtjDkYbVh (Sleepless Development)
    + for any queries reach out in the server; or send a dm.
"""