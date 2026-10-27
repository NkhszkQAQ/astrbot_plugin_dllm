# astrbot_plugin_dllm

有 5-10% 的概率，AI 只回一个 `dllm`，其他什么都不说。

完整说明（配置、边界、测试方法）见仓库根目录的 [README](../README.md)。

## 快速开始

1. 把本目录放进 AstrBot 的 `data/plugins/`
2. 重启或重载插件
3. 配置页调概率，或直接发 `/dllm` 手动触发

## 一句话原理

挂 `on_decorating_result`，AI 正常生成回复，命中时把整条消息链换成单个 `dllm`。
