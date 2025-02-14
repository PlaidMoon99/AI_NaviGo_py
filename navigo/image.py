# pip install fastapi
# pip install uvicorn
# pip install googlemaps
# pip install requests
# pip install google-cloud-vision
# pip install python-dotenv
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import googlemaps
import requests
import os
from google.cloud import vision
from io import BytesIO

app = FastAPI()

# Google API 설정
GOOGLE_API_KEY = "AIzaSyCk4TLaiqwRtD_vYoGz9mj9Fh22Q6JsYA4"
gmaps = googlemaps.Client(key=GOOGLE_API_KEY)

# Kakao API 설정
KAKAO_API_KEY = "b1ab60b7906158849aa701b75e186433"
KAKAO_SEARCH_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
KAKAO_IMAGE_SEARCH_URL = "https://dapi.kakao.com/v2/search/image"

# Naver API 설정
NAVER_CLIENT_ID = "cxw00x8NMSjR3d11gVpB"
NAVER_CLIENT_SECRET = "8QN6ksYwAU"
NAVER_SEARCH_URL = "https://openapi.naver.com/v1/search/local.json"
NAVER_IMAGE_SEARCH_URL = "https://openapi.naver.com/v1/search/image.json"

# Google Cloud Vision API 설정
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "C:\\ThisIsJava\\workspace_mid\\vscode\\navigo\\app\\nevigo-1f0e882ebb53.json"
vision_client = vision.ImageAnnotatorClient()

@app.post("/analyze")
async def analyze_image(image: UploadFile = File(...)):
    try:
        # 이미지 읽기
        image_bytes = await image.read()
        image_obj = vision.Image(content=image_bytes)

        # Vision API 호출
        landmark_response = vision_client.landmark_detection(image=image_obj)
        label_response = vision_client.label_detection(image=image_obj)

        landmarks = [landmark.description for landmark in landmark_response.landmark_annotations]
        labels = [label.description.lower() for label in label_response.label_annotations]

        # Kakao API를 사용한 국내 여행지 검색
        search_terms = landmarks if landmarks else labels[:3]
        places = []
        for term in search_terms:
            kakao_places = get_kakao_places(f"{term} 관광지")
            if kakao_places:
                places.extend(kakao_places)
            else:
                places.extend(get_kakao_places(f"{term} 명소"))

        # 중복 제거
        unique_places = {place["place_name"]: place for place in places}.values()
        result_places = []

        for place in unique_places:
            image_url = get_naver_image(place["place_name"])
            naver_place = get_naver_place_info(place["place_name"])
            address = naver_place["address"] if naver_place else place.get("road_address_name", place["address_name"])
            print(image_url)
            result_places.append({
                "name": place["place_name"],
                "address": address,
                "image_url": image_url
            })

        return JSONResponse(content={"places": result_places})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def get_kakao_places(query):
    headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
    params = {"query": query, "category_group_code": "AT4", "size": 3}
    response = requests.get(KAKAO_SEARCH_URL, headers=headers, params=params)
    return response.json().get("documents", []) if response.status_code == 200 else []

def get_kakao_image(query):
    headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
    params = {"query": query, "size": 1}
    response = requests.get(KAKAO_IMAGE_SEARCH_URL, headers=headers, params=params)
    if response.status_code == 200:
        results = response.json().get("documents", [])
        return results[0]['image_url'] if results else "https://via.placeholder.com/300x200?text=No+Image"
    return "https://via.placeholder.com/300x200?text=Error"

def get_naver_place_info(query):
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    params = {"query": query, "display": 1}
    response = requests.get(NAVER_SEARCH_URL, headers=headers, params=params)
    if response.status_code == 200:
        result = response.json().get("items", [])
        return result[0] if result else None
    return None

def get_naver_image(query):
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    params = {"query": query, "display": 5, "sort": "sim"}  # 최대 5개 이미지 검색
    response = requests.get(NAVER_IMAGE_SEARCH_URL, headers=headers, params=params)
    
    if response.status_code == 200:
        items = response.json().get("items", [])
        for item in items:
            image_url = item["link"]
            # 이미지 URL 유효성 검사
            if is_valid_image_url(image_url):
                return image_url
    
    return "https://via.placeholder.com/300x200?text=No+Valid+Image"

def is_valid_image_url(url):
    """URL이 유효한 이미지인지 확인"""
    try:
        response = requests.head(url, timeout=5)  # 빠른 응답을 위해 HEAD 요청
        return response.status_code == 200 and "image" in response.headers.get("Content-Type", "")
    except requests.RequestException:
        return False


# ✅ FastAPI 실행
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000, reload=True)