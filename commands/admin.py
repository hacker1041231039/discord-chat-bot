"""
Admin/Moderation commands for the Discord bot.
Only usable by users with appropriate permissions.
"""
import discord
from discord import app_commands
from discord.ext import commands
from loguru import logger

from bot import ChatBot
from config import settings
from utils.conversation import conversation_manager
from utils.rate_limiter import rate_limiter


def is_owner_check():
    """Custom check for slash commands - only bot owner can use."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.client.owner_id is None:
            # Fetch owner if not cached
            app_info = await interaction.client.application_info()
            interaction.client.owner_id = app_info.owner.id
        return interaction.user.id == interaction.client.owner_id
    return app_commands.check(predicate)


class AdminCommands(commands.Cog):
    """Administrative and moderation commands."""

    def __init__(self, bot: ChatBot) -> None:
        self.bot = bot

    def _is_admin(self, user: discord.User | discord.Member) -> bool:
        """Check if user is bot admin (owner or has administrator permission)."""
        if user.id == self.bot.owner_id:
            return True
        if isinstance(user, discord.Member) and user.guild_permissions.administrator:
            return True
        return False

    # Prefix command: !clear / !purge
    @commands.command(name="clear", aliases=["purge"], help="Clear messages in channel")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True, read_message_history=True)
    @commands.cooldown(1, 30, commands.BucketType.channel)
    async def clear_prefix(
        self,
        ctx: commands.Context,
        amount: int = 10,
        user: discord.Member | None = None,
    ) -> None:
        """Clear messages in channel (prefix command)."""
        if amount < 1 or amount > 100:
            await ctx.send("Amount must be between 1 and 100.")
            return

        def check(message: discord.Message) -> bool:
            if user and message.author.id != user.id:
                return False
            return not message.pinned

        try:
            deleted = await ctx.channel.purge(limit=amount + 1, check=check)  # +1 for command message
            embed = discord.Embed(
                title="🗑️ Messages Cleared",
                description=f"Deleted {len(deleted) - 1} message(s).",
                color=discord.Color.green(),
            )
            if user:
                embed.add_field(name="Filtered by User", value=user.mention, inline=True)
            msg = await ctx.send(embed=embed)
            await msg.delete(delay=5)
        except discord.Forbidden:
            await ctx.send("I don't have permission to delete messages.")
        except discord.HTTPException as e:
            logger.error(f"Error clearing messages: {e}")
            await ctx.send("Failed to clear messages.")

    # Slash command: /clear
    @app_commands.command(name="clear", description="Clear messages in channel")
    @app_commands.describe(
        amount="Number of messages to delete (1-100)",
        user="Only delete messages from this user",
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.checks.bot_has_permissions(manage_messages=True, read_message_history=True)
    async def clear_slash(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 1, 100] = 10,
        user: discord.Member | None = None,
    ) -> None:
        """Clear messages in channel (slash command)."""
        def check(message: discord.Message) -> bool:
            if user and message.author.id != user.id:
                return False
            return not message.pinned

        try:
            await interaction.response.defer(ephemeral=True)
            deleted = await interaction.channel.purge(limit=amount, check=check)

            embed = discord.Embed(
                title="🗑️ Messages Cleared",
                description=f"Deleted {len(deleted)} message(s).",
                color=discord.Color.green(),
            )
            if user:
                embed.add_field(name="Filtered by User", value=user.mention, inline=True)

            await interaction.followup.send(embed=embed, ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("I don't have permission to delete messages.", ephemeral=True)
        except discord.HTTPException as e:
            logger.error(f"Error clearing messages: {e}")
            await interaction.followup.send("Failed to clear messages.", ephemeral=True)

    # Prefix command: !reload
    @commands.command(name="reload", help="Reload a cog")
    @commands.is_owner()
    async def reload_prefix(self, ctx: commands.Context, cog: str) -> None:
        """Reload a cog (prefix command, owner only)."""
        await self._reload_cog(ctx, cog)

    # Slash command: /reload
    @app_commands.command(name="reload", description="Reload a cog (owner only)")
    @app_commands.describe(cog="Cog name to reload (e.g., commands.general)")
    @is_owner_check()
    async def reload_slash(self, interaction: discord.Interaction, cog: str) -> None:
        """Reload a cog (slash command, owner only)."""
        await self._reload_cog(interaction, cog)

    async def _reload_cog(self, destination, cog: str) -> None:
        """Reload a cog."""
        try:
            await self.bot.reload_extension(cog)
            logger.info(f"Reloaded cog: {cog}")
            msg = f"✅ Reloaded `{cog}`"
        except commands.ExtensionNotLoaded:
            try:
                await self.bot.load_extension(cog)
                logger.info(f"Loaded cog: {cog}")
                msg = f"✅ Loaded `{cog}`"
            except Exception as e:
                logger.error(f"Failed to load cog {cog}: {e}")
                msg = f"❌ Failed to load `{cog}`: {e}"
        except Exception as e:
            logger.error(f"Failed to reload cog {cog}: {e}")
            msg = f"❌ Failed to reload `{cog}`: {e}"

        if hasattr(destination, "response"):
            await destination.response.send_message(msg, ephemeral=True)
        else:
            await destination.send(msg)

    # Prefix command: !sync
    @commands.command(name="sync", help="Sync slash commands")
    @commands.is_owner()
    async def sync_prefix(self, ctx: commands.Context, guild_only: bool = False) -> None:
        """Sync slash commands (prefix command, owner only)."""
        await self._sync_commands(ctx, guild_only)

    # Slash command: /sync
    @app_commands.command(name="sync", description="Sync slash commands (owner only)")
    @app_commands.describe(guild_only="Sync only to current guild")
    @is_owner_check()
    async def sync_slash(self, interaction: discord.Interaction, guild_only: bool = False) -> None:
        """Sync slash commands (slash command, owner only)."""
        await self._sync_commands(interaction, guild_only)

    async def _sync_commands(self, destination, guild_only: bool) -> None:
        """Sync slash commands."""
        try:
            if guild_only and hasattr(destination, "guild") and destination.guild:
                guild = destination.guild
                self.bot.tree.copy_global_to(guild=guild)
                await self.bot.tree.sync(guild=guild)
                msg = f"✅ Synced commands to guild {guild.name}"
            else:
                await self.bot.tree.sync()
                msg = "✅ Synced commands globally"

            logger.info(msg)

            if hasattr(destination, "response"):
                await destination.response.send_message(msg, ephemeral=True)
            else:
                await destination.send(msg)
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")
            msg = f"❌ Failed to sync commands: {e}"
            if hasattr(destination, "response"):
                await destination.response.send_message(msg, ephemeral=True)
            else:
                await destination.send(msg)

    # Prefix command: !clearhistory / !ch
    @commands.command(name="clearhistory", aliases=["ch"], help="Clear conversation history")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def clear_history_prefix(
        self,
        ctx: commands.Context,
        target: discord.Member | discord.TextChannel | None = None,
    ) -> None:
        """Clear conversation history (prefix command)."""
        await self._clear_history(ctx, target)

    # Slash command: /clearhistory
    @app_commands.command(name="clearhistory", description="Clear conversation history")
    @app_commands.describe(
        target="User or channel to clear history for (default: current channel/user)"
    )
    async def clear_history_slash(
        self,
        interaction: discord.Interaction,
        target: discord.Member | discord.TextChannel | None = None,
    ) -> None:
        """Clear conversation history (slash command)."""
        await self._clear_history(interaction, target)

    async def _clear_history(
        self,
        destination,
        target: discord.Member | discord.TextChannel | None,
    ) -> None:
        """Clear conversation history."""
        if target is None:
            # Clear current channel/user
            if isinstance(destination, commands.Context):
                channel_id = destination.channel.id
                user_id = destination.author.id
                is_dm = isinstance(destination.channel, discord.DMChannel)
            else:
                channel_id = destination.channel_id
                user_id = destination.user.id
                is_dm = isinstance(destination.channel, discord.DMChannel) if destination.channel else False
        elif isinstance(target, discord.Member):
            # Clear specific user's history in current channel
            if isinstance(destination, commands.Context):
                channel_id = destination.channel.id
            else:
                channel_id = destination.channel_id
            user_id = target.id
            is_dm = False
        elif isinstance(target, discord.TextChannel):
            # Clear entire channel history
            channel_id = target.id
            user_id = self.bot.user.id  # Use bot ID as key for channel-wide clear
            is_dm = False
        else:
            msg = "Invalid target type."
            if hasattr(destination, "response"):
                await destination.response.send_message(msg, ephemeral=True)
            else:
                await destination.send(msg)
            return

        conversation_manager.clear_history(channel_id, user_id, is_dm)

        if isinstance(target, discord.TextChannel):
            msg = f"✅ Cleared conversation history for channel {target.mention}"
        elif isinstance(target, discord.Member):
            msg = f"✅ Cleared conversation history for {target.mention}"
        else:
            msg = "✅ Cleared conversation history"

        if hasattr(destination, "response"):
            await destination.response.send_message(msg, ephemeral=True)
        else:
            await destination.send(msg)

    # Prefix command: !ratelimit / !rl
    @commands.command(name="ratelimit", aliases=["rl"], help="Manage rate limits")
    @commands.is_owner()
    async def rate_limit_prefix(
        self,
        ctx: commands.Context,
        action: str,
        user: discord.User | None = None,
    ) -> None:
        """Manage rate limits (prefix command, owner only)."""
        await self._manage_rate_limit(ctx, action, user)

    # Slash command: /ratelimit
    @app_commands.command(name="ratelimit", description="Manage rate limits (owner only)")
    @app_commands.describe(
        action="Action to perform: reset, status",
        user="Target user (default: yourself for status)",
    )
    @is_owner_check()
    async def rate_limit_slash(
        self,
        interaction: discord.Interaction,
        action: str,
        user: discord.User | None = None,
    ) -> None:
        """Manage rate limits (slash command, owner only)."""
        await self._manage_rate_limit(interaction, action, user)

    async def _manage_rate_limit(
        self,
        destination,
        action: str,
        user: discord.User | None,
    ) -> None:
        """Manage rate limits."""
        action = action.lower()

        if action == "reset":
            if user is None:
                msg = "Please specify a user to reset."
            else:
                rate_limiter.reset_user(user.id)
                msg = f"✅ Reset rate limit for {user.mention}"
        elif action == "status":
            target = user or (destination.author if isinstance(destination, commands.Context) else destination.user)
            remaining = rate_limiter.get_remaining(target.id)
            retry_after = rate_limiter.get_retry_after(target.id)

            embed = discord.Embed(title="📊 Rate Limit Status", color=discord.Color.blue())
            embed.add_field(name="User", value=target.mention, inline=True)
            embed.add_field(name="Remaining", value=str(remaining), inline=True)
            embed.add_field(name="Limit", value=str(settings.rate_limit_per_user), inline=True)
            embed.add_field(
                name="Reset In",
                value=f"{retry_after:.1f}s" if retry_after > 0 else "Ready",
                inline=True,
            )

            if hasattr(destination, "response"):
                await destination.response.send_message(embed=embed, ephemeral=True)
            else:
                await destination.send(embed=embed)
            return
        else:
            msg = "Invalid action. Use: reset, status"

        if hasattr(destination, "response"):
            await destination.response.send_message(msg, ephemeral=True)
        else:
            await destination.send(msg)

    # Prefix command: !shutdown
    @commands.command(name="shutdown", help="Shutdown the bot")
    @commands.is_owner()
    async def shutdown_prefix(self, ctx: commands.Context) -> None:
        """Shutdown the bot (prefix command, owner only)."""
        await ctx.send("🛑 Shutting down...")
        logger.info("Shutdown requested by owner")
        await self.bot.close()

    # Slash command: /shutdown
    @app_commands.command(name="shutdown", description="Shutdown the bot (owner only)")
    @is_owner_check()
    async def shutdown_slash(self, interaction: discord.Interaction) -> None:
        """Shutdown the bot (slash command, owner only)."""
        await interaction.response.send_message("🛑 Shutting down...", ephemeral=True)
        logger.info("Shutdown requested by owner")
        await self.bot.close()

    # Error handlers for admin commands
    async def cog_command_error(
        self,
        ctx: commands.Context,
        error: commands.CommandError,
    ) -> None:
        """Handle errors in admin commands."""
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You don't have permission to use this command.")
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send("I don't have the required permissions.")
        elif isinstance(error, commands.NotOwner):
            await ctx.send("This command is restricted to the bot owner.")
        else:
            logger.error(f"Admin command error: {error}", exc_info=error)
            await ctx.send("An error occurred.")

    async def cog_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        """Handle errors in admin slash commands."""
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message(
                "This command is restricted to the bot owner.", ephemeral=True
            )
        elif isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
        elif isinstance(error, app_commands.BotMissingPermissions):
            await interaction.response.send_message(
                "I don't have the required permissions.", ephemeral=True
            )
        else:
            logger.error(f"Admin slash command error: {error}", exc_info=error)
            if not interaction.response.is_done():
                await interaction.response.send_message("An error occurred.", ephemeral=True)
            else:
                await interaction.followup.send("An error occurred.", ephemeral=True)


async def setup(bot: ChatBot) -> None:
    """Setup function for loading the cog."""
    await bot.add_cog(AdminCommands(bot))