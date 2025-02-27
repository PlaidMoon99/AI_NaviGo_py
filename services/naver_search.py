import aiohttp
from utils.settings import settings
from utils.logger import setup_logger
from utils.cache import Cache

logger = setup_logger("NaverSearchService")
cache = Cache()

class NaverSearchClient:
    def __init__(self):
        self.client_id = settings.NAVER_CLIENT_ID
        self.client_secret = settings.NAVER_CLIENT_SECRET
        self.base_url = "https://openapi.naver.com/v1/search/local.json"
        self.headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret
        }

    async def search_places(self, query, region):
        """
        ✅ Naver API를 사용하여 특정 지역에서 장소 검색
        - Redis 캐싱을 활용하여 중복 호출 방지 (24시간 캐싱)
        - 초당 10개 요청 제한 고려하여 안전한 API 호출
        """
        cache_key = f"naver_places:{query}:{region}"
        cached_data = await cache.get(cache_key)
        if cached_data:
            logger.info(f"✅ Redis 캐시 사용: {query}, {region}")
            return cached_data

        params = {"query": f"{region} {query}", "display": "5", "sort": "random"}
        async with aiohttp.ClientSession() as session:
            async with session.get(self.base_url, headers=self.headers, params=params) as response:
                if response.status != 200:
                    logger.error(f"🚨 Naver API 오류: {response.status}")
                    return []
                
                data = await response.json()
                results = data.get("items", [])

                # 🚀 24시간 캐싱 적용
                await cache.set(cache_key, results, ttl=86400)
                
                # 장소에 대한 이미지 정보 추가
                for result in results:
                    result["image"] = result.get("thumbnail", "이미지 없음")  # 이미지가 있으면 추가, 없으면 기본값 설정
                
                return results

    async def get_coordinates(self, query, region):
        """
        ✅ Naver API를 사용하여 특정 장소의 좌표(mapx, mapy) 조회
        """
        results = await self.search_places(query, region)
        if results and len(results) > 0:
            return {"mapx": results[0]["mapx"], "mapy": results[0]["mapy"]}
        
        logger.warning(f"🚨 Naver API에서 좌표를 찾을 수 없음: {query}")
        return {"mapx": None, "mapy": None}

    async def get_reviews(self, place_name):
        """
        ✅ Naver 블로그 검색 API를 사용하여 장소 리뷰 조회
        - 블로그 데이터를 기반으로 사용자 리뷰 보강
        """
        cache_key = f"naver_reviews:{place_name}"
        cached_data = await cache.get(cache_key)
        if cached_data:
            logger.info(f"✅ Redis 캐시 사용: {place_name} 리뷰")
            return cached_data

        params = {"query": f"{place_name} 리뷰", "display": "5", "sort": "date"}
        async with aiohttp.ClientSession() as session:
            async with session.get("https://openapi.naver.com/v1/search/blog.json", headers=self.headers, params=params) as response:
                if response.status != 200:
                    logger.error(f"🚨 Naver 블로그 API 오류: {response.status}")
                    return []

                data = await response.json()
                reviews = data.get("items", [])

                # 🚀 24시간 캐싱 적용
                await cache.set(cache_key, reviews, ttl=86400)
                return reviews
