"""
Enhanced Walkability Analysis
Adds OSM sidewalk data and walkability scores to accessibility results
Uses buffer along actual OSRM walking routes
"""

import pandas as pd
import geopandas as gpd
import numpy as np
import warnings
from pathlib import Path
from shapely.geometry import LineString, Point

warnings.filterwarnings('ignore', 'Geometry is in a geographic CRS')

# project root directory - three levels up from this script
PROJECT_ROOT = Path(__file__).parent.parent.parent


def load_complete_distances():
    """
    load the merged distance results from previous calculations.
    
    attempts to load the complete merged file first, falls back to
    google walking results if complete file not found.
    
    returns dataframe with distance metrics for all population centers.
    """
    path = PROJECT_ROOT / "data" / "outputs" / "accessibility_scores_complete.csv"
    if path.exists():
        df = pd.read_csv(path)
    else:
        path = PROJECT_ROOT / "data" / "outputs" / "accessibility_scores_google_walking.csv"
        df = pd.read_csv(path)
    df['GEOID'] = df['GEOID'].astype(str)
    return df


def load_paving_data():
    """
    load montgomery county paving project data.
    
    searches multiple possible file paths for the paving dataset.
    this data contains road quality and construction status information.
    
    returns geodataframe with paving segments, or none if not found.
    """
    possible_paths = [
        PROJECT_ROOT / "data" / "infrastructure" / "montgomery_paving.geojson",
        PROJECT_ROOT / "data" / "infrastructure" / "Paving_Project.geojson",
        PROJECT_ROOT / "data" / "infrastructure" / "paving.geojson",
    ]
    for path in possible_paths:
        if path.exists():
            return gpd.read_file(path)
    return None


def load_population_centers():
    """
    load census 2020 centers of population with geometries.
    
    reads the comma-delimited text file from the census bureau and filters
    to montgomery county block groups only. creates point geometries from
    longitude and latitude coordinates.
    
    returns geodataframe with population centers for montgomery county.
    """
    centers_path = PROJECT_ROOT / "data" / "census" / "raw" / "CenPop2020_Mean_BG01.txt"
    df = pd.read_csv(centers_path, encoding='utf-8-sig')
    
    # construct full 12-digit geoid from component parts
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
    gdf = gpd.GeoDataFrame(montgomery, geometry=geometry, crs="EPSG:4326")
    
    return gdf


def load_polling_places():
    """
    load polling place locations from geojson file.
    
    attempts to load the 2020 version first, falls back to generic
    montgomery polling places file if 2020 version not found.
    
    returns geodataframe with polling place locations.
    """
    path = PROJECT_ROOT / "data" / "polling" / "processed" / "polling_places_montgomery_2020.geojson"
    if not path.exists():
        path = PROJECT_ROOT / "data" / "polling" / "processed" / "polling_places_montgomery.geojson"
    gdf = gpd.read_file(path)
    return gdf


def load_or_download_osm_data():
    """
    load openstreetmap sidewalk data, downloading if necessary.
    
    checks for cached osm data file first. if not found, downloads
    road network with sidewalk tags from openstreetmap using osmnx.
    
    returns geodataframe with road segments and sidewalk information.
    """
    osm_path = PROJECT_ROOT / "data" / "infrastructure" / "osm_roads_montgomery_enhanced.geojson"
    
    if osm_path.exists():
        print(f"Loading existing OSM data from {osm_path}")
        return gpd.read_file(osm_path)
    
    print("Downloading Montgomery County road network from OpenStreetMap")
    
    try:
        import osmnx as ox
        gdf = ox.features_from_place(
            "Montgomery County, Alabama, USA",
            tags={"highway": True}
        )
        
        # keep only columns relevant to sidewalk analysis
        cols_to_keep = ['highway', 'sidewalk', 'footway', 'name', 'geometry']
        available_cols = [c for c in cols_to_keep if c in gdf.columns]
        gdf = gdf[available_cols].copy()
        
        # helper function to determine if a road segment has a sidewalk
        def has_sidewalk(row):
            if 'sidewalk' in row and pd.notna(row['sidewalk']):
                sidewalk_val = str(row['sidewalk']).lower()
                return sidewalk_val in ['yes', 'both', 'right', 'left', 'separate']
            if 'footway' in row and pd.notna(row['footway']):
                footway_val = str(row['footway']).lower()
                return footway_val in ['sidewalk', 'yes', 'both']
            return None
        
        gdf['sidewalk_present'] = gdf.apply(has_sidewalk, axis=1)
        
        osm_path.parent.mkdir(parents=True, exist_ok=True)
        gdf.to_file(osm_path, driver='GeoJSON')
        print(f"Downloaded {len(gdf)} road segments")
        print(f"Saved to {osm_path}")
        
        return gdf
        
    except Exception as e:
        print(f"Could not download OSM data: {e}")
        return None


