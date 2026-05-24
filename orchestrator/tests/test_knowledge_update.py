from unittest import TestCase

from orchestration.knowledge_update import (
    format_knowledge_update_proposal,
    generate_knowledge_update_proposal,
)


class KnowledgeUpdateProposalTests(TestCase):
    def test_destination_none_has_no_approval_required(self) -> None:
        proposal = generate_knowledge_update_proposal(
            {
                "destination": "none",
                "suggested_target": "none",
                "suggested_entry_type": "none",
            },
            "update README",
        )

        self.assertEqual(proposal["destination"], "none")
        self.assertFalse(proposal["approval_required"])
        self.assertEqual(proposal["write_status"], "not_written")

    def test_e2e_test_like_outcome_suggests_test_scenarios_target(self) -> None:
        proposal = generate_knowledge_update_proposal(
            {
                "destination": "project_docs",
                "suggested_target": "docs/project-map.md",
                "suggested_entry_type": "decision",
            },
            "validate e2e checkout flow",
            findings=["Verification gate passed after targeted regression checks."],
            suggested_tests=["Run the E2E checkout regression flow."],
        )

        self.assertEqual(proposal["entry_type"], "test_scenario")
        self.assertEqual(proposal["suggested_target"], "docs/test-scenarios.md")
        self.assertTrue(proposal["approval_required"])
        self.assertEqual(proposal["write_status"], "not_written")

    def test_risk_security_outcome_suggests_risk_registry(self) -> None:
        proposal = generate_knowledge_update_proposal(
            {
                "destination": "ai_brain",
                "suggested_target": "AI-Brain reusable engineering notes",
                "suggested_entry_type": "decision",
            },
            "review auth token handling",
            findings=["Security risk: token handling must be reviewed before release."],
        )

        self.assertEqual(proposal["entry_type"], "risk")
        self.assertEqual(proposal["destination"], "both")
        self.assertIn("docs/risk-registry.md", proposal["suggested_target"])
        self.assertTrue(proposal["approval_required"])

    def test_reusable_engineering_pattern_suggests_ai_brain(self) -> None:
        proposal = generate_knowledge_update_proposal(
            {
                "destination": "ai_brain",
                "suggested_target": "AI-Brain reusable engineering notes",
                "suggested_entry_type": "decision",
            },
            "standardize shared formatter workflow",
            findings=["Reusable shared formatter pattern for orchestrator workflows."],
        )

        self.assertEqual(proposal["destination"], "ai_brain")
        self.assertIn("AI-Brain", proposal["suggested_target"])
        self.assertEqual(proposal["entry_type"], "decision")
        self.assertTrue(proposal["approval_required"])

    def test_secret_like_proposed_content_is_blocked_redacted(self) -> None:
        secret_value = "super-secret-token-123"
        proposal = generate_knowledge_update_proposal(
            {
                "destination": "ai_brain",
                "suggested_target": "AI-Brain reusable engineering notes",
                "suggested_entry_type": "decision",
            },
            "record reusable lesson",
            findings=[f"API_TOKEN={secret_value}"],
        )
        output = format_knowledge_update_proposal(proposal)

        self.assertEqual(proposal["write_status"], "not_written")
        self.assertNotIn(secret_value, output)
        self.assertIn("blocked or redacted", output)
