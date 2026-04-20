# statistical analysis of voter turnout and accessibility
# montgomery county, alabama
# uses tract-level demographics with complete poverty data

library(tidyverse)
library(broom)

# load all prepared datasets from previous processing steps
load_analysis_data <- function() {
  cat("\nLoading datasets\n")
  
  precinct_results <- read_csv("data/elections/processed/montgomery_precinct_results_2024.csv",
                               show_col_types = FALSE)
  cat(sprintf("  Loaded %d precincts (2024)\n", nrow(precinct_results)))
  
  precinct_results_2020 <- read_csv("data/elections/processed/montgomery_precinct_results_2020.csv",
                                    show_col_types = FALSE)
  cat(sprintf("  Loaded %d precincts (2020)\n", nrow(precinct_results_2020)))
  
  # use tract-level demographics since poverty data is available at tract level
  tract_demo <- read_csv("data/census/processed/montgomery_demographics_tract.csv",
                         show_col_types = FALSE)
  cat(sprintf("  Loaded %d tracts with demographics (poverty data available)\n", nrow(tract_demo)))
  
  accessibility <- read_csv("data/outputs/accessibility_scores_enhanced_complete.csv",
                            show_col_types = FALSE)
  cat(sprintf("  Loaded %d accessibility records\n", nrow(accessibility)))
  
  isochrone <- read_csv("data/outputs/polling_isochrone_summary.csv",
                        show_col_types = FALSE)
  cat(sprintf("  Loaded %d isochrone records\n", nrow(isochrone)))
  
  return(list(
    precinct_2024 = precinct_results,
    precinct_2020 = precinct_results_2020,
    tract_demo = tract_demo,
    accessibility = accessibility,
    isochrone = isochrone
  ))
}

# generate descriptive statistics for the county
generate_descriptive_stats <- function(data) {
  cat("\n")
  cat("Descriptive statistics\n\n")
  cat("Montgomery County Overview (2024)\n")
  
  total_votes_2024 <- sum(data$precinct_2024$total_pres_votes_2024, na.rm = TRUE)
  cat(sprintf("  Total Presidential Votes: %s\n", 
              format(total_votes_2024, big.mark = ",")))
  
  dem_votes_2024 <- sum(data$precinct_2024$dem_pres, na.rm = TRUE)
  dem_share_2024 <- (dem_votes_2024 / total_votes_2024) * 100
  cat(sprintf("  Democratic Vote Share: %.1f%%\n", dem_share_2024))
  
  rep_votes_2024 <- sum(data$precinct_2024$rep_pres, na.rm = TRUE)
  rep_share_2024 <- (rep_votes_2024 / total_votes_2024) * 100
  cat(sprintf("  Republican Vote Share: %.1f%%\n", rep_share_2024))
  
  cat("\nTurnout Change 2020-2024\n")
  
  n_min <- min(nrow(data$precinct_2020), nrow(data$precinct_2024))
  
  turnout_change_df <- data$precinct_2020 %>%
    slice(1:n_min) %>%
    select(Precinct, total_pres_votes_2020, dem_share_2020) %>%
    bind_cols(
      data$precinct_2024 %>%
        slice(1:n_min) %>%
        select(Precinct_2024 = Precinct, total_pres_votes_2024, dem_share_2024)
    ) %>%
    mutate(
      vote_change = total_pres_votes_2024 - total_pres_votes_2020,
      pct_change = (vote_change / total_pres_votes_2020) * 100
    )
  
  cat(sprintf("  Mean vote change per precinct: %.0f\n", 
              mean(turnout_change_df$vote_change, na.rm = TRUE)))
  cat(sprintf("  Median vote change: %.0f\n", 
              median(turnout_change_df$vote_change, na.rm = TRUE)))
  cat(sprintf("  Precincts with increased turnout: %.1f%%\n", 
              mean(turnout_change_df$vote_change > 0, na.rm = TRUE) * 100))
  cat(sprintf("  Average percentage change: %.1f%%\n", 
              mean(turnout_change_df$pct_change, na.rm = TRUE)))
  
  cat("\nAccessibility Metrics\n")
  
  access_summary <- data$accessibility %>%
    summarise(
      mean_dist = mean(min_google_walking_dist_miles, na.rm = TRUE),
      median_dist = median(min_google_walking_dist_miles, na.rm = TRUE),
      max_dist = max(min_google_walking_dist_miles, na.rm = TRUE),
      mean_osrm_walking = mean(min_walking_dist_miles, na.rm = TRUE),
      mean_driving = mean(min_network_dist_miles, na.rm = TRUE)
    )
  
  cat(sprintf("  Average Google walking distance: %.2f miles\n", 
              access_summary$mean_dist))
  cat(sprintf("  Median Google walking distance: %.2f miles\n", 
              access_summary$median_dist))
  cat(sprintf("  Maximum walking distance: %.2f miles\n", 
              access_summary$max_dist))
  cat(sprintf("  Average OSRM walking distance: %.2f miles\n", 
              access_summary$mean_osrm_walking))
  cat(sprintf("  Average driving distance: %.2f miles\n", 
              access_summary$mean_driving))
  
  cat("\nWalkability Categories\n")
  
  walkability_counts <- data$accessibility %>%
    count(walkability_category) %>%
    mutate(pct = n / sum(n) * 100)
  
  for (i in 1:nrow(walkability_counts)) {
    cat(sprintf("  %s: %d areas (%.1f%%)\n", 
                walkability_counts$walkability_category[i],
                walkability_counts$n[i],
                walkability_counts$pct[i]))
  }
  
  cat("\n15-Minute Walkable Area\n")
  
  iso_15 <- data$isochrone %>% filter(time_minutes == 15)
  if (nrow(iso_15) > 0) {
    cat(sprintf("  Average walkable area: %.2f sq miles\n", 
                mean(iso_15$area_sq_miles, na.rm = TRUE)))
    cat(sprintf("  Total walkable area (all polling places): %.2f sq miles\n", 
                sum(iso_15$area_sq_miles, na.rm = TRUE)))
    cat(sprintf("  Average population within 15-min walk: %.0f\n", 
                mean(iso_15$population_served, na.rm = TRUE)))
  }
  
  return(list(
    total_votes_2024 = total_votes_2024,
    dem_share_2024 = dem_share_2024,
    access_summary = access_summary,
    walkability_counts = walkability_counts,
    turnout_change = turnout_change_df
  ))
}

