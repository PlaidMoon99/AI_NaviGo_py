import aiohttp
import json
from utils.settings import settings
from utils.logger import setup_logger
from utils.cache import Cache

logger = setup_logger("GooglePlacesService")
cache = Cache()

class GooglePlacesClient:
    def __init__(self):
        self.api_key = settings.GOOGLE_PLACES_API_KEY
        self.base_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        self.place_details_url = "https://maps.googleapis.com/maps/api/place/details/json"  # 장소 상세 정보 URL

    async def search_places(self, query, region):
        """
        ✅ Google Places API를 사용하여 장소 검색
        - 요청 제한(초당 50개) 고려하여 캐싱 적용
        """
        cache_key = f"google_places:{query}:{region}"
        cached_data = await cache.get(cache_key)
        if cached_data:
            logger.info(f"✅ Redis 캐시 사용: {query}, {region}")
            return cached_data

        params = {
            "query": f"{query} in {region}",
            "key": self.api_key,
            "language": "ko"
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(self.base_url, params=params) as response:
                if response.status != 200:
                    logger.error(f"🚨 Google Places API 오류: {response.status}")
                    return []
                
                data = await response.json()
                results = data.get("results", [])

                await cache.set(cache_key, results, ttl=86400)  # 1일 캐싱
                return results

    async def get_coordinates(self, query, region):
        """
        ✅ 장소 좌표 반환 (Google → Naver 순으로 조회)
        """
        results = await self.search_places(query, region)
        if results and len(results) > 0:
            place = results[0]
            location = place.get("geometry", {}).get("location", {})

            # 🔥 mapx, mapy 값이 존재하는지 검증 후 반환
            if location.get("lat") is not None and location.get("lng") is not None:
                return {"mapx": location["lng"], "mapy": location["lat"]}

        logger.warning(f"🚨 Google Places API에서 좌표를 찾을 수 없음: {query}")
        return {"mapx": None, "mapy": None}

    async def get_place_images(self, place_id):
        """
        ✅ place_id로 Google Places API에서 사진 정보 가져오기
        """
        cache_key = f"google_place_images:{place_id}"
        cached_images = await cache.get(cache_key)
        
        # 캐시 데이터가 문자열이면 JSON으로 파싱 시도
        if isinstance(cached_images, str):
            try:
                cached_images = json.loads(cached_images)
                logger.info(f"✅ Redis 캐시 (문자열 파싱 후) 사용: 사진 정보 {place_id}")
            except json.JSONDecodeError:
                logger.error(f"🚨 캐시 데이터 파싱 실패: {cached_images}")
                cached_images = None

        if cached_images:
            return cached_images

        try:
            params = {
                "place_id": place_id,
                "key": self.api_key
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(self.place_details_url, params=params) as response:
                    if response.status != 200:
                        logger.error(f"🚨 Google Places API 오류: {response.status}")
                        return []

                    data = await response.json()
                    photos = data.get("result", {}).get("photos", [])

                    # photos가 리스트가 아닐 경우 처리
                    if not isinstance(photos, list):
                        logger.error(f"사진 정보가 리스트가 아닙니다: {photos}")
                        return []

                    # 최대 3개의 사진 가져오기
                    image_urls = [photo.get("photo_reference") for photo in photos[:3] if photo.get("photo_reference")]

                    # 사진 URL 생성
                    photo_urls = []
                    for reference in image_urls:
                        if reference:
                            url = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photoreference={reference}&key={self.api_key}"
                            photo_urls.append(url)

                    # 캐시 저장 (JSON 직렬화)
                    if photo_urls:
                        await cache.set(cache_key, json.dumps(photo_urls), ttl=86400)
                        return photo_urls
                    return []

        except aiohttp.ClientError as e:
            logger.error(f"네트워크 오류: {e}")
            return []
        except Exception as e:
            logger.error(f"사진 정보 가져오기 오류: {e}")
            return []