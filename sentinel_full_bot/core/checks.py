from database.db import fetch_user

async def has_power(actor_id, target_id):
    actor = await fetch_user(actor_id)
    target = await fetch_user(target_id)
    return actor["power"] > target["power"]
