import discord
from discord.ext import commands
from discord import ui
from typing import Optional

class LockUnlockView(ui.View):
    def __init__(self, channel, author, ctx):
        super().__init__(timeout=120)
        self.channel = channel
        self.author = author
        self.ctx = ctx  
        self.message: Optional[discord.Message] = None  

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("You are not allowed to interact with this!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            if hasattr(item, 'label') and getattr(item, 'label', None) != "Delete":
                try:
                    item.disabled = True  # type: ignore[attr-defined]
                except Exception:
                    pass
        if self.message and hasattr(self.message, 'edit') and callable(self.message.edit):
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @ui.button(label="Unlock", style=discord.ButtonStyle.success)
    async def unlock(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.channel and interaction.guild:
            if isinstance(self.channel, discord.Thread):
                # For threads, we manage the archive/lock state
                if self.channel.locked:
                    await self.channel.edit(locked=False)
                if self.channel.archived:
                    await self.channel.edit(archived=False)
            elif hasattr(interaction.guild, 'default_role'):
                # For text channels, manage permissions
                await self.channel.set_permissions(interaction.guild.default_role, send_messages=True)
        
        channel_type = "Thread" if isinstance(self.channel, discord.Thread) else "Channel"
        await interaction.response.send_message(f"{self.channel.mention} has been unlocked.", ephemeral=True)

        embed = discord.Embed(
            description=f"<:feast_channels:1400425854294560829>**{channel_type}**: {self.channel.mention}\n<:feast_tick:1400143469892210753> **Status**: Unlocked\n<:Commands:1329004882992300083>**Reason:** Unlock request by {self.author}",
            color=0x006fb9
        )
        embed.add_field(name="<:Feast_staff:1228227884481515613> **Moderator:**", value=self.ctx.author.mention, inline=False)
        embed.set_author(name=f"Successfully Unlocked {self.channel.name}", icon_url="https://cdn.discordapp.com/attachments/1329411292532051999/1329451540028719255/Feast_X.jpeg?ex=678a63bb&is=6789123b&hm=917647b44f40b887260074c1ccc602f0b7b8f4054c18ccc5ab6a5824bf77a9aa&")
        if self.message and hasattr(self.message, 'edit') and callable(self.message.edit):
            try:
                await self.message.edit(embed=embed, view=self)
            except Exception:
                pass

        for item in self.children:
            if hasattr(item, 'label') and getattr(item, 'label', None) != "Delete":
                try:
                    item.disabled = True  # type: ignore[attr-defined]
                except Exception:
                    pass
        if self.message and hasattr(self.message, 'edit') and callable(self.message.edit):
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @ui.button(style=discord.ButtonStyle.gray, emoji="<:feast_delete:1400140670659989524>")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.message:
            await interaction.message.delete()


class Lock(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = discord.Color.from_rgb(0, 0, 0)

    @commands.hybrid_command(
        name="lock",
        help="Locks a channel or thread to prevent sending messages.",
        usage="lock <channel/thread>",
        aliases=["lockchannel", "lockthread"])
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def lock_command(self, ctx, channel: 'discord.TextChannel | discord.Thread | None' = None):
        # Accept None for channel, but ensure type safety
        if channel is None:
            if isinstance(ctx.channel, (discord.TextChannel, discord.Thread)):
                channel = ctx.channel
            else:
                await ctx.send("This command must be used in a text channel/thread or specify a text channel/thread.")
                return
        
        # Check if already locked
        is_locked = False
        if isinstance(channel, discord.Thread):
            is_locked = channel.locked
        elif isinstance(channel, discord.TextChannel):
            is_locked = channel.permissions_for(ctx.guild.default_role).send_messages is False
        
        channel_type = "Thread" if isinstance(channel, discord.Thread) else "Channel"
        
        if is_locked:
            embed = discord.Embed(
                description=f"**<:feast_channels:1400425854294560829>{channel_type}**: {channel.mention}\n<:feast_tick:1400143469892210753> **Status**: Already Locked",
                color=self.color
            )
            embed.set_author(name=f"{channel.name} is Already Locked", icon_url="https://cdn.discordapp.com/attachments/1329411292532051999/1329451540028719255/Feast_X.jpeg?ex=678a63bb&is=6789123b&hm=917647b44f40b887260074c1ccc602f0b7b8f4054c18ccc5ab6a5824bf77a9aa&")
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url)
            view = LockUnlockView(channel=channel, author=ctx.author, ctx=ctx)  
            message = await ctx.send(embed=embed, view=view)
            view.message = message
            return

        # Lock the channel/thread
        if isinstance(channel, discord.Thread):
            await channel.edit(locked=True)
        else:
            await channel.set_permissions(ctx.guild.default_role, send_messages=False)

        embed = discord.Embed(
            description=f"<:feast_channels:1400425854294560829>**{channel_type}**: {channel.mention}\n<:feast_tick:1400143469892210753> **Status**: Locked\n<:Commands:1329004882992300083> **Reason:** Lock request by {ctx.author}",
            color=self.color
        )
        embed.add_field(name="<:U_admin:1327829252120510567> **Moderator:**", value=ctx.author.mention, inline=False)
        embed.set_author(name=f"Successfully Locked {channel.name}", icon_url="https://cdn.discordapp.com/attachments/1329411292532051999/1329451540028719255/Feast_X.jpeg?ex=678a63bb&is=6789123b&hm=917647b44f40b887260074c1ccc602f0b7b8f4054c18ccc5ab6a5824bf77a9aa&")
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url)
        view = LockUnlockView(channel=channel, author=ctx.author, ctx=ctx)  
        message = await ctx.send(embed=embed, view=view)
        view.message = message


"""
@Author: Frosty
    + Discord: frosty.pyro
    + Community: https://discord.gg/5wtjDkYbVh (Sleepless Development)
    + for any queries reach out in the server; or send a dm.
"""