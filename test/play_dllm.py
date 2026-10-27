"""Drive astrbot_plugin_dllm's real main.py against a fake AstrBot runtime.

Run:  python3 play_dllm.py
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "fakes"))

PLUGIN_MAIN = HERE.parent / "astrbot_plugin_dllm" / "main.py"

from astrbot.api.event import (  # noqa: E402
    AstrMessageEvent,
    MessageEventResult,
    ResultContentType,
)
from astrbot.api.message_components import Image, Plain  # noqa: E402
from astrbot.api.star import Context  # noqa: E402

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  \033[32mPASS\033[0m {name}")
    else:
        FAIL += 1
        print(f"  \033[31mFAIL\033[0m {name}  {detail}")


def load_plugin():
    spec = importlib.util.spec_from_file_location("dllm_plugin", PLUGIN_MAIN)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dllm_plugin"] = mod
    spec.loader.exec_module(mod)
    return mod


def make_plugin(**overrides):
    mod = load_plugin()
    cfg = {
        "Enable": True,
        "Probability_Min": 5,
        "Probability_Max": 10,
        "Cooldown_Seconds": 0,
    }
    cfg.update(overrides)
    return mod.DLLM(Context({}), cfg)


def llm_result(*components) -> MessageEventResult:
    res = MessageEventResult()
    res.chain = list(components)
    res.set_result_content_type(ResultContentType.LLM_RESULT)
    return res


def general_result(*components) -> MessageEventResult:
    res = MessageEventResult()
    res.chain = list(components)
    res.set_result_content_type(ResultContentType.GENERAL_RESULT)
    return res


async def s1_load():
    print("\n[1] 插件加载 & 注册")
    mod = load_plugin()
    check("模块可加载", hasattr(mod, "DLLM"))
    from astrbot.api.star import _REGISTERED

    meta = _REGISTERED.get("astrbot_plugin_dllm")
    check("注册名正确", meta is not None, str(_REGISTERED.keys()))
    check("版本号", meta is not None and meta["version"] == "0.1.0")
    p = mod.DLLM(
        Context({}),
        {"Enable": True, "Probability_Min": 5, "Probability_Max": 10, "Cooldown_Seconds": 0},
    )
    check("构造成功", isinstance(p, mod.DLLM))
    check("decorate 是 on_decorating_result 钩子", getattr(p.decorate, "_fake_kind", None) == "on_decorating_result")
    check("cmd_dllm 是 command", getattr(p.cmd_dllm, "_fake_kind", None) == "command")


async def s2_rate():
    print("\n[2] 概率统计（min=5 max=10，cooldown=0）")
    p = make_plugin()
    n = 200_000
    hit = sum(1 for _ in range(n) if p.roll())
    rate = hit / n
    print(f"  样本 {n}，命中 {hit}，实测 {rate*100:.2f}%（理论 7.50%）")
    check("落在 7.5% ± 0.5%", abs(rate - 0.075) < 0.005, f"实测 {rate*100:.2f}%")

    p0 = make_plugin(Probability_Min=0, Probability_Max=0)
    check("0% 永不命中", not any(p0.roll() for _ in range(1000)))

    p100 = make_plugin(Probability_Min=100, Probability_Max=100)
    check("100% 必命中", all(p100.roll() for _ in range(100)))


async def s3_replace():
    print("\n[3] 命中：整条消息链被替换成单个 dllm")
    p = make_plugin(Probability_Min=100, Probability_Max=100)
    ev = AstrMessageEvent()
    ev.set_result(llm_result(Plain("今天天气不错，"), Image(file="cat.png"), Plain("你觉得呢？")))
    await p.decorate(ev)
    out = ev.get_result()
    check("chain 只剩一个组件", len(out.chain) == 1, str(out.chain))
    check("唯一组件是 Plain('dllm')", out.chain == [Plain("dllm")], repr(out.chain))
    check("纯文本正好是 dllm", out.get_plain_text() == "dllm", repr(out.get_plain_text()))
    check(
        "result_content_type 仍是 LLM_RESULT",
        out.result_content_type == ResultContentType.LLM_RESULT,
        str(out.result_content_type),
    )


async def s4_miss():
    print("\n[4] 未命中：原回复原样保留")
    p = make_plugin(Probability_Min=0, Probability_Max=0)
    ev = AstrMessageEvent()
    original = llm_result(Plain("正常回复"), Image(file="cat.png"))
    ev.set_result(original)
    await p.decorate(ev)
    out = ev.get_result()
    check("chain 未被换", out is original and len(out.chain) == 2, str(out.chain))


async def s5_non_llm():
    print("\n[5] 非 LLM 结果（命令/系统回复）不触发")
    p = make_plugin(Probability_Min=100, Probability_Max=100)
    ev = AstrMessageEvent()
    ev.set_result(general_result(Plain("/help 的输出")))
    await p.decorate(ev)
    check("命令结果原样", ev.get_result().get_plain_text() == "/help 的输出")


async def s6_empty():
    print("\n[6] 空消息链不触发")
    p = make_plugin(Probability_Min=100, Probability_Max=100)
    ev = AstrMessageEvent()
    ev.set_result(llm_result())
    await p.decorate(ev)
    check("空 chain 保持空", len(ev.get_result().chain) == 0)

    ev2 = AstrMessageEvent()
    await p.decorate(ev2)
    check("无 result 不崩", ev2.get_result() is None)


async def s7_enable():
    print("\n[7] Enable=False 时不触发")
    p = make_plugin(Enable=False, Probability_Min=100, Probability_Max=100)
    check("roll 恒 False", not any(p.roll() for _ in range(1000)))
    ev = AstrMessageEvent()
    ev.set_result(llm_result(Plain("照常回答")))
    await p.decorate(ev)
    check("回复未被换", ev.get_result().get_plain_text() == "照常回答")


async def s8_cooldown():
    print("\n[8] 冷却时间")
    p = make_plugin(Probability_Min=100, Probability_Max=100, Cooldown_Seconds=60)
    check("冷却期内第一次命中", p.roll() is True)
    check("冷却期内第二次不命中", p.roll() is False)
    p2 = make_plugin(Probability_Min=100, Probability_Max=100, Cooldown_Seconds=0)
    check("无冷却时可连续命中", p2.roll() and p2.roll())

    # 回归：CI runner 刚开机时 monotonic() 可能小于冷却时长，
    # 初始状态不能被误判成"还在冷却"（GitHub Actions 上真踩过）。
    import time as time_module

    orig = time_module.monotonic
    time_module.monotonic = lambda: 10.0
    try:
        p3 = make_plugin(Probability_Min=100, Probability_Max=100, Cooldown_Seconds=60)
        check("开机 10s 时首次命中不被冷却误伤", p3.roll() is True)
        check("同一时刻第二次仍被冷却拦住", p3.roll() is False)
    finally:
        time_module.monotonic = orig


async def s9_range():
    print("\n[9] 概率区间容错（Min > Max / 越界）")
    p = make_plugin(Probability_Min=30, Probability_Max=5)
    vals = [p.probability_percent() for _ in range(2000)]
    check("自动排序到 [5,30]", 5 <= min(vals) and max(vals) <= 30, f"min={min(vals):.2f} max={max(vals):.2f}")

    p2 = make_plugin(Probability_Min=-50, Probability_Max=999)
    vals2 = [p2.probability_percent() for _ in range(2000)]
    check("越界钳到 [0,100]", 0 <= min(vals2) and max(vals2) <= 100)


async def s10_command():
    print("\n[10] /dllm 命令强制触发")
    p = make_plugin(Probability_Min=0, Probability_Max=0)
    ev = AstrMessageEvent()
    await p.cmd_dllm(ev)
    check("命令结果就是 dllm", ev.get_result().get_plain_text() == "dllm", repr(ev.get_result()))


async def main():
    await s1_load()
    await s2_rate()
    await s3_replace()
    await s4_miss()
    await s5_non_llm()
    await s6_empty()
    await s7_enable()
    await s8_cooldown()
    await s9_range()
    await s10_command()
    print(f"\n{'='*50}\nPASS {PASS} / FAIL {FAIL}")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
