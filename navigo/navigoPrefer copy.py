from fastapi import FastAPI, HTTPException
import pymysql
import pandas as pd
from rapidfuzz import fuzz
import unicodedata
import os
import math  # NaN 검사용

app = FastAPI(docs_url="/docs", openapi_url="/openapi.json")

EXCEL_FILE_PATH = "data/한국관광공사_국문_서비스분류코드_v4.2_gs.xlsx"
category_data_cache = None

def get_connection():
    return pymysql.connect(
        host="192.168.0.6",
        user="sion",
        password="00000000",
        database="navi_go",
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor
    )

async def get_user_preference(member_id):
    connection = get_connection()
    cursor = connection.cursor()
    sql = "SELECT prefer_purpose FROM preference WHERE member_id = %s"
    cursor.execute(sql, (member_id,))
    result = cursor.fetchone()
    connection.close()
    return result["prefer_purpose"] if result else None

async def get_user_click_history(member_id):
    connection = get_connection()
    cursor = connection.cursor()
    # 실제 테이블에서는 'clicked_at' 컬럼으로 되어 있음
    sql = "SELECT contentid, cat1, cat2, cat3, clicked_at FROM user_activity WHERE memberid = %s"
    cursor.execute(sql, (member_id,))
    result = cursor.fetchall()
    connection.close()
    return result

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
        df = pd.read_excel(xls, sheet_name=sheet_name, dtype=str)
        expected_columns = ["contenttypeid", "cat1", "cat2", "cat3", "대분류", "중분류", "소분류"]
        df.columns = expected_columns[:len(df.columns)]
        df = df.dropna(how="all").reset_index(drop=True)
        df["소분류"] = df["소분류"].astype(str).str.strip()
        print("✅ [엑셀 로딩 완료] 데이터 개수:", df.shape[0])
        category_data_cache = df
        return df
    except Exception as e:
        raise Exception(f"❌ 엑셀 로드 중 오류 발생: {e}")

