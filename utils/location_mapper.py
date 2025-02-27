import json
from typing import Optional, Dict
from utils.logger import setup_logger

logger = setup_logger("LocationMapper")

# Regional area code mapping (simplified metropolitan areas)
AREA_CODE_MAP: Dict[str, int] = {
    "서울": 1, "인천": 2, "대전": 3, "대구": 4, "광주": 5, "부산": 6, "울산": 7, "세종": 8,
    "경기": 31, "강원": 32, "충북": 33, "충남": 34, "경북": 35, "경남": 36, "전북": 37,
    "전남": 38, "제주": 39
}

# Sigungu (district) code mapping (excludes Seoul to Sejong and Jeju)
SIGUNGU_CODE_MAP: Dict[int, Dict[str, int]] = {
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
        "진천군": 8, "청주시": 10, "충주시": 11, "증평군": 12  # "창원군" typo removed
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
        "하동군": 18, "함안군": 19, "함양군": 20, "합천군": 21  # "마산시" merged into 창원시
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
    # Seoul(1) to Sejong(8) and Jeju(39) are not included in SIGUNGU_CODE_MAP
}

def get_area_code(region: str | int) -> Optional[int]:
    """
    Returns the area code for a given region name or passes through an integer area code.
    :param region: Region name (e.g., "서울", "부산") or area code (e.g., 1, 31)
    :return: Area code or None if invalid
    """
    if isinstance(region, int):
        if region in AREA_CODE_MAP.values():
            return region
        logger.warning(f"⚠️ Invalid area code provided: {region}")
        return None
    
    if not isinstance(region, str):
        logger.warning(f"⚠️ Region must be string or integer, got: {type(region)}")
        return None
    
    region_name = region.strip()
    code = AREA_CODE_MAP.get(region_name)
    if code is None:
        logger.warning(f"⚠️ Area code mapping failed for region: {region_name}")
    return code

def get_sigungu_code(region: str | int, district_name: Optional[str | int]) -> Optional[int]:
    """
    Returns the sigungu code for a given region and district name.
    :param region: Region name (e.g., "경기") or area code (e.g., 31)
    :param district_name: District name (e.g., "용인시") or None
    :return: Sigungu code or None
    """
    if not district_name:
        return None
    
    area_code = get_area_code(region)
    if not area_code:
        logger.warning(f"⚠️ No area code found for region: {region}")
        return None
    
    # Seoul(1) to Sejong(8) and Jeju(39) have no sigungu codes
    if area_code in {1, 2, 3, 4, 5, 6, 7, 8, 39}:
        return None
    
    if area_code not in SIGUNGU_CODE_MAP:
        logger.warning(f"⚠️ No sigungu mapping for region with area code: {area_code}")
        return None
    
    if isinstance(district_name, int):
        logger.warning(f"⚠️ District name cannot be an integer: {district_name}")
        return None
    
    if not isinstance(district_name, str):
        logger.warning(f"⚠️ District name must be string, got: {type(district_name)}")
        return None
    
    district_name = district_name.strip()
    code = SIGUNGU_CODE_MAP[area_code].get(district_name)
    if code is None:
        logger.warning(f"⚠️ Sigungu code mapping failed: region={region}, district={district_name}")
    return code

def validate_location(region: str | int, district_name: Optional[str | int] = None) -> bool:
    """
    Validates the region and optional district name.
    :param region: Region name or area code
    :param district_name: District name (optional)
    :return: True if valid, False otherwise
    """
    area_code = get_area_code(region)
    if not area_code:
        return False
    
    if district_name:
        # Seoul to Sejong and Jeju do not have sigungu codes
        if area_code in {1, 2, 3, 4, 5, 6, 7, 8, 39}:
            logger.warning(f"⚠️ Region {region} does not support districts")
            return False
        sigungu_code = get_sigungu_code(region, district_name)
        return bool(sigungu_code)
    
    return True

# Example usage
if __name__ == "__main__":
    test_cases = [
        ("서울", None),          # Valid without district
        ("서울", "종로구"),       # Invalid (Seoul has no sigungu codes)
        ("인천", None),          # Valid without district
        ("대전", "유성구"),       # Invalid (Daejeon has no sigungu codes)
        ("세종", None),          # Valid without district
        ("제주", None),          # Valid without district
        ("제주", "제주시"),       # Invalid (Jeju has no sigungu codes)
        ("경기", "용인시"),       # Valid with district
        ("강원", "춘천시"),       # Valid with district
        ("충북", "청주시"),       # Valid with district
        ("전남", "순천시"),       # Valid with district
        ("invalid", "invalid"),  # Invalid region and district
        (31, "용인시"),          # Valid with area code and district
        (1, None),               # Valid with area code, no district
        (999, None),             # Invalid area code
    ]

    for region, district in test_cases:
        area_code = get_area_code(region)
        sigungu_code = get_sigungu_code(region, district)
        is_valid = validate_location(region, district)
        print(f"Region: {region}, District: {district}, AreaCode: {area_code}, "
              f"SigunguCode: {sigungu_code}, Valid: {is_valid}")