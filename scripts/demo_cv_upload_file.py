import json
import requests

url = "http://localhost:9000/api/v1/cv/ingest-file"
file_path = "scripts/sample_cv_upload.txt"

with open(file_path, "rb") as file_handle:
    files = {
        "cv_file": ("sample_cv_upload.txt", file_handle, "text/plain")
    }
    data = {
        "job_id": "3",
        "timeframe_weeks": "24",
        "max_skills_per_phase": "4"
    }
    response = requests.post(url, files=files, data=data, timeout=30)

print("Status:", response.status_code)
parsed = response.json()

if response.status_code == 200:
    print("Match score:", parsed["job_match"]["score"])
    print("Roadmap weeks:", parsed["roadmap"]["total_weeks"])
    print("Phases:", len(parsed["roadmap"]["phases"]))
else:
    print(json.dumps(parsed, ensure_ascii=False, indent=2))
