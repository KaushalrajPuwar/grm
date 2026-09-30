"""Runtime configuration: one fixed model per agent role.

Reads API_KEY, BASE_URL, MODELID_1 (chat), MODELID_2 (reasoning),
MODELID_3 (QA) from the environment. Model bindings are static: a role is
assigned its model at construction and nothing resolves a model at runtime.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent.parent

#: Local Beneficiary 360 response standing in for the live API until it lands.
#: Demo content only: an LPG subsidy case with a dispatched cylinder and a
#: blocked subsidy release.
SAMPLE_BLOB_PATH = PACKAGE_ROOT / "data" / "beneficiary360_demo_lpg.json"

#: Demo contact for the OTP flow. The response schema carries no mobile number,
#: so the demo hardcodes one and masks all but the last three digits.
DEMO_REGISTERED_MOBILE = "9845012345"

#: Shared store between the server process and the standalone OTP issuer, so a
#: human reads the code in a second terminal and types it into the chat window.
OTP_ISSUE_PATH = PROJECT_ROOT / "var" / "demo_otp_issued.json"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_key: str = ""
    base_url: str = ""
    modelid_1: str = ""
    modelid_2: str = ""
    modelid_3: str = ""

    @property
    def chat_model(self) -> str:
        """MODELID_1. Fixed to the chat agent."""
        return self.modelid_1

    @property
    def reasoning_model(self) -> str:
        """MODELID_2. Fixed to the analysis agent."""
        return self.modelid_2

    @property
    def qa_model(self) -> str:
        """MODELID_3. Fixed to the evaluation agent."""
        return self.modelid_3


@lru_cache
def get_settings() -> Settings:
    return Settings()
