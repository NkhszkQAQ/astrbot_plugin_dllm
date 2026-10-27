"""fake: astrbot.core.platform.AstrMessageEvent（只实现插件和测试用到的部分）"""

from __future__ import annotations

from astrbot.core.message.message_event_result import (
    EventResultType,
    MessageEventResult,
)


class AstrMessageEvent:
    def __init__(self, session_id: str = "session-1", sender_id: str = "user-1"):
        self.session_id = session_id
        self.sender_id = sender_id
        self._result: MessageEventResult | None = None
        self._force_stopped = False
        self.platform_name = "aiocqhttp"
        self.plugins_name = None

    # ---- result ----
    def get_result(self) -> MessageEventResult | None:
        return self._result

    def set_result(self, result) -> None:
        if isinstance(result, str):
            result = MessageEventResult().message(result)
        self._result = result

    def clear_result(self) -> None:
        self._result = None

    def make_result(self) -> MessageEventResult:
        return MessageEventResult()

    def plain_result(self, text: str) -> MessageEventResult:
        return MessageEventResult().message(text)

    def chain_result(self, chain: list) -> MessageEventResult:
        mer = MessageEventResult()
        mer.chain = chain
        return mer

    # ---- stop ----
    def stop_event(self) -> None:
        self._force_stopped = True
        if self._result is None:
            self.set_result(MessageEventResult().stop_event())
        else:
            self._result.stop_event()

    def is_stopped(self) -> bool:
        if self._force_stopped:
            return True
        if self._result is None:
            return False
        return self._result.is_stopped()

    def get_sender_id(self) -> str:
        return self.sender_id
