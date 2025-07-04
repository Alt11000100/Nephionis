import os
from typing import Optional, List


from fastapi.responses import Response
from pydantic import ConfigDict, BaseModel, Field, EmailStr
from pydantic.functional_validators import BeforeValidator

from typing_extensions import Annotated




# Represents an ObjectId field in the database.
# It will be represented as a `str` on the model so that it can be serialized to JSON.
PyObjectId = Annotated[str, BeforeValidator(str)]


class BenchmarkerReport(BaseModel):
    """
    Container for a benchmarker report.
    """
    id: Optional[PyObjectId] = Field(alias="_id", default=None)

    session_id: str = Field(...)
    report_type: str = Field(...)
    metadata: dict
    result: dict
    statistics: dict
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_schema_extra={
            "example": {
                "session_id": "6da28d7cb2b74f00b3cc23b1f224f743",
                "report_type": "benchmarker",
                "metadata" : {},
                "results" : {},
                "statistics" : {},
            }
        },
    )

class SessionModel(BaseModel):
    """
    Container for a session.
    """


    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    session_id : str = Field(...)
    name: str
    sha256: str
    buildargs: dict
    process_monitor_flag: bool
    timestamp: str
    executed: str
    configuration: dict
    reports_list: Optional[List[PyObjectId]] = Field(default_factory=list)

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    }

class MalwareModel(BaseModel):
    """
    Container for a single malware binary.
    """
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    name: str = Field(...)
    hash: str = Field(...)
    uri: str = Field(...)
    type: str = Field(...)
    bitness: int = Field(...)
    tags: List[str] = Field(default_factory=list)

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_schema_extra": {
            "example": {
                "name": "Mirai",
                "hash": "e11271171067715941a63b98d2a2ccca756b5e90c3df6fac27712f5ca6a624ae",
                "uri": "https://bazaar.abuse.ch/sample/e11271171067715941a63b98d2a2ccca756b5e90c3df6fac27712f5ca6a624ae/",
                "type": "elf",
                "bitness": 64,
                "tags": ["Mirai", "elf", "64"]
            }
        }
    }