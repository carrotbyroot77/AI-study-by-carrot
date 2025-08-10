# 사용: python advisor.py Seoul [Busan Incheon ...] [--ai] [--model gpt-4o-mini]
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
    """weather_now(city) JSON-RPC 호출 → structuredContent(dict) 반환"""
    payload = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "tools/call",
        "params": {"name": "weather_now", "arguments": {"city": city}},
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }

    with httpx.Client(timeout=timeout, headers=headers) as c:
        r = c.post(MCP_URL, json=payload)  # 상수 사용
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

    return sc  # dict: city, temperature, windspeed, apparent_temperature, uv_index 등

def make_advice_ext(sc: dict) -> str:
    t   = sc.get("temperature")
    ap  = sc.get("apparent_temperature")
    w   = sc.get("windspeed")
    uv  = sc.get("uv_index")
    pp  = sc.get("precipitation_probability")
    pmm = sc.get("precipitation_mm")
    hum = sc.get("humidity")

    parts = []

    # 1) 기본 옷차림 (체감우선)
    ref = ap if ap is not None else t
    if ref is None:
        parts.append("온도 정보 없음")
    else:
        r = float(ref)
        if r >= 30:   parts.append("무더위 주의. 통풍 좋은 옷, 수분 보충 🔆")
        elif r >= 25: parts.append("덥습니다. 반팔/얇은 셔츠, 냉방 대비 가벼운 겉옷")
        elif r >= 20: parts.append("선선~약간 따뜻. 가벼운 긴팔/가디건")
        elif r >= 13: parts.append("다소 선선. 얇은 자켓/가디건")
        elif r >= 9:  parts.append("쌀쌀합니다. 자켓/맨투맨")
        else:         parts.append("춥습니다. 두꺼운 코트/패딩")

    # 2) 바람
    if w is not None:
        w = float(w)
        if w >= 10: parts.append("강풍 주의, 우산/모자 사용 유의")
        elif w >= 6: parts.append("바람이 다소 강합니다. 체감온도 낮게 느껴질 수 있어요")

    # 3) 강수 (확률 우선, 양 보조)
    needs_umbrella = (pp is not None and float(pp) >= 60) or (pmm is not None and float(pmm) >= 1.0)
    if needs_umbrella:
        parts.append("우산 챙기세요 ☔")

    # 4) 자외선 (WHO 단계)
    if uv is not None:
        u = float(uv)
        if u >= 11: parts.append("자외선 매우 위험. 실외활동 최소화, 차광 필수")
        elif u >= 8: parts.append("자외선 매우 강함. 모자/선글라스/자외선 차단제")
        elif u >= 6: parts.append("자외선 강함. 자외선 차단 권장")
        elif u >= 3: parts.append("자외선 보통. 한낮 노출 주의")

    # 5) 습도 (선택)
    if hum is not None:
        h = float(hum)
        if h >= 80 and (ref or 0) >= 25:
            parts.append("습도가 높아 무더위를 더 세게 느낌")

    return " ".join(parts)

