"""EnvPort's deliberately small environment inspection API."""

from .contract import ProbeSpec, StepResult
from .doctor import doctor
from .trajectory import validate_trajectory

__version__ = "0.1.0a1"
__all__ = ["ProbeSpec", "StepResult", "doctor", "validate_trajectory"]
