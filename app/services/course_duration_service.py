from __future__ import annotations

import re


class CourseDurationService:
    DEFAULT_HOURS_PER_WEEK = 8

    @staticmethod
    def _normalize_text(value: str | None) -> str:
        return str(value or "").strip()

    @staticmethod
    def _extract_number(token: str) -> float | None:
        match = re.search(r"(\d+(?:\.\d+)?)", token)
        if not match:
            return None
        try:
            return float(match.group(1))
        except ValueError:
            return None

    @classmethod
    def _extract_unit_tokens(cls, text: str) -> list[str]:
        patterns = [
            r"\b\d+(?:\.\d+)?\s*(?:hours?|hrs?)\b",
            r"\b\d+(?:\.\d+)?\s*(?:hours?|hrs?)\s*(?:per week|a week|each week|/week)\b",
            r"\b\d+(?:\.\d+)?\s*(?:weeks?)\b",
            r"\b\d+(?:\.\d+)?\s*(?:months?)\b",
            r"\b\d+(?:\.\d+)?\s*(?:days?)\b",
            r"\bapproximately\s+\d+(?:\.\d+)?\s*(?:hours?|weeks?|months?|days?)\b",
        ]

        lower = cls._normalize_text(text).lower()
        tokens: list[str] = []
        for pattern in patterns:
            for match in re.finditer(pattern, lower):
                token = cls._normalize_text(match.group(0))
                if token:
                    tokens.append(token)
        return list(dict.fromkeys(tokens))

    @classmethod
    def parse_duration_hours(cls, duration_text: str | None) -> int | None:
        text = cls._normalize_text(duration_text).lower()
        if not text:
            return None

        if "completion path" in text:
            lead_hours = re.match(r"^\s*(\d+(?:\.\d+)?)\s*(hours?|hrs?)\b", text)
            if lead_hours:
                try:
                    return round(float(lead_hours.group(1)))
                except ValueError:
                    return None

        per_week_match = re.search(r"(\d+(?:\.\d+)?)\s*(hours?|hrs?)\s*(?:per week|a week|each week|/week)", text)
        weekly_hours = None
        if per_week_match:
            try:
                weekly_hours = float(per_week_match.group(1))
            except ValueError:
                weekly_hours = None

        month_match = re.search(r"(\d+(?:\.\d+)?)\s*(months?)\b", text)
        if month_match:
            try:
                months = float(month_match.group(1))
                return round(months * 4 * (weekly_hours or cls.DEFAULT_HOURS_PER_WEEK))
            except ValueError:
                return None

        week_match = re.search(r"(\d+(?:\.\d+)?)\s*(weeks?)\b", text)
        if week_match:
            try:
                weeks = float(week_match.group(1))
                return round(weeks * (weekly_hours or cls.DEFAULT_HOURS_PER_WEEK))
            except ValueError:
                return None

        day_match = re.search(r"(\d+(?:\.\d+)?)\s*(days?)\b", text)
        if day_match:
            try:
                days = float(day_match.group(1))
                return round(days * (weekly_hours or cls.DEFAULT_HOURS_PER_WEEK))
            except ValueError:
                return None

        hour_match = re.search(r"(\d+(?:\.\d+)?)\s*(hours?|hrs?)\b", text)
        if hour_match:
            try:
                return round(float(hour_match.group(1)))
            except ValueError:
                return None

        token_candidates = cls._extract_unit_tokens(text)
        best_hours: int | None = None
        for token in token_candidates:
            hours = cls.parse_duration_hours(token)
            if hours is None:
                continue
            if best_hours is None or hours > best_hours:
                best_hours = hours
        return best_hours

    @classmethod
    def extract_duration_token(cls, raw_text: str | None) -> str | None:
        text = cls._normalize_text(raw_text)
        if not text:
            return None

        lower = text.lower()
        if "completion path" in lower:
            match = re.search(r"^\s*\d+(?:\.\d+)?\s*(?:hours?|hrs?)\b(?:\s*\([^)]*\))?", lower)
            if match:
                return cls._normalize_text(match.group(0))

        tokens = cls._extract_unit_tokens(lower)
        if not tokens:
            return None

        if any("per week" in token or "/week" in token for token in tokens):
            for token in tokens:
                if "week" in token and "per week" not in token and "/week" not in token:
                    return token
                if "month" in token:
                    return token

        best = None
        best_hours = -1
        for token in tokens:
            hours = cls.parse_duration_hours(token)
            if hours is None:
                continue
            if hours > best_hours:
                best = token
                best_hours = hours
        return best
