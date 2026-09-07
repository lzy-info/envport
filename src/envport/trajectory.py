"""Structural checks only: no tokenization, image decoding, or gradient test."""

import math

from .report import finding, report


def _number(value):
    try:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        return False


def _json_value(value):
    if value is None or isinstance(value, (str, bool)):
        return True
    if isinstance(value, (int, float)):
        return _number(value)
    if isinstance(value, list):
        return all(_json_value(v) for v in value)
    if isinstance(value, dict):
        return all(isinstance(k, str) and _json_value(v) for k, v in value.items())
    return False


def validate_trajectory(data) -> dict:
    """Validate envport.trajectory.v1, allowing extra metadata fields.

    All steps contain action (object), reward (finite number), token_ids
    (nonnegative integers), logprobs (finite numbers), loss_mask (booleans or
    integer 0/1), image_refs (declared image IDs). Token arrays have equal
    nonzero length. Declared images map nonempty IDs to nonempty URI strings.
    Image resources are never opened. Optional terminated must be a boolean.
    """
    checks = []

    def check(name, condition, detail):
        checks.append(finding(name, "pass" if condition else "fail", detail))

    def result():
        return report("trajectory", checks,
                      scope="Schema-only: no image loading, tensor propagation, gradient flow, tokenization alignment, or framework compatibility verification.")

    if not isinstance(data, dict):
        check("document", False, "Trajectory must be a JSON object.")
        return result()
    check("schema_version", data.get("schema_version") == "envport.trajectory.v1",
          "Expected schema_version 'envport.trajectory.v1'.")
    images = data.get("images")
    images_valid = isinstance(images, dict) and all(
        isinstance(k, str) and k.strip() and isinstance(v, str) and v.strip()
        for k, v in images.items())
    check("images", bool(images_valid), "images must map nonempty image IDs to nonempty URI strings; resources are not opened.")
    steps = data.get("steps")
    if not isinstance(steps, list) or not steps:
        check("steps", False, "steps must be a nonempty array.")
        return result()
    check("steps", True, f"Inspecting {len(steps)} steps.")
    for index, step in enumerate(steps):
        prefix = f"steps[{index}]"
        if not isinstance(step, dict):
            check(prefix, False, "Step must be an object.")
            continue
        check(prefix + ".action", isinstance(step.get("action"), dict) and _json_value(step["action"]),
              "action must be a finite JSON object.")
        check(prefix + ".reward", _number(step.get("reward")), "reward must be a finite number, not a boolean.")
        tokens, logs, mask = (step.get(key) for key in ("token_ids", "logprobs", "loss_mask"))
        check(prefix + ".token_ids", isinstance(tokens, list) and bool(tokens) and all(
            type(t) is int and t >= 0 for t in tokens), "token_ids must be a nonempty array of nonnegative integers.")
        check(prefix + ".logprobs", isinstance(logs, list) and all(_number(n) for n in logs),
              "logprobs must be an array of finite numbers.")
        check(prefix + ".loss_mask", isinstance(mask, list) and all(
            isinstance(n, bool) or type(n) is int and n in (0, 1) for n in mask),
              "loss_mask must contain only booleans or integer 0/1.")
        check(prefix + ".token_lengths", all(isinstance(x, list) for x in (tokens, logs, mask))
              and len(tokens) == len(logs) == len(mask), "token_ids, logprobs, and loss_mask must have equal lengths.")
        refs = step.get("image_refs")
        refs_valid = isinstance(refs, list) and all(isinstance(r, str) and r.strip() for r in refs)
        if refs_valid:
            refs_valid = len(refs) == len(set(refs)) and bool(images_valid) and all(r in images for r in refs)
        check(prefix + ".image_refs", bool(refs_valid), "image_refs must be distinct string IDs declared in images; use [] for text-only steps.")
        if "terminated" in step:
            check(prefix + ".terminated", isinstance(step["terminated"], bool), "terminated must be a boolean.")
    return result()
