"""Base helpers for constructing Strands Agents from the declarative agents.yaml config.

Wires two distinct Strands concepts per agent:
- tools: plain @tool callables passed directly to Agent(tools=[...]).
- skills: Agent Skills (SKILL.md packages under ./skills/) loaded on demand
  via the AgentSkills plugin, so instructions don't bloat the system prompt.
"""
from __future__ import annotations

from pathlib import Path

import yaml
from strands import Agent
from strands.vended_plugins.skills import AgentSkills

from src.agents.model_provider import get_model
from src.tools import get_tools

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_PATH = _REPO_ROOT / "config" / "agents.yaml"
_SKILLS_DIR = _REPO_ROOT / "skills"


def _load_agent_config(agent_key: str) -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    if agent_key not in config:
        raise KeyError(f"No config found for agent '{agent_key}' in {_CONFIG_PATH}")
    return config[agent_key]


def build_agent(agent_key: str, system_prompt: str | None = None) -> Agent:
    """Build a Strands Agent wired to the tools/skills declared for it in config/agents.yaml."""
    cfg = _load_agent_config(agent_key)
    tools = get_tools(*cfg.get("tools", []))

    plugins = []
    skill_names = cfg.get("skills", [])
    if skill_names:
        skill_paths = [str(_SKILLS_DIR / name) for name in skill_names]
        plugins.append(AgentSkills(skills=skill_paths))

    return Agent(
        model=get_model(),
        tools=tools,
        plugins=plugins,
        system_prompt=system_prompt or cfg.get("description", ""),
    )
