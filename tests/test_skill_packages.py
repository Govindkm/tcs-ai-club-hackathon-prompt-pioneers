"""Validates every ./skills/* package against the real Strands Skill parser."""
from pathlib import Path

from strands.vended_plugins.skills import Skill

_SKILLS_DIR = Path(__file__).resolve().parents[1] / "skills"


def _skill_dirs():
    return [p for p in _SKILLS_DIR.iterdir() if p.is_dir() and (p / "SKILL.md").exists()]


def test_skills_directory_has_expected_packages():
    names = {p.name for p in _skill_dirs()}
    assert names == {
        "document-extraction",
        "completeness-validation",
        "explainable-scoring",
        "reviewer-workflow",
    }


def test_each_skill_md_parses_with_required_frontmatter():
    for skill_dir in _skill_dirs():
        skill = Skill.from_file(str(skill_dir))
        assert skill.name == skill_dir.name
        assert skill.description
