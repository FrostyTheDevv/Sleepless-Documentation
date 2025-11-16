# VoiceMaster temp channel system
from __future__ import annotations
from .commands.voicemaster import VoiceMaster
from core import sleepless
from colorama import Fore, Style

# ---------- Commands ---------- #
from .commands.help import Help
from .commands.showcase import Showcase
# AccessPanel verification system
from .commands.accesspanel import AccessPanel
from .commands.InviteTracker import invitetracker
#from .commands.joinchannel import joinchannel
from .commands.buttonroles import ButtonRoles
from .commands.giveaway import Giveaway
from .commands.autonick import AutoNick
from .commands.team import Team
from .commands.links import Links
from .commands.vote import Vote
from .commands.general import General
from .commands.music import Music
from .commands.automod import Automod
from .commands.welcome import Welcomer
from .commands.farewell import Farewell
from .commands.fun import Fun
from .commands.Games import Games
from .commands.extra import Extra
from .commands.owner import Owner, Badges
from .commands.voice import Voice
from .commands.afk import afk
from .commands.ignore import Ignore
from .commands.Media import Media
from .commands.Invc import Invcrole
from .commands.giveaway import Giveaway
from .commands.Embed import Embed
from .commands.steal import Steal
from .commands.msgpack import Messagespack
from .commands.ship import Ship
from .commands.timer import Timer
from .commands.blacklist import Blacklist
from .commands.block import Block
from .commands.ryzenmode import ryzenmode
from .commands.button import ButtonManager
from .commands.vctracker import VCTracker 
from .commands.map import Map
from .commands.autoresponder import AutoResponder
from .commands.customrole import Customrole
from .commands.joinchannel import joinchannel
from .commands.logging import Logging
from .commands.translate import TranslateCog
from .commands.jail import Jail
from .commands.custom_permissions import CustomPermissions
from .commands.role_restoration import RoleRestoration
from .commands.advanced_permissions import AdvancedPermissions
from .commands.member_state_commands import MemberStateCommands
# DISABLED: Role persistence system - causes performance issues with high member turnover
# from .events.member_state_handler import MemberStateHandler
from .commands.suggestion import Suggestion
from .commands.antinuke import Antinuke
from .commands.extraown import Extraowner
from .commands.anti_wl import Whitelist
from .commands.anti_unwl import Unwhitelist
from .commands.slots import Slots
from .commands.blackjack import Blackjack
from .commands.autoreact import AutoReaction
from .commands.stats import Stats
from .commands.emergency import Emergency
from .commands.notify import NotifCommands
from .commands.status import Status
from .commands.np import NoPrefix
from .commands.filters import FilterCog
from .commands.owner2 import Global
from .commands.arole import Arole
from .commands.ar import ARL
from .commands.payment import Payment
#from .commands.vanityroles import Vanityroles
from .commands.reactionroles import ReactionRoles 
from .commands.messages import Messages
from .commands.say import Say
from .commands.tickets import Tickets
from .commands.customize import customize
from .commands.br import BoosterRoles
from .commands.sticky import StickyMessages
from .commands.timezone import TimezoneCommands
from .commands.pingonjoin import PingOnJoin
from .commands.leveling import LevelingSystem
from .commands.comprehensive_stats import ComprehensiveStats
from .commands.greet_test import GreetTest
from .commands.interactions import Interactions
from .commands.lastfm import LastFMCog
from .commands.live_leaderboard import LiveLeaderboard
from .commands.clans import ClanSystem

# ---------- Events ---------- #
from .events.autoblacklist import AutoBlacklist
from .events.Errors import Errors
from .events.error_handler import ErrorHandler
from .events.on_guild import Guild
from .events.autorole import Autorole2
from .events.greet2 import greet
from .events.mention import Mention
from .events.react import React
from .events.autoreact import AutoReactListener
from .events.booster_messages import BoosterMessages

