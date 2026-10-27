"""fake: astrbot.api.star —— Context / Star / register，对齐 AstrBot v4 的注入方式。

真实加载器：star_cls(context=..., config=plugin_config)。插件配置来自
_conf_schema.json 生成的 AstrBotConfig，不是全局 context.get_config()。
"""

from __future__ import annotations

import logging

_REGISTERED: dict[str, dict] = {}


class Context:
    def __init__(self, config: dict | None = None):
        self._config = config or {}

    def get_config(self):
        return self._config


class Star:
    def __init__(self, context: Context, config: dict | None = None):
        self.context = context
        self.config = config
        self.logger = logging.getLogger(f"astrbot.plugin.{type(self).__name__}")


def register(name: str, author: str, desc: str, version: str, repo: str | None = None):
    def deco(cls):
        _REGISTERED[name] = {
            "cls": cls,
            "author": author,
            "desc": desc,
            "version": version,
            "repo": repo,
        }
        return cls

    return deco
