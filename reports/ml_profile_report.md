# ML Data Quality Report

Generated on: 2026-04-09 19:57:59.530700

## 1. Data Summary
asset_symbol interval  row_count          start_date            end_date
         DOT        W         66 2025-01-06 00:00:00 2026-04-06 00:00:00
        DYDX       1h      39199 2021-10-19 13:00:00 2026-04-09 19:00:00
         LTC        W         87 2024-08-12 00:00:00 2026-04-06 00:00:00
         XRP        W         58 2025-03-03 00:00:00 2026-04-06 00:00:00
         ADA       1d       1650 2021-10-03 00:00:00 2026-04-09 00:00:00
         BTC       1d       2008 2020-10-10 00:00:00 2026-04-09 00:00:00
         SOL        W         36 2025-08-04 00:00:00 2026-04-06 00:00:00
        MSFT       1d       3388 2012-10-16 00:00:00 2026-04-09 00:00:00
         SOL       1h      39109 2021-10-23 07:00:00 2026-04-09 19:00:00
        META       1h       3319 2024-05-13 16:30:00 2026-04-09 19:30:00
        META      1wk        527 2016-03-07 00:00:00 2026-04-06 00:00:00
         DOT       1h      44164 2021-03-26 16:00:00 2026-04-09 19:00:00
        DYDX        W         36 2025-08-04 00:00:00 2026-04-06 00:00:00
         ETH       1d       1653 2021-09-30 00:00:00 2026-04-09 00:00:00
         LTC       1h      47716 2020-10-29 16:00:00 2026-04-09 19:00:00
         XRP       1h      42820 2021-05-21 16:00:00 2026-04-09 19:00:00
       GOOGL       1d       3388 2012-10-16 00:00:00 2026-04-09 00:00:00
        TSLA       1h       3319 2024-05-13 16:30:00 2026-04-09 19:30:00
        TSLA      1wk        552 2015-10-25 00:00:00 2026-04-06 00:00:00
    1000PEPE       1d        874 2023-11-18 00:00:00 2026-04-09 00:00:00
        AVAX       1h      39821 2021-09-23 15:00:00 2026-04-09 19:00:00
        DOGE        W         55 2025-03-24 00:00:00 2026-04-06 00:00:00
        DOGE       1d       1574 2021-12-18 00:00:00 2026-04-09 00:00:00
        AAPL       1h       3319 2024-05-13 16:30:00 2026-04-09 19:30:00
        AAPL      1wk        552 2015-10-25 00:00:00 2026-04-06 00:00:00
        AMZN       1d       3388 2012-10-16 00:00:00 2026-04-09 00:00:00
         ETH        W         66 2025-01-06 00:00:00 2026-04-06 00:00:00
         ADA       1h      44166 2021-03-26 14:00:00 2026-04-09 19:00:00
         BTC       1h      52755 2020-04-02 17:00:00 2026-04-09 19:00:00
        MSFT       1h       3319 2024-05-13 16:30:00 2026-04-09 19:30:00
        MSFT      1wk        552 2015-10-25 00:00:00 2026-04-06 00:00:00
         ADA        W         66 2025-01-06 00:00:00 2026-04-06 00:00:00
         BTC        W        117 2024-01-15 00:00:00 2026-04-06 00:00:00
         SOL       1d       1439 2022-05-02 00:00:00 2026-04-09 00:00:00
        AMZN       1h       3319 2024-05-13 16:30:00 2026-04-09 19:30:00
        AMZN      1wk        552 2015-10-25 00:00:00 2026-04-06 00:00:00
        AVAX        W         40 2025-07-07 00:00:00 2026-04-06 00:00:00
        DOGE       1h      42339 2021-06-10 17:00:00 2026-04-09 19:00:00
        AAPL       1d       3388 2012-10-16 00:00:00 2026-04-09 00:00:00
        META       1d       3293 2013-03-07 00:00:00 2026-04-09 00:00:00
         DOT       1d       1650 2021-10-03 00:00:00 2026-04-09 00:00:00
       GOOGL       1h       3319 2024-05-13 16:30:00 2026-04-09 19:30:00
       GOOGL      1wk        552 2015-10-25 00:00:00 2026-04-06 00:00:00
        TSLA       1d       3388 2012-10-16 00:00:00 2026-04-09 00:00:00
    1000PEPE       1h      25538 2023-05-11 18:00:00 2026-04-09 19:00:00
        AVAX       1d       1469 2022-04-02 00:00:00 2026-04-09 00:00:00
        DYDX       1d       1443 2022-04-28 00:00:00 2026-04-09 00:00:00
         ETH       1h      44245 2021-03-23 07:00:00 2026-04-09 19:00:00
         LTC       1d       1798 2021-05-08 00:00:00 2026-04-09 00:00:00
         XRP       1d       1594 2021-11-28 00:00:00 2026-04-09 00:00:00

