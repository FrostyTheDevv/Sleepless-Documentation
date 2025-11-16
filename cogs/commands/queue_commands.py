"""
Action Queue Commands
Commands for managing and monitoring the action queue system
"""

import discord
from discord.ext import commands
from typing import Optional
from utils.action_queue import get_queue, QueuePriority
import time


class QueueCommands(commands.Cog):
    """Commands for managing the action queue"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.group(name="queue", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def queue(self, ctx):
        """Manage the action queue system"""
        embed = discord.Embed(
            title="⚙️ Action Queue Management",
            description="Manage bulk antinuke operations with the action queue system",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📊 Status Commands",
            value=(
                "`$queue status` - View queue status\n"
                "`$queue guild` - View guild-specific queue\n"
                "`$queue stats` - View detailed statistics"
            ),
            inline=False
        )
        
        embed.add_field(
            name="⚙️ Control Commands",
            value=(
                "`$queue pause` - Pause queue processing\n"
                "`$queue resume` - Resume queue processing\n"
                "`$queue clear [guild_id]` - Clear queue for guild"
            ),
            inline=False
        )
        
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
        await ctx.send(embed=embed)
    
    @queue.command(name="status")
    @commands.has_permissions(administrator=True)
    async def queue_status(self, ctx):
        """View current queue status"""
        queue = get_queue()
        
        if not queue:
            await ctx.send("❌ Action queue is not initialized.")
            return
        
        status = queue.get_queue_status()
        
        # Create status indicator
        if not status["is_running"]:
            status_emoji = "🔴"
            status_text = "Stopped"
        elif status["is_paused"]:
            status_emoji = "🟡"
            status_text = "Paused"
        else:
            status_emoji = "🟢"
            status_text = "Running"
        
        embed = discord.Embed(
            title="📊 Action Queue Status",
            description=f"{status_emoji} **Status:** {status_text}",
            color=discord.Color.green() if status["is_running"] and not status["is_paused"] else discord.Color.orange()
        )
        
        # Queue metrics
        pending = status["pending"]
        embed.add_field(
            name="📥 Pending Actions",
            value=(
                f"**Total:** {pending['total']}\n"
                f"🔴 Critical: {pending['critical']}\n"
                f"🟠 High: {pending['high']}\n"
                f"🟡 Medium: {pending['medium']}\n"
                f"⚪ Low: {pending['low']}"
            ),
            inline=True
        )
        
        # Completion metrics
        embed.add_field(
            name="✅ Completed",
            value=(
                f"**Success:** {status['completed']}\n"
                f"**Failed:** {status['failed']}\n"
                f"**Total:** {status['statistics']['total_queued']}"
            ),
            inline=True
        )
        
        # System metrics
        embed.add_field(
            name="⚙️ System",
            value=(
                f"**Workers:** {status['workers']}\n"
                f"**Rate Limit:** {status['rate_limit']}/s\n"
                f"**Uptime:** {self._format_duration(status['uptime_seconds'])}"
            ),
            inline=True
        )
        
        # Statistics
        stats = status["statistics"]
        success_rate = (stats["total_completed"] / stats["total_queued"] * 100) if stats["total_queued"] > 0 else 0
        
        embed.add_field(
            name="📈 Statistics",
            value=(
                f"**Success Rate:** {success_rate:.1f}%\n"
                f"**Retried:** {stats['total_retried']}\n"
                f"**Queue Time:** {self._format_duration(time.time() - stats['start_time'])}"
            ),
            inline=False
        )
        
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
        await ctx.send(embed=embed)
    
    @queue.command(name="guild")
    @commands.has_permissions(administrator=True)
    async def queue_guild(self, ctx, guild_id: Optional[int] = None):
        """View queued actions for a specific guild"""
        queue = get_queue()
        
        if not queue:
            await ctx.send("❌ Action queue is not initialized.")
            return
        
        # Use current guild if not specified
        target_guild_id = guild_id or ctx.guild.id
        
        actions = queue.get_guild_queue(target_guild_id)
        
        if not actions:
            await ctx.send(f"✅ No pending actions for guild {target_guild_id}")
            return
        
        embed = discord.Embed(
            title=f"📋 Queued Actions for Guild {target_guild_id}",
            description=f"**Total Actions:** {len(actions)}",
            color=discord.Color.blue()
        )
        
        # Group by priority
        priority_counts = {}
        action_types = {}
        
        for action in actions:
            priority_counts[action.priority.name] = priority_counts.get(action.priority.name, 0) + 1
            action_types[action.action_type] = action_types.get(action.action_type, 0) + 1
        
        # Priority breakdown
        priority_text = "\n".join([f"**{p}:** {c}" for p, c in sorted(priority_counts.items())])
        embed.add_field(
            name="🎯 By Priority",
            value=priority_text or "None",
            inline=True
        )
        
        # Action type breakdown
        type_text = "\n".join([f"**{t}:** {c}" for t, c in sorted(action_types.items(), key=lambda x: x[1], reverse=True)[:5]])
        embed.add_field(
            name="📊 By Type",
            value=type_text or "None",
            inline=True
        )
        
        # Oldest action
        oldest = min(actions, key=lambda a: a.timestamp)
        embed.add_field(
            name="⏰ Oldest Action",
            value=f"**Type:** {oldest.action_type}\n**Age:** {self._format_duration(time.time() - oldest.timestamp)}",
            inline=False
        )
        
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
        await ctx.send(embed=embed)
    
    @queue.command(name="pause")
    @commands.has_permissions(administrator=True)
    async def queue_pause(self, ctx):
        """Pause queue processing"""
        queue = get_queue()
        
        if not queue:
            await ctx.send("❌ Action queue is not initialized.")
            return
        
        if queue.is_paused:
            await ctx.send("⚠️ Queue is already paused.")
            return
        
        queue.pause()
        await ctx.send("⏸️ Queue processing paused. Use `$queue resume` to continue.")
    
    @queue.command(name="resume")
    @commands.has_permissions(administrator=True)
    async def queue_resume(self, ctx):
        """Resume queue processing"""
        queue = get_queue()
        
        if not queue:
            await ctx.send("❌ Action queue is not initialized.")
            return
        
        if not queue.is_paused:
            await ctx.send("⚠️ Queue is not paused.")
            return
        
        queue.resume()
        await ctx.send("▶️ Queue processing resumed.")
    
    @queue.command(name="clear")
    @commands.has_permissions(administrator=True)
    async def queue_clear(self, ctx, guild_id: Optional[int] = None):
        """Clear queued actions for a guild"""
        queue = get_queue()
        
        if not queue:
            await ctx.send("❌ Action queue is not initialized.")
            return
        
        # Use current guild if not specified
        target_guild_id = guild_id or ctx.guild.id
        
        # Confirmation
        confirm_embed = discord.Embed(
            title="⚠️ Confirm Queue Clear",
            description=f"Are you sure you want to clear all pending actions for guild {target_guild_id}?",
            color=discord.Color.orange()
        )
        confirm_embed.add_field(
            name="⚠️ Warning",
            value="This action cannot be undone. All pending actions will be removed from the queue.",
            inline=False
        )
        
        confirm_msg = await ctx.send(embed=confirm_embed)
        await confirm_msg.add_reaction("✅")
        await confirm_msg.add_reaction("❌")
        
        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == confirm_msg.id
        
        try:
            reaction, user = await self.bot.wait_for("reaction_add", timeout=30.0, check=check)
            
            if str(reaction.emoji) == "✅":
                removed = queue.clear_guild_queue(target_guild_id)
                await ctx.send(f"✅ Cleared {removed} pending actions for guild {target_guild_id}")
            else:
                await ctx.send("❌ Queue clear cancelled.")
                
        except TimeoutError:
            await ctx.send("❌ Confirmation timed out. Queue clear cancelled.")
    
    @queue.command(name="stats")
    @commands.has_permissions(administrator=True)
    async def queue_stats(self, ctx):
        """View detailed queue statistics"""
        queue = get_queue()
        
        if not queue:
            await ctx.send("❌ Action queue is not initialized.")
            return
        
        status = queue.get_queue_status()
        stats = status["statistics"]
        
        embed = discord.Embed(
            title="📈 Action Queue Statistics",
            description="Detailed performance metrics",
            color=discord.Color.blue()
        )
        
        # Total metrics
        embed.add_field(
            name="📊 Totals",
            value=(
                f"**Queued:** {stats['total_queued']}\n"
                f"**Completed:** {stats['total_completed']}\n"
                f"**Failed:** {stats['total_failed']}\n"
                f"**Retried:** {stats['total_retried']}"
            ),
            inline=True
        )
        
        # Success rate
        if stats["total_queued"] > 0:
            success_rate = (stats["total_completed"] / stats["total_queued"]) * 100
            failure_rate = (stats["total_failed"] / stats["total_queued"]) * 100
            
            embed.add_field(
                name="✅ Success Rate",
                value=(
                    f"**Success:** {success_rate:.1f}%\n"
                    f"**Failure:** {failure_rate:.1f}%\n"
                    f"**Pending:** {status['pending']['total']}"
                ),
                inline=True
            )
        
        # Performance metrics
        uptime = status["uptime_seconds"]
        actions_per_hour = (stats["total_completed"] / (uptime / 3600)) if uptime > 0 else 0
        
        embed.add_field(
            name="⚡ Performance",
            value=(
                f"**Uptime:** {self._format_duration(uptime)}\n"
                f"**Actions/Hour:** {actions_per_hour:.1f}\n"
                f"**Rate Limit:** {status['rate_limit']}/s"
            ),
            inline=True
        )
        
        # Recent activity (last 10 completed)
        recent = queue.completed_actions[-10:]
        if recent:
            recent_text = "\n".join([
                f"• {a.action_type} (Guild: {a.guild_id})"
                for a in reversed(recent)
            ])
            embed.add_field(
                name="🕐 Recent Completions",
                value=recent_text[:1024],
                inline=False
            )
        
        # Recent failures (last 5)
        failures = queue.failed_actions[-5:]
        if failures:
            failure_text = "\n".join([
                f"• {f.action_type}: {f.error[:50] if f.error else 'Unknown error'}"
                for f in reversed(failures)
            ])
            embed.add_field(
                name="❌ Recent Failures",
                value=failure_text[:1024],
                inline=False
            )
        
        embed.set_footer(text=f"Started: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stats['start_time']))}")
        await ctx.send(embed=embed)
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds / 60)}m {int(seconds % 60)}s"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m"
        else:
            days = int(seconds / 86400)
            hours = int((seconds % 86400) / 3600)
            return f"{days}d {hours}h"


async def setup(bot):
    await bot.add_cog(QueueCommands(bot))
