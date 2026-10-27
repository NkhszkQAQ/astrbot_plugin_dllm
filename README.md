# dllm

有 5-10% 的概率，AI 只回一个 `dllm`，其他什么都不说。

```
用户：今天好累啊
bot：dllm
用户：睡不着，给我讲个故事
bot：从前有个……
```

两种形态，按使用的机器人选一种：

| 形态 | 目录 | 适用 |
|---|---|---|
| AstrBot 插件（真随机、全局生效） | `astrbot_plugin_dllm/` | QQ 机器人（NapCat / LLOneBot + AstrBot） |
| DSH skill（提示词层） | `dllm-skill/SKILL.md` | DeepSeek Harness / 任何吃系统提示词的 AI 客户端 |

## AstrBot 插件

### 工作原理

挂 `on_decorating_result`（发送前钩子）。AI 照常生成回复，命中时把整条消息链替换成单个 `Plain("dllm")`。原来的文字、图片、表情全部丢掉，一个字都不补。

概率不是写死的：每次判定都从 `[Probability_Min, Probability_Max]` 里重新取一个百分比，所以概率本身也是浮动的（主人原话：5-10% 的概率不定）。

### 安装

1. 把 `astrbot_plugin_dllm/` 整个目录放进 AstrBot 的 `data/plugins/` 下
2. 重启 AstrBot，或在 WebUI 插件管理里重载
3. 插件配置页会出现「总开关 / 最低概率 / 最高概率 / 冷却时间」

### 配置

| 项 | 默认 | 说明 |
|---|---|---|
| `Enable` | `true` | 总开关 |
| `Probability_Min` | `5` | 每次判定的概率下限（%） |
| `Probability_Max` | `10` | 概率上限（%）；写反了会自动排序 |
| `Cooldown_Seconds` | `0` | 命中后多少秒内不再触发；`0` = 不冷却 |

### 行为边界

- 只替换 LLM 生成的回复。命令回复（`/help` 等）、错误提示原样放行。
- 流式输出（streaming）下 AstrBot 的 `on_decorating_result` 本身就不稳定，dllm 可能不生效；要稳定效果请关掉流式。
- 群聊里按「每条会回复的消息」独立掷骰，不是按「每轮对话」。
- `/dllm` 命令永远强制来一发，不受开关和概率影响。
- 插件没有网络调用、不落盘、不读消息内容，只在发送前换链。

### 测试

**假运行时（不需要装 AstrBot）**

```bash
cd test
python3 play_dllm.py
```

`test/fakes/` 是按 AstrBot v4 源码行为写的假运行时（`astrbot.api` / `astrbot.api.event` / `astrbot.api.star` / `astrbot.core.message`），`play_dllm.py` 用 importlib 直接加载**未修改的** `main.py`，跑 10 组场景 25 项断言：概率统计、命中替换、`content_type` 保留、未命中保留、非 LLM 不触发、空链、开关、冷却、区间容错、`/dllm` 命令。

**真实 AstrBot 环境（不启动 bot，只 import 真模块）**

```bash
uv venv /tmp/astrbot_venv --python 3.12
uv pip install --python /tmp/astrbot_venv/bin/python astrbot
/tmp/astrbot_venv/bin/python test/test_real_astrbot.py
```

用真实的 `AstrMessageEvent` / `MessageEventResult` / `Plain` / `PlatformMetadata` 构造事件，覆盖构造、命中替换、`content_type` 保留、未命中保留、非 LLM 放行、概率统计、`/dllm`，10 项断言。

> 已验证：AstrBot **4.29.3** 真环境 10/10 通过，假运行时 25/25 通过。没在完整启动的 bot 进程里接 QQ 平台跑过。

## DSH skill

`dllm-skill/SKILL.md`，安装到 `~/.dsh/skills/dllm/SKILL.md`（本机已装）。

DSH 没有消息钩子，这条走提示词层，行为等效物：

- 默认「自觉档」：靠生成时的内部随机，不可验证，纯乐子。
- 「严格档」：每次最终回复前跑一次 `shuf -i 0-999 -n 1`，`< 70` 命中（≈7%），真随机但每条回复多一次工具调用。

技术任务、代码、调试、危险操作提示不套；用户说「认真点」当场关。

## 名字

`dllm` 是粤语粗口的缩写（Diu Lei Lo Mo）。本插件只负责在对话里随机丢一句，不解释含义、不展开、不洗白。

## License

MIT
