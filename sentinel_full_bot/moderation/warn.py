import discord
from discord.ext import commands
from datetime import datetime, timedelta
import json
import os
import asyncio

LOG_CHANNEL_ID = 1466641783105785886

# Warnings data file
WARNINGS_FILE = "data/warnings.json"

# Warning thresholds
WARN_LIMIT = 3
TIMEOUT_DURATION = 20  # minutes


class WarnSystem:
    """Manage user warnings"""
    
    def __init__(self):
        self.warnings = self._load_warnings()
    
    def _load_warnings(self) -> dict:
        """Load warnings from file"""
        if not os.path.exists(WARNINGS_FILE):
            return {}
        
        try:
            with open(WARNINGS_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    
    def _save_warnings(self):
        """Save warnings to file"""
        os.makedirs("data", exist_ok=True)
        with open(WARNINGS_FILE, 'w') as f:
            json.dump(self.warnings, f, indent=2)
    
    def add_warning(self, guild_id: int, user_id: int, reason: str, moderator_id: int) -> int:
        """Add warning and return current count"""
        key = f"{guild_id}_{user_id}"
        
        if key not in self.warnings:
            self.warnings[key] = {
                "count": 0,
                "warnings": []
            }
        
        self.warnings[key]["warnings"].append({
            "reason": reason,
            "moderator_id": moderator_id,
            "timestamp": datetime.utcnow().isoformat()
        })
        self.warnings[key]["count"] += 1
        
        self._save_warnings()
        return self.warnings[key]["count"]
    
    def get_warnings(self, guild_id: int, user_id: int) -> dict:
        """Get user warnings"""
        key = f"{guild_id}_{user_id}"
        return self.warnings.get(key, {"count": 0, "warnings": []})
    
    def clear_warnings(self, guild_id: int, user_id: int) -> int:
        """Clear all warnings for a user"""
        key = f"{guild_id}_{user_id}"
        
        if key not in self.warnings:
            return 0
        
        count = self.warnings[key]["count"]
        del self.warnings[key]
        self._save_warnings()
        return count
    
    def remove_warning(self, guild_id: int, user_id: int, warning_index: int) -> bool:
        """Remove specific warning by index"""
        key = f"{guild_id}_{user_id}"
        
        if key not in self.warnings or warning_index >= len(self.warnings[key]["warnings"]):
            return False
        
        self.warnings[key]["warnings"].pop(warning_index)
        self.warnings[key]["count"] -= 1
        self._save_warnings()
        return True


class Warn(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.warn_system = WarnSystem()

    def _has_warn_permission(self, member: discord.Member) -> bool:
        """Check if member can warn users"""
        return member.guild_permissions.manage_messages

    @commands.command(name="warn")
    @commands.guild_only()
    async def warn(
        self,
        ctx: commands.Context,
        target: str,
        *,
        reason: str = "No reason provided"
    ):
        """
        Warn a user for rule violations
        3rd warning = 20 minute timeout
        Usage: !warn @user [reason]
               !warn user_id [reason]
               !warn username [reason]
        """
        
        # 🔇 Silent permission check
        if not self._has_warn_permission(ctx.author):
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
        
        # Can't warn self
        if target_member.id == ctx.author.id:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return
        
        # Can't warn the owner
        if target_member.id == 814466767598256150:  # Owner ID
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return
        
        # Can't warn bot
        if target_member.bot:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return
        
        # Can't warn higher role (unless owner)
        if target_member.top_role >= ctx.author.top_role and ctx.author.id != guild.owner_id:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return
        
        # Add warning
        warn_count = self.warn_system.add_warning(guild.id, target_member.id, reason, ctx.author.id)
        
        # Send DM to warned user
        try:
            embed = discord.Embed(
                title="⚠️ You have been warned",
                color=discord.Color.orange(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Server", value=guild.name, inline=False)
            embed.add_field(name="Moderator", value=str(ctx.author), inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Warnings", value=f"{warn_count}/{WARN_LIMIT}", inline=True)
            
            if warn_count == WARN_LIMIT:
                embed.add_field(
                    name="⚠️ Alert",
                    value=f"You have reached the warning limit and will be timed out for {TIMEOUT_DURATION} minutes!",
                    inline=False
                )
                embed.color = discord.Color.red()
            
            embed.set_footer(text="Sentinel Moderation System")
            
            await target_member.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            # User has DMs disabled, continue anyway
            pass
        
        # Delete command message
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass
        
        # Send confirmation message
        confirm_msg = await ctx.send(
            f"⚠️ **{target_member}** has been warned.\n**Warnings:** {warn_count}/{WARN_LIMIT}\n**Reason:** {reason}"
        )
        
        # Auto-delete confirmation after 3 seconds
        await asyncio.sleep(3)
        try:
            await confirm_msg.delete()
        except discord.Forbidden:
            pass
        
        # Log warning
        await self._log_warning(guild, ctx.author, target_member, reason, warn_count)
        
        # If 3rd warning, timeout
        if warn_count >= WARN_LIMIT:
            await self._execute_timeout(ctx, guild, target_member)
    
    async def _execute_timeout(self, ctx: commands.Context, guild: discord.Guild, member: discord.Member):
        """Execute timeout on 3rd warning"""
        
        # Check bot permissions
        if not guild.me.guild_permissions.moderate_members:
            return
        
        try:
            timeout_until = discord.utils.utcnow() + timedelta(minutes=TIMEOUT_DURATION)
            await member.timeout(
                timeout_until,
                reason=f"Automatic timeout: {WARN_LIMIT} warnings reached"
            )
            
            # Log timeout
            await self._log_timeout(guild, member)
            
        except discord.Forbidden:
            pass
        except discord.HTTPException:
            pass

    @commands.command(name="warnings")
    @commands.guild_only()
    async def warnings(self, ctx: commands.Context, target: str = None):
        """
        Check warnings for a user (default: yourself)
        Usage: !warnings
               !warnings @user
               !warnings user_id
        """
        
        # If no target provided, show warnings for command author
        if not target:
            target_user = ctx.author
            target_id = ctx.author.id
        else:
            # Try to resolve target
            target_user = None
            target_id = None
            
            # 1. Try mention
            if ctx.message.mentions:
                target_user = ctx.message.mentions[0]
                target_id = target_user.id
            else:
                # 2. Try ID
                try:
                    target_id = int(target)
                    try:
                        target_user = await ctx.guild.fetch_member(target_id)
                    except discord.NotFound:
                        pass
                except ValueError:
                    pass
            
            # 3. Try username
            if not target_id:
                for member in ctx.guild.members:
                    if member.name.lower() == target.lower() or member.display_name.lower() == target.lower():
                        target_user = member
                        target_id = member.id
                        break
            
            # Not found
            if not target_id:
                await ctx.send("❌ User not found")
                return
        
        # Get warnings
        warn_data = self.warn_system.get_warnings(ctx.guild.id, target_id)
        warn_count = warn_data["count"]
        
        embed = discord.Embed(
            title="⚠️ Warning History",
            color=discord.Color.orange() if warn_count > 0 else discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(
            name="User",
            value=f"{target_user.mention if target_user else f'ID: {target_id}'} ({target_user or 'Unknown'})",
            inline=False
        )
        embed.add_field(
            name="Total Warnings",
            value=f"{warn_count}/{WARN_LIMIT}",
            inline=True
        )
        
        if warn_count >= WARN_LIMIT:
            embed.add_field(
                name="Status",
                value="🔴 TIMED OUT (Warning limit reached)",
                inline=True
            )
        
        if warn_data["warnings"]:
            for i, warning in enumerate(warn_data["warnings"], 1):
                mod = await self.bot.fetch_user(warning["moderator_id"]) if warning.get("moderator_id") else None
                warn_time = datetime.fromisoformat(warning["timestamp"])
                
                embed.add_field(
                    name=f"Warning #{i}",
                    value=f"**Reason:** {warning['reason']}\n**Moderator:** {mod or 'Unknown'}\n**Time:** {discord.utils.format_dt(warn_time, style='F')}",
                    inline=False
                )
        else:
            embed.add_field(
                name="Warnings",
                value="✅ No warnings",
                inline=False
            )
        
        embed.set_footer(text="Sentinel Moderation System")
        
        await ctx.send(embed=embed)

    @commands.command(name="clear_warns")
    @commands.guild_only()
    async def clear_warns(self, ctx: commands.Context, target: str, *, reason: str = "No reason provided"):
        """
        Clear all warnings for a user
        Usage: !clear_warns @user [reason]
               !clear_warns user_id [reason]
        
        Requires Manage Messages permission
        """
        
        if not self._has_warn_permission(ctx.author):
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return
        
        # Try to resolve target
        target_member = None
        
        # 1. Try mention
        if ctx.message.mentions:
            target_member = ctx.message.mentions[0]
        else:
            # 2. Try ID
            try:
                user_id = int(target)
                try:
                    target_member = await ctx.guild.fetch_member(user_id)
                except discord.NotFound:
                    pass
            except ValueError:
                pass
        
        # 3. Try username
        if not target_member:
            for member in ctx.guild.members:
                if member.name.lower() == target.lower() or member.display_name.lower() == target.lower():
                    target_member = member
                    break
        
        if not target_member:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return
        
        # Clear warnings
        cleared_count = self.warn_system.clear_warnings(ctx.guild.id, target_member.id)
        
        # Delete command
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass
        
        # Send confirmation
        confirm_msg = await ctx.send(
            f"✅ Cleared {cleared_count} warning(s) for **{target_member}**.\n**Reason:** {reason}"
        )
        
        await asyncio.sleep(3)
        try:
            await confirm_msg.delete()
        except discord.Forbidden:
            pass
        
        # Log
        await self._log_clear_warns(ctx.guild, ctx.author, target_member, cleared_count, reason)

    async def _log_warning(
        self,
        guild: discord.Guild,
        moderator: discord.Member,
        target: discord.Member,
        reason: str,
        count: int
    ):
        """Log warning to log channel"""
        log_channel = guild.get_channel(LOG_CHANNEL_ID)
        if not log_channel:
            return
        
        embed = discord.Embed(
            title="⚠️ User Warned",
            color=discord.Color.orange() if count < WARN_LIMIT else discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="User", value=f"{target.mention} ({target})", inline=False)
        embed.add_field(name="Moderator", value=f"{moderator.mention} ({moderator})", inline=True)
        embed.add_field(name="Warnings", value=f"{count}/{WARN_LIMIT}", inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        
        if count >= WARN_LIMIT:
            embed.add_field(
                name="⚠️ Action",
                value=f"User will be timed out for {TIMEOUT_DURATION} minutes",
                inline=False
            )
        
        embed.set_footer(text="Sentinel Moderation System")
        
        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            pass
        
        print(f"[WARN] {target} ({count}/{WARN_LIMIT}) | Reason: {reason} | By: {moderator}")

    async def _log_timeout(self, guild: discord.Guild, member: discord.Member):
        """Log automatic timeout from warnings"""
        log_channel = guild.get_channel(LOG_CHANNEL_ID)
        if not log_channel:
            return
        
        embed = discord.Embed(
            title="⏱️ Auto-Timeout: Warning Limit Reached",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="User", value=f"{member.mention} ({member})", inline=False)
        embed.add_field(name="Duration", value=f"{TIMEOUT_DURATION} minutes", inline=True)
        embed.add_field(name="Reason", value=f"{WARN_LIMIT} warnings received", inline=False)
        embed.set_footer(text="Sentinel Moderation System")
        
        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            pass
        
        print(f"[AUTO TIMEOUT] {member} - Warning limit reached")

    async def _log_clear_warns(
        self,
        guild: discord.Guild,
        moderator: discord.Member,
        target: discord.Member,
        count: int,
        reason: str
    ):
        """Log warning clear"""
        log_channel = guild.get_channel(LOG_CHANNEL_ID)
        if not log_channel:
            return
        
        embed = discord.Embed(
            title="✅ Warnings Cleared",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="User", value=f"{target.mention} ({target})", inline=False)
        embed.add_field(name="Moderator", value=f"{moderator.mention} ({moderator})", inline=True)
        embed.add_field(name="Cleared", value=f"{count} warning(s)", inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text="Sentinel Moderation System")
        
        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(Warn(bot))
