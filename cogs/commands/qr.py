import discord
from discord.ext import commands
from utils.config import PAYPAL_EMAIL, SUBSCRIPTION_PRICES

from utils.error_helpers import StandardErrorHandler
class QR(commands.Cog):
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot

    @commands.command(
        name="qr",
        aliases=["qrcode", "payment"],
        help="View payment information and QR codes.",
        with_app_command=True
    )
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def qr(self, ctx):
        embed = discord.Embed(
            title="💳 Payment Platform - Sleepless",
            description="Subscribe to premium features and support development!",
            color=0x0070ba
        )

        embed.add_field(
            name="💰 PayPal Email",
            value=f"`{PAYPAL_EMAIL}`",
            inline=False
        )

        embed.add_field(
            name="📋 Subscription Plans",
            value="\n".join([f"• **{k.upper()}**: ${v}" for k, v in SUBSCRIPTION_PRICES.items() if v > 0]),
            inline=False
        )

        embed.add_field(
            name="🎯 How to Subscribe",
            value="Use `$subscribe` to view all plans and start the payment process",
            inline=False
        )

        embed.add_field(
            name="📝 Payment Notes",
            value="• Always include your Discord ID in payment notes\n• Payments are verified within 5 minutes\n• Premium features activate automatically",
            inline=False
        )

        embed.set_footer(text="Sleepless Development", icon_url=self.bot.user.avatar.url)

        await ctx.reply(embed=embed)

    @qr.error
    async def qr_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.reply("❌ You must be an **administrator** to use this command.")
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.reply(f"⏳ You're on cooldown. Try again in `{round(error.retry_after, 1)}s`.")
        else:
            await ctx.reply(f"⚠️ An error occurred: `{str(error)}`")

# Required for bot.load_extension()
async def setup(bot):
    await bot.add_cog(QR(bot))
