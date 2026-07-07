# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import json
import logging
import os

# Conditional import of Vertex AI and Cloud Logging based on environment variable
if os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "True").lower() != "false":
    import vertexai
    from google.cloud import logging as google_cloud_logging
else:
    # Fallback: no Vertex AI; use standard logging only
    vertexai = None
    google_cloud_logging = None

import os
from typing import Any

from dotenv import load_dotenv
from google.adk.artifacts import GcsArtifactService, InMemoryArtifactService

# Conditional import of Vertex AI utilities
if os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "True").lower() != "false":
    from vertexai.agent_engines.templates.adk import AdkApp
else:
    # Define a lightweight fallback AdkApp with minimal async streaming capability
    from collections.abc import AsyncGenerator
    from typing import Any


    class AdkApp:
        def __init__(self, *args, **kwargs):
            pass

        def set_up(self) -> None:
            """No-op for fallback when Vertex AI is disabled."""
            pass

        async def async_stream_query(self, message: str, user_id: str) -> AsyncGenerator[dict, None]:
            """Yield a simple echo event for testing purposes."""
            # Construct a minimal Event-like dict
            yield {"content": {"parts": [{"text": f"Echo: {message}"}]}}

        def register_feedback(self, feedback: dict) -> None:
            """Placeholder feedback handler."""
            pass

from app.api import app as adk_app
from app.app_utils.telemetry import setup_telemetry
from app.app_utils.typing import Feedback

# Load environment variables from .env file at runtime
load_dotenv()


class AgentEngineApp(AdkApp):
    def set_up(self) -> None:
        """Initialize the agent engine app with logging and telemetry.
        If GOOGLE_GENAI_USE_VERTEXAI is set to "False", skip Vertex AI initialization
        and Cloud Logging client creation (we only use Gemini API key)."""
        use_vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "True").lower() != "false"
        if use_vertex:
            vertexai.init()
        setup_telemetry()
        super().set_up()
        logging.basicConfig(level=logging.INFO)
        if use_vertex:
            logging_client = google_cloud_logging.Client()
            self.logger = logging_client.logger(__name__)
        else:
            # Fallback logger that writes to stdout
            self.logger = logging.getLogger(__name__)
        gemini_location = os.environ.get("GOOGLE_CLOUD_LOCATION")
        if gemini_location:
            os.environ["GOOGLE_CLOUD_LOCATION"] = gemini_location

    def register_feedback(self, feedback: dict[str, Any]) -> None:
        """Collect and log feedback."""
        feedback_obj = Feedback.model_validate(feedback)
        self.logger.info(json.dumps(feedback_obj.model_dump()))

    def register_operations(self) -> dict[str, list[str]]:
        """Registers the operations of the Agent."""
        operations = super().register_operations()
        operations[""] = [*operations.get("", []), "register_feedback"]
        return operations

    def clone(self) -> "AgentEngineApp":
        """Returns a clone of the Agent Runtime application."""
        return self


logs_bucket_name = os.environ.get("LOGS_BUCKET_NAME")
# Instantiate AgentEngineApp unconditionally; internal set_up handles vertex usage
agent_runtime = AgentEngineApp(
    app=adk_app,
    artifact_service_builder=lambda: (
        GcsArtifactService(bucket_name=logs_bucket_name)
        if logs_bucket_name
        else InMemoryArtifactService()
    ),
)
