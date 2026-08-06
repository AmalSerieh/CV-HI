"""Pure final-report integration helpers."""

from __future__ import annotations

from copy import deepcopy

from .exceptions import InvalidPipelineInputError


def attach_target_role(pipeline_json: dict, target_role_result: dict) -> dict:
    """Return a copy with ``target_role`` replaced by the supplied result.

    Replacement is intentional and deterministic when the pipeline already has
    a ``target_role`` key. Neither input argument is modified.
    """

    if not isinstance(pipeline_json, dict):
        raise InvalidPipelineInputError("pipeline_json must be a dictionary")
    if not isinstance(target_role_result, dict):
        raise InvalidPipelineInputError("target_role_result must be a dictionary")
    payload = target_role_result.get("target_role", target_role_result)
    if not isinstance(payload, dict):
        raise InvalidPipelineInputError("target_role_result.target_role must be an object")
    merged = deepcopy(pipeline_json)
    merged["target_role"] = deepcopy(payload)
    return merged
