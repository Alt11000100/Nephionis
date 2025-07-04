import os
from typing import Optional, List

from fastapi import FastAPI, Body, HTTPException, status
from fastapi.responses import Response
from pydantic import ConfigDict, BaseModel, Field, EmailStr
from pydantic.functional_validators import BeforeValidator

from typing_extensions import Annotated

from bson import ObjectId
import motor.motor_asyncio
from pymongo import ReturnDocument

from models import SessionModel

MONGODB_URL = ""

app = FastAPI(
    title="The API",
    summary="A sample application showing how to use FastAPI to add a ReST API to a MongoDB collection.",
)
# fix this as secret 
# client = motor.motor_asyncio.AsyncIOMotorClient(os.environ["MONGODB_URL"])
client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URL)


db = client.college
student_collection = db.get_collection("students")

# User collections 
# this holds the binaries to analyze
db = client.playground
malware_collection = db.get_collection("malware")

# For the reports
report_collection = db.get_collection("reports")

# For the sessions 
session_collection = db.get_collection("sessions")


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




class StudentModel(BaseModel):
    """
    Container for a single student record.
    """

    # The primary key for the StudentModel, stored as a `str` on the instance.
    # This will be aliased to `_id` when sent to MongoDB,
    # but provided as `id` in the API requests and responses.
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    name: str = Field(...)
    email: EmailStr = Field(...)
    course: str = Field(...)
    gpa: float = Field(..., le=4.0)
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_schema_extra={
            "example": {
                "name": "Jane Doe",
                "email": "jdoe@example.com",
                "course": "Experiments, Science, and Fashion in Nanophotonics",
                "gpa": 3.0,
            }
        },
    )


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



class UpdateStudentModel(BaseModel):
    """
    A set of optional updates to be made to a document in the database.
    """

    name: Optional[str] = None
    email: Optional[EmailStr] = None
    course: Optional[str] = None
    gpa: Optional[float] = None
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        json_schema_extra={
            "example": {
                "name": "Jane Doe",
                "email": "jdoe@example.com",
                "course": "Experiments, Science, and Fashion in Nanophotonics",
                "gpa": 3.0,
            }
        },
    )

class UpdateMalwareModel(BaseModel):
    """
    A set of optional updates to be made to a document in the database.
    """

    name: Optional[str] = None
    hash: Optional[str] = None
    uri: Optional[str] = None
    type: Optional[float] = None
    bitness: Optional[int] = None
    tags: Optional[List[str]] = None
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        json_schema_extra={
            "example": {
                "name": "Mirai Variant",
                "hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "uri": "https://bazaar.abuse.ch/sample/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/",
                "type": "elf",
                "bitness": 64,
                "tags": ["Mirai", "variant", "elf"],
            }
        },
    )


class StudentCollection(BaseModel):
    """
    A container holding a list of `StudentModel` instances.

    This exists because providing a top-level array in a JSON response can be a [vulnerability](https://haacked.com/archive/2009/06/25/json-hijacking.aspx/)
    """

    students: List[StudentModel]

class MalwareCollection(BaseModel):
    """
    A container holding a list of `MalwareModel` instances.

    This exists because providing a top-level array in a JSON response can be a [vulnerability](https://haacked.com/archive/2009/06/25/json-hijacking.aspx/)
    """
    malwares: List[MalwareModel]

class ReportCollection(BaseModel):
    """
    A container holding a list of `BenchmarkerReport` instances.

    This exists because providing a top-level array in a JSON response can be a [vulnerability](https://haacked.com/archive/2009/06/25/json-hijacking.aspx/)
    """
    reports: List[BenchmarkerReport]


class SessionCollection(BaseModel):
    """
    A container holding a list of `SessionModel` instances.

    This exists because providing a top-level array in a JSON response can be a [vulnerability](https://haacked.com/archive/2009/06/25/json-hijacking.aspx/)
    """
    sessions: List[SessionModel]



@app.post(
    "/students/",
    response_description="Add new student",
    response_model=StudentModel,
    status_code=status.HTTP_201_CREATED,
    response_model_by_alias=False,
)
async def create_student(student: StudentModel = Body(...)):
    """
    Insert a new student record.

    A unique `id` will be created and provided in the response.
    """
    new_student = await student_collection.insert_one(
        student.model_dump(by_alias=True, exclude=["id"])
    )
    created_student = await student_collection.find_one(
        {"_id": new_student.inserted_id}
    )
    return created_student


@app.post(
    "/malware/",
    response_description="Add new malware sample",
    response_model=MalwareModel,
    status_code=status.HTTP_201_CREATED,
    response_model_by_alias=False,
)
async def create_malware(malware: MalwareModel = Body(...)):
    """
    Insert a new malware record.

    A unique `_id` will be created and provided in the response.
    """
    new_malware = await malware_collection.insert_one(
        malware.model_dump(by_alias=True, exclude=["id"])
    )
    created_malware = await malware_collection.find_one(
        {"_id": new_malware.inserted_id}
    )
    return created_malware

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


