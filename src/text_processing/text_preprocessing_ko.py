import re
from rapidfuzz import fuzz
from src.utils.global_logger import info, debug




def _is_bullet_line(s: str) -> bool:
    """'-', '*', '+', 및 다양한 유니코드 불릿(•   등)으로 시작하는지 검사"""
    if not s: return False
    ss = s.lstrip()
    if not ss: return False
    if ss[0] in "-*+":  # 마크다운 기본
        return True
    # 흔한 유니코드/특수 불릿 문자
    if ss[0] in "•·●□◦▪▶※ㆍ":
        return True
    # OCR 섞인 변형
    if ss.startswith(("- :", "-:", "- ", "-  ")):
        return True
    # 번호가 매겨진 리스트 (1., 2., 3. 등)
    if re.match(r"^\d+\.?\s", ss):
        return True
    return False

def _is_bullet_list_block(text: str, min_items: int = 8, ratio: float = 0.5, avg_line_max: int = 100) -> bool:
    """
    불릿 라인이 다수인 '나열형 문단' 감지.
    - min_items: 불릿 항목 최소 개수
    - ratio    : 불릿 라인 비율(불릿/전체) 임계값
    - avg_line_max: 평균 라인 길이 상한(너무 길면 서술형으로 간주)
    """
    lines = [ln for ln in text.split("\n") if ln.strip()]
    if not lines:
        return False
    bullet_cnt = sum(1 for ln in lines if _is_bullet_line(ln))
    avg_len = sum(len(ln.strip()) for ln in lines) / len(lines)
    return (bullet_cnt >= min_items) and (bullet_cnt / len(lines) >= ratio) and (avg_len <= avg_line_max)




def _normalize_ocr_punct(text: str) -> str:
    """OCR 텍스트 특성 보정: 줄바꿈/공백/문장부호 앞 공백 정리 + 전각 바/대시 정규화"""
    t = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u00A0", " ")
    # 전각/비표준 바/대시 → ASCII
    trans = {
        ord("｜"): "|", ord("│"): "|", ord("¦"): "|",
        ord("—"): "-", ord("–"): "-", ord("─"): "-", ord("‐"): "-",
        ord("－"): "-", ord("―"): "-", ord("﹘"): "-",
    }
    t = t.translate(trans)
    # 문장부호 앞 공백 제거 + 다중 공백 축소
    t = re.sub(r"\s+([,.;!?])", r"\1", t)   # '합니다 .' → '합니다.'
    t = re.sub(r"[ \t]{2,}", " ", t)
    return t


