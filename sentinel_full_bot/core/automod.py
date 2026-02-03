import discord
from discord.ext import commands
from collections import defaultdict, deque
from datetime import datetime, timedelta
import time
import json
import os
import re

LOG_CHANNEL_ID = 1466641783105785886
AUTOMOD_FILE = "data/automod_violations.json"
BANNED_WORDS_FILE = "data/banned_words.json"

# Bad words/slurs list (comprehensive)
BAD_WORDS = {
    # Slurs and offensive terms - common variants
    "n1gg3r", "n1gg4", "n1gg@", "nigger", "nigg3r", "nigg4", "nigg@",
    "f@g", "f@gg0t", "faggot", "f4g", "f4gg0t",
    "k1k3", "k1k3", "kike",
    "tr@nny", "tranny", "tr4nny",
    "c0ck", "c0cks", "c0cks@ck",
    "b1tch", "b1tches", "bitches", "bitch", "b4tch",
    "wh0r3", "whor3", "whore", "w0r3",
    "sh1t", "sh1te", "sh1tty", "shite", "shitty", "sh4t",
    "d4mn", "damn", "d@mn",
    "h3ll", "hell", "h@ll",
    "c0ck", "c0cks", "c0cks@ck", "cocksucker",
    "a55h0l3", "a55h0le", "asshole", "a55hole",
    "b@stard", "bastard", "b4stard",
    "d1ck", "d1cks", "d1cksh1t", "d1ckhead", "dick", "dicks", "dickshit", "dickhead",
    "p155", "p1ss", "piss", "p1ssed",
    "sl@g", "slag", "sl4g",
    "tw@t", "twat", "tw4t",
    "v@g1n@", "vag1n@", "vagina",
    "c0ckwor3", "cockwhore",
    
    # Racist slurs
    "ch1nk", "chink", "ch4nk",
    "sp1c", "spic", "sp4c",
    "b00g1e", "boogie",
    
    # Additional variations
    "f*ck","fuck", "f*cking", "f*cked", "f*cker", "fck", "fcking",
    "m0therf*ck","motherfucker", "m0therf@ck", "motherf*ck",
}


def _load_custom_banned_words():
    """Load custom banned words from JSON file"""
    if os.path.exists(BANNED_WORDS_FILE):
        try:
            with open(BANNED_WORDS_FILE, 'r') as f:
                return set(json.load(f))
        except:
            return set()
    return set()


def _save_custom_banned_words(words: set):
    """Save custom banned words to JSON file"""
    os.makedirs("data", exist_ok=True)
    with open(BANNED_WORDS_FILE, 'w') as f:
        json.dump(list(words), f, indent=2)


# Load custom banned words on startup
CUSTOM_BANNED_WORDS = _load_custom_banned_words()

# ⚡ Pre-compile regex pattern for faster matching
ALL_BANNED_WORDS = BAD_WORDS.union(CUSTOM_BANNED_WORDS)
WORD_PATTERN = re.compile(r'\b(' + '|'.join(re.escape(word) for word in ALL_BANNED_WORDS) + r')\b')




class AutomodViolation:
    """Track user violations for timeout escalation"""
    
    def __init__(self):
        self.violations = defaultdict(deque)  # user_id -> deque of timestamps
        self.timeouts = defaultdict(float)  # user_id -> timeout expiry time
    
    def add_violation(self, user_id: int) -> int:
        """Add violation and return current count in last minute"""
        now = time.time()
        
        # Remove violations older than 1 minute
        while self.violations[user_id] and self.violations[user_id][0] < now - 60:
            self.violations[user_id].popleft()
        
        # Add new violation
        self.violations[user_id].append(now)
        
        return len(self.violations[user_id])
    
    def should_timeout(self, user_id: int) -> bool:
        """Check if user should be timed out (3+ violations in a minute)"""
        count = len(self.violations[user_id])
        return count >= 3
    
    def is_already_timed_out(self, user_id: int) -> bool:
        """Check if user is already on cooldown"""
        return time.time() < self.timeouts[user_id]
    
    def set_timeout(self, user_id: int):
        """Set timeout expiry time (5 minutes from now)"""
        self.timeouts[user_id] = time.time() + 300  # 5 minutes


