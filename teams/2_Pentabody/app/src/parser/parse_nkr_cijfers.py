from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Mapping
from urllib.request import Request, urlopen

API_BASE_URL = "https://api.nkr-cijfers.iknl.nl/api"
DEFAULT_LANGUAGE = "nl-NL"


def _post_json(endpoint: str, payload: Mapping[str, object]) -> object:
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        f"{API_BASE_URL}/{endpoint}?format=json",
        data=body,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


def navigation_items(language: str = DEFAULT_LANGUAGE) -> object:
    return _post_json("navigation-items", {"language": language})


def configuration(navigation_code: str, language: str = DEFAULT_LANGUAGE) -> object:
    return _post_json(
        "configuration",
        {
            "language": language,
            "currentNavigation": {"code": navigation_code},
        },
    )


def filter_groups(
    navigation_code: str,
    filter_values_selected: list[dict[str, object]] | None = None,
    language: str = DEFAULT_LANGUAGE,
    user_action_code: str = "restart",
    user_action_value: str = "",
) -> object:
    return _post_json(
        "filter-groups",
        {
            "currentNavigation": {"code": navigation_code},
            "language": language,
            "filterValuesSelected": filter_values_selected or [],
            "userAction": {"code": user_action_code, "value": user_action_value},
        },
    )


def data(query_payload: Mapping[str, object]) -> object:
    return _post_json("data", query_payload)


def extract_navigation_items(language: str = DEFAULT_LANGUAGE) -> list[dict[str, str]]:
    response = navigation_items(language=language)
    items_by_code: dict[str, dict[str, str]] = {}

    for node in _iter_dicts(response):
        code = _string_value(node.get("code"))
        if not code or "/" not in code:
            continue
        label = _first_non_empty_string(
            node.get("label"),
            node.get("title"),
            node.get("name"),
            node.get("description"),
        )
        items_by_code.setdefault(code, {"code": code, "label": label or code})

    return sorted(items_by_code.values(), key=lambda item: item["code"])


def extract(navigation_code: str, language: str = DEFAULT_LANGUAGE) -> list[str]:
    return extract_kankersoorten(navigation_code=navigation_code, language=language)


def extract_kankersoorten(navigation_code: str, language: str = DEFAULT_LANGUAGE) -> list[str]:
    options = extract_kankersoort_options(navigation_code=navigation_code, language=language)
    return sorted(item["code"] for item in options)


def extract_kankersoort_options(
    navigation_code: str, language: str = DEFAULT_LANGUAGE
) -> list[dict[str, str]]:
    values = _extract_filter_values(
        filter_groups(navigation_code=navigation_code, language=language),
        filter_code="filter/kankersoort",
    )
    return sorted(values.values(), key=lambda item: item["label"])


def extract_filter_options(
    navigation_code: str, language: str = DEFAULT_LANGUAGE
) -> list[dict[str, object]]:
    response = filter_groups(navigation_code=navigation_code, language=language)
    groups: dict[str, dict[str, object]] = {}

    for node in _iter_dicts(response):
        code = _string_value(node.get("code"))
        if not code or not code.startswith("filter/"):
            continue

        values = _extract_direct_values(node)
        if not values:
            continue

        groups[code] = {
            "code": code,
            "label": _node_label(node, code),
            "values": values,
        }

    return sorted(groups.values(), key=lambda item: str(item["code"]))


def extract_statistic_options(
    navigation_code: str, language: str = DEFAULT_LANGUAGE
) -> list[dict[str, str]]:
    response = configuration(navigation_code=navigation_code, language=language)
    statistics: dict[str, dict[str, str]] = {}

    for node in _iter_dicts(response):
        code = _string_value(node.get("code"))
        if not code or not code.startswith("statistiek/"):
            continue
        statistics[code] = {"code": code, "label": _node_label(node, code)}

    return sorted(statistics.values(), key=lambda item: item["code"])


