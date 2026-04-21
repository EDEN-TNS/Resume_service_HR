from rapidfuzz import fuzz
from src.utils.global_logger import info, debug

remove_sections = {
    "journal": [
        "INTERNATIONAL JOURNALS",
        "INTERNATIONALJOURNALS",
        "international journals",
        "DOMESTIC JOURNALS",
        "domestic journals"
    ],
    "publications": [
        "Publications",
        "Publications (SCI)",
        "Publications (SSCI)",
        "Publications (KCI)",
        "Refereed Conference Proceedings"
    ],
    "conferences": [
        "CONFERENCES",
        "conferences",
        "Conference Talk"
    ],
    "presentations": [
        "Presentation",
        "PRESENTATION",
        "Presentations",
        "PRESENTATIONS",
        "Poster Presentation"
    ],
    "mentoring": [
        "MENTORING",
        "Mentoring",
        "MENTORING EXPERIENCE",
        "Mentoring Experience"
    ],
    "professional_memberships": [
        "PROFESSIONAL MEMBERSHIPS AND SERVICES",
        "Professional Memberships and Services",
        "PROFESSIONAL MEMBERSHIPS",
        "Professional Memberships",
        "MEMBERSHIPS",
        "Memberships",
        "PROFESSIONAL SERVICES",
        "Professional Services"
    ],
    "conference_abstracts": [
        "Conference Abstracts",
        "CONFERENCE ABSTRACTS"
    ],
    "under_review": [
        "Under Review",
        "UNDER REVIEW"
    ],
    "in_preparation": [
        "In Preparation",
        "IN PREPARATION"
    ],
    "invited_seminar": [
        "Invited Seminar Talk",
        "INVITED SEMINAR TALK"
    ],
    "conference_talk": [
        "Conference Talk",
        "CONFERENCE TALK"
    ],
    "poster_presentation": [
        "Poster Presentation",
        "POSTER PRESENTATION"
    ],
    "patents": [
        "PATENTS",
        "Patents"
    ],
    "research_funding": [
        "CONTRIBUTED RESEARCH FUNDING",
        "Contributed Research Funding",
        "RESEARCH FUNDING",
        "Research Funding",
        "FUNDING",
        "Funding"
    ],
    "phd_candidate": [
        "PhD Candidate",
        "PHD CANDIDATE"
    ],
    "journal_articles": [
        "I. Journal Articles",
        "Journal Articles",
        "JOURNAL ARTICLES"
    ],
    "conference_presentations": [
        "II. Conference Presentations",
        "Conference Presentations",
        "CONFERENCE PRESENTATIONS"
    ],
    "patents_iii": [
        "III. Patents",
        "Patents",
        "PATENTS"
    ],
}

# def extract_strip_text_pdf(pdf):
#     lines = []
#     for page in pdf.pages:
#         current_lines = page.extract_text_lines(layout=True, strip=True, return_chars=True)
#         lines.extend(current_lines)
#     return lines

# def extract_text_pdf(pdf):
#     lines = []
#     for page in pdf.pages:
#         current_lines = page.extract_text_lines(layout=True, strip=False, return_chars=True)
#         lines.extend(current_lines)
#     return lines

def round_to_tolerance(value, tolerance=0.05):
    return round(round(value / tolerance) * tolerance,3)

def get_fonts_line(line):
    fonts = set()

    for char in line["chars"]:
        #fontname = char["fontname"]
        size = char["size"]
        round_size = round_to_tolerance(size)
        #font = f'{fontname}-{round_size}'
        font = f'{round_size}'
        if font  not in fonts:
            fonts.add(font)
    return fonts

def get_fonts(lines):
    fonts = {}
    for line in lines:
        for char in line["chars"]:
            #fontname = char["fontname"]
            size = char["size"]
            round_size = round_to_tolerance(size)
            #font = f'{fontname}-{round_size}'
            font = f'{round_size}'
            if font  not in fonts:
                fonts[font] = 1
            else:
                fonts[font] += 1
    return fonts
