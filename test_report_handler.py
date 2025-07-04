from requests import get, post, put, delete, HTTPError
from report_handler import create_analysis_report_from_files,upload_session
import os 
import json
import session
from datetime import datetime

def test_api2():

    report_root = "http://localhost:8000/reports/"

    initial_doc = create_analysis_report_from_files("c0df581f48e84161ac8c322dbd288cd3")

    # print(json.dumps(initial_doc,indent=2))

    response = post(report_root, json=initial_doc)
    response.raise_for_status()
    doc = response.json()
    inserted_id = doc["id"]
    print(f"Inserted document with id: {inserted_id}")


# print(os.getcwd())
# test_api2()


def test_session():

    root = "http://localhost:8000/session/"

    obj , initial_doc = session.Session().get("b1ccb1ef2b124f18ad99c2f81920e357")

    print(initial_doc)

    initial_doc["session_id"] = initial_doc["id"]
    initial_doc.pop("id")

    response = post(root, json=initial_doc)
    response.raise_for_status()
    doc = response.json()
    inserted_id = doc["id"]
    print(f"Inserted document with id: {inserted_id}")

    pass


# print(datetime.now())

# test_session()

def test_session_up():
    obj , initial_doc = session.Session().get("af813d78aa0244db9f7fec71da070776")
    # initial_doc = obj.to_dict()

    # initial_doc["session_id"] = initial_doc["id"]
    # initial_doc.pop("id")


    upload_session(obj)


# test_session_up()