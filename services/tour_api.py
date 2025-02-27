import aiohttp
import json
from utils.settings import settings
from utils.logger import setup_logger
from utils.cache import Cache
from utils.service_code_loader import THEME_CATEGORIES, CAT3_THEME_MAPPING
from loguru import logger

logger = setup_logger("TourAPIService")
cache = Cache()

class TourAPIService:
    def __init__(self):
        self.api_key = settings.TOUR_API_KEY
        self.base_url = f"{settings.TOUR_API_BASE_URL}/areaBasedList1"

    async def get_places(self, area_code: str, sigungu_code: str, themes: list[str] = None):
        """
        ✅ TourAPI를 사용하여 관광지 정보 조회
        - 요청 제한(초당 1개) 고려하여 캐싱 적용
        - `themes`에 해당하는 모든 `cat3` 코드들을 조회
        """
        try:
            # 테마에 따라 관련된 cat3 코드들을 모두 가져오기
            cat3_codes = self.get_cat3_codes_for_themes(themes)
            
            cache_key = f"tour_api:{area_code}:{sigungu_code}:{cat3_codes}"
            cached_data = await cache.get(cache_key)
            if cached_data:
                logger.info(f"✅ Redis 캐시 사용: {area_code}, {sigungu_code}, {cat3_codes}")
                return cached_data

            params = {
                'serviceKey': self.api_key,
                'numOfRows': '100',
                'pageNo': '1',
                'MobileOS': 'ETC',
                'MobileApp': 'Navigo',
                'arrange': 'P',
                '_type': 'json',
            }
            
            # None이 아닌 값만 params에 추가
            if area_code:
                params['areaCode'] = area_code
            if sigungu_code:
                params['sigunguCode'] = sigungu_code
            if cat3_codes:  # cat3_codes가 있으면 추가
                params['cat3Code'] = ','.join(map(str, cat3_codes))

            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url, params=params) as response:
                    logger.debug(f"API 요청 URL: {response.url}")
                    if response.status != 200:
                        logger.error(f"🚨 TourAPI 오류: {response.status}")
                        return []

                    data = await response.text()
                    logger.debug(f"API 응답: {data[:200]}...")  # 처음 200자만 로깅
                    try:
                        # 문자열을 JSON으로 파싱
                        data = json.loads(data)
                        results = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
                        logger.info(f"성공적으로 {len(results)}개의 장소를 가져왔습니다.")
                        await cache.set(cache_key, results, ttl=86400)  # 1일 캐싱
                        return results
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON 파싱 오류: {e}")
                        logger.error(f"받은 데이터: {data}")
                        return []
        except Exception as e:
            logger.error(f"API 요청 중 오류 발생: {e}")
            return []

    def get_cat3_codes_for_themes(self, themes: list[str]):
        """
        주어진 테마에 해당하는 모든 cat3 코드를 반환
        """
        cat3_codes = set()

        for theme in themes:
            if theme in THEME_CATEGORIES:
                # 해당 테마에 속하는 cat3 코드들을 추가
                for cat3_code, mapped_theme in CAT3_THEME_MAPPING.items():
                    if mapped_theme == theme:
                        cat3_codes.add(cat3_code)
            
        logger.debug(f"테마 '{themes}'에 해당하는 cat3 코드들: {cat3_codes}")
        return list(cat3_codes)
