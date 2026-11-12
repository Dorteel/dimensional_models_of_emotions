"""Populate the Owlready2 emotion ontology from the dictionary and domain YAML files.

Run create_ontology.py first. This script never modifies the inputs.
"""
from pathlib import Path
import hashlib
import re
import types

import pandas as pd
import yaml
from owlready2 import *

BASE_DIR = Path(__file__).resolve().parent
DICTIONARY_PATH = BASE_DIR / "sources/emotions/emotion_dictionary.ods"
DOMAINS_DIR = BASE_DIR / "domains"
ONTOLOGY_PATH = BASE_DIR / "owl/emotional_ontology.owl"
OUTPUT_PATH = BASE_DIR / "owl/emotional_ontology_populated.owl"


def safe_name(text: str) -> str:
    text = str(text).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    if not text:
        raise ValueError("An ontology identifier cannot be empty")
    return "n_" + text if text[0].isdigit() else text


def nonempty(value) -> bool:
    return value is not None and not pd.isna(value) and str(value).strip() not in {"", "-"}


def add_once(property_values, value):
    if value not in property_values:
        property_values.append(value)


def named_individual(onto, cls, name: str):
    existing = onto[name]
    if existing is not None:
        if isinstance(existing, ThingClass):
            raise ValueError(f"'{name}' already identifies a class")
        if cls not in existing.is_a:
            existing.is_a.append(cls)
        return existing
    return cls(name)


def add_definition(onto, subject, text, source=None, class_subject=False):
    """Keep the Definition individual and its provenance; annotate OWL classes."""
    if not nonempty(text):
        return
    text = str(text).strip()
    origin = str(source).strip() if nonempty(source) else ""
    token = hashlib.sha256((subject.name + "\0" + text + "\0" + origin).encode()).hexdigest()[:16]
    definition = named_individual(onto, onto.Definition, f"definition_{token}")
    definition.hasValue = [text]
    if origin:
        source_id = hashlib.sha256(origin.encode()).hexdigest()[:16]
        repository = named_individual(onto, onto.KnowledgeRepository, f"source_{source_id}")
        repository.label = [origin]
        add_once(definition.hasSource, repository)
    if class_subject:
        # OWL annotation properties can describe classes without turning them into individuals.
        add_once(onto.hasClassDefinition[subject], definition)
    else:
        add_once(subject.hasDefinition, definition)


def read_dictionary():
    if not DICTIONARY_PATH.is_file():
        raise FileNotFoundError(f"Emotion dictionary not found: {DICTIONARY_PATH}")
    sheets = pd.read_excel(DICTIONARY_PATH, sheet_name=None, engine="odf", dtype=str)
    if list(sheets) != ["Dictionary"]:
        raise ValueError("The emotion dictionary must have exactly one 'Dictionary' sheet")
    df = sheets["Dictionary"].fillna("")
    if df.shape[1] < 1 or (df.shape[1] - 1) % 2:
        raise ValueError("Expected Emotion plus adjacent definition/source column pairs")
    for i in range(1, df.shape[1], 2):
        if not str(df.columns[i]).lower().endswith("definition") or not str(df.columns[i + 1]).lower().endswith("source"):
            raise ValueError(f"Invalid definition/source column pair at columns {i + 1}-{i + 2}")
    return df


def read_domains():
    if not DOMAINS_DIR.is_dir():
        raise FileNotFoundError(f"Domain directory not found: {DOMAINS_DIR}")
    documents = []
    for path in sorted(DOMAINS_DIR.glob("*.yaml")) + sorted(DOMAINS_DIR.glob("*.yml")):
        with path.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        if not isinstance(data, dict):
            raise ValueError(f"{path}: expected a YAML mapping")
        if str(data.get("schema_version", "1.0")) != "1.0":
            raise ValueError(f"{path}: unsupported schema_version")
        if not data.get("name") or not isinstance(data.get("dimensions"), list):
            raise ValueError(f"{path}: missing name or dimensions")
        if not isinstance(data.get("emotions", []), list):
            raise ValueError(f"{path}: emotions must be a list")
        dimension_ids = set()
        for dimension in data["dimensions"]:
            if not isinstance(dimension, dict) or not dimension.get("id") or not dimension.get("name"):
                raise ValueError(f"{path}: each dimension needs an id and name")
            identifier = str(dimension["id"])
            if identifier in dimension_ids:
                raise ValueError(f"{path}: duplicate dimension {identifier}")
            dimension_ids.add(identifier)
            minimum, maximum = dimension.get("min"), dimension.get("max")
            if (isinstance(minimum, bool) or isinstance(maximum, bool)
                    or not isinstance(minimum, (float, int)) or not isinstance(maximum, (float, int))
                    or minimum >= maximum):
                raise ValueError(f"{path}: invalid range for {identifier}")
            if not isinstance(dimension.get("circular"), bool):
                raise ValueError(f"{path}: circular must be boolean for {identifier}")
        seen_emotions = set()
        for emotion in data["emotions"]:
            if not isinstance(emotion, dict) or not emotion.get("id"):
                raise ValueError(f"{path}: each emotion needs an id")
            emotion_id = safe_name(emotion["id"])
            if emotion_id in seen_emotions:
                raise ValueError(f"{path}: duplicate emotion {emotion_id}")
            seen_emotions.add(emotion_id)
            coordinates = emotion.get("coordinates")
            if not isinstance(coordinates, dict) or set(coordinates) != dimension_ids:
                raise ValueError(f"{path}: prototype {emotion_id} needs exactly the domain dimensions")
            for dimension in data["dimensions"]:
                value = coordinates[dimension["id"]]
                if (isinstance(value, bool) or not isinstance(value, (float, int))
                        or not dimension["min"] <= value <= dimension["max"]):
                    raise ValueError(f"{path}: {emotion_id} has an invalid coordinate for {dimension['id']}")
        documents.append((path, data))
    return documents


