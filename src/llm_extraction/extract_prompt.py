import json
import os
import re
from functools import lru_cache
from typing import Any, Dict

from src.llm_extraction.resume_schema import get_publications_json_schema, get_resume_json_schema
from src.utils.global_logger import debug, error
from src.utils.http_client import get_http_client
from src.utils.time_tracking import measure_ollama_response_time

_LLM_HTTP_HEADERS = {
    "Content-Type": "application/json",
    "ngrok-skip-browser-warning": "true",
}

_PROMPTS_RESUME_DIR = os.path.join(os.path.dirname(__file__), "prompts_resume")


@lru_cache(maxsize=8)
def _load_prompt_txt(filename: str) -> str:
    path = os.path.join(_PROMPTS_RESUME_DIR, filename)
    with open(path, encoding="utf-8") as f:
        return f.read()


def _fstring_braces_to_literal(template: str) -> str:
    """프롬프트 txt에 남아 있는 f-string용 `{{` `}}`를 LLM에 넘길 단일 `{` `}`로 바꿉니다."""
    return template.replace("{{", "{").replace("}}", "}")


def _build_resume_prompt(markdown_content: str) -> str:
    t = _load_prompt_txt("resume_prompt.txt")
    t = t.replace("{markdown_content}", "__PROMPT_MD__")
    t = _fstring_braces_to_literal(t)
    return t.replace("__PROMPT_MD__", markdown_content)


def _build_publications_prompt(sections_journal_content: str) -> str:
    t = _load_prompt_txt("publications_prompt.txt")
    t = t.replace("{sections_journal_content}", "__PROMPT_SJC__")
    t = _fstring_braces_to_literal(t)
    return t.replace("__PROMPT_SJC__", sections_journal_content)


def _resume_structured_response_format() -> Dict[str, Any]:
    """OpenAI 호환 structured output — `resume_schema.ResumeExtraction` 과 동일."""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "ResumeExtraction",
            "schema": get_resume_json_schema(),
        },
    }


def _publications_structured_response_format() -> Dict[str, Any]:
    """OpenAI 호환 structured output — `resume_schema.PublicationsExtraction` 과 동일."""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "publications_extraction",
            "schema": get_publications_json_schema(),
        },
    }


