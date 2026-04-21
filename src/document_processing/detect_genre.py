import re

def contains_korean(text):
    """
    Detects if the given text contains any Korean characters.

    Args:
        text (str): The input text to check.

    Returns:
        bool: True if Korean characters are found, False otherwise.
    """
    korean_regex = re.compile(r'[\uAC00-\uD7A3]')
    return bool(korean_regex.search(text))

def is_valid_code(s: str) -> bool:
    pattern = r'^[A-Za-z]{3}\d{4}$'
    return bool(re.match(pattern, s))
    
def detect_genre(doc):
    fonts = list(set([char['fontname'] for char in doc.pages[0].chars]))
    text = doc.pages[0].extract_text()
    first = text[0:8]

    if len(fonts) == 1 and fonts[0].endswith("ArialUnicodeMS"):
        return "linkedin"
    # remember 형식 체크: 첫 번째 줄이 특정 패턴(예: ETA2759, BJH6O8O)인지 확인
    if is_valid_code(first):
        return "remember"
        
    if contains_korean(text):
        if all("NanumBarunGothic" in font for font in fonts):
            return "wanted" 
        if all("gunGothic" in font or "Pretendard" in font for font in fonts):
            return "saramin"
        else:
            return "korean"
    return "normal"
