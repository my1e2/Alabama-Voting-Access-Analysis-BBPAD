"""
Distance Calculations for Voter Accessibility Analysis
Calculates Euclidean and Manhattan distance from population centers
to polling places and reference points
"""

import pandas as pd
import geopandas as gpd
import numpy as np
from pathlib import Path
from shapely.geometry import Point
from scipy.spatial.distance import cdist

# project root directory - three levels up from this script
PROJECT_ROOT = Path(__file__).parent.parent.parent

# reference points in montgomery county for civic infrastructure analysis
# coordinates sourced from official city records and community center listings
REFERENCE_POINTS = {
    'city_hall': {'lat': 32.37921, 'lon': -86.30792, 'name': 'Montgomery City Hall'},
    'loveless_cc': {'lat': 32.3542, 'lon': -86.3397, 'name': 'Loveless Community Center'},
    'houston_hill_cc': {'lat': 32.3746, 'lon': -86.3001, 'name': 'Houston Hill Community Center'},
    'highland_gardens_cc': {'lat': 32.3851, 'lon': -86.2725, 'name': 'Highland Gardens Community Center'},
    'hayneville_rd_cc': {'lat': 32.3209, 'lon': -86.3248, 'name': 'Hayneville Road Community Center'},
    'hunter_station_cc': {'lat': 32.3347, 'lon': -86.3572, 'name': 'Hunter Station Community Center'}
}


def load_population_centers():
    """
    load census 2020 centers of population for alabama.
    
    reads the comma-delimited text file from the census bureau and filters
    to montgomery county block groups only. creates a geoid column from
    component state, county, tract, and block group identifiers.
    
    returns:
        geodataframe: population centers with point geometries for montgomery county
    """
    # path to census bureau population centers file
    centers_path = PROJECT_ROOT / "data" / "census" / "raw" / "CenPop2020_Mean_BG01.txt"
    
    # read comma-delimited file with utf-8 encoding (handles byte order mark)
    df = pd.read_csv(centers_path, encoding='utf-8-sig')
    
    # display available columns for debugging and verification
    print(f"Available columns: {list(df.columns)}")
    
    # construct full 12-digit geoid from component parts
    # format: state (2) + county (3) + tract (6) + block group (1)
    df['GEOID'] = (
        df['STATEFP'].astype(str).str.zfill(2) + 
        df['COUNTYFP'].astype(str).str.zfill(3) + 
        df['TRACTCE'].astype(str).str.zfill(6) + 
        df['BLKGRPCE'].astype(str).str.zfill(1)
    )
    
    # filter to montgomery county only (fips code 01101 = state 01 + county 101)
    montgomery_centers = df[df['GEOID'].astype(str).str[:5] == '01101'].copy()
    
    print(f"Loaded {len(montgomery_centers)} population centers for Montgomery County")
    
    # create point geometries from longitude and latitude columns
    geometry = [Point(xy) for xy in zip(montgomery_centers['LONGITUDE'], montgomery_centers['LATITUDE'])]
    gdf = gpd.GeoDataFrame(montgomery_centers, geometry=geometry, crs="EPSG:4326")
    
    return gdf


def load_polling_places():
    """
    load processed polling places from geojson file.
    
    returns:
        geodataframe: polling place locations with point geometries
    """
    polling_path = PROJECT_ROOT / "data" / "polling" / "processed" / "polling_places_montgomery_2020.geojson"
    gdf = gpd.read_file(polling_path)
    return gdf


def calculate_euclidean_distances(pop_centers_gdf, polling_gdf):
    """
    calculate euclidean (straight-line) distances from each population center
    to all polling places. returns the minimum distance to any polling place.
    
    euclidean distance formula: sqrt((x2-x1)^2 + (y2-y1)^2)
    
    args:
        pop_centers_gdf: geodataframe of population centers
        polling_gdf: geodataframe of polling places
        
    returns:
        geodataframe: population centers with added distance columns
    """
    # extract coordinate arrays for vectorized distance calculation
    pop_coords = np.column_stack([
        pop_centers_gdf.geometry.x.values,
        pop_centers_gdf.geometry.y.values
    ])
    
    poll_coords = np.column_stack([
        polling_gdf.geometry.x.values,
        polling_gdf.geometry.y.values
    ])
    
    # calculate pairwise euclidean distances between all points
    # result is a matrix of shape (n_population_centers, n_polling_places)
    distances = cdist(pop_coords, poll_coords, metric='euclidean')
    
    # convert degrees to miles using approximation (1 degree latitude ≈ 69 miles)
    # note: this assumes relatively small geographic area where distortion is minimal
    distances_miles = distances * 69
    
    # find minimum distance to any polling place for each population center
    min_distances = distances_miles.min(axis=1)
    
    # find index of the nearest polling place (for reference)
    nearest_idx = distances_miles.argmin(axis=1)
    
    # add results to geodataframe
    pop_centers_gdf['min_dist_to_poll_miles'] = min_distances
    pop_centers_gdf['nearest_polling_idx'] = nearest_idx
    
    return pop_centers_gdf


