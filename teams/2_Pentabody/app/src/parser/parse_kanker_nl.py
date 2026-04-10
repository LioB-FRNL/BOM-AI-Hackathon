import json
from pathlib import Path

data_path = Path(__file__).resolve().parents[5]
data_source = data_path / "data/kanker_nl_pages_all.json"


def _load_data() -> dict[str, dict[str, str]]:
    with data_source.open("r", encoding="utf-8") as file:
        return json.load(file)


def extract() -> list[str]:
    data = _load_data()
    return sorted({entry["kankersoort"] for entry in data.values()})


def grab_by_type(soort: str) -> list[str]:
    data = _load_data()
    return [entry["text"] for entry in data.values() if entry["kankersoort"] == soort]


if __name__ == "__main__":
    soorten = extract()
    print(f"Found {len(soorten)} kankersoorten")
    print(soorten)
