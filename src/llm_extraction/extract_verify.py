import base64
import imghdr
import io
import json
import os
from typing import Any, Dict, List

import httpx
from PIL import Image

from src.document_processing.ocr_processing import _ocr_with_chandra, _safe_ocr
from src.llm_extraction.verify_prompts import DocumentPrompts
from src.utils.http_client import get_http_client

_LLM_HTTP_HEADERS = {
    "Content-Type": "application/json",
    "ngrok-skip-browser-warning": "true",
}


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


async def extract_verify_fields(markdown_content: str, doc_type: str, required_fields: List[str] = None) -> Dict[str, Any]:
    """
    주어진 문서(markdown)에서 특정 doc_type에 대해 필드를 추출
    DocumentPrompts에서 문서별 특화 프롬프트 사용
    """
    print("Markdown 기반 LLM 추출")
    import time
    start_time = time.time()

    # 마크다운 길이 제한 (너무 긴 경우 LLM API 에러 발생)
    max_length = 50000
    original_length = len(markdown_content)
    if original_length > max_length:
        print(f"⚠️ 마크다운이 너무 깁니다 ({original_length:,} chars). {max_length:,}자로 제한합니다.")
        markdown_content = markdown_content[:max_length] + "\n\n... (내용이 너무 길어 제한됨)"
    
    print(f"📝 마크다운 길이: {len(markdown_content):,} characters")

    # 문서 타입별 특화 프롬프트 가져오기
    base_prompt, doc_fields = DocumentPrompts.get_prompt_and_fields(doc_type)
    print(f"📋 {doc_type} 문서 특화 프롬프트 사용")

    # 환경변수에서 LLM 설정 가져오기
    vllm_base_url = os.environ.get("VLLM_URL", "http://192.168.14.248:12001/gemma-3-27b")
    llm_url = f"{vllm_base_url.rstrip('/')}/v1/chat/completions"
    llm_model = os.environ.get("VLLM_MODEL", "RedHatAI/gemma-3-27b-it-quantized.w4a16")

    # 프롬프트에 마크다운 콘텐츠 추가
    prompt = f"""{base_prompt}

DOCUMENT CONTENT (Markdown):
---
{markdown_content}
---
"""

    payload = {
        "model": llm_model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 4000,
        "temperature": 0.1,        # 낮은 온도로 일관성 향상
        "repetition_penalty": 1.1, # 반복 방지
        "seed": 42                # 시드 고정으로 재현성 확보
    }

    try:
        client = get_http_client(timeout=180.0)
        response = await client.post(llm_url, json=payload, headers=_LLM_HTTP_HEADERS)
        response.raise_for_status()

        result = response.json()
        response_text = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        # 📊 LLM 응답 원본 미리보기 (debug)
        preview_length = 500
        response_preview = response_text[:preview_length] + "..." if len(response_text) > preview_length else response_text
        print(f"📄 [VERIFY Markdown LLM 응답 미리보기]\n{response_preview}")

        try:
            cleaned = response_text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            start = cleaned.find("{")
            end = cleaned.rfind("}") + 1
            if start != -1 and end != 0:
                json_str = cleaned[start:end]
                json_str = json_str.replace("\\_", "_").replace("\\/", "/")
                data = json.loads(json_str)
            else:
                data = {"raw_response": response_text}
        except json.JSONDecodeError as e:
            data = {"raw_response": response_text, "parse_error": str(e)}
        
        # 📊 파싱된 JSON 결과 요약 (debug)
        if isinstance(data, dict) and "raw_response" not in data:
            keys = list(data.keys())
            print(f"📊 [VERIFY Markdown 추출 결과] 추출된 필드 수: {len(keys)}, 필드: {keys}")

        return data

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        end_time = time.time()
        elapsed = end_time - start_time
        print(f"Verify LLM API Error: {str(e)}")
        print(f"Error details: {error_details}")
        print(f"에러 발생까지 소요 시간: {elapsed:.2f}초")
        return {"error": f"Unexpected error: {str(e)}", "details": error_details}

# ... existing code ...

