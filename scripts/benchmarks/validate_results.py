import argparse
import json
from pathlib import Path
import sys

from jsonschema import validate, ValidationError


def validate_json_file(data_path: Path, schema_path: Path) -> bool:
    if not data_path.is_file():
        print(f"[FAIL] Data file does not exist: {data_path}")
        return False
    if not schema_path.is_file():
        print(f"[FAIL] Schema file does not exist: {schema_path}")
        return False

    try:
        data = json.loads(data_path.read_text(encoding="utf-8"))
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        validate(instance=data, schema=schema)
        print(f"[PASS] {data_path.name} conforms to {schema_path.name}")
        return True
    except ValidationError as err:
        print(f"[FAIL] Validation error in {data_path.name}: {err.message}")
        if err.path:
            print(f"       Failed property: {' -> '.join(str(p) for p in err.path)}")
        return False
    except Exception as exc:
        print(f"[FAIL] Exception validating {data_path.name}: {exc}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate benchmark JSON against schema")
    parser.add_argument("--result", required=True, help="Path to result JSON file")
    parser.add_argument("--schema", required=True, help="Path to JSON schema file")
    args = parser.parse_args()

    success = validate_json_file(Path(args.result).resolve(), Path(args.schema).resolve())
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

