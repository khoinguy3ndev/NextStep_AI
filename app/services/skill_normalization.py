from __future__ import annotations

import re
from typing import Iterable


_STOPWORDS = {
    "developer",
    "development",
    "engineer",
    "engineering",
    "programming",
    "software",
    "application",
    "apps",
    "framework",
    "tools",
    "tool",
    "specialization",
    "certificate",
    "certificates",
    "professional",
    "learn",
}


def normalize_skill_text(value: str | None) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = text.replace("c plus plus", "c++")
    text = text.replace("c sharp", "c#")
    text = text.replace("node js", "node.js")
    text = text.replace("react js", "react.js")
    text = text.replace("restful api", "rest api")
    return text


def normalize_skill_key(value: str | None) -> str:
    text = normalize_skill_text(value)
    if not text:
        return ""

    text = text.replace("c#", "csharp")
    text = text.replace("c++", "cpp")
    text = text.replace("node.js", "nodejs")
    text = text.replace("react.js", "reactjs")
    text = text.replace(".net", "dotnet")
    text = re.sub(r"[^a-z0-9+#]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize_skill(value: str | None) -> set[str]:
    text = normalize_skill_key(value)
    if not text:
        return set()
    tokens = [item for item in re.split(r"[^a-zA-Z0-9+#]+", text) if item]
    return {item for item in tokens if item not in _STOPWORDS and len(item) >= 2}


def skill_similarity(left: str | None, right: str | None) -> float:
    a = tokenize_skill(left)
    b = tokenize_skill(right)
    if not a or not b:
        return 0.0
    union = a.union(b)
    if not union:
        return 0.0
    return len(a.intersection(b)) / len(union)


def build_skill_index(names: Iterable[str], aliases: Iterable[Iterable[str]]) -> dict[str, str]:
    index: dict[str, str] = {}
    for name, alias_list in zip(names, aliases):
        canonical = normalize_skill_key(name)
        if not canonical:
            continue
        index[canonical] = name
        for alias in alias_list:
            alias_key = normalize_skill_key(alias)
            if alias_key and alias_key not in index:
                index[alias_key] = name
    return index
