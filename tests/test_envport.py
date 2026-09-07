import copy
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from envport import ProbeSpec, StepResult, doctor, validate_trajectory
from envport.cli import main
from envport.demo import BrokenCounterEnvironment, CounterEnvironment


def statuses(result):
    return {item["name"]: item["status"] for item in result["checks"]}


class DoctorTests(unittest.TestCase):
    def test_good_demo(self):
        result = doctor(CounterEnvironment)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["summary"], {"pass": 10, "fail": 0, "skip": 0})

    def test_bad_demo_detects_three_real_defects(self):
        result = doctor(BrokenCounterEnvironment)
        self.assertEqual(result["status"], "fail")
        self.assertEqual({k for k, v in statuses(result).items() if v == "fail"},
                         {"reset_after_actions", "noop_grade", "reward_bounds"})
        json.dumps(result, allow_nan=False)

    def test_actual_state_transitions(self):
        env = CounterEnvironment()
        self.assertEqual(env.reset(7)["position"], 0)
        self.assertEqual(env.step({"move": "right"}).reward, 0)
        self.assertEqual(env.grade(), 0)
        env.step({"move": "right"})
        self.assertTrue(env.step({"move": "right"}).terminated)
        self.assertEqual(env.grade(), 1)
        self.assertEqual(env.reset(7)["position"], 0)
        env.close()
        with self.assertRaises(RuntimeError):
            env.observe()

    def test_shared_state_detected(self):
        class Shared(CounterEnvironment):
            state = {"position": 0}

            @property
            def position(self):
                return self.state["position"]

            @position.setter
            def position(self, value):
                self.state["position"] = value
        self.assertEqual(statuses(doctor(Shared))["cross_instance_isolation"], "fail")

    def test_missing_probe_skips(self):
        class NoProbe(CounterEnvironment):
            envport_probe = None
        result = doctor(NoProbe)
        self.assertEqual(statuses(result)["same_seed_reset"], "pass")
        self.assertEqual(statuses(result)["noop_grade"], "skip")
        self.assertEqual(result["summary"]["skip"], 7)

    def test_invalid_probe_fails(self):
        class BadProbe(CounterEnvironment):
            def envport_probe(self):
                return ProbeSpec(({},), ({},), reward_min=2, reward_max=1)
        result = doctor(BadProbe)
        self.assertEqual(statuses(result)["probe_contract"], "fail")
        self.assertEqual(statuses(result)["reward_bounds"], "skip")

    def test_noncallable_probe_fails(self):
        class InvalidProbe(CounterEnvironment):
            envport_probe = "invalid"
        result = doctor(InvalidProbe)
        self.assertEqual(result["status"], "fail")
        self.assertEqual(statuses(result)["probe_contract"], "fail")
        self.assertEqual(statuses(result)["reward_bounds"], "skip")

    def test_missing_close_is_reported(self):
        result = doctor(object)
        self.assertEqual(statuses(result)["cleanup"], "fail")
        cleanup = next(c for c in result["checks"] if c["name"] == "cleanup")
        self.assertIn("Closed 0 of 1", cleanup["detail"])

    def test_factory_reuse_rejected(self):
        env = CounterEnvironment()
        result = doctor(lambda: env)
        self.assertEqual(statuses(result)["interface"], "fail")
        self.assertTrue(env.closed)

    def test_cleanup_after_step_failure(self):
        created = []

        class Crashing(CounterEnvironment):
            def step(self, action):
                raise RuntimeError("deliberate step exception")

        def factory():
            env = Crashing()
            created.append(env)
            return env
        result = doctor(factory)
        self.assertEqual(result["status"], "fail")
        self.assertTrue(all(env.closed for env in created))

    def test_close_failure_reported(self):
        class BadClose(CounterEnvironment):
            def close(self):
                raise RuntimeError("close failed")
        self.assertEqual(statuses(doctor(BadClose))["cleanup"], "fail")

    def test_bad_interface_is_report_not_exception(self):
        self.assertEqual(statuses(doctor(object))["interface"], "fail")

    def test_step_return_type_checked(self):
        class WrongReturn(CounterEnvironment):
            def step(self, action):
                return {"observation": self.observe()}
        self.assertEqual(doctor(WrongReturn)["status"], "fail")

    def test_step_observation_mismatch_fails(self):
        class WrongObservation(CounterEnvironment):
            def step(self, action):
                result = super().step(action)
                return StepResult({"wrong": True}, result.reward, result.terminated)
        self.assertEqual(statuses(doctor(WrongObservation))["oracle_grade"], "fail")

    def test_reward_out_of_bounds(self):
        class BadReward(CounterEnvironment):
            def step(self, action):
                result = super().step(action)
                return StepResult(result.observation, 2, result.terminated)
        self.assertEqual(statuses(doctor(BadReward))["reward_bounds"], "fail")

    def test_nondeterministic_replay_detected(self):
        counter = 0

        class DifferentRuns(CounterEnvironment):
            def __init__(self):
                nonlocal counter
                super().__init__()
                counter += 1
                self.unique = counter

            def step(self, action):
                result = super().step(action)
                return StepResult(result.observation, self.unique / 100, result.terminated)
        self.assertEqual(statuses(doctor(DifferentRuns))["deterministic_replay"], "fail")


