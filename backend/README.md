# SEDU Backend

FastAPI backend for the SEDU project with PostgreSQL integration.

## Setup

```bash
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1   # Windows PowerShell
# source venv/bin/activate    # macOS / Linux
pip install -r requirements.txt
```

## Run PostgreSQL (Docker)

```bash
docker run --name sedu-postgres \
  -e POSTGRES_USER=sedu \
  -e POSTGRES_PASSWORD=sedu \
  -e POSTGRES_DB=sedu \
  -p 5432:5432 \
  -d postgres:15
```

Apply schema:

```bash
docker exec -i sedu-postgres psql -U sedu -d sedu < migrations/schema.sql
```

## Configure DATABASE_URL

PowerShell:

```powershell
$env:DATABASE_URL="postgresql+psycopg://sedu:sedu@localhost:5432/sedu"
```

bash/zsh:

```bash
export DATABASE_URL="postgresql+psycopg://sedu:sedu@localhost:5432/sedu"
```

## Run API server

```bash
uvicorn app.main:app --reload
```

Server starts at http://localhost:8000

## API Endpoints

| Method | Path                                         | Description                 |
|--------|----------------------------------------------|-----------------------------|
| GET    | /health                                      | Health check                         |
| POST   | /v1/sets                                     | Upload file metadata + create set    |
| GET    | /v1/sets/{setPublicId}                       | Get set detail from DB               |
| GET    | /v1/sets/{setPublicId}/questions             | List questions in set from DB        |
| POST   | /v1/sets/{setPublicId}/extraction-jobs       | Create extraction job row            |
| GET    | /v1/extraction-jobs/{jobPublicId}            | Get job status/stage/percent from DB |
| GET    | /v1/questions/{questionPublicId}             | Get question detail from DB          |
| PATCH  | /v1/questions/{questionPublicId}             | Patch question fields in DB          |
| GET    | /docs                                        | Swagger UI (auto)                    |

## ID Strategy

- Internal DB primary keys: UUID v4
- Public IDs exposed to frontend: `{prefix}{ULID}`
  - `set_01J...`, `job_01J...`, `q_01J...`, `a_01J...`

## Fake Extraction Simulator

MVP 테스트용 가짜 추출 파이프라인이 내장되어 있습니다.

1. `POST /v1/sets` 로 파일을 업로드하여 세트 생성
2. `POST /v1/sets/{setId}/extraction-jobs` 로 추출 작업 생성
3. 백그라운드에서 자동으로 시뮬레이터가 실행됨:
   - `preprocess` → `layout_analysis` → `crop_questions` → `ocr` → `structuring` 단계를 거치며 진행률 업데이트
   - 약 5초 후 5개의 플레이스홀더 문제가 자동 생성
4. `GET /v1/extraction-jobs/{jobId}` 로 진행 상태 폴링
5. 완료 후 `GET /v1/sets/{setId}/questions` 로 생성된 문제 조회

## Google Cloud Vision OCR

문제 크롭 이미지에서 텍스트를 추출하기 위해 Cloud Vision `DOCUMENT_TEXT_DETECTION`을 사용합니다.

### 1. Vision API 활성화

1. [Google Cloud Console](https://console.cloud.google.com/) → API 및 서비스 → Cloud Vision API 활성화
2. 서비스 계정 생성 → JSON 키 다운로드

### 2. 인증 설정

PowerShell:

```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS="C:\path\to\service-account.json"
```

bash/zsh:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
```

### 3. 파이프라인 구조

```
업로드 이미지 → 문제 크롭 → Vision OCR (word별 bbox + confidence) → DB 저장
                                                                  ↓
                                                        Gemini 구조화 (추후)
```

- `app/ocr/vision_client.py` — Vision API 호출 및 응답 정규화
- `app/pipeline/ocr_step.py` — 문제 단위 OCR 실행 및 DB 반영
- OCR 결과는 `questions.ocr_text`, `questions.structure.ocr_tokens`, `questions.metadata.ocr_avg_confidence`에 저장

## Database

Schema lives in `migrations/schema.sql` (PostgreSQL 15+).
API endpoints are wired to PostgreSQL via SQLAlchemy 2.0 + psycopg.
