from weather.nasa_power import get_weather
from satellite.ndvi import get_ndvi

def build_features(lat, lon, acres, N, P, K, ph):

    temp, humidity, rainfall = get_weather(lat, lon)
    ndvi, ee_coords = get_ndvi(lat, lon, acres)

    X = [
        N, P, K,
        temp,
        humidity,
        ph,
        rainfall
    ]

    return X, ndvi, ee_coords
