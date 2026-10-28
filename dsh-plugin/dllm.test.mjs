/**
 * dllm 插件单元测试（不依赖 DSH 启动）。
 * 模拟 ctx / agent / session，直接驱动 apply() 注册的 pre-step listener。
 *
 * Run: node dllm.test.mjs
 */
import assert from "node:assert";
import { apply } from "./dllm.js";

function makeHarness(failOn = []) {
  const listeners = new Map();
  const ctx = {
    on(event, fn, opts) {
      listeners.set(event, { fn, opts });
      return () => listeners.delete(event);
    },
    effect(fn) {
      fn();
    },
    logger: { info() {}, warn() {} },
  };
  const events = [];
  const agent = {
    session: {
      requestHeader: () => ({ config: { provider: "deepseek", model: "deepseek-flash" } }),
      append: (type, data, opts) => {
        if (failOn.includes(type)) throw new Error(`append ${type} failed`);
        events.push({ type, data, opts });
      },
    },
  };
  return { ctx, listeners, events, agent };
}

function preStep(listeners) {
  return listeners.get("agent/pre-step").fn;
}

const defaultDecision = { kind: "enter", messages: [{ role: "user" }] };

async function run(hitConfig, payload = {}) {
  const h = makeHarness();
  apply(h.ctx, { enable: true, min: 100, max: 100, cooldownSeconds: 0, onlyFirstStep: true, ...hitConfig });
  const listener = preStep(h.listeners);
  const decision = await listener(
    {
      agent: h.agent,
      messages: [{ role: "user" }],
      signal: { aborted: false },
      turn: 1,
      step: 1,
      ...payload,
    },
    async () => defaultDecision,
  );
  return { decision, events: h.events };
}

let pass = 0;
const fail = [];

function check(name, cond, detail = "") {
  if (cond) {
    pass++;
    console.log(`  PASS ${name}`);
  } else {
    fail.push(name);
    console.log(`  FAIL ${name} ${detail}`);
  }
}

// 1. 100% 必中：写 step 生命周期 + dllm + reject
{
  const { decision, events } = await run({});
  check("命中返回 reject", decision.kind === "reject", JSON.stringify(decision));
  check(
    "写 step/start、assistant/message、step/end",
    events.length === 3 &&
      events.map((e) => e.type).join(",") === "step/start,assistant/message,step/end",
    JSON.stringify(events.map((e) => e.type)),
  );
  const msg = events[1];
  const blocks = msg?.data?.message?.content ?? [];
  check(
    "内容正好是 dllm",
    blocks.length === 1 && blocks[0].type === "text" && blocks[0].text === "dllm",
    JSON.stringify(blocks),
  );
  check(
    "带 turn/step",
    events.every((e) => e.data?.turn === 1 && e.data?.step === 1),
  );
  check(
    "source 路由来自 requestHeader",
    msg?.data?.message?.source?.provider === "deepseek" &&
      msg?.data?.message?.source?.model === "deepseek-flash",
    JSON.stringify(msg?.data?.message?.source),
  );
  check("surfaceOp=append", msg?.opts?.surfaceOp === "append");
  check(
    "带 settlement 字段（stream/usage）",
    Array.isArray(msg?.data?.stream) && typeof msg?.data?.usage?.totalTokens === "number",
    JSON.stringify(msg?.data && { stream: msg.data.stream, usage: msg.data.usage }),
  );
}

// 2. 0% 必不中：原决策原样返回
{
  const { decision, events } = await run({ min: 0, max: 0 });
  check("未命中返回原决策", decision === defaultDecision);
  check("未命中不写事件", events.length === 0);
}

// 3. 只在 step 1 掷骰
{
  const { decision, events } = await run({}, { step: 2 });
  check("step 2 不触发", decision === defaultDecision && events.length === 0);
}

