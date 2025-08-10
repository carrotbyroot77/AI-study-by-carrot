
# Weather-MCP in Python
*  *A tiny Weather MCP built with FastMCP and Open-Meteo, written in Python.*

로컬 FastMCP 서버에서 현재 날씨를 가져와 **규칙 기반 조언**을 생성하고, <br>
선택적으로 **OpenAI Responses API(chatgpt 4o mini)로 자연어 다듬기**까지 해 주는 미니 프로젝트이다. <br>
Windows + PowerShell 기준 예시를 포함한다. <br>

---

# 실습 작업
* **vs code와 python 그리고 powershell(관리자)** 으로 작업했다
* `weather_server.py` 와 `advisor.py` 파일이 핵심 파일이다. 나머지는 test나 부수적인 파일


## ✔ 사전준비
* **powershell 사용**

### 1) 가상환경 및 서버 준비 (한 번만)

```powershell
# 프로젝트 폴더로
cd C:\Users\이노메랩\weather-mcp

# 가상환경 생성 + 활성화
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# (만약 스크립트 실행 정책 에러가 나면)
# Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# 패키지 설치/업데이트
python -m pip install --upgrade pip
pip install fastmcp httpx python-dateutil requests openai
```

#### (옵션) AI 다듬기 쓰려면 API 키 설정

```powershell
# 현재 창에서만
$env:OPENAI_API_KEY = "여기에_키 입력"

# 영구 저장(사용자 변수, 새 창 열어야 반영)
[Environment]::SetEnvironmentVariable("OPENAI_API_KEY","여기에_키 입력","User")
```

<br>
<br>

### 2) 서버 가동

```powershell
# 가상환경이 켜져 있는 상태에서
python weather_server.py
```

* 정상: 배너가 뜨고 `http://127.0.0.1:8000/mcp/` 대기

<br>
<br>

### 3) 서버 동작 테스트 (둘 중 편한 걸로)

#### 방법 A) PowerShell로 바로 호출

```powershell
$headers = @{
  "Content-Type" = "application/json"
  "Accept"       = "application/json, text/event-stream"
}
$body = @{
  jsonrpc = "2.0"
  id      = "1"
  method  = "tools/call"
  params  = @{ name = "weather_now"; arguments = @{ city = "Seoul" } }
} | ConvertTo-Json -Compress

Invoke-WebRequest -Uri "http://127.0.0.1:8000/mcp/" -Method POST -Headers $headers -Body $body | Select -Expand Content
```

#### 방법 B) 테스트 스크립트

```powershell
python mcp_test.py
```

<br>
<br>

### 4) 어드바이저 실행 (규칙 기반/AI 다듬기)

```powershell
# 규칙 기반 한 줄 조언
python advisor.py Seoul

# AI 다듬기(친근 톤, 1문장)
python advisor.py Seoul --ai --tone friendly --detail short
```

<br>
<br>

### 5) 자주 겪는 오류 & 빠른 해결

* **WinError 10048** (포트 충돌):
  8000 포트를 쓰는 프로세스를 종료하거나 포트를 바꿔 실행.

  ```powershell
  Get-NetTCPConnection -LocalPort 8000 | Select OwningProcess,State
  Stop-Process -Id <PID> -Force
  ```

  또는 `weather_server.py`에서 `port=8010`으로 변경 → `advisor.py`/`mcp_test.py`의 `MCP_URL`도 `8010`으로 맞추기.

* **406 Not Acceptable**:
  클라이언트 요청에 `Accept: application/json, text/event-stream`를 꼭 포함하세요.
  JSON-RPC는 **`method: "tools/call"`** + **`params: { name, arguments }`** 형태여야 합니다.

* **AI 다듬기에서 401/권한 문제**:
  `OPENAI_API_KEY` 환경변수 설정/철자 확인, 새 터미널 열어 재시도.
<br>
<br>

## ✔ 본격 실습

### 0) 두 개의 PowerShell 창 준비

* 창 A: 서버 실행
* 창 B: 테스트 & 어드바이저 실행

<br>
<br>

### 1) 창 A — 가상환경 만들기 + 패키지 설치 + 서버 실행

```powershell
cd C:\Users\이노메랩\weather-mcp

# (최초 1회) 가상환경 생성
python -m venv .venv

# 가상환경 활성화
.\.venv\Scripts\Activate.ps1

# (최초 1회) 패키지 설치/업데이트
python -m pip install --upgrade pip
pip install fastmcp httpx python-dateutil requests openai

# 서버 실행
python weather_server.py
```

