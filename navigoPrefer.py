import time
from fastapi import FastAPI, HTTPException, Query
import pymysql
import pandas as pd
from rapidfuzz import fuzz
import unicodedata
import os
import requests
from typing import List, Optional
import random
import urllib.parse
import json
from konlpy.tag import Okt

app = FastAPI(docs_url="/docs", openapi_url="/openapi.json")

EXCEL_FILE_PATH = "data/한국관광공사_국문_서비스분류코드_v4.2_gs.xlsx"
category_data_cache = None
SERVICE_KEY = "zEp9kLeLZiXElh6mddTl2DXHIl44C4brxSyQojUBO6zjiy25apv9Dvh00sygk%2BKzMuXzMv3zKpoylWiGbVlCLA%3D%3D"
SERVICE_KEY_DECODE = "zEp9kLeLZiXElh6mddTl2DXHIl44C4brxSyQojUBO6zjiy25apv9Dvh00sygk+KzMuXzMv3zKpoylWiGbVlCLA=="

# KoNLPy의 Okt 인스턴스 생성 (한국어 형태소 분석용)
okt = Okt()

def extract_keyword_korean(text: str) -> str:
    """
    소분류 문자열에서 핵심 명사를 추출하여 반환합니다.
    예) "일반축제" -> "축제", "야영장,오토캠핑장" -> 둘 중 길이가 긴 명사(또는 첫 번째 명사)
    """
    nouns = okt.nouns(text)
    if nouns:
        # 가장 긴 명사를 반환 (필요에 따라 다른 기준을 적용할 수 있음)
        return max(nouns, key=len)
    return text

def get_connection():
    return pymysql.connect(
        host="localhost",
        user="root",
        password="11111111",
        database="navi_go",
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor
    )

async def get_user_preference(member_id: str) -> str:
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            sql = "SELECT prefer_purpose FROM preference WHERE member_id = %s"
            cursor.execute(sql, (member_id,))
            result = cursor.fetchone()
            print(f"[User Preference] member_id={member_id}, result={result}")
            return result["prefer_purpose"] if result else None
    finally:
        connection.close()

async def get_user_click_history(member_id: str) -> List[dict]:
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            sql = "SELECT contentid, cat1, cat2, cat3, title, clicked_at FROM user_activity WHERE memberid = %s"
            cursor.execute(sql, (member_id,))
            results = cursor.fetchall()
            print(f"[Click History] member_id={member_id}, count={len(results)}")
            return results
    finally:
        connection.close()

def load_category_data() -> pd.DataFrame:
    global category_data_cache
    if category_data_cache is not None:
        return category_data_cache
    if not os.path.exists(EXCEL_FILE_PATH):
        raise FileNotFoundError(f"❌ 엑셀 파일이 존재하지 않습니다: {EXCEL_FILE_PATH}")
    print("Loading Excel file...")
    try:
        xls = pd.ExcelFile(EXCEL_FILE_PATH, engine="openpyxl")
        sheet_name = "시트1" if "시트1" in xls.sheet_names else xls.sheet_names[0]
        df = pd.read_excel(xls, sheet_name=sheet_name, dtype=str)
        expected_columns = ["contenttypeid", "cat1", "cat2", "cat3", "대분류", "중분류", "소분류"]
        df.columns = expected_columns[:len(df.columns)]
        df = df.dropna(how="all").reset_index(drop=True)
        df["소분류"] = df["소분류"].astype(str).str.strip()
        print(f"Excel loaded: {df.shape[0]} rows")
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

