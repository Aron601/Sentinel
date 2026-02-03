from typing import List
import asyncio
import discord
from discord.app_commands.models import AppCommand
from discord.ext import commands

from config import TOKEN
from database.db import connect

# moderation / core cogs
from moderation.purge import Purge
from moderation.spam import SpamHandler
from moderation.lockdown import Lockdown
from moderation.history import History
from moderation.quarantine import Quarantine
from moderation.ban import Ban
from moderation.kick import Kick
from moderation.slowmode import SlowMode
from moderation.modabuse import ModAbuseDetector
from moderation.whois import WhoIs
from moderation.timeout import TimeOut
from moderation.warn import Warn
from core.restart import Restart    
from core.verify import VerificationSystem
from core.automod import AutoMod
from core.server_logging import ServerLogging

from core.ping_test import PingTest
from core.eval_prefix import EvalPrefix
from core.help_cmd import HelpCommand

# 🔥 AI audit / permission manager
from moderation.ai_manage import AIManage


# 🔴 MUST MATCH ALL COMMAND FILES
GUILD_ID = 969259122409218118


# ⚡ WINDOWS EVENT LOOP FIX (VERY IMPORTANT)
asyncio.set_event_loop_policy(
    asyncio.WindowsProactorEventLoopPolicy()  # Faster than Selector
)


# ⚡ ULTRA LOW-LATENCY INTENTS (only essentials)
intents = discord.Intents(
    guilds=True,
    members=True,
    messages=True,
    message_content=True,
    moderation=True
)


class SentinelBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            # ⚡ Low latency settings
            heartbeat_timeout=60.0,  # Faster disconnect detection
            max_messages=512,  # Reduce memory overhead
        )

        # one spam handler instance
        self.spam_handler = SpamHandler()

        # AI audit state (used by !ai_apply)
        self.last_ai_plan = None
        
        # Cache for guild
        self._cached_guild = None

    async def setup_hook(self):
        # Database (safe startup) - non-blocking
        asyncio.create_task(self._connect_db())

        # Load cogs in parallel for faster startup
        cogs = [
            Lockdown(self),
            Purge(self),
            History(self),
            Quarantine(self),
            EvalPrefix(self),
            PingTest(self),
            Kick(self),
            Ban(self),
            SlowMode(self),
            ModAbuseDetector(self),
            Restart(self),
            AIManage(self),
            VerificationSystem(self),
            AutoMod(self),
            ServerLogging(self),
            WhoIs(self),
            TimeOut(self),
            Warn(self),
            HelpCommand(self)
        ]
        
        await asyncio.gather(*[self.add_cog(cog) for cog in cogs])

    async def _connect_db(self):
        """Connect to database without blocking"""
        try:
            await connect()
        except Exception as e:
            print("DB skipped:", e)

    async def on_ready(self):
        print(f"[READY] Sentinel online as {self.user}")

        # Cache guild object
        if not self._cached_guild:
            self._cached_guild = self.get_guild(GUILD_ID)

        # Guild slash sync - async without blocking
        guild = discord.Object(id=GUILD_ID)
        synced: List[AppCommand] = await self.tree.sync(guild=guild)

        print("[SYNC] Guild slash commands synced successfully:")
        for cmd in synced:
            print(f"  - /{cmd.name}")

    async def on_message(self, message: discord.Message):
        # ⚡ Ultra-fast exit paths (no awaits here)
        if message.author.bot:
            return
        
        if not message.guild:
            return

        # Non-blocking spam check
        asyncio.create_task(self.spam_handler.handle_message(message))
        
        # Non-blocking command processing
        asyncio.create_task(self.process_commands(message))


# Run bot
bot = SentinelBot()
bot.run(TOKEN)
