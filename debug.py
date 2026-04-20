import requests
import json

VALHALLA_URL = "http://localhost:8002"

# Test route from center 11010001001 to its polling place
# Center: 32.379105, -86.308949
# Poll 16: You can find coordinates from your polling_gdf.iloc[16]

payload = {
    "locations": [
        {"lat": 32.379105, "lon": -86.308949, "type": "break"},
        {"lat": 32.379782, "lon": -86.285370, "type": "break"}  # Poll 16 coords (from your CSV, row 500)
    ],
    "costing": "pedestrian",
    "directions_options": {"units": "miles"}
}

response = requests.post(f"{VALHALLA_URL}/route", json=payload, timeout=30)
print(f"Status: {response.status_code}")
print(f"Response: {response.text[:500]}")