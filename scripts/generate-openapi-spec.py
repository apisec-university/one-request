import json

from fastapi.openapi.utils import get_openapi
from one_request.app import app
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Generate OpenAPI schema")
    parser.add_argument(
        "--output",
        "-o",
        default="openapi.json",
        help="Output file relative to repo root directory",
    )

    args = parser.parse_args()

    # Get the script's location and construct the output path
    script_path = Path(__file__).resolve()
    base_path = script_path.parent.parent
    output = (base_path / args.output).resolve()

    # Create output directory if it doesn't exist
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w") as f:
        json.dump(
            get_openapi(
                title=app.title,
                version=app.version,
                openapi_version=app.openapi_version,
                description=app.description,
                routes=app.routes,
            ),
            f,
        )

    print(f"OpenAPI schema generated at: {output}")


if __name__ == "__main__":
    main()
