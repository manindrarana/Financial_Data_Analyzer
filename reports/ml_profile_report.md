# ML Data Quality Report

Generated on: 2026-05-09 14:05:22.508851

## 1. Data Summary
asset_symbol interval  row_count          start_date            end_date
         DOT        W         70 2025-01-06 00:00:00 2026-05-04 00:00:00
        DYDX       1h      39914 2021-10-19 13:00:00 2026-05-09 14:00:00
         ADA       1d       1680 2021-10-03 00:00:00 2026-05-09 00:00:00
         BTC       1d       2038 2020-10-10 00:00:00 2026-05-09 00:00:00
         SOL        W         40 2025-08-04 00:00:00 2026-05-04 00:00:00
        AMZN       1h       3445 2024-05-13 16:30:00 2026-05-05 19:30:00
        AMZN      1wk        556 2015-10-25 00:00:00 2026-05-04 00:00:00
        AVAX        W         44 2025-07-07 00:00:00 2026-05-04 00:00:00
        DOGE       1h      43054 2021-06-10 17:00:00 2026-05-09 14:00:00
        AAPL       1d       3406 2012-10-16 00:00:00 2026-05-05 00:00:00
         LTC        W         91 2024-08-12 00:00:00 2026-05-04 00:00:00
         XRP        W         62 2025-03-03 00:00:00 2026-05-04 00:00:00
        MSFT       1d       3406 2012-10-16 00:00:00 2026-05-05 00:00:00
         SOL       1h      39824 2021-10-23 07:00:00 2026-05-09 14:00:00
       GOOGL       1d       3406 2012-10-16 00:00:00 2026-05-05 00:00:00
        TSLA       1h       3445 2024-05-13 16:30:00 2026-05-05 19:30:00
        TSLA      1wk        556 2015-10-25 00:00:00 2026-05-04 00:00:00
    1000PEPE       1d        904 2023-11-18 00:00:00 2026-05-09 00:00:00
        AVAX       1h      40536 2021-09-23 15:00:00 2026-05-09 14:00:00
        DOGE        W         59 2025-03-24 00:00:00 2026-05-04 00:00:00
         ETH       1d       1683 2021-09-30 00:00:00 2026-05-09 00:00:00
         LTC       1h      48404 2020-10-29 16:00:00 2026-05-08 11:00:00
         XRP       1h      43535 2021-05-21 16:00:00 2026-05-09 14:00:00
         ETH        W         70 2025-01-06 00:00:00 2026-05-04 00:00:00
        META       1h       3445 2024-05-13 16:30:00 2026-05-05 19:30:00
        META      1wk        531 2016-03-07 00:00:00 2026-05-04 00:00:00
         DOT       1h      44879 2021-03-26 16:00:00 2026-05-09 14:00:00
        DYDX        W         40 2025-08-04 00:00:00 2026-05-04 00:00:00
        META       1d       3311 2013-03-07 00:00:00 2026-05-05 00:00:00
         DOT       1d       1680 2021-10-03 00:00:00 2026-05-09 00:00:00
         ETH       1h      44960 2021-03-23 07:00:00 2026-05-09 14:00:00
         LTC       1d       1828 2021-05-08 00:00:00 2026-05-09 00:00:00
         XRP       1d       1624 2021-11-28 00:00:00 2026-05-09 00:00:00
         ADA       1h      44881 2021-03-26 14:00:00 2026-05-09 14:00:00
         BTC       1h      53470 2020-04-02 17:00:00 2026-05-09 14:00:00
        MSFT       1h       3445 2024-05-13 16:30:00 2026-05-05 19:30:00
        MSFT      1wk        556 2015-10-25 00:00:00 2026-05-04 00:00:00
         ADA        W         70 2025-01-06 00:00:00 2026-05-04 00:00:00
         BTC        W        121 2024-01-15 00:00:00 2026-05-04 00:00:00
         SOL       1d       1469 2022-05-02 00:00:00 2026-05-09 00:00:00
       GOOGL       1h       3445 2024-05-13 16:30:00 2026-05-05 19:30:00
       GOOGL      1wk        556 2015-10-25 00:00:00 2026-05-04 00:00:00
        TSLA       1d       3406 2012-10-16 00:00:00 2026-05-05 00:00:00
    1000PEPE       1h      26253 2023-05-11 18:00:00 2026-05-09 14:00:00
        AVAX       1d       1499 2022-04-02 00:00:00 2026-05-09 00:00:00
        DYDX       1d       1473 2022-04-28 00:00:00 2026-05-09 00:00:00
        AAPL       1h       3445 2024-05-13 16:30:00 2026-05-05 19:30:00
        AAPL      1wk        556 2015-10-25 00:00:00 2026-05-04 00:00:00
        AMZN       1d       3406 2012-10-16 00:00:00 2026-05-05 00:00:00
        DOGE       1d       1604 2021-12-18 00:00:00 2026-05-09 00:00:00

