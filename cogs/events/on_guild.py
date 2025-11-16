from discord.ext import commands
from core import sleepless, Cog
import discord
import logging
from discord.ui import View, Button, Select

logging.basicConfig(
    level=logging.INFO,
    format="\x1b[38;5;197m[\x1b[0m%(asctime)s\x1b[38;5;197m]\x1b[0m -> \x1b[38;5;197m%(message)s\x1b[0m",
    datefmt="%H:%M:%S",
)

client = sleepless()

class Guild(Cog):
    def __init__(self, client: sleepless):
        self.client = client

    @client.event
    @commands.Cog.listener(name="on_guild_join")
    async def on_guild_add(self, guild):
        try:
            
            rope = [inv for inv in await guild.invites() if inv.max_age == 0 and inv.max_uses == 0]
            ch = 1396762457732550717  
            me = self.client.get_channel(ch)
            if me is None:
                logging.error(f"Channel with ID {ch} not found.")
                return

            channels = len(set(self.client.get_all_channels()))
            embed = discord.Embed(title=f"{guild.name}'s Information", color=0x006fb9)
            
            embed.set_author(name="Guild Joined")
            embed.set_footer(text=f"Added in {guild.name}")

            embed.add_field(
                name="**__About__**",
                value=f"**Name : ** {guild.name}\n**ID :** {guild.id}\n**Owner <:owner:1329041011984433185> :** {guild.owner} (<@{guild.owner_id}>)\n**Created At : **{guild.created_at.month}/{guild.created_at.day}/{guild.created_at.year}\n**Members :** {len(guild.members)}",
                inline=False
            )
            embed.add_field(
                name="**__Description__**",
                value=f"""{guild.description}""",
                inline=False
            )
            embed.add_field(
                name="**__Members__**",
                value=f"""<:riverse_fun:1327829569264160870> Members : {len(guild.members)}\n <:user:1329379728603353108> Humans : {len(list(filter(lambda m: not m.bot, guild.members)))}\n<:icons_bot:1327829370881966092> Bots : {len(list(filter(lambda m: m.bot, guild.members)))}
                """,
                inline=False
            )
            embed.add_field(
                name="**__Channels__**",
                value=f"""
Categories : {len(guild.categories)}
Text Channels : {len(guild.text_channels)}
Voice Channels : {len(guild.voice_channels)}
Threads : {len(guild.threads)}
                """,
                inline=False
            )  
            embed.add_field(name="__Bot Stats:__", 
            value=f"Servers: `{len(self.client.guilds)}`\nUsers: `{len(self.client.users)}`\nChannels: `{channels}`", inline=False)  

            if guild.icon is not None:
                embed.set_thumbnail(url=guild.icon.url)

            embed.timestamp = discord.utils.utcnow()
            from discord.abc import Messageable
            if isinstance(me, Messageable):
                await me.send(f"{rope[0]}" if rope else "No Pre-Made Invite Found", embed=embed)
            else:
                logging.error(f"'me' object does not support sending messages.")

            if not guild.chunked:
                await guild.chunk()

            # Get server prefix
            from utils.config_utils import getConfig
            config = await getConfig(guild.id)
            prefix = config.get("prefix", "$") if config else "$"
            
            # Get total command count dynamically
            total_commands = len([cmd for cmd in self.client.walk_commands()])
            
            embed = discord.Embed(
                title="Welcome to SleeplessPY",
                description=(
                    f"Thank you for adding **SleeplessPY** to **{guild.name}**.\n"
                    f"**{total_commands}** commands available — Your server prefix is `{prefix}`\n"
                    f"Use `{prefix}help` to get started."
                ),
                color=0x2f3136
            )
            
            # Core Features
            embed.add_field(
                name="Core Features",
                value=(
                    f"`{prefix}antinuke` — Professional-grade security system\n"
                    f"`{prefix}vanity` — Custom vanity URL management\n"
                    f"`{prefix}greet` / `{prefix}farewell` — Welcome/goodbye messages\n"
                    f"`{prefix}levels` — XP system with rank cards\n"
                    f"`{prefix}arl` — Autorole lists & configurations\n"
                    f"`{prefix}rr` — Reaction role panels\n"
                    f"`{prefix}voicemaster` — Temporary voice channels\n"
                    f"`{prefix}ticket` — Support ticket system\n"
                    f"`{prefix}sticky` — Sticky messages\n"
                    f"`{prefix}poj` — Ping on join notifications"
                ),
                inline=False
            )
            
            # Quick Start
            embed.add_field(
                name="Quick Start",
                value=(
                    f"1. Move SleeplessPY to the top of your role list\n"
                    f"2. Run `{prefix}antinuke enable` for protection\n"
                    f"3. Use `{prefix}help` to explore all commands"
                ),
                inline=False
            )
            
            embed.set_author(
                name="SleeplessPY • Enterprise Discord Bot", 
                icon_url=self.client.user.display_avatar.url if self.client.user else None
            )
            
            embed.set_footer(
                text=f"Developed by Frosty • {prefix}help for commands • Version 2.0",
                icon_url=self.client.user.display_avatar.url if self.client.user else None
            )
            
            if guild.icon:
                embed.set_thumbnail(url=guild.icon.url)

            # Create comprehensive button view with interaction handling
            class WelcomeView(View):
                def __init__(self):
                    super().__init__(timeout=None)
                    
                @discord.ui.button(
                    label='Getting Started', 
                    style=discord.ButtonStyle.secondary,
                    emoji='🚀',
                    custom_id='help_getting_started'
                )
                async def getting_started(self, interaction: discord.Interaction, button: Button):
                    help_embed = discord.Embed(
                        title="🚀 Getting Started with SleeplessPY",
                        description=(
                            "**Essential First Steps:**\n\n"
                            "**1.** Move SleeplessPY to the top of your roles\n"
                            "**2.** Run `$antinuke enable` for security\n"
                            "**3.** Try `$play [song]` for music\n"
                            "**4.** Use `$help` to explore all features\n\n"
                            "**Need help?** Join our support server!"
                        ),
                        color=0x185fe5
                    )
                    await interaction.response.send_message(embed=help_embed, ephemeral=True)
                
                @discord.ui.button(
                    label='Feature Examples', 
                    style=discord.ButtonStyle.primary,
                    emoji='🌟',
                    custom_id='feature_examples'
                )
                async def feature_examples(self, interaction: discord.Interaction, button: Button):
                    examples_embed = discord.Embed(
                        title="🌟 Feature Examples & Tutorials",
                        description=(
                            "**Quick Start Examples:**\n\n"
                            "🎵 **Music Setup**: `$play [song]` → `$queue` → `$volume 75`\n"
                            "🛡️ **Server Protection**: `$antinuke enable` → `$automod enable`\n"
                            "🎭 **Voice Channels**: `$voicemaster setup #category`\n"
                            "🎮 **Reaction Roles**: `$rr create #roles 'Pick your roles!'`\n\n"
                            "**Use `$showcase [category]` for detailed tutorials:**\n"
                            "• `$showcase gaming` - Gaming server setup\n"
                            "• `$showcase professional` - Business server config\n"
                            "• `$showcase music` - Advanced music features\n"
                            "• `$showcase troubleshoot` - Common solutions\n\n"
                            "**💡 Pro Tip**: Use `$examples quick` for instant setups!"
                        ),
                        color=0xf39c12
                    )
                    await interaction.response.send_message(embed=examples_embed, ephemeral=True)
            
            support_button = Button(
                label='Support Server',
                style=discord.ButtonStyle.link,
                url='https://discord.gg/5wtjDkYbVh',
                emoji='�'
            )
            
            invite_button = Button(
                label='Invite Bot',
                style=discord.ButtonStyle.link,
                url='https://discord.com/oauth2/authorize?client_id=1414317652066832527&permissions=8&integration_type=0&scope=bot+applications.commands',
                emoji='🔗'
            )
            
            view = WelcomeView()
            view.add_item(support_button)
            view.add_item(invite_button)
            # Find the best channel to send the welcome message
            channel = None
            
            # Priority order: general, welcome, announcements, first available channel
            preferred_names = ['general', 'welcome', 'announcements', 'chat', 'main']
            
            for name in preferred_names:
                channel = discord.utils.get(guild.text_channels, name=name)
                if channel and channel.permissions_for(guild.me).send_messages:
                    break
            
            # If no preferred channel found, find any channel we can send to
            if not channel:
                channels = [ch for ch in guild.text_channels 
                           if ch.permissions_for(guild.me).send_messages and 
                           ch.permissions_for(guild.me).embed_links]
                if channels:
                    # Sort by position to get the topmost channel
                    channel = sorted(channels, key=lambda x: x.position)[0]
                else:
                    logging.warning(f"No suitable channel found for welcome message in guild: {guild.name}")
                    return

            # Send the comprehensive welcome message
            try:
                from discord.abc import Messageable
                if isinstance(channel, Messageable):
                    welcome_msg = await channel.send(embed=embed, view=view)
                    channel_name = getattr(channel, 'name', 'Unknown Channel')
                    logging.info(f"Welcome message sent to {guild.name} ({guild.id}) in #{channel_name}")
                    
                    # Add the view to the bot for persistent interactions
                    self.client.add_view(view)
                    
                else:
                    logging.error(f"Channel {channel} does not support sending messages.")
            except discord.Forbidden:
                logging.warning(f"Missing permissions to send welcome message in {guild.name}")
            except discord.HTTPException as e:
                logging.error(f"HTTP error sending welcome message to {guild.name}: {e}")
            except Exception as e:
                logging.error(f"Unexpected error sending welcome message to {guild.name}: {e}")

        except Exception as e:
            logging.error(f"Error in on_guild_join: {e}")

    @client.event
    @commands.Cog.listener(name="on_guild_remove")
    async def on_guild_remove(self, guild):
        try:
            ch = 1271825683672203294  
            idk = self.client.get_channel(ch)
            if idk is None:
                logging.error(f"Channel with ID {ch} not found.")
                return

            channels = len(set(self.client.get_all_channels()))
            embed = discord.Embed(title=f"{guild.name}'s Information", color=0x006fb9)
        
            embed.set_author(name="Guild Removed")
            embed.set_footer(text=f"{guild.name}")

            embed.add_field(
                name="**__About__**",
                value=f"**Name : ** {guild.name}\n**ID :** {guild.id}\n**Owner <:feast_owner:1228227536207740989> :** {guild.owner} (<@{guild.owner_id}>)\n**Created At : **{guild.created_at.month}/{guild.created_at.day}/{guild.created_at.year}\n**Members :** {len(guild.members)}",
                inline=False
            )
            embed.add_field(
                name="**__Description__**",
                value=f"""{guild.description}""",
                inline=False
            )
            
                
            embed.add_field(
                name="**__Members__**",
                value=f"""
Members : {len(guild.members)}
Humans : {len(list(filter(lambda m: not m.bot, guild.members)))}
Bots : {len(list(filter(lambda m: m.bot, guild.members)))}
                """,
                inline=False
            )
            embed.add_field(
                name="**__Channels__**",
                value=f"""
Categories : {len(guild.categories)}
Text Channels : {len(guild.text_channels)}
Voice Channels : {len(guild.voice_channels)}
Threads : {len(guild.threads)}
                """,
                inline=False
            )   
            embed.add_field(name="__Bot Stats:__", 
            value=f"Servers: `{len(self.client.guilds)}`\nUsers: `{len(self.client.users)}`\nChannels: `{channels}`", inline=False)

            if guild.icon is not None:
                embed.set_thumbnail(url=guild.icon.url)

            embed.timestamp = discord.utils.utcnow()
            from discord.abc import Messageable
            if isinstance(idk, Messageable):
                await idk.send(embed=embed)
            else:
                logging.error(f"'idk' object does not support sending messages.")
        except Exception as e:
            logging.error(f"Error in on_guild_remove: {e}")
    
    @commands.command(name="testwelcome", aliases=["testwelcomemsg", "testguildjoin"])
    @commands.has_permissions(administrator=True)
    async def test_welcome(self, ctx):
        """Test the guild welcome message (Admin only)"""
        try:
            # Reuse the same welcome message logic from on_guild_join
            guild = ctx.guild
            
            # Get server prefix
            from utils.config_utils import getConfig
            prefix = (await getConfig(guild.id)).get("prefix", "$")
            
            # Get total command count dynamically
            total_commands = len([cmd for cmd in self.client.walk_commands()])
            
            embed = discord.Embed(
                title="Welcome to SleeplessPY",
                description=(
                    f"Thank you for adding **SleeplessPY** to **{guild.name}**.\n"
                    f"**{total_commands}** commands available — Your server prefix is `{prefix}`\n"
                    f"Use `{prefix}help` to get started."
                ),
                color=0x185fe5
            )
            
            # Core Features
            embed.add_field(
                name="Core Features",
                value=(
                    f"`{prefix}antinuke` — Professional-grade security system\n"
                    f"`{prefix}vanity` — Custom vanity URL management\n"
                    f"`{prefix}greet` / `{prefix}farewell` — Welcome/goodbye messages\n"
                    f"`{prefix}levels` — XP system with rank cards\n"
                    f"`{prefix}arl` — Autorole lists & configurations\n"
                    f"`{prefix}rr` — Reaction role panels\n"
                    f"`{prefix}voicemaster` — Temporary voice channels\n"
                    f"`{prefix}ticket` — Support ticket system\n"
                    f"`{prefix}sticky` — Sticky messages\n"
                    f"`{prefix}poj` — Ping on join notifications"
                ),
                inline=False
            )
            
            # Quick Start
            embed.add_field(
                name="Quick Start",
                value=(
                    f"1. Move SleeplessPY to the top of your role list\n"
                    f"2. Run `{prefix}antinuke enable` for protection\n"
                    f"3. Use `{prefix}help` to explore all commands"
                ),
                inline=False
            )
            
            embed.set_author(
                name="SleeplessPY • Enterprise Discord Bot", 
                icon_url=self.client.user.display_avatar.url if self.client.user else None
            )
            
            embed.set_footer(
                text=f"Developed by Frosty • {prefix}help for commands • Version 2.0 • TEST MESSAGE",
            )
            
            if guild.icon:
                embed.set_thumbnail(url=guild.icon.url)

            # Create comprehensive button view with interaction handling
            class WelcomeView(View):
                def __init__(self):
                    super().__init__(timeout=None)
                    
                @discord.ui.button(
                    label='Getting Started', 
                    style=discord.ButtonStyle.secondary,
                    emoji='🚀',
                    custom_id='help_getting_started'
                )
                async def getting_started(self, interaction: discord.Interaction, button: Button):
                    help_embed = discord.Embed(
                        title="🚀 Getting Started with SleeplessPY",
                        description=(
                            "**Essential First Steps:**\n\n"
                            "**1.** Move SleeplessPY to the top of your roles\n"
                            "**2.** Run `$antinuke enable` for security\n"
                            "**3.** Try `$play [song]` for music\n"
                            "**4.** Use `$help` to explore all features\n\n"
                            "**Need help?** Join our support server!"
                        ),
                        color=0x185fe5
                    )
                    await interaction.response.send_message(embed=help_embed, ephemeral=True)
                
                @discord.ui.button(
                    label='Feature Examples', 
                    style=discord.ButtonStyle.primary,
                    emoji='🌟',
                    custom_id='feature_examples'
                )
                async def feature_examples(self, interaction: discord.Interaction, button: Button):
                    examples_embed = discord.Embed(
                        title="🌟 Feature Examples & Tutorials",
                        description=(
                            "**Quick Start Examples:**\n\n"
                            "🎵 **Music Setup**: `$play [song]` → `$queue` → `$volume 75`\n"
                            "🛡️ **Server Protection**: `$antinuke enable` → `$automod enable`\n"
                            "🎭 **Voice Channels**: `$voicemaster setup #category`\n"
                            "🎮 **Reaction Roles**: `$rr create #roles 'Pick your roles!'`\n\n"
                            "**Use `$showcase [category]` for detailed tutorials:**\n"
                            "• `$showcase gaming` - Gaming server setup\n"
                            "• `$showcase professional` - Business server config\n"
                            "• `$showcase music` - Advanced music features\n"
                            "• `$showcase troubleshoot` - Common solutions\n\n"
                            "**💡 Pro Tip**: Use `$examples quick` for instant setups!"
                        ),
                        color=0xf39c12
                    )
                    await interaction.response.send_message(embed=examples_embed, ephemeral=True)
            
            support_button = Button(
                label='Support Server',
                style=discord.ButtonStyle.link,
                url='https://discord.gg/5wtjDkYbVh',
                emoji='💬'
            )
            
            invite_button = Button(
                label='Invite Bot',
                style=discord.ButtonStyle.link,
                url='https://discord.com/oauth2/authorize?client_id=1414317652066832527&permissions=8&integration_type=0&scope=bot+applications.commands',
                emoji='🔗'
            )
            
            view = WelcomeView()
            view.add_item(support_button)
            view.add_item(invite_button)
            
            await ctx.send(embed=embed, view=view)
            logging.info(f"Test welcome message sent in {guild.name} by {ctx.author}")
            
        except Exception as e:
            await ctx.send(f"❌ Error sending test welcome message: {str(e)}")
            logging.error(f"Error in test_welcome command: {e}")

#client.add_cog(Guild(client))




