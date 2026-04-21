"""
재사용 가능한 HTTP 클라이언트 유틸리티

httpx.AsyncClient를 싱글톤으로 관리하여 커넥션 풀 재사용
- TCP 커넥션 재사용으로 성능 향상
- 커넥션 풀 관리로 리소스 효율성 개선
"""

import httpx
from typing import Optional


class HTTPClientManager:
    """HTTP 클라이언트 싱글톤 관리자"""
    
    _instance: Optional['HTTPClientManager'] = None
    _client: Optional[httpx.AsyncClient] = None
    _default_timeout: float = 300.0
    
    def __new__(cls):
        """싱글톤 패턴 구현"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """초기화 (한 번만 실행)"""
        if self._client is not None:
            return
        
        # 기본 클라이언트 생성 (커넥션 풀 포함)
        self._client = httpx.AsyncClient(
            timeout=self._default_timeout,
            limits=httpx.Limits(
                max_keepalive_connections=20,  # 유지할 최대 커넥션 수
                max_connections=100,            # 최대 동시 커넥션 수
                keepalive_expiry=30.0          # 커넥션 유지 시간 (초)
            )
        )
    
    @property
    def client(self) -> httpx.AsyncClient:
        """재사용 가능한 HTTP 클라이언트 반환"""
        if self._client is None:
            self.__init__()
        return self._client
    
    def get_client(self, timeout: Optional[float] = None) -> httpx.AsyncClient:
        """
        HTTP 클라이언트 반환
        
        Args:
            timeout: 특정 타임아웃이 필요한 경우 (기본값 사용 시 None)
        
        Returns:
            httpx.AsyncClient: 재사용 가능한 클라이언트
        """
        if timeout is None or timeout == self._default_timeout:
            return self.client
        
        # 다른 타임아웃이 필요한 경우 새 클라이언트 생성
        # (일반적으로는 기본 클라이언트 사용 권장)
        return httpx.AsyncClient(timeout=timeout)
    
    async def close(self):
        """클라이언트 종료 (애플리케이션 종료 시 호출)"""
        if self._client is not None:
            await self._client.aclose()
            self._client = None


# 전역 HTTP 클라이언트 매니저 인스턴스
_http_client_manager: Optional[HTTPClientManager] = None


def get_http_client(timeout: Optional[float] = None) -> httpx.AsyncClient:
    """
    재사용 가능한 HTTP 클라이언트 반환
    
    사용 예시:
        # 기본 타임아웃 사용 (300초)
        client = get_http_client()
        response = await client.post(url, json=data)
        
        # 특정 타임아웃 사용
        client = get_http_client(timeout=180.0)
        response = await client.post(url, json=data)
    
    Args:
        timeout: HTTP 요청 타임아웃 (초). None이면 기본값(300초) 사용
    
    Returns:
        httpx.AsyncClient: 재사용 가능한 HTTP 클라이언트
    """
    global _http_client_manager
    if _http_client_manager is None:
        _http_client_manager = HTTPClientManager()
    return _http_client_manager.get_client(timeout=timeout)


async def close_http_client():
    """HTTP 클라이언트 종료 (애플리케이션 종료 시 호출)"""
    global _http_client_manager
    if _http_client_manager is not None:
        await _http_client_manager.close()
        _http_client_manager = None

