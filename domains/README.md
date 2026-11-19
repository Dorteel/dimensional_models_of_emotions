# Domain models

Each active model has a folder containing `<model_id>.ods` and `<model_id>.yaml`:

```text
domains/
├── create_custom_domain_model.ods
├── domain_model_template.ods
├── circumplex/        # 28 prototypes
├── pad/               # 8 prototypes
├── plutchik_model/    # dimensions only; no documented prototypes
├── vector_model/      # dimensions only; no documented prototypes
├── examples/yourdomainmodel/  # two example YAMLs; no matching ODS
├── ods_export.py
├── validate_domain_models.py
├── GENERATION_REPORT.md
└── MISSING_DEFINITIONS.md
```

The YAML schema and research definitions/coordinates are unchanged. `examples/` and any future `drafts/` are excluded from automatic ontology population. The two example YAMLs share one model ID and must not be imported together.

## Edit and export

1. Open `domains/create_custom_domain_model.ods` in LibreOffice with macros enabled. Use the existing Main form to record the model name, dimensions and optional prototypes.
2. Click **SAVE DOMAIN MODEL**. The workbook switches to DomainModel and asks you to review the complete record before saving.
3. Confirm the review. The action creates `domains/<model_id>/` beside the builder and saves `<model_id>.yaml` plus `<model_id>.ods`. The ODS contains only the completed DomainModel tab, using `domain_model_template.ods` for its layout; the builder keeps both original tabs.

Keep the builder beside `domain_model_template.ods`. Paths follow the document location. The existing SafeID convention supplies the folder and filenames (lowercase, with spaces/hyphens converted to underscores); the model's display name keeps its original case. Definitions, dimensions, coordinates and notes are saved in both formats using the existing YAML schema and validation. Replacing either existing model file requires explicit confirmation. The files are prepared together; a failed save attempts to restore the previous pair.

`domains/domain_model_template.ods` is a blank DomainModel layout without embedded macros. The saved single-sheet models and existing research ODS files have no embedded macros. Edit their DomainModel tab and re-export YAML with the Python exporter when needed. To export one of these files, including its existing unknown ranges/circularity:

```sh
python3 domains/ods_export.py --export domains/pad/pad.ods
```

This preserves the established Python exporter, including `unknown` → YAML `null`, and writes YAML beside the supplied ODS. A failed export leaves existing YAML intact. The interactive macro retains its stricter requirement for known ranges and circularity. No original-source regeneration command is retained.

The small `ods_export.py` module is necessary because the retained validator uses its LibreOffice session helpers, real Basic formatting functions and ODS-to-YAML export for independent re-export checks. Only those reusable parts of the former conversion tool were retained.

## Populate and validate

The dictionary and catalogue are now `emotions/emotion_dictionary.ods` and `emotions/emotion_catalogue.ods` at the repository root. All other original reference sources remain under `sources/`.

```sh
python3 ontology/create_ontology.py
python3 ontology/populate_ontology.py
python3 domains/validate_domain_models.py
python3 -m unittest discover -s tests -v
```

Named domain selection uses the standard `domains/<name>/<name>.yaml` layout, with names taken from the folders. `examples/`, `drafts/` and the two legacy example names are excluded:

```sh
python3 ontology/populate_ontology.py --list-domains
python3 ontology/populate_ontology.py --domains circumplex
python3 ontology/populate_ontology.py --domains circumplex pad
python3 ontology/populate_ontology.py --all-domains
python3 ontology/populate_ontology.py --domains  # shared dictionary only
```

`--list-domains` displays available names and paths without needing the schema or changing the output. `--all-domains` selects all models in that standard layout. Selected YAML files are validated before saving; invalid selected models or unknown names cause a clear error and leave the existing output intact. Invalid unselected YAML does not block a named selection. Model validity follows the existing importer rules; this does not certify scientific completeness or infer a missing reference/generated designation.

All selections populate the complete shared dictionary. Domain dimensions, prototypes, points, coordinates and their definitions/notes are included only for selected models. Each run starts from the schema in a fresh Owlready2 world and replaces `ontology/emotional_ontology_populated.owl`, so prior domain selections do not accumulate. Name order and repeated names do not change the resulting RDF graph.

With no selection flags, the existing recursive discovery of active `.yaml` and `.yml` files is unchanged, including legacy root-level files. Legacy explicit paths also remain supported, for example `python3 ontology/populate_ontology.py domains/pad/pad.yaml`. Selection flags are mutually exclusive and cannot be combined with explicit paths. Duplicate model IDs in separate YAML files remain errors. Keep new active models in their standard folders so both named selection and automatic discovery find them.

Validation compares all four research ODS/YAML pairs with their reference sources and the top-level dictionary/catalogue. It checks field equivalence, numeric fidelity, missing-definition records, real macro path helpers, exact YAML re-export and invalid coordinates. It is a reference-model regression suite, not a general scientific validator of arbitrary custom models. Validation checks that it leaves its input files unchanged.

The Save Domain Model regression tests run the real Basic action in LibreOffice, with dialogs answered automatically in temporary workbook copies:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/libreoffice -v
```

They check folder creation, ODS/YAML equality after reopening, definitions/notes and Unicode text, review cancellation, overwrite confirmation, validation failures, and rollback if installing the pair fails.

The ontology scripts and tests use the root `requirements.txt`. Export and domain validation additionally require LibreOffice and its Python UNO bridge. GUI loading tests are documented in `gui/README.md`.

`GENERATION_REPORT.md` preserves the historical model inventory, and `MISSING_DEFINITIONS.md` preserves unresolved research information. Both remain in place. Update documented facts and both model representations together when resolving a missing value; definitions or coordinates must not be invented.
