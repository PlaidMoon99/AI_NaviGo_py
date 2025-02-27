import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from services.travel_planner import TravelPlanner
from utils.service_code_loader import load_service_code_mapping
from services.tour_api import TourAPIService
import logging as logger


app = FastAPI()

# CORS 설정 (프론트엔드에서 API 호출 가능하도록 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 도메인 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# @app.on_event("startup")
# async def startup_event():
#     # 서비스 코드 매핑 로드 및 저장
#     load_service_code_mapping()

#     # TourAPI 데이터 가져오기 및 처리
#     tour_api_service = TourAPIService()
#     # 기본값 설정 또는 유효성 검사
#     area_code = "1"  # 예시 기본값
#     sigungu_code = None  # 필요없다면 제외
#     content_type_ids = ["12", "14", "15"]  # 예시 기본값
    
#     data = await tour_api_service.get_places(area_code, sigungu_code, content_type_ids)
#     if data:
#         logger.info(f"📌 가져온 여행지 데이터: {len(data)}개")
#     else:
#         logger.info("📌 가져온 여행지 데이터: 0개")

@app.post("/generate-plan")
async def generate_plan(request: Request):
    """🚀 AI 여행 일정 생성 API"""
    
    request_data = await request.json()
    planner = TravelPlanner()
    travel_plan = await planner.create_plan(request_data)

    if travel_plan:
        return {"status": "success", "travel_plan": travel_plan}
    return {"status": "error", "message": "일정 생성 실패"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=4000, reload=True)


