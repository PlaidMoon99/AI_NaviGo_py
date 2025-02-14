from fastapi import FastAPI, HTTPException
import pymysql
import pandas as pd
from rapidfuzz import process, fuzz
import unicodedata
import os

app = FastAPI(docs_url="/docs", openapi_url="/openapi.json")  # FastAPI 문서 URL 명시적 설정

# 📂 최신 엑셀 파일 경로
EXCEL_FILE_PATH = "data/한국관광공사_국문_서비스분류코드_v4.2_gs.xlsx"

# ✅ 캐시 변수 (엑셀 데이터를 미리 로드하여 재사용)
category_data_cache = None

# ✅ 기본 API (FastAPI 정상 실행 여부 확인)
@app.get("/")
async def root():
    return {"message": "NaviGo API is running!"}

# ✅ MySQL 연결 함수
def get_connection():
    return pymysql.connect(
        host="192.168.0.6",
        user="sion",
        password="00000000",
        database="navi_go",
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor
    )

# ✅ 사용자 선호도 조회 (비동기)
async def get_user_preference(member_id):
    """
    preference 테이블에서 member_id에 해당하는 prefer_purpose를 가져옵니다.
    - 이제 '소분류'에 대응하는 값(사용자가 선택한 취향)이 저장되어 있다고 가정.
    """
    connection = get_connection()
    cursor = connection.cursor()
    sql = "SELECT prefer_purpose FROM preference WHERE member_id = %s"
    cursor.execute(sql, (member_id,))
    result = cursor.fetchone()
    connection.close()
    return result["prefer_purpose"] if result else None

# ✅ 사용자 클릭 기록 조회 (비동기)
async def get_user_click_history(member_id):
    """
    user_activity 테이블에서 member_id에 해당하는 클릭 기록(cat3 등)을 가져옵니다.
    """
    connection = get_connection()
    cursor = connection.cursor()
    sql = "SELECT contentid, cat1, cat2, cat3 FROM user_activity WHERE memberid = %s"
    cursor.execute(sql, (member_id,))
    result = cursor.fetchall()
    connection.close()
    return result

# ✅ 엑셀 데이터 로딩 함수 (캐싱 적용)
def load_category_data():
    global category_data_cache
    if category_data_cache is not None:
        return category_data_cache

    if not os.path.exists(EXCEL_FILE_PATH):
        raise FileNotFoundError(f"❌ 엑셀 파일이 존재하지 않습니다: {EXCEL_FILE_PATH}")

    print("🔄 엑셀 파일 로딩 중...")
    try:
        xls = pd.ExcelFile(EXCEL_FILE_PATH, engine="openpyxl")
        available_sheets = xls.sheet_names
        sheet_name = "시트1" if "시트1" in available_sheets else available_sheets[0]

        # 모든 데이터를 문자열로 읽어들이기 위해 dtype=str 설정
        df = pd.read_excel(xls, sheet_name=sheet_name, skiprows=0, dtype=str)
        expected_columns = ["contenttypeid", "cat1", "cat2", "cat3", "대분류", "중분류", "소분류"]
        df.columns = expected_columns[:len(df.columns)]
        df = df.dropna(how="all").reset_index(drop=True)

        # 필요 시 공백 제거
        df["소분류"] = df["소분류"].astype(str).str.strip()

        print("✅ [엑셀 로딩 완료] 데이터 개수:", df.shape[0])
        category_data_cache = df
        return df
    except Exception as e:
        raise Exception(f"❌ 엑셀 로드 중 오류 발생: {e}")

