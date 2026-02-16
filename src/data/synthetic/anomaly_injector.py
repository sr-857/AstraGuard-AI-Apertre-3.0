import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

def inject_anomalies(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    Injects anomalies into the dataframe based on configuration.
    Adds an 'is_anomaly' column.
    """
    df = df.copy()
    n_samples = len(df)
    df['is_anomaly'] = 0

    anom_cfg = config.get('anomalies', {})
    if not anom_cfg.get('enabled', False):
        return df

    total_anomalies = int(n_samples * anom_cfg.get('percentage', 0.05))
    logger.info(f"Injecting approx {total_anomalies} anomalous samples...")

    # We will distribute anomalies among enabled types
    types = anom_cfg.get('types', {})
    enabled_types = [k for k, v in types.items() if v.get('enabled', False)]

    if not enabled_types:
        return df

    # Rough distribution
    per_type = total_anomalies // len(enabled_types)

    # ---------------------------------------------------------
    # 1. Point Anomalies (Spikes/Drops)
    # ---------------------------------------------------------
    if 'point' in enabled_types:
        cfg = types['point']
        # Random indices
        indices = np.random.choice(n_samples, per_type, replace=False)

        # Apply to voltage or current randomly
        for idx in indices:
            feature = np.random.choice(['voltage', 'current'])
            multiplier = cfg.get('multiplier', 3.0)

            # 50% chance of spike up vs spike down
            # Ensure we don't drop voltage to negative unless realistic
            if np.random.random() > 0.5:
                df.at[idx, feature] *= multiplier
            else:
                df.at[idx, feature] *= (1.0 / multiplier)

            df.at[idx, 'is_anomaly'] = 1

    # ---------------------------------------------------------
    # 2. Collective Anomalies (Contextual - Sequence)
    # ---------------------------------------------------------
    if 'collective' in enabled_types:
        # Scenario: Motor Stall (High Current, Low Speed)
        duration = 50 # 50 samples duration
        num_events = max(1, int(per_type / duration))

        for _ in range(num_events):
            start = np.random.randint(0, n_samples - duration)
            end = start + duration

            # Set wheel speed to near 0 (stall)
            df.loc[start:end-1, 'wheel_speed'] = np.abs(np.random.normal(0, 0.5, duration))

            # Set current to high (stall current)
            stall_current = config['features']['current']['mean'] * 3.0
            df.loc[start:end-1, 'current'] = np.random.normal(stall_current, 1.0, duration)

            # Voltage dip due to high load
            df.loc[start:end-1, 'voltage'] -= 5.0

            df.loc[start:end-1, 'is_anomaly'] = 1

    # ---------------------------------------------------------
    # 3. Drift Anomalies (Trend Shift)
    # ---------------------------------------------------------
    if 'drift' in enabled_types:
        # Scenario: Thermal Runaway
        cfg = types['drift']
        slope_mult = cfg.get('slope_multiplier', 5.0)

        duration = 100
        num_events = max(1, int(per_type / duration))

        for _ in range(num_events):
            start = np.random.randint(0, n_samples - duration)
            end = start + duration

            # Add increasing trend to temperature
            t_local = np.arange(duration)
            # Artificial rapid rise
            rise = 0.2 * slope_mult * t_local

            df.loc[start:end-1, 'temperature'] += rise

            df.loc[start:end-1, 'is_anomaly'] = 1

    logger.info(f"Anomalies injected. Total anomalous samples: {df['is_anomaly'].sum()}")
    return df
