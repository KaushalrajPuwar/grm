"""Turn in/out contract. Both chat and voice teams bind to this."""

from pydantic import BaseModel


class TurnRequest(BaseModel):
    # TODO: session id, text, channel, version fields.
    pass


class TurnResponse(BaseModel):
    # TODO: reply text, satisfaction prompt flag, session state.
    pass
