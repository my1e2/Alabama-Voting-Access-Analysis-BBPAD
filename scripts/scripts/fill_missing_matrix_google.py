"""
Fill missing values in Google walking distance matrix.
Uses Google Routes API to compute walking distances for matrix cells
that failed in the initial batch processing run.
"""

import pandas as pd
import geopandas as gpd
import numpy as np
import requests
import time
from pathlib import Path
from shapely.geometry import Point

# project root directory - three levels up from this script
PROJECT_ROOT = Path(__file__).parent.parent.parent

# google routes api configuration
# api key for distance matrix computations (walking mode)
API_KEY = ""
ROUTES_URL = "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"


def load_population_centers():
    """
    load census 2020 centers of population for montgomery county.
    
    reads the comma-delimited text file from the census bureau and filters
    to montgomery county block groups only. creates point geometries from
    longitude and latitude coordinates.
    
    returns geodataframe with population centers for montgomery county.
    """
    # path to census bureau population centers file
    centers_path = PROJECT_ROOT / "data" / "census" / "raw" / "CenPop2020_Mean_BG01.txt"
    
    # read with utf-8 encoding to handle byte order mark
    df = pd.read_csv(centers_path, encoding='utf-8-sig')
    
    # construct full 12-digit geoid from component parts
    # format: state (2) + county (3) + tract (6) + block group (1)
    df['GEOID'] = (
        df['STATEFP'].astype(str).str.zfill(2) + 
        df['COUNTYFP'].astype(str).str.zfill(3) + 
        df['TRACTCE'].astype(str).str.zfill(6) + 
        df['BLKGRPCE'].astype(str).str.zfill(1)
    )
    
    # filter to montgomery county only (fips code 01101)
    montgomery_centers = df[df['GEOID'].astype(str).str[:5] == '01101'].copy()
    
    # create point geometries from coordinates
    geometry = [Point(xy) for xy in zip(montgomery_centers['LONGITUDE'], montgomery_centers['LATITUDE'])]
    gdf = gpd.GeoDataFrame(montgomery_centers, geometry=geometry, crs="EPSG:4326")
    
    return gdf


def load_polling_places():
    """
    load processed polling places from geojson file.
    
    returns geodataframe with polling place locations and point geometries.
    """
    polling_path = PROJECT_ROOT / "data" / "polling" / "processed" / "polling_places_montgomery_2020.geojson"
    gdf = gpd.read_file(polling_path)
    return gdf


