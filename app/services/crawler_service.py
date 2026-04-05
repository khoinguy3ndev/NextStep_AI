import os
import re
import time
import json
import unicodedata
from datetime import datetime, timezone
from html import unescape
from typing import Iterable
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.job import Currency, Job, JobStatus
from app.models.job_skill import JobSkill
from app.models.skill import Skill


class JobCrawler:
    def __init__(self) -> None:
        self._user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/129.0.0.0 Safari/537.36"
        )
        self._body_wait_seconds = int(os.getenv("CRAWLER_BODY_WAIT_SECONDS", "12"))
        self._post_load_sleep_seconds = float(os.getenv("CRAWLER_POST_LOAD_SLEEP_SECONDS", "1.2"))
        self._page_load_timeout_seconds = int(os.getenv("CRAWLER_PAGELOAD_TIMEOUT_SECONDS", "20"))
        self._use_webdriver_manager = os.getenv("CRAWLER_USE_WEBDRIVER_MANAGER", "0").strip().lower() in {"1", "true", "yes"}

    def _create_driver(self) -> webdriver.Chrome:
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--blink-settings=imagesEnabled=false")
        options.page_load_strategy = "eager"
        options.add_argument(f"user-agent={self._user_agent}")
        options.add_experimental_option(
            "prefs",
            {
                "profile.managed_default_content_settings.images": 2,
                "profile.default_content_setting_values.notifications": 2,
            },
        )

        chromedriver_path = os.getenv("CHROMEDRIVER_PATH", "").strip()
        if chromedriver_path:
            service = Service(executable_path=chromedriver_path)
            driver = webdriver.Chrome(service=service, options=options)
            driver.set_page_load_timeout(self._page_load_timeout_seconds)
            return driver

        try:
            driver = webdriver.Chrome(options=options)
            driver.set_page_load_timeout(self._page_load_timeout_seconds)
            return driver
        except Exception:
            if not self._use_webdriver_manager:
                raise

        manager_path = ChromeDriverManager().install()
        if manager_path.lower().endswith("third_party_notices.chromedriver"):
            manager_path = os.path.join(os.path.dirname(manager_path), "chromedriver.exe")

        service = Service(manager_path)
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(self._page_load_timeout_seconds)
        return driver

    @staticmethod
    def _source_name_topdev() -> str:
        return "TopDev"

    @staticmethod
    def is_topdev_detail_url(url: str) -> bool:
        parsed = urlparse(url)
        hostname = parsed.netloc.lower()
        path = parsed.path.lower()
        return "topdev.vn" in hostname and "/detail-jobs/" in path

    @staticmethod
    def _first_non_empty(values: list[str]) -> str:
        for value in values:
            if value and value.strip():
                return value.strip()
        return ""

    @staticmethod
    def _clean_lines(text: str) -> str:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines)

    @staticmethod
    def _dedupe_preserve_order(values: list[str]) -> list[str]:
        results: list[str] = []
        seen: set[str] = set()
        for value in values:
            key = value.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            results.append(value.strip())
        return results

    @staticmethod
    def _normalize_skill_name(skill: str) -> str:
        raw = re.sub(r"\s+", " ", skill or "").strip()
        if not raw:
            return ""

        normalized_map = {
            "postgresql": "PostgreSQL",
            "postgressql": "PostgreSQL",
            "postgres": "PostgreSQL",
            "javascript": "JavaScript",
            "typescript": "TypeScript",
            "nodejs": "Node.js",
            "node.js": "Node.js",
            "reactjs": "React",
            "react.js": "React",
            "vuejs": "Vue.js",
            "vue.js": "Vue.js",
            "springboot": "Spring Boot",
            "spring boot": "Spring Boot",
            "dotnet": ".NET",
            ".net": ".NET",
            "c sharp": "C#",
            "c#": "C#",
            "golang": "Go",
            "ci/cd": "CI/CD",
            "rest api": "REST API",
            "graphql": "GraphQL",
            "aws": "AWS",
            "gcp": "GCP",
            "k8s": "Kubernetes",
            "elasticsearch": "Elasticsearch",
            "opensearch": "OpenSearch",
        }

        key = raw.lower().replace(" ", "")
        if key in normalized_map:
            return normalized_map[key]

        key_with_space = raw.lower()
        if key_with_space in normalized_map:
            return normalized_map[key_with_space]

        return raw

    @staticmethod
    def _strip_accents(text: str) -> str:
        if not text:
            return ""
        normalized = unicodedata.normalize("NFD", text)
        return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")

    def _extract_title(self, soup: BeautifulSoup) -> str:
        candidates = [
            soup.select_one("h1") and soup.select_one("h1").get_text(" ", strip=True),
            soup.find("meta", property="og:title") and soup.find("meta", property="og:title").get("content", ""),
            soup.title and soup.title.get_text(" ", strip=True),
        ]
        title = self._first_non_empty([value for value in candidates if value])
        return title or "Không tìm thấy tiêu đề"

    @staticmethod
    def _extract_job_posting_jsonld(soup: BeautifulSoup) -> dict:
        scripts = soup.select("script[type='application/ld+json']")
        for script in scripts:
            raw = (script.string or script.get_text() or "").strip()
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            candidates = []
            if isinstance(data, dict):
                candidates.append(data)
                graph = data.get("@graph")
                if isinstance(graph, list):
                    candidates.extend([item for item in graph if isinstance(item, dict)])
            elif isinstance(data, list):
                candidates.extend([item for item in data if isinstance(item, dict)])

            for item in candidates:
                item_type = item.get("@type")
                if isinstance(item_type, list):
                    is_job_posting = any(str(t).lower() == "jobposting" for t in item_type)
                else:
                    is_job_posting = str(item_type).lower() == "jobposting"
                if is_job_posting:
                    return item

        return {}

    def _extract_company(self, soup: BeautifulSoup, job_posting: dict | None = None) -> str:
        if job_posting:
            org = job_posting.get("hiringOrganization")
            if isinstance(org, dict):
                name = org.get("name")
                if isinstance(name, str) and name.strip():
                    return name.strip()

        selectors = [
            "[data-testid='company-name']",
            ".company-name",
            "a[href*='/company/']",
            "a[href*='/nha-tuyen-dung/']",
        ]
        values: list[str] = []
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                values.append(element.get_text(" ", strip=True))

        marker = soup.find(string=re.compile(r"(Company|Công ty|Employer)", re.I))
        if marker:
            parent = marker.find_parent(["div", "section", "article"])
            if parent:
                values.append(parent.get_text(" ", strip=True))

        company_name = self._first_non_empty(values)
        return company_name or "N/A"

    def _extract_location(self, soup: BeautifulSoup, job_posting: dict | None = None) -> str:
        if job_posting:
            job_location = job_posting.get("jobLocation")
            if isinstance(job_location, list):
                job_location = job_location[0] if job_location else None

            if isinstance(job_location, dict):
                address = job_location.get("address")
                if isinstance(address, dict):
                    parts = [
                        str(address.get("streetAddress", "")).strip(),
                        str(address.get("addressLocality", "")).strip(),
                        str(address.get("addressRegion", "")).strip(),
                    ]
                    location = ", ".join([part for part in parts if part])
                    if location:
                        return location

        selectors = [
            "[data-testid='job-location']",
            ".job-location",
            "a[href*='location']",
            "span[class*='location']",
        ]
        values: list[str] = []
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                values.append(element.get_text(" ", strip=True))

        location = self._first_non_empty(values)
        return location or "Việt Nam"

    def _extract_salary(self, soup: BeautifulSoup, job_posting: dict | None = None) -> str:
        if job_posting:
            base_salary = job_posting.get("baseSalary")
            if isinstance(base_salary, dict):
                currency = base_salary.get("currency")
                value = base_salary.get("value")
                if isinstance(value, dict):
                    raw_value = value.get("value")
                    if raw_value is not None:
                        salary_text = str(raw_value).strip()
                        if salary_text:
                            if currency:
                                return f"{salary_text} {currency}"
                            return salary_text

        selectors = [
            "[data-testid='salary']",
            ".salary",
            "span[class*='salary']",
            "div[class*='salary']",
        ]
        values: list[str] = []
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(" ", strip=True)
                if text:
                    values.append(text)

        if not values:
            body_text = soup.get_text(" ", strip=True)
            salary_match = re.search(r"(\$\s?\d[\d,\.\s-]*|\d+[\d,\.\s-]*(VND|USD|triệu|million))", body_text, re.I)
            if salary_match:
                values.append(salary_match.group(0))

        return self._first_non_empty(values)

    def _extract_skill_tags_from_page(self, soup: BeautifulSoup) -> list[str]:
        selectors = [
            "div.flex.flex-wrap.items-center.gap-1 a",
            "a[class*='skill']",
            "span[class*='skill']",
            "li[class*='skill']",
            "[data-testid='job-skill']",
            "a[href*='keyword=']",
        ]

        skills: list[str] = []
        for selector in selectors:
            for element in soup.select(selector):
                text = element.get_text(" ", strip=True)
                if text and 1 < len(text) <= 50:
                    skills.append(text)

        normalized: list[str] = []
        ignored = {"4+", "xem thêm", "apply", "ứng tuyển", "save job", "hot"}
        for skill in skills:
            cleaned = self._normalize_skill_name(skill)
            key = cleaned.lower().strip()
            if key in ignored:
                continue
            if len(cleaned) <= 1:
                continue
            normalized.append(cleaned)

        return self._dedupe_preserve_order(normalized)

    def _extract_skills_from_text(self, text: str) -> list[str]:
        if not text:
            return []

        ascii_text = self._strip_accents(text).lower()

        keyword_patterns: list[tuple[str, str]] = [
            ("JavaScript", r"\bjavascript\b"),
            ("TypeScript", r"\btypescript\b"),
            ("Java", r"\bjava\b"),
            ("Python", r"\bpython\b"),
            ("C#", r"\bc#\b|\bc\s*sharp\b"),
            (".NET", r"\b\.net\b|\bdotnet\b"),
            ("Spring Boot", r"\bspring\s*boot\b"),
            ("React", r"\breact(?:\.js|js)?\b"),
            ("Vue.js", r"\bvue(?:\.js|js)?\b"),
            ("Angular", r"\bangular\b"),
            ("Node.js", r"\bnode(?:\.js|js)?\b"),
            ("PostgreSQL", r"\bpostgres(?:ql)?\b"),
            ("MySQL", r"\bmysql\b"),
            ("MongoDB", r"\bmongodb\b"),
            ("Redis", r"\bredis\b"),
            ("Elasticsearch", r"\belasticsearch\b"),
            ("OpenSearch", r"\bopensearch\b"),
            ("AWS", r"\baws\b|\bamazon web services\b"),
            ("GCP", r"\bgcp\b|\bgoogle cloud\b"),
            ("Azure", r"\bazure\b"),
            ("Docker", r"\bdocker\b"),
            ("Kubernetes", r"\bkubernetes\b|\bk8s\b"),
            ("Linux", r"\blinux\b"),
            ("CI/CD", r"\bci/cd\b|\bci\s*cd\b"),
            ("REST API", r"\brest\s*api\b|\brestful\b"),
            ("GraphQL", r"\bgraphql\b"),
            ("Microservices", r"\bmicroservices?\b"),
            ("Kafka", r"\bkafka\b"),
            ("RabbitMQ", r"\brabbitmq\b"),
            ("Selenium", r"\bselenium\b"),
            ("JQuery", r"\bjquery\b"),
            ("Information Security", r"an\s*ninh\s*thong\s*tin|\binformation\s+security\b"),
            ("Security Architecture", r"kien\s*truc\s*an\s*ninh\s*thong\s*tin|\bsecurity\s+architecture\b"),
            ("Security Policy", r"chinh\s*sach\s*an\s*ninh\s*thong\s*tin|\bsecurity\s+policy\b"),
            ("Risk Management", r"\brisk\s+management\b|quan\s*tri\s*rui\s*ro"),
            ("SOC", r"\bsoc\b|security\s*operations\s*center"),
            ("SIEM", r"\bsiem\b"),
            ("IAM", r"\biam\b|identity\s*(and|&)\s*access\s*management"),
            ("ISO 27001", r"\biso\s*27001\b"),
            ("NIST", r"\bnist\b"),
            ("CISSP", r"\bcissp\b"),
            ("CISM", r"\bcism\b"),
            ("PCI DSS", r"\bpci\s*dss\b"),
            ("Threat Modeling", r"\bthreat\s+model(?:ing|ling)\b"),
            ("Zero Trust", r"\bzero\s+trust\b"),
        ]

        found: list[str] = []
        for skill_name, pattern in keyword_patterns:
            if re.search(pattern, text, flags=re.IGNORECASE) or re.search(pattern, ascii_text, flags=re.IGNORECASE):
                found.append(skill_name)

        return self._dedupe_preserve_order(found)

    def _extract_skills(
        self,
        soup: BeautifulSoup,
        description: str,
        title: str,
        job_posting: dict | None = None,
    ) -> list[str]:
        merged_skills: list[str] = []

        if job_posting:
            skills_value = job_posting.get("skills")
            if isinstance(skills_value, str) and skills_value.strip():
                jsonld_skills = [item.strip() for item in skills_value.split(",") if item.strip()]
                merged_skills.extend([self._normalize_skill_name(skill) for skill in jsonld_skills])
            elif isinstance(skills_value, list):
                merged_skills.extend(
                    [self._normalize_skill_name(str(item).strip()) for item in skills_value if str(item).strip()]
                )

        merged_skills.extend(self._extract_skill_tags_from_page(soup))
        inference_text = f"{title}\n{description}" if title else description
        merged_skills.extend(self._extract_skills_from_text(inference_text))

        clean_skills: list[str] = []
        for skill in merged_skills:
            normalized = self._normalize_skill_name(skill)
            if not normalized:
                continue
            if len(normalized) > 50:
                continue
            clean_skills.append(normalized)

        return self._dedupe_preserve_order(clean_skills)

    @staticmethod
    def _build_skill_details(skills: list[str], description: str, title: str) -> list[dict]:
        if not skills:
            return []

        title_text = (title or "").lower()
        normalized_description = description or ""
        description_ascii = JobCrawler._strip_accents(normalized_description).lower()

        lines = [line.strip() for line in normalized_description.splitlines() if line.strip()]
        if not lines:
            lines = [normalized_description]

        sentences = [item.strip() for item in re.split(r"[\n\.\!\?;•\-]+", normalized_description) if item.strip()]
        sentence_pool = sentences if sentences else lines

        must_keywords = [
            "must",
            "required",
            "mandatory",
            "strong",
            "expert",
            "proficient",
            "need",
            "yeu cau",
            "bat buoc",
            "kinh nghiem",
            "thanh thao",
            "bắt buộc",
            "yêu cầu",
            "kinh nghiệm",
            "thành thạo",
            "cần",
        ]
        preferred_keywords = [
            "preferred",
            "nice to have",
            "plus",
            "bonus",
            "advantage",
            "uu tien",
            "loi the",
            "ưu tiên",
            "lợi thế",
        ]
        optional_keywords = [
            "familiar",
            "exposure",
            "basic",
            "co ban",
            "cơ bản",
            "biet",
            "biết",
        ]
        requirement_headers = [
            "requirement",
            "qualification",
            "must-have",
            "job requirement",
            "yeu cau",
            "bắt buộc",
            "yêu cầu",
        ]
        preferred_headers = [
            "preferred",
            "nice to have",
            "benefit",
            "plus",
            "ưu tiên",
            "lợi thế",
        ]

        def _contains_any(value: str, tokens: list[str]) -> bool:
            lowered = value.lower()
            lowered_ascii = JobCrawler._strip_accents(lowered)
            return any(token in lowered or token in lowered_ascii for token in tokens)

        def classify_text(value: str) -> float:
            if _contains_any(value, must_keywords):
                return 0.25
            if _contains_any(value, preferred_keywords):
                return -0.05
            if _contains_any(value, optional_keywords):
                return -0.10
            return 0.10

        def section_bonus(evidence_text: str) -> float:
            target = evidence_text.lower()
            target_ascii = JobCrawler._strip_accents(target)

            for idx, line in enumerate(lines):
                candidate = line.lower()
                candidate_ascii = JobCrawler._strip_accents(candidate)
                if target in candidate or target_ascii in candidate_ascii:
                    window = " ".join(lines[max(0, idx - 3) : min(len(lines), idx + 1)])
                    if _contains_any(window, requirement_headers):
                        return 0.10
                    if _contains_any(window, preferred_headers):
                        return -0.05
                    break
            return 0.0

        def _skill_patterns(skill_name: str) -> tuple[re.Pattern[str], re.Pattern[str] | None]:
            plain = re.compile(rf"(?<!\w){re.escape(skill_name)}(?!\w)", re.IGNORECASE)
            normalized_skill = JobCrawler._strip_accents(skill_name)
            if len(normalized_skill) <= 3:
                return plain, None
            ascii_variant = re.compile(rf"(?<!\w){re.escape(normalized_skill)}(?!\w)", re.IGNORECASE)
            return plain, ascii_variant

        details: list[dict] = []
        seen: set[str] = set()

        for skill in skills:
            key = skill.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)

            importance = 0.60
            evidence = ""

            if key in title_text:
                importance += 0.20

            pattern, ascii_pattern = _skill_patterns(skill)
            matched_lines = [line for line in sentence_pool if pattern.search(line)]

            if not matched_lines and ascii_pattern is not None:
                for line in sentence_pool:
                    if ascii_pattern.search(JobCrawler._strip_accents(line)):
                        matched_lines.append(line)

            if matched_lines:
                evidence = matched_lines[0]
                importance += classify_text(evidence)
                importance += section_bonus(evidence)
            else:
                if pattern.search(normalized_description):
                    importance += 0.05
                elif ascii_pattern is not None and ascii_pattern.search(description_ascii):
                    importance += 0.05

            importance = max(0.35, min(1.0, importance))
            details.append(
                {
                    "skill": skill,
                    "importance": round(importance, 2),
                    "evidence_snippet": evidence[:220] if evidence else None,
                }
            )

        if len(details) >= 2:
            unique_importance = {item["importance"] for item in details}
            if len(unique_importance) == 1:
                ranked: list[tuple[float, int, dict]] = []
                total = len(details)
                for idx, item in enumerate(details):
                    signal = 0.0
                    skill_key = item["skill"].strip().lower()
                    evidence_text = (item.get("evidence_snippet") or "").lower()

                    if skill_key in title_text:
                        signal += 0.9

                    if evidence_text:
                        signal += 0.25
                        if _contains_any(evidence_text, must_keywords):
                            signal += 0.6
                        elif _contains_any(evidence_text, preferred_keywords):
                            signal -= 0.2
                        elif _contains_any(evidence_text, optional_keywords):
                            signal -= 0.35

                    # Ưu tiên nhẹ skill xuất hiện sớm trong danh sách đã trích xuất
                    signal += (total - idx) / (total * 10.0)
                    ranked.append((signal, idx, item))

                ranked.sort(key=lambda value: (value[0], -value[1]), reverse=True)

                top_cut = max(1, round(total * 0.3))
                mid_cut = max(top_cut + 1, round(total * 0.7))

                for rank_idx, (_, _, item) in enumerate(ranked):
                    if rank_idx < top_cut:
                        item["importance"] = 0.85
                    elif rank_idx < mid_cut:
                        item["importance"] = 0.65
                    else:
                        item["importance"] = 0.45

        return details

    def _extract_description(self, soup: BeautifulSoup, job_posting: dict | None = None) -> str:
        if job_posting:
            description_html = job_posting.get("description")
            if isinstance(description_html, str) and description_html.strip():
                unescaped = unescape(description_html)
                text = BeautifulSoup(unescaped, "html.parser").get_text("\n", strip=True)
                cleaned = self._clean_lines(text)
                if len(cleaned) > 80:
                    return cleaned

        description_selectors = [
            "div[class*='job-description']",
            "section[class*='job-description']",
            "div.prose",
            "article",
            "main",
        ]

        for selector in description_selectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text("\n", strip=True)
                cleaned = self._clean_lines(text)
                if len(cleaned) > 120:
                    return cleaned

        role_header = soup.find(string=re.compile(r"(Responsibilities|Mô tả công việc|Job Description|Yêu cầu)", re.I))
        if role_header:
            block = role_header.find_parent(["div", "section", "article"])
            if block:
                text = block.get_text("\n", strip=True)
                cleaned = self._clean_lines(text)
                if len(cleaned) > 80:
                    return cleaned

        fallback = self._clean_lines(soup.get_text("\n", strip=True))
        return fallback[:3000] if fallback else "Không tìm thấy mô tả công việc"

    def get_job_info(self, url: str):
        driver = None
        try:
            if not self.is_topdev_detail_url(url):
                raise ValueError("Chỉ hỗ trợ crawl link TopDev dạng /detail-jobs/")

            print(f"DEBUG: Bắt đầu crawl Selenium: {url}")
            driver = self._create_driver()
            driver.get(url)
            WebDriverWait(driver, self._body_wait_seconds).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            WebDriverWait(driver, self._body_wait_seconds).until(
                lambda current_driver: current_driver.execute_script("return document.readyState") in ["interactive", "complete"]
            )
            time.sleep(self._post_load_sleep_seconds)

            html = driver.page_source
            soup = BeautifulSoup(html, "html.parser")
            job_posting = self._extract_job_posting_jsonld(soup)

            title = self._extract_title(soup)
            if job_posting and isinstance(job_posting.get("title"), str) and job_posting.get("title", "").strip():
                title = job_posting.get("title", "").strip()

            company_name = self._extract_company(soup, job_posting)
            location = self._extract_location(soup, job_posting)
            salary_range = self._extract_salary(soup, job_posting)
            description = self._extract_description(soup, job_posting)
            skills_list = self._extract_skills(soup, description, title, job_posting)
            skill_details = self._build_skill_details(skills_list, description, title)

            print(f"DEBUG: Title: {title}")
            print(f"DEBUG: Company: {company_name}")
            print(
                f"DEBUG: Skills ({len(skills_list)}): "
                f"{', '.join(skills_list[:15]) if skills_list else 'Không tìm thấy'}"
            )

            return {
                "title": title,
                "company_name": company_name,
                "location": location,
                "salary_range": salary_range,
                "description": description,
                "job_requirements": ", ".join(skills_list) if skills_list else "Không tìm thấy kỹ năng",
                "job_skill_details": skill_details,
                "source_url": url,
                "source_website": self._source_name_topdev(),
            }
        except (WebDriverException, TimeoutException, ValueError) as exc:
            print(f"Lỗi Selenium {url}: {exc}")
            return None
        finally:
            if driver is not None:
                driver.quit()

    def save_job_to_db(self, db: Session, job_data: dict):
        if not job_data:
            return None

        try:
            def parse_salary_fields(salary_text: str | None) -> tuple[int | None, int | None, Currency | None]:
                if not salary_text:
                    return None, None, None

                normalized = salary_text.lower()
                currency: Currency | None = None
                if "$" in normalized or "usd" in normalized:
                    currency = Currency.USD
                elif "vnd" in normalized or "triệu" in normalized or "đ" in normalized:
                    currency = Currency.VND

                numbers = re.findall(r"\d+[\d\.,]*", salary_text)
                parsed: list[int] = []
                for raw in numbers:
                    cleaned = re.sub(r"[^\d]", "", raw)
                    if not cleaned:
                        continue
                    try:
                        parsed.append(int(cleaned))
                    except ValueError:
                        continue

                if not parsed:
                    return None, None, currency
                if len(parsed) == 1:
                    return parsed[0], parsed[0], currency
                return min(parsed), max(parsed), currency

            def upsert_company(company_name: str, location: str | None) -> Company:
                cleaned_name = (company_name or "N/A").strip() or "N/A"
                company = db.query(Company).filter(func.lower(Company.name) == cleaned_name.lower()).first()
                if company:
                    if location and not company.location:
                        company.location = location
                    return company

                company = Company(name=cleaned_name, location=location)
                db.add(company)
                db.flush()
                return company

            def replace_job_skills(job: Job, skills_text: str | None, skill_details: list[dict] | None = None) -> None:
                db.query(JobSkill).filter(JobSkill.job_job_id == job.job_id).delete()

                def to_importance_tier(raw_value: float) -> float:
                    if raw_value >= 2.5:
                        return 3.0
                    if raw_value >= 1.5:
                        return 2.0
                    if raw_value > 1.0:
                        return 1.0
                    if raw_value >= 0.8:
                        return 3.0
                    if raw_value >= 0.55:
                        return 2.0
                    return 1.0

                normalized_details: list[dict] = []
                if skill_details:
                    seen_keys: set[str] = set()
                    for detail in skill_details:
                        skill_name = str(detail.get("skill", "")).strip()
                        if not skill_name:
                            continue
                        key = skill_name.lower()
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)

                        raw_importance = detail.get("importance", 0.6)
                        try:
                            importance_value = float(raw_importance)
                        except (TypeError, ValueError):
                            importance_value = 0.6

                        normalized_details.append(
                            {
                                "skill": skill_name,
                                "importance": to_importance_tier(importance_value),
                                "evidence_snippet": detail.get("evidence_snippet"),
                            }
                        )

                if normalized_details:
                    unique_tiers = {float(item.get("importance", 2.0)) for item in normalized_details}
                    if len(unique_tiers) == 1 and len(normalized_details) >= 2:
                        ranked_details = sorted(
                            normalized_details,
                            key=lambda item: (
                                len(str(item.get("evidence_snippet") or "")),
                                str(item.get("skill") or "").lower(),
                            ),
                            reverse=True,
                        )

                        total = len(ranked_details)
                        top_cut = max(1, round(total * 0.3))
                        mid_cut = max(top_cut + 1, round(total * 0.7))

                        for idx, item in enumerate(ranked_details):
                            if idx < top_cut:
                                item["importance"] = 3.0
                            elif idx < mid_cut:
                                item["importance"] = 2.0
                            else:
                                item["importance"] = 1.0

                if not normalized_details and not skills_text:
                    return

                if not normalized_details:
                    skill_names = [item.strip() for item in skills_text.split(",") if item.strip()]
                    deduped: list[str] = []
                    seen: set[str] = set()
                    for skill_name in skill_names:
                        key = skill_name.lower()
                        if key in seen:
                            continue
                        seen.add(key)
                        deduped.append(skill_name)
                    normalized_details = [
                        {
                            "skill": skill_name,
                            "importance": 2.0,
                            "evidence_snippet": None,
                        }
                        for skill_name in deduped
                    ]

                for detail in normalized_details:
                    skill_name = detail["skill"]
                    skill = db.query(Skill).filter(func.lower(Skill.name) == skill_name.lower()).first()
                    if not skill:
                        skill = Skill(name=skill_name, category="technical", aliases=[], is_active=True)
                        db.add(skill)
                        db.flush()

                    db.add(
                        JobSkill(
                            job_job_id=job.job_id,
                            skill_skill_id=skill.skill_id,
                            importance=detail["importance"],
                            evidence_snippet=detail.get("evidence_snippet"),
                        )
                    )

            salary_min, salary_max, currency = parse_salary_fields(job_data.get("salary_range"))
            raw_description = job_data.get("description") or ""
            cleaned_description = self._clean_lines(raw_description)
            company = upsert_company(job_data.get("company_name") or "N/A", job_data.get("location"))
            existing_job = db.query(Job).filter(Job.source_url == job_data["source_url"]).first()

            if existing_job:
                existing_job.title = job_data["title"]
                existing_job.company_company_id = company.company_id
                existing_job.location = job_data["location"]
                existing_job.salary_min = salary_min
                existing_job.salary_max = salary_max
                existing_job.currency = currency
                existing_job.description_raw = raw_description
                existing_job.description_clean = cleaned_description
                existing_job.source_site = job_data["source_website"]
                existing_job.scraped_at = datetime.now(timezone.utc)
                existing_job.status = JobStatus.active

                replace_job_skills(existing_job, job_data.get("job_requirements"), job_data.get("job_skill_details"))
                db.commit()
                db.refresh(existing_job)
                print(f"--- UPDATED --- {existing_job.title}")
                return existing_job

            new_job = Job(
                company_company_id=company.company_id,
                title=job_data["title"],
                location=job_data["location"],
                salary_min=salary_min,
                salary_max=salary_max,
                currency=currency,
                description_raw=raw_description,
                description_clean=cleaned_description,
                source_url=job_data["source_url"],
                source_site=job_data["source_website"],
                scraped_at=datetime.now(timezone.utc),
                status=JobStatus.active,
            )
            db.add(new_job)
            db.flush()

            replace_job_skills(new_job, job_data.get("job_requirements"), job_data.get("job_skill_details"))
            db.commit()
            db.refresh(new_job)
            print(f"--- CREATED --- {new_job.title}")
            return new_job
        except SQLAlchemyError as exc:
            db.rollback()
            print(f"Lỗi Database: {exc}")
            return None


class CrawlerService:
    @staticmethod
    def crawl_job(db: Session, url: str):
        crawler = JobCrawler()
        job_data = crawler.get_job_info(url)
        if not job_data:
            raise ValueError("Không crawl được dữ liệu job từ URL đã cung cấp")

        crawler.save_job_to_db(db, job_data)
        return job_data

    @staticmethod
    def crawl_jobs(db: Session, urls: Iterable[str]):
        crawler = JobCrawler()
        results = []
        for url in urls:
            if not crawler.is_topdev_detail_url(url):
                results.append(
                    {
                        "url": url,
                        "status": "skipped",
                        "reason": "topdev_detail_only",
                    }
                )
                continue

            job_data = crawler.get_job_info(url)
            if not job_data:
                results.append({"url": url, "status": "failed"})
                continue

            saved = crawler.save_job_to_db(db, job_data)
            results.append(
                {
                    "url": url,
                    "status": "success" if saved else "failed",
                    "title": job_data.get("title"),
                    "source_website": job_data.get("source_website"),
                }
            )
        return results
