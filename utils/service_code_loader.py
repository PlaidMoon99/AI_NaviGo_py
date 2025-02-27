import os
import pandas as pd
from utils.logger import setup_logger
import json

logger = setup_logger("ServiceCodeLoader")

DEFAULT_SERVICE_CODE_MAPPING = {
    "12": {"국립공원", "산", "해수욕장", "섬", "고궁", "성", "민속마을", "유적지/사적지", "사찰", "테마공원"},
    "14": {"박물관", "미술관/화랑", "전시관", "기념관", "도서관", "공연장"},
    "15": {"문화관광축제", "일반축제", "전통공연", "전시회", "박람회"},
    "28": {"패러글라이딩", "번지점프", "서핑", "ATV", "래프팅", "수상 스포츠", "스키/스노보드"},
    "38": {"5일장", "상설시장"},
    "39": {"카페/전통찻집"}
}

# 테마 카테고리 정의 (확장된 "테마파크" 포함)
THEME_CATEGORIES = {
    "산": {"국립공원", "도립공원", "군립공원", "산", "등산로", "산림욕장"},
    "바다": {"해수욕장", "항구/포구", "섬", "해안절경", "등대"},
    "실내 여행지": {"박물관", "미술관/화랑", "전시관", "기념관", "도서관", "공연장"},
    "액티비티": {"패러글라이딩", "번지점프", "서핑", "ATV", "래프팅", "수상 스포츠", "스키/스노보드"},
    "문화 & 역사": {"유적지/사적지", "고궁", "성", "문", "고택", "생가", "전통마을", "사찰"},
    "테마파크": {"놀이공원", "워터파크", "테마공원", "동물원", "수족관"},
    "카페": {"감성카페", "전망카페", "브런치카페", "디저트카페"},
    "전통시장": {"재래시장", "전통시장", "로컬푸드", "야시장"},
    "축제": {"문화관광축제", "일반축제", "전통공연", "전시회", "박람회", "불꽃놀이"}
}

# cat3 코드와 테마 매핑 (TourAPI 기반, "테마파크" 확장)
CAT3_THEME_MAPPING = {
    # "산" 테마
    "A01010100": "산",  # 국립공원
    "A01010200": "산",  # 도립공원
    "A01010300": "산",  # 군립공원
    "A01010400": "산",  # 산
    # "바다" 테마
    "A01011200": "바다",  # 해수욕장
    "A01011300": "바다",  # 섬
    "A01011400": "바다",  # 항구/포구
    "A01011600": "바다",  # 등대
    "A01011100": "바다",  # 해안절경
    # "실내 여행지" 테마
    "A02060100": "실내 여행지",  # 박물관
    "A02060200": "실내 여행지",  # 기념관
    "A02060300": "실내 여행지",  # 전시관
    "A02060500": "실내 여행지",  # 미술관/화랑
    "A02060600": "실내 여행지",  # 공연장
    "A02060900": "실내 여행지",  # 도서관
    # "액티비티" 테마
    "A03022400": "액티비티",  # 번지점프
    "A03030800": "액티비티",  # 래프팅
    "A03021200": "액티비티",  # 스키/스노보드
    "A03022100": "액티비티",  # ATV
    "A03030100": "액티비티",  # 윈드서핑/제트스키
    "A03030200": "액티비티",  # 카약/카누
    "A03040300": "액티비티",  # 헹글라이딩/패러글라이딩
    # "문화 & 역사" 테마
    "A02010100": "문화 & 역사",  # 고궁
    "A02010200": "문화 & 역사",  # 성
    "A02010300": "문화 & 역사",  # 문
    "A02010400": "문화 & 역사",  # 고택
    "A02010500": "문화 & 역사",  # 생가
    "A02010600": "문화 & 역사",  # 민속마을
    "A02010700": "문화 & 역사",  # 유적지/사적지
    "A02010800": "문화 & 역사",  # 사찰
    # "테마파크" 테마 (TourAPI에서 직접 매핑 가능한 항목만)
    "A02020600": "테마파크",  # 테마공원 (놀이공원, 동물원 등은 명시적 cat3 없음)
    # "전통시장" 테마
    "A04010100": "전통시장",  # 5일장
    "A04010200": "전통시장",  # 상설시장
    # "축제" 테마
    "A02070100": "축제",  # 문화관광축제
    "A02070200": "축제",  # 일반축제
    "A02080100": "축제",  # 전통공연
    "A02080500": "축제",  # 전시회
    "A02080600": "축제",  # 박람회
    # "카페" 테마
    "A05020900": "카페",  # 카페/전통찻집
    # 기타 자연 요소
    "A01010500": "산",  # 자연생태관광지
    "A01010600": "산",  # 자연휴양림
    "A01010700": "산",  # 수목원
    "A01010800": "산",  # 폭포
    "A01010900": "산",  # 계곡
    "A01011700": "바다",  # 호수
    "A01011800": "바다",  # 강
    "A01011900": "산",  # 동굴
}

