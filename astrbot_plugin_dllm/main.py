"""astrbot_plugin_dllm —— 有 5-10% 的概率，只回一个「dllm」，其他什么都不说。

机制：挂 on_decorating_result（发送前钩子）。AI 照常生成回复，掷骰子命中就把整条
消息链替换成单个 Plain("dllm")，原来的文字/图片/表情全部丢弃。

概率不是固定值：每次判定都从 [Probability_Min, Probability_Max] 里重新取一个百分比，
所以「概率」本身也是浮动的。

兼容 AstrBot v4.x（on_decorating_result 由 ResultDecorateStage 在发送前收集）。
"""

from __future__ import annotations

import random
import time

from astrbot.api.event import filter
from astrbot.api.message_components import Plain
from astrbot.api.star import Context, Star, register

PLUGIN_NAME = "astrbot_plugin_dllm"
DLLM_TEXT = "dllm"


@register(
    PLUGIN_NAME,
    "nkhszk",
    "有 5-10% 的概率，AI 只回一个 dllm，其他什么都不说",
    "0.1.0",
)
class DLLM(Star):
    """有 5-10% 的概率，只回一个 dllm。

    命中时把回复整条替换成「dllm」，不解释、不加标点、不补充别的内容。
    概率区间、冷却时间、总开关都可以在插件配置里调。
    """

    DEFAULT_MIN = 5
    DEFAULT_MAX = 10

    def __init__(self, context: Context, config: dict | None = None):
        super().__init__(context)
        # AstrBot 的插件加载器会把 _conf_schema.json 生成的配置作为 config 传进来。
        self.config = config or {}
        self._last_hit_at = 0.0

    # ------------------------------------------------------------------ 配置
    def _cfg(self) -> dict:
        return self.config if isinstance(self.config, dict) else {}

    def _get(self, key: str, default):
        return self._cfg().get(key, default)

    @staticmethod
    def _to_int(value, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def probability_percent(self) -> float:
        """本次判定的概率（百分比）。每次调用都重新在区间里随机取。"""
        lo = self._to_int(self._get("Probability_Min", self.DEFAULT_MIN), self.DEFAULT_MIN)
        hi = self._to_int(self._get("Probability_Max", self.DEFAULT_MAX), self.DEFAULT_MAX)
        lo, hi = sorted((lo, hi))
        lo = max(0, min(100, lo))
        hi = max(0, min(100, hi))
        if lo == hi:
            return float(lo)
        return random.uniform(lo, hi)

    def _cooldown_ok(self) -> bool:
        try:
            cooldown = float(self._get("Cooldown_Seconds", 0))
        except (TypeError, ValueError):
            cooldown = 0.0
        if cooldown <= 0:
            return True
        return (time.monotonic() - self._last_hit_at) >= cooldown

    # ------------------------------------------------------------------ 掷骰
    def roll(self) -> bool:
        """掷一次骰子。True 表示这一轮只回 dllm。"""
        if not self._get("Enable", True):
            return False
        if not self._cooldown_ok():
            return False
        if random.random() * 100.0 < self.probability_percent():
            self._last_hit_at = time.monotonic()
            return True
        return False

    # ------------------------------------------------------------------ 钩子
    @filter.on_decorating_result()
    async def decorate(self, event):
        """发送前拦截：命中就把整条消息链换成单个 dllm。"""
        result = event.get_result()
        if result is None or not result.chain:
            return
        # 只对 LLM 生成的回复生效；命令回复、错误提示等原样放行。
        if not result.is_llm_result():
            return
        if not self.roll():
            return
        self.logger.info("dllm 命中，本条只回 %r", DLLM_TEXT)
        event.set_result(event.chain_result([Plain(DLLM_TEXT)]))

    @filter.command("dllm")
    async def cmd_dllm(self, event):
        """强制来一发 dllm（测试/手动整活用）"""
        event.set_result(event.chain_result([Plain(DLLM_TEXT)]))
