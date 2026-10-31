"""
Main Discord bot class with proper setup and lifecycle management.
"""
import asyncio
from typing import Optional

import discord
from discord.ext import commands
from loguru import logger

from config import settings
from logging_config import setup_logging
from services.llm_service import llm_service
from utils.rate_limiter import rate_limiter


class ChatBot(commands.Bot):
    """Main Discord chat bot class."""

    def __init__(self) -> None:
        # Configure intents - we need message content for reading messages
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.messages = True
        intents.dm_messages = True
        intents.reactions = True
        intents.members = True  # For member-related events

        super().__init__(
            command_prefix=settings.command_prefix,
            intents=intents,
            application_id=settings.discord_application_id,
            help_command=None,  # We'll implement custom help
            case_insensitive=True,
            strip_after_prefix=True,
        )

        self._startup_complete = False

    async def setup_hook(self) -> None:
        """Async initialization hook called before login."""
        logger.info("Setting up bot...")

        # Load cogs (command modules)
        await self._load_cogs()

        # Sync commands
        await self._sync_commands()

        self._startup_complete = True
        logger.info("Bot setup complete")

    async def _load_cogs(self) -> None:
        """Load all command cogs."""
        cogs = [
            "commands.general",
            "commands.admin",
            "commands.llm",
        ]

        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(f"Loaded cog: {cog}")
            except Exception as e:
                logger.error(f"Failed to load cog {cog}: {e}")

    async def _sync_commands(self) -> None:
        """Sync slash commands with Discord."""
        try:
            if settings.discord_guild_id:
                # Sync to specific guild for faster development
                guild = discord.Object(id=settings.discord_guild_id)
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
                logger.info(f"Synced commands to guild {settings.discord_guild_id}")
            else:
                # Global sync (can take up to 1 hour to propagate)
                await self.tree.sync()
                logger.info("Synced commands globally")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")

    async def on_ready(self) -> None:
        """Called when bot is ready and connected."""
        if not self._startup_complete:
            return

        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guilds")

        # Set bot presence
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.playing,
                name=settings.bot_status,
            )
        )

        # Log guild info
        for guild in self.guilds:
            logger.info(f"  - {guild.name} (ID: {guild.id}, Members: {guild.member_count})")

    async def on_message(self, message: discord.Message) -> None:
        """Handle incoming messages."""
        # Ignore messages from bots (including ourselves)
        if message.author.bot:
            return

        # Ignore system messages
        if message.type != discord.MessageType.default:
            return

        # Process commands first
        await self.process_commands(message)

        # Handle auto-response for non-command messages
        await self._handle_auto_response(message)

    async def _handle_auto_response(self, message: discord.Message) -> None:
        """Handle automatic responses to non-command messages."""
        # Skip if message starts with command prefix (already processed)
        if message.content.startswith(settings.command_prefix):
            return

        # Skip if it's a slash command interaction (handled separately)
        # This is a fallback for messages not caught by command processor

        # Check rate limit
        if not rate_limiter.is_allowed(message.author.id):
            retry_after = rate_limiter.get_retry_after(message.author.id)
            logger.warning(
                f"Rate limited user {message.author} ({message.author.id}), "
                f"retry after {retry_after:.1f}s"
            )
            # Optionally notify user (but don't spam)
            return

        # Check if bot is mentioned or in DM
        is_mentioned = self.user in message.mentions
        is_dm = isinstance(message.channel, discord.DMChannel)

        # Respond if mentioned, in DM, or configured to respond to all messages
        # For now, respond to mentions and DMs only to avoid spam
        if not is_mentioned and not is_dm:
            return

        # Remove bot mention from content
        content = message.content
        if is_mentioned:
            content = content.replace(f"<@{self.user.id}>", "").replace(f"<@!{self.user.id}>", "").strip()

        if not content:
            return

        # Show typing indicator
        async with message.channel.typing():
            try:
                response = await self._generate_llm_response(message, content)
                if response:
                    # Split long responses
                    await self._send_long_message(message.channel, response)
            except Exception as e:
                logger.error(f"Error generating response: {e}")
                await message.reply("Sorry, I encountered an error processing your message.")

    async def _generate_llm_response(
        self,
        message: discord.Message,
        user_content: str,
    ) -> Optional[str]:
        """Generate LLM response with conversation context."""
        from utils.conversation import conversation_manager

        is_dm = isinstance(message.channel, discord.DMChannel)
        channel_id = message.channel.id
        user_id = message.author.id

        # Get conversation history
        history = conversation_manager.get_history(
            channel_id=channel_id,
            user_id=user_id,
            is_dm=is_dm,
        )

        # Generate response
        response = await llm_service.generate_response(
            user_message=user_content,
            conversation_history=history,
        )

        # Store in conversation history
        conversation_manager.add_message(
            channel_id=channel_id,
            user_id=user_id,
            role="user",
            content=user_content,
            is_dm=is_dm,
        )
        conversation_manager.add_message(
            channel_id=channel_id,
            user_id=user_id,
            role="assistant",
            content=response,
            is_dm=is_dm,
        )

        return response

    async def _send_long_message(
        self,
        channel: discord.abc.Messageable,
        content: str,
        reference: Optional[discord.Message] = None,
    ) -> None:
        """Send a message, splitting if longer than Discord's limit."""
        MAX_LENGTH = 2000

        if len(content) <= MAX_LENGTH:
            await channel.send(content, reference=reference, mention_author=False)
            return

        # Split into chunks
        chunks = []
        current_chunk = ""

        for line in content.split("\n"):
            if len(current_chunk) + len(line) + 1 > MAX_LENGTH:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = line
            else:
                if current_chunk:
                    current_chunk += "\n" + line
                else:
                    current_chunk = line

        if current_chunk:
            chunks.append(current_chunk)

        # Send chunks
        for i, chunk in enumerate(chunks):
            if i == 0:
                await channel.send(chunk, reference=reference, mention_author=False)
            else:
                await channel.send(chunk, mention_author=False)

    async def on_command_error(
        self,
        context: commands.Context,
        error: commands.CommandError,
    ) -> None:
        """Global command error handler."""
        # Ignore certain errors
        if isinstance(error, commands.CommandNotFound):
            return

        if isinstance(error, commands.MissingRequiredArgument):
            await context.send(f"Missing required argument: {error.param.name}")
            return

        if isinstance(error, commands.BadArgument):
            await context.send(f"Invalid argument: {error}")
            return

        if isinstance(error, commands.CommandOnCooldown):
            await context.send(
                f"This command is on cooldown. Try again in {error.retry_after:.1f}s."
            )
            return

        if isinstance(error, commands.MissingPermissions):
            await context.send("You don't have permission to use this command.")
            return

        if isinstance(error, commands.BotMissingPermissions):
            await context.send("I don't have the required permissions to execute this command.")
            return

        # Log unexpected errors
        logger.error(f"Command error in {context.command}: {error}", exc_info=error)
        await context.send("An error occurred while executing the command.")

    async def on_error(self, event: str, *args, **kwargs) -> None:
        """Global event error handler."""
        logger.error(f"Error in event {event}", exc_info=True)

    async def close(self) -> None:
        """Cleanup on shutdown."""
        logger.info("Shutting down bot...")
        await llm_service.close()
        await super().close()
        logger.info("Bot shutdown complete")


async def main() -> None:
    """Main entry point."""
    setup_logging()

    bot = ChatBot()

    try:
        await bot.start(settings.discord_token)
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
    finally:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())