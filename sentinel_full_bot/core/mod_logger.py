import discord
from datetime import datetime

LOG_CHANNEL_ID = 1466641783105785886  # 🔴 FIXED LOG CHANNEL


class ModLogger:
    def __init__(self, bot: discord.Client):
        self.bot = bot

    async def log(
        self,
        guild: discord.Guild,
        action: str,
        actor,              # discord.Member | None
        target: str,
        reason: str,
        trust_before=None,
        trust_after=None,
        escalation_level: int = 0
    ):
        channel = guild.get_channel(LOG_CHANNEL_ID)
        if channel is None:
            return  # fail silently if channel missing

        embed = discord.Embed(
            title="🛡️ Moderation Log",
            color=discord.Color.red() if escalation_level else discord.Color.blurple(),
            timestamp=datetime.utcnow()
        )

        embed.add_field(name="Action", value=action, inline=True)
        embed.add_field(
            name="Actor",
            value=actor.mention if actor else "System",
            inline=True
        )
        embed.add_field(name="Target", value=target, inline=True)

        embed.add_field(
            name="Reason",
            value=reason or "No reason provided",
            inline=False
        )

        if trust_before is not None and trust_after is not None:
            embed.add_field(
                name="Trust",
                value=f"{trust_before} → {trust_after}",
                inline=True
            )

        if escalation_level:
            embed.add_field(
                name="Escalation Level",
                value=str(escalation_level),
                inline=True
            )

        embed.set_footer(text="Sentinel Moderation System")

        await channel.send(embed=embed)
