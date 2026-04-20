"""
Final Valhalla Isochrone Analysis for Montgomery County Polling Places
Generates 5, 10, 15, 20, and 30-minute walking isochrones for all polling places
"""

import pandas as pd
import geopandas as gpd
import requests
import json
import time
from pathlib import Path
from shapely.geometry import Point

# project root directory - three levels up from this script
PROJECT_ROOT = Path(__file__).parent.parent.parent

# valhalla routing engine url (running locally on port 8002)
VALHALLA_URL = "http://localhost:8002"


def load_polling_places():
    """
    load polling place locations from geojson file.
    
    attempts to load the 2020 version first, falls back to generic
    montgomery polling places file if 2020 version not found.
    
    returns geodataframe with polling place locations.
    """
    # try 2020 version first
    path = PROJECT_ROOT / "data" / "polling" / "processed" / "polling_places_montgomery_2020.geojson"
    if not path.exists():
        # fallback to generic montgomery polling places
        path = PROJECT_ROOT / "data" / "polling" / "processed" / "polling_places_montgomery.geojson"
    return gpd.read_file(path)


def load_population_centers():
    """
    load census 2020 centers of population for coverage analysis.
    
    reads the comma-delimited text file from the census bureau and filters
    to montgomery county block groups only. used to calculate population
    served by each isochrone.
    
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
    montgomery = df[df['GEOID'].astype(str).str[:5] == '01101'].copy()
    
    # create point geometries from coordinates
    geometry = [Point(xy) for xy in zip(montgomery['LONGITUDE'], montgomery['LATITUDE'])]
    
    return gpd.GeoDataFrame(montgomery, geometry=geometry, crs="EPSG:4326")


def get_isochrone(lat, lon, time_minutes, max_retries=3):
    """
    get walking isochrone polygon from valhalla routing engine.
    
    sends a request to the local valhalla instance for a pedestrian isochrone
    around the specified coordinates. implements retry logic for transient
    failures.
    
    args:
        lat: latitude of origin point
        lon: longitude of origin point
        time_minutes: travel time in minutes for isochrone boundary
        max_retries: number of retry attempts before giving up
        
    returns:
        geodataframe with isochrone polygon, or none if request fails
    """
    # build request payload for valhalla isochrone endpoint
    payload = {
        "locations": [{"lat": lat, "lon": lon}],
        "costing": "pedestrian",
        "contours": [{"time": time_minutes}],
        "polygons": True,
        "denoise": 0.11  # smooths jagged edges from network analysis
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.post(f"{VALHALLA_URL}/isochrone", json=payload, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if 'features' in data and len(data['features']) > 0:
                    # convert geojson features to geodataframe
                    return gpd.GeoDataFrame.from_features(data['features']).set_crs("EPSG:4326")
            
            # brief delay before retry
            time.sleep(1)
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
    
    return None


def calculate_population_served(isochrone_gdf, population_gdf):
    """
    calculate total population within an isochrone polygon.
    
    performs spatial join to count population centers that fall within
    the isochrone boundary. sums the population column for all enclosed points.
    
    args:
        isochrone_gdf: geodataframe containing a single isochrone polygon
        population_gdf: geodataframe of population centers
        
    returns:
        total population served (sum of POPULATION column for enclosed points)
    """
    if isochrone_gdf is None or population_gdf is None:
        return 0
    
    # ensure both dataframes use same coordinate reference system
    if isochrone_gdf.crs != population_gdf.crs:
        population_gdf = population_gdf.to_crs(isochrone_gdf.crs)
    
    # extract the isochrone polygon
    isochrone_poly = isochrone_gdf.geometry.iloc[0]
    
    # create boolean mask for points within polygon
    mask = population_gdf.geometry.within(isochrone_poly)
    
    # sum population for points inside the isochrone
    return population_gdf[mask]['POPULATION'].sum()


def main():
    """
    main execution function.
    
    verifies valhalla connection, loads polling places and population centers,
    generates walking isochrones for multiple time intervals at each polling
    place, calculates area and population served, and saves results to
    geojson and csv files.
    """
    print("VALHALLA WALKING ISOCHRONE ANALYSIS")
    print("Montgomery County, Alabama - All Polling Places")
    print("")
    
    # verify valhalla routing engine is accessible
    print("Checking Valhalla connection")
    try:
        test = requests.get(f"{VALHALLA_URL}/status", timeout=5)
        if test.status_code == 200:
            data = test.json()
            print(f"Valhalla {data.get('version', 'unknown')} is running")
        else:
            print("Valhalla not responding")
            return
    except:
        print("Cannot connect to Valhalla on port 8002")
        return
    
    # load input data
    print("")
    print("Loading data")
    polling_gdf = load_polling_places()
    population_gdf = load_population_centers()
    print(f"{len(polling_gdf)} polling places")
    print(f"{len(population_gdf)} population centers")
    print(f"Total Montgomery County population: {population_gdf['POPULATION'].sum():,}")
    print("")
    
    # define time intervals for isochrone generation (in minutes)
    time_intervals = [5, 10, 15, 20, 30]
    
    # lists to store results for later concatenation and summary
    all_isochrones = []
    summary_data = []
    
    print(f"Generating isochrones for {len(polling_gdf)} polling places")
    print(f"Time intervals: {time_intervals} minutes")
    print("")
    
    # process each polling place
    for idx, row in polling_gdf.iterrows():
        # get polling place name from available columns
        poll_name = row.get('Precinct', row.get('NAME', f'Poll_{idx}'))
        print(f"Processing: {poll_name}")
        
        # generate isochrone for each time interval
        for minutes in time_intervals:
            iso = get_isochrone(row.geometry.y, row.geometry.x, minutes)
            
            if iso is not None:
                # attach metadata to isochrone geodataframe
                iso['polling_place'] = poll_name
                iso['time_minutes'] = minutes
                iso['poll_lat'] = row.geometry.y
                iso['poll_lon'] = row.geometry.x
                
                # calculate area in square miles
                # convert to utm zone 16n (epsg:32616) for accurate area calculation
                iso_area = iso.to_crs("EPSG:32616").geometry.area.iloc[0] / 2.59e6
                
                # calculate population within isochrone
                pop_served = calculate_population_served(iso, population_gdf)
                
                iso['area_sq_miles'] = iso_area
                iso['population_served'] = pop_served
                
                all_isochrones.append(iso)
                
                print(f"  {minutes:2d}-min: {iso_area:.2f} sq mi, {pop_served:,} people")
                
                # store summary data for csv export
                summary_data.append({
                    'polling_place': poll_name,
                    'time_minutes': minutes,
                    'area_sq_miles': iso_area,
                    'population_served': pop_served
                })
            else:
                print(f"  {minutes:2d}-min: failed")
            
            # small delay to avoid overwhelming valhalla
            time.sleep(0.15)
    
    # save results
    print("")
    print("SAVING RESULTS")
    print("")
    
    if all_isochrones:
        # combine all isochrone geodataframes into one
        combined_gdf = pd.concat(all_isochrones, ignore_index=True)
        
        # save geojson with all isochrones
        geojson_path = PROJECT_ROOT / "data" / "outputs" / "polling_isochrones_all.geojson"
        combined_gdf.to_file(geojson_path, driver='GeoJSON')
        print(f"Saved {len(combined_gdf)} isochrones to: {geojson_path}")
        
        # save summary statistics as csv
        summary_df = pd.DataFrame(summary_data)
        csv_path = PROJECT_ROOT / "data" / "outputs" / "polling_isochrone_summary.csv"
        summary_df.to_csv(csv_path, index=False)
        print(f"Saved summary to: {csv_path}")
        
        # print coverage statistics by time interval
        print("")
        print("COVERAGE STATISTICS")
        print("")
        
        for minutes in time_intervals:
            subset = summary_df[summary_df['time_minutes'] == minutes]
            if len(subset) > 0:
                avg_area = subset['area_sq_miles'].mean()
                total_area = subset['area_sq_miles'].sum()
                print(f"{minutes}-minute walking distance:")
                print(f"  Average walkable area: {avg_area:.2f} sq mi")
                print(f"  Total walkable area: {total_area:.2f} sq mi")
                print("")
        
        # identify best and worst coverage for 15-minute walk
        print("BEST AND WORST COVERAGE (15-minute walk)")
        print("")
        
        min15 = summary_df[summary_df['time_minutes'] == 15]
        if len(min15) > 0:
            best = min15.loc[min15['area_sq_miles'].idxmax()]
            worst = min15.loc[min15['area_sq_miles'].idxmin()]
            
            print(f"Best coverage: {best['polling_place']}")
            print(f"  Walkable area: {best['area_sq_miles']:.2f} sq mi")
            print(f"  Population served: {best['population_served']:,}")
            print("")
            
            print(f"Worst coverage: {worst['polling_place']}")
            print(f"  Walkable area: {worst['area_sq_miles']:.2f} sq mi")
            print(f"  Population served: {worst['population_served']:,}")
    



if __name__ == "__main__":
    main()