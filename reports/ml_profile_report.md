# ML Data Quality Report

Generated on: 2026-05-13 12:00:57.342065

## 1. Data Summary
asset_symbol interval  row_count          start_date            end_date
         LTC        W         92 2024-08-12 00:00:00 2026-05-11 00:00:00
         XRP        W         63 2025-03-03 00:00:00 2026-05-11 00:00:00
        DOGE        W         60 2025-03-24 00:00:00 2026-05-11 00:00:00
    1000PEPE       1d        908 2023-11-18 00:00:00 2026-05-13 00:00:00
        AVAX       1h      40629 2021-09-23 15:00:00 2026-05-13 11:00:00
       GOOGL       1d       3410 2012-10-16 00:00:00 2026-05-11 00:00:00
        TSLA       1h       3473 2024-05-13 16:30:00 2026-05-11 19:30:00
        TSLA      1wk        557 2015-10-25 00:00:00 2026-05-11 00:00:00
         DOT       1h      44972 2021-03-26 16:00:00 2026-05-13 11:00:00
        DYDX        W         41 2025-08-04 00:00:00 2026-05-11 00:00:00
        META       1h       3473 2024-05-13 16:30:00 2026-05-11 19:30:00
        META      1wk        532 2016-03-07 00:00:00 2026-05-11 00:00:00
        DOGE       1d       1608 2021-12-18 00:00:00 2026-05-13 00:00:00
        AAPL       1h       3473 2024-05-13 16:30:00 2026-05-11 19:30:00
        AAPL      1wk        557 2015-10-25 00:00:00 2026-05-11 00:00:00
        AMZN       1d       3410 2012-10-16 00:00:00 2026-05-11 00:00:00
         ETH        W         71 2025-01-06 00:00:00 2026-05-11 00:00:00
         ETH       1d       1687 2021-09-30 00:00:00 2026-05-13 00:00:00
         LTC       1h      48524 2020-10-29 16:00:00 2026-05-13 11:00:00
         XRP       1h      43628 2021-05-21 16:00:00 2026-05-13 11:00:00
        DYDX       1d       1477 2022-04-28 00:00:00 2026-05-13 00:00:00
         ETH       1h      45053 2021-03-23 07:00:00 2026-05-13 11:00:00
         LTC       1d       1832 2021-05-08 00:00:00 2026-05-13 00:00:00
         XRP       1d       1628 2021-11-28 00:00:00 2026-05-13 00:00:00
         DOT       1d       1684 2021-10-03 00:00:00 2026-05-13 00:00:00
        META       1d       3315 2013-03-07 00:00:00 2026-05-11 00:00:00
         BTC       1h      53563 2020-04-02 17:00:00 2026-05-13 11:00:00
         ADA       1h      44974 2021-03-26 14:00:00 2026-05-13 11:00:00
        DOGE       1h      43147 2021-06-10 17:00:00 2026-05-13 11:00:00
        AVAX        W         45 2025-07-07 00:00:00 2026-05-11 00:00:00
        AAPL       1d       3410 2012-10-16 00:00:00 2026-05-11 00:00:00
        AMZN       1h       3473 2024-05-13 16:30:00 2026-05-11 19:30:00
        AMZN      1wk        557 2015-10-25 00:00:00 2026-05-11 00:00:00
        MSFT       1d       3410 2012-10-16 00:00:00 2026-05-11 00:00:00
         SOL       1h      39917 2021-10-23 07:00:00 2026-05-13 11:00:00
    1000PEPE       1h      26346 2023-05-11 18:00:00 2026-05-13 11:00:00
        AVAX       1d       1503 2022-04-02 00:00:00 2026-05-13 00:00:00
       GOOGL       1h       3473 2024-05-13 16:30:00 2026-05-11 19:30:00
       GOOGL      1wk        557 2015-10-25 00:00:00 2026-05-11 00:00:00
        TSLA       1d       3410 2012-10-16 00:00:00 2026-05-11 00:00:00
         DOT        W         71 2025-01-06 00:00:00 2026-05-11 00:00:00
        DYDX       1h      40007 2021-10-19 13:00:00 2026-05-13 11:00:00
         ADA       1d       1684 2021-10-03 00:00:00 2026-05-13 00:00:00
         BTC       1d       2042 2020-10-10 00:00:00 2026-05-13 00:00:00
         SOL        W         41 2025-08-04 00:00:00 2026-05-11 00:00:00
         BTC        W        122 2024-01-15 00:00:00 2026-05-11 00:00:00
         ADA        W         71 2025-01-06 00:00:00 2026-05-11 00:00:00
        MSFT       1h       3473 2024-05-13 16:30:00 2026-05-11 19:30:00
        MSFT      1wk        557 2015-10-25 00:00:00 2026-05-11 00:00:00
         SOL       1d       1473 2022-05-02 00:00:00 2026-05-13 00:00:00

