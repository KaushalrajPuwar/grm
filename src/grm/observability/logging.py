"""structlog JSON setup. LangSmith hook point lives here, no secrets in logs."""


# TODO: configure_logging() with redaction of identifiers.
def configure_logging():
    raise NotImplementedError
