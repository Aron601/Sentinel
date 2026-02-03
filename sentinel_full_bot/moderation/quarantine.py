import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import json
import os
import asyncio

# 🔴 MUST MATCH main.py
GUILD_ID = 969259122409218118
OWNER_ID = 814466767598256150

LOG_CHANNEL_ID = 1466641783105785886

QUARANTINE_ROLE_NAME = "Quarantined"
NOTICE_CHANNEL_NAME = "server-quarantine"

# 📁 Stable data directory (absolute)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)


def snapshot_path(guild_id: int) -> str:
    return os.path.join(DATA_DIR, f"quarantine_{guild_id}.json")


def is_owner(user: discord.User) -> bool:
    return user.id == OWNER_ID


class Quarantine(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _can_use_quarantine(self, member: discord.Member) -> bool:
        """Check if member is owner or admin"""
        return is_owner(member) or member.guild_permissions.administrator

    async def _delete_all_invites(self, guild: discord.Guild) -> int:
        """Delete all server invites"""
        deleted_count = 0
        try:
            invites = await guild.invites()
            for invite in invites:
                try:
                    await invite.delete(reason="Quarantine: Delete all invites")
                    deleted_count += 1
                except discord.Forbidden:
                    continue
        except discord.Forbidden:
            pass
        return deleted_count

    # ======================================================
    # 🔒 QUARANTINE
    # ======================================================
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(
        name="quarantine",
        description="ADMIN/OWNER ONLY: Remove all roles and quarantine the server"
    )
    @app_commands.describe(reason="Reason for quarantine")
    async def quarantine(self, interaction: discord.Interaction, reason: str):
        if not self._can_use_quarantine(interaction.user):
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="You need **Administrator** permission or be the **Owner** to use this command.",
                color=discord.Color.red(),
                timestamp=datetime.utcnow()
            )
            embed.set_footer(text="Sentinel Security System")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer(thinking=True)
        guild = interaction.guild

        # Verify quarantine role exists or create it
        quarantine_role = discord.utils.get(guild.roles, name=QUARANTINE_ROLE_NAME)
        if not quarantine_role:
            try:
                quarantine_role = await guild.create_role(
                    name=QUARANTINE_ROLE_NAME,
                    color=discord.Color.red(),
                    reason="Quarantine system role"
                )
            except discord.Forbidden:
                error_embed = discord.Embed(
                    title="❌ Error",
                    description=f"Could not create role `{QUARANTINE_ROLE_NAME}`. Bot lacks permissions.",
                    color=discord.Color.red(),
                    timestamp=datetime.utcnow()
                )
                error_embed.set_footer(text="Sentinel Security System")
                await interaction.edit_original_response(embed=error_embed)
                return

        # 🧠 Snapshot: record removed staff roles per member and existing channel overwrites
        snapshot = {
            "guild_id": guild.id,
            "timestamp": datetime.utcnow().isoformat(),
            "reason": reason,
            "quarantined_by": str(interaction.user),
            "members": {},  # member_id -> removed_role_ids
            "channel_permissions": {}
        }

        removed_roles_total = 0
        skipped_count = 0

        # Identify staff roles (roles that grant moderation/administration powers)
        staff_role_ids = set()
        for role in guild.roles:
            perms = role.permissions
            if perms.administrator or perms.manage_guild or perms.moderate_members or perms.manage_messages or perms.kick_members or perms.ban_members or perms.manage_roles:
                staff_role_ids.add(role.id)

        # Remove staff roles from members and snapshot removed role ids
        for member in guild.members:
            if member.bot:
                continue

            removed = [role.id for role in member.roles if role.id in staff_role_ids]
            if not removed:
                continue

            snapshot["members"][str(member.id)] = removed
            try:
                new_roles = [r for r in member.roles if r.id not in staff_role_ids]
                await member.edit(
                    roles=new_roles,
                    reason=f"SERVER QUARANTINE (remove staff roles): {reason}"
                )
                removed_roles_total += len(removed)
            except discord.Forbidden:
                skipped_count += 1
                continue

        # 📋 Snapshot channel permissions for restoration, then deny view for @everyone
        for channel in guild.channels:
            try:
                perms = []
                for target, overwrite in channel.overwrites.items():
                    try:
                        perms.append({
                            "id": target.id,
                            "type": "role" if isinstance(target, discord.Role) else "member",
                            "allow": overwrite.pair()[0].value,
                            "deny": overwrite.pair()[1].value
                        })
                    except Exception:
                        continue
                snapshot["channel_permissions"][str(channel.id)] = perms

                # Apply deny view_channel to @everyone as the quarantine exception
                try:
                    await channel.set_permissions(
                        guild.default_role,
                        overwrite=discord.PermissionOverwrite(view_channel=False),
                        reason="Quarantine: Deny view to Member role"
                    )
                except discord.Forbidden:
                    # Skip channels where we lack permission
                    continue
            except Exception:
                continue

        # Save snapshot
        path = snapshot_path(guild.id)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, indent=2)
        except Exception as e:
            print(f"[QUARANTINE ERROR] Failed to save snapshot: {e}")

        # 🗑️ Delete all server invites
        deleted_invites = await self._delete_all_invites(guild)

        # 📢 Notice channel (safe)
        notice = discord.utils.get(guild.text_channels, name=NOTICE_CHANNEL_NAME)

        if not notice:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(
                    view_channel=True,
                    read_message_history=True,
                    send_messages=False,
                    add_reactions=False
                )
            }

            try:
                notice = await guild.create_text_channel(
                    name=NOTICE_CHANNEL_NAME,
                    overwrites=overwrites,
                    reason="Quarantine notice channel"
                )
            except discord.Forbidden:
                pass

        if notice:
            embed = discord.Embed(
                title="🚨 Server Quarantined",
                description=(
                    "**This server is temporarily locked.**\n\n"
                    f"**Reason:** {reason}\n\n"
                    "All member roles have been removed.\n"
                    "Please wait for restoration by the owner."
                ),
                color=discord.Color.red(),
                timestamp=datetime.utcnow()
            )
            embed.set_footer(text="Sentinel Security System")

            try:
                await notice.send(embed=embed)
            except discord.Forbidden:
                pass

        # 📜 Log with embed
        log_channel = guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            log_embed = discord.Embed(
                title="🚨 Server Quarantine Activated",
                color=discord.Color.dark_red(),
                timestamp=datetime.utcnow()
            )
            log_embed.add_field(name="Guild", value=f"{guild.name} ({guild.id})", inline=False)
            log_embed.add_field(name="Quarantined By", value=f"{interaction.user.mention} ({interaction.user})", inline=True)
            log_embed.add_field(name="Reason", value=reason, inline=False)
            log_embed.add_field(name="Staff Roles Removed (total)", value=str(removed_roles_total), inline=True)
            log_embed.add_field(name="Skipped (No Perms)", value=str(skipped_count), inline=True)
            log_embed.add_field(name="Invites Deleted", value=str(deleted_invites), inline=True)
            log_embed.add_field(name="Snapshot File", value=f"quarantine_{guild.id}.json", inline=True)
            log_embed.set_footer(text="Sentinel Security System")

            try:
                await log_channel.send(
                    embed=log_embed,
                    file=discord.File(path, filename=f"quarantine_{guild.id}.json")
                )
            except Exception as e:
                print(f"[QUARANTINE ERROR] Failed to send log: {e}")

        # ✅ Confirmation embed
        confirm_embed = discord.Embed(
            title="✅ Server Quarantine Successful",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        confirm_embed.add_field(name="Staff Roles Removed (total)", value=str(removed_roles_total), inline=True)
        confirm_embed.add_field(name="Invites Deleted", value=str(deleted_invites), inline=True)
        confirm_embed.add_field(name="Status", value="🔒 Server is locked (Member view denied)", inline=False)
        confirm_embed.set_footer(text="Sentinel Security System")

        print(
            f"[QUARANTINE] {guild.name} | "
            f"By: {interaction.user} | "
            f"Reason: {reason} | "
            f"StaffRolesRemoved: {removed_roles_total} | "
            f"Invites Deleted: {deleted_invites}"
        )

        await interaction.edit_original_response(embed=confirm_embed)

    # ======================================================
    # 🔓 RESTORE
    # ======================================================
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(
        name="restore",
        description="ADMIN/OWNER ONLY: Restore server from quarantine"
    )
    async def restore(self, interaction: discord.Interaction):
        if not self._can_use_quarantine(interaction.user):
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="You need **Administrator** permission or be the **Owner** to use this command.",
                color=discord.Color.red(),
                timestamp=datetime.utcnow()
            )
            embed.set_footer(text="Sentinel Security System")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer(thinking=True)
        guild = interaction.guild
        path = snapshot_path(guild.id)

        if not os.path.exists(path):
            error_embed = discord.Embed(
                title="❌ No Snapshot Found",
                description="No quarantine snapshot found for this server.",
                color=discord.Color.red(),
                timestamp=datetime.utcnow()
            )
            error_embed.set_footer(text="Sentinel Security System")
            await interaction.edit_original_response(embed=error_embed)
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                snapshot = json.load(f)
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to read snapshot: {str(e)}",
                color=discord.Color.red(),
                timestamp=datetime.utcnow()
            )
            error_embed.set_footer(text="Sentinel Security System")
            await interaction.edit_original_response(embed=error_embed)
            return

        restored_count = 0
        failed_count = 0

        # Restore member roles (add back removed staff roles)
        for member_id, removed_role_ids in snapshot["members"].items():
            member = guild.get_member(int(member_id))
            if not member:
                continue

            roles_to_add = [
                guild.get_role(rid)
                for rid in removed_role_ids
                if guild.get_role(rid)
            ]

            if not roles_to_add:
                continue

            # Build new role list preserving existing roles plus restored ones
            try:
                current_roles = [r for r in member.roles if r is not None]
                # Avoid duplicates
                role_ids_existing = {r.id for r in current_roles}
                final_roles = current_roles + [r for r in roles_to_add if r.id not in role_ids_existing]

                await member.edit(
                    roles=final_roles,
                    reason=f"QUARANTINE RESTORE"
                )
                restored_count += 1
            except discord.Forbidden:
                failed_count += 1
                continue

        # Restore channel permissions if available
        restored_perms = 0
        if "channel_permissions" in snapshot:
            for channel_id_str, perms in snapshot["channel_permissions"].items():
                channel = guild.get_channel(int(channel_id_str))
                if not channel:
                    continue

                for perm in perms:
                    target = None
                    if perm["type"] == "role":
                        target = guild.get_role(perm["id"])
                    else:
                        target = guild.get_member(perm["id"])

                    if target:
                        try:
                            allow = discord.Permissions(perm["allow"])
                            deny = discord.Permissions(perm["deny"])
                            await channel.set_permissions(
                                target,
                                overwrite=discord.PermissionOverwrite.from_pair(allow, deny),
                                reason="Quarantine restore"
                            )
                            restored_perms += 1
                        except discord.Forbidden:
                            continue

        # 🧹 Remove notice channel
        notice = discord.utils.get(guild.text_channels, name=NOTICE_CHANNEL_NAME)
        if notice:
            try:
                await notice.delete(reason="Quarantine restored")
            except discord.Forbidden:
                pass

        # Delete snapshot file
        try:
            os.remove(path)
        except Exception as e:
            print(f"[QUARANTINE] Failed to delete snapshot: {e}")

        # 📜 Log restore with embed
        log_channel = guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            log_embed = discord.Embed(
                title="✅ Server Restored from Quarantine",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            log_embed.add_field(name="Guild", value=f"{guild.name} ({guild.id})", inline=False)
            log_embed.add_field(name="Restored By", value=f"{interaction.user.mention} ({interaction.user})", inline=True)
            log_embed.add_field(name="Members Restored", value=str(restored_count), inline=True)
            log_embed.add_field(name="Failed Restores", value=str(failed_count), inline=True)
            log_embed.add_field(name="Permissions Restored", value=str(restored_perms), inline=True)
            
            # Get original quarantine info if available
            if "reason" in snapshot:
                log_embed.add_field(name="Original Reason", value=snapshot["reason"], inline=False)
            if "quarantined_by" in snapshot:
                log_embed.add_field(name="Originally Quarantined By", value=snapshot["quarantined_by"], inline=True)
            
            log_embed.set_footer(text="Sentinel Security System")

            try:
                await log_channel.send(embed=log_embed)
            except Exception as e:
                print(f"[QUARANTINE ERROR] Failed to send restore log: {e}")

        # ✅ Confirmation embed
        confirm_embed = discord.Embed(
            title="✅ Server Fully Restored",
            description="All roles and permissions have been restored.",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        confirm_embed.add_field(name="Members Restored", value=str(restored_count), inline=True)
        confirm_embed.add_field(name="Failed", value=str(failed_count), inline=True)
        confirm_embed.add_field(name="Permissions Restored", value=str(restored_perms), inline=True)
        confirm_embed.add_field(name="Status", value="🔓 Server is unlocked", inline=False)
        confirm_embed.set_footer(text="Sentinel Security System")

        print(
            f"[QUARANTINE RESTORE] {guild.name} | "
            f"By: {interaction.user} | "
            f"Members: {restored_count} | "
            f"Failed: {failed_count}"
        )

        await interaction.edit_original_response(embed=confirm_embed)
