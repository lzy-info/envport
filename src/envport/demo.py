"""A tiny deterministic environment and an intentionally broken variant."""

from .contract import ProbeSpec, StepResult


class CounterEnvironment:
    """Reach position 3. Every third seed selects a decorative alternate label."""

    def __init__(self) -> None:
        self.position = 0
        self.seed = 0
        self.closed = False

    def reset(self, seed: int) -> dict:
        self._open()
        self.seed = seed
        self.position = 0
        return self.observe()

    def _open(self) -> None:
        if self.closed:
            raise RuntimeError("environment is closed")

    def observe(self) -> dict:
        self._open()
        return {"position": self.position, "goal": 3, "theme": self.seed % 3}

    def step(self, action: dict) -> StepResult:
        self._open()
        if action not in ({"move": "right"}, {"move": "noop"}):
            raise ValueError("action must be {'move': 'right'} or {'move': 'noop'}")
        if self.position == 3:
            raise ValueError("episode terminated; call reset before stepping")
        if action["move"] == "right":
            self.position += 1
        done = self.position == 3
        return StepResult(self.observe(), float(done), done)

    def grade(self) -> float:
        self._open()
        return float(self.position == 3)

    def envport_probe(self) -> ProbeSpec:
        return ProbeSpec(
            noop_actions=({"move": "noop"},) * 3,
            oracle_actions=({"move": "right"},) * 3,
        )

    def close(self) -> None:
        self.closed = True


class BrokenCounterEnvironment(CounterEnvironment):
    """Three deliberate defects: reset leak, permissive grade, NaN reward."""

    def reset(self, seed: int) -> dict:
        self._open()
        self.seed = seed
        # BUG: position is not restored.
        return self.observe()

    def grade(self) -> float:
        self._open()
        # BUG: awards success even when no progress was made.
        return 1.0

    def step(self, action: dict) -> StepResult:
        result = super().step(action)
        # BUG: non-finite reward is unusable for ordinary training pipelines.
        return StepResult(result.observation, float("nan"), result.terminated)
