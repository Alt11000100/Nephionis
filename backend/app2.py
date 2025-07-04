
import os
from typing import Optional, List

from fastapi import FastAPI, Body, HTTPException, status
from fastapi.responses import Response
from pydantic import ConfigDict, BaseModel, Field, EmailStr
from pydantic.functional_validators import BeforeValidator

from typing_extensions import Annotated


import motor.motor_asyncio





MONGODB_URL = ""

app = FastAPI(
    title="The API",
    summary="A sample application to communicate with mongodb",
)

PyObjectId = Annotated[str, BeforeValidator(str)]


client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URL)


db = client.playground

report_collection = db.get_collection("reports")

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
        arbitrary_types_allowed=False,
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


class ReportCollection(BaseModel):
    """
    A container holding a list of `BenchmarkerReport` instances.

    This exists because providing a top-level array in a JSON response can be a [vulnerability](https://haacked.com/archive/2009/06/25/json-hijacking.aspx/)
    """
    reports: List[BenchmarkerReport]


@app.post(
    "/reports/",
    response_description="Add new report sample",
    response_model=BenchmarkerReport,
    status_code=status.HTTP_201_CREATED,
    response_model_by_alias=False,
)
async def create_report(report: BenchmarkerReport = Body(...)):
    """
    Insert a new report record.

    A unique `_id` will be created and provided in the response.
    """
    new_report = await report_collection.insert_one(
        report.model_dump(by_alias=True, exclude=["id"])
    )
    created_report = await report_collection.find_one(
        {"_id": new_report.inserted_id}
    )
    return created_report
