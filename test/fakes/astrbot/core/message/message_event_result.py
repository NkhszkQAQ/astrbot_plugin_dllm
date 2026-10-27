"""fake: astrbot.core.message.message_event_result —— 对齐 AstrBot v4 真实 dataclass 行为。"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field


class ResultContentType(enum.Enum):
    LLM_RESULT = enum.auto()
    AGENT_RUNNER_ERROR = enum.auto()
    GENERAL_RESULT = enum.auto()
    STREAMING_RESULT = enum.auto()
    STREAMING_FINISH = enum.auto()


class EventResultType(enum.Enum):
    CONTINUE = enum.auto()
    STOP = enum.auto()


@dataclass
class MessageChain:
    chain: list = field(default_factory=list)
    use_t2i_: bool | None = None
    use_markdown_: bool | None = None
    type: str | None = None

    def message(self, message: str):
        from astrbot.api.message_components import Plain

        self.chain.append(Plain(message))
        return self

    def get_plain_text(self) -> str:
        from astrbot.api.message_components import Plain

        return "".join(c.text for c in self.chain if isinstance(c, Plain))

    def __len__(self):
        return len(self.chain)


@dataclass
class MessageEventResult(MessageChain):
    result_type: EventResultType | None = field(default_factory=lambda: EventResultType.CONTINUE)
    result_content_type: ResultContentType | None = field(
        default_factory=lambda: ResultContentType.GENERAL_RESULT
    )
    async_stream: object | None = None

    def stop_event(self):
        self.result_type = EventResultType.STOP
        return self

    def continue_event(self):
        self.result_type = EventResultType.CONTINUE
        return self

    def is_stopped(self) -> bool:
        return self.result_type == EventResultType.STOP

    def set_result_content_type(self, typ):
        self.result_content_type = typ
        return self

    def is_llm_result(self) -> bool:
        return self.result_content_type == ResultContentType.LLM_RESULT

    def is_model_result(self) -> bool:
        return self.result_content_type in (
            ResultContentType.LLM_RESULT,
            ResultContentType.AGENT_RUNNER_ERROR,
        )


CommandResult = MessageEventResult
