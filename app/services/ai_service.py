from google import genai
from app.core.config import settings

class AIService:
    @staticmethod
    def extract_skills(jd_text: str) -> str:
        if not jd_text or len(jd_text.strip()) < 50:
            return "Mô tả công việc quá ngắn."

        try:
            # FIX TRIỆT ĐỂ: Ép sử dụng API version 'v1' thay vì 'v1beta'
            client = genai.Client(
                api_key=settings.GEMINI_API_KEY,
                http_options={'api_version': 'v1'}
            )

            prompt = f"Trích xuất danh sách kỹ năng IT từ văn bản sau (chỉ trả về từ khóa, cách nhau bằng dấu phẩy): {jd_text}"

            # Thử gọi model với tên đầy đủ để tránh nhầm lẫn
            response = client.models.generate_content(
                model="gemini-1.5-flash", 
                contents=prompt
            )

            if response and response.text:
                return response.text.strip()

            return "AI không trả về kỹ năng."

        except Exception as e:
            # In lỗi chi tiết ra Terminal để bạn thấy được nguyên nhân thật sự
            print(f"--- THÔNG BÁO LỖI: {str(e)} ---")
            return f"Lỗi AI: {str(e)}"