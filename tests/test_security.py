from app.security import extract_mac, normalize_mac, quote_cfg, constant_time_equals


def test_normalize_mac_strips_separators():
    assert normalize_mac("00:15:65:c1:87:25") == "001565C18725"
    assert normalize_mac("001565c18725") == "001565C18725"
    assert normalize_mac("bad") is None


def test_extract_mac_from_yealink_ua_does_not_glue_firmware():
    ua = "Yealink SIP-T46U 108.87.14.1 24:9a:d8:6e:9d:88"
    assert extract_mac(ua, "") == "249AD86E9D88"


def test_extract_mac_from_query():
    assert extract_mac("", "24-9a-d8-6e-9d-88") == "249AD86E9D88"


def test_quote_cfg_special_chars():
    assert quote_cfg("simple") == "simple"
    assert quote_cfg("p@ss word") == '"p@ss word"'
    assert quote_cfg('a"b') == r'"a\"b"'
    assert quote_cfg(True) == "1"
    assert quote_cfg(False) == "0"


def test_constant_time_equals():
    assert constant_time_equals("abc", "abc")
    assert not constant_time_equals("abc", "abd")
