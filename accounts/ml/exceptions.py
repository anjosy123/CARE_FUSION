class MLPredictionError(Exception):
    """Base exception for ML prediction errors"""
    pass

class DataPreprocessingError(MLPredictionError):
    """Raised when data preprocessing fails"""
    pass

class ModelPredictionError(MLPredictionError):
    """Raised when model prediction fails"""
    pass

class InvalidInputError(MLPredictionError):
    """Raised when input data is invalid"""
    pass

class ModelNotFoundError(MLPredictionError):
    """Raised when ML model file is not found"""
    pass
