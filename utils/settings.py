from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """🚀 FastAPI 환경 변수 설정"""
    
    # ✅ API Keys (Pydantic에서 자동 로드)
    TOUR_API_KEY: str
    GOOGLE_PLACES_API_KEY: str
    KAKAO_REST_API_KEY: str
    NAVER_CLIENT_ID: str
    NAVER_CLIENT_SECRET: str
    GEMINI_AI_KEY: str
    GEMINI_API_KEY: str
    OPENAI_API_KEY: str  # ✅ 추가
    GEMINI_MODEL: str  # ✅ 추가
    GOOGLE_CLOUD_API_KEY: str  # ✅ 추가
    EXCHANGERATES: str  # ✅ 추가
    KAKAO_JS_API_KEY: str  # ✅ 추가

    # ✅ API Endpoints (기본값 설정)
    TOUR_API_BASE_URL: str = "http://apis.data.go.kr/B551011/KorService1"
    GOOGLE_PLACES_BASE_URL: str = "https://maps.googleapis.com/maps/api/place"
    KAKAO_MAP_BASE_URL: str = "https://dapi.kakao.com/v2/local"
    NAVER_SEARCH_BASE_URL: str = "https://openapi.naver.com/v1/search"

    # ✅ Redis 설정 (기본값 포함)
    REDIS_URL: str = "redis://localhost:6379"

    db_host: str 
    db_user: str
    db_password: str
    db_name: str

    # model_config = ConfigDict(extra="allow") 

    # ✅ 로그 파일 경로
    LOG_FILE: str = "logs/navigo.log"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "forbid"  # ❌ 정의되지 않은 변수는 허용되지 않음 (ValidationError 방지)

# 설정 인스턴스 생성
settings = Settings()
