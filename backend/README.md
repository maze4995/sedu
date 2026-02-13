# SEDU Backend v2 (Sprint 1)

SEDU 백엔드 재시작 버전입니다. 기존 코드는 `backend_legacy/`에 보관됩니다.

## 목표

- FastAPI 기반 v2 API 계약 고정
- A단계(문제 Crop/메타데이터)의 엔드포인트 스켈레톤 제공
- Port/Adapter 구조로 OCR/LLM/Storage 의존성 분리

## 실행

```bash
cd backend
python3 -m venv .venv
# Windows
.venv\\Scripts\\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload
```

`python3 -m venv`가 실패하면(ensurepip 없음), 시스템 패키지 설치가 필요합니다.
```bash
sudo apt install python3.12-venv python3-pip
```

서버: `http://localhost:8000`
Swagger: `http://localhost:8000/docs`

## 디렉터리

- `app/api/v2`: HTTP 라우터와 스키마
- `app/application`: 유스케이스 서비스
- `app/domain`: 도메인 모델/타입
- `app/infra/db`: SQLAlchemy 모델/세션/DB Store
- `app/infra/ports`: 포트 인터페이스
- `app/infra/storage|ocr|llm`: 외부 의존 어댑터 구현
- `tests`: Sprint 1 계약 테스트

## 운영 기본값

- Runtime: FastAPI
- Data target: PostgreSQL + Object Storage(S3형)
- Local dev/test: SQLite + Local file + Mock OCR/LLM

## 환경 변수

- `DATABASE_URL`
  - 기본값: `sqlite:///backend/sedu_v2.db`
  - PostgreSQL 예시: `postgresql+psycopg://sedu:sedu@localhost:5432/sedu`
- `SEDU_JOB_STAGE_DELAY_MS`
  - 기본값: `0`
  - 개발 중 job 상태 전이(queued/running/done) 확인용 단계 지연(ms)
  - 예시: `SEDU_JOB_STAGE_DELAY_MS=800`

## Job 디버깅

- `GET /v2/jobs/{jobId}`: 현재 상태 조회
- `GET /v2/jobs/{jobId}/events`: 상태 전이 이력(queued/running/done 타임라인) 조회
