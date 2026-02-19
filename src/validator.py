"""Optional JSON Schema validation for incoming WebSocket events.

Validates messages against bot-ws-schema/schema/events.json when enabled.
In production this is typically disabled for performance; useful for debugging.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SCHEMA_PATH = (
    Path(__file__).parent.parent / "schema" / "bot-ws-schema" / "schema" / "events.json"
)


class EventValidator:
    """Validates WebSocket event dicts against the shared JSON Schema."""

    def __init__(self) -> None:
        try:
            import jsonschema  # noqa: F401

            self._schema = json.loads(SCHEMA_PATH.read_text())
            self._enabled = True
            logger.info("Schema validation enabled (loaded %s)", SCHEMA_PATH)
        except ImportError:
            logger.warning(
                "jsonschema not installed; schema validation disabled"
            )
            self._enabled = False
        except FileNotFoundError:
            logger.warning(
                "Schema file not found at %s; validation disabled", SCHEMA_PATH
            )
            self._enabled = False

    def validate(self, event: dict) -> bool:
        """Validate an event dict. Returns True if valid or validation disabled."""
        if not self._enabled:
            return True

        import jsonschema

        try:
            jsonschema.validate(instance=event, schema=self._schema)
            return True
        except jsonschema.ValidationError as e:
            logger.warning(
                "Schema validation failed: %s (path: %s)",
                e.message,
                list(e.absolute_path),
            )
            return False
