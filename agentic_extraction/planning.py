# ========================================================
# Ontology Builder
# --------------------------------------------------------
from rdflib import Graph, Namespace, RDF, RDFS, Literal, XSD
from pathlib import Path
from typing import List

import yaml

class OntologyBuilder:
    def __init__(self, base_uri):
        self.graph = Graph()
        self.path = Path(__file__).resolve().parent / "ontology.ttl"
        self.ns = Namespace(base_uri)

    def add_class(self, name, definition=None, parent=None):
        self.graph.add((self.ns[name], RDF.type, RDFS.Class))
        if definition:
            self.graph.add((self.ns[name], RDFS.comment, Literal(definition)))
        if parent:
            self.graph.add((self.ns[name], RDFS.subClassOf, self.ns[parent]))

    def add_property(self, name, domain=None, range=None, definition=None):
        self.graph.add((self.ns[name], RDF.type, RDF.Property))
        if domain:
            self.graph.add((self.ns[name], RDFS.domain, self.ns[domain]))
        if range:
            self.graph.add((self.ns[name], RDFS.range, self.ns[range]))
        if definition:
            self.graph.add((self.ns[name], RDFS.comment, Literal(definition)))

    def add_data_property(self, name, domain, datatype=XSD.string, definition=None):
        self.graph.add((self.ns[name], RDF.type, RDF.Property))
        self.graph.add((self.ns[name], RDFS.domain, self.ns[domain]))
        self.graph.add((self.ns[name], RDFS.range, datatype))
        if definition:
            self.graph.add((self.ns[name], RDFS.comment, Literal(definition)))

    def save(self, path=None):
        if not path: path = self.path
        self.graph.serialize(path, format="turtle")

    def load(self, path):
        self.graph.parse(path, format="turtle")

    def display(self):
        print(self.graph.serialize(format="turtle"))


class PlanningOntologyBuilder(OntologyBuilder):
    def __init__(self):
        super().__init__("http://example.org/planning#")

        # Planning Ontology Classes and Properties

        self.add_domain("A domain that encompasses a set of planning actions and their relationships.")
        self.add_action("An action that can be performed in a planning context.")
        self.add_pddltype("A type (of entity) that can be involved as parameters in planning actions or domains.")
        self.add_predicate("A relationship between one or multiple entities in the planning context.")
        self.add_actionprecondition("A relationship indicating that an action has a specific precondition.")
        self.add_actioneffect("A relationship indicating that an action has a specific effect.")
        self.add_problem("A specific planning problem, defined by a domain, initial state, and goal state.")
        self.add_state("A specific configuration of the world, defined by a set of predicates.")
        self.add_initial_state("The starting configuration of the world, defined by a set of predicates.")
        self.add_goal_state("The desired configuration of the world, defined by a set of predicates.")

        self.add_domain_has_action("A relationship indicating that a domain includes a specific action.")
        self.add_domain_has_pddltype("A relationship indicating that a domain includes a specific PDDL type.")
        self.add_domain_has_predicate("A relationship indicating that a domain includes a specific predicate.") 

        self.add_action_has_actionprecondition("A relationship indicating that an action includes a specific action precondition.")
        self.add_action_has_actioneffect("A relationship indicating that an action includes a specific action effect.")

        self.add_domain_has_problem("A relationship indicating that a domain includes a specific planning problem.")
        self.add_problem_has_initial_state("A relationship indicating that a planning problem has a specific initial state.")
        self.add_problem_has_goal_state("A relationship indicating that a planning problem has a specific goal state.")
        self.add_state_has_predicate("A relationship indicating that a state includes a specific predicate.")

        # Additional Classes and Properties
        self.add_capability("A capability that an agent can possess, enabling it to perform specific actions or achieve certain goals.")
        self.add_requires_capability("A relationship indicating that a specific action requires a certain capability to be performed.")
        self.add_has_intent("A relationship indicating that a specific action is associated with a certain intent or purpose.")
        self.add_has_argument("A relationship indicating that a specific predicate has a certain argument or parameter.")

    # Adding classes
    def add_domain(self, definition=None):
        self.add_class("PlanningDomain", definition)

    def add_problem(self, definition=None):
        self.add_class("PlanningProblem", definition)
    
    def add_pddltype(self, definition=None):
        self.add_class("PDDLType", definition)

    def add_action(self, definition=None):
        self.add_class("PlanningAction", definition)

    def add_actionprecondition(self, definition=None):
        self.add_class("ActionPrecondition", definition)

    def add_actioneffect(self, definition=None):
        self.add_class("ActionEffect", definition)

    def add_predicate(self, definition=None):
        self.add_class("PlanningPredicate", definition)

    def add_state(self, definition=None):
        self.add_class("PlanningState", definition)

    def add_initial_state(self, definition=None):
        self.add_class("InitialState", definition, parent="PlanningState")

    def add_goal_state(self, definition=None):
        self.add_class("GoalState", definition, parent="PlanningState")

    # Adding properties
    def add_domain_has_action(self, definition=None):
        self.add_property("hasAction", domain="PlanningDomain", range="PlanningAction", definition=definition)

    def add_domain_has_pddltype(self, definition=None):
        self.add_property("hasPDDLType", domain="PlanningDomain", range="PDDLType", definition=definition)

    def add_domain_has_predicate(self, definition=None):
        self.add_property("hasDomainPredicate", domain="PlanningDomain", range="PlanningPredicate", definition=definition)

    def add_action_has_actionprecondition(self, definition=None):
        self.add_property("hasActionPrecondition", domain="PlanningAction", range="ActionPrecondition", definition=definition)

    def add_action_has_actioneffect(self, definition=None):
        self.add_property("hasActionEffect", domain="PlanningAction", range="ActionEffect", definition=definition)

    def add_domain_has_problem(self, definition=None):
        self.add_property("hasProblem", domain="PlanningDomain", range="PlanningProblem", definition=definition)

    def add_problem_has_initial_state(self, definition=None):
        self.add_property("hasInitialState", domain="PlanningProblem", range="InitialState", definition=definition)

    def add_problem_has_goal_state(self, definition=None):
        self.add_property("hasGoalState", domain="PlanningProblem", range="GoalState", definition=definition)

    def add_state_has_predicate(self, definition=None):
        self.add_property("hasStatePredicate", domain="PlanningState", range="PlanningPredicate", definition=definition)

    # Adding additional classes
    def add_capability(self, definition=None):
        self.add_class("Capability", definition)

    def add_requires_capability(self, definition=None):
        self.add_property("requiresCapability", domain="PlanningAction", range="Capability", definition=definition)

    def add_has_intent(self, definition=None):
        self.add_data_property("hasIntent", domain="PlanningAction",  definition=definition)

    def add_has_argument(self, definition=None):
        self.add_data_property("hasArgument", domain="PlanningPredicate", definition=definition)

