from typing import Dict, List, Any
from datetime import date, datetime, timedelta
import json

class TravelDataCollector:
    def __init__(self, place_helper, hotels_helper, gemini_helper):
        self.place_helper = place_helper
        self.hotels_helper = hotels_helper
        self.gemini_helper = gemini_helper

    async def collect_travel_data(
        self,
        destination: Dict[str, Any],  # name, location{lat, lng}
        start_date: date,
        end_date: date,
        budget: int,
        themes: List[str],
        travelers: Dict[str, Any]  # count, type
    ) -> Dict[str, Any]:
        """여행 계획 생성에 필요한 모든 데이터를 수집"""
        
        # 1. 기본 여행 정보
        travel_data = {
            "destination": destination["name"],
            "duration": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "total_days": (end_date - start_date).days + 1
            },
            "budget": budget,
            "themes": themes,
            "travelers": travelers,
            "locations": {}
        }

        # 2. 호텔 정보 수집
        hotels = await self.hotels_helper.search_hotels(
            location=destination["location"],
            radius=30000  # 30km 반경
        )
        
        if hotels:
            travel_data["hotels"] = [{
                "name": hotel.name,
                "location": {
                    "lat": hotel.location.lat,
                    "lng": hotel.location.lng
                },
                "rating": hotel.rating,
                "price_level": hotel.price_level,
                "address": hotel.address,
                "reviews": hotel.reviews[:3] if hotel.reviews else [],
                "photos": hotel.photos[:3] if hotel.photos else [],
                "opening_hours": hotel.opening_hours
            } for hotel in hotels]
            
            # 위치 데이터 저장
            for hotel in hotels:
                travel_data["locations"][hotel.name] = {
                    "type": "hotel",
                    "lat": hotel.location.lat,
                    "lng": hotel.location.lng
                }

        # 3. 관광지 정보 수집 (음식점 제외)
        tourist_themes = [theme for theme in themes if theme != "음식/맛집"]
        if tourist_themes:
            attractions = await self.place_helper.get_nearby_places(
                location=destination["location"],
                selected_themes=tourist_themes
            )
            
            if attractions:
                travel_data["attractions"] = []
                for place in attractions:
                    # 상세 정보 가져오기
                    details = await self.place_helper.get_place_details(place["place_id"])
                    if not details:
                        continue
                        
                    attraction_data = {
                        "name": place["name"],
                        "location": {
                            "lat": place["location"]["lat"],
                            "lng": place["location"]["lng"]
                        },
                        "rating": place.get("rating", 0),
                        "types": place.get("types", []),
                        "price_level": place.get("price_level", 1),
                        "reviews": details.reviews if details.reviews else [],
                        "photos": details.photos[:3] if details.photos else [],
                        "opening_hours": details.opening_hours if details.opening_hours else [],
                        "estimated_duration": self._estimate_visit_duration(place["types"]),
                        "recommended_time": self._get_recommended_visit_time(
                            place["types"],
                            details.opening_hours if details.opening_hours else []
                        )
                    }
                    
                    travel_data["attractions"].append(attraction_data)
                    travel_data["locations"][place["name"]] = {
                        "type": "attraction",
                        "lat": place["location"]["lat"],
                        "lng": place["location"]["lng"]
                    }

        # 4. 음식점 정보 수집
        restaurants = await self.place_helper.get_nearby_places(
            location=destination["location"],
            selected_themes=["음식/맛집"]
        )
        
        if restaurants:
            travel_data["restaurants"] = []
            for place in restaurants:
                details = await self.place_helper.get_place_details(place["place_id"])
                if not details:
                    continue
                    
                restaurant_data = {
                    "name": place["name"],
                    "location": {
                        "lat": place["location"]["lat"],
                        "lng": place["location"]["lng"]
                    },
                    "rating": place.get("rating", 0),
                    "price_level": place.get("price_level", 1),
                    "cuisine_type": next((t for t in place.get("types", []) if t not in ["restaurant", "food", "point_of_interest", "establishment"]), "일반 음식점"),
                    "reviews": details.reviews if details.reviews else [],
                    "photos": details.photos[:3] if details.photos else [],
                    "opening_hours": details.opening_hours if details.opening_hours else [],
                    "recommended_time": self._get_restaurant_time()
                }
                
                travel_data["restaurants"].append(restaurant_data)
                travel_data["locations"][place["name"]] = {
                    "type": "restaurant",
                    "lat": place["location"]["lat"],
                    "lng": place["location"]["lng"]
                }

        return travel_data

    def _estimate_visit_duration(self, place_types: List[str]) -> int:
        """장소 유형별 예상 방문 시간 (분 단위) 추정"""
        duration_estimates = {
            "museum": 120,
            "art_gallery": 90,
            "park": 60,
            "tourist_attraction": 60,
            "church": 45,
            "historic_site": 60
        }
        
        # 해당하는 타입 중 가장 긴 시간을 선택
        max_duration = 60  # 기본값
        for place_type in place_types:
            if place_type in duration_estimates:
                max_duration = max(max_duration, duration_estimates[place_type])
        
        return max_duration

    def _get_recommended_visit_time(
        self,
        place_types: List[str],
        opening_hours: List[str]
    ) -> Dict[str, str]:
        """장소별 추천 방문 시간대 결정"""
        
        # 기본 추천 시간대
        recommendations = {
            "museum": {"start": "10:00", "end": "16:00"},
            "art_gallery": {"start": "11:00", "end": "15:00"},
            "park": {"start": "09:00", "end": "17:00"},
            "tourist_attraction": {"start": "10:00", "end": "16:00"}
        }

        # 장소 타입에 따른 기본 추천 시간 선택
        for place_type in place_types:
            if place_type in recommendations:
                return recommendations[place_type]
        
        # 기본값
        return {"start": "10:00", "end": "17:00"}

    def _get_restaurant_time(self) -> Dict[str, Dict[str, str]]:
        """음식점 추천 시간대"""
        return {
            "lunch": {"start": "12:00", "end": "14:00"},
            "dinner": {"start": "18:00", "end": "20:00"}
        }