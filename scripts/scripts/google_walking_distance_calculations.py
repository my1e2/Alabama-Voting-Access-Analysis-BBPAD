"""
Google Routes API - Walking Distance Calculations
Uses the Routes API (Compute Route Matrix) for pedestrian distances
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
API_KEY = "AIzaSyBYWZPJn3r__GIM1Vazym8KByuVNCLlpN0"
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
    print(f"Loaded {len(montgomery_centers)} population centers for Montgomery County")
    
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
    print(f"Loaded {len(gdf)} polling places")
    return gdf


def compute_route_matrix(origins, destinations, max_retries=9):
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
            {
                "waypoint": {
                    "location": {
                        "latLng": {
                            "latitude": lat,
                            "longitude": lon
                        }
                    }
                }
            }
            for lat, lon in origins
        ],
        "destinations": [
            {
                "waypoint": {
                    "location": {
                        "latLng": {
                            "latitude": lat,
                            "longitude": lon
                        }
                    }
                }
            }
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
                valid_count = 0
                
                # parse each route result from the response
                for item in results:
                    origin_idx = item.get('originIndex')
                    dest_idx = item.get('destinationIndex')
                    distance_meters = item.get('distanceMeters')
                    
                    # empty status object means success, just check for distance value
                    if distance_meters is not None:
                        # convert meters to miles (1 mile = 1609.34 meters)
                        distances[origin_idx, dest_idx] = distance_meters / 1609.34
                        valid_count += 1
                
                if valid_count > 0:
                    return distances
                else:
                    print(f"  No valid distances in response")
                    return None
                    
            elif response.status_code == 429:
                # rate limited - wait with exponential backoff
                # wait times: 2s, 4s, 8s, 16s, 32s, 64s, 128s, 256s, 512s
                wait_time = (2 ** attempt) * 2
                print(f"  Rate limited, waiting {wait_time}s before retry")
                time.sleep(wait_time)
                
            else:
                print(f"  API Error {response.status_code}: {response.text[:200]}")
                return None
                
        except Exception as e:
            print(f"  Request failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                return None
    
    print(f"  Failed after {max_retries} retries")
    return None


def calculate_google_walking_distances(pop_centers_gdf, polling_gdf, sample_size=None):
    """
    calculate walking distances from each population center to all polling places.
    
    uses the google routes api to compute pedestrian distances between all
    population centers and polling places. processes in batches to respect
    api rate limits and element count restrictions.
    
    args:
        pop_centers_gdf: geodataframe of population centers
        polling_gdf: geodataframe of polling places
        sample_size: if provided, only process first n centers (for testing)
        
    returns:
        tuple of (updated pop_centers_gdf with min_distance column,
                 full distance matrix as dataframe)
    """
    
    if sample_size:
        pop_centers_gdf = pop_centers_gdf.head(sample_size).copy()
        print(f"Testing with first {sample_size} centers")
    
    n_centers = len(pop_centers_gdf)
    n_polls = len(polling_gdf)
    
    # google routes api expects coordinates in (latitude, longitude) order
    origins = [(row.geometry.y, row.geometry.x) for _, row in pop_centers_gdf.iterrows()]
    destinations = [(row.geometry.y, row.geometry.x) for _, row in polling_gdf.iterrows()]
    
    print(f"")
    print(f"Calculating Google walking distances for {n_centers} centers x {n_polls} polling places")
    print(f"Total routes: {n_centers * n_polls}")
    print("")
    
    start_time = time.time()
    
    # batch size: 6 origins x 49 destinations = 294 elements
    # this stays safely under the 625 element limit per request
    MAX_ORIGINS_PER_BATCH = 6
    
    all_distances = np.full((n_centers, n_polls), np.nan)
    successful_batches = 0
    failed_batches = 0
    
    for i in range(0, n_centers, MAX_ORIGINS_PER_BATCH):
        batch_origins = origins[i:i+MAX_ORIGINS_PER_BATCH]
        batch_end = min(i+MAX_ORIGINS_PER_BATCH, n_centers)
        
        print(f"Processing origins {i+1}-{batch_end} of {n_centers}")
        
        distances = compute_route_matrix(batch_origins, destinations)
        
        if distances is not None:
            all_distances[i:i+len(batch_origins), :] = distances
            successful_batches += 1
            print(f"  batch successful")
        else:
            failed_batches += 1
            print(f"  batch failed, continuing")
        
        # wait 2.5 seconds between batches to stay safely under rate limits
        # free tier allows approximately 1 request per second
        time.sleep(2.5)
    
    elapsed_total = time.time() - start_time
    print(f"")
    print(f"Completed in {elapsed_total/60:.1f} minutes")
    print(f"Successful batches: {successful_batches}")
    print(f"Failed batches: {failed_batches}")
    
    # calculate minimum distance to any polling place for each center
    min_distances = np.full(n_centers, np.nan)
    nearest_poll_idx = np.full(n_centers, -1)
    
    for i in range(n_centers):
        valid_dists = all_distances[i, ~np.isnan(all_distances[i])]
        if len(valid_dists) > 0:
            min_distances[i] = np.nanmin(all_distances[i])
            nearest_poll_idx[i] = np.nanargmin(all_distances[i])
    
    # add results to geodataframe
    pop_centers_gdf['min_google_walking_dist_miles'] = min_distances
    pop_centers_gdf['nearest_poll_google_walking_idx'] = nearest_poll_idx
    
    # report summary statistics
    valid_count = (~np.isnan(min_distances)).sum()
    print(f"")
    print(f"Valid distances: {valid_count}/{n_centers} centers")
    
    if valid_count > 0:
        print(f"Average Google walking distance: {np.nanmean(min_distances):.2f} miles")
        print(f"Maximum Google walking distance: {np.nanmax(min_distances):.2f} miles")
        print(f"Minimum Google walking distance: {np.nanmin(min_distances):.2f} miles")
    
    # create distance matrix dataframe with meaningful labels
    matrix_df = pd.DataFrame(
        all_distances,
        index=pop_centers_gdf['GEOID'],
        columns=[f"poll_{i}" for i in range(n_polls)]
    )
    
    return pop_centers_gdf, matrix_df


def main():
    """
    main execution function.
    
    loads population centers and polling places, calculates walking distances
    using the google routes api, and saves results to csv files for later
    analysis and visualization.
    """
    print("Google Routes API - Walking Distance Calculations")
    print("Montgomery County, Alabama")
    print("")
    
    # load input data
    print("Loading population centers")
    pop_centers = load_population_centers()
    
    print("Loading polling places")
    polling = load_polling_places()
    
    # calculate distances for all centers
    # set sample_size=5 for testing with a small subset
    pop_centers, distance_matrix = calculate_google_walking_distances(
        pop_centers, 
        polling,
        sample_size=None  # full calculation for all 203 centers
    )
    
    # save results to processed outputs directory
    print("")
    print("Saving results")
    
    # save accessibility scores with walking distances included
    output_path = PROJECT_ROOT / "data" / "outputs" / "accessibility_scores_google_walking.csv"
    pop_centers.to_csv(output_path, index=False)
    print(f"Saved to {output_path}")
    
    # save full distance matrix for detailed analysis
    matrix_path = PROJECT_ROOT / "data" / "outputs" / "distance_matrix_google_walking.csv"
    distance_matrix.to_csv(matrix_path)
    print(f"Saved to {matrix_path}")
    



if __name__ == "__main__":
    main()