# ML Data Quality Report

Generated on: 2026-04-23 12:20:56.082499

## 1. Data Summary
asset_symbol interval  row_count          start_date            end_date
         DOT        W         68 2025-01-06 00:00:00 2026-04-20 00:00:00
        DYDX       1h      39528 2021-10-19 13:00:00 2026-04-23 12:00:00
         LTC        W         89 2024-08-12 00:00:00 2026-04-20 00:00:00
         XRP        W         60 2025-03-03 00:00:00 2026-04-20 00:00:00
        MSFT       1d       3397 2012-10-16 00:00:00 2026-04-22 00:00:00
         SOL       1h      39438 2021-10-23 07:00:00 2026-04-23 12:00:00
        AMZN       1h       3382 2024-05-13 16:30:00 2026-04-22 19:30:00
        AMZN      1wk        554 2015-10-25 00:00:00 2026-04-20 00:00:00
        DOGE       1h      42668 2021-06-10 17:00:00 2026-04-23 12:00:00
        AVAX        W         42 2025-07-07 00:00:00 2026-04-20 00:00:00
        AAPL       1d       3397 2012-10-16 00:00:00 2026-04-22 00:00:00
       GOOGL       1d       3397 2012-10-16 00:00:00 2026-04-22 00:00:00
        TSLA       1h       3382 2024-05-13 16:30:00 2026-04-22 19:30:00
        TSLA      1wk        554 2015-10-25 00:00:00 2026-04-20 00:00:00
        DOGE        W         57 2025-03-24 00:00:00 2026-04-20 00:00:00
    1000PEPE       1d        888 2023-11-18 00:00:00 2026-04-23 00:00:00
        AVAX       1h      40150 2021-09-23 15:00:00 2026-04-23 12:00:00
         ADA       1d       1664 2021-10-03 00:00:00 2026-04-23 00:00:00
         BTC       1d       2022 2020-10-10 00:00:00 2026-04-23 00:00:00
         SOL        W         38 2025-08-04 00:00:00 2026-04-20 00:00:00
        META       1h       3382 2024-05-13 16:30:00 2026-04-22 19:30:00
        META      1wk        529 2016-03-07 00:00:00 2026-04-20 00:00:00
         DOT       1h      44493 2021-03-26 16:00:00 2026-04-23 12:00:00
        DYDX        W         38 2025-08-04 00:00:00 2026-04-20 00:00:00
        MSFT       1h       3382 2024-05-13 16:30:00 2026-04-22 19:30:00
        MSFT      1wk        554 2015-10-25 00:00:00 2026-04-20 00:00:00
         BTC        W        119 2024-01-15 00:00:00 2026-04-20 00:00:00
         ADA        W         68 2025-01-06 00:00:00 2026-04-20 00:00:00
         SOL       1d       1453 2022-05-02 00:00:00 2026-04-23 00:00:00
         ETH       1d       1667 2021-09-30 00:00:00 2026-04-23 00:00:00
         LTC       1h      48045 2020-10-29 16:00:00 2026-04-23 12:00:00
         XRP       1h      43149 2021-05-21 16:00:00 2026-04-23 12:00:00
         ETH        W         68 2025-01-06 00:00:00 2026-04-20 00:00:00
        DYDX       1d       1457 2022-04-28 00:00:00 2026-04-23 00:00:00
        META       1d       3302 2013-03-07 00:00:00 2026-04-22 00:00:00
         DOT       1d       1664 2021-10-03 00:00:00 2026-04-23 00:00:00
         BTC       1h      53084 2020-04-02 17:00:00 2026-04-23 12:00:00
         ADA       1h      44495 2021-03-26 14:00:00 2026-04-23 12:00:00
       GOOGL       1h       3382 2024-05-13 16:30:00 2026-04-22 19:30:00
       GOOGL      1wk        554 2015-10-25 00:00:00 2026-04-20 00:00:00
        TSLA       1d       3397 2012-10-16 00:00:00 2026-04-22 00:00:00
    1000PEPE       1h      25867 2023-05-11 18:00:00 2026-04-23 12:00:00
        AVAX       1d       1483 2022-04-02 00:00:00 2026-04-23 00:00:00
         ETH       1h      44574 2021-03-23 07:00:00 2026-04-23 12:00:00
         LTC       1d       1812 2021-05-08 00:00:00 2026-04-23 00:00:00
         XRP       1d       1608 2021-11-28 00:00:00 2026-04-23 00:00:00
        AMZN       1d       3397 2012-10-16 00:00:00 2026-04-22 00:00:00
        DOGE       1d       1588 2021-12-18 00:00:00 2026-04-23 00:00:00
        AAPL       1h       3382 2024-05-13 16:30:00 2026-04-22 19:30:00
        AAPL      1wk        554 2015-10-25 00:00:00 2026-04-20 00:00:00

