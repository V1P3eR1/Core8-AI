import json

from agents.base import BaseAgent, AgentConfig


_AGENTS: dict[str, BaseAgent] = {}


def load_agent(row: dict) -> BaseAgent:
    raw_allowed = row.get("allowed_tools")
    config = AgentConfig(
        id=row["id"],
        name=row["name"],
        description=row["description"] or "",
        model=row["model"],
        system_prompt=row["system_prompt"] or "",
        allowed_tools=json.loads(raw_allowed) if raw_allowed else None,
    )
    agent = BaseAgent(config)
    _AGENTS[config.id] = agent
    return agent


def get_agent(agent_id: str) -> BaseAgent | None:
    return _AGENTS.get(agent_id)


def list_agents() -> list[BaseAgent]:
    return list(_AGENTS.values())
