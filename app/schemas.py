"""Pydantic-схемы под OpenAPI. HTML-формы разбираются в роутерах напрямую
(request.form()), потому что UI шлёт multipart + JSON-строки, а не application/json.
"""