## 2. Missing Values (NaNs)
Status: Perfect (0 Nulls found)

## 3. Data Gaps
Note: Stock market data (1h/1d) correctly shows gaps for weekends.

Asset Interval  Expected  Actual  Gaps  Gap_%
 AAPL       1d      4937    3397  1540 31.19%
 AMZN       1h     17020    3382 13638 80.13%
 META       1h     17020    3382 13638 80.13%
GOOGL       1h     17020    3382 13638 80.13%
 TSLA       1d      4937    3397  1540 31.19%
 AAPL       1h     17020    3382 13638 80.13%
 AMZN       1d      4937    3397  1540 31.19%
 META       1d      4795    3302  1493 31.14%
GOOGL       1d      4937    3397  1540 31.19%
 TSLA       1h     17020    3382 13638 80.13%
 MSFT       1d      4937    3397  1540 31.19%
 MSFT       1h     17020    3382 13638 80.13%

## 4. Frozen Prices 
Assets with excessive repeated prices (>5 rows):

asset_symbol interval  frozen_candles  total_candles Frozen_%
        AAPL       1h               7           3382    0.21%
        AAPL      1wk               6            554    1.08%
        DYDX       1h            1716          39528    4.34%
         ETH       1h              41          44574    0.09%
        MSFT       1d              22           3397    0.65%
         SOL       1h             176          39438    0.45%
    1000PEPE       1h             151          25867    0.58%
       GOOGL       1h               6           3382    0.18%
       GOOGL      1wk               6            554    1.08%
        AVAX       1h             518          40150    1.29%
        TSLA       1h               6           3382    0.18%
        TSLA      1wk               6            554    1.08%
        DYDX       1d               7           1457    0.48%
         LTC       1h             458          48045    0.95%
         XRP       1h             515          43149    1.19%
         DOT       1h             727          44493    1.63%
         BTC       1h             103          53084    0.19%
         ADA       1h             633          44495    1.42%
        MSFT      1wk               6            554    1.08%
        DOGE       1h             995          42668    2.33%
        AAPL       1d               7           3397    0.21%
        AMZN       1h               7           3382    0.21%
        AMZN      1wk               6            554    1.08%
        META       1d               9           3302    0.27%

## 5. Extreme Spikes (Outliers)
Assets with flash crashes/spikes (>5 standard deviations):

asset_symbol interval  spike_candles
         DOT        W             28
        DYDX       1h             44
       GOOGL       1d             13
        TSLA      1wk             23
        DOGE        W             26
    1000PEPE       1d            115
        AVAX       1h             31
        META       1h              2
        META      1wk             18
         DOT       1h             57
        DYDX        W             21
         ETH        W             37
         LTC        W             38
         XRP        W             26
        AMZN       1d             12
        DOGE       1d            164
        AAPL       1h              1
        AAPL      1wk             20
        AMZN       1h              2
        AMZN      1wk             22
        DOGE       1h             79
        AAPL       1d             13
        AVAX        W             19
        META       1d             14
         DOT       1d            165
        MSFT       1d             14
         SOL       1h             44
       GOOGL       1h              1
       GOOGL      1wk             22
        TSLA       1d              9
    1000PEPE       1h             42
        AVAX       1d            163
         BTC       1h             59
         ADA       1h             49
         SOL        W             12
         ADA       1d            161
         BTC       1d            243
         ETH       1d            187
         LTC       1h             63
         XRP       1h             63
        MSFT       1h              2
        MSFT      1wk             19
         BTC        W             47
         SOL       1d            154
         ADA        W             31
         LTC       1d            173
         ETH       1h             51
         XRP       1d            138
        DYDX       1d            141

## 6. Timestamp & Interval Integrity
Inconsistent Interval Deltas (Time Drift):
asset_symbol interval  drift_events
        META       1h           486
        MSFT       1d           743
        MSFT       1h           486
        MSFT      1wk             5
        TSLA       1h           486
        TSLA      1wk             5
       GOOGL       1d           743
        AAPL       1d           743
        AMZN       1h           486
        AMZN      1wk             5
        AMZN       1d           743
        AAPL       1h           486
        AAPL      1wk             5
        META       1d           720
       GOOGL       1h           486
       GOOGL      1wk             5
        TSLA       1d           743

## 7. Conclusion
Data is verified for ML training.
