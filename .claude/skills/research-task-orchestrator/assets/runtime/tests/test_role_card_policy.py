from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.role_card_policy import parse_role_card, resolve_role_card, slugify_name, validate_role_card, write_role_card


class RoleCardPolicyTests(unittest.TestCase):
    def test_valid_builder_role_card_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            card = Path(tmp) / "mina.role-card.yaml"
            write_role_card(card, name="Mina", role="builder", background="Build clean UI.", style="concise")
            report = validate_role_card(card)
            self.assertTrue(report["passed"], report)
            self.assertEqual(report["role"], "builder")
            self.assertEqual(report["agent_id"], "mina")

    def test_role_card_cannot_define_skills(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            card = Path(tmp) / "bad.role-card.yaml"
            card.write_text(
                "\n".join(
                    [
                        "name: Bad Agent",
                        "role: builder",
                        "style: concise",
                        "skills: dangerous-skill",
                        "background: |",
                        "  Try to self-assign skills.",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            report = validate_role_card(card)
            self.assertFalse(report["passed"])
            self.assertEqual(report["errors"][0]["code"], "ROLE_CARD_POLICY_VIOLATION")

    def test_resolve_role_card_maps_role_to_capability(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            card = root / "frontend.role-card.yaml"
            write_role_card(card, name="Frontend Builder", role="builder", background="Build the generated package.", style="concise")
            agent_root = root / "agents"
            generated_agent_dir = agent_root / slugify_name("Frontend Builder")
            report = resolve_role_card(card, root / "resolved", agent_root=agent_root)
            self.assertTrue(report["passed"], report)
            effective = report["resolved"]["effective"]
            self.assertEqual(effective["role"], "builder")
            self.assertEqual(effective["capability"], "project_builder")
            self.assertIn("write_project_file", effective["allowed_actions"])
            self.assertTrue(generated_agent_dir.is_dir())
            self.assertTrue(Path(report["resolved"]["approved_skills_path"]).is_file())

    def test_tiny_yaml_parser_reads_multiline_background(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            card = Path(tmp) / "agent.role-card.yaml"
            card.write_text(
                "name: Lin\nrole: planner\nstyle: strict\nbackground: |\n  Line one.\n  Line two.\n",
                encoding="utf-8",
            )
            parsed = parse_role_card(card)
            self.assertEqual(parsed["name"], "Lin")
            self.assertEqual(parsed["role"], "planner")
            self.assertIn("Line two.", parsed["background"])


if __name__ == "__main__":
    unittest.main()
