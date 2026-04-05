import os
import sys
from datetime import date

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.append(root_dir)

from app.services.learning_duration_service import LearningDurationService


def main() -> None:
    sample_skills = [
        {"skill": "Python", "gap": 0.7, "importance": "high"},
        {"skill": "SQL", "gap": 0.5, "importance": "high"},
        {"skill": "Docker", "gap": 0.6, "importance": "medium"},
        {"skill": "Kubernetes", "gap": 0.8, "importance": "medium"},
        {"skill": "React", "gap": 0.4, "importance": "low"},
    ]

    estimates = LearningDurationService.estimate_batch(sample_skills, hours_per_week=8)

    print("Skill Learning-Time Report")
    print(f"Generated at: {date.today().isoformat()}")
    print("Method: Reference baseline (Coursera-style) + gap/importance adjustment")
    print()
    print("| Skill | Baseline (h) | Ref range (h) | Adjusted (h) | Est. weeks | Note |")
    print("|---|---:|---:|---:|---:|---|")

    for item in estimates:
        low, high = item.reference_range_hours
        print(
            f"| {item.skill} | {item.baseline_hours} | {low}-{high} | "
            f"{item.adjusted_hours} | {item.estimated_weeks} | {item.note} |"
        )


if __name__ == "__main__":
    main()
