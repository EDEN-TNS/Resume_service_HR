"""
HR 전용 로컬 처리기 - /test_resume 단일 경로를 위한 최소 구성
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any, Callable, Dict, TypeVar

from fastapi import UploadFile

from src.document_processing.document_preprocessor import preprocess_document
from src.llm_extraction import extract_resume_info
from src.llm_extraction.extract_prompt import extract_publications_info
from src.utils.debug_file import DebugFileManager
from src.utils.global_logger import debug, info, warning
from src.utils.token_count import count_tokens

T = TypeVar("T")

# OOM 재시도 설정 (환경 변수로 제어 가능)
OOM_MAX_RETRIES = int(os.getenv("OOM_MAX_RETRIES", "3"))
OOM_RETRY_DELAY = float(os.getenv("OOM_RETRY_DELAY", "5.0"))  # seconds


def is_oom_error(error: Exception) -> bool:
    error_str = str(error).lower()
    error_type = type(error).__name__

    oom_patterns = [
        "out of memory",
        "cuda out of memory",
        "runtimeerror: cuda out of memory",
        "cudaerror: out of memory",
        "allocator failed",
        "memory allocation failed",
    ]
    oom_exception_types = {"RuntimeError", "CUDAError", "MemoryError"}

    if any(p in error_str for p in oom_patterns):
        return True

    if error_type in oom_exception_types and ("memory" in error_str or "cuda" in error_str):
        return True

    return False


def cleanup_gpu_memory() -> None:
    # CPU-only 모드: CUDA 관련 호출을 하지 않는다.
    return


async def retry_on_oom(
    func: Callable[..., T],
    *args,
    max_retries: int = OOM_MAX_RETRIES,
    retry_delay: float = OOM_RETRY_DELAY,
    **kwargs,
) -> T:
    last_exception: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            return func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if not is_oom_error(e):
                raise

            if attempt >= max_retries:
                raise

            warning(f"⚠️ OOM 에러 발생 (시도 {attempt + 1}/{max_retries + 1}): {str(e)}")
            cleanup_gpu_memory()
            await asyncio.sleep(retry_delay)

    raise last_exception or RuntimeError("Unexpected error in retry_on_oom")


class HrTaskProcessor:
    """
    HR Agent용 로컬 즉시 처리기.

    - RabbitMQ/비동기 task_id 모델을 제거하고, 업로드 1건을 바로 처리해 JSON으로 반환한다.
    """

    def __init__(self):
        self.debug_manager = DebugFileManager()

    async def process_resume(self, file: UploadFile) -> Dict[str, Any]:
        start = time.time()
        result = await retry_on_oom(self._process_resume_extraction, file)
        info(f"⏱️ [HR] resume 처리 시간: {time.time() - start:.2f}s")
        return result

    async def _process_resume_extraction(self, file: UploadFile) -> Dict[str, Any]:
        loop = asyncio.get_running_loop()
        processed_markdown, genre, remember_result, sections_journal_result = await loop.run_in_executor(
            None, preprocess_document, file
        )

        # Remember 형식에서 OCR 실패한 경우
        if genre == "remember" and remember_result and not processed_markdown:
            return remember_result

        token_count = count_tokens(processed_markdown)
        resume_info = await extract_resume_info(processed_markdown)

        publications_info = None
        if sections_journal_result:
            try:
                if sections_journal_result.get("sections_journal_result"):
                    publications_info = await extract_publications_info(sections_journal_result["sections_journal_result"])
                else:
                    debug("📄 논문 섹션이 없어 논문 정보 추출 생략")
            except Exception as e:
                warning(f"❌ 논문 정보 추출 중 오류 발생: {str(e)}")

        resume_info.update(
            {
                "markdown_length": len(processed_markdown),
                "token_count": token_count,
                "genre": genre,
                "publications_info": publications_info,
            }
        )

        self.debug_manager.save_json_result(resume_info, file.filename)
        return resume_info

