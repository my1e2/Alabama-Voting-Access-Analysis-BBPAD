"""
Google Walking Distance Matrix Verification
Run this file after google api batch processing to check for gaps
Helps identify if rate-limiting caused any failed batches
"""

import pandas as pd
import numpy as np
from pathlib import Path

# project root directory - three levels up from this script
PROJECT_ROOT = Path(__file__).parent.parent.parent

# load existing distance matrix from previous batch processing
# this file contains all pairwise distances between centers and polling places
matrix_path = PROJECT_ROOT / "data" / "outputs" / "distance_matrix_google_walking.csv"
matrix = pd.read_csv(matrix_path, index_col=0)

# load updated summary file with minimum distances for all centers
# this file should have complete data for all 203 population centers
summary_path = PROJECT_ROOT / "data" / "outputs" / "accessibility_scores_google_walking.csv"
summary = pd.read_csv(summary_path)

# display matrix dimensions and count of missing values
# when no nan values remain, the matrix is fully populated
print(f"Matrix shape: {matrix.shape}")
print(f"NaN values in matrix: {matrix.isna().sum().sum()}")

# additional verification - check that summary has expected number of rows
print(f"")
print(f"Summary rows: {len(summary)}")
print(f"Valid distances in summary: {summary['min_google_walking_dist_miles'].notna().sum()}")