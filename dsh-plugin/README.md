# dllm — DSH 插件

有 5-10% 的概率，本次回复直接变成一句 `dllm`，其他什么都不说。

和 `dllm-skill/` 的区别：skill 走提示词层、靠模型自觉；这个插件挂 `agent/pre-step`，命中时**根本不调用模型**，直接写一条 `dllm` 回复。

## 安装

1. 把 `dllm.js` 复制到 DSH profile 的 `plugins/` 目录，例如 `~/.dsh/profiles/desktop/plugins/dllm.js`。
2. 在同一 profile 的 `cordis.patch.yml` 末尾加：

```yaml
- insert:
    - id: dllm
      name: ./plugins/dllm.js
      config:
        enable: true
        min: 5
        max: 10
        cooldownSeconds: 0
        onlyFirstStep: true
```

3. 重启 DSH（客户端或 `dsh --profile <name>`）。

## 配置

| 项 | 默认 | 说明 |
|---|---|---|
| `enable` | `true` | 总开关 |
| `min` | `5` | 每次判定的概率下限（%） |
| `max` | `10` | 概率上限（%）；写反了自动排序 |
| `cooldownSeconds` | `0` | 命中后多少秒内不再触发 |
| `onlyFirstStep` | `true` | 只对 turn 的第一个 step 掷骰，工具调用后的续步不掷 |

## 为什么会有"修复版"

早期版本只往 session 写一条 `assistant/message` 就 reject。这会让会话日志变得无法加载：

- pre-step 被拒绝的 turn 里没有任何 step，孤立的 `assistant/message` 会触发
  `assistant/message does not match an open turn and step`；
- `assistant/message` 的 data 还要求 settlement 字段（`turn`/`step`/`stream`，以及 `usage`），
  缺了会报 `invalid settlement fields`。

**这两条都是加载期校验，一旦写进去，整个会话在 DSH 里就打不开了**（不是只丢这一条回复）。

修复版按合法顺序写 `step/start` → `assistant/message`（带 `usage`、`stream`）→ `step/end`，再 reject；
写入失败时也会尽力关闭 step，不留 open step。

## 测试

需要能解析 `@deepseek-ai/dsh-llm` 的环境。把本目录放到 profile 的 `plugins/` 下后运行：

```bash
node dllm.test.mjs
```

19 项断言：命中/未命中、概率分布、冷却、开关、step 2 不触发、上游 reject 让路、空 step、写入失败路径。

## 边界

- 只影响 turn 的第一个 step；工具调用后的续步正常跑。
- 命中时 turn 以 `blocked` 结束，模型不会被调用，不消耗 token（`usage` 记 0）。
- 空 step（没有要发给模型的消息）不替换。
- 上游已有 reject 决策时让路，不抢别人的决策。

## License

MIT