def find_navigation_item(
    terms: Iterable[str], language: str = DEFAULT_LANGUAGE
) -> dict[str, str] | None:
    matches = [
        item
        for item in extract_navigation_items(language=language)
        if _matches_terms(item["code"], terms) or _matches_terms(item["label"], terms)
    ]
    if not matches:
        return None
    return matches[0]


def match_kankersoort_option(
    navigation_code: str, cancer_type: str, language: str = DEFAULT_LANGUAGE
) -> dict[str, str] | None:
    options = extract_kankersoort_options(navigation_code=navigation_code, language=language)
    terms = _candidate_terms(cancer_type)

    exact_or_prefix_matches = [
        option
        for option in options
        if any(_slugify(option["label"]) == term or _slugify(option["code"]).endswith(term) for term in terms)
    ]
    if exact_or_prefix_matches:
        return exact_or_prefix_matches[0]

    fuzzy_matches = [
        option
        for option in options
        if any(term in _slugify(option["label"]) or term in _slugify(option["code"]) for term in terms)
    ]
    if fuzzy_matches:
        return fuzzy_matches[0]

    return None


def build_survival_query_payload(
    navigation_code: str,
    kanker_code: str,
    language: str = DEFAULT_LANGUAGE,
) -> dict[str, object]:
    filters = extract_filter_options(navigation_code=navigation_code, language=language)
    statistics = extract_statistic_options(navigation_code=navigation_code, language=language)
    statistic = _pick_statistic(statistics)

    aggregate_by: list[dict[str, object]] = []
    for filter_group in filters:
        filter_code = str(filter_group["code"])
        values = filter_group.get("values", [])
        if not isinstance(values, list) or not values:
            continue

        if filter_code == "filter/kankersoort":
            selected_value = kanker_code
        else:
            selected_value = _pick_default_filter_value(values)

        if not selected_value:
            continue

        aggregate_by.append(
            {
                "code": filter_code,
                "values": [{"code": selected_value}],
            }
        )

    payload: dict[str, object] = {
        "language": language,
        "navigation": {"code": navigation_code},
        "groupBy": [],
        "aggregateBy": aggregate_by,
    }
    if statistic:
        payload["statistic"] = {"code": statistic}
    return payload


def get_survival_data(cancer_type: str, language: str = DEFAULT_LANGUAGE) -> dict[str, object] | None:
    navigation = find_navigation_item(["overleving", "relatief"], language=language)
    if navigation is None:
        navigation = find_navigation_item(["overleving"], language=language)
    if navigation is None:
        return None

    kanker_option = match_kankersoort_option(
        navigation_code=navigation["code"],
        cancer_type=cancer_type,
        language=language,
    )
    if kanker_option is None:
        return None

    query_payload = build_survival_query_payload(
        navigation_code=navigation["code"],
        kanker_code=kanker_option["code"],
        language=language,
    )
    result = data(query_payload)
    return {
        "source": "nkr-cijfers",
        "kind": "survival_data",
        "navigation": navigation,
        "matched_kankersoort": kanker_option,
        "query": query_payload,
        "data": result,
    }


def _extract_filter_values(response: object, filter_code: str) -> dict[str, dict[str, str]]:
    value_prefix = f"{filter_code.split('/')[-1]}/"
    collected: dict[str, dict[str, str]] = {}
    in_target_filter = False

    for node in _iter_dicts(response):
        code = _string_value(node.get("code"))
        if code == filter_code:
            in_target_filter = True
            continue

        if in_target_filter and code and code.startswith(value_prefix):
            collected[code] = {"code": code, "label": _node_label(node, code)}

    if not collected:
        for node in _iter_dicts(response):
            code = _string_value(node.get("code"))
            if code and code.startswith(value_prefix):
                collected[code] = {"code": code, "label": _node_label(node, code)}

    return collected


