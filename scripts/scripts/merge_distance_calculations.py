"""
Merge Euclidean, Network, OSRM Walking, and Google Walking Distance Results
Combines accessibility scores from all calculations into one comprehensive dataset
"""

import pandas as pd
from pathlib import Path

# project root directory - three levels up from this script
PROJECT_ROOT = Path(__file__).parent.parent.parent


def merge_distance_results():
    """
    merge all distance calculation results into a single master file.
    
    loads results from euclidean, osrm driving, osrm walking, and google
    walking calculations. merges them on geoid and creates cross-comparison
    metrics between different routing methods. saves the combined dataset
    and prints summary statistics.
    
    returns:
        dataframe: merged dataset with all distance metrics, or none if base file missing
    """
    print("Merging all distance calculation results")
    print("")
    
    # load euclidean and manhattan results as the base dataset
    # this file contains the original straight-line distance calculations
    euclidean_path = PROJECT_ROOT / "data" / "outputs" / "accessibility_scores_by_tract.csv"
    if not euclidean_path.exists():
        print(f"Euclidean results not found at {euclidean_path}")
        return None
    
    df_merged = pd.read_csv(euclidean_path)
    print(f"Loaded Euclidean results: {len(df_merged)} rows")
    print(f"Base columns: {list(df_merged.columns)[:8]}...")
    print("")
    
    # load and merge osrm driving distance results
    # these are network-based driving distances from the osrm routing engine
    network_path = PROJECT_ROOT / "data" / "outputs" / "accessibility_scores_network.csv"
    if network_path.exists():
        df_network = pd.read_csv(network_path)
        print(f"Loaded OSRM Driving results: {len(df_network)} rows")
        
        # select only the columns needed for merge
        network_cols = ['GEOID', 'min_network_dist_miles', 'nearest_poll_network_idx']
        available = [c for c in network_cols if c in df_network.columns]
        
        df_merged = df_merged.merge(df_network[available], on='GEOID', how='left')
        
        # add driving comparison metrics for analysis
        if 'min_dist_to_poll_miles' in df_merged.columns and 'min_network_dist_miles' in df_merged.columns:
            # ratio of driving distance to straight-line distance
            df_merged['driving_to_euclidean_ratio'] = (
                df_merged['min_network_dist_miles'] / df_merged['min_dist_to_poll_miles']
            )
            # absolute difference between driving and straight-line distance
            df_merged['driving_euclidean_diff_miles'] = (
                df_merged['min_network_dist_miles'] - df_merged['min_dist_to_poll_miles']
            )
        print(f"Added OSRM Driving metrics")
    else:
        print(f"OSRM Driving results not found - skipping")
    print("")
    
    # load and merge osrm walking distance results
    # these are pedestrian network distances from the osrm routing engine
    walking_osrm_path = PROJECT_ROOT / "data" / "outputs" / "accessibility_scores_walking.csv"
    if walking_osrm_path.exists():
        df_walking_osrm = pd.read_csv(walking_osrm_path)
        print(f"Loaded OSRM Walking results: {len(df_walking_osrm)} rows")
        
        # select only the columns needed for merge
        walking_osrm_cols = ['GEOID', 'min_walking_dist_miles', 'nearest_poll_walking_idx']
        available = [c for c in walking_osrm_cols if c in df_walking_osrm.columns]
        
        df_merged = df_merged.merge(df_walking_osrm[available], on='GEOID', how='left')
        
        # add osrm walking comparison metrics
        if 'min_dist_to_poll_miles' in df_merged.columns and 'min_walking_dist_miles' in df_merged.columns:
            # ratio of walking network distance to straight-line distance
            df_merged['osrm_walking_to_euclidean_ratio'] = (
                df_merged['min_walking_dist_miles'] / df_merged['min_dist_to_poll_miles']
            )
        print(f"Added OSRM Walking metrics")
    else:
        print(f"OSRM Walking results not found - skipping")
    print("")
    
    # load and merge google walking distance results
    # these are pedestrian distances from the google routes api
    google_path = PROJECT_ROOT / "data" / "outputs" / "accessibility_scores_google_walking.csv"
    if google_path.exists():
        df_google = pd.read_csv(google_path)
        print(f"Loaded Google Walking results: {len(df_google)} rows")
        
        # select only the columns needed for merge
        google_cols = ['GEOID', 'min_google_walking_dist_miles', 'nearest_poll_google_walking_idx']
        available = [c for c in google_cols if c in df_google.columns]
        
        df_merged = df_merged.merge(df_google[available], on='GEOID', how='left')
        
        # add google walking comparison metrics
        if 'min_dist_to_poll_miles' in df_merged.columns and 'min_google_walking_dist_miles' in df_merged.columns:
            # ratio of google walking distance to straight-line distance
            df_merged['google_walking_to_euclidean_ratio'] = (
                df_merged['min_google_walking_dist_miles'] / df_merged['min_dist_to_poll_miles']
            )
        print(f"Added Google Walking metrics")
        
        # count how many centers have valid google distances
        valid_google = df_merged['min_google_walking_dist_miles'].notna().sum()
        print(f"Valid Google distances: {valid_google}/{len(df_merged)} centers")
    else:
        print(f"Google Walking results not found - skipping")
    print("")
    
    # create cross-comparison metrics between different routing methods
    # these ratios help understand the relationship between different distance calculations
    print(f"Creating cross-comparison metrics")
    
    # osrm walking compared to driving (walkability index proxy)
    if 'min_network_dist_miles' in df_merged.columns and 'min_walking_dist_miles' in df_merged.columns:
        df_merged['osrm_walking_to_driving_ratio'] = (
            df_merged['min_walking_dist_miles'] / df_merged['min_network_dist_miles']
        )
        print(f"  - osrm_walking_to_driving_ratio")
    
    # google walking compared to osrm walking (api comparison)
    if 'min_google_walking_dist_miles' in df_merged.columns and 'min_walking_dist_miles' in df_merged.columns:
        df_merged['google_to_osrm_walking_ratio'] = (
            df_merged['min_google_walking_dist_miles'] / df_merged['min_walking_dist_miles']
        )
        print(f"  - google_to_osrm_walking_ratio")
    
    # google walking compared to driving (pedestrian vs vehicle)
    if 'min_network_dist_miles' in df_merged.columns and 'min_google_walking_dist_miles' in df_merged.columns:
        df_merged['google_walking_to_driving_ratio'] = (
            df_merged['min_google_walking_dist_miles'] / df_merged['min_network_dist_miles']
        )
        print(f"  - google_walking_to_driving_ratio")
    
    print("")
    
    # save the complete merged dataset
    output_path = PROJECT_ROOT / "data" / "outputs" / "accessibility_scores_complete.csv"
    df_merged.to_csv(output_path, index=False)
    print(f"Saved merged results to: {output_path}")
    print(f"Final dimensions: {len(df_merged)} rows x {len(df_merged.columns)} columns")
    print("")
    
    # print summary statistics for all available distance metrics
    print("Summary statistics - all distance metrics")
    print("")
    
    # euclidean straight-line distance
    if 'min_dist_to_poll_miles' in df_merged.columns:
        print(f"Euclidean (straight-line):")
        print(f"  Average: {df_merged['min_dist_to_poll_miles'].mean():.2f} miles")
        print(f"  Maximum: {df_merged['min_dist_to_poll_miles'].max():.2f} miles")
        print("")
    
    # manhattan grid-based distance
    if 'min_manhattan_dist_miles' in df_merged.columns:
        print(f"Manhattan (grid-based):")
        print(f"  Average: {df_merged['min_manhattan_dist_miles'].mean():.2f} miles")
        print("")
    
    # osrm driving network distance
    if 'min_network_dist_miles' in df_merged.columns:
        print(f"OSRM Driving:")
        print(f"  Average: {df_merged['min_network_dist_miles'].mean():.2f} miles")
        print(f"  Maximum: {df_merged['min_network_dist_miles'].max():.2f} miles")
        if 'driving_to_euclidean_ratio' in df_merged.columns:
            print(f"  vs Euclidean: {df_merged['driving_to_euclidean_ratio'].mean():.2f}x")
        print("")
    
    # osrm walking network distance
    if 'min_walking_dist_miles' in df_merged.columns:
        print(f"OSRM Walking:")
        print(f"  Average: {df_merged['min_walking_dist_miles'].mean():.2f} miles")
        print(f"  Maximum: {df_merged['min_walking_dist_miles'].max():.2f} miles")
        print("")
    
    # google walking api distance
    if 'min_google_walking_dist_miles' in df_merged.columns:
        print(f"Google Walking:")
        valid = df_merged['min_google_walking_dist_miles'].notna()
        print(f"  Valid centers: {valid.sum()}/{len(df_merged)}")
        print(f"  Average: {df_merged.loc[valid, 'min_google_walking_dist_miles'].mean():.2f} miles")
        print(f"  Maximum: {df_merged.loc[valid, 'min_google_walking_dist_miles'].max():.2f} miles")
        print("")
    
    # cross-comparison between google and osrm walking
    if 'google_to_osrm_walking_ratio' in df_merged.columns:
        valid = df_merged['google_to_osrm_walking_ratio'].notna()
        if valid.sum() > 0:
            print(f"Google vs OSRM Walking Ratio:")
            print(f"  Average: {df_merged.loc[valid, 'google_to_osrm_walking_ratio'].mean():.2f}x")
    
    return df_merged


if __name__ == "__main__":
    merged = merge_distance_results()
    
    if merged is not None:
        print("")
        print(f"Master file: data/outputs/accessibility_scores_complete.csv")