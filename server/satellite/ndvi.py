import ee
import geemap
import numpy as np
from datetime import datetime, timedelta

ee.Initialize(project="space-485616")

def get_ndvi(lat, lon, acres):

    point = ee.Geometry.Point([lon, lat])
    radius = (acres * 4047) ** 0.5
    region = point.buffer(radius).bounds()

    # DYNAMIC DATES: Look for images from the last 6 months
    end_date = datetime.now()
    start_date = end_date - timedelta(days=180)

    # HARMONIZED DATASET
    collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(region)
        .filterDate(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
        .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
        .sort("CLOUDY_PIXEL_PERCENTAGE")
    )

    # SAFETY CHECK: Stop gracefully if 0 images are found
    if collection.size().getInfo() == 0:
        raise ValueError(f"No satellite imagery found for coordinates: {lat}, {lon}")

    image = collection.first().clip(region)

    ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")

    stats = ndvi.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=region,
        scale=10,
        maxPixels=1e9
    )

    ndvi_value = stats.get("NDVI").getInfo()

    if ndvi_value is None:
        raise ValueError("Calculated NDVI is null. The selected area might be over water.")

    ndvi_vis = ndvi.visualize(
        min=0, max=1, palette=["brown", "yellow", "green"]
    )

    geemap.ee_export_image(
        ndvi_vis, filename="field_ndvi.tif", scale=10, region=region
    )
    
    bounds_info = region.coordinates().getInfo()
    ee_coords = bounds_info # List of [lon, lat] pairs

    return ndvi_value, ee_coords