async def extract_verify_fields_from_ocr(
    image_bytes: bytes, 
    doc_type: str, 
    required_fields: List[str] = None
) -> Dict[str, Any]:
    """
    이미지를 EasyOCR로 텍스트 추출 후 필드 추출
    DocumentPrompts에서 문서별 특화 프롬프트 사용
    """
    print("EasyOCR 기반 LLM 요청")
    import time
    start_time = time.time()
    
    # 1) EasyOCR로 텍스트 추출
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        ocr_text = _safe_ocr(img)
        print(f"OCR 추출 텍스트 길이: {len(ocr_text)} characters")
        
        if not ocr_text or len(ocr_text.strip()) < 10:
            return {
                "error": "OCR failed to extract meaningful text",
                "ocr_text": ocr_text
            }
    except Exception as e:
        return {
            "error": f"OCR processing failed: {str(e)}"
        }
    
    # 2) 문서 타입별 특화 프롬프트 가져오기
    base_prompt, doc_fields = DocumentPrompts.get_prompt_and_fields(doc_type)
    print(f"📋 {doc_type} 문서 특화 프롬프트 사용")
    
    # 3) LLM으로 필드 추출 (텍스트 기반)
    # 환경변수에서 LLM 설정 가져오기
    vllm_base_url = os.environ.get("VLLM_URL", "http://192.168.14.248:12001/gemma-3-27b")
    llm_url = f"{vllm_base_url.rstrip('/')}/v1/chat/completions"
    llm_model = os.environ.get("VLLM_MODEL", "RedHatAI/gemma-3-27b-it-quantized.w4a16")
    
    # 프롬프트에 OCR 텍스트 추가
    prompt = f"""{base_prompt}

OCR EXTRACTED TEXT:
---
{ocr_text}
---
"""
    
    payload = {
        "model": llm_model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 4000,
        "temperature": 0.1,
        "repetition_penalty": 1.1,
        "seed": 42
    }
    
    try:
        client = get_http_client(timeout=180.0)
        response = await client.post(llm_url, json=payload, headers=_LLM_HTTP_HEADERS)
        response.raise_for_status()
        
        result = response.json()
        response_text = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        # 📊 LLM 응답 원본 미리보기 (debug)
        preview_length = 500
        response_preview = response_text[:preview_length] + "..." if len(response_text) > preview_length else response_text
        print(f"📄 [VERIFY EasyOCR LLM 응답 미리보기]\n{response_preview}")
        
        try:
            cleaned = response_text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            
            start = cleaned.find("{")
            end = cleaned.rfind("}") + 1
            if start != -1 and end != 0:
                json_str = cleaned[start:end]
                json_str = json_str.replace("\\_", "_").replace("\\/", "/")
                data = json.loads(json_str)
            else:
                data = {"raw_response": response_text}
        except json.JSONDecodeError as e:
            data = {"raw_response": response_text, "parse_error": str(e)}
        
        # 📊 파싱된 JSON 결과 요약 (debug)
        if isinstance(data, dict) and "raw_response" not in data:
            keys = list(data.keys())
            print(f"📊 [VERIFY EasyOCR 추출 결과] 추출된 필드 수: {len(keys)}, 필드: {keys}")
        
        # OCR 텍스트도 함께 반환 (디버깅용)
        data["_ocr_text"] = ocr_text
        data["_extraction_method"] = "easyocr"
        
        return data
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        end_time = time.time()
        elapsed = end_time - start_time
        print(f"Verify OCR LLM API Error: {str(e)}")
        print(f"Error details: {error_details}")
        print(f"에러 발생까지 소요 시간: {elapsed:.2f}초")
        return {"error": f"Unexpected error: {str(e)}", "details": error_details}
    
