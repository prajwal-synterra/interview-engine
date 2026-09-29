"""
Hierarchical Heterogeneous Graph Knowledge Tracing (HHGKT) Engine.
Document Reference: AIS-ARCH-2026-V3-MASTER / REPORT 5
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple
import math
from app.bkt_engine import BKTNode, SeniorityTier, MasteryStatus


class EdgeType(str, Enum):
    PREREQUISITE = "PREREQUISITE"      # Directed: from_skill -> to_skill
    CO_REQUISITE = "CO_REQUISITE"      # Bidirectional: skill_a <-> skill_b
    ABSTRACTION = "ABSTRACTION"        # Hierarchical: parent -> child


@dataclass
class GraphEdge:
    from_skill: str
    to_skill: str
    edge_type: EdgeType
    weight: float = 0.5               # Influence factor beta between 0.0 and 1.0


class KnowledgeGraph:
    """Directed Heterogeneous Knowledge Graph with Message Passing."""

    def __init__(self, seniority: SeniorityTier = SeniorityTier.MID):
        self.seniority = seniority
        self.nodes: Dict[str, BKTNode] = {}
        self.edges: List[GraphEdge] = []
        self.adjacency: Dict[str, List[GraphEdge]] = {}

    def add_skill(self, skill_code: str, custom_prior: Optional[float] = None) -> BKTNode:
        """Registers a skill node with its BKT engine."""
        node = BKTNode(skill_code=skill_code, seniority=self.seniority)
        if custom_prior is not None:
            node.p_l = max(0.01, min(0.99, custom_prior))
        self.nodes[skill_code] = node
        if skill_code not in self.adjacency:
            self.adjacency[skill_code] = []
        return node

    def add_dependency(self, from_skill: str, to_skill: str, edge_type: EdgeType, weight: float = 0.5):
        """Adds a directional or bidirectional dependency between two concepts."""
        assert from_skill in self.nodes, f"Skill {from_skill} not registered"
        assert to_skill in self.nodes, f"Skill {to_skill} not registered"
        
        edge = GraphEdge(from_skill=from_skill, to_skill=to_skill, edge_type=edge_type, weight=weight)
        self.edges.append(edge)
        self.adjacency[from_skill].append(edge)

        # If bidirectional co-requisite, register reverse edge as well
        if edge_type == EdgeType.CO_REQUISITE:
            rev_edge = GraphEdge(from_skill=to_skill, to_skill=from_skill, edge_type=edge_type, weight=weight)
            self.adjacency[to_skill].append(rev_edge)

    def propagate_mastery(self, source_skill: str) -> Dict[str, float]:
        """
        Executes Graph Message-Passing from a recently updated skill node.
        Propagates knowledge influence to outgoing neighbors.
        Returns a dict of {neighbor_skill: new_prior}.
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

            current_target_p = target_node.p_l
            weight = edge.weight

            # Calculate influence delta based on source mastery relative to neutral baseline (0.50)
            # If source is mastered (>0.85), it provides a positive boost
            # If source is deficient (<0.20), it dampens the neighbor's prior
            mastery_influence = (source_p - 0.50) * weight * 0.40

            new_p = current_target_p + mastery_influence
            target_node.p_l = max(0.05, min(0.95, round(new_p, 4)))
            updates[edge.to_skill] = target_node.p_l

        return updates

    def get_prerequisite_readiness(self, skill_code: str) -> Tuple[bool, List[str]]:
        """
        Checks if all prerequisites for a skill have been satisfied (P(L) >= 0.50).
        Prevents asking high-level questions when foundational concepts are unmastered.
        """
        missing_prereqs = []
        for edge in self.edges:
            if edge.to_skill == skill_code and edge.edge_type == EdgeType.PREREQUISITE:
                prereq_node = self.nodes.get(edge.from_skill)
                if prereq_node and prereq_node.p_l < 0.50:
                    missing_prereqs.append(edge.from_skill)

        is_ready = len(missing_prereqs) == 0
        return is_ready, missing_prereqs

    def get_next_recommended_skill(self) -> Optional[str]:
        """
        Selects the next optimal skill to interview based on:
        1. Readiness (prerequisites fulfilled)
        2. High measurement leverage (closest to decision boundary P(L) ≈ 0.50)
        """
        candidate_skills = []
        for code, node in self.nodes.items():
            if node.status != MasteryStatus.IN_PROGRESS:
                continue
            is_ready, _ = self.get_prerequisite_readiness(code)
            if is_ready:
                # Distance to 0.50 boundary (lower distance = higher information gain)
                uncertainty = 1.0 - abs(node.p_l - 0.50)
                candidate_skills.append((code, uncertainty))

        if not candidate_skills:
            return None

        # Sort by highest uncertainty (maximum information gain)
        candidate_skills.sort(key=lambda x: x[1], reverse=True)
        return candidate_skills[0][0]
