"""
Enhanced Map: Isochrones and Population Centers with Basemap
Creates a detailed visualization of walkable areas with demographic overlay
"""

import geopandas as gpd
import matplotlib.pyplot as plt
import contextily as ctx
from matplotlib.lines import Line2D
from pathlib import Path
import numpy as np

# project root directory - three levels up from this script
PROJECT_ROOT = Path(__file__).parent.parent.parent

# load all required spatial datasets
isochrones = gpd.read_file(PROJECT_ROOT / "data" / "outputs" / "polling_isochrones_all.geojson")
population = gpd.read_file(PROJECT_ROOT / "data" / "outputs" / "population_centers_montgomery.geojson")
polling = gpd.read_file(PROJECT_ROOT / "data" / "polling" / "processed" / "polling_places_montgomery_2020.geojson")

# convert all layers to web mercator projection for basemap compatibility
# epsg:3857 is required for contextily basemaps
isochrones = isochrones.to_crs("EPSG:3857")
population = population.to_crs("EPSG:3857")
polling = polling.to_crs("EPSG:3857")

# filter isochrones to only 15-minute walking distance
# this provides a standardized comparison across all polling places
iso_15 = isochrones[isochrones['time_minutes'] == 15]

# create figure with appropriate size for detailed viewing
fig, ax = plt.subplots(1, 1, figsize=(16, 14))

# plot the 15-minute isochrones as semi-transparent polygons
iso_15.plot(ax=ax, alpha=0.3, edgecolor='#1f77b4', facecolor='#a6cee3', linewidth=0.8)

# add openstreetmap basemap for geographic context
ctx.add_basemap(ax, source=ctx.providers.OpenStreetMap.Mapnik, zoom=11)

# plot population centers with size proportional to population count
# log scale improves visibility across wide range of population values
sizes = np.log1p(population['POPULATION']) * 15
population.plot(ax=ax, color='#e31a1c', markersize=sizes, 
                alpha=0.7, edgecolor='white', linewidth=0.5)

# plot polling places as prominent star markers
polling.plot(ax=ax, color='#2c3e50', markersize=120, marker='*', 
             edgecolor='white', linewidth=1.5, label='Polling Places')

# add labels for the top 5 polling places with largest walkable coverage area
iso_summary = iso_15.groupby('polling_place')['area_sq_miles'].mean().sort_values(ascending=False).head(5)
for name in iso_summary.index:
    poll_point = polling[polling['Precinct'] == name]
    if len(poll_point) > 0:
        x, y = poll_point.geometry.iloc[0].x, poll_point.geometry.iloc[0].y
        ax.annotate(name, xy=(x, y), xytext=(5, 5), textcoords='offset points',
                   fontsize=8, fontweight='bold', color='#2c3e50',
                   bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))

# set map title and remove axis for cleaner presentation
ax.set_title("15-Minute Walking Isochrones and Population Centers - Montgomery County, AL", 
             fontsize=18, fontweight='bold', pad=20)
ax.set_axis_off()

# create custom legend to explain map elements

legend_elements = [
    Line2D([0], [0], marker='o', color='w', markerfacecolor='#e31a1c', 
           markersize=10, label='Population Centers (size proportional to population)'),
    Line2D([0], [0], marker='*', color='w', markerfacecolor='#2c3e50', 
           markersize=12, label='Polling Places'),
    Line2D([0], [0], color='#1f77b4', linewidth=2, label='15-Minute Walkable Area')
]
ax.legend(handles=legend_elements, loc='lower left', framealpha=0.9)

# save the map with high resolution for publication quality
plt.tight_layout()
output_path = PROJECT_ROOT / "outputs" / "figures" / "isochrones_enhanced.png"
plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
print(f"Enhanced map saved to: {output_path}")