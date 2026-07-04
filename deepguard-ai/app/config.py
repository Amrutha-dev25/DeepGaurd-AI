import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

@dataclass
class AgentConfig:
    """Configuration used by all agents in the project."""
    model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    mcp_server_port: int = 8090
    max_iterations: int = 3
    pii_redaction_enabled: bool = True
    injection_detection_enabled: bool = True

config = AgentConfig()
