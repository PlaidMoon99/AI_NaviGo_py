import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# API 키들
GOOGLE_CLOUD_API_KEY = os.getenv('GOOGLE_CLOUD_API_KEY')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-pro')
EXCHANGERATES = os.getenv('EXCHANGERATES')

# 프로젝트 설정
PROJECT_NAME = "Travel Planner API"
API_V1_STR = "/api/v1"
LOG_LEVEL = "INFO"

# API 키 검증
def validate_api_keys():
    if not GOOGLE_CLOUD_API_KEY:
        raise ValueError("Google Cloud API 키가 설정되지 않았습니다.")
    if not GEMINI_API_KEY:
        raise ValueError("Gemini API 키가 설정되지 않았습니다.")

# 애플리케이션 시작 시 API 키 검증
validate_api_keys()

# Example Request Body
{
  "destination": {
    "name": "Prague",
    "lat": 50.0755,
    "lng": 14.4378
  },
  "start_date": "2024-02-20",
  "end_date": "2024-02-26",
  "budget": 2000000,
  "themes": ["문화/역사", "관광명소", "음식/맛집"],
  "travelers": {
    "count": 2,
    "type": "couple"
  }
}