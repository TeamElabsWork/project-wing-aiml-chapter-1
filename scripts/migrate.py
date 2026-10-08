"""Migration runner for memory schema.

Reads embedding.dimensions from config/models.yaml and ensures the
pgvector column in 001_initial_schema.sql reflects the configured dimensions.
"""

import re
import sys
from pathlib import Path

import yaml


def run_migration(models_config_path: Path, migration_file_path: Path) -> int:
    dimensions = 1536
    if models_config_path.exists():
        with open(models_config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            dimensions = data.get("embedding", {}).get("dimensions", 1536)

    if not migration_file_path.exists():
        print(f"[ERROR] Migration file not found: {migration_file_path}", file=sys.stderr)
        return 1

    content = migration_file_path.read_text(encoding="utf-8")

    # Replace vector(1536) or vector({{...}}) with configured vector dimension
    pattern = r"vector\([^\)]+\)"
    new_vector = f"vector({dimensions})"
    updated_content, count = re.subn(pattern, new_vector, content)

    # Ensure timestamp column is used instead of created_at
    updated_content = re.sub(
        r"created_at TIMESTAMPTZ NOT NULL DEFAULT NOW\(\)",
        "timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()",
        updated_content,
    )
    updated_content = re.sub(
        r"idx_memory_nodes_created_at ON memory_nodes\(created_at DESC\)",
        "idx_memory_nodes_timestamp ON memory_nodes(timestamp DESC)",
        updated_content,
    )

    migration_file_path.write_text(updated_content, encoding="utf-8")
    print(
        f"[MIGRATE] Updated {migration_file_path.name} with vector dimension {dimensions} "
        f"(substitutions: {count}) from {models_config_path.name}."
    )
    return 0


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    models_cfg = repo_root / "config" / "models.yaml"
    migration_file = (
        repo_root / "packages" / "memory" / "store" / "migrations" / "001_initial_schema.sql"
    )

    exit_code = run_migration(models_cfg, migration_file)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
