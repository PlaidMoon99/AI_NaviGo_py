import json
from services.google_places import GooglePlacesClient
from utils.logger import setup_logger
from utils.settings import settings
import urllib.parse

logger = setup_logger("HotelFinder")

class HotelFinder:
    def __init__(self):
        """🚀 Google Places API 클라이언트 초기화"""
        self.google_api = GooglePlacesClient()

    async def get_hotels(self, region, district=None, min_rating=4.0, max_results=5):
        """
        Google Places API에서 숙소 정보 검색 (평점 높은 숙소 우선 제공)
        - 최소 평점(min_rating) 이상의 숙소만 반환
        - 최대 max_results 개의 숙소만 반환
        """
        search_query = f"{district or region} 숙소"
        logger.info(f"🔍 숙소 검색: {search_query}")

        hotels = await self.google_api.search_places("lodging", search_query)

        refined_hotels = []
        for hotel in hotels:
            rating = hotel.get("rating", 0)
            if rating < min_rating:  # 평점 필터 적용
                continue

            # 숙소 정보 구성
            hotel_info = {
                "name": hotel.get("name", "N/A"),
                "address": hotel.get("formatted_address", "주소 정보 없음"),
                "rating": rating,
                "reviews": hotel.get("user_ratings_total", 0),
                "price_level": hotel.get("price_level", "가격 정보 없음"),
                "website": hotel.get("website", "웹사이트 없음"),
                "phone": hotel.get("international_phone_number", "연락처 없음"),
                "location": hotel.get("geometry", {}).get("location", {}),
                "type": self._classify_hotel_type(hotel.get("name", "").lower())  # 숙소 유형 분류
            }

            # place_id를 사용하여 이미지 정보 가져오기
            place_id = hotel.get("place_id")
            if place_id:
                images = await self.get_place_images(place_id)
                hotel_info["images"] = images

            refined_hotels.append(hotel_info)

        # ⭐ 평점 높은 순으로 정렬 후 상위 max_results 개만 반환
        refined_hotels = sorted(refined_hotels, key=lambda x: (x["rating"] or 0, x["reviews"] or 0), reverse=True)[:max_results]

        logger.info(f"✅ 숙소 검색 완료: {len(refined_hotels)}개 반환")
        return refined_hotels

    def _classify_hotel_type(self, name):
        """
        ✅ 숙소 유형 분류 (호텔, 한옥스테이, 게스트하우스 등)
        """
        name = name.lower()
        if "호텔" in name or "hotel" in name:
            return "호텔"
        elif "리조트" in name or "resort" in name:
            return "리조트"
        elif "한옥" in name or "hanok" in name:
            return "한옥스테이"
        elif "게스트하우스" in name or "guesthouse" in name:
            return "게스트하우스"
        elif "모텔" in name or "motel" in name:
            return "모텔"
        else:
            return "기타 숙소"

    async def get_place_images(self, place_id):
        """Google Places API에서 숙소 사진을 가져옵니다."""
        try:
            # 해당 place_id로 사진 정보 가져오기
            photos = await self.google_api.get_place_images(place_id)
            # photos가 문자열일 경우 JSON으로 파싱
            if isinstance(photos, str):
                try:
                    photos = json.loads(photos)
                    logger.info(f"✅ 사진 데이터 문자열 파싱 성공: {place_id}")
                except json.JSONDecodeError as e:
                    logger.error(f"🚨 사진 데이터 파싱 오류: {e}, place_id={place_id}")
                    return []  # 파싱 실패 시 빈 리스트 반환
            # 사진을 리스트로 처리 (리스트가 아니면 빈 리스트로 변환)
            if not isinstance(photos, list):
                logger.error(f"🚨 사진 데이터 형식이 리스트가 아님: {photos}, place_id={place_id}")
                return []

            # 최대 3개의 사진 URL 추출 및 유효성 검증
            image_urls = []
            for photo in photos[:10]:
                if isinstance(photo, str) and self._is_valid_url(photo):
                    image_urls.append(photo)
                elif isinstance(photo, dict) and photo.get("photo_reference"):
                    url = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photoreference={photo['photo_reference']}&key={settings.GOOGLE_PLACES_API_KEY}"
                    if self._is_valid_url(url):
                        image_urls.append(url)
                    else:
                        logger.warning(f"⚠️ 유효하지 않은 사진 URL: {url}, place_id={place_id}")
                else:
                    logger.warning(f"⚠️ 유효하지 않은 사진 데이터: {photo}, place_id={place_id}")

            logger.info(f"✅ 사진 URL 가져오기 성공: {image_urls}, place_id={place_id}")
            return image_urls
        except Exception as e:
            logger.error(f"🚨 사진 가져오기 오류: {e}, place_id={place_id}")
            return []  # 사진이 없거나 오류 발생 시 빈 리스트 반환

    def _is_valid_url(self, url):
        """
        ✅ URL이 유효한지 확인 (기본적인 형식 검사)
        """
        try:
            result = urllib.parse.urlparse(url)
            return all([result.scheme, result.netloc]) and ".googleapis.com" in result.netloc
        except Exception as e:
            logger.warning(f"⚠️ URL 유효성 검사 오류: {e}, url={url}")
            return False