# Prompt 5: Normalizer Ablation Report

Evaluated on DEV DATA ONLY: ArgGround dev, DeRef fcrb dev, DeRef cfb dev, and MCP-Atlas dev.
Paired difference $\Delta = \text{Metric}(\text{config}) - \text{Metric}(\text{all-on})$ with 95% paired cluster-bootstrap CIs.

## 1. Ablation Results Table

| Dataset | Configuration | Detection [95% CI] | Diff Detection vs all-on [95% CI] | Hard-Block [95% CI] | Interruption [95% CI] | Diff Interruption vs all-on [95% CI] |
| --- | --- | --- | --- | --- | --- | --- |
| argground | all-on | 0.964 [0.952, 0.977] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.068 [0.052, 0.085] | 0.000 [0.000, 0.000] |
| argground | all-off | 0.986 [0.977, 0.993] | +0.021 [0.012, 0.031] | 0.000 [0.000, 0.000] | 0.147 [0.124, 0.173] | +0.079 [0.062, 0.098] |
| argground | loo_spelled_numbers | 0.964 [0.952, 0.977] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.068 [0.052, 0.085] | 0.000 [0.000, 0.000] |
| argground | loo_numeric_formats | 0.964 [0.952, 0.977] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.113 [0.094, 0.135] | +0.045 [0.032, 0.059] |
| argground | loo_iso_dates | 0.948 [0.931, 0.963] | -0.017 [-0.028, -0.007] | 0.000 [0.000, 0.000] | 0.072 [0.055, 0.090] | +0.003 [0.000, 0.008] |
| argground | loo_spoken_dates_times | 0.964 [0.952, 0.977] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.073 [0.056, 0.091] | +0.004 [0.001, 0.009] |
| argground | loo_currency_equivalence | 0.972 [0.960, 0.983] | +0.007 [0.002, 0.013] | 0.000 [0.000, 0.000] | 0.090 [0.072, 0.111] | +0.022 [0.012, 0.033] |
| argground | loo_stemming | 0.966 [0.953, 0.978] | +0.001 [0.000, 0.004] | 0.000 [0.000, 0.000] | 0.070 [0.054, 0.088] | +0.002 [0.000, 0.006] |
| argground | loo_fuzzy_match | 0.973 [0.961, 0.983] | +0.008 [0.002, 0.015] | 0.000 [0.000, 0.000] | 0.069 [0.054, 0.087] | +0.001 [0.000, 0.003] |
| argground | loo_token_set_containment | 0.964 [0.952, 0.977] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.068 [0.052, 0.085] | 0.000 [0.000, 0.000] |
| argground | aoi_spelled_numbers | 0.986 [0.977, 0.993] | +0.021 [0.012, 0.031] | 0.000 [0.000, 0.000] | 0.147 [0.124, 0.173] | +0.079 [0.062, 0.098] |
| argground | aoi_numeric_formats | 0.986 [0.977, 0.993] | +0.021 [0.012, 0.031] | 0.000 [0.000, 0.000] | 0.102 [0.084, 0.126] | +0.034 [0.022, 0.048] |
| argground | aoi_iso_dates | 0.986 [0.977, 0.993] | +0.021 [0.012, 0.031] | 0.000 [0.000, 0.000] | 0.149 [0.125, 0.173] | +0.080 [0.063, 0.099] |
| argground | aoi_spoken_dates_times | 0.986 [0.977, 0.993] | +0.021 [0.012, 0.031] | 0.000 [0.000, 0.000] | 0.147 [0.124, 0.173] | +0.079 [0.062, 0.098] |
| argground | aoi_currency_equivalence | 0.979 [0.968, 0.988] | +0.014 [0.007, 0.022] | 0.000 [0.000, 0.000] | 0.125 [0.104, 0.148] | +0.057 [0.042, 0.072] |
| argground | aoi_stemming | 0.977 [0.967, 0.987] | +0.013 [0.005, 0.022] | 0.000 [0.000, 0.000] | 0.140 [0.117, 0.165] | +0.072 [0.055, 0.089] |
| argground | aoi_fuzzy_match | 0.959 [0.943, 0.972] | -0.006 [-0.019, 0.006] | 0.000 [0.000, 0.000] | 0.143 [0.121, 0.169] | +0.075 [0.058, 0.093] |
| argground | aoi_token_set_containment | 0.979 [0.968, 0.987] | +0.014 [0.006, 0.023] | 0.000 [0.000, 0.000] | 0.142 [0.119, 0.167] | +0.074 [0.056, 0.092] |
| deref_fcrb | all-on | 0.654 [0.605, 0.709] | 0.000 [0.000, 0.000] | 0.127 [0.091, 0.160] | 0.559 [0.508, 0.613] | 0.000 [0.000, 0.000] |
| deref_fcrb | all-off | 0.743 [0.692, 0.791] | +0.089 [0.057, 0.122] | 0.127 [0.091, 0.160] | 0.648 [0.598, 0.698] | +0.089 [0.062, 0.123] |
| deref_fcrb | loo_spelled_numbers | 0.663 [0.611, 0.717] | +0.010 [0.000, 0.022] | 0.127 [0.091, 0.160] | 0.571 [0.521, 0.624] | +0.013 [0.003, 0.026] |
| deref_fcrb | loo_numeric_formats | 0.657 [0.606, 0.713] | +0.003 [0.000, 0.010] | 0.127 [0.091, 0.160] | 0.571 [0.520, 0.625] | +0.013 [0.003, 0.026] |
| deref_fcrb | loo_iso_dates | 0.673 [0.620, 0.726] | +0.019 [0.006, 0.034] | 0.127 [0.091, 0.160] | 0.571 [0.522, 0.627] | +0.013 [-0.006, 0.035] |
| deref_fcrb | loo_spoken_dates_times | 0.676 [0.623, 0.731] | +0.022 [0.007, 0.039] | 0.127 [0.091, 0.160] | 0.584 [0.533, 0.639] | +0.025 [0.009, 0.046] |
| deref_fcrb | loo_currency_equivalence | 0.657 [0.608, 0.711] | +0.003 [0.000, 0.010] | 0.127 [0.091, 0.160] | 0.565 [0.515, 0.617] | +0.006 [0.000, 0.016] |
| deref_fcrb | loo_stemming | 0.654 [0.605, 0.709] | 0.000 [0.000, 0.000] | 0.127 [0.091, 0.160] | 0.559 [0.508, 0.613] | 0.000 [0.000, 0.000] |
| deref_fcrb | loo_fuzzy_match | 0.689 [0.637, 0.741] | +0.035 [0.016, 0.056] | 0.127 [0.091, 0.160] | 0.587 [0.536, 0.639] | +0.029 [0.013, 0.048] |
| deref_fcrb | loo_token_set_containment | 0.654 [0.605, 0.709] | 0.000 [0.000, 0.000] | 0.127 [0.091, 0.160] | 0.559 [0.508, 0.613] | 0.000 [0.000, 0.000] |
| deref_fcrb | aoi_spelled_numbers | 0.737 [0.685, 0.786] | +0.083 [0.052, 0.113] | 0.127 [0.091, 0.160] | 0.641 [0.591, 0.692] | +0.083 [0.055, 0.115] |
| deref_fcrb | aoi_numeric_formats | 0.740 [0.689, 0.788] | +0.086 [0.055, 0.117] | 0.127 [0.091, 0.160] | 0.635 [0.584, 0.686] | +0.076 [0.051, 0.109] |
| deref_fcrb | aoi_iso_dates | 0.743 [0.692, 0.791] | +0.089 [0.057, 0.122] | 0.127 [0.091, 0.160] | 0.651 [0.602, 0.702] | +0.092 [0.064, 0.126] |
| deref_fcrb | aoi_spoken_dates_times | 0.743 [0.692, 0.791] | +0.089 [0.057, 0.122] | 0.127 [0.091, 0.160] | 0.648 [0.598, 0.698] | +0.089 [0.062, 0.123] |
| deref_fcrb | aoi_currency_equivalence | 0.740 [0.691, 0.788] | +0.086 [0.054, 0.117] | 0.127 [0.091, 0.160] | 0.641 [0.592, 0.692] | +0.083 [0.056, 0.115] |
| deref_fcrb | aoi_stemming | 0.717 [0.667, 0.767] | +0.063 [0.036, 0.092] | 0.127 [0.091, 0.160] | 0.635 [0.585, 0.688] | +0.076 [0.051, 0.106] |
| deref_fcrb | aoi_fuzzy_match | 0.695 [0.645, 0.750] | +0.041 [0.021, 0.064] | 0.127 [0.091, 0.160] | 0.613 [0.563, 0.666] | +0.054 [0.027, 0.088] |
| deref_fcrb | aoi_token_set_containment | 0.721 [0.669, 0.771] | +0.067 [0.039, 0.093] | 0.127 [0.091, 0.160] | 0.635 [0.585, 0.688] | +0.076 [0.051, 0.106] |
| deref_cfb | all-on | 0.480 [0.429, 0.535] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.397 [0.324, 0.467] | 0.000 [0.000, 0.000] |
| deref_cfb | all-off | 0.706 [0.657, 0.753] | +0.225 [0.182, 0.272] | 0.000 [0.000, 0.000] | 0.414 [0.339, 0.484] | +0.017 [0.000, 0.039] |
| deref_cfb | loo_spelled_numbers | 0.480 [0.429, 0.535] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.397 [0.324, 0.467] | 0.000 [0.000, 0.000] |
| deref_cfb | loo_numeric_formats | 0.480 [0.429, 0.535] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.397 [0.324, 0.467] | 0.000 [0.000, 0.000] |
| deref_cfb | loo_iso_dates | 0.477 [0.426, 0.531] | -0.003 [-0.009, 0.000] | 0.000 [0.000, 0.000] | 0.397 [0.323, 0.467] | 0.000 [-0.016, 0.017] |
| deref_cfb | loo_spoken_dates_times | 0.480 [0.429, 0.535] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.402 [0.329, 0.470] | +0.006 [0.000, 0.018] |
| deref_cfb | loo_currency_equivalence | 0.480 [0.429, 0.535] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.397 [0.324, 0.467] | 0.000 [0.000, 0.000] |
| deref_cfb | loo_stemming | 0.480 [0.429, 0.535] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.397 [0.324, 0.467] | 0.000 [0.000, 0.000] |
| deref_cfb | loo_fuzzy_match | 0.697 [0.648, 0.744] | +0.216 [0.174, 0.262] | 0.000 [0.000, 0.000] | 0.402 [0.330, 0.472] | +0.006 [0.000, 0.018] |
| deref_cfb | loo_token_set_containment | 0.480 [0.429, 0.535] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.397 [0.324, 0.467] | 0.000 [0.000, 0.000] |
| deref_cfb | aoi_spelled_numbers | 0.706 [0.657, 0.753] | +0.225 [0.182, 0.272] | 0.000 [0.000, 0.000] | 0.414 [0.339, 0.484] | +0.017 [0.000, 0.039] |
| deref_cfb | aoi_numeric_formats | 0.706 [0.657, 0.753] | +0.225 [0.182, 0.272] | 0.000 [0.000, 0.000] | 0.414 [0.339, 0.484] | +0.017 [0.000, 0.039] |
| deref_cfb | aoi_iso_dates | 0.706 [0.657, 0.753] | +0.225 [0.182, 0.272] | 0.000 [0.000, 0.000] | 0.414 [0.339, 0.484] | +0.017 [0.000, 0.039] |
| deref_cfb | aoi_spoken_dates_times | 0.706 [0.657, 0.753] | +0.225 [0.182, 0.272] | 0.000 [0.000, 0.000] | 0.414 [0.339, 0.484] | +0.017 [0.000, 0.039] |
| deref_cfb | aoi_currency_equivalence | 0.706 [0.657, 0.753] | +0.225 [0.182, 0.272] | 0.000 [0.000, 0.000] | 0.414 [0.339, 0.484] | +0.017 [0.000, 0.039] |
| deref_cfb | aoi_stemming | 0.697 [0.648, 0.744] | +0.216 [0.174, 0.262] | 0.000 [0.000, 0.000] | 0.402 [0.330, 0.474] | +0.006 [-0.012, 0.028] |
| deref_cfb | aoi_fuzzy_match | 0.486 [0.435, 0.541] | +0.006 [0.000, 0.015] | 0.000 [0.000, 0.000] | 0.408 [0.333, 0.478] | +0.011 [0.000, 0.030] |
| deref_cfb | aoi_token_set_containment | 0.697 [0.648, 0.744] | +0.216 [0.174, 0.262] | 0.000 [0.000, 0.000] | 0.402 [0.330, 0.474] | +0.006 [-0.012, 0.028] |
| mcpatlas | all-on | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.688 [0.669, 0.704] | 0.000 [0.000, 0.000] |
| mcpatlas | all-off | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.741 [0.724, 0.757] | +0.054 [0.044, 0.064] |
| mcpatlas | loo_spelled_numbers | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.688 [0.669, 0.704] | 0.000 [0.000, 0.000] |
| mcpatlas | loo_numeric_formats | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.688 [0.670, 0.705] | +0.000 [0.000, 0.001] |
| mcpatlas | loo_iso_dates | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.688 [0.669, 0.704] | 0.000 [0.000, 0.000] |
| mcpatlas | loo_spoken_dates_times | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.688 [0.669, 0.704] | 0.000 [0.000, 0.000] |
| mcpatlas | loo_currency_equivalence | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.688 [0.669, 0.704] | 0.000 [0.000, 0.000] |
| mcpatlas | loo_stemming | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.690 [0.672, 0.707] | +0.002 [0.001, 0.005] |
| mcpatlas | loo_fuzzy_match | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.703 [0.685, 0.720] | +0.015 [0.010, 0.021] |
| mcpatlas | loo_token_set_containment | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.688 [0.669, 0.704] | 0.000 [0.000, 0.000] |
| mcpatlas | aoi_spelled_numbers | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.741 [0.724, 0.757] | +0.054 [0.044, 0.064] |
| mcpatlas | aoi_numeric_formats | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.741 [0.724, 0.757] | +0.053 [0.044, 0.063] |
| mcpatlas | aoi_iso_dates | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.741 [0.724, 0.757] | +0.054 [0.044, 0.064] |
| mcpatlas | aoi_spoken_dates_times | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.741 [0.724, 0.757] | +0.054 [0.044, 0.064] |
| mcpatlas | aoi_currency_equivalence | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.741 [0.724, 0.757] | +0.054 [0.044, 0.064] |
| mcpatlas | aoi_stemming | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.703 [0.686, 0.720] | +0.016 [0.011, 0.021] |
| mcpatlas | aoi_fuzzy_match | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.714 [0.696, 0.730] | +0.027 [0.020, 0.034] |
| mcpatlas | aoi_token_set_containment | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.706 [0.688, 0.723] | +0.018 [0.013, 0.024] |

