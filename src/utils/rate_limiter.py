"""
IP/클라이언트별 Rate Limiting 유틸리티
- 슬라이딩 윈도우 알고리즘 사용
- 메모리 기반 (in-memory)
"""

import time
from collections import defaultdict, deque
from typing import Optional, Tuple

from fastapi import HTTPException, Request, status

from src.utils.global_logger import warning


class RateLimiter:
    """IP/클라이언트별 Rate Limiter (슬라이딩 윈도우)"""

    def __init__(
        self,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        window_size_seconds: int = 60,
    ):
        """
        Args:
            requests_per_minute: 분당 허용 요청 수
            requests_per_hour: 시간당 허용 요청 수
            window_size_seconds: 슬라이딩 윈도우 크기 (초)
        """
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.window_size = window_size_seconds

        # IP별 요청 타임스탬프 저장 (슬라이딩 윈도우)
        # {ip: deque([timestamp1, timestamp2, ...])}
        self._request_timestamps: defaultdict[str, deque] = defaultdict(deque)

        # IP별 시간당 요청 카운터 (시간 윈도우)
        # {ip: {hour_timestamp: count}}
        self._hourly_requests: defaultdict[str, dict] = defaultdict(dict)

    def _get_client_ip(self, request: Request) -> str:
        """클라이언트 IP 주소 추출"""
        # X-Forwarded-For 헤더 확인 (프록시/로드밸런서 뒤에 있을 때)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # 첫 번째 IP 사용 (원본 클라이언트)
            return forwarded_for.split(",")[0].strip()

        # X-Real-IP 헤더 확인
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

        # 직접 연결인 경우
        if request.client:
            return request.client.host

        return "unknown"

    def _cleanup_old_timestamps(self, ip: str, current_time: float):
        """오래된 타임스탬프 정리 (슬라이딩 윈도우)"""
        timestamps = self._request_timestamps[ip]
        # 윈도우 밖의 타임스탬프 제거
        while timestamps and (current_time - timestamps[0]) > self.window_size:
            timestamps.popleft()

    def _cleanup_old_hourly(self, ip: str, current_time: float):
        """오래된 시간별 카운터 정리"""
        hour_timestamp = int(current_time // 3600)  # 시간 단위 타임스탬프
        hourly = self._hourly_requests[ip]

        # 1시간 이상 오래된 항목 제거
        keys_to_remove = [
            key for key in hourly.keys() if key < hour_timestamp - 1
        ]
        for key in keys_to_remove:
            del hourly[key]

    def is_allowed(self, request: Request) -> Tuple[bool, Optional[str]]:
        """
        요청이 허용되는지 확인

        Returns:
            (is_allowed, error_message)
        """
        ip = self._get_client_ip(request)
        current_time = time.time()

        # 슬라이딩 윈도우 정리
        self._cleanup_old_timestamps(ip, current_time)
        self._cleanup_old_hourly(ip, current_time)

        # 분당 요청 수 체크 (슬라이딩 윈도우)
        timestamps = self._request_timestamps[ip]
        if len(timestamps) >= self.requests_per_minute:
            return (
                False,
                f"Rate limit exceeded: {self.requests_per_minute} requests per minute",
            )

        # 시간당 요청 수 체크
        hour_timestamp = int(current_time // 3600)
        hourly = self._hourly_requests[ip]
        current_hour_count = hourly.get(hour_timestamp, 0)

        if current_hour_count >= self.requests_per_hour:
            return (
                False,
                f"Rate limit exceeded: {self.requests_per_hour} requests per hour",
            )

        # 요청 허용 - 타임스탬프 추가
        timestamps.append(current_time)
        hourly[hour_timestamp] = current_hour_count + 1

        return (True, None)

    def get_remaining_requests(self, request: Request) -> dict[str, int]:
        """남은 요청 수 반환"""
        ip = self._get_client_ip(request)
        current_time = time.time()

        self._cleanup_old_timestamps(ip, current_time)
        self._cleanup_old_hourly(ip, current_time)

        timestamps = self._request_timestamps[ip]
        hour_timestamp = int(current_time // 3600)
        hourly = self._hourly_requests[ip]

        return {
            "remaining_per_minute": max(0, self.requests_per_minute - len(timestamps)),
            "remaining_per_hour": max(
                0, self.requests_per_hour - hourly.get(hour_timestamp, 0)
            ),
            "requests_in_minute": len(timestamps),
            "requests_in_hour": hourly.get(hour_timestamp, 0),
        }

    def reset(self, ip: Optional[str] = None):
        """Rate limiter 초기화 (특정 IP 또는 전체)"""
        if ip:
            if ip in self._request_timestamps:
                del self._request_timestamps[ip]
            if ip in self._hourly_requests:
                del self._hourly_requests[ip]
        else:
            self._request_timestamps.clear()
            self._hourly_requests.clear()


# 전역 Rate Limiter 인스턴스
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Rate Limiter 싱글톤 인스턴스 반환"""
    global _rate_limiter
    if _rate_limiter is None:
        import os

        requests_per_minute = int(os.getenv("RATE_LIMIT_PER_MINUTE", "1000")) # 분당 허용 요청 수 (기본값: 1000)
        requests_per_hour = int(os.getenv("RATE_LIMIT_PER_HOUR", "1000")) # 시간당 허용 요청 수 (기본값: 1000)
        window_size = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60")) # 슬라이딩 윈도우 크기 (기본값: 60초)

        _rate_limiter = RateLimiter(
            requests_per_minute=requests_per_minute,
            requests_per_hour=requests_per_hour,
            window_size_seconds=window_size,
        )
    return _rate_limiter


async def rate_limit_middleware(request: Request, call_next):
    """Rate Limiting 미들웨어"""
    # 헬스 체크 및 디버그 엔드포인트는 제외
    excluded_paths = ["/health", "/docs", "/redoc", "/openapi.json", "/"]
    if request.url.path in excluded_paths:
        return await call_next(request)

    rate_limiter = get_rate_limiter()
    is_allowed, error_message = rate_limiter.is_allowed(request)

    if not is_allowed:
        warning(
            f"🚫 [Rate Limit] 요청 차단: IP={rate_limiter._get_client_ip(request)}, "
            f"Path={request.url.path}, Error={error_message}"
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Rate limit exceeded",
                "message": error_message,
                "remaining": rate_limiter.get_remaining_requests(request),
            },
        )

    response = await call_next(request)

    # Rate limit 헤더 추가
    remaining = rate_limiter.get_remaining_requests(request)
    response.headers["X-RateLimit-Limit-PerMinute"] = str(
        rate_limiter.requests_per_minute
    )
    response.headers["X-RateLimit-Limit-PerHour"] = str(rate_limiter.requests_per_hour)
    response.headers["X-RateLimit-Remaining-PerMinute"] = str(
        remaining["remaining_per_minute"]
    )
    response.headers["X-RateLimit-Remaining-PerHour"] = str(
        remaining["remaining_per_hour"]
    )

    return response

