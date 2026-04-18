from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


@dataclass
class SkillDurationEstimate:
    skill: str
    baseline_hours: int
    adjusted_hours: int
    estimated_weeks: int
    hours_per_week: int
    reference_range_hours: Tuple[int, int]
    note: str


class LearningDurationService:
    DEFAULT_HOURS_PER_WEEK = 8
    DEFAULT_BASELINE_HOURS = 48

    _IMPORTANCE_FACTOR: Dict[str, float] = {
        "high": 1.15,
        "medium": 1.0,
        "low": 0.9,
    }

    @classmethod
    def _data_file(cls) -> Path:
        return Path(__file__).resolve().parents[1] / "data" / "skill_duration_baseline.json"

    @classmethod
    def _load_baseline_data(cls) -> dict:
        with cls._data_file().open("r", encoding="utf-8") as handle:
            return json.load(handle)

    @staticmethod
    def _normalize_skill(value: str) -> str:
        return value.strip().lower()

    @classmethod
    def _build_index(cls) -> Dict[str, dict]:
        payload = cls._load_baseline_data()
        index: Dict[str, dict] = {}

        for item in payload.get("skills", []):
            canonical = cls._normalize_skill(item["skill"])
            index[canonical] = item
            for alias in item.get("aliases", []):
                index[cls._normalize_skill(alias)] = item

        return index

    @classmethod
    def get_reference_baseline(cls, skill_name: str) -> tuple[int, tuple[int, int], str]:
        index = cls._build_index()
        key = cls._normalize_skill(skill_name)
        baseline = index.get(key)

        base_hours = int(baseline["baseline_hours"]) if baseline else cls.DEFAULT_BASELINE_HOURS
        reference_range = (
            tuple(baseline.get("reference_range_hours", [max(20, base_hours - 20), base_hours + 20]))
            if baseline
            else (max(20, base_hours - 20), base_hours + 20)
        )
        note = "baseline_from_reference" if baseline else "fallback_baseline_no_reference_match"
        return base_hours, (int(reference_range[0]), int(reference_range[1])), note

    @classmethod
    def estimate_skill_duration(
        cls,
        skill_name: str,
        gap_value: float = 0.5,
        importance: str = "medium",
        hours_per_week: int = DEFAULT_HOURS_PER_WEEK,
    ) -> SkillDurationEstimate:
        base_hours, reference_range, note = cls.get_reference_baseline(skill_name)

        normalized_gap = max(0.0, min(gap_value, 1.0))
        gap_factor = 1.0 + (normalized_gap * 0.8)

        importance_key = importance.strip().lower()
        importance_factor = cls._IMPORTANCE_FACTOR.get(importance_key, 1.0)

        adjusted_hours = max(1, round(base_hours * gap_factor * importance_factor))
        weekly_hours = max(1, hours_per_week)
        estimated_weeks = math.ceil(adjusted_hours / weekly_hours)

        return SkillDurationEstimate(
            skill=skill_name,
            baseline_hours=base_hours,
            adjusted_hours=adjusted_hours,
            estimated_weeks=estimated_weeks,
            hours_per_week=weekly_hours,
            reference_range_hours=(int(reference_range[0]), int(reference_range[1])),
            note=note,
        )

    @classmethod
    def estimate_batch(
        cls,
        skills: List[dict],
        hours_per_week: int = DEFAULT_HOURS_PER_WEEK,
    ) -> List[SkillDurationEstimate]:
        results: List[SkillDurationEstimate] = []
        for item in skills:
            results.append(
                cls.estimate_skill_duration(
                    skill_name=item.get("skill", "unknown"),
                    gap_value=float(item.get("gap", 0.5)),
                    importance=item.get("importance", "medium"),
                    hours_per_week=hours_per_week,
                )
            )
        return results
