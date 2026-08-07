import asyncio
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from uuid import uuid4

from asagent.chat.service import ChatService
from asagent.core.conversation import Conversation
from asagent.core.ids import ConversationId, MessageId, UserId
from asagent.models.contracts import (
    ModelEvent,
    ModelMessageRole,
    ModelRequest,
    ModelResponse,
)
from asagent.storage.in_memory_conversation_repository import (
    InMemoryConversationRepository,
)


class _EchoModelProvider:
    async def complete(self, request: ModelRequest) -> ModelResponse:
        content = next(
            (
                message.content
                for message in reversed(request.messages)
                if message.role is ModelMessageRole.USER
            ),
            "",
        )
        return ModelResponse(text=f"Echo: {content}", tool_calls=())

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelEvent]:
        response = await self.complete(request)
        if response.text is not None:
            yield ModelEvent(event_type="model.delta", text_delta=response.text)


async def run_chat(
    *,
    chat_service: ChatService,
    conversation: Conversation,
    model_name: str,
    system_prompt: str,
    read_line: Callable[[str], str],
    write_line: Callable[[str], None],
) -> None:
    write_line("asAgent development chat. Type 'exit' to quit.")

    while True:
        try:
            content = read_line("You: ")
        except EOFError:
            return

        if content.strip().lower() in {"exit", "quit"}:
            return

        if not content.strip():
            continue

        try:
            reply = await chat_service.send(
                conversation=conversation,
                content=content,
                model_name=model_name,
                system_prompt=system_prompt,
            )
        except Exception as error:
            write_line(f"Error: {error}")
            continue

        write_line(f"asAgent: {reply.content}")


def now() -> datetime:
    return datetime.now(UTC)


def new_conversation_id() -> ConversationId:
    return ConversationId(f"conv_{uuid4().hex}")


def new_message_id() -> MessageId:
    return MessageId(f"msg_{uuid4().hex}")


def main() -> None:
    created_at = now()
    conversation = Conversation(
        conversation_id=new_conversation_id(),
        user_id=UserId("local-user"),
        created_at=created_at,
        updated_at=created_at,
    )
    chat_service = ChatService(
        conversations=InMemoryConversationRepository(),
        model_provider=_EchoModelProvider(),
        now=now,
        new_message_id=new_message_id,
    )
    asyncio.run(
        run_chat(
            chat_service=chat_service,
            conversation=conversation,
            model_name="development-echo",
            system_prompt="You are asAgent's development echo assistant.",
            read_line=input,
            write_line=print,
        ),
    )


if __name__ == "__main__":
    main()