def main():
    ontology_path = ONTOLOGY_PATH
    if not ontology_path.is_file():
        # create_ontology.py currently saves into the working directory.
        ontology_path = BASE_DIR / "emotional_ontology.owl"
    if not ontology_path.is_file():
        raise FileNotFoundError("Base ontology not found. Run create_ontology.py first.")

    dictionary = read_dictionary()
    domains = read_domains()
    onto = get_ontology(ontology_path.as_uri()).load()
    emotions = {}

    for _, row in dictionary.iterrows():
        label = row.iloc[0]
        if not nonempty(label):
            continue
        identifier = safe_name(label)
        if identifier in emotions:
            raise ValueError(f"Duplicate emotion identifier in dictionary: {identifier}")
        existing = onto[identifier]
        if existing is not None and not isinstance(existing, ThingClass):
            raise ValueError(f"Legacy emotion individual '{identifier}' conflicts with the required class")
        if existing is None:
            with onto:
                emotion_class = types.new_class(identifier, (onto.Emotion,))
        else:
            emotion_class = existing
        if onto.Emotion not in emotion_class.is_a:
            raise ValueError(f"Existing class '{identifier}' is not an Emotion subclass")
        emotion_class.label = [str(label).strip()]
        emotions[identifier] = emotion_class
        for i in range(1, len(row), 2):
            add_definition(onto, emotion_class, row.iloc[i], row.iloc[i + 1], class_subject=True)

    for path, model in domains:
        model_id = safe_name(model.get("id") or model["name"])
        domain = named_individual(onto, onto.Domain, f"domain_{model_id}")
        domain.label = [str(model["name"])]
        domain.hasModelType = [str(model.get("model_type", "reference"))]
        if nonempty(model.get("notes")):
            add_once(domain.hasNotes, str(model["notes"]))
        add_definition(onto, domain, model.get("description"), str(path.relative_to(BASE_DIR)))
        dimensions = {}
        for item in model["dimensions"]:
            dim_id = str(item["id"])
            # Domain-scoped IDs avoid assuming same-named dimensions have the same semantics.
            dimension = named_individual(onto, onto.QualityDimension, f"dimension_{model_id}_{safe_name(dim_id)}")
            dimension.label = [str(item["name"])]
            dimension.hasRange = [f"min={item['min']},max={item['max']}"]
            dimension.isCircular = [item["circular"]]
            if nonempty(item.get("measurement_level")):
                dimension.hasMeasurementLevel = [str(item["measurement_level"])]
            if nonempty(item.get("notes")):
                add_once(dimension.hasNotes, str(item["notes"]))
            add_definition(onto, dimension, item.get("definition"), str(path.relative_to(BASE_DIR)))
            add_once(domain.hasQualityDimension, dimension)
            dimensions[dim_id] = dimension

        for item in model["emotions"]:
            emotion_id = safe_name(item["id"])
            if emotion_id not in emotions:
                raise ValueError(f"{path}: emotion '{emotion_id}' is absent from the dictionary")
            prototype = named_individual(onto, onto.PrototypicalInstance, f"prototype_{model_id}_{emotion_id}")
            add_once(prototype.is_a, emotions[emotion_id])
            prototype.label = [str(item.get("name") or item["id"])]
            add_once(prototype.belongsToDomain, domain)
            add_once(domain.hasDomainPrototype, prototype)
            if nonempty(item.get("notes")):
                add_once(prototype.hasNotes, str(item["notes"]))
            add_definition(onto, prototype, item.get("definition"), str(path.relative_to(BASE_DIR)))
            point = named_individual(onto, onto.Point, f"point_{model_id}_{emotion_id}")
            add_once(prototype.hasPoint, point)
            for dim_id, value in item["coordinates"].items():
                coordinate = named_individual(onto, onto.Coordinate, f"coordinate_{model_id}_{emotion_id}_{safe_name(dim_id)}")
                coordinate.onQualityDimension = [dimensions[dim_id]]
                coordinate.numericValue = [float(value)]
                add_once(point.hasCoordinate, coordinate)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    onto.save(file=str(OUTPUT_PATH), format="rdfxml")
    print(f"Emotions: {len(emotions)}; domains: {len(domains)}")
    print(f"Saved: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
