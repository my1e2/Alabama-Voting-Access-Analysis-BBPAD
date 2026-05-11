import pandas as pd
import geopandas as gpd
from shapely import wkt

# load the export

df = pd.read_csv("/tmp/arcgis_export.csv")

# convert WKT geometry to shapely geometries

df['geometry'] = df['wkt_geometry'].apply(wkt.loads)

# create GeoDataFrame

gdf = gpd.GeoDataFrame(df, geometry='geometry', crs="EPSG:4326")

# save as GeoJSON (ArcGIS Online compatible)

gdf.to_file("/tmp/montgomery_accessibility.geojson", driver='GeoJSON')

# also save polling places

polling_df = pd.read_csv("/tmp/polling_places_export.csv")
polling_df['geometry'] = polling_df['wkt_geometry'].apply(wkt.loads)
polling_gdf = gpd.GeoDataFrame(polling_df, geometry='geometry', crs="EPSG:4326")
polling_gdf.to_file("/tmp/montgomery_polling_places.geojson", driver='GeoJSON')

print(f"Exported {len(gdf)} block groups and {len(polling_gdf)} polling places")