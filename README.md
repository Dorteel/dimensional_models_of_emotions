# Dimensional Models of Emotions

The emotion dictionary and catalogue are in `emotions/`. Reference sources remain in `sources/`; domain ODS/YAML pairs and the two ODS templates are in `domains/`. Ontology scripts and OWL files are in `ontology/`. The workflow is `emotions/ + domains/ → ontology/ → gui/`.

## Ontology and validation

Install the Python dependencies from `requirements.txt`, then run from the repository root:

```sh
python3 ontology/create_ontology.py
python3 ontology/populate_ontology.py
python3 -m unittest discover -s tests -v
python3 domains/validate_domain_models.py
```

Domain validation additionally requires LibreOffice and its Python UNO bridge. The ontology files are saved under `ontology/`. See [domain instructions](domains/README.md) for editing and export. Source-conversion scripts have been retired; the retained `domains/ods_export.py` supplies the export functions required by validation.

## GUI

```sh
python3 gui/server.py
```

Open `http://127.0.0.1:8765/`. The GUI dynamically reads `ontology/emotional_ontology_populated.owl` by default. See [GUI instructions and tests](gui/README.md).

## Running local models

sudo apt-get install zstd

curl -fsSL https://ollama.com/install.sh | sh

ollama pull qwen3:4b

pip install ollama