from __future__ import annotations

import json
import re
from typing import Any

from google import genai

from app.core.config import settings


class AIService:
	@staticmethod
	def _build_client() -> genai.Client:
		return genai.Client(
			api_key=settings.GEMINI_API_KEY,
			http_options={"api_version": "v1"},
		)

	@staticmethod
	def _extract_json(text: str) -> dict[str, Any] | None:
		if not text:
			return None

		normalized = text.strip()
		try:
			loaded = json.loads(normalized)
			if isinstance(loaded, dict):
				return loaded
		except json.JSONDecodeError:
			pass

		match = re.search(r"\{[\s\S]*\}", normalized)
		if not match:
			return None

		try:
			loaded = json.loads(match.group(0))
			if isinstance(loaded, dict):
				return loaded
		except json.JSONDecodeError:
			return None
		return None

	@staticmethod
	def extract_skills(jd_text: str) -> str:
		if not jd_text or len(jd_text.strip()) < 50:
			return "Mô tả công việc quá ngắn."

		try:
			client = AIService._build_client()
			prompt = f"Trích xuất danh sách kỹ năng IT từ văn bản sau (chỉ trả về từ khóa, cách nhau bằng dấu phẩy): {jd_text}"
			response = client.models.generate_content(
				model="gemini-1.5-flash",
				contents=prompt,
			)
			if response and response.text:
				return response.text.strip()
			return "AI không trả về kỹ năng."
		except Exception as exc:
			print(f"--- THÔNG BÁO LỖI: {str(exc)} ---")
			return f"Lỗi AI: {str(exc)}"

	@staticmethod
	def extract_cv_profile(cv_text: str, skill_candidates: list[str]) -> dict[str, Any] | None:
		if not settings.CV_AI_ENRICHMENT_ENABLED:
			return None

		if not settings.GEMINI_API_KEY:
			return None

		cleaned_text = (cv_text or "").strip()
		if len(cleaned_text) < 80:
			return None

		limited_text = cleaned_text[:8000]
		candidate_text = ", ".join(skill_candidates[:400])

		prompt = (
			"Bạn là chuyên gia phân tích CV IT. "
			"Hãy trích xuất hồ sơ ứng viên và chỉ trả về JSON hợp lệ, không thêm markdown. "
			"Schema JSON:\n"
			"{\n"
			'  "cv_level": "intern|junior|mid|senior|lead",\n'
			'  "cv_years_experience": number,\n'
			'  "preferred_locations": [string],\n'
			'  "cv_certifications": [string],\n'
			'  "cv_skills": [\n'
			'    {"name": string, "proficiency": number(0..1), "years_of_experience": number >= 0}\n'
			"  ]\n"
			"}\n"
			"Yêu cầu:\n"
			"- Chỉ chọn skill trong danh sách ứng viên nếu có thể.\n"
			"- Không bịa thông tin; nếu không rõ thì để giá trị bảo thủ (0 hoặc mảng rỗng).\n"
			"- Dùng tiếng Anh cho tên skill nếu có thể.\n\n"
			f"Danh sách skill ứng viên: {candidate_text}\n\n"
			f"CV text:\n{limited_text}"
		)

		try:
			client = AIService._build_client()
			response = client.models.generate_content(
				model="gemini-1.5-flash",
				contents=prompt,
			)
			text = (response.text or "").strip() if response else ""
			if not text:
				return None

			data = AIService._extract_json(text)
			if not data:
				return None
			return data
		except Exception as exc:
			print(f"--- CV AI ENRICHMENT ERROR: {exc} ---")
			return None
