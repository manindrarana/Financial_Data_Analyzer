# ML Data Quality Report

Generated on: 2026-05-14 15:01:21.360352

## 1. Data Summary
asset_symbol interval  row_count          start_date            end_date
         LTC        W         92 2024-08-12 00:00:00 2026-05-11 00:00:00
         XRP        W         63 2025-03-03 00:00:00 2026-05-11 00:00:00
         SOL       1h      39944 2021-10-23 07:00:00 2026-05-14 14:00:00
        MSFT       1d       3410 2012-10-16 00:00:00 2026-05-11 00:00:00
         DOT        W         71 2025-01-06 00:00:00 2026-05-11 00:00:00
        DYDX       1h      40034 2021-10-19 13:00:00 2026-05-14 14:00:00
    1000PEPE       1d        909 2023-11-18 00:00:00 2026-05-14 00:00:00
        AVAX       1h      40656 2021-09-23 15:00:00 2026-05-14 14:00:00
        DOGE        W         60 2025-03-24 00:00:00 2026-05-11 00:00:00
       GOOGL       1d       3410 2012-10-16 00:00:00 2026-05-11 00:00:00
        TSLA       1h       3473 2024-05-13 16:30:00 2026-05-11 19:30:00
        TSLA      1wk        557 2015-10-25 00:00:00 2026-05-11 00:00:00
         SOL        W         41 2025-08-04 00:00:00 2026-05-11 00:00:00
         ADA       1d       1685 2021-10-03 00:00:00 2026-05-14 00:00:00
         BTC       1d       2043 2020-10-10 00:00:00 2026-05-14 00:00:00
         LTC       1h      48551 2020-10-29 16:00:00 2026-05-14 14:00:00
         XRP       1h      43655 2021-05-21 16:00:00 2026-05-14 14:00:00
         ETH       1d       1688 2021-09-30 00:00:00 2026-05-14 00:00:00
         DOT       1h      44999 2021-03-26 16:00:00 2026-05-14 14:00:00
        META       1h       3473 2024-05-13 16:30:00 2026-05-11 19:30:00
        META      1wk        532 2016-03-07 00:00:00 2026-05-11 00:00:00
        DYDX        W         41 2025-08-04 00:00:00 2026-05-11 00:00:00
        DOGE       1d       1609 2021-12-18 00:00:00 2026-05-14 00:00:00
        AAPL       1h       3473 2024-05-13 16:30:00 2026-05-11 19:30:00
        AAPL      1wk        557 2015-10-25 00:00:00 2026-05-11 00:00:00
        AMZN       1d       3410 2012-10-16 00:00:00 2026-05-11 00:00:00
         ETH        W         71 2025-01-06 00:00:00 2026-05-11 00:00:00
        DYDX       1d       1478 2022-04-28 00:00:00 2026-05-14 00:00:00
         SOL       1d       1474 2022-05-02 00:00:00 2026-05-14 00:00:00
         ADA        W         71 2025-01-06 00:00:00 2026-05-11 00:00:00
         BTC        W        122 2024-01-15 00:00:00 2026-05-11 00:00:00
        MSFT       1h       3473 2024-05-13 16:30:00 2026-05-11 19:30:00
        MSFT      1wk        557 2015-10-25 00:00:00 2026-05-11 00:00:00
        AAPL       1d       3410 2012-10-16 00:00:00 2026-05-11 00:00:00
        AVAX        W         45 2025-07-07 00:00:00 2026-05-11 00:00:00
        DOGE       1h      43174 2021-06-10 17:00:00 2026-05-14 14:00:00
        AMZN       1h       3473 2024-05-13 16:30:00 2026-05-11 19:30:00
        AMZN      1wk        557 2015-10-25 00:00:00 2026-05-11 00:00:00
         XRP       1d       1629 2021-11-28 00:00:00 2026-05-14 00:00:00
         ETH       1h      45080 2021-03-23 07:00:00 2026-05-14 14:00:00
         LTC       1d       1833 2021-05-08 00:00:00 2026-05-14 00:00:00
    1000PEPE       1h      26373 2023-05-11 18:00:00 2026-05-14 14:00:00
        AVAX       1d       1504 2022-04-02 00:00:00 2026-05-14 00:00:00
       GOOGL       1h       3473 2024-05-13 16:30:00 2026-05-11 19:30:00
       GOOGL      1wk        557 2015-10-25 00:00:00 2026-05-11 00:00:00
        TSLA       1d       3410 2012-10-16 00:00:00 2026-05-11 00:00:00
         ADA       1h      45001 2021-03-26 14:00:00 2026-05-14 14:00:00
         BTC       1h      53590 2020-04-02 17:00:00 2026-05-14 14:00:00
         DOT       1d       1685 2021-10-03 00:00:00 2026-05-14 00:00:00
        META       1d       3315 2013-03-07 00:00:00 2026-05-11 00:00:00

