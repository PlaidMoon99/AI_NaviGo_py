import subprocess
import sys
import os

# 현재 가상 환경의 Python 실행 경로 가져오기
venv_python = os.path.join(sys.prefix, "Scripts", "python.exe")

# 실행할 서버 리스트 (명확한 Python 경로 사용)
servers = [
    ["uvicorn", "navigoPrefer:app", "--host", "127.0.0.1", "--port", "5000", "--reload"],  # FastAPI 실행
    [venv_python, "gemini_flask.py"],  # Flask 실행
    ["uvicorn", "image:app", "--host", "127.0.0.1", "--port", "8000", "--reload"],  # image.py를 FastAPI로 실행
    ["uvicorn", "main:app", "--host", "127.0.0.1", "--port", "7373", "--reload"],
    ["uvicorn", "AI_planner:app", "--host", "127.0.0.1", "--port", "4000", "--reload"]
]


# 프로세스를 저장할 리스트
processes = []

try:
    for server in servers:
        print(f"🚀 실행 중: {' '.join(server)}")
        process = subprocess.Popen(server)
        processes.append(process)

    # 모든 프로세스가 종료될 때까지 대기
    for process in processes:
        process.wait()

except KeyboardInterrupt:
    print("\n⛔ 종료 중...")
    for process in processes:
        process.terminate()
