from __future__ import annotations

import json

from parser import parse_nkr_cijfers


class _FakeResponse:
    def __init__(self, payload: object):
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_navigation_items_posts_expected_payload(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse([{"code": "incidentie"}])

    monkeypatch.setattr(parse_nkr_cijfers, "urlopen", fake_urlopen)

    response = parse_nkr_cijfers.navigation_items()

    assert response == [{"code": "incidentie"}]
    assert captured["url"] == (
        "https://api.nkr-cijfers.iknl.nl/api/navigation-items?format=json"
    )
    assert captured["method"] == "POST"
    assert captured["body"] == {"language": "nl-NL"}
    headers = {key.lower(): value for key, value in captured["headers"].items()}
    assert headers["content-type"] == "application/json"
    assert headers["accept"] == "application/json"


def test_extract_navigation_items_flattens_nested_payload(monkeypatch) -> None:
    payload = {
        "navigationItems": [
            {
                "code": "incidentie",
                "label": "Incidentie",
                "children": [
                    {
                        "code": "incidentie/verdeling-per-stadium",
                        "label": "Verdeling per stadium",
                    },
                    {
                        "code": "incidentie/trend",
                        "title": "Trend",
                    },
                ],
            },
            {
                "code": "overleving",
                "label": "Overleving",
                "children": [
                    {
                        "code": "overleving/relatief",
                        "name": "Relatieve overleving",
                    }
                ],
            },
        ]
    }
    monkeypatch.setattr(parse_nkr_cijfers, "navigation_items", lambda language="nl-NL": payload)

    result = parse_nkr_cijfers.extract_navigation_items()

    assert result == [
        {"code": "incidentie/trend", "label": "Trend"},
        {"code": "incidentie/verdeling-per-stadium", "label": "Verdeling per stadium"},
        {"code": "overleving/relatief", "label": "Relatieve overleving"},
    ]


def test_extract_kankersoorten_reads_filter_values(monkeypatch) -> None:
    payload = {
        "filterGroups": [
            {
                "code": "filter/kankersoort",
                "values": [
                    {"code": "kankersoort/totaal/alle", "label": "Alle kanker"},
                    {"code": "kankersoort/borst/borstkanker", "label": "Borstkanker"},
                    {"code": "kankersoort/long/longkanker", "label": "Longkanker"},
                ],
            },
            {
                "code": "filter/geslacht",
                "values": [{"code": "geslacht/totaal/alle", "label": "Alle"}],
            },
        ]
    }
    monkeypatch.setattr(
        parse_nkr_cijfers,
        "filter_groups",
        lambda navigation_code, language="nl-NL": payload,
    )

    result = parse_nkr_cijfers.extract("incidentie/verdeling-per-stadium")

    assert result == [
        "kankersoort/borst/borstkanker",
        "kankersoort/long/longkanker",
        "kankersoort/totaal/alle",
    ]


def test_extract_kankersoort_options_keeps_labels(monkeypatch) -> None:
    payload = {
        "filterGroups": [
            {
                "code": "filter/kankersoort",
                "values": [
                    {"code": "kankersoort/302310", "label": "Borst"},
                    {"code": "kankersoort/205320", "label": "Long"},
                ],
            }
        ]
    }
    monkeypatch.setattr(
        parse_nkr_cijfers,
        "filter_groups",
        lambda navigation_code, language="nl-NL": payload,
    )

    result = parse_nkr_cijfers.extract_kankersoort_options("overleving/relatief")

    assert result == [
        {"code": "kankersoort/302310", "label": "Borst"},
        {"code": "kankersoort/205320", "label": "Long"},
    ]


def test_extract_kankersoorten_falls_back_to_recursive_code_scan(monkeypatch) -> None:
    payload = {
        "items": [
            {
                "group": {"code": "filter/stadium"},
                "values": [{"code": "stadium/i"}],
            },
            {
                "group": {"code": "something-else"},
                "nested": {
                    "values": [
                        {"code": "kankersoort/huid/melanoom"},
                        {"code": "kankersoort/prostaat/prostaatkanker"},
                    ]
                },
            },
        ]
    }
    monkeypatch.setattr(
        parse_nkr_cijfers,
        "filter_groups",
        lambda navigation_code, language="nl-NL": payload,
    )

    result = parse_nkr_cijfers.extract_kankersoorten("incidentie/trend")

    assert result == [
        "kankersoort/huid/melanoom",
        "kankersoort/prostaat/prostaatkanker",
    ]


def test_build_survival_query_payload_prefers_totals(monkeypatch) -> None:
    monkeypatch.setattr(
        parse_nkr_cijfers,
        "extract_filter_options",
        lambda navigation_code, language="nl-NL": [
            {
                "code": "filter/kankersoort",
                "label": "Kankersoort",
                "values": [
                    {"code": "kankersoort/302310", "label": "Borst"},
                ],
            },
            {
                "code": "filter/geslacht",
                "label": "Geslacht",
                "values": [
                    {"code": "geslacht/totaal/alle", "label": "Alle"},
                    {"code": "geslacht/vrouw", "label": "Vrouw"},
                ],
            },
        ],
    )
    monkeypatch.setattr(
        parse_nkr_cijfers,
        "extract_statistic_options",
        lambda navigation_code, language="nl-NL": [
            {"code": "statistiek/percentage", "label": "Percentage"}
        ],
    )

    payload = parse_nkr_cijfers.build_survival_query_payload(
        navigation_code="overleving/relatief",
        kanker_code="kankersoort/302310",
    )

    assert payload == {
        "language": "nl-NL",
        "navigation": {"code": "overleving/relatief"},
        "groupBy": [],
        "aggregateBy": [
            {
                "code": "filter/kankersoort",
                "values": [{"code": "kankersoort/302310"}],
            },
            {
                "code": "filter/geslacht",
                "values": [{"code": "geslacht/totaal/alle"}],
            },
        ],
        "statistic": {"code": "statistiek/percentage"},
    }


def test_get_survival_data_builds_package(monkeypatch) -> None:
    monkeypatch.setattr(
        parse_nkr_cijfers,
        "find_navigation_item",
        lambda terms, language="nl-NL": {
            "code": "overleving/relatief",
            "label": "Relatieve overleving",
        },
    )
    monkeypatch.setattr(
        parse_nkr_cijfers,
        "match_kankersoort_option",
        lambda navigation_code, cancer_type, language="nl-NL": {
            "code": "kankersoort/302310",
            "label": "Borst",
        },
    )
    monkeypatch.setattr(
        parse_nkr_cijfers,
        "build_survival_query_payload",
        lambda navigation_code, kanker_code, language="nl-NL": {
            "language": language,
            "navigation": {"code": navigation_code},
            "aggregateBy": [{"code": "filter/kankersoort", "values": [{"code": kanker_code}]}],
        },
    )
    monkeypatch.setattr(
        parse_nkr_cijfers,
        "data",
        lambda query_payload: {"rows": [{"year": 5, "value": 88.0}]},
    )

    result = parse_nkr_cijfers.get_survival_data("borstkanker")

    assert result == {
        "source": "nkr-cijfers",
        "kind": "survival_data",
        "navigation": {
            "code": "overleving/relatief",
            "label": "Relatieve overleving",
        },
        "matched_kankersoort": {
            "code": "kankersoort/302310",
            "label": "Borst",
        },
        "query": {
            "language": "nl-NL",
            "navigation": {"code": "overleving/relatief"},
            "aggregateBy": [
                {
                    "code": "filter/kankersoort",
                    "values": [{"code": "kankersoort/302310"}],
                }
            ],
        },
        "data": {"rows": [{"year": 5, "value": 88.0}]},
    }
