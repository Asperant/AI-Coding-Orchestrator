import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from agents.ai_brain_context import build_ai_brain_context_pack, format_ai_brain_context_pack, format_ai_brain_guidance_for_codex

class AIBrainContextTests(TestCase):
    def test_builds_context_pack_from_sample_files(self):
        with TemporaryDirectory() as brain_tmp, TemporaryDirectory() as proj_tmp:
            brain_dir = Path(brain_tmp)
            proj_dir = Path(proj_tmp)
            
            # create global rules
            (brain_dir / "global_rules.md").write_text("Rule 1: Always be safe.\nRule 2: Don't leak.", encoding="utf-8")
            (brain_dir / "testing_strategy.md").write_text("Test with pytest.\nMock dependencies.", encoding="utf-8")
            
            # create project docs
            docs = proj_dir / "docs"
            docs.mkdir()
            (docs / "product-context.md").write_text("This is a special test app.\nUses React.", encoding="utf-8")
            
            pack = build_ai_brain_context_pack(
                task="test app",
                project_path=str(proj_dir),
                ai_brain_path=str(brain_dir),
                approved_paths=[str(proj_dir)],
                context_budget=5000
            )
            
            self.assertIn("global_rules.md", pack["files_read"])
            self.assertIn("product-context.md", pack["files_read"])
            self.assertIn("testing_strategy.md", pack["files_read"])
            
            fmt = format_ai_brain_context_pack(pack)
            self.assertIn("AI-Brain Context Pack:", fmt)
            self.assertIn("Rule 1:", fmt)
            self.assertIn("Test with pytest", fmt)
            self.assertIn("special test app", fmt)

    def test_missing_files_reported_not_fatal(self):
        with TemporaryDirectory() as proj_tmp, TemporaryDirectory() as brain_tmp:
            proj_dir = Path(proj_tmp)
            pack = build_ai_brain_context_pack(
                task="test app",
                project_path=str(proj_dir),
                ai_brain_path=brain_tmp,
                approved_paths=[str(proj_dir)]
            )
            self.assertNotIn("global_rules.md", pack["files_read"])
            self.assertIn("CORE-RULES.md", pack["files_missing"])
            self.assertIn("Context-Budget-Rules.md", pack["files_missing"])
            
    def test_secret_content_blocked(self):
        with TemporaryDirectory() as brain_tmp:
            brain_dir = Path(brain_tmp)
            (brain_dir / "global_rules.md").write_text("API_KEY=sk-ant-api03-abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef12", encoding="utf-8")
            
            pack = build_ai_brain_context_pack(
                task="test app",
                project_path="",
                ai_brain_path=str(brain_dir),
                approved_paths=[]
            )
            
            self.assertTrue(pack["blocked"])
            self.assertIn("global_rules.md", pack["files_read"])
            
            fmt = format_ai_brain_context_pack(pack)
            self.assertIn("Safety status: BLOCKED", fmt)
            self.assertNotIn("sk-ant-api03", fmt)

    def test_context_budget_enforced(self):
        with TemporaryDirectory() as brain_tmp:
            brain_dir = Path(brain_tmp)
            (brain_dir / "global_rules.md").write_text("A\n" * 200, encoding="utf-8")
            
            pack = build_ai_brain_context_pack(
                task="test app",
                project_path="",
                ai_brain_path=str(brain_dir),
                approved_paths=[],
                context_budget=100
            )
            
            self.assertEqual(len(pack["relevant_rules"]), 1)
            self.assertLessEqual(len(pack["relevant_rules"][0]), 150) # includes prefix length

    def test_format_ai_brain_guidance_for_codex_compacts_and_dedupes(self):
        pack = {
            "relevant_rules": ["Rule 1", "Rule 2", "Rule 1", "Rule 3", "Rule 4", "Rule 5", "Rule 6"],
            "testing_notes": ["Test with pytest"],
            "memory_notes": ["Sync memory"],
            "files_read": ["global_rules.md"]
        }
        fmt = format_ai_brain_guidance_for_codex(pack, max_chars=1800)
        self.assertIn("AI-Brain Guidance:", fmt)
        self.assertIn("- Operating rules:", fmt)
        self.assertIn("  - Rule 1", fmt)
        self.assertIn("  - Rule 5", fmt)
        self.assertNotIn("Rule 6", fmt) # Limited to 5 items
        self.assertEqual(fmt.count("Rule 1"), 1) # Deduplicated
        self.assertIn("- Testing expectations:", fmt)
        self.assertIn("  - Test with pytest", fmt)
        self.assertIn("- Memory sync:", fmt)
        self.assertIn("  - Sync memory", fmt)
        self.assertIn("- Context summary:", fmt)
        self.assertIn("  - Files read: global_rules.md", fmt)

    def test_format_ai_brain_guidance_for_codex_empty_fallback(self):
        pack = {"files_read": []}
        fmt = format_ai_brain_guidance_for_codex(pack)
        self.assertIn("AI-Brain Guidance:", fmt)
        self.assertIn("no task-relevant AI-Brain guidance found", fmt)
        self.assertNotIn("Operating rules:", fmt)

    def test_format_ai_brain_guidance_for_codex_strips_links(self):
        pack = {
            "relevant_rules": ["Check [[Project Map]]", "Read [Docs](url) here"]
        }
        fmt = format_ai_brain_guidance_for_codex(pack)
        self.assertIn("Check Project Map", fmt)
        self.assertNotIn("[[Project Map]]", fmt)
        self.assertIn("Read Docs here", fmt)
        self.assertNotIn("[Docs](url)", fmt)