# ========================================================
# Competency Questions
# --------------------------------------------------------
from dataclasses import dataclass, field

@dataclass
class PlanningCompetencyQuestion:
    name: str
    text: str
    sparql: str
    prefixes: dict = field(default_factory=dict)
    arguments: List[str] = field(default_factory=list)

CQ_DOMAINS_AVAILABLE = PlanningCompetencyQuestion(
    name="available domains",
    text="What planning domains are known?",
    sparql="""
        SELECT ?domain WHERE {
            ?domain rdf:type planning:PlanningDomain .
        }
    """,
    arguments=[]
)

CQ_DOMAIN_ACTIONS = PlanningCompetencyQuestion(
    name="actions for a domain",
    text="What actions are available in this domain?",
    sparql="""
        SELECT ?domain ?action WHERE {
            ?domain rdf:type planning:PlanningDomain .
            ?action rdf:type planning:PlanningAction .
            ?domain planning:hasAction ?action .
        }
    """,
    arguments=["domain"]
)

CQ_ALL_ACTIONS = PlanningCompetencyQuestion(
    name="actions contained in the ontology",
    text="What actions are known?",
    sparql="""
    SELECT ?action WHERE {
            ?action rdf:type planning:PlanningAction .
        }
    """
)

CQ_ALL_ACTIONS_AND_INTENTS = PlanningCompetencyQuestion(
    name="actions contained in the ontology",
    text="What actions are known?",
    sparql="""
    SELECT ?action ?intent WHERE {
            ?action rdf:type planning:PlanningAction .
            ?action planning:hasIntent ?intent .
        }
    """
)

CQ_DOMAIN_TYPES = PlanningCompetencyQuestion(
    name="types for a domain",
    text="What types are available in this domain?",
    sparql="""
        SELECT ?domain ?type WHERE {
            ?domain rdf:type planning:PlanningDomain .
            ?type rdf:type planning:PDDLType .
            ?domain planning:hasPDDLType ?type .
        }
    """,
    arguments=["domain"]
)

CQ_DOMAIN_PREDICATES = PlanningCompetencyQuestion(
    name="predicates for a domain",
    text="What predicates are available in this domain?",
    sparql="""
        SELECT ?domain ?predicate WHERE {
            ?domain rdf:type planning:PlanningDomain .
            ?predicate rdf:type planning:PlanningPredicate .
            ?domain planning:hasPredicate ?predicate .
        }
    """,
    arguments=["domain"]
)

CQ_ALL_PREDICATES_AND_INTENTS = PlanningCompetencyQuestion(
    name="predicates contained in the ontology",
    text="What predicates are known?",
    sparql="""
    SELECT ?predicate ?intent WHERE {
            ?predicate rdf:type planning:PlanningPredicate .
            ?predicate planning:hasIntent ?intent .
        }
    """
)


