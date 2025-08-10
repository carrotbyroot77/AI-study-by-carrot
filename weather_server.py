# weather_server.py  ─ FastMCP 호환 서버 (description 제거 + run 시그니처 자동 대응)
from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult
from mcp.types import TextContent
from typing import TypedDict, Optional
from datetime import datetime
from dateutil import parser as dtparser
import httpx

TIMEOUT = httpx.Timeout(20.0)

# description 인자 제거 (버전별 차이를 피하기 위함)
mcp = FastMCP("weather")

async def _safe_get(url: str, **kwargs):
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as c:
            r = await c.get(url, **kwargs)
            r.raise_for_status()
            return r.json()
    except httpx.RequestError as e:
        return {"error": f"외부 API 호출 실패: {e}"}


async def _geocode(city: str):
    data = await _safe_get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": city, "count": 1, "language": "en", "format": "json"},
    )
    if "error" in data or not data.get("results"):
        return None
    res = data["results"][0]
    return res["latitude"], res["longitude"]


# (선택적 삭제가능) 반환 스키마 명시
class WeatherNow(TypedDict, total=False):
    city: str
    temperature: Optional[float]
    windspeed: Optional[float]                  # m/s
    apparent_temperature: Optional[float]       # °C
    uv_index: Optional[float]                   # WHO 기준 0~11+
    precipitation_probability: Optional[float]  # %
    precipitation_mm: Optional[float]           # mm
    humidity: Optional[float]                   # %


def _nearest_index(times: list[str], target_iso: Optional[str]) -> Optional[int]:
    if not times:
        return None
    if target_iso:
        try:
            tgt = dtparser.isoparse(target_iso)
        except Exception:
            tgt = None
    else:
        tgt = datetime.utcnow()
    if tgt is None:
        return len(times) - 1
    diffs = []
    for i, t in enumerate(times):
        try:
            diffs.append((abs(dtparser.isoparse(t) - tgt), i))
        except Exception:
            diffs.append((datetime.max - datetime.min, i))
    diffs.sort()
    return diffs[0][1]


@mcp.tool()
async def weather_now(city: str) -> "WeatherNow":
    """
     도시명을 받아 현재 기온/풍속 + 체감온도/자외선/강수/습도까지 반환
    반환: 사람이 읽는 요약문 + structuredContent
    """
    loc = await _geocode(city)
    if not loc:
        return {"error": f"'{city}' 좌표를 찾을 수 없거나 외부 API 접근이 차단됨."}
    lat, lon = loc

    wjson = await _safe_get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "timezone": "auto",
            "current_weather": "true",
            "hourly": ",".join([
                "temperature_2m",
                "apparent_temperature",
                "uv_index",
                "precipitation",
                "precipitation_probability",
                "relative_humidity_2m",
                "wind_speed_10m",
            ]),
            "forecast_days": 1,
            "windspeed_unit": "ms",
            "precipitation_unit": "mm",
        },
    )
    if "error" in wjson:
        return wjson
    
    cw = wjson.get("current_weather", {})  # 기본 현재값
    hourly = wjson.get("hourly", {})
    times = hourly.get("time", [])
    idx = _nearest_index(times, cw.get("time"))

    def pick(name: str):
        arr = hourly.get(name)
        if not arr or idx is None or idx >= len(arr):
            return None
        return arr[idx]

    data: WeatherNow = {
        "city": city,
        "temperature": cw.get("temperature") or pick("temperature_2m"),
        "windspeed": cw.get("windspeed") or pick("wind_speed_10m"),  # m/s
        "apparent_temperature": pick("apparent_temperature"),
        "uv_index": pick("uv_index"),
        "precipitation_probability": pick("precipitation_probability"),
        "precipitation_mm": pick("precipitation"),
        "humidity": pick("relative_humidity_2m"),
        "is_day": cw.get("is_day"),
        "time_iso": cw.get("time"),
    }

    # 사람용 요약 한 줄
    t = data.get("temperature")
    w = data.get("windspeed")
    ap = data.get("apparent_temperature")
    uv = data.get("uv_index")
    pp = data.get("precipitation_probability")
    pmm = data.get("precipitation_mm")

    bits = [f"{city}"]
    if t is not None:   bits.append(f"{t:.1f}°C")
    if ap is not None:  bits.append(f"(체감 {ap:.1f}°C)")
    if w is not None:   bits.append(f"바람 {w:.1f} m/s")
    if uv is not None:  bits.append(f"UV {uv:.1f}")
    if pp is not None:  bits.append(f"강수확률 {pp:.0f}%")
    if pmm and pmm >= 0.1: bits.append(f"강수량 {pmm:.1f}mm")
    summary = ", ".join(bits)

    return ToolResult(
        content=[TextContent(text=summary)],
        structured_content=data
    )


if __name__ == "__main__":
    mcp.run(
        transport="http",
        host="127.0.0.1",
        port=8000,
        path="/mcp/",
        stateless_http=True,   # 여기에서 run 쪽에 넣는다
        show_banner=True       # (선택) 배너 보고 싶으면
    )



