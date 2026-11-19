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
run the appropriate pipeline, then serialize its result. Within those pipelines,
only domain YAML I/O works today. There are no extraction prompts, algorithms,
evaluation metrics, model SDK dependencies, or ontology imports. Evaluation
modules and the two separate `prompts/` packages reserve their locations.

## Download and verify local VLMs

`local_models/download_models.py` uses the existing Ollama service's HTTP API,
independently of the still-deferred `OllamaModel.execute` adapter. It requires
no additional Python dependencies. Start Ollama first, then run from the
repository root:

```sh
python3 extraction_pipeline/local_models/download_models.py --list
python3 extraction_pipeline/local_models/download_models.py --pull qwen3_vl_2b --quant q4 q8
python3 extraction_pipeline/local_models/download_models.py --all --test-image imgs/angry.jpg
python3 extraction_pipeline/local_models/download_models.py --all --test-only --test-image imgs/angry.jpg
python3 extraction_pipeline/local_models/download_models.py --pull granite_vision_2b --quant q4 q8 --test-only --test-image imgs/angry.jpg --context 8192
```

`--all` selects nine variants: Q4/Q8 for Qwen3-VL 2B and 4B, Gemma 3 4B, and
Granite Vision 3.2 2B; Q4 for LLaVA-Phi3. `--quant q4` or `--quant q8` filters
them. `--pull` defaults to Q4 and accepts multiple family names. Tags,
quantizations, and vision projectors are verified in the registry before pulling;
installed tags are skipped. Unrelated models are preserved.

Weights stay in Ollama's standard storage. `model_dictionary.ods` contains one
row per variant; `local_models/model_results.json` stores metadata, manifests,
commands, image hashes, responses, failures, and memory snapshots. Sizes are
actual `/api/tags` artifact bytes / 1,000,000,000, including the projector.
They measure model bundles, not network traffic or deduplicated disk usage.
Parameter counts use `model_info.general.parameter_count` from the model GGUF
where available, with Ollama's rounded count as fallback; advertised sizes can differ.

`Downloaded` means registered locally; `Tested` additionally requires vision
support and a completed, nonempty image response. `Failed` records the failing
stage, including inference after a successful download. `Unavailable` means a
registry 404; blank metadata/status means not checked.
`Tested` records successful image-request execution, not description quality:
both Granite variants accepted the image but returned `unanswerable` for a
generic caption and a clothing-color question. Their Notes explicitly retain
this limitation. The other seven variants produced image-specific descriptions.

Image checks run sequentially: default context 4096 (`--context` overrides it),
batch 64, up to 96 output tokens, temperature 0. Granite's full-resolution test
image needs 7351 input tokens, so use context 8192 for that model. `--prompt`
can supply a concrete image-verification question. Previous test attempts remain
in the results and dictionary notes when retesting.
Checks try automatic placement, then CPU (`num_gpu=0`) on failure,
and unload each model. `--timeout` defaults to 600 seconds. Other loaded models
prevent testing and are not evicted. Memory snapshots describe these smoke tests;
larger contexts/images may need more memory, and description quality is not scored.

Official tag inventories: [Qwen3-VL](https://ollama.com/library/qwen3-vl/tags),
[Gemma 3](https://ollama.com/library/gemma3/tags),
[Granite Vision](https://ollama.com/library/granite3.2-vision/tags), and
[LLaVA-Phi3](https://ollama.com/library/llava-phi3/tags).
The legacy LLaVA-Phi3 `q4_0` tag reports `Q4_K_M` in its registry configuration;
the dictionary uses the installed model's reported quantization, not its suffix.

Run offline tests, then verify the completed setup against Ollama and LibreOffice:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s extraction_pipeline/local_models -p test_download_models.py -v
PYTHONDONTWRITEBYTECODE=1 python3 extraction_pipeline/local_models/verify_models.py
```

The live verifier checks model metadata, saved image responses/hashes, unloading,
and unrelated models, then reopens the ODS using a temporary LibreOffice profile.

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