def clean_tables_only(md: str, keep_table_max_rows: int = 50) -> str:
    """
    표(테이블) 블록 안에서만 정리:
    - 전각 파이프/대시(｜, －, ─ 등) → ASCII
    - 표 내부의 파이프/대시 전용 줄(구분선)은 '헤더 바로 아래 1줄'만 유지, 나머지는 삭제
    - 표 밖의 파이프/대시 전용 줄은 항상 삭제
    - 헤더 구분선(---, :---, ---:, :---:) 표준화
    - 각 행을 '| a | b |' 형태로 정규화
    - 데이터 없는 표(헤더+구분선만) 제거
    - 너무 긴 표는 앞 N행만 유지
    ※ 표 밖의 라인은 전혀 수정/삭제하지 않음
    """
    trans = {
        ord("｜"): "|", ord("│"): "|", ord("¦"): "|",
        ord("—"): "-", ord("–"): "-", ord("─"): "-", ord("‐"): "-",
        ord("－"): "-", ord("―"): "-", ord("﹘"): "-",
        ord("\u00A0"): ord(" "),
    }
    t = md.translate(trans).replace("\r\n", "\n").replace("\r", "\n")
    lines = t.split("\n")

    def is_only_pipes_or_dashes(s: str) -> bool:
        ss = s.strip()
        return bool(ss) and bool(re.fullmatch(r"[|\-\s:]+", ss)) and any(ch in ss for ch in "|-")

    def is_tabley(s: str) -> bool:
        # 파이프가 2개 이상이고, 파이프 외 문자가 조금이라도 있으면 표 성향
        return s.count("|") >= 2 and len(s.strip("| ").strip()) > 0

    def normalize_table_row(row: str) -> str:
        raw = row.strip()
        if set(raw) <= {"|", " ", "-"}:
            return raw
        parts = [c.strip() for c in raw.strip("| ").split("|")]
        
        # 중복 내용 제거: 모든 컬럼이 같은 내용인 경우 첫 번째 컬럼에만 표시
        if len(parts) > 1 and all(part == parts[0] and part.strip() for part in parts):
            # 모든 컬럼이 같은 내용이면 첫 번째 컬럼에만 표시하고 나머지는 비움
            normalized_parts = [parts[0]] + [""] * (len(parts) - 1)
        elif len(parts) > 1 and all(part.strip() and part == parts[1] for part in parts[1:]):
            # 첫 번째 컬럼을 제외하고 나머지가 모두 같은 경우
            normalized_parts = [parts[0]] + [parts[1]] + [""] * (len(parts) - 2)
        else:
            # 내용 손실 없이 정규화만 수행
            normalized_parts = []
            for part in parts:
                # 불필요한 공백 정리 (연속된 공백을 하나로, 앞뒤 공백 제거)
                cleaned_part = re.sub(r'\s+', ' ', part.strip())
                normalized_parts.append(cleaned_part)
        
        return "| " + " | ".join(normalized_parts) + " |"

    def normalize_header_sep(row: str) -> str:
        raw = row.strip()
        if raw.count("|") < 2:
            return row
        cells = [c.strip() for c in raw.strip("| ").split("|")]
        norm_cells = []
        for c in cells:
            left_colon  = c.startswith(":")
            right_colon = c.endswith(":")
            dash_count = len(re.sub(r"[^-]", "", c))
            # 구분선 길이를 적절하게 제한 (최대 25개 대시로 완화)
            dash_count = min(dash_count, 25) if dash_count > 0 else 3
            dashes = "-" * max(3, dash_count)
            if left_colon and right_colon: norm = ":" + dashes + ":"
            elif left_colon:               norm = ":" + dashes
            elif right_colon:              norm = dashes + ":"
            else:                          norm = dashes
            norm_cells.append(norm)
        return "| " + " | ".join(norm_cells) + " |"

    out = []
    i, n = 0, len(lines)
    while i < n:
        ln = lines[i]

        # 표 블록이 아니면: 외톨이 파이프/대시 라인은 항상 제거, 아니면 그대로 보존
        if not is_tabley(ln):
            if is_only_pipes_or_dashes(ln):
                i += 1
                continue
            out.append(ln)
            i += 1
            continue

        # 표 블록 수집 (표 내부에서는 구분선 라인도 포함)
        block = [ln]
        j = i + 1
        while j < n and (is_tabley(lines[j]) or is_only_pipes_or_dashes(lines[j])):
            block.append(lines[j])
            j += 1

        # 표 내부: 구분선 라인 위치 파악
        only_sep_idx = [k for k, r in enumerate(block) if is_only_pipes_or_dashes(r)]
        first_sep = only_sep_idx[0] if only_sep_idx else None

        # '헤더 바로 아래 첫 구분선'만 남기고 나머지 구분선/파이프-only 라인은 삭제
        new_block = []
        for k, r in enumerate(block):
            if k in only_sep_idx:
                if k == 1 or (first_sep is not None and k == first_sep):
                    new_block.append(normalize_header_sep(r))
                else:
                    continue  # 표 내부 다른 구분선/파이프-only 라인 제거
            else:
                new_block.append(r)
        block = new_block

        # 각 행 정규화
        block = [normalize_table_row(b) for b in block]
        # 데이터 없는 표(헤더+구분선만)는 제거
        data_rows = [r for r in block[2:] if not is_only_pipes_or_dashes(r)]
        if len(block) >= 2 and len(data_rows) == 0:
            i = j
            continue
        out.extend(block)
        i = j

    return "\n".join(out)



