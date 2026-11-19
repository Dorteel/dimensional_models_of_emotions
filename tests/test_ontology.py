"""End-to-end ontology checks; run with python3 -m unittest discover -s tests -v."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd
import yaml
from rdflib import BNode, Graph, Namespace, RDF, RDFS, OWL, Literal
from rdflib.compare import isomorphic

ROOT = Path(__file__).resolve().parents[1]
NS = Namespace('http://example.org/conceptual-space-emotion.owl#')


class OntologyIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        (cls.root / 'ontology').mkdir()
        for filename in ('create_ontology.py', 'populate_ontology.py'):
            shutil.copy(ROOT / 'ontology' / filename, cls.root / 'ontology' / filename)
        shutil.copytree(ROOT / 'domains', cls.root / 'domains')
        (cls.root / 'emotions').mkdir(parents=True)
        shutil.copy(ROOT / 'emotions/emotion_dictionary.ods', cls.root / 'emotions')
        cls.run_script('create_ontology.py')
        cls.schema = Graph().parse(cls.root / 'ontology/emotional_ontology.owl')
        cls.run_script('populate_ontology.py')
        cls.output = cls.root / 'ontology/emotional_ontology_populated.owl'
        cls.graph = Graph().parse(cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    @classmethod
    def run_script(cls, script, *args):
        subprocess.run([sys.executable, str(cls.root / 'ontology' / script), *args], check=True, cwd=cls.root, capture_output=True, text=True)

    def test_schema(self):
        for name in ('ConceptualSpace', 'Domain', 'QualityDimension', 'Point', 'Region', 'ConvexRegion', 'ContrastClass', 'Context', 'SimSensParameter'):
            self.assertIn((NS[name], RDF.type, OWL.Class), self.schema)
        for child, parent in [('Emotion', 'Concept'), ('PrototypicalInstance', 'Instance'), ('ObservedInstance', 'Instance')]:
            self.assertIn((NS[child], RDFS.subClassOf, NS[parent]), self.schema)
        self.assertFalse(list(self.graph.subjects(RDF.type, NS.ConvexRegion)))

    def test_dictionary_definitions_and_sources(self):
        import re
        rows = pd.read_excel(self.root / 'emotions/emotion_dictionary.ods', engine='odf', dtype=str).fillna('')
        for _, row in rows.iterrows():
            name = re.sub(r'[^a-z0-9]+', '_', row.iloc[0].strip().lower()).strip('_')
            name = 'n_' + name if name[0].isdigit() else name
            subject = NS[name]
            self.assertIn((subject, RDFS.subClassOf, NS.Emotion), self.graph)
            definitions = list(self.graph.objects(subject, NS.hasClassDefinition))
            for i in range(1, len(row), 2):
                value, source = str(row.iloc[i]).strip(), str(row.iloc[i + 1]).strip()
                if value and value != '-':
                    matches = [d for d in definitions if value in map(str, self.graph.objects(d, NS.hasValue))]
                    self.assertTrue(matches, (name, value))
                    if source and source != '-':
                        self.assertTrue(any(source in map(str, self.graph.objects(repo, RDFS.label)) for d in matches for repo in self.graph.objects(d, NS.hasSource)))

    def test_models_and_coordinates(self):
        for file in ('circumplex.yaml', 'pad.yaml', 'plutchik_model.yaml', 'vector_model.yaml'):
            model = yaml.safe_load((self.root / 'domains' / Path(file).stem / file).read_text())
            mid = model['id']
            domain = NS['domain_' + mid]
            self.assertIn((domain, RDF.type, NS.Domain), self.graph)
            if model.get('notes'):
                self.assertIn(model['notes'], map(str, self.graph.objects(domain, NS.hasNotes)))
            for dim in model['dimensions']:
                dimension = NS[f"dimension_{mid}_{dim['id']}"]
                self.assertIn((domain, NS.hasQualityDimension, dimension), self.graph)
                expected = dim['definition'] if dim['definition'] != 'undefined' else 'no known definitions'
                self.assertTrue(any(expected in map(str, self.graph.objects(d, NS.hasValue)) for d in self.graph.objects(dimension, NS.hasDefinition)))
                if dim['circular'] is None:
                    self.assertFalse(list(self.graph.objects(dimension, NS.isCircular)))
            for emotion in model['emotions']:
                eid = emotion['id']
                prototype = NS[f'prototype_{mid}_{eid}']
                self.assertIn((prototype, RDF.type, NS.PrototypicalInstance), self.graph)
                self.assertIn((prototype, RDF.type, NS[eid]), self.graph)
                self.assertIn((prototype, NS.belongsToDomain, domain), self.graph)
                self.assertIn((domain, NS.hasDomainPrototype, prototype), self.graph)
                self.assertIn(emotion['notes'], map(str, self.graph.objects(prototype, NS.hasNotes)))
                point = NS[f'point_{mid}_{eid}']
                self.assertIn((prototype, NS.hasPoint, point), self.graph)
                self.assertEqual(len(list(self.graph.objects(point, NS.hasCoordinate))), len(emotion['coordinates']))
                for dim, value in emotion['coordinates'].items():
                    coord = NS[f'coordinate_{mid}_{eid}_{dim}']
                    self.assertIn((point, NS.hasCoordinate, coord), self.graph)
                    self.assertIn((coord, NS.onQualityDimension, NS[f'dimension_{mid}_{dim}']), self.graph)
                    self.assertEqual(float(next(self.graph.objects(coord, NS.numericValue))), value)

    def test_generated_model_and_missing_coordinates(self):
        model = {
            'id': 'generated_test', 'name': 'Generated test', 'model_type': 'generated',
            'notes': 'Model run provenance',
            'dimensions': [
                {'id': 'x', 'name': 'X', 'min': None, 'max': None, 'circular': None},
                {'id': 'y', 'name': 'Y', 'min': None, 'max': None, 'circular': None},
            ],
            'emotions': [
                {'id': 'joy', 'coordinates': {'x': 0.125}, 'notes': 'coordinate source'},
                {'id': 'sadness'},
            ],
        }
        path = self.root / 'domains/generated_test/generated_test.yaml'
        path.parent.mkdir(parents=True)
        path.write_text(yaml.safe_dump(model))
        try:
            self.run_script('populate_ontology.py')
            graph = Graph().parse(self.output)
            domain = NS.domain_generated_test
            self.assertIn('generated', map(str, graph.objects(domain, NS.hasModelType)))
            self.assertIn((NS.prototype_generated_test_joy, NS.belongsToDomain, domain), graph)
            self.assertIn((NS.prototype_generated_test_sadness, NS.belongsToDomain, domain), graph)
            self.assertFalse(list(graph.objects(NS.prototype_generated_test_sadness, NS.hasPoint)))
            self.assertEqual(float(next(graph.objects(NS.coordinate_generated_test_joy_x, NS.numericValue))), 0.125)
            self.assertFalse(list(graph.subjects(RDF.type, NS.ConvexRegion)))
        finally:
            path.unlink()
            self.run_script('populate_ontology.py')

    def test_idempotency_and_reload(self):
        self.run_script('populate_ontology.py')
        self.assertTrue(isomorphic(self.graph, Graph().parse(self.output)))
        # Owlready2 reload in a fresh process, independent of its in-memory cache.
        code = 'from owlready2 import get_ontology; import pathlib,sys; o=get_ontology(pathlib.Path(sys.argv[1]).as_uri()).load(); assert o.Emotion and o.domain_pad'
        subprocess.run([sys.executable, '-c', code, str(self.output)], check=True)

    def test_flat_and_nested_models_have_equivalent_content(self):
        # Rebuild the pre-move layout in isolation. Moving files necessarily
        # changes the YAML-path provenance and its hashed helper identifiers.
        with tempfile.TemporaryDirectory() as directory:
            flat = Path(directory)
            (flat / 'ontology').mkdir()
            for filename in ('create_ontology.py', 'populate_ontology.py'):
                shutil.copy(self.root / 'ontology' / filename, flat / 'ontology' / filename)
            shutil.copytree(self.root / 'emotions', flat / 'emotions')
            (flat / 'domains').mkdir()
            for name in ('circumplex', 'pad', 'plutchik_model', 'vector_model'):
                shutil.copy(self.root / f'domains/{name}/{name}.yaml', flat / 'domains')
            for filename in ('create_ontology.py', 'populate_ontology.py'):
                subprocess.run([sys.executable, str(flat / 'ontology' / filename)], check=True, capture_output=True)
            before = Graph().parse(flat / 'ontology/emotional_ontology_populated.owl')

        def comparable(graph):
            result = Graph()
            helpers = set(graph.subjects(RDF.type, NS.Definition)) | set(graph.subjects(RDF.type, NS.KnowledgeRepository))
            def normalize(term):
                if term in helpers:
                    return BNode(str(term))
                if isinstance(term, Literal) and term.datatype and str(term).startswith('domains/'):
                    value = str(term)
                    for name in ('circumplex', 'pad', 'plutchik_model', 'vector_model'):
                        value = value.replace(f'domains/{name}/{name}.yaml', f'domains/{name}.yaml')
                    return Literal(value, datatype=term.datatype)
                return term
            for triple in graph:
                result.add(tuple(normalize(term) for term in triple))
            return result

        self.assertEqual(len(before), len(self.graph))
        self.assertTrue(isomorphic(comparable(before), comparable(self.graph)))


if __name__ == '__main__':
    unittest.main()
