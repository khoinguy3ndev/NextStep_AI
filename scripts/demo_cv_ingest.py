import json
import requests

url = "http://localhost:9000/api/v1/cv/ingest"

payload = {
    "job_id": 3,
    "timeframe_weeks": 24,
    "max_skills_per_phase": 4,
    "cv_text": """
Nguyen Van A
Email: nguyenvana@gmail.com
Location: Ho Chi Minh

Summary:
Junior backend developer with 2 years of experience.
Worked with Python, SQL, Docker and Git.
Built REST API with FastAPI and PostgreSQL.
Basic understanding of React and AWS.

Experience:
- 2 years software development experience
- Collaborated with CI/CD team

Certificates:
- AWS Certified Cloud Practitioner
""",
}

response = requests.post(url, json=payload, timeout=20)
print("Status:", response.status_code)

try:
    data = response.json()
except Exception:
    print(response.text)
    raise

print("\n=== SUMMARY ===")
if response.status_code == 200:
    print("Match Score:", data["job_match"]["score"])
    print("Missing Skills:", data["job_match"]["missingSkills"])
    print("Recommended Skills:", data["gap_analysis"]["recommendedSkills"])
    print("Roadmap Total Weeks:", data["roadmap"]["total_weeks"])
    print("Roadmap Difficulty:", data["roadmap"]["difficulty_level"])
    print("Phases:", len(data["roadmap"]["phases"]))
else:
    print(json.dumps(data, ensure_ascii=False, indent=2))

print("\n=== FULL RESPONSE ===")
print(json.dumps(data, ensure_ascii=False, indent=2))
