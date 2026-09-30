"""Runtime configuration. One fixed model per agent role, ARCHITECTURE.md section 6."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    api_key: str = ""
    base_url: str = ""
    # TODO: per role model map, Redis URL, SQLite path.


# TODO: cached get_settings loader.
