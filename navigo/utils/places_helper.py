from typing import List, Dict, Optional, Union
import asyncio
import aiohttp
import time
from pydantic import BaseModel, Field
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import GOOGLE_CLOUD_API_KEY

# Place Type Mappings (이전과 동일)
THEME_TO_PLACE_TYPE = {
    "박물관": ["museum"],
    "미술관": ["art_gallery"],
    "문화/역사": ["historic_site", "archaeological_site"],
    "관광명소": ["tourist_attraction", "landmark", "city_hall", "courthouse", "embassy", "town_square"],
    "자연/아웃도어": ["park", "natural_feature", "campground", "beach", "rv_park", "picnic_ground", "waterfall", "pier", "marina"],
    "음식/맛집": ["restaurant", "cafe", "bar", "bakery", "meal_takeaway", "meal_delivery", "ice_cream_shop"],
    "쇼핑": ["shopping_mall", "department_store", "market", "jewelry_store", "shoe_store", "clothing_store", "book_store", "electronics_store", "convenience_store", "supermarket"],
    "휴양/힐링": ["spa", "beauty_salon", "amusement_park", "zoo", "hot_spring", "hair_care", "massage", "gym"]
}

# Pydantic 모델 정의 (이전과 동일)
class LocationModel(BaseModel):
    lat: float
    lng: float

class PlaceSuggestionModel(BaseModel):
    description: str
    place_id: str

class PlaceDetailsModel(BaseModel):
    name: str
    address: str
    location: LocationModel
    rating: Optional[float] = None
    opening_hours: Optional[List[str]] = None
    reviews: Optional[List[Dict[str, Union[str, float]]]] = None
    price_level: Optional[int] = None
    photos: Optional[List[str]] = None
    website: Optional[str] = None
    phone: Optional[str] = None

