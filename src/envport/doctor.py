"""Bounded behavioral probes. Passing does not prove safety or correctness."""

import copy
import json
import math
from typing import Callable

from .contract import ProbeSpec, StepResult
from .report import finding, report


def _finite(value) -> bool:
    try:
        return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)
    except OverflowError:
        return False


def _snapshot(value) -> str:
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":"))


def _spec_error(spec) -> str | None:
    if not isinstance(spec, ProbeSpec):
        return "envport_probe() must return envport.ProbeSpec"
    numbers = (spec.reward_min, spec.reward_max, spec.grade_min, spec.grade_max,
               spec.noop_grade_max, spec.oracle_grade_min)
    if not all(_finite(n) for n in numbers):
        return "all probe bounds and grade thresholds must be finite numbers"
    if spec.reward_min > spec.reward_max or spec.grade_min > spec.grade_max:
        return "probe minimum bounds must not exceed maximum bounds"
    if not (spec.grade_min <= spec.noop_grade_max < spec.oracle_grade_min <= spec.grade_max):
        return "grade thresholds must be within bounds and no-op maximum below oracle minimum"
    for actions in (spec.noop_actions, spec.oracle_actions):
        if not isinstance(actions, (tuple, list)) or not 1 <= len(actions) <= 1000:
            return "each probe sequence must contain 1 to 1,000 actions"
        try:
            _snapshot(actions)
        except (TypeError, ValueError, OverflowError, RecursionError):
            return "probe actions must be finite JSON-compatible values"
    return None


