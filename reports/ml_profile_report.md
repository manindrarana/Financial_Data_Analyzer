# ML Data Quality Report

Generated on: 2026-05-08 11:11:17.974313

## 1. Data Summary
asset_symbol interval  row_count          start_date            end_date
         SOL       1h      39797 2021-10-23 07:00:00 2026-05-08 11:00:00
        MSFT       1d       3406 2012-10-16 00:00:00 2026-05-05 00:00:00
         LTC        W         91 2024-08-12 00:00:00 2026-05-04 00:00:00
         XRP        W         62 2025-03-03 00:00:00 2026-05-04 00:00:00
        DOGE        W         59 2025-03-24 00:00:00 2026-05-04 00:00:00
    1000PEPE       1d        903 2023-11-18 00:00:00 2026-05-08 00:00:00
        AVAX       1h      40509 2021-09-23 15:00:00 2026-05-08 11:00:00
       GOOGL       1d       3406 2012-10-16 00:00:00 2026-05-05 00:00:00
        TSLA       1h       3445 2024-05-13 16:30:00 2026-05-05 19:30:00
        TSLA      1wk        556 2015-10-25 00:00:00 2026-05-04 00:00:00
         ETH       1d       1682 2021-09-30 00:00:00 2026-05-08 00:00:00
         LTC       1h      48404 2020-10-29 16:00:00 2026-05-08 11:00:00
         XRP       1h      43508 2021-05-21 16:00:00 2026-05-08 11:00:00
         DOT       1h      44852 2021-03-26 16:00:00 2026-05-08 11:00:00
        DYDX        W         40 2025-08-04 00:00:00 2026-05-04 00:00:00
        META       1h       3445 2024-05-13 16:30:00 2026-05-05 19:30:00
        META      1wk        531 2016-03-07 00:00:00 2026-05-04 00:00:00
         SOL        W         40 2025-08-04 00:00:00 2026-05-04 00:00:00
         ADA       1d       1679 2021-10-03 00:00:00 2026-05-08 00:00:00
         BTC       1d       2037 2020-10-10 00:00:00 2026-05-08 00:00:00
        DOGE       1d       1603 2021-12-18 00:00:00 2026-05-08 00:00:00
        AAPL       1h       3445 2024-05-13 16:30:00 2026-05-05 19:30:00
        AAPL      1wk        556 2015-10-25 00:00:00 2026-05-04 00:00:00
        AMZN       1d       3406 2012-10-16 00:00:00 2026-05-05 00:00:00
        DOGE       1h      43027 2021-06-10 17:00:00 2026-05-08 11:00:00
        AAPL       1d       3406 2012-10-16 00:00:00 2026-05-05 00:00:00
        AVAX        W         44 2025-07-07 00:00:00 2026-05-04 00:00:00
        AMZN       1h       3445 2024-05-13 16:30:00 2026-05-05 19:30:00
        AMZN      1wk        556 2015-10-25 00:00:00 2026-05-04 00:00:00
         ETH        W         70 2025-01-06 00:00:00 2026-05-04 00:00:00
        DYDX       1d       1472 2022-04-28 00:00:00 2026-05-08 00:00:00
         ETH       1h      44933 2021-03-23 07:00:00 2026-05-08 11:00:00
         LTC       1d       1827 2021-05-08 00:00:00 2026-05-08 00:00:00
         XRP       1d       1623 2021-11-28 00:00:00 2026-05-08 00:00:00
         BTC       1h      53443 2020-04-02 17:00:00 2026-05-08 11:00:00
         ADA       1h      44854 2021-03-26 14:00:00 2026-05-08 11:00:00
         DOT       1d       1679 2021-10-03 00:00:00 2026-05-08 00:00:00
        META       1d       3311 2013-03-07 00:00:00 2026-05-05 00:00:00
    1000PEPE       1h      26226 2023-05-11 18:00:00 2026-05-08 11:00:00
        AVAX       1d       1498 2022-04-02 00:00:00 2026-05-08 00:00:00
       GOOGL       1h       3445 2024-05-13 16:30:00 2026-05-05 19:30:00
       GOOGL      1wk        556 2015-10-25 00:00:00 2026-05-04 00:00:00
        TSLA       1d       3406 2012-10-16 00:00:00 2026-05-05 00:00:00
         BTC        W        121 2024-01-15 00:00:00 2026-05-04 00:00:00
         SOL       1d       1468 2022-05-02 00:00:00 2026-05-08 00:00:00
         ADA        W         70 2025-01-06 00:00:00 2026-05-04 00:00:00
        MSFT       1h       3445 2024-05-13 16:30:00 2026-05-05 19:30:00
        MSFT      1wk        556 2015-10-25 00:00:00 2026-05-04 00:00:00
         DOT        W         70 2025-01-06 00:00:00 2026-05-04 00:00:00
        DYDX       1h      39887 2021-10-19 13:00:00 2026-05-08 11:00:00