class PlacesHelper:
    def __init__(self, api_key: str = GOOGLE_CLOUD_API_KEY):
        self.api_key = api_key
        self.theme_to_place_type = THEME_TO_PLACE_TYPE

    async def calculate_city_radius(self, location: Dict[str, float]) -> int:
        """
        도시의 viewport 정보를 기반으로 적절한 검색 반경을 비동기로 계산
        """
        base_url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            "latlng": f"{location['lat']},{location['lng']}",
            "key": self.api_key
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(base_url, params=params) as response:
                    data = await response.json()
                    
                    if data.get("results"):
                        # 도시 정보를 찾기 위해 결과를 순회
                        for result in data["results"]:
                            if "locality" in result["types"]:
                                viewport = result["geometry"]["viewport"]
                                ne = viewport["northeast"]
                                sw = viewport["southwest"]
                                
                                # 위도/경도 차이를 km로 변환하여 대략적인 도시 크기 계산
                                lat_diff = abs(ne["lat"] - sw["lat"])
                                lng_diff = abs(ne["lng"] - sw["lng"])
                                
                                # 도시의 대각선 길이를 기준으로 반경 결정
                                city_size = (lat_diff ** 2 + lng_diff ** 2) ** 0.5
                                
                                if city_size > 0.5:  # 대도시 (예: 뉴욕, 도쿄)
                                    return 50000
                                elif city_size > 0.2:  # 중간 크기 도시
                                    return 30000
                                else:  # 작은 도시
                                    return 15000
        except Exception as e:
            print(f"Error calculating city radius: {str(e)}")
        
        return 30000  # 기본값으로 30km 반환

    async def get_place_suggestions(self, query: str) -> List[PlaceSuggestionModel]:
        """
        Google Places Autocomplete API를 비동기로 호출하여 장소 추천을 받아옵니다.
        """
        if not query:
            return []
        
        base_url = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
        params = {
            "input": query,
            "types": "(regions)",  # 도시로 제한
            "language": "ko",     # 한글 결과
            "key": self.api_key
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(base_url, params=params) as response:
                    data = await response.json()
                    suggestions = data.get("predictions", [])
                    
                    return [
                        PlaceSuggestionModel(
                            description=place["description"], 
                            place_id=place["place_id"]
                        ) 
                        for place in suggestions
                    ]
        except Exception as e:
            print(f"장소 검색 중 오류가 발생했습니다: {str(e)}")
            return []

    async def get_nearby_places(
        self, 
        location: Dict[str, float], 
        selected_themes: List[str]
    ) -> List[Dict]:
        """
        선택된 위치 주변의 관광지를 비동기로 검색합니다.
        """
        initial_radius = await self.calculate_city_radius(location)
        print(f"Initial search radius: {initial_radius}m")
        
        # 선택된 테마에 해당하는 place type들을 모두 가져옴
        place_types = []
        for theme in selected_themes:
            place_types.extend(self.theme_to_place_type.get(theme, []))
        
        if not place_types:
            print("No place types found for the selected themes.")
            return []

        all_places = []
        
        hotel_keywords = ["hotel", "resort", "motel", "inn", "bnb", "guesthouse", "hostel", "lodging"]
        
        async with aiohttp.ClientSession() as session:
            multiple_selection = len(place_types) > 1  # ✅ 복수 선택 여부 확인
            
            for place_type in place_types:
                next_page_token = None
                
                # ✅ 복수 선택이면 1페이지만, 단일 선택이면 3페이지까지 조회
                max_pages = 1 if multiple_selection else 3  

                for page in range(max_pages):
                    params = {
                        "location": f"{location['lat']},{location['lng']}",
                        "radius": initial_radius,
                        "type": place_type,
                        "language": "ko",
                        "key": self.api_key
                    }
                    
                    if next_page_token:
                        params["pagetoken"] = next_page_token
                    
                    try:
                        async with session.get(
                            "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
                            params=params
                        ) as response:
                            data = await response.json()
                            
                            if data.get("status") != "OK":
                                print(f"API call failed with status: {data.get('status')}")
                                break
                            
                            batch_results = data.get("results", [])
                            if not batch_results:
                                print("No results found for this page.")
                                break
                            
                            for place in batch_results:
                                place_name = place.get("name", "").lower()
                                place_types = place.get("types", [])

                                # ❌ 숙박업소(호텔) 필터링
                                if "lodging" in place_types:
                                    continue
                                if any(keyword in place_name for keyword in hotel_keywords):
                                    continue
                                
                                place_details = {
                                    "place_id": place["place_id"],
                                    "name": place["name"],
                                    "location": place["geometry"]["location"],
                                    "rating": place.get("rating", 0),
                                    "user_ratings_total": place.get("user_ratings_total", 0),
                                    "types": place["types"],
                                    "place_type": place_type
                                }
                                
                                if "photos" in place:
                                    place_details["photo_reference"] = place["photos"][0]["photo_reference"]
                                
                                if "price_level" in place:
                                    place_details["price_level"] = place["price_level"]
                                
                                all_places.append(place_details)

                    except Exception as e:
                        print(f"Error fetching places for type {place_type}: {str(e)}")
                        break

        
        # 중복 제거
        unique_places = {place["place_id"]: place for place in all_places}
        
        # 점수 계산 및 정렬
        def calculate_score(place):
            rating = place.get("rating", 0)
            reviews = place.get("user_ratings_total", 0)
            
            if reviews < 50 or rating < 3.5:
                return -1
            
            max_reviews = 5000
            review_weight = min(reviews / max_reviews, 1.0)
            rating_weight = rating / 5
            
            score = (review_weight * 0.6 + rating_weight * 0.4) * 100
            return round(score, 1)
        
        filtered_places = [place for place in unique_places.values() if calculate_score(place) != -1]
        sorted_places = sorted(filtered_places, key=calculate_score, reverse=True)
        
        return sorted_places[:40]  # 상위 40개만 반환

    async def get_place_details(self, place_id: str) -> Optional[PlaceDetailsModel]:
        """
        특정 장소의 상세 정보를 비동기로 가져옵니다.
        """
        base_url = "https://maps.googleapis.com/maps/api/place/details/json"
        params = {
            "place_id": place_id,
            "fields": "name,formatted_address,geometry,opening_hours,rating,reviews,price_level,photos,website,formatted_phone_number",
            "language": "ko",
            "key": self.api_key
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(base_url, params=params) as response:
                    data = await response.json()
                    result = data.get("result", {})
                    
                    return PlaceDetailsModel(
                        name=result.get("name"),
                        address=result.get("formatted_address"),
                        location=LocationModel(
                            lat=result.get("geometry", {}).get("location", {}).get("lat"),
                            lng=result.get("geometry", {}).get("location", {}).get("lng")
                        ),
                        rating=result.get("rating"),
                        opening_hours=result.get("opening_hours", {}).get("weekday_text", []),
                        reviews=[
                            {
                                "text": review.get("text"),
                                "rating": review.get("rating"),
                                "time": review.get("relative_time_description")
                            }
                            for review in result.get("reviews", [])
                            if len(review.get("text", "")) > 30  # 30자 이상 리뷰만 필터링
                            and review.get("rating", 0) >= 4     # 4점 이상 리뷰만 표시
                        ][:3],  # 상위 3개 리뷰만
                        price_level=result.get("price_level"),
                        photos=[photo.get("photo_reference") for photo in result.get("photos", [])[:5]],  # 최대 5장
                        website=result.get("website"),
                        phone=result.get("formatted_phone_number")
                    )
                    
        except Exception as e:
            print(f"Error fetching place details: {str(e)}")
            return None
    
    async def get_place_details_by_id(self, place_id: str) -> Dict:
        """
        Place ID를 기반으로 장소의 상세 정보(위도/경도 포함)를 가져옵니다.
        """
        base_url = "https://maps.googleapis.com/maps/api/place/details/json"
        params = {
            "place_id": place_id,
            "fields": "geometry",  # 위도/경도 정보만 필요
            "key": self.api_key
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(base_url, params=params) as response:
                    data = await response.json()
                    if data.get("status") == "OK":
                        location = data["result"]["geometry"]["location"]
                        return {
                            "lat": location["lat"],
                            "lng": location["lng"]
                        }
                    return None
        except Exception as e:
            print(f"Error fetching place details: {str(e)}")
            return None

    async def get_place_photo(self, photo_reference: str, max_width: int = 400) -> Optional[str]:
        """
        장소 사진의 URL을 비동기로 가져옵니다.
        """
        base_url = "https://maps.googleapis.com/maps/api/place/photo"
        params = {
            "photoreference": photo_reference,
            "maxwidth": max_width,
            "key": self.api_key
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(base_url, params=params, allow_redirects=False) as response:
                    if response.status == 302:  # Google은 리다이렉트로 실제 이미지 URL을 제공
                        return response.headers.get("Location")
        except Exception as e:
            print(f"Error fetching photo: {str(e)}")
        
        return None

# 전역 인스턴스 생성 (선택적)
places_helper = PlacesHelper()