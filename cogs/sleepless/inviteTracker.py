import discord

from discord.ext import commands

class _inviteTracker(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

    """Invite, VC & Message Tracker"""

    def help_custom(self):

              emoji = '<:ppl:1427471598578958386>'

              label = "Trackers"

              description = "Show you Commands of Invite & Message Tracker"

              return emoji, label, description

    @commands.group()

    async def __Trackers__(self, ctx: commands.Context):

        """**INVITE TRACKER**\n`$Inviteenable` , `$Invitedisable `, `$invites` , `$invited` , `$inviter` , `$resetinvites` , `$addinvites` , `$removeinvites` , `$resetserverinvites` , `$inviteleaderboard`\n\n**JOINCHANNEL**\n`$joinchannnel add`,`$joinchannel remove` , `$joinchannel list` , `$joinchannel setmessage` , `$joinchannel list` , `$joinchannel viewmessage`\n\n**MESSAGES TRACKER**\n`$messages` , `$removemsg` , `$addmsg` , `$clearmsg` , `$messageleaderboard`\n\n**VC TRACKER**\n`vctrack` , `vctime add {user} {seconds} , vctime remove {user} {seconds}` , `vctime reset {user}`"""