# merge accessibility scores with tract-level demographics
merge_accessibility_tract_demographics <- function(accessibility, tract_demo) {
  cat("\n")
  cat("Merging accessibility with tract demographics\n\n")
  
  # build proper tract geoid from accessibility tractce field
  acc_clean <- accessibility %>%
    mutate(
      tract_6digit = str_pad(as.character(TRACTCE), width = 6, side = "left", pad = "0"),
      tract_geoid = paste0("01101", tract_6digit)
    ) %>%
    select(
      tract_geoid,
      walking_dist = min_google_walking_dist_miles,
      walkability_score = walkability_score,
      walkability_category = walkability_category,
      euclidean_dist = min_dist_to_poll_miles,
      driving_dist = min_network_dist_miles,
      walking_osrm = min_walking_dist_miles
    )
  
  cat("Built accessibility tract geoids\n")
  cat("  Sample:", paste(head(unique(acc_clean$tract_geoid), 3), collapse = ", "), "\n\n")
  
  # prepare tract demographics for merge
  tract_demo_clean <- tract_demo %>%
    mutate(
      tract_geoid = as.character(GEOID)
    ) %>%
    select(
      tract_geoid,
      total_pop = total_popE,
      pct_black,
      pct_poverty,
      pct_no_vehicle,
      pct_bachelors,
      median_income = median_incomeE,
      vulnerability_index,
      vulnerability_category
    )
  
  cat("Tract demographics prepared\n")
  cat("  Sample tract:", head(tract_demo_clean$tract_geoid, 1), "\n")
  cat("  pct_poverty NAs:", sum(is.na(tract_demo_clean$pct_poverty)), "/", nrow(tract_demo_clean), "\n\n")
  
  # perform the merge
  merged <- acc_clean %>%
    left_join(tract_demo_clean, by = "tract_geoid")
  
  match_count <- sum(!is.na(merged$pct_black))
  cat(sprintf("Final merge: %d / %d rows matched (%.1f%%)\n", 
              match_count, nrow(merged), match_count/nrow(merged)*100))
  
  return(merged)
}