def analyze_osm_sidewalk_coverage(origin_point, dest_point, osm_gdf, buffer_distance_miles=0.05):
    """
    analyze sidewalk coverage along route using openstreetmap data.
    
    creates a buffer corridor around the straight-line path and identifies
    intersecting osm road segments. calculates percentage of the corridor
    that has explicit sidewalk tags.
    
    args:
        origin_point: shapely point for starting location
        dest_point: shapely point for destination location
        osm_gdf: geodataframe of osm road segments
        buffer_distance_miles: width of corridor in miles
        
    returns:
        dictionary with sidewalk coverage metrics
    """
    if osm_gdf is None:
        return {
            'osm_coverage_pct': 0,
            'osm_has_sidewalk': False,
            'osm_sidewalk_segments': 0,
            'osm_no_sidewalk_segments': 0,
            'osm_segments_checked': 0
        }
    
    # create a corridor along the route for intersection analysis
    line = LineString([origin_point, dest_point])
    buffer_degrees = buffer_distance_miles * 0.01
    corridor = line.buffer(buffer_degrees)
    
    # find osm segments that intersect the corridor
    intersecting = osm_gdf[osm_gdf.intersects(corridor)].copy()
    
    if len(intersecting) == 0:
        return {
            'osm_coverage_pct': 0,
            'osm_has_sidewalk': False,
            'osm_sidewalk_segments': 0,
            'osm_no_sidewalk_segments': 0,
            'osm_segments_checked': 0
        }
    
    # count segments with and without sidewalk tags
    if 'sidewalk_present' in intersecting.columns:
        sidewalk_segs = intersecting[intersecting['sidewalk_present'] == True]
        no_sidewalk_segs = intersecting[intersecting['sidewalk_present'] == False]
        
        # calculate coverage percentage based on segment lengths
        total_length = intersecting.geometry.length.sum()
        sidewalk_length = sidewalk_segs.geometry.length.sum() if len(sidewalk_segs) > 0 else 0
        coverage_pct = (sidewalk_length / total_length * 100) if total_length > 0 else 0
        
        return {
            'osm_coverage_pct': coverage_pct,
            'osm_has_sidewalk': len(sidewalk_segs) > 0,
            'osm_sidewalk_segments': len(sidewalk_segs),
            'osm_no_sidewalk_segments': len(no_sidewalk_segs),
            'osm_segments_checked': len(intersecting)
        }
    
    return {
        'osm_coverage_pct': 0,
        'osm_has_sidewalk': False,
        'osm_sidewalk_segments': 0,
        'osm_no_sidewalk_segments': 0,
        'osm_segments_checked': len(intersecting)
    }


