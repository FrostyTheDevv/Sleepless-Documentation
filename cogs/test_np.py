"""
Live test for no-prefix system - Add this as a temporary command to test in Discord
"""
from discord.ext import commands
import discord

class NoPrefixTest(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name="testnp", help="Test the no-prefix system behavior")
    @commands.is_owner()
    async def test_no_prefix(self, ctx):
        """Test command to verify no-prefix logic"""
        
        embed = discord.Embed(
            title="🧪 No-Prefix System Test",
            description="Testing the refined no-prefix command detection",
            color=0x00ff00
        )
        
        # Get all valid commands
        valid_commands = set()
        for command in self.bot.commands:
            valid_commands.add(command.name.lower())
            if hasattr(command, 'aliases') and command.aliases:
                valid_commands.update(alias.lower() for alias in command.aliases)
        
        embed.add_field(
            name="📊 Command Registry Stats",
            value=f"Total Commands: {len(self.bot.commands)}\n"
                  f"Total Names + Aliases: {len(valid_commands)}",
            inline=False
        )
        
        # Test scenarios
        test_messages = [
            ("invite", "✅ Execute", "Valid command"),
            ("invite my friend", "✅ Execute", "Command with args"),
            ("hey everyone", "⏭️ Ignore", "Regular conversation"),
            ("can someone help me", "⏭️ Ignore", "Non-command start"),
            ("whitelist @user ban", "✅ Execute", "Antinuke command"),
            ("wl @user", "✅ Execute", "Command alias"),
        ]
        
        test_results = []
        for msg, expected, desc in test_messages:
            first_word = msg.strip().split()[0].lower() if msg.strip() else ""
            is_command = first_word in valid_commands
            actual = "✅ Execute" if is_command else "⏭️ Ignore"
            status = "✅" if actual == expected else "❌"
            test_results.append(f"{status} `{msg}`\n   → {actual} ({desc})")
        
        embed.add_field(
            name="🧪 Test Results",
            value="\n\n".join(test_results),
            inline=False
        )
        
        # Check if user has no-prefix
        has_np = False
        try:
            dbs = getattr(self.bot, 'dbs', None)
            if dbs and 'np' in dbs:
                async with dbs["np"].execute("SELECT 1 FROM np WHERE user_id = ?", (str(ctx.author.id),)) as cursor:
                    has_np = await cursor.fetchone() is not None
        except:
            pass
        
        embed.add_field(
            name="👤 Your Status",
            value=f"No-Prefix Permission: {'✅ Yes' if has_np else '❌ No'}\n"
                  f"If you have no-prefix, try sending messages like:\n"
                  f"`invite` (should work)\n"
                  f"`hey everyone` (should be ignored)",
            inline=False
        )
        
        embed.set_footer(text="The system validates first word against command registry")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(NoPrefixTest(bot))
