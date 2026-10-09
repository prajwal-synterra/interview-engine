# pyrefly: ignore [missing-import]
"""
Hierarchical Heterogeneous Knowledge Graph (HHGKT) Engine.
Manages:
- Semantic dependencies (PREREQUISITE, CO_REQUISITE) between competency pillars
- Graph message passing (mastery propagation to downstream concepts)
- Prerequisite gates (prevents jumping to advanced topics prematurely)
- Active Information Gain (recommends next skill closest to decision boundary P(L) ≈ 0.50)
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple
from app.bkt_engine import BKTNode, SeniorityTier, MasteryStatus


class EdgeType(str, Enum):
    PREREQUISITE = "PREREQUISITE"      # Directed: from_skill -> to_skill
    CO_REQUISITE = "CO_REQUISITE"      # Bidirectional synergy: skill_a <-> skill_b
    ABSTRACTION = "ABSTRACTION"        # Hierarchical parent -> child


@dataclass
class GraphEdge:
    from_skill: str
    to_skill: str
    edge_type: EdgeType
    weight: float = 0.5               # Influence weight between 0.0 and 1.0


class KnowledgeGraph:
    """Directed Heterogeneous Knowledge Graph with Message Passing."""

    def __init__(self, seniority: SeniorityTier = SeniorityTier.MID):
        self.seniority = seniority
        self.nodes: Dict[str, BKTNode] = {}
        self.edges: List[GraphEdge] = []
        self.adjacency: Dict[str, List[GraphEdge]] = {}

    def add_skill(
        self,
        skill_code: str,
        custom_prior: Optional[float] = None,
        description: Optional[str] = None
    ) -> BKTNode:
        """Registers a skill node backed by its own BKT tracker."""
        node = BKTNode(skill_code=skill_code, seniority=self.seniority)
        if isinstance(custom_prior, (int, float)):
            node.p_l = max(0.01, min(0.99, float(custom_prior)))
        self.nodes[skill_code] = node
        if skill_code not in self.adjacency:
            self.adjacency[skill_code] = []
        return node

    def add_dependency(
        self,
        from_skill: str,
        to_skill: str,
        edge_type: EdgeType,
        weight: float = 0.5
    ):
        """Adds a directional or bidirectional dependency between two concepts."""
        assert from_skill in self.nodes, f"Skill '{from_skill}' not registered in graph"
        assert to_skill in self.nodes, f"Skill '{to_skill}' not registered in graph"

        edge = GraphEdge(from_skill=from_skill, to_skill=to_skill, edge_type=edge_type, weight=weight)
        self.edges.append(edge)
        self.adjacency[from_skill].append(edge)

        # If bidirectional co-requisite, register reverse edge
        if edge_type == EdgeType.CO_REQUISITE:
            rev_edge = GraphEdge(from_skill=to_skill, to_skill=from_skill, edge_type=edge_type, weight=weight)
            self.adjacency[to_skill].append(rev_edge)

    def propagate_mastery(self, source_skill: str) -> Dict[str, float]:
        """
        Executes Graph Message Passing from an updated skill node.
        Propagates knowledge influence to outgoing neighbors.
        If source is mastered (>0.50), neighbor gets a positive boost.
        If source is deficient (<0.50), neighbor's prior is dampened.
        """
        source_node = self.nodes.get(source_skill)
        if not source_node:
            return {}

        source_p = source_node.p_l
        updates: Dict[str, float] = {}

        for edge in self.adjacency.get(source_skill, []):
            target_node = self.nodes.get(edge.to_skill)
            if not target_node or target_node.status != MasteryStatus.IN_PROGRESS:
                continue

            # Influence delta relative to 0.50 neutral baseline
            mastery_influence = (source_p - 0.50) * edge.weight * 0.40
            new_p = target_node.p_l + mastery_influence

            # Clamp updated prior safely
            target_node.p_l = max(0.05, min(0.95, round(new_p, 4)))
            updates[edge.to_skill] = target_node.p_l

        return updates

    def get_prerequisite_readiness(self, skill_code: str) -> Tuple[bool, List[str]]:
        """
        Checks if all prerequisites for a skill are satisfied (P(L) >= 0.50).
        Prevents asking high-level questions when foundational concepts are weak.
        """
        missing_prereqs = []
        for edge in self.edges:
            if edge.to_skill == skill_code and edge.edge_type == EdgeType.PREREQUISITE:
                prereq_node = self.nodes.get(edge.from_skill)
                if prereq_node and prereq_node.p_l < 0.50:
                    missing_prereqs.append(edge.from_skill)

        is_ready = (len(missing_prereqs) == 0)
        return is_ready, missing_prereqs

    def get_next_recommended_skill(self) -> Optional[str]:
        """
        Active Information Gain: Selects the optimal next skill to interview:
        1. Must be IN_PROGRESS
        2. Must have all prerequisites satisfied
        3. Closest to P(L) ≈ 0.50 (maximum uncertainty = highest information gain)
        """
        candidate_skills = []
        for code, node in self.nodes.items():
            if node.status != MasteryStatus.IN_PROGRESS:
                continue
            is_ready, _ = self.get_prerequisite_readiness(code)
            if is_ready:
                # Distance to 0.50 boundary (lower distance = higher uncertainty)
                uncertainty = 1.0 - abs(node.p_l - 0.50)
                candidate_skills.append((code, uncertainty))

        if not candidate_skills:
            return None

        # Sort descending by uncertainty
        candidate_skills.sort(key=lambda x: x[1], reverse=True)
        return candidate_skills[0][0]


# Curated Semantic Ontology Dependencies across Foundational Competency Pillars
STANDARD_ONTOLOGY_DEPENDENCIES = [
    # Foundational Prerequisite edges (directed: from_skill -> to_skill)
    ("DATA_STRUCTURES_ALGORITHMS", "DISTRIBUTED_CACHING", EdgeType.PREREQUISITE, 0.75),
    ("DATA_STRUCTURES_ALGORITHMS", "DATABASE_MODELING_TRANSACTIONS", EdgeType.PREREQUISITE, 0.70),
    ("API_DESIGN_PROTOCOLS", "ASYNC_CONCURRENCY", EdgeType.PREREQUISITE, 0.65),
    ("ASYNC_CONCURRENCY", "EVENT_STREAMING_MESSAGING", EdgeType.PREREQUISITE, 0.80),
    ("DATABASE_MODELING_TRANSACTIONS", "DISTRIBUTED_CACHING", EdgeType.PREREQUISITE, 0.70),
    ("DATABASE_MODELING_TRANSACTIONS", "NOSQL_DISTRIBUTED_STORAGE", EdgeType.PREREQUISITE, 0.75),

    # Co-Requisite edges (bidirectional synergies)
    ("ASYNC_CONCURRENCY", "DISTRIBUTED_CACHING", EdgeType.CO_REQUISITE, 0.65),
    ("EVENT_STREAMING_MESSAGING", "DISTRIBUTED_CACHING", EdgeType.CO_REQUISITE, 0.60),
    ("AI_INFERENCE_ORCHESTRATION", "ASYNC_CONCURRENCY", EdgeType.CO_REQUISITE, 0.70),
    ("AI_INFERENCE_ORCHESTRATION", "API_DESIGN_PROTOCOLS", EdgeType.CO_REQUISITE, 0.60),
    ("CONTAINER_INFRASTRUCTURE", "EVENT_STREAMING_MESSAGING", EdgeType.CO_REQUISITE, 0.55),
    ("CONTAINER_INFRASTRUCTURE", "API_DESIGN_PROTOCOLS", EdgeType.CO_REQUISITE, 0.50),
    ("CLOUD_SECURITY_AUTH", "API_DESIGN_PROTOCOLS", EdgeType.CO_REQUISITE, 0.65),
]


def build_dynamic_pillar_graph(
    matched_pillars: List[Dict],
    seniority: SeniorityTier = SeniorityTier.MID
) -> KnowledgeGraph:
    """
    Constructs a connected KnowledgeGraph populated with the candidate's
    matched competency pillars and their semantic dependency edges.
    """
    graph = KnowledgeGraph(seniority=seniority)
    pillar_ids = []

    # Calibrate initial priors by seniority
    tier_prior = {
        SeniorityTier.STUDENT: 0.35,
        SeniorityTier.JUNIOR: 0.35,
        SeniorityTier.MID: 0.40,
        SeniorityTier.SENIOR_STAFF: 0.30
    }.get(seniority, 0.40)

    # 1. Register Nodes
    for p in matched_pillars:
        custom_node_prior = tier_prior
        if isinstance(p, dict):
            pid = p.get("pillar_id") or p.get("pillarId")
            name = p.get("name", pid)
        elif isinstance(p, (tuple, list)):
            pid = p[0]
            name = str(p[0])
            if len(p) > 1 and isinstance(p[1], (int, float)):
                custom_node_prior = float(p[1])
        elif isinstance(p, str):
            pid = p
            name = p
        else:
            continue

        if not pid:
            continue
        pillar_ids.append(pid)
        graph.add_skill(pid, custom_prior=custom_node_prior, description=name)

    # 2. Wire Ontology Edges
    active_set = set(pillar_ids)
    for from_s, to_s, edge_type, weight in STANDARD_ONTOLOGY_DEPENDENCIES:
        if from_s in active_set and to_s in active_set:
            graph.add_dependency(from_s, to_s, edge_type, weight=weight)

    # 3. Connectivity: If any node has no edges, bridge with nearest peer
    for pid in pillar_ids:
        if not graph.adjacency.get(pid):
            peers = [other for other in pillar_ids if other != pid]
            if peers:
                graph.add_dependency(pid, peers[0], EdgeType.CO_REQUISITE, weight=0.5)

    return graph
