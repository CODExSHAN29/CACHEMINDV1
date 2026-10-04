"""Inference subsystem package."""
from backend.inference.models import InferenceResult
from backend.inference.pipeline import InferencePipeline, get_inference_pipeline, set_inference_pipeline

__all__ = ["InferenceResult", "InferencePipeline", "get_inference_pipeline", "set_inference_pipeline"]
