"""
Simple Translation Command for Sleepless Bot
Works like Bleed Bot's translation system with reply feature
Author: Frosty
"""

import discord
from discord.ext import commands
from typing import Optional
from core import Cog, Context

class TranslationTool(Cog):
    """Simple translation tool with reply feature like Bleed Bot"""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def translate_text(self, text: str, target_lang: str) -> dict:
        """Translate text using Google Translate"""
        try:
            from deep_translator import GoogleTranslator
            translator = GoogleTranslator(source='auto', target=target_lang)
            translated = translator.translate(text)
            
            return {
                'success': True,
                'translated_text': translated,
                'target_language': target_lang,
                'provider': 'Google Translate'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_language_code(self, language: str) -> str:
        """Convert language name to code"""
        language = language.lower().strip()
        
        # Language mappings
        lang_map = {
            'english': 'en', 'spanish': 'es', 'french': 'fr', 'german': 'de',
            'italian': 'it', 'portuguese': 'pt', 'russian': 'ru', 'japanese': 'ja',
            'korean': 'ko', 'chinese': 'zh', 'arabic': 'ar', 'hindi': 'hi',
            'dutch': 'nl', 'polish': 'pl', 'turkish': 'tr', 'vietnamese': 'vi',
            'thai': 'th', 'greek': 'el', 'hebrew': 'he', 'swedish': 'sv',
            'norwegian': 'no', 'danish': 'da', 'finnish': 'fi', 'czech': 'cs'
        }
        
        if language in lang_map:
            return lang_map[language]
        elif len(language) == 2:
            return language
        else:
            # Try partial matching
            for name, code in lang_map.items():
                if language in name or name.startswith(language):
                    return code
            return language
    
    @commands.command(name="tr", aliases=["translate"])
    async def translate_command(self, ctx: Context, target_lang: Optional[str] = None, *, text: Optional[str] = None):
        """🌐 Translate foreign text to English or reply to translate messages
        
        Usage:
        - Reply to message + tr - Translate foreign message to English
        - tr <text> - Translate foreign text to English
        - tr <language> <text> - Translate text to specific language
        
        Examples:
        - Reply to foreign message + tr
        - tr Hola mundo
        - tr spanish Hello world
        """
        
        # Check if this is a reply to a message
        if ctx.message.reference and ctx.message.reference.message_id:
            try:
                # Get the referenced message
                referenced_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                
                if not referenced_message.content:
                    return await ctx.send("❌ The message you replied to has no text to translate.")
                
                # Use the referenced message content
                text = referenced_message.content
                
                # If target_lang is provided with reply, use it; otherwise translate to English
                if target_lang:
                    # Check if target_lang is actually text (meaning user wants English translation)
                    if len(target_lang.split()) > 1 or any(char.isdigit() or not char.isalpha() for char in target_lang if char != ' '):
                        # target_lang looks like text, so translate to English
                        target_code = 'en'
                        text = target_lang  # Use the "target_lang" as the text to translate
                    else:
                        # target_lang is actually a language code
                        target_code = self.get_language_code(target_lang)
                else:
                    # No language specified, translate to English
                    target_code = 'en'
                
                result = await self.translate_text(text, target_code)
                
                if result['success']:
                    embed = discord.Embed(
                        title="🌐 Translation",
                        color=0x2f3136
                    )
                    
                    # Original message info
                    embed.add_field(
                        name="📤 Original",
                        value=f"**{referenced_message.author}:** {text[:200]}{'...' if len(text) > 200 else ''}",
                        inline=False
                    )
                    
                    # Translation
                    embed.add_field(
                        name=f"📥 English" if target_code == 'en' else f"📥 {target_code.upper()}",
                        value=result['translated_text'],
                        inline=False
                    )
                    
                    embed.set_footer(
                        text=f"Translated by {ctx.author}",
                        icon_url=ctx.author.display_avatar.url
                    )
                    
                    return await ctx.send(embed=embed)
                else:
                    return await ctx.send(f"❌ Translation failed: {result.get('error', 'Unknown error')}")
                    
            except discord.NotFound:
                return await ctx.send("❌ Could not find the message you replied to.")
            except discord.Forbidden:
                return await ctx.send("❌ I don't have permission to access that message.")
            except Exception as e:
                return await ctx.send(f"❌ Error: {str(e)}")
        
        # Regular translation
        if not target_lang:
            embed = discord.Embed(
                title="🌐 Translation Command",
                description="**Translate foreign text to English like Bleed Bot**",
                color=0x2f3136
            )
            
            embed.add_field(
                name="📝 Usage",
                value="**Reply to message + `tr`** - Translate foreign message to English\n`tr <foreign text>` - Translate foreign text to English\n`tr <language> <text>` - Translate to specific language",
                inline=False
            )
            
            embed.add_field(
                name="💡 Examples",
                value="• **Reply to foreign message + `tr`** ⭐\n• `tr Hola mundo` → English\n• `tr spanish Hello world` → Spanish\n• `tr Bonjour le monde` → English",
                inline=False
            )
            
            return await ctx.send(embed=embed)
        
        # Check if target_lang is actually text to translate (no second parameter)
        if not text:
            # target_lang is probably text to translate to English
            text = target_lang
            target_code = 'en'  # Default to English
        else:
            # Normal translation with specified language
            target_code = self.get_language_code(target_lang)
        
        result = await self.translate_text(text, target_code)
        
        if result['success']:
            embed = discord.Embed(
                title="🌐 Translation",
                color=0x2f3136
            )
            
            embed.add_field(
                name="📤 Original",
                value=text,
                inline=False
            )
            
            embed.add_field(
                name=f"📥 English" if target_code == 'en' else f"📥 {target_code.upper()}",
                value=result['translated_text'],
                inline=False
            )
            
            embed.set_footer(
                text=f"Translated by {ctx.author}",
                icon_url=ctx.author.display_avatar.url
            )
            
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❌ Translation failed: {result.get('error', 'Unknown error')}")

async def setup(bot):
    await bot.add_cog(TranslationTool(bot))