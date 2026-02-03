import discord
from discord.ext import commands
from datetime import datetime

LOG_CHANNEL_ID = 1466641783105785886


class WhoIs(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    def _has_manage_permission(self, member: discord.Member) -> bool:
        """Check if member can manage messages"""
        return member.guild_permissions.manage_messages
    
    def _format_permissions(self, perms: discord.Permissions) -> list:
        """Get list of notable permissions"""
        notable_perms = [
            "administrator",
            "manage_guild",
            "manage_channels",
            "manage_roles",
            "manage_messages",
            "ban_members",
            "kick_members",
            "moderate_members",
            "manage_webhooks",
            "manage_nicknames",
        ]
        
        active_perms = []
        for perm in notable_perms:
            if getattr(perms, perm, False):
                # Format: "manage_guild" -> "Manage Guild"
                formatted = perm.replace("_", " ").title()
                active_perms.append(formatted)
        
        return active_perms if active_perms else ["No notable permissions"]
    
    @commands.command(name="whois", aliases=["ws"])
    @commands.guild_only()
    async def whois(self, ctx: commands.Context, *, target: str = None):
        """
        Get detailed information about a user
        Usage: !whois @user
               !whois user_id
               !whois username
        
        Only users with Manage Messages permission can use this command
        """
        
        # Permission check
        if not self._has_manage_permission(ctx.author):
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return
        
        # If no target provided, show info about command author
        if not target:
            target_member = ctx.author
        else:
            # Try to resolve target
            target_member = None
            
            # 1. Try mention
            if ctx.message.mentions:
                target_member = ctx.message.mentions[0]
            
            # 2. Try user ID
            if not target_member:
                try:
                    user_id = int(target)
                    try:
                        target_member = await ctx.guild.fetch_member(user_id)
                    except discord.NotFound:
                        # Not in guild, try to fetch user anyway
                        try:
                            target_user = await self.bot.fetch_user(user_id)
                            await self._show_absent_user_info(ctx, target_user)
                            return
                        except discord.NotFound:
                            await ctx.send("❌ User not found")
                            return
                except ValueError:
                    pass
            
            # 3. Try username
            if not target_member:
                target_lower = target.lower()
                for member in ctx.guild.members:
                    if member.name.lower() == target_lower or member.display_name.lower() == target_lower:
                        target_member = member
                        break
            
            # 4. Try fuzzy search
            if not target_member:
                for member in ctx.guild.members:
                    if target_lower in member.name.lower() or target_lower in member.display_name.lower():
                        target_member = member
                        break
            
            # Not found
            if not target_member:
                await ctx.send("❌ User not found")
                return
        
        # Show user info
        await self._show_user_info(ctx, target_member)
    
    async def _show_user_info(self, ctx: commands.Context, member: discord.Member):
        """Show detailed info about a member in the server"""
        
        guild = ctx.guild
        embed = discord.Embed(
            title="👤 User Information",
            color=member.color if member.color != discord.Color.default() else discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        # Basic Info
        embed.add_field(
            name="Username",
            value=f"{member} (ID: {member.id})",
            inline=False
        )
        embed.add_field(
            name="Display Name",
            value=member.display_name,
            inline=True
        )
        embed.add_field(
            name="Status",
            value=f"{member.status.name.capitalize()}",
            inline=True
        )
        
        # Account Dates
        embed.add_field(
            name="Account Created",
            value=f"{discord.utils.format_dt(member.created_at, style='F')}\n({self._time_ago(member.created_at)} ago)",
            inline=False
        )
        embed.add_field(
            name="Joined Server",
            value=f"{discord.utils.format_dt(member.joined_at, style='F')}\n({self._time_ago(member.joined_at)} ago)",
            inline=False
        )
        
        # Membership Duration
        duration = datetime.utcnow() - member.joined_at.replace(tzinfo=None)
        embed.add_field(
            name="In Server For",
            value=self._format_duration(duration),
            inline=True
        )
        
        # Account Age
        account_age = datetime.utcnow() - member.created_at.replace(tzinfo=None)
        embed.add_field(
            name="Account Age",
            value=self._format_duration(account_age),
            inline=True
        )
        
        # Roles
        if member.roles:
            roles = [role.mention for role in member.roles if role != guild.default_role]
            if roles:
                embed.add_field(
                    name=f"Roles ({len(roles)})",
                    value=", ".join(roles[:20]) if len(roles) <= 20 else f"{', '.join(roles[:20])}... and {len(roles) - 20} more",
                    inline=False
                )
            else:
                embed.add_field(
                    name="Roles",
                    value="No roles",
                    inline=False
                )
        
        # Top Role
        embed.add_field(
            name="Highest Role",
            value=member.top_role.mention if member.top_role != guild.default_role else "No roles",
            inline=True
        )
        
        # Permissions
        perms = self._format_permissions(member.guild_permissions)
        embed.add_field(
            name=f"Notable Permissions ({len(perms)})",
            value=", ".join(perms) if len(", ".join(perms)) < 1024 else (", ".join(perms)[:1000] + "..."),
            inline=False
        )
        
        # Bot Status
        if member.bot:
            embed.add_field(
                name="Bot",
                value="✅ Yes",
                inline=True
            )
        
        # Premium Member
        if member.premium_since:
            embed.add_field(
                name="Boosting Since",
                value=discord.utils.format_dt(member.premium_since, style='F'),
                inline=True
            )
        
        # Avatar
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        
        # Footer
        embed.set_footer(text=f"Requested by {ctx.author} • Sentinel Whois System")
        
        await ctx.send(embed=embed)
    
    async def _show_absent_user_info(self, ctx: commands.Context, user: discord.User):
        """Show info about a user not in the server"""
        
        embed = discord.Embed(
            title="👤 User Information (Not in Server)",
            color=discord.Color.greyple(),
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name="Username",
            value=f"{user} (ID: {user.id})",
            inline=False
        )
        embed.add_field(
            name="Account Created",
            value=f"{discord.utils.format_dt(user.created_at, style='F')}\n({self._time_ago(user.created_at)} ago)",
            inline=False
        )
        
        # Account Age
        account_age = datetime.utcnow() - user.created_at.replace(tzinfo=None)
        embed.add_field(
            name="Account Age",
            value=self._format_duration(account_age),
            inline=True
        )
        
        # Bot Status
        if user.bot:
            embed.add_field(
                name="Bot",
                value="✅ Yes",
                inline=True
            )
        
        # Status
        embed.add_field(
            name="Server Status",
            value="❌ Not in server",
            inline=False
        )
        
        embed.add_field(
            name="Information",
            value="User is not a member of this server. Limited information available.",
            inline=False
        )
        
        # Avatar
        embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
        
        # Footer
        embed.set_footer(text=f"Requested by {ctx.author} • Sentinel Whois System")
        
        await ctx.send(embed=embed)
    
    def _time_ago(self, dt: datetime) -> str:
        """Format datetime as time ago"""
        now = datetime.utcnow()
        delta = now - dt.replace(tzinfo=None)
        
        total_seconds = int(delta.total_seconds())
        
        if total_seconds < 60:
            return f"{total_seconds}s"
        elif total_seconds < 3600:
            return f"{total_seconds // 60}m"
        elif total_seconds < 86400:
            return f"{total_seconds // 3600}h"
        else:
            return f"{total_seconds // 86400}d"
    
    def _format_duration(self, delta) -> str:
        """Format timedelta to human readable string"""
        total_seconds = int(delta.total_seconds())
        
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)
        
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if seconds > 0 or not parts:
            parts.append(f"{seconds}s")
        
        return " ".join(parts)


async def setup(bot: commands.Bot):
    await bot.add_cog(WhoIs(bot))
