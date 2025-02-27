import redis.asyncio as aioredis
import json
import os
from utils.settings import settings
from utils.logger import setup_logger
from typing import Any, Optional
import asyncio

logger = setup_logger("CacheService")

class Cache:
    def __init__(self):
        """Redis 캐싱 초기화"""
        self.redis_url = settings.REDIS_URL
        self.redis: Optional[aioredis.Redis] = None
        self._lock = asyncio.Lock()  # 동시 초기화 방지용 락
        self._initialized = False  # 초기화 상태 추적

    async def _initialize(self) -> bool:
        """
        Redis 연결 초기화
        :return: 초기화 성공 여부
        """
        async with self._lock:  # 동시 접근 방지
            if self._initialized:
                return True

            try:
                self.redis = await aioredis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    max_connections=10  # 최대 연결 수 제한
                )
                # 연결 상태 확인
                await self.redis.ping()
                # 간단한 테스트 키로 연결 확인
                test_key = "test:connection"
                await self.redis.set(test_key, "test", ex=10)
                if await self.redis.get(test_key) != "test":
                    logger.error("🚨 Redis 연결 실패: 저장/조회 불일치")
                    await self.redis.close()
                    self.redis = None
                    return False
                logger.info("✅ Redis 연결 성공")
                self._initialized = True
                return True
            except aioredis.RedisError as e:
                logger.error(f"🚨 Redis 초기화 실패: {e}")
                self.redis = None
                return False

    async def ensure_connection(self) -> None:
        """Redis 연결 보장 (필요 시 초기화)"""
        if not self.redis or not self._initialized:
            await self._initialize()

    async def close(self) -> None:
        """Redis 연결 종료"""
        async with self._lock:
            if self.redis and self._initialized:
                try:
                    await self.redis.close()
                    logger.info("✅ Redis 연결 종료")
                except aioredis.RedisError as e:
                    logger.error(f"🚨 Redis 연결 종료 실패: {e}")
                finally:
                    self.redis = None
                    self._initialized = False

    async def get(self, key: str) -> Optional[Any]:
        """
        Redis에서 데이터 가져오기
        :param key: 캐시 키
        :return: 캐시된 데이터 또는 None
        """
        await self.ensure_connection()
        if not self.redis:
            logger.warning("⚠️ Redis 연결 없음")
            return None

        try:
            data = await self.redis.get(key)
            if data is None:
                logger.debug(f"ℹ️ 캐시 미스: {key}")
                return None
            return json.loads(data)
        except json.JSONDecodeError as e:
            logger.error(f"🚨 JSON 파싱 오류: {key}, 오류: {e}")
            return None
        except aioredis.RedisError as e:
            logger.error(f"🚨 Redis get 실패: {key}, 오류: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """
        Redis에 데이터 저장
        :param key: 캐시 키
        :param value: 저장할 값
        :param ttl: 만료 시간 (초, 기본값 3600)
        :return: 저장 성공 여부
        """
        await self.ensure_connection()
        if not self.redis:
            logger.warning("⚠️ Redis 연결 없음")
            return False

        try:
            serialized_value = json.dumps(value)
            await self.redis.setex(key, ttl, serialized_value)
            # 저장 확인
            if await self.redis.get(key) is None:
                logger.error(f"🚨 캐시 저장 실패: {key} 저장 후 조회 불가")
                return False
            logger.info(f"✅ 캐시 저장 성공: {key}, TTL={ttl}")
            return True
        except json.JSONEncodeError as e:
            logger.error(f"🚨 JSON 직렬화 오류: {key}, 오류: {e}")
            return False
        except aioredis.RedisError as e:
            logger.error(f"🚨 Redis set 실패: {key}, 오류: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """
        Redis에서 특정 키 삭제
        :param key: 삭제할 캐시 키
        :return: 삭제 성공 여부
        """
        await self.ensure_connection()
        if not self.redis:
            logger.warning("⚠️ Redis 연결 없음")
            return False

        try:
            result = await self.redis.delete(key)
            if result > 0:
                logger.info(f"✅ 캐시 삭제 성공: {key}")
                return True
            logger.debug(f"ℹ️ 삭제할 캐시 없음: {key}")
            return False
        except aioredis.RedisError as e:
            logger.error(f"🚨 Redis delete 실패: {key}, 오류: {e}")
            return False

# 사용 예시
async def main():
    cache_service = Cache()
    await cache_service.ensure_connection()

    # 데이터 저장
    await cache_service.set("example_key", {"data": "test"}, ttl=60)
    
    # 데이터 조회
    value = await cache_service.get("example_key")
    print(f"캐시 값: {value}")
    
    # 데이터 삭제
    await cache_service.delete("example_key")
    
    # 연결 종료
    await cache_service.close()

if __name__ == "__main__":
    asyncio.run(main())