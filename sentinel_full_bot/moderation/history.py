import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import json
import os

from utils.modlog import get_history

GUILD_ID = 969259122409218118
WARNINGS_FILE = "data/warnings.json"
AUTOMOD_FILE = "data/automod_violations.json"


class History(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _has_history_permission(self, member: discord.Member) -> bool:
        """Check if member can view history"""
        return member.guild_permissions.manage_messages or member.guild_permissions.administrator

    def _load_warnings(self, guild_id: int, user_id: int) -> list:
        """Load warnings for a user"""
        if not os.path.exists(WARNINGS_FILE):
            return []
        
        try:
            with open(WARNINGS_FILE, 'r') as f:
                data = json.load(f)
                key = f"{guild_id}_{user_id}"
                return data.get(key, {}).get("warnings", [])
        except:
            return []

    def _load_automod_violations(self, user_id: int) -> list:
        """Load automod violations for a user"""
        if not os.path.exists(AUTOMOD_FILE):
            return []
        
        try:
            with open(AUTOMOD_FILE, 'r') as f:
                data = json.load(f)
                return data.get(str(user_id), [])
        except:
            return []

    @commands.command(name="history")
    @commands.guild_only()
    async def history(self, ctx: commands.Context, *, target: str = None):
        """
        View complete moderation history of a user
        Usage: !history @user
               !history user_id
               !history username
        
        Shows: warnings, bans, kicks, timeouts, automod violations
        Only for users with Manage Messages or Administrator
        """
        
        # Permission check
        if not self._has_history_permission(ctx.author):
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            return
        
        # If no target provided, show info about command author
        if not target:
            target_member = ctx.author
        else:
            # Try to resolve target
            target_member = None
            
            # 1. Try mention
            if ctx.message.mentions:
                target_member = ctx.message.mentions[0]
            
            # 2. Try user ID
            if not target_member:
                try:
                    user_id = int(target)
                    try:
                        target_member = await ctx.guild.fetch_member(user_id)
                    except discord.NotFound:
                        await ctx.send("❌ User not found")
                        return
                except ValueError:
                    pass
            
            # 3. Try username
            if not target_member:
                target_lower = target.lower()
                for member in ctx.guild.members:
                    if member.name.lower() == target_lower or member.display_name.lower() == target_lower:
                        target_member = member
                        break
            
            # 4. Try fuzzy search
            if not target_member:
                for member in ctx.guild.members:
                    if target_lower in member.name.lower() or target_lower in member.display_name.lower():
                        target_member = member
                        break
            
            # Not found
            if not target_member:
                await ctx.send("❌ User not found")
                return
        
        # Collect all offenses
        offenses = []
        
        # Get warnings
        warnings = self._load_warnings(ctx.guild.id, target_member.id)
        for i, warn in enumerate(warnings, 1):
            offenses.append({
                "type": "⚠️ Warning",
                "timestamp": datetime.fromisoformat(warn.get("timestamp", datetime.utcnow().isoformat())),
                "reason": warn.get("reason", "Unknown"),
                "moderator_id": warn.get("moderator_id"),
                "details": f"Warning #{i}",
                "color": discord.Color.orange()
            })
        
        # Get automod violations
        automod_violations = self._load_automod_violations(target_member.id)
        for violation in automod_violations:
            offenses.append({
                "type": "🚫 Automod Violation",
                "timestamp": datetime.fromisoformat(violation.get("timestamp", datetime.utcnow().isoformat())),
                "reason": violation.get("reason", "Bad language/slurs"),
                "moderator_id": None,
                "details": violation.get("details", ""),
                "color": discord.Color.red()
            })
        
        # Get modlog history
        modlog_history = get_history(target_member.id)
        for entry in modlog_history:
            # Skip WARN entries since they're already handled by warnings system
            if entry["action"] == "WARN":
                continue
            
            action_map = {
                "BAN": ("🚫 Ban", discord.Color.dark_red()),
                "KICK": ("🦶 Kick", discord.Color.red()),
                "TIMEOUT": ("⏱️ Timeout", discord.Color.orange()),
                "MUTE": ("🔇 Mute", discord.Color.blurple()),
            }
            
            action_type, color = action_map.get(entry["action"], (f"📝 {entry['action']}", discord.Color.greyple()))
            
            offenses.append({
                "type": action_type,
                "timestamp": entry["timestamp"],
                "reason": entry.get("reason", "Unknown"),
                "moderator_id": None,
                "details": entry.get("moderator", ""),
                "color": color
            })
        
        # Sort by timestamp (most recent first)
        offenses.sort(key=lambda x: x["timestamp"], reverse=True)
        
        # If no offenses, show clean record
        if not offenses:
            embed = discord.Embed(
                title=f"📜 Moderation History — {target_member}",
                description="✅ **Clean Record** - No offenses found",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            embed.set_thumbnail(url=target_member.avatar.url if target_member.avatar else "")
            embed.set_footer(text="Sentinel History System")
            
            await ctx.send(embed=embed)
            return
        
        # Create embed with offenses
        embed = discord.Embed(
            title=f"📜 Moderation History — {target_member}",
            color=discord.Color.red() if len(offenses) >= 5 else discord.Color.orange() if len(offenses) >= 3 else discord.Color.yellow(),
            timestamp=datetime.utcnow()
        )
        
        # Summary
        warn_count = sum(1 for o in offenses if "Warning" in o["type"])
        automod_count = sum(1 for o in offenses if "Automod" in o["type"])
        ban_count = sum(1 for o in offenses if "Ban" in o["type"])
        kick_count = sum(1 for o in offenses if "Kick" in o["type"])
        timeout_count = sum(1 for o in offenses if "Timeout" in o["type"])
        
        summary = f"**Total Offenses:** {len(offenses)}"
        if warn_count > 0:
            summary += f"\n**Warnings:** {warn_count}"
        if automod_count > 0:
            summary += f"\n**Automod Violations:** {automod_count}"
        if ban_count > 0:
            summary += f"\n**Bans:** {ban_count}"
        if kick_count > 0:
            summary += f"\n**Kicks:** {kick_count}"
        if timeout_count > 0:
            summary += f"\n**Timeouts:** {timeout_count}"
        
        embed.add_field(
            name="📊 Summary",
            value=summary,
            inline=False
        )
        
        # Show offenses (limit to 20 most recent)
        for offense in offenses[:20]:
            mod_str = ""
            if offense["moderator_id"]:
                try:
                    mod = await self.bot.fetch_user(offense["moderator_id"])
                    mod_str = f"\n**Moderator:** {mod}"
                except:
                    mod_str = f"\n**Moderator:** Unknown (ID: {offense['moderator_id']})"
            
            timestamp_str = discord.utils.format_dt(offense["timestamp"], style="F")
            
            value = f"**Reason:** {offense['reason']}\n**Time:** {timestamp_str}{mod_str}"
            if offense["details"]:
                value += f"\n**Details:** {offense['details']}"
            
            embed.add_field(
                name=f"{offense['type']} • {offense['timestamp'].strftime('%Y-%m-%d %H:%M')}",
                value=value,
                inline=False
            )
        
        if len(offenses) > 20:
            embed.add_field(
                name="...",
                value=f"and {len(offenses) - 20} more offense(s)",
                inline=False
            )
        
        embed.set_thumbnail(url=target_member.avatar.url if target_member.avatar else "")
        embed.set_footer(text="Sentinel History System")
        
        await ctx.send(embed=embed)
