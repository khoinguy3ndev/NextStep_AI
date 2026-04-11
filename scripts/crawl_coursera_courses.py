from __future__ import annotations

import os
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass
from urllib.parse import parse_qs, unquote, urlparse

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from app.db.session import get_standalone_db
from app.models.skill import Skill
from app.models.skill_course import SkillCourse
from scripts.build_skill_relation_groups import build_skill_relation_groups


# DÁN SKILL + LINK TRANG SEARCH COURSERA TẠI ĐÂY
SKILL_CRAWL_TARGETS = [
    {
        "skill": "Java",
        "url": "https://www.coursera.org/specializations/learn-java-programming",
    },
]

MAX_COURSES_PER_URL = 20
PAGE_WAIT_SECONDS = 15
DEFAULT_HOURS_PER_WEEK = 8
MAX_CORE_COURSES_PER_SKILL = 3
MIN_DURATION_HOURS = 4
REPLACE_EXISTING_COURSERA_ROWS = True


@dataclass
class CourseCandidate:
    title: str
    url: str
    duration: str | None
    duration_hours: int | None
    level: str | None


def _normalize_text(value: str | None) -> str:
    return str(value or "").strip()


def _extract_query_skill(search_url: str) -> str | None:
    parsed = urlparse(search_url)
    query_map = parse_qs(parsed.query)
    for key in ["query", "q"]:
        values = query_map.get(key)
        if values:
            skill = unquote(str(values[0])).strip()
            if skill:
                return skill
    return None


def _infer_skill_from_url(search_url: str) -> str | None:
    parsed = urlparse(search_url)
    path = _normalize_text(parsed.path).strip("/").lower()
    if not path:
        return None
    tokens = re.split(r"[-_/]+", path)
    ignored = {
        "search",
        "learn",
        "specializations",
        "professional",
        "certificates",
        "professional-certificates",
        "projects",
    }
    candidates = [item for item in tokens if item and item not in ignored]
    if not candidates:
        return None
    return candidates[0].capitalize()


def _extract_first_number(text: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _extract_number_range(text: str) -> tuple[float, float] | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)", text)
    if not match:
        return None
    try:
        return float(match.group(1)), float(match.group(2))
    except ValueError:
        return None


def _duration_text_to_hours(duration_text: str | None) -> int | None:
    text = _normalize_text(duration_text).lower()
    if not text:
        return None

    range_value = _extract_number_range(text)
    number = ((range_value[0] + range_value[1]) / 2) if range_value else _extract_first_number(text)
    if number is None or number <= 0:
        return None

    if "hour" in text or "hr" in text:
        if "per week" in text or "/week" in text:
            if "month" in text:
                return round(number * DEFAULT_HOURS_PER_WEEK * 4)
            if "week" in text:
                return round(number * DEFAULT_HOURS_PER_WEEK)
        return round(number)

    if "week" in text:
        return round(number * DEFAULT_HOURS_PER_WEEK)

    if "month" in text:
        return round(number * DEFAULT_HOURS_PER_WEEK * 4)

    return round(number)


def _estimate_duration_hours(duration_text: str | None) -> int | None:
    return _duration_text_to_hours(duration_text)


def _extract_duration_from_text(raw_text: str) -> str | None:
    text = _normalize_text(raw_text)
    if not text:
        return None

    patterns = [
        r"\b\d+(?:\.\d+)?\s*(?:hours?|hrs?)\b",
        r"\b\d+(?:\.\d+)?\s*(?:weeks?)\b",
        r"\b\d+(?:\.\d+)?\s*(?:months?)\b",
        r"\bapproximately\s+\d+(?:\.\d+)?\s*(?:hours?|weeks?|months?)\b",
    ]

    lower = text.lower()
    candidates: list[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, lower):
            token = _normalize_text(match.group(0))
            if token:
                candidates.append(token)

    if not candidates:
        return None

    unique_candidates = list(dict.fromkeys(candidates))
    best = None
    best_hours = -1
    for token in unique_candidates:
        hours = _duration_text_to_hours(token)
        if hours is None:
            continue
        if hours > best_hours:
            best = token
            best_hours = hours

    if best is not None:
        return best

    return None


