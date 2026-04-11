from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from app.db.session import get_standalone_db
from app.models.job_skill import JobSkill
from app.models.skill import Skill
from app.services.skill_normalization import normalize_skill_key, skill_similarity, tokenize_skill

OUTPUT_FILE = Path(root_dir) / "app" / "data" / "skill_relation_groups.json"
MIN_CO_OCCUR = 2
MIN_CONDITIONAL_CO_OCCUR = 0.35
MIN_EDGE_SCORE = 0.45

STOPWORDS = {
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
}


@dataclass
class SkillNode:
    skill_id: int
    name: str
    aliases: list[str]


def _normalize_text(value: str | None) -> str:
    return normalize_skill_key(value)


def _tokenize(value: str) -> set[str]:
    tokens = tokenize_skill(value)
    return {item for item in tokens if item not in STOPWORDS and len(item) >= 2}


def _token_jaccard(left: str, right: str) -> float:
    return skill_similarity(left, right)


def _alias_score(skill_a: SkillNode, skill_b: SkillNode) -> float:
    aliases_a = {_normalize_text(item) for item in [skill_a.name, *skill_a.aliases] if _normalize_text(item)}
    aliases_b = {_normalize_text(item) for item in [skill_b.name, *skill_b.aliases] if _normalize_text(item)}

    if aliases_a.intersection(aliases_b):
        return 1.0

    if any(item in aliases_b for item in aliases_a):
        return 0.8

    text_score = _token_jaccard(skill_a.name, skill_b.name)
    if text_score >= 0.65:
        return 0.6

    return 0.0


def _collect_skills(db) -> dict[int, SkillNode]:
    result: dict[int, SkillNode] = {}
    for row in db.query(Skill).all():
        if not row.name:
            continue
        result[row.skill_id] = SkillNode(
            skill_id=row.skill_id,
            name=row.name,
            aliases=[str(item) for item in (row.aliases or []) if str(item).strip()],
        )
    return result


def _collect_job_skill_sets(db) -> list[set[int]]:
    rows = db.query(JobSkill).all()
    by_job: dict[int, set[int]] = defaultdict(set)
    for row in rows:
        if row.job_job_id is None or row.skill_skill_id is None:
            continue
        by_job[row.job_job_id].add(int(row.skill_skill_id))
    return [values for values in by_job.values() if len(values) >= 2]


def _build_co_occurrence(skill_ids_per_job: list[set[int]]) -> tuple[dict[int, int], dict[tuple[int, int], int]]:
    freq: dict[int, int] = defaultdict(int)
    pair_count: dict[tuple[int, int], int] = defaultdict(int)

    for skill_set in skill_ids_per_job:
        for sid in skill_set:
            freq[sid] += 1

        for a, b in combinations(sorted(skill_set), 2):
            pair_count[(a, b)] += 1

    return dict(freq), dict(pair_count)


def _edge_score(
    skill_a: SkillNode,
    skill_b: SkillNode,
    freq: dict[int, int],
    pair_count: dict[tuple[int, int], int],
) -> tuple[float, dict]:
    a, b = sorted((skill_a.skill_id, skill_b.skill_id))
    co = pair_count.get((a, b), 0)
    f_a = max(1, freq.get(a, 0))
    f_b = max(1, freq.get(b, 0))

    conditional = co / min(f_a, f_b)
    co_score = 0.0
    if co >= MIN_CO_OCCUR and conditional >= MIN_CONDITIONAL_CO_OCCUR:
        co_score = min(1.0, conditional)

    alias_score = _alias_score(skill_a, skill_b)
    text_score = _token_jaccard(skill_a.name, skill_b.name)

    # ưu tiên tín hiệu co-occurrence thực tế từ JD, alias là tín hiệu phụ
    score = (0.65 * co_score) + (0.25 * alias_score) + (0.10 * text_score)

    details = {
        "co_occurrence": co,
        "conditional_co_occurrence": round(conditional, 3),
        "co_score": round(co_score, 3),
        "alias_score": round(alias_score, 3),
        "text_score": round(text_score, 3),
        "edge_score": round(score, 3),
    }
    return score, details


def _build_graph(skills: dict[int, SkillNode], freq: dict[int, int], pair_count: dict[tuple[int, int], int]):
    adjacency: dict[int, set[int]] = defaultdict(set)
    edges: list[dict] = []

    skill_list = list(skills.values())
    for left_idx in range(len(skill_list)):
        for right_idx in range(left_idx + 1, len(skill_list)):
            left = skill_list[left_idx]
            right = skill_list[right_idx]

            score, details = _edge_score(left, right, freq, pair_count)
            if score < MIN_EDGE_SCORE:
                continue

            adjacency[left.skill_id].add(right.skill_id)
            adjacency[right.skill_id].add(left.skill_id)
            edges.append(
                {
                    "skill_a": left.name,
                    "skill_b": right.name,
                    **details,
                }
            )

    return adjacency, edges


def _connected_components(adjacency: dict[int, set[int]]) -> list[list[int]]:
    visited: set[int] = set()
    groups: list[list[int]] = []

    for start in adjacency.keys():
        if start in visited:
            continue

        stack = [start]
        component: list[int] = []
        while stack:
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            component.append(node)
            stack.extend(adjacency.get(node, set()) - visited)

        if len(component) >= 2:
            groups.append(sorted(component))

    return groups


def build_skill_relation_groups() -> dict:
    db = get_standalone_db()
    try:
        skills = _collect_skills(db)
        job_skill_sets = _collect_job_skill_sets(db)
        freq, pair_count = _build_co_occurrence(job_skill_sets)
        adjacency, edges = _build_graph(skills, freq, pair_count)
        components = _connected_components(adjacency)

        grouped_skills = []
        for idx, component in enumerate(components, start=1):
            names = [skills[sid].name for sid in component if sid in skills]
            grouped_skills.append(
                {
                    "group_id": idx,
                    "size": len(names),
                    "skills": sorted(names),
                }
            )

        payload = {
            "meta": {
                "description": "Skill relation groups inferred from job co-occurrence + aliases + text similarity.",
                "min_co_occur": MIN_CO_OCCUR,
                "min_conditional_co_occur": MIN_CONDITIONAL_CO_OCCUR,
                "min_edge_score": MIN_EDGE_SCORE,
                "total_skills": len(skills),
                "total_groups": len(grouped_skills),
                "total_edges": len(edges),
            },
            "groups": grouped_skills,
            "edges": sorted(edges, key=lambda item: item["edge_score"], reverse=True),
        }

        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload
    finally:
        db.close()


def main() -> None:
    payload = build_skill_relation_groups()
    print(f"Wrote: {OUTPUT_FILE}")
    print(f"skills={payload['meta']['total_skills']} groups={payload['meta']['total_groups']} edges={payload['meta']['total_edges']}")
    for group in payload["groups"][:10]:
        print(f"- group#{group['group_id']} size={group['size']}: {', '.join(group['skills'][:8])}")


if __name__ == "__main__":
    main()
