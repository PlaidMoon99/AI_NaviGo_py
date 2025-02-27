from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import re
import openai
import json

app = Flask(__name__)
CORS(app)

# Gemini API 설정
genai.configure(api_key="AIzaSyDgzsS6mn3ozqSYbfwwsC-21uD_BPniIpg")
model = genai.GenerativeModel('gemini-2.0-flash')
chat = model.start_chat(history=[])

@app.route('/', methods=['POST'])
def chat_response():
    if request.method == 'POST':
        try:
            data = request.get_json()
            user_message = data.get('message')

            if not user_message:
                return jsonify({"error": "메시지가 없습니다"}), 400

            # "여행 일정"이 포함된 경우, 포맷된 응답 요청
            if "여행 일정" in user_message:
                prompt = """
                여행 일정을 보기 좋게 정리해서 제공해줘.
                **아래 형식을 반드시 따라야 해.**  
                - **굵은 글씨**를 사용해야 하고,  
                - 개행과 들여쓰기를 적용해야 해.  
                - "1일차", "2일차" 같은 형식이 유지되어야 해.  

                ---  
                **1일차: 부산 도착 및 해운대**  
                - **체크인 및 휴식**: 부산에 도착 후 숙소에 체크인하고 잠시 휴식.  
                - **해운대 해수욕장**: 해운대 해변을 방문하여 바다를 즐기고, 해변 산책을 하세요.  
                - **더베이 101**: 저녁에는 더베이 101에서 멋진 야경을 감상하고, 해산물 레스토랑에서 석식.  

                **2일차: 문화 탐방**  
                - **부산타워**: 아침에 부산타워를 방문하여 도시 전경을 감상합니다.  
                - **감천문화마을**: 감천문화마을을 탐방하며 독특한 벽화와 아기자기한 집들을 즐기세요.  
                - **자갈치 시장**: 점심으로 자갈치 시장에서 신선한 해산물을 맛보세요.  
                - **광안리 해변**: 저녁에는 광안리 해변에서 석양을 바라보며 여유로운 시간을 보내세요.  

                **3일차: 자연과 역사**  
                - **태종대**: 오전에는 태종대를 방문하여 자연경관과 등대를 즐기세요.  
                - **부산역 주변 탐방**: 부산역 근처에서 기념품 쇼핑 및 간단한 점심.  
                - **자유시간 및 귀가**: 마지막으로 자유롭게 시간을 보내고, 귀가 준비.  

                이 일정이 마음에 드시나요? 또는 다른 활동을 원하신다면 말씀해 주세요!  
                ---  
                위와 같은 형식으로 응답해줘.
                """

                response = chat.send_message(prompt)
                return jsonify({"response": response.text})

            # 일반 메시지 처리
            response = chat.send_message(user_message)
            return jsonify({"response": response.text})

        except Exception as e:
            return jsonify({"error": str(e)}), 500
        
# def format_response(text):
#     """
#     Gemini 응답을 보기 좋게 변환
#     """
#     text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)  # **텍스트** → 텍스트 (굵은 글씨 제거)
#     text = text.replace("\n", "<br>")  # 개행을 <br> 태그로 변환
#     text = re.sub(r"- (.+)", r"• \1", text)  # 리스트(- item)를 점 리스트(• item)로 변환

#     return text


if __name__ == '__main__':
    app.run(port=8501, debug=True)