import joblib
from features.builder import build_features

#model = joblib.load("models/crop_model.pkl")

lat = float(input("Lat: "))
lon = float(input("Lon: "))
acres = float(input("Acres: "))

N = float(input("N: "))
P = float(input("P: "))
K = float(input("K: "))
ph = float(input("pH: "))

X, ndvi = build_features(lat, lon, acres, N, P, K, ph)

#crop = model.predict([X])[0]

#print("\nRecommended crop:", crop)
print("NDVI:", ndvi)
print("Saved NDVI map → field_ndvi.tif")
