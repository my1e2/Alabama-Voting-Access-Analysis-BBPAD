"""
Fill missing Google walking distances for centers 157-162
Uses Google Routes API to compute walking distances for centers
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
                valid_count = 0
                
                # parse each route result from the response
                for item in results:
                    origin_idx = item.get('originIndex')
                    dest_idx = item.get('destinationIndex')
                    distance_meters = item.get('distanceMeters')
                    
                    if distance_meters is not None:
                        # convert meters to miles (1 mile = 1609.34 meters)
                        distances[origin_idx, dest_idx] = distance_meters / 1609.34
                        valid_count += 1
                
                if valid_count > 0:
                    return distances
                else:
                    return None
                    
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
    
    loads existing accessibility results, identifies centers with missing
    google walking distances, fetches those distances via the routes api,
    and updates the csv file with the new values.
    """
    print("FILLING MISSING GOOGLE WALKING DISTANCES")
    print("")
    
    # load existing accessibility results from previous processing
    existing_path = PROJECT_ROOT / "data" / "outputs" / "accessibility_scores_google_walking.csv"
    df_existing = pd.read_csv(existing_path, dtype={'GEOID': str})
    
    # identify which centers are missing google walking distances
    missing_mask = df_existing['min_google_walking_dist_miles'].isna()
    missing_geoids_short = df_existing[missing_mask]['GEOID'].astype(str).tolist()
    
    print(f"Missing centers: {len(missing_geoids_short)}")
    print(f"GEOIDs (from CSV): {missing_geoids_short}")
    print("")
    
    # load full population centers dataset for coordinate lookup
    all_centers = load_population_centers()
    
    # convert short geoid format to full 12-digit format
    # the csv has geoids like '11010026002' (missing leading zero)
    # full format should be '01101' + tract + block group = 12 digits
    missing_geoids_full = []
    for geoid in missing_geoids_short:
        # remove any non-digit characters for safety
        geoid_clean = ''.join(c for c in str(geoid) if c.isdigit())
        
        # if it starts with '1101', prepend a zero to match full format
        if geoid_clean.startswith('1101'):
            full_geoid = '0' + geoid_clean
        else:
            full_geoid = geoid_clean
            
        missing_geoids_full.append(full_geoid)
    
    print(f"GEOIDs (converted): {missing_geoids_full[:3]}")
    print(f"Sample from all_centers: {all_centers['GEOID'].iloc[0]}")
    print("")
    
    # filter population centers to only those missing distances
    missing_centers = all_centers[all_centers['GEOID'].isin(missing_geoids_full)].copy()
    print(f"Loaded {len(missing_centers)} missing centers")
    
    # if no matches found, print diagnostic information and exit
    if len(missing_centers) == 0:
        print("")
        print("Still no matches. Trying alternative matching")
        print("")
        print("All GEOIDs from population centers (first 10):")
        for geoid in all_centers['GEOID'].head(10).tolist():
            print(f"  {geoid}")
        print("")
        print("Missing GEOIDs from CSV:")
        for geoid in missing_geoids_short:
            print(f"  {geoid}")
        return
    
    # load polling places for destination coordinates
    polling = load_polling_places()
    print(f"Loaded {len(polling)} polling places")
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
    
    # calculate minimum distance to any polling place for each origin
    min_distances = np.full(len(origins), np.nan)
    for i in range(len(origins)):
        valid_dists = all_distances[i, ~np.isnan(all_distances[i])]
        if len(valid_dists) > 0:
            min_distances[i] = np.nanmin(all_distances[i])
    
    # update the existing dataframe with new distance values
    for i, full_geoid in enumerate(missing_centers['GEOID'].tolist()):
        # convert back to short format (remove leading zero if present)
        short_geoid = full_geoid[1:] if full_geoid.startswith('0') else full_geoid
        mask = df_existing['GEOID'].astype(str) == short_geoid
        df_existing.loc[mask, 'min_google_walking_dist_miles'] = min_distances[i]
        print(f"  Updated {short_geoid}: {min_distances[i]:.2f} miles")
    
    # save updated file back to original location
    df_existing.to_csv(existing_path, index=False)
    print(f"")
    print(f"Updated saved to {existing_path}")
    
    # final validation count
    valid_count = df_existing['min_google_walking_dist_miles'].notna().sum()
    print(f"")
    print(f"Valid distances: {valid_count}/{len(df_existing)} centers")
    
    if valid_count == 203:
        print("All 203 centers now have Google walking distances")


if __name__ == "__main__":
    main()