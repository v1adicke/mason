from datetime import UTC, datetime

from mason.telegram.models import Chat, Message

DEMO_CHAT_ID = -1001234567890


class DemoBackend:
    """serve a small fictional chat without Telegram credentials"""

    def __init__(self):
        self.chat = Chat(id=DEMO_CHAT_ID, title="Mason demo", kind="supergroup")
        texts = [
            "Let's work on the discrete maths homework this week",
            "The homework PDF is pinned in the study group",
            "We agreed to meet at 18:00 on Friday",
            "The discrete maths deadline is Monday",
        ]
        self.messages = [
            Message(
                chat=self.chat,
                message_id=number,
                sender="Demo student",
                sender_id=1,
                date=datetime(2026, 1, number, 12, tzinfo=UTC),
                text=text,
            )
            for number, text in enumerate(texts, start=1)
        ]

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def get_chat(self, chat_id: int) -> Chat:
        return self.chat

    async def read_messages(
        self,
        chat_id: int,
        *,
        limit: int,
        query: str | None = None,
        before_id: int = 0,
        date_to: datetime | None = None,
        sender_id: int | None = None,
    ) -> list[Message]:
        return [
            message
            for message in reversed(self.messages)
            if (not before_id or message.message_id < before_id)
            and (date_to is None or message.date < date_to)
            and (query is None or query.casefold() in message.text.casefold())
            and (sender_id is None or message.sender_id == sender_id)
        ][:limit]

    async def get_context(
        self, chat_id: int, message_id: int, before: int, after: int
    ) -> list[Message]:
        for index, message in enumerate(self.messages):
            if message.message_id == message_id:
                return self.messages[max(0, index - before) : index + after + 1]
        return []
