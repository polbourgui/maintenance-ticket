"""Write the OpenAPI schema to stdout (used to generate the frontend TypeScript types).

python scripts/export_openapi.py > frontend/openapi.json
"""

from __future__ import annotations

import json
import sys

from pydantic import SecretStr

from app.core.config import Settings
from app.main import create_app


def main() -> None:
    settings = Settings(
        secret_key=SecretStr("openapi-export-" + "x" * 32), database_url="sqlite://"
    )
    json.dump(create_app(settings).openapi(), sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
