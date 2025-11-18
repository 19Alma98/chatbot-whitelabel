import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from openai.types.chat import ChatCompletionMessageParam
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi_app.postgres_models import ConversationMemory

logger = logging.getLogger("ragapp")


class ConversationService:
    """Service for managing conversation memory storage and retrieval."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    @staticmethod
    def generate_conversation_id() -> str:
        """Generate a unique conversation ID."""
        return str(uuid.uuid4())

    async def save_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        timestamp: datetime = datetime.now(timezone.utc),
    ) -> ConversationMemory:
        """
        Save a single message to the conversation memory.

        Args:
            conversation_id: The ID of the conversation
            role: The role of the message sender (user, assistant, system)
            content: The content of the message
            timestamp: Optional timestamp for the message (defaults to current time)

        Returns:
            The saved ConversationMemory object
        """
        message = ConversationMemory(
            conversation_id=conversation_id,
            message_role=role,
            message_content=content,
            message_timestamp=timestamp,
        )
        self.db_session.add(message)
        await self.db_session.commit()
        await self.db_session.refresh(message)
        logger.info(
            f"Saved message {message.message_id} to conversation {conversation_id}"
        )
        return message

    async def save_messages(
        self,
        conversation_id: str,
        messages: list[ChatCompletionMessageParam],
    ) -> list[ConversationMemory]:
        """
        Save multiple messages to the conversation memory.

        Args:
            conversation_id: The ID of the conversation
            messages: List of message objects with 'role' and 'content' keys

        Returns:
            List of saved ConversationMemory objects
        """
        saved_messages = []
        for message in messages:
            role = message["role"]
            content = message["content"]

            # Handle case where content might be a list (for multimodal messages)
            if isinstance(content, list):
                # Join all text content parts
                content = " ".join(
                    str(part.get("text", ""))
                    for part in content
                    if isinstance(part, dict) and "text" in part
                )

            saved_message = ConversationMemory(
                conversation_id=conversation_id,
                message_role=str(role),
                message_content=str(content),
            )
            self.db_session.add(saved_message)
            saved_messages.append(saved_message)

        await self.db_session.commit()
        for msg in saved_messages:
            await self.db_session.refresh(msg)

        logger.info(
            f"Saved {len(saved_messages)} messages to conversation {conversation_id}"
        )
        return saved_messages

    async def get_conversation_history(
        self,
        conversation_id: str,
        limit: Optional[int] = None,
    ) -> list[ConversationMemory]:
        """
        Retrieve conversation history for a given conversation ID.

        Args:
            conversation_id: The ID of the conversation
            limit: Optional limit on the number of messages to retrieve

        Returns:
            List of ConversationMemory objects ordered by timestamp (oldest first)
        """
        query = (
            select(ConversationMemory)
            .where(ConversationMemory.conversation_id == conversation_id)
            .order_by(ConversationMemory.message_timestamp)
        )

        if limit:
            query = query.limit(limit)

        result = await self.db_session.execute(query)
        messages = result.scalars().all()
        logger.info(
            f"Retrieved {len(messages)} messages for conversation {conversation_id}"
        )
        return list(messages)

    async def get_recent_messages(
        self,
        conversation_id: str,
        count: int = 10,
    ) -> list[ConversationMemory]:
        """
        Get the most recent messages from a conversation.

        Args:
            conversation_id: The ID of the conversation
            count: Number of recent messages to retrieve

        Returns:
            List of recent ConversationMemory objects ordered by timestamp (oldest first)
        """
        # Get the most recent messages in descending order, then reverse
        query = (
            select(ConversationMemory)
            .where(ConversationMemory.conversation_id == conversation_id)
            .order_by(desc(ConversationMemory.message_timestamp))
            .limit(count)
        )

        result = await self.db_session.execute(query)
        messages = list(result.scalars().all())
        # Reverse to get chronological order (oldest to newest)
        messages.reverse()
        logger.info(
            f"Retrieved {len(messages)} recent messages for conversation {conversation_id}"
        )
        return messages

    async def delete_conversation(self, conversation_id: str) -> int:
        """
        Delete all messages from a conversation.

        Args:
            conversation_id: The ID of the conversation to delete

        Returns:
            Number of messages deleted
        """
        messages = await self.get_conversation_history(conversation_id)
        count = len(messages)

        for message in messages:
            await self.db_session.delete(message)

        await self.db_session.commit()
        logger.info(f"Deleted {count} messages from conversation {conversation_id}")
        return count

    async def get_conversation_list(
        self,
        limit: int = 50,
    ) -> list[dict[str, str]]:
        """
        Get a list of unique conversation IDs with their most recent message timestamp.

        Args:
            limit: Maximum number of conversations to return

        Returns:
            List of dictionaries with conversation_id and last_message_timestamp
        """
        # This query gets distinct conversation IDs with their latest timestamp
        from sqlalchemy import func

        query = (
            select(
                ConversationMemory.conversation_id,
                func.max(ConversationMemory.message_timestamp).label("last_message"),
            )
            .group_by(ConversationMemory.conversation_id)
            .order_by(desc("last_message"))
            .limit(limit)
        )

        result = await self.db_session.execute(query)
        conversations = []
        for row in result:
            conversations.append(
                {
                    "conversation_id": row.conversation_id,
                    "last_message_timestamp": row.last_message.isoformat()
                    if row.last_message
                    else None,
                }
            )

        logger.info(f"Retrieved {len(conversations)} conversations")
        return conversations
