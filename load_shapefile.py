import geopandas as gpd
import pandas as pd
pd.set_option('display.max_columns', None)

file_path = "data/raw/polling_places/Al_Polls_Flood_SLED.shp"

polls = gpd.read_file(file_path)

tracts = gpd.read_file("data/raw/Alabama_Census_Tracts_2020/Alabama_Census_Tracts%2C_2020.shp")

print("Polls CRS:", polls.crs)
print("Tracts CRS:", tracts.crs)

#Results:
#Location: Longitude, Latitude
#Voting/Precinct: Precinct, PrecintNu, Country
#Address info: Address, City, Zip
#Flood/Haxard Metabada: FLD_ZONE, ZONE_SUBTY
#MatchType, NumMatch

#Focus on specific counties within Alabama, those included in the black belt
gdf_clean = polls[['County', 'Precinct', 'Address', 'geometry']]
black_belt = [
    "Montgomery", "Dallas", "Perry", "Lowndes", "Sumter",
    "Wilcox", "Greene", "Hale", "Bullock", "Macon"
]

#If county is in the black belt, print out the county and the count of polls
bb_data = polls[polls['County'].isin(black_belt)]
print(bb_data.head())
print(polls['County'].value_counts())


polls_clean = polls[['Precinct', 'Address', 'City', 'Zip', 'County', 'geometry']]

#Will be extracting specifically these variables - Lat/Long Version
#polls_clean['lon'] = polls_clean.geometry.x
#polls_clean['lat'] = polls_clean.geometry.y

#polls_clean.to_csv("clean_polling_data.csv", index=False)

#Will be extracting specifically these variables - Converted to US National Albers

if polls_clean.crs is None:
    polls_clean = polls_clean.set_crs(epsg=4326)

if tracts.crs is None:
    tracts = tracts.set_crs(epsg=4326)

polls_clean = polls_clean.to_crs(epsg=5070)
tracts = tracts.to_crs(epsg=5070)

print("Projected CRS:", polls_clean.crs)

print("Poll bounds:", polls_clean.total_bounds)
print("Tract bounds:", tracts.total_bounds)

tracts = tracts[tracts.geometry.is_valid & tracts.geometry.notnull()].copy()
polls_clean = polls_clean[polls_clean.geometry.is_valid & polls_clean.geometry.notnull()].copy()

"""
tract_centroids = tracts.copy()
tract_centroids["centroid"] = tract_centroids.geometry.centroid
tract_centroids = tract_centroids.set_geometry("centroid")
"""
tract_centroids = tracts.copy()

# create centroid geometry
tract_centroids["centroid"] = tract_centroids.geometry.centroid

# DROP original polygon geometry completely
tract_centroids = tract_centroids.drop(columns=["geometry"])

# now set centroid as ONLY geometry
tract_centroids = gpd.GeoDataFrame(
    tract_centroids,
    geometry="centroid",
    crs=tracts.crs
)

#added
if "GEOID20" in tract_centroids.columns:
    tract_centroids = tract_centroids.rename(columns={"GEOID20": "GEOID"})

#poll_union = polls_clean.geometry.union_all()
#tract_centroids["nearest_poll_m"] = tract_centroids.geometry.distance(poll_union)

polls_sindex = polls_clean.sindex

def nearest_distance(point, gdf):
    nearest_geom = gdf.geometry.distance(point).min()
    return nearest_geom

tract_centroids["nearest_poll_m"] = tract_centroids.geometry.apply(
    lambda x: polls_clean.distance(x).min()
)

tract_centroids["nearest_poll_miles"] = tract_centroids["nearest_poll_m"] / 1609.34


print(tract_centroids[["GEOID", "nearest_poll_miles"]].head())
print(tract_centroids["nearest_poll_miles"].describe())


#tract_centroids = tract_centroids.drop(columns=["geometry"])
#Updated
tract_centroids.to_csv("tract_polling_distances.csv", index = False)


#added
#tract_centroids = tract_centroids.drop(columns=["geometry"])

#tract_centroids.to_file("tract_polling_distances.geojson", driver="GeoJSON")

#Analysis Based Questions
#How many communities are more than 5 miles from a polling place?

far_tracts = tract_centroids[tract_centroids["nearest_poll_miles"] > 5]
print("Number of tracts > 5 miles:", len(far_tracts))

print(tracts.columns)

tract_info = tracts[[
    "GEOID",
    "NAMELSAD20",
    "COUNTYFP20",
    "POP20"
]].copy()

#final_df = tract_centroids.merge(tract_info, on="GEOID", how="left")

# make sure GEOID is clean in BOTH tables
tract_centroids["GEOID"] = tract_centroids["GEOID"].astype(str)
tract_info["GEOID"] = tract_info["GEOID"].astype(str)

# drop duplicate GEOID columns if they exist
tract_centroids = tract_centroids.loc[:, ~tract_centroids.columns.duplicated()]
tract_info = tract_info.loc[:, ~tract_info.columns.duplicated()]

# merge safely
final_df = pd.merge(
    tract_centroids,
    tract_info,
    on="GEOID",
    how="left",
    suffixes=("", "_drop")
)

final_df = final_df.loc[:, ~final_df.columns.duplicated()]

final_df = final_df[[c for c in final_df.columns if not c.endswith("_drop")]]

final_df = final_df[[
    "GEOID",
    "NAMELSAD20",
    "COUNTYFP20",
    "POP20",
    "nearest_poll_miles",
    "centroid"
]].copy()


# make sure geometry column is clean and single
final_gdf = final_df.copy()

# ensure correct geometry column
final_gdf = gpd.GeoDataFrame(
    final_gdf,
    geometry="centroid",
    crs=tracts.crs
)

# drop ANY duplicate column names (critical fix)
final_gdf = final_gdf.loc[:, ~final_gdf.columns.duplicated()]

# make sure no leftover geometry conflicts exist
final_gdf = final_gdf.drop(columns=[
    col for col in final_gdf.columns
    if col != "centroid" and "geom" in col.lower()
], errors="ignore")

# export
final_gdf.to_file("tract_polling_distances.geojson", driver="GeoJSON")

def access_level(miles):
    if miles < 1:
        return "Very Close"
    elif miles < 3:
        return "Moderate"
    elif miles < 5:
        return "Limited"
    else:
        return "Poor Access"

final_df["Access_Level"] = final_df["nearest_poll_miles"].apply(access_level)

final_df.drop(columns=["centroid"]).to_csv(
    "final_polling_access_table.csv",
    index=False
)

import matplotlib.pyplot as plt
import geopandas as gpd

map_gdf = gpd.GeoDataFrame(
    final_df,
    geometry="centroid",
    crs=tracts.crs
)

fig, ax = plt.subplots(1, 1, figsize=(12, 10))

final_gdf.plot(
    column="nearest_poll_miles",
    cmap="YlOrRd",
    legend=True,
    ax=ax
)

ax.set_title("Polling Accessibility by Census Tract (Alabama)", fontsize=14)
ax.set_axis_off()

plt.savefig(
    "alabama_polling_access_map.png",
    dpi=300,
    bbox_inches="tight"
)

plt.show()

far = map_gdf[map_gdf["Nearest_Poll_Miles"] > 5]

for idx, row in far.iterrows():
    ax.annotate(
        text=row["GEOID"],
        xy=(row.geometry.x, row.geometry.y),
        fontsize=8,
        color="black"
    )

plt.show()