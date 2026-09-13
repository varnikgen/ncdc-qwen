import base64

from app.database import SessionLocal
from app.models import Phone, Account, PhoneModel
from app.provision_templates import jinja_env
from app.services.config_builder import build_phone_config, build_model_config


def _basic(user, password):
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def test_health_open(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


def test_admin_requires_auth(client):
    r = client.get("/")
    assert r.status_code == 401


def test_provision_requires_auth(client):
    r = client.get("/provision/y000000000000.cfg")
    assert r.status_code == 401


def test_provision_global_with_auth(client):
    r = client.get("/provision/y000000000000.cfg", headers=_basic("provision", "test-prov-pass"))
    assert r.status_code == 200
    body = r.text
    assert "#!version:1.0.0.1" in body
    # HTML-escaping would turn query '&' into '&' and break Yealink
    assert "amp;mac=" not in body
    assert "token=test-token-123&mac=" in body
    assert "10.30.30.30" not in body
    # URL не в кавычках — иначе часть прошивок не подставляет $mac
    assert 'action_url.registered = https://' in body
    assert "action_url.setup_completed =" in body
    assert "features.action_uri_limit_ip = any" in body


def test_unknown_mac_auto_enrolls(client):
    r = client.get("/provision/001565C18725.cfg", headers=_basic("provision", "test-prov-pass"))
    assert r.status_code == 200
    db = SessionLocal()
    try:
        phone = db.query(Phone).filter(Phone.mac == "001565C18725").first()
        assert phone is not None
    finally:
        db.close()


def test_action_url_requires_token(client):
    r = client.get("/actions/?mac=001565AABBCC&event=registered")
    assert r.status_code == 403


def test_action_url_enroll_and_dnd(client):
    r = client.get(
        "/actions/?token=test-token-123&mac=00:11:22:33:44:55&event=registered",
        headers={"User-Agent": "Yealink SIP-T46U 108.87.14.1 00:11:22:33:44:55"},
    )
    assert r.status_code == 200
    assert r.json()["created"] is True

    r = client.get("/actions/?token=test-token-123&mac=001122334455&event=dnd_on")
    assert r.status_code == 200
    db = SessionLocal()
    try:
        phone = db.query(Phone).filter(Phone.mac == "001122334455").first()
        assert phone.status == "dnd"
    finally:
        db.close()


def test_create_phone_and_custom_config(client, admin_headers):
    r = client.post(
        "/phones/",
        data={"mac": "aabbccddeeff", "admin_username": "admin", "admin_password": "secret"},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    db = SessionLocal()
    try:
        phone = db.query(Phone).filter(Phone.mac == "AABBCCDDEEFF").first()
        assert phone is not None
        phone_id = phone.id
    finally:
        db.close()

    r = client.post(
        f"/phones/{phone_id}/update",
        data={
            "custom_config": '{"voice.handset.spk_vol": "10"}',
            "custom_dss_keys": "[]",
            "account_ids": "",
            "override_dss_keys": "0",
        },
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    db = SessionLocal()
    try:
        phone = db.query(Phone).filter(Phone.id == phone_id).first()
        assert phone.custom_config == {"voice.handset.spk_vol": "10"}
    finally:
        db.close()


def test_model_default_config_rendered():
    model = PhoneModel(
        name="T46U",
        ieee802_1x_enable=True,
        ieee802_1x_identity="yealink",
        ieee802_1x_mode=0,
        firmware_url="tftp://example/fw.rom",
        default_config={"phone_setting.ring_type": 2},
    )
    cfg = build_model_config(model, "T46U")
    rendered = jinja_env.get_template("model.cfg.j2").render(config=cfg)
    assert "static.network.802_1x.enable = 1" in rendered
    assert "phone_setting.ring_type = 2" in rendered
    assert "firmware.url =" in rendered


def test_sip_password_is_quoted():
    db = SessionLocal()
    try:
        acc = Account(
            name="Office",
            sip_server="10.0.0.1",
            username="10400",
            password="p@ss word",
        )
        db.add(acc)
        db.flush()
        phone = Phone(mac="FFFFEEEE0001", account_ids=[acc.id], custom_config={})
        db.add(phone)
        db.commit()
        data = build_phone_config(db, "FFFFEEEE0001")
        rendered = jinja_env.get_template("phone.cfg.j2").render(config=data)
        assert 'account.1.password = "p@ss word"' in rendered
    finally:
        db.close()


def test_boolean_off_is_saved(client, admin_headers):
    r = client.post(
        "/settings/global",
        data={
            "param_static.network.ipv6_enable": "0",
            "param_ldap.enable": "0",
        },
        headers=admin_headers,
    )
    assert r.status_code == 200


def test_dss_keys_not_glued_and_unused_disabled():
    """Регрессия: label склеивался с linekey.N.line и следующим ключом."""
    from app.services.linekeys import render_linekeys_block

    block = render_linekeys_block(
        [
            {"line": 1, "type": 15, "account": 1, "label": "", "value": "", "extension": ""},
            {"line": 7, "type": 15, "account": 2, "label": "Acc2", "value": "", "extension": ""},
        ],
        max_keys=10,
    )
    rendered = jinja_env.get_template("phone.cfg.j2").render(
        config={
            "phone": {},
            "accounts": [],
            "dss_keys": [],
            "linekeys_block": block,
        }
    )
    assert "linekey.1.label = linekey" not in rendered
    assert "1linekey" not in rendered
    assert "linekey.1.type = 15" in rendered
    assert "linekey.1.line = 1" in rendered
    assert "linekey.7.type = 15" in rendered
    assert "linekey.7.line = 2" in rendered
    assert "linekey.7.label = Acc2" in rendered
    # account.2 не должен сам встать на клавишу 2
    assert "linekey.2.type = 0" in rendered
    # каждая директива на своей строке
    for raw in rendered.splitlines():
        if raw.startswith("linekey."):
            assert raw.count("linekey.") == 1, raw


def test_quote_cfg_does_not_quote_urls():
    from app.security import quote_cfg

    url = "https://ncdc.test/actions/?token=abc&mac=$mac&event=registered"
    assert quote_cfg(url) == url
