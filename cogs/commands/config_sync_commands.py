"""
Config Sync Commands
Discord commands for multi-server configuration synchronization
"""

import discord
from discord.ext import commands
import json
import time
from typing import Optional, List
from utils.config_sync import get_sync_manager


class ConfigSyncCommands(commands.Cog):
    """Commands for syncing antinuke configs across servers"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.group(name='sync', invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def sync(self, ctx):
        """Multi-server configuration sync system"""
        embed = discord.Embed(
            title="🔄 Config Sync System",
            description="Synchronize antinuke configurations across multiple servers",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Export/Import",
            value=(
                "`$sync export` - Export current server config\n"
                "`$sync import <profile_id>` - Import config to this server\n"
                "`$sync save <name>` - Save current config as profile"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Profiles",
            value=(
                "`$sync profiles` - List all saved profiles\n"
                "`$sync profile <id>` - View profile details\n"
                "`$sync delete <id>` - Delete a profile"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Multi-Server",
            value=(
                "`$sync push <profile_id> <guild_ids...>` - Push to multiple servers\n"
                "`$sync status` - View sync status for this server\n"
                "`$sync history <profile_id>` - View sync history"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Templates",
            value=(
                "`$sync template <name>` - Apply template (strict/moderate/lenient)\n"
                "`$sync templates` - List available templates"
            ),
            inline=False
        )
        
        embed.set_footer(text="Administrator permission required")
        
        await ctx.send(embed=embed)
    
    @sync.command(name='export')
    @commands.has_permissions(administrator=True)
    async def sync_export(self, ctx):
        """Export current server configuration"""
        manager = get_sync_manager()
        if not manager:
            return await ctx.send("❌ Config sync not initialized")
        
        # Export config
        config = await manager.export_guild_config(ctx.guild.id)
        
        # Create embed with summary
        embed = discord.Embed(
            title="📤 Configuration Exported",
            description=f"Server: **{ctx.guild.name}**",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="Thresholds",
            value=f"{len(config['thresholds'])} action types configured",
            inline=True
        )
        
        embed.add_field(
            name="Whitelist",
            value=(
                f"👤 {len(config['whitelist']['users'])} users\n"
                f"🎭 {len(config['whitelist']['roles'])} roles"
            ),
            inline=True
        )
        
        # Create JSON file
        json_str = json.dumps(config, indent=2)
        file = discord.File(
            fp=io.BytesIO(json_str.encode()),
            filename=f"antinuke_config_{ctx.guild.id}.json"
        )
        
        embed.add_field(
            name="📁 File Attached",
            value="Download to import to other servers",
            inline=False
        )
        
        await ctx.send(embed=embed, file=file)
    
    @sync.command(name='import')
    @commands.has_permissions(administrator=True)
    async def sync_import(self, ctx, profile_id: str):
        """Import configuration from a profile"""
        manager = get_sync_manager()
        if not manager:
            return await ctx.send("❌ Config sync not initialized")
        
        # Confirmation
        confirm_embed = discord.Embed(
            title="⚠️ Import Configuration",
            description=(
                "This will **overwrite** current antinuke settings.\n"
                "React with ✅ to confirm."
            ),
            color=discord.Color.orange()
        )
        
        msg = await ctx.send(embed=confirm_embed)
        await msg.add_reaction('✅')
        await msg.add_reaction('❌')
        
        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ['✅', '❌']
        
        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=30.0, check=check)
            
            if str(reaction.emoji) == '❌':
                return await ctx.send("❌ Import cancelled")
            
        except:
            return await ctx.send("❌ Import timed out")
        
        # Load profile
        profile = await manager.load_profile(profile_id)
        if not profile:
            return await ctx.send("❌ Profile not found")
        
        # Import
        stats = await manager.import_guild_config(ctx.guild.id, profile)
        
        # Success embed
        embed = discord.Embed(
            title="✅ Configuration Imported",
            description=f"Profile: **{profile['name']}**",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="📊 Import Statistics",
            value=(
                f"⚙️ Thresholds: {stats['thresholds_imported']}\n"
                f"👤 Users: {stats['users_whitelisted']}\n"
                f"🎭 Roles: {stats['roles_whitelisted']}"
            ),
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @sync.command(name='save')
    @commands.has_permissions(administrator=True)
    async def sync_save(self, ctx, *, name: str):
        """Save current configuration as a profile"""
        manager = get_sync_manager()
        if not manager:
            return await ctx.send("❌ Config sync not initialized")
        
        # Export current config
        config = await manager.export_guild_config(ctx.guild.id)
        
        # Save as profile
        profile_id = await manager.save_profile(
            name=name,
            description=f"Exported from {ctx.guild.name}",
            created_by=ctx.author.id,
            config=config
        )
        
        embed = discord.Embed(
            title="💾 Profile Saved",
            description=f"Profile ID: `{profile_id}`",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="Name",
            value=name,
            inline=True
        )
        
        embed.add_field(
            name="Items",
            value=(
                f"⚙️ {len(config['thresholds'])} thresholds\n"
                f"👤 {len(config['whitelist']['users'])} users\n"
                f"🎭 {len(config['whitelist']['roles'])} roles"
            ),
            inline=True
        )
        
        embed.add_field(
            name="Usage",
            value=f"`$sync import {profile_id}`",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @sync.command(name='profiles')
    @commands.has_permissions(administrator=True)
    async def sync_profiles(self, ctx):
        """List all saved configuration profiles"""
        manager = get_sync_manager()
        if not manager:
            return await ctx.send("❌ Config sync not initialized")
        
        profiles = await manager.list_profiles()
        
        if not profiles:
            return await ctx.send("📋 No saved profiles")
        
        embed = discord.Embed(
            title="📋 Saved Configuration Profiles",
            color=discord.Color.blue()
        )
        
        for profile in profiles[:10]:  # Show first 10
            created_at = time.strftime('%Y-%m-%d %H:%M', time.localtime(profile['created_at']))
            
            embed.add_field(
                name=profile['name'],
                value=(
                    f"ID: `{profile['profile_id']}`\n"
                    f"Created: {created_at}\n"
                    f"By: <@{profile['created_by']}>"
                ),
                inline=False
            )
        
        if len(profiles) > 10:
            embed.set_footer(text=f"Showing 10 of {len(profiles)} profiles")
        
        await ctx.send(embed=embed)
    
    @sync.command(name='profile')
    @commands.has_permissions(administrator=True)
    async def sync_profile(self, ctx, profile_id: str):
        """View detailed profile information"""
        manager = get_sync_manager()
        if not manager:
            return await ctx.send("❌ Config sync not initialized")
        
        profile = await manager.load_profile(profile_id)
        
        if not profile:
            return await ctx.send("❌ Profile not found")
        
        embed = discord.Embed(
            title=f"📄 {profile['name']}",
            description=profile.get('description', 'No description'),
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Profile ID",
            value=f"`{profile_id}`",
            inline=False
        )
        
        embed.add_field(
            name="Thresholds",
            value=f"{len(profile['thresholds'])} action types configured",
            inline=True
        )
        
        embed.add_field(
            name="Whitelist",
            value=(
                f"👤 {len(profile['whitelist']['users'])} users\n"
                f"🎭 {len(profile['whitelist']['roles'])} roles"
            ),
            inline=True
        )
        
        created_at = time.strftime('%Y-%m-%d %H:%M', time.localtime(profile['created_at']))
        embed.add_field(
            name="Created",
            value=f"{created_at}\nBy: <@{profile['created_by']}>",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @sync.command(name='delete')
    @commands.has_permissions(administrator=True)
    async def sync_delete(self, ctx, profile_id: str):
        """Delete a configuration profile"""
        manager = get_sync_manager()
        if not manager:
            return await ctx.send("❌ Config sync not initialized")
        
        deleted = await manager.delete_profile(profile_id)
        
        if deleted:
            await ctx.send(f"✅ Deleted profile `{profile_id}`")
        else:
            await ctx.send("❌ Profile not found")
    
    @sync.command(name='push')
    @commands.has_permissions(administrator=True)
    async def sync_push(self, ctx, profile_id: str, *guild_ids: str):
        """Push configuration to multiple servers"""
        manager = get_sync_manager()
        if not manager:
            return await ctx.send("❌ Config sync not initialized")
        
        if not guild_ids:
            return await ctx.send("❌ Provide at least one guild ID")
        
        # Convert to integers
        try:
            target_guilds = [int(gid) for gid in guild_ids]
        except ValueError:
            return await ctx.send("❌ Invalid guild IDs")
        
        # Confirmation
        guild_list = "\n".join([f"• {gid}" for gid in target_guilds[:5]])
        if len(target_guilds) > 5:
            guild_list += f"\n• ... and {len(target_guilds) - 5} more"
        
        confirm_embed = discord.Embed(
            title="⚠️ Push Configuration",
            description=(
                f"This will push profile `{profile_id}` to:\n{guild_list}\n\n"
                "React with ✅ to confirm."
            ),
            color=discord.Color.orange()
        )
        
        msg = await ctx.send(embed=confirm_embed)
        await msg.add_reaction('✅')
        await msg.add_reaction('❌')
        
        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ['✅', '❌']
        
        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=30.0, check=check)
            
            if str(reaction.emoji) == '❌':
                return await ctx.send("❌ Push cancelled")
            
        except:
            return await ctx.send("❌ Push timed out")
        
        # Perform sync
        results = await manager.sync_to_guilds(profile_id, target_guilds, ctx.author.id)
        
        if "error" in results:
            return await ctx.send(f"❌ {results['error']}")
        
        # Results embed
        embed = discord.Embed(
            title="✅ Configuration Push Complete",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="Success",
            value=f"{len(results['success'])} servers",
            inline=True
        )
        
        embed.add_field(
            name="Failed",
            value=f"{len(results['failed'])} servers",
            inline=True
        )
        
        if results['success']:
            success_list = "\n".join([f"• {gid}" for gid in results['success'][:5]])
            if len(results['success']) > 5:
                success_list += f"\n• ... and {len(results['success']) - 5} more"
            
            embed.add_field(
                name="✅ Successful Syncs",
                value=success_list,
                inline=False
            )
        
        if results['failed']:
            failed_list = "\n".join([
                f"• {item['guild_id']}: {item['error']}" 
                for item in results['failed'][:3]
            ])
            if len(results['failed']) > 3:
                failed_list += f"\n• ... and {len(results['failed']) - 3} more"
            
            embed.add_field(
                name="❌ Failed Syncs",
                value=failed_list,
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @sync.command(name='status')
    @commands.has_permissions(administrator=True)
    async def sync_status(self, ctx):
        """View sync status for current server"""
        manager = get_sync_manager()
        if not manager:
            return await ctx.send("❌ Config sync not initialized")
        
        profile_id = await manager.get_guild_profile(ctx.guild.id)
        
        if not profile_id:
            return await ctx.send("ℹ️ No profile applied to this server")
        
        profile = await manager.load_profile(profile_id)
        
        if not profile:
            return await ctx.send("❌ Profile data not found")
        
        embed = discord.Embed(
            title="🔄 Current Configuration",
            description=f"Server: **{ctx.guild.name}**",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Active Profile",
            value=profile['name'],
            inline=False
        )
        
        embed.add_field(
            name="Profile ID",
            value=f"`{profile_id}`",
            inline=True
        )
        
        embed.add_field(
            name="Created By",
            value=f"<@{profile['created_by']}>",
            inline=True
        )
        
        await ctx.send(embed=embed)


import io


async def setup(bot):
    """Load the cog"""
    await bot.add_cog(ConfigSyncCommands(bot))