def remove_long_paragraphs_by_sentences_ocr(
    md_text: str,
    sentence_count_threshold: int = 5,  # 3 → 5로 완화
    avg_length_threshold: int = 80,     # 50 → 80으로 완화
    format_type: str = "default",       # "remember" 또는 "default"
) -> str:
    """
    OCR 특화: 문장 수/평균 길이 기준 + 쉼표 보조 분리 + 장문 블랍 휴리스틱 + 불릿 나열 블록 제거
    (섹션 통삭제/영문 슬로건 제거는 포함하지 않음)
    """
    text = _normalize_ocr_punct(md_text)
    
    # ✅ 표 선제 정리 
    text = clean_tables_only(text)


    # 코드블록 보존
    parts = re.split(r"(```.*?```)", text, flags=re.S)
    out_parts = []

    def process_block(block: str) -> str:
        # 문단 분리 방식: remember 형식은 단일 줄바꿈, 다른 형식은 이중 줄바꿈
        if format_type == "remember":
            paragraphs = re.split(r"\n{1,}", block)  # 단일 줄바꿈으로 분리
        else:
            paragraphs = re.split(r"\n{2,}", block)  # 이중 줄바꿈으로 분리
        kept = []

        for para in paragraphs:
            raw = para.strip()
            if not raw:
                continue

            # 0) 불릿 나열 블록이면 상위 5개만 남기고 나머지 삭제 (더 적극적으로)
            if _is_bullet_list_block(raw, min_items=8, ratio=0.6, avg_line_max=120):  # 더 관대한 조건
                lines = raw.split("\n")
                raw = "\n".join(lines[:5]) if len(lines) > 5 else raw  # 10개 → 5개로 줄임
                if not raw.strip():
                    continue

            # 1) 마크다운 구조(헤더/표/리스트)는 보존
            if re.match(r"^\s*(#{1,6}\s|\|.*\||\d+\.\s|[-*+]\s)", raw):
                kept.append(raw)
                continue

            # 2) 줄바꿈 → 공백 후 재정규화
            norm = _normalize_ocr_punct(raw.replace("\n", " ")).strip()

            # 3) 1차: .?! 기준 문장 분리
            sents = re.split(r"(?<=[.?!])\s+", norm)
            sents = [s.strip(" .!?") for s in sents if s.strip()]
            # print(f"문장 구분자 기준 분리: {len(sents)} 문장")

            # 4) 문장 수 부족하면 쉼표 기반 보조 분리 (OCR에서 .?!가 희소한 경우 대비)
            if len(sents) < sentence_count_threshold:
                alt = re.split(r"\s*[,，、]\s*", norm)
                alt = [s.strip(" ,") for s in alt if s.strip(" ,")]
                if len(alt) >= sentence_count_threshold:
                    # print(f"쉼표 기반 분리: {len(sents)} → {len(alt)} 문장")
                    sents = alt

            avg_len = (sum(len(s) for s in sents) / len(sents)) if sents else 0
            # print(f"문단 길이: {len(norm)}, 문장 수: {len(sents)}, 평균 길이: {avg_len:.1f}")

            # 5) 평균 길이가 100 이상인 경우 문장을 절반으로 줄이기
            if  format_type != "remember" and avg_len >= 100 and len(sents) > 1:
                half_count = round(len(sents) / 2)
                kept_sents = sents[:half_count]
                raw = " ".join(kept_sents)
                # print(f"평균 길이 {avg_len:.1f}로 인해 문장을 절반으로 줄임: {len(sents)} → {len(kept_sents)} 문장")
                info(f"원본 길이: {len(norm)}, 처리 후 길이: {len(raw)}")

            # 6) 장문 블랍 휴리스틱: 더 엄격한 조건으로 변경
            comma_count = norm.count(",")
            # 500자 이상이고 문장이 8개 이상일 때만 제거 
            long_blob = (len(norm) >= 500 and len(sents) >= 8 and comma_count >= 10)
            
            # 7) 최종 제거 조건 더 적극적으로
            condition1 = len(sents) >= sentence_count_threshold and avg_len >= avg_length_threshold
            # if condition1 or condition2 or condition3 or long_blob:
            if condition1 or long_blob:
                info(f"문단 제거됨: {raw[:50]}...")
                continue  # 제거

            # print(f"문단 유지됨: {raw[:50]}...")
            kept.append(raw)

        return "\n".join(kept)

    for i, part in enumerate(parts):
        out_parts.append(part if i % 2 == 1 else process_block(part))

    return "".join(out_parts)