def compute_route_matrix(origins, destinations, max_retries=5):
    """
    compute distance matrix using google routes api.
    
    sends a batch request to the routes api for walking distances between
    origin points and destination points. implements exponential backoff
    for rate limiting and retries on failure.
    
    args:
        origins: list of (latitude, longitude) tuples for starting points
        destinations: list of (latitude, longitude) tuples for ending points
        max_retries: number of retry attempts before giving up
        
    returns:
        2d numpy array of distances in miles, or none if request fails
    """
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": "originIndex,destinationIndex,distanceMeters,status"
    }
    
    # build request body with waypoint objects for walking travel mode
    body = {
        "origins": [
            {"waypoint": {"location": {"latLng": {"latitude": lat, "longitude": lon}}}}
            for lat, lon in origins
        ],
        "destinations": [
            {"waypoint": {"location": {"latLng": {"latitude": lat, "longitude": lon}}}}
            for lat, lon in destinations
        ],
        "travelMode": "WALK"
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.post(ROUTES_URL, headers=headers, json=body, timeout=30)
            
            if response.status_code == 200:
                results = response.json()
                
                # initialize distance matrix with nan values
                distances = np.full((len(origins), len(destinations)), np.nan)
                
                # parse each route result from the response
                for item in results:
                    origin_idx = item.get('originIndex')
                    dest_idx = item.get('destinationIndex')
                    distance_meters = item.get('distanceMeters')
                    
                    if distance_meters is not None:
                        # convert meters to miles (1 mile = 1609.34 meters)
                        distances[origin_idx, dest_idx] = distance_meters / 1609.34
                
                return distances
                    
            elif response.status_code == 429:
                # rate limited - wait with exponential backoff
                # wait times: 3s, 6s, 12s, 24s, 48s
                wait_time = (2 ** attempt) * 3
                print(f"  Rate limited, waiting {wait_time}s")
                time.sleep(wait_time)
            else:
                print(f"  API Error {response.status_code}")
                return None
                
        except Exception as e:
            print(f"  Error: {e}")
            time.sleep(3)
    
    return None


def main():
    """
    main execution function.
    
    loads existing google walking distance matrix, identifies rows with
    missing values, fetches those distances via the routes api, and updates
    the matrix csv file with the new values.
    """
    print("FILLING MISSING GOOGLE WALKING MATRIX VALUES")
    print("")
    
    # load existing distance matrix from previous processing
    matrix_path = PROJECT_ROOT / "data" / "outputs" / "distance_matrix_google_walking.csv"
    df_matrix = pd.read_csv(matrix_path, index_col=0)
    
    print(f"Matrix shape: {df_matrix.shape}")
    print(f"Current NaN values: {df_matrix.isna().sum().sum()}")
    print("")
    
    # identify rows that contain at least one nan value
    rows_with_nan = df_matrix[df_matrix.isna().any(axis=1)]
    missing_indices = list(rows_with_nan.index)
    
    print(f"Rows with missing data: {len(missing_indices)}")
    print(f"Indices: {missing_indices}")
    print("")
    
    # if no missing data, exit early
    if len(missing_indices) == 0:
        print("Matrix is already complete")
        return
    
    # load full population centers and polling places for coordinate lookup
    all_centers = load_population_centers()
    polling = load_polling_places()
    
    # map the matrix index (short geoid format) to full geoid format
    # short format example: "11010026002"
    # full format example:  "011010026002"
    full_geoids = []
    for short_geoid in missing_indices:
        short_geoid_str = str(short_geoid)
        # if it starts with '1101', prepend a zero to match full format
        full_geoid = '0' + short_geoid_str if short_geoid_str.startswith('1101') else short_geoid_str
        full_geoids.append(full_geoid)
    
    # filter population centers to only those with missing matrix data
    missing_centers = all_centers[all_centers['GEOID'].isin(full_geoids)].copy()
    
    # ensure order matches the missing_indices list for correct row assignment
    geoid_to_row = {geoid: i for i, geoid in enumerate(full_geoids)}
    missing_centers['sort_order'] = missing_centers['GEOID'].map(geoid_to_row)
    missing_centers = missing_centers.sort_values('sort_order')
    
    print(f"Loaded {len(missing_centers)} missing centers")
    print("")
    
    # extract coordinate tuples for api requests
    origins = [(row.geometry.y, row.geometry.x) for _, row in missing_centers.iterrows()]
    destinations = [(row.geometry.y, row.geometry.x) for _, row in polling.iterrows()]
    
    print(f"Calculating distances for {len(origins)} centers x {len(destinations)} polling places")
    print("")
    
    # process origins in small batches to avoid api rate limits
    BATCH_SIZE = 3
    all_distances = np.full((len(origins), len(destinations)), np.nan)
    
    for i in range(0, len(origins), BATCH_SIZE):
        batch_origins = origins[i:i+BATCH_SIZE]
        batch_end = min(i+BATCH_SIZE, len(origins))
        
        print(f"Processing origin {i+1}-{batch_end} of {len(origins)}")
        
        distances = compute_route_matrix(batch_origins, destinations, max_retries=5)
        
        if distances is not None:
            all_distances[i:i+len(batch_origins), :] = distances
            print(f"  success")
        else:
            print(f"  failed")
        
        # delay between batches to respect api rate limits
        time.sleep(5.0)
    
    # update the matrix with new distance values
    for i, short_geoid in enumerate(missing_indices):
        df_matrix.loc[short_geoid] = all_distances[i]
        print(f"  Updated row {short_geoid}")
    
    # save updated matrix back to original location
    df_matrix.to_csv(matrix_path)
    print(f"")
    print(f"Updated matrix saved to {matrix_path}")
    
    # final validation count
    remaining_nan = df_matrix.isna().sum().sum()
    print(f"")
    print(f"Remaining NaN values: {remaining_nan}")
    
    if remaining_nan == 0:
        print("Matrix is 100 percent complete")


if __name__ == "__main__":
    main()