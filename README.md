# NextStep AI Server

## Quick Start for AI Server

### 0) Tạo file môi trường

Copy file mẫu thành `.env` rồi điền key của bạn:

```powershell
Copy-Item .env.example .env
```

Biến bắt buộc cần điền:

- `GEMINI_API_KEY`
- `DATABASE_URL`

Khuyến nghị dùng Supabase pooler cho runtime:

- `DB_HOST=aws-1-ap-northeast-1.pooler.supabase.com`
- `DB_PORT=6543`
- `DB_NAME=postgres`
- `DB_USERNAME=postgres.<your-project-ref>`

### 1) Kết nối database

AI server dùng chung database Supabase qua `DATABASE_URL`.

Không cần chạy PostgreSQL Docker riêng cho AI server.

Nếu cần migration trực tiếp, dùng `DATABASE_URL` từ `.env`.

### 2) Cào dữ liệu job về DB

```powershell
python .\scripts\run_crawl.py
```

### 3) Chuyển job sang vector (embedding)

```powershell
python -c "from app.db.session import get_standalone_db; from app.services.embedding_service import EmbeddingService; db=get_standalone_db(); print(EmbeddingService.sync_job_embeddings(db, limit=10, only_missing=True)); db.close()"
```

### 4) Kiểm tra dữ liệu

- Bảng job đã crawl: `jobs`
- Bảng vector: `entity_embeddings`
- Bảng skill baseline: `skill_courses`
- Bảng analysis: `cv_analysis_results`, `cv_skills`, `skill_gaps`

### Lưu ý quan trọng

- AI server đọc `.env` trong thư mục [ai_job_server](ai_job_server) dù chạy từ đâu.
- File [ai_job_server/docker-compose.yml](ai_job_server/docker-compose.yml) hiện chỉ để mở Adminer cùng network, không tạo DB riêng.
- Các script crawl/seed đều ghi thẳng vào database qua SQLAlchemy session dùng chung `DATABASE_URL`.
