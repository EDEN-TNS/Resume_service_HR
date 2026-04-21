import base64
import imghdr
import io
import os
import re
import warnings

import numpy as np
import torch
from PIL import Image, ImageFile

import easyocr
from src.utils.global_logger import debug, info, warning
from src.utils.http_client import get_http_client

# 손상된 이미지 파일도 로드할 수 있도록 설정
ImageFile.LOAD_TRUNCATED_IMAGES = True

# PyTorch RNN 모듈의 메모리 경고 필터링 (EasyOCR 내부 사용으로 인한 경고)
warnings.filterwarnings("ignore", message="RNN module weights are not part of single contiguous chunk of memory")

# ------------------------------
# EasyOCR 기반 이미지 OCR
# ------------------------------

# Base64 이미지 패턴 상수
BASE64_IMAGE_PATTERN = r"!\[([^\]]*)\]\(data:image/(?:png|jpeg|jpg);base64,([^)]+)\)"
_easy_reader = None

def _is_oom_error(error: Exception) -> bool:
    """
    OOM(Out of Memory) 에러인지 확인
    
    Args:
        error: 확인할 예외 객체
        
    Returns:
        bool: OOM 에러인 경우 True
    """
    error_str = str(error).lower()
    error_type = type(error).__name__
    
    # CUDA OOM 에러 패턴
    oom_patterns = [
        "out of memory",
        "cuda out of memory",
        "runtimeerror: cuda out of memory",
        "cudaerror: out of memory",
        "allocator failed",
        "memory allocation failed",
        # cuDNN 관련 메모리 에러
        "cudnn_status_internal_error",
        "cudnn error",
        "cudnn_status_alloc_failed",
        # cuBLAS 관련 메모리 에러
        "cublas_status_alloc_failed",
        "cublas error",
    ]
    
    # OOM 관련 예외 타입
    oom_exception_types = [
        "RuntimeError",
        "CUDAError",
        "MemoryError",
    ]
    
    # 패턴 매칭
    for pattern in oom_patterns:
        if pattern in error_str:
            return True
    
    # 예외 타입 확인
    if error_type in oom_exception_types:
        if "memory" in error_str or "cuda" in error_str:
            return True
    
    return False


def _cleanup_gpu_memory():
    """
    GPU 메모리 정리
    """
    try:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            debug("🧹 GPU 메모리 정리 완료")
    except Exception as e:
        warning(f"⚠️ GPU 메모리 정리 중 오류: {e}")


def _safe_ocr(img: Image.Image) -> str:
    """
    Extract text from image using EasyOCR.
    
    OOM 에러 발생 시 예외를 재발생시켜 상위 재시도 메커니즘이 작동하도록 함.
    일반 에러는 빈 문자열을 반환하여 하위 호환성 유지.
    
    Returns:
        str: OCR로 추출된 텍스트, 또는 빈 문자열 (일반 에러 시)
        
    Raises:
        Exception: OOM 에러인 경우 예외 재발생
    """
    try:
        global _easy_reader
        if _easy_reader is None:
            gpu_available = torch.cuda.is_available()
            # debug(f"GPU 사용 가능: {gpu_available}")
            _easy_reader = easyocr.Reader(
                ["ko", "en"],
                gpu=gpu_available,
            )
            info("✅ EasyOCR 모델 초기화 완료")

        text_lines = _easy_reader.readtext(np.array(img), detail=0, paragraph=True)
        result = "\n".join(text_lines).strip()
        # debug(f"OCR 처리 완료. 텍스트 라인 수: {len(text_lines)}")
        return result
    except Exception as e:
        # OOM 에러인지 확인
        if _is_oom_error(e):
            warning(f"⚠️ EasyOCR OOM 에러 발생: {e}")
            debug("   GPU 메모리 정리 후 예외 재발생 (상위 재시도 메커니즘 작동)")
            # GPU 메모리 정리
            _cleanup_gpu_memory()
            # OOM 에러는 예외를 재발생시켜 상위 재시도 메커니즘이 작동하도록 함
            raise
        else:
            # 일반 에러는 빈 문자열 반환 (하위 호환성 유지)
            warning(f"⚠️ EasyOCR failed (non-OOM): {e}")
            return ""
    
