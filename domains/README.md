# Domain models

Each active model has a folder containing `<model_id>.ods` and `<model_id>.yaml`:

```text
domains/
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

For an interactive new model, open the root `create_custom_domain_model.ods` with LibreOffice macros enabled. Its SaveModel button copies form values into the DomainModel sheet; use LibreOffice **Save As** to save the workbook as `domains/<model_id>/<model_id>.ods`. ExportYAML saves the workbook and exports `<model_id>.yaml` beside it, confirming replacement if necessary. Paths are relative to the saved document.

The root `domain_model_template.ods` is a blank DomainModel layout without embedded macros. The existing research ODS files also have no embedded macros. To export one of these files, including its existing unknown ranges/circularity:

```sh
python3 domains/ods_export.py --export domains/pad/pad.ods
```

This preserves the established Python exporter, including `unknown` → YAML `null`, and writes YAML beside the supplied ODS. A failed export leaves existing YAML intact. The interactive macro retains its stricter requirement for known ranges and circularity. No original-source regeneration command is retained.

The small `ods_export.py` module is necessary because the retained validator uses its LibreOffice session helpers, real Basic formatting functions and ODS-to-YAML export for independent re-export checks. Only those reusable parts of the former conversion tool were retained.

## Populate and validate

The dictionary and catalogue are now `emotions/emotion_dictionary.ods` and `emotions/emotion_catalogue.ods` at the repository root. All other original reference sources remain under `sources/`.

```sh
python3 create_ontology.py
python3 populate_ontology.py
python3 domains/validate_domain_models.py
python3 -m unittest discover -s tests -v
```

Population recursively discovers active `.yaml` and `.yml` files. Explicit paths replace automatic selection, for example `python3 populate_ontology.py domains/pad/pad.yaml`. Duplicate model IDs are rejected. Root-level YAML remains supported for compatibility, but keep each active model in its own folder.

Validation compares all four research ODS/YAML pairs with their reference sources and the top-level dictionary/catalogue. It checks field equivalence, numeric fidelity, missing-definition records, real macro path helpers, exact YAML re-export and invalid coordinates. It is a reference-model regression suite, not a general scientific validator of arbitrary custom models. Validation checks that it leaves its input files unchanged.

The ontology scripts and tests use the root `requirements.txt`. Export and domain validation additionally require LibreOffice and its Python UNO bridge. GUI loading tests are documented in `gui/README.md`.

`GENERATION_REPORT.md` preserves the historical model inventory, and `MISSING_DEFINITIONS.md` preserves unresolved research information. Both remain in place. Update documented facts and both model representations together when resolving a missing value; definitions or coordinates must not be invented.
