import re
from typing import Optional

def clean_address(address: Optional[str]) -> str:
    """
    주소 정제 함수: 잘못된 형식 수정 및 표준화
    :param address: 정제할 주소 문자열 (None 가능)
    :return: 정제된 주소 문자열
    """
    # 입력값이 없거나 비어 있을 경우 기본값 반환
    if not address or not address.strip():
        return "서울특별시 중구"

    # 소문자 변환 및 불필요한 공백 제거 (초기 정제)
    address = address.strip()

    # 국가명 및 불필요한 접두어 제거
    address = re.sub(r"대한민국\s?|Republic\s?of\s?Korea\s?|KR\s?", "", address, flags=re.IGNORECASE)

    # 흔한 오타 수정
    address = address.replace("중고", "중구")  # "중고" → "중구"
    address = address.replace("강남고", "강남구")  # "강남고" → "강남구" (추가 예시)

    # 우편번호 및 괄호 안 내용 제거 (예: [12345])
    address = re.sub(r"\[\d{5}\]|\(\d{5}\)", "", address)

    # 특수 문자 제거 (필요 시 제외 문자 지정 가능)
    address = re.sub(r"[!@#$%^&*+=|;:\"'<>,.?/]+", " ", address)

    # 연속 공백 정리 및 최종 트리밍
    address = re.sub(r"\s+", " ", address).strip()

    # 결과가 비어 있으면 기본값 반환
    return address if address else "서울특별시 중구"

# 테스트 코드
def test_clean_address():
    test_cases = [
        (None, "서울특별시 중구"),
        ("", "서울특별시 중구"),
        ("대한민국 서울특별시 중고", "서울특별시 중구"),
        ("KR 서울특별시 강남고 [12345]", "서울특별시 강남구"),
        ("Republic of Korea 부산광역시 해운대구!!!", "부산광역시 해운대구"),
        ("  서울   중구   ", "서울 중구"),
        ("경기도 수원시 영통구 (12345)", "경기도 수원시 영통구")
    ]
    
    for input_addr, expected in test_cases:
        result = clean_address(input_addr)
        print(f"입력: {input_addr}, 결과: {result}, 예상: {expected}, "
              f"{'✅ 통과' if result == expected else '❌ 실패'}")

if __name__ == "__main__":
    test_clean_address()