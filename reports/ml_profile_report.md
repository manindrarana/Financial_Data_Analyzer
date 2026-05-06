# ML Data Quality Report

Generated on: 2026-05-06 13:01:09.693023

## 1. Data Summary
asset_symbol interval  row_count          start_date            end_date
         DOT        W         70 2025-01-06 00:00:00 2026-05-04 00:00:00
        DYDX       1h      39840 2021-10-19 13:00:00 2026-05-06 12:00:00
         LTC        W         91 2024-08-12 00:00:00 2026-05-04 00:00:00
         XRP        W         62 2025-03-03 00:00:00 2026-05-04 00:00:00
        DOGE        W         59 2025-03-24 00:00:00 2026-05-04 00:00:00
       GOOGL       1d       3406 2012-10-16 00:00:00 2026-05-05 00:00:00
        TSLA       1h       3445 2024-05-13 16:30:00 2026-05-05 19:30:00
        TSLA      1wk        556 2015-10-25 00:00:00 2026-05-04 00:00:00
    1000PEPE       1d        901 2023-11-18 00:00:00 2026-05-06 00:00:00
        AVAX       1h      40462 2021-09-23 15:00:00 2026-05-06 12:00:00
        MSFT       1d       3406 2012-10-16 00:00:00 2026-05-05 00:00:00
         SOL       1h      39750 2021-10-23 07:00:00 2026-05-06 12:00:00
         ADA       1d       1677 2021-10-03 00:00:00 2026-05-06 00:00:00
         BTC       1d       2035 2020-10-10 00:00:00 2026-05-06 00:00:00
         SOL        W         40 2025-08-04 00:00:00 2026-05-04 00:00:00
         ETH       1d       1680 2021-09-30 00:00:00 2026-05-06 00:00:00
         LTC       1h      48357 2020-10-29 16:00:00 2026-05-06 12:00:00
         XRP       1h      43461 2021-05-21 16:00:00 2026-05-06 12:00:00
         DOT       1h      44805 2021-03-26 16:00:00 2026-05-06 12:00:00
        META       1h       3445 2024-05-13 16:30:00 2026-05-05 19:30:00
        META      1wk        531 2016-03-07 00:00:00 2026-05-04 00:00:00
        DYDX        W         40 2025-08-04 00:00:00 2026-05-04 00:00:00
        DOGE       1h      42980 2021-06-10 17:00:00 2026-05-06 12:00:00
        AMZN       1h       3445 2024-05-13 16:30:00 2026-05-05 19:30:00
        AMZN      1wk        556 2015-10-25 00:00:00 2026-05-04 00:00:00
        AVAX        W         44 2025-07-07 00:00:00 2026-05-04 00:00:00
        AAPL       1d       3406 2012-10-16 00:00:00 2026-05-05 00:00:00
        DYDX       1d       1470 2022-04-28 00:00:00 2026-05-06 00:00:00
         BTC        W        121 2024-01-15 00:00:00 2026-05-04 00:00:00
        MSFT       1h       3445 2024-05-13 16:30:00 2026-05-05 19:30:00
        MSFT      1wk        556 2015-10-25 00:00:00 2026-05-04 00:00:00
         ADA        W         70 2025-01-06 00:00:00 2026-05-04 00:00:00
         SOL       1d       1466 2022-05-02 00:00:00 2026-05-06 00:00:00
         ETH       1h      44886 2021-03-23 07:00:00 2026-05-06 12:00:00
         LTC       1d       1825 2021-05-08 00:00:00 2026-05-06 00:00:00
         XRP       1d       1621 2021-11-28 00:00:00 2026-05-06 00:00:00
         DOT       1d       1677 2021-10-03 00:00:00 2026-05-06 00:00:00
        META       1d       3311 2013-03-07 00:00:00 2026-05-05 00:00:00
       GOOGL       1h       3445 2024-05-13 16:30:00 2026-05-05 19:30:00
       GOOGL      1wk        556 2015-10-25 00:00:00 2026-05-04 00:00:00
        TSLA       1d       3406 2012-10-16 00:00:00 2026-05-05 00:00:00
    1000PEPE       1h      26179 2023-05-11 18:00:00 2026-05-06 12:00:00
        AVAX       1d       1496 2022-04-02 00:00:00 2026-05-06 00:00:00
         ETH        W         70 2025-01-06 00:00:00 2026-05-04 00:00:00
         BTC       1h      53396 2020-04-02 17:00:00 2026-05-06 12:00:00
         ADA       1h      44807 2021-03-26 14:00:00 2026-05-06 12:00:00
        DOGE       1d       1601 2021-12-18 00:00:00 2026-05-06 00:00:00
        AAPL       1h       3445 2024-05-13 16:30:00 2026-05-05 19:30:00
        AAPL      1wk        556 2015-10-25 00:00:00 2026-05-04 00:00:00
        AMZN       1d       3406 2012-10-16 00:00:00 2026-05-05 00:00:00

