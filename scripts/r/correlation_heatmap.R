library(pheatmap)
library(tidyverse)

# load the correlation data from your R analysis output

corr_df <- read_csv("outputs/tables/correlation_data_tract.csv")

# compute correlation matrix on numeric columns

cor_matrix <- corr_df %>%
  select(where(is.numeric)) %>%
  cor(use = "complete.obs")

# save as png

png("outputs/figures/correlation_heatmap_r.png", width = 10, height = 8, units = "in", res = 300)
pheatmap(cor_matrix,
         display_numbers = TRUE,
         number_format = "%.3f",
         color = colorRampPalette(c("#2166ac", "#f7f7f7", "#b2182b"))(100),
         main = "Correlation Matrix: Voting Access Variables\nMontgomery County, AL",
         fontsize_number = 9,
         clustering_method = "complete")
dev.off()