import discord
from discord.ext import commands
import textwrap
import traceback

OWNER_ID = 814466767598256150  # PUT YOUR USER ID HERE


class EvalPrefix(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # persistent eval state
        if not hasattr(bot, "setup_state"):
            bot.setup_state = {}

    @commands.command(name="eval")
    async def eval_cmd(self, ctx: commands.Context, *, code: str = None):
        # 🔐 owner only
        if ctx.author.id != OWNER_ID:
            return

        # 📥 determine code source
        file_code = None

        if ctx.message.attachments:
            attachment = ctx.message.attachments[0]

            if not attachment.filename.endswith(".txt"):
                await ctx.send("❌ Only `.txt` files are supported.")
                return

            try:
                file_code = (await attachment.read()).decode("utf-8")
            except Exception as e:
                await ctx.send(f"❌ Failed to read file: `{e}`")
                return

        # prefer file code over inline
        code = file_code or code

        if not code:
            await ctx.send(
                "❌ No code provided.\n"
                "Use:\n"
                "`!eval <code>` or attach a `.txt` file"
            )
            return

        # persistent state
        state = self.bot.setup_state

        # execution environment
        env = {
            "bot": self.bot,
            "ctx": ctx,
            "guild": ctx.guild,
            "discord": discord,
            "state": state,
        }

        # indent code for async wrapper
        code = textwrap.indent(code, "    ")

        source = f"""
async def _eval():
{code}
"""

        try:
            exec(source, env)
            result = await env["_eval"]()

            if result is not None:
                await ctx.send(f"✅ Result: `{result}`")
            else:
                await ctx.send("✅ Eval executed successfully.")
        except Exception:
            await ctx.send(
                f"❌ Eval error:\n```py\n{traceback.format_exc()}\n```"
            )