# run regression models to analyze relationships
run_turnout_regression <- function(data) {
  cat("\n")
  cat("Regression analysis (tract-level demographics)\n")
  
  # use tract-level merge for complete poverty data
  analysis_df <- merge_accessibility_tract_demographics(data$accessibility, data$tract_demo)
  
  # prepare complete cases for modeling
  analysis_df_complete <- analysis_df %>%
    select(walking_dist, walkability_score, walkability_category,
           pct_black, pct_poverty, pct_no_vehicle, pct_bachelors, 
           median_income, vulnerability_index, vulnerability_category) %>%
    na.omit()
  
  cat("\nComplete cases for regression:", nrow(analysis_df_complete), "\n\n")
  
  if (nrow(analysis_df_complete) < 5) {
    cat("Insufficient complete cases\n")
    return(list(analysis_df = analysis_df, merge_success = FALSE))
  }
  
  # model 1: walkability score predicted by demographics
  cat("Model 1: Walkability Score by Percent Black and Poverty\n")
  
  model1 <- lm(walkability_score ~ pct_black + pct_poverty, data = analysis_df_complete)
  
  coefs1 <- summary(model1)$coefficients
  for (i in 2:nrow(coefs1)) {
    pval <- coefs1[i, 4]
    sig <- ifelse(pval < 0.001, "***", ifelse(pval < 0.01, "**", ifelse(pval < 0.05, "*", "")))
    cat(sprintf("  %s: %.4f (p=%.4f) %s\n", 
                rownames(coefs1)[i], coefs1[i, 1], pval, sig))
  }
  cat(sprintf("  R-squared: %.4f\n\n", summary(model1)$r.squared))
  
  # model 2: walking distance predicted by demographics and vehicle access
  cat("Model 2: Walking Distance by Percent Black, Poverty, and No Vehicle\n")
  
  model2 <- lm(walking_dist ~ pct_black + pct_poverty + pct_no_vehicle, data = analysis_df_complete)
  
  coefs2 <- summary(model2)$coefficients
  for (i in 2:nrow(coefs2)) {
    pval <- coefs2[i, 4]
    sig <- ifelse(pval < 0.001, "***", ifelse(pval < 0.01, "**", ifelse(pval < 0.05, "*", "")))
    cat(sprintf("  %s: %.4f (p=%.4f) %s\n", 
                rownames(coefs2)[i], coefs2[i, 1], pval, sig))
  }
  cat(sprintf("  R-squared: %.4f\n\n", summary(model2)$r.squared))
  
  # model 3: walking distance predicted by vulnerability index
  cat("Model 3: Walking Distance by Vulnerability Index\n")
  
  model3 <- lm(walking_dist ~ vulnerability_index, data = analysis_df_complete)
  
  coefs3 <- summary(model3)$coefficients
  if (nrow(coefs3) > 1) {
    pval <- coefs3[2, 4]
    sig <- ifelse(pval < 0.001, "***", ifelse(pval < 0.01, "**", ifelse(pval < 0.05, "*", "")))
    cat(sprintf("  vulnerability_index: %.4f (p=%.4f) %s\n", 
                coefs3[2, 1], pval, sig))
    cat(sprintf("  R-squared: %.4f\n\n", summary(model3)$r.squared))
  }
  
  # group comparison by vulnerability category
  cat("Walking Distance by Vulnerability Category\n")
  
  vuln_summary <- analysis_df_complete %>%
    group_by(vulnerability_category) %>%
    summarise(
      n = n(),
      avg_distance = mean(walking_dist, na.rm = TRUE),
      sd_distance = sd(walking_dist, na.rm = TRUE),
      avg_pct_black = mean(pct_black, na.rm = TRUE),
      avg_pct_poverty = mean(pct_poverty, na.rm = TRUE),
      .groups = "drop"
    ) %>%
    arrange(desc(avg_distance))
  
  for (i in 1:nrow(vuln_summary)) {
    cat(sprintf("  %s (n=%d): %.2f miles (SD=%.2f)\n", 
                vuln_summary$vulnerability_category[i],
                vuln_summary$n[i],
                vuln_summary$avg_distance[i],
                vuln_summary$sd_distance[i]))
    cat(sprintf("    Avg %% Black: %.1f%%, Avg %% Poverty: %.1f%%\n",
                vuln_summary$avg_pct_black[i],
                vuln_summary$avg_pct_poverty[i]))
  }
  
  # high versus low percent black comparison
  cat("\nWalking Distance by Percent Black Category\n")
  
  analysis_df_complete <- analysis_df_complete %>%
    mutate(black_category = ifelse(pct_black > 50, "High % Black (>50%)", "Low % Black (<50%)"))
  
  black_summary <- analysis_df_complete %>%
    group_by(black_category) %>%
    summarise(
      n = n(),
      avg_distance = mean(walking_dist, na.rm = TRUE),
      sd_distance = sd(walking_dist, na.rm = TRUE),
      avg_poverty = mean(pct_poverty, na.rm = TRUE),
      .groups = "drop"
    )
  
  for (i in 1:nrow(black_summary)) {
    cat(sprintf("  %s (n=%d): %.2f miles (SD=%.2f), poverty=%.1f%%\n", 
                black_summary$black_category[i],
                black_summary$n[i],
                black_summary$avg_distance[i],
                black_summary$sd_distance[i],
                black_summary$avg_poverty[i]))
  }
  
  # t-test for statistical significance
  high_group <- analysis_df_complete %>% 
    filter(black_category == "High % Black (>50%)") %>% 
    pull(walking_dist)
  low_group <- analysis_df_complete %>% 
    filter(black_category == "Low % Black (<50%)") %>% 
    pull(walking_dist)
  
  if (length(high_group) > 1 && length(low_group) > 1) {
    t_test <- t.test(high_group, low_group)
    diff_mean <- mean(high_group) - mean(low_group)
    cat(sprintf("\n  Difference: %.2f miles\n", diff_mean))
    cat(sprintf("  T-test p-value: %.4f %s\n", 
                t_test$p.value,
                ifelse(t_test$p.value < 0.05, "(statistically significant)", "(not significant)")))
  }
  
  return(list(
    model1 = model1,
    model2 = model2,
    model3 = model3,
    vuln_summary = vuln_summary,
    black_summary = black_summary,
    analysis_df = analysis_df_complete,
    merge_success = TRUE
  ))
}

