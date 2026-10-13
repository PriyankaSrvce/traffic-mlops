# EDA Findings

Dataset: 8,936 rows covering 1 January 2022 to 9 August 2024, across 8 areas and 16 roads, with no missing values and no duplicate rows. Traffic volume ranges from 4,233 to 72,039, with 24 high outliers (0.27%) by the IQR rule.

Location is the strongest pattern. Koramangala has the highest average volume (about 40,800) and Electronic City the lowest (about 16,300). Road identity alone explains about 34% of the variance in volume (R2 = 0.34).

There is almost no variation over time or weather. Weekend volume is only 0.7% lower than weekday volume, monthly averages stay between about 28,800 and 29,700, yearly averages are flat (29,456 in 2022, 29,016 in 2023, 29,235 in 2024), and average volume is similar across all weather types.

Rows are uneven across areas (Indiranagar 19.2% vs Electronic City 6.2%), and Windy weather is the rarest condition at 4.8%.

Columns such as Environmental Impact (correlation about 1.0 with volume), Congestion Level, and Travel Time Index are measured together with volume and cannot be used as model inputs.

Expected effect on modelling: location will be the main predictor, with time and weather adding little.