def _is_program_url(url: str) -> bool:
    target = _normalize_text(url).lower()
    return bool(re.search(r"coursera\.org\/(learn|specializations|professional-certificates)\/", target))


def _tokenize_skill(skill_name: str) -> list[str]:
    stopwords = {"developer", "development", "engineering", "engineer", "skill", "skills", "full", "stack"}
    tokens = [item for item in re.split(r"[^a-zA-Z0-9+#]+", skill_name.lower()) if item]
    return [token for token in tokens if token not in stopwords and len(token) >= 2]


def _candidate_relevance(skill_name: str, item: CourseCandidate) -> int:
    tokens = _tokenize_skill(skill_name)
    if not tokens:
        return 1
    haystack = f"{item.title} {item.url}".lower()
    return sum(1 for token in tokens if token in haystack)


def _create_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1600,1200")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
    )

    chromedriver_path = os.getenv("CHROMEDRIVER_PATH", "").strip()
    if chromedriver_path:
        service = Service(executable_path=chromedriver_path)
        return webdriver.Chrome(service=service, options=options)

    try:
        return webdriver.Chrome(options=options)
    except Exception:
        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)


def _collect_course_links(driver: webdriver.Chrome, search_url: str) -> list[str]:
    driver.get(search_url)
    WebDriverWait(driver, PAGE_WAIT_SECONDS).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    time.sleep(1.2)

    links = driver.execute_script(
        """
        const anchors = Array.from(document.querySelectorAll('a[href]'));
        const accepted = [];
        const seen = new Set();
        for (const a of anchors) {
            const href = a.getAttribute('href') || '';
            const full = href.startsWith('http') ? href : `https://www.coursera.org${href}`;
            if (!/coursera\.org\/(learn|specializations|professional-certificates)\//.test(full)) {
                continue;
            }
            if (seen.has(full)) {
                continue;
            }
            seen.add(full);
            accepted.push(full);
        }
        return accepted;
        """
    )

    return [item for item in links if isinstance(item, str)]


def _score_candidate(skill_name: str, item: CourseCandidate) -> float:
    score = 0.0
    url = item.url.lower()
    title = item.title.lower()
    skill = skill_name.lower()

    if "/professional-certificates/" in url:
        score += 40
    if "/specializations/" in url:
        score += 35
    if "/learn/" in url:
        score += 25

    if any(token in title for token in ["fundamentals", "foundations", "complete", "introduction", "beginner"]):
        score += 10

    if skill and skill in title:
        score += 8

    relevance = _candidate_relevance(skill_name, item)
    score += relevance * 20

    score += min(float(item.duration_hours or 0), 80) / 10
    return score


def _aggregate_completion_path(skill_name: str, candidates: list[CourseCandidate], fallback_url: str) -> CourseCandidate | None:
    valid = [
        item
        for item in candidates
        if (item.duration_hours or 0) >= MIN_DURATION_HOURS and _candidate_relevance(skill_name, item) >= 1
    ]
    if not valid:
        return None

    ranked = sorted(valid, key=lambda item: _score_candidate(skill_name, item), reverse=True)
    selected = ranked[:MAX_CORE_COURSES_PER_SKILL]
    if not selected:
        return None

    total_hours = sum(item.duration_hours or 0 for item in selected)
    if total_hours <= 0:
        return None

    level_votes = [item.level for item in selected if item.level]
    level = Counter(level_votes).most_common(1)[0][0] if level_votes else None
    duration_label = f"{total_hours} hours (completion path from {len(selected)} core courses)"

    return CourseCandidate(
        title=f"{skill_name} Skill Completion Path (Coursera)",
        url=fallback_url,
        duration=duration_label,
        duration_hours=total_hours,
        level=level,
    )