@app.post(
    "/session/",
    response_description="Add new session sample",
    response_model=SessionModel,
    status_code=status.HTTP_201_CREATED,
    response_model_by_alias=False,
)
async def create_session(session: SessionModel = Body(...)):
    """
    Insert a new session record.

    A unique `_id` will be created and provided in the response.
    """
    new_session = await session_collection.insert_one(
        session.model_dump(by_alias=True, exclude=["id"])
    )
    created_session= await session_collection.find_one(
        {"_id": new_session.inserted_id}
    )
    return created_session



@app.get(
    "/students/",
    response_description="List all students",
    response_model=StudentCollection,
    response_model_by_alias=False,
)
async def list_students():
    """
    List all of the student data in the database.

    The response is unpaginated and limited to 1000 results.
    """
    return StudentCollection(students=await student_collection.find().to_list(1000))



@app.get(
    "/malware/",
    response_description="List all malware samples",
    response_model=MalwareCollection,
    response_model_by_alias=False,
)
async def list_malware():
    """
    List all of the malware data in the database.

    The response is unpaginated and limited to 1000 results.
    """
    malware_list = await malware_collection.find().to_list(1000)
    return MalwareCollection(malwares=malware_list)

@app.get(
    "/session/",
    response_description="List all sessions",
    response_model=SessionCollection,
    response_model_by_alias=False,
)
async def list_session():
    """
    List all of the session data in the database.

    The response is unpaginated and limited to 1000 results.
    """
    session_list = await session_collection.find().to_list(1000)
    return SessionCollection(sessions=session_list)

@app.get(
    "/reports/",
    response_description="List all reports",
    response_model=ReportCollection,
    response_model_by_alias=False,
)
async def list_reports():
    """
    List all of the session data in the database.

    The response is unpaginated and limited to 1000 results.
    """
    report_list = await report_collection.find().to_list(1000)
    return ReportCollection(reports=report_list)



@app.get(
    "/students/{id}",
    response_description="Get a single student",
    response_model=StudentModel,
    response_model_by_alias=False,
)
async def show_student(id: str):
    """
    Get the record for a specific student, looked up by `id`.
    """
    if (
        student := await student_collection.find_one({"_id": ObjectId(id)})
    ) is not None:
        return student

    raise HTTPException(status_code=404, detail=f"Student {id} not found")

@app.get(
    "/malware/{id}",
    response_description="Get a single malware",
    response_model=MalwareModel,
    response_model_by_alias=False,
)
async def show_malware(id: str):
    """
    Get the record for a specific malware, looked up by `id`. looked by 'name' right now
    """
    if (
        # malware := await malware_collection.find_one({"_id": ObjectId(id)})
        malware := await malware_collection.find_one({"name": id})
    ) is not None:
        return malware

    raise HTTPException(status_code=404, detail=f"Malware {id} not found")


@app.get(
    "/session/{id}",
    response_description="Get a single session",
    response_model=SessionModel,
    response_model_by_alias=False,
)
async def show_session(id: str):
    """
    Get the record for a specific session, looked up by `session_id`.
    """
    if (
        # malware := await malware_collection.find_one({"_id": ObjectId(id)})
        session := await session_collection.find_one({"session_id": id})
    ) is not None:
        return session

    raise HTTPException(status_code=404, detail=f"Session {id} not found")


@app.get(
    "/reports/{id}",
    response_description="Get a single report",
    response_model=BenchmarkerReport,
    response_model_by_alias=False,
)
async def show_report(id: str):
    """
    Get the record for a specific session, looked up by `session_id`.
    """
    if (
        # malware := await malware_collection.find_one({"_id": ObjectId(id)})
        report := await report_collection.find_one({"session_id": id})
    ) is not None:
        return report

    raise HTTPException(status_code=404, detail=f"Report {id} not found")



@app.put(
    "/students/{id}",
    response_description="Update a student",
    response_model=StudentModel,
    response_model_by_alias=False,
)
async def update_student(id: str, student: UpdateStudentModel = Body(...)):
    """
    Update individual fields of an existing student record.

    Only the provided fields will be updated.
    Any missing or `null` fields will be ignored.
    """
    student = {
        k: v for k, v in student.model_dump(by_alias=True).items() if v is not None
    }

    if len(student) >= 1:
        update_result = await student_collection.find_one_and_update(
            {"_id": ObjectId(id)},
            {"$set": student},
            return_document=ReturnDocument.AFTER,
        )
        if update_result is not None:
            return update_result
        else:
            raise HTTPException(status_code=404, detail=f"Student {id} not found")

    # The update is empty, but we should still return the matching document:
    if (existing_student := await student_collection.find_one({"_id": id})) is not None:
        return existing_student

    raise HTTPException(status_code=404, detail=f"Student {id} not found")


@app.delete("/students/{id}", response_description="Delete a student")
async def delete_student(id: str):
    """
    Remove a single student record from the database.
    """
    delete_result = await student_collection.delete_one({"_id": ObjectId(id)})

    if delete_result.deleted_count == 1:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    raise HTTPException(status_code=404, detail=f"Student {id} not found")
