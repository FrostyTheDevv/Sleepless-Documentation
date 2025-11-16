from discord.ext import commands
import discord

from utils.error_helpers import StandardErrorHandler
class TestGroupCog(commands.Cog):
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="testgroup", invoke_without_command=True)
    async def testgroup(self, ctx):
        print("[DEBUG] testgroup command group registered and invoked!")
        if ctx.invoked_subcommand is None:
            await ctx.send("Test group root invoked!")

    @testgroup.command(name="ping")
    async def ping(self, ctx):
        """Redirects to the comprehensive network diagnostics command"""
        # Get the moderation cog's ping command
        moderation_cog = self.bot.get_cog('Moderation')
        if moderation_cog and hasattr(moderation_cog, 'ping'):
            await moderation_cog.ping(ctx)
        else:
            await ctx.send("❌ Comprehensive ping command not available. Use `ping` directly instead of `testgroup ping`.")

async def setup(bot):
    await bot.add_cog(TestGroupCog(bot))