async def extract_verify_fields_from_chandra_ocr(
    image_bytes: bytes, 
    doc_type: str, 
    required_fields: List[str] = None
) -> Dict[str, Any]:
    """
    이미지를 chandra ocr 로 텍스트 추출 후 필드 추출
    DocumentPrompts에서 문서별 특화 프롬프트 사용
    """
    print("chandra ocr 기반 LLM 요청")
    import time
    start_time = time.time()
    
    # 1) EasyOCR로 텍스트 추출
    try:
        # img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        # ocr_text = _safe_ocr(img)
        ocr_text = await _ocr_with_chandra(image_bytes)
        print(f"OCR 추출 텍스트 길이: {len(ocr_text)} characters")
        
        if not ocr_text or len(ocr_text.strip()) < 10:
            return {
                "error": "OCR failed to extract meaningful text",
                "ocr_text": ocr_text
            }
    except Exception as e:
        return {
            "error": f"OCR processing failed: {str(e)}"
        }
    
    # 2) 문서 타입별 특화 프롬프트 가져오기
    base_prompt, doc_fields = DocumentPrompts.get_prompt_and_fields(doc_type)
    print(f"📋 {doc_type} 문서 특화 프롬프트 사용")
    
    # 3) LLM으로 필드 추출 (텍스트 기반)
    # 환경변수에서 LLM 설정 가져오기
    vllm_base_url = os.environ.get("VLLM_URL", "http://192.168.14.248:12001/gemma-3-27b")
    llm_url = f"{vllm_base_url.rstrip('/')}/v1/chat/completions"
    llm_model = os.environ.get("VLLM_MODEL", "RedHatAI/gemma-3-27b-it-quantized.w4a16")
    
    # 프롬프트에 OCR 텍스트 추가
    prompt = f"""{base_prompt}

OCR EXTRACTED TEXT:
---
{ocr_text}
---
"""
    
    payload = {
        "model": llm_model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 4000,
        "temperature": 0.1,
        "repetition_penalty": 1.1,
        "seed": 42
    }
    
    try:
        client = get_http_client(timeout=180.0)
        response = await client.post(llm_url, json=payload, headers=_LLM_HTTP_HEADERS)
        response.raise_for_status()
        
        result = response.json()
        print("LLM 추출 결과 : ", result)
        choices = result.get("choices", [])
        
        # 핵심: choices가 없으면 에러 반환
        if not choices:
            print("  ❌ [chandra-ocr] LLM 응답에 choices 없음")
            return {
                "error": "LLM response has no choices",
                "raw_result": result,
                "_extraction_method": "chandra-ocr"
            }
        
        response_text = choices[0].get("message", {}).get("content", "")
        
        # 📊 LLM 응답 원본 미리보기 (debug)
        preview_length = 500
        response_preview = response_text[:preview_length] + "..." if len(response_text) > preview_length else response_text
        print(f"📄 [VERIFY Chandra OCR LLM 응답 미리보기]\n{response_preview}")
        
        # 핵심: 응답 텍스트가 비어있으면 에러 반환
        if not response_text or len(response_text.strip()) == 0:
            print("  ❌ [chandra-ocr] LLM 응답 텍스트 비어있음")
            return {
                "error": "LLM response text is empty",
                "raw_result": result,
                "_extraction_method": "chandra-ocr"
            }
        
        try:
            cleaned = response_text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            
            start = cleaned.find("{")
            end = cleaned.rfind("}") + 1
            if start != -1 and end != 0:
                json_str = cleaned[start:end]
                json_str = json_str.replace("\\_", "_").replace("\\/", "/")
                data = json.loads(json_str)
            else:
                print("  ⚠️ [chandra-ocr] JSON 구조 없음, raw_response 반환")
                data = {"raw_response": response_text}
        except json.JSONDecodeError as e:
            print(f"  ⚠️ [chandra-ocr] JSON 파싱 실패: {str(e)}")
            data = {"raw_response": response_text, "parse_error": str(e)}
        
        # 📊 파싱된 JSON 결과 요약 (debug)
        if isinstance(data, dict) and "raw_response" not in data:
            keys = list(data.keys())
            print(f"📊 [VERIFY Chandra OCR 추출 결과] 추출된 필드 수: {len(keys)}, 필드: {keys}")
        
        data["_ocr_text"] = ocr_text
        data["_extraction_method"] = "chandra-ocr"
        
        end_time = time.time()
        elapsed = end_time - start_time
        print(f"  ✅ [chandra-ocr] 완료 ({elapsed:.2f}초)")
        
        return data
    
    except httpx.TimeoutException as e:
        print(f"  ❌ [chandra-ocr] 타임아웃: {str(e)}")
        return {
            "error": f"LLM API timeout: {str(e)}",
            "_extraction_method": "chandra-ocr"
        }
    except httpx.HTTPStatusError as e:
        print(f"  ❌ [chandra-ocr] HTTP 에러: status={e.response.status_code}")
        return {
            "error": f"LLM API HTTP error: {str(e)}", 
            "status_code": e.response.status_code,
            "_extraction_method": "chandra-ocr"
        }
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"  ❌ [chandra-ocr] 예외: {str(e)}")
        print(f"     {error_details}")
        return {
            "error": f"Unexpected error: {str(e)}", 
            "details": error_details,
            "_extraction_method": "chandra-ocr"
        }

