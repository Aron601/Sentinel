import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import traceback
import textwrap

GUILD_ID = 969259122409218118
OWNER_ID = 814466767598256150  # <-- YOUR USER ID

DANGER_EVAL_ENABLED = False


class Eval(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # 🔥 TOGGLE
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="eval_toggle", description="Enable/disable eval (OWNER ONLY)")
    async def eval_toggle(self, interaction: discord.Interaction):
        global DANGER_EVAL_ENABLED

        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message("❌ Owner only.", ephemeral=True)
            return

        DANGER_EVAL_ENABLED = not DANGER_EVAL_ENABLED
        state = "ENABLED" if DANGER_EVAL_ENABLED else "DISABLED"

        await interaction.response.send_message(
            f"⚠️ **Danger eval {state}**",
            ephemeral=True
        )

    # 🧠 EVAL
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="eval", description="Owner-only eval (danger mode)")
    async def eval(self, interaction: discord.Interaction, code: str):
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message("❌ Owner only.", ephemeral=True)
            return

        if not DANGER_EVAL_ENABLED:
            await interaction.response.send_message(
                "❌ Eval is disabled. Use `/eval_toggle` first.",
                ephemeral=True
            )
            return

        await interaction.response.defer(thinking=True)

        code = code.strip("` ")
        code = textwrap.indent(code, "    ")

        env = {
            "__builtins__": {
                "len": len,
                "range": range,
                "min": min,
                "max": max,
                "sum": sum,
                "print": print,
                "str": str,
                "int": int,
                "float": float,
            },
            "discord": discord,
            "bot": self.bot,
            "guild": interaction.guild,
            "channel": interaction.channel,
            "author": interaction.user,
            "asyncio": asyncio,
        }

        src = f"""
async def __eval_fn__():
{code}
"""

        try:
            exec(src, env)
            result = await asyncio.wait_for(env["__eval_fn__"](), timeout=5)
        except Exception:
            await interaction.followup.send(
                f"❌ **Error:**\n```py\n{traceback.format_exc(limit=6)}\n```",
                ephemeral=True
            )
            return

        await interaction.followup.send(
            f"✅ **Result:**\n```py\n{result}\n```",
            ephemeral=True
        )
