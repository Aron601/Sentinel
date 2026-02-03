import discord
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
import asyncio

from utils.modlog import log_action
from core.server_logging import mark_deletion_as_spam


# 🔧 SPAM CONFIG
SPAM_LIMIT = 5           # messages
SPAM_INTERVAL = 5        # seconds
AUTO_PURGE_LIMIT = 20
TIMEOUT_MINUTES = 5

# 🧾 LOG CHANNEL
AUTO_PURGE_LOG_CHANNEL_ID = 1466641783105785886


def is_staff(member: discord.Member) -> bool:
    perms = member.guild_permissions
    return (
        perms.administrator
        or perms.manage_messages
        or perms.ban_members
        or perms.kick_members
        or perms.moderate_members
    )


class SpamHandler:
    def __init__(self):
        # user_id -> deque[timestamps]
        self.user_messages: dict[int, deque[float]] = defaultdict(deque)

    async def handle_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        if not isinstance(message.author, discord.Member):
            return

        # 🚫 Ignore staff completely
        if is_staff(message.author):
            return

        now = time.monotonic()  # faster & safer than time.time()
        user_id = message.author.id
        timestamps = self.user_messages[user_id]

        # ⏱️ Remove old timestamps (O(1) amortized)
        while timestamps and now - timestamps[0] > SPAM_INTERVAL:
            timestamps.popleft()

        timestamps.append(now)

        # 🚨 Spam detected
        if len(timestamps) >= SPAM_LIMIT:
            timestamps.clear()
            # Fire-and-forget async spam handler for minimum latency
            asyncio.create_task(self._handle_spam(message))

    async def _handle_spam(self, message: discord.Message):
        """Handle spam with parallel execution for minimum latency"""
        guild = message.guild
        channel = message.channel
        member = message.author

        # ⚡ Execute all operations in parallel
        purge_task = asyncio.create_task(self._purge_messages(channel, member))
        timeout_task = asyncio.create_task(self._timeout_member(member))
        log_task = asyncio.create_task(self._log_spam_action(guild, channel, member))

        # Wait for critical operations only
        deleted_count, timeout_result = await asyncio.gather(
            purge_task,
            timeout_task,
            return_exceptions=True
        )

        # Log asynchronously without blocking
        asyncio.create_task(log_task)

        # 🖨️ Console log
        print(
            f"[AUTO-SPAM] {member} | "
            f"Purged {deleted_count} msgs | "
            f"Timeout {TIMEOUT_MINUTES}m | "
            f"#{channel.name}"
        )

    async def _purge_messages(self, channel: discord.TextChannel, member: discord.Member) -> int:
        """Purge spam messages with minimal latency"""
        try:
            deleted = await channel.purge(
                limit=AUTO_PURGE_LIMIT,
                check=lambda m: m.author.id == member.id
            )
            # Mark all deleted messages as spam operations
            for message in deleted:
                mark_deletion_as_spam(message.id)
            return len(deleted)
        except (discord.Forbidden, discord.HTTPException):
            return 0

    async def _timeout_member(self, member: discord.Member) -> bool:
        """Timeout member with minimal latency"""
        try:
            until = discord.utils.utcnow() + timedelta(minutes=TIMEOUT_MINUTES)
            await member.timeout(
                until,
                reason="Automatic spam detection"
            )
            return True
        except (discord.Forbidden, discord.HTTPException):
            return False

    async def _log_spam_action(self, guild: discord.Guild, channel: discord.TextChannel, member: discord.Member):
        """Log spam action (non-blocking)"""
        try:
            # Try to get deletion count quickly
            deleted_count = 0
            
            # Log to database
            try:
                log_action(
                    action="AUTO_SPAM",
                    target_id=member.id,
                    moderator="SYSTEM",
                    reason="Automatic spam detection",
                    extra={
                        "purged": deleted_count,
                        "timeout_minutes": TIMEOUT_MINUTES,
                        "channel": channel.name
                    }
                )
            except Exception:
                pass

            # Log to Discord channel
            log_channel = guild.get_channel(AUTO_PURGE_LOG_CHANNEL_ID)
            if log_channel:
                embed = discord.Embed(
                    title="🚨 Auto Spam Action",
                    color=discord.Color.red(),
                    timestamp=datetime.utcnow()
                )

                embed.add_field(
                    name="User",
                    value=f"{member} ({member.id})",
                    inline=False
                )
                embed.add_field(
                    name="Channel",
                    value=channel.mention,
                    inline=True
                )
                embed.add_field(
                    name="Timeout",
                    value=f"{TIMEOUT_MINUTES} minutes",
                    inline=True
                )

                embed.set_footer(text="Sentinel Auto-Moderation")

                try:
                    await log_channel.send(embed=embed)
                except discord.Forbidden:
                    pass

        except Exception as e:
            print(f"[SPAM LOG ERROR] {e}")
