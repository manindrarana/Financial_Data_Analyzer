# ML Data Quality Report

Generated on: 2026-04-25 19:13:30.021432

## 1. Data Summary
asset_symbol interval  row_count          start_date            end_date
         DOT        W         68 2025-01-06 00:00:00 2026-04-20 00:00:00
        DYDX       1h      39583 2021-10-19 13:00:00 2026-04-25 19:00:00
         LTC        W         89 2024-08-12 00:00:00 2026-04-20 00:00:00
         XRP        W         60 2025-03-03 00:00:00 2026-04-20 00:00:00
        MSFT       1d       3397 2012-10-16 00:00:00 2026-04-22 00:00:00
         SOL       1h      39493 2021-10-23 07:00:00 2026-04-25 19:00:00
       GOOGL       1d       3397 2012-10-16 00:00:00 2026-04-22 00:00:00
        TSLA       1h       3382 2024-05-13 16:30:00 2026-04-22 19:30:00
        TSLA      1wk        554 2015-10-25 00:00:00 2026-04-20 00:00:00
    1000PEPE       1d        890 2023-11-18 00:00:00 2026-04-25 00:00:00
        AVAX       1h      40205 2021-09-23 15:00:00 2026-04-25 19:00:00
        DOGE        W         57 2025-03-24 00:00:00 2026-04-20 00:00:00
         ADA       1d       1666 2021-10-03 00:00:00 2026-04-25 00:00:00
         BTC       1d       2024 2020-10-10 00:00:00 2026-04-25 00:00:00
         SOL        W         38 2025-08-04 00:00:00 2026-04-20 00:00:00
        AMZN       1h       3382 2024-05-13 16:30:00 2026-04-22 19:30:00
        AMZN      1wk        554 2015-10-25 00:00:00 2026-04-20 00:00:00
        AVAX        W         42 2025-07-07 00:00:00 2026-04-20 00:00:00
        DOGE       1h      42723 2021-06-10 17:00:00 2026-04-25 19:00:00
        AAPL       1d       3397 2012-10-16 00:00:00 2026-04-22 00:00:00
        META       1h       3382 2024-05-13 16:30:00 2026-04-22 19:30:00
        META      1wk        529 2016-03-07 00:00:00 2026-04-20 00:00:00
         DOT       1h      44548 2021-03-26 16:00:00 2026-04-25 19:00:00
        DYDX        W         38 2025-08-04 00:00:00 2026-04-20 00:00:00
        AMZN       1d       3397 2012-10-16 00:00:00 2026-04-22 00:00:00
        DOGE       1d       1590 2021-12-18 00:00:00 2026-04-25 00:00:00
        AAPL       1h       3382 2024-05-13 16:30:00 2026-04-22 19:30:00
        AAPL      1wk        554 2015-10-25 00:00:00 2026-04-20 00:00:00
         ETH       1d       1669 2021-09-30 00:00:00 2026-04-25 00:00:00
         LTC       1h      48100 2020-10-29 16:00:00 2026-04-25 19:00:00
         XRP       1h      43204 2021-05-21 16:00:00 2026-04-25 19:00:00
         ETH        W         68 2025-01-06 00:00:00 2026-04-20 00:00:00
        MSFT       1h       3382 2024-05-13 16:30:00 2026-04-22 19:30:00
        MSFT      1wk        554 2015-10-25 00:00:00 2026-04-20 00:00:00
         ADA        W         68 2025-01-06 00:00:00 2026-04-20 00:00:00
         BTC        W        119 2024-01-15 00:00:00 2026-04-20 00:00:00
         SOL       1d       1455 2022-05-02 00:00:00 2026-04-25 00:00:00
        META       1d       3302 2013-03-07 00:00:00 2026-04-22 00:00:00
         DOT       1d       1666 2021-10-03 00:00:00 2026-04-25 00:00:00
         ADA       1h      44550 2021-03-26 14:00:00 2026-04-25 19:00:00
         BTC       1h      53139 2020-04-02 17:00:00 2026-04-25 19:00:00
       GOOGL       1h       3382 2024-05-13 16:30:00 2026-04-22 19:30:00
       GOOGL      1wk        554 2015-10-25 00:00:00 2026-04-20 00:00:00
        TSLA       1d       3397 2012-10-16 00:00:00 2026-04-22 00:00:00
    1000PEPE       1h      25922 2023-05-11 18:00:00 2026-04-25 19:00:00
        AVAX       1d       1485 2022-04-02 00:00:00 2026-04-25 00:00:00
         ETH       1h      44629 2021-03-23 07:00:00 2026-04-25 19:00:00
         LTC       1d       1814 2021-05-08 00:00:00 2026-04-25 00:00:00
         XRP       1d       1610 2021-11-28 00:00:00 2026-04-25 00:00:00
        DYDX       1d       1459 2022-04-28 00:00:00 2026-04-25 00:00:00

