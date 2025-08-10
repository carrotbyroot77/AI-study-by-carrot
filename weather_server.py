# weather_server.py  ─ FastMCP 호환 서버 (description 제거 + run 시그니처 자동 대응)
from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult
from mcp.types import TextContent
from typing import TypedDict, Optional
import httpx
import inspect
import secrets

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


class WeatherNow(TypedDict):
    city: str
    temperature: Optional[float]
    windspeed: Optional[float]


@mcp.tool()
async def weather_now(city: str) -> dict:
    """
    도시명을 받아 현재 기온/풍속을 반환.
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
            "current_weather": "true",
            "temperature_unit": "celsius",
            "windspeed_unit": "ms", # 풍속 단위 m/s
            "timezone": "auto",
        },
    )
    if "error" in wjson:
        return wjson
    
    w = wjson.get("current_weather", {})
    data = {
        "city": city,
        "temperature": w.get("temperature"),
        "windspeed": w.get("windspeed"),
    }

    summary = f"{city}: {data['temperature']}°C, wind {data['windspeed']} m/s"
    return ToolResult(
        content=[TextContent(text=summary)],
        structured_content=data,
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



