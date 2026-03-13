# NextStep AI Server

## Quick Start for BE

### 0) Tạo file môi trường

Copy file mẫu thành `.env` rồi điền key của bạn:

```powershell
Copy-Item .env.example .env
```

Biến bắt buộc cần điền:

- `GEMINI_API_KEY`
- (tuỳ môi trường) `DB_PASSWORD`, `DATABASE_URL`

### 1) Chạy Database Docker (pgvector + Adminer)

Chạy trong thư mục `ai_job_server`:

```powershell
docker compose up -d
```

- PostgreSQL: `localhost:5433`
- Adminer: `http://localhost:8080`

Thông tin đăng nhập Adminer:

- System: `PostgreSQL`
- Server: `db` (nếu chạy trong Docker network) hoặc `localhost`
- Username: `postgres`
- Password: `123456`
- Database: `ai_job_db`

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

### Lưu ý quan trọng

- AI server đang dùng DB URL ở file `.env`, cổng chuẩn hiện tại là `5433`.
- Nếu máy có PostgreSQL local chạy cổng `5432`, vẫn không ảnh hưởng luồng Docker ở `5433`.