# ---------- Help Categories ---------- #
from .sleepless.antinuke import _antinuke
from .sleepless.extra import _extra
from .sleepless.general import _general
from .sleepless.automod import _automod 
from .sleepless.moderation import _moderation
from .sleepless.music import _music
from .sleepless.fun import _fun
from .sleepless.games import _games
from .sleepless.ignore import _ignore
from .sleepless.server import _server
from .sleepless.voice import _voice 
from .sleepless.welcome import _welcome 
from .sleepless.farewell import _farewell 
from .sleepless.giveaway import _giveaway
from .sleepless.logging import Loggingdrop
from .commands.vanity import VanitySystem
from .sleepless.inviteTracker import _inviteTracker
# from .sleepless.leveling import _leveling  # Disabled - conflicts with LevelingSystem
from .sleepless.interactions import _interactions
from .sleepless.afk import _afk
from .sleepless.reactionroles import _reactionroles
from .sleepless.jail import _jail
from .sleepless.chatmanagement import _chatmanagement
from .sleepless.tickets import _tickets
from .sleepless.voicemaster import _voicemaster
from .sleepless.sticky import _sticky
from .sleepless.boosterroles import _boosterroles
from .sleepless.messageTracker import _MessageTracker
from .sleepless.ticket import _ticket

# ---------- Antinuke Events ---------- #
from .antinuke.anti_member_update import AntiMemberUpdate
from .antinuke.antiban import AntiBan
from .antinuke.antibotadd import AntiBotAdd
from .antinuke.antichcr import AntiChannelCreate
from .antinuke.antichdl import AntiChannelDelete
from .antinuke.antichup import AntiChannelUpdate
from .antinuke.antiemocr import AntiEmojiCreate
from .antinuke.antiemodl import AntiEmojiDelete
from .antinuke.antiemoup import AntiEmojiUpdate
from .antinuke.antieveryone import AntiEveryone
from .antinuke.antiguild import AntiGuild
from .antinuke.antiIntegration import AntiIntegration
from .antinuke.antikick import AntiKick
from .antinuke.antiprune import AntiPrune
from .antinuke.antirlcr import AntiRoleCreate
from .antinuke.antirldl import AntiRoleDelete
from .antinuke.antirlup import AntiRoleUpdate
from .antinuke.antisticker import AntiSticker
from .antinuke.antiunban import AntiUnban
from .antinuke.antiwebhook import AntiWebhookUpdate
from .antinuke.antiwebhookcr import AntiWebhookCreate
from .antinuke.antiwebhookdl import AntiWebhookDelete

# ---------- Automod ---------- #
from .automod.antispam import AntiSpam
from .automod.anticaps import AntiCaps
from .automod.antilink import AntiLink
from .automod.anti_invites import AntiInvite
from .automod.anti_mass_mention import AntiMassMention
from .automod.anti_emoji_spam import AntiEmojiSpam

# ---------- Moderation ---------- #
from .moderation.ban import Ban
from .moderation.unban import Unban
from .moderation.timeout import Mute
from .moderation.unmute import Unmute
from .moderation.lock import Lock
from .moderation.unlock import Unlock
from .moderation.hide import Hide
from .moderation.unhide import Unhide
from .moderation.kick import Kick
from .moderation.warn import Warn
from .moderation.role import Role
from .moderation.message import Message
from .moderation.moderation import Moderation
from .moderation.topcheck import TopCheck
from .moderation.snipe import Snipe