async def extract_verify_fields_from_image(image_bytes: bytes, doc_type: str, required_fields: List[str] = None) -> Dict[str, Any]:
    """
    이미지(스캔/사진)에서 필드 추출 (멀티모달 모델 - gemma3)
    DocumentPrompts에서 문서별 특화 프롬프트 사용
    """
    print("이미지 기반 LLM 요청")
    import time
    start_time = time.time()

    # 문서 타입별 특화 프롬프트 가져오기
    base_prompt, doc_fields = DocumentPrompts.get_prompt_and_fields(doc_type)
    print(f"📋 {doc_type} 문서 특화 프롬프트 사용")

    # 환경변수에서 LLM 설정 가져오기 (gemma3 멀티모달 모델 사용)
    vllm_base_url = os.environ.get("VLLM_URL", "http://192.168.14.248:12001/gemma-3-27b")
    llm_url = f"{vllm_base_url.rstrip('/')}/v1/chat/completions"
    llm_model = os.environ.get("VLLM_MODEL", "RedHatAI/gemma-3-27b-it-quantized.w4a16")

    # 프롬프트 텍스트 (이미지와 함께 전송됨)
    prompt_text = f"""{base_prompt}

Note: The image of the document is provided. Extract information directly from the image."""

    data_url = _to_data_url(image_bytes)

    payload = {
        "model": llm_model,  # gemma3 멀티모달 모델
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        "max_tokens": 4000,
        "temperature": 0.1,
        "repetition_penalty": 1.1,
        "seed": 42,
    }

    try:
        client = get_http_client(timeout=180.0)
        response = await client.post(llm_url, json=payload, headers=_LLM_HTTP_HEADERS)
        response.raise_for_status()

        result = response.json()
        response_text = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        # 📊 LLM 응답 원본 미리보기 (debug)
        preview_length = 500
        response_preview = response_text[:preview_length] + "..." if len(response_text) > preview_length else response_text
        print(f"📄 [VERIFY Image LLM 응답 미리보기]\n{response_preview}")

        try:
            cleaned = response_text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            start = cleaned.find("{")
            end = cleaned.rfind("}") + 1
            if start != -1 and end != 0:
                json_str = cleaned[start:end]
                json_str = json_str.replace("\\_", "_").replace("\\/", "/")
                data = json.loads(json_str)
            else:
                data = {"raw_response": response_text}
        except json.JSONDecodeError as e:
            data = {"raw_response": response_text, "parse_error": str(e)}
        
        # 📊 파싱된 JSON 결과 요약 (debug)
        if isinstance(data, dict) and "raw_response" not in data:
            keys = list(data.keys())
            print(f"📊 [VERIFY Image 추출 결과] 추출된 필드 수: {len(keys)}, 필드: {keys}")

        return data

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        end_time = time.time()
        elapsed = end_time - start_time
        print(f"Verify Image LLM API Error: {str(e)}")
        print(f"Error details: {error_details}")
        print(f"에러 발생까지 소요 시간: {elapsed:.2f}초")
        return {"error": f"Unexpected error: {str(e)}", "details": error_details}


