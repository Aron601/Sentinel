def snapshot_guild(guild):
    data = {
        "roles": [],
        "channels": []
    }

    for r in guild.roles:
        data["roles"].append({
            "name": r.name,
            "position": r.position,
            "permissions": r.permissions.value
        })

    for ch in guild.channels:
        overwrites = []
        for target, perm in ch.overwrites.items():
            overwrites.append({
                "target": getattr(target, "name", "unknown"),
                "allow": perm.pair()[0].value,
                "deny": perm.pair()[1].value
            })

        data["channels"].append({
            "name": ch.name,
            "type": ch.__class__.__name__,
            "category": ch.category.name if ch.category else None,
            "overwrites": overwrites
        })

    return data
