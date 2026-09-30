"""Shared adapter. Each role holds one fixed LangChain chat model."""

from dataclasses import dataclass


@dataclass
class AgentAdapter:
    role: str
    model_id: str
    # TODO: configured chat model instance bound at startup.


# TODO: run(adapter, state) helper issuing the model call for a node.