## 2. Normalizers that Do NOT Statistically Significantly Help (95% CI Contains Zero)

A normalizer is reported here if removing it (`leave-one-out`) produces a $\Delta \text{Interruption}$ whose 95% paired CI includes 0.0:

- **argground**: fuzzy_match, iso_dates, spelled_numbers, stemming, token_set_containment
- **deref_fcrb**: currency_equivalence, iso_dates, stemming, token_set_containment
- **deref_cfb**: currency_equivalence, fuzzy_match, iso_dates, numeric_formats, spelled_numbers, spoken_dates_times, stemming, token_set_containment
- **mcpatlas**: currency_equivalence, iso_dates, numeric_formats, spelled_numbers, spoken_dates_times, token_set_containment

## 3. Top 30 Most Frequent False Blocks under all-on

Clean calls (`label == 0`) flagged as ungrounded by the checker, with nearest context span found via string/numeric distance.

| Rank | Dataset | Argument | Value | Count | Nearest Context Span | Similarity Ratio |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | mcpatlas | base_id | `appIF9byLfQwdHqE2` | 201 | `SpaceX launched the` | 0.278 |
| 2 | mcpatlas | database | `video_game_store` | 184 | `gaming store,` | 0.552 |
| 3 | mcpatlas | field_name | `Date` | 81 | `data?` | 0.667 |
| 4 | mcpatlas | interval | `1d` | 59 | `and` | 0.4 |
| 5 | mcpatlas | table_name | `Sales Expenses` | 54 | `was exploring` | 0.519 |
| 6 | mcpatlas | path | `/data` | 48 | `at` | 0.571 |
| 7 | mcpatlas | collection | `Purchase History` | 33 | `game store,` | 0.519 |
| 8 | mcpatlas | languageId | `python` | 28 | `the one` | 0.615 |
| 9 | mcpatlas | symbol | `BTC` | 23 | `bitcoin` | 0.6 |
| 10 | mcpatlas | command | `ls` | 22 | `is` | 0.5 |
| 11 | mcpatlas | collection | `Customers` | 22 | `store` | 0.571 |
| 12 | mcpatlas | path | `/data/Top Movies.csv` | 20 | `top movies` | 0.667 |
| 13 | mcpatlas | path | `/data/repos` | 17 | `are.` | 0.4 |
| 14 | argground | symbol | `MSFT` | 15 | `Microsoft?` | 0.571 |
| 15 | mcpatlas | database_id | `21b97551-844e-8090-b48d-d33c1c2be7f8` | 15 | `decade of` | 0.178 |
| 16 | mcpatlas | table_name | `Turnover Retention` | 15 | `friend, move to` | 0.485 |
| 17 | mcpatlas | database_id | `21b97551-844e-8068-b387-fe7a56b04348` | 15 | `between the campaign` | 0.143 |
| 18 | mcpatlas | collection | `Delivery Logistics` | 14 | `delivery? This` | 0.688 |
| 19 | mcpatlas | max_records | `10` | 13 | `My` | 0.0 |
| 20 | mcpatlas | path | `/data/Crime_records.csv` | 13 | `crimes recorded` | 0.579 |
| 21 | mcpatlas | command | `ls /data` | 12 | `I want` | 0.429 |
| 22 | mcpatlas | source | `en-EN` | 12 | `written in` | 0.4 |
| 23 | deref_cfb | sortBy | `attr_book_score` | 11 | `attraction there?` | 0.438 |
| 24 | mcpatlas | collection | `Social Media` | 11 | `social` | 0.667 |
| 25 | mcpatlas | channel_id | `C093FF10B5J` | 10 | `oscar for best` | 0.24 |
| 26 | mcpatlas | target | `es-ES` | 10 | `exists,` | 0.5 |
| 27 | mcpatlas | table_name | `Inventory Levels Turnover` | 10 | `I need to know` | 0.41 |
| 28 | mcpatlas | path | `/data/CoinbaseTradeHistory.csv` | 10 | `that operation` | 0.364 |
| 29 | deref_cfb | pick_up_time | `08:00` | 9 | `8` | 0.333 |
| 30 | mcpatlas | repo_path | `/data/repos/snake-game` | 9 | `this snake-game` | 0.649 |