def fetch_travel_destinations_area(cat3: str, exclude_contentids: Optional[List[str]] = None) -> List[dict]:
    numOfRows = 20
    api_url = (
        f"http://apis.data.go.kr/B551011/KorService1/areaBasedList1?"
        f"serviceKey={SERVICE_KEY}&MobileOS=ETC&MobileApp=AppTest&_type=json"
        f"&listYN=Y&arrange=Q&numOfRows={numOfRows}&cat3={cat3}"
    )
    print(f"[Fetch Area] cat3={cat3}, numOfRows={numOfRows}")
    response = requests.get(api_url)
    if response.status_code == 200:
        try:
            data = response.json()
        except Exception as e:
            print(f"[Fetch Area] JSON parsing error for cat3={cat3}: {e}, response: {response.text}")
            return []
        if not isinstance(data, dict):
            print(f"[Fetch Area] Expected dict but got {type(data)} for cat3={cat3}, data: {data}")
            return []
        items = data.get('response', {}).get('body', {}).get('items', {}).get('item', [])
        if exclude_contentids:
            items = [item for item in items if item['contentid'] not in exclude_contentids]
        print(f"[Fetch Area] cat3={cat3}, fetched {len(items)} items")
        return items
    print(f"[Fetch Area] Failed to fetch cat3={cat3}, status_code={response.status_code}")
    return []

def fetch_travel_destinations_keyword(subcategory: str, exclude_contentids: Optional[List[str]] = None) -> List[dict]:
    numOfRows = 20
    encoded_subcategory = urllib.parse.quote(subcategory, safe="")
    api_url = (
        f"http://apis.data.go.kr/B551011/KorService1/searchKeyword1?"
        f"serviceKey={SERVICE_KEY}&MobileOS=ETC&MobileApp=AppTest&_type=json"
        f"&listYN=Y&arrange=C&numOfRows={numOfRows}&keyword={encoded_subcategory}"
    )
    print(f"[Fetch Keyword] subcategory={subcategory} (encoded: {encoded_subcategory}), numOfRows={numOfRows}")
    print("keyword api url: " + api_url)
    response = requests.get(api_url)
    if response.status_code == 200:
        content_type = response.headers.get('Content-Type', '')
        if 'application/json' not in content_type:
            print(f"[Fetch Keyword] Unexpected Content-Type: {content_type}. Response: {response.text}")
            return []
        try:
            data = response.json()
        except Exception as e:
            print(f"[Fetch Keyword] Error parsing JSON for subcategory={subcategory}: {e}, response: {response.text}")
            return []
        # items가 빈 문자열일 경우 빈 리스트로 처리
        items_obj = data.get('response', {}).get('body', {}).get('items', "")
        if not isinstance(items_obj, dict):
            print(f"[Fetch Keyword] No valid items found for subcategory={subcategory}")
            items = []
        else:
            items = items_obj.get('item', [])
            if not isinstance(items, list):
                items = [items]  # 단일 항목인 경우 리스트로 변환
        if exclude_contentids:
            items = [item for item in items if item.get('contentid') not in exclude_contentids]
        print(f"[Fetch Keyword] subcategory={subcategory}, fetched {len(items)} items")
        return items
    print(f"[Fetch Keyword] Failed to fetch subcategory={subcategory}, status_code={response.status_code}")
    return []