# correlation analysis between distance metrics and demographics
run_correlation_analysis <- function(data) {
  cat("\n")
  cat("Correlation analysis\n\n")
  
  merged <- merge_accessibility_tract_demographics(data$accessibility, data$tract_demo)
  
  corr_df <- merged %>%
    select(walking_dist, walkability_score, euclidean_dist, driving_dist, walking_osrm,
           pct_black, pct_poverty, pct_no_vehicle, pct_bachelors, median_income, 
           vulnerability_index) %>%
    na.omit()
  
  cat("Complete cases:", nrow(corr_df), "\n\n")
  
  cat("Correlations with Walking Distance:\n")
  
  if ("walking_dist" %in% names(corr_df)) {
    for (col in names(corr_df)) {
      if (col != "walking_dist") {
        cor_val <- cor(corr_df$walking_dist, corr_df[[col]], use = "complete.obs")
        if (!is.na(cor_val)) {
          # calculate p-value for correlation
          n <- nrow(corr_df)
          t_stat <- cor_val * sqrt((n - 2) / (1 - cor_val^2))
          p_val <- 2 * pt(abs(t_stat), df = n - 2, lower.tail = FALSE)
          sig <- ifelse(p_val < 0.001, "***", ifelse(p_val < 0.01, "**", ifelse(p_val < 0.05, "*", "")))
          
          strength <- ifelse(abs(cor_val) > 0.5, "strong",
                             ifelse(abs(cor_val) > 0.3, "moderate", "weak"))
          cat(sprintf("  %s: %.3f (p=%.3f) %s (%s)\n", 
                      col, cor_val, p_val, sig, strength))
        }
      }
    }
  }
  
  return(corr_df)
}

