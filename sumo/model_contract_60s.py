"""Shared 60-second queue-model input contract for the SUMO controller."""


FEATURES = (
    "queue_length_m",
    "vehicle_count",
    "halting_vehicle_count",
    "mean_speed_mps",
    "phase_elapsed_s",
    "intersection_id",
    "approach_id",
    "lane_id",
    "signal_phase_id",
    "signal_state",
)


def validate_model_feature_schema(model):
    """Fail clearly if a saved model expects another feature order/schema."""
    model_features = list(getattr(model, "feature_names_in_", ()))
    if model_features != list(FEATURES):
        raise ValueError(
            "Saved model feature schema differs from the expected schema.\n"
            f"Expected: {list(FEATURES)}\n"
            f"Found:    {model_features}"
        )
    return True
