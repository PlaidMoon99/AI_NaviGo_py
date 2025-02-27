from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
import asyncio
from pydantic import BaseModel
from typing import List, Dict, Any
from datetime import date
import json
import os
import folium
from folium import plugins

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

class TravelersModel(BaseModel):
    count: int
    type: str

# 지도 파일 저장 디렉토리 생성
if not os.path.exists("travel_maps"):
    os.makedirs("travel_maps")

@app.post("/travel-plan")
async def create_travel_plan(request: TravelPlanRequestModel):
    """여행 계획 생성 엔드포인트"""
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
        
        # 생성된 일정 데이터 저장
        with open("travel_data.json", "w", encoding='utf-8') as f:
            json.dump(plan_data, f, ensure_ascii=False, indent=2)
        
        return plan_data
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/combined-map", response_class=HTMLResponse)
async def get_combined_map(days: str = Query(..., description="Comma separated days or range (e.g. '1,2,3' or '1-7')")):
    """선택된 일자들의 마커를 하나의 지도에 표시"""
    try:
        # 저장된 일정 데이터 읽기
        try:
            with open("travel_data.json", "r", encoding='utf-8') as f:
                schedule_data = json.load(f)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Travel schedule not found")

        # 일자 파싱
        requested_days = set()
        day_parts = days.split(',')
        
        for part in day_parts:
            if '-' in part:
                start, end = map(int, part.split('-'))
                requested_days.update(range(start, end + 1))
            else:
                requested_days.add(int(part))

        # 기본 지도 생성
        m = folium.Map(zoom_start=13, tiles="CartoDB positron")
        
        # 모든 마커의 좌표를 저장할 리스트
        all_coordinates = []
        
        # 일자별 색상
        colors = ['red', 'blue', 'green', 'purple', 'orange', 'darkred', 'darkblue', 'darkgreen', 'cadetblue', 'darkpurple']
        
        # 각 일자별 마커 그룹 생성
        for day in sorted(requested_days):
            # 해당 일자의 일정 찾기
            day_schedule = next(
                (schedule for schedule in schedule_data["daily_schedule"] 
                 if schedule["day"] == day), None
            )
            
            if not day_schedule:
                continue
                
            # 해당 일자의 마커 그룹 생성
            day_group = folium.FeatureGroup(name=f"Day {day}")
            
            for activity in day_schedule['activities']:
                if 'location' in activity:
                    lat = activity['location']['lat']
                    lng = activity['location']['lng']
                    all_coordinates.append([lat, lng])
                    
                    # 마커 생성
                    popup_html = f"""
                    <div style="width: 200px; padding: 10px;">
                        <h4 style="margin: 0 0 10px 0;">{activity['place']}</h4>
                        <p style="margin: 5px 0;"><b>시간:</b> {activity['time']}</p>
                        <p style="margin: 5px 0;"><b>소요시간:</b> {activity['duration']}분</p>
                        <p style="margin: 5px 0;"><b>유형:</b> {activity['type']}</p>
                        {f"<p style='margin: 5px 0;'><b>비고:</b> {activity['notes']}</p>" if 'notes' in activity else ''}
                    </div>
                    """
                    
                    # 일자별로 다른 색상 사용
                    color_idx = (day - 1) % len(colors)
                    
                    folium.Marker(
                        [lat, lng],
                        popup=folium.Popup(popup_html, max_width=300),
                        tooltip=f"Day {day}: {activity['place']}",
                        icon=folium.Icon(color=colors[color_idx])
                    ).add_to(day_group)
            
            day_group.add_to(m)
        
        if not all_coordinates:
            raise HTTPException(status_code=404, detail="No data found for the requested days")
        
        # 모든 마커가 보이도록 지도 범위 조정
        m.fit_bounds(all_coordinates)
        
        # 레이어 컨트롤 추가 (일자별 토글 가능)
        folium.LayerControl().add_to(m)
        
        # 미니맵 추가
        minimap = plugins.MiniMap(toggle_display=True)
        m.add_child(minimap)
        
        # 거리 측정 도구 추가
        plugins.MeasureControl(position='topleft').add_to(m)
        
        # 전체화면 버튼 추가
        plugins.Fullscreen().add_to(m)
        
        # HTML로 변환
        return m.get_root().render()
        
    except ValueError as e:
        raise HTTPException(
            status_code=400, 
            detail="Invalid day format. Use comma separated numbers or ranges (e.g. '1,2,3' or '1-7')"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/place-suggestions")
async def get_place_suggestions(query: str = Query(..., min_length=1)):
    """장소 추천 엔드포인트"""
    try:
        places_helper = PlacesHelper()
        suggestions = await places_helper.get_place_suggestions(query)
        return suggestions
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/place-location/{place_id}")
async def get_place_location(place_id: str):
    """Place ID로부터 위치 정보를 가져오는 엔드포인트"""
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
    """주변 장소 검색 엔드포인트"""
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
    """주변 음식점만 검색하는 엔드포인트"""
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
    """호텔 검색 엔드포인트"""
    try:
        hotels_helper = HotelsHelper()
        hotels = await hotels_helper.search_hotels(
            location={"lat": lat, "lng": lng},
            radius=radius
        )
        return hotels
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 요청 형식 정의
class PlaceRequest(BaseModel):
    places: List[str]

@app.post("/places-photos")
async def get_plan_photos(request: PlaceRequest):
   """여행 계획의 모든 장소 사진을 가져오는 엔드포인트"""
   try:
       places_helper = PlacesHelper()
       hotels_helper = HotelsHelper()
       photos = {}

       for place_name in request.places:
           # 먼저 호텔로 시도
           hotel_photos = await hotels_helper.get_hotel_photos_batch([place_name])
           if hotel_photos.get(place_name):
               photos[place_name] = hotel_photos[place_name]
               continue
           
           # 호텔 사진이 없으면 일반 장소로 시도
           place_photos = await places_helper.get_place_photos_batch([place_name])
           if place_photos.get(place_name):
               photos[place_name] = place_photos[place_name]

       return {
           "success": True,
           "photos": photos
       }
   except Exception as e:
       raise HTTPException(status_code=500, detail=str(e))

# 서버 실행
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=7373)