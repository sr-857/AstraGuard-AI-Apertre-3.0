from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from src.training.transformers import MissingValueHandler, NumericalScaler, DebugLogger

def create_preprocessing_pipeline(config: dict) -> Pipeline:
    """
    Create a scikit-learn preprocessing pipeline.

    Args:
        config (dict): Configuration dictionary containing feature names.

    Returns:
        Pipeline: Scikit-learn pipeline object.
    """
    numeric_features = config["data"]["features"]

    # Define numeric transformer
    numeric_transformer = Pipeline(steps=[
        ('imputer', MissingValueHandler(strategy='mean')),
        ('scaler', NumericalScaler()),
        ('logger', DebugLogger(message="After numeric scaling"))
    ])

    # Combine transformers using ColumnTransformer
    # We only have numeric features for now as per config.
    # If categorical features exist in the future, we would add another transformer here.

    preprocessor = ColumnTransformer(
        transformers=[
            ('num', numeric_transformer, numeric_features)
        ],
        remainder='drop'  # Drop columns not specified in features to ensure clean input
    )

    # Create the final pipeline
    # We wrap the preprocessor in a pipeline to allow adding more steps if needed
    pipeline = Pipeline(steps=[
        ('preprocessor', preprocessor)
    ])

    return pipeline