async def extract_verify_fields_from_ocr_and_image(
    image_bytes: bytes, 
    doc_type: str, 
    required_fields: List[str] = None
) -> Dict[str, Any]:
    """
    OCR 텍스트 + 이미지를 함께 LLM에 전송하여 필드 추출
    DocumentPrompts에서 문서별 특화 프롬프트 사용
    - 이미지의 시각적 정보
    - OCR로 추출한 텍스트
    두 가지를 모두 활용하여 더 정확한 추출
    """
    print("OCR + 이미지 결합 방식 LLM 요청")
    import time
    start_time = time.time()
    
    # 1) EasyOCR로 텍스트 추출
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        ocr_text = _safe_ocr(img)
        print(f"OCR 추출 텍스트 길이: {len(ocr_text)} characters")
        
        if not ocr_text or len(ocr_text.strip()) < 10:
            print("⚠️ OCR 텍스트가 부족하여 이미지 전용 방식으로 폴백")
            # OCR 실패 시 이미지 전용으로 처리
            return await extract_verify_fields_from_image(image_bytes, doc_type, required_fields)
    except Exception as e:
        print(f"⚠️ OCR 처리 실패, 이미지 전용 방식으로 폴백: {str(e)}")
        return await extract_verify_fields_from_image(image_bytes, doc_type, required_fields)
    
    # 2) 문서 타입별 특화 프롬프트 가져오기
    base_prompt, doc_fields = DocumentPrompts.get_prompt_and_fields(doc_type)
    print(f"📋 {doc_type} 문서 특화 프롬프트 사용")
    
    # 3) LLM으로 필드 추출 (OCR 텍스트 + 이미지)
    # 환경변수에서 LLM 설정 가져오기 (gemma3 멀티모달 모델 사용)
    vllm_base_url = os.environ.get("VLLM_URL", "http://192.168.14.248:12001/gemma-3-27b")
    llm_url = f"{vllm_base_url.rstrip('/')}/v1/chat/completions"
    llm_model = os.environ.get("VLLM_MODEL", "RedHatAI/gemma-3-27b-it-quantized.w4a16")
    
    # 프롬프트에 OCR 텍스트와 이미지 안내 추가
    prompt_text = f"""{base_prompt}

ADDITIONAL CONTEXT:
Below is OCR-extracted text from the image. Use BOTH the image and this text to extract information accurately.

OCR TEXT:
---
{ocr_text}
---

Note: The image of the document is also provided. Cross-reference the visual information with the OCR text for maximum accuracy."""
    
    data_url = _to_data_url(image_bytes)
    
    payload = {
        "model": llm_model,  # gemma3 멀티모달 모델
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        "max_tokens": 4000,
        "temperature": 0.1,
        "repetition_penalty": 1.1,
        "seed": 42,
    }
    
    try:
        client = get_http_client(timeout=180.0)
        response = await client.post(llm_url, json=payload, headers=_LLM_HTTP_HEADERS)
        response.raise_for_status()
        
        result = response.json()
        response_text = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        # 📊 LLM 응답 원본 미리보기 (debug)
        preview_length = 500
        response_preview = response_text[:preview_length] + "..." if len(response_text) > preview_length else response_text
        print(f"📄 [VERIFY OCR+Image LLM 응답 미리보기]\n{response_preview}")
        
        try:
            cleaned = response_text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            
            start = cleaned.find("{")
            end = cleaned.rfind("}") + 1
            if start != -1 and end != 0:
                json_str = cleaned[start:end]
                json_str = json_str.replace("\\_", "_").replace("\\/", "/")
                data = json.loads(json_str)
            else:
                data = {"raw_response": response_text}
        except json.JSONDecodeError as e:
            data = {"raw_response": response_text, "parse_error": str(e)}
        
        # 📊 파싱된 JSON 결과 요약 (debug)
        if isinstance(data, dict) and "raw_response" not in data:
            keys = list(data.keys())
            print(f"📊 [VERIFY OCR+Image 추출 결과] 추출된 필드 수: {len(keys)}, 필드: {keys}")
        
        # OCR 텍스트도 함께 반환 (디버깅용)
        data["_ocr_text"] = ocr_text
        data["_extraction_method"] = "ocr_and_image"
        
        return data
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        end_time = time.time()
        elapsed = end_time - start_time
        print(f"Verify OCR+Image LLM API Error: {str(e)}")
        print(f"Error details: {error_details}")
        print(f"에러 발생까지 소요 시간: {elapsed:.2f}초")
        return {"error": f"Unexpected error: {str(e)}", "details": error_details}


