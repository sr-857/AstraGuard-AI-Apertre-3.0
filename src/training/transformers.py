from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class MissingValueHandler(BaseEstimator, TransformerMixin):
    """
    Transformer to handle missing values using SimpleImputer.
    Defaults to mean imputation.
    """
    def __init__(self, strategy="mean"):
        self.strategy = strategy
        self.imputer = SimpleImputer(strategy=self.strategy)

    def fit(self, X, y=None):
        self.imputer.fit(X)
        return self

    def transform(self, X):
        X_imputed = self.imputer.transform(X)
        # SimpleImputer returns a numpy array, but we might want to keep DataFrame structure if possible
        # However, for consistency in pipelines, numpy array is standard.
        # But let's try to preserve pandas if input is pandas
        if isinstance(X, pd.DataFrame):
            return pd.DataFrame(X_imputed, columns=X.columns, index=X.index)
        return X_imputed

class NumericalScaler(BaseEstimator, TransformerMixin):
    """
    Transformer to scale numerical features using StandardScaler.
    """
    def __init__(self, with_mean=True, with_std=True):
        self.with_mean = with_mean
        self.with_std = with_std
        self.scaler = StandardScaler(with_mean=self.with_mean, with_std=self.with_std)

    def fit(self, X, y=None):
        self.scaler.fit(X)
        return self

    def transform(self, X):
        X_scaled = self.scaler.transform(X)
        if isinstance(X, pd.DataFrame):
            return pd.DataFrame(X_scaled, columns=X.columns, index=X.index)
        return X_scaled

class DebugLogger(BaseEstimator, TransformerMixin):
    """
    Transformer that logs the shape of the data and passes it through unchanged.
    Useful for debugging pipelines.
    """
    def __init__(self, message=""):
        self.message = message

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        logger.info(f"{self.message}: Data shape: {X.shape}")
        return X
