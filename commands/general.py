"""
General commands for the Discord bot.
Includes help, ping, info, and utility commands.
"""
import platform
import time
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands
from loguru import logger

from bot import ChatBot
from config import settings
from utils.rate_limiter import rate_limiter


class GeneralCommands(commands.Cog):
    """General purpose commands."""

    def __init__(self, bot: ChatBot) -> None:
        self.bot = bot
        self._start_time = time.time()

    # Prefix command: !ping
    @commands.command(name="ping", help="Check bot latency")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def ping_prefix(self, ctx: commands.Context) -> None:
        """Check bot latency (prefix command)."""
        start = time.perf_counter()
        message = await ctx.reply("Pinging...")
        end = time.perf_counter()

        latency = (end - start) * 1000
        ws_latency = self.bot.latency * 1000

        embed = discord.Embed(title="🏓 Pong!", color=discord.Color.green())
        embed.add_field(name="Message Latency", value=f"{latency:.2f}ms", inline=True)
        embed.add_field(name="WebSocket Latency", value=f"{ws_latency:.2f}ms", inline=True)

        await message.edit(content=None, embed=embed)

    # Slash command: /ping
    @app_commands.command(name="ping", description="Check bot latency")
    async def ping_slash(self, interaction: discord.Interaction) -> None:
        """Check bot latency (slash command)."""
        start = time.perf_counter()
        await interaction.response.defer()
        end = time.perf_counter()

        latency = (end - start) * 1000
        ws_latency = self.bot.latency * 1000

        embed = discord.Embed(title="🏓 Pong!", color=discord.Color.green())
        embed.add_field(name="Message Latency", value=f"{latency:.2f}ms", inline=True)
        embed.add_field(name="WebSocket Latency", value=f"{ws_latency:.2f}ms", inline=True)

        await interaction.followup.send(embed=embed)

    # Prefix command: !help
    @commands.command(name="help", help="Show help message")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def help_prefix(self, ctx: commands.Context, *, command: str = "") -> None:
        """Show help message (prefix command)."""
        if command:
            # Show help for specific command
            cmd = self.bot.get_command(command)
            if not cmd:
                await ctx.send(f"Command `{command}` not found.")
                return

            embed = discord.Embed(
                title=f"Help: {settings.command_prefix}{cmd.name}",
                description=cmd.help or "No description available.",
                color=discord.Color.blue(),
            )
            if cmd.aliases:
                embed.add_field(name="Aliases", value=", ".join(cmd.aliases), inline=False)
            if cmd.signature:
                embed.add_field(name="Usage", value=f"`{settings.command_prefix}{cmd.name} {cmd.signature}`", inline=False)
        else:
            # Show general help
            embed = discord.Embed(
                title="🤖 Bot Commands",
                description=(
                    "Here are the available commands. "
                    f"Use `{settings.command_prefix}help <command>` for more info."
                ),
                color=discord.Color.blue(),
            )

            # Group commands by cog
            cogs = {}
            for cmd in self.bot.commands:
                if cmd.hidden:
                    continue
                cog_name = cmd.cog_name or "General"
                if cog_name not in cogs:
                    cogs[cog_name] = []
                cogs[cog_name].append(cmd)

            for cog_name, cmds in sorted(cogs.items()):
                cmd_list = ", ".join(f"`{settings.command_prefix}{c.name}`" for c in cmds)
                embed.add_field(name=cog_name, value=cmd_list, inline=False)

            embed.set_footer(text=f"Prefix: {settings.command_prefix} | Also supports slash commands (/)")

        await ctx.send(embed=embed)

    # Slash command: /help
    @app_commands.command(name="help", description="Show help message")
    @app_commands.describe(command="Command to get help for")
    async def help_slash(self, interaction: discord.Interaction, command: str = "") -> None:
        """Show help message (slash command)."""
        if command:
            cmd = self.bot.get_command(command)
            if not cmd:
                await interaction.response.send_message(f"Command `{command}` not found.", ephemeral=True)
                return

            embed = discord.Embed(
                title=f"Help: /{cmd.name}",
                description=cmd.help or "No description available.",
                color=discord.Color.blue(),
            )
        else:
            embed = discord.Embed(
                title="🤖 Bot Commands",
                description=(
                    "Here are the available commands. "
                    "Use `/help <command>` for more info."
                ),
                color=discord.Color.blue(),
            )

            cogs = {}
            for cmd in self.bot.commands:
                if cmd.hidden:
                    continue
                cog_name = cmd.cog_name or "General"
                if cog_name not in cogs:
                    cogs[cog_name] = []
                cogs[cog_name].append(cmd)

            for cog_name, cmds in sorted(cogs.items()):
                cmd_list = ", ".join(f"`/{c.name}`" for c in cmds)
                embed.add_field(name=cog_name, value=cmd_list, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # Prefix command: !info / !botinfo
    @commands.command(name="info", aliases=["botinfo", "bi"], help="Show bot information")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def info_prefix(self, ctx: commands.Context) -> None:
        """Show bot information (prefix command)."""
        await self._send_info(ctx)

    # Slash command: /info
    @app_commands.command(name="info", description="Show bot information")
    async def info_slash(self, interaction: discord.Interaction) -> None:
        """Show bot information (slash command)."""
        await self._send_info(interaction)

    async def _send_info(self, destination) -> None:
        """Send bot info embed."""
        uptime = time.time() - self._start_time
        days, remainder = divmod(int(uptime), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)

        uptime_str = ""
        if days:
            uptime_str += f"{days}d "
        if hours:
            uptime_str += f"{hours}h "
        if minutes:
            uptime_str += f"{minutes}m "
        uptime_str += f"{seconds}s"

        embed = discord.Embed(title="🤖 Bot Information", color=discord.Color.blue())
        embed.add_field(name="Bot Name", value=str(self.bot.user), inline=True)
        embed.add_field(name="Bot ID", value=str(self.bot.user.id), inline=True)
        embed.add_field(name="Discord.py Version", value=discord.__version__, inline=True)
        embed.add_field(name="Python Version", value=platform.python_version(), inline=True)
        embed.add_field(name="Platform", value=platform.platform(), inline=True)
        embed.add_field(name="Uptime", value=uptime_str.strip(), inline=True)
        embed.add_field(name="Guilds", value=str(len(self.bot.guilds)), inline=True)
        embed.add_field(name="Users", value=str(len(self.bot.users)), inline=True)
        embed.add_field(name="Latency", value=f"{self.bot.latency * 1000:.2f}ms", inline=True)
        embed.add_field(name="Command Prefix", value=settings.command_prefix, inline=True)

        if self.bot.user.avatar:
            embed.set_thumbnail(url=self.bot.user.avatar.url)

        if hasattr(destination, "response"):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

    # Prefix command: !invite
    @commands.command(name="invite", help="Get bot invite link")
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def invite_prefix(self, ctx: commands.Context) -> None:
        """Get bot invite link (prefix command)."""
        await self._send_invite(ctx)

    # Slash command: /invite
    @app_commands.command(name="invite", description="Get bot invite link")
    async def invite_slash(self, interaction: discord.Interaction) -> None:
        """Get bot invite link (slash command)."""
        await self._send_invite(interaction)

    async def _send_invite(self, destination) -> None:
        """Send bot invite link."""
        permissions = discord.Permissions(
            send_messages=True,
            embed_links=True,
            attach_files=True,
            read_message_history=True,
            add_reactions=True,
            use_external_emojis=True,
            manage_messages=True,
        )
        invite_url = discord.utils.oauth_url(
            self.bot.user.id,
            permissions=permissions,
            scopes=("bot", "applications.commands"),
        )

        embed = discord.Embed(
            title="📨 Invite Me!",
            description=f"[Click here to invite the bot]({invite_url})",
            color=discord.Color.green(),
        )

        if hasattr(destination, "response"):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

    # Prefix command: !rate
    @commands.command(name="rate", help="Check your rate limit status")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def rate_prefix(self, ctx: commands.Context) -> None:
        """Check rate limit status (prefix command)."""
        remaining = rate_limiter.get_remaining(ctx.author.id)
        retry_after = rate_limiter.get_retry_after(ctx.author.id)

        embed = discord.Embed(title="📊 Rate Limit Status", color=discord.Color.blue())
        embed.add_field(name="Remaining Requests", value=str(remaining), inline=True)
        embed.add_field(name="Limit", value=str(settings.rate_limit_per_user), inline=True)
        embed.add_field(
            name="Reset In",
            value=f"{retry_after:.1f}s" if retry_after > 0 else "Ready",
            inline=True,
        )

        await ctx.send(embed=embed)

    # Slash command: /rate
    @app_commands.command(name="rate", description="Check your rate limit status")
    async def rate_slash(self, interaction: discord.Interaction) -> None:
        """Check rate limit status (slash command)."""
        remaining = rate_limiter.get_remaining(interaction.user.id)
        retry_after = rate_limiter.get_retry_after(interaction.user.id)

        embed = discord.Embed(title="📊 Rate Limit Status", color=discord.Color.blue())
        embed.add_field(name="Remaining Requests", value=str(remaining), inline=True)
        embed.add_field(name="Limit", value=str(settings.rate_limit_per_user), inline=True)
        embed.add_field(
            name="Reset In",
            value=f"{retry_after:.1f}s" if retry_after > 0 else "Ready",
            inline=True,
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # Prefix command: !uptime
    @commands.command(name="uptime", help="Show bot uptime")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def uptime_prefix(self, ctx: commands.Context) -> None:
        """Show bot uptime (prefix command)."""
        uptime = time.time() - self._start_time
        days, remainder = divmod(int(uptime), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)

        parts = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        parts.append(f"{seconds}s")

        await ctx.send(f"⏱️ Uptime: {' '.join(parts)}")

    # Slash command: /uptime
    @app_commands.command(name="uptime", description="Show bot uptime")
    async def uptime_slash(self, interaction: discord.Interaction) -> None:
        """Show bot uptime (slash command)."""
        uptime = time.time() - self._start_time
        days, remainder = divmod(int(uptime), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)

        parts = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        parts.append(f"{seconds}s")

        await interaction.response.send_message(f"⏱️ Uptime: {' '.join(parts)}", ephemeral=True)


async def setup(bot: ChatBot) -> None:
    """Setup function for loading the cog."""
    await bot.add_cog(GeneralCommands(bot))