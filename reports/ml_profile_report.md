# ML Data Quality Report

Generated on: 2026-04-08 19:45:21.394452

## 1. Data Summary
asset_symbol interval  row_count          start_date            end_date
        MSFT       1d       3384 2012-10-16 00:00:00 2026-04-02 00:00:00
         SOL       1h      39085 2021-10-23 07:00:00 2026-04-08 19:00:00
         LTC        W         87 2024-08-12 00:00:00 2026-04-06 00:00:00
         XRP        W         58 2025-03-03 00:00:00 2026-04-06 00:00:00
         ADA       1d       1649 2021-10-03 00:00:00 2026-04-08 00:00:00
         BTC       1d       2007 2020-10-10 00:00:00 2026-04-08 00:00:00
         SOL        W         36 2025-08-04 00:00:00 2026-04-06 00:00:00
        DOGE       1d       1573 2021-12-18 00:00:00 2026-04-08 00:00:00
        AAPL       1h       3291 2024-05-13 16:30:00 2026-04-02 19:30:00
        AAPL      1wk        546 2015-10-25 00:00:00 2026-03-30 00:00:00
        AMZN       1d       3384 2012-10-16 00:00:00 2026-04-02 00:00:00
        META       1h       3291 2024-05-13 16:30:00 2026-04-02 19:30:00
        META      1wk        526 2016-03-07 00:00:00 2026-03-30 00:00:00
         DOT       1h      44140 2021-03-26 16:00:00 2026-04-08 19:00:00
        DYDX        W         36 2025-08-04 00:00:00 2026-04-06 00:00:00
         DOT        W         66 2025-01-06 00:00:00 2026-04-06 00:00:00
        DYDX       1h      39175 2021-10-19 13:00:00 2026-04-08 19:00:00
       GOOGL       1d       3384 2012-10-16 00:00:00 2026-04-02 00:00:00
        TSLA       1h       3291 2024-05-13 16:30:00 2026-04-02 19:30:00
        TSLA      1wk        546 2015-10-25 00:00:00 2026-03-30 00:00:00
        DOGE        W         55 2025-03-24 00:00:00 2026-04-06 00:00:00
    1000PEPE       1d        873 2023-11-18 00:00:00 2026-04-08 00:00:00
        AVAX       1h      39797 2021-09-23 15:00:00 2026-04-08 19:00:00
        AMZN       1h       3291 2024-05-13 16:30:00 2026-04-02 19:30:00
        AMZN      1wk        546 2015-10-25 00:00:00 2026-03-30 00:00:00
        DOGE       1h      42315 2021-06-10 17:00:00 2026-04-08 19:00:00
        AVAX        W         40 2025-07-07 00:00:00 2026-04-06 00:00:00
        AAPL       1d       3384 2012-10-16 00:00:00 2026-04-02 00:00:00
        META       1d       3289 2013-03-07 00:00:00 2026-04-02 00:00:00
         DOT       1d       1649 2021-10-03 00:00:00 2026-04-08 00:00:00
         ETH       1d       1652 2021-09-30 00:00:00 2026-04-08 00:00:00
         LTC       1h      47692 2020-10-29 16:00:00 2026-04-08 19:00:00
         XRP       1h      42796 2021-05-21 16:00:00 2026-04-08 19:00:00
       GOOGL       1h       3291 2024-05-13 16:30:00 2026-04-02 19:30:00
       GOOGL      1wk        546 2015-10-25 00:00:00 2026-03-30 00:00:00
        TSLA       1d       3384 2012-10-16 00:00:00 2026-04-02 00:00:00
    1000PEPE       1h      25514 2023-05-11 18:00:00 2026-04-08 19:00:00
        AVAX       1d       1468 2022-04-02 00:00:00 2026-04-08 00:00:00
         BTC       1h      52731 2020-04-02 17:00:00 2026-04-08 19:00:00
         ADA       1h      44142 2021-03-26 14:00:00 2026-04-08 19:00:00
        DYDX       1d       1442 2022-04-28 00:00:00 2026-04-08 00:00:00
         ETH        W         66 2025-01-06 00:00:00 2026-04-06 00:00:00
         ETH       1h      44221 2021-03-23 07:00:00 2026-04-08 19:00:00
         LTC       1d       1797 2021-05-08 00:00:00 2026-04-08 00:00:00
         XRP       1d       1593 2021-11-28 00:00:00 2026-04-08 00:00:00
        MSFT       1h       3291 2024-05-13 16:30:00 2026-04-02 19:30:00
        MSFT      1wk        546 2015-10-25 00:00:00 2026-03-30 00:00:00
         BTC        W        117 2024-01-15 00:00:00 2026-04-06 00:00:00
         ADA        W         66 2025-01-06 00:00:00 2026-04-06 00:00:00
         SOL       1d       1438 2022-05-02 00:00:00 2026-04-08 00:00:00