CQ_ACTION_PRECONDITIONS = PlanningCompetencyQuestion(
    name="preconditions for an action",
    text="What preconditions are associated with this action?",
    sparql="""
        SELECT ?action ?precondition WHERE {
            ?action rdf:type planning:PlanningAction .
            ?precondition rdf:type planning:ActionPrecondition .
            ?action planning:hasActionPrecondition ?precondition .
        }
    """,
    arguments=["action"]
)

CQ_ACTION_EFFECTS = PlanningCompetencyQuestion(
    name="effects for an action",
    text="What effects are associated with this action?",
    sparql="""
        SELECT ?action ?effect WHERE {
            ?action rdf:type planning:PlanningAction .
            ?effect rdf:type planning:ActionEffect .
            ?action planning:hasActionEffect ?effect .
        }
    """,
    arguments=["action"]
)

CQ_PROBLEM_INITIAL_STATES = PlanningCompetencyQuestion(
    name="initial states for a problem",
    text="What initial states are associated with this planning problem?",
    sparql="""
        SELECT ?problem ?initialState WHERE {
            ?problem rdf:type planning:PlanningProblem .
            ?initialState rdf:type planning:InitialState .
            ?problem planning:hasInitialState ?initialState .
        }
    """,
    arguments=["problem"]
)

CQ_PROBLEM_GOAL_STATES = PlanningCompetencyQuestion(
    name="goal states for a problem",
    text="What goal states are associated with this planning problem?",
    sparql="""
        SELECT ?problem ?goalState WHERE {
            ?problem rdf:type planning:PlanningProblem .
            ?goalState rdf:type planning:GoalState .
            ?problem planning:hasGoalState ?goalState .
        }
    """,
    arguments=["problem"]
)

# ========================================================
# Knowledge Interface
# --------------------------------------------------------

class KnowledgeInterface:
    def __init__(self, builder):
        self.graph = builder.graph
        self.ns = builder.ns

    def ask(self, cq, **bindings):
        return self.graph.query(
            cq.sparql,
            initNs={"planning": self.ns, "rdf": RDF},
            initBindings={
                key: self.ns[value]
                for key, value in bindings.items()
            }
        )

# ========================================================
# Knowledge Graph Populator
# --------------------------------------------------------

class PlanningOntologyPopulator:
    def __init__(self, builder=None):
        self.builder = builder or PlanningOntologyBuilder()

    def populate(self, actions=None, predicates=None, types=None):
        if actions:
            self.load_actions(actions)
        if predicates:
            self.load_predicates(predicates)
        if types:
            self.load_types(types)

    def load_actions(self, path):
        """Load action instances and their metadata from YAML."""
        with open(path) as file:
            actions = yaml.safe_load(file)

        for name, data in actions.items():
            action = self.builder.ns[name]

            self.builder.graph.add((action, RDF.type, self.builder.ns.PlanningAction))
            self.builder.graph.add((action, self.builder.ns.hasIntent, Literal(data["intent"])))

            requirements = data["requires_capabilities"]

            # Normalize both YAML forms into a simple list.
            if isinstance(requirements, dict):
                requirements = requirements["any_of"]

            for capability_name in requirements:
                capability = self.builder.ns[capability_name]

                self.builder.graph.add((capability, RDF.type, self.builder.ns.Capability))
                self.builder.graph.add(
                    (action, self.builder.ns.requiresCapability, capability))
                
    def load_predicates(self, path):
        with open(path) as file:
            predicates = yaml.safe_load(file)

        for name, data in predicates.items():
            predicate = self.builder.ns[name]

            self.builder.graph.add((predicate, RDF.type, self.builder.ns.PlanningPredicate))
            self.builder.graph.add((predicate, self.builder.ns.hasIntent, Literal(data["intent"])))
            self.builder.graph.add((predicate, self.builder.ns.hasArgument, Literal(data["arguments"])))


# ========================================================
# Main Execution
# --------------------------------------------------------
if __name__ == "__main__":

    # Define paths for input files:
    actions_path = Path(__file__).resolve().parent / "data" / "actions.yaml"
    predicates_path = Path(__file__).resolve().parent / "data" / "predicates.yaml"

    # Build the ontology schema.
    builder = PlanningOntologyBuilder()

    # Create a populator that works on that ontology.
    populator = PlanningOntologyPopulator(builder)

    # Add action instances from YAML.
    populator.load_actions(actions_path)
    populator.load_predicates(predicates_path)

    # Inspect and save the result.
    builder.display()
    builder.save()

    # Create a knowledge interface to query the ontology.
    interface = KnowledgeInterface(builder)

    results_actions = interface.ask(CQ_ALL_ACTIONS_AND_INTENTS)
    results_predicates = interface.ask(CQ_ALL_PREDICATES_AND_INTENTS)
    
    for row in results_predicates:
        print(f"Predicate: {row.predicate} Intent: {row.intent})")