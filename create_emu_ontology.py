from owlready2 import *

onto = get_ontology("http://example.org/conceptual-space-emotion.owl#")

with onto:
    # ---------- Classes ----------
    class Context(Thing):
        pass

    class SimSensParameter(Thing):
        """Similarity sensitivity parameter."""
        pass

    class ConceptualSpace(Thing):
        pass

    class Concept(Thing):
        pass

    class Emotion(Concept):
        pass

    class Instance(Thing):
        pass

    class PrototypicalInstance(Instance):
        pass

    class Point(Thing):
        pass

    class Definition(Thing):
        pass

    class KnowledgeRepository(Thing):
        pass

    class Region(Thing):
        pass

    class ContrastClass(Region):
        pass

    class ConvexRegion(Region):
        pass

    class Domain(Thing):
        pass

    class QualityDimension(Thing):
        pass

    class ActionUnit(Thing):
        pass

    # ---------- Object properties ----------
    class hasContext(ObjectProperty):
        domain = [ConceptualSpace]
        range = [Context]

    class hasSimParam(ObjectProperty):
        domain = [ConceptualSpace]
        range = [SimSensParameter]

    class hasContrastClass(ObjectProperty):
        domain = [ConceptualSpace]
        range = [ContrastClass]

    class hasInstance(ObjectProperty):
        domain = [ConceptualSpace]
        range = [Instance]

    class hasConcept(ObjectProperty):
        domain = [ConceptualSpace]
        range = [Concept]

    class hasDomain(ObjectProperty):
        domain = [ConceptualSpace]
        range = [Domain]

    class hasRegion(ObjectProperty):
        domain = [Concept]
        range = [ConvexRegion]

    class hasPrototypicalInstance(ObjectProperty):
        domain = [Concept]
        range = [PrototypicalInstance]

    class definedBy(ObjectProperty):
        domain = [Point]
        range = [Definition]

    class hasDefinition(ObjectProperty):
        domain = [PrototypicalInstance]
        range = [Definition]

    class hasSource(ObjectProperty):
        domain = [Definition]
        range = [KnowledgeRepository]

    class describedBy(ObjectProperty):
        namespace = onto.get_namespace("https://w3id.org/def/orka#")
        domain = [Emotion]
        range = [KnowledgeRepository]

    class hasActionUnit(ObjectProperty):
        domain = [Emotion]
        range = [ActionUnit]

    class correspondsTo(ObjectProperty):
        domain = [ConvexRegion]
        range = [Domain]

    class hasQualityDimension(ObjectProperty):
        domain = [ConvexRegion]
        range = [QualityDimension]

    # ---------- Data properties ----------
    class hasValue(DataProperty):
        domain = [Definition]
        range = [str]

    class isCircular(DataProperty, FunctionalProperty):
        domain = [QualityDimension]
        range = [bool]

    class hasMeasurementLevel(DataProperty, FunctionalProperty):
        domain = [QualityDimension]
        range = [str]

    class hasRange(DataProperty, FunctionalProperty):
        domain = [QualityDimension]
        range = [str]

    # ---------- Simple controlled vocabulary ----------
    # Measurement levels encoded as strings to stay close to the sketch:
    # {"nominal", "ratio", "interval", "ordinal", "categorical"}
    VALID_MEASUREMENT_LEVELS = {"nominal", "ratio", "interval", "ordinal", "categorical"}


# Save as RDF/XML OWL file
onto.save(file="emotional_ontology.owl", format="rdfxml")
print("Saved:", "emotional_ontology.owl")