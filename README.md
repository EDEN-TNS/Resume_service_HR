# Resume Extract Service (HR Minimal API)

이 프로젝트는 **HR Agent 용도**로, 이력서 파일을 업로드하면 **RabbitMQ 없이 로컬에서 즉시 처리**하여 결과를 반환하는 **미니멀 FastAPI** 서비스입니다.

## 제공 API

- **GET `/health`**: 헬스 체크
- **POST `/test_resume/`**: 이력서 추출(파일 업로드) → JSON 결과 반환
- **GET `/docs`**: Swagger UI (정적 파일 필요)

## 실행 방법

### Docker Compose (권장)

레포에 포함된 `docker-compose-hr.yml`은 **test_resume 전용(비 RabbitMQ)** 구성을 사용합니다.

```bash
docker compose -f docker-compose-hr.yml up --build
```

- 기본 매핑 포트: **`http://localhost:8700`** (컨테이너 내부 8000)
- Swagger UI: `http://localhost:8700/docs`

### 로컬 실행 (Python)

```bash
pip install -r requirements.txt
python3 -m src.api.main
# 또는
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

로컬 실행 시 Swagger UI를 쓰려면 정적 파일 디렉터리가 필요합니다.

- 기본 탐색 순서: `./static` → `./swagger_ui`
- 또는 환경변수로 지정: `STATIC_DIR=/path/to/swagger_ui`

## 환경 변수

- **`DEBUG_MODE`**: `true/false` (기본 `false`)
- **`STATIC_DIR`**: Swagger UI 정적 파일 디렉터리 경로(선택)

`docker-compose-hr.yml` 기준으로는 `./swagger_ui`가 컨테이너의 `/app/static`로 마운트되며, API는 이를 `/static/*`으로 서빙합니다.

## 호출 예시

### health

```bash
curl -s "http://localhost:8700/health"
```

### test_resume (파일 업로드)

```bash
curl -X POST "http://localhost:8700/test_resume/" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/resume.pdf"
```

## 구현 위치

- API 진입점: `src/api/main.py`
- 실제 처리 로직: `src/engine/hr_task_processor.py` (`HrTaskProcessor`)

