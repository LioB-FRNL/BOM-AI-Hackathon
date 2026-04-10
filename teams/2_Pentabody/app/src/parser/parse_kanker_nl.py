from pathlib import Path
import json

data_path = Path(__file__).parent.parent.parent.parent.parent.parent
data_source = data_path / "data/kanker_nl_pages_all.json"


def grab_by_type(soort):
    with open(data_source, "r") as file:
        data = json.load(file)

    return [entry["text"] for entry in data.values() if entry["kankersoort"] == soort]


if __name__ == "__main__":
    result = grab_by_type("darmkanker-dikkedarmkanker")
    print(result[0])
    print(len(result))
