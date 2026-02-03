import discord
from discord.ext import commands
from datetime import datetime


class HelpCommand(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Remove default help command
        self.bot.remove_command("help")

    @commands.command(name="help")
    @commands.guild_only()
    async def help_command(self, ctx: commands.Context, command_name: str = None):
        """Display all available commands or get help for a specific command"""
        
        if command_name:
            # Get help for specific command
            cmd = self.bot.get_command(command_name.lower())
            if not cmd:
                await ctx.send(f"❌ Command `{command_name}` not found.")
                return
            
            # Format command name with aliases
            cmd_display = f"!{cmd.name}"
            if cmd.aliases:
                aliases_str = ", ".join(f"!{alias}" for alias in cmd.aliases)
                cmd_display += f" (aliases: {aliases_str})"
            
            embed = discord.Embed(
                title=f"📖 Command: {cmd_display}",
                color=discord.Color.blue(),
                description=cmd.help or "No description available.",
                timestamp=datetime.utcnow()
            )
            embed.set_footer(text="Sentinel Help System")
            await ctx.send(embed=embed)
            return
        
        # Display all commands organized by category/cog
        embed = discord.Embed(
            title="📖 Sentinel Bot - All Commands",
            color=discord.Color.blue(),
            description="Use `!help <command>` for detailed info on any command.",
            timestamp=datetime.utcnow()
        )
        
        # Organize commands by cog
        cogs_dict = {}
        
        for cmd in self.bot.commands:
            # Skip hidden commands
            if cmd.hidden:
                continue
            
            # Get cog name or use "General"
            cog_name = cmd.cog.__class__.__name__ if cmd.cog else "General"
            
            if cog_name not in cogs_dict:
                cogs_dict[cog_name] = []
            
            cogs_dict[cog_name].append(cmd)
        
        # Sort and display
        for cog_name in sorted(cogs_dict.keys()):
            commands_list = sorted(cogs_dict[cog_name], key=lambda c: c.name)
            
            # Format commands with descriptions and aliases
            cmd_descriptions = []
            for cmd in commands_list:
                # Get first line of docstring
                description = cmd.help.split('\n')[0] if cmd.help else "No description"
                
                # Add aliases if present
                if cmd.aliases:
                    aliases_str = ", ".join(cmd.aliases)
                    cmd_display = f"`!{cmd.name}` (alias: {aliases_str})"
                else:
                    cmd_display = f"`!{cmd.name}`"
                
                cmd_descriptions.append(f"{cmd_display} - {description}")
            
            if cmd_descriptions:
                embed.add_field(
                    name=f"⚙️ {cog_name}",
                    value="\n".join(cmd_descriptions[:5]),  # Limit to 5 per field
                    inline=False
                )
                
                # If more than 5 commands, add continuation
                if len(cmd_descriptions) > 5:
                    embed.add_field(
                        name=f"⚙️ {cog_name} (continued)",
                        value="\n".join(cmd_descriptions[5:]),
                        inline=False
                    )
        
        # Add slash commands section
        slash_commands = self.bot.tree.get_commands()
        if slash_commands:
            slash_descriptions = []
            for cmd in sorted(slash_commands, key=lambda c: c.name):
                description = cmd.description or "No description"
                slash_descriptions.append(f"`/{cmd.name}` - {description}")
            
            if slash_descriptions:
                embed.add_field(
                    name="Slash Commands (/) - Use these with /",
                    value="\n".join(slash_descriptions[:10]),
                    inline=False
                )
                
                if len(slash_descriptions) > 10:
                    embed.add_field(
                        name="Slash Commands (continued)",
                        value="\n".join(slash_descriptions[10:]),
                        inline=False
                    )
        
        embed.set_footer(text="Use !help <command> for more details | Sentinel Bot")
        await ctx.send(embed=embed)

    @commands.command(name="commands")
    @commands.guild_only()
    async def commands_list(self, ctx: commands.Context):
        """Show a quick list of all command names"""
        
        all_commands = sorted([cmd.name for cmd in self.bot.commands if not cmd.hidden])
        
        # Split into chunks for readability
        chunks = [all_commands[i:i+10] for i in range(0, len(all_commands), 10)]
        
        embed = discord.Embed(
            title=f"📋 Available Commands ({len(all_commands)} total)",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        
        for i, chunk in enumerate(chunks):
            embed.add_field(
                name=f"Commands {i*10+1}-{min((i+1)*10, len(all_commands))}",
                value=", ".join(f"`!{cmd}`" for cmd in chunk),
                inline=False
            )
        
        embed.add_field(
            name="💡 Tip",
            value="Use `!help` for detailed command descriptions or `!help <command>` for specific info.",
            inline=False
        )
        embed.set_footer(text="Sentinel Bot")
        
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCommand(bot))