class TrajectoryTests(unittest.TestCase):
    def setUp(self):
        self.data = {"schema_version": "envport.trajectory.v1", "images": {"s1": "image.png"},
                     "steps": [{"action": {"move": "right"}, "reward": 0,
                                "token_ids": [1, 2], "logprobs": [-0.1, -0.2],
                                "loss_mask": [False, 1], "image_refs": ["s1"]}]}

    def test_valid(self):
        self.assertEqual(validate_trajectory(self.data)["status"], "pass")

    def test_text_only(self):
        self.data["images"] = {}
        self.data["steps"][0]["image_refs"] = []
        self.assertEqual(validate_trajectory(self.data)["status"], "pass")

    def test_malformed_top_level(self):
        for bad in (None, [], 2, "text", {}):
            with self.subTest(bad=bad):
                self.assertEqual(validate_trajectory(bad)["status"], "fail")

    def test_required_step_fields(self):
        for key in self.data["steps"][0]:
            data = copy.deepcopy(self.data)
            del data["steps"][0][key]
            with self.subTest(key=key):
                self.assertEqual(validate_trajectory(data)["status"], "fail")

    def test_lengths(self):
        self.data["steps"][0]["logprobs"] = [-1]
        self.assertEqual(statuses(validate_trajectory(self.data))["steps[0].token_lengths"], "fail")

    def test_token_types(self):
        for bad in ([True], [-1], [1.0], [], "1", None):
            with self.subTest(bad=bad):
                self.data["steps"][0]["token_ids"] = bad
                self.assertEqual(statuses(validate_trajectory(self.data))["steps[0].token_ids"], "fail")

    def test_mask_types(self):
        for bad in ([0.0, 1.0], [0, 2], [None, 1], "01"):
            with self.subTest(bad=bad):
                self.data["steps"][0]["loss_mask"] = bad
                self.assertEqual(statuses(validate_trajectory(self.data))["steps[0].loss_mask"], "fail")

    def test_nonfinite_and_boolean_numbers(self):
        for bad in (float("nan"), float("inf"), True, "0", 10 ** 1000):
            with self.subTest(bad_type=type(bad).__name__):
                self.data["steps"][0]["reward"] = bad
                self.data["steps"][0]["logprobs"] = [bad, -1]
                checks = statuses(validate_trajectory(self.data))
                self.assertEqual(checks["steps[0].reward"], "fail")
                self.assertEqual(checks["steps[0].logprobs"], "fail")

    def test_invalid_image_refs(self):
        for bad in (["absent"], ["s1", "s1"], [{}], [None], "s1", [""]):
            with self.subTest(bad=bad):
                self.data["steps"][0]["image_refs"] = bad
                self.assertEqual(statuses(validate_trajectory(self.data))["steps[0].image_refs"], "fail")

    def test_invalid_images(self):
        for bad in ([], None, {"": "x"}, {"s1": 1}, {"s1": ""}):
            with self.subTest(bad=bad):
                self.data["images"] = bad
                self.assertEqual(statuses(validate_trajectory(self.data))["images"], "fail")

    def test_invalid_action_and_termination(self):
        self.data["steps"][0]["action"] = {"value": float("inf")}
        self.data["steps"][0]["terminated"] = 1
        checks = statuses(validate_trajectory(self.data))
        self.assertEqual(checks["steps[0].action"], "fail")
        self.assertEqual(checks["steps[0].terminated"], "fail")