## 2. Missing Values (NaNs)
Status: Perfect (0 Nulls found)

## 3. Data Gaps
Note: Stock market data (1h/1d) correctly shows gaps for weekends.

Asset Interval  Expected  Actual  Gaps  Gap_%
GOOGL       1d      4917    3384  1533 31.18%
 TSLA       1h     16540    3291 13249 80.10%
 MSFT       1d      4917    3384  1533 31.18%
 META       1h     16540    3291 13249 80.10%
 MSFT       1h     16540    3291 13249 80.10%
 META       1d      4775    3289  1486 31.12%
 AAPL       1h     16540    3291 13249 80.10%
 AMZN       1d      4917    3384  1533 31.18%
 AMZN       1h     16540    3291 13249 80.10%
 AAPL       1d      4917    3384  1533 31.18%
GOOGL       1h     16540    3291 13249 80.10%
 TSLA       1d      4917    3384  1533 31.18%

## 4. Frozen Prices 
Assets with excessive repeated prices (>5 rows):

asset_symbol interval  frozen_candles  total_candles Frozen_%
        AMZN       1h               7           3291    0.21%
        DOGE       1h             990          42315    2.34%
        AAPL       1d               7           3384    0.21%
        DYDX       1d               7           1442    0.49%
        DYDX       1h            1717          39175    4.38%
        MSFT       1d              22           3384    0.65%
         SOL       1h             173          39085    0.44%
        META       1d               9           3289    0.27%
         ADA       1h             618          44142    1.40%
         BTC       1h             103          52731    0.20%
        AVAX       1h             517          39797    1.30%
        TSLA       1h               6           3291    0.18%
        AAPL       1h               7           3291    0.21%
    1000PEPE       1h             145          25514    0.57%
       GOOGL       1h               6           3291    0.18%
         DOT       1h             725          44140    1.64%
         LTC       1h             450          47692    0.94%
         XRP       1h             512          42796    1.20%
         ETH       1h              41          44221    0.09%

## 5. Extreme Spikes (Outliers)
Assets with flash crashes/spikes (>5 standard deviations):

asset_symbol interval  spike_candles
        MSFT       1d             14
         SOL       1h             43
        AMZN       1h              2
        AMZN      1wk             21
        AAPL       1d             12
        AVAX        W             19
        DOGE       1h             78
         LTC       1h             62
         XRP       1h             62
         ETH       1d            185
        META       1h              2
        META      1wk             16
         DOT       1h             57
        DYDX        W             19
         LTC        W             38
         XRP        W             27
       GOOGL       1d             13
        TSLA      1wk             22
    1000PEPE       1d            113
        AVAX       1h             30
        DOGE        W             25
       GOOGL       1h              1
       GOOGL      1wk             21
        TSLA       1d              9
    1000PEPE       1h             42
        AVAX       1d            164
        DYDX       1d            139
         XRP       1d            139
         LTC       1d            173
         ETH       1h             51
        META       1d             14
         DOT       1d            162
         ADA       1h             48
         BTC       1h             59
        MSFT       1h              2
        MSFT      1wk             18
         SOL       1d            155
         ADA        W             31
         BTC        W             46
         DOT        W             29
        DYDX       1h             45
        AAPL       1h              1
        AAPL      1wk             20
        AMZN       1d             12
        DOGE       1d            163
         ETH        W             36
         SOL        W             13
         ADA       1d            161
         BTC       1d            245

## 6. Timestamp & Interval Integrity
Inconsistent Interval Deltas (Time Drift):
asset_symbol interval  drift_events
        MSFT       1d           740
        AMZN       1h           473
        AAPL       1d           740
        META       1h           473
        TSLA       1h           473
       GOOGL       1d           740
        MSFT       1h           473
        AMZN       1d           740
        AAPL       1h           473
        META       1d           717
       GOOGL       1h           473
        TSLA       1d           740

## 7. Conclusion
Data is verified for ML training.