## 2. Missing Values (NaNs)
Status: Perfect (0 Nulls found)

## 3. Data Gaps
Note: Stock market data (1h/1d) correctly shows gaps for weekends.

Asset Interval  Expected  Actual  Gaps  Gap_%
 META       1h     17332    3445 13887 80.12%
 MSFT       1d      4950    3406  1544 31.19%
 AAPL       1h     17332    3445 13887 80.12%
 AMZN       1d      4950    3406  1544 31.19%
 AMZN       1h     17332    3445 13887 80.12%
 AAPL       1d      4950    3406  1544 31.19%
 META       1d      4808    3311  1497 31.14%
GOOGL       1h     17332    3445 13887 80.12%
 TSLA       1d      4950    3406  1544 31.19%
 MSFT       1h     17332    3445 13887 80.12%
GOOGL       1d      4950    3406  1544 31.19%
 TSLA       1h     17332    3445 13887 80.12%

## 4. Frozen Prices 
Assets with excessive repeated prices (>5 rows):

asset_symbol interval  frozen_candles  total_candles Frozen_%
        DOGE       1h             996          42980    2.32%
        AMZN       1h               7           3445    0.20%
        AMZN      1wk               6            556    1.08%
        AAPL       1d               7           3406    0.21%
         SOL       1h             181          39750    0.46%
        MSFT       1d              22           3406    0.65%
        DYDX       1d               7           1470    0.48%
         DOT       1h             733          44805    1.64%
        DYDX       1h            1716          39840    4.31%
         ETH       1h              41          44886    0.09%
        META       1d               9           3311    0.27%
       GOOGL       1h               6           3445    0.17%
       GOOGL      1wk               6            556    1.08%
    1000PEPE       1h             158          26179    0.60%
         ADA       1h             652          44807    1.46%
         BTC       1h             103          53396    0.19%
        AAPL       1h               7           3445    0.20%
        AAPL      1wk               6            556    1.08%
         XRP       1h             517          43461    1.19%
         LTC       1h             469          48357    0.97%
        MSFT      1wk               6            556    1.08%
        AVAX       1h             524          40462    1.30%
        TSLA       1h               6           3445    0.17%
        TSLA      1wk               6            556    1.08%

## 5. Extreme Spikes (Outliers)
Assets with flash crashes/spikes (>5 standard deviations):

asset_symbol interval  spike_candles
         LTC        W             38
         XRP        W             26
         ETH       1d            188
         LTC       1h             65
         XRP       1h             63
       GOOGL       1d             14
        TSLA      1wk             23
        DOGE        W             27
    1000PEPE       1d            116
        AVAX       1h             31
        META       1h              2
        META      1wk             18
        DYDX        W             22
         DOT       1h             57
        META       1d             14
         DOT       1d            166
        MSFT       1h              2
        MSFT      1wk             19
         SOL       1d            154
         BTC        W             48
         ADA        W             32
         ETH        W             37
         DOT        W             29
        DYDX       1h             43
        AAPL       1h              1
        AAPL      1wk             20
        AMZN       1d             12
        DOGE       1d            164
         LTC       1d            175
         ETH       1h             51
         XRP       1d            139
         BTC       1h             59
         ADA       1h             50
       GOOGL       1h              1
       GOOGL      1wk             23
        TSLA       1d              9
    1000PEPE       1h             42
        AVAX       1d            163
        AMZN       1h              2
        AMZN      1wk             22
        AAPL       1d             13
        DOGE       1h             79
        AVAX        W             19
        MSFT       1d             14
         SOL       1h             44
         SOL        W             12
         ADA       1d            162
         BTC       1d            245
        DYDX       1d            142

## 6. Timestamp & Interval Integrity
Inconsistent Interval Deltas (Time Drift):
asset_symbol interval  drift_events
        AMZN       1h           495
        AMZN      1wk             5
        AAPL       1d           745
        TSLA       1h           495
        TSLA      1wk             5
       GOOGL       1d           745
        MSFT       1h           495
        MSFT      1wk             5
        META       1d           722
        AMZN       1d           745
        AAPL       1h           495
        AAPL      1wk             5
        META       1h           495
        MSFT       1d           745
        TSLA       1d           745
       GOOGL       1h           495
       GOOGL      1wk             5

## 7. Conclusion
Data is verified for ML training.
