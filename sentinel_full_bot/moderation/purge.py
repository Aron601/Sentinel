import discord
from discord.ext import commands
from discord import ui
from datetime import datetime, timedelta
import asyncio
import os
from core.server_logging import mark_deletion_as_purge

LOG_CHANNEL_ID = 1466641783105785886

# Data directory for purge logs
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)


class PurgeConfirmView(ui.View):
    def __init__(self, timeout=60):
        super().__init__(timeout=timeout)
        self.confirmed = False

    @ui.button(label="Confirm Purge", style=discord.ButtonStyle.red, emoji="🧹")
    async def confirm_button(self, interaction: discord.Interaction, button: ui.Button):
        self.confirmed = True
        await interaction.response.defer()
        self.stop()

    @ui.button(label="Cancel", style=discord.ButtonStyle.gray, emoji="❌")
    async def cancel_button(self, interaction: discord.Interaction, button: ui.Button):
        self.confirmed = False
        await interaction.response.defer()
        self.stop()


class Purge(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.purge_cooldowns = {}  # Track cooldowns: {user_id: datetime}

    def _is_admin(self, member: discord.Member) -> bool:
        """Check if member is admin"""
        return member.guild_permissions.administrator

    def _is_staff(self, member: discord.Member) -> bool:
        """Check if member has manage_messages permission"""
        return member.guild_permissions.manage_messages

    def _check_cooldown(self, user_id: int) -> tuple[bool, float]:
        """Check if user is on cooldown. Returns (is_cooled_down, time_remaining)"""
        if user_id not in self.purge_cooldowns:
            return False, 0

        cooldown_end = self.purge_cooldowns[user_id]
        now = datetime.utcnow()

        if now < cooldown_end:
            remaining = (cooldown_end - now).total_seconds()
            return True, remaining
        else:
            del self.purge_cooldowns[user_id]
            return False, 0

    def _set_cooldown(self, user_id: int, seconds: int = 60):
        """Set cooldown for user"""
        self.purge_cooldowns[user_id] = datetime.utcnow() + timedelta(seconds=seconds)

    def _save_purge_log(self, guild_id: int, channel_name: str, moderator: str, messages: list) -> str:
        """Save purged messages to a txt file. Returns filename."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"purge_{guild_id}_{channel_name}_{timestamp}.txt"
        filepath = os.path.join(DATA_DIR, filename)

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"PURGE LOG - {datetime.utcnow().isoformat()}\n")
                f.write(f"Guild ID: {guild_id}\n")
                f.write(f"Channel: {channel_name}\n")
                f.write(f"Moderator: {moderator}\n")
                f.write(f"Total Messages: {len(messages)}\n")
                f.write("=" * 80 + "\n\n")

                for msg in messages:
                    f.write(f"[{msg.created_at.isoformat()}] {msg.author} ({msg.author.id}):\n")
                    f.write(f"{msg.content}\n")
                    if msg.attachments:
                        f.write(f"Attachments: {', '.join([a.filename for a in msg.attachments])}\n")
                    f.write("-" * 80 + "\n")

            return filename
        except Exception as e:
            print(f"[PURGE ERROR] Failed to save log: {e}")
            return None

    @commands.command(name="purge")
    async def purge(self, ctx: commands.Context, amount: int):
        # 🔇 Silent permission check - only staff can use
        if not self._is_staff(ctx.author):
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return

        # Validate amount
        if amount < 1:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return

        # 🔄 Cooldown check (no cooldown for admins)
        if not self._is_admin(ctx.author):
            is_cooled, remaining = self._check_cooldown(ctx.author.id)
            if is_cooled:
                try:
                    await ctx.message.delete()
                except discord.Forbidden:
                    pass
                return

        # ⚠️ Confirmation for large purges (> 100 messages)
        if amount > 100:
            view = PurgeConfirmView()
            confirm_msg = await ctx.send(
                f"⚠️ **Confirm purge of {amount} messages?**\n"
                f"Moderator: {ctx.author.mention}",
                view=view
            )

            await view.wait()

            if not view.confirmed:
                try:
                    await confirm_msg.delete()
                except discord.Forbidden:
                    pass
                try:
                    await ctx.message.delete()
                except discord.Forbidden:
                    pass
                return

            try:
                await confirm_msg.delete()
            except discord.Forbidden:
                pass

        # Cap at 1000 messages
        if amount > 1000:
            amount = 1000

        # 🧹 Delete command message FIRST
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

        # ⏱️ Small yield to avoid race condition
        await asyncio.sleep(0.05)

        try:
            deleted = await ctx.channel.purge(
                limit=amount,
                bulk=True
            )
        except (discord.Forbidden, discord.HTTPException):
            return
        
        # Mark all deleted messages as purge operations
        for message in deleted:
            mark_deletion_as_purge(message.id)

        # ✅ SINGLE, CORRECT RESPONSE
        msg = await ctx.channel.send(
            f"🧹 Deleted **{len(deleted)}** messages."
        )

        # Auto-delete confirmation
        await asyncio.sleep(2.5)
        try:
            await msg.delete()
        except discord.Forbidden:
            pass

        # 🔄 Set cooldown for non-admins
        if not self._is_admin(ctx.author):
            self._set_cooldown(ctx.author.id, 60)

        # 🧾 Log async
        asyncio.create_task(
            self._log_purge(
                ctx.guild,
                ctx.author,
                ctx.channel,
                deleted
            )
        )

    async def _log_purge(self, guild, moderator, channel, messages):
        """Log purge to channel and save messages to file"""
        count = len(messages)
        file_saved = None

        # Save messages to txt if more than 20
        if count >= 20:
            file_saved = self._save_purge_log(
                guild.id,
                channel.name,
                str(moderator),
                messages
            )

        log_channel = guild.get_channel(LOG_CHANNEL_ID)
        if not log_channel:
            return

        embed = discord.Embed(
            title="🧹 Purge Executed",
            color=discord.Color.orange(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Moderator", value=str(moderator), inline=True)
        embed.add_field(name="Admin", value="Yes" if self._is_admin(moderator) else "No", inline=True)
        embed.add_field(name="Channel", value=channel.mention, inline=True)
        embed.add_field(name="Deleted", value=str(count), inline=True)

        if file_saved:
            embed.add_field(name="Log File", value=f"`{file_saved}`", inline=False)

        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            pass
