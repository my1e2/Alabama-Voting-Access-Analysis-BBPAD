"""
Polling Place Data Processing
Validates and standardizes client-provided polling location shapefile
Filters to Montgomery County only
"""

import geopandas as gpd
import pandas as pd
from pathlib import Path

# project root directory - three levels up from this script
PROJECT_ROOT = Path(__file__).parent.parent.parent


def load_client_polling_places():
    """
    load the client-provided polling place shapefile.
    
    reads the statewide alabama polling places shapefile containing
    all voting locations across the state. the file includes point
    geometries and attribute data for each polling place.
    
    returns geodataframe with all alabama polling places.
    """
    # path to statewide polling places shapefile
    shapefile_path = PROJECT_ROOT / "data" / "polling" / "raw" / "Polling-Places-Alabama" / "Al_Polls_Flood_SLED.shp"
    
    # read shapefile into geodataframe
    gdf = gpd.read_file(shapefile_path)
    
    print(f"Loaded {len(gdf)} total polling places (all Alabama)")
    print(f"CRS: {gdf.crs}")
    print(f"Columns: {list(gdf.columns)}")
    
    return gdf


def filter_to_montgomery(gdf):
    """
    filter the statewide polling places to only montgomery county.
    
    attempts to locate the county column using common naming conventions.
    filters records where the county name contains 'montgomery' in any case.
    
    args:
        gdf: geodataframe of all alabama polling places
        
    returns:
        geodataframe with only montgomery county polling places
    """
    # search for the county column using multiple common naming conventions
    county_column = None
    for possible_name in ['COUNTY', 'County', 'county', 'COUNTY_NAME', 'COUNTY_NAM', 'CNTY_NAME', 'NAME']:
        if possible_name in gdf.columns:
            county_column = possible_name
            break
    
    if county_column is None:
        print("")
        print("Warning: No county column found")
        print("Available columns:")
        for col in gdf.columns:
            print(f"  - {col}")
        print("")
        print("Please identify the county column and update the script")
        return gdf  # return unfiltered as fallback
    
    print(f"")
    print(f"Found county column: '{county_column}'")
    print(f"Unique values in this column: {gdf[county_column].unique()[:20]}")
    
    # filter to montgomery county using case-insensitive string matching
    # this handles variations like 'MONTGOMERY', 'Montgomery', 'montgomery'
    mask = gdf[county_column].astype(str).str.upper().str.contains('MONTGOMERY', na=False)
    montgomery_gdf = gdf[mask].copy()
    
    print(f"")
    print(f"Filtered from {len(gdf)} to {len(montgomery_gdf)} polling places in Montgomery County")
    
    return montgomery_gdf


def standardize_polling_place_fields(gdf):
    """
    standardize column names and create consistent identifiers.
    
    preserves all original columns and adds standardized fields for
    unique identification and coordinate access.
    
    args:
        gdf: geodataframe of montgomery county polling places
        
    returns:
        geodataframe with standardized fields added
    """
    # display original columns for reference and debugging
    print("")
    print("Original column names:")
    for col in gdf.columns:
        print(f"  - {col}")
    
    # add standardized fields while preserving all original data
    # create zero-padded unique identifier for each polling place
    gdf['polling_place_id'] = gdf.index.astype(str).str.zfill(4)
    
    # extract longitude and latitude from point geometry for easier access
    gdf['longitude'] = gdf.geometry.x
    gdf['latitude'] = gdf.geometry.y
    
    return gdf


def create_polling_place_database(gdf):
    """
    export polling place data to multiple formats for different use cases.
    
    saves both csv (non-spatial) and geojson (spatial web-friendly) formats
    to the processed data directory for downstream analysis and visualization.
    
    args:
        gdf: standardized geodataframe of montgomery county polling places
    """
    # save as csv for non-spatial analysis (drops geometry column)
    csv_path = PROJECT_ROOT / "data" / "polling" / "processed" / "polling_places_montgomery_clean_2020.csv"
    df = gdf.drop(columns=['geometry']).copy()
    df.to_csv(csv_path, index=False)
    
    # save as geojson for spatial analysis and web mapping
    geojson_path = PROJECT_ROOT / "data" / "polling" / "processed" / "polling_places_montgomery_2020.geojson"
    gdf.to_file(geojson_path, driver='GeoJSON')
    
    print(f"")
    print(f"Exported to: {csv_path}")
    print(f"Exported to: {geojson_path}")


def export_to_shapefile(gdf):
    """
    export the filtered montgomery county data to shapefile format.
    
    creates a shapefile in the precincts directory for use with
    arcgis and other traditional gis software.
    
    args:
        gdf: standardized geodataframe of montgomery county polling places
    """
    shp_path = PROJECT_ROOT / "data" / "shapefiles" / "precincts" / "montgomery_polling_places_2020.shp"
    gdf.to_file(shp_path)
    print(f"Exported Shapefile: {shp_path}")


if __name__ == "__main__":
    # main execution block - processes polling place data sequentially
    
    print("Polling place data processing")
    print("")
    
    # load statewide polling places shapefile
    polling_gdf = load_client_polling_places()
    
    # filter to montgomery county only
    montgomery_gdf = filter_to_montgomery(polling_gdf)
    
    # standardize fields and add identifiers
    standardized_gdf = standardize_polling_place_fields(montgomery_gdf)
    
    # export to multiple formats for downstream use
    create_polling_place_database(standardized_gdf)
    export_to_shapefile(standardized_gdf)
    
    # display summary statistics
    print("")
    print("Polling place summary")
    print("")
    print(f"Total Alabama polling places: {len(polling_gdf)}")
    print(f"Montgomery County polling places: {len(montgomery_gdf)}")
    
    if len(montgomery_gdf) > 0:
        print(f"")
        print(f"First 5 Montgomery polling places:")
        for i, row in standardized_gdf.head(5).iterrows():
            name_col = None
            for col in ['NAME', 'POLLING_NA', 'LOCATION', 'POLL_NAME']:
                if col in standardized_gdf.columns:
                    name_col = col
                    break
            if name_col:
                print(f"  - {row[name_col]}")