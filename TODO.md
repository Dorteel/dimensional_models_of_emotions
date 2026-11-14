# Emotional Conceptual Spaces — TODO

_Last updated: 2026-11-10_

## Agreed conceptual decisions

- **Emotion dictionary:** one row per emotion concept; one pair of columns (`definition`, `source`) for each definition provider. No extra tabs. The emotion catalogue is a separate lightweight list.
- **Ontology:** each emotion is an OWL **subclass** of `Emotion`. Preserve the architecture and coding style of `create_ontology.py` (Owlready2). `Instance` has subclasses `PrototypicalInstance` and `ObservedInstance`.
- **Domain models:** psychological emotion models are domain models, organized by quality dimensions. Each included emotion has a model-specific prototype (with coordinates when available). Models, dimensions, and emotions can each have optional notes. Existing reference and VLM-generated domains use the same structure but retain distinct provenance.
- **Inputs:** LibreOffice `.ods` is human-editable; YAML is the portable backend format. Maintain equivalent information in both. Users can create their own models.
- **Architecture:** `sources/`, `ontology/`, `gui/`, `backend/`, `conceptual_space_generator/`. Ontology design remains a joint conceptual decision.

## Next session — immediate action

- [ ] **Ask Codex to revise `domains/build_domain_models.py`** so missing dimension/emotion definitions do **not** block export. Use the exact placeholder `no known definitions`.
- [ ] Generate `domains/MISSING_DEFINITIONS.md`, listing each unresolved definition, its domain/model and any known source reference so a human can look it up.
- [ ] For other missing required metadata (range, circularity, coordinates), **do not invent defaults**. Preserve unknowns and report them explicitly; decide how incomplete models are represented/exported.
- [ ] Generate matching `.ods` and `.yaml` for each model where structurally possible; ensure one is generated from the other, not maintained independently.
- [ ] Validate original source values, exact definitions, and `.ods` ↔ YAML consistency. Run `python3 domains/validate_domain_models.py` and report outcomes.

## Current repository state (from coding-agent reports; recheck in repo)

- [x] `PROJECT_OVERVIEW.md` repository audit created.
- [x] `sources/emotions/emotion_dictionary.ods` simplified: one sheet, 117 emotion concepts, paired definition/source columns, 167 definitions and 165 source references; 21 verification checks reported passing.
- [x] `sources/emotions/emotion_catalogue.ods` created; unchanged after dictionary simplification.
- [x] Builder/verifier scripts for the emotion tables created.
- [x] Domain Model `.ods` templates with optional notes for model, dimensions, emotions and YAML export; builder tested interactively after a Basic syntax fix.
- [x] Codex created `domains/drafts/` for Circumplex, PAD, Plutchik intensity, and Vector models; reported 39 passing validation checks, but **no official YAMLs yet** because definitions/metadata were missing.
- [x] `create_ontology.py` and `populate_ontology.py` revised in this chat; **integration with the actual repository has not been verified**.

## Ontology implementation and testing

- [ ] Confirm revised scripts are copied into the repository and match the final YAML produced by the domain builder.
- [ ] Create schema using `create_ontology.py`; populate from `sources/emotions/emotion_dictionary.ods` and `domains/*.yaml` using `populate_ontology.py`.
- [ ] Verify every emotion is a subclass of `Emotion`, every definition retains its source, and prototypes are instances of both `PrototypicalInstance` and their emotion class.
- [ ] Verify dimensions, notes, numeric coordinates, model provenance and idempotent regeneration.
- [ ] Preserve old conceptual-space classes (`ConceptualSpace`, `Domain`, `QualityDimension`, `Point`, `ConvexRegion`, etc.) and avoid silently introducing new semantics.
- [ ] Add reproducible ontology tests and exact run commands. Do not modify source data during population.

## Source and domain-model review

- [ ] Review `domains/GENERATION_REPORT.md` and new missing-definition report.
- [ ] Verify definitions from original literature for **valence, arousal, pleasure, dominance, intensity**; record references and avoid unsupported interpretations.
- [ ] Resolve ranges and circularity, especially for PAD and the distinction between circular Circumplex arrangement versus individual dimensions.
- [ ] Review Circumplex's 28 coordinates, PAD's 8 prototype coordinates, and incomplete Plutchik/Vector models.
- [ ] Keep discrete models (Ekman, Plutchik discrete, Mikels) out of a dimensional format unless a faithful representation is agreed.
- [ ] Optionally preserve known lexical/source ambiguities in `sources/emotions/source_issues.md`, separate from the simplified dictionary.

## Later milestones

- [ ] **GUI:** design standalone, modular web dashboard for browsing domains, inspecting/visualizing dimensions and prototypes, defining emotions, selecting models, and running experiments. Each module should have independent scripts.
- [ ] **Generation input template:** create a domain definition **without reference prototypes**, suitable for VLM-driven space generation. Support configurable temperature, seed, logits/probabilities, prompts/definitions, and other inference parameters as appropriate.
- [ ] **Backend + generator:** separate model execution from conceptual-space generation; generate model-specific prototypes and preserve provenance and experimental settings.
- [ ] **Evaluation:** compare generated spaces with reference psychological coordinates and test whether generated domains improve emotion recognition performance.

## Guardrails for future coding prompts

- Conceptual fidelity over convenient implementation. Resolve ontology decisions with the researcher rather than inventing them.
- Preserve original text, coordinates, identifiers and provenance. Record missing facts explicitly.
- Prefer minimal diffs, existing scripts, repeatable verification, and exact executable test commands.
