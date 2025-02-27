import json
from services.google_places import GooglePlacesClient
from utils.logger import setup_logger
from utils.settings import settings

logger = setup_logger("RestaurantFinder")

class RestaurantFinder:
    def __init__(self):
        """🚀 Google Places API 클라이언트 초기화"""
        self.google_api = GooglePlacesClient()

    async def get_restaurants(self, region, district=None):
        """
        ✅ Google Places API에서 맛집 검색
        - `restaurant` 카테고리에서 평점이 높은 맛집 추천
        """
        # 지역과 시군구 정보를 결합하여 검색 쿼리 생성
        search_query = f"{district or region} 맛집"
        logger.info(f"🔍 맛집 검색: {search_query}")

        # district이 None이면 region만으로 검색, 그렇지 않으면 district과 region을 함께 사용
        restaurants = await self.google_api.search_places("restaurant", search_query)

        # 🔥 평점 높은 맛집 필터링 (평점 4.0 이상, 리뷰 수 50개 이상)
        refined_restaurants = []
        for restaurant in restaurants:
            rating = restaurant.get("rating", 0)
            review_count = restaurant.get("user_ratings_total", 0)

            if rating >= 4.0 and review_count >= 50:  # ⭐ 필터 조건 적용
                # 맛집 정보 구성
                restaurant_info = {
                    "name": restaurant.get("name", "N/A"),
                    "address": restaurant.get("formatted_address", "주소 정보 없음"),
                    "rating": rating,
                    "reviews": review_count,
                    "price_level": restaurant.get("price_level", "가격 정보 없음"),
                    "website": restaurant.get("website", "웹사이트 없음"),
                    "phone": restaurant.get("international_phone_number", "연락처 없음"),
                    "location": restaurant.get("geometry", {}).get("location", {}),
                }

                # place_id를 이용해 추가 정보(사진 등) 가져오기
                place_id = restaurant.get("place_id")
                if place_id:
                    # place_id를 사용해 해당 장소의 사진 가져오기
                    images = await self.get_place_images(place_id)
                    restaurant_info["images"] = images

                refined_restaurants.append(restaurant_info)

        return refined_restaurants

    async def get_place_images(self, place_id):
        """Google Places API에서 맛집 사진을 가져옵니다."""
        try:
            # 해당 place_id로 사진 정보 가져오기
            photos = await self.google_api.get_place_images(place_id)
            # photos가 문자열일 경우 JSON으로 파싱 (리스트로 반환된다고 가정)
            if isinstance(photos, str):
                try:
                    photos = json.loads(photos)
                except json.JSONDecodeError as e:
                    logger.error(f"사진 데이터 파싱 오류: {e}")
                    return []  # 파싱 실패 시 빈 리스트 반환
            # 사진을 리스트로 처리 (리스트가 아니면 빈 리스트로 변환)
            if not isinstance(photos, list):
                logger.error(f"사진 데이터 형식이 리스트가 아님: {photos}")
                return []

            # 최대 3개의 사진 URL 사용 (이미 URL로 변환된 리스트 처리)
            image_urls = photos[:10]  # 이미 URL 리스트로 반환된 상태이므로 그대로 사용
            logger.info(f"✅ 사진 URL 가져오기 성공: {image_urls}")
            return image_urls
        except Exception as e:
            logger.error(f"사진 가져오기 오류: {e}")
            return []  # 사진이 없거나 오류 발생 시 빈 리스트 반환