def _extract_direct_values(node: Mapping[str, object]) -> list[dict[str, str]]:
    raw_values = node.get("values")
    if not isinstance(raw_values, list):
        return []

    values: list[dict[str, str]] = []
    for item in raw_values:
        if not isinstance(item, Mapping):
            continue
        code = _string_value(item.get("code"))
        if not code:
            continue
        values.append({"code": code, "label": _node_label(item, code)})
    return values


def _iter_dicts(value: object) -> Iterable[Mapping[str, object]]:
    if isinstance(value, Mapping):
        yield value
        for nested in value.values():
            yield from _iter_dicts(nested)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_dicts(item)


def _string_value(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _first_non_empty_string(*values: object) -> str | None:
    for value in values:
        text = _string_value(value)
        if text:
            return text
    return None


def _node_label(node: Mapping[str, object], fallback: str) -> str:
    return (
        _first_non_empty_string(
            node.get("label"),
            node.get("title"),
            node.get("name"),
            node.get("description"),
        )
        or fallback
    )


def _slugify(value: str) -> str:
    return value.lower().replace("_", "-").replace(" ", "-")


def _matches_terms(value: str, terms: Iterable[str]) -> bool:
    normalized = _slugify(value)
    return all(_slugify(term) in normalized for term in terms)


def _candidate_terms(cancer_type: str) -> list[str]:
    normalized = _slugify(cancer_type)
    candidates = {normalized}
    for part in normalized.split("-"):
        if not part:
            continue
        candidates.add(part)
        if part.endswith("kanker") and len(part) > len("kanker"):
            candidates.add(part[: -len("kanker")])
    return sorted(candidates, key=len, reverse=True)


def _pick_default_filter_value(values: list[dict[str, str]]) -> str | None:
    preferred_markers = [
        "totaal/alle",
        "totaal",
        "alle",
        "all",
        "nvt",
    ]
    for marker in preferred_markers:
        for value in values:
            code = value["code"]
            if marker in code:
                return code
    return values[0]["code"] if values else None


def _pick_statistic(statistics: list[dict[str, str]]) -> str | None:
    if not statistics:
        return None

    preferred_markers = [
        "percentage",
        "procent",
        "relatieve",
        "overleving",
    ]
    for marker in preferred_markers:
        for statistic in statistics:
            if marker in _slugify(statistic["label"]) or marker in _slugify(statistic["code"]):
                return statistic["code"]
    return statistics[0]["code"]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect NKR Cijfers topics and kankersoorten for a simple example case."
    )
    parser.add_argument(
        "--topic-terms",
        nargs="+",
        default=["overleving"],
        help="Terms used to match a navigation item, e.g. overleving relatief",
    )
    parser.add_argument(
        "--cancer-terms",
        nargs="+",
        default=["borst"],
        help="Terms used to match a kankersoort, e.g. borst",
    )
    args = parser.parse_args()

    navigation_matches = [
        item
        for item in extract_navigation_items()
        if _matches_terms(item["code"], args.topic_terms)
        or _matches_terms(item["label"], args.topic_terms)
    ]

    if not navigation_matches:
        print("No matching navigation items found.")
        return

    print("Matching navigation items:")
    for item in navigation_matches:
        print(f"- {item['code']} ({item['label']})")

    selected = navigation_matches[0]
    print(f"\nUsing topic: {selected['code']}")

    kanker_type_options = extract_kankersoort_options(selected["code"])
    cancer_matches = [
        kanker_type
        for kanker_type in kanker_type_options
        if _matches_terms(kanker_type["code"], args.cancer_terms)
        or _matches_terms(kanker_type["label"], args.cancer_terms)
    ]

    print("\nMatching kankersoorten:")
    if cancer_matches:
        for kanker_type in cancer_matches:
            print(f"- {kanker_type['label']} [{kanker_type['code']}]")
    else:
        print("No matching kankersoorten found for the selected topic.")
        print("\nAvailable kankersoorten for this topic:")
        for kanker_type in kanker_type_options:
            print(f"- {kanker_type['label']} [{kanker_type['code']}]")


if __name__ == "__main__":
    main()