def analyze_paving_coverage(origin_point, dest_point, paving_gdf, buffer_distance_miles=0.05):
    """
    analyze road quality using paving project data.
    
    creates a buffer corridor along the route and identifies intersecting
    paving segments. calculates an average road quality score based on
    road class, width, and construction status.
    
    args:
        origin_point: shapely point for starting location
        dest_point: shapely point for destination location
        paving_gdf: geodataframe of paving project segments
        buffer_distance_miles: width of corridor in miles
        
    returns:
        dictionary with paving coverage and quality metrics
    """
    if paving_gdf is None:
        return {
            'paving_coverage_pct': 0,
            'paving_avg_score': 50,
            'paving_segments_analyzed': 0
        }
    
    # create a corridor along the route for intersection analysis
    line = LineString([origin_point, dest_point])
    buffer_degrees = buffer_distance_miles * 0.01
    corridor = line.buffer(buffer_degrees)
    
    # find paving segments that intersect the corridor
    intersecting = paving_gdf[paving_gdf.intersects(corridor)].copy()
    
    if len(intersecting) == 0:
        return {
            'paving_coverage_pct': 0,
            'paving_avg_score': 50,
            'paving_segments_analyzed': 0
        }
    
    # score each intersecting segment based on road characteristics
    scores = []
    for _, seg in intersecting.iterrows():
        score = 50  # baseline neutral score
        
        # adjust score based on road classification
        road_class = str(seg.get('Class', '')).upper()
        if 'ARTERIAL' in road_class or 'HIGHWAY' in road_class:
            score -= 20  # less pedestrian friendly
        elif 'COLLECTOR' in road_class:
            score -= 10
        elif 'LOCAL' in road_class:
            score += 10  # more pedestrian friendly
        
        # adjust score based on road width
        width = seg.get('Width_ft', 0)
        if pd.notna(width):
            if width < 25:
                score += 10  # narrower roads better for pedestrians
            elif width > 40:
                score -= 10  # wider roads less pedestrian friendly
        
        # adjust score based on construction status
        status = str(seg.get('Status', '')).upper()
        if 'COMPLETE' in status:
            score += 10
        elif 'IN PROGRESS' in status:
            score += 5
        
        scores.append(max(0, min(100, score)))
    
    avg_score = np.mean(scores) if scores else 50
    
    # calculate what percentage of the route has paving data
    total_length = intersecting.geometry.length.sum()
    path_length = line.length
    coverage_pct = min((total_length / path_length) * 100, 100) if path_length > 0 else 0
    
    return {
        'paving_coverage_pct': coverage_pct,
        'paving_avg_score': avg_score,
        'paving_segments_analyzed': len(intersecting)
    }


def calculate_composite_walkability(distance, paving_score, osm_has_sidewalk, osm_coverage):
    """
    calculate final walkability score combining all metrics.
    
    combines distance, road quality, and sidewalk availability into
    a single walkability score from 0-100. higher scores indicate
    better walkability.
    
    args:
        distance: walking distance in miles
        paving_score: road quality score from 0-100
        osm_has_sidewalk: boolean indicating sidewalk presence
        osm_coverage: percentage of route with sidewalk coverage
        
    returns:
        tuple of (total_score, category_label)
    """
    # distance component (0-40 points)
    # shorter distances receive higher scores
    if pd.isna(distance):
        dist_score = 20  # neutral if unknown
    elif distance < 0.5:
        dist_score = 40
    elif distance < 1.0:
        dist_score = 32
    elif distance < 2.0:
        dist_score = 24
    elif distance < 3.0:
        dist_score = 16
    elif distance < 5.0:
        dist_score = 8
    else:
        dist_score = 0
    
    # road quality component (0-30 points)
    # better road conditions receive higher scores
    if pd.isna(paving_score):
        road_score = 15
    else:
        road_score = (paving_score / 100) * 30
    
    # sidewalk component (0-30 points)
    # presence and coverage of sidewalks determines score
    if osm_has_sidewalk:
        sidewalk_score = 20 + (osm_coverage / 100) * 10  # 20-30 points
    elif osm_coverage > 0:
        sidewalk_score = osm_coverage / 100 * 15  # partial credit
    else:
        sidewalk_score = 0
    
    total_score = dist_score + road_score + sidewalk_score
    
    # categorize the composite score
    if total_score >= 80:
        category = "Excellent"
    elif total_score >= 60:
        category = "Good"
    elif total_score >= 40:
        category = "Fair"
    elif total_score >= 20:
        category = "Poor"
    else:
        category = "Very Poor"
    
    return total_score, category


