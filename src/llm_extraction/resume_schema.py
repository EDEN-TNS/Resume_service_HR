"""
이력서 추출용 고정 스키마 (structured output / 프롬프트와 동일 키만 사용).
Publications 는 별도 PublicationsExtraction 만 유지.
Field description 은 JSON Schema / vLLM structured output 힌트용.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

# --- Resume: flat snake_case (고정 항목만) ---

class BasicInfoBlock(BaseModel):
    """인적사항·연락처 (기본 정보)."""

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(None, description="성명 Full name or null")
    gender: Optional[str] = Field(None, description="성별 M/F or null")
    nationality: Optional[str] = Field(None, description="국적, 한글만 (e.g. 대한민국/미국/일본/기타) or null")
    address: Optional[str] = Field(None, description="현재 주소 Current address or null")
    birth_date: Optional[str] = Field(None, description="생년월일 YYYY.MM.DD or null")
    email: Optional[str] = Field(None, description="이메일 Email address or null")
    phone: Optional[str] = Field(None, description="연락처 010-XXXX-XXXX or null")

class ServicePeriod(BaseModel):
    """복무 기간."""

    model_config = ConfigDict(extra="forbid")

    start_date: Optional[str] = Field(None, description="복무 시작일 YYYY.MM.DD or null")
    end_date: Optional[str] = Field(None, description="복무 종료일 YYYY.MM.DD or null (복무 중이면 null)")


class MilitaryServiceBlock(BaseModel):
    """병역: 상태, 군종, 기간, 계급."""

    model_config = ConfigDict(extra="forbid")

    status: Optional[str] = Field(
        None,
        description="군필/면제/복무중/비대상/미필/해당없음 등 Completed/Exempted/Serving/Not applicable or null",
    )
    branch: Optional[str] = Field(None, description="군종 e.g. 육군/해군/공군/공익 Army/Navy/Air Force or null")
    rank: Optional[str] = Field(None, description="계급/병과 Rank at discharge or null")
    service_period: Optional[ServicePeriod] = Field(None, description="복무 기간 (시작·종료)")


class VeteransBlock(BaseModel):
    """보훈: 취업보호, 보훈번호, 가산점."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    type: Optional[str] = Field(None, description="보훈 대상 유형 Veteran type or null")
    veterans_id: Optional[str] = Field(None, description="보훈 ID 번호 Veterans ID or null")
    bonus_points: Optional[str] = Field(None, description="가산점 5% / 10% / 해당없음 or null")
    employment_protection: Optional[str] = Field(None, description="취업보호 Y/N/해당없음 or null")