class CliTests(unittest.TestCase):
    def invoke(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(args)
        return code, out.getvalue(), err.getvalue()

    def test_good_and_bad_exit_codes(self):
        for demo, expected in (("good", 0), ("bad", 1)):
            code, out, err = self.invoke("doctor", "--demo", demo, "--format", "json")
            self.assertEqual(code, expected)
            self.assertEqual(json.loads(out)["schema_version"], "envport.report.v1")
            self.assertEqual(err, "")

    def test_factory(self):
        code, _, _ = self.invoke("doctor", "--factory", "envport.demo:CounterEnvironment")
        self.assertEqual(code, 0)

    def test_malformed_and_missing_factory_clean_error(self):
        for factory in ("https://example.test/code.py", "bad", "missing_module_xyz:factory", "envport.demo:no_such_name"):
            with self.subTest(factory=factory):
                code, out, err = self.invoke("doctor", "--factory", factory)
                self.assertEqual(code, 2)
                self.assertEqual(out, "")
                self.assertIn("envport:", err)
                self.assertNotIn("Traceback", err)

    def test_factory_import_error_is_clean(self):
        with patch("envport.cli.importlib.import_module", side_effect=RuntimeError("bad import")):
            code, _, err = self.invoke("doctor", "--factory", "custom:factory")
        self.assertEqual(code, 2)
        self.assertNotIn("Traceback", err)

    def test_noisy_factory_keeps_json_stdout_clean(self):
        def factory():
            print("environment diagnostic")
            return CounterEnvironment()
        with patch("envport.cli._factory", return_value=factory):
            code, out, err = self.invoke("doctor", "--factory", "custom:factory", "--format", "json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["status"], "pass")
        self.assertIn("environment diagnostic", err)

    def test_missing_file_clean_error(self):
        code, _, err = self.invoke("validate-trajectory", "/definitely/missing/envport.json")
        self.assertEqual(code, 2)
        self.assertNotIn("Traceback", err)

    def test_malformed_json_clean_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            for content in ('{', '{"reward":NaN}', '{"a":1,"a":2}', '\udcff'):
                with self.subTest(content=repr(content)):
                    path.write_bytes(content.encode("utf-8", errors="surrogatepass"))
                    code, _, err = self.invoke("validate-trajectory", str(path))
                    self.assertEqual(code, 2)
                    self.assertNotIn("Traceback", err)

    def test_output_json_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            code, _, _ = self.invoke("doctor", "--demo", "good", "--output", str(path))
            self.assertEqual(code, 0)
            original = path.read_text()
            self.assertEqual(json.loads(original)["status"], "pass")
            code, _, err = self.invoke("doctor", "--demo", "bad", "--output", str(path))
            self.assertEqual(code, 2)
            self.assertIn("FileExistsError", err)
            self.assertEqual(path.read_text(), original)

    def test_valid_json_with_bad_schema_exit_one(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad-schema.json"
            path.write_text("[]")
            code, out, _ = self.invoke("validate-trajectory", str(path), "--format", "json")
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(out)["status"], "fail")


if __name__ == "__main__":
    unittest.main()
