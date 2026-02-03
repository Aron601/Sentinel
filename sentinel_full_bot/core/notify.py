import discord
from datetime import datetime

async def notify_user(
    *,
    bot,
    guild: discord.Guild,
    member: discord.Member,
    action: str,
    reason: str,
    actor_trust_before=None,
    actor_trust_after=None,
    escalation_level: int = 0
) -> bool:
    """
    Sends a DM to the affected user and logs the result.
    Moderator identity is NEVER shown to the user.
    """

    # -------------------------
    # BUILD DM EMBED
    # -------------------------
    embed = discord.Embed(
        title=f"🚨 You were {action}",
        color=discord.Color.red(),
        timestamp=datetime.utcnow()
    )

    embed.add_field(
        name="Server",
        value=guild.name,
        inline=False
    )

    embed.add_field(
        name="Reason",
        value=reason if reason else "No reason provided",
        inline=False
    )

    embed.add_field(
        name="Notice",
        value=(
            "This action was taken by the server moderation system.\n"
            "Moderator identities are kept private."
        ),
        inline=False
    )

    embed.set_footer(text="Sentinel Moderation System")

    # -------------------------
    # SEND DM
    # -------------------------
    dm_sent = False
    dm_error = None

    try:
        await member.send(embed=embed)
        dm_sent = True
    except discord.Forbidden:
        dm_error = "DMs closed"
    except Exception as e:
        dm_error = str(e)

    # -------------------------
    # LOG NOTIFICATION RESULT
    # -------------------------
    logger = getattr(bot, "mod_logger", None)
    if logger:
        await logger.log(
            guild=guild,
            action=f"{action.upper()} — USER NOTIFICATION",
            actor=None,  # system-level
            target=str(member),
            reason=(
                f"{reason}\n\n"
                f"DM Status: {'Sent' if dm_sent else 'Failed'}"
                + (f" ({dm_error})" if dm_error else "")
            ),
            trust_before=actor_trust_before,
            trust_after=actor_trust_after,
            escalation_level=escalation_level
        )

    return dm_sent
