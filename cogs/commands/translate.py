import discord
from discord.ext import commands
from deep_translator import GoogleTranslator

from utils.error_helpers import StandardErrorHandler
class TranslateCog(commands.Cog):
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(
        name="hinglish",
        help="Translate informal Hinglish to proper English.",
        usage="$hinglish chlo udhr chat active krlo idhr nai"
    )
    async def hinglish(self, ctx: commands.Context, *, text: str = ""):
        if not text:
            return await ctx.reply(
                "⚠️ Please provide some Hinglish text to translate.",
                ephemeral=True if ctx.interaction else False
            )

        msg = await ctx.reply(
            "🔄 Translating Hinglish...",
            ephemeral=True if ctx.interaction else False
        )

        try:
            # Translation using deep-translator (Google)
            translated = GoogleTranslator(source="auto", target="en").translate(text)

            embed = discord.Embed(
                title="🗣 Hinglish → English",
                color=0x00b0f4
            )
            embed.add_field(name="Original", value=text, inline=False)
            embed.add_field(name="Translated", value=translated, inline=False)
            embed.set_footer(
                text=f"Requested by {ctx.author}",
                icon_url=ctx.author.display_avatar.url
            )

            await msg.edit(content=None, embed=embed)

        except Exception as e:
            await msg.edit(content=f"❌ Translation failed: `{str(e)}`")

    @commands.hybrid_command(
        name="tr",
        help="Translate foreign text to English by replying to a message.",
        usage="Reply to a message and use: $tr"
    )
    async def tr(self, ctx: commands.Context):
        # Check if this is a reply to another message
        if not ctx.message.reference or not ctx.message.reference.message_id:
            return await ctx.reply(
                "⚠️ Please reply to a message you want to translate.",
                ephemeral=True if ctx.interaction else False
            )

        try:
            # Get the referenced message
            channel = ctx.channel
            referenced_message = await channel.fetch_message(ctx.message.reference.message_id)
            
            if not referenced_message.content:
                return await ctx.reply(
                    "⚠️ The message you replied to has no text content.",
                    ephemeral=True if ctx.interaction else False
                )

            # Send loading message
            msg = await ctx.reply(
                "🔄 Translating to English...",
                ephemeral=True if ctx.interaction else False
            )

            # Try different source languages for better detection
            original_text = referenced_message.content
            
            # First try auto-detection
            translator = GoogleTranslator(source="auto", target="en")
            translated = translator.translate(original_text)
            detected_lang = "auto"
            
            # If the translation is the same as original (just capitalized), try Hindi
            if translated.lower().replace(" ", "") == original_text.lower().replace(" ", ""):
                try:
                    hindi_translator = GoogleTranslator(source="hi", target="en")
                    hindi_translated = hindi_translator.translate(original_text)
                    if hindi_translated.lower() != original_text.lower():
                        translated = hindi_translated
                        detected_lang = "hindi"
                except:
                    # If Hindi fails, try other common languages
                    for lang_code in ["ur", "bn", "ta"]:  # Urdu, Bengali, Tamil
                        try:
                            alt_translator = GoogleTranslator(source=lang_code, target="en")
                            alt_translated = alt_translator.translate(original_text)
                            if alt_translated.lower() != original_text.lower():
                                translated = alt_translated
                                detected_lang = lang_code
                                break
                        except:
                            continue

            # Create embed with better information
            embed = discord.Embed(
                title="🌍 Translation to English",
                color=0x00b0f4
            )
            embed.add_field(name="Original", value=original_text, inline=False)
            embed.add_field(name="Translated", value=translated, inline=False)
            
            # Add detection info if translation seems unsuccessful
            if translated.lower().replace(" ", "") == original_text.lower().replace(" ", ""):
                embed.add_field(
                    name="⚠️ Note", 
                    value="Language auto-detection may have failed. The text might be in a mixed language or dialect.", 
                    inline=False
                )
            
            embed.set_footer(
                text=f"Requested by {ctx.author} • Detected: {detected_lang}",
                icon_url=ctx.author.display_avatar.url
            )

            await msg.edit(content=None, embed=embed)

        except Exception as e:
            await ctx.reply(f"❌ Translation failed: `{str(e)}`")

async def setup(bot):
    await bot.add_cog(TranslateCog(bot))