→ 배너가 뜨고 `http://127.0.0.1:8000/mcp/` 대기 상태가 되면 OK.

<br>
<br>

### 2) 창 B — 같은 가상환경 활성화 + 서버 호출 테스트

```powershell
cd C:\Users\이노메랩\weather-mcp
.\.venv\Scripts\Activate.ps1

# (A) 테스트 스크립트로 확인
python mcp_test.py
```

또는 PowerShell로 직접 호출하고 결과 확인하려면:

```powershell
$headers = @{ "Content-Type" = "application/json"; "Accept" = "application/json, text/event-stream" }
$body = @{ jsonrpc = "2.0"; id = "1"; method = "tools/call"; params = @{ name = "weather_now"; arguments = @{ city = "Seoul" } } } | ConvertTo-Json -Compress
$raw = (Invoke-WebRequest -Uri "http://127.0.0.1:8000/mcp/" -Method POST -Headers $headers -Body $body).Content
$raw   # 원문 보기
```

<br>
<br>

### 3) 어드바이저 실행 (규칙 기반)

```powershell
python advisor.py Seoul
```

예:
`Seoul: 31.0°C (체감 NA), wind 3.6 m/s, UV NA, P(NA) 0.0 mm — 무더위 주의...`

<br>
<br>

### 4) 어드바이저 실행 (AI 다듬기)

```powershell
# (한 번만) 현재 창에 키 주입
$env:OPENAI_API_KEY="sk-여기에_키"

# 친근 톤 + 1문장
python advisor.py Seoul --ai --tone friendly --detail short

# 여러 도시도 가능
python advisor.py Seoul Busan Incheon --ai --tone friendly --detail medium
```


## ✔ 실습 사진
**(1)서버화면**
<img width="960" height="1030" alt="서버 작동 화면" src="https://github.com/user-attachments/assets/9ecc1701-4ee5-47e0-bea5-de45c8afcb79" />
<br>

**(2)powershell로 MCP 서버에서 AI 작동 화면**
<img width="960" height="1030" alt="다른 powershell에서 mcp+AI 작동 화면" src="https://github.com/user-attachments/assets/731c4b3f-07f0-473c-ba62-88a45f9330b1" />
<br>

**(3)기온 변화에 따라 달라지는 AI 어이스트의 조언**
<img width="937" height="116" alt="기온 변화로 달라진 AI 어시스턴트 조언" src="https://github.com/user-attachments/assets/2b291117-5806-4c0c-83cc-d43a5cedc85c" />

<br>


---
# 추가 설명(필요시 확인)
## 구성 파일
- **`weather_server.py`**: FastMCP 호환 서버. `weather_now(city)` 툴을 노출한다.<br>
  현재 기온/풍속 + 체감온도/자외선/강수/습도 등 확장 지표를 반환하며, 사람용 요약문도 함께 제공한다.<br>
  HTTP (stateless)로 `/mcp/` 경로에서 서비스.<br>
  <br>
  
- **`advisor.py`**: MCP 서버에 JSON-RPC(`tools/call`)로 요청 → 구조화 데이터 받아서 조언 생성.<br>
  `--ai` 옵션으로 OpenAI Responses API를 통해 자연어 한두 문장으로 다듬을 수 있다.<br>
  톤(`--tone`), 길이(`--detail`) 조절 가능.<br>
  <br>
  
- **`mcp_test.py`**: 간단한 도구 호출 테스트 스크립트.<br>
  SSE(`text/event-stream`) 응답에서 `data:` 라인만 파싱해 결과 확인.<br>
  <br>
  
- **`test_openai.py`**: OpenAI SDK 통신 스모크 테스트.<br>
  <br>
  
- **`.gitignore`**: 가상환경/캐시/IDE 설정/민감 파일 무시.<br>
<br>
<br>

## 요구 사항
- Python **3.10+** (권장: 최신)
- 패키지:
  - `fastmcp`, `httpx`, `python-dateutil`, `requests`, `openai`

> 가상환경을 권장한다. (예: PowerShell)
> ```powershell
> python -m venv .venv
> .\.venv\Scripts\Activate.ps1
> python -m pip install --upgrade pip
> pip install fastmcp httpx python-dateutil requests openai
> ```

<br>
<br>

## 환경 변수 (AI 다듬기용)
`advisor.py --ai` 모드에서 OpenAI API 키가 필요하다.

- **현재 세션만:**
  ```powershell
  $env:OPENAI_API_KEY = "sk-..."
  ```
<br>

