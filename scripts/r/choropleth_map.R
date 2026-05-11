library(tidyverse)
library(tigris)
library(sf)

# fetch tract boundaries

montgomery_tracts <- tracts(state = "AL", county = "Montgomery", year = 2020)

# load accessibility data (has TRACTCE)

accessibility <- read_csv("data/outputs/accessibility_scores_enhanced_complete.csv")

# load merged analysis data

analysis_df <- read_csv("outputs/tables/merged_analysis_tract_level.csv")

# build tract GEOID from TRACTCE and add to analysis
# the accessibility file and analysis_df are in the same row order (both 203/201 rows)

analysis_df$tract_geoid <- paste0(
  "01101",
  str_pad(as.character(accessibility$TRACTCE[1:nrow(analysis_df)]), 
          width = 6, side = "left", pad = "0")
)

# join with tract geometries

map_data <- montgomery_tracts %>%
  left_join(analysis_df, by = c("GEOID" = "tract_geoid"))

# verify the join worked

print(paste("Rows in map_data:", nrow(map_data)))
print(paste("Rows with walking_dist:", sum(!is.na(map_data$walking_dist))))

# create walking distance choropleth

ggplot(map_data) +
  geom_sf(aes(fill = walking_dist)) +
  scale_fill_viridis_c(option = "plasma", name = "Walking Distance (miles)") +
  labs(title = "Walking Distance to Nearest Polling Place",
       subtitle = "Montgomery County, AL — Tract Level") +
  theme_minimal() +
  theme(axis.text = element_blank(), axis.ticks = element_blank())

ggsave("outputs/maps/walking_distance_choropleth_r.png", width = 12, height = 10, dpi = 300)