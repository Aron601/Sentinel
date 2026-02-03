import discord
from discord.ext import commands
import json
import os
from datetime import datetime

# File to track if verification message has been posted
VERIFY_STATE_FILE = "data/verify_state.json"

# Channel and role names
VERIFY_CHANNEL_NAME = "verify"
VERIFIED_ROLE_NAME = "Member"


class VerifyButton(discord.ui.View):
    """Button view for verification"""
    
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)  # Never timeout
        self.bot = bot
    
    @discord.ui.button(label="Verify!", style=discord.ButtonStyle.green, custom_id="verify_button")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle verification button click"""
        
        guild = interaction.guild
        user = interaction.user
        
        # Get the verified role
        verified_role = discord.utils.get(guild.roles, name=VERIFIED_ROLE_NAME)
        if not verified_role:
            await interaction.response.send_message(
                "❌ Verified role not found. Please contact an administrator.",
                ephemeral=True
            )
            return
        
        # Check if user already has the role
        if verified_role in user.roles:
            await interaction.response.send_message(
                "✅ You are already verified!",
                ephemeral=True
            )
            return
        
        # Add the role
        try:
            await user.add_roles(verified_role, reason="User verified")
            await interaction.response.send_message(
                f"✅ Welcome! You have been verified and can now access the server.",
                ephemeral=True
            )
            
            # Log verification
            print(f"[VERIFY] {user} ({user.id}) verified in {guild.name}")
            
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to assign roles. Please contact an administrator.",
                ephemeral=True
            )
        except discord.HTTPException as e:
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )


class VerificationSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Add the persistent view when cog is loaded
        self.bot.add_view(VerifyButton(bot))
    
    @commands.command(name="setup_verify")
    @commands.is_owner()
    @commands.guild_only()
    async def setup_verify(self, ctx: commands.Context):
        """
        Setup verification system - posts the verify embed in #verify channel
        Only works if bot owner uses it
        """
        
        # Check if verify message has already been posted
        if self._has_verify_message_posted():
            await ctx.send("⚠️ Verification message already posted. Use `!reset_verify` to post again.")
            return
        
        # Find or create verify channel
        verify_channel = discord.utils.get(ctx.guild.channels, name=VERIFY_CHANNEL_NAME)
        if not verify_channel:
            try:
                verify_channel = await ctx.guild.create_text_channel(
                    VERIFY_CHANNEL_NAME,
                    reason="Verification channel"
                )
            except discord.Forbidden:
                await ctx.send("❌ I don't have permission to create channels.")
                return
        
        # Check if verified role exists, create if not
        verified_role = discord.utils.get(ctx.guild.roles, name=VERIFIED_ROLE_NAME)
        if not verified_role:
            try:
                verified_role = await ctx.guild.create_role(
                    name=VERIFIED_ROLE_NAME,
                    color=discord.Color.green(),
                    reason="Verification role"
                )
            except discord.Forbidden:
                await ctx.send("❌ I don't have permission to create roles.")
                return
        
        # Create embed
        embed = discord.Embed(
            title="✅ Server Verification",
            description="Welcome to our server! Please verify to access all channels.",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(
            name="Why verify?",
            value="Verification helps keep our server safe and organized.",
            inline=False
        )
        embed.add_field(
            name="How to verify?",
            value="Click the **Verify!** button below to get instant access to the server.",
            inline=False
        )
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else "")
        embed.set_footer(text="Sentinel Verification System")
        
        # Post message with button
        try:
            message = await verify_channel.send(embed=embed, view=VerifyButton(self.bot))
            
            # Mark as posted
            self._mark_verify_message_posted(ctx.guild.id, message.id, verify_channel.id)
            
            await ctx.send(f"✅ Verification message posted in {verify_channel.mention}")
            print(f"[VERIFY] Setup verification in {ctx.guild.name}")
            
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to send messages in that channel.")
    
    @commands.command(name="reset_verify")
    @commands.is_owner()
    @commands.guild_only()
    async def reset_verify(self, ctx: commands.Context):
        """
        Reset verification - allows setup_verify to post message again
        Owner only
        """
        
        self._clear_verify_state(ctx.guild.id)
        await ctx.send("✅ Verification state reset. You can now use `!setup_verify` again.")
        print(f"[VERIFY] Reset verification state for {ctx.guild.name}")
    
    def _has_verify_message_posted(self) -> bool:
        """Check if verify message has been posted"""
        if not os.path.exists(VERIFY_STATE_FILE):
            return False
        
        try:
            with open(VERIFY_STATE_FILE, 'r') as f:
                data = json.load(f)
                return len(data.get("guilds", {})) > 0
        except:
            return False
    
    def _mark_verify_message_posted(self, guild_id: int, message_id: int, channel_id: int):
        """Mark that verify message has been posted"""
        
        # Ensure data directory exists
        os.makedirs("data", exist_ok=True)
        
        # Load existing data or create new
        if os.path.exists(VERIFY_STATE_FILE):
            with open(VERIFY_STATE_FILE, 'r') as f:
                data = json.load(f)
        else:
            data = {"guilds": {}}
        
        # Update data
        data["guilds"][str(guild_id)] = {
            "message_id": message_id,
            "channel_id": channel_id,
            "posted_at": datetime.utcnow().isoformat()
        }
        
        # Save data
        with open(VERIFY_STATE_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _clear_verify_state(self, guild_id: int):
        """Clear verify state for a guild"""
        if not os.path.exists(VERIFY_STATE_FILE):
            return
        
        try:
            with open(VERIFY_STATE_FILE, 'r') as f:
                data = json.load(f)
            
            if str(guild_id) in data.get("guilds", {}):
                del data["guilds"][str(guild_id)]
            
            with open(VERIFY_STATE_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(VerificationSystem(bot))
