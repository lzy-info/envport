"""Run from the repository root:

python -m envport doctor --factory examples.custom_factory:make_env
"""

from envport.demo import CounterEnvironment


def make_env():
    return CounterEnvironment()