# generate client-friendly executive summary
generate_client_summary <- function(stats, models, corr_df) {
  cat("\n")
  cat("Executive summary for client delivery\n\n")
  
  cat("Key findings\n\n")
  
  cat("Voting accessibility\n")
  cat(sprintf("  Average walking distance to polling place: %.2f miles\n", 
              stats$access_summary$mean_dist))
  cat(sprintf("  %.0f%% of areas have poor or very poor walkability\n",
              round(sum(stats$walkability_counts$pct[
                stats$walkability_counts$walkability_category %in% c("Poor", "Very Poor")
              ]))))
  cat(sprintf("  Maximum walking distance found: %.2f miles\n\n", 
              stats$access_summary$max_dist))
  
  cat("Turnout patterns (2020-2024)\n")
  cat(sprintf("  Average turnout change: %+.1f%%\n",
              mean(stats$turnout_change$pct_change, na.rm = TRUE)))
  cat(sprintf("  Only %.0f%% of precincts saw increased turnout\n\n",
              mean(stats$turnout_change$vote_change > 0, na.rm = TRUE) * 100))
  
  cat("Demographic disparities (tract-level analysis)\n")
  if (!is.null(models) && !is.null(models$black_summary)) {
    for (i in 1:nrow(models$black_summary)) {
      cat(sprintf("  %s: %.2f miles average walking distance (poverty: %.1f%%)\n",
                  models$black_summary$black_category[i],
                  models$black_summary$avg_distance[i],
                  models$black_summary$avg_poverty[i]))
    }
  }
  
  cat("\nVulnerability index findings\n")
  if (!is.null(models) && !is.null(models$vuln_summary)) {
    for (i in 1:min(3, nrow(models$vuln_summary))) {
      cat(sprintf("  %s vulnerability tracts: %.2f miles avg distance\n",
                  models$vuln_summary$vulnerability_category[i],
                  models$vuln_summary$avg_distance[i]))
    }
  }
  
  cat("\nRecommendations\n")
  cat("  Priority intervention areas with walking distance greater than 2 miles\n")
  cat("  Focus on tracts with high vulnerability designation\n")
  cat("  Consider mobile voting units in very poor walkability zones\n")
}

# save all outputs to csv files for documentation
save_outputs <- function(stats, models, corr_df) {
  cat("\n")
  cat("Saving outputs\n\n")
  
  if (!dir.exists("outputs/tables")) {
    dir.create("outputs/tables", recursive = TRUE)
  }
  
  if (!is.null(stats$turnout_change)) {
    write_csv(stats$turnout_change, "outputs/tables/turnout_change_2020_2024.csv")
    cat("  Saved turnout_change_2020_2024.csv\n")
  }
  
  if (!is.null(stats$walkability_counts)) {
    write_csv(stats$walkability_counts, "outputs/tables/walkability_summary.csv")
    cat("  Saved walkability_summary.csv\n")
  }
  
  if (!is.null(models) && !is.null(models$analysis_df)) {
    write_csv(models$analysis_df, "outputs/tables/merged_analysis_tract_level.csv")
    cat("  Saved merged_analysis_tract_level.csv\n")
  }
  
  if (!is.null(corr_df)) {
    write_csv(corr_df, "outputs/tables/correlation_data_tract.csv")
    cat("  Saved correlation_data_tract.csv\n")
  }
  
  if (!is.null(models) && !is.null(models$model2)) {
    sink("outputs/tables/regression_results_tract_level.txt")
    cat("Voter accessibility analysis - Montgomery County, AL\n")
    cat("Tract-level demographic analysis\n\n")
    cat("Model 1: Walkability Score by Percent Black and Poverty\n")
    if (!is.null(models$model1)) print(summary(models$model1))
    cat("\n\nModel 2: Walking Distance by Percent Black, Poverty, and No Vehicle\n")
    if (!is.null(models$model2)) print(summary(models$model2))
    cat("\n\nModel 3: Walking Distance by Vulnerability Index\n")
    if (!is.null(models$model3)) print(summary(models$model3))
    cat("\n\nVulnerability category summary\n")
    print(models$vuln_summary)
    sink()
    cat("  Saved regression_results_tract_level.txt\n")
  }
  
  cat("\n  All outputs saved to outputs/tables/\n")
}

# main execution function
main <- function() {
  cat("Voter accessibility statistical analysis\n")
  cat("Montgomery County, Alabama (tract-level demographics)\n\n")
  
  data <- load_analysis_data()
  
  stats <- generate_descriptive_stats(data)
  models <- run_turnout_regression(data)
  corr_df <- run_correlation_analysis(data)
  generate_client_summary(stats, models, corr_df)
  save_outputs(stats, models, corr_df)
  
}

# run analysis
main()