def _extract_course_details(driver: webdriver.Chrome, course_url: str) -> CourseCandidate | None:
    try:
        driver.get(course_url)
        WebDriverWait(driver, PAGE_WAIT_SECONDS).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(0.8)
    except Exception:
        return None

    try:
        title = driver.execute_script(
            """
            const h1 = document.querySelector('h1');
            if (h1 && h1.textContent) return h1.textContent.trim();
            const og = document.querySelector('meta[property="og:title"]');
            if (og) return (og.getAttribute('content') || '').trim();
            return document.title || '';
            """
        )
    except Exception:
        title = ""

    if not _normalize_text(title):
        return None

    page_text = driver.execute_script("return document.body ? document.body.innerText : '';")
    duration_text = _extract_duration_from_text(page_text)
    duration_hours = _estimate_duration_hours(duration_text)

    level = None
    lower_text = _normalize_text(page_text).lower()
    if "beginner" in lower_text:
        level = "beginner"
    elif "intermediate" in lower_text:
        level = "intermediate"
    elif "advanced" in lower_text:
        level = "advanced"

    return CourseCandidate(
        title=_normalize_text(title),
        url=course_url,
        duration=duration_text,
        duration_hours=duration_hours,
        level=level,
    )


def _ensure_skill(db, skill_name: str) -> Skill:
    candidate = _normalize_text(skill_name)
    if not candidate:
        candidate = "Unknown Skill"

    existing = db.query(Skill).filter(Skill.name.ilike(candidate)).first()
    if existing:
        return existing

    skill = Skill(name=candidate, category="technical", aliases=[], is_active=True)
    db.add(skill)
    db.flush()
    return skill


def _existing_titles_by_skill(db, skill_id: int) -> set[str]:
    rows = (
        db.query(SkillCourse)
        .filter(SkillCourse.skill_id == skill_id, SkillCourse.platform == "Coursera")
        .all()
    )
    return {_normalize_text(row.title).lower() for row in rows if _normalize_text(row.title)}


def crawl_direct_pages() -> None:
    db = get_standalone_db()
    driver = _create_driver()
    inserted_total = 0

    try:
        for target in SKILL_CRAWL_TARGETS:
            search_url = _normalize_text(target.get("url"))
            if not search_url:
                continue

            skill_name = (
                _normalize_text(target.get("skill"))
                or _extract_query_skill(search_url)
                or _infer_skill_from_url(search_url)
                or "Unknown Skill"
            )
            skill = _ensure_skill(db, skill_name)

            print(f"[INFO] crawling URL={search_url}")
            print(f"[INFO] target skill={skill.name}")

            links: list[str]
            if _is_program_url(search_url):
                links = [search_url]
            else:
                links = _collect_course_links(driver, search_url)
                links = links[:MAX_COURSES_PER_URL]

            if not links:
                print("[WARN] no course links found")
                continue

            candidates: list[CourseCandidate] = []
            for link in links:
                detail = _extract_course_details(driver, link)
                if not detail:
                    continue

                candidates.append(detail)

            aggregated = _aggregate_completion_path(skill.name, candidates, search_url)
            if not aggregated:
                print(f"[WARN] skill={skill.name}: no valid core course to aggregate")
                continue

            if REPLACE_EXISTING_COURSERA_ROWS:
                (
                    db.query(SkillCourse)
                    .filter(SkillCourse.skill_id == skill.skill_id, SkillCourse.platform == "Coursera")
                    .delete(synchronize_session=False)
                )

            db.add(
                SkillCourse(
                    skill_id=skill.skill_id,
                    platform="Coursera",
                    title=aggregated.title,
                    url=aggregated.url,
                    duration=aggregated.duration,
                    duration_hours=aggregated.duration_hours,
                    level=aggregated.level,
                )
            )
            inserted_total += 1

            db.commit()
            print(
                f"[OK] skill={skill.name} links={len(links)} aggregated_hours={aggregated.duration_hours} inserted=1"
            )

        relation_payload = build_skill_relation_groups()
        print(
            f"[RELATION] groups={relation_payload['meta']['total_groups']} edges={relation_payload['meta']['total_edges']}"
        )
        print(f"Done. total inserted={inserted_total}")
    finally:
        driver.quit()
        db.close()


def main() -> None:
    crawl_direct_pages()


if __name__ == "__main__":
    main()
