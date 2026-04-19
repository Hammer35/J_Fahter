from urllib.parse import parse_qs, urlparse


def extract_claude_auth_code(url: str) -> str | None:
    """
    Извлекает код авторизации из OAuth callback URL Claude.

    Ожидаемые форматы:
    - https://claude.ai/...?code=XXXX&...
    - https://...#code=XXXX
    """
    parsed = urlparse(url)

    # Проверяем query string (?code=...)
    params = parse_qs(parsed.query)
    if "code" in params:
        return params["code"][0]

    # Проверяем fragment (#code=...)
    fragment_params = parse_qs(parsed.fragment)
    if "code" in fragment_params:
        return fragment_params["code"][0]

    return None
