"""
문서 타입별 Verify 프롬프트 및 필드 정의

각 문서 타입에 대해:
- 추출할 필드 목록
- 문서 특성을 반영한 상세 프롬프트
"""

from typing import List


class DocumentPrompts:
    """문서 타입별 프롬프트 및 필드 정의"""
    
    @staticmethod
    def get_prompt_and_fields(doc_type: str) -> tuple[str, List[str]]:
        """
        문서 타입에 해당하는 프롬프트와 필드 목록 반환
        
        Args:
            doc_type: 문서 타입 (예: "OPIC", "TOEIC")
            
        Returns:
            (prompt_template, required_fields)
        """
        prompts = {
            "OPIC": DocumentPrompts._get_opic_prompt(),
            "TOEIC": DocumentPrompts._get_toeic_prompt(),
            "TOEIC_SPEAKING": DocumentPrompts._get_toeic_speaking_prompt(),
            "TEPS": DocumentPrompts._get_teps_prompt(),
            "TOEFL": DocumentPrompts._get_toefl_prompt(),
            "HSK": DocumentPrompts._get_hsk_prompt(),
            "JLPT": DocumentPrompts._get_jlpt_prompt(),
            "GTELP": DocumentPrompts._get_gtelp_prompt(),
            "FINAL_EDU_CERT": DocumentPrompts._get_final_edu_cert_prompt(),
            "UNIV_GRAD_CERT": DocumentPrompts._get_univ_grad_cert_prompt(),
            "KOREAN_HISTORY": DocumentPrompts._get_korean_history_prompt(),
        }
        
        return prompts.get(doc_type, DocumentPrompts._get_default_prompt(doc_type))
    
    @staticmethod
    def _get_opic_prompt() -> tuple[str, List[str]]:
        """OPIC (Oral Proficiency Interview - Computer) 프롬프트"""
        fields = [
            "인증서번호",
            "NAME", 
            "Test ID",
            "Date of Birth",
            "Test Date",
            "Test Type",
            "RANK",
            "Date of Issue",
            "Date of Expiry"
        ]
        
        prompt = """
You are extracting fields from an **OPIC (Oral Proficiency Interview - Computer)** certificate.

📋 DOCUMENT CHARACTERISTICS:
- Korean & English bilingual document
- Contains a certification number (인증서번호)
- Shows test taker's name in English (NAME)
- Includes Test ID (unique identifier)
- Displays birth date, test date, issue date, and expiry date
- Shows RANK (rating level: e.g., AL, IH, IM, IL, NH, NM, NL)
- Test Type indicates the level tested

🎯 EXTRACTION RULES:
1. **인증서번호**: Extract the full certificate number exactly as printed (may contain numbers and dashes)
2. **NAME**: Full name in English (UPPERCASE, e.g., "KANG SEONG MUN")
3. **Test ID**: Unique test identifier (format: KOR followed by numbers)
4. **Date of Birth**: Format as shown (e.g., "1997년 02월 21일" or "Feb 21, 1997")
5. **Test Date**: Date when test was taken
6. **Test Type**: The level category (e.g., "IM/IH", "NH/NM")
7. **RANK**: The achieved rating level (AL/IH/IM/IL/NH/NM/NL)
8. **Date of Issue**: Certificate issue date
9. **Date of Expiry**: Certificate expiration date

⚠️ IMPORTANT:
- Keep all dates in their original format
- Preserve exact spelling and capitalization for NAME
- RANK must be one of the valid OPIC levels
- Do NOT translate Korean text to English
- If any field is not clearly visible, use null

OUTPUT: Single JSON object with the above keys only.
"""
        
        return prompt, fields
    
    @staticmethod
    def _get_toeic_prompt() -> tuple[str, List[str]]:
        """TOEIC (Listening & Reading) 프롬프트"""
        fields = [
            "이름",
            "등록번호",
            "생년월일",
            "시험일자",
            "유효기간",
            "듣기점수",
            "읽기점수",
            "총점",
            "발급번호"
        ]
        
        prompt = """
You are extracting fields from a **TOEIC (Listening & Reading)** score certificate (Korean version).

📋 DOCUMENT CHARACTERISTICS:
- All text in Korean
- Shows personal info: name (이름), registration number (등록번호), birth date (생년월일)
- Test date (시험일자) and validity period (유효기간)
- Score breakdown: Listening (듣기), Reading (읽기), Total (총점)
- Issue number (발급번호)

🎯 EXTRACTION RULES:
1. **이름**: Full Korean name (e.g., "홍길동")
2. **등록번호**: Registration/ID number (may contain letters and numbers)
3. **생년월일**: Birth date in Korean format (e.g., "1990년 01월 15일")
4. **시험일자**: Test date (e.g., "2025년 10월 24일")
5. **유효기간**: Validity/expiration date
6. **듣기점수**: Listening score (0-495)
7. **읽기점수**: Reading score (0-495)
8. **총점**: Total score (0-990)
9. **발급번호**: Certificate issue number

⚠️ IMPORTANT:
- Scores must be numeric values only
- Keep dates in Korean format as printed
- Total score = Listening + Reading
- Do NOT translate field names
- If any field is unclear, use null

OUTPUT: Single JSON object with the above keys only.
"""
        
        return prompt, fields
    
    @staticmethod
    def _get_toeic_speaking_prompt() -> tuple[str, List[str]]:
        """TOEIC Speaking & Writing 프롬프트"""
        fields = [
            "이름",
            "등록번호",
            "생년월일",
            "시험일자",
            "유효기간",
            "말하기점수",
            "쓰기점수",
            "총점",
            "발급번호"
        ]
        
        prompt = """
You are extracting fields from a **TOEIC Speaking & Writing** certificate (Korean version).

📋 DOCUMENT CHARACTERISTICS:
- Similar to TOEIC L&R but tests Speaking (말하기) and Writing (쓰기)
- Speaking score range: 0-200
- Writing score range: 0-200
- May show level ratings alongside numeric scores

🎯 EXTRACTION RULES:
1. **이름**: Full Korean name
2. **등록번호**: Registration number
3. **생년월일**: Birth date in Korean format
4. **시험일자**: Test date
5. **유효기간**: Certificate validity period
6. **말하기점수**: Speaking score (0-200)
7. **쓰기점수**: Writing score (0-200)
8. **총점**: Total or combined representation
9. **발급번호**: Issue number

⚠️ IMPORTANT:
- Speaking and Writing are separate scores
- Each section may also show level (1-8)
- Extract numeric scores only, ignore level descriptions
- Keep all Korean text unchanged

OUTPUT: Single JSON object with the above keys only.
"""
        
        return prompt, fields
    
    @staticmethod
    def _get_teps_prompt() -> tuple[str, List[str]]:
        """TEPS (Test of English Proficiency developed by Seoul National University) 프롬프트"""
        fields = [
            "NAME",
            "REGISTRATION NO.",
            "DATE OF BIRTH",
            "TEST DATE",
            "GENDER",
            "VALID UNTIL",
            "Listening Score",
            "Grammar Score",
            "Vocabulary Score",
            "Reading Score",
            "TOTAL Score",
            "ISSUE NO."
        ]
        
        prompt = """
You are extracting fields from a **TEPS** certificate (English format).

📋 DOCUMENT CHARACTERISTICS:
- All field names in English
- Developed by Seoul National University
- Four sections: Listening, Grammar, Vocabulary, Reading
- Each section scored separately
- Total score is sum of all sections (max varies by version)

🎯 EXTRACTION RULES:
1. **NAME**: Full name in English (UPPERCASE)
2. **REGISTRATION NO.**: Registration/ID number
3. **DATE OF BIRTH**: Birth date
4. **TEST DATE**: Date of examination
5. **GENDER**: Male/Female or M/F
6. **VALID UNTIL**: Certificate expiration date
7. **Listening Score**: Score for listening section
8. **Grammar Score**: Score for grammar section (Note: "Grammar" not "Grammer")
9. **Vocabulary Score**: Score for vocabulary section
10. **Reading Score**: Score for reading section
11. **TOTAL Score**: Sum of all four sections
12. **ISSUE NO.**: Certificate issue number

⚠️ IMPORTANT:
- All section scores should be numeric
- Total = Listening + Grammar + Vocabulary + Reading
- Keep exact field name capitalization (e.g., "Grammar Score" not "Grammer Score")
- Date format may vary (MM/DD/YYYY or similar)

OUTPUT: Single JSON object with the above keys only.
"""
        
        return prompt, fields
    
    @staticmethod
    def _get_toefl_prompt() -> tuple[str, List[str]]:
        """TOEFL (Test of English as a Foreign Language) 프롬프트"""
        fields = [
            "수험번호",
            "시험일자",
            "성적표 발급번호",
            "총점/영역점수"
        ]
        
        prompt = """
You are extracting fields from a **TOEFL** score report (Korean version).

📋 DOCUMENT CHARACTERISTICS:
- International English test by ETS
- Shows total score (0-120) and section scores
- Sections: Reading, Listening, Speaking, Writing (each 0-30)
- Contains test taker registration number

🎯 EXTRACTION RULES:
1. **수험번호**: Test registration/confirmation number
2. **시험일자**: Test date
3. **성적표 발급번호**: Score report issue number
4. **총점/영역점수**: Total score and/or section breakdown
   - Format may be: "Total: 110 (R:28 L:29 S:27 W:26)"
   - Or just total score

⚠️ IMPORTANT:
- Total score range: 0-120
- Each section range: 0-30
- Extract scores as shown on document
- If section breakdown not visible, extract total only

OUTPUT: Single JSON object with the above keys only.
"""
        
        return prompt, fields
    
    @staticmethod
    def _get_hsk_prompt() -> tuple[str, List[str]]:
        """HSK (Hanyu Shuiping Kaoshi - Chinese Proficiency Test) 프롬프트"""
        fields = [
            "성적표번호",
            "성명",
            "생년월일",
            "국적",
            "성별",
            "듣기점수",
            "독해점수",
            "쓰기점수",
            "총점"
        ]
        
        prompt = """
You are extracting fields from an **HSK** (Chinese Proficiency Test) certificate (Korean version).

📋 DOCUMENT CHARACTERISTICS:
- Chinese language proficiency test
- Levels: HSK 1-6 (or newer HSK 1-9)
- Three sections: Listening (듣기), Reading (독해), Writing (쓰기)
- Shows nationality (국적) field
- Score ranges vary by level

🎯 EXTRACTION RULES:
1. **성적표번호**: Certificate/score report number
2. **성명**: Full name (may be in Korean, Chinese, or English)
3. **생년월일**: Date of birth
4. **국적**: Nationality (e.g., "중국", "한국")
5. **성별**: Gender (남/여 or M/F)
6. **듣기점수**: Listening score
7. **독해점수**: Reading score
8. **쓰기점수**: Writing score
9. **총점**: Total score

⚠️ IMPORTANT:
- Score ranges depend on HSK level (e.g., HSK 4: each section 0-100)
- Extract scores as numeric values
- Name may be in multiple languages - extract as shown
- Keep nationality in original language

OUTPUT: Single JSON object with the above keys only.
"""
        
        return prompt, fields
    
    @staticmethod
    def _get_jlpt_prompt() -> tuple[str, List[str]]:
        """JLPT (Japanese Language Proficiency Test) 프롬프트"""
        fields = [
            "수험번호",
            "시험일자",
            "성적표 발급번호",
            "점수/합격 여부"
        ]
        
        prompt = """
You are extracting fields from a **JLPT** (Japanese Language Proficiency Test) certificate.

📋 DOCUMENT CHARACTERISTICS:
- Japanese proficiency test with 5 levels (N1-N5)
- Shows pass/fail status and scores
- Sections vary by level but typically include Language Knowledge, Reading, Listening
- Passing score varies by level

🎯 EXTRACTION RULES:
1. **수험번호**: Examinee registration number
2. **시험일자**: Test date
3. **성적표 발급번호**: Score report issue number
4. **점수/합격 여부**: Scores and pass/fail status
   - May include total score, section scores, and "합격/불합격"
   - Format: "총점: 120/180 (합격)" or similar

⚠️ IMPORTANT:
- Extract both numeric scores and pass/fail status if shown
- N1 is highest level, N5 is basic level
- Score ranges differ by level and section

OUTPUT: Single JSON object with the above keys only.
"""
        
        return prompt, fields
    
    @staticmethod
    def _get_gtelp_prompt() -> tuple[str, List[str]]:
        """G-TELP (General Tests of English Language Proficiency) 프롬프트"""
        fields = [
            "이름",
            "주민등록번호",
            "합격여부",
            "듣기점수",
            "읽기 및 어휘 점수",
            "문법점수",
            "총점"
        ]
        
        prompt = """
You are extracting fields from a **G-TELP** certificate (Korean version).

📋 DOCUMENT CHARACTERISTICS:
- General English proficiency test
- Levels: 1-5 (Level 2 most common)
- Shows Korean resident registration number (주민등록번호)
- Pass/Fail status (합격/불합격)
- Sections: Listening, Grammar, Reading & Vocabulary

🎯 EXTRACTION RULES:
1. **이름**: Full Korean name
2. **주민등록번호**: Korean resident registration number (format: XXXXXX-XXXXXXX)
3. **합격여부**: Pass/Fail status ("합격" or "불합격")
4. **듣기점수**: Listening score
5. **읽기 및 어휘 점수**: Reading & Vocabulary combined score
6. **문법점수**: Grammar score
7. **총점**: Total score

⚠️ IMPORTANT:
- Resident registration number format: 6 digits - 7 digits
- Pass/fail criteria varies by level and purpose
- Extract exact scores as shown
- Keep Korean text unchanged

OUTPUT: Single JSON object with the above keys only.
"""
        
        return prompt, fields
    
    @staticmethod
    def _get_final_edu_cert_prompt() -> tuple[str, List[str]]:
        """최종학력증명서 프롬프트"""
        fields = [
            "성명",
            "생년월일",
            "소속",
            "입학일자",
            "졸업일자",
            "학위등록번호",
            "학위명",
            "복수전공",
            "문서 진위확인 번호"
        ]
        
        prompt = """
You are extracting fields from a **최종학력증명서** (Final Education Certificate - Korean university degree certificate).

📋 DOCUMENT CHARACTERISTICS:
- Official university degree certificate from Korean institution
- Shows student's academic record and degree information
- Contains unique degree registration number (학위등록번호)
- Includes document verification number (문서 진위확인 번호) for authenticity check
- May show double major (복수전공) if applicable

🎯 EXTRACTION RULES:
1. **성명**: Full name in Korean (e.g., "홍길동")
2. **생년월일**: Birth date (format: YYYY년 MM월 DD일 or YYYY.MM.DD)
3. **소속**: Department/College/School (e.g., "공과대학 컴퓨터공학과")
4. **입학일자**: Admission/enrollment date
5. **졸업일자**: Graduation date
6. **학위등록번호**: Degree registration number (unique identifier)
7. **학위명**: Degree name (e.g., "공학사", "이학사", "문학사")
8. **복수전공**: Double major if applicable (null if none)
9. **문서 진위확인 번호**: Document verification number for authenticity

⚠️ IMPORTANT:
- **학위등록번호** is critical for verification - extract complete number
- **문서 진위확인 번호** allows online verification - must be exact
- Keep all Korean text exactly as written
- Dates should match the format shown on document
- If 복수전공 not mentioned, use null
- Department (소속) may include college and major

OUTPUT: Single JSON object with the above keys only.
"""
        
        return prompt, fields
    
    @staticmethod
    def _get_univ_grad_cert_prompt() -> tuple[str, List[str]]:
        """졸업증명서 프롬프트"""
        fields = [
            "문서명",
            "문서번호",
            "학교",
            "이름",
            "발급일",
            "생년월일",
        ]
        
        prompt = """
You are extracting fields from a **졸업증명서** (University Graduation Certificate).

📋 DOCUMENT CHARACTERISTICS:
- Korean university graduation certificate
- Contains document title, school name, student name, dates
- Official document with document number
- May include verification number at bottom

🎯 EXTRACTION RULES:
1. **문서명**: Document title exactly as printed
   - Usually "졸업증명서" or "졸업증명서(국문)" or "Graduation Certificate"
   - Extract the exact title text at top of document

2. **문서번호**: Document Verification Number (primary)
   - 목적: 온라인 진위 확인에 사용되는 번호만 추출.
   - 우선순위 규칙:
     1) "문서확인번호", "원본(문서)확인번호", "Document Verification Number",
        "Certificate Verification Code", 또는 전자증명서의 "INTERNET NO"로
        표시된 **검증 번호**가 있으면 그것만 단일 값으로 추출.
     2) 위 항목이 없을 때에만 보조적으로 "제 ○○호" 형식의 **행정 발급번호**를 추출.
   - 위치: 문서 어디에든 있을 수 있으므로 위치를 가정하지 말 것.
   - 형식/정규화:
     - 라벨(예: "문서확인번호:", "INTERNET NO")은 제거하고 **코드만** 반환.
     - 코드 내부 공백/줄바꿈을 제거하고 하이픈은 원문 그대로 유지.
     - 대소문자는 원문 표기를 유지(영문자 보정 금지), 숫자/문자 혼동(O↔0 등) 추측 금지.
   - 금지 사항:
     - 서로 다른 번호를 **결합하거나 줄바꿈으로 함께 반환하지 말 것**(항상 단일 문자열).
     - 다음 항목은 문서번호로 취급하지 말 것:
       "학위등록번호", "졸업증서번호", "접수/신청/발급 번호" 등 학내 관리용 식별자.
   - 패턴 힌트(예시, 강제 아님):
     - 검증번호: 대문자/숫자 하이픈 조합(예: `XXXX-XXXX-XXXX-XXXX`), 또는
       12~24자리 이상의 숫자열(예: `INTERNET NO 3538804515533827`).
     - 행정번호: `제` [숫자/하이픈/공백] `호` (예: `제 11892 호`, `제-11892호`).

3. **학교**: School/University name
   - Full official name (e.g., "서울대학교", "고려대학교", "연세대학교")
   - Extract exactly as printed, including "대학교" suffix
   - Do NOT abbreviate

4. **이름**: Student name
   - Full Korean name (e.g., "홍길동", "김철수")
   - May be labeled as "성명" or "이름"
   - Extract exactly as written

5. **발급일**: Issue date
   - Format: "YYYY년 MM월 DD일" or "YYYY.MM.DD"
   - May be labeled as "발급일자", "발급일", or near official seal
   - Keep original format (do NOT convert)

6. **생년월일**: Date of birth
   - Format: "YYYY년 MM월 DD일" or "YYYY.MM.DD" or "YYMMDD"
   - May be labeled as "생년월일" or near name field
   - Keep original format exactly as shown

⚠️ IMPORTANT:
- Extract text EXACTLY as printed (no translation, no conversion)
- Keep all Korean text in Korean
- Keep date formats as shown on document
- If field not clearly visible → use null
- Document number is critical for verification - must be complete

OUTPUT: Single JSON object with the 6 keys above only.
"""
        
        return prompt, fields
    
    @staticmethod
    def _get_korean_history_prompt() -> tuple[str, List[str]]:
        """한국사능력검정시험 프롬프트"""
        fields = [
            "성명",
            "생년월일",
            "합격등급",
            "인증서번호",
            "합격일자"
        ]
        
        prompt = """
You are extracting fields from a **한국사능력검정시험** (Korean History Proficiency Test) certificate.

📋 DOCUMENT CHARACTERISTICS:
- Korean government-administered history test
- Shows grade level (등급): 1급 (highest), 2급, 3급, or 4급/5급/6급 (basic)
- Contains certificate number (인증서번호)
- Pass date (합격일자) indicates when passed

🎯 EXTRACTION RULES:
1. **성명**: Full name in Korean
2. **생년월일**: Birth date
3. **합격등급**: Pass grade/level (e.g., "1급", "2급", "3급")
4. **인증서번호**: Certificate number (unique identifier)
5. **합격일자**: Date of passing the exam

⚠️ IMPORTANT:
- Grade (등급) is critical - must be exact: 1급, 2급, 3급, etc.
- Certificate number format may vary
- This certificate is often required for public sector jobs
- Keep all Korean text unchanged

OUTPUT: Single JSON object with the above keys only.
"""
        
        return prompt, fields
    
    @staticmethod
    def _get_default_prompt(doc_type: str) -> tuple[str, List[str]]:
        """기본 프롬프트 (문서 타입이 정의되지 않은 경우)"""
        fields = []
        
        prompt = f"""
You are a document field extractor for verification.

Document type: {doc_type}

This document type is not yet configured with specific fields.
Please extract all visible key-value pairs from the document.

RULES:
- Extract information exactly as printed
- Keep original language (do not translate)
- Use null for missing or unclear values
- Output as JSON object

OUTPUT: JSON object with extracted fields.
"""
        
        return prompt, fields

