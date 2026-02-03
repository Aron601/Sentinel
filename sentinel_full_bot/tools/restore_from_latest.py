import os
import json
import asyncio
from pathlib import Path
from datetime import datetime
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# load config
import config
import argparse
import discord

DATA_DIR = Path(__file__).parent.parent / 'data'

# pick latest quarantine snapshot file
def latest_snapshot():
    files = list(DATA_DIR.glob('quarantine_*.json'))
    if not files:
        return None
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0]


async def fetch_snapshot_from_log(token: str, log_channel_id: int):
    """Log in briefly, scan the log channel for attachments named quarantine_*.json and download the newest."""
    intents = discord.Intents.default()
    intents.guilds = True
    intents.messages = True

    client = discord.Client(intents=intents)
    result = {"path": None}

    @client.event
    async def on_ready():
        try:
            channel = client.get_channel(log_channel_id)
            if not channel:
                print('Log channel not found on this bot.')
                await client.close()
                return

            async for message in channel.history(limit=200):
                for att in message.attachments:
                    if att.filename.startswith('quarantine_') and att.filename.endswith('.json'):
                        dest = DATA_DIR / att.filename
                        try:
                            await att.save(dest)
                            print('Downloaded snapshot from log channel:', dest)
                            result['path'] = dest
                            await client.close()
                            return
                        except Exception as e:
                            print('Failed to download attachment:', e)
                            continue

            await client.close()
        except Exception as e:
            print('Error while fetching from log channel:', e)
            await client.close()

    try:
        await client.start(token)
    except Exception:
        # client.start raises on close; swallow
        pass

    return Path(result['path']) if result['path'] else None


async def run_restore():
    snapshot_path = latest_snapshot()

    parser = argparse.ArgumentParser()
    parser.add_argument('--yes', action='store_true', help='Auto-confirm and run')
    args = parser.parse_args()

    token = getattr(config, 'TOKEN', None)
    if not token:
        print('No TOKEN found in config.py')
        return

    if not snapshot_path:
        print('No local snapshot found — attempting to fetch from mod log channel...')
        log_channel_id = getattr(config, 'LOG_CHANNEL_ID', None)
        if not log_channel_id:
            print('No LOG_CHANNEL_ID configured in config.py')
            return

        fetched = await fetch_snapshot_from_log(token, log_channel_id)
        if not fetched:
            print('No snapshot found in log channel.')
            return
        snapshot_path = fetched

    print('Using snapshot:', snapshot_path)

    try:
        data = json.loads(snapshot_path.read_text(encoding='utf-8'))
    except Exception as e:
        print('Failed to read snapshot:', e)
        return

    guild_id = data.get('guild_id')
    if not guild_id:
        print('Snapshot missing guild_id')
        return

    intents = discord.Intents.default()
    intents.guilds = True
    intents.members = True

    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        print('Logged in as', client.user)
        guild = client.get_guild(guild_id)
        if not guild:
            print(f'Bot is not in guild {guild_id}.')
            await client.close()
            return

        print('Restoring snapshot for guild:', guild.name, guild.id)

        restored = 0
        failed = 0

        # Restore member roles
        members = data.get('members', {})
        for member_id_str, removed_role_ids in members.items():
            try:
                member_id = int(member_id_str)
            except:
                continue
            try:
                member = guild.get_member(member_id) or await guild.fetch_member(member_id)
            except Exception as e:
                print('Failed to fetch member', member_id, e)
                failed += 1
                continue

            roles_to_add = [guild.get_role(rid) for rid in removed_role_ids if guild.get_role(rid)]
            if not roles_to_add:
                continue

            # add roles
            try:
                await member.add_roles(*roles_to_add, reason='One-off restore from snapshot')
                restored += 1
                print(f'Restored roles for member {member} ({member.id})')
            except Exception as e:
                print('Failed to add roles to', member, e)
                failed += 1

        # Restore channel permissions
        channel_perms = data.get('channel_permissions', {})
        perm_restored = 0
        perm_failed = 0
        for channel_id_str, perms in channel_perms.items():
            try:
                channel = guild.get_channel(int(channel_id_str))
            except Exception:
                continue
            if not channel:
                continue
            for perm in perms:
                target = None
                try:
                    if perm.get('type') == 'role':
                        target = guild.get_role(perm.get('id'))
                    else:
                        target = guild.get_member(perm.get('id'))
                except Exception:
                    target = None
                if not target:
                    continue
                try:
                    allow = discord.Permissions(perm.get('allow', 0))
                    deny = discord.Permissions(perm.get('deny', 0))
                    overwrite = discord.PermissionOverwrite.from_pair(allow, deny)
                    await channel.set_permissions(target, overwrite=overwrite, reason='One-off restore from snapshot')
                    perm_restored += 1
                except Exception as e:
                    perm_failed += 1
                    print('Failed to set permissions on', channel, 'for', target, e)

        print('Done. members restored:', restored, 'failed:', failed)
        print('channel perms restored:', perm_restored, 'failed:', perm_failed)

        # remove snapshot file after successful restore
        try:
            backup = snapshot_path.with_name(snapshot_path.stem + '_restored_' + datetime.utcnow().strftime('%Y%m%d%H%M%S') + snapshot_path.suffix)
            snapshot_path.rename(backup)
            print('Snapshot moved to', backup)
        except Exception as e:
            print('Failed to move snapshot file:', e)

        await client.close()

    # Warn about disconnecting any running bot
    print('WARNING: logging in with this token will disconnect any currently running bot using the same token.')
    # args already parsed above
    if not args.yes:
        confirm = input('Proceed? (yes/no): ').strip().lower()
        if confirm != 'yes':
            print('Aborting')
            return

    await client.start(token)

if __name__ == '__main__':
    asyncio.run(run_restore())