async def recommend_travel_destinations(member_id: str, exclude_contentids: Optional[List[str]] = None) -> List[dict]:
    user_clicks = await get_user_click_history(member_id)
    user_preference = await get_user_preference(member_id)
    category_data = load_category_data()

    if not user_clicks:
        norm_user_pref = deep_normalize(user_preference) if user_preference else ""
        category_data["소분류_norm"] = category_data["소분류"].apply(deep_normalize)
        category_data["similarity"] = category_data["소분류_norm"].apply(lambda x: fuzz.ratio(norm_user_pref, x))
        top_cat3 = category_data.nlargest(5, 'similarity')['cat3'].tolist()
        print(f"[No Clicks] Top cat3 based on similarity: {top_cat3}")
    else:
        clicks_df = pd.DataFrame(user_clicks)
        clicks_df["clicked_at"] = pd.to_datetime(clicks_df["clicked_at"])
        clicks_df = clicks_df.sort_values(by="clicked_at", ascending=False)
        clicks_df['weight'] = clicks_df['clicked_at'].rank(ascending=False).apply(lambda x: 0.9 ** (x - 1))
        cat3_weights = clicks_df.groupby('cat3')['weight'].sum().reset_index()

        if user_preference:
            norm_user_pref = deep_normalize(user_preference)
            category_data["소분류_norm"] = category_data["소분류"].apply(deep_normalize)
            category_data["pref_similarity"] = category_data["소분류_norm"].apply(lambda x: fuzz.ratio(norm_user_pref, x))
            cat3_weights = cat3_weights.merge(category_data[['cat3', 'pref_similarity']], on='cat3', how='left')
            cat3_weights['pref_similarity'] = cat3_weights['pref_similarity'].fillna(0)
            cat3_weights['score'] = cat3_weights['weight'] + cat3_weights['pref_similarity'] / 100
        else:
            cat3_weights['score'] = cat3_weights['weight']

        clicked_titles = clicks_df['title'].unique().tolist()
        norm_clicked_titles = [deep_normalize(title) for title in clicked_titles]
        category_data["title_similarity"] = category_data["소분류"].apply(
            lambda x: max([fuzz.ratio(deep_normalize(x), norm_title) for norm_title in norm_clicked_titles], default=0)
        )
        cat3_title_similarity = category_data.groupby('cat3')['title_similarity'].mean().reset_index()
        cat3_weights = cat3_weights.merge(cat3_title_similarity, on='cat3', how='left')
        cat3_weights['score'] = cat3_weights['score'] + cat3_weights['title_similarity'] / 100

        top_cat3 = cat3_weights.nlargest(5, 'score')['cat3'].tolist()
        print(f"[With Clicks] Top cat3 based on combined score: {top_cat3}")

    # 생성된 Excel DataFrame에서 cat3 -> 소분류 매핑 생성
    mapping = category_data.set_index("cat3")["소분류"].to_dict()

    travel_destinations = []
    for cat3 in top_cat3:
        # area API는 cat3 코드를 그대로 사용
        items_area = fetch_travel_destinations_area(cat3, exclude_contentids)
        travel_destinations.extend(items_area)
        # 키워드 API는 소분류(실제 한국어 키워드)를 사용.
        subcategory = mapping.get(cat3, cat3)
        # 만약 소분류 값에 쉼표가 있다면 첫 번째 항목만 사용
        if ',' in subcategory:
            subcategory = subcategory.split(',')[0].strip()
        # KoNLPy를 사용해 소분류에서 핵심 명사를 추출
        refined_subcategory = extract_keyword_korean(subcategory)
        items_keyword = fetch_travel_destinations_keyword(refined_subcategory, exclude_contentids)
        travel_destinations.extend(items_keyword)
        print(f"[For cat3 {cat3}] area items: {len(items_area)}, keyword items (for refined subcategory '{refined_subcategory}'): {len(items_keyword)}")

    unique_destinations = {item['contentid']: item for item in travel_destinations}.values()
    unique_destinations = list(unique_destinations)
    print(f"Total unique recommendations before shuffling: {len(unique_destinations)}")
    return unique_destinations

@app.get("/recommend/{member_id}")
async def get_recommendations(member_id: str,
                              exclude: Optional[str] = None,
                              page: int = Query(1, ge=1),
                              refresh: Optional[bool] = Query(False),
                              seed: Optional[int] = Query(None)):
    exclude_contentids = exclude.split(',') if exclude else None
    recommendations = await recommend_travel_destinations(member_id, exclude_contentids)
    if not recommendations:
        raise HTTPException(status_code=404, detail="No recommendations found")
    per_page = 3
    if refresh or seed is None:
        seed = int(time.time() * 1000)
    print(f"Total recommendations: {len(recommendations)} before shuffling")
    rnd = random.Random(seed)
    rnd.shuffle(recommendations)
    start = (page - 1) * per_page
    end = start + per_page
    paged_recommendations = recommendations[start:end]
    print(f"Returning page {page} with seed {seed} and {len(paged_recommendations)} recommendations")
    return {"seed": seed, "page": page, "recommendations": paged_recommendations}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5000, reload=True)