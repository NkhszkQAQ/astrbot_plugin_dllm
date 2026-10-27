"""fake: astrbot.api.message_components"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Plain:
    text: str = ""
    type: str = "plain"


@dataclass
class Image:
    file: str = ""
    url: str = ""
    type: str = "image"

    @classmethod
    def fromURL(cls, url: str):
        return cls(url=url)

    @classmethod
    def fromFileSystem(cls, path: str):
        return cls(file=path)
