"""fake: astrbot.api.event —— filter 装饰器 + 关键类型 re-export。

对齐 AstrBot v4：@filter.on_decorating_result() 只把函数登记到
EventType.OnDecoratingResultEvent，运行时由 ResultDecorateStage 调用 handler(event)。
测试里直接 await plugin.decorate(event) 模拟这一调用。
"""

from __future__ import annotations

from astrbot.core.message.message_event_result import (
    CommandResult,
    EventResultType,
    MessageChain,
    MessageEventResult,
    ResultContentType,
)
from astrbot.core.platform import AstrMessageEvent

__all__ = [
    "AstrMessageEvent",
    "CommandResult",
    "EventResultType",
    "MessageChain",
    "MessageEventResult",
    "ResultContentType",
    "EventMessageType",
    "filter",
]


class EventMessageType:
    ALL = "all"
    GROUP_MESSAGE = "group_message"
    PRIVATE_MESSAGE = "private_message"


class _Filter:
    """只做打标，不模拟真实注册表。"""

    EventMessageType = EventMessageType

    @staticmethod
    def _tag(fn, kind, **meta):
        fn._fake_kind = kind
        fn._fake_meta = meta
        return fn

    def on_decorating_result(self, **kwargs):
        def deco(fn):
            return self._tag(fn, "on_decorating_result", **kwargs)

        return deco

    def command(self, name=None, **kwargs):
        def deco(fn):
            return self._tag(fn, "command", name=name, **kwargs)

        return deco

    def event_message_type(self, event_type=None, **kwargs):
        def deco(fn):
            return self._tag(fn, "event_message_type", event_type=event_type, **kwargs)

        return deco

    def llm_tool(self, name=None, **kwargs):
        def deco(fn):
            return self._tag(fn, "llm_tool", name=name, **kwargs)

        return deco


filter = _Filter()
