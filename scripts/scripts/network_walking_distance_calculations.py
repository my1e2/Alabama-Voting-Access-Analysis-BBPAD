# using osrm for walking distance calculations
# google api and road shapefiles could be added later for traffic times
# note: full traffic analysis would require significant additional time

"""
Network Distance Calculations using OSRM
Calculates actual walking distances from population centers to polling places
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

# osrm server configuration for walking profile
# osrm server expected to be running locally on port 5002 with foot profile
OSRM_URL = "http://localhost:5002/route/v1/foot/"


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


def get_osrm_walking_distance(lon1, lat1, lon2, lat2):
    """
    get walking distance between two points using osrm foot profile.
    
    sends a request to the local osrm server for the shortest walking route
    between origin and destination coordinates using pedestrian pathways.
    
    args:
        lon1: origin longitude
        lat1: origin latitude
        lon2: destination longitude
        lat2: destination latitude
        
    returns:
        distance in miles, or none if routing fails
    """
    # osrm expects coordinates in longitude,latitude order
    coordinates = f"{lon1},{lat1};{lon2},{lat2}"
    url = f"{OSRM_URL}{coordinates}?overview=false"
    
    try:
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data['code'] == 'Ok' and len(data['routes']) > 0:
                # distance is returned in meters by default
                distance_meters = data['routes'][0]['distance']
                # convert meters to miles (1 mile = 1609.34 meters)
                distance_miles = distance_meters / 1609.34
                return distance_miles
            else:
                return None
        else:
            return None
            
    except requests.exceptions.RequestException:
        return None


def calculate_walking_distances(pop_centers_gdf, polling_gdf, sample_size=None):
    """
    calculate walking distances from each population center to all polling places.
    
    uses the osrm routing engine with foot profile to compute pedestrian network
    distances. processes each origin-destination pair individually with a small
    delay to avoid overwhelming the local server.
    
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
    
    # prepare arrays for results storage
    n_centers = len(pop_centers_gdf)
    n_polls = len(polling_gdf)
    
    min_distances = np.full(n_centers, np.nan)
    nearest_poll_idx = np.full(n_centers, -1)
    distance_matrix = np.full((n_centers, n_polls), np.nan)
    
    # extract polling place coordinates once for efficiency
    poll_coords = [(row.geometry.x, row.geometry.y) for _, row in polling_gdf.iterrows()]
    
    print(f"")
    print(f"Calculating walking distances for {n_centers} centers x {n_polls} polling places")
    print(f"Total routes to calculate: {n_centers * n_polls}")
    print(f"This will take approximately 5-10 minutes")
    print("")
    
    start_time = time.time()
    completed = 0
    total_routes = n_centers * n_polls
    
    # calculate distances for each population center
    for i, (_, center) in enumerate(pop_centers_gdf.iterrows()):
        center_lon, center_lat = center.geometry.x, center.geometry.y
        
        distances = []
        for j, (poll_lon, poll_lat) in enumerate(poll_coords):
            dist = get_osrm_walking_distance(center_lon, center_lat, poll_lon, poll_lat)
            distances.append(dist)
            
            if dist is not None:
                distance_matrix[i, j] = dist
            
            completed += 1
            
            # progress indicator every 100 routes
            if completed % 100 == 0:
                elapsed = time.time() - start_time
                pct = (completed / total_routes) * 100
                rate = completed / elapsed if elapsed > 0 else 0
                remaining = (total_routes - completed) / rate if rate > 0 else 0
                print(f"Progress: {completed}/{total_routes} ({pct:.1f} percent)")
                print(f"  Rate: {rate:.1f} req/sec, Est. remaining: {remaining/60:.1f} min")
        
        # find minimum valid distance for this center
        valid_distances = [d for d in distances if d is not None]
        if valid_distances:
            min_distances[i] = min(valid_distances)
            nearest_poll_idx[i] = distances.index(min(valid_distances))
        
        # small delay to avoid overwhelming the osrm server
        time.sleep(0.05)
    
    elapsed_total = time.time() - start_time
    print(f"")
    print(f"Completed in {elapsed_total/60:.1f} minutes")
    
    # add results to geodataframe
    pop_centers_gdf['min_walking_dist_miles'] = min_distances
    pop_centers_gdf['nearest_poll_walking_idx'] = nearest_poll_idx
    
    # create distance matrix dataframe with meaningful labels
    matrix_df = pd.DataFrame(
        distance_matrix,
        index=pop_centers_gdf['GEOID'],
        columns=[f"poll_{i}" for i in range(n_polls)]
    )
    
    # report summary statistics
    valid_count = (~np.isnan(min_distances)).sum()
    print(f"")
    print(f"Valid distances calculated: {valid_count}/{n_centers} centers")
    
    if valid_count > 0:
        print(f"Average walking distance: {np.nanmean(min_distances):.2f} miles")
        print(f"Maximum walking distance: {np.nanmax(min_distances):.2f} miles")
        print(f"Minimum walking distance: {np.nanmin(min_distances):.2f} miles")
    
    return pop_centers_gdf, matrix_df


