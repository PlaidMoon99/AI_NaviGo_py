import google.generativeai as genai
from typing import Dict, Any
import json
from datetime import datetime
from config import GEMINI_API_KEY

class GeminiAPIHelper:
    def __init__(self, api_key: str = GEMINI_API_KEY):
        genai.configure(api_key=api_key)
        # generation_config를 사용하여 응답 제한 설정
        generation_config = {
            "temperature": 0.9,              # 응답의 창의성 정도 (0.0 ~ 1.0)
            "top_p": 1,                      # 샘플링 확률 (0.0 ~ 1.0)
            "top_k": 40,                     # 고려할 최상위 토큰 수
            "max_output_tokens": 8192,       # 최대 출력 토큰 수 (8192가 최대)
        }
        self.model = genai.GenerativeModel('gemini-pro', generation_config=generation_config)

    def _clean_json_response(self, text: str) -> str:
        """Gemini 응답에서 JSON 부분만 추출"""
        if '```json' in text:
            text = text.split('```json')[1]
        if '```' in text:
            text = text.split('```')[0]
        return text.strip()

    def create_travel_plan(self, travel_data: Dict[str, Any]) -> Dict[str, Any]:
        """여행 데이터를 기반으로 Gemini API를 사용하여 상세 여행 계획 생성"""
        # JSON 템플릿을 클래스 변수로 정의
        json_template = """{
        "summary": {
            "main_attractions": [주요 방문지 5-6곳],
            "route_overview": "간단한 동선 설명"
        },
        "daily_schedule": [
            {
                "day": 1,
                "date": "YYYY-MM-DD",
                "activities": [
                    {
                        "type": "attraction/restaurant/hotel",
                        "place": "장소명",
                        "notes": "장소에 대한 간략한 설명 및 방문 목적"
                    }
                ],
                "total_distance": 이동거리(km)
            }
        ]
    }"""
        # 1. 기본 데이터 준비
        start_date = datetime.strptime(travel_data['duration']['start_date'], '%Y-%m-%d')
        total_days = travel_data['duration']['total_days']

        # 2. 선택 가능한 장소 목록 생성
        available_places = {
            'hotels': [h['name'] for h in travel_data.get('hotels', [])],
            'attractions': [a['name'] for a in travel_data.get('attractions', [])],
            'restaurants': [r['name'] for r in travel_data.get('restaurants', [])]
        }

        safety_prompt = "반드시 유효한 JSON 형식으로 응답해주시고, 추가 설명이나 마크다운 기호는 사용하지 말아주세요."

        prompt = f"""
{safety_prompt}

여행 플래너로서 {travel_data['destination']}의 {total_days}일 일정을 한국어로 만들어주세요.

기본 정보:
- 기간: {start_date.strftime('%Y-%m-%d')}부터 {total_days}일
- 여행자: {travel_data['travelers']['count']}명 ({travel_data['travelers']['type']})

선택 가능한 장소 목록:
1. 숙소: {', '.join(available_places['hotels'])}
2. 관광지: {', '.join(available_places['attractions'])}
3. 식당: {', '.join(available_places['restaurants'])}

필수 규칙:
1. 정확히 {total_days}일의 일정을 작성하세요.
2. 하루 3-4곳만 방문하세요 (식당 제외).
3. 위 목록에 있는 장소만 사용하세요.
4. 하루 식사는 점심, 저녁 각 1곳씩만 선택하세요.
5. 첫날은 비행기 도착 시간을 고려해 오후부터 시작하고 2-3곳만 방문하세요.
6. 마지막 날은 비행기 출발 시간을 고려해 오전에만 1-2곳 방문하고 일정을 마무리하세요.
7. 모든 장소에 대한 간략한 설명을 작성하세요.



{json_template}"""

        try:
            # 1. 응답 생성 시도 (최대 2번)
            for attempt in range(2):
                try:
                    response = self.model.generate_content(
                        prompt,
                        stream=False,  # 스트리밍 비활성화로 전체 응답을 한 번에 받음
                    )
                    
                    cleaned_response = self._clean_json_response(response.text)
                    plan_data = json.loads(cleaned_response)
                    
                    # 검증 통과시 바로 반환
                    if isinstance(plan_data, dict) and "daily_schedule" in plan_data:
                        if len(plan_data["daily_schedule"]) == total_days:
                            # 위치 정보 추가
                            for day in plan_data["daily_schedule"]:
                                for activity in day["activities"]:
                                    place_name = activity["place"]
                                    if place_name in travel_data["locations"]:
                                        activity["location"] = travel_data["locations"][place_name]
                            
                            return plan_data
                except Exception as e:
                    print(f"Attempt {attempt + 1} failed: {str(e)}")
                    if attempt == 1:  # 마지막 시도에서 실패
                        raise e
            
            raise ValueError("유효한 여행 계획을 생성하지 못했습니다.")
            
        except Exception as e:
            print(f"Error generating travel plan: {str(e)}")
            return {
                "error": "여행 계획 생성에 실패했습니다.",
                "message": str(e),
                "raw_response": response.text if 'response' in locals() else None
            }
