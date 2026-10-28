/**
 * dllm — DSH 插件
 *
 * 有 5-10% 的概率，本次回复直接变成一句 `dllm`，其他什么都不说。
 *
 * 机制：挂 `agent/pre-step` waterfall 钩子。命中概率时跳过模型调用：
 * 往 session 写 `step/start`、`assistant/message`、`step/end` 三条事件，
 * 然后返回 `{ kind: "reject" }` 让本 turn 以 blocked 结束。模型根本没被调用，
 * 所以不存在「生成了又丢弃」的浪费，也不依赖模型听话。
 *
 * 写入必须补齐完整生命周期：pre-step 被拒绝的 turn 里没有 step，单写一条
 * assistant/message 会变成孤儿事件；加载时校验器会报
 * "assistant/message does not match an open turn and step"。
 * 同理，assistant/message 的 data 必须带 settlement 字段（turn/step/stream，
 * 以及 usage），否则会报 "invalid settlement fields"。这两处都会让整个
 * 会话日志在 DSH 里打不开。
 *
 * 只对 turn 的第一个 step 掷骰（`onlyFirstStep`），一次用户输入只有一次机会；
 * 工具调用后的续步不掷，避免把半个任务打断。
 */
import { createAssistantMessage } from "@deepseek-ai/dsh-llm";

export const name = "dllm";

const DLLM_TEXT = "dllm";

export function apply(ctx, config = {}) {
  const conf = {
    enable: true,
    min: 5,
    max: 10,
    cooldownSeconds: 0,
    onlyFirstStep: true,
    ...config,
  };
  let lastHit = null;

  function roll() {
    if (!conf.enable) return false;
    const now = Date.now();
    if (conf.cooldownSeconds > 0 && lastHit !== null) {
      if (now - lastHit < conf.cooldownSeconds * 1000) return false;
    }
    const lo = Math.min(conf.min, conf.max);
    const hi = Math.max(conf.min, conf.max);
    const percent = lo + Math.random() * (hi - lo);
    if (Math.random() * 100 < percent) {
      lastHit = now;
      return true;
    }
    return false;
  }

  const dispose = ctx.on(
    "agent/pre-step",
    async (payload, next) => {
      const { agent, signal, step, turn } = payload;
      // 先让其它 listener（模型切换提示等）跑完，不抢它们的决策。
      const decision = await next();
      if (decision.kind === "reject") return decision;
      if (signal.aborted) return decision;
      if (conf.onlyFirstStep && step !== 1) return decision;
      // 没有要发给模型的消息（空 step）就不替换，保持原语义。
      if (decision.messages.length === 0) return decision;
      if (!roll()) return decision;

      try {
        const header = agent.session.requestHeader?.();
        const route = header?.config ?? {};
        // A pre-step rejection leaves the turn with no step at all, so an
        // assistant/message written here would be an orphan. Open and close
        // the step in the log so the event owns a legal lifecycle.
        const message = createAssistantMessage({
          content: [{ type: "text", text: DLLM_TEXT }],
          source: {
            provider: route.provider ?? "dllm",
            model: route.model ?? "dllm",
          },
        });
        try {
          agent.session.append("step/start", { turn, step });
        } catch (error) {
          ctx.logger?.warn("dllm: 写入 step/start 失败，放行原决策: %o", error);
          return decision;
        }
        try {
          agent.session.append(
            "assistant/message",
            {
              turn,
              step,
              message,
              // The loader requires settlement fields on every assistant message.
              usage: {
                inputTokens: 0,
                outputTokens: 0,
                cacheReadTokens: 0,
                cacheWriteTokens: 0,
                totalTokens: 0,
              },
              stream: [],
            },
            { surfaceOp: "append" },
          );
        } catch (error) {
          ctx.logger?.warn("dllm: 写入 dllm 回复失败: %o", error);
        } finally {
          try {
            agent.session.append("step/end", { turn, step });
          } catch (error) {
            ctx.logger?.warn("dllm: 写入 step/end 失败: %o", error);
          }
        }
        ctx.logger?.info("dllm hit: 第 %d 轮只回 %s", turn, DLLM_TEXT);
        return { kind: "reject" };
      } catch (error) {
        ctx.logger?.warn("dllm: 写入 dllm 回复失败，放行原决策: %o", error);
        return decision;
      }
    },
    { prepend: true },
  );

  ctx.effect(() => () => dispose(), "dllm: dispose pre-step listener");
}
