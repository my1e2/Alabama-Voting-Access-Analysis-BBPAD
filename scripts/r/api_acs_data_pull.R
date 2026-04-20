# acs data pull for montgomery county, alabama
# uses tidycensus package to retrieve demographic variables from census api

library(tidycensus)
library(tidyverse)
library(sf)
library(tigris)

# api key stored in gitignore file natively on machine
# defining montgomery county fips codes for api queries
al_fips <- "01"
montgomery_fips <- "101"
montgomery_county_fips <- paste0(al_fips, montgomery_fips)

# defining acs variables to retrieve using 2020-2024 5-year estimates
acs_year <- 2024
acs_survey <- "acs5"

# variables dictionary mapping descriptive names to census table codes
acs_variables <- c(
  # population totals
  total_pop = "B01001_001",
  # race and ethnicity (non-hispanic categories)
  white_alone = "B02001_002",
  black_alone = "B02001_003",
  asian_alone = "B02001_005",
  hispanic_total = "B03002_012",
  # economic indicators
  median_income = "B19013_001",
  poverty_total = "B17001_001",
  poverty_below = "B17001_002",
  # transportation access
  total_households = "B25044_001",
  no_vehicle = "B25044_003",
  # educational attainment used as socioeconomic proxy
  pop_25_plus = "B15003_001",
  bachelors_plus = "B15003_022"
)

# function to retrieve acs data at tract level for montgomery county
get_montgomery_tract_data <- function() {
  # query census api for tract-level data with spatial geometries
  tract_data <- get_acs(
    geography = "tract",
    variables = acs_variables,
    state = al_fips,
    county = montgomery_fips,
    year = acs_year,
    survey = acs_survey,
    geometry = TRUE,
    output = "wide"
  )
  # calculate derived percentage columns from raw counts
  tract_data <- tract_data %>%
    mutate(
      # race and ethnicity percentages
      pct_black = (black_aloneE / total_popE) * 100,
      pct_white = (white_aloneE / total_popE) * 100,
      pct_hispanic = (hispanic_totalE / total_popE) * 100,
      # poverty rate calculation
      pct_poverty = (poverty_belowE / poverty_totalE) * 100,
      # no vehicle access rate
      pct_no_vehicle = (no_vehicleE / total_householdsE) * 100,
      # bachelor's degree attainment rate among adults
      pct_bachelors = (bachelors_plusE / pop_25_plusE) * 100,
      # flag tracts with high margin of error for quality control
      high_moe_flag = ifelse(total_popM / total_popE > 0.15, 1, 0)
    )
  return(tract_data)
}

# function to retrieve block group level data for finer spatial resolution
get_montgomery_bg_data <- function() {
  # query census api for block group data with spatial geometries
  bg_data <- get_acs(
    geography = "block group",
    variables = acs_variables,
    state = al_fips,
    county = montgomery_fips,
    year = acs_year,
    survey = acs_survey,
    geometry = TRUE,
    output = "wide"
  )
  # calculate derived percentages at block group level
  bg_data <- bg_data %>%
    mutate(
      pct_black = (black_aloneE / total_popE) * 100,
      pct_poverty = (poverty_belowE / poverty_totalE) * 100,
      pct_no_vehicle = (no_vehicleE / total_householdsE) * 100,
      high_moe_flag = ifelse(total_popM / total_popE > 0.15, 1, 0)
    )
  return(bg_data)
}

# function to create vulnerability index identifying communities at risk
# uses z-score normalization for consistent comparison across metrics
calculate_vulnerability_index <- function(data) {
  data <- data %>%
    mutate(
      # standardize each component using z-score transformation
      z_pct_black = scale(pct_black)[,1],
      z_pct_poverty = scale(pct_poverty)[,1],
      z_pct_no_vehicle = scale(pct_no_vehicle)[,1],
      # composite vulnerability index with equal weighting
      vulnerability_index = (z_pct_black + z_pct_poverty + z_pct_no_vehicle) / 3,
      # categorize vulnerability levels for easier interpretation
      vulnerability_category = case_when(
        vulnerability_index > 1.0 ~ "High",
        vulnerability_index > 0.0 ~ "Moderate",
        vulnerability_index > -1.0 ~ "Low",
        TRUE ~ "Very Low"
      )
    )
  return(data)
}

# main execution function coordinating the full data retrieval workflow
main <- function() {
  cat("Retrieving Montgomery County ACS data\n")
  # process tract-level data
  cat("Tract-level data\n")
  tract_data <- get_montgomery_tract_data()
  tract_data <- calculate_vulnerability_index(tract_data)
  # process block group-level data
  cat("Block group-level data\n")
  bg_data <- get_montgomery_bg_data()
  bg_data <- calculate_vulnerability_index(bg_data)
  # save non-spatial versions as csv files for analysis
  tract_df <- tract_data %>% st_drop_geometry()
  bg_df <- bg_data %>% st_drop_geometry()
  write_csv(tract_df, "data/census/processed/montgomery_demographics_tract.csv")
  write_csv(bg_df, "data/census/processed/montgomery_demographics_bg.csv")
  # save spatial versions as geojson for mapping and gis integration
  st_write(tract_data, "data/census/processed/montgomery_demographics_tract.geojson", 
           delete_dsn = TRUE)
  st_write(bg_data, "data/census/processed/montgomery_demographics_bg.geojson",
           delete_dsn = TRUE)
  # display summary counts
  cat("\nACS Data:\n")
  cat("Tracts:", nrow(tract_data), "\n")
  cat("Block Groups:", nrow(bg_data), "\n")
  # display demographic summary statistics for the county
  cat("\nMontgomery County Demographic Summary:\n")
  cat(sprintf("Total Population: %s\n", 
              format(sum(tract_data$total_popE, na.rm=TRUE), big.mark=",")))
  cat(sprintf("Black/African American: %.1f%%\n", 
              mean(tract_data$pct_black, na.rm=TRUE)))
  cat(sprintf("Below Poverty: %.1f%%\n", 
              mean(tract_data$pct_poverty, na.rm=TRUE)))
  cat(sprintf("No Vehicle Access: %.1f%%\n", 
              mean(tract_data$pct_no_vehicle, na.rm=TRUE)))
}

# execute main function
main()