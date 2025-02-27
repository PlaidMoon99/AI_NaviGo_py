import google.generativeai as genai
import json
import re
from utils.settings import settings
from utils.logger import setup_logger
from utils.cache import Cache
from services.google_places import GooglePlacesClient
import aiohttp
from datetime import datetime, timedelta

logger = setup_logger("GeminiService")
cache = Cache()

# 시군구 코드 맵 (기존 코드에서 가져옴)
SIGUNGU_CODE_MAP = {
    31: {  # Gyeonggi
        "가평군": 1, "고양시": 2, "과천시": 3, "광명시": 4, "광주시": 5, "구리시": 6, "군포시": 7,
        "김포시": 8, "남양주시": 9, "동두천시": 10, "부천시": 11, "성남시": 12, "수원시": 13, "시흥시": 14,
        "안산시": 15, "안성시": 16, "안양시": 17, "양주시": 18, "양평군": 19, "여주시": 20, "연천군": 21,
        "오산시": 22, "용인시": 23, "의왕시": 24, "의정부시": 25, "이천시": 26, "파주시": 27, "평택시": 28,
        "포천시": 29, "하남시": 30, "화성시": 31
    },
    32: {  # Gangwon
        "강릉시": 1, "고성군": 2, "동해시": 3, "삼척시": 4, "속초시": 5, "양구군": 6, "양양군": 7,
        "영월군": 8, "원주시": 9, "인제군": 10, "정선군": 11, "철원군": 12, "춘천시": 13, "태백시": 14,
        "평창군": 15, "홍천군": 16, "화천군": 17, "횡성군": 18
    },
    33: {  # Chungbuk
        "괴산군": 1, "단양군": 2, "보은군": 3, "영동군": 4, "옥천군": 5, "음성군": 6, "제천시": 7,
        "진천군": 8, "청주시": 10, "충주시": 11, "증평군": 12
    },
    34: {  # Chungnam
        "공주시": 1, "금산군": 2, "논산시": 3, "당진시": 4, "보령시": 5, "부여군": 6, "서산시": 7,
        "서천군": 8, "아산시": 9, "예산군": 11, "천안시": 12, "청양군": 13, "태안군": 14, "홍성군": 15
    },
    35: {  # Gyeongbuk
        "경산시": 1, "경주시": 2, "고령군": 3, "구미시": 4, "군위군": 5, "김천시": 6, "문경시": 7,
        "봉화군": 8, "상주시": 9, "성주군": 10, "안동시": 11, "영덕군": 12, "영양군": 13, "영주시": 14,
        "영천시": 15, "예천군": 16, "울릉군": 17, "울진군": 18, "의성군": 19, "청도군": 20, "청송군": 21,
        "칠곡군": 22, "포항시": 23
    },
    36: {  # Gyeongnam
        "거제시": 1, "거창군": 2, "고성군": 3, "김해시": 4, "남해군": 5, "밀양시": 7, "사천시": 8,
        "산청군": 9, "양산시": 10, "의령군": 12, "진주시": 13, "창녕군": 15, "창원시": 16, "통영시": 17,
        "하동군": 18, "함안군": 19, "함양군": 20, "합천군": 21
    },
    37: {  # Jeonbuk
        "고창군": 1, "군산시": 2, "김제시": 3, "남원시": 4, "무주군": 5, "부안군": 6, "순창군": 7,
        "완주군": 8, "익산시": 9, "임실군": 10, "장수군": 11, "전주시": 12, "정읍시": 13, "진안군": 14
    },
    38: {  # Jeonnam
        "강진군": 1, "고흥군": 2, "곡성군": 3, "광양시": 4, "구례군": 5, "나주시": 6, "담양군": 7,
        "목포시": 8, "무안군": 9, "보성군": 10, "순천시": 11, "신안군": 12, "여수시": 13, "영광군": 16,
        "영암군": 17, "완도군": 18, "장성군": 19, "장흥군": 20, "진도군": 21, "함평군": 22, "해남군": 23,
        "화순군": 24
    }
}

AREA_CODE_MAP = {
    "서울": 1, "인천": 2, "대전": 3, "대구": 4, "광주": 5, "부산": 6, "울산": 7, "세종": 8,
    "경기": 31, "강원": 32, "충북": 33, "충남": 34, "경북": 35, "경남": 36, "전북": 37,
    "전남": 38, "제주": 39
}

