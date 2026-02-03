import discord
from discord.ext import commands
from datetime import datetime
import asyncio

LOG_CHANNEL_ID = 1466641783105785886


class Ban(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _has_ban_permission(self, member: discord.Member) -> bool:
        """Check if member can ban"""
        return member.guild_permissions.ban_members

    @commands.command(name="ban")
    @commands.guild_only()
    async def ban(
        self,
        ctx: commands.Context,
        target: str,
        *,
        reason: str = "No reason provided"
    ):
        """
        Ban a user by mention, name, or ID
        Usage: !ban @user [reason]
               !ban user_id [reason]
               !ban username [reason]
        """
        
        # 🔇 Silent permission check
        if not self._has_ban_permission(ctx.author):
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return

        guild = ctx.guild
        
        # Try to resolve the target
        target_member = None
        target_user = None
        
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
                    # User might not be in guild, but we can still ban by ID
                    target_user = await self.bot.fetch_user(user_id)
            except (ValueError, discord.NotFound):
                pass
        
        # 3. Try as username/display name
        if not target_member and not target_user:
            for member in guild.members:
                if member.name.lower() == target.lower() or member.display_name.lower() == target.lower():
                    target_member = member
                    break
        
        # 4. Try fuzzy search (partial match)
        if not target_member and not target_user:
            target_lower = target.lower()
            for member in guild.members:
                if target_lower in member.name.lower() or target_lower in member.display_name.lower():
                    target_member = member
                    break
        
        # No target found
        if not target_member and not target_user:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return
        
        # Get the actual target (prefer member)
        target = target_member or target_user
        
        # Can't ban self
        if target.id == ctx.author.id:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return
        
        # Can't ban the owner
        if target.id == 814466767598256150:  # Owner ID
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return
        
        # Can't ban bot
        if target.bot:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return
        
        # Can't ban higher role (only check if member in guild)
        if target_member and target_member.top_role >= ctx.author.top_role and ctx.author.id != guild.owner_id:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return
        
        # Verify bot has permissions
        if not guild.me.guild_permissions.ban_members:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return
        
        # Send DM to banned user
        try:
            embed = discord.Embed(
                title="🚫 You have been banned",
                color=discord.Color.dark_red(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Server", value=guild.name, inline=False)
            embed.add_field(name="Moderator", value=str(ctx.author), inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.set_footer(text="Sentinel Moderation System")
            
            await target.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            # User has DMs disabled, continue anyway
            pass
        
        # Attempt the ban
        try:
            await guild.ban(target, reason=f"Banned by {ctx.author} | {reason}", delete_message_days=0)
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
            f"✅ **{target}** has been banned.\n**Reason:** {reason}"
        )
        
        # Auto-delete confirmation after 3 seconds
        await asyncio.sleep(3)
        try:
            await confirm_msg.delete()
        except discord.Forbidden:
            pass
        
        # Log to log channel
        await self._log_ban(guild, ctx.author, target, reason)

    @commands.command(name="unban")
    @commands.guild_only()
    async def unban(
        self,
        ctx: commands.Context,
        user_id: str,
        *,
        reason: str = "No reason provided"
    ):
        """
        Unban a user by ID
        Usage: !unban user_id [reason]
        """
        
        # 🔇 Silent permission check
        if not self._has_ban_permission(ctx.author):
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return

        guild = ctx.guild
        
        # Parse user ID
        try:
            user_id = int(user_id)
        except ValueError:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return
        
        # Try to fetch the user
        try:
            user = await self.bot.fetch_user(user_id)
        except discord.NotFound:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return
        
        # Attempt the unban
        try:
            await guild.unban(user, reason=f"Unbanned by {ctx.author} | {reason}")
        except discord.Forbidden:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return
        except discord.NotFound:
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
            f"✅ **{user}** has been unbanned.\n**Reason:** {reason}"
        )
        
        # Auto-delete confirmation after 3 seconds
        await asyncio.sleep(3)
        try:
            await confirm_msg.delete()
        except discord.Forbidden:
            pass
        
        # Log to log channel
        await self._log_unban(guild, ctx.author, user, reason)

    @commands.command(name="ban_info")
    @commands.guild_only()
    async def ban_info(self, ctx: commands.Context):
        """Show ban command info"""
        if not self._has_ban_permission(ctx.author):
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return
        
        embed = discord.Embed(
            title="📋 Ban Command Info",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(
            name="Ban Usage",
            value="`!ban <user> [reason]`",
            inline=False
        )
        embed.add_field(
            name="Ban Target Formats",
            value="• `@mention` - Mention the user\n• `user_id` - User's Discord ID\n• `username` - User's name or display name",
            inline=False
        )
        embed.add_field(
            name="Ban Examples",
            value="`!ban @user Spamming`\n`!ban 123456789 Rule violation`\n`!ban John Inappropriate behavior`",
            inline=False
        )
        embed.add_field(
            name="Unban Usage",
            value="`!unban <user_id> [reason]`",
            inline=False
        )
        embed.add_field(
            name="Unban Example",
            value="`!unban 123456789 Appeal accepted`",
            inline=False
        )
        embed.add_field(
            name="Requirements",
            value="• You need **Ban Members** permission\n• Target must be below your role",
            inline=False
        )
        embed.set_footer(text="Sentinel Moderation System")
        
        await ctx.send(embed=embed, delete_after=15)
        
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

    async def _log_ban(self, guild: discord.Guild, moderator: discord.Member, 
                      target: discord.User, reason: str):
        """Log ban action to log channel"""
        log_channel = guild.get_channel(LOG_CHANNEL_ID)
        if not log_channel:
            return
        
        embed = discord.Embed(
            title="🚫 User Banned",
            color=discord.Color.dark_red(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="User", value=f"{target.mention} ({target})" if isinstance(target, discord.Member) else f"{target} (ID: {target.id})", inline=False)
        embed.add_field(name="Moderator", value=f"{moderator.mention} ({moderator})", inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text="Sentinel Moderation System")
        
        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            pass
        
        print(f"[BAN] {target} | By: {moderator} | Reason: {reason}")

    async def _log_unban(self, guild: discord.Guild, moderator: discord.Member, 
                        user: discord.User, reason: str):
        """Log unban action to log channel"""
        log_channel = guild.get_channel(LOG_CHANNEL_ID)
        if not log_channel:
            return
        
        embed = discord.Embed(
            title="✅ User Unbanned",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="User", value=f"{user} (ID: {user.id})", inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text="Sentinel Moderation System")
        
        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            pass
        
        print(f"[UNBAN] {user} | By: {moderator} | Reason: {reason}")

async def setup(bot: commands.Bot):
    await bot.add_cog(Ban(bot))