class DisabilityBlock(BaseModel):
    """장애: 유형, 등급."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    type: Optional[str] = Field(
        None,
        description="장애 유형 지체/시각/청각/지적/자폐성/기타/해당없음 or null",
    )
    severity: Optional[str] = Field(None, description="등급/중증도 1~3급/4~6급/중증장애인 등 or null")


class FamilyMemberItem(BaseModel):
    """가족 1명."""

    model_config = ConfigDict(extra="forbid")

    relation: Optional[str] = Field(None, description="관계 부/모/배우자/자녀/형제 등 or null")
    name: Optional[str] = Field(None, description="가족 성명 or null")
    birth_date: Optional[str] = Field(None, description="생년월일 YYYY.MM.DD or null")


class EducationItem(BaseModel):
    """학력 1건 (초·중·고·대학 등 공통)."""

    model_config = ConfigDict(extra="forbid")

    school_name: Optional[str] = Field(None, description="교명만, 괄호 내 지역 제외 School name or null")
    location: Optional[str] = Field(None, description="시/도 + 시/군/구 Geographic location or null")
    major: Optional[str] = Field(None, description="전공 Major or null")
    degree: Optional[str] = Field(None, description="학위 High school/College/Bachelor/Master/PhD or null")
    status: Optional[str] = Field(
        None,
        description="졸업상태 재학/졸업/수료/중퇴/졸업예정/타교편입 or null",
    )
    start_date: Optional[str] = Field(None, description="시작 YYYY-MM or null")
    end_date: Optional[str] = Field(None, description="종료 YYYY-MM or null")
    gpa: Optional[Union[str, float, int]] = Field(None, description="학점 GPA, 명시 시에만 (문자열 권장) or null")


class LanguageTestItem(BaseModel):
    """공인어학 시험 1건."""

    model_config = ConfigDict(extra="forbid")

    category: Optional[str] = Field(None, description="언어 구분 e.g. English, Japanese or null")
    test_name: Optional[str] = Field(None, description="시험명 TOEIC/OPIc/JLPT 등 or null")
    score: Optional[str] = Field(None, description="점수/등급 Score or level or null")
    acquired_date: Optional[str] = Field(None, description="취득일 YYYY-MM or null")


class LanguageSkillItem(BaseModel):
    """외국어 구술·작문 역량 1건 (자연어; 프로그래밍 언어 제외)."""

    model_config = ConfigDict(extra="forbid")

    language: Optional[str] = Field(None, description="언어 e.g. 영어/일본어 or null")
    country_of_use: Optional[str] = Field(None, description="사용 국가 Country or null")
    proficiency: Optional[str] = Field(None, description="수준 High/Intermediate/Basic/CEFR 등 or null")


class CertificationItem(BaseModel):
    """자격증 1건."""

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(None, description="자격증명 or null")
    level: Optional[str] = Field(None, description="등급/레벨 or null")
    acquired_date: Optional[str] = Field(None, description="취득일 YYYY-MM or null")
    issuer: Optional[str] = Field(None, description="발급 기관 Issuing organization or null")


class OverseasExperienceItem(BaseModel):
    """해외 체류·연수 1건."""

    model_config = ConfigDict(extra="forbid")

    organization: Optional[str] = Field(None, description="기관/단체 Organization or null")
    period_start: Optional[str] = Field(None, description="시작 YYYY-MM or null")
    period_end: Optional[str] = Field(None, description="종료 YYYY-MM or null")
    reason: Optional[str] = Field(None, description="체류 목적 Purpose of stay or null")
    family_companions: Optional[str] = Field(None, description="동반 가족 Accompanying family or null")


class SoftwareSkillItem(BaseModel):
    """프로그램·도구 숙련도 1건."""

    model_config = ConfigDict(extra="forbid")

    category: Optional[str] = Field(None, description="구분 Office/Design/Development/해당없음 or null")
    study_period_start: Optional[str] = Field(None, description="학습 시작 YYYY-MM or null")
    study_period_end: Optional[str] = Field(None, description="학습 종료 YYYY-MM or null")
    program_name: Optional[str] = Field(None, description="프로그램·도구명 e.g. Python, Excel or null")
    proficiency: Optional[str] = Field(None, description="숙련도 Advanced/Intermediate/Basic or null")


class ExperienceItem(BaseModel):
    """경력 1건."""

    model_config = ConfigDict(extra="forbid")

    employment_type: Optional[str] = Field(None, description="고용형태 정규/계약/인턴/프리랜서 등 or null")
    company: Optional[str] = Field(None, description="회사명 (위치 제외) Company name or null")
    location: Optional[str] = Field(None, description="근무지 City/주소 or null")
    department: Optional[str] = Field(None, description="부서/팀 Department or null")
    period_start: Optional[str] = Field(None, description="입사 YYYY-MM or null")
    period_end: Optional[str] = Field(None, description="퇴사 YYYY-MM or null")
    position: Optional[str] = Field(None, description="직위/직급 Official job title/rank or null")
    role: Optional[str] = Field(None, description="직무/담당 업무 Functional area or null")
    reason_for_change: Optional[str] = Field(None, description="이직 사유 Reason for leaving or null")
    annual_salary: Optional[Union[str, float, int]] = Field(None, description="연봉 명시 시만 or null")
    details: Optional[str] = Field(None, description="상세 업무/성과 Job description or achievements or null")


class ActivityCompetitionItem(BaseModel):
    """대외활동·수상·공모전 등 1건."""

    model_config = ConfigDict(extra="forbid")

    period_start: Optional[str] = Field(None, description="시작 YYYY-MM or null")
    period_end: Optional[str] = Field(None, description="종료 YYYY-MM or null")
    award: Optional[str] = Field(None, description="수상명·대회명 Award/competition name or null")
    agency: Optional[str] = Field(None, description="주관 기관 Sponsoring agency or null")
    description: Optional[str] = Field(None, description="활동·수상 상세 Activity details or null")


class ResumeExtraction(BaseModel):
    """고정 키만 갖는 이력서 추출 루트."""

    model_config = ConfigDict(extra="forbid")

    basic_info: BasicInfoBlock = Field(default_factory=BasicInfoBlock, description="인적사항·연락처")
    military_service: MilitaryServiceBlock = Field(default_factory=MilitaryServiceBlock, description="병역")
    veterans: VeteransBlock = Field(default_factory=VeteransBlock, description="보훈")
    disability: DisabilityBlock = Field(default_factory=DisabilityBlock, description="장애")
    family_members: list[FamilyMemberItem] = Field(default_factory=list, description="가족 구성원 목록")
    education: list[EducationItem] = Field(default_factory=list, description="학력 목록 (문서 순서)")
    language_tests: list[LanguageTestItem] = Field(default_factory=list, description="공인어학 시험 목록")
    language_skills: list[LanguageSkillItem] = Field(default_factory=list, description="외국어 역량 목록 (자연어)")
    certifications: list[CertificationItem] = Field(default_factory=list, description="자격증 목록")
    overseas_experience: list[OverseasExperienceItem] = Field(default_factory=list, description="해외 경험 목록")
    software_skills: list[SoftwareSkillItem] = Field(default_factory=list, description="프로그램/스킬 목록")
    experience: list[ExperienceItem] = Field(default_factory=list, description="경력 목록 (문서 순서)")
    activities_competitions: list[ActivityCompetitionItem] = Field(
        default_factory=list,
        description="대외활동·수상·공모전 등 목록",
    )
    available_start_date: Optional[str] = Field(
        None,
        description="입사 가능일 YYYY-MM or YYYY-MM-DD, 문서에 명시된 경우만 or null",
    )


ResumeExtraction.model_rebuild()


@lru_cache(maxsize=1)
def get_resume_json_schema() -> dict:
    return ResumeExtraction.model_json_schema()


# --- Publications (논문 전용, 이력서 스키마와 분리) ---


class RmkResearchReportsItem(BaseModel):
    """논문/연구보고서 1건."""

    model_config = ConfigDict(extra="forbid")

    researchType: Optional[Literal["학위논문", "학술지", "보고서", "기타"]] = Field(
        None,
        description="논문 유형: '학위논문'/'학술지'/'보고서' 중 해당 없으면 '기타'. null 허용",
    )
    registerLabName: Optional[str] = Field(None, description="저널명/학회명/발행기관명 or null")
    registerDate: Optional[str] = Field(None, description="YYYY.MM.DD or null")
    authorName: Optional[str] = Field("기타", description="항상 '기타'로 설정 (스키마 규칙)")
    reportTitle: Optional[str] = Field(None, description="논문 제목 or null")
    reportContent: Optional[str] = Field(None, description="논문 내용/요약 or null")


class PublicationsExtraction(BaseModel):
    """논문 정보 추출 결과 (논문만 별도 추출하는 경우)."""

    model_config = ConfigDict(extra="forbid")

    rmkResearchReportsInfoList: list[RmkResearchReportsItem] = Field(
        default_factory=list,
        description="논문/연구보고서 목록",
    )


PublicationsExtraction.model_rebuild()


@lru_cache(maxsize=1)
def get_publications_json_schema() -> dict:
    return PublicationsExtraction.model_json_schema()