def _to_data_url(image_bytes: bytes) -> str:
    # png/jpeg/gif/webp 등 자동 판별 (fallback: png)
    ext = imghdr.what(None, h=image_bytes) or "png"
    mime = {
        "png": "image/png",
        "jpeg": "image/jpeg",
        "jpg": "image/jpeg",
        "gif": "image/gif",
        "webp": "image/webp",
        "bmp": "image/bmp",
        "tiff": "image/tiff",
    }.get(ext.lower(), "image/png")
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{mime};base64,{b64}"
    
    
async def _ocr_with_chandra(image_bytes: bytes, timeout: float = 600) -> str:
    """
    이미지 1장을 Chandra-OCR(vLLM Vision)로 보내 '순수 텍스트'만 받아온다.
    - 결과는 프롬프트에 붙일 OCR 텍스트로 사용.
    """
    CHANDRA_API_BASE = os.environ.get("CHANDRA_OCR_URL", "http://192.168.14.248:18000/v1")
    CHANDRA_MODEL = "chandra"
    data_url = _to_data_url(image_bytes)
    prompt = (
        "You are an OCR transcriber.\n"
        "- Extract PLAIN TEXT ONLY from the document image.\n"
        "- Keep reading order and line breaks.\n"
        "- Do not add explanations, JSON, or markdown fences."
    )
    payload = {
        "model": CHANDRA_MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }],
        "temperature": 0.0,
        "max_tokens": 8192,
        "seed": 42,
    }
    url = f"{CHANDRA_API_BASE}/chat/completions"

    client = get_http_client(timeout=timeout)
    r = await client.post(url, json=payload)
    r.raise_for_status()
    j = r.json()
    text = (j.get("choices", [{}])[0].get("message", {}) or {}).get("content", "") or ""

    # 가끔 ```로 감싸면 제거
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[-1].strip()
    return t


def _decode_b64_image(b64: str) -> Image.Image:
    """base64str to PIL Image"""
    data = base64.b64decode(b64)
    img = Image.open(io.BytesIO(data)).convert("RGB")
    return img


def inject_image_ocr(md: str) -> str:
    """
    base64 image to replace OCR text.
    
    OOM 에러 발생 시 예외를 재발생시켜 상위 재시도 메커니즘이 작동하도록 함.
    """

    def repl(m: re.Match) -> str:
        _ = m.group(1)  # alt_text (not used)
        b64 = m.group(2)
        # debug(f"base64 이미지 발견: {alt_text}, 데이터 길이: {len(b64)}")
        img = _decode_b64_image(b64)
        
        # # === 이미지 저장 코드 추가 ===
        # output_dir = "markdown_result/document_artifacts"
        # os.makedirs(output_dir, exist_ok=True)
        # timestamp = time.strftime("%Y%m%d_%H%M%S")
        # img_filename = f"image_{timestamp}_{alt_text}.png"
        # img_path = os.path.join(output_dir, img_filename)
        # img.save(img_path)
        # debug(f"이미지 저장 완료: {img_path}")
        
        # OCR (OOM 에러는 예외로 전파됨)
        ocr = _safe_ocr(img)
        debug(f"OCR 결과: '{ocr}'")
        if ocr:
            return f"\n{ocr}\n"
        else:
            return "\n"      

    try:
        return re.sub(BASE64_IMAGE_PATTERN, repl, md)
    except Exception as e:
        # OOM 에러인 경우 예외를 재발생시켜 상위 재시도 메커니즘이 작동하도록 함
        if _is_oom_error(e):
            warning(f"⚠️ inject_image_ocr에서 OOM 에러 발생: {e}")
            raise
        else:
            # 일반 에러는 기존 마크다운 반환 (하위 호환성)
            warning(f"⚠️ inject_image_ocr에서 일반 에러 발생: {e}")
            return md