## 2. Missing Values (NaNs)
Status: Perfect (0 Nulls found)

## 3. Data Gaps
Note: Stock market data (1h/1d) correctly shows gaps for weekends.

Asset Interval  Expected  Actual  Gaps  Gap_%
 AAPL       1d      4956    3410  1546 31.19%
 AMZN       1h     17476    3473 14003 80.13%
 MSFT       1h     17476    3473 14003 80.13%
GOOGL       1d      4956    3410  1546 31.19%
 TSLA       1h     17476    3473 14003 80.13%
 META       1d      4814    3315  1499 31.14%
 MSFT       1d      4956    3410  1546 31.19%
 META       1h     17476    3473 14003 80.13%
 AAPL       1h     17476    3473 14003 80.13%
 AMZN       1d      4956    3410  1546 31.19%
GOOGL       1h     17476    3473 14003 80.13%
 TSLA       1d      4956    3410  1546 31.19%

## 4. Frozen Prices 
Assets with excessive repeated prices (>5 rows):

asset_symbol interval  frozen_candles  total_candles Frozen_%
        DYDX       1d               7           1477    0.47%
         SOL       1h             184          39917    0.46%
        MSFT       1d              22           3410    0.65%
        MSFT      1wk               6            557    1.08%
         DOT       1h             733          44972    1.63%
        DOGE       1h             998          43147    2.31%
        AAPL       1d               7           3410    0.21%
        AMZN       1h               7           3473    0.20%
        AMZN      1wk               6            557    1.08%
         ETH       1h              42          45053    0.09%
        DYDX       1h            1716          40007    4.29%
         ADA       1h             657          44974    1.46%
         BTC       1h             103          53563    0.19%
        META       1d               9           3315    0.27%
         LTC       1h             470          48524    0.97%
         XRP       1h             517          43628    1.19%
       GOOGL       1h               6           3473    0.17%
       GOOGL      1wk               6            557    1.08%
    1000PEPE       1h             162          26346    0.61%
        AAPL       1h               7           3473    0.20%
        AAPL      1wk               6            557    1.08%
        AVAX       1h             525          40629    1.29%
        TSLA       1h               6           3473    0.17%
        TSLA      1wk               6            557    1.08%

## 5. Extreme Spikes (Outliers)
Assets with flash crashes/spikes (>5 standard deviations):

asset_symbol interval  spike_candles
         LTC        W             38
         XRP        W             26
        MSFT       1d             14
         SOL       1h             44
         SOL        W             12
         ADA       1d            162
         BTC       1d            245
        AAPL       1d             13
        AMZN       1h              2
        AMZN      1wk             22
        AVAX        W             19
        DOGE       1h             79
        META       1h              2
        META      1wk             18
         DOT       1h             57
        DYDX        W             22
        MSFT       1h              2
        MSFT      1wk             20
         SOL       1d            155
         ADA        W             32
         BTC        W             48
        DYDX       1d            143
         LTC       1d            175
         ETH       1h             51
         XRP       1d            139
         ETH        W             37
       GOOGL       1h              1
       GOOGL      1wk             23
        TSLA       1d              9
    1000PEPE       1h             42
        AVAX       1d            163
         ETH       1d            188
         LTC       1h             65
         XRP       1h             63
        META       1d             14
         DOT       1d            166
         ADA       1h             52
         BTC       1h             60
       GOOGL       1d             14
        TSLA      1wk             23
    1000PEPE       1d            116
        AVAX       1h             31
        DOGE        W             27
        AAPL       1h              1
        AAPL      1wk             20
        AMZN       1d             12
        DOGE       1d            165
         DOT        W             29
        DYDX       1h             44

## 6. Timestamp & Interval Integrity
Inconsistent Interval Deltas (Time Drift):
asset_symbol interval  drift_events
        META       1h           499
        MSFT       1d           746
        TSLA       1h           499
        TSLA      1wk             5
       GOOGL       1d           746
        AMZN       1h           499
        AMZN      1wk             5
        AAPL       1d           746
       GOOGL       1h           499
       GOOGL      1wk             5
        TSLA       1d           746
        AAPL       1h           499
        AAPL      1wk             5
        AMZN       1d           746
        MSFT       1h           499
        MSFT      1wk             5
        META       1d           723

## 7. Conclusion
Data is verified for ML training.