def load_service_code_mapping(file_path="C:\\ThisIsJava\\workspace_fin2\\navigo\\data\\tour_service_codes.xlsx", 
                              output_file="C:\\ThisIsJava\\workspace_fin2\\navigo\\data\\service_code_mapping.json"):
    service_code_mapping = DEFAULT_SERVICE_CODE_MAPPING.copy()
    theme_mapping = {theme: set() for theme in THEME_CATEGORIES}
    cat3_mapping = {}

    if not os.path.exists(file_path):
        logger.warning(f"⚠️ 엑셀 파일 없음: {file_path}, 기본 매핑 사용")
    else:
        try:
            df = pd.read_excel(file_path, engine="openpyxl", header=0)
            df.rename(columns={"소분류": "소분류명"}, inplace=True)
            df["contenttypeid"] = df["contenttypeid"].astype(str).fillna("").str.extract(r"(\d+)")[0]
            df["contenttypeid"] = df["contenttypeid"].ffill()

            # 엑셀 파일 로딩 후, 'contenttypeid'가 제대로 로딩되었는지 확인
            logger.info(f"엑셀 데이터 로드 완료. 데이터 예시:\n{df.head()}")

            for _, row in df.iterrows():
                content_type = row["contenttypeid"]
                cat3 = row.get("소분류 (cat3)", "")
                theme = str(row["소분류명"]).strip()

                # 유효한 content_type, 테마, cat3 값만 처리
                if not content_type or not theme or theme.lower() == 'nan':
                    continue

                service_code_mapping.setdefault(content_type, set()).add(theme)
                if cat3:
                    cat3_mapping.setdefault(content_type, {}).setdefault(cat3, set()).add(theme)
                for category, theme_set in THEME_CATEGORIES.items():
                    if theme in theme_set:
                        theme_mapping[category].add(theme)

            logger.info(f"✅ 엑셀에서 서비스 코드 및 테마 매핑 로드 완료")
        except Exception as e:
            logger.error(f"❌ 엑셀 로딩 오류: {e}, 파일 경로: {file_path}")
            return {}, {}, {}

    save_service_code_mapping(service_code_mapping, theme_mapping, cat3_mapping, output_file)
    return service_code_mapping, theme_mapping, cat3_mapping

def save_service_code_mapping(service_code_mapping, theme_mapping, cat3_mapping, output_file):
    try:
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        data = {
            "service_code_mapping": {k: sorted(v) for k, v in service_code_mapping.items()},
            "theme_mapping": {k: sorted(v) for k, v in theme_mapping.items()},
            "cat3_mapping": {k: {ck: sorted(cv) for ck, cv in v.items()} for k, v in cat3_mapping.items()}
        }
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        logger.info(f"✅ 매핑 저장 완료: {output_file}")
    except Exception as e:
        logger.error(f"❌ JSON 저장 오류: {e}")
