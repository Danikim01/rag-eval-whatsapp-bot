import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    verify_token: str
    app_secret: str
    access_token: str
    phone_number_id: str
    graph_api_version: str
    db_path: str
    owner_phone_number: str

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        required = ["WA_VERIFY_TOKEN", "WA_APP_SECRET", "WA_ACCESS_TOKEN", "WA_PHONE_NUMBER_ID", "OWNER_PHONE_NUMBER"]
        missing = [k for k in required if not os.environ.get(k)]
        if missing:
            raise RuntimeError(f"Missing env vars: {', '.join(missing)}")
        owner = os.environ["OWNER_PHONE_NUMBER"].strip()
        if not owner.isdigit():
            raise RuntimeError("OWNER_PHONE_NUMBER must contain digits only")
        return cls(
            verify_token=os.environ["WA_VERIFY_TOKEN"],
            app_secret=os.environ["WA_APP_SECRET"],
            access_token=os.environ["WA_ACCESS_TOKEN"],
            phone_number_id=os.environ["WA_PHONE_NUMBER_ID"],
            graph_api_version=os.environ.get("WA_GRAPH_API_VERSION", "v23.0"),
            db_path=os.environ.get("WABOT_DB_PATH", "data/wabot.db"),
            owner_phone_number=owner,
        )
