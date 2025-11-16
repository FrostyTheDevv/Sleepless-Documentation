import discord
from discord.ext import commands
from discord import app_commands, Interaction
from difflib import get_close_matches
from contextlib import suppress
from core import Context
from core.sleepless import sleepless
from core.Cog import Cog
from utils.config_utils import getConfig
from itertools import chain
import json
from utils import help as vhelp
from utils import Paginator, DescriptionEmbedPaginator, FieldPagePaginator, TextPaginator
import asyncio
from utils.config import serverLink
from utils.Tools import *

color = 0x185fe5
client = sleepless()

class HelpCommand(commands.HelpCommand):

  async def send_ignore_message(self, ctx, ignore_type: str):

    if ignore_type == "channel":
      await ctx.reply(f"This channel is ignored.", mention_author=False)
    elif ignore_type == "command":
      await ctx.reply(f"{ctx.author.mention} This Command, Channel, or You have been ignored here.", delete_after=6)
    elif ignore_type == "user":
      await ctx.reply(f"You are ignored.", mention_author=False)

  async def on_help_command_error(self, ctx, error):
    errors = [
      commands.CommandOnCooldown, commands.CommandNotFound,
      discord.HTTPException, commands.CommandInvokeError
    ]
    
    # Handle empty message errors specifically
    if isinstance(error, discord.HTTPException) and error.code == 50006:
      try:
        embed = discord.Embed(
          title="❌ Help Error",
          description="Sorry, I couldn't find help information for that command. Use `help` to see all available commands.",
          color=0xFF6B6B
        )
        embed.add_field(name="💡 Tip", value="Try using `help <category>` or `help <command>`", inline=False)
        await ctx.send(embed=embed)
      except Exception as e:
        print(f"[HELP] Error sending help error embed: {e}")
        try:
          await ctx.send("Sorry, I couldn't find that command. Use `help` to see available commands.")
        except:
          pass
      return
    
    # Handle CommandNotFound specifically
    if isinstance(error, commands.CommandNotFound):
      # This should be handled by command_not_found method, but just in case
      try:
        embed = discord.Embed(
          title="❌ Command Not Found",
          description="That command doesn't exist. Use `help` to see all available commands.",
          color=0xFF6B6B
        )
        await ctx.send(embed=embed)
      except:
        try:
          await ctx.send("Command not found. Use `help` to see available commands.")
        except:
          pass
      return
    
    if not type(error) in errors:
      try:
        error_message = str(getattr(error, 'original', error))
        if error_message and error_message.strip():
          embed = discord.Embed(
            title="❌ Help System Error",
            description=f"An error occurred: {error_message[:200]}{'...' if len(error_message) > 200 else ''}",
            color=0xFF6B6B
          )
          await ctx.reply(embed=embed, mention_author=False)
        else:
          embed = discord.Embed(
            title="❌ Help System Error",
            description="An unknown error occurred with the help command.",
            color=0xFF6B6B
          )
          await ctx.reply(embed=embed, mention_author=False)
      except:
        pass
    else:
      if type(error) == commands.CommandOnCooldown:
        return

    return await super().on_help_command_error(ctx, error if isinstance(error, commands.CommandError) else commands.CommandInvokeError(error))

  def command_not_found(self, string: str) -> str:
    # Return a proper error message string that won't be empty
    # The message will be sent by the help system, not by us directly
    
    try:
        cmds = [str(cmd) for cmd in self.context.bot.walk_commands()]
        matches = get_close_matches(string, cmds, n=3, cutoff=0.6)
        
        if matches:
            suggestion_text = ", ".join([f"`{match}`" for match in matches])
            return f"Command `{string}` not found. Did you mean: {suggestion_text}?"
        else:
            return f"Command `{string}` not found. Use `help` to see all available commands."
            
    except Exception as e:
        print(f"[HELP] Error in command_not_found: {e}")
        return f"Command `{string}` not found."

  async def send_bot_help(self, mapping):
    ctx = self.context
    print(f"[HELP] send_bot_help called by {ctx.author} in {ctx.guild.name if ctx.guild else 'DM'}")
    
    check_ignore = await ignore_check().predicate(ctx)
    check_blacklist = await blacklist_check().predicate(ctx)
    
    print(f"[HELP] Blacklist check: {check_blacklist}, Ignore check: {check_ignore}")

    if not check_blacklist:
      print(f"[HELP] User {ctx.author} failed blacklist check")
      return

    if not check_ignore:
      print(f"[HELP] User {ctx.author} failed ignore check")
      await self.send_ignore_message(ctx, "command")
      return

    guild_id = self.context.guild.id if self.context.guild is not None else None
    data = await getConfig(guild_id) if guild_id is not None else {"prefix": "!"}
    prefix = data["prefix"]
    filtered = await self.filter_commands(self.context.bot.walk_commands(), sort=True)

    embed = discord.Embed(
        description=(
          f"**<:sleep_dot:1427471567838777347> Server Prefix:** `{prefix}`\n"
          f"**<:sleep_dot:1427471567838777347> Total Commands:** `{len(set(self.context.bot.walk_commands()))}`\n"
          f"**<:sleep_dot:1427471567838777347> [Get Sleepless](https://discord.com/oauth2/authorize?client_id=1414317652066832527&permissions=8&integration_type=0&scope=bot+applications.commands) | [Support Server](https://discord.gg/5wtjDkYbVh)**\n"
          f"**<:sleep_dot:1427471567838777347> Use `{prefix}showcase` to see setup examples**\n"),
        color=0x185fe5)

    # Core system categories organized by functionality
    embed.add_field(
        name="<:cloud1:1427471615473750039> __**CORE & SECURITY**__",
        value=">>> \n <:security:1428163112409759945> Security & AntiNuke\n"
              " <:mod:1427471611262537830> Moderation Tools\n"
              " <:am:1427471527594692690> Auto Moderation\n"
              " <:file:1427471573304217651> Advanced Logging\n"
              " <:dotdot:1428168822887546930> Ignore System\n"
              " <:bot:1428163130663375029> Admin & Utility\n",
        inline=True
    )
    
    embed.add_field(
        name="<:cloud1:1427471615473750039> __**ENTERTAINMENT & SOCIAL**__", 
        value=">>> \n <:music:1427471622335500439> Music & Audio\n"
              " <:web:1428162947187736679> Fun & AI Generation\n"
              " <:mobile:1427471608062410833> Games & Activities\n"
              " <:web:1428162947187736679> Last.fm Integration (FM)\n"
              " <:web:1428162947187736679> Interactions System\n"
              " <a:loading:1430203733593034893> AFK & Social Status\n",
        inline=True
    )

    embed.add_field(
        name="<:cloud1:1427471615473750039> __**CUSTOMIZATION & AUTOMATION**__",
        value=">>> \n <:voice:1428163515318800524> VoiceMaster & Voice\n"
              " <:plusu:1428164526884257852> Reaction Roles (RR)\n"
              " <:sleep_customrole:1427471561085943988> Custom Roles & Vanity\n"
              " <:ar:1427471532841631855> AutoRole & Auto Systems\n"
              " <:greet:1427471580014837881> Welcomer & Farewell\n"
              " <:clock1:1427471544409657354> Auto React & Responder\n",
        inline=False
    )
    
    embed.add_field(
        name="<:cloud1:1427471615473750039> __**ANALYTICS & PROFESSIONAL**__",
        value=">>> \n <:slash:1428164524372000879> Leveling System\n"
              " <:ppl:1427471598578958386> Global Leaderboard (GLB)\n"
              " <:ppl:1427471598578958386> Trackers & Statistics\n"
              " <:ticket1:1428163964017049690> Ticket & Support System\n"
              " <:confetti:1428163119187890358> Giveaway Management\n"
              " <:woah:1428170830042632292> Sticky Messages\n"
              " <:skull1:1428168178936188968> Jail & Timeout\n"
              " <:tchat:1430364431195570198> Chat Management\n"
              " <:vanity:1428163639814389771> Vanity & Server Rep\n",
        inline=False
    )

    embed.set_footer(
      text=f"Requested by {self.context.author} • Use dropdown to view specific categories",
      icon_url=self.context.author.avatar.url if self.context.author.avatar else self.context.author.default_avatar.url
    )
    
    try:
        # Try to create and send with view
        view = vhelp.View(mapping=mapping, ctx=self.context, homeembed=embed, ui=2)  # type: ignore
        await ctx.reply(embed=embed, view=view)
        print(f"[HELP] Successfully sent help with view for {ctx.author}")
    except Exception as e:
        print(f"[HELP] Error with view system: {e}")
        try:
            # Fallback: send embed without view
            await ctx.reply(embed=embed)
            print(f"[HELP] Successfully sent help without view for {ctx.author}")
        except Exception as e2:
            print(f"[HELP] Critical error sending help embed: {e2}")
            # Last resort: send simple message
            try:
                await ctx.reply("❌ Help system encountered an error. Please try again or contact support.")
            except:
                pass  # If even this fails, there's nothing more we can do

  async def send_command_help(self, command):
    ctx = self.context
    check_ignore = await ignore_check().predicate(ctx)
    check_blacklist = await blacklist_check().predicate(ctx)

    if not check_blacklist:
      return

    if not check_ignore:
      await self.send_ignore_message(ctx, "command")
      return

    sonu = f">>> {command.help}" if command.help else '>>> No Help Provided...'
    embed = discord.Embed(
        description=f"""```xml
<[] = optional | ‹› = required\nDon't type these while using Commands>```\n{sonu}""",
        color=color)
    alias = ' | '.join(command.aliases)

    embed.add_field(name="**Aliases**",
                      value=f"{alias}" if command.aliases else "No Aliases",
                      inline=False)
    embed.add_field(name="**Usage**",
                      value=f"`{self.context.prefix}{command.signature}`\n")
    if self.context.bot.user is not None:
        icon_url = self.context.bot.user.display_avatar.url if hasattr(self.context.bot.user, "display_avatar") else (self.context.bot.user.avatar.url if self.context.bot.user.avatar else self.context.bot.user.default_avatar.url)
    else:
        icon_url = ""
    embed.set_author(name=f"{command.qualified_name.title()} Command",
                       icon_url=icon_url)
    await self.context.reply(embed=embed, mention_author=False)

  def get_command_signature(self, command: commands.Command) -> str:
    parent = command.full_parent_name
    if len(command.aliases) > 0:
      aliases = ' | '.join(command.aliases)
      fmt = f'[{command.name} | {aliases}]'
      if parent:
        fmt = f'{parent}'
      alias = f'[{command.name} | {aliases}]'
    else:
      alias = command.name if not parent else f'{parent} {command.name}'
    return f'{alias} {command.signature}'

  def common_command_formatting(self, embed_like, command):
    embed_like.title = self.get_command_signature(command)
    if command.description:
      embed_like.description = f'{command.description}\n\n{command.help}'
    else:
      embed_like.description = command.help or 'No help found...'

  async def send_group_help(self, group):
    ctx = self.context
    check_ignore = await ignore_check().predicate(ctx)
    check_blacklist = await blacklist_check().predicate(ctx)

    if not check_blacklist:
      return

    if not check_ignore:
      await self.send_ignore_message(ctx, "command")
      return

    def get_all_subcommands(cmd, prefix):
      entries = []
      for sub in cmd.commands:
        usage = f"{prefix}{sub.qualified_name} {sub.signature}".strip()
        doc = sub.short_doc if sub.short_doc else ''
        entries.append((f"➜ `{usage}`\n", f"{doc}\n\u200b"))
        if isinstance(sub, commands.Group):
          entries.extend(get_all_subcommands(sub, prefix))
      return entries

    prefix = self.context.prefix
    entries = get_all_subcommands(group, prefix)
    count = len(entries)

    paginator = Paginator(source=FieldPagePaginator(
      entries=entries,
      title=f"{group.qualified_name.title()} [{count}]",
      description="< > Duty | [ ] Optional\n",
      color=color,
      per_page=4),
                          ctx=self.context)
    await paginator.paginate()

  async def send_cog_help(self, cog):
    ctx = self.context
    check_ignore = await ignore_check().predicate(ctx)
    check_blacklist = await blacklist_check().predicate(ctx)

    if not check_blacklist:
      return

    if not check_ignore:
      await self.send_ignore_message(ctx, "command")
      return

    entries = [(
      f"➜ `{self.context.prefix}{cmd.qualified_name}`",
      f"{cmd.short_doc if cmd.short_doc else ''}"
      f"\n\u200b",
    ) for cmd in cog.get_commands()]
    paginator = Paginator(source=FieldPagePaginator(
      entries=entries,
      title=f"{cog.qualified_name.title()} ({len(cog.get_commands())})",
      description="< > Duty | [ ] Optional\n\n",
      color=color,
      per_page=4),
                          ctx=self.context)
    await paginator.paginate()


class Help(Cog, name="help"):

  def __init__(self, client: sleepless):
    self._original_help_command = client.help_command
    attributes = {
      'name': "help",
      'aliases': ['h'],
      'cooldown': commands.CooldownMapping.from_cooldown(1, 5, commands.BucketType.user),
      'help': 'Shows help about bot, a command, or a category'
    }
    client.help_command = HelpCommand(command_attrs=attributes)
    client.help_command.cog = self

  async def cog_unload(self):
    self.help_command = self._original_help_command