## 2. Missing Values (NaNs)
Status: Perfect (0 Nulls found)

## 3. Data Gaps
Note: Stock market data (1h/1d) correctly shows gaps for weekends.

Asset Interval  Expected  Actual  Gaps  Gap_%
 MSFT       1h     16708    3319 13389 80.14%
 META       1h     16708    3319 13389 80.14%
GOOGL       1h     16708    3319 13389 80.14%
 TSLA       1d      4924    3388  1536 31.19%
 META       1d      4782    3293  1489 31.14%
 AAPL       1h     16708    3319 13389 80.14%
 AMZN       1d      4924    3388  1536 31.19%
 MSFT       1d      4924    3388  1536 31.19%
GOOGL       1d      4924    3388  1536 31.19%
 TSLA       1h     16708    3319 13389 80.14%
 AMZN       1h     16708    3319 13389 80.14%
 AAPL       1d      4924    3388  1536 31.19%

## 4. Frozen Prices 
Assets with excessive repeated prices (>5 rows):

asset_symbol interval  frozen_candles  total_candles Frozen_%
         SOL       1h             173          39109    0.44%
        MSFT       1d              22           3388    0.65%
         ETH       1h              41          44245    0.09%
         DOT       1h             725          44164    1.64%
        DYDX       1d               7           1443    0.49%
        MSFT      1wk               6            552    1.09%
        META       1d               9           3293    0.27%
         BTC       1h             103          52755    0.20%
         ADA       1h             619          44166    1.40%
    1000PEPE       1h             146          25538    0.57%
       GOOGL       1h               6           3319    0.18%
       GOOGL      1wk               6            552    1.09%
        AAPL       1h               7           3319    0.21%
        AAPL      1wk               6            552    1.09%
        AVAX       1h             516          39821    1.30%
        TSLA       1h               6           3319    0.18%
        TSLA      1wk               6            552    1.09%
        DYDX       1h            1716          39199    4.38%
        AAPL       1d               7           3388    0.21%
        DOGE       1h             989          42339    2.34%
        AMZN       1h               7           3319    0.21%
        AMZN      1wk               6            552    1.09%
         LTC       1h             450          47716    0.94%
         XRP       1h             513          42820    1.20%

## 5. Extreme Spikes (Outliers)
Assets with flash crashes/spikes (>5 standard deviations):

asset_symbol interval  spike_candles
         DOT        W             28
        DYDX       1h             44
        AMZN       1h              2
        AMZN      1wk             21
        AVAX        W             19
        AAPL       1d             13
        DOGE       1h             78
         LTC        W             38
         XRP        W             26
         ETH       1d            186
         LTC       1h             62
         XRP       1h             62
        MSFT       1h              2
        MSFT      1wk             19
         ADA        W             31
         SOL       1d            154
         BTC        W             46
        AAPL       1h              1
        AAPL      1wk             20
        AMZN       1d             12
        DOGE       1d            163
         ADA       1h             48
         BTC       1h             59
         LTC       1d            173
         ETH       1h             51
         XRP       1d            138
        DYDX       1d            140
         ETH        W             37
        META       1d             14
         DOT       1d            163
         ADA       1d            161
         BTC       1d            242
         SOL        W             12
       GOOGL       1h              1
       GOOGL      1wk             22
        TSLA       1d              9
    1000PEPE       1h             42
        AVAX       1d            163
       GOOGL       1d             13
        TSLA      1wk             22
    1000PEPE       1d            114
        AVAX       1h             30
        DOGE        W             26
        META       1h              2
        META      1wk             17
        DYDX        W             20
         DOT       1h             57
        MSFT       1d             14
         SOL       1h             43

## 6. Timestamp & Interval Integrity
Inconsistent Interval Deltas (Time Drift):
asset_symbol interval  drift_events
        MSFT       1d           741
        META       1h           477
        AAPL       1d           741
        AMZN       1h           477
        AMZN      1wk             5
        AAPL       1h           477
        AAPL      1wk             5
        AMZN       1d           741
        TSLA       1h           477
       GOOGL       1d           741
        TSLA      1wk             5
        TSLA       1d           741
       GOOGL       1h           477
       GOOGL      1wk             5
        META       1d           718
        MSFT       1h           477
        MSFT      1wk             5

## 7. Conclusion
Data is verified for ML training.
