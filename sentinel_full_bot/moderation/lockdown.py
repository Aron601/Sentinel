import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
from typing import Literal, Optional
import asyncio

# 🔴 MUST MATCH main.py EXACTLY
GUILD_ID = 969259122409218118

class Lockdown(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.lockdown_timers = {}  # Store timed lockdowns

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(
        name="lockdown",
        description="Lock or unlock the server with a reason"
    )
    @app_commands.describe(
        mode="on = lock server, off = unlock server",
        reason="Reason for lockdown or unlock",
        duration="Duration in minutes (optional, auto-unlock after timeout)",
        include_voice="Lock voice channels too"
    )
    async def Lockdown(
        self,
        interaction: discord.Interaction,
        mode: Literal["on", "off"],
        reason: str,
        duration: Optional[int] = None,
        include_voice: bool = False
    ):

        guild = interaction.guild
        await interaction.response.defer(thinking=True)

        # Check permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send(
                "❌ You need Administrator permissions to use this command.",
                ephemeral=True
            )
            return

        locked_count = 0
        failed_count = 0

        # 🔒 Lock / unlock all text channels
        for channel in guild.text_channels:
            try:
                overwrite = channel.overwrites_for(guild.default_role)
                overwrite.send_messages = False if mode == "on" else None

                await channel.set_permissions(
                    guild.default_role,
                    overwrite=overwrite,
                    reason=f"Lockdown {mode.upper()} by {interaction.user} | {reason}"
                )
                locked_count += 1
            except discord.Forbidden:
                failed_count += 1
                continue

        # 🔊 Lock voice channels if enabled
        voice_count = 0
        if include_voice:
            for channel in guild.voice_channels:
                try:
                    overwrite = channel.overwrites_for(guild.default_role)
                    overwrite.connect = False if mode == "on" else None

                    await channel.set_permissions(
                        guild.default_role,
                        overwrite=overwrite,
                        reason=f"Lockdown {mode.upper()} by {interaction.user} | {reason}"
                    )
                    voice_count += 1
                except discord.Forbidden:
                    failed_count += 1
                    continue

        # 📢 Embed announcement
        embed = discord.Embed(
            title="🔒 SERVER LOCKDOWN" if mode == "on" else "🔓 LOCKDOWN LIFTED",
            color=discord.Color.red() if mode == "on" else discord.Color.green(),
            timestamp=datetime.utcnow()
        )

        embed.add_field(name="Action", value=mode.upper(), inline=True)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        
        if duration:
            embed.add_field(name="Duration", value=f"{duration} minutes", inline=True)
        
        if include_voice:
            embed.add_field(name="Channels Locked", value=f"Text: {locked_count} | Voice: {voice_count}", inline=False)
        else:
            embed.add_field(name="Channels Locked", value=f"{locked_count}", inline=False)
        
        embed.set_footer(text="Sentinel Security System")

        # Send to #general if exists, else current channel
        general = discord.utils.get(guild.text_channels, name="general")
        announcement = await (general or interaction.channel).send(embed=embed)

        # 🖨️ Console log (DB-ready)
        print(
            f"[LOCKDOWN] {guild.name} | "
            f"{mode.upper()} | "
            f"By: {interaction.user} | "
            f"Reason: {reason} | "
            f"Channels: {locked_count} | "
            f"Voice: {voice_count}"
        )

        # 📋 Status message
        status_msg = f"✅ Lockdown {mode.upper()} executed.\n📊 Text channels: {locked_count}"
        if include_voice:
            status_msg += f"\n🔊 Voice channels: {voice_count}"
        if failed_count > 0:
            status_msg += f"\n⚠️ Failed: {failed_count}"

        await interaction.followup.send(status_msg, ephemeral=True)

        # ⏰ Auto-unlock timer
        if mode == "on" and duration:
            self.lockdown_timers[guild.id] = {
                "announced": False,
                "announcement_msg": announcement
            }
            asyncio.create_task(self._auto_unlock(guild, reason, duration))

    async def _auto_unlock(self, guild: discord.Guild, reason: str, duration: int):
        """Auto-unlock server after specified duration"""
        try:
            await asyncio.sleep(duration * 60)
            
            # Unlock all channels
            unlocked = 0
            for channel in guild.text_channels:
                try:
                    overwrite = channel.overwrites_for(guild.default_role)
                    overwrite.send_messages = None
                    await channel.set_permissions(
                        guild.default_role,
                        overwrite=overwrite,
                        reason=f"Auto-unlock after {duration} minutes (Lockdown reason: {reason})"
                    )
                    unlocked += 1
                except discord.Forbidden:
                    continue

            # Send notification
            general = discord.utils.get(guild.text_channels, name="general")
            embed = discord.Embed(
                title="🔓 AUTOMATIC LOCKDOWN LIFT",
                description=f"Lockdown has been automatically lifted after {duration} minutes.",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Original Reason", value=reason, inline=False)
            embed.add_field(name="Channels Unlocked", value=str(unlocked), inline=True)
            embed.set_footer(text="Sentinel Security System")
            
            if general:
                await general.send(embed=embed)
            
            print(f"[LOCKDOWN] Auto-unlock executed for {guild.name} | Channels unlocked: {unlocked}")
            
            # Clean up timer
            if guild.id in self.lockdown_timers:
                del self.lockdown_timers[guild.id]
        except Exception as e:
            print(f"[LOCKDOWN ERROR] Auto-unlock failed: {e}")

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(
        name="lockdown_status",
        description="Check current lockdown status"
    )
    async def lockdown_status(self, interaction: discord.Interaction):
        """Check if server is currently locked"""
        guild = interaction.guild
        await interaction.response.defer(thinking=True)

        locked_channels = []
        unlocked_channels = []

        for channel in guild.text_channels:
            overwrite = channel.overwrites_for(guild.default_role)
            if overwrite.send_messages is False:
                locked_channels.append(channel.name)
            else:
                unlocked_channels.append(channel.name)

        embed = discord.Embed(
            title="📊 Lockdown Status",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )

        embed.add_field(name="🔒 Locked Channels", value=f"{len(locked_channels)}", inline=True)
        embed.add_field(name="🔓 Unlocked Channels", value=f"{len(unlocked_channels)}", inline=True)
        
        if locked_channels and len(locked_channels) <= 10:
            embed.add_field(name="Locked List", value=", ".join(locked_channels), inline=False)
        
        is_locked = len(locked_channels) > 0
        embed.add_field(
            name="Status",
            value="🔒 SERVER IS LOCKED" if is_locked else "🔓 Server is unlocked",
            inline=False
        )
        
        embed.set_footer(text="Sentinel Security System")

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(
        name="lockdown_emergency",
        description="Emergency lockdown - locks everything immediately"
    )
    @app_commands.describe(
        reason="Reason for emergency lockdown"
    )
    async def emergency_lockdown(
        self,
        interaction: discord.Interaction,
        reason: str
    ):
        """Instant emergency lockdown with voice channel lock"""
        guild = interaction.guild
        await interaction.response.defer(thinking=True)

        # Check permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send(
                "❌ You need Administrator permissions.",
                ephemeral=True
            )
            return

        locked_count = 0

        # Lock everything
        for channel in guild.channels:
            try:
                overwrite = channel.overwrites_for(guild.default_role)
                if isinstance(channel, discord.TextChannel):
                    overwrite.send_messages = False
                elif isinstance(channel, discord.VoiceChannel):
                    overwrite.connect = False
                
                await channel.set_permissions(
                    guild.default_role,
                    overwrite=overwrite,
                    reason=f"EMERGENCY LOCKDOWN by {interaction.user} | {reason}"
                )
                locked_count += 1
            except discord.Forbidden:
                continue

        # Alert embed
        embed = discord.Embed(
            title="🚨 EMERGENCY LOCKDOWN ACTIVATED",
            description=reason,
            color=discord.Color.dark_red(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        embed.add_field(name="Channels Locked", value=str(locked_count), inline=True)
        embed.set_footer(text="Sentinel Security System")

        general = discord.utils.get(guild.text_channels, name="general")
        await (general or interaction.channel).send(embed=embed)

        print(f"[EMERGENCY LOCKDOWN] {guild.name} | By: {interaction.user} | Reason: {reason} | Channels: {locked_count}")

        await interaction.followup.send(f"🚨 Emergency lockdown activated! {locked_count} channels locked.", ephemeral=True)
