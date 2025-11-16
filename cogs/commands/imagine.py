import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
import random
import time
import aiosqlite
from utils.ai_utils import poly_image_gen, generate_image_prodia
from prodia.constants import Model
from utils.Tools import *
from typing import Optional

from utils.error_helpers import StandardErrorHandler
blacklisted_words = [
    "naked", "nude", "nudes", "teen", "gay", "lesbian", "porn", "xnxx",
    "bitch", "loli", "hentai", "explicit", "pornography", "adult", "XXX",
    "sex", "erotic", "dick", "vagina", "pussy", "gay", "lick", "creampie", "nsfw",
    "hardcore", "ass", "anal", "anus", "boobs", "tits", "cum", "cunnilingus", "squirt", "penis", "lick", "masturbate", "masturbation ", "orgasm", "orgy", "fap", "fapping", "fuck", "fucking", "handjob", "cowgirl", "doggystyle", "blowjob", "boobjob", "boobies", "horny", "nudity"
]

blocked=["minor", "minors", "kid", "kids", "child", "children", "baby", "babies", "toddler", "childporn", "todd", "underage"]

class CooldownManager:
    def __init__(self, rate: int, per: float):
        self.rate = rate
        self.per = per
        # Removed in-memory cooldowns: self.cooldowns = {}

    async def save_cooldown_usage(self, user_id: int, timestamp: float):
        """Save a cooldown usage to the database"""
        async with aiosqlite.connect('db/imagine.db') as db:
            await db.execute('''
                INSERT INTO imagine_cooldowns (user_id, timestamp)
                VALUES (?, ?)
            ''', (user_id, timestamp))
            await db.commit()

    async def get_user_cooldowns(self, user_id: int, time_window: float):
        """Get user cooldowns within a time window"""
        cutoff_time = time.time() - time_window
        
        async with aiosqlite.connect('db/imagine.db') as db:
            cursor = await db.execute('''
                SELECT timestamp FROM imagine_cooldowns
                WHERE user_id = ? AND timestamp >= ?
                ORDER BY timestamp DESC
            ''', (user_id, cutoff_time))
            
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

    async def cleanup_old_cooldowns(self, max_age=3600):  # 1 hour
        """Clean up cooldowns older than max_age"""
        cutoff_time = time.time() - max_age
        async with aiosqlite.connect('db/imagine.db') as db:
            await db.execute('DELETE FROM imagine_cooldowns WHERE timestamp < ?', (cutoff_time,))
            await db.commit()

    async def check_cooldown(self, user_id: int):
        now = time.time()
        
        # Get recent cooldowns within the time period
        recent_cooldowns = await self.get_user_cooldowns(user_id, self.per)
        
        if len(recent_cooldowns) >= self.rate:
            retry_after = self.per - (now - recent_cooldowns[0])
            return retry_after
        
        # Save this usage
        await self.save_cooldown_usage(user_id, now)
        return None

cooldown_manager = CooldownManager(rate=1, per=60.0)

async def cooldown_check(interaction: discord.Interaction):
    retry_after = await cooldown_manager.check_cooldown(interaction.user.id)
    if retry_after:
        await interaction.response.send_message(f"You are on cooldown. Try again in {retry_after:.2f} seconds.", ephemeral=True)
        return False
    return True