def deep_normalize(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize('NFC', text)
    for ch in ["\u00A0", "\u200B", "\u2006", "\u202F"]:
        text = text.replace(ch, "")
    return ''.join(text.split())

def sanitize_rec(rec: dict) -> dict:
    # NaN (float('nan')) 검사를 통해 NaN인 값은 None으로 치환
    for k, v in rec.items():
        if isinstance(v, float) and math.isnan(v):
            rec[k] = None
    return rec

def fallback_recommendation(category_data, norm_user_pref):
    data_copy = category_data.copy()
    data_copy["소분류_norm"] = data_copy["소분류"].apply(lambda x: deep_normalize(x))
    data_copy["similarity"] = data_copy["소분류_norm"].apply(lambda x: fuzz.ratio(norm_user_pref, x) if norm_user_pref else 0)
    print("\n🔎 [Fallback Matching] 결과:")
    print(data_copy[["cat3", "대분류", "중분류", "소분류", "similarity"]])
    if not data_copy.empty:
        best_idx = data_copy["similarity"].idxmax()
        best_match = data_copy.loc[best_idx]
        if best_match["similarity"] >= 60:
            rec = {
                "cat3": best_match["cat3"],
                "대분류": best_match["대분류"],
                "중분류": best_match["중분류"],
                "소분류": best_match["소분류"],
                "similarity": float(best_match["similarity"])
            }
            rec = sanitize_rec(rec)
            print(f"🟣 Fallback 추천 결과: {rec}")
            return rec
    fallback = category_data.sample(n=min(3, len(category_data)))[["cat3", "대분류", "중분류", "소분류"]].to_dict(orient="records")
    rec = fallback[0] if fallback else None
    rec = sanitize_rec(rec) if rec else None
    print(f"🟣 최종 무작위 fallback 추천: {rec}")
    return rec

# 추천 로직: 클릭 데이터가 없으면 선호도 기반 추천, 클릭 데이터가 있으면 최신 3건을 기준으로
# 빈도수 기반 후보를 선정하고, 빈도 tie 시에만 사용자 선호도를 활용하여 tie-break
async def recommend_best_cat3(member_id):
    print(f"\n\n✅ 추천 요청된 member_id: {member_id}")
    user_clicks = await get_user_click_history(member_id)
    user_preference = await get_user_preference(member_id)
    print(f"🟢 user_preference (소분류 선호): {user_preference}")

    category_data = load_category_data()
    norm_user_pref = deep_normalize(user_preference) if user_preference else None
    print(f"🔍 정규화된 사용자 선호도: {norm_user_pref}")

    import pandas as pd
    # 클릭 데이터가 없으면 선호도 기반 fallback 추천 사용
    if not user_clicks:
        print("클릭 데이터가 없으므로 선호도 기반 추천 진행")
        return fallback_recommendation(category_data, norm_user_pref)

    # 클릭 데이터가 있을 때: 최신 3건 추출 (clicked_at 기준)
    clicks_df = pd.DataFrame(user_clicks)
    if "clicked_at" in clicks_df.columns:
        clicks_df["clicked_at"] = pd.to_datetime(clicks_df["clicked_at"])
        clicks_df = clicks_df.sort_values(by="clicked_at", ascending=False)
        latest_clicks = clicks_df.head(3)
    else:
        latest_clicks = clicks_df

    if latest_clicks.empty:
        return fallback_recommendation(category_data, norm_user_pref)

    # Step 1: 최신 클릭 기록에서 cat3 빈도수 계산
    freq = latest_clicks["cat3"].value_counts()
    print("클릭 기록 빈도수:\n", freq)
    if freq.empty:
        return fallback_recommendation(category_data, norm_user_pref)
    
    # 빈도수가 유일하면 그 후보 사용
    if len(freq) == 1:
        selected_candidate = freq.index[0]
        print(f"유일한 후보: {selected_candidate}")
    else:
        max_freq = freq.max()
        candidate_list = freq[freq == max_freq].index.tolist()
        print(f"빈도 tie 후보들: {candidate_list}")
        # Tie-break: 후보 목록 중, tie 상황에서는 사용자 선호도와 일치하는 후보 우선
        if len(candidate_list) > 1:
            category_data["소분류_norm"] = category_data["소분류"].apply(lambda x: deep_normalize(x))
            category_data["pref_similarity"] = category_data["소분류_norm"].apply(lambda x: fuzz.ratio(norm_user_pref, x) if norm_user_pref else 0)
            best_idx_pref = category_data["pref_similarity"].idxmax()
            preferred_cat3 = category_data.loc[best_idx_pref, "cat3"]
            print(f"선호도 기반 추천 cat3: {preferred_cat3}")
            if preferred_cat3 in candidate_list:
                selected_candidate = preferred_cat3
                print(f"선호도 기반 후보 {preferred_cat3} 선택 (tie-break)")
            else:
                # tie 후보들 중 추가 기준 없이 후보별 소분류 유사도 최대값을 비교하여 선택
                candidate_scores = {}
                for candidate in candidate_list:
                    candidate_df = category_data[category_data["cat3"] == candidate].copy()
                    candidate_df["소분류_norm"] = candidate_df["소분류"].apply(lambda x: deep_normalize(x))
                    candidate_scores[candidate] = candidate_df["소분류_norm"].apply(lambda x: fuzz.ratio(norm_user_pref, x)).max() if not candidate_df.empty else 0
                    print(f"Candidate {candidate} 유사도: {candidate_scores[candidate]}")
                selected_candidate = max(candidate_scores, key=candidate_scores.get)
                print(f"최종 tie-break 후보: {selected_candidate}")
        else:
            selected_candidate = candidate_list[0]
            print(f"유일 후보 선택: {selected_candidate}")

    # Step 2: 선택된 후보에 해당하는 Excel 데이터에서 해당 cat3 정보를 그대로 추천
    candidate_df = category_data[category_data["cat3"] == selected_candidate].copy()
    if not candidate_df.empty:
        rec = candidate_df.iloc[0].to_dict()
        rec["source"] = "click 기반 추천"
        rec = sanitize_rec(rec)
        print(f"🟣 최종 추천 결과 (클릭 데이터 기반): {rec}")
        return rec

    return fallback_recommendation(category_data, norm_user_pref)

@app.get("/recommend/{member_id}")
async def get_recommendations(member_id: str):
    recommendation = await recommend_best_cat3(member_id)
    if not recommendation:
        raise HTTPException(status_code=404, detail="No recommendations found")
    return recommendation

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5000, reload=True)