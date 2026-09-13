"""Jinja-окружение для cfg-файлов.

Нельзя использовать request.app.state.templates (Jinja2Templates):
там включён HTML-autoescape, и '&' в Action URL превращается в '&' —
трубка получает битый адрес. Здесь autoescape выключен, значения
прогоняются через фильтр |cfg (кавычки при спецсимволах).
"""

import os
from jinja2 import Environment, FileSystemLoader

from app.security import quote_cfg

_templates_dir = os.path.join(os.path.dirname(__file__), "templates", "provision")

jinja_env = Environment(
    loader=FileSystemLoader(_templates_dir),
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)
jinja_env.filters["cfg"] = quote_cfg