def doctor(factory: Callable, *, seed: int = 7, source: str = "factory") -> dict:
    """Construct fresh instances; execute only an explicit, trusted local factory.

    Environment code runs in-process, without a sandbox or timeout. Factories
    must return distinct instances and methods must return promptly. Only this
    seed and the supplied probe actions are sampled.
    """
    checks = []
    instances = []

    def add(name, ok, detail):
        checks.append(finding(name, "pass" if ok else "fail", detail))

    def fresh():
        env = factory()
        if any(env is previous for previous in instances):
            raise ValueError("factory returned a previously used instance")
        instances.append(env)
        for method in ("reset", "observe", "step", "grade", "close"):
            if not callable(getattr(env, method, None)):
                raise TypeError(f"environment is missing callable {method}()")
        return env

    def run(name, fn):
        try:
            fn()
        except Exception as exc:
            checks.append(finding(name, "fail", f"{type(exc).__name__}: {exc}"))

    try:
        first, second = fresh(), fresh()
        add("interface", True, "Two distinct instances expose reset, observe, step, grade, close.")
        probe_method = getattr(first, "envport_probe", None)
        spec = None
        if probe_method is None:
            checks.append(finding("probe_contract", "skip", "No envport_probe(); action and grade probes unavailable."))
        elif not callable(probe_method):
            add("probe_contract", False, "envport_probe is present but is not callable.")
        else:
            try:
                candidate = probe_method()
                error = _spec_error(candidate)
                add("probe_contract", error is None, error or "Explicit action sequences and numerical expectations are valid.")
                if error is None:
                    spec = candidate
            except Exception as exc:
                add("probe_contract", False, f"{type(exc).__name__}: {exc}")

        def initial_reset():
            first.reset(seed)
            initial = _snapshot(first.observe())
            first.reset(seed)
            repeated = _snapshot(first.observe())
            second.reset(seed)
            separate = _snapshot(second.observe())
            add("same_seed_reset", initial == repeated == separate,
                "Compared initial observations after repeated same-seed resets and on a second instance.")
        run("same_seed_reset", initial_reset)

        if spec is None:
            for name in ("reset_after_actions", "cross_instance_isolation", "deterministic_replay",
                         "noop_grade", "oracle_grade", "reward_bounds"):
                checks.append(finding(name, "skip", "A valid explicit probe contract is required."))
        else:
            def reset_after_actions():
                env = fresh()
                env.reset(seed)
                baseline = _snapshot(env.observe())
                for action in spec.oracle_actions:
                    result = env.step(copy.deepcopy(action))
                    if not isinstance(result, StepResult):
                        raise TypeError("step() must return envport.StepResult")
                    if result.terminated:
                        break
                env.reset(seed)
                observed = _snapshot(env.observe())
                add("reset_after_actions", baseline == observed,
                    "Compared fresh reset observation with same-seed reset after oracle actions.")
            run("reset_after_actions", reset_after_actions)

            def isolation():
                first.reset(seed)
                second.reset(seed)
                before = _snapshot(second.observe())
                first.step(copy.deepcopy(spec.oracle_actions[0]))
                after = _snapshot(second.observe())
                add("cross_instance_isolation", before == after,
                    "Second instance observation remained unchanged while the first was stepped." if before == after
                    else "Stepping the first instance changed the second instance observation.")
            run("cross_instance_isolation", isolation)

            sampled_rewards = []
            traces = {}

            def sequence(label, actions):
                env = fresh()
                env.reset(seed)
                trace = [_snapshot(env.observe())]
                for action in actions:
                    result = env.step(copy.deepcopy(action))
                    if not isinstance(result, StepResult):
                        raise TypeError("step() must return envport.StepResult")
                    sampled_rewards.append(result.reward)
                    if not isinstance(result.terminated, bool):
                        raise TypeError("StepResult.terminated must be a bool")
                    observation = _snapshot(result.observation)
                    if observation != _snapshot(env.observe()):
                        raise ValueError("step observation does not match observe()")
                    # repr captures non-finite reward defects without putting NaN in reports.
                    trace.append((observation, repr(result.reward), result.terminated))
                    if result.terminated:
                        break
                grade = env.grade()
                if not _finite(grade) or not spec.grade_min <= grade <= spec.grade_max:
                    raise ValueError("grade() must be a finite number within declared grade bounds")
                trace.append(repr(grade))
                traces[label] = trace
                if label == "noop":
                    add("noop_grade", grade <= spec.noop_grade_max,
                        f"No-op grade {grade!r}; expected <= {spec.noop_grade_max!r}.")
                elif label == "oracle":
                    add("oracle_grade", grade >= spec.oracle_grade_min,
                        f"Oracle grade {grade!r}; expected >= {spec.oracle_grade_min!r}.")

            run("noop_grade", lambda: sequence("noop", spec.noop_actions))
            run("oracle_grade", lambda: sequence("oracle", spec.oracle_actions))
            run("deterministic_replay", lambda: sequence("replay", spec.oracle_actions))
            if "oracle" in traces and "replay" in traces:
                add("deterministic_replay", traces["oracle"] == traces["replay"],
                    "Compared observations, rewards, termination flags, and grade for same-seed oracle runs on fresh instances.")
            elif not any(c["name"] == "deterministic_replay" for c in checks):
                checks.append(finding("deterministic_replay", "skip", "Oracle run failed; replay comparison unavailable."))
            if sampled_rewards:
                invalid = sum(not _finite(r) or not spec.reward_min <= r <= spec.reward_max
                              for r in sampled_rewards)
                add("reward_bounds", invalid == 0,
                    f"{invalid} of {len(sampled_rewards)} sampled rewards non-finite or outside [{spec.reward_min}, {spec.reward_max}].")
            else:
                checks.append(finding("reward_bounds", "skip", "No rewards could be sampled."))
    except Exception as exc:
        add("interface", False, f"{type(exc).__name__}: {exc}")
    finally:
        close_errors = []
        closed = 0
        for env in reversed(instances):
            try:
                close = getattr(env, "close", None)
                if callable(close):
                    close()
                    closed += 1
                else:
                    close_errors.append("Constructed instance has no callable close().")
            except Exception as exc:
                close_errors.append(f"{type(exc).__name__}: {exc}")
        add("cleanup", not close_errors, f"Closed {closed} of {len(instances)} constructed instances. " + "; ".join(close_errors))
    return report("doctor", checks, source=source, seed=seed,
                  scope="Sampled in-process contract checks; not a proof of safety, isolation, determinism, or training compatibility.")