def calculate_manhattan_distances(pop_centers_gdf, polling_gdf):
    """
    calculate manhattan (taxicab) distances from each population center
    to all polling places. returns the minimum manhattan distance.
    
    manhattan distance formula: |x2-x1| + |y2-y1|
    more appropriate for grid-based urban navigation than euclidean.
    
    args:
        pop_centers_gdf: geodataframe of population centers
        polling_gdf: geodataframe of polling places
        
    returns:
        geodataframe: population centers with added manhattan distance column
    """
    # extract coordinate arrays
    pop_coords = np.column_stack([
        pop_centers_gdf.geometry.x.values,
        pop_centers_gdf.geometry.y.values
    ])
    
    poll_coords = np.column_stack([
        polling_gdf.geometry.x.values,
        polling_gdf.geometry.y.values
    ])
    
    # calculate pairwise manhattan distances using cityblock metric
    distances = cdist(pop_coords, poll_coords, metric='cityblock')
    
    # convert degrees to miles (same approximation as euclidean)
    distances_miles = distances * 69
    
    # find minimum manhattan distance for each population center
    min_distances = distances_miles.min(axis=1)
    
    pop_centers_gdf['min_manhattan_dist_miles'] = min_distances
    
    return pop_centers_gdf


def calculate_distances_to_reference_points(pop_centers_gdf):
    """
    calculate distances from each population center to all reference points.
    returns the minimum distance to any reference point as a measure of
    proximity to civic infrastructure (city hall, community centers).
    
    args:
        pop_centers_gdf: geodataframe of population centers
        
    returns:
        geodataframe: population centers with reference point distance columns
    """
    # build coordinate array from reference points dictionary
    ref_coords = np.array([
        [ref['lon'], ref['lat']] for ref in REFERENCE_POINTS.values()
    ])
    
    # extract population center coordinates
    pop_coords = np.column_stack([
        pop_centers_gdf.geometry.x.values,
        pop_centers_gdf.geometry.y.values
    ])
    
    # calculate euclidean distances to all reference points
    distances = cdist(pop_coords, ref_coords, metric='euclidean')
    distances_miles = distances * 69
    
    # minimum distance to any reference point (civic infrastructure access)
    pop_centers_gdf['min_dist_to_civic_center_miles'] = distances_miles.min(axis=1)
    
    # distance specifically to city hall (primary civic landmark)
    city_hall_idx = list(REFERENCE_POINTS.keys()).index('city_hall')
    pop_centers_gdf['dist_to_city_hall_miles'] = distances_miles[:, city_hall_idx]
    
    return pop_centers_gdf


def calculate_accessibility_score(pop_centers_gdf):
    """
    create a composite accessibility score based on multiple distance metrics.
    
    components (lower score indicates better accessibility):
        - distance to nearest polling place (euclidean) - 40% weight
        - distance to nearest polling place (manhattan) - 30% weight
        - distance to civic center or reference point - 30% weight
    
    all components are normalized to 0-1 scale before combination.
    
    args:
        pop_centers_gdf: geodataframe with distance columns
        
    returns:
        geodataframe: population centers with accessibility scores and categories
    """
    # list of distance components to normalize
    components = ['min_dist_to_poll_miles', 'min_manhattan_dist_miles', 
                  'min_dist_to_civic_center_miles']
    
    # normalize each component to range [0, 1] using min-max scaling
    for col in components:
        if col in pop_centers_gdf.columns:
            min_val = pop_centers_gdf[col].min()
            max_val = pop_centers_gdf[col].max()
            
            if max_val > min_val:
                pop_centers_gdf[f'{col}_norm'] = (pop_centers_gdf[col] - min_val) / (max_val - min_val)
            else:
                # handle case where all values are identical
                pop_centers_gdf[f'{col}_norm'] = 0
    
    # calculate weighted composite score
    # weights based on relative importance of each metric
    pop_centers_gdf['accessibility_score'] = (
        pop_centers_gdf['min_dist_to_poll_miles_norm'] * 0.4 +
        pop_centers_gdf['min_manhattan_dist_miles_norm'] * 0.3 +
        pop_centers_gdf['min_dist_to_civic_center_miles_norm'] * 0.3
    )
    
    # categorize accessibility scores into interpretable labels
    # lower score = better accessibility
    pop_centers_gdf['accessibility_category'] = pd.cut(
        pop_centers_gdf['accessibility_score'],
        bins=[0, 0.25, 0.50, 0.75, 1.0],
        labels=['Excellent', 'Good', 'Fair', 'Poor']
    )
    
    return pop_centers_gdf