- **영구 저장(사용자 변수):**

  ```powershell
  [Environment]::SetEnvironmentVariable("OPENAI_API_KEY", "sk-...", "User")
  # 새 PowerShell 창에서 적용 확인
  [bool]([Environment]::GetEnvironmentVariable("OPENAI_API_KEY","User"))
  ```

<br>
<br>

## 서버 실행 (FastMCP)

```powershell
python weather_server.py
```

성공 시 배너와 함께 `http://127.0.0.1:8000/mcp/`에서 대기한다.
<br>
<br>

### 흔한 오류

* **포트 충돌**: `WinError 10048` → 8000번 포트를 쓰는 프로세스를 종료하거나 `weather_server.py`의 포트를 변경한다.
* **Not Acceptable (406)**: 클라이언트에서 `Accept: application/json, text/event-stream`를 포함한다.

<br>
<br>

## 빠른 테스트

### 1) mcp\_test.py

```powershell
python mcp_test.py
```

SSE 본문에서 `data:` JSON을 파싱해 `result`(요약문 + `structuredContent`)가 출력된다.

### 2) PowerShell로 직접 호출

```powershell
$headers = @{ "Content-Type" = "application/json"; "Accept" = "application/json, text/event-stream" }
$body = @{ jsonrpc = "2.0"; id = 1; method = "tools/call"; params = @{ name = "weather_now"; arguments = @{ city = "Seoul" } } } | ConvertTo-Json -Compress
Invoke-WebRequest -Uri "http://127.0.0.1:8000/mcp/" -Method POST -Headers $headers -Body $body | Select -Expand Content
```

<br>
<br>

## 어드바이저(조언) 실행

규칙 기반 한 줄 조언:

```powershell
python advisor.py Seoul
```

AI 다듬기(친근 톤, 1문장):

```powershell
python advisor.py Seoul --ai --tone friendly --detail short
```

옵션:

* `--ai`: OpenAI Responses API 사용(환경변수 `OPENAI_API_KEY` 필요)
* `--model`: 기본 `gpt-4o-mini`
* `--tone`: `friendly | neutral | formal`
* `--detail`: `short | medium`

출력 예시:

```
Seoul: 31.0°C (체감 33.0°C), wind 3.6 m/s, UV 7.0, P(40%) 0.0 mm — 야외는 덥겠습니다. 통풍 좋은 옷과 수분 보충을 권장해요
```

<br>
<br>

## 동작 개요

1. **`weather_server.py`**

   * 도시명을 지오코딩(Open-Meteo Geocoding) → 위/경도 확인
   * Open-Meteo Forecast API로 `current_weather` + `hourly`(기온, 체감, UV, 강수, 습도, 바람) 조회
   * 현재 시각에 가장 가까운 시간 인덱스를 선택해 지표 추출
   * MCP `ToolResult`로 **사람용 요약문** + **구조화 데이터** 동시 반환
2. **`advisor.py`**

   * JSON-RPC 메서드 `tools/call`로 서버의 `weather_now` 호출
   * SSE 또는 JSON 응답을 파싱해 `structuredContent` 확보
   * 규칙 기반으로 옷차림/우산/자외선/바람/습도 조언 생성
   * `--ai`일 때 OpenAI Responses API로 톤/길이에 맞춰 자연어 다듬기

<br>
<br>

## 설정 변경 팁

* **MCP\_URL**: 서버 포트를 바꾸면 `advisor.py`/`mcp_test.py`의 `MCP_URL` 상수도 함께 변경한다.
* **단위**: 서버는 `°C`, `m/s`, `mm` 기준으로 내려줍니다. 다른 단위를 쓰고 싶다면 `weather_server.py`의 쿼리 파라미터를 조정한다.
* **캐싱**: 반복 호출이 많다면 서버 측에서 간단한 캐시(예: 60초)로 지연/호출수 절감 가능.

<br>
<br>

## 보안

* API 키는 **환경변수**로 관리하고, 절대 코드/레포에 하드코딩하지 않는다.
* `.gitignore`에 `.env`/가상환경/캐시 항목이 포함되어 있습니다. 민감정보 파일이 커밋되지 않도록 유의한다.

<br>
<br>

# 업데이트 예정

## 확장 아이디어

* 1\~7일 **예보 툴** 추가(`forecast(city, days)`)
* 위치 즐겨찾기·일일 리포트(이메일/슬랙/디스코드) 자동 발송
* 자외선/강수 경보 알림(조건부 트리거)
* 다국어 지원

---

## 라이선스

원하는 라이선스를 `LICENSE` 파일로 추가 가능 (예: MIT)