# 한국어/다른 장르용 논문 섹션 패턴
korean_remove_sections = {
    "publications": [
        "논문", "논 문", "연구논문", "학술논문", "학술지논문", "저널논문",
        "Publications", "Research Papers", "Academic Papers",
        "국제논문", "국내논문", "해외논문", "SCI논문", "SSCI논문", "KCI논문",
        "국제학술지", "국내학술지", "해외학술지",
        "박사학위논문", "박사학위 논문", "박사논문", "박사 논문",
        "석사학위논문", "석사학위 논문", "석사논문", "석사 논문",
        "학위논문", "학위 논문", "Dissertation", "Thesis",
        "논문 및 저서", "논문저서", "연구실적", "연구성과", "논문 및 출원 특허"
    ],
    "conferences": [
        "학회발표", "학술발표", "컨퍼런스", "학회", "학술대회",
        "Conferences", "Conference Presentations", "학회발표논문",
        "국제학회", "국내학회", "해외학회", "학술대회발표"
    ],
    "cover_letter": [
        "지원동기", "지원 동기", "입사동기", "입사 동기",
        "지원동기 및 포부", "지원동기및포부", "지원동기 및 포부",
        "성장과정", "성장 과정", "성장배경", "성장 배경",
        "자기소개서", "자기 소개서", "자기소개", "자기 소개",
        "성격", "성격 및 장단점", "성격 장단점", "성격및장단점", "성격 소개",
        "기타사항", "기타 사항", "기타정보", "기타 정보", "기타 특기 사항", "성격 ( 장단점 ) 및 대인관계", 
    ]
}


def identify_sections_korean(text_lines, target_sections):
    """
    한국어 문서에서 섹션을 식별하는 함수
    """
    sections = []
    
    for i, line_dict in enumerate(text_lines):
        line_text = line_dict["text"].strip()
        
        # 헤더 패턴 확인 (##, ###, 또는 대문자로 시작하는 라인, 또는 키워드 포함)
        line_text_no_space = line_text.replace(" ", "").replace("　", "")
        
        # [포상], [수상], [상] 등의 인라인 패턴도 섹션으로 인식
        inline_award_patterns = ["[포상]", "[수상]", "[상]", "[기타이력]"]
        is_inline_award = any(pattern in line_text for pattern in inline_award_patterns)
        
        # 인라인 논문 패턴도 섹션으로 인식
        inline_thesis_patterns = ["박사 논문:", "석사 논문:", "학위논문:", "논문:"]
        is_inline_thesis = any(pattern in line_text for pattern in inline_thesis_patterns)
        
        if (line_text.startswith("##") or 
            line_text.startswith("###") or 
            (len(line_text) < 50 and line_text.isupper()) or
            (len(line_text) < 50 and any(keyword in line_text_no_space for keyword in ["논문", "발표", "수상", "특허", "학위", "박사", "석사", "지원", "성격", "자기"])) or
            is_inline_award or is_inline_thesis):
            
            # 각 타겟 섹션과 유사도 비교
            for section in target_sections:
                # 원본과 공백 제거 버전 모두 확인
                similarity1 = fuzz.ratio(line_text.lower(), section.lower())
                similarity2 = fuzz.ratio(line_text_no_space.lower(), section.lower())
                
                # 인라인 포상 패턴의 경우 특별 처리
                if is_inline_award and any(keyword in section.lower() for keyword in ["포상", "수상", "상", "awards", "활동", "대회", "경진대회", "컨테스트", "콘테스트", "경기"]):
                    max_similarity = 80  # 인라인 포상 패턴은 높은 유사도로 처리
                # 인라인 논문 패턴의 경우 특별 처리
                elif is_inline_thesis and any(keyword in section.lower() for keyword in ["논문", "publications", "research", "academic", "박사", "석사", "학위", "thesis", "dissertation"]):
                    max_similarity = 80  # 인라인 논문 패턴은 높은 유사도로 처리
                else:
                    # 더 높은 유사도를 선택하고, 임계값을 60%로 낮춤
                    max_similarity = max(similarity1, similarity2)
                
                if max_similarity >= 60:  # 60% 이상 유사하면 매칭
                    sections.append((i, line_text, max_similarity))
                    break
    
    return sections


