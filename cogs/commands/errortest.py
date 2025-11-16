import discord
from discord.ext import commands
from core import Cog, Context, sleepless
from utils.error_logger import ErrorLogger


class ErrorTest(Cog):
    def __init__(self, client: sleepless):
        self.client = client
        self.error_logger = ErrorLogger(client)

    @commands.command(name="testerror", help="Test the error logging system")
    @commands.is_owner()
    async def test_error(self, ctx: Context, error_type: str = "test"):
        """Test command to verify error logging works"""
        
        if error_type.lower() == "command":
            # Test command error logging
            raise ValueError("This is a test command error!")
        elif error_type.lower() == "database":
            # Test database error logging
            await self.error_logger.log_database_error(
                "Test Operation", 
                Exception("Test database connection failed"), 
                "test_table"
            )
            await ctx.send("✅ Database error test logged!")
        elif error_type.lower() == "custom":
            # Test custom error logging
            await self.error_logger.log_error(
                "Custom Test Error",
                "This is a custom test error message",
                f"Triggered by: {ctx.author}\nIn channel: {getattr(ctx.channel, 'name', str(ctx.channel))}"
            )
            await ctx.send("✅ Custom error test logged!")
        else:
            # Test general error logging
            await self.error_logger.log_error(
                "General Test Error",
                "This is a general test error from the test command"
            )
            await ctx.send("✅ General error test logged!")

    @commands.command(name="testcrash", help="Test unhandled exception logging")
    @commands.is_owner()
    async def test_crash(self, ctx: Context):
        """Test command that creates an unhandled exception"""
        # This will trigger the on_command_error handler
        undefined_variable = some_undefined_variable  # pyright: ignore[reportUndefinedVariable] # This will cause a NameError
        await ctx.send("This shouldn't be reached")


async def setup(client):
    await client.add_cog(ErrorTest(client))