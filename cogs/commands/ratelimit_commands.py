"""
Rate Limit Protection Commands
Commands for monitoring and managing rate limits
"""

import discord
from discord.ext import commands
from typing import Optional
from utils.rate_limit_protection import get_rate_limiter, RateLimitType
import time


class RateLimitCommands(commands.Cog):
    """Commands for rate limit management"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.group(name="ratelimit", aliases=["rl"], invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def ratelimit(self, ctx):
        """Manage rate limit protection system"""
        embed = discord.Embed(
            title="⏱️ Rate Limit Protection",
            description="Monitor and manage Discord API rate limits",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📊 Monitoring Commands",
            value=(
                "`$ratelimit status` - View current rate limit status\n"
                "`$ratelimit stats [hours]` - View rate limit statistics\n"
                "`$ratelimit buckets` - View active buckets"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🔍 Bucket Commands",
            value=(
                "`$ratelimit bucket <type>` - View specific bucket status\n"
                "`$ratelimit cooldowns` - View active cooldowns"
            ),
            inline=False
        )
        
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
        await ctx.send(embed=embed)
    
    @ratelimit.command(name="status")
    @commands.has_permissions(administrator=True)
    async def rl_status(self, ctx):
        """View current rate limit status"""
        limiter = get_rate_limiter()
        
        if not limiter:
            await ctx.send("❌ Rate limiter is not initialized.")
            return
        
        stats = limiter.stats
        
        # Calculate rates
        total = stats["total_requests"]
        blocked = stats["blocked_requests"]
        block_rate = (blocked / total * 100) if total > 0 else 0
        
        embed = discord.Embed(
            title="⏱️ Rate Limit Status",
            description="Current rate limit protection status",
            color=discord.Color.green() if block_rate < 10 else discord.Color.orange()
        )
        
        # Request statistics
        embed.add_field(
            name="📊 Request Statistics",
            value=(
                f"**Total Requests:** {total:,}\n"
                f"**Blocked:** {blocked:,} ({block_rate:.1f}%)\n"
                f"**Global Blocks:** {stats['global_blocks']}\n"
                f"**Bucket Blocks:** {stats['bucket_blocks']}"
            ),
            inline=True
        )
        
        # Rate limit hits
        embed.add_field(
            name="⚠️ Rate Limit Hits",
            value=(
                f"**429 Errors:** {stats['rate_limit_hits']}\n"
                f"**Total Wait Time:** {stats['total_wait_time']:.2f}s\n"
                f"**Avg Wait:** {(stats['total_wait_time'] / max(1, blocked)):.2f}s"
            ),
            inline=True
        )
        
        # Active buckets
        active_buckets = len(limiter.buckets)
        exhausted = sum(1 for b in limiter.buckets.values() if b.is_exhausted())
        
        embed.add_field(
            name="🪣 Buckets",
            value=(
                f"**Active:** {active_buckets}\n"
                f"**Exhausted:** {exhausted}\n"
                f"**Available:** {active_buckets - exhausted}"
            ),
            inline=True
        )
        
        # Global bucket
        if limiter.global_bucket:
            gb = limiter.global_bucket
            embed.add_field(
                name="🌐 Global Bucket",
                value=(
                    f"**Status:** {'🔴 Exhausted' if gb.is_exhausted() else '🟢 Available'}\n"
                    f"**Remaining:** {gb.remaining}/{gb.limit}\n"
                    f"**Reset:** {gb.time_until_reset():.1f}s"
                ),
                inline=False
            )
        
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
        await ctx.send(embed=embed)
    
    @ratelimit.command(name="stats")
    @commands.has_permissions(administrator=True)
    async def rl_stats(self, ctx, hours: int = 24):
        """View rate limit statistics"""
        limiter = get_rate_limiter()
        
        if not limiter:
            await ctx.send("❌ Rate limiter is not initialized.")
            return
        
        if hours < 1 or hours > 168:
            await ctx.send("❌ Hours must be between 1 and 168 (7 days).")
            return
        
        msg = await ctx.send("📊 Fetching rate limit statistics...")
        
        try:
            stats = await limiter.get_statistics(hours)
            
            embed = discord.Embed(
                title=f"📊 Rate Limit Statistics ({hours}h)",
                color=discord.Color.blue()
            )
            
            # Overview
            total = stats["total_events"]
            blocked = stats["blocked_requests"]
            block_rate = (blocked / total * 100) if total > 0 else 0
            
            embed.add_field(
                name="📈 Overview",
                value=(
                    f"**Total Events:** {total:,}\n"
                    f"**Blocked:** {blocked:,} ({block_rate:.1f}%)\n"
                    f"**Total Wait:** {stats['total_wait_time']:.2f}s\n"
                    f"**Avg Wait:** {stats['average_wait_time']:.2f}s"
                ),
                inline=True
            )
            
            # Current stats
            current = stats["current_stats"]
            embed.add_field(
                name="🔄 Current Session",
                value=(
                    f"**Requests:** {current['total_requests']:,}\n"
                    f"**Blocked:** {current['blocked_requests']:,}\n"
                    f"**429 Hits:** {current['rate_limit_hits']}"
                ),
                inline=True
            )
            
            # Bucket info
            embed.add_field(
                name="🪣 Bucket Info",
                value=(
                    f"**Active:** {stats['active_buckets']}\n"
                    f"**On Cooldown:** {stats['buckets_on_cooldown']}"
                ),
                inline=True
            )
            
            # By bucket type
            if stats["by_bucket_type"]:
                type_text = "\n".join([
                    f"**{t}:** {c:,} events"
                    for t, c in sorted(stats["by_bucket_type"].items(), key=lambda x: x[1], reverse=True)[:5]
                ])
                embed.add_field(
                    name="📊 By Bucket Type",
                    value=type_text or "No data",
                    inline=False
                )
            
            embed.set_footer(text=f"Timeframe: Last {hours} hours")
            await msg.edit(content=None, embed=embed)
            
        except Exception as e:
            await msg.edit(content=f"❌ Failed to fetch statistics: {e}")
    
    @ratelimit.command(name="buckets")
    @commands.has_permissions(administrator=True)
    async def rl_buckets(self, ctx):
        """View active rate limit buckets"""
        limiter = get_rate_limiter()
        
        if not limiter:
            await ctx.send("❌ Rate limiter is not initialized.")
            return
        
        if not limiter.buckets:
            await ctx.send("✅ No active rate limit buckets.")
            return
        
        embed = discord.Embed(
            title="🪣 Active Rate Limit Buckets",
            description=f"Total: {len(limiter.buckets)}",
            color=discord.Color.blue()
        )
        
        # Group by status
        available = []
        exhausted = []
        
        for bucket in limiter.buckets.values():
            status = "🔴" if bucket.is_exhausted() else "🟢"
            bucket_info = f"{status} `{bucket.bucket_id}` - {bucket.remaining}/{bucket.limit}"
            
            if bucket.is_exhausted():
                bucket_info += f" (resets in {bucket.time_until_reset():.1f}s)"
                exhausted.append(bucket_info)
            else:
                available.append(bucket_info)
        
        if available:
            embed.add_field(
                name=f"🟢 Available ({len(available)})",
                value="\n".join(available[:10]) + (f"\n... and {len(available) - 10} more" if len(available) > 10 else ""),
                inline=False
            )
        
        if exhausted:
            embed.add_field(
                name=f"🔴 Exhausted ({len(exhausted)})",
                value="\n".join(exhausted[:10]) + (f"\n... and {len(exhausted) - 10} more" if len(exhausted) > 10 else ""),
                inline=False
            )
        
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
        await ctx.send(embed=embed)
    
    @ratelimit.command(name="bucket")
    @commands.has_permissions(administrator=True)
    async def rl_bucket(self, ctx, bucket_type: str, resource_id: Optional[str] = None):
        """View specific bucket status"""
        limiter = get_rate_limiter()
        
        if not limiter:
            await ctx.send("❌ Rate limiter is not initialized.")
            return
        
        # Parse bucket type
        try:
            type_enum = RateLimitType[bucket_type.upper()]
        except KeyError:
            await ctx.send(f"❌ Invalid bucket type. Valid types: {', '.join([t.name for t in RateLimitType])}")
            return
        
        status = limiter.get_bucket_status(type_enum, resource_id)
        
        embed = discord.Embed(
            title=f"🪣 Bucket Status: {status['bucket_id']}",
            color=discord.Color.red() if status['is_exhausted'] else discord.Color.green()
        )
        
        embed.add_field(
            name="📊 Limits",
            value=(
                f"**Limit:** {status['limit']}\n"
                f"**Remaining:** {status['remaining']}\n"
                f"**Reset After:** {status['reset_after']}s"
            ),
            inline=True
        )
        
        embed.add_field(
            name="⏱️ Status",
            value=(
                f"**Can Request:** {'✅ Yes' if status['can_request'] else '❌ No'}\n"
                f"**Exhausted:** {'🔴 Yes' if status['is_exhausted'] else '🟢 No'}\n"
                f"**Reset In:** {status['time_until_reset']:.1f}s"
            ),
            inline=True
        )
        
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
        await ctx.send(embed=embed)
    
    @ratelimit.command(name="cooldowns")
    @commands.has_permissions(administrator=True)
    async def rl_cooldowns(self, ctx):
        """View active cooldowns"""
        limiter = get_rate_limiter()
        
        if not limiter:
            await ctx.send("❌ Rate limiter is not initialized.")
            return
        
        if not limiter.cooldowns:
            await ctx.send("✅ No active cooldowns.")
            return
        
        embed = discord.Embed(
            title="⏱️ Active Cooldowns",
            description=f"Total: {len(limiter.cooldowns)}",
            color=discord.Color.blue()
        )
        
        cooldown_list = []
        for key, reset_time in limiter.cooldowns.items():
            remaining = reset_time - time.time()
            if remaining > 0:
                cooldown_list.append(f"• `{key}` - {remaining:.1f}s remaining")
        
        if cooldown_list:
            embed.add_field(
                name="Active Cooldowns",
                value="\n".join(cooldown_list[:15]) + (f"\n... and {len(cooldown_list) - 15} more" if len(cooldown_list) > 15 else ""),
                inline=False
            )
        else:
            embed.description = "No active cooldowns"
        
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(RateLimitCommands(bot))