def ai_polish(city: str, sc: dict, base_advice: str, model: str = "gpt-4o-mini", tone: str = "friendly", detail: str = "short") -> str:
    """OpenAI Responses API로 한 문장 요약+조언 자연스럽게 다듬기(확장 지표 포함)"""

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return base_advice

    t  = sc.get("temperature")
    ap = sc.get("apparent_temperature")
    w  = sc.get("windspeed")
    uv = sc.get("uv_index")
    pp = sc.get("precipitation_probability")
    pmm = sc.get("precipitation_mm")
    hum = sc.get("humidity")
    is_day = sc.get("is_day")
    time_iso = sc.get("time_iso")

    t_str  = f"{t:.1f}°C" if t is not None else "NA"
    ap_str = f"{ap:.1f}°C" if ap is not None else "NA"
    w_str  = f"{w:.1f} m/s" if w is not None else "NA"
    uv_str = f"{uv:.1f}" if uv is not None else "NA"
    p_str  = f"{pp:.0f}%" if pp is not None else "NA"
    mm_str = f"{pmm:.1f} mm" if pmm is not None else "0.0 mm"
    day_state = "day" if is_day == 1 else "night"


    tone_map = {
        "friendly": "따뜻하고 다정한 말투(반말은 금지, 존댓말로 친근하게).",
        "neutral":  "중립적이고 간결한 말투.",
        "formal":   "격식을 갖춘 공손한 말투.",
    }
    length_map = {
        "short":  "정확히 1문장으로.",
        "medium": "최대 2문장으로.",
    }


    policy = f"""
- 낮/밤: 현재는 {day_state}. 자외선 조언은 낮(is_day=1)일 때만 고려.
- 강수: 강수확률≥60% 또는 강수량≥1mm면 우산 권장.
- 바람: 풍속≥10m/s 강풍 주의, ≥6m/s면 체감온도 하락 언급 가능.
- 습도: 습도≥80%이고 기온 또는 체감온도≥25°C면 무더위/후텁지근 언급.
- 옷차림: 체감온도 우선(ref=apparent_temperature 없으면 temperature 사용).
"""

    system = f"너는 사용자의 하루를 챙기는 친밀한 날씨 어시스턴트다. {tone_map[tone]} 정보 정확성이 최우선이며, 불필요한 군더더기는 금지한다."
    user = f"""
도시: {city}
시간(대략): {time_iso}
지표: 기온 {t_str}, 체감 {ap_str}, 바람 {w_str}, 자외선 {uv_str}, 강수확률 {p_str}, 강수량 {mm_str}, 습도 {hum if hum is not None else "NA"}%
기본 규칙 기반 조언: {base_advice}

요구사항:
- {length_map[detail]} 꼭 한국어.
- 사용자의 입장에서 오늘 외출 준비에 바로 도움이 되게 말하기
- 우산/자외선/옷차림/바람/습도 조언은 위 정책을 바탕으로 **필요할 때만** 포함.
- °C, m/s, mm, % 단위 유지
- 필요한 경우 우산/자외선/옷차림 조언 포함
- 과장 금지, 불확실하면 조심스럽게 표현.
- 이모지는 최대 1개만, 상황 맞을 때만 사용.
""".strip()

    client = OpenAI(api_key=api_key)
    resp = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system + "\n" + policy.strip()},
            {"role": "user", "content": user.strip()},
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
    parser.add_argument("--tone", choices=["friendly","neutral","formal"], default="friendly", help="응답 톤")
    parser.add_argument("--detail", choices=["short","medium"], default="short", help="문장 길이")
    args = parser.parse_args()

    for city in args.cities:
        try:
            sc = call_mcp_weather(city)  # dict
            t  = sc.get("temperature"); w = sc.get("windspeed")
            ap = sc.get("apparent_temperature"); uv = sc.get("uv_index")
            pp = sc.get("precipitation_probability"); pmm = sc.get("precipitation_mm")

            t_str  = f"{t:.1f}°C" if t is not None else "NA"
            ap_str = f"{ap:.1f}°C" if ap is not None else "NA"
            w_str  = f"{w:.1f} m/s" if w is not None else "NA"
            uv_str = f"{uv:.1f}" if uv is not None else "NA"
            p_str  = f"{pp:.0f}%" if pp is not None else "NA"
            mm_str = f"{pmm:.1f} mm" if pmm is not None else "0.0 mm"

            base = make_advice_ext(sc)
            final = ai_polish(city, sc, base, model=args.model, tone=args.tone, detail=args.detail) if args.ai else base

            print(f"{city}: {t_str} (체감 {ap_str}), wind {w_str}, UV {uv_str}, P({p_str}) {mm_str} — {final}")

        except Exception as e:
            print(f"{city}: 데이터를 가져오지 못했습니다. ({e})")

if __name__ == "__main__":
    main()
