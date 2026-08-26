from fillonce.normalization import canonical_key, normalize_date, normalize_label


def test_multilingual_aliases_are_conservative() -> None:
    assert canonical_key("Family Name") == "last_name"
    assert canonical_key("姓") == "last_name"
    assert canonical_key("联系电话") == "phone"
    assert canonical_key("Favorite color") == "favorite_color"


def test_normalization_handles_machine_field_names() -> None:
    assert normalize_label("APPLICANT_EMAIL-ADDRESS") == "applicant email address"


def test_only_unambiguous_dates_are_changed() -> None:
    assert normalize_date("2026/08/21") == "2026-08-21"
    assert normalize_date("08/09/10") == "08/09/10"