class AutoMod(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.violations = AutomodViolation()
    
    def _save_violation(self, user_id: int, words: list):
        """Save automod violation to persistent file"""
        os.makedirs("data", exist_ok=True)
        
        if os.path.exists(AUTOMOD_FILE):
            with open(AUTOMOD_FILE, 'r') as f:
                data = json.load(f)
        else:
            data = {}
        
        user_key = str(user_id)
        if user_key not in data:
            data[user_key] = []
        
        data[user_key].append({
            "reason": f"Bad language/slurs: {', '.join(words[:3])}",
            "details": ", ".join(words),
            "timestamp": datetime.utcnow().isoformat()
        })
        
        with open(AUTOMOD_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Monitor messages for bad words"""
        
        # Ignore bots
        if message.author.bot:
            return
        
        # Ignore DMs
        if not message.guild:
            return
        
        # Ignore messages in thread/voice
        if not isinstance(message.channel, discord.TextChannel):
            return
        
        # Skip users with manage_messages permission or higher
        if message.author.guild_permissions.manage_messages:
            return
        
        # Check for bad words
        content = message.content.lower()
        found_words = self._check_bad_words(content)
        
        if not found_words:
            return
        
        # ⚡ INSTANT deletion - delete before any other processing
        try:
            await message.delete()
        except discord.Forbidden:
            pass
        
        # Record violation
        violation_count = self.violations.add_violation(message.author.id)
        
        # Save violation to persistent storage
        self._save_violation(message.author.id, found_words)
        
        # Check if should timeout
        if self.violations.should_timeout(message.author.id):
            # Skip if already timed out recently
            if self.violations.is_already_timed_out(message.author.id):
                return
            
            # Execute timeout
            try:
                await message.author.timeout(
                    timedelta(minutes=5),
                    reason=f"Automod: Excessive bad language (3+ violations in 1 minute)"
                )
                self.violations.set_timeout(message.author.id)
                
                # Log timeout
                await self._log_timeout(message.guild, message.author, found_words)
                
            except discord.Forbidden:
                # Log to channel if no permission to timeout
                await self._log_violation(message.guild, message.author, found_words, timeout_failed=True)
        else:
            # Log violation
            await self._log_violation(message.guild, message.author, found_words)
    
    def _check_bad_words(self, content: str) -> list:
        """⚡ Fast regex-based bad word detection"""
        matches = WORD_PATTERN.findall(content)
        return list(dict.fromkeys(matches))  # Remove duplicates, preserve order
    
    async def _log_violation(
        self, 
        guild: discord.Guild, 
        user: discord.Member, 
        words: list,
        timeout_failed: bool = False
    ):
        """Log automod violation to log channel"""
        log_channel = guild.get_channel(LOG_CHANNEL_ID)
        if not log_channel:
            return
        
        embed = discord.Embed(
            title="🚫 Automod Violation",
            color=discord.Color.orange(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="User", value=f"{user.mention} ({user})", inline=False)
        embed.add_field(name="Violation Count", value="1", inline=True)
        embed.add_field(name="Bad Words", value=", ".join(words)[:100] if words else "Unknown", inline=False)
        
        if timeout_failed:
            embed.add_field(
                name="⚠️ Warning",
                value="Failed to timeout - missing permissions",
                inline=False
            )
        
        embed.set_footer(text="Sentinel Automod System")
        
        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            pass
        
        print(f"[AUTOMOD] {user} - Words: {', '.join(words)}")
    
    async def _log_timeout(
        self,
        guild: discord.Guild,
        user: discord.Member,
        words: list
    ):
        """Log automod timeout to log channel"""
        log_channel = guild.get_channel(LOG_CHANNEL_ID)
        if not log_channel:
            return
        
        embed = discord.Embed(
            title="⏱️ Automod Timeout (3+ Violations)",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="User", value=f"{user.mention} ({user})", inline=False)
        embed.add_field(name="Duration", value="5 minutes", inline=True)
        embed.add_field(name="Reason", value="3+ bad language violations in 1 minute", inline=False)
        embed.add_field(name="Recent Bad Words", value=", ".join(words)[:100] if words else "Unknown", inline=False)
        embed.set_footer(text="Sentinel Automod System")
        
        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            pass
        
        print(f"[AUTOMOD TIMEOUT] {user} - 5 minute timeout for excessive bad language")
    
    @commands.command(name="automod_status")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def automod_status(self, ctx: commands.Context):
        """Show automod status and stats"""
        
        embed = discord.Embed(
            title="🛡️ Automod Status",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(
            name="Status",
            value="✅ Active",
            inline=True
        )
        embed.add_field(
            name="Monitored",
            value=f"{len(BAD_WORDS)} default + {len(CUSTOM_BANNED_WORDS)} custom = {len(BAD_WORDS) + len(CUSTOM_BANNED_WORDS)} total words",
            inline=True
        )
        embed.add_field(
            name="Violation Threshold",
            value="3+ violations in 1 minute",
            inline=True
        )
        embed.add_field(
            name="Punishment",
            value="5 minute timeout",
            inline=True
        )
        embed.add_field(
            name="Exemptions",
            value="Users with Manage Messages permission or higher",
            inline=False
        )
        embed.add_field(
            name="Features",
            value="• Auto-delete messages with bad words\n• Track violations per minute\n• Auto-timeout on threshold\n• Comprehensive logging\n• Custom banned words",
            inline=False
        )
        embed.set_footer(text="Sentinel Automod System")
        
        await ctx.send(embed=embed)
    
    @commands.command(name="ban_word")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def ban_word(self, ctx: commands.Context, *, word: str):
        """Add a custom banned word (admin only)"""
        word = word.lower().strip()
        
        if len(word) < 2:
            await ctx.send("❌ Word must be at least 2 characters long.")
            return
        
        if word in CUSTOM_BANNED_WORDS:
            await ctx.send(f"❌ `{word}` is already banned.")
            return
        
        if word in BAD_WORDS:
            await ctx.send(f"❌ `{word}` is already in the default banned words list.")
            return
        
        CUSTOM_BANNED_WORDS.add(word)
        _save_custom_banned_words(CUSTOM_BANNED_WORDS)
        
        # ⚡ Recompile regex pattern for fast matching
        global WORD_PATTERN, ALL_BANNED_WORDS
        ALL_BANNED_WORDS = BAD_WORDS.union(CUSTOM_BANNED_WORDS)
        WORD_PATTERN = re.compile(r'\b(' + '|'.join(re.escape(w) for w in ALL_BANNED_WORDS) + r')\b')
        
        embed = discord.Embed(
            title="✅ Word Added to Banlist",
            color=discord.Color.green(),
            description=f"Added `{word}` to custom banned words."
        )
        embed.add_field(name="Total Custom Words", value=len(CUSTOM_BANNED_WORDS), inline=True)
        embed.set_footer(text=f"Added by {ctx.author}")
        
        await ctx.send(embed=embed)
    
    @commands.command(name="unban_word")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def unban_word(self, ctx: commands.Context, *, word: str):
        """Remove a custom banned word (admin only)"""
        word = word.lower().strip()
        
        if word not in CUSTOM_BANNED_WORDS:
            await ctx.send(f"❌ `{word}` is not in the custom banned words list.")
            return
        
        CUSTOM_BANNED_WORDS.discard(word)
        _save_custom_banned_words(CUSTOM_BANNED_WORDS)
        
        # ⚡ Recompile regex pattern for fast matching
        global WORD_PATTERN, ALL_BANNED_WORDS
        ALL_BANNED_WORDS = BAD_WORDS.union(CUSTOM_BANNED_WORDS)
        WORD_PATTERN = re.compile(r'\b(' + '|'.join(re.escape(w) for w in ALL_BANNED_WORDS) + r')\b')
        
        embed = discord.Embed(
            title="✅ Word Removed from Banlist",
            color=discord.Color.green(),
            description=f"Removed `{word}` from custom banned words."
        )
        embed.add_field(name="Total Custom Words", value=len(CUSTOM_BANNED_WORDS), inline=True)
        embed.set_footer(text=f"Removed by {ctx.author}")
        
        await ctx.send(embed=embed)
    
    @commands.command(name="banned_words")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def banned_words(self, ctx: commands.Context):
        """List all custom banned words"""
        if not CUSTOM_BANNED_WORDS:
            await ctx.send("No custom banned words configured.")
            return
        
        words_list = sorted(list(CUSTOM_BANNED_WORDS))
        chunks = [words_list[i:i+10] for i in range(0, len(words_list), 10)]
        
        embed = discord.Embed(
            title="📋 Custom Banned Words",
            color=discord.Color.blue(),
            description=f"Total: {len(CUSTOM_BANNED_WORDS)} words"
        )
        
        for i, chunk in enumerate(chunks):
            embed.add_field(
                name=f"Words {i*10+1}-{min((i+1)*10, len(words_list))}",
                value=", ".join(f"`{w}`" for w in chunk),
                inline=False
            )
        
        embed.set_footer(text="Use !ban_word <word> to add more")
        
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoMod(bot))