def extract_sections_korean_result(markdown_text, **kwargs):
    """
    한국어/다른 장르 문서에서 논문 관련 섹션을 추출하는 함수
    
    Args:
        markdown_text: 원본 마크다운 텍스트
        
    Returns:
        dict: {
            "extracted_sections_result": 마크다운 형태의 추출된 섹션들 (논문, 활동/대회/수상),
            "section_info": 찾은 섹션 정보,
            "removed_count": 추출된 라인 수
        }
    """
    # markdown 텍스트를 라인별로 분리
    lines = markdown_text.split('\n')
    
    # 각 라인을 딕셔너리 형태로 변환 (기존 구조와 호환)
    text_lines = []
    for i, line in enumerate(lines):
        text_lines.append({
            "text": line,
            "chars": [{"size": 12}]  # 기본 폰트 크기 설정
        })
    
    # 논문 관련 섹션들만 추출
    target_sections = []
    # 논문 관련 섹션들
    target_sections.extend(korean_remove_sections.get("publications", []))
    target_sections.extend(korean_remove_sections.get("conferences", []))
    
    sections = identify_sections_korean(text_lines, target_sections)
    
    debug(f"🔍 찾은 한국어 섹션들: {sections}")
    
    # 찾은 섹션들의 인덱스 정보 수집
    section_indices = []
    for idx, section_name, score in sections:
        section_indices.append((idx, section_name, score))
    
    # 섹션 인덱스로 정렬
    section_indices.sort(key=lambda x: x[0])
    
    # 추출된 섹션들을 마크다운으로 구성
    extracted_sections_result = []
    removed_count = 0
    
    for idx, section_name, score in section_indices:
        # 논문, 발표, 수상, 특허 관련 섹션인지 확인
        should_extract = False
        section_type = ""
        
        if any(keyword in section_name for keyword in korean_remove_sections.get("publications", [])):
            should_extract = True
            section_type = "논문"
            info(f"📚 논문 섹션 발견: '{section_name}'")
        elif any(keyword in section_name for keyword in korean_remove_sections.get("conferences", [])):
            should_extract = True
            section_type = "학회발표"
            info(f"🎤 학회발표 섹션 발견: '{section_name}'")
        
        if should_extract:
            # 섹션 헤더 추가
            extracted_sections_result.append(f"## {section_name}")
            extracted_sections_result.append("")  # 빈 줄 추가
            
            # 섹션 내용 추가
            start_idx = idx + 1  # 헤더 다음 라인부터 시작
            end_idx = len(text_lines)
            
            # 인라인 포상 패턴인 경우 현재 라인도 포함
            inline_award_patterns = ["[포상]", "[수상]", "[상]", "[기타이력]"]
            is_inline_award = any(pattern in section_name for pattern in inline_award_patterns)
            
            # 인라인 논문 패턴 감지
            inline_thesis_patterns = ["박사 논문:", "석사 논문:", "학위논문:", "논문:"]
            is_inline_thesis = any(pattern in text_lines[idx]["text"] for pattern in inline_thesis_patterns)
            
            if is_inline_award or is_inline_thesis:
                # 인라인 포상/논문 패턴의 경우 현재 라인부터 시작
                start_idx = idx
                # 현재 라인에 포상/논문 정보가 포함되어 있으면 바로 추가
                if (any(pattern in text_lines[idx]["text"] for pattern in inline_award_patterns) or
                    any(pattern in text_lines[idx]["text"] for pattern in inline_thesis_patterns)):
                    extracted_sections_result.append(text_lines[idx]["text"])
                    removed_count += 1
                    start_idx = idx + 1
            
            # 다음 섹션의 시작점 찾기 (다음 ## 헤더 찾기)
            for i in range(start_idx, len(text_lines)):
                if (text_lines[i]["text"].strip().startswith("##") or 
                    text_lines[i]["text"].strip().startswith("###") or
                    (len(text_lines[i]["text"].strip()) < 50 and text_lines[i]["text"].strip().isupper()) or
                    any(pattern in text_lines[i]["text"] for pattern in inline_award_patterns)):
                    end_idx = i
                    break
            
            # 섹션 내용 수집
            for i in range(start_idx, end_idx):
                line_text = text_lines[i]["text"].strip()
                if line_text:  # 빈 줄이 아닌 경우만 추가
                    extracted_sections_result.append(line_text)
                    removed_count += 1
            
            extracted_sections_result.append("")  # 섹션 끝에 빈 줄 추가
            debug(f"📝 추출된 {section_type} 섹션: '{section_name}' ({end_idx - start_idx}개 라인)")
    
    # 마크다운 문자열로 결합
    extracted_sections_markdown = '\n'.join(extracted_sections_result)
    
    debug(f"📊 한국어 섹션 추출 통계: {removed_count}개 라인 추출 (총 {len(sections)}개 섹션)")
    
    output = {
        "sections_journal_result": extracted_sections_markdown,
        "section_info": sections,
        "removed_count": removed_count,
        "total_sections": len(sections)
    }
    
    return output