class GeminiService:
    def __init__(self):
        """Gemini AI 및 Google Places 클라이언트 초기화"""
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel("gemini-1.5-flash")  # 최신 모델 사용
        self.google_api = GooglePlacesClient()

    async def generate_itinerary(self, travel_data):
        """여행 일정을 생성하고 이미지 URL을 보강하여 반환"""
        # 캐시 키 생성
        cache_key = f"gemini_plan:{travel_data['region']}:{travel_data.get('district', 'none')}:{travel_data['start_date']}:{travel_data['end_date']}"
        cached_data = await cache.get(cache_key)
        if cached_data:
            logger.info("✅ Redis 캐시 사용: Gemini 일정 반환")
            await self.validate_image_urls(cached_data)
            return cached_data

        # 입력 데이터 파싱
        companion_type = travel_data.get("companion_type", "개별 여행자")
        themes = ", ".join(travel_data.get("themes", ["추천 여행지"]))
        location_info = f"{travel_data['region']} {travel_data.get('district', '')}".strip()
        hotels = travel_data.get("hotels", [])
        restaurants = travel_data.get("restaurants", [])

        # 추천 정보 준비
        hotel_info = "\n".join([f"- {h['name']} ({h['address']})" for h in hotels]) if hotels else "추천 숙소 없음"
        restaurant_info = "\n".join([f"- {r['name']} ({r['address']})" for r in restaurants]) if restaurants else "추천 맛집 없음"

        # 날짜 범위 계산
        start_date = datetime.strptime(travel_data["start_date"], "%Y-%m-%d")
        end_date = datetime.strptime(travel_data["end_date"], "%Y-%m-%d")
        days = (end_date - start_date).days + 1

        # 인근 지역 정의
        nearby_regions = [travel_data["region"]]
        nearby_districts = self.get_nearby_districts(travel_data["region"], travel_data.get("district", None))
        if days >= 3 and nearby_districts:
            nearby_regions.extend([f"{travel_data['region']} {district}" for district in nearby_districts])

        # 프롬프트 생성
        prompt = f"""
        사용자가 {location_info} 여행을 계획 중입니다.
        여행 날짜는 {travel_data["start_date"]}부터 {travel_data["end_date"]}까지이며, 총 {days}일입니다.
        동행자는 {companion_type}이며, 주요 관심사는 {themes}입니다.

        {location_info}를 중심으로 하루별 여행 일정을 JSON 형식으로 반환해주세요.
        - 각 날짜는 "date" (형식: "YYYY-MM-DD")와 "places" (장소 리스트)로 구성하세요.
        - 장소는 다음 필드를 포함:
          - "type": "관광지" | "점심" | "저녁" | "숙소"
          - "name": 장소 이름
          - "address": 장소 주소
          - "image": 빈 문자열 "" (이미지는 백엔드에서 채워짐)
        - **하루 일정 규칙**:
          - 일반 날: "관광지 → 점심 → 관광지 → 저녁 → 숙소" 순으로 5개 장소.
          - 마지막 날: "관광지 → 점심 → 관광지 → 저녁" 순으로 4개 장소 (숙소 제외).
        - {days}일 모두 커버하며, {themes}와 관련된 장소를 우선 포함하세요.
        - 3일 이상일 경우 인근 시군구 ({', '.join(nearby_regions)})도 포함하세요.
        - 추천 숙소와 맛집을 활용하며, 부족하면 추가로 추천하세요.
        - 완전한 JSON을 반환하세요.

        🔹 **추천 숙소 목록**:
        {hotel_info}

        🔹 **추천 맛집 목록**:
        {restaurant_info}

        ✅ JSON 형식 예시:
        {{"travel_plan": [
            {{"date": "2025-03-01", "places": [
                {{"type": "관광지", "name": "경복궁", "address": "서울 종로구", "image": ""}},
                {{"type": "점심", "name": "종로 맛집", "address": "서울 종로구", "image": ""}},
                {{"type": "관광지", "name": "창덕궁", "address": "서울 종로구", "image": ""}},
                {{"type": "저녁", "name": "북촌 한정식", "address": "서울 종로구", "image": ""}},
                {{"type": "숙소", "name": "종로 호텔", "address": "서울 종로구", "image": ""}}
            ]}},
            {{"date": "2025-03-02", "places": [
                {{"type": "관광지", "name": "남산타워", "address": "서울 용산구", "image": ""}},
                {{"type": "점심", "name": "남산 맛집", "address": "서울 용산구", "image": ""}},
                {{"type": "관광지", "name": "일산 호수공원", "address": "경기 고양시", "image": ""}},
                {{"type": "저녁", "name": "고양 맛집", "address": "경기 고양시", "image": ""}},
                {{"type": "숙소", "name": "고양 호텔", "address": "경기 고양시", "image": ""}}
            ]}},
            {{"date": "2025-03-03", "places": [
                {{"type": "관광지", "name": "인사동", "address": "서울 종로구", "image": ""}},
                {{"type": "점심", "name": "인사동 맛집", "address": "서울 종로구", "image": ""}},
                {{"type": "관광지", "name": "명동성당", "address": "서울 중구", "image": ""}},
                {{"type": "저녁", "name": "명동 맛집", "address": "서울 중구", "image": ""}}
            ]}}
        ]}}
        **JSON 코드 블록(```json ... ```) 없이 JSON만 반환하세요.**
        """

        # 최대 3회 시도
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                response = self.model.generate_content(prompt)
                if not response or not response.text:
                    logger.error(f"🚨 Gemini AI 응답 없음 (시도 {attempt + 1}/{max_attempts})")
                    continue

                response_text = response.text.strip()
                cleaned_response = re.sub(r"```json\n|\n```", "", response_text).strip()
                json_response = self.fix_invalid_json(cleaned_response)

                if json_response and "travel_plan" in json_response:
                    await self.enrich_with_images(json_response, location_info)
                    await self.validate_image_urls(json_response)
                    await cache.set(cache_key, json_response, ttl=3600)
                    logger.info("✅ Gemini AI 일정 생성 성공")
                    return json_response

                logger.warning(f"🚨 JSON 변환 실패 (시도 {attempt + 1}/{max_attempts}): {response_text}")

            except Exception as e:
                logger.error(f"🚨 Gemini AI 호출 실패 (시도 {attempt + 1}/{max_attempts}): {str(e)}")

        # 기본 응답
        default_response = self.generate_default_itinerary(travel_data, days, location_info)
        await cache.set(cache_key, default_response, ttl=3600)
        logger.info("✅ 기본 일정 반환")
        return default_response

    def get_nearby_districts(self, region, district):
        """주어진 지역 내 인근 시군구 반환"""
        area_code = AREA_CODE_MAP.get(region)
        if area_code not in SIGUNGU_CODE_MAP or not district:
            return []

        districts = list(SIGUNGU_CODE_MAP[area_code].keys())
        if district not in districts:
            return districts[:3]  # 임의로 3개 반환

        # 인근 시군구 선택 (단순히 인덱스 기반으로 앞뒤 3개 선택)
        district_index = districts.index(district)
        start = max(0, district_index - 3)
        end = min(len(districts), district_index + 4)
        nearby = districts[start:district_index] + districts[district_index + 1:end]
        return nearby[:3]  # 최대 3개 반환

    def generate_default_itinerary(self, travel_data, days, location_info):
        """기본 일정 생성"""
        start_date = datetime.strptime(travel_data["start_date"], "%Y-%m-%d")
        travel_plan = []

        for day in range(days):
            current_date = start_date + timedelta(days=day)
            date_str = current_date.strftime("%Y-%m-%d")
            places = [
                {"type": "관광지", "name": f"{location_info} 관광지 1", "address": location_info, "image": ""},
                {"type": "점심", "name": f"{location_info} 점심 맛집", "address": location_info, "image": ""},
                {"type": "관광지", "name": f"{location_info} 관광지 2", "address": location_info, "image": ""},
                {"type": "저녁", "name": f"{location_info} 저녁 맛집", "address": location_info, "image": ""}
            ]
            if day < days - 1:  # 마지막 날 제외
                places.append({"type": "숙소", "name": f"{location_info} 기본 숙소", "address": location_info, "image": ""})
            travel_plan.append({"date": date_str, "places": places})

        return {"travel_plan": travel_plan}

    async def enrich_with_images(self, json_response, region):
        """모든 장소에 대해 Google Places API로 이미지 URL을 보강"""
        for day in json_response.get("travel_plan", []):
            for place in day.get("places", []):
                logger.debug(f"🔍 이미지 보강 시도: {place['name']}")
                try:
                    google_results = await self.google_api.search_places(place["name"], region)
                    if google_results and "place_id" in google_results[0]:
                        images = await self.google_api.get_place_images(google_results[0]["place_id"])
                        place["image"] = images[0] if images else "https://via.placeholder.com/400x300?text=No+Image"
                    else:
                        place["image"] = "https://via.placeholder.com/400x300?text=No+Image"
                    logger.debug(f"✅ 이미지 설정 완료: {place['name']} - {place['image']}")
                except Exception as e:
                    logger.error(f"🚨 이미지 보강 실패: {place['name']} - {str(e)}")
                    place["image"] = "https://via.placeholder.com/400x300?text=No+Image"

    async def validate_image_urls(self, json_response):
        """이미지 URL 유효성 검사 및 리다이렉션 처리"""
        async with aiohttp.ClientSession() as session:
            for day in json_response.get("travel_plan", []):
                for place in day.get("places", []):
                    image_url = place.get("image", "")
                    if image_url and image_url != "https://via.placeholder.com/400x300?text=No+Image":
                        try:
                            async with session.head(image_url, timeout=aiohttp.ClientTimeout(total=5), allow_redirects=True) as resp:
                                if resp.status == 200:
                                    logger.debug(f"✅ 이미지 URL 유효: {place['name']} - {image_url}")
                                elif resp.status == 302:
                                    logger.info(f"ℹ️ 이미지 URL 리다이렉션: {place['name']} - {image_url}")
                                    async with session.get(image_url, allow_redirects=True) as get_resp:
                                        if get_resp.status == 200:
                                            place["image"] = str(get_resp.url)
                                            logger.debug(f"✅ 리다이렉션 후 URL 갱신: {place['name']} - {place['image']}")
                                        else:
                                            logger.warning(f"⚠️ 리다이렉션 후 오류 ({get_resp.status}): {place['name']} - {image_url}")
                                else:
                                    logger.warning(f"🚨 이미지 URL 오류 ({resp.status}): {place['name']} - {image_url}")
                                    await self.retry_image_enrichment(place, day, session)
                        except Exception as e:
                            logger.error(f"🚨 이미지 URL 검증 실패: {place['name']} - {str(e)}")
                            await self.retry_image_enrichment(place, day, session)

    async def retry_image_enrichment(self, place, day, session):
        """이미지 URL 오류 시 재시도"""
        try:
            region = day["places"][0]["address"].split()[0]
            google_results = await self.google_api.search_places(place["name"], region)
            if google_results and "place_id" in google_results[0]:
                images = await self.google_api.get_place_images(google_results[0]["place_id"])
                place["image"] = images[0] if images else "https://via.placeholder.com/400x300?text=No+Image"
            else:
                place["image"] = "https://via.placeholder.com/400x300?text=No+Image"
            logger.debug(f"✅ 이미지 재설정: {place['name']} - {place['image']}")
        except Exception as e:
            logger.error(f"🚨 이미지 재시도 실패: {place['name']} - {str(e)}")
            place["image"] = "https://via.placeholder.com/400x300?text=No+Image"

    def fix_invalid_json(self, json_text):
        """불완전한 JSON을 수정하여 파싱"""
        try:
            return json.loads(json_text)
        except json.JSONDecodeError:
            json_text = json_text.replace("'", '"')
            json_text = re.sub(r"([{,])\s*([a-zA-Z0-9_]+)\s*:", r'\1"\2":', json_text)
            if not json_text.endswith("}}]}"):
                last_brace_index = json_text.rfind("}")
                if last_brace_index != -1:
                    json_text = json_text[:last_brace_index + 1] + "]}"
                else:
                    json_text += "]}"
            try:
                return json.loads(json_text)
            except json.JSONDecodeError as e:
                logger.error(f"🚨 JSON 수정 실패: {e}")
                return None