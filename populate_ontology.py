from pathlib import Path
import re
import pandas as pd
from owlready2 import *

BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "sources/emotion_definitions.csv"
ONTOLOGY_PATH = BASE_DIR / "emotional_ontology.owl"
OUTPUT_PATH = BASE_DIR / "emotional_ontology_populated.owl"

SOURCE_COLUMNS = {
    "apa_definition": "apa_definition_source",
    "sentiwordnet_definition": "sentiwordnet_definition_source",
    "cambridge_definition": "cambridge_definition_source",
}

def safe_name(text: str) -> str:
    text = str(text).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    if not text:
        text = "unnamed"
    if text[0].isdigit():
        text = "n_" + text
    return text

def valid_cell(value) -> bool:
    if pd.isna(value):
        return False
    value = str(value).strip()
    return value not in {"", "-", "nan", "None"}

def get_or_create_named(cls, name: str):
    existing = cls.instances()
    for inst in existing:
        if inst.name == name:
            return inst
    return cls(name)

def main():
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"CSV not found: {CSV_PATH}")
    if not ONTOLOGY_PATH.exists():
        raise FileNotFoundError(
            f"Ontology file not found: {ONTOLOGY_PATH}\n"
            "Create/export the base ontology first."
        )

    df = pd.read_csv(CSV_PATH)

    onto = get_ontology(ONTOLOGY_PATH.as_uri()).load()

    # Expected classes from your base ontology
    Emotion = onto.Emotion
    Definition = onto.Definition
    KnowledgeRepository = onto.KnowledgeRepository

    # Expected properties from your base ontology
    hasSource = onto.hasSource
    hasValue = onto.hasValue

    # 'describedBy' may live in the ORKA namespace, so we try both routes
    describedBy = getattr(onto, "describedBy", None)
    if describedBy is None:
        orka_ns = onto.get_namespace("https://w3id.org/def/orka#")
        describedBy = getattr(orka_ns, "describedBy", None)

    created_emotions = 0
    created_definitions = 0
    created_sources = 0

    for _, row in df.iterrows():
        if not valid_cell(row.get("emotion_label")):
            continue

        emotion_name = safe_name(row["emotion_label"])
        emotion = get_or_create_named(Emotion, emotion_name)
        created_emotions += 1

        # Keep the human-readable label
        if not getattr(emotion, "label", []):
            emotion.label = [str(row["emotion_label"]).strip()]

        # Optional synset, stored as comment for now since you said leave the rest
        if valid_cell(row.get("synset")) and not getattr(emotion, "comment", []):
            emotion.comment = [f"synset: {row['synset']}"]

        for def_col, src_col in SOURCE_COLUMNS.items():
            definition_text = row.get(def_col)
            source_text = row.get(src_col)

            if not valid_cell(definition_text):
                continue

            definition_name = safe_name(f"{emotion_name}_{def_col}")
            definition = get_or_create_named(Definition, definition_name)
            created_definitions += 1

            definition.hasValue = [str(definition_text).strip()]

            if definition not in getattr(emotion, "is_defined_by", []):
                # no-op placeholder if inverse exists in another version
                pass

            # Link emotion -> definition if the ontology supports it.
            # Your current ontology has hasDefinition only for PrototypicalInstance,
            # so for now we attach definitions through comments + source linkage and,
            # if available later, you can add a direct property like hasDefinition.
            if valid_cell(source_text):
                source_name = safe_name(str(source_text))
                source = get_or_create_named(KnowledgeRepository, source_name)
                created_sources += 1

                # Add label so the URL stays readable
                if not getattr(source, "label", []):
                    source.label = [str(source_text).strip()]

                definition.hasSource = [source]

                # Optional direct emotion -> source link if describedBy exists
                if describedBy is not None:
                    current = list(getattr(emotion, describedBy.python_name, []))
                    if source not in current:
                        setattr(emotion, describedBy.python_name, current + [source])

            # Store provenance in comments until a direct Emotion->Definition
            # property is added to the ontology
            note = f"{def_col}: {str(definition_text).strip()}"
            current_comments = list(getattr(emotion, "comment", []))
            if note not in current_comments:
                emotion.comment = current_comments + [note]

    onto.save(file=str(OUTPUT_PATH), format="rdfxml")

    print("Done.")
    print(f"Rows read: {len(df)}")
    print(f"Emotion rows processed: {created_emotions}")
    print(f"Definitions processed: {created_definitions}")
    print(f"Sources processed: {created_sources}")
    print(f"Saved populated ontology to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
