# discord-studymanager-python
스터디 관리 디스코드 봇 만들기 - 파이썬 전환

### 🛠 Tech Stack & Libraries

| 라이브러리 | 역할 | 선정 이유 |
| :--- | :--- | :--- |
| **`discord.py`** | 디스코드 봇 제어 및 이벤트 처리 | 파이썬 표준 디스코드 라이브러리로, 비동기(`async/await`) 방식을 통해 공지 메시지 전송, 이미지 첨부, 디스코드 스레드 생성 등을 안정적으로 처리 |
| **`gspread`** | 구글 스프레드시트 데이터 조작 | Google Sheets API를 파이썬 모듈로 래핑하여 주차별 워크시트 조회 및 데이터 추출을 직관적인 코드로 작성 가능 |
| **`oauth2client`** | Google API OAuth 2.0 인증 | 서비스 계정 키(`credentials.json`)를 사용해 별도 로그인 없이 구글 시트에 안전하게 접근할 수 있는 권한 제공 |
| **`apscheduler`** | 백그라운드 작업 스케줄링 | 한국 시간(KST) 기준으로 특정 날짜 및 특정 시각의 규칙(`CronTrigger`) 수행에 용이 |
| **`html2image`** | HTML/CSS → 이미지(PNG) 변환 | 구글 시트 데이터를 HTML 표로 바꾼 뒤 헤드리스 브라우저를 이용해 공지용 스크린샷 이미지로 고화질 렌더링 |
