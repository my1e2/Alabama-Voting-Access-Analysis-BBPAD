library(sf)
library(ggplot2)
library(ggspatial)
library(patchwork)

# load data

isochrones <- st_read("data/outputs/polling_isochrones_all.geojson")
polling <- st_read("data/polling/processed/polling_places_montgomery_2020.geojson")

# transform to Web Mercator

isochrones <- st_transform(isochrones, 3857)
polling <- st_transform(polling, 3857)

# darker, more visible colors with better contrast

time_colors <- c(
  "5"  = "#08519c",   # dark blue
  "10" = "#2171b5",   # medium-dark blue
  "15" = "#4292c6",   # medium blue
  "20" = "#74a9cf",   # light blue
  "30" = "#bdc9e1"    # very light blue-grey
)

# border colors (darker than fill for visibility)

border_colors <- c(
  "5"  = "#063a73",
  "10" = "#08519c",
  "15" = "#2171b5",
  "20" = "#4292c6",
  "30" = "#6baed6"
)

create_isochrone_map <- function(minutes) {
  iso_subset <- isochrones[isochrones$time_minutes == minutes, ]
  
  ggplot() +
    annotation_map_tile(type = "osm", zoom = 11) +
    geom_sf(data = iso_subset, 
            aes(fill = as.character(time_minutes)),
            alpha = 0.35,                              # slightly more opaque
            color = border_colors[as.character(minutes)],
            linewidth = 0.4) +
    geom_sf(data = polling, 
            color = "#1a1a1a",                         # nearly black for contrast
            size = 1.2,                                # much smaller points
            shape = 21,
            fill = "#e34a33",                          # red-orange fill (stands out)
            stroke = 0.5) +
    scale_fill_manual(values = time_colors, guide = "none") +
    labs(title = paste(minutes, "-Minute Walk"), 
         subtitle = paste(nrow(iso_subset), "polling places")) +
    coord_sf(expand = FALSE) +                         # prevents extra padding
    theme_void() +
    theme(
      plot.title = element_text(size = 11, face = "bold", hjust = 0.5),
      plot.subtitle = element_text(size = 8, hjust = 0.5, color = "grey40"),
      panel.border = element_rect(color = "grey70", fill = NA, linewidth = 0.5)
    )
}

map_5  <- create_isochrone_map(5)
map_10 <- create_isochrone_map(10)
map_15 <- create_isochrone_map(15)
map_20 <- create_isochrone_map(20)
map_30 <- create_isochrone_map(30)

combined_map <- (map_5 + map_10 + map_15) / (map_20 + map_30 + plot_spacer()) +
  plot_annotation(
    title = "Walking Isochrones Around Polling Places",
    subtitle = "Montgomery County, AL",
    theme = theme(
      plot.title = element_text(size = 16, face = "bold", hjust = 0.5),
      plot.subtitle = element_text(size = 12, hjust = 0.5, color = "grey40")
    )
  )

ggsave("outputs/maps/isochrone_panel_r.png", 
       combined_map, 
       width = 16, 
       height = 12, 
       dpi = 300)