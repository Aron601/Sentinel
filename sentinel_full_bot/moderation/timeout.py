import discord
from discord.ext import commands
from datetime import datetime, timedelta
import asyncio
import re

LOG_CHANNEL_ID = 1466641783105785886

# Max timeout duration is 28 days
MAX_TIMEOUT_SECONDS = 28 * 24 * 60 * 60


class TimeOut(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _has_timeout_permission(self, member: discord.Member) -> bool:
        """Check if member can timeout users"""
        return member.guild_permissions.moderate_members

    def _parse_duration(self, duration_str: str) -> int:
        """
        Parse duration string and return seconds
        Examples: 5m, 30m, 2h, 1d
        Returns: seconds, or None if invalid
        """
        duration_str = duration_str.lower().strip()
        match = re.match(r'^(\d+)([smhd])$', duration_str)
        
        if not match:
            return None
        
        amount, unit = int(match.group(1)), match.group(2)
        
        if unit == 's':
            return amount
        elif unit == 'm':
            return amount * 60
        elif unit == 'h':
            return amount * 3600
        elif unit == 'd':
            return amount * 86400
        
        return None

    def _format_duration(self, seconds: int) -> str:
        """Format seconds to human readable string"""
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}m"
        elif seconds < 86400:
            return f"{seconds // 3600}h"
        else:
            return f"{seconds // 86400}d"

    @commands.command(name="timeout")
    @commands.guild_only()
    async def timeout(
        self,
        ctx: commands.Context,
        target: str = None,
        duration: str = None,
        *,
        reason: str = "No reason provided"
    ):
        """
        Timeout a user for specified duration
        Usage: !timeout @user 5m [reason]
               !timeout user_id 1h [reason]
               !timeout username 30m [reason]
        
        Durations: s (seconds), m (minutes), h (hours), d (days) - max 28d
        """
        
        # Validate required arguments
        if not target or not duration:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return
        
        # 🔇 Silent permission check
        if not self._has_timeout_permission(ctx.author):
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return

        guild = ctx.guild
        
        # Parse duration
        timeout_seconds = self._parse_duration(duration)
        if not timeout_seconds:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return
        
        # Check max duration (28 days)
        if timeout_seconds > MAX_TIMEOUT_SECONDS:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return
        
        # Try to resolve the target
        target_member = None
        
        # 1. Try as mention
        try:
            if ctx.message.mentions:
                target_member = ctx.message.mentions[0]
        except:
            pass
        
        # 2. Try as user ID
        if not target_member:
            try:
                user_id = int(target)
                try:
                    target_member = await guild.fetch_member(user_id)
                except discord.NotFound:
                    pass
            except (ValueError, discord.NotFound):
                pass
        
        # 3. Try as username/display name
        if not target_member:
            for member in guild.members:
                if member.name.lower() == target.lower() or member.display_name.lower() == target.lower():
                    target_member = member
                    break
        
        # 4. Try fuzzy search (partial match)
        if not target_member:
            target_lower = target.lower()
            for member in guild.members:
                if target_lower in member.name.lower() or target_lower in member.display_name.lower():
                    target_member = member
                    break
        
        # No target found
        if not target_member:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return
        
        # Can't timeout self
        if target_member.id == ctx.author.id:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return
        
        # Can't timeout the owner
        if target_member.id == 814466767598256150:  # Owner ID
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return
        
        # Can't timeout bot
        if target_member.bot:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return
        
        # Can't timeout higher role (unless owner)
        if target_member.top_role >= ctx.author.top_role and ctx.author.id != guild.owner_id:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return
        
        # Verify bot has permissions
        if not guild.me.guild_permissions.moderate_members:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return
        
        # Calculate timeout until time
        timeout_until = discord.utils.utcnow() + timedelta(seconds=timeout_seconds)
        
        # Send DM to timed out user
        try:
            embed = discord.Embed(
                title="⏱️ You have been timed out",
                color=discord.Color.orange(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Server", value=guild.name, inline=False)
            embed.add_field(name="Duration", value=self._format_duration(timeout_seconds), inline=True)
            embed.add_field(name="Until", value=discord.utils.format_dt(timeout_until, style="F"), inline=False)
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.set_footer(text="Sentinel Moderation System")
            
            await target_member.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            # User has DMs disabled, continue anyway
            pass
        
        # Attempt the timeout
        try:
            await target_member.timeout(
                timeout_until,
                reason=f"Timed out by {ctx.author} | {reason}"
            )
        except discord.Forbidden:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return
        
        # Delete command message
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass
        
        # Send confirmation message
        confirm_msg = await ctx.send(
            f"⏱️ **{target_member}** has been timed out for **{self._format_duration(timeout_seconds)}**.\n**Reason:** {reason}"
        )
        
        # Auto-delete confirmation after 3 seconds
        await asyncio.sleep(3)
        try:
            await confirm_msg.delete()
        except discord.Forbidden:
            pass
        
        # Log to log channel
        await self._log_timeout(guild, ctx.author, target_member, timeout_seconds, reason)

    @commands.command(name="untimeout")
    @commands.guild_only()
    async def untimeout(
        self,
        ctx: commands.Context,
        target: str,
        *,
        reason: str = "No reason provided"
    ):
        """
        Remove timeout from a user
        Usage: !untimeout @user [reason]
               !untimeout user_id [reason]
        """
        
        # 🔇 Silent permission check
        if not self._has_timeout_permission(ctx.author):
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return

        guild = ctx.guild
        
        # Try to resolve the target
        target_member = None
        
        # 1. Try as mention
        try:
            if ctx.message.mentions:
                target_member = ctx.message.mentions[0]
        except:
            pass
        
        # 2. Try as user ID
        if not target_member:
            try:
                user_id = int(target)
                try:
                    target_member = await guild.fetch_member(user_id)
                except discord.NotFound:
                    pass
            except (ValueError, discord.NotFound):
                pass
        
        # 3. Try as username/display name
        if not target_member:
            for member in guild.members:
                if member.name.lower() == target.lower() or member.display_name.lower() == target.lower():
                    target_member = member
                    break
        
        # 4. Try fuzzy search
        if not target_member:
            target_lower = target.lower()
            for member in guild.members:
                if target_lower in member.name.lower() or target_lower in member.display_name.lower():
                    target_member = member
                    break
        
        # No target found
        if not target_member:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return
        
        # Verify bot has permissions
        if not guild.me.guild_permissions.moderate_members:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return
        
        # Attempt to remove timeout
        try:
            await target_member.timeout(None, reason=f"Timeout removed by {ctx.author} | {reason}")
        except discord.Forbidden:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return
        
        # Delete command message
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass
        
        # Send confirmation message
        confirm_msg = await ctx.send(
            f"✅ **{target_member}** timeout has been removed.\n**Reason:** {reason}"
        )
        
        # Auto-delete confirmation after 3 seconds
        await asyncio.sleep(3)
        try:
            await confirm_msg.delete()
        except discord.Forbidden:
            pass
        
        # Log to log channel
        await self._log_untimeout(guild, ctx.author, target_member, reason)

    @commands.command(name="timeout_info")
    @commands.guild_only()
    async def timeout_info(self, ctx: commands.Context):
        """Show timeout command info"""
        if not self._has_timeout_permission(ctx.author):
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return
        
        embed = discord.Embed(
            title="📋 Timeout Command Info",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(
            name="Timeout Usage",
            value="`!timeout <user> <duration> [reason]`",
            inline=False
        )
        embed.add_field(
            name="Duration Format",
            value="• `s` - seconds\n• `m` - minutes\n• `h` - hours\n• `d` - days (max 28d)",
            inline=False
        )
        embed.add_field(
            name="Timeout Examples",
            value="`!timeout @user 5m Spam`\n`!timeout 123456789 1h Spamming`\n`!timeout John 30m Too many messages`",
            inline=False
        )
        embed.add_field(
            name="Untimeout Usage",
            value="`!untimeout <user> [reason]`",
            inline=False
        )
        embed.add_field(
            name="Untimeout Example",
            value="`!untimeout @user Appeal accepted`",
            inline=False
        )
        embed.add_field(
            name="Requirements",
            value="• You need **Moderate Members** permission\n• Target must be below your role",
            inline=False
        )
        embed.set_footer(text="Sentinel Moderation System")
        
        await ctx.send(embed=embed, delete_after=15)
        
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

    async def _log_timeout(
        self,
        guild: discord.Guild,
        moderator: discord.Member,
        target: discord.Member,
        duration: int,
        reason: str
    ):
        """Log timeout action to log channel"""
        log_channel = guild.get_channel(LOG_CHANNEL_ID)
        if not log_channel:
            return
        
        embed = discord.Embed(
            title="⏱️ User Timed Out",
            color=discord.Color.orange(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="User", value=f"{target.mention} ({target})", inline=False)
        embed.add_field(name="Moderator", value=f"{moderator.mention} ({moderator})", inline=True)
        embed.add_field(name="Duration", value=self._format_duration(duration), inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text="Sentinel Moderation System")
        
        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            pass
        
        print(f"[TIMEOUT] {target} | Duration: {self._format_duration(duration)} | By: {moderator}")

    async def _log_untimeout(
        self,
        guild: discord.Guild,
        moderator: discord.Member,
        target: discord.Member,
        reason: str
    ):
        """Log timeout removal to log channel"""
        log_channel = guild.get_channel(LOG_CHANNEL_ID)
        if not log_channel:
            return
        
        embed = discord.Embed(
            title="✅ Timeout Removed",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="User", value=f"{target.mention} ({target})", inline=False)
        embed.add_field(name="Moderator", value=f"{moderator.mention} ({moderator})", inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text="Sentinel Moderation System")
        
        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            pass
        
        print(f"[UNTIMEOUT] {target} | By: {moderator}")


async def setup(bot: commands.Bot):
    await bot.add_cog(TimeOut(bot))
