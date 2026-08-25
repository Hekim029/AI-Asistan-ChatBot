"""Open-Meteo üzerinden anahtarsız hava durumu verisi."""

from __future__ import annotations

import requests
from services.security import clean_single_line, sanitize_untrusted_text


WMO_DESCRIPTIONS = {
    0: "açık",
    1: "çoğunlukla açık",
    2: "parçalı bulutlu",
    3: "kapalı",
    45: "sisli",
    48: "kırağılı sis",
    51: "hafif çisenti",
    53: "çisenti",
    55: "yoğun çisenti",
    56: "hafif donan çisenti",
    57: "yoğun donan çisenti",
    61: "hafif yağmurlu",
    63: "yağmurlu",
    65: "şiddetli yağmurlu",
    66: "hafif donan yağmur",
    67: "yoğun donan yağmur",
    71: "hafif kar yağışlı",
    73: "kar yağışlı",
    75: "yoğun kar yağışlı",
    77: "kar taneli",
    80: "hafif sağanak",
    81: "sağanak",
    82: "şiddetli sağanak",
    85: "hafif kar sağanağı",
    86: "yoğun kar sağanağı",
    95: "gök gürültülü fırtına",
    96: "dolu ihtimalli fırtına",
    99: "şiddetli dolulu fırtına",
}


def describe_weather_code(code: int) -> str:
    return WMO_DESCRIPTIONS.get(int(code), "bilinmeyen hava durumu")


def _geocode(city: str) -> dict:
    city = clean_single_line(city, name="Şehir", max_length=120)
    response = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={
            "name": city,
            "count": 1,
            "language": "tr",
            "format": "json",
        },
        timeout=8,
        allow_redirects=False,
    )
    response.raise_for_status()
    results = response.json().get("results") or []
    if not results:
        raise ValueError(f"'{city}' için konum bulunamadı.")
    return results[0]


def get_weather(city: str, period: str = "today") -> str:
    location = _geocode(city)
    response = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "current": (
                "temperature_2m,apparent_temperature,weather_code,"
                "wind_speed_10m,relative_humidity_2m"
            ),
            "daily": (
                "weather_code,temperature_2m_max,temperature_2m_min,"
                "precipitation_probability_max"
            ),
            "timezone": "auto",
            "forecast_days": 7,
        },
        timeout=10,
        allow_redirects=False,
    )
    response.raise_for_status()
    data = response.json()
    display_name = sanitize_untrusted_text(", ".join(
        part for part in (location.get("name"), location.get("admin1")) if part
    ), 300)

    if period == "now":
        current = data["current"]
        return (
            f"{display_name} şu an: {describe_weather_code(current['weather_code'])}, "
            f"{current['temperature_2m']}°C "
            f"(hissedilen {current['apparent_temperature']}°C), "
            f"nem %{current['relative_humidity_2m']}, "
            f"rüzgâr {current['wind_speed_10m']} km/sa."
        )

    daily = data["daily"]
    indices = [1] if period == "tomorrow" else list(range(7)) if period == "week" else [0]
    lines = []
    for index in indices:
        lines.append(
            f"- {daily['time'][index]}: "
            f"{describe_weather_code(daily['weather_code'][index])}, "
            f"{daily['temperature_2m_min'][index]}–"
            f"{daily['temperature_2m_max'][index]}°C, "
            f"yağış olasılığı %{daily['precipitation_probability_max'][index]}"
        )
    return f"{display_name} hava tahmini:\n" + "\n".join(lines)
