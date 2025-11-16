import discord
from discord.ext import commands

from utils.error_helpers import StandardErrorHandler
class GreetTest(commands.Cog):
    """Test cog for greet functionality"""
    
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="testgreet", help="Test the greet system")
    @commands.is_owner()
    async def test_greet(self, ctx, member: discord.Member | None = None):
        """Manually test the greet system"""
        if not member:
            member = ctx.author
        
        # Ensure member is not None before accessing mention
        if member is None:
            await ctx.send("❌ Could not determine member to test with")
            return
            
        await ctx.send(f"🧪 Testing greet system for {member.mention}")
        
        # Get the greet cog
        greet_cog = self.bot.get_cog('greet')
        if not greet_cog:
            await ctx.send("❌ Greet cog not found!")
            return
        
        # Manually trigger the event
        try:
            await greet_cog.on_member_join(member)
            await ctx.send("✅ Greet test completed - check console for debug output")
        except Exception as e:
            await ctx.send(f"❌ Error testing greet: {e}")

async def setup(bot):
    await bot.add_cog(GreetTest(bot))