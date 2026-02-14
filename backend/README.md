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
- `app/workers/extraction`: 전처리/추출 파이프라인 (Phase A MVP)
- `tests`: Sprint 1 계약 테스트

## 운영 기본값

- Runtime: FastAPI
- Data target: PostgreSQL + Object Storage(S3형)
- Local dev/test: SQLite + Local file + Mock OCR/LLM

## 추출 엔진(Phase A MVP)

- PDF: `PyMuPDF` 텍스트/레이아웃 추출
- 이미지: `Google Vision OCR` 또는 `pytesseract + opencv`
- 스캔 PDF(이미지 PDF): 페이지 렌더링 후 Vision OCR 또는 `pytesseract` OCR
- Gemini Full 모드: PDF/이미지를 Gemini 멀티모달로 직접 구조화 추출(문항/메타데이터/crop 힌트)
- 선택사항: OCR 결과를 LLM(Gemini)로 후처리하여 문제 경계/텍스트/메타데이터 보정
- 문제별 이미지 Crop 생성: 업로드 원본에서 문항 단위 세로 분할 후 `/uploads/{setId}/questions/*.png` 저장
- Fallback: 내부 OCR mock/UTF-8 decode

`pytesseract`를 실제로 쓰려면 OS에 Tesseract 바이너리가 필요합니다.
```bash
sudo apt install tesseract-ocr
```

Google Vision OCR을 쓰려면 서비스 계정 키를 준비하고 환경변수를 설정하세요.
```bash
export GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/service-account.json
```

## 환경 변수

- `DATABASE_URL`
  - 기본값: `sqlite:///backend/sedu_v2.db`
  - PostgreSQL 예시: `postgresql+psycopg://sedu:sedu@localhost:5432/sedu`
- `SEDU_JOB_STAGE_DELAY_MS`
  - 기본값: `0`
  - 개발 중 job 상태 전이(queued/running/done) 확인용 단계 지연(ms)
  - 예시: `SEDU_JOB_STAGE_DELAY_MS=800`
- `SEDU_OCR_LANG`
  - 기본값: `kor+eng`
  - Tesseract OCR 언어 설정
- `SEDU_OCR_BACKEND`
  - 기본값: `mock`
  - 값: `mock | vision`
  - `vision` 사용 시 `google-cloud-vision` 패키지 + `GOOGLE_APPLICATION_CREDENTIALS` 필요
- `SEDU_EXTRACTION_LLM_ENABLED`
  - 기본값: `1`
  - `1`이면 A단계 추출에서 LLM 후처리 보정을 시도
- `SEDU_EXTRACTION_MODE`
  - 기본값: `hybrid`
  - 값: `hybrid | gemini_full`
  - `gemini_full`: Gemini가 문서(이미지/PDF)를 직접 읽어 문제/메타데이터/crop 힌트를 생성하고, 실패 시 job을 `failed`로 종료(OCR 폴백 없음)
- `SEDU_LLM_BACKEND`
  - 기본값: `mock`
  - 값: `mock | gemini`
  - `gemini` 사용 시 `GEMINI_API_KEY` 필요
- `GEMINI_MODEL`
  - 기본값: `gemini-2.5-flash`
- `SEDU_LLM_TIMEOUT_SECONDS`
  - 기본값: `90`
- `SEDU_LLM_MAX_RETRIES`
  - 기본값: `1`
  - Gemini 호출 타임아웃/일시적 5xx/429 응답 시 재시도 횟수

## Job 디버깅

- `GET /v2/jobs/{jobId}`: 현재 상태 조회
- `GET /v2/jobs/{jobId}/events`: 상태 전이 이력(queued/running/done 타임라인) 조회

## 세트 관리

- `DELETE /v2/sets/{setId}`: 문제세트 삭제

## AI 생성 엔드포인트

- `GET /v2/questions/{questionId}/variants`: 변형문제 목록 조회 (DB 저장)
- `POST /v2/questions/{questionId}/variants`: 변형문제 1건 생성 (LLM 우선, 실패 시 규칙기반 fallback)
- `POST /v2/questions/{questionId}/hint`: 단계형 힌트 생성 (LLM 우선, 실패 시 규칙기반 fallback)
