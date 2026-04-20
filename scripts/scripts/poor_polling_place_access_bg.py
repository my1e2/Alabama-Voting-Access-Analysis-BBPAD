"""
Quick Analysis: Identify Areas with Poor Polling Place Access
Filters accessibility scores to show only block groups categorized as having poor access
"""

import pandas as pd
from pathlib import Path

# project root directory - three levels up from this script
PROJECT_ROOT = Path(__file__).parent.parent.parent

# load the accessibility scores dataset
# contains distance metrics and accessibility categories for each block group
results_path = PROJECT_ROOT / "data" / "outputs" / "accessibility_scores_by_tract.csv"
df = pd.read_csv(results_path)

# filter to only block groups categorized as having poor access
# accessibility categories are: excellent, good, fair, poor
poor_access = df[df['accessibility_category'] == 'Poor']

print("Block groups with poor polling place access:")
print("")
print(poor_access[['GEOID', 'min_dist_to_poll_miles', 'POPULATION']])

# additional summary statistics for context
print("")
print(f"Total block groups analyzed: {len(df)}")
print(f"Block groups with poor access: {len(poor_access)}")
print(f"Percentage with poor access: {(len(poor_access)/len(df))*100:.1f} percent")