def detect_fonts(font_dict, threshold_percent=0.7):
    """
    Detects the fonts that make up at least the given threshold percentage
    of total characters from the provided font dictionary.
    
    Parameters:
        font_dict (dict): A dictionary with font sizes as keys and character counts as values.
        threshold_percent (float): The percentage threshold (default is 0.7 for 70%).
        
    Returns:
        list: A list of font sizes that cumulatively reach or exceed the threshold.
    """
    # Calculate total number of characters
    total_chars = sum(font_dict.values())
    threshold = threshold_percent * total_chars

    # Sort the dictionary items by count in descending order
    sorted_fonts = sorted(font_dict.items(), key=lambda x: x[1], reverse=True)

    accumulated = 0
    selected_fonts = []

    # Accumulate counts until reaching the threshold
    for font, count in sorted_fonts:
        accumulated += count
        selected_fonts.append(font)
        if accumulated >= threshold:
            break

    return set(selected_fonts)

def fuzzy_match_field(text, sections, min_score=80):
    best_match = None
    best_score = 0
    
    # 괄호와 그 내용을 제거한 텍스트 생성
    import re
    text_without_brackets = re.sub(r'\s*\([^)]*\)', '', text).strip()
    
    # 먼저 정확한 매칭 확인 (원본 텍스트)
    for section in sections:
        if text.lower().strip() == section.lower().strip():
            return section, 100
    
    # 괄호 제거한 텍스트로 정확한 매칭 확인
    for section in sections:
        section_without_brackets = re.sub(r'\s*\([^)]*\)', '', section).strip()
        if text_without_brackets.lower() == section_without_brackets.lower():
            return section, 100
    
    # 정확한 매칭이 없으면 fuzzy matching (원본 텍스트)
    for section in sections:
        score = fuzz.ratio(text.lower(), section.lower())
        if score > best_score:
            best_score = score
            best_match = section
    
    # 괄호 제거한 텍스트로 fuzzy matching
    for section in sections:
        section_without_brackets = re.sub(r'\s*\([^)]*\)', '', section).strip()
        score = fuzz.ratio(text_without_brackets.lower(), section_without_brackets.lower())
        if score > best_score:
            best_score = score
            best_match = section
    
    # 최소 점수 이상일 때만 매칭으로 인정
    if best_score >= min_score:
        return best_match, best_score
    else:
        return None, best_score

def identify_sections_resume(page_items, sections):
    title_items = []
    fonts = get_fonts(page_items)
    main_fonts = detect_fonts(fonts)
    for idx, element in enumerate(page_items):
        line_fonts = get_fonts_line(element)
        if len(line_fonts) == 1:
            current_font = next(iter(line_fonts))
            if current_font in main_fonts:
                continue
        elif line_fonts == main_fonts:
            continue

        cleaned_text = ' '.join(element["text"].split())
        
        # 마크다운 헤더에서 ## 제거
        if cleaned_text.startswith('## '):
            cleaned_text = cleaned_text[3:].strip()
        
        # 테이블 형식의 섹션 헤더 처리 (|로 구분된 경우 첫 번째 부분만 추출)
        if '|' in cleaned_text:
            cleaned_text = cleaned_text.split('|')[0].strip()

        k,v = fuzzy_match_field(cleaned_text,sections)
        if k is not None:
            title_items.append((idx,k,v))

    if len(title_items) == 0:
        for idx, element in enumerate(page_items):
            cleaned_text = ' '.join(element["text"].split())
            
            # 마크다운 헤더에서 ## 제거
            if cleaned_text.startswith('## '):
                cleaned_text = cleaned_text[3:].strip()
            
            # 테이블 형식의 섹션 헤더 처리 (|로 구분된 경우 첫 번째 부분만 추출)
            if '|' in cleaned_text:
                cleaned_text = cleaned_text.split('|')[0].strip()

            k,v = fuzzy_match_field(cleaned_text,sections)
            if k is not None:
                title_items.append((idx,k,v))
        
    return title_items


