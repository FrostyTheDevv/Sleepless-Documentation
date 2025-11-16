import discord
from discord.ext import commands
from discord import ui
import aiohttp
import json
from datetime import datetime, timedelta, timezone
from utils.config import PAYPAL_EMAIL, SUBSCRIPTION_PRICES, OWNER_IDS
from utils.timezone_helpers import get_timezone_helpers
import aiosqlite
import os

from utils.error_helpers import StandardErrorHandler
class SubscriptionSelect(ui.Select):
    def __init__(self, user):
        self.user = user
        options = [
            discord.SelectOption(
                label="10 Minutes Trial",
                description="Free trial - No prefix for 10 minutes",
                value="10m",
                emoji="🆓"
            ),
            discord.SelectOption(
                label="1 Week",
                description=f"${SUBSCRIPTION_PRICES['1w']} - No prefix for 1 week",
                value="1w",
                emoji="📅"
            ),
            discord.SelectOption(
                label="1 Month",
                description=f"${SUBSCRIPTION_PRICES['1m']} - No prefix for 1 month",
                value="1m",
                emoji="📆"
            ),
            discord.SelectOption(
                label="3 Months",
                description=f"${SUBSCRIPTION_PRICES['3m']} - No prefix for 3 months",
                value="3m",
                emoji="📊"
            ),
            discord.SelectOption(
                label="1 Year",
                description=f"${SUBSCRIPTION_PRICES['1y']} - No prefix for 1 year",
                value="1y",
                emoji="🎯"
            ),
            discord.SelectOption(
                label="Lifetime",
                description=f"${SUBSCRIPTION_PRICES['lifetime']} - Permanent no prefix access",
                value="lifetime",
                emoji="💎"
            ),
        ]
        super().__init__(placeholder="Choose your subscription plan", options=options)

    async def callback(self, interaction: discord.Interaction):
        plan = self.values[0]
        price = SUBSCRIPTION_PRICES[plan]

        option = self.get_option(plan)
        plan_label = option.label if option else plan
        embed = discord.Embed(
            title="💳 Payment Required",
            description=f"You've selected the **{plan_label}** plan.",
            color=0x0070ba
        )

        if price == 0:
            embed.add_field(
                name="🎁 Free Trial",
                value="This is a free trial! Click the button below to activate.",
                inline=False
            )
        else:
            embed.add_field(
                name=f"💰 Price: ${price}",
                value=f"Send **${price}** to: `{PAYPAL_EMAIL}`\n\n**Important:** Include your Discord ID (`{interaction.user.id}`) in the payment notes!",
                inline=False
            )
            embed.add_field(
                name="📝 Payment Instructions",
                value="1. Send payment via PayPal\n2. Include your Discord ID in notes\n3. Click 'I've Paid' button\n4. Wait for verification (usually < 5 minutes)",
                inline=False
            )

        view = PaymentView(interaction.user, plan, price)
        await interaction.response.edit_message(embed=embed, view=view)

    def get_option(self, value):
        return next((opt for opt in self.options if opt.value == value), None)


class PaymentView(ui.View):
    def __init__(self, user, plan, price):
        super().__init__(timeout=300)  # 5 minutes timeout
        self.user = user
        self.plan = plan
        self.price = price

    @ui.button(label="I've Paid", style=discord.ButtonStyle.green, emoji="✅")
    async def paid_button(self, interaction: discord.Interaction, button):
        if interaction.user != self.user:
            return await interaction.response.send_message("This payment form is not for you!", ephemeral=True)

        # Disable the button
        button.disabled = True
        await interaction.response.edit_message(view=self)

        # Send notification to log channel for verification
        log_channel = interaction.client.get_channel(1414349197146062858)
        if isinstance(log_channel, discord.TextChannel):
            embed = discord.Embed(
                title="💳 Payment Verification Needed",
                description=f"**User:** {self.user.mention} ({self.user.id})\n**Plan:** {self.plan.upper()}\n**Amount:** ${self.price}",
                color=0xffa500
            )
            embed.add_field(
                name="Action Required",
                value="Please verify the PayPal payment and activate the subscription using:\n`$np verify @user plan`",
                inline=False
            )
            embed.set_footer(text=f"Payment submitted at <t:{int(interaction.created_at.timestamp())}:F>")

            try:
                # Ping the owner in the log channel
                owner_mention = f"<@{OWNER_IDS[0]}>"
                await log_channel.send(f"{owner_mention} New payment verification needed!", embed=embed)
            except Exception as e:
                print(f"Failed to send log notification: {e}")

        # Confirm to user
        embed = discord.Embed(
            title="⏳ Payment Submitted",
            description="Your payment has been submitted for verification!\n\n**What happens next:**\n• Our team will verify your payment (usually < 5 minutes)\n• You'll receive a DM when activated\n• Premium features will be enabled automatically",
            color=0x00ff00
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji="❌")
    async def cancel_button(self, interaction: discord.Interaction, button):
        if interaction.user != self.user:
            return await interaction.response.send_message("This payment form is not for you!", ephemeral=True)

        embed = discord.Embed(
            title="❌ Payment Cancelled",
            description="Your payment has been cancelled. You can start over anytime with `$subscribe`",
            color=0xff0000
        )
        await interaction.response.edit_message(embed=embed, view=None)


