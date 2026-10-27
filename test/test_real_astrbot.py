"""在真实 AstrBot 环境里验证 astrbot_plugin_dllm（不需要启动 bot）。

前置：一个装了 astrbot 的 Python 环境，例如：

    uv venv /tmp/astrbot_venv --python 3.12
    uv pip install --python /tmp/astrbot_venv/bin/python astrbot
    /tmp/astrbot_venv/bin/python test/test_real_astrbot.py

和 play_dllm.py 的区别：这里用真实的 astrbot.core 模块
（AstrMessageEvent / MessageEventResult / Plain / PlatformMetadata），
而不是 test/fakes/ 里的假运行时。
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parent / "astrbot_plugin_dllm" / "main.py"

from astrbot.core.message.components import Image, Plain  # noqa: E402
from astrbot.core.message.message_event_result import (  # noqa: E402
    MessageEventResult,
    ResultContentType,
)
from astrbot.core.platform import (  # noqa: E402
    AstrBotMessage,
    AstrMessageEvent,
    MessageMember,
    MessageType,
    PlatformMetadata,
)

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name}  {detail}")


def load_plugin():
    spec = importlib.util.spec_from_file_location("dllm_plugin_real", PLUGIN)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dllm_plugin_real"] = mod
    spec.loader.exec_module(mod)
    return mod


def make_plugin(mod, **kw):
    cfg = {
        "Enable": True,
        "Probability_Min": 5,
        "Probability_Max": 10,
        "Cooldown_Seconds": 0,
    }
    cfg.update(kw)
    return mod.DLLM(object(), cfg)


def make_event(chain, content_type=ResultContentType.LLM_RESULT):
    msg = AstrBotMessage()
    msg.type = MessageType.FRIEND_MESSAGE
    msg.self_id = "bot-1"
    msg.session_id = "session-1"
    msg.message_id = "msg-1"
    msg.group = None
    msg.sender = MessageMember(user_id="user-1", nickname="tester")
    msg.message = list(chain)
    msg.message_str = "".join(c.text for c in chain if isinstance(c, Plain))
    msg.raw_message = None
    meta = PlatformMetadata(name="aiocqhttp", description="test", id="aiocqhttp")
    ev = AstrMessageEvent(msg.message_str, msg, meta, "session-1")
    res = MessageEventResult()
    res.chain = list(chain)
    res.set_result_content_type(content_type)
    ev.set_result(res)
    return ev


async def main():
    mod = load_plugin()

    print("[A] 真实 AstrBot 环境下构造插件")
    p = make_plugin(mod)
    check("构造成功", isinstance(p, mod.DLLM))
    check("有 logger", getattr(p, "logger", None) is not None)

    print("\n[B] 命中（100%）：整条消息链 -> 单个 dllm")
    p = make_plugin(mod, Probability_Min=100, Probability_Max=100)
    ev = make_event([Plain("今天天气不错，"), Image(file="cat.png"), Plain("你觉得呢？")])
    before = len(ev.get_result().chain)
    await p.decorate(ev)
    out = ev.get_result()
    check(f"组件数 {before} -> 1", len(out.chain) == 1, str(out.chain))
    check("唯一组件是 Plain('dllm')", out.chain == [Plain("dllm")], repr(out.chain))
    check("纯文本 == 'dllm'", out.get_plain_text() == "dllm", repr(out.get_plain_text()))
    check(
        "result_content_type 仍是 LLM_RESULT",
        out.result_content_type == ResultContentType.LLM_RESULT,
        str(out.result_content_type),
    )

    print("\n[C] 未命中（0%）：原链保留")
    p = make_plugin(mod, Probability_Min=0, Probability_Max=0)
    ev = make_event([Plain("正常回复"), Image(file="cat.png")])
    original = ev.get_result()
    await p.decorate(ev)
    check("chain 未被换", ev.get_result() is original and len(ev.get_result().chain) == 2)

    print("\n[D] 非 LLM 结果不触发")
    p = make_plugin(mod, Probability_Min=100, Probability_Max=100)
    ev = make_event([Plain("/help 的输出")], content_type=ResultContentType.GENERAL_RESULT)
    await p.decorate(ev)
    check("命令结果原样", ev.get_result().get_plain_text() == "/help 的输出")

    print("\n[E] 真环境概率统计（min=5 max=10）")
    p = make_plugin(mod)
    n = 50_000
    hit = sum(1 for _ in range(n) if p.roll())
    rate = hit / n
    print(f"  样本 {n}，命中 {hit}，实测 {rate * 100:.2f}%（理论 7.50%）")
    check("落在 7.5% ± 0.8%", abs(rate - 0.075) < 0.008, f"实测 {rate * 100:.2f}%")

    print("\n[F] /dllm 命令")
    p = make_plugin(mod, Probability_Min=0, Probability_Max=0)
    ev = make_event([Plain("x")])
    await p.cmd_dllm(ev)
    check("命令结果 == dllm", ev.get_result().get_plain_text() == "dllm")

    print(f"\n{'=' * 50}\nREAL ENV: PASS {PASS} / FAIL {FAIL}")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
