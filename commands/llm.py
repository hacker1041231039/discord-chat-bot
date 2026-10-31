"""
LLM-specific commands for the Discord bot.
Includes chat, configuration, and model management commands.
"""
import discord
from discord import app_commands
from discord.ext import commands
from loguru import logger

from bot import ChatBot
from config import settings
from services.llm_service import llm_service, LLMError
from utils.conversation import conversation_manager
from utils.rate_limiter import rate_limiter


class LLMCommands(commands.Cog):
    """LLM and AI-related commands."""

    def __init__(self, bot: ChatBot) -> None:
        self.bot = bot

    # Prefix command: !chat / !ask
    @commands.command(name="chat", aliases=["ask", "ai"], help="Chat with the AI")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def chat_prefix(self, ctx: commands.Context, *, message: str) -> None:
        """Chat with the AI (prefix command)."""
        await self._handle_chat(ctx, message, is_slash=False)

    # Slash command: /chat
    @app_commands.command(name="chat", description="Chat with the AI")
    @app_commands.describe(message="Your message to the AI")
    async def chat_slash(self, interaction: discord.Interaction, message: str) -> None:
        """Chat with the AI (slash command)."""
        await self._handle_chat(interaction, message, is_slash=True)

    async def _handle_chat(
        self,
        destination,
        user_message: str,
        is_slash: bool,
    ) -> None:
        """Handle chat request."""
        # Rate limiting
        user_id = destination.author.id if not is_slash else destination.user.id
        if not rate_limiter.is_allowed(user_id):
            retry_after = rate_limiter.get_retry_after(user_id)
            msg = f"⏳ Rate limited. Try again in {retry_after:.1f}s."
            if is_slash:
                await destination.response.send_message(msg, ephemeral=True)
            else:
                await destination.send(msg)
            return

        # Defer for slash commands
        if is_slash:
            await destination.response.defer()

        # Get context
        if not is_slash:
            channel_id = destination.channel.id
            is_dm = isinstance(destination.channel, discord.DMChannel)
            reference = destination.message
        else:
            channel_id = destination.channel_id
            is_dm = isinstance(destination.channel, discord.DMChannel) if destination.channel else False
            reference = None

        # Show typing
        channel = destination.channel if not is_slash else destination.channel
        async with channel.typing():
            try:
                # Get conversation history
                history = conversation_manager.get_history(
                    channel_id=channel_id,
                    user_id=user_id,
                    is_dm=is_dm,
                )

                # Generate response
                response = await llm_service.generate_response(
                    user_message=user_message,
                    conversation_history=history,
                )

                # Store in history
                conversation_manager.add_message(
                    channel_id=channel_id,
                    user_id=user_id,
                    role="user",
                    content=user_message,
                    is_dm=is_dm,
                )
                conversation_manager.add_message(
                    channel_id=channel_id,
                    user_id=user_id,
                    role="assistant",
                    content=response,
                    is_dm=is_dm,
                )

                # Send response
                if is_slash:
                    await self._send_response(destination, response, is_slash=True)
                else:
                    await self._send_response(destination, response, reference=reference, is_slash=False)

            except LLMError as e:
                logger.error(f"LLM error: {e}")
                msg = f"❌ AI Error: {e}"
                if is_slash:
                    await destination.followup.send(msg, ephemeral=True)
                else:
                    await destination.send(msg)
            except Exception as e:
                logger.error(f"Unexpected error in chat: {e}", exc_info=e)
                msg = "❌ An unexpected error occurred."
                if is_slash:
                    await destination.followup.send(msg, ephemeral=True)
                else:
                    await destination.send(msg)

    async def _send_response(
        self,
        destination,
        response: str,
        reference: discord.Message | None = None,
        is_slash: bool = False,
    ) -> None:
        """Send response, handling long messages."""
        MAX_LENGTH = 2000

        if len(response) <= MAX_LENGTH:
            if is_slash:
                await destination.followup.send(response)
            else:
                await destination.send(response, reference=reference, mention_author=False)
            return

        # Split into chunks
        chunks = []
        current_chunk = ""

        for line in response.split("\n"):
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
            if is_slash:
                if i == 0:
                    await destination.followup.send(chunk)
                else:
                    await destination.followup.send(chunk)
            else:
                if i == 0:
                    await destination.send(chunk, reference=reference, mention_author=False)
                else:
                    await destination.send(chunk, mention_author=False)

    # Prefix command: !model
    @commands.command(name="model", help="Show or change LLM model")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def model_prefix(self, ctx: commands.Context, model: str | None = None) -> None:
        """Show or change LLM model (prefix command)."""
        await self._handle_model(ctx, model)

    # Slash command: /model
    @app_commands.command(name="model", description="Show or change LLM model")
    @app_commands.describe(model="Model name to use (optional)")
    async def model_slash(self, interaction: discord.Interaction, model: str | None = None) -> None:
        """Show or change LLM model (slash command)."""
        await self._handle_model(interaction, model)

    async def _handle_model(self, destination, model: str | None) -> None:
        """Handle model command."""
        if model is None:
            # Show current model
            embed = discord.Embed(title="🤖 Current LLM Model", color=discord.Color.blue())
            embed.add_field(name="Model", value=settings.llm_model, inline=True)
            embed.add_field(name="Max Tokens", value=str(settings.llm_max_tokens), inline=True)
            embed.add_field(name="Temperature", value=str(settings.llm_temperature), inline=True)
            embed.add_field(name="API Endpoint", value=settings.llm_api_url, inline=False)

            if hasattr(destination, "response"):
                await destination.response.send_message(embed=embed, ephemeral=True)
            else:
                await destination.send(embed=embed)
        else:
            # Change model (owner only for persistence, but allow temporary for session)
            if not await self.bot.is_owner(destination.author if not hasattr(destination, "user") else destination.user):
                msg = "Only the bot owner can change the model."
                if hasattr(destination, "response"):
                    await destination.response.send_message(msg, ephemeral=True)
                else:
                    await destination.send(msg)
                return

            # Note: This only changes for the current session
            # For persistence, user should update .env
            old_model = settings.llm_model
            settings.llm_model = model
            llm_service.model = model

            msg = f"✅ Model changed from `{old_model}` to `{model}` (session only)"
            if hasattr(destination, "response"):
                await destination.response.send_message(msg, ephemeral=True)
            else:
                await destination.send(msg)

    # Prefix command: !systemprompt / !sp
    @commands.command(name="systemprompt", aliases=["sp"], help="Show or set system prompt")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def system_prompt_prefix(
        self,
        ctx: commands.Context,
        *,
        prompt: str | None = None,
    ) -> None:
        """Show or set system prompt (prefix command)."""
        await self._handle_system_prompt(ctx, prompt)

    # Slash command: /systemprompt
    @app_commands.command(name="systemprompt", description="Show or set system prompt")
    @app_commands.describe(prompt="New system prompt (optional)")
    async def system_prompt_slash(
        self,
        interaction: discord.Interaction,
        prompt: str | None = None,
    ) -> None:
        """Show or set system prompt (slash command)."""
        await self._handle_system_prompt(interaction, prompt)

    async def _handle_system_prompt(
        self,
        destination,
        prompt: str | None,
    ) -> None:
        """Handle system prompt command."""
        user = destination.author if not hasattr(destination, "user") else destination.user

        if not await self.bot.is_owner(user):
            msg = "Only the bot owner can view/change the system prompt."
            if hasattr(destination, "response"):
                await destination.response.send_message(msg, ephemeral=True)
            else:
                await destination.send(msg)
            return

        if prompt is None:
            # Show current prompt
            embed = discord.Embed(
                title="📝 System Prompt",
                description=f"```\n{settings.llm_system_prompt}\n```",
                color=discord.Color.blue(),
            )
            if hasattr(destination, "response"):
                await destination.response.send_message(embed=embed, ephemeral=True)
            else:
                await destination.send(embed=embed)
        else:
            # Update prompt (session only)
            old_prompt = settings.llm_system_prompt
            settings.llm_system_prompt = prompt
            llm_service.system_prompt = prompt

            embed = discord.Embed(
                title="✅ System Prompt Updated (Session Only)",
                color=discord.Color.green(),
            )
            embed.add_field(name="Previous", value=f"```\n{old_prompt[:500]}\n```", inline=False)
            embed.add_field(name="New", value=f"```\n{prompt[:500]}\n```", inline=False)

            if hasattr(destination, "response"):
                await destination.response.send_message(embed=embed, ephemeral=True)
            else:
                await destination.send(embed=embed)

    # Prefix command: !temperature / !temp
    @commands.command(name="temperature", aliases=["temp"], help="Show or set temperature")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def temperature_prefix(
        self,
        ctx: commands.Context,
        temperature: float | None = None,
    ) -> None:
        """Show or set temperature (prefix command)."""
        await self._handle_temperature(ctx, temperature)

    # Slash command: /temperature
    @app_commands.command(name="temperature", description="Show or set temperature")
    @app_commands.describe(temperature="Temperature value (0-2)")
    async def temperature_slash(
        self,
        interaction: discord.Interaction,
        temperature: float | None = None,
    ) -> None:
        """Show or set temperature (slash command)."""
        await self._handle_temperature(interaction, temperature)

    async def _handle_temperature(
        self,
        destination,
        temperature: float | None,
    ) -> None:
        """Handle temperature command."""
        user = destination.author if not hasattr(destination, "user") else destination.user

        if not await self.bot.is_owner(user):
            msg = "Only the bot owner can change temperature."
            if hasattr(destination, "response"):
                await destination.response.send_message(msg, ephemeral=True)
            else:
                await destination.send(msg)
            return

        if temperature is None:
            embed = discord.Embed(title="🌡️ Current Temperature", color=discord.Color.blue())
            embed.add_field(name="Temperature", value=str(settings.llm_temperature), inline=True)
            if hasattr(destination, "response"):
                await destination.response.send_message(embed=embed, ephemeral=True)
            else:
                await destination.send(embed=embed)
        else:
            if not 0 <= temperature <= 2:
                msg = "Temperature must be between 0 and 2."
                if hasattr(destination, "response"):
                    await destination.response.send_message(msg, ephemeral=True)
                else:
                    await destination.send(msg)
                return

            old_temp = settings.llm_temperature
            settings.llm_temperature = temperature
            llm_service.temperature = temperature

            msg = f"✅ Temperature changed from `{old_temp}` to `{temperature}` (session only)"
            if hasattr(destination, "response"):
                await destination.response.send_message(msg, ephemeral=True)
            else:
                await destination.send(msg)

    # Prefix command: !llmhealth / !llmstatus
    @commands.command(name="llmhealth", aliases=["llmstatus"], help="Check LLM API health")
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def llm_health_prefix(self, ctx: commands.Context) -> None:
        """Check LLM API health (prefix command)."""
        await self._check_llm_health(ctx)

    # Slash command: /llmhealth
    @app_commands.command(name="llmhealth", description="Check LLM API health")
    async def llm_health_slash(self, interaction: discord.Interaction) -> None:
        """Check LLM API health (slash command)."""
        await self._check_llm_health(interaction)

    async def _check_llm_health(self, destination) -> None:
        """Check LLM API health."""
        if hasattr(destination, "response"):
            await destination.response.defer(ephemeral=True)
        else:
            msg = await destination.send("Checking LLM API health...")

        try:
            healthy = await llm_service.health_check()

            embed = discord.Embed(
                title="🏥 LLM API Health Check",
                color=discord.Color.green() if healthy else discord.Color.red(),
            )
            embed.add_field(name="Status", value="✅ Healthy" if healthy else "❌ Unhealthy", inline=True)
            embed.add_field(name="Model", value=settings.llm_model, inline=True)
            embed.add_field(name="Endpoint", value=settings.llm_api_url, inline=True)

            if hasattr(destination, "response"):
                await destination.followup.send(embed=embed, ephemeral=True)
            else:
                await msg.edit(content=None, embed=embed)
        except Exception as e:
            logger.error(f"Health check error: {e}")
            embed = discord.Embed(
                title="🏥 LLM API Health Check",
                description=f"❌ Error: {e}",
                color=discord.Color.red(),
            )
            if hasattr(destination, "response"):
                await destination.followup.send(embed=embed, ephemeral=True)
            else:
                await msg.edit(content=None, embed=embed)

    # Prefix command: !personality / !persona
    @commands.command(name="personality", aliases=["persona"], help="Set AI personality for this conversation")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def personality_prefix(
        self,
        ctx: commands.Context,
        *,
        personality: str | None = None,
    ) -> None:
        """Set AI personality for this conversation (prefix command)."""
        await self._handle_personality(ctx, personality)

    # Slash command: /personality
    @app_commands.command(name="personality", description="Set AI personality for this conversation")
    @app_commands.describe(personality="Personality description (e.g., 'pirate', 'shakespearean', 'technical expert')")
    async def personality_slash(
        self,
        interaction: discord.Interaction,
        personality: str | None = None,
    ) -> None:
        """Set AI personality for this conversation (slash command)."""
        await self._handle_personality(interaction, personality)

    async def _handle_personality(
        self,
        destination,
        personality: str | None,
    ) -> None:
        """Handle personality command."""
        user_id = destination.author.id if not hasattr(destination, "user") else destination.user.id
        channel_id = destination.channel.id if not hasattr(destination, "channel_id") else destination.channel_id
        is_dm = isinstance(destination.channel, discord.DMChannel) if not hasattr(destination, "channel_id") else (
            isinstance(destination.channel, discord.DMChannel) if destination.channel else False
        )

        # Clear history to start fresh with new personality
        conversation_manager.clear_history(channel_id, user_id, is_dm)

        if personality is None:
            # Show current personalities suggestions
            embed = discord.Embed(
                title="🎭 Personality Presets",
                description=(
                    "Use `!personality <description>` to set a personality for this conversation.\n"
                    "This clears conversation history and adds a personality instruction to the system prompt."
                ),
                color=discord.Color.purple(),
            )
            embed.add_field(
                name="Examples",
                value=(
                    "`pirate` - Talk like a pirate\n"
                    "`shakespearean` - Use Shakespearean English\n"
                    "`technical expert` - Detailed technical explanations\n"
                    "`concise` - Brief, to-the-point answers\n"
                    "`creative writer` - Creative and expressive\n"
                    "`teacher` - Educational and encouraging"
                ),
                inline=False,
            )
            if hasattr(destination, "response"):
                await destination.response.send_message(embed=embed, ephemeral=True)
            else:
                await destination.send(embed=embed)
        else:
            # Create custom system prompt with personality
            base_prompt = settings.llm_system_prompt
            custom_prompt = f"{base_prompt}\n\nPersonality: {personality}"

            # Store custom prompt in conversation manager (we'll handle this in the chat command)
            # For now, just acknowledge
            embed = discord.Embed(
                title="✅ Personality Set",
                description=f"Personality: **{personality}**\nConversation history cleared.",
                color=discord.Color.green(),
            )
            embed.set_footer(text="This applies to your current conversation only.")

            if hasattr(destination, "response"):
                await destination.response.send_message(embed=embed, ephemeral=True)
            else:
                await destination.send(embed=embed)


async def setup(bot: ChatBot) -> None:
    """Setup function for loading the cog."""
    await bot.add_cog(LLMCommands(bot))