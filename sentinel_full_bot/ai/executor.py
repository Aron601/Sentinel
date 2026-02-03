import discord

async def apply_actions(guild: discord.Guild, plan: dict):
    for step in plan.get("actions", []):
        action = step["action"]
        target = step["target"]
        reason = step.get("reason", "AI audit fix")

        if action == "restrict_channel":
            cat = discord.utils.get(guild.categories, name=target)
            if cat:
                for role_name in ("@everyone", "Member", "VIP"):
                    role = discord.utils.get(guild.roles, name=role_name)
                    if role:
                        await cat.set_permissions(
                            role,
                            view_channel=False,
                            reason=reason
                        )

        elif action == "enforce_muted":
            role = discord.utils.get(guild.roles, name="Muted")
            if role:
                for ch in guild.text_channels:
                    await ch.set_permissions(
                        role,
                        send_messages=False,
                        add_reactions=False,
                        reason=reason
                    )

        elif action == "fix_readonly":
            ch = discord.utils.get(guild.channels, name=target)
            if ch:
                await ch.set_permissions(
                    guild.default_role,
                    send_messages=False,
                    reason=reason
                )

        elif action == "sync_category":
            cat = discord.utils.get(guild.categories, name=target)
            if cat:
                for ch in cat.channels:
                    await ch.edit(sync_permissions=True)
