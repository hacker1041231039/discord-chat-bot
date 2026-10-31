"""
LLM Service for integrating with various LLM APIs.
Supports OpenAI-compatible APIs (OpenRouter, Together.ai, Groq, etc.)
"""
import json
from typing import Any

import aiohttp
from loguru import logger
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import settings


class LLMService:
    """Service for communicating with LLM APIs."""

    def __init__(self) -> None:
        self.api_url = settings.llm_api_url
        self.api_key = settings.llm_api_key
        self.model = settings.llm_model
        self.max_tokens = settings.llm_max_tokens
        self.temperature = settings.llm_temperature
        self.system_prompt = settings.llm_system_prompt
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=60)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self) -> None:
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((aiohttp.ClientError, TimeoutError)),
    )
    async def generate_response(
        self,
        user_message: str,
        conversation_history: list[dict[str, str]] | None = None,
        system_prompt: str | None = None,
    ) -> str:
        """
        Generate a response from the LLM.

        Args:
            user_message: The user's message
            conversation_history: Optional list of previous messages
            system_prompt: Optional custom system prompt

        Returns:
            The LLM's response text

        Raises:
            LLMError: If the API request fails
        """
        if not self.api_key:
            raise LLMError("LLM API key not configured")

        messages = []

        # Add system prompt
        prompt = system_prompt or self.system_prompt
        messages.append({"role": "system", "content": prompt})

        # Add conversation history
        if conversation_history:
            messages.extend(conversation_history)

        # Add current user message
        messages.append({"role": "user", "content": user_message})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": False,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        session = await self._get_session()

        try:
            async with session.post(
                self.api_url, json=payload, headers=headers
            ) as response:
                if response.status == 401:
                    raise LLMAuthError("Invalid API key")
                elif response.status == 429:
                    raise LLMRateLimitError("Rate limited by LLM provider")
                elif response.status >= 500:
                    raise LLMServerError(f"LLM server error: {response.status}")
                elif response.status != 200:
                    error_text = await response.text()
                    raise LLMError(f"API error ({response.status}): {error_text}")

                data = await response.json()
                return self._extract_response(data)

        except aiohttp.ClientError as e:
            logger.error(f"LLM API connection error: {e}")
            raise LLMError(f"Connection error: {e}") from e
        except json.JSONDecodeError as e:
            logger.error(f"LLM API response parse error: {e}")
            raise LLMError(f"Invalid response format: {e}") from e

    def _extract_response(self, data: dict[str, Any]) -> str:
        """Extract response text from API response."""
        # OpenAI-compatible format
        if "choices" in data and data["choices"]:
            choice = data["choices"][0]
            if "message" in choice and "content" in choice["message"]:
                return choice["message"]["content"].strip()
            if "text" in choice:
                return choice["text"].strip()

        # Fallback for other formats
        if "response" in data:
            return str(data["response"]).strip()

        raise LLMError(f"Unexpected response format: {data}")

    async def health_check(self) -> bool:
        """Check if LLM API is accessible."""
        if not self.api_key:
            return False

        try:
            await self.generate_response("ping", max_tokens=5)
            return True
        except Exception as e:
            logger.warning(f"LLM health check failed: {e}")
            return False


class LLMError(Exception):
    """Base exception for LLM errors."""
    pass


class LLMAuthError(LLMError):
    """Authentication error with LLM API."""
    pass


class LLMRateLimitError(LLMError):
    """Rate limit error from LLM API."""
    pass


class LLMServerError(LLMError):
    """Server error from LLM API."""
    pass


# Global LLM service instance
llm_service = LLMService()