def create_distance_matrix(pop_centers_gdf, polling_gdf):
    """
    create a full distance matrix between all population centers and polling places.
    saved to csv for detailed analysis and spatial queries.
    
    args:
        pop_centers_gdf: geodataframe of population centers
        polling_gdf: geodataframe of polling places
        
    returns:
        dataframe: matrix with rows as population centers, columns as polling places
    """
    # extract coordinate arrays
    pop_coords = np.column_stack([
        pop_centers_gdf.geometry.x.values,
        pop_centers_gdf.geometry.y.values
    ])
    
    poll_coords = np.column_stack([
        polling_gdf.geometry.x.values,
        polling_gdf.geometry.y.values
    ])
    
    # calculate full pairwise distance matrix
    distances = cdist(pop_coords, poll_coords, metric='euclidean')
    distances_miles = distances * 69
    
    # create dataframe with meaningful index and column names
    matrix_df = pd.DataFrame(
        distances_miles,
        index=pop_centers_gdf['GEOID'],
        columns=[f"poll_{i}" for i in range(len(polling_gdf))]
    )
    
    # save matrix to csv for later analysis
    output_path = PROJECT_ROOT / "data" / "outputs" / "distance_matrix_montgomery.csv"
    matrix_df.to_csv(output_path)
    
    print(f"Distance matrix saved to {output_path}")
    print(f"Dimensions: {matrix_df.shape[0]} centers x {matrix_df.shape[1]} polling places")
    
    return matrix_df


def main():
    """
    main execution function.
    
    loads population centers and polling places, calculates multiple distance
    metrics, creates accessibility scores, and saves all results to csv.
    """
    print("Distance Calculations for Montgomery County\n")
    
    # load input data
    print("Loading population centers\n")
    pop_centers = load_population_centers()
    
    print("Loading polling places\n")
    polling = load_polling_places()
    
    # calculate distance metrics
    print("\nCalculating Euclidean distances\n")
    pop_centers = calculate_euclidean_distances(pop_centers, polling)
    
    print("Calculating Manhattan distances\n")
    pop_centers = calculate_manhattan_distances(pop_centers, polling)
    
    print("Calculating distances to reference points\n")
    pop_centers = calculate_distances_to_reference_points(pop_centers)
    
    print("Calculating accessibility scores\n")
    pop_centers = calculate_accessibility_score(pop_centers)
    
    # create and save full distance matrix
    print("\nCreating full distance matrix\n")
    matrix = create_distance_matrix(pop_centers, polling)
    
    # save complete results to csv
    output_path = PROJECT_ROOT / "data" / "outputs" / "accessibility_scores_by_tract.csv"
    pop_centers.to_csv(output_path, index=False)
    print(f"\nAccessibility scores saved to {output_path}")
    
    # display summary statistics
    print("\nAccessibility Summary Statistics")
    print(f"Average distance to nearest poll -- Euclidean (miles): {pop_centers['min_dist_to_poll_miles'].mean():.2f}")
    print(f"Maximum distance to nearest poll -- Euclidean (miles): {pop_centers['min_dist_to_poll_miles'].max():.2f}")
    print(f"Average Manhattan distance (miles): {pop_centers['min_manhattan_dist_miles'].mean():.2f}")
    print(f"Average distance to civic center -- Euclidean (miles): {pop_centers['min_dist_to_civic_center_miles'].mean():.2f}")
    
    print("\nAccessibility Category Distribution:")
    print(pop_centers['accessibility_category'].value_counts().sort_index())
    
    return pop_centers


if __name__ == "__main__":
    results = main()