import glob
import os

import joblib
import mlflow

MODEL_NAME = "cf-recommender"

# In-memory cache — simple module-level state, since we only ever need
# "the one currently loaded champion model" for the whole process.
_cache = {"package": None, "version": None}


def _client():
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI")
    if not tracking_uri:
        raise RuntimeError("MLFLOW_TRACKING_URI is not set")
    mlflow.set_tracking_uri(tracking_uri)
    return mlflow.MlflowClient()


def reload_champion_model():
    """
    Downloads the current 'champion' version of the CF model from the
    MLflow Model Registry and loads it into memory. Returns the version
    number that was loaded.

    Called explicitly (via the /admin/reload-model endpoint) rather than
    on every request, so that swapping in a newly-trained champion is a
    deliberate, visible action rather than something that happens silently
    in the background mid-service.
    """
    client = _client()
    version = client.get_model_version_by_alias(MODEL_NAME, "champion")

    local_dir = mlflow.artifacts.download_artifacts(artifact_uri=version.source)
    joblib_files = glob.glob(os.path.join(local_dir, "*.joblib"))
    if not joblib_files:
        raise RuntimeError(f"No .joblib artifact found under {local_dir}")

    package = joblib.load(joblib_files[0])
    _cache["package"] = package
    _cache["version"] = version.version
    return version.version


def get_champion_package():
    """
    Returns the currently loaded package: {"cf": model, "items": [...],
    "users": [...], "train_matrix": ...}, or None if no model has been
    loaded yet (reload_champion_model() was never called or failed).
    """
    return _cache["package"]


def get_champion_version():
    return _cache["version"]