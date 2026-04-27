"""
통합 API 서버 - RabbitMQ 기반 비동기 처리 + 동기 처리 지원
"""

import os
from io import BytesIO

import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from src.utils.debug_file import set_debug_mode
from src.utils.file_validator import get_file_validator
from src.utils.global_logger import debug, error, info

# 환경 변수 설정
debug_mode = os.getenv("DEBUG_MODE", "false").lower() == "true"

# 디버그 모드 설정
set_debug_mode(debug_mode)

def _use_mock_processor() -> bool:
    return os.getenv("MOCK_HR_PROCESSOR", "false").lower() == "true"


if _use_mock_processor():
    class _MockTaskProcessor:
        async def process_resume(self, file: UploadFile):  # noqa: ANN001
            return {
                "status": "ok",
                "message": "mocked processor (MOCK_HR_PROCESSOR=true)",
                "filename": getattr(file, "filename", None),
            }

    task_processor = _MockTaskProcessor()
else:
    from src.engine.hr_task_processor import HrTaskProcessor

    # 로컬 처리용 프로세서
    task_processor = HrTaskProcessor()

app = FastAPI(
    title="Resume Extract Service API",
    description="Minimal API exposing /test_resume only",
)

# Docker 이미지에는 swagger 정적 파일이 /app/swagger_ui 로 복사된다.
# 작업 디렉터리(/app) 기준 상대경로로 마운트한다.
app.mount("/static", StaticFiles(directory="swagger_ui"), name="static")
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title="Resume Extract Service API-Docs",
        swagger_js_url="/static/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger-ui.css",
    )

@app.get("/health")
async def health_check():
    """헬스 체크"""
    debug("🏥 [Health] 헬스 체크")
    return {
        "status": "healthy",
        "message": "API is running",
        "api": "test_resume_only",
    }

@app.post("/test_resume/")
async def create_upload_file(file: UploadFile):
    """
    test_resume route - 다른 서버의 test_resume 엔드포인트와 호환성을 위해 추가
    RabbitMQ 없이 로컬에서 즉시 처리 (동기 응답 형태) - HR Agent용
    """
    try:
        # 1. API 요청 수신
        info(f"📥 [요청] test_resume 요청 수신: {file.filename}")
        
        # 파일 검증
        validator = get_file_validator()
        validation_info = await validator.validate_upload_file(file)
        
        # 파일 읽기
        file_content = await file.read()
        
        # 파일 내용 검증 (크기 포함)
        validator.validate_file_content(file_content, validation_info['filename'])

        # 2. 로컬에서 즉시 처리 (RabbitMQ 제거)
        upload_file = UploadFile(
            file=BytesIO(file_content),
            filename=validation_info["filename"],
            headers={"content-type": file.content_type or "application/octet-stream"},
        )

        result = await task_processor.process_resume(upload_file)

        # 3. 처리 완료
        info("✅ [완료] test_resume 처리 완료 (로컬 처리)")

        # 결과를 JSONResponse로 직접 반환 (다른 서버 형식과 동일)
        return JSONResponse(content=result)
        
    except HTTPException:
        raise
    except Exception as e:
        error(f"❌ [에러] test_resume 처리 실패: {str(e)}")
        output = {}
        output["status"] = "Fail"
        output["message"] = f"Error occured: {str(e)}"
        raise HTTPException(status_code=400, detail=output)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
