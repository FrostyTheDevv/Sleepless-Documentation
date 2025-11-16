import discord
from discord.utils import get
from core import sleepless, Cog
from utils.Tools import *
from utils.config import BotName, serverLink
from discord.ext import commands
from discord.ui import Button, View

class Autorole(Cog):
    def __init__(self, bot: sleepless):
       self.bot = bot


    @commands.Cog.listener(name="on_guild_join")
    async def send_msg_to_adder(self, guild: discord.Guild):
        async for entry in guild.audit_logs(limit=3):
            if entry.action == discord.AuditLogAction.bot_add and entry.user is not None:
                embed = discord.Embed(
                   description=f"🤖 **Thanks for adding Sleepless!**\n\n➡️ My default prefix is `$`\n➡️ Use the `$help` command to see a list of commands\n➡️ Use `$tos` for Terms of Service and `$privacy` for Privacy Policy\n➡️ For detailed guides, FAQ and information, visit our **[Support Server](https://discord.gg/5wtjDkYbVh)**",
                    color=0x004cff
               )
                avatar = getattr(entry.user, 'avatar', None)
                if avatar and hasattr(avatar, 'url') and avatar.url is not None:
                    embed.set_thumbnail(url=avatar.url)
                else:
                    default_avatar = getattr(entry.user, 'default_avatar', None)
                    if default_avatar and hasattr(default_avatar, 'url') and default_avatar.url is not None:
                        embed.set_thumbnail(url=default_avatar.url)
                embed.set_author(name=f"{guild.name}", icon_url=guild.me.display_avatar.url)
               
                website_button = Button(label='Website - Coming Soon', style=discord.ButtonStyle.secondary, disabled=True)
                support_button = Button(label='Support', style=discord.ButtonStyle.link, url='https://discord.gg/5wtjDkYbVh')
                vote_button = Button(label='Vote for Me', style=discord.ButtonStyle.link, url=f'https://top.gg/bot/1414317652066832527/vote')
                view = View()
                view.add_item(support_button)
                view.add_item(website_button)
                #view.add_item(vote_button)
                if guild.icon:
                    embed.set_author(name=guild.name, icon_url=guild.icon.url)
                try:
                    await entry.user.send(embed=embed, view=view)
                except Exception as e:
                    print(e)
