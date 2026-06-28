import duckdb
import yaml
import os
import pandas as pd
from dotenv import load_dotenv
from src.utils import get_logger
import ta
import numpy as np

MIN_ROWS_FOR_INDICATORS = 200


class TechnicalIndicatorProcessor:
    """Calculates technical indicators for ML feature engineering"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        load_dotenv()
        
        with open("configs/settings.yml", "r") as f:
            self.config = yaml.safe_load(f)
            
        self.db_path = self.config["paths"]["database"]
        self.analytics_bucket = self.config["paths"].get("analytics_bucket", "analytics-data")
        self.conn = duckdb.connect(self.db_path)
        
        s3_endpoint = os.getenv("S3_ENDPOINT_URL", "http://localhost:9000").replace("http://", "")
        self.conn.execute("INSTALL httpfs; LOAD httpfs;")
        self.conn.execute(f"""
            CREATE SECRET IF NOT EXISTS (
                TYPE S3,
                KEY_ID '{os.getenv("AWS_ACCESS_KEY_ID")}',
                SECRET '{os.getenv("AWS_SECRET_ACCESS_KEY")}',
                ENDPOINT '{s3_endpoint}',
                URL_STYLE 'path',
                USE_SSL false
            );
        """)
    
    def calculate_indicators_for_asset(self, df):
        """Calculate all technical indicators for a single asset's data"""
        
        df = df.sort_values('date').reset_index(drop=True)
        
        self.logger.info(f"  Calculating indicators for {len(df)} data points...")
        
        df['rsi_14'] = ta.momentum.RSIIndicator(close=df['close'], window=14).rsi()
        
        macd_indicator = ta.trend.MACD(close=df['close'], window_slow=26, window_fast=12, window_sign=9)
        df['macd'] = macd_indicator.macd()
        df['macd_signal'] = macd_indicator.macd_signal()
        df['macd_histogram'] = macd_indicator.macd_diff()
        
        df['roc_10'] = ta.momentum.ROCIndicator(close=df['close'], window=10).roc()
        df['roc_20'] = ta.momentum.ROCIndicator(close=df['close'], window=20).roc()
        
        stoch = ta.momentum.StochasticOscillator(high=df['high'], low=df['low'], close=df['close'], 
                                              window=14, smooth_window=3)
        df['stoch_k'] = stoch.stoch()
        df['stoch_d'] = stoch.stoch_signal()
        
        df['ema_12'] = ta.trend.EMAIndicator(close=df['close'], window=12).ema_indicator()
        df['ema_26'] = ta.trend.EMAIndicator(close=df['close'], window=26).ema_indicator()
        df['ema_50'] = ta.trend.EMAIndicator(close=df['close'], window=50).ema_indicator()
        df['ema_200'] = ta.trend.EMAIndicator(close=df['close'], window=200).ema_indicator()
        
        df['sma_50'] = ta.trend.SMAIndicator(close=df['close'], window=50).sma_indicator()
        df['sma_100'] = ta.trend.SMAIndicator(close=df['close'], window=100).sma_indicator()
        df['sma_200'] = ta.trend.SMAIndicator(close=df['close'], window=200).sma_indicator()
        
        bollinger = ta.volatility.BollingerBands(close=df['close'], window=20, window_dev=2)
        df['bb_upper'] = bollinger.bollinger_hband()
        df['bb_middle'] = bollinger.bollinger_mavg()
        df['bb_lower'] = bollinger.bollinger_lband()
        df['bb_width'] = bollinger.bollinger_wband()
        df['bb_percentage'] = bollinger.bollinger_pband()
        
        df['atr_14'] = ta.volatility.AverageTrueRange(high=df['high'], low=df['low'], 
                                                    close=df['close'], window=14).average_true_range()
        
        df['obv'] = ta.volume.OnBalanceVolumeIndicator(close=df['close'], volume=df['volume']).on_balance_volume()
        
        df['vwap'] = ta.volume.VolumeWeightedAveragePrice(high=df['high'], low=df['low'], 
                                                        close=df['close'], volume=df['volume']).volume_weighted_average_price()
        
        df['volume_sma_20'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma_20'].replace(0, 1)
        
        df['returns_1p'] = df['close'].pct_change(periods=1)
        df['returns_5p'] = df['close'].pct_change(periods=5)
        df['returns_10p'] = df['close'].pct_change(periods=10)
        df['returns_20p'] = df['close'].pct_change(periods=20)
        
        df['log_returns'] = np.log(df['close'] / df['close'].shift(1))
        
        df['hl_ratio'] = (df['high'] - df['low']) / df['close'].replace(0, 1)
        
        df['close_position'] = (df['close'] - df['low']) / (df['high'] - df['low']).replace(0, 1)
        
        df['prev_close'] = df['close'].shift(1)
        df['prev_volume'] = df['volume'].shift(1)
        df['prev_high'] = df['high'].shift(1)
        df['prev_low'] = df['low'].shift(1)
        
        return df
    
    def _create_feature_tables(self):
        """Create gold feature tables if they don't exist"""
        crypto_cols = [
            ("asset_symbol", "VARCHAR"), ("asset_class", "VARCHAR"), ("exchange", "VARCHAR"),
            ("interval", "VARCHAR"), ("date", "TIMESTAMP"),
            ("open", "DOUBLE"), ("high", "DOUBLE"), ("low", "DOUBLE"), ("close", "DOUBLE"),
            ("volume", "DOUBLE"), ("daily_volatility", "DOUBLE"), ("sma_7", "DOUBLE"), ("sma_30", "DOUBLE"),
            ("rsi_14", "DOUBLE"), ("macd", "DOUBLE"), ("macd_signal", "DOUBLE"), ("macd_histogram", "DOUBLE"),
            ("roc_10", "DOUBLE"), ("roc_20", "DOUBLE"),
            ("stoch_k", "DOUBLE"), ("stoch_d", "DOUBLE"),
            ("ema_12", "DOUBLE"), ("ema_26", "DOUBLE"), ("ema_50", "DOUBLE"), ("ema_200", "DOUBLE"),
            ("sma_50", "DOUBLE"), ("sma_100", "DOUBLE"), ("sma_200", "DOUBLE"),
            ("bb_upper", "DOUBLE"), ("bb_middle", "DOUBLE"), ("bb_lower", "DOUBLE"),
            ("bb_width", "DOUBLE"), ("bb_percentage", "DOUBLE"),
            ("atr_14", "DOUBLE"), ("obv", "DOUBLE"), ("vwap", "DOUBLE"),
            ("volume_sma_20", "DOUBLE"), ("volume_ratio", "DOUBLE"),
            ("returns_1p", "DOUBLE"), ("returns_5p", "DOUBLE"), ("returns_10p", "DOUBLE"), ("returns_20p", "DOUBLE"),
            ("log_returns", "DOUBLE"), ("hl_ratio", "DOUBLE"), ("close_position", "DOUBLE"),
            ("prev_close", "DOUBLE"), ("prev_volume", "DOUBLE"), ("prev_high", "DOUBLE"), ("prev_low", "DOUBLE"),
            ("turnover", "DOUBLE"), ("open_interest", "DOUBLE"), ("funding_rate", "DOUBLE"),
            ("fear_greed", "DOUBLE"),
        ]
        stock_cols = [c for c in crypto_cols if c[0] not in ('turnover', 'open_interest', 'funding_rate', 'fear_greed')]

        try:
            existing_crypto_cols = [
                r[0] for r in self.conn.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_name = 'gold_crypto_features'"
                ).fetchall()
            ]
            if existing_crypto_cols and 'fear_greed' not in existing_crypto_cols:
                self.logger.info("gold_crypto_features missing fear_greed column - dropping for rebuild")
                self.conn.execute("DROP TABLE IF EXISTS gold_crypto_features")
        except Exception:
            pass

        for asset_class, cols in [('crypto', crypto_cols), ('stock', stock_cols)]:
            col_defs = ', '.join(f"{name} {dtype}" for name, dtype in cols)
            self.conn.execute(f"CREATE TABLE IF NOT EXISTS gold_{asset_class}_features ({col_defs})")
            self.logger.info(f" gold_{asset_class}_features table is ready")

    def generate_ml_features_table(self):
        self.logger.info("=" * 60)
        self.logger.info("Building Specialized Gold Feature Stores (incremental)")
        self.logger.info("=" * 60)

        indicator_cols = ['rsi_14', 'macd', 'macd_signal', 'macd_histogram', 'roc_10', 'roc_20',
                          'stoch_k', 'stoch_d', 'ema_12', 'ema_26', 'ema_50', 'ema_200',
                          'sma_50', 'sma_100', 'sma_200', 'bb_upper', 'bb_middle', 'bb_lower',
                          'bb_width', 'bb_percentage', 'atr_14', 'obv', 'vwap',
                          'volume_sma_20', 'volume_ratio', 'returns_1p', 'returns_5p',
                          'returns_10p', 'returns_20p', 'log_returns', 'hl_ratio', 'close_position']

        self._create_feature_tables()

        query = """
            SELECT asset_symbol, asset_class, exchange, interval, date,
                   open, high, low, close, volume, daily_volatility, sma_7, sma_30
            FROM gold_crypto_analytics
            UNION ALL
            SELECT asset_symbol, asset_class, exchange, interval, date,
                   open, high, low, close, volume, daily_volatility, sma_7, sma_30
            FROM gold_stock_analytics
        """
        df_all = self.conn.execute(query).df()
        self.logger.info(f"Loaded {len(df_all)} rows from specialized intermediate layers")

        crypto_extra = self.conn.execute("""
            SELECT asset_symbol, interval, date,
                   turnover, open_interest, funding_rate
            FROM gold_crypto_analytics
        """).df()

        fear_greed_df = self.conn.execute("""
            SELECT date, value AS fear_greed
            FROM clean_fear_greed
        """).df()

        total_groups = df_all.groupby(['asset_symbol', 'interval']).ngroups
        total_inserted = 0

        for current_group, ((asset, interval), group_df) in enumerate(df_all.groupby(['asset_symbol', 'interval']), 1):
            self.logger.info(f"[{current_group}/{total_groups}] Processing {asset} ({interval})...")

            asset_class = group_df['asset_class'].iloc[0].lower()
            table_name = f"gold_{asset_class}_features"

            max_date = self.conn.execute(f"""
                SELECT MAX(date) FROM {table_name}
                WHERE asset_symbol = ? AND interval = ?
            """, [asset, interval]).fetchone()[0]

            if max_date is not None:
                group_df = group_df[group_df['date'] > max_date]
                if len(group_df) == 0:
                    self.logger.info(f"  No new data for {asset} ({interval}), skipping")
                    continue

                cutoff_date = group_df['date'].min()
                buffer_size = max(MIN_ROWS_FOR_INDICATORS, 300)
                buffer_df = self.conn.execute(f"""
                    SELECT asset_symbol, asset_class, exchange, interval, date,
                           open, high, low, close, volume, daily_volatility, sma_7, sma_30
                    FROM gold_{asset_class}_analytics
                    WHERE asset_symbol = ? AND interval = ? AND date < ?
                    ORDER BY date DESC
                    LIMIT {buffer_size}
                """, [asset, interval, cutoff_date]).df()

                if len(buffer_df) > 0:
                    buffer_df = buffer_df.sort_values('date')
                    group_df = pd.concat([buffer_df, group_df], ignore_index=True)

            if len(group_df) < MIN_ROWS_FOR_INDICATORS:
                self.logger.warning(f"  Skipping {asset} ({interval}) - only {len(group_df)} rows (need {MIN_ROWS_FOR_INDICATORS}+)")
                continue

            enhanced_df = self.calculate_indicators_for_asset(group_df.copy())
            initial_rows = len(enhanced_df)
            cols_to_check = [c for c in indicator_cols if c in enhanced_df.columns]
            enhanced_df = enhanced_df.dropna(subset=cols_to_check)
            self.logger.info(f"  Dropped {initial_rows - len(enhanced_df)} rows with NaNs (warm-up)")

            if max_date is not None:
                enhanced_df = enhanced_df[enhanced_df['date'] > max_date]

            if asset_class == 'crypto' and len(enhanced_df) > 0:
                merge_keys = ['asset_symbol', 'interval', 'date']
                enhanced_df = enhanced_df.merge(
                    crypto_extra[merge_keys + ['turnover', 'open_interest', 'funding_rate']],
                    on=merge_keys, how='left'
                )

                fg_lookup = fear_greed_df[['date', 'fear_greed']].copy()
                fg_lookup['join_date'] = fg_lookup['date'].dt.date
                fg_lookup = fg_lookup[['join_date', 'fear_greed']]
                enhanced_df['join_date'] = enhanced_df['date'].dt.date
                enhanced_df = enhanced_df.merge(
                    fg_lookup,
                    on='join_date', how='left'
                )
                enhanced_df.drop(columns=['join_date'], inplace=True)

            if len(enhanced_df) == 0:
                self.logger.info(f"  No new rows after filtering for {asset} ({interval})")
                continue

            self.conn.register('temp_class_df', enhanced_df)
            self.conn.execute(f"""
                INSERT INTO {table_name}
                SELECT * FROM temp_class_df
                WHERE NOT EXISTS (
                    SELECT 1 FROM {table_name} f
                    WHERE f.asset_symbol = temp_class_df.asset_symbol
                      AND f.interval = temp_class_df.interval
                      AND f.date = temp_class_df.date
                )
            """)
            self.conn.unregister('temp_class_df')

            inserted = self.conn.execute(f"""
                SELECT COUNT(*) FROM {table_name}
                WHERE asset_symbol = ? AND interval = ? AND date > ?
            """, [asset, interval, max_date or '1900-01-01']).fetchone()[0]
            self.logger.info(f"  Inserted {inserted} new rows for {asset} ({interval})")
            total_inserted += inserted

            cnt = self.conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            self.logger.info(f"  {table_name} now has {cnt} total rows!")

        self.logger.info(f"Total new rows inserted across all feature tables: {total_inserted}")

        for asset_class in ['crypto', 'stock']:
            out_path = f"s3://{self.analytics_bucket}/{asset_class}_features.parquet"
            try:
                self.conn.execute(f"COPY gold_{asset_class}_features TO '{out_path}' (FORMAT PARQUET)")
                self.logger.info(f"Exported to MinIO: {out_path}")
            except Exception as e:
                self.logger.error(f"Failed to export {asset_class} Features to MinIO: {e}")
    
    def run(self):
        self.logger.info("*" * 60)
        self.logger.info("Starting Technical Indicator Calculation Process")
        self.logger.info("*" * 60)
        
        self.generate_ml_features_table()
        
        self.logger.info("*" * 60)
        self.logger.info("Technical Indicators Completed")
        self.logger.info("*" * 60)
    
    def close(self):
        if self.conn:
            self.conn.close()


if __name__ == "__main__":
    processor = TechnicalIndicatorProcessor()
    processor.run()
    processor.close()