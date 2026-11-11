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

# The repo's .env is authoritative for local runs. Without override, a stale
# API_KEY exported in the shell silently shadows a renewed one in .env.
load_dotenv(override=True)

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent.parent

#: Directory of local Beneficiary 360 responses, standing in for the live API.
#: One file per person, named after their registration number, for example
#: FID9988776655.json. The file name is the index; the record is only read
#: after a caller has been matched to it.
SAMPLE_BLOB_DIR = PACKAGE_ROOT / "data" / "beneficiaries"

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

    #: One switch for the QA gate. False ships the reasoning agent's candidate
    #: directly. The QA code and prompt stay intact, so turning it back on is
    #: one environment change and a restart.
    qa_enabled: bool = False

    #: One switch for the agent architecture. False keeps the two-agent flow:
    #: chat routes, reasoning analyses. True collapses both responsibilities
    #: into the chat model, which then sees the full snapshot and the merged
    #: constitution. Every existing path stays intact for rollback.
    single_agent: bool = False

    #: TEMPORARY demo switch. True verifies a matched identifier without an OTP,
    #: so the voice team can test before SMS delivery exists. Set
    #: DEMO_AUTO_VERIFY=false and restart to restore the real gate. The OTP code
    #: path is untouched and resumes the moment this is off.
    demo_auto_verify: bool = True

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
