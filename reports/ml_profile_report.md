# ML Data Quality Report

Generated on: 2026-05-03 14:01:26.053265

## 1. Data Summary
asset_symbol interval  row_count          start_date            end_date
        AMZN       1h       3382 2024-05-13 16:30:00 2026-04-22 19:30:00
        AMZN      1wk        554 2015-10-25 00:00:00 2026-04-20 00:00:00
        AVAX        W         43 2025-07-07 00:00:00 2026-04-27 00:00:00
        AAPL       1d       3397 2012-10-16 00:00:00 2026-04-22 00:00:00
        DOGE       1h      42909 2021-06-10 17:00:00 2026-05-03 13:00:00
       GOOGL       1d       3397 2012-10-16 00:00:00 2026-04-22 00:00:00
        TSLA       1h       3382 2024-05-13 16:30:00 2026-04-22 19:30:00
        TSLA      1wk        554 2015-10-25 00:00:00 2026-04-20 00:00:00
    1000PEPE       1d        898 2023-11-18 00:00:00 2026-05-03 00:00:00
        AVAX       1h      40391 2021-09-23 15:00:00 2026-05-03 13:00:00
        DOGE        W         58 2025-03-24 00:00:00 2026-04-27 00:00:00
         ETH       1d       1677 2021-09-30 00:00:00 2026-05-03 00:00:00
         LTC       1h      48286 2020-10-29 16:00:00 2026-05-03 13:00:00
         XRP       1h      43390 2021-05-21 16:00:00 2026-05-03 13:00:00
        META       1h       3382 2024-05-13 16:30:00 2026-04-22 19:30:00
        META      1wk        529 2016-03-07 00:00:00 2026-04-20 00:00:00
         DOT       1h      44734 2021-03-26 16:00:00 2026-05-03 13:00:00
        DYDX        W         39 2025-08-04 00:00:00 2026-04-27 00:00:00
        AAPL       1h       3382 2024-05-13 16:30:00 2026-04-22 19:30:00
        AAPL      1wk        554 2015-10-25 00:00:00 2026-04-20 00:00:00
        AMZN       1d       3397 2012-10-16 00:00:00 2026-04-22 00:00:00
        DOGE       1d       1598 2021-12-18 00:00:00 2026-05-03 00:00:00
         ADA       1d       1674 2021-10-03 00:00:00 2026-05-03 00:00:00
         BTC       1d       2032 2020-10-10 00:00:00 2026-05-03 00:00:00
         SOL        W         39 2025-08-04 00:00:00 2026-04-27 00:00:00
         ETH        W         69 2025-01-06 00:00:00 2026-04-27 00:00:00
        META       1d       3302 2013-03-07 00:00:00 2026-04-22 00:00:00
         DOT       1d       1674 2021-10-03 00:00:00 2026-05-03 00:00:00
         ADA       1h      44736 2021-03-26 14:00:00 2026-05-03 13:00:00
         BTC       1h      53325 2020-04-02 17:00:00 2026-05-03 13:00:00
        MSFT       1h       3382 2024-05-13 16:30:00 2026-04-22 19:30:00
        MSFT      1wk        554 2015-10-25 00:00:00 2026-04-20 00:00:00
         ADA        W         69 2025-01-06 00:00:00 2026-04-27 00:00:00
         SOL       1d       1463 2022-05-02 00:00:00 2026-05-03 00:00:00
         BTC        W        120 2024-01-15 00:00:00 2026-04-27 00:00:00
        DYDX       1d       1467 2022-04-28 00:00:00 2026-05-03 00:00:00
       GOOGL       1h       3382 2024-05-13 16:30:00 2026-04-22 19:30:00
       GOOGL      1wk        554 2015-10-25 00:00:00 2026-04-20 00:00:00
        TSLA       1d       3397 2012-10-16 00:00:00 2026-04-22 00:00:00
    1000PEPE       1h      26108 2023-05-11 18:00:00 2026-05-03 13:00:00
        AVAX       1d       1493 2022-04-02 00:00:00 2026-05-03 00:00:00
         DOT        W         69 2025-01-06 00:00:00 2026-04-27 00:00:00
        DYDX       1h      39769 2021-10-19 13:00:00 2026-05-03 13:00:00
         LTC        W         90 2024-08-12 00:00:00 2026-04-27 00:00:00
         XRP        W         61 2025-03-03 00:00:00 2026-04-27 00:00:00
        MSFT       1d       3397 2012-10-16 00:00:00 2026-04-22 00:00:00
         SOL       1h      39679 2021-10-23 07:00:00 2026-05-03 13:00:00
         ETH       1h      44815 2021-03-23 07:00:00 2026-05-03 13:00:00
         LTC       1d       1822 2021-05-08 00:00:00 2026-05-03 00:00:00
         XRP       1d       1618 2021-11-28 00:00:00 2026-05-03 00:00:00