def remove_sections_journal(markdown_text, **kwargs):
    # markdown 텍스트를 라인별로 분리
    lines = markdown_text.split('\n')
    
    # 각 라인을 딕셔너리 형태로 변환 (기존 구조와 호환)
    text_lines = []
    for i, line in enumerate(lines):
        text_lines.append({
            "text": line,
            "chars": [{"size": 12}]  # 기본 폰트 크기 설정
        })
    
    # resume_sections에서 remove_sections에 해당하는 섹션들만 추출
    sections_to_remove = []
    for section_type, section_list in remove_sections.items():
        sections_to_remove.extend(section_list)
    
    # print(f"🗑️ 제거 대상 섹션들: {sections_to_remove}")
    
    # sections = identify_sections_resume(text_lines, sections_to_remove)
    # 직접 섹션 찾기 (폰트 기반 로직 대신 간단한 텍스트 매칭 사용)
    sections = []
    for idx, line_dict in enumerate(text_lines):
        line_text = line_dict["text"].strip()
        
        # 마크다운 헤더에서 ## 제거
        if line_text.startswith('## '):
            cleaned_text = line_text[3:].strip()
            # print(f"🗑️ 헤더 라인 {idx}: '{line_text}' -> '{cleaned_text}'")
        else:
            cleaned_text = line_text
        
        # 테이블 형식의 섹션 헤더 처리 (|로 시작하는 경우)
        if cleaned_text.startswith('|') and '|' in cleaned_text[1:]:
            original_cleaned = cleaned_text
            # 첫 번째 |와 두 번째 | 사이의 내용 추출
            parts = cleaned_text.split('|')
            if len(parts) >= 2:
                cleaned_text = parts[1].strip()  # 첫 번째 | 다음 부분
            # print(f"🗑️ 테이블 헤더 처리: '{original_cleaned}' -> '{cleaned_text}'")
        
        # 타겟 섹션과 매칭 확인
        for section in sections_to_remove:
            if cleaned_text.lower() == section.lower():
                sections.append((idx, section, 100))
                # print(f"🎯 제거할 섹션 매칭: '{cleaned_text}' -> '{section}'")
                break
    
    print(f"🔍 찾은 섹션들: {sections}")
    
    # remove_sections에 정의된 모든 섹션 키들을 하나의 리스트로 합치기
    all_sections_to_remove = []
    for section_type, section_list in remove_sections.items():
        all_sections_to_remove.extend(section_list)
    
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
        # remove_sections에 정의된 섹션인지 확인
        should_remove = False
        for stype, slist in remove_sections.items():
            if section_name in slist:
                should_remove = True
                break
        
        if should_remove:
            # remove_sections에 정의된 섹션은 헤더와 내용 모두 삭제
            start_idx = idx  # 헤더부터 시작 (헤더도 삭제)
            end_idx = len(text_lines)
            
            # 다음 섹션의 시작점 찾기 (다음 ## 헤더 찾기)
            for i in range(start_idx + 1, len(text_lines)):
                if text_lines[i]["text"].strip().startswith("## "):
                    end_idx = i
                    break
            
            # 제거할 텍스트 수집 (헤더 포함)
            for i in range(start_idx, end_idx):
                if i not in removed_indices:
                    # print(f"🗑️ 섹션 삭제: '{text_lines[i]['text']}' (라인 {i+1})")
                    removed_texts.append(text_lines[i]["text"])
                    removed_indices.add(i)
        else:
            # remove_sections에 정의되지 않은 섹션은 삭제하지 않음
            # print(f"ℹ️ 보존할 섹션: '{text_lines[idx]['text']}' (라인 {idx+1})")
            pass
    
    # 제거되지 않은 텍스트만 남기기
    filtered_lines = []
    for i, line in enumerate(text_lines):
        if i not in removed_indices:
            filtered_lines.append(line["text"])
    
    # 필터링된 텍스트를 다시 markdown 형태로 결합
    filtered_markdown = '\n'.join(filtered_lines)
    
    print(f"📊 삭제 통계: {len(removed_indices)}개 라인 삭제 (전체 {len(text_lines)}개 중)")
    # print(f"🗑️ 삭제된 텍스트들: {removed_texts}")
    
    output = {
        "original_text": markdown_text,
        "filtered_text": filtered_markdown,
        "removed_sections": removed_texts,
        "section_info": sections,
        "removed_count": len(removed_indices),
        "total_count": len(text_lines)
    }
    
    return output


