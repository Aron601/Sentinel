import asyncio
import discord
from discord.ext import commands
from datetime import datetime
from typing import Optional
import re

LOG_CHANNEL_ID = 1466641783105785886

class SlowMode(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.slowmode_history = {}  # Track slowmode changes
        self.temp_slowmode_timers = {}  # Store temporary slowmode timers

    def _has_kick_permission(self, member: discord.Member) -> bool:
        """Check if member has kick_members permission"""
        return member.guild_permissions.kick_members

    @commands.command(
        name="slowmode",
        aliases=["sm", "slow"],
        help="Set slowmode on a channel. Usage: !slowmode <duration> [channel] [reason]"
    )
    @commands.guild_only()
    async def slowmode(
        self,
        ctx: commands.Context,
        duration: Optional[str] = None,
        channel: Optional[discord.TextChannel] = None,
        *,
        reason: str = "No reason provided"
    ):
        """
        Complex slowmode command with permission checks
        Usage: !slowmode <duration> [channel] [reason]
        Duration formats: 0, 5s, 30m, 2h, 1d
        Examples:
            !slowmode 0 - Remove slowmode from current channel
            !slowmode 5s #general - 5 second cooldown in general
            !slowmode 30m - 30 minute slowmode in current channel
            !slowmode 2h #announcements Spam prevention
        """

        # Permission check - only users with kick_members can use this
        if not self._has_kick_permission(ctx.author):
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return

        # Validate input
        if duration is None:
            embed = discord.Embed(
                title="❌ Invalid Arguments",
                description="Please provide a duration.",
                color=discord.Color.red(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Usage", value="`!slowmode <duration> [channel] [reason]`", inline=False)
            embed.add_field(
                name="Duration Formats",
                value="`0` = Remove\n`5s` = Seconds\n`30m` = Minutes\n`2h` = Hours\n`1d` = Days",
                inline=False
            )
            embed.add_field(
                name="Examples",
                value="`!slowmode 0` - Remove slowmode\n`!slowmode 5s #general` - 5s cooldown\n`!slowmode 30m Spam prevention`",
                inline=False
            )
            embed.set_footer(text="Sentinel Security System")
            return await ctx.send(embed=embed, delete_after=15)

        # Parse duration
        try:
            seconds = self._parse_duration(duration)
        except ValueError:
            embed = discord.Embed(
                title="❌ Invalid Duration Format",
                description=f"Could not parse `{duration}`",
                color=discord.Color.red(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(
                name="Valid Formats",
                value="`0` = Remove\n`5s` = Seconds\n`30m` = Minutes\n`2h` = Hours\n`1d` = Days",
                inline=False
            )
            embed.set_footer(text="Sentinel Security System")
            return await ctx.send(embed=embed, delete_after=10)

        # Cap slowmode at 21600 seconds (6 hours)
        if seconds > 21600 and seconds != 0:
            embed = discord.Embed(
                title="⚠️ Duration Too Long",
                description="Maximum slowmode duration is 6 hours (21600 seconds).",
                color=discord.Color.orange(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Requested", value=f"{seconds} seconds", inline=False)
            embed.add_field(name="Maximum", value="21600 seconds (6 hours)", inline=False)
            embed.set_footer(text="Sentinel Security System")
            return await ctx.send(embed=embed, delete_after=10)

        # Use specified channel or current channel
        target_channel = channel or ctx.channel

        # Verify bot has permissions
        if not target_channel.permissions_for(ctx.guild.me).manage_channels:
            embed = discord.Embed(
                title="❌ Missing Permissions",
                description=f"I don't have **Manage Channels** permission in {target_channel.mention}",
                color=discord.Color.red(),
                timestamp=datetime.utcnow()
            )
            embed.set_footer(text="Sentinel Security System")
            return await ctx.send(embed=embed, delete_after=10)

        # Store previous slowmode for logging
        previous_slowmode = target_channel.slowmode_delay
        
        try:
            await target_channel.edit(
                slowmode_delay=seconds,
                reason=f"Slowmode set by {ctx.author} | {reason}"
            )
        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Error",
                description="Failed to set slowmode. Bot lacks permissions.",
                color=discord.Color.red(),
                timestamp=datetime.utcnow()
            )
            embed.set_footer(text="Sentinel Security System")
            return await ctx.send(embed=embed, delete_after=10)

        # Log to history
        if target_channel.id not in self.slowmode_history:
            self.slowmode_history[target_channel.id] = []
        
        self.slowmode_history[target_channel.id].append({
            "moderator": str(ctx.author),
            "timestamp": datetime.utcnow(),
            "previous": previous_slowmode,
            "new": seconds,
            "reason": reason
        })

        # Create response embed
        embed = discord.Embed(
            title="✅ Slowmode Updated",
            color=discord.Color.green() if seconds > 0 else discord.Color.orange(),
            timestamp=datetime.utcnow()
        )

        embed.add_field(name="Channel", value=target_channel.mention, inline=True)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        
        if seconds == 0:
            embed.add_field(name="Status", value="🟢 Slowmode Removed", inline=True)
            embed.add_field(name="Previous Cooldown", value=f"{previous_slowmode}s", inline=True)
        else:
            embed.add_field(name="Cooldown Duration", value=self._format_duration(seconds), inline=True)
            embed.add_field(name="Previous Cooldown", value=f"{previous_slowmode}s" if previous_slowmode > 0 else "None", inline=True)
        
        embed.add_field(name="Reason", value=reason, inline=False)
        
        embed.set_footer(text="Sentinel Security System")

        # Log to console
        print(
            f"[SLOWMODE] {target_channel.guild.name} | "
            f"Channel: {target_channel.name} | "
            f"Duration: {seconds}s | "
            f"Previous: {previous_slowmode}s | "
            f"By: {ctx.author} | "
            f"Reason: {reason}"
        )

        # Log to log channel
        log_channel = ctx.guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            try:
                await log_channel.send(embed=embed)
            except discord.Forbidden:
                pass

        # Delete command message
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

    @commands.command(
        name="slowmode_status",
        aliases=["smstatus", "sm_status"],
        help="Check slowmode status of all channels or specific channel"
    )
    @commands.guild_only()
    async def slowmode_status(
        self,
        ctx: commands.Context,
        channel: Optional[discord.TextChannel] = None
    ):
        """Check slowmode status of channels"""

        if not self._has_kick_permission(ctx.author):
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return

        embed = discord.Embed(
            title="📊 Slowmode Status Report",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )

        if channel:
            # Single channel status
            slowmode = channel.slowmode_delay
            status = "🔴 Active" if slowmode > 0 else "🟢 Inactive"
            
            embed.add_field(name="Channel", value=channel.mention, inline=False)
            embed.add_field(name="Status", value=status, inline=True)
            embed.add_field(name="Cooldown", value=f"{slowmode}s" if slowmode > 0 else "None", inline=True)
            
            if slowmode > 0:
                embed.add_field(name="Formatted", value=self._format_duration(slowmode), inline=True)
            
            # Show history if available
            if channel.id in self.slowmode_history:
                history = self.slowmode_history[channel.id][-3:]  # Last 3 changes
                history_text = "\n".join([
                    f"• {h['moderator']}: {h['previous']}s → {h['new']}s ({h['reason']})"
                    for h in history
                ])
                embed.add_field(name="Recent Changes", value=history_text, inline=False)
        else:
            # All channels status
            active_channels = []
            inactive_channels = 0

            for ch in ctx.guild.text_channels:
                if ch.slowmode_delay > 0:
                    active_channels.append(f"{ch.mention}: {ch.slowmode_delay}s")
                else:
                    inactive_channels += 1

            embed.add_field(name="Total Channels", value=str(len(ctx.guild.text_channels)), inline=True)
            embed.add_field(name="Active Slowmode", value=str(len(active_channels)), inline=True)
            embed.add_field(name="Inactive", value=str(inactive_channels), inline=True)

            if active_channels:
                if len(active_channels) <= 10:
                    embed.add_field(
                        name="🔴 Channels with Slowmode",
                        value="\n".join(active_channels),
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="🔴 Channels with Slowmode (Top 10)",
                        value="\n".join(active_channels[:10]),
                        inline=False
                    )

        embed.set_footer(text="Sentinel Security System")
        
        # Log to log channel
        log_channel = ctx.guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            try:
                await log_channel.send(embed=embed)
            except discord.Forbidden:
                pass

        # Delete command message
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

    @commands.command(
        name="slowmode_reset",
        aliases=["smreset", "sm_reset"],
        help="Reset slowmode on all channels"
    )
    @commands.guild_only()
    async def slowmode_reset(self, ctx: commands.Context):
        """Reset slowmode on all channels at once"""

        if not self._has_kick_permission(ctx.author):
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return

        # Confirmation
        confirm_embed = discord.Embed(
            title="⚠️ Confirm Slowmode Reset",
            description="This will remove slowmode from all channels. React ✅ to confirm.",
            color=discord.Color.orange(),
            timestamp=datetime.utcnow()
        )
        confirm_embed.set_footer(text="Sentinel Security System")
        
        msg = await ctx.send(embed=confirm_embed)
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ["✅", "❌"]

        try:
            reaction, user = await self.bot.wait_for("reaction_add", check=check, timeout=30)

            if str(reaction.emoji) == "❌":
                cancel_embed = discord.Embed(
                    title="❌ Cancelled",
                    description="Slowmode reset cancelled.",
                    color=discord.Color.red(),
                    timestamp=datetime.utcnow()
                )
                cancel_embed.set_footer(text="Sentinel Security System")
                return await ctx.send(embed=cancel_embed, delete_after=5)

        except asyncio.TimeoutError:
            timeout_embed = discord.Embed(
                title="⏰ Timeout",
                description="Slowmode reset cancelled (timeout).",
                color=discord.Color.red(),
                timestamp=datetime.utcnow()
            )
            timeout_embed.set_footer(text="Sentinel Security System")
            return await ctx.send(embed=timeout_embed, delete_after=1)

        # Reset all channels
        reset_count = 0
        for channel in ctx.guild.text_channels:
            if channel.slowmode_delay > 0:
                try:
                    await channel.edit(
                        slowmode_delay=0,
                        reason=f"Slowmode reset by {ctx.author}"
                    )
                    reset_count += 1
                except discord.Forbidden:
                    continue

        success_embed = discord.Embed(
            title="✅ Slowmode Reset Complete",
            description=f"Removed slowmode from {reset_count} channels.",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        success_embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        success_embed.set_footer(text="Sentinel Security System")

        print(f"[SLOWMODE] Batch reset executed by {ctx.author} | Channels reset: {reset_count}")

        # Log to log channel
        log_channel = ctx.guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            try:
                await log_channel.send(embed=success_embed)
            except discord.Forbidden:
                pass

        # Delete command message
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

    def _parse_duration(self, duration_str: str) -> int:
        """Parse duration string to seconds"""
        duration_str = duration_str.lower().strip()

        if duration_str == "0":
            return 0

        # Extract number and unit
        import re
        match = re.match(r'(\d+)([smhd]?)', duration_str)
        
        if not match:
            raise ValueError(f"Invalid duration format: {duration_str}")

        amount = int(match.group(1))
        unit = match.group(2) or "s"

        multipliers = {
            "s": 1,
            "m": 60,
            "h": 3600,
            "d": 86400
        }

        if unit not in multipliers:
            raise ValueError(f"Invalid time unit: {unit}")

        return amount * multipliers[unit]

    def _format_duration(self, seconds: int) -> str:
        """Format seconds to human-readable duration"""
        if seconds == 0:
            return "No cooldown"

        if seconds < 60:
            return f"{seconds} second{'s' if seconds != 1 else ''}"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        elif seconds < 86400:
            hours = seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''}"
        else:
            days = seconds // 86400
            return f"{days} day{'s' if days != 1 else ''}"


async def setup(bot: commands.Bot):
    await bot.add_cog(SlowMode(bot))
