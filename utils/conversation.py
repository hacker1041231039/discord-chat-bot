"""
Conversation history manager for maintaining context across messages.
Stores per-channel/user conversation history with configurable limits.
"""
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from loguru import logger


@dataclass
class ConversationEntry:
    """Single conversation entry."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: float


class ConversationManager:
    """Manages conversation history for channels and users."""

    def __init__(
        self,
        max_history_per_channel: int = 20,
        max_history_per_user: int = 10,
        max_age_seconds: int = 3600,  # 1 hour
    ) -> None:
        self.max_history_per_channel = max_history_per_channel
        self.max_history_per_user = max_history_per_user
        self.max_age_seconds = max_age_seconds

        # Channel-based history (for server channels)
        self._channel_history: Dict[int, List[ConversationEntry]] = defaultdict(list)
        # User-based history (for DMs)
        self._user_history: Dict[int, List[ConversationEntry]] = defaultdict(list)

    def add_message(
        self,
        channel_id: int,
        user_id: int,
        role: str,
        content: str,
        is_dm: bool = False,
    ) -> None:
        """Add a message to conversation history."""
        import time
        entry = ConversationEntry(
            role=role,
            content=content,
            timestamp=time.time(),
        )

        if is_dm:
            history = self._user_history[user_id]
            history.append(entry)
            self._trim_history(history, self.max_history_per_user)
        else:
            history = self._channel_history[channel_id]
            history.append(entry)
            self._trim_history(history, self.max_history_per_channel)

    def get_history(
        self,
        channel_id: int,
        user_id: int,
        is_dm: bool = False,
        include_system: bool = False,
    ) -> List[dict]:
        """
        Get conversation history formatted for LLM API.

        Args:
            channel_id: Discord channel ID
            user_id: Discord user ID
            is_dm: Whether this is a DM
            include_system: Whether to include system prompt (handled separately)

        Returns:
            List of message dicts for LLM API
        """
        history = self._user_history[user_id] if is_dm else self._channel_history[channel_id]
        self._cleanup_old(history)

        return [
            {"role": entry.role, "content": entry.content}
            for entry in history
        ]

    def clear_history(self, channel_id: int, user_id: int, is_dm: bool = False) -> None:
        """Clear conversation history."""
        if is_dm:
            self._user_history[user_id].clear()
        else:
            self._channel_history[channel_id].clear()

    def _trim_history(self, history: List[ConversationEntry], max_len: int) -> None:
        """Trim history to maximum length."""
        if len(history) > max_len:
            # Keep the most recent messages
            excess = len(history) - max_len
            del history[:excess]

    def _cleanup_old(self, history: List[ConversationEntry]) -> None:
        """Remove entries older than max_age_seconds."""
        import time
        cutoff = time.time() - self.max_age_seconds
        # Remove old entries from the beginning
        while history and history[0].timestamp < cutoff:
            history.pop(0)


# Global conversation manager instance
conversation_manager = ConversationManager()