from pydantic import BaseModel


class SettingResponse(BaseModel):
    key: str
    value: str
    group: str
    display_name: str
    is_secret: bool
    source: str  # "database" or "env"

    model_config = {"from_attributes": True}


class SettingUpdate(BaseModel):
    value: str


class SettingsGroupResponse(BaseModel):
    group: str
    display_name: str
    settings: list[SettingResponse]


class SettingsBulkUpdate(BaseModel):
    settings: dict[str, str]


class ConnectionTestResult(BaseModel):
    success: bool
    message: str
