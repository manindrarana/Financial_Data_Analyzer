import pandas as pd

from scripts.compare_multitimeframe_models import prepare_interval_data


def test_prepare_interval_data_uses_candle_close_as_availability_time():
    source = pd.DataFrame({
        "date": [pd.Timestamp("2026-01-01 00:00:00", tz="UTC")],
        "close": [100.0],
        "rsi_14": [50.0],
    })

    prepared, features = prepare_interval_data(source, "1h")

    assert features == ["rsi_14"]
    assert prepared.loc[0, "available_at"] == pd.Timestamp(
        "2026-01-01 01:00:00", tz="UTC"
    )