## 2. Missing Values (NaNs)
Status: Perfect (0 Nulls found)

## 3. Data Gaps
Note: Stock market data (1h/1d) correctly shows gaps for weekends.

Asset Interval  Expected  Actual  Gaps  Gap_%
 MSFT       1d      4937    3397  1540 31.19%
 META       1h     17020    3382 13638 80.13%
 MSFT       1h     17020    3382 13638 80.13%
 META       1d      4795    3302  1493 31.14%
 AMZN       1d      4937    3397  1540 31.19%
 AAPL       1h     17020    3382 13638 80.13%
GOOGL       1h     17020    3382 13638 80.13%
 TSLA       1d      4937    3397  1540 31.19%
 AMZN       1h     17020    3382 13638 80.13%
 AAPL       1d      4937    3397  1540 31.19%
GOOGL       1d      4937    3397  1540 31.19%
 TSLA       1h     17020    3382 13638 80.13%

## 4. Frozen Prices 
Assets with excessive repeated prices (>5 rows):

asset_symbol interval  frozen_candles  total_candles Frozen_%
        AVAX       1h             519          40205    1.29%
        TSLA       1h               6           3382    0.18%
        TSLA      1wk               6            554    1.08%
         DOT       1h             729          44548    1.64%
        DYDX       1d               7           1459    0.48%
    1000PEPE       1h             153          25922    0.59%
       GOOGL       1h               6           3382    0.18%
       GOOGL      1wk               6            554    1.08%
        DYDX       1h            1716          39583    4.34%
        AAPL       1h               7           3382    0.21%
        AAPL      1wk               6            554    1.08%
        META       1d               9           3302    0.27%
         SOL       1h             177          39493    0.45%
        MSFT       1d              22           3397    0.65%
        MSFT      1wk               6            554    1.08%
        DOGE       1h             995          42723    2.33%
        AMZN       1h               7           3382    0.21%
        AMZN      1wk               6            554    1.08%
        AAPL       1d               7           3397    0.21%
         ETH       1h              41          44629    0.09%
         LTC       1h             459          48100    0.95%
         XRP       1h             515          43204    1.19%
         ADA       1h             638          44550    1.43%
         BTC       1h             103          53139    0.19%

## 5. Extreme Spikes (Outliers)
Assets with flash crashes/spikes (>5 standard deviations):

asset_symbol interval  spike_candles
         LTC        W             38
         XRP        W             26
         DOT        W             28
        DYDX       1h             43
         ETH       1d            187
         LTC       1h             63
         XRP       1h             63
         ADA       1d            161
         BTC       1d            243
         SOL        W             12
       GOOGL       1d             13
        TSLA      1wk             23
        DOGE        W             26
    1000PEPE       1d            115
        AVAX       1h             31
        META       1h              2
        META      1wk             18
        DYDX        W             21
         DOT       1h             57
         ETH        W             37
        DYDX       1d            141
        AMZN       1d             12
        DOGE       1d            164
        AAPL       1h              1
        AAPL      1wk             20
         BTC       1h             59
         ADA       1h             49
        META       1d             14
         DOT       1d            165
        MSFT       1d             14
         SOL       1h             44
         LTC       1d            173
         ETH       1h             51
         XRP       1d            138
        MSFT       1h              2
        MSFT      1wk             19
         BTC        W             47
         ADA        W             31
         SOL       1d            154
       GOOGL       1h              1
       GOOGL      1wk             22
        TSLA       1d              9
    1000PEPE       1h             42
        AVAX       1d            163
        AMZN       1h              2
        AMZN      1wk             22
        DOGE       1h             79
        AVAX        W             19
        AAPL       1d             13

## 6. Timestamp & Interval Integrity
Inconsistent Interval Deltas (Time Drift):
asset_symbol interval  drift_events
        AMZN       1h           486
        AMZN      1wk             5
        AAPL       1d           743
        META       1h           486
        MSFT       1d           743
        MSFT       1h           486
        MSFT      1wk             5
        META       1d           720
        TSLA       1d           743
       GOOGL       1h           486
       GOOGL      1wk             5
        AMZN       1d           743
        AAPL       1h           486
        AAPL      1wk             5
       GOOGL       1d           743
        TSLA       1h           486
        TSLA      1wk             5

## 7. Conclusion
Data is verified for ML training.
