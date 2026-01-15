"""
Conversation history manager with Redis-first storage.
"""

import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class ConversationManager:
    """
    Conversation History Manager.

    Features:
    - Redis-first storage with in-memory fallback
    - Automatic conversation creation
    - Token-aware context windows
    - 24-hour TTL for conversations
    - Metadata tracking (language, topics, sources)
    """

    def __init__(self, redis_client=None, max_history: int = 20, ttl: int = 86400):
        """
        Initialize ConversationManager.

        Args:
            redis_client: Redis client (can be None)
            max_history: Maximum messages per conversation (default: 20)
            ttl: Time-to-live in seconds (default: 24 hours)
        """
        self.redis = redis_client
        self.max_history = max_history
        self.ttl = ttl
        self.in_memory_store = {}

        self.stats = {
            'total_conversations': 0,
            'total_messages': 0,
            'redis_hits': 0,
            'redis_misses': 0,
            'errors': 0
        }

        logger.info(f"ConversationManager initialized (Redis: {'available' if redis_client else 'fallback to memory'})")

    def create_conversation(
        self,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Create new conversation or get existing.

        Args:
            conversation_id: Custom ID or auto-generate
            user_id: Optional user identifier
            metadata: Optional initial metadata

        Returns:
            Conversation dict with id, timestamps, messages
        """
        conv_id = conversation_id or f"conv_{uuid4().hex[:12]}"

        existing = self._load_conversation(conv_id)
        if existing:
            logger.debug(f"Conversation {conv_id} already exists")
            return existing

        conversation = {
            "id": conv_id,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "messages": [],
            "metadata": metadata or {
                "total_messages": 0,
                "languages_used": set(),
                "topics": [],
                "sources_used": set()
            }
        }

        self._save_conversation(conv_id, conversation)
        self.stats['total_conversations'] += 1

        logger.info(f"Created conversation: {conv_id}")
        return conversation

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Add message to conversation.

        Args:
            conversation_id: Conversation ID
            role: 'user' or 'assistant'
            content: Message content
            metadata: Optional metadata (language, sources, etc.)

        Returns:
            Success boolean
        """
        try:
            conversation = self._load_conversation(conversation_id)
            if not conversation:
                conversation = self.create_conversation(conversation_id)

            message = {
                "role": role,
                "content": content,
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": metadata or {}
            }

            conversation["messages"].append(message)
            conversation["updated_at"] = datetime.utcnow().isoformat()

            conversation["metadata"]["total_messages"] = len(conversation["messages"])

            if metadata:
                if "language" in metadata:
                    if isinstance(conversation["metadata"]["languages_used"], set):
                        conversation["metadata"]["languages_used"] = list(conversation["metadata"]["languages_used"])
                    if metadata["language"] not in conversation["metadata"]["languages_used"]:
                        conversation["metadata"]["languages_used"].append(metadata["language"])

                if "sources" in metadata:
                    if isinstance(conversation["metadata"]["sources_used"], set):
                        conversation["metadata"]["sources_used"] = list(conversation["metadata"]["sources_used"])
                    for source in metadata["sources"]:
                        if source not in conversation["metadata"]["sources_used"]:
                            conversation["metadata"]["sources_used"].append(source)

            if len(conversation["messages"]) > self.max_history:
                removed_count = len(conversation["messages"]) - self.max_history
                conversation["messages"] = conversation["messages"][-self.max_history:]
                logger.debug(f"Trimmed {removed_count} old messages from {conversation_id}")

            self._save_conversation(conversation_id, conversation)
            self.stats['total_messages'] += 1

            return True

        except Exception as e:
            logger.error(f"Failed to add message to {conversation_id}: {e}")
            self.stats['errors'] += 1
            return False

    def get_history(
        self,
        conversation_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get conversation message history.

        Args:
            conversation_id: Conversation ID
            limit: Max messages to return (default: all)

        Returns:
            List of message dicts (newest last)
        """
        conversation = self._load_conversation(conversation_id)
        if not conversation:
            return []

        messages = conversation.get("messages", [])

        if limit:
            messages = messages[-limit:]

        return messages

    def get_context_window(
        self,
        conversation_id: str,
        max_tokens: int = 2000,
        format: str = "string"
    ) -> Any:
        """
        Get formatted conversation context for LLM.

        Args:
            conversation_id: Conversation ID
            max_tokens: Approximate token limit (chars * 4)
            format: 'string' (formatted text) or 'list' (message dicts)

        Returns:
            Formatted context string or list of messages
        """
        messages = self.get_history(conversation_id)

        if format == "list":
            max_chars = max_tokens * 4
            result = []
            total_chars = 0

            for msg in reversed(messages):
                msg_chars = len(msg['content']) + 50
                if total_chars + msg_chars > max_chars:
                    break
                result.insert(0, msg)
                total_chars += msg_chars

            return result

        context_parts = []
        total_chars = 0
        max_chars = max_tokens * 4

        for msg in reversed(messages):
            msg_text = f"{msg['role'].upper()}: {msg['content']}\n"
            if total_chars + len(msg_text) > max_chars:
                break
            context_parts.insert(0, msg_text)
            total_chars += len(msg_text)

        return "\n".join(context_parts)

    def clear_conversation(self, conversation_id: str) -> bool:
        """Delete conversation completely"""
        try:
            if self.redis:
                key = f"conversation:{conversation_id}"
                self.redis.delete(key)

            if conversation_id in self.in_memory_store:
                del self.in_memory_store[conversation_id]

            logger.info(f"Cleared conversation: {conversation_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to clear {conversation_id}: {e}")
            return False

    def get_conversation_metadata(self, conversation_id: str) -> Optional[Dict]:
        """Get conversation metadata without messages"""
        conversation = self._load_conversation(conversation_id)
        if not conversation:
            return None

        return {
            "id": conversation["id"],
            "created_at": conversation["created_at"],
            "updated_at": conversation["updated_at"],
            "user_id": conversation.get("user_id"),
            "metadata": conversation["metadata"]
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get manager statistics"""
        total_requests = self.stats['redis_hits'] + self.stats['redis_misses']
        hit_rate = (self.stats['redis_hits'] / total_requests * 100) if total_requests > 0 else 0

        return {
            **self.stats,
            'cache_hit_rate': round(hit_rate, 2),
            'in_memory_conversations': len(self.in_memory_store)
        }

    def _load_conversation(self, conversation_id: str) -> Optional[Dict]:
        """Load from Redis or memory"""
        if self.redis:
            try:
                key = f"conversation:{conversation_id}"
                data = self.redis.get(key)
                if data:
                    self.stats['redis_hits'] += 1
                    if isinstance(data, bytes):
                        conversation = json.loads(data.decode('utf-8'))
                    else:
                        conversation = json.loads(data)

                    if "metadata" in conversation:
                        for key in ["languages_used", "sources_used"]:
                            if key in conversation["metadata"] and isinstance(conversation["metadata"][key], list):
                                conversation["metadata"][key] = set(conversation["metadata"][key])

                    return conversation
                else:
                    self.stats['redis_misses'] += 1
            except Exception as e:
                logger.warning(f"Redis load failed for {conversation_id}: {e}")
                self.stats['errors'] += 1

        return self.in_memory_store.get(conversation_id)

    def _save_conversation(self, conversation_id: str, conversation: Dict):
        """Save to Redis and memory"""
        conv_copy = json.loads(json.dumps(conversation, default=str))
        if "metadata" in conv_copy:
            for key in ["languages_used", "sources_used"]:
                if key in conv_copy["metadata"] and isinstance(conv_copy["metadata"][key], set):
                    conv_copy["metadata"][key] = list(conv_copy["metadata"][key])

        if self.redis:
            try:
                key = f"conversation:{conversation_id}"
                self.redis.setex(
                    key,
                    self.ttl,
                    json.dumps(conv_copy, ensure_ascii=False)
                )
            except Exception as e:
                logger.warning(f"Redis save failed for {conversation_id}: {e}")
                self.stats['errors'] += 1

        self.in_memory_store[conversation_id] = conversation