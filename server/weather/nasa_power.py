import requests
from datetime import datetime, timedelta, timezone

def get_weather(lat, lon):

    end = datetime.now(timezone.utc) - timedelta(days=10)
    start = end - timedelta(days=60)

    url = (
        "https://power.larc.nasa.gov/api/temporal/daily/point?"
        "community=AG&parameters=T2M,RH2M,PRECTOTCORR"
        f"&latitude={lat}&longitude={lon}"
        f"&start={start.strftime('%Y%m%d')}"
        f"&end={end.strftime('%Y%m%d')}"
        "&format=JSON"
    )

    r = requests.get(url).json()
    data = r["properties"]["parameter"]

    temp = [v for v in data.get("T2M", {}).values() if v != -999]
    humidity = [v for v in data.get("RH2M", {}).values() if v != -999]
    rain = [v for v in data.get("PRECTOTCORR", {}).values() if v != -999]

    if not temp or not humidity or not rain:
        raise Exception("Weather data incomplete")

    return sum(temp)/len(temp), sum(humidity)/len(humidity), sum(rain)