# ✅ 텍스트 정규화 함수 (유니코드 NFC 변환 및 모든 공백 제거)
def deep_normalize(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize('NFC', text)
    invisible_chars = ["\u00A0", "\u200B", "\u2006", "\u202F"]
    for ch in invisible_chars:
        text = text.replace(ch, "")
    # 스페이스, 탭, 개행 등 모든 공백 제거
    return ''.join(text.split())

# ✅ 추천 시스템 함수 (비동기)
async def recommend_best_cat3(member_id):
    print(f"\n\n✅ 추천 요청된 member_id: {member_id}")

    # 1. 사용자 클릭 기록과 선호도 조회
    user_clicks = await get_user_click_history(member_id)
    print(f"🟡 user_clicks: {user_clicks}")
    user_preference = await get_user_preference(member_id)
    print(f"🟢 user_preference (소분류 선호): {user_preference}")

    # 2. 엑셀 데이터 로딩
    category_data = load_category_data()

    # 정규화된 사용자 선호도 (이제 '소분류'가 저장되어 있다고 가정)
    norm_user_pref = deep_normalize(user_preference) if user_preference else None
    print(f"🔍 정규화된 사용자 선호도: {norm_user_pref}")

    # ==================== [1] 클릭 기록 + 소분류 Fuzzy 매칭 ====================
    if user_clicks and norm_user_pref:
        # 클릭 기록을 DataFrame으로 변환
        clicks_df = pd.DataFrame(user_clicks)

        # DB에서 가져온 cat3와 엑셀의 cat3를 매칭시켜 merge
        merged_df = clicks_df.merge(category_data, on="cat3", how="left", suffixes=("_click", "_excel"))

        # 엑셀의 소분류 컬럼 정규화
        merged_df["소분류_norm"] = merged_df["소분류"].apply(lambda x: deep_normalize(x) if isinstance(x, str) else "")

        # 유사도 계산 (임계값 50 적용)
        merged_df["similarity"] = merged_df["소분류_norm"].apply(lambda x: fuzz.ratio(norm_user_pref, x))
        print("\n🔎 [Click Matching] 결과:")
        print(merged_df[["cat3", "소분류", "소분류_norm", "similarity"]])

        best_idx = merged_df["similarity"].idxmax()
        best_match_row = merged_df.loc[best_idx]
        if best_match_row["similarity"] >= 50:
            rec = {
                "cat3": best_match_row["cat3"],
                "대분류": best_match_row["대분류"],
                "중분류": best_match_row["중분류"],
                "소분류": best_match_row["소분류"]
            }
            print(f"🟣 추천 결과 (클릭 기록 기반, similarity={best_match_row['similarity']}): {rec}")
            return rec
        else:
            print(f"⚠️ 클릭 기록 기반 매칭 실패. 최고 similarity: {best_match_row['similarity']} (threshold=50)")

    # ==================== [2] fallback: 소분류 기반 Fuzzy 매칭 ====================
    if user_preference and norm_user_pref:
        # 엑셀 데이터를 복사해서 소분류 기준으로 유사도 비교
        data_copy = category_data.copy()
        data_copy["소분류_norm"] = data_copy["소분류"].apply(lambda x: deep_normalize(x) if isinstance(x, str) else "")
        data_copy["similarity"] = data_copy["소분류_norm"].apply(lambda x: fuzz.ratio(norm_user_pref, x))

        print("\n🔎 [Preference Matching] (소분류 기준) 결과:")
        print(data_copy[["cat3", "대분류", "중분류", "소분류", "소분류_norm", "similarity"]])

        best_idx = data_copy["similarity"].idxmax()
        best_match_row = data_copy.loc[best_idx]
        if best_match_row["similarity"] >= 50:
            rec = {
                "cat3": best_match_row["cat3"],
                "대분류": best_match_row["대분류"],
                "중분류": best_match_row["중분류"],
                "소분류": best_match_row["소분류"]
            }
            print(f"🟣 추천 결과 (Preference 기반, similarity={best_match_row['similarity']}): {rec}")
            return rec
        else:
            print(f"⚠️ Preference 기반 매칭 실패. 최고 similarity: {best_match_row['similarity']} (threshold=50)")

    # ==================== [3] 최종 fallback: 무작위 추천 ====================
    print("🟣 최종 fallback 추천 실행")
    fallback = category_data.sample(n=min(3, len(category_data)))[["cat3", "대분류", "중분류", "소분류"]].to_dict(orient="records")
    return fallback[0] if fallback else None

# ✅ FastAPI 추천 시스템 라우터
@app.get("/recommend/{member_id}")
async def get_recommendations(member_id: str):
    """
    GET /recommend/{member_id}
      1) 사용자의 preference(소분류 선호도) + 클릭 기록을 합쳐서 
         엑셀 데이터(소분류)와의 fuzzy 매칭을 진행
      2) 매칭 실패 시 fallback (소분류 기준 fuzzy 매칭 -> 무작위)
    """
    recommendation = await recommend_best_cat3(member_id)
    if not recommendation:
        raise HTTPException(status_code=404, detail="No recommendations found")
    return recommendation


# ✅ FastAPI 실행
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5000, reload=True)
