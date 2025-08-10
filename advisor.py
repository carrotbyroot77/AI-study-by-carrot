# 사용: python advisor.py Seoul [Busan Incheon ...]
import sys, json, os, argparse
import httpx
from openai import OpenAI

MCP_URL = "http://127.0.0.1:8000/mcp/"  # weather_server.py의 run 설정과 일치해야 함

def _parse_possible_sse(text: str):
    """SSE 형식이면 data: ... 라인에서 마지막 JSON을 파싱"""
    lines = text.splitlines()
    data_lines = [ln[5:].strip() for ln in lines if ln.startswith("data:")]
    if not data_lines:
        return None
    try:
        return json.loads(data_lines[-1])
    except json.JSONDecodeError:
        return None

def call_mcp_weather(city: str, timeout=20):
    """weather_now(city) JSON-RPC 호출 → (temp, wind) 반환"""
    payload = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "tools/call",
        "params": {"name": "weather_now", "arguments": {"city": city}}
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
    }

    with httpx.Client(timeout=timeout, headers=headers) as c:
        r = c.post("http://127.0.0.1:8000/mcp/", json=payload)  
        r.raise_for_status()
        ct = r.headers.get("content-type", "")
        data = _parse_possible_sse(r.text) if "text/event-stream" in ct else r.json()

    # FastMCP의 JSON-RPC 응답 형태 처리(정규화)
    result = data.get("result", data)
    sc = result.get("structuredContent") or result.get("structured_content")

    # 혹시 structuredContent가 없다면 content[0].text가 JSON 문자열일 수 있음
    if not sc and isinstance(result.get("content"), list) and result["content"]:
        try:
            sc = json.loads(result["content"][0].get("text", ""))
        except Exception:
            sc = None

    if not sc:
        raise RuntimeError(f"예상치 못한 응답 형식: {data}")

    return sc.get("temperature"), sc.get("windspeed")

def make_advice(temp, wind):
    """기온/풍속 기반 한 줄 조언 생성 (°C, m/s 가정)"""
    parts = []

    # 기온 기준 옷차림
    if temp is None:
        parts.append("온도 정보 없음")
    else:
        t = float(temp)
        if t >= 30:
            parts.append("아주 덥습니다. 통풍 잘 되는 반팔/민소매, 수분 보충 🔆")
        elif t >= 25:
            parts.append("덥습니다. 반팔/얇은 셔츠, 실내 냉방 대비 가벼운 겉옷")
        elif t >= 20:
            parts.append("선선~약간 따뜻. 가벼운 긴팔/얇은 가디건")
        elif t >= 13:
            parts.append("다소 선선. 얇은 자켓/가디건 추천")
        elif t >= 9:
            parts.append("쌀쌀합니다. 자켓/맨투맨, 긴바지")
        else:
            parts.append("춥습니다. 두꺼운 코트/패딩, 목도리 🧣")

    # 풍속 기준 주의
    if wind is not None:
        w = float(wind)  # m/s 가정 (weather_server.py에서 windspeed_unit='ms'인 경우)
        if w >= 10:
            parts.append("강풍 주의! 우산/모자 사용 주의, 체감온도 하락")
        elif w >= 6:
            parts.append("바람이 다소 강합니다. 체감온도 낮게 느껴질 수 있어요")

    # 1~2문장으로 조합
    return " ".join(parts)

def ai_polish(city: str, temp, wind, base_advice: str, model: str = "gpt-4o-mini"):
    """OpenAI Responses API로 한 문장 요약+조언 자연스럽게 다듬기"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return base_advice

    client = OpenAI(api_key=api_key)
    prompt = f"""
도시: {city}
현재 기온: {temp if temp is not None else "NA"} °C
풍속: {wind if wind is not None else "NA"} m/s
기본 조언: {base_advice}

요구사항:
- 한국어로 1~2문장만 출력
- 정보 전달 위주, 과장/군더더기 금지 (이모지는 최대 1개)
- °C, m/s 단위 유지
- 필요 시 옷차림/주의사항 요약
"""
    resp = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": "너는 간결하고 실용적인 날씨 어시스턴트다."},
            {"role": "user", "content": prompt.strip()},
        ],
    )
    try:
        return resp.output_text.strip()
    except Exception:
        if getattr(resp, "output", None):
            return resp.output[0].content[0].text.strip()
        return base_advice

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cities", nargs="+", help="조회할 도시명들")
    parser.add_argument("--ai", action="store_true", help="AI로 문장 다듬기")
    parser.add_argument("--model", default="gpt-4o-mini", help="AI 모델명 (기본: gpt-4o-mini)")
    args = parser.parse_args()

    for city in args.cities:
        try:
            temp, wind = call_mcp_weather(city)
            t_str = f"{temp:.1f}°C" if temp is not None else "NA"
            w_str = f"{wind:.1f} m/s" if wind is not None else "NA"
            base = make_advice(temp, wind)
            final = ai_polish(city, temp, wind, base, model=args.model) if args.ai else base
            print(f"{city}: {t_str}, wind {w_str} — {final}")
        except Exception as e:
            print(f"{city}: 데이터를 가져오지 못했습니다. ({e})")

if __name__ == "__main__":
    main()
