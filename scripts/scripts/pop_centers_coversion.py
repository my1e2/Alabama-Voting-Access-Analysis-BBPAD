"""
Create Population Centers GeoJSON for Mapping
Converts census population center data to spatial format for visualization
"""

import pandas as pd
import geopandas as gpd
from pathlib import Path
from shapely.geometry import Point

# project root directory - three levels up from this script
PROJECT_ROOT = Path(__file__).parent.parent.parent

# load census 2020 centers of population data
# file contains population-weighted centroids for all census block groups
centers_path = PROJECT_ROOT / "data" / "census" / "raw" / "CenPop2020_Mean_BG01.txt"
df = pd.read_csv(centers_path, encoding='utf-8-sig')

# construct full 12-digit geoid from component parts
# format: state (2) + county (3) + tract (6) + block group (1)
df['GEOID'] = (
    df['STATEFP'].astype(str).str.zfill(2) + 
    df['COUNTYFP'].astype(str).str.zfill(3) + 
    df['TRACTCE'].astype(str).str.zfill(6) + 
    df['BLKGRPCE'].astype(str).str.zfill(1)
)

# filter to montgomery county only using fips code prefix
# montgomery county fips is 01101 (state 01 + county 101)
montgomery = df[df['GEOID'].astype(str).str[:5] == '01101'].copy()

# create point geometries from longitude and latitude coordinates
geometry = [Point(xy) for xy in zip(montgomery['LONGITUDE'], montgomery['LATITUDE'])]
gdf = gpd.GeoDataFrame(montgomery, geometry=geometry, crs="EPSG:4326")

# save as geojson for web mapping and spatial analysis
output_path = PROJECT_ROOT / "data" / "outputs" / "population_centers_montgomery.geojson"
gdf.to_file(output_path, driver='GeoJSON')

print(f"Saved {len(gdf)} population centers to: {output_path}")
print(f"Total population: {gdf['POPULATION'].sum():,}")