def extract_sections_journal_result(markdown_text, **kwargs):
    """
    publications만 선별적으로 추출하는 함수
    
    Args:
        markdown_text: 원본 마크다운 텍스트
        
    Returns:
        dict: {
            "sections_journal_result": 마크다운 형태의 추출된 섹션들,
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
    
    # 논문과 수상 관련 섹션들만 추출
    target_sections = []
    # 논문 관련 섹션들
    target_sections.extend(remove_sections.get("publications", []))
    target_sections.extend(remove_sections.get("journal", []))
    target_sections.extend(remove_sections.get("journal_articles", []))
    
    # print(f"🎯 추출 대상 섹션들: {target_sections}")

    # sections = identify_sections_resume(text_lines, target_sections)

    # 직접 섹션 찾기 (폰트 기반 로직 대신 간단한 텍스트 매칭 사용)
    sections = []
    for idx, line_dict in enumerate(text_lines):
        line_text = line_dict["text"].strip()
        
        # 마크다운 헤더에서 ## 제거
        if line_text.startswith('## '):
            cleaned_text = line_text[3:].strip()
            # print(f"🔍 헤더 라인 {idx}: '{line_text}' -> '{cleaned_text}'")
        else:
            cleaned_text = line_text
        
        # 테이블 형식의 섹션 헤더 처리 (|로 시작하는 경우)
        if cleaned_text.startswith('|') and '|' in cleaned_text[1:]:
            original_cleaned = cleaned_text
            # 첫 번째 |와 두 번째 | 사이의 내용 추출
            parts = cleaned_text.split('|')
            if len(parts) >= 2:
                cleaned_text = parts[1].strip()  # 첫 번째 | 다음 부분
            # print(f"🔍 테이블 헤더 처리: '{original_cleaned}' -> '{cleaned_text}'")
        
        # 타겟 섹션과 매칭 확인
        for section in target_sections:
            if cleaned_text.lower() == section.lower():
                sections.append((idx, section, 100))
                # debug(f"🎯 섹션 매칭: '{cleaned_text}' -> '{section}'")
                break
    
    debug(f"🔍 찾은 섹션들: {sections}")
    
    # 찾은 섹션들의 인덱스 정보 수집
    section_indices = []
    for idx, section_name, score in sections:
        section_indices.append((idx, section_name, score))
    
    # 섹션 인덱스로 정렬
    section_indices.sort(key=lambda x: x[0])
    
    # 추출된 섹션들을 마크다운으로 구성
    sections_journal_result = []
    removed_count = 0
    
    for idx, section_name, score in section_indices:
        # 논문 또는 수상 관련 섹션인지 확인
        should_extract = False
        if section_name in remove_sections.get("publications", []):
            should_extract = True
            # print(f"📚 Publications 섹션 발견: '{section_name}'")
        elif section_name in remove_sections.get("journal", []):
            should_extract = True
            # print(f"📖 Journal 섹션 발견: '{section_name}'")
        elif section_name in remove_sections.get("journal_articles", []):
            should_extract = True
            # print(f"📄 Journal Articles 섹션 발견: '{section_name}'")
        
        if should_extract:
            # 섹션 헤더 추가
            sections_journal_result.append(f"## {section_name}")
            sections_journal_result.append("")  # 빈 줄 추가
            
            # 섹션 내용 추가
            start_idx = idx + 1  # 헤더 다음 라인부터 시작
            end_idx = len(text_lines)
            
            # 다음 섹션의 시작점 찾기 (다음 ## 헤더 찾기)
            for i in range(start_idx, len(text_lines)):
                if text_lines[i]["text"].strip().startswith("## "):
                    end_idx = i
                    break
            
            # 섹션 내용 수집
            for i in range(start_idx, end_idx):
                line_text = text_lines[i]["text"].strip()
                if line_text:  # 빈 줄이 아닌 경우만 추가
                    sections_journal_result.append(line_text)
                    removed_count += 1
            
            sections_journal_result.append("")  # 섹션 끝에 빈 줄 추가
            # print(f"📝 추출된 섹션: '{section_name}' ({end_idx - start_idx}개 라인)")
    
    # 마크다운 문자열로 결합
    sections_journal_markdown = '\n'.join(sections_journal_result)
    
    # print(f"📊 추출 통계: {removed_count}개 라인 추출 (총 {len(sections)}개 섹션)")
    
    output = {
        "sections_journal_result": sections_journal_markdown,
        "section_info": sections,
        "removed_count": removed_count,
        "total_sections": len(sections)
    }
    
    return output