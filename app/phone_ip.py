"""Какой IP считать адресом трубки.

Телефон → nginx в сети Podman/pasta. X-Forwarded-For тогда 10.89.0.3,
не LAN. AutoP на 10.89.0.3 бьёт в сам nginx.

TCP-источник никогда не доверяем (rootless Podman SNAT). Только:
  1) Yealink $ip в Action URL
  2) ручное поле в карточке устройства
"""
from __future__ import annotations

import ipaddress
from fastapi import Request

CONTAINER_NETWORKS = (
    ipaddress.ip_network("10.88.0.0/16"),     # podman
    ipaddress.ip_network("10.89.0.0/16"),     # pasta
    ipaddress.ip_network("10.0.2.0/24"),      # slirp4netns
    ipaddress.ip_network("192.168.127.0/24"), # pasta usernet
    ipaddress.ip_network("172.16.0.0/12"),    # docker bridges
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
)


def parse_ip(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    if not text or text.startswith("$"):
        return None
    if text.startswith("[") and "]" in text:
        text = text[1:text.index("]")]
    if "%" in text:
        text = text.split("%", 1)[0]
    try:
        addr = ipaddress.ip_address(text)
    except ValueError:
        return None
    if addr.is_loopback or addr.is_unspecified or addr.is_multicast or addr.is_link_local:
        return None
    return str(addr)


def is_container_ip(ip: str | None) -> bool:
    parsed = parse_ip(ip)
    if not parsed:
        return True
    addr = ipaddress.ip_address(parsed)
    return any(addr in net for net in CONTAINER_NETWORKS)


def is_phone_ip(ip: str | None) -> bool:
    parsed = parse_ip(ip)
    return bool(parsed) and not is_container_ip(parsed)


def request_src_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return parse_ip(forwarded.split(",")[0])
    if request.client:
        return parse_ip(request.client.host)
    return None


def reported_phone_ip(request: Request) -> str | None:
    """IP, который трубка сама подставила вместо $ip / $wanip."""
    for key in ("ip", "phone_ip", "wanip", "ipv4"):
        parsed = parse_ip(request.query_params.get(key, ""))
        if is_phone_ip(parsed):
            return parsed
    return None


def pick_phone_ip(reported: str | None, src: str | None, existing: str | None) -> str | None:
    """src (X-Forwarded-For) игнорируется — это NAT Podman.

    Возвращает LAN-адрес или None (тогда контейнерный мусор надо стереть).
    """
    _ = src
    if is_phone_ip(reported):
        return parse_ip(reported)
    if is_phone_ip(existing):
        return parse_ip(existing)
    return None