## 2. Missing Values (NaNs)
Status: Perfect (0 Nulls found)

## 3. Data Gaps
Note: Stock market data (1h/1d) correctly shows gaps for weekends.

Asset Interval  Expected  Actual  Gaps  Gap_%
 AMZN       1h     17332    3445 13887 80.12%
 AAPL       1d      4950    3406  1544 31.19%
 META       1h     17332    3445 13887 80.12%
 META       1d      4808    3311  1497 31.14%
 AAPL       1h     17332    3445 13887 80.12%
 AMZN       1d      4950    3406  1544 31.19%
GOOGL       1d      4950    3406  1544 31.19%
 TSLA       1h     17332    3445 13887 80.12%
GOOGL       1h     17332    3445 13887 80.12%
 TSLA       1d      4950    3406  1544 31.19%
 MSFT       1h     17332    3445 13887 80.12%
 MSFT       1d      4950    3406  1544 31.19%

## 4. Frozen Prices 
Assets with excessive repeated prices (>5 rows):

asset_symbol interval  frozen_candles  total_candles Frozen_%
         DOT       1h             733          44879    1.63%
         ETH       1h              42          44960    0.09%
        AAPL       1h               7           3445    0.20%
        AAPL      1wk               6            556    1.08%
        META       1d               9           3311    0.27%
        AVAX       1h             524          40536    1.29%
        TSLA       1h               6           3445    0.17%
        TSLA      1wk               6            556    1.08%
    1000PEPE       1h             160          26253    0.61%
       GOOGL       1h               6           3445    0.17%
       GOOGL      1wk               6            556    1.08%
         BTC       1h             103          53470    0.19%
         ADA       1h             655          44881    1.46%
        DYDX       1d               7           1473    0.48%
         SOL       1h             183          39824    0.46%
        MSFT       1d              22           3406    0.65%
         LTC       1h             470          48404    0.97%
         XRP       1h             517          43535    1.19%
        DYDX       1h            1716          39914    4.30%
        DOGE       1h             997          43054    2.32%
        AAPL       1d               7           3406    0.21%
        AMZN       1h               7           3445    0.20%
        AMZN      1wk               6            556    1.08%
        MSFT      1wk               6            556    1.08%

## 5. Extreme Spikes (Outliers)
Assets with flash crashes/spikes (>5 standard deviations):

asset_symbol interval  spike_candles
         DOT        W             29
        DYDX       1h             43
         LTC        W             38
         XRP        W             26
         XRP       1h             63
         LTC       1h             65
         ETH       1d            188
        MSFT       1d             14
         SOL       1h             44
       GOOGL       1d             14
        TSLA      1wk             23
        DOGE        W             27
    1000PEPE       1d            116
        AVAX       1h             31
        DYDX       1d            143
         XRP       1d            139
         ETH       1h             51
         LTC       1d            175
        MSFT       1h              2
        MSFT      1wk             19
         BTC        W             48
         SOL       1d            154
         ADA        W             32
         SOL        W             12
         ADA       1d            162
         BTC       1d            245
       GOOGL       1h              1
       GOOGL      1wk             23
        TSLA       1d              9
    1000PEPE       1h             42
        AVAX       1d            163
        META       1h              2
        META      1wk             18
         DOT       1h             57
        DYDX        W             22
        AAPL       1h              1
        AAPL      1wk             20
        AMZN       1d             12
        DOGE       1d            165
        META       1d             14
         DOT       1d            166
        AMZN       1h              2
        AMZN      1wk             22
        DOGE       1h             79
        AAPL       1d             13
        AVAX        W             19
         ETH        W             37
         BTC       1h             60
         ADA       1h             51

## 6. Timestamp & Interval Integrity
Inconsistent Interval Deltas (Time Drift):
asset_symbol interval  drift_events
        AMZN       1h           495
        AMZN      1wk             5
        AAPL       1d           745
        MSFT       1d           745
        MSFT       1h           495
        MSFT      1wk             5
       GOOGL       1d           745
        TSLA       1h           495
        TSLA      1wk             5
        META       1d           722
        META       1h           495
       GOOGL       1h           495
       GOOGL      1wk             5
        TSLA       1d           745
        AAPL       1h           495
        AAPL      1wk             5
        AMZN       1d           745

## 7. Conclusion
Data is verified for ML training.