// 4. 概率统计（5-10%，10 万次）
{
  const h = makeHarness();
  apply(h.ctx, { enable: true, min: 5, max: 10, cooldownSeconds: 0, onlyFirstStep: true });
  const listener = preStep(h.listeners);
  const N = 100_000;
  let hits = 0;
  for (let i = 0; i < N; i++) {
    const decision = await listener(
      { agent: h.agent, messages: [{ role: "user" }], signal: { aborted: false }, turn: 1, step: 1 },
      async () => defaultDecision,
    );
    if (decision.kind === "reject") hits++;
  }
  const rate = hits / N;
  check(`命中率 ${(rate * 100).toFixed(2)}% ≈ 7.5%`, Math.abs(rate - 0.075) < 0.006);
}

// 5. 冷却
{
  const h = makeHarness();
  apply(h.ctx, { enable: true, min: 100, max: 100, cooldownSeconds: 60, onlyFirstStep: true });
  const listener = preStep(h.listeners);
  const payload = (turn) => ({
    agent: h.agent,
    messages: [{ role: "user" }],
    signal: { aborted: false },
    turn,
    step: 1,
  });
  const first = await listener(payload(1), async () => defaultDecision);
  const second = await listener(payload(2), async () => defaultDecision);
  check("冷启动第一次命中", first.kind === "reject");
  check("冷却期内第二次不命中", second === defaultDecision);
}

// 6. enable=false
{
  const { decision, events } = await run({ enable: false });
  check("总开关关闭不触发", decision === defaultDecision && events.length === 0);
}

// 7. 上游 reject 时让路
{
  const h = makeHarness();
  apply(h.ctx, { enable: true, min: 100, max: 100, cooldownSeconds: 0, onlyFirstStep: true });
  const listener = preStep(h.listeners);
  const upstream = { kind: "reject" };
  const decision = await listener(
    { agent: h.agent, messages: [{ role: "user" }], signal: { aborted: false }, turn: 1, step: 1 },
    async () => upstream,
  );
  check("上游 reject 原样返回", decision === upstream && h.events.length === 0);
}

// 8. 空消息 step 不替换
{
  const h = makeHarness();
  apply(h.ctx, { enable: true, min: 100, max: 100, cooldownSeconds: 0, onlyFirstStep: true });
  const listener = preStep(h.listeners);
  const empty = { kind: "enter", messages: [] };
  const decision = await listener(
    { agent: h.agent, messages: [], signal: { aborted: false }, turn: 1, step: 1 },
    async () => empty,
  );
  check("空 step 不触发", decision === empty && h.events.length === 0);
}

// 9. assistant 写入失败：仍关闭 step，避免日志留下 open step
{
  const h = makeHarness(["assistant/message"]);
  apply(h.ctx, { enable: true, min: 100, max: 100, cooldownSeconds: 0, onlyFirstStep: true });
  const listener = preStep(h.listeners);
  const decision = await listener(
    { agent: h.agent, messages: [{ role: "user" }], signal: { aborted: false }, turn: 1, step: 1 },
    async () => defaultDecision,
  );
  check("assistant 失败仍 reject", decision.kind === "reject");
  check(
    "assistant 失败仍关闭 step",
    h.events.map((e) => e.type).join(",") === "step/start,step/end",
    JSON.stringify(h.events.map((e) => e.type)),
  );
}

// 10. step/start 写入失败：放行原决策，不写任何事件
{
  const h = makeHarness(["step/start"]);
  apply(h.ctx, { enable: true, min: 100, max: 100, cooldownSeconds: 0, onlyFirstStep: true });
  const listener = preStep(h.listeners);
  const decision = await listener(
    { agent: h.agent, messages: [{ role: "user" }], signal: { aborted: false }, turn: 1, step: 1 },
    async () => defaultDecision,
  );
  check("step/start 失败放行原决策", decision === defaultDecision && h.events.length === 0);
}

console.log(`\n${"=".repeat(50)}\nPASS ${pass} / FAIL ${fail.length}`);
process.exit(fail.length === 0 ? 0 : 1);