def main():
    """
    main execution function.
    
    verifies osrm walking server connection, loads population centers and
    polling places, calculates pedestrian network distances, and saves
    results to csv files.
    """
    print("Walking distance calculations for Montgomery County")
    print("")
    
    # verify osrm walking server is accessible
    print("Checking OSRM walking server")
    try:
        # test route between two known montgomery locations
        test_url = f"{OSRM_URL}-86.3079,32.3792;-86.3001,32.3746?overview=false"
        response = requests.get(test_url, timeout=5)
        if response.status_code == 200:
            print("OSRM walking server is running")
        else:
            print("OSRM server not responding correctly")
            print("Make sure you ran: osrm-routed alabama-latest.osrm --port 5002 --algorithm=MLD")
            return
    except requests.exceptions.ConnectionError:
        print("Cannot connect to OSRM server")
        print("Make sure you started the server on port 5002")
        return
    
    print("")
    
    # load input data
    print("Loading population centers")
    pop_centers = load_population_centers()
    
    print("Loading polling places")
    polling = load_polling_places()
    
    # calculate walking distances for all centers
    # set sample_size=10 for a quick test, or none for full calculation
    pop_centers, distance_matrix = calculate_walking_distances(
        pop_centers, 
        polling,
        sample_size=None  # full calculation for all centers
    )
    
    # save results to processed outputs directory
    print("")
    print("Saving results")
    
    # save accessibility scores with walking distances included
    output_path = PROJECT_ROOT / "data" / "outputs" / "accessibility_scores_walking.csv"
    pop_centers.to_csv(output_path, index=False)
    print(f"Saved to {output_path}")
    
    # save full distance matrix for detailed analysis
    matrix_path = PROJECT_ROOT / "data" / "outputs" / "distance_matrix_walking.csv"
    distance_matrix.to_csv(matrix_path)
    print(f"Saved to {matrix_path}")
    
    # compare with euclidean distances if available from previous calculations
    print("")
    print("Comparison with previous metrics")
    print("")
    
    if 'min_dist_to_poll_miles' in pop_centers.columns:
        valid_mask = ~np.isnan(pop_centers['min_walking_dist_miles'])
        if valid_mask.sum() > 0:
            euclidean_avg = pop_centers.loc[valid_mask, 'min_dist_to_poll_miles'].mean()
            walking_avg = pop_centers.loc[valid_mask, 'min_walking_dist_miles'].mean()
            ratio = walking_avg / euclidean_avg
            
            print(f"Average Euclidean distance: {euclidean_avg:.2f} miles")
            print(f"Average Walking distance: {walking_avg:.2f} miles")
            print(f"Walking/Euclidean ratio: {ratio:.2f}x")
    
    print("")
    print("Analysis complete")


if __name__ == "__main__":
    main()