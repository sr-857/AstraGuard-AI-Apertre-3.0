import pandas as pd
import numpy as np
import yaml
import os
import logging

logger = logging.getLogger(__name__)

def load_config(config_path: str = None) -> dict:
    if config_path is None:
        # Default to the config in the same directory
        base_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(base_dir, "config.yaml")

    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def generate_normal_data(config_path: str = None) -> pd.DataFrame:
    """
    Generates normal telemetry data based on configuration.
    Includes natural drift and correlations between features.
    """
    config = load_config(config_path)

    n_samples = config['samples']
    np.random.seed(config['random_seed'])

    # ---------------------------------------------------------
    # 1. Base Time Index
    # ---------------------------------------------------------
    t = np.arange(n_samples)

    # ---------------------------------------------------------
    # 2. Wheel Speed (Driver)
    # ---------------------------------------------------------
    # Use an Ornstein-Uhlenbeck process to simulate changing operating modes
    ws_cfg = config['features']['wheel_speed']

    # Parameters for OU process
    theta = 0.02  # Speed of reversion to mean
    sigma = ws_cfg['std'] * 0.5 # Volatility

    wheel_speed = np.zeros(n_samples)
    wheel_speed[0] = ws_cfg['mean']

    noise = np.random.normal(0, sigma, n_samples)

    for i in range(1, n_samples):
        prev = wheel_speed[i-1]
        drift = theta * (ws_cfg['mean'] - prev)
        diffusion = noise[i]
        wheel_speed[i] = prev + drift + diffusion

    # Ensure non-negative
    wheel_speed = np.maximum(wheel_speed, 0)

    # ---------------------------------------------------------
    # 3. Current (Dependent on Speed + Load)
    # ---------------------------------------------------------
    curr_cfg = config['features']['current']
    corr = config['correlations']

    # Current = Mean + Factor * (Speed - MeanSpeed) + Noise
    # This correlates current spikes with speed spikes (acceleration/load)
    current_noise = np.random.normal(0, curr_cfg['std'], n_samples)
    current = curr_cfg['mean'] + corr['speed_current_factor'] * (wheel_speed - ws_cfg['mean']) + current_noise
    current = np.maximum(current, 0)

    # ---------------------------------------------------------
    # 4. Temperature (Dependent on Current + Drift)
    # ---------------------------------------------------------
    temp_cfg = config['features']['temperature']

    # Natural drift (e.g., warming up over operation)
    temp_drift = temp_cfg.get('drift_slope', 0) * t

    # Load effect: Higher current -> Higher temp
    # We model it as deviation from mean
    temp_load = corr['current_temp_factor'] * (current - curr_cfg['mean'])

    temp_noise = np.random.normal(0, temp_cfg['std'], n_samples)
    temperature = temp_cfg['mean'] + temp_drift + temp_load + temp_noise

    # ---------------------------------------------------------
    # 5. Voltage (Dependent on Battery State - Load)
    # ---------------------------------------------------------
    volt_cfg = config['features']['voltage']

    # Natural drift (battery drain)
    volt_drift = volt_cfg.get('drift_slope', 0) * t

    # Load drop: Higher current -> Lower voltage (V = V_source - I*R)
    # Modeled as deviation from mean to keep mean centered if current is mean
    volt_load = corr['current_voltage_drop'] * (current - curr_cfg['mean'])

    volt_noise = np.random.normal(0, volt_cfg['std'], n_samples)
    voltage = volt_cfg['mean'] + volt_drift - volt_load + volt_noise

    # ---------------------------------------------------------
    # 6. Gyro (Independent Noise)
    # ---------------------------------------------------------
    gyro_cfg = config['features']['gyro']
    gyro = np.random.normal(gyro_cfg['mean'], gyro_cfg['std'], n_samples)

    # Compile DataFrame
    df = pd.DataFrame({
        'voltage': voltage,
        'temperature': temperature,
        'current': current,
        'wheel_speed': wheel_speed,
        'gyro': gyro
    })

    logger.info(f"Generated {n_samples} normal samples with drift and correlations.")
    return df

if __name__ == "__main__":
    import argparse
    import sys

    # Ensure we can import from src if running as script
    if __package__ is None:
        sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
        from src.data.synthetic.anomaly_injector import inject_anomalies
    else:
        from .anomaly_injector import inject_anomalies

    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Generate synthetic telemetry data.")
    parser.add_argument("--output", help="Path to save CSV output")
    parser.add_argument("--config", help="Path to config file")

    args = parser.parse_args()

    # 1. Generate Normal
    df = generate_normal_data(args.config)

    # 2. Inject Anomalies
    config = load_config(args.config)
    df = inject_anomalies(df, config)

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        df.to_csv(args.output, index=False)
        print(f"Saved synthetic dataset to {args.output}")
        print(f"Shape: {df.shape}, Anomalies: {df['is_anomaly'].sum()}")
    else:
        print(df.head())
        print(df.describe())
        print(f"Anomalies: {df['is_anomaly'].sum()}")