## 2. Missing Values (NaNs)
Status: Perfect (0 Nulls found)

## 3. Data Gaps
Note: Stock market data (1h/1d) correctly shows gaps for weekends.

Asset Interval  Expected  Actual  Gaps  Gap_%
 AAPL       1d      4956    3410  1546 31.19%
 AMZN       1h     17476    3473 14003 80.13%
 META       1h     17476    3473 14003 80.13%
 AAPL       1h     17476    3473 14003 80.13%
 AMZN       1d      4956    3410  1546 31.19%
GOOGL       1h     17476    3473 14003 80.13%
 TSLA       1d      4956    3410  1546 31.19%
GOOGL       1d      4956    3410  1546 31.19%
 TSLA       1h     17476    3473 14003 80.13%
 MSFT       1h     17476    3473 14003 80.13%
 META       1d      4814    3315  1499 31.14%
 MSFT       1d      4956    3410  1546 31.19%

## 4. Frozen Prices 
Assets with excessive repeated prices (>5 rows):

asset_symbol interval  frozen_candles  total_candles Frozen_%
        AMZN       1h               7           3473    0.20%
        DOGE       1h             997          43174    2.31%
        AAPL       1d               7           3410    0.21%
         DOT       1h             733          44999    1.63%
        AVAX       1h             527          40656    1.30%
        TSLA       1h               6           3473    0.17%
        DYDX       1d               7           1478    0.47%
    1000PEPE       1h             162          26373    0.61%
       GOOGL       1h               6           3473    0.17%
        AAPL       1h               7           3473    0.20%
         XRP       1h             517          43655    1.18%
         LTC       1h             470          48551    0.97%
        DYDX       1h            1716          40034    4.29%
         ETH       1h              42          45080    0.09%
         SOL       1h             186          39944    0.47%
        MSFT       1d              22           3410    0.65%
         BTC       1h             103          53590    0.19%
         ADA       1h             654          45001    1.45%
        META       1d               9           3315    0.27%

## 5. Extreme Spikes (Outliers)
Assets with flash crashes/spikes (>5 standard deviations):

asset_symbol interval  spike_candles
         LTC        W             39
         XRP        W             26
       GOOGL       1d             14
        TSLA      1wk             23
    1000PEPE       1d            116
        AVAX       1h             31
        DOGE        W             27
        MSFT       1d             14
         SOL       1h             44
         DOT        W             29
        DYDX       1h             43
        META       1h              2
        META      1wk             17
         DOT       1h             57
        DYDX        W             25
         ADA       1d            162
         BTC       1d            245
         SOL        W             13
         ETH        W             37
        AAPL       1h              1
        AAPL      1wk             20
        AMZN       1d             12
        DOGE       1d            165
        META       1d             14
         DOT       1d            166
        AAPL       1d             13
        AMZN       1h              2
        AMZN      1wk             21
        AVAX        W             20
        DOGE       1h             80
        MSFT       1h              2
        MSFT      1wk             20
         ADA        W             32
         BTC        W             48
         SOL       1d            154
         ETH       1d            188
         LTC       1h             65
         XRP       1h             63
        DYDX       1d            142
       GOOGL       1h              1
       GOOGL      1wk             23
        TSLA       1d              9
    1000PEPE       1h             42
        AVAX       1d            163
         ADA       1h             52
         BTC       1h             60
         LTC       1d            175
         ETH       1h             51
         XRP       1d            139

## 6. Timestamp & Interval Integrity
Inconsistent Interval Deltas (Time Drift):
asset_symbol interval  drift_events
        META       1h           499
        MSFT       1d           746
        AMZN       1d           746
        AAPL       1h           499
        AAPL      1wk             5
        AMZN       1h           499
        AMZN      1wk             5
        AAPL       1d           746
        META       1d           723
       GOOGL       1h           499
       GOOGL      1wk             5
        TSLA       1d           746
        MSFT       1h           499
        MSFT      1wk             5
       GOOGL       1d           746
        TSLA       1h           499
        TSLA      1wk             5

## 7. Conclusion
Data is verified for ML training.