## 2. Missing Values (NaNs)
Status: Perfect (0 Nulls found)

## 3. Data Gaps
Note: Stock market data (1h/1d) correctly shows gaps for weekends.

Asset Interval  Expected  Actual  Gaps  Gap_%
 AMZN       1h     17332    3445 13887 80.12%
 AAPL       1d      4950    3406  1544 31.19%
 META       1h     17332    3445 13887 80.12%
 MSFT       1d      4950    3406  1544 31.19%
 META       1d      4808    3311  1497 31.14%
GOOGL       1h     17332    3445 13887 80.12%
 TSLA       1d      4950    3406  1544 31.19%
 AAPL       1h     17332    3445 13887 80.12%
 AMZN       1d      4950    3406  1544 31.19%
GOOGL       1d      4950    3406  1544 31.19%
 TSLA       1h     17332    3445 13887 80.12%
 MSFT       1h     17332    3445 13887 80.12%

## 4. Frozen Prices 
Assets with excessive repeated prices (>5 rows):

asset_symbol interval  frozen_candles  total_candles Frozen_%
        AVAX       1h             524          40509    1.29%
        TSLA       1h               6           3445    0.17%
        TSLA      1wk               6            556    1.08%
        META       1d               9           3311    0.27%
        DYDX       1d               7           1472    0.48%
         DOT       1h             733          44852    1.63%
         LTC       1h             470          48404    0.97%
         XRP       1h             517          43508    1.19%
        DYDX       1h            1716          39887    4.30%
         ADA       1h             652          44854    1.45%
         BTC       1h             103          53443    0.19%
        AAPL       1h               7           3445    0.20%
        AAPL      1wk               6            556    1.08%
        MSFT       1d              22           3406    0.65%
         SOL       1h             181          39797    0.45%
        MSFT      1wk               6            556    1.08%
         ETH       1h              42          44933    0.09%
       GOOGL       1h               6           3445    0.17%
       GOOGL      1wk               6            556    1.08%
    1000PEPE       1h             159          26226    0.61%
        AMZN       1h               7           3445    0.20%
        AMZN      1wk               6            556    1.08%
        DOGE       1h             997          43027    2.32%
        AAPL       1d               7           3406    0.21%

## 5. Extreme Spikes (Outliers)
Assets with flash crashes/spikes (>5 standard deviations):

asset_symbol interval  spike_candles
         DOT        W             29
        DYDX       1h             43
        MSFT       1d             14
         SOL       1h             44
         ADA       1d            162
         BTC       1d            245
         SOL        W             12
         LTC        W             38
         XRP        W             26
         BTC       1h             59
         ADA       1h             50
        AMZN       1h              2
        AMZN      1wk             22
        AVAX        W             19
        DOGE       1h             79
        AAPL       1d             13
         XRP       1d            139
         ETH       1h             51
         LTC       1d            175
        AAPL       1h              1
        AAPL      1wk             20
        AMZN       1d             12
        DOGE       1d            165
        MSFT       1h              2
        MSFT      1wk             19
         ADA        W             32
         BTC        W             48
         SOL       1d            154
         XRP       1h             63
         LTC       1h             65
         ETH       1d            188
        META       1h              2
        META      1wk             18
         DOT       1h             57
        DYDX        W             22
       GOOGL       1d             14
        TSLA      1wk             23
    1000PEPE       1d            116
        AVAX       1h             31
        DOGE        W             27
        DYDX       1d            143
        META       1d             14
         DOT       1d            166
         ETH        W             37
       GOOGL       1h              1
       GOOGL      1wk             23
        TSLA       1d              9
    1000PEPE       1h             42
        AVAX       1d            163

## 6. Timestamp & Interval Integrity
Inconsistent Interval Deltas (Time Drift):
asset_symbol interval  drift_events
        MSFT       1d           745
        AMZN       1h           495
        AMZN      1wk             5
        AAPL       1d           745
        TSLA       1h           495
        TSLA      1wk             5
       GOOGL       1d           745
        META       1h           495
        AAPL       1h           495
        AAPL      1wk             5
        AMZN       1d           745
        META       1d           722
        TSLA       1d           745
       GOOGL       1h           495
       GOOGL      1wk             5
        MSFT       1h           495
        MSFT      1wk             5

## 7. Conclusion
Data is verified for ML training.
