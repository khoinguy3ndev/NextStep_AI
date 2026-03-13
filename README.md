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

### 1) Chạy Database Docker từ BE (nguồn gốc)

Chạy trong thư mục `NextStep_BE`:

```powershell
docker compose up -d
```

- PostgreSQL: `localhost:5444`

AI server sẽ dùng chung DB này qua `DATABASE_URL`.

Thông số DB hiện tại của BE mà AI đang dùng chung:

- Host: `localhost`
- Port: `5444`
- Username: `nextstep`
- Database: `postgres`

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

- BE là nguồn cấu hình DB chính; AI chỉ kết nối theo BE.
- AI server đang dùng DB URL ở file `.env`, cổng chuẩn hiện tại là `5444`.
- File [ai_job_server/docker-compose.yml](ai_job_server/docker-compose.yml) không còn tạo DB riêng; chỉ dùng để mở Adminer cùng network với BE.
