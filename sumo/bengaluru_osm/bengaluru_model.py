"""Stable import path for the serialized two-stage queue regressor."""
from __future__ import annotations
import numpy as np

class HurdleQueueModel:
    def __init__(self, classifier, regressor, threshold, features):
        self.classifier=classifier;self.regressor=regressor;self.threshold=float(threshold);self.feature_names_in_=np.array(features)
    def predict(self, X):
        X=X[list(self.feature_names_in_)]
        probability=self.classifier.predict_proba(X)[:,1]
        positive=np.maximum(0,self.regressor.predict(X))
        return np.where(probability>=self.threshold,positive,0.0)
