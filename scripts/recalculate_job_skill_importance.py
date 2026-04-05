from __future__ import annotations

import os
import re
import sys

from sqlalchemy import text

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from app.db.session import get_standalone_db
from app.models.job import Job
from app.services.crawler_service import JobCrawler


def _tier_from_score(score: float) -> float:
    if score >= 0.78:
        return 3.0
    if score >= 0.55:
        return 2.0
    return 1.0


def _mention_count(description: str, skill_name: str) -> int:
    pattern = re.compile(rf"(?<!\w){re.escape(skill_name)}(?!\w)", re.IGNORECASE)
    return len(pattern.findall(description or ""))


def main() -> None:
    db = get_standalone_db()
    updated = 0

    try:
        jobs = db.query(Job).all()
        crawler = JobCrawler()

        for job in jobs:
            skill_rows = [row for row in job.job_skills if row.skill and row.skill.name]
            if not skill_rows:
                continue

            skill_names = [row.skill.name for row in skill_rows]
            details = crawler._build_skill_details(
                skills=skill_names,
                description=job.description_raw or "",
                title=job.title or "",
            )
            detail_map = {str(item.get("skill", "")).strip().lower(): item for item in details}
            scored_rows: list[tuple] = []

            for row in skill_rows:
                skill_name = row.skill.name.strip().lower()
                detail = detail_map.get(skill_name, {})
                base_score = float(detail.get("importance", 0.6))
                mention_boost = min(0.15, _mention_count(job.description_raw or "", row.skill.name) * 0.03)
                title_boost = 0.1 if row.skill.name.lower() in (job.title or "").lower() else 0.0
                score = max(0.35, min(1.0, base_score + mention_boost + title_boost))
                scored_rows.append((row, score, detail.get("evidence_snippet")))

            scored_rows.sort(key=lambda item: item[1], reverse=True)

            for idx, (row, score, evidence) in enumerate(scored_rows):
                tier_importance = _tier_from_score(score)

                if len(scored_rows) >= 4:
                    if idx == 0:
                        tier_importance = 3.0
                    elif idx >= len(scored_rows) - max(1, len(scored_rows) // 4):
                        tier_importance = 1.0

                if row.importance != tier_importance or (evidence and row.evidence_snippet != evidence):
                    row.importance = tier_importance
                    if evidence:
                        row.evidence_snippet = evidence
                    updated += 1

        db.commit()

        distribution = db.execute(
            text("SELECT importance, COUNT(*) FROM job_skills GROUP BY importance ORDER BY importance")
        ).fetchall()

        print(f"updated rows: {updated}")
        print(f"importance distribution: {distribution}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
