import discord
from discord.ext import commands
from ai.snapshot import snapshot_guild
from ai.ai_engine import ask_ai
from ai.executor import apply_actions

class AIManage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_plan = None

    @commands.command(name="ai_scan")
    @commands.has_guild_permissions(manage_guild=True)
    async def ai_scan(self, ctx):
        await ctx.send("🧠 AI is auditing the server…")

        snapshot = snapshot_guild(ctx.guild)
        plan = await ask_ai(snapshot)
        self.last_plan = plan

        embed = discord.Embed(
            title="🧠 AI Server Audit",
            color=discord.Color.orange()
        )

        for item in plan.get("audit", []):
            embed.add_field(
                name=f"{item['severity'].upper()} • confidence {item['confidence']}",
                value=(
                    f"**Problem:** {item['problem']}\n"
                    f"**Why:** {item['why_this_is_bad']}\n"
                    f"**Fix:** {item['recommended_fix']}"
                ),
                inline=False
            )

        await ctx.send(embed=embed)

    @commands.command(name="ai_apply")
    @commands.has_guild_permissions(administrator=True)
    async def ai_apply(self, ctx):
        if not self.last_plan:
            await ctx.send("❌ Run `!ai_scan` first.")
            return

        await apply_actions(ctx.guild, self.last_plan)
        await ctx.send("✅ AI fixes applied (batch execution).")
