from utils.service_code_loader import load_service_code_mapping
from utils.location_mapper import get_area_code, get_sigungu_code, SIGUNGU_CODE_MAP
from services.tour_api import TourAPIService
from services.naver_search import NaverSearchClient
from services.google_places import GooglePlacesClient
from services.kakao_map import KakaoMapClient
from services.gemini_service import GeminiService
from services.hotel_finder import HotelFinder
from services.restaurant_finder import RestaurantFinder
from utils.logger import setup_logger
from utils.cache import Cache
import asyncio
import re

logger = setup_logger("TravelPlanner")
cache = Cache()

def clean_text(text):
    """✅ HTML 태그, 괄호, 연도, 월/일/예정 관련 정보 제거. ✅ 도로명 주소(길 포함)는 유지."""
    if not text:
        return ""

    text = re.sub(r"<[^>]*>", "", text)
    text = re.sub(r"\([^)]*\)", "", text)
    text = re.sub(r"\b\d{4}년\b", "", text)
    text = re.sub(r"\b\d{1,2}월 예정\b", "", text)
    text = re.sub(r"\b\d{1,2}월\b", "", text)
    text = re.sub(r"\b\d{1,2}일\b", "", text)
    text = re.sub(r"&[a-zA-Z]+;", "", text)
    text = re.sub(r"[^가-힣a-zA-Z0-9\s길로번]", "", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text

class TravelPlanner:
    def __init__(self):
        """🚀 API 서비스 초기화"""
        self.service_code_mapping = load_service_code_mapping()
        self.tour_api = TourAPIService()
        self.google_api = GooglePlacesClient()
        self.kakao_api = KakaoMapClient()
        self.naver_api = NaverSearchClient()
        self.gemini_ai = GeminiService()
        self.hotel_finder = HotelFinder()
        self.restaurant_finder = RestaurantFinder()

    async def create_plan(self, request):
        """✅ AI 기반 여행 일정 생성 + 숙소 & 맛집 추천 추가"""
        region = request["region"]
        district = request.get("district", None)

        area_code = get_area_code(region)
        if area_code is None:
            logger.error(f"🚨 유효하지 않은 지역: {region}")
            return {"status": "error", "message": f"지역 '{region}'을(를) 찾을 수 없습니다."}
        
        if district and area_code in SIGUNGU_CODE_MAP:
            sigungu_code = get_sigungu_code(region, district)
            if sigungu_code is None:
                logger.warning(f"⚠️ 유효하지 않은 시군구: {district} (region={region})")
        else:
            sigungu_code = None

        logger.info(f"🔍 지역 코드 사용: areaCode={area_code}, sigunguCode={sigungu_code}")

        request["companion_type"] = request.get("companion_type", "개별 여행자")

        selected_content_ids = set()
        themes_without_content_id = []

        for theme in request["themes"]:
            if theme in self.service_code_mapping:
                selected_content_ids.update(self.service_code_mapping[theme])
            else:
                themes_without_content_id.append(theme)
                
        logger.info(f"🎯 선택된 contentTypeIds: {selected_content_ids}")
        logger.info(f"🚨 contentTypeId 없음 → 추가 검색 필요: {themes_without_content_id}")

        places = []
        if selected_content_ids:
            places = await self.tour_api.get_places(area_code=area_code, sigungu_code=sigungu_code, content_type_ids=list(selected_content_ids))

        additional_places = []
        if themes_without_content_id:
            search_tasks = [
                self.google_api.search_places(theme, district or region) for theme in themes_without_content_id
            ] + [
                self.naver_api.search_places(theme, district or region) for theme in themes_without_content_id
            ]
            additional_results = await asyncio.gather(*search_tasks, return_exceptions=True)
            for result in additional_results:
                if isinstance(result, Exception):
                    logger.error(f"🚨 추가 장소 검색 실패: {result}")
                else:
                    additional_places.extend(result)

        all_places = places + additional_places

        # 장소 데이터 정규화
        normalized_places = []
        for place in all_places:
            if "mapx" not in place or "mapy" not in place or not place["mapx"] or not place["mapy"]:
                coords = await self.kakao_api.get_coordinates(place.get("name", "Unknown"), region)
                if coords["mapx"] is None or coords["mapy"] is None:
                    logger.warning(f"🚨 최종적으로 좌표를 찾을 수 없음: {place.get('name', 'Unknown')}")
                    continue
                place["mapx"] = coords["mapx"]
                place["mapy"] = coords["mapy"]
            if "name" not in place:
                place["name"] = place.get("title", "Unnamed Place")
            normalized_places.append(place)

        if not normalized_places:
            return {"status": "error", "message": "여행할 장소를 찾을 수 없습니다."}

        optimized_route = await self._optimize_travel_path(normalized_places)

        hotels = await self.hotel_finder.get_hotels(region, district)
        restaurants = await self.restaurant_finder.get_restaurants(region, district)

        if not isinstance(hotels, list):
            logger.error(f"🚨 잘못된 숙소 데이터 형식: {type(hotels)} - {hotels}")
            hotels = [{"name": "숙소 정보 없음", "address": "N/A"}]

        if not isinstance(restaurants, list):
            logger.error(f"🚨 잘못된 음식점 데이터 형식: {type(restaurants)} - {restaurants}")
            restaurants = [{"name": "음식점 정보 없음", "address": "N/A"}]

        request["places"] = optimized_route
        request["hotels"] = hotels
        request["restaurants"] = restaurants
        travel_plan = await self.gemini_ai.generate_itinerary(request)

        if "travel_plan" not in travel_plan:
            return {"status": "error", "message": "AI 응답을 JSON으로 변환할 수 없습니다.", "raw_response": travel_plan}

        return {"status": "success", "travel_plan": travel_plan["travel_plan"]}

    async def _optimize_travel_path(self, places):
        """✅ KakaoMap을 사용하여 이동 경로 최적화 (Greedy TSP 적용)"""
        if len(places) <= 1:
            return places

        logger.info("🚀 KakaoMap을 사용한 이동 경로 최적화 시작...")

        valid_places = [place for place in places if place.get("mapx") and place.get("mapy")]
        if len(valid_places) < 2:
            logger.warning("⚠️ KakaoMap 최적화 불가능 → 좌표 정보 부족")
            return valid_places

        travel_times = {}
        tasks = []
        for i, place1 in enumerate(valid_places):
            for j, place2 in enumerate(valid_places):
                if i != j and (j, i) not in travel_times:
                    tasks.append(self._get_travel_time_with_timeout(place1, place2))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        task_idx = 0
        for i in range(len(valid_places)):
            for j in range(len(valid_places)):
                if i != j and (j, i) not in travel_times:
                    result = results[task_idx]
                    if isinstance(result, Exception):
                        travel_times[(i, j)] = 99999
                        logger.error(f"🚨 이동 시간 계산 실패: {valid_places[i]['name']} -> {valid_places[j]['name']} | 오류: {result}")
                    else:
                        travel_times[(i, j)] = result
                    task_idx += 1

        # 실패한 경우 평균 이동 시간으로 대체
        valid_times = [t for t in travel_times.values() if t != 99999]
        avg_travel_time = sum(valid_times) / max(1, len(valid_times)) if valid_times else 99999
        for (i, j) in travel_times:
            if travel_times[(i, j)] == 99999:
                travel_times[(i, j)] = avg_travel_time

        optimized_route = []
        unvisited = set(range(len(valid_places)))
        current = 0
        optimized_route.append(valid_places[current])
        unvisited.remove(current)

        while unvisited:
            next_place = min(unvisited, key=lambda x: travel_times.get((current, x), float('inf')))
            optimized_route.append(valid_places[next_place])
            unvisited.remove(next_place)
            current = next_place

        logger.info(f"✅ 최적화된 경로: {[place.get('name', 'Unnamed') for place in optimized_route]}")
        return optimized_route

    async def _get_travel_time_with_timeout(self, place1, place2):
        """✅ KakaoMap API 호출 시 타임아웃 적용 (5초) 및 좌표 기반 이동 시간 계산"""
        try:
            # place1, place2는 이미 'mapx', 'mapy'를 포함한 딕셔너리 형태
            origin = {
                "name": place1.get("name", "Unknown"),
                "mapx": place1.get("mapx"),
                "mapy": place1.get("mapy")
            }
            destination = {
                "name": place2.get("name", "Unknown"),
                "mapx": place2.get("mapx"),
                "mapy": place2.get("mapy")
            }
            
            logger.debug(f"🔍 KakaoMap 요청: 출발={origin['name']} ({origin['mapx']},{origin['mapy']}), 도착={destination['name']} ({destination['mapx']},{destination['mapy']})")
            travel_time = await asyncio.wait_for(self.kakao_api.get_travel_time(origin, destination), timeout=5)
            if travel_time is None:
                logger.warning(f"⚠️ 이동 시간 계산 실패 (데이터 없음): {origin['name']} -> {destination['name']}")
                return 99999
            return travel_time
        except asyncio.TimeoutError:
            logger.error(f"🚨 KakaoMap API 응답 지연: {origin['name']} -> {destination['name']}")
            return 99999
        except Exception as e:
            logger.error(f"🚨 KakaoMap API 호출 실패: {origin['name']} -> {destination['name']} | 오류: {str(e)}")
            return 99999
