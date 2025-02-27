import aiohttp
from utils.settings import settings
from utils.logger import setup_logger
from utils.cache import Cache
from services.google_places import GooglePlacesClient
from services.naver_search import NaverSearchClient

logger = setup_logger("KakaoMapService")
cache = Cache()

class KakaoMapClient:
    def __init__(self):
        self.rest_api_key = settings.KAKAO_REST_API_KEY
        self.base_url = "https://dapi.kakao.com/v2/local/search/keyword.json"
        self.headers = {"Authorization": f"KakaoAK {self.rest_api_key}"}

        self.google_places = GooglePlacesClient()
        self.naver_search = NaverSearchClient()

    async def search_places(self, query, region):
        """
        ✅ Kakao Map API를 사용하여 장소 검색
        - 요청 제한 고려하여 Redis 캐싱 적용
        - 이미지 정보도 함께 반환
        """
        cache_key = f"kakao_places:{query}:{region}"
        cached_data = await cache.get(cache_key)
        if cached_data:
            logger.info(f"✅ Redis 캐시 사용: {query}, {region}")
            return cached_data

        params = {"query": f"{region} {query}"}
        async with aiohttp.ClientSession() as session:
            async with session.get(self.base_url, headers=self.headers, params=params) as response:
                if response.status != 200:
                    logger.error(f"🚨 Kakao Map API 오류: {response.status}")
                    return []

                data = await response.json()
                results = data.get("documents", [])

                # 🚀 24시간 캐싱 적용
                await cache.set(cache_key, results, ttl=86400)

                # 이미지 정보 추가 (Kakao API에서는 'thumbnail' 필드 사용)
                for result in results:
                    result["image"] = result.get("thumbnail", "이미지 없음")

                return results
            
    async def get_coordinates(self, query, region):
        """
        ✅ Kakao Map API에서 좌표 조회 (Kakao → Google → Naver 순서로 조회)
        """
        if not query or query.isspace():
            logger.error("🚨 비어 있거나 잘못된 장소 이름 → 좌표 조회 중단")
            return {"mapx": None, "mapy": None}

        kakao_coords = await self._get_kakao_coordinates(query)
        if kakao_coords["mapx"] and kakao_coords["mapy"]:
            return kakao_coords

        logger.warning(f"⚠️ Kakao에서 좌표를 찾을 수 없음 → Google API로 조회 시도: {query}")
        google_coords = await self.google_places.get_coordinates(query, region)
        if google_coords["mapx"] and google_coords["mapy"]:
            return google_coords

        logger.warning(f"⚠️ Google에서도 좌표를 찾을 수 없음 → Naver API로 조회 시도: {query}")
        naver_coords = await self.naver_search.get_coordinates(query, region)
        return naver_coords


    async def _get_kakao_coordinates(self, query):
        """
        ✅ Kakao API에서 장소 좌표 조회
        """
        cache_key = f"kakao_coords:{query}"
        cached_data = await cache.get(cache_key)
        if cached_data:
            return cached_data

        params = {"query": query}
        async with aiohttp.ClientSession() as session:
            async with session.get(self.base_url, headers=self.headers, params=params) as response:
                if response.status != 200:
                    logger.error(f"🚨 Kakao API 오류: {response.status}")
                    return {"mapx": None, "mapy": None}

                data = await response.json()
                if data.get("documents"):
                    place = data["documents"][0]
                    coords = {"mapx": float(place["x"]), "mapy": float(place["y"])}
                    await cache.set(cache_key, coords, ttl=86400)  # 1일 캐싱
                    return coords

        return {"mapx": None, "mapy": None}