class AiStuffCog(commands.Cog):
    
    # Use standardized error handler
    cog_command_error = StandardErrorHandler.create_cog_error_handler()
    
    def __init__(self, bot):
        self.bot = bot

    async def setup_database(self):
        """Create the imagine database and tables"""
        async with aiosqlite.connect('db/imagine.db') as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS imagine_cooldowns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    timestamp REAL NOT NULL
                )
            ''')
            await db.commit()

    @commands.Cog.listener()
    async def on_ready(self):
        await self.setup_database()

    @commands.guild_only()
    @app_commands.command(name="imagine", description="Generate an image using AI")

    #@app_commands.check(blacklist_check())
    #@app_commands.check(ignore_check())
    #@app_commands.check(cooldown_check)
    @discord.app_commands.choices(
        model=[
            discord.app_commands.Choice(name='✨ Elldreth vivid mix (Landscapes, Stylized characters, nsfw)', value='ELLDRETHVIVIDMIX'),
            discord.app_commands.Choice(name='💪 Deliberate v2 (Anything you want, nsfw)', value='DELIBERATE'),
            discord.app_commands.Choice(name='🔮 Dreamshaper (HOLYSHIT this so good)', value='DREAMSHAPER_6'),
            discord.app_commands.Choice(name='🎼 Lyriel', value='LYRIEL_V16'),
            discord.app_commands.Choice(name='💥 Anything diffusion (Good for anime)', value='ANYTHING_V4'),
            discord.app_commands.Choice(name='🌅 Openjourney (Midjourney alternative)', value='OPENJOURNEY'),
            discord.app_commands.Choice(name='🏞️ Realistic (Lifelike pictures)', value='REALISTICVS_V20'),
            discord.app_commands.Choice(name='👨‍🎨 Portrait (For headshots I guess)', value='PORTRAIT'),
            discord.app_commands.Choice(name='🌟 Rev animated (Illustration, Anime)', value='REV_ANIMATED'),
            discord.app_commands.Choice(name='🤖 Analog', value='ANALOG'),
            discord.app_commands.Choice(name='🌌 AbyssOrangeMix', value='ABYSSORANGEMIX'),
            discord.app_commands.Choice(name='🌌 Dreamlike v1', value='DREAMLIKE_V1'),
            discord.app_commands.Choice(name='🌌 Dreamlike v2', value='DREAMLIKE_V2'),
            discord.app_commands.Choice(name='🌌 Dreamshaper 5', value='DREAMSHAPER_5'),
            discord.app_commands.Choice(name='🌌 MechaMix', value='MECHAMIX'),
            discord.app_commands.Choice(name='🌌 MeinaMix', value='MEINAMIX'),
            discord.app_commands.Choice(name='🌌 Stable Diffusion v14', value='SD_V14'),
            discord.app_commands.Choice(name='🌌 Stable Diffusion v15', value='SD_V15'),
            discord.app_commands.Choice(name="🌌 Shonin's Beautiful People", value='SBP'),
            discord.app_commands.Choice(name="🌌 TheAlly's Mix II", value='THEALLYSMIX'),
            discord.app_commands.Choice(name='🌌 Timeless', value='TIMELESS')
        ],
        sampler=[
            discord.app_commands.Choice(name='📏 Euler (Recommended)', value='Euler'),
            discord.app_commands.Choice(name='📏 Euler a', value='Euler a'),
            discord.app_commands.Choice(name='📐 Heun', value='Heun'),
            discord.app_commands.Choice(name='💥 DPM++ 2M Karras', value='DPM++ 2M Karras'),
            discord.app_commands.Choice(name='💥 DPM++ SDE Karras', value='DPM++ SDE Karras'),
            discord.app_commands.Choice(name='🔍 DDIM', value='DDIM')
        ]
    )
    @discord.app_commands.describe(
        prompt="Write an amazing prompt for an image",
        model="Model to generate image",
        sampler="Sampler for denoising",
        negative="Prompt that specifies what you do not want the model to generate",
    )
    async def imagine(self, interaction: discord.Interaction, prompt: str, model: discord.app_commands.Choice[str], sampler: discord.app_commands.Choice[str], negative: Optional[str] = None, seed: Optional[int] = None):
        retry_after = await cooldown_manager.check_cooldown(interaction.user.id)
        if retry_after:
            await interaction.response.send_message(f"You are on cooldown. Try again in {retry_after:.2f} seconds.", ephemeral=True)
            return

        await interaction.response.defer()

        is_nsfw = any(word in prompt.lower() for word in blacklisted_words)
        is_child = any(word in prompt.lower() for word in blocked)

        if is_child:
            await interaction.followup.send("Child porn is not allowed as it violates Discord ToS. Please try again with a different peompt.")
            return

        # Only check .nsfw if channel is a TextChannel or ForumChannel
        channel = interaction.channel
        channel_is_nsfw = False
        if isinstance(channel, (discord.TextChannel, getattr(discord, 'ForumChannel', type(None)))):
            channel_is_nsfw = getattr(channel, 'nsfw', False)

        if is_nsfw and not channel_is_nsfw:
            await interaction.followup.send("You can create NSFW images in NSFW channels only. Please try in an appropriate channel.", ephemeral=True)
            return

        model_uid = Model[model.value].value[0]

        # Default negative to empty string and seed to 0 if None
        negative_val = negative if negative is not None else ""
        seed_val = seed if seed is not None else 0

        try:
            imagefileobj = await generate_image_prodia(prompt, model_uid, sampler.value, seed_val, negative_val)
        except aiohttp.ClientPayloadError:
            await interaction.followup.send("An error occurred while generating the image. Please try again later.", ephemeral=True)
            return
        except Exception as e:
            await interaction.followup.send(f"An unexpected error occurred: {e}", ephemeral=True)
            return

        if is_nsfw:
            img_file = discord.File(imagefileobj, filename="image.png", spoiler=True, description=prompt)
            prompt = f"||{prompt}||"
        else:
            img_file = discord.File(imagefileobj, filename="image.png", description=prompt)

        embed = discord.Embed(color=0xFF0000) if is_nsfw else discord.Embed(color=discord.Color.random())
        embed.title = f"Generated Image by {interaction.user.display_name}"
        embed.add_field(name='Prompt', value=f'- {prompt}', inline=False)
        embed.add_field(name='Image Details', value=f"- **Model:** {model.value}\n- **Sampler:** {sampler.value}\n- **Seed:**{seed}", inline=True)
        embed.set_footer(text=f"© Sleepless Development", icon_url=self.bot.user.avatar.url)
        #embed.set_thumbnail(url=img_file)
        if negative:
            embed.add_field(name='Negative Prompt', value=f'- {negative}', inline=False)
        if is_nsfw:
            embed.add_field(name='NSFW', value=f'- {str(is_nsfw)}', inline=True)
            


        await interaction.followup.send(embed=embed, file=img_file, ephemeral=True)


"""
@Author: Frosty
    + Discord: frosty.pyro
    + Community: https://discord.gg/5wtjDkYbVh (Sleepless Development)
    + for any queries reach out in the server; or send a dm.
"""