def main():
    """
    main execution function.
    
    loads all required datasets, analyzes sidewalk coverage and road quality
    for each population center's route to its nearest polling place, calculates
    composite walkability scores, and saves enhanced results.
    """
    print("Enhanced walkability analysis")
    print("Distance plus paving data plus OSM sidewalk tags")
    print("")
    
    # load all input data
    print("Loading data")
    
    df_distances = load_complete_distances()
    print(f"Loaded {len(df_distances)} distance records")
    
    centers_gdf = load_population_centers()
    print(f"Loaded {len(centers_gdf)} population centers")
    
    polling_gdf = load_polling_places()
    print(f"Loaded {len(polling_gdf)} polling places")
    
    paving_gdf = load_paving_data()
    if paving_gdf is not None:
        print(f"Loaded {len(paving_gdf)} paving segments")
    else:
        print("No paving data available")
    
    osm_gdf = load_or_download_osm_data()
    if osm_gdf is not None:
        print(f"OSM data ready: {len(osm_gdf)} road segments")
        if 'sidewalk_present' in osm_gdf.columns:
            explicit_yes = (osm_gdf['sidewalk_present'] == True).sum()
            explicit_no = (osm_gdf['sidewalk_present'] == False).sum()
            print(f"  - Explicit sidewalk=yes: {explicit_yes}")
            print(f"  - Explicit sidewalk=no: {explicit_no}")
    else:
        print("No OSM sidewalk data available")
    
    print("")
    
    # initialize results columns in the dataframe
    df_distances['osm_coverage_pct'] = np.nan
    df_distances['osm_has_sidewalk'] = False
    df_distances['osm_sidewalk_segments'] = 0
    df_distances['osm_no_sidewalk_segments'] = 0
    df_distances['osm_segments_checked'] = 0
    df_distances['paving_coverage_pct'] = np.nan
    df_distances['paving_avg_score'] = np.nan
    df_distances['paving_segments_analyzed'] = 0
    df_distances['walkability_score'] = np.nan
    df_distances['walkability_category'] = 'Unknown'
    
    print("Analyzing routes")
    
    # process each population center
    for idx, row in df_distances.iterrows():
        if idx % 25 == 0:
            print(f"  Processing center {idx+1}/{len(df_distances)}")
        
        # get geoid and find corresponding center point
        geoid = str(row['GEOID'])
        if not geoid.startswith('0') and len(geoid) < 11:
            geoid = '0' + geoid
        
        center_match = centers_gdf[centers_gdf['GEOID'] == geoid]
        if len(center_match) == 0:
            continue
        
        center_point = center_match.iloc[0].geometry
        
        # get walking distance (prefer google, fallback to osrm walking, then driving)
        distance = row.get('min_google_walking_dist_miles',
                          row.get('min_walking_dist_miles',
                          row.get('min_network_dist_miles', np.nan)))
        
        # find index of nearest polling place
        poll_idx = None
        for col in ['nearest_poll_google_walking_idx', 'nearest_poll_walking_idx', 'nearest_poll_network_idx']:
            if col in row and pd.notna(row[col]):
                poll_idx = int(row[col])
                break
        
        if poll_idx is None or poll_idx >= len(polling_gdf):
            continue
        
        poll_point = polling_gdf.iloc[poll_idx].geometry
        
        # analyze sidewalk coverage along the route
        osm_result = analyze_osm_sidewalk_coverage(center_point, poll_point, osm_gdf)
        df_distances.loc[idx, 'osm_coverage_pct'] = osm_result['osm_coverage_pct']
        df_distances.loc[idx, 'osm_has_sidewalk'] = osm_result['osm_has_sidewalk']
        df_distances.loc[idx, 'osm_sidewalk_segments'] = osm_result['osm_sidewalk_segments']
        df_distances.loc[idx, 'osm_no_sidewalk_segments'] = osm_result['osm_no_sidewalk_segments']
        df_distances.loc[idx, 'osm_segments_checked'] = osm_result['osm_segments_checked']
        
        # analyze road quality along the route
        paving_result = analyze_paving_coverage(center_point, poll_point, paving_gdf)
        df_distances.loc[idx, 'paving_coverage_pct'] = paving_result['paving_coverage_pct']
        df_distances.loc[idx, 'paving_avg_score'] = paving_result['paving_avg_score']
        df_distances.loc[idx, 'paving_segments_analyzed'] = paving_result['paving_segments_analyzed']
        
        # calculate composite walkability score
        total_score, category = calculate_composite_walkability(
            distance,
            paving_result['paving_avg_score'],
            osm_result['osm_has_sidewalk'],
            osm_result['osm_coverage_pct']
        )
        
        df_distances.loc[idx, 'walkability_score'] = total_score
        df_distances.loc[idx, 'walkability_category'] = category
    
    # display summary statistics
    print("")
    print("Walkability summary")
    print("")
    
    print("OSM Sidewalk Data:")
    if 'osm_has_sidewalk' in df_distances.columns:
        routes_with_sidewalks = df_distances['osm_has_sidewalk'].sum()
        pct_sidewalks = routes_with_sidewalks/len(df_distances)*100
        print(f"  Routes with explicit sidewalks: {routes_with_sidewalks}/{len(df_distances)} ({pct_sidewalks:.1f} percent)")
    
    if 'osm_coverage_pct' in df_distances.columns:
        avg_osm = df_distances['osm_coverage_pct'].mean()
        print(f"  Average OSM sidewalk coverage: {avg_osm:.1f} percent")
    
    print("")
    print("Paving Data:")
    if 'paving_avg_score' in df_distances.columns:
        avg_paving = df_distances['paving_avg_score'].mean()
        print(f"  Average road quality score: {avg_paving:.1f}/100")
    
    if 'paving_coverage_pct' in df_distances.columns:
        avg_paving_cov = df_distances['paving_coverage_pct'].mean()
        print(f"  Average paving data coverage: {avg_paving_cov:.1f} percent")
    
    print("")
    print("Final Walkability Categories:")
    if 'walkability_category' in df_distances.columns:
        category_counts = df_distances['walkability_category'].value_counts().sort_index()
        for cat, count in category_counts.items():
            pct = count / len(df_distances) * 100
            print(f"  {cat}: {count} ({pct:.1f} percent)")
    
    # save enhanced results
    output_path = PROJECT_ROOT / "data" / "outputs" / "accessibility_scores_enhanced_complete.csv"
    df_distances.to_csv(output_path, index=False)
    print(f"")
    print(f"Saved enhanced results to: {output_path}")
    
    # identify critical priority areas with very poor walkability
    print("")
    print("Critical priority areas (Very Poor Walkability):")
    very_poor = df_distances[df_distances['walkability_category'] == 'Very Poor']
    if len(very_poor) > 0:
        for _, row in very_poor.head(10).iterrows():
            distance = row.get('min_google_walking_dist_miles',
                              row.get('min_walking_dist_miles', 'N/A'))
            osm_sidewalk = "Yes" if row.get('osm_has_sidewalk', False) else "No"
            if pd.notna(distance):
                print(f"  GEOID {row['GEOID']}: {distance:.2f} miles, Sidewalk: {osm_sidewalk}, Score: {row['walkability_score']:.0f}")
    else:
        print("  None identified")
    
    print("")

    return df_distances


if __name__ == "__main__":
    enhanced = main()