"""
Antinuke Analytics Commands
Provides statistics and insights dashboard
"""

import discord
from discord.ext import commands
from utils.antinuke_analytics import AntianukeAnalytics
from datetime import datetime
import time

class AntiAnalytics(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.group(name="analytics", aliases=["stats", "antistats"], invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def analytics(self, ctx):
        """View antinuke analytics and statistics"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="📊 Antinuke Analytics",
                description="View comprehensive statistics about antinuke activity",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="📈 Overview Commands",
                value=(
                    "`$analytics overview` - Daily summary\n"
                    "`$analytics dashboard` - Full analytics dashboard\n"
                    "`$analytics timeline [days]` - Activity over time"
                ),
                inline=False
            )
            embed.add_field(
                name="👥 Violator Analysis",
                value=(
                    "`$analytics top [limit]` - Top violators\n"
                    "`$analytics offenders` - Repeat offenders\n"
                    "`$analytics violators [days]` - Violator activity"
                ),
                inline=False
            )
            embed.add_field(
                name="🛡️ Protection Stats",
                value=(
                    "`$analytics protections` - Most triggered protections\n"
                    "`$analytics effectiveness` - Protection effectiveness\n"
                    "`$analytics punishments` - Punishment statistics"
                ),
                inline=False
            )
            embed.add_field(
                name="📉 Activity Analysis",
                value=(
                    "`$analytics frequency [days]` - Action frequency\n"
                    "`$analytics hourly` - Hourly activity pattern\n"
                    "`$analytics actions [days]` - Action breakdown"
                ),
                inline=False
            )
            embed.set_footer(text="⚠️ Administrator permission required")
            await ctx.send(embed=embed)
    
    @analytics.command(name="overview")
    @commands.has_permissions(administrator=True)
    async def analytics_overview(self, ctx):
        """Get today's activity summary"""
        try:
            summary = await AntianukeAnalytics.get_daily_summary(ctx.guild.id)
            
            embed = discord.Embed(
                title="📊 Daily Overview",
                description=f"Summary for {datetime.now().strftime('%B %d, %Y')}",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(
                name="📈 Total Actions",
                value=f"**{summary['total_actions']}** actions detected",
                inline=True
            )
            embed.add_field(
                name="👥 Unique Violators",
                value=f"**{summary['unique_violators']}** users",
                inline=True
            )
            embed.add_field(
                name="🔨 Punishments",
                value=f"**{summary['punishments_applied']}** applied",
                inline=True
            )
            
            if summary['most_active_hour'] is not None:
                embed.add_field(
                    name="⏰ Peak Hour",
                    value=f"{summary['most_active_hour']:02d}:00 - {summary['most_active_hour']+1:02d}:00",
                    inline=True
                )
            
            # Status indicator
            if summary['total_actions'] == 0:
                embed.add_field(
                    name="🟢 Status",
                    value="No suspicious activity today",
                    inline=False
                )
            elif summary['total_actions'] < 10:
                embed.add_field(
                    name="🟡 Status",
                    value="Low activity - Normal operation",
                    inline=False
                )
            elif summary['total_actions'] < 50:
                embed.add_field(
                    name="🟠 Status",
                    value="Moderate activity - Monitoring",
                    inline=False
                )
            else:
                embed.add_field(
                    name="🔴 Status",
                    value="High activity - Potential raid detected",
                    inline=False
                )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Failed to get overview: {e}")
    
    @analytics.command(name="dashboard")
    @commands.has_permissions(administrator=True)
    async def analytics_dashboard(self, ctx, days: int = 7):
        """Full analytics dashboard (default: 7 days)"""
        try:
            if days < 1 or days > 365:
                await ctx.send("❌ Days must be between 1 and 365")
                return
            
            msg = await ctx.send("📊 Generating analytics dashboard...")
            
            # Gather all statistics
            top_violators = await AntianukeAnalytics.get_top_violators(ctx.guild.id, limit=5, days=days)
            action_freq = await AntianukeAnalytics.get_action_frequency(ctx.guild.id, days=days)
            punishment_stats = await AntianukeAnalytics.get_punishment_stats(ctx.guild.id, days=days)
            protections = await AntianukeAnalytics.get_most_triggered_protections(ctx.guild.id, days=days)
            
            # Main dashboard embed
            embed = discord.Embed(
                title="📊 Antinuke Analytics Dashboard",
                description=f"Comprehensive statistics for the past {days} day(s)",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            
            # Punishment overview
            embed.add_field(
                name="🔨 Punishment Overview",
                value=(
                    f"**Total:** {punishment_stats['total_punishments']}\n"
                    f"**Reverted:** {punishment_stats['actions_reverted']} actions"
                ),
                inline=True
            )
            
            # Action frequency
            total_actions = sum(action_freq.values())
            embed.add_field(
                name="📈 Total Actions",
                value=f"**{total_actions}** actions detected",
                inline=True
            )
            
            # Protection effectiveness
            embed.add_field(
                name="🛡️ Protections Triggered",
                value=f"**{len(protections)}** protection types",
                inline=True
            )
            
            # Top violators
            if top_violators:
                violator_text = []
                for i, v in enumerate(top_violators[:5], 1):
                    user = ctx.guild.get_member(v['user_id'])
                    name = user.display_name if user else f"User {v['user_id']}"
                    violator_text.append(f"{i}. **{name}** - {v['action_count']} actions")
                
                embed.add_field(
                    name="👥 Top Violators",
                    value="\n".join(violator_text) if violator_text else "None",
                    inline=False
                )
            
            # Most triggered protections
            if protections:
                prot_text = []
                for action_type, count in protections[:5]:
                    prot_text.append(f"• **{action_type}** - {count} times")
                
                embed.add_field(
                    name="🎯 Most Triggered Protections",
                    value="\n".join(prot_text),
                    inline=False
                )
            
            # Escalation distribution
            if punishment_stats['escalation_distribution']:
                esc_text = []
                for level, count in punishment_stats['escalation_distribution'].items():
                    esc_text.append(f"• {level}: {count}")
                
                embed.add_field(
                    name="📊 Escalation Levels",
                    value="\n".join(esc_text),
                    inline=True
                )
            
            # Punishment types
            if punishment_stats['by_type']:
                pun_text = []
                for pun_type, count in list(punishment_stats['by_type'].items())[:5]:
                    pun_text.append(f"• {pun_type}: {count}")
                
                embed.add_field(
                    name="⚖️ Punishment Types",
                    value="\n".join(pun_text),
                    inline=True
                )
            
            embed.set_footer(text=f"Use $analytics for more detailed commands • Requested by {ctx.author}")
            
            await msg.edit(content=None, embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Failed to generate dashboard: {e}")
    
    @analytics.command(name="top")
    @commands.has_permissions(administrator=True)
    async def analytics_top(self, ctx, limit: int = 10, days: int = 30):
        """View top violators (default: top 10, last 30 days)"""
        try:
            if limit < 1 or limit > 50:
                await ctx.send("❌ Limit must be between 1 and 50")
                return
            
            violators = await AntianukeAnalytics.get_top_violators(ctx.guild.id, limit=limit, days=days)
            
            if not violators:
                await ctx.send(f"✅ No violations detected in the past {days} day(s)")
                return
            
            embed = discord.Embed(
                title=f"👥 Top {min(limit, len(violators))} Violators",
                description=f"Most active users in the past {days} day(s)",
                color=discord.Color.red()
            )
            
            for i, v in enumerate(violators, 1):
                user = ctx.guild.get_member(v['user_id'])
                name = user.mention if user else f"User {v['user_id']}"
                
                last_action_time = datetime.fromtimestamp(v['last_action'])
                time_ago = AntianukeAnalytics.format_duration(time.time() - v['last_action'])
                
                embed.add_field(
                    name=f"#{i} - {name}",
                    value=(
                        f"**Actions:** {v['action_count']}\n"
                        f"**Types:** {', '.join(v['action_types'][:3])}\n"
                        f"**Last:** {time_ago} ago"
                    ),
                    inline=True
                )
            
            embed.set_footer(text=f"Use $analytics dashboard for full overview")
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Failed to get top violators: {e}")
    
    @analytics.command(name="protections")
    @commands.has_permissions(administrator=True)
    async def analytics_protections(self, ctx, days: int = 30):
        """View most triggered protection types"""
        try:
            protections = await AntianukeAnalytics.get_most_triggered_protections(ctx.guild.id, days=days)
            
            if not protections:
                await ctx.send(f"✅ No protections triggered in the past {days} day(s)")
                return
            
            embed = discord.Embed(
                title="🛡️ Protection Statistics",
                description=f"Most triggered protections in the past {days} day(s)",
                color=discord.Color.blue()
            )
            
            # Create bar chart
            prot_dict = {action_type: count for action_type, count in protections}
            chart = AntianukeAnalytics.create_ascii_bar_chart(prot_dict, max_width=15)
            
            embed.add_field(
                name="📊 Trigger Frequency",
                value=f"```\n{chart}\n```",
                inline=False
            )
            
            total_triggers = sum(count for _, count in protections)
            embed.add_field(
                name="📈 Total Triggers",
                value=f"**{total_triggers}** protection triggers",
                inline=True
            )
            embed.add_field(
                name="🎯 Active Protections",
                value=f"**{len(protections)}** protection types",
                inline=True
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Failed to get protection stats: {e}")
    
    @analytics.command(name="offenders")
    @commands.has_permissions(administrator=True)
    async def analytics_offenders(self, ctx, min_offenses: int = 3, days: int = 30):
        """View repeat offenders (default: 3+ offenses, 30 days)"""
        try:
            offenders = await AntianukeAnalytics.get_repeat_offenders(ctx.guild.id, min_offenses, days)
            
            if not offenders:
                await ctx.send(f"✅ No repeat offenders with {min_offenses}+ offenses in the past {days} day(s)")
                return
            
            embed = discord.Embed(
                title="⚠️ Repeat Offenders",
                description=f"Users with {min_offenses}+ offenses in {days} day(s)",
                color=discord.Color.dark_red()
            )
            
            for offender in offenders[:10]:
                user = ctx.guild.get_member(offender['user_id'])
                name = user.mention if user else f"User {offender['user_id']}"
                
                embed.add_field(
                    name=f"{name}",
                    value=(
                        f"**Offenses:** {offender['offense_count']}\n"
                        f"**Max Level:** {offender['max_escalation_level']}\n"
                        f"**Actions:** {', '.join(offender['action_types'][:3])}"
                    ),
                    inline=True
                )
            
            if len(offenders) > 10:
                embed.set_footer(text=f"Showing 10 of {len(offenders)} repeat offenders")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Failed to get repeat offenders: {e}")
    
    @analytics.command(name="timeline")
    @commands.has_permissions(administrator=True)
    async def analytics_timeline(self, ctx, days: int = 7):
        """View activity timeline (default: 7 days)"""
        try:
            if days < 1 or days > 90:
                await ctx.send("❌ Days must be between 1 and 90")
                return
            
            timeline = await AntianukeAnalytics.get_timeline_data(ctx.guild.id, days=days)
            
            if not timeline:
                await ctx.send(f"📭 No activity data for the past {days} day(s)")
                return
            
            embed = discord.Embed(
                title="📈 Activity Timeline",
                description=f"Daily activity over the past {days} day(s)",
                color=discord.Color.green()
            )
            
            # Format timeline data
            dates = []
            actions = []
            punishments = []
            
            for entry in timeline:
                dates.append(entry['date'])
                actions.append(str(entry['action_count']))
                punishments.append(str(entry['punishment_count']))
            
            # Show last 14 days max in embed
            display_days = timeline[-14:]
            
            timeline_text = []
            for entry in display_days:
                date_obj = datetime.strptime(entry['date'], '%Y-%m-%d')
                date_str = date_obj.strftime('%m/%d')
                timeline_text.append(
                    f"`{date_str}` Actions: **{entry['action_count']}** | Punishments: **{entry['punishment_count']}**"
                )
            
            embed.add_field(
                name="📊 Daily Breakdown",
                value="\n".join(timeline_text),
                inline=False
            )
            
            # Summary stats
            total_actions = sum(e['action_count'] for e in timeline)
            total_punishments = sum(e['punishment_count'] for e in timeline)
            avg_daily = total_actions / len(timeline) if timeline else 0
            
            embed.add_field(
                name="📈 Summary",
                value=(
                    f"**Total Actions:** {total_actions}\n"
                    f"**Total Punishments:** {total_punishments}\n"
                    f"**Avg Daily:** {avg_daily:.1f} actions"
                ),
                inline=False
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Failed to get timeline: {e}")
    
    @analytics.command(name="effectiveness")
    @commands.has_permissions(administrator=True)
    async def analytics_effectiveness(self, ctx, days: int = 30):
        """View protection effectiveness ratings"""
        try:
            effectiveness = await AntianukeAnalytics.get_protection_effectiveness(ctx.guild.id, days=days)
            
            if not effectiveness:
                await ctx.send(f"📭 No effectiveness data for the past {days} day(s)")
                return
            
            embed = discord.Embed(
                title="🎯 Protection Effectiveness",
                description=f"How effectively each protection catches violations ({days} days)",
                color=discord.Color.gold()
            )
            
            for action_type, percent in sorted(effectiveness.items(), key=lambda x: x[1], reverse=True):
                if percent >= 80:
                    emoji = "🟢"
                    rating = "Excellent"
                elif percent >= 60:
                    emoji = "🟡"
                    rating = "Good"
                elif percent >= 40:
                    emoji = "🟠"
                    rating = "Fair"
                else:
                    emoji = "🔴"
                    rating = "Needs Improvement"
                
                embed.add_field(
                    name=f"{emoji} {action_type}",
                    value=f"**{percent}%** - {rating}",
                    inline=True
                )
            
            embed.set_footer(text="Effectiveness = % of detected actions that resulted in punishment")
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Failed to get effectiveness: {e}")
    
    @analytics.command(name="hourly")
    @commands.has_permissions(administrator=True)
    async def analytics_hourly(self, ctx, days: int = 1):
        """View hourly activity pattern"""
        try:
            hourly = await AntianukeAnalytics.get_hourly_activity(ctx.guild.id, days=days)
            
            if not hourly:
                await ctx.send(f"📭 No activity data for the past {days} day(s)")
                return
            
            embed = discord.Embed(
                title="⏰ Hourly Activity Pattern",
                description=f"Activity distribution by hour ({days} day(s))",
                color=discord.Color.purple()
            )
            
            # Create bar chart
            chart = AntianukeAnalytics.create_ascii_bar_chart(
                {f"{h:02d}:00": count for h, count in sorted(hourly.items())},
                max_width=10
            )
            
            embed.add_field(
                name="📊 Activity by Hour",
                value=f"```\n{chart}\n```",
                inline=False
            )
            
            # Find peak hours
            if hourly:
                peak_hour = max(hourly.items(), key=lambda x: x[1])[0]
                peak_count = hourly[peak_hour]
                
                embed.add_field(
                    name="📈 Peak Hour",
                    value=f"**{peak_hour:02d}:00** with **{peak_count}** actions",
                    inline=True
                )
                
                total = sum(hourly.values())
                embed.add_field(
                    name="📊 Total Actions",
                    value=f"**{total}** actions",
                    inline=True
                )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Failed to get hourly stats: {e}")

async def setup(bot):
    await bot.add_cog(AntiAnalytics(bot))
