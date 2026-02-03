import discord
from discord.ext import commands
import os
import sys
from datetime import datetime

# 🔐 OWNER ID
OWNER_ID = 814466767598256150  # ← your user ID

# 🧾 LOG CHANNEL
LOG_CHANNEL_ID = 1466641783105785886


class Restart(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="restart")
    async def restart(self, ctx: commands.Context):
        # 🔐 Owner check
        if ctx.author.id != OWNER_ID:
            return

        await ctx.send("♻️ **Restarting Sentinel…**")

        # 📜 Log
        log_channel = ctx.guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            embed = discord.Embed(
                title="♻️ Bot Restart",
                color=discord.Color.orange(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(
                name="Triggered by",
                value=f"{ctx.author} ({ctx.author.id})",
                inline=False
            )
            embed.set_footer(text="Sentinel System")

            try:
                await log_channel.send(embed=embed)
            except discord.Forbidden:
                pass

        # 🛑 Close bot cleanly
        await self.bot.close()

        # 🔄 Restart process
        os.execv(sys.executable, [sys.executable] + sys.argv)
