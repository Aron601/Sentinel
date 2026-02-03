import discord
from discord.ext import commands
from datetime import datetime
import asyncio

LOG_CHANNEL_ID = 1466641783105785886


class Kick(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _has_kick_permission(self, member: discord.Member) -> bool:
        """Check if member can kick/ban"""
        return member.guild_permissions.kick_members or member.guild_permissions.ban_members

    @commands.command(name="kick")
    @commands.guild_only()
    async def kick(
        self,
        ctx: commands.Context,
        target: str,
        *,
        reason: str = "No reason provided"
    ):
        """
        Kick a user by mention, name, or ID
        Usage: !kick @user [reason]
               !kick user_id [reason]
               !kick username [reason]
        """
        
        # 🔇 Silent permission check
        if not self._has_kick_permission(ctx.author):
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
                target_member = await guild.fetch_member(user_id)
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
        
        # Can't kick self
        if target_member.id == ctx.author.id:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return
        
        # Can't kick the owner
        if target_member.id == 814466767598256150:  # Owner ID
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return
        
        # Can't kick bot
        if target_member.bot:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return
        
        # Can't kick higher role
        if target_member.top_role >= ctx.author.top_role and ctx.author.id != guild.owner_id:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return
        
        # Verify bot has permissions
        if not guild.me.guild_permissions.kick_members:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return
        
        # Send DM to kicked user
        try:
            embed = discord.Embed(
                title="🦶 You have been kicked",
                color=discord.Color.red(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Server", value=guild.name, inline=False)
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.set_footer(text="Sentinel Moderation System")
            
            await target_member.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            # User has DMs disabled, continue anyway
            pass
        
        # Attempt the kick
        try:
            await target_member.kick(reason=f"Kicked by {ctx.author} | {reason}")
            kicked = True
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
            f"✅ **{target_member}** has been kicked.\n**Reason:** {reason}"
        )
        
        # Auto-delete confirmation after 3 seconds
        await asyncio.sleep(3)
        try:
            await confirm_msg.delete()
        except discord.Forbidden:
            pass
        
        # Log to log channel
        await self._log_kick(guild, ctx.author, target_member, reason)

    @commands.command(name="kick_info")
    @commands.guild_only()
    async def kick_info(self, ctx: commands.Context):
        """Show kick command info"""
        if not self._has_kick_permission(ctx.author):
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return
        
        embed = discord.Embed(
            title="📋 Kick Command Info",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(
            name="Usage",
            value="`!kick <user> [reason]`",
            inline=False
        )
        embed.add_field(
            name="Target Formats",
            value="• `@mention` - Mention the user\n• `user_id` - User's Discord ID\n• `username` - User's name or display name",
            inline=False
        )
        embed.add_field(
            name="Examples",
            value="`!kick @user Spamming`\n`!kick 123456789 Rule violation`\n`!kick John Inappropriate behavior`",
            inline=False
        )
        embed.add_field(
            name="Requirements",
            value="• You need **Kick Members** or **Ban Members** permission\n• Target must be below your role",
            inline=False
        )
        embed.set_footer(text="Sentinel Moderation System")
        
        await ctx.send(embed=embed, delete_after=15)
        
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

    async def _log_kick(self, guild: discord.Guild, moderator: discord.Member, 
                       target: discord.Member, reason: str):
        """Log kick action to log channel"""
        log_channel = guild.get_channel(LOG_CHANNEL_ID)
        if not log_channel:
            return
        
        embed = discord.Embed(
            title="🦶 User Kicked",
            color=discord.Color.orange(),
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
        
        print(f"[KICK] {target} | By: {moderator} | Reason: {reason}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Kick(bot))
