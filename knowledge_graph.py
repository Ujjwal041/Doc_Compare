"""
STEP 1 — Knowledge Graph Builder
Builds a pure NetworkX graph of PBM rules and relationships.
NO temporal metadata here — just WHAT the rules are.

Node types:
  Plan, Drug, CopayRule, PAREquirement, StepTherapyRule,
  Exclusion, CoverageLimit, SpecialCoverage

Edge types:
  HAS_COPAY_RULE, REQUIRES_PA, HAS_STEP_THERAPY,
  EXCLUDES, HAS_LIMIT, EXTENDS_COVERAGE
"""

import networkx as nx
import json
from datetime import datetime


class KnowledgeGraph:
    def __init__(self, plan_id: str):
        self.plan_id = plan_id
        self.G = nx.DiGraph()
        self._add_plan_node()

    def _add_plan_node(self):
        self.G.add_node(
            self.plan_id,
            node_type="Plan",
            label=self.plan_id,
        )

    # ── Copay Rules ───────────────────────────────────────────────

    def add_copay_rule(self, rule: dict) -> str:
        """Add a copay rule node and connect to plan."""
        rule_id = rule.get("rule_id", f"COPAY_{rule['drug_name'].upper()}")
        node_id = f"{self.plan_id}_{rule_id}"

        self.G.add_node(node_id,
            node_type    = "CopayRule",
            label        = f"{rule['drug_name']} → {rule['tier']} → ${rule.get('copay_amount', '?')}",
            drug_name    = rule.get("drug_name"),
            drug_ndc     = rule.get("drug_ndc"),
            tier         = rule.get("tier"),
            copay_amount = rule.get("copay_amount"),
            copay_unit   = rule.get("copay_unit", "per_fill"),
            days_supply  = rule.get("days_supply", 30),
            drug_type    = rule.get("drug_type"),
            condition    = rule.get("condition"),
            section_ref  = rule.get("section_reference"),
        )

        self.G.add_edge(self.plan_id, node_id,
            relation = "HAS_COPAY_RULE"
        )
        return node_id

    # ── PA Requirements ───────────────────────────────────────────

    def add_pa_requirement(self, rule: dict) -> str:
        rule_id = rule.get("rule_id", f"PA_{rule['drug_name'].upper()}")
        node_id = f"{self.plan_id}_{rule_id}"

        self.G.add_node(node_id,
            node_type       = "PAREquirement",
            label           = f"{rule['drug_name']} → PA {'Required' if rule.get('pa_required') else 'Not Required'}",
            drug_name       = rule.get("drug_name"),
            drug_ndc        = rule.get("drug_ndc"),
            pa_required     = rule.get("pa_required", True),
            pa_criteria     = rule.get("pa_criteria"),
            pa_duration_months = rule.get("pa_duration_months"),
            pa_waiver_condition = rule.get("pa_waiver_condition"),
            reject_code     = rule.get("reject_code", "75"),
            section_ref     = rule.get("section_reference"),
        )

        self.G.add_edge(self.plan_id, node_id,
            relation = "REQUIRES_PA"
        )
        return node_id

    # ── Step Therapy ──────────────────────────────────────────────

    def add_step_therapy(self, rule: dict) -> str:
        rule_id = rule.get("rule_id", f"STEP_{rule['target_drug'].upper()[:10]}")
        node_id = f"{self.plan_id}_{rule_id}"

        self.G.add_node(node_id,
            node_type           = "StepTherapyRule",
            label               = f"{rule['target_drug']} → try {rule.get('required_first_step','')} first",
            target_drug         = rule.get("target_drug"),
            required_first_step = rule.get("required_first_step"),
            trial_duration_days = rule.get("trial_duration_days"),
            documentation       = rule.get("documentation_needed"),
            reject_code         = rule.get("reject_code", "76"),
            section_ref         = rule.get("section_reference"),
        )

        self.G.add_edge(self.plan_id, node_id,
            relation = "HAS_STEP_THERAPY"
        )
        return node_id

    # ── Exclusions ────────────────────────────────────────────────

    def add_exclusion(self, rule: dict) -> str:
        rule_id = rule.get("rule_id", f"EXCL_{rule['drug_or_class'].upper()[:12]}")
        node_id = f"{self.plan_id}_{rule_id}"

        self.G.add_node(node_id,
            node_type           = "Exclusion",
            label               = f"EXCLUDED: {rule['drug_or_class']}",
            drug_or_class       = rule.get("drug_or_class"),
            examples            = rule.get("examples", []),
            reject_code         = rule.get("reject_code", "70"),
            exception_available = rule.get("exception_available", False),
            section_ref         = rule.get("section_reference"),
        )

        self.G.add_edge(self.plan_id, node_id,
            relation = "EXCLUDES"
        )
        return node_id

    # ── Coverage Limits ───────────────────────────────────────────

    def add_coverage_limit(self, rule: dict) -> str:
        rule_id = rule.get("rule_id", f"LIMIT_{rule.get('limit_type','').upper()}")
        node_id = f"{self.plan_id}_{rule_id}"

        self.G.add_node(node_id,
            node_type   = "CoverageLimit",
            label       = f"LIMIT: {rule.get('limit_type')} max {rule.get('max_value')}",
            limit_type  = rule.get("limit_type"),
            max_value   = rule.get("max_value"),
            applies_to  = rule.get("applies_to"),
            reject_code = rule.get("reject_code", "76"),
            section_ref = rule.get("section_reference"),
        )

        self.G.add_edge(self.plan_id, node_id,
            relation = "HAS_LIMIT"
        )
        return node_id

    # ── Special Coverages (Rider) ─────────────────────────────────

    def add_special_coverage(self, rule: dict) -> str:
        rule_id = rule.get("rule_id", f"SPEC_{rule.get('coverage_type','').upper()[:10]}")
        node_id = f"{self.plan_id}_{rule_id}"

        self.G.add_node(node_id,
            node_type             = "SpecialCoverage",
            label                 = f"RIDER: {rule.get('drug_class')} → ${rule.get('special_copay')}",
            coverage_type         = rule.get("coverage_type"),
            drug_class            = rule.get("drug_class"),
            special_copay         = rule.get("special_copay"),
            pa_required           = rule.get("pa_required"),
            step_therapy_waived   = rule.get("step_therapy_waived"),
            quantity_limit_waived = rule.get("quantity_limit_waived"),
            eligibility_criteria  = rule.get("eligibility_criteria"),
            section_ref           = rule.get("section_reference"),
        )

        self.G.add_edge(self.plan_id, node_id,
            relation = "EXTENDS_COVERAGE"
        )
        return node_id

    # ── Ingest extracted rules dict ───────────────────────────────

    def ingest_extracted_rules(self, rules: dict) -> dict:
        """
        Takes the output of extractor.py and adds all rules to the graph.
        Returns summary of nodes added.
        """
        added = {
            "copay_rules": [],
            "pa_requirements": [],
            "step_therapy_rules": [],
            "exclusions": [],
            "coverage_limits": [],
            "special_coverages": [],
        }

        for r in rules.get("copay_rules", []):
            nid = self.add_copay_rule(r)
            added["copay_rules"].append(nid)

        for r in rules.get("pa_requirements", []):
            nid = self.add_pa_requirement(r)
            added["pa_requirements"].append(nid)

        for r in rules.get("step_therapy_rules", []):
            nid = self.add_step_therapy(r)
            added["step_therapy_rules"].append(nid)

        for r in rules.get("exclusions", []):
            nid = self.add_exclusion(r)
            added["exclusions"].append(nid)

        for r in rules.get("coverage_limits", []):
            nid = self.add_coverage_limit(r)
            added["coverage_limits"].append(nid)

        for r in rules.get("special_coverages", []):
            nid = self.add_special_coverage(r)
            added["special_coverages"].append(nid)

        return added

    # ── Query ─────────────────────────────────────────────────────

    def get_all_rules(self) -> list:
        """Return all rule nodes connected to this plan."""
        rules = []
        for _, neighbor, edge_data in self.G.out_edges(self.plan_id, data=True):
            node_data = dict(self.G.nodes[neighbor])
            node_data["_node_id"] = neighbor
            node_data["_edge_relation"] = edge_data.get("relation")
            rules.append(node_data)
        return rules

    def get_rules_by_type(self, node_type: str) -> list:
        return [r for r in self.get_all_rules() if r.get("node_type") == node_type]

    def get_drug_rules(self, drug_name: str) -> list:
        """Get all rules for a specific drug name (case-insensitive partial match)."""
        drug_lower = drug_name.lower()
        results = []
        for rule in self.get_all_rules():
            for field in ["drug_name", "target_drug", "drug_or_class", "drug_class"]:
                val = rule.get(field, "") or ""
                if drug_lower in val.lower():
                    results.append(rule)
                    break
        return results

    def summary(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "total_nodes": self.G.number_of_nodes(),
            "total_edges": self.G.number_of_edges(),
            "copay_rules": len(self.get_rules_by_type("CopayRule")),
            "pa_requirements": len(self.get_rules_by_type("PAREquirement")),
            "step_therapy_rules": len(self.get_rules_by_type("StepTherapyRule")),
            "exclusions": len(self.get_rules_by_type("Exclusion")),
            "coverage_limits": len(self.get_rules_by_type("CoverageLimit")),
            "special_coverages": len(self.get_rules_by_type("SpecialCoverage")),
        }

    def save(self, path: str):
        data = nx.node_link_data(self.G)
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def load(self, path: str):
        with open(path) as f:
            data = json.load(f)
        self.G = nx.node_link_graph(data)
