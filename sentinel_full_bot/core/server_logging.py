import discord
from discord.ext import commands
from datetime import datetime
import asyncio

LOG_CHANNEL_ID = 1466641783105785886

# Track deletions to exclude purge and spam operations
# Format: {message_id: "purge" | "spam"}
EXCLUDED_DELETIONS = {}


class ServerLogging(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Log when member joins the server"""
        
        guild = member.guild
        embed = discord.Embed(
            title="✅ Member Joined",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(
            name="User",
            value=f"{member.mention} ({member})",
            inline=False
        )
        embed.add_field(
            name="User ID",
            value=member.id,
            inline=True
        )
        embed.add_field(
            name="Account Created",
            value=discord.utils.format_dt(member.created_at, style="F"),
            inline=False
        )
        embed.add_field(
            name="Joined At",
            value=discord.utils.format_dt(member.joined_at, style="F"),
            inline=False
        )
        
        # Check if new account (less than 24 hours old)
        account_age = datetime.utcnow() - member.created_at.replace(tzinfo=None)
        if account_age.total_seconds() < 86400:
            embed.add_field(
                name="⚠️ New Account",
                value=f"Created {int(account_age.total_seconds() // 3600)} hours ago",
                inline=False
            )
            embed.color = discord.Color.gold()
        
        embed.set_thumbnail(url=member.avatar.url if member.avatar else "")
        embed.set_footer(text="Sentinel Logging System")
        
        await self._send_log(guild, embed)
        print(f"[JOIN] {member} ({member.id})")
    
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Log when member leaves the server"""
        
        guild = member.guild
        embed = discord.Embed(
            title="❌ Member Left",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(
            name="User",
            value=f"{member} ({member.name}#{member.discriminator})",
            inline=False
        )
        embed.add_field(
            name="User ID",
            value=member.id,
            inline=True
        )
        embed.add_field(
            name="Joined At",
            value=discord.utils.format_dt(member.joined_at, style="F") if member.joined_at else "Unknown",
            inline=False
        )
        embed.add_field(
            name="Member Duration",
            value=self._format_duration(datetime.utcnow() - member.joined_at.replace(tzinfo=None)) if member.joined_at else "Unknown",
            inline=True
        )
        
        # Show roles
        if member.roles:
            roles = [role.mention for role in member.roles if role != guild.default_role]
            if roles:
                embed.add_field(
                    name="Roles",
                    value=", ".join(roles)[:1024],
                    inline=False
                )
        
        embed.set_thumbnail(url=member.avatar.url if member.avatar else "")
        embed.set_footer(text="Sentinel Logging System")
        
        await self._send_log(guild, embed)
        print(f"[LEAVE] {member} ({member.id})")
    
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Log when message is deleted (excluding purge and spam operations)"""
        
        # Ignore bot messages
        if message.author.bot:
            return
        
        # Check if this deletion should be excluded (purge or spam)
        if message.id in EXCLUDED_DELETIONS:
            del EXCLUDED_DELETIONS[message.id]
            return
        
        guild = message.guild
        if not guild:
            return
        
        # Build message content for log
        content = message.content or "(No text content)"
        if len(content) > 1024:
            content = content[:1021] + "..."
        
        embed = discord.Embed(
            title="🗑️ Message Deleted",
            color=discord.Color.orange(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(
            name="User",
            value=f"{message.author.mention} ({message.author})",
            inline=False
        )
        embed.add_field(
            name="Channel",
            value=f"{message.channel.mention}",
            inline=True
        )
        embed.add_field(
            name="Message ID",
            value=message.id,
            inline=True
        )
        embed.add_field(
            name="Content",
            value=content,
            inline=False
        )
        
        # Add message metadata
        embed.add_field(
            name="Posted At",
            value=discord.utils.format_dt(message.created_at, style="F"),
            inline=False
        )
        embed.add_field(
            name="Message Age",
            value=self._format_duration(datetime.utcnow() - message.created_at.replace(tzinfo=None)),
            inline=True
        )
        
        # Show attachments if any
        if message.attachments:
            attachment_names = [att.filename for att in message.attachments]
            embed.add_field(
                name=f"Attachments ({len(message.attachments)})",
                value=", ".join(attachment_names)[:1024],
                inline=False
            )
        
        # Show embeds if any
        if message.embeds:
            embed.add_field(
                name=f"Embeds ({len(message.embeds)})",
                value=f"{len(message.embeds)} embedded message(s)",
                inline=False
            )
        
        embed.set_thumbnail(url=message.author.avatar.url if message.author.avatar else "")
        embed.set_footer(text="Sentinel Logging System")
        
        await self._send_log(guild, embed)
        print(f"[DELETE] {message.author} - {message.id} in {message.channel.name}")
    
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Log when member is banned or timeout is applied"""
        
        guild = before.guild
        
        # Check if timed out
        if before.timed_out_until != after.timed_out_until and after.timed_out_until:
            embed = discord.Embed(
                title="⏱️ Member Timeout",
                color=discord.Color.orange(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(
                name="User",
                value=f"{after.mention} ({after})",
                inline=False
            )
            
            if after.timed_out_until:
                duration = after.timed_out_until.replace(tzinfo=None) - datetime.utcnow()
                embed.add_field(
                    name="Duration",
                    value=self._format_duration(duration),
                    inline=True
                )
                embed.add_field(
                    name="Until",
                    value=discord.utils.format_dt(after.timed_out_until, style="F"),
                    inline=True
                )
            
            embed.set_thumbnail(url=after.avatar.url if after.avatar else "")
            embed.set_footer(text="Sentinel Logging System")
            
            await self._send_log(guild, embed)
            print(f"[TIMEOUT] {after} ({after.id}) for {duration if after.timed_out_until else 'unknown duration'}")
        
        # Check if timed out was removed
        elif before.timed_out_until and not after.timed_out_until:
            embed = discord.Embed(
                title="✅ Timeout Removed",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(
                name="User",
                value=f"{after.mention} ({after})",
                inline=False
            )
            embed.set_thumbnail(url=after.avatar.url if after.avatar else "")
            embed.set_footer(text="Sentinel Logging System")
            
            await self._send_log(guild, embed)
            print(f"[TIMEOUT REMOVED] {after} ({after.id})")
    
    async def _send_log(self, guild: discord.Guild, embed: discord.Embed):
        """Send log embed to log channel"""
        log_channel = guild.get_channel(LOG_CHANNEL_ID)
        if not log_channel:
            return
        
        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            print(f"[LOGGING ERROR] No permission to send in log channel")
    
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


def mark_deletion_as_purge(message_id: int):
    """Mark message deletion as part of purge operation"""
    EXCLUDED_DELETIONS[message_id] = "purge"


def mark_deletion_as_spam(message_id: int):
    """Mark message deletion as part of spam operation"""
    EXCLUDED_DELETIONS[message_id] = "spam"


async def setup(bot: commands.Bot):
    await bot.add_cog(ServerLogging(bot))