async def setup(bot: sleepless):
    cogs_to_load = [
        Help, Showcase, Vote, General, Moderation, Automod, Welcomer, Farewell, Fun, Games, Extra,
        Voice, Owner, Customrole, afk, Embed, Media, Ignore, Logging,
        Invcrole, Steal, Ship, Timer,
        Blacklist, Block, ryzenmode, Badges, Antinuke, Whitelist, 
        Unwhitelist, Extraowner, Blackjack, Slots, Team,
        AutoBlacklist, Suggestion, Guild, Errors, ErrorHandler, greet, AutoResponder,
        Mention, React, AntiMemberUpdate, AntiBan, AntiBotAdd,
        AntiChannelCreate, AntiChannelDelete, AntiChannelUpdate, 
        AntiEmojiCreate, AntiEmojiDelete, AntiEmojiUpdate,
        AntiEveryone, AntiGuild, AntiIntegration, AntiKick, AntiPrune, 
        AntiRoleCreate, AntiRoleDelete, AntiRoleUpdate, 
        AntiSticker, AntiUnban,
        AntiWebhookUpdate, AntiWebhookCreate, AntiWebhookDelete, 
        AntiSpam, AntiCaps, AntiLink, AntiInvite, AntiMassMention, Music, 
        Stats, Emergency, Status, NoPrefix, FilterCog, AutoReaction, AutoReactListener, 
        Ban, Unban, Mute, Unmute, Lock, Unlock, Hide, Unhide, Kick, Warn, Role, 
        Message, TopCheck, Snipe, Global, ReactionRoles, Messages, Payment, 
        TranslateCog, Jail, CustomPermissions, RoleRestoration, AdvancedPermissions, MemberStateCommands, Messagespack, Links, VCTracker, Map, AutoNick, 
        ButtonRoles, NotifCommands, Giveaway, Say, Tickets, Arole, ARL, AccessPanel, VoiceMaster, invitetracker, customize, BoosterRoles, StickyMessages, TimezoneCommands, PingOnJoin, LevelingSystem, BoosterMessages, GreetTest, Interactions, LastFMCog, LiveLeaderboard, ComprehensiveStats, ButtonManager, ClanSystem #Vanityroles,
    ]

    for cog in cogs_to_load:
        try:
            print(f"[DEBUG] Adding cog: {cog.__name__}")
            await bot.add_cog(cog(bot))
            print(Fore.BLUE + Style.BRIGHT + f"Loaded cog: {cog.__name__}")
        except Exception as e:
            # Print full traceback to diagnose cog loading issues (helps find where errors originate)
            import traceback
            print(Fore.RED + Style.BRIGHT + f"Failed to load cog {getattr(cog, '__name__', str(cog))}: {e}")
            traceback.print_exc()

    # Help categories
    await bot.add_cog(_antinuke(bot))
    await bot.add_cog(_extra(bot))
    await bot.add_cog(_general(bot))
    await bot.add_cog(_automod(bot))  
    await bot.add_cog(_moderation(bot))
    await bot.add_cog(_music(bot))
    await bot.add_cog(_fun(bot))
    await bot.add_cog(_games(bot))
    await bot.add_cog(_ignore(bot))
    await bot.add_cog(_server(bot))
    await bot.add_cog(_voice(bot))   
    await bot.add_cog(_welcome(bot))
    await bot.add_cog(_farewell(bot))
    await bot.add_cog(_giveaway(bot))
    await bot.add_cog(Loggingdrop(bot))
    await bot.add_cog(VanitySystem(bot))
    await bot.add_cog(_inviteTracker(bot))
    # await bot.add_cog(_leveling(bot))  # Disabled - conflicts with LevelingSystem
    await bot.add_cog(_interactions(bot))
    await bot.add_cog(_afk(bot))
    await bot.add_cog(_reactionroles(bot))
    await bot.add_cog(_jail(bot))
    await bot.add_cog(_chatmanagement(bot))
    await bot.add_cog(_tickets(bot))
    # await bot.add_cog(_voicemaster(bot))  # Disabled - conflicts with main VoiceMaster
    await bot.add_cog(_sticky(bot))
    await bot.add_cog(_boosterroles(bot))
    await bot.add_cog(_MessageTracker(bot))
    await bot.add_cog(_ticket(bot))

    print(Fore.GREEN + Style.BRIGHT + "✅ All feast cogs loaded successfully.")
