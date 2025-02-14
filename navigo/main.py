from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import List, Dict, Any
from datetime import date
import json

# 기존 헬퍼 클래스들 import
from utils.places_helper import PlacesHelper
from utils.hotels_helper import HotelsHelper
from utils.travel_data_collector import TravelDataCollector
from utils.gemini_api_helper import GeminiAPIHelper
from config import GEMINI_API_KEY

app = FastAPI(title="Travel Planner API")

# 요청 모델 정의
class LocationModel(BaseModel):
    lat: float
    lng: float
    name: str

class TravelPlanRequestModel(BaseModel):
    destination: LocationModel
    start_date: date
    end_date: date
    budget: int
    themes: List[str]
    travelers: Dict[str, Any]

    class Config:
        arbitrary_types_allowed = True
        
app = FastAPI(title="Travel Planner API")

class TravelersModel(BaseModel):
    count: int
    type: str

@app.post("/travel-plan")
async def create_travel_plan(request: TravelPlanRequestModel):
    """
    여행 계획 생성 엔드포인트
    """
    try:
        # 데이터 수집
        collector = TravelDataCollector(
            place_helper=PlacesHelper(),
            hotels_helper=HotelsHelper(),
            gemini_helper=GeminiAPIHelper(GEMINI_API_KEY)
        )
        
        travel_data = await collector.collect_travel_data(
            destination={
                "name": request.destination.name,
                "location": {
                    "lat": request.destination.lat,
                    "lng": request.destination.lng
                }
            },
            start_date=request.start_date,
            end_date=request.end_date,
            budget=request.budget,
            themes=request.themes,
            travelers={
                "count": request.travelers.get('count', 1),
                "type": request.travelers.get('type', '혼자')
            }
        )
        
        # Gemini API 호출
        gemini_helper = GeminiAPIHelper()
        plan_data = gemini_helper.create_travel_plan(travel_data)
        
        if not plan_data:
            raise HTTPException(status_code=500, detail="여행 계획 생성에 실패했습니다.")
        
        return plan_data
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/place-suggestions")
async def get_place_suggestions(query: str = Query(..., min_length=1)):
    """
    장소 추천 엔드포인트
    """
    try:
        places_helper = PlacesHelper()
        suggestions = await places_helper.get_place_suggestions(query)  # await 추가
        return suggestions
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/place-location/{place_id}")
async def get_place_location(place_id: str):
    """
    Place ID로부터 위치 정보를 가져오는 엔드포인트
    """
    try:
        places_helper = PlacesHelper()
        location = await places_helper.get_place_details_by_id(place_id)
        if location:
            return location
        raise HTTPException(status_code=404, detail="Place not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/nearby-places")
async def get_nearby_places(
    lat: float, 
    lng: float, 
    themes: List[str] = Query(...)
):
    """
    주변 장소 검색 엔드포인트
    """
    try:
        places_helper = PlacesHelper()
        nearby_places = await places_helper.get_nearby_places(
            location={"lat": lat, "lng": lng},
            selected_themes=themes
        )
        return nearby_places
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/restaurants")
async def get_nearby_restaurants(
    lat: float,
    lng: float
):
    """
    주변 음식점만 검색하는 엔드포인트
    """
    try:
        places_helper = PlacesHelper()
        restaurants = await places_helper.get_nearby_places(
            location={"lat": lat, "lng": lng},
            selected_themes=["음식/맛집"]  # 자동으로 음식 관련 테마만 선택
        )
        return restaurants
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/hotels")
async def search_hotels(
    lat: float, 
    lng: float, 
    radius: int = 30000
):
    """
    호텔 검색 엔드포인트
    """
    try:
        hotels_helper = HotelsHelper()
        hotels = await hotels_helper.search_hotels(
            location={"lat": lat, "lng": lng},
            radius=radius
        )
        return hotels
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 추가: Swagger UI 및 ReDoc 문서화
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)