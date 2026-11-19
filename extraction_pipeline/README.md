# Extraction pipeline

Scaffolding for two independent VLM workflows:

- `prototypical_emotion_generation/`: standardized Domain Model → generated
  Domain Model with estimated emotion prototypes.
- `emotion_estimation/`: image + Domain Model → `ObservedInstance` with
  dimensional coordinates.

Each workflow owns its prompts, evaluation module, and domain/result I/O.
They share only `model_execution.ModelExecutor`, a structural Python protocol
with `execute(prompt, *, images=(), options=None) -> str`. Options are opaque
provider settings, reserved for later experiments such as temperature, logits,
and JSON Schema constraints. Provider support and response formats remain open.
`local_models.OllamaModel` and `api_models.APIModel` have this interface but raise
`NotImplementedError`; constructing or importing them does not run a model,
download anything, read credentials, or contact a service.

## Current interfaces

Both pipelines expose `load_domain_model(path)` in their entry-point modules.
It reads the existing `domains/<name>/<name>.yaml` mapping, including
`schema_version`, model metadata, `dimensions`, and `emotions` with coordinates
keyed by dimension ID. It checks only that the document is a mapping. Existing
domain validation remains part of preparing the input; no alternative schema,
default definitions, or coordinate normalization is introduced.

`prototypical_emotion_generation.generator` exposes:

- `generate(domain, model) -> dict`: unimplemented generation interface.
- `save_domain_model(domain, path)`: working YAML serializer using the existing
  contract. It preserves mapping values and unknown metadata, but not YAML
  comments or formatting. It requires an existing parent directory and refuses
  to overwrite an existing file.

`emotion_estimation.estimator` exposes:

- `estimate(image, domain, model) -> ObservedInstance`: unimplemented estimation
  interface.
- `ObservedInstance(image, domain_id, coordinates)`: an in-memory Python record;
  coordinate keys refer to the input dimension IDs. It has no OWL dependency.
- `save_observation(observation, path)`: serialization interface, currently
  raising `NotImplementedError` until an observed-result format is agreed.

The intended workflow is to load a validated domain, supply a model executor,
run the appropriate pipeline, then serialize its result. Only domain YAML I/O
works today. There are no prompts, extraction algorithms, evaluation metrics,
model SDK dependencies, or ontology imports. Evaluation modules and the two
separate `prompts/` packages reserve their respective locations.

## Before implementing generation

Agree which emotions to generate (existing prototype rows, the emotion
dictionary, or an explicit selection), and whether reference coordinates are
replaced or retained in a separately identified generated model. Agree how model
identity, prompts, settings, and provenance fit the existing domain metadata
without changing its schema. Define policies for missing estimates, unknown
dimension ranges, out-of-range values, and circular dimensions before choosing
response constraints or evaluation metrics.

For image estimation, observed-instance identity, provenance, persistence, and
any later ontology conversion also need agreement. Those decisions are deferred.

## Verification

From the repository root, with the existing PyYAML dependency installed:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_extraction_pipeline.py -v
```

Tests cover independent imports, model interfaces, unchanged domain values
through YAML loading/serialization, overwrite protection, and explicit deferred
operations. They do not call a model or require credentials.
