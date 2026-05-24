from unittest import TestCase
from agents.agent_decision import (
    normalize_agent_decision,
    format_agent_decision,
    format_agent_decision_list,
    aggregate_agent_decisions,
    format_aggregated_decision
)

class AgentDecisionTests(TestCase):
    def test_normalize_valid_decision(self):
        data = {
            "agent_role": "Security",
            "decision": "needs_changes",
            "confidence": "high",
            "risk_level": "medium",
            "findings": ["Found issue"],
            "required_fixes": ["Fix issue"],
            "suggested_tests": ["Test issue"],
            "blocked_reasons": [],
            "next_action": "apply fixes",
            "safety_notes": ["Note"]
        }
        norm = normalize_agent_decision(data)
        self.assertEqual(norm["decision"], "needs_changes")
        self.assertEqual(norm["confidence"], "high")
        self.assertEqual(norm["risk_level"], "medium")
        self.assertEqual(norm["findings"], ["Found issue"])

    def test_unknown_decision_normalizes_to_needs_context(self):
        data = {"decision": "maybe", "confidence": "super_high", "risk_level": "unknown"}
        norm = normalize_agent_decision(data)
        self.assertEqual(norm["decision"], "needs_context")
        self.assertEqual(norm["confidence"], "low")
        self.assertEqual(norm["risk_level"], "high")

    def test_missing_fields_get_safe_defaults(self):
        norm = normalize_agent_decision({})
        self.assertEqual(norm["decision"], "needs_context")
        self.assertEqual(norm["confidence"], "low")
        self.assertEqual(norm["risk_level"], "high")
        self.assertEqual(norm["findings"], [])
        self.assertEqual(norm["required_fixes"], [])
        self.assertEqual(norm["suggested_tests"], [])
        self.assertEqual(norm["blocked_reasons"], [])

    def test_block_decision_dominates_aggregation(self):
        d1 = {"decision": "approve", "agent_role": "A1"}
        d2 = {"decision": "block", "agent_role": "A2"}
        d3 = {"decision": "needs_changes", "agent_role": "A3"}
        agg = aggregate_agent_decisions([d1, d2, d3])
        self.assertEqual(agg["final_decision"], "block")

    def test_needs_changes_dominates_approve(self):
        d1 = {"decision": "approve", "agent_role": "A1"}
        d2 = {"decision": "needs_changes", "agent_role": "A2"}
        agg = aggregate_agent_decisions([d1, d2])
        self.assertEqual(agg["final_decision"], "needs_changes")

    def test_needs_context_works_when_no_stronger_exists(self):
        d1 = {"decision": "approve", "agent_role": "A1"}
        d2 = {"decision": "needs_context", "agent_role": "A2"}
        agg = aggregate_agent_decisions([d1, d2])
        self.assertEqual(agg["final_decision"], "needs_context")

    def test_risk_aggregation_picks_highest(self):
        d1 = {"risk_level": "low", "agent_role": "A1"}
        d2 = {"risk_level": "medium", "agent_role": "A2"}
        agg = aggregate_agent_decisions([d1, d2])
        self.assertEqual(agg["risk_level"], "medium")
        
        d3 = {"risk_level": "high", "agent_role": "A3"}
        agg = aggregate_agent_decisions([d1, d2, d3])
        self.assertEqual(agg["risk_level"], "high")

    def test_required_fixes_and_tests_deduped(self):
        d1 = {"required_fixes": ["Fix A", "Fix B"], "suggested_tests": ["Test A"], "agent_role": "A1"}
        d2 = {"required_fixes": ["Fix B", "Fix C"], "suggested_tests": ["Test A", "Test B"], "agent_role": "A2"}
        agg = aggregate_agent_decisions([d1, d2])
        self.assertEqual(agg["required_fixes"], ["Fix A", "Fix B", "Fix C"])
        self.assertEqual(agg["suggested_tests"], ["Test A", "Test B"])

    def test_formatted_decision_no_leak_secrets(self):
        d = {"decision": "approve", "findings": ["API_KEY=sk-ant-api03-abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef12"]}
        fmt = format_agent_decision(d)
        self.assertIn("blocked", fmt.lower())
        self.assertNotIn("sk-ant-api03", fmt)

    def test_format_aggregated_decision(self):
        agg = {
            "final_decision": "needs_changes",
            "risk_level": "medium",
            "confidence": "high",
            "agents_used": ["A1", "A2"],
            "required_fixes": ["Fix"],
            "suggested_tests": ["Test"],
            "next_action": "Apply fixes."
        }
        fmt = format_aggregated_decision(agg)
        self.assertIn("- Final decision: needs_changes", fmt)
        self.assertIn("- Risk: medium", fmt)
        self.assertIn("- Confidence: high", fmt)
        self.assertIn("- Agents: A1, A2", fmt)
        self.assertIn("- Required fixes: 1", fmt)
        self.assertIn("- Suggested tests: 1", fmt)
        self.assertIn("- Next action: Apply fixes.", fmt)
