from parser.parse_kanker_nl import extract, grab_by_type


def test_extract_returns_sorted_unique_kankersoorten() -> None:
    soorten = extract()

    assert soorten == sorted(soorten)
    assert len(soorten) == len(set(soorten))
    assert "darmkanker-dikkedarmkanker" in soorten
    assert "prostaatkanker" in soorten


def test_grab_by_type_returns_matching_pages() -> None:
    pages = grab_by_type("prostaatkanker")

    assert pages
    assert all(isinstance(page, str) for page in pages)
    assert any("prostaatkanker" in page.lower() for page in pages)
