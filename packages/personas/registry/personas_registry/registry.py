"""Persona registry loading and caching Persona models from YAML files.

Owner: C1
"""

from pathlib import Path
from typing import Dict, List, Optional

import yaml
from contracts.models import Persona


class PersonaRegistry:
    """Loads and holds Persona specifications."""

    def __init__(self, personas_dir: Optional[Path | str] = None) -> None:
        self._personas: Dict[str, Persona] = {}
        if personas_dir:
            self.load_from_dir(personas_dir)
        else:
            self._register_default_placeholders()

    def _register_default_placeholders(self) -> None:
        """Seed the 4 required placeholder personas in-memory if no directory is provided."""
        defaults = [
            Persona(
                id="coder",
                name="Code Specialist",
                description="Handles software engineering, code refactoring, test writing, and bug fixes.",
                system_prompt="",
                allowed_tools=["echo"],
                default_autonomy="semi",
            ),
            Persona(
                id="researcher",
                name="Research & Synthesis Specialist",
                description="Handles literature reviews, technical research, and information summarization.",
                system_prompt="",
                allowed_tools=["echo"],
                default_autonomy="semi",
            ),
            Persona(
                id="ops",
                name="Operations Specialist",
                description="Handles infrastructure, deployments, incident response, and log inspection.",
                system_prompt="",
                allowed_tools=["echo"],
                default_autonomy="supervised",
            ),
            Persona(
                id="writer",
                name="Documentation & Content Specialist",
                description="Handles technical documentation, release notes, and user-facing communications.",
                system_prompt="",
                allowed_tools=["echo"],
                default_autonomy="full",
            ),
        ]
        for p in defaults:
            self.register(p)

    def load_from_dir(self, personas_dir: Path | str) -> None:
        """Scan directory for *.yaml persona definition files."""
        # TODO (C1 Persona Owner): Add hot-reloading, schema validation error reporting,
        # and persona inheritance/composition.
        path = Path(personas_dir)
        if not path.exists():
            self._register_default_placeholders()
            return

        yaml_files = list(path.glob("*.yaml")) + list(path.glob("*.yml"))
        if not yaml_files:
            self._register_default_placeholders()
            return

        for yf in yaml_files:
            with open(yf, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if data and isinstance(data, dict) and "id" in data:
                    persona = Persona(**data)
                    self.register(persona)

    def register(self, persona: Persona) -> None:
        self._personas[persona.id.lower()] = persona

    def get(self, persona_id: str) -> Persona:
        lowered = persona_id.lower()
        if lowered not in self._personas:
            raise KeyError(
                f"Persona '{persona_id}' not found. Available personas: {list(self._personas.keys())}"
            )
        return self._personas[lowered]

    def list_all(self) -> List[Persona]:
        return list(self._personas.values())
