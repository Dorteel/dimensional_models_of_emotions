"""Import/interface checks for the extraction scaffold; no VLM is executed."""

import copy
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from extraction_pipeline.api_models import APIModel
from extraction_pipeline.emotion_estimation import estimator
from extraction_pipeline.local_models import OllamaModel
from extraction_pipeline.model_execution import ModelExecutor
from extraction_pipeline.prototypical_emotion_generation import generator


class PipelineImports(unittest.TestCase):
    def test_each_pipeline_imports_independently_without_model_or_ontology_sdks(self):
        for pipeline, other in (
            ("prototypical_emotion_generation", "emotion_estimation"),
            ("emotion_estimation", "prototypical_emotion_generation"),
        ):
            with self.subTest(pipeline=pipeline):
                entry = "generator" if pipeline == "prototypical_emotion_generation" else "estimator"
                code = f"""
import importlib
import importlib.abc
import sys

blocked = (
    'owlready2', 'ontology', 'gui', 'ollama', 'local_llms', 'agentic_extraction',
    'extraction_pipeline.{other}',
)
class BlockImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == prefix or fullname.startswith(prefix + '.') for prefix in blocked):
            raise ImportError('Unexpected dependency: ' + fullname)

sys.meta_path.insert(0, BlockImports())
for name in (
    'extraction_pipeline.{pipeline}.{entry}',
    'extraction_pipeline.{pipeline}.evaluation',
    'extraction_pipeline.{pipeline}.prompts',
    'extraction_pipeline.local_models',
    'extraction_pipeline.api_models',
):
    importlib.import_module(name)
"""
                result = subprocess.run(
                    [sys.executable, "-c", code], cwd=ROOT,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                    capture_output=True, text=True, timeout=15,
                )
                self.assertEqual(result.returncode, 0, result.stderr)


class ModelInterfaces(unittest.TestCase):
    def test_local_and_api_placeholders_accept_the_shared_execution_interface(self):
        for model in (OllamaModel("local-test"), APIModel("remote-test")):
            with self.subTest(model=type(model).__name__):
                self.assertIsInstance(model, ModelExecutor)
                with self.assertRaisesRegex(NotImplementedError, "execution"):
                    model.execute(
                        "test only", images=[Path("unread-image.png")],
                        options={"temperature": 0},
                    )

    def test_executor_protocol_accepts_an_independent_implementation(self):
        class FakeModel:
            def execute(self, prompt, *, images=(), options=None):
                return "test response"

        model = FakeModel()
        self.assertIsInstance(model, ModelExecutor)
        self.assertEqual(model.execute("test"), "test response")


class DomainContract(unittest.TestCase):
    def test_existing_research_models_round_trip_without_value_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ("circumplex", "pad", "plutchik_model", "vector_model"):
                with self.subTest(domain=name):
                    source = ROOT / "domains" / name / f"{name}.yaml"
                    original_bytes = source.read_bytes()
                    expected = yaml.safe_load(original_bytes)
                    generated_input = generator.load_domain_model(source)
                    estimated_input = estimator.load_domain_model(source)
                    self.assertEqual(generated_input, expected)
                    self.assertEqual(estimated_input, expected)
                    output = Path(directory) / f"{name}.yaml"
                    generator.save_domain_model(generated_input, output)
                    self.assertEqual(yaml.safe_load(output.read_text(encoding="utf-8")), expected)
                    self.assertEqual(estimator.load_domain_model(output), expected)
                    self.assertEqual(source.read_bytes(), original_bytes)

    def test_serializer_retains_unknown_metadata_and_null_or_numeric_values(self):
        domain = generator.load_domain_model(ROOT / "domains/pad/pad.yaml")
        # Additional caller data must pass through without inventing new fields.
        domain["notes"] = "Multiple lines\nUnicode: émotion"
        domain["extra_metadata"] = {"unknown": None, "values": [1, -0.125, True]}
        before = copy.deepcopy(domain)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.yaml"
            generator.save_domain_model(domain, path)
            for load in (generator.load_domain_model, estimator.load_domain_model):
                self.assertEqual(load(path), before)
        self.assertEqual(domain, before)

    def test_serializer_refuses_to_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "existing.yaml"
            path.write_text("existing data", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                generator.save_domain_model({}, path)
            self.assertEqual(path.read_text(encoding="utf-8"), "existing data")

    def test_loaders_reject_non_mapping_documents(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.yaml"
            for text in ("", "- not a domain\n", "just a string\n"):
                path.write_text(text, encoding="utf-8")
                for load in (generator.load_domain_model, estimator.load_domain_model):
                    with self.subTest(loader=load.__module__, document=text):
                        with self.assertRaisesRegex(ValueError, "mapping"):
                            load(path)

    def test_loaders_use_safe_yaml(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unsafe.yaml"
            path.write_text("!!python/object/apply:builtins.str [unsafe]\n", encoding="utf-8")
            for load in (generator.load_domain_model, estimator.load_domain_model):
                with self.assertRaises(yaml.constructor.ConstructorError):
                    load(path)


class DeferredOperations(unittest.TestCase):
    def test_generation_and_estimation_do_not_call_models_or_mutate_domains(self):
        domain = generator.load_domain_model(ROOT / "domains/pad/pad.yaml")
        before = copy.deepcopy(domain)
        model = Mock(spec=ModelExecutor)
        with self.assertRaisesRegex(NotImplementedError, "Prototype generation"):
            generator.generate(domain, model)
        with self.assertRaisesRegex(NotImplementedError, "Emotion estimation"):
            estimator.estimate(Path("unread-image.png"), domain, model)
        model.execute.assert_not_called()
        self.assertEqual(domain, before)

    def test_observed_result_contract_does_not_choose_a_storage_schema(self):
        observation = estimator.ObservedInstance(
            image=Path("unread-image.png"), domain_id="pad",
            coordinates={"pleasure": 0.25, "arousal": -0.5, "dominance": 0.0},
        )
        self.assertEqual(observation.domain_id, "pad")
        self.assertEqual(observation.coordinates["pleasure"], 0.25)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "observation.yaml"
            with self.assertRaisesRegex(NotImplementedError, "serialization"):
                estimator.save_observation(observation, output)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
