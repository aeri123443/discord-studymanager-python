import threading
from flask import Flask
import os
import asyncio
from datetime import datetime
import pytz
import discord
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from html2image import Html2Image
from dotenv import load_dotenv
import traceback

# ==========================================
# 1. 환경변수 및 상수 설정
# ==========================================
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID")) if os.getenv("CHANNEL_ID") else None
SPREADSHEET_KEY = os.getenv("SPREADSHEET_KEY")

# 서비스 계정 키 파일 경로 직접 사용
JSON_KEY_FILE = "credentials.json"

CURRENT_WEEK = 11  # 진행할 현재 주차

def get_current_week():
    global CURRENT_WEEK
    # KST (한국 표준시) 타임존
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst).date()
    
    # 1주차 기준일: 5월 24일
    base_date = datetime(2026, 5, 24).date()
    
    # 기준일로부터 지난 일수 계산
    days_diff = (now - base_date).days
    
    # 주차 계산 (7일 단위)
    CURRENT_WEEK = (days_diff // 7) + 1

# Render 포트 감지용 더미 웹 서버 구성
app = Flask(__name__)

@app.route('/')
def home():
    return "Discord Bot is running!"

def run_web_server():
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ==========================================
# 2. 봇 & 스케줄러 & html2image 초기화
# ==========================================
intents = discord.Intents.default()
intents.message_content = True  # MESSAGE CONTENT INTENT 필수
bot = commands.Bot(command_prefix="!", intents=intents)

scheduler = AsyncIOScheduler(timezone="Asia/Seoul")  # 한국 시간(KST) 기준

# Render/Linux 헤드리스 환경을 고려한 브라우저 플래그
# hti = Html2Image(
#     custom_flags=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]
# )

# ==========================================
# 3. 구글 시트 데이터 로드 (JSON 파일 사용)
# ==========================================
def fetch_sheet_data(sheet_title):
    scope = ["https://www.googleapis.com/auth/spreadsheets.readonly"]    
    creds = ServiceAccountCredentials.from_json_keyfile_name(JSON_KEY_FILE, scope)
    client = gspread.authorize(creds)
    
    # 시트 열기 및 해당 주차 탭 선택
    doc = client.open_by_key(SPREADSHEET_KEY)
    sheet = doc.worksheet(sheet_title)

    # 모든 셀 데이터를 2차원 리스트 형태로 가져옴
    rows = sheet.spreadsheet.values_get(f"'{sheet_title}'!C4:H8")['values']
    if not rows:
        return []
    
    # 처음 두 행을 헤더로 지정

    # DayDD -> DD
    day_headers = rows[0]
    for i, h in enumerate(day_headers):
        h = ''.join(list(h.strip())[3:])
        new_h = 'Day' + ('0' if len(h) == 2 else '') + h
        day_headers[i] = new_h

    # M/D -> MMDD
    date_headers = rows[1] 
    for i, h in enumerate(date_headers):
        date_list = list(h.strip().split('/'))
        date_list = [ x if len(x)==2 else '0'+x for x in date_list]
        date_headers[i] = ''.join(date_list)


    data = []

    # rows[2]: cs 면접 - 하드코딩
    # rows[3]: 코테 입문 - 과제 문항만 가져옴 (-로 시작)
    ro3 = []
    for cell in rows[3]:
        tmp = cell.split('\n')
        c_list = [t for t in tmp if t.startswith('-')]
        ro3.append(c_list)
    
    # rows[4]: 코테 실전 - 과제 문항만 가져옴 (-로 시작, 링크와 제목 분리))
    ro4 = []
    for cell in rows[4]:
        tmp = cell.split('\n')
        c_list = []

        for t in tmp:
            if not t.startswith('-'): continue

            name_date, link = t.split('#')
            d, name = name_date.strip('-').strip().split('번: ')
            c_list.append([d, name, link]) # 출제 일자, 타이틀, 링크

        ro4.append(c_list)

    data.append(ro3)
    data.append(ro4)

    return day_headers, date_headers, data

# ==========================================
# 4. 표 HTML -> PNG 이미지 변환 (해당 코드는 향후 수정)
# ==========================================
# def generate_schedule_image(day_headers, date_headers, data, output_filename="schedule.png"):
#     if not (day_headers and date_headers and data):
#         return None
    
#     headers = list(data[0].keys())
    
#     html_content = """
#     <html>
#     <head>
#         <style>
#             body { 
#                 font-family: 'NanumGothic', 'Arial', sans-serif; 
#                 padding: 20px; 
#                 background-color: #2f3136; 
#                 color: white; 
#             }
#             table { border-collapse: collapse; width: 100%; font-size: 16px; }
#             th, td { border: 1px solid #4f545c; padding: 12px; text-align: left; }
#             th { background-color: #5865f2; color: white; }
#             tr:nth-child(even) { background-color: #36393f; }
#         </style>
#     </head>
#     <body>
#         <table>
#             <thead>
#                 <tr>""" + "".join([f"<th>{h}</th>" for h in day_headers]) + """</tr>
#                 <tr>""" + "".join([f"<th>{h}</th>" for h in date_headers]) + """</tr>
#             </thead>
#             <tbody>
#     """

#     for row in data:
#         html_content += "<tr>" + "".join([f"<td>{row.get(h, '')}</td>" for h in headers]) + "</tr>"
        
#     html_content += """
#             </tbody>
#         </table>
#     </body>
#     </html>
#     """
    
#     hti.screenshot(html_str=html_content, save_as=output_filename, size=(800, 600))
#     return output_filename

# ==========================================
# 5. 주간 자동 실행 메인 로직
# ==========================================
async def weekly_task():
    global CURRENT_WEEK
    sheet_title = f"{CURRENT_WEEK}주차"

    # 디스코드 채널
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print(f"❌ 채널 ID {CHANNEL_ID}를 찾을 수 없습니다.")
        return

    try:
        print(f"🔍 [{sheet_title}] 구글 시트 데이터 로드 중...")
        # 1. 시트 데이터 가져오기
        day_headers, date_headers, data = fetch_sheet_data(sheet_title)

        # 2. 이미지 생성
        # image_path = generate_schedule_image(day_headers, date_headers, data)
        
        # 3. 채널 공지 및 이미지 파일(향후) 업로드 
        message_content = (
            f"## :closed_book: {CURRENT_WEEK}주차 과제" 
            "\n이번 주 스터디 일정입니다. 아래 스레드에서 일자별 인증을 진행해주세요."
            "\n마지막까지 화이팅! :muscle: :muscle:"
            "\n\n프로그래머스 Tip: https://school.programmers.co.kr/learn/courses/30/lessons/00000"
            "\n위의 주소에서 00000 부분에 문제 번호를 입력하면 해당 문제 링크로 이동합니다!"
        )
        # file = discord.File(image_path, filename="schedule.png")
        
        print(f"🔍 디스코드 채널에 공지 메시지 전송 중...")
        print(f"message_content: {message_content}")

        await channel.send(content=message_content)
        
        # 4. 월~금 5개 스레드 일괄 생성
        print(f"🔍 디스코드 채널에 스레드 생성 중...")
        for idx in range(5):
            title = day_headers[idx] + ' | ' + date_headers[idx]
            msg = (
                "-- -- -- -- -- -- -- -- -- -- -- -- -- -- --\n"
                "## :speaking_head:  CS 면접\n"
                "\n랜덤 5문제 답변\n답변을 녹음해보고\n본인의 습관을 점검해보세요.\n"
                "\n"
                "**과제:**\n"
                "> 정리했던 질문을 보고 답변\n"
                "> 답변 내용을 녹음해보고 내 말투 점검해보기\n"
                "> 답변하지 못한 항목을 체크 후 복습하기\n"
                "녹음 내역 캡처\n"
                "\n"
                "-- -- -- -- -- -- -- -- -- -- -- -- -- -- --\n"
                "## :beginner: 코테-입문\n"
                "\n"
                "**프로그래머스 lv3 랜덤 3문제**\n"
                "\n"
                "**과제: **\n"
                "> 문제 코드 캡처 및\n" 
                "> 정답 혹은 몇 개 TC 통과했는지 화면 캡처\n"
                f"{'\n'.join(data[0][idx])}"
                "\n"

                "-- -- -- -- -- -- -- -- -- -- -- -- -- -- --\n"
                "## :diamond_shape_with_a_dot_inside:  코테-실전\n"
                "\n"
                "**기업 기출 문제 1회**\n"
                "삼성, 카카오 등\n"
                "원하는 기업의 기출문제 풀이\n"
                "(타 기업 문제도 ok)\n"
                "\n"
                "**과제:**\n"
                "> 문제 코드 캡처 및\n"
                "> 정답 혹은 몇 개 TC 통과했는지 화면 캡처\n"
                f"{'- ' + data[1][idx][0][0] + '번: [' + data[1][idx][0][1] + '](' + data[1][idx][0][2] + ')'}"
                "\n" 
                "-- -- -- -- -- -- -- -- -- -- -- -- -- -- --"
            )

            thread = await channel.create_thread(
                name=title,
                type=discord.ChannelType.public_thread
            )
            
            await thread.send(msg)

        # 토요일(복습) 스레드 별도 생성
        idx = 5
        title = day_headers[idx] + ' | ' + date_headers[idx]
        msg = (
            "-- -- -- -- -- -- -- -- -- -- -- -- -- -- --\n"
            "## :speaking_head:  CS 면접\n"
            "\n**전체 내용 복습**\n"
            "\n"
            "**과제:**\n"
            "> 정리했던 질문을 보고 답변\n"
            "> 답변 내용을 녹음해보고 내 말투 점검해보기\n"
            "> 답변하지 못한 항목을 체크 후 복습하기\n"
            "녹음 내역 캡처\n"
            "\n"
            "-- -- -- -- -- -- -- -- -- -- -- -- -- -- --\n"
            "## :beginner: 코테-입문\n"
            "\n"
            "**학습 내용 복습**\n"
            "\n"
            "**과제: **\n"
            "틀리거나, 해답을 찾아보거나, 시간이 가장 오래 걸린 문제에 대하여 다시 풀어보고 정답 화면 캡처하기\n" 
            "*(1개 이상, 틀렸던 문제 전부)*\n"
            "\n"

            "-- -- -- -- -- -- -- -- -- -- -- -- -- -- --\n"
            "## :diamond_shape_with_a_dot_inside:  코테-실전\n"
            "\n"
            "**학습 내용 복습**\n"
            "\n"
            "틀리거나, 해답을 찾아보거나, 시간이 가장 오래 걸린 문제에 대하여 다시 풀어보고 정답 화면 캡처하기\n" 
            "*(1개 이상, 틀렸던 문제 전부)*\n"
            "\n"   
            "-- -- -- -- -- -- -- -- -- -- -- -- -- -- --"
        )

        thread = await channel.create_thread(
            name=title,
            type=discord.ChannelType.public_thread
        )
        
        await thread.send(msg)
        print(f"[{sheet_title}] 공지 작성 및 스레드 생성 완료!")
        CURRENT_WEEK += 1
        
    except Exception as e:
        print(f"작업 실행 중 오류 발생: {e}")

# ==========================================
# 6. 이벤트 및 스케줄러 등록
# ==========================================
@bot.event
async def on_ready():
    get_current_week()
    print(f"성공적으로 로그인했습니다: {bot.user.name}")
    
    # 매주 일요일 12:00 (KST) 정시 실행
    scheduler.add_job(
        weekly_task,
        CronTrigger(day_of_week="sun", hour=12, minute=0, timezone="Asia/Seoul")
    )
    scheduler.start()

    print("스케줄러가 활성화되었습니다.")

# 수동 테스트용 명령어 (!run_task)
@bot.command()
async def run_task(ctx):
    get_current_week()
    print(f"✅ {CURRENT_WEEK}주차 run_task 호출")
    await ctx.send("테스트 실행을 시작합니다.")
    try:
        print("🔍 weekly_task 실행 시작...")
        await weekly_task()
        print("✅ weekly_task 완료!")
    except Exception as e:
        print(f"❌ [run_task 커맨드 실행 중 에러 발생]: {e}")
        traceback.print_exc()
        await ctx.send(f"❌ 실행 중 에러가 발생했습니다: `{e}`")

if __name__ == "__main__":
    # 백그라운드 스레드로 더미 웹 서버 실행
    threading.Thread(target=run_web_server, daemon=True).start()
    
    # 디스코드 봇 실행
    bot.run(DISCORD_TOKEN)