class Payment(commands.Cog):
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot
        self.tz_helpers = get_timezone_helpers(bot)

    @commands.command(
        name="subscribe",
        aliases=["premium", "donate", "payment"],
        help="Subscribe to premium features",
        with_app_command=True
    )
    async def subscribe(self, ctx):
        """Subscribe to Sleepless Premium features"""

        embed = discord.Embed(
            title="💎 Sleepless Premium",
            description="Unlock premium features with our subscription plans!\n\n**Premium Benefits:**\n• 🚫 No prefix required for commands\n• ⚡ Priority support\n• 🎵 Extended music features\n• 🛡️ Enhanced security features",
            color=0x0070ba
        )

        embed.add_field(
            name="💳 Payment Method",
            value="We accept PayPal payments for instant activation",
            inline=False
        )

        view = ui.View()
        view.add_item(SubscriptionSelect(ctx.author))

        await ctx.reply(embed=embed, view=view)

    @commands.command(
        name="paypal",
        aliases=["pay"],
        help="View PayPal payment information",
        with_app_command=True
    )
    async def paypal(self, ctx):
        """View PayPal payment information"""

        embed = discord.Embed(
            title="💳 PayPal Payment Info",
            description="Send payments to our PayPal account for premium subscriptions",
            color=0x0070ba
        )

        embed.add_field(
            name="📧 PayPal Email",
            value=f"`{PAYPAL_EMAIL}`",
            inline=False
        )

        embed.add_field(
            name="📝 Important Notes",
            value="• Always include your Discord ID in payment notes\n• Payments are verified manually for security\n• Activation usually takes < 5 minutes",
            inline=False
        )

        embed.add_field(
            name="🎯 Subscription Plans",
            value="Use `$subscribe` to view all available plans and pricing",
            inline=False
        )

        embed.set_footer(text="Sleepless Development", icon_url=self.bot.user.avatar.url)

        await ctx.reply(embed=embed)

    @commands.command(
        name="verify",
        help="Verify a user's payment (Owner only)",
        with_app_command=True
    )
    @commands.check(lambda ctx: ctx.author.id in OWNER_IDS)
    async def verify_payment(self, ctx, user: discord.User, plan: str):
        """Verify and activate a user's premium subscription"""

        if plan not in SUBSCRIPTION_PRICES:
            return await ctx.reply("❌ Invalid plan specified!")

        # Calculate expiry time
        duration_mapping = {
            "10m": timedelta(minutes=10),
            "1w": timedelta(weeks=1),
            "2w": timedelta(weeks=2),
            "3w": timedelta(weeks=3),
            "1m": timedelta(days=30),
            "3m": timedelta(days=90),
            "6m": timedelta(days=180),
            "1y": timedelta(days=365),
            "3y": timedelta(days=365 * 3),
            "lifetime": None
        }

        expiry_time = None
        if plan != "lifetime":
            expiry_time = datetime.now(timezone.utc) + duration_mapping[plan]
            expiry_str = expiry_time.isoformat()
        else:
            expiry_str = None

        # Add to database
        async with aiosqlite.connect('db/np.db') as db:
            await db.execute("INSERT OR REPLACE INTO np (id, expiry_time) VALUES (?, ?)", (user.id, expiry_str))
            await db.commit()

        # Assign role if in main guild
        guild = self.bot.get_guild(1369497441061179393)
        if guild:
            member = guild.get_member(user.id)
            if member:
                role = guild.get_role(1414349030498107413)
                if role:
                    await member.add_roles(role, reason="Premium subscription activated")

        # Send confirmation
        embed = discord.Embed(
            title="✅ Premium Activated!",
            description=f"Successfully activated **{plan.upper()}** plan for {user.mention}",
            color=0x00ff00
        )

        if expiry_time:
            embed.add_field(
                name="⏰ Expires",
                value=f"<t:{int(expiry_time.timestamp())}:F>",
                inline=True
            )

        await ctx.reply(embed=embed)

        # DM user
        try:
            user_embed = discord.Embed(
                title="🎉 Premium Activated!",
                description=f"Your **{plan.upper()}** subscription has been activated!\n\nYou now have access to all premium features.",
                color=0x00ff00
            )

            if expiry_time:
                user_embed.add_field(
                    name="⏰ Expires",
                    value=f"<t:{int(expiry_time.timestamp())}:F>",
                    inline=False
                )

            await user.send(embed=user_embed)
        except:
            pass


async def setup(bot):
    await bot.add_cog(Payment(bot))