## 2. Missing Values (NaNs)
Status: Perfect (0 Nulls found)

## 3. Data Gaps
Note: Stock market data (1h/1d) correctly shows gaps for weekends.

Asset Interval  Expected  Actual  Gaps  Gap_%
 MSFT       1d      4937    3397  1540 31.19%
 MSFT       1h     17020    3382 13638 80.13%
 AMZN       1h     17020    3382 13638 80.13%
 AAPL       1d      4937    3397  1540 31.19%
 META       1d      4795    3302  1493 31.14%
GOOGL       1h     17020    3382 13638 80.13%
 TSLA       1d      4937    3397  1540 31.19%
GOOGL       1d      4937    3397  1540 31.19%
 TSLA       1h     17020    3382 13638 80.13%
 AAPL       1h     17020    3382 13638 80.13%
 AMZN       1d      4937    3397  1540 31.19%
 META       1h     17020    3382 13638 80.13%

## 4. Frozen Prices 
Assets with excessive repeated prices (>5 rows):

asset_symbol interval  frozen_candles  total_candles Frozen_%
       GOOGL       1h               6           3382    0.18%
       GOOGL      1wk               6            554    1.08%
    1000PEPE       1h             156          26108    0.60%
        DYDX       1h            1716          39769    4.31%
         SOL       1h             181          39679    0.46%
        MSFT       1d              22           3397    0.65%
        AAPL       1h               7           3382    0.21%
        AAPL      1wk               6            554    1.08%
        AAPL       1d               7           3397    0.21%
        DOGE       1h             996          42909    2.32%
        AMZN       1h               7           3382    0.21%
        AMZN      1wk               6            554    1.08%
        MSFT      1wk               6            554    1.08%
         DOT       1h             733          44734    1.64%
         LTC       1h             467          48286    0.97%
         XRP       1h             517          43390    1.19%
        DYDX       1d               7           1467    0.48%
        AVAX       1h             523          40391    1.29%
        TSLA       1h               6           3382    0.18%
        TSLA      1wk               6            554    1.08%
         ETH       1h              41          44815    0.09%
        META       1d               9           3302    0.27%
         BTC       1h             103          53325    0.19%
         ADA       1h             650          44736    1.45%

## 5. Extreme Spikes (Outliers)
Assets with flash crashes/spikes (>5 standard deviations):

asset_symbol interval  spike_candles
         DOT        W             28
        DYDX       1h             43
         LTC        W             38
         XRP        W             26
       GOOGL       1d             13
        TSLA      1wk             23
        DOGE        W             26
    1000PEPE       1d            116
        AVAX       1h             31
         ETH       1d            187
         LTC       1h             64
         XRP       1h             63
         ADA       1d            162
         BTC       1d            245
         SOL        W             12
        AAPL      1wk             20
        AMZN       1d             12
        DOGE       1d            164
        AAPL       1h              1
        DYDX       1d            142
         LTC       1d            173
         ETH       1h             51
         XRP       1d            139
         BTC       1h             59
         ADA       1h             50
        META       1h              2
        META      1wk             18
         DOT       1h             57
        DYDX        W             22
        MSFT       1h              2
        MSFT      1wk             19
         BTC        W             47
         ADA        W             31
         SOL       1d            154
         ETH        W             37
        META       1d             14
         DOT       1d            165
       GOOGL       1h              1
       GOOGL      1wk             22
        TSLA       1d              9
    1000PEPE       1h             42
        AVAX       1d            163
        MSFT       1d             14
         SOL       1h             44
        AMZN       1h              2
        AMZN      1wk             22
        DOGE       1h             79
        AVAX        W             19
        AAPL       1d             13

## 6. Timestamp & Interval Integrity
Inconsistent Interval Deltas (Time Drift):
asset_symbol interval  drift_events
        META       1h           486
       GOOGL       1d           743
        TSLA       1h           486
        TSLA      1wk             5
        MSFT       1d           743
        MSFT       1h           486
        MSFT      1wk             5
        META       1d           720
        AAPL       1h           486
        AAPL      1wk             5
        AMZN       1d           743
        TSLA       1d           743
       GOOGL       1h           486
       GOOGL      1wk             5
        AMZN       1h           486
        AMZN      1wk             5
        AAPL       1d           743

## 7. Conclusion
Data is verified for ML training.