def remove_sections_korean(markdown_text, **kwargs):
    """
    한국어 문서에서 특정 섹션들을 삭제하는 함수
    논문, 수상, 특허, 개인정보 섹션들을 삭제
    """
    # markdown 텍스트를 라인별로 분리
    lines = markdown_text.split('\n')
    
    # 각 라인을 딕셔너리 형태로 변환 (기존 구조와 호환)
    text_lines = []
    for i, line in enumerate(lines):
        text_lines.append({
            "text": line,
            "chars": [{"size": 12}]  # 기본 폰트 크기 설정
        })
    
    # 삭제할 섹션들 수집
    sections_to_remove = []
    for section_type, section_list in korean_remove_sections.items():
        sections_to_remove.extend(section_list)
    
    sections = identify_sections_korean(text_lines, sections_to_remove)
    
    debug(f"🔍 삭제할 한국어 섹션들: {sections}")
    
    # 찾은 섹션들의 인덱스 정보 수집
    section_indices = []
    for idx, section_name, score in sections:
        section_indices.append((idx, section_name, score))
    
    # 섹션 인덱스로 정렬
    section_indices.sort(key=lambda x: x[0])
    
    # 제거할 텍스트 라인들 수집
    removed_texts = []
    removed_indices = set()
    
    for idx, section_name, score in section_indices:
        # 삭제할 섹션인지 확인
        should_remove = False
        section_type = ""
        
        if any(keyword in section_name for keyword in korean_remove_sections.get("publications", [])):
            should_remove = True
            section_type = "논문"
        elif any(keyword in section_name for keyword in korean_remove_sections.get("conferences", [])):
            should_remove = True
            section_type = "학회발표"
        elif any(keyword in section_name for keyword in korean_remove_sections.get("cover_letter", [])):
            should_remove = True
            section_type = "자기소개서"
        
        if should_remove:
            info(f"🗑️ {section_type} 섹션 삭제: '{section_name}'")
            
            # 섹션 헤더와 내용 모두 삭제
            start_idx = idx  # 헤더부터 시작
            end_idx = len(text_lines)
            
            # 다음 섹션의 시작점 찾기 (더 유연한 패턴)
            for i in range(start_idx + 1, len(text_lines)):
                line_text = text_lines[i]["text"].strip()
                # 마크다운 헤더, 불릿 포인트, 또는 다른 섹션 헤더 패턴 감지
                if (line_text.startswith("##") or 
                    line_text.startswith("###") or
                    (len(line_text) < 50 and line_text.isupper()) or
                    (len(line_text) < 50 and any(keyword in line_text.replace(" ", "").replace("　", "") for keyword in ["논문", "발표", "수상", "특허", "학위", "박사", "석사", "지원", "성장", "자기", "성격", "기타"]))):
                    end_idx = i
                    break
            
            # 섹션 내용 삭제
            for i in range(start_idx, end_idx):
                if i not in removed_indices:
                    # print(f"🗑️ 섹션 내용 삭제: '{text_lines[i]['text']}' (라인 {i+1})")
                    removed_texts.append(text_lines[i]["text"])
                    removed_indices.add(i)
        else:
            # print(f"ℹ️ 보존할 섹션: '{section_name}' (라인 {idx+1})")
            pass
    
    # 제거되지 않은 텍스트만 남기기
    filtered_lines = []
    for i, line in enumerate(text_lines):
        if i not in removed_indices:
            filtered_lines.append(line["text"])
    
    # 필터링된 텍스트를 다시 markdown 형태로 결합
    filtered_markdown = '\n'.join(filtered_lines)
    
    
    output = {
        "original_text": markdown_text,
        "filtered_text": filtered_markdown,
        "removed_sections": removed_texts,
        "section_info": sections,
        "removed_count": len(removed_indices),
        "total_count": len(text_lines)
    }
    
    return output