def parse_and_clean_json_response(response_text: str) -> Dict[str, Any]:
    """
    LLM 응답에서 JSON을 파싱하고 괄호를 제거하는 통합 함수
    """

    def clean_string(value):
        if isinstance(value, str):
            # 괄호 제거 및 공백 정리
            cleaned = re.sub(r"[()]", "", value).strip()
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
            return cleaned if cleaned else None
        return value

    def process_data(obj):
        if isinstance(obj, dict):
            return {key: process_data(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [process_data(item) for item in obj]
        else:
            return clean_string(obj)

    try:
        # Clean up the response text to extract JSON
        # Remove markdown code blocks if present
        cleaned_text = response_text.strip()

        # Remove ```json and ``` markers
        if cleaned_text.startswith("```json"):
            cleaned_text = cleaned_text[7:]  # Remove ```json
        elif cleaned_text.startswith("```"):
            cleaned_text = cleaned_text[3:]  # Remove ```

        if cleaned_text.endswith("```"):
            cleaned_text = cleaned_text[:-3]  # Remove trailing ```

        cleaned_text = cleaned_text.strip()

        # Find JSON boundaries
        json_start = cleaned_text.find("{")
        json_end = cleaned_text.rfind("}") + 1

        if json_start != -1 and json_end != 0:
            json_str = cleaned_text[json_start:json_end]

            # Fix invalid escape sequences
            json_str = json_str.replace("\\_", "_")  # Fix \\_ to _
            json_str = json_str.replace("\\/", "/")  # Fix \\/ to /

            # Fix trailing commas (remove comma before closing brace/bracket)
            json_str = re.sub(r",(\s*[}\]])", r"\1", json_str)

            parsed_data = json.loads(json_str)
            # 괄호 제거 후처리 적용
            return process_data(parsed_data)
        else:
            # If no JSON found, return the raw response
            return {"raw_response": response_text}

    except json.JSONDecodeError as e:
        # If JSON parsing fails, return the raw response
        return {
            "raw_response": response_text,
            "parse_error": f"Failed to parse JSON response: {str(e)}",
        }


@measure_ollama_response_time
async def extract_resume_info(markdown_content: str) -> Dict[str, Any]:
    """
    Send markdown content to LLM API to extract resume information in JSON format
    """
    import time

    start_time = time.time()

    if os.environ.get("MOCK_LLM", "false").lower() == "true":
        # CI/테스트에서 vLLM 호출 없이 파이프라인(docling 전처리 등)만 검증하기 위한 더미 응답
        return {
            "name": None,
            "email": None,
            "phone": None,
            "summary": "mocked (MOCK_LLM=true)",
        }

    # 환경변수에서 LLM 설정 가져오기
    vllm_base_url = os.environ.get("VLLM_URL", "http://192.168.14.248:12001/gemma-3-27b")
    llm_url = f"{vllm_base_url.rstrip('/')}/v1/chat/completions"
    llm_model = os.environ.get("VLLM_MODEL", "RedHatAI/gemma-3-27b-it-quantized.w4a16")

    prompt = _build_resume_prompt(markdown_content)

    payload: Dict[str, Any] = {
        "model": llm_model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 4000,
        "temperature": 0.1,  # 낮은 온도로 일관성 향상
        "repetition_penalty": 1.1,  # 반복 방지
        "seed": 42,  # 시드 고정으로 재현성 확보
    }
    payload["response_format"] = _resume_structured_response_format()
    try:
        client = get_http_client(timeout=300.0)
        response = await client.post(llm_url, json=payload, headers=_LLM_HTTP_HEADERS)
        response.raise_for_status()

        result = response.json()
        # vLLM API 응답 형식에 맞게 수정
        response_text = result.get("choices", [{}])[0].get("message", {}).get("content", "")

        # 📊 LLM 응답 원본 미리보기 (debug)
        preview_length = 500
        response_preview = (
            response_text[:preview_length] + "..."
            if len(response_text) > preview_length
            else response_text
        )
        debug(f"📄 [LLM 응답 원본 미리보기]\n{response_preview}")

        # JSON 파싱 및 후처리
        resume_info = parse_and_clean_json_response(response_text)

        # 📊 파싱된 JSON 결과 요약 (debug)
        if isinstance(resume_info, dict):
            keys = list(resume_info.keys())
            debug(
                f"📊 [LLM 추출 결과] 추출된 필드 수: {len(keys)}, 필드: {keys[:10]}"
            )  # 처음 10개만

        return resume_info

    except Exception as e:
        import traceback

        error_details = traceback.format_exc()
        end_time = time.time()
        elapsed_time = end_time - start_time
        error(f"❌ LLM API Error: {str(e)}")
        error(f"Error details: {error_details}")
        error(f"에러 발생까지 소요 시간: {elapsed_time:.2f}초")
        return {"error": f"Unexpected error: {str(e)}", "details": error_details}


@measure_ollama_response_time
async def extract_publications_info(sections_journal_content: str) -> Dict[str, Any]:
    """
    논문/출판물 관련 정보만 추출하는 함수
    sections_journal_result에서 논문, 저널, 학회 발표 등의 정보를 추출
    """
    import time

    start_time = time.time()

    if os.environ.get("MOCK_LLM", "false").lower() == "true":
        return {
            "publications": [],
            "summary": "mocked (MOCK_LLM=true)",
        }

    # 환경변수에서 LLM 설정 가져오기
    vllm_base_url = os.environ.get("VLLM_URL", "http://192.168.14.248:12001/gemma-3-27b")
    llm_url = f"{vllm_base_url.rstrip('/')}/v1/chat/completions"
    llm_model = os.environ.get("VLLM_MODEL", "RedHatAI/gemma-3-27b-it-quantized.w4a16")

    prompt = _build_publications_prompt(sections_journal_content)

    payload: Dict[str, Any] = {
        "model": llm_model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 4000,
        "temperature": 0.1,  # 낮은 온도로 일관성 향상
        "repetition_penalty": 1.1,  # 반복 방지
        "seed": 42,  # 시드 고정으로 재현성 확보
    }
    payload["response_format"] = _publications_structured_response_format()

    try:
        client = get_http_client(timeout=300.0)
        response = await client.post(llm_url, json=payload, headers=_LLM_HTTP_HEADERS)
        response.raise_for_status()

        result = response.json()
        # vLLM API 응답 형식에 맞게 수정
        response_text = result.get("choices", [{}])[0].get("message", {}).get("content", "")

        # 📊 LLM 응답 원본 미리보기 (debug)
        preview_length = 500
        response_preview = (
            response_text[:preview_length] + "..."
            if len(response_text) > preview_length
            else response_text
        )
        debug(f"📄 [LLM 논문 추출 응답 미리보기]\n{response_preview}")

        # JSON 파싱 및 후처리
        publications_info = parse_and_clean_json_response(response_text)

        # 📊 파싱된 JSON 결과 요약 (debug)
        if isinstance(publications_info, dict):
            keys = list(publications_info.keys())
            debug(f"📊 [LLM 논문 추출 결과] 추출된 필드 수: {len(keys)}, 필드: {keys}")

        return publications_info

    except Exception as e:
        import traceback

        error_details = traceback.format_exc()
        end_time = time.time()
        elapsed_time = end_time - start_time
        error(f"❌ Publications LLM API Error: {str(e)}")
        error(f"Error details: {error_details}")
        error(f"에러 발생까지 소요 시간: {elapsed_time:.2f}초")
        return {"error": f"Unexpected error: {str(e)}", "details": error_details}
