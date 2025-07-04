import json
import os
from typing import Dict
from backend.models import BenchmarkerReport
import aiohttp
import asyncio
import time
import re
from pymongo import MongoClient

from pydantic import ConfigDict, BaseModel, Field
from pydantic.functional_validators import BeforeValidator

from typing_extensions import Annotated
from typing import Optional, List

# MONGO_CLIENT = os.getenv('MONGO_CLIENT')
MONGO_CLIENT = "" # make it secret
DB = "playground"

PyObjectId = Annotated[str, BeforeValidator(str)]

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


def load_json_file(filepath: str) -> Dict:
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)
    

def create_analysis_report_from_files(
    analysis_id: str,
    base_path: str="my_results"
    ):
    """
    Loads metadata, results, and statistics JSON files for a given analysis_id
   
    :param analysis_id: Unique ID for the analysis (used in filenames)
    :param base_path: Directory containing the JSON files
    :return: Dict
    """
    base_path = f"{os.path.dirname(__file__)}/my_results" 

    metadata_path = os.path.join(base_path, f"metadata-{analysis_id}.json")
    results_path = os.path.join(base_path, f"result-{analysis_id}.json")
    statistics_path = os.path.join(base_path, f"statistics-{analysis_id}.json")

    metadata = load_json_file(metadata_path)
    result = load_json_file(results_path)
    statistics = load_json_file(statistics_path)

    dictionary = {
        "session_id" : f"{analysis_id}",
        "report_type" : "benchmarker",
        "metadata" : metadata,
        "result" : result,
        "statistics" : statistics,
    }

    # report = BenchmarkerReport(
    #     session_id=analysis_id,
    #     report_type="benchmarker",
    #     metadata=metadata,
    #     result=results,
    #     statistics=statistics

    # )
    # print(type(metadata))
    return dictionary


# create_analysis_report_from_files("c0df581f48e84161ac8c322dbd288cd3")


async def fetch_data(session, url,params):
    ''' Async requests'''
    # print(f"Starting task: {url} , {params}")
    try:
        async with session.get(url,params=params) as response:
            response.raise_for_status()  # Raise exception for HTTP errors
            
            data = await response.json()
            # print(f"Completed task: {url}")
            return data
    except aiohttp.ClientError as e:
        print(f"Error fetching data from {url}: {e}")
    except asyncio.TimeoutError:
        print(f"Request to {url} timed out")


async def prom_raw( session_id = "1bb05bc397af4045821869795eabc01d",STEP = "2s"):

    '''Write in files the raw data from prometheus queries. '''

    PROMETHEUS_URL = "http://localhost:9090"
    url =  f"{PROMETHEUS_URL}/api/v1/query_range"
    # QUERY = '(container_fs_usage_bytes{name="redis"})'
    END = int(time.time()) - (int(time.time()) % 30) # 
    START = END - 3600
    

    queries = [ f'sum by (name) (rate(container_cpu_usage_seconds_total{{name=~"sandbox_{session_id}"}}[1m])) * 100', 
               f'container_memory_working_set_bytes{{name=~"sandbox_{session_id}"}}',
               f'(container_fs_usage_bytes{{name="sandbox_{session_id}"}})', 
               f'sum by (name) (rate(container_fs_reads_bytes_total{{name="sandbox_{session_id}"}}[1m]) + rate(container_fs_writes_bytes_total{{name="sandbox_{session_id}"}}[1m]))',
              f'sum by (name) (rate(container_network_receive_bytes_total{{name=~"sandbox_{session_id}"}}[1m]) + rate(container_network_transmit_bytes_total{{name=~"sandbox_{session_id}"}}[1m]))'
    ]
    res_dir = f'{os.path.dirname(__file__)}/prometheus_results/{session_id}'
    os.makedirs(res_dir, exist_ok=True)

    async with aiohttp.ClientSession() as session:
        tasks = [fetch_data(session, url,params={
            "query": query,
            "start": START,
            "end": END,
            "step": STEP,
        },) for query in queries]
        results = await asyncio.gather(*tasks)

        upload_prom(session_id,results)

        for query, result in zip(queries, results):
            metric_name = extract_metric(query)
            filename = os.path.join(res_dir,f"{metric_name}.json")
            with open(filename, "w") as f:
                json.dump(result, f, indent=2)
            print(f"Saved {filename}")


def extract_metric(query):
    '''Uses some regex matching to extract the name of the query'''
    match = re.search(r'rate\(([^({]+)', query)

    if not match:
        match = re.search(r'(?:rate\()?([a-zA-Z_][a-zA-Z0-9_]*)[^{]*\{', query)
        if not match:
            return "unknown_metric"
        
    return match.group(1)



def upload_session(session):
    mongo = MongoClient(MONGO_CLIENT)
    db = mongo[DB]
    collection = db["session"]
    try:
        initial_doc = session.to_dict()

        initial_doc["session_id"] = initial_doc["id"]
        initial_doc.pop("id")

        validated = SessionModel(**initial_doc)

        collection.insert_one(validated.model_dump())

        print(f"Stored {validated}")
    except Exception as e:
        print(f" Exception when trying to upload session to mongo : {e}")


def upload_docker_stats(session_id):
    mongo = MongoClient(MONGO_CLIENT)
    db = mongo[DB]
    collection = db["docker_stats"]

    base_path = f"{os.path.dirname(__file__)}/docker_stats" 

    
    results_path = os.path.join(base_path, f"result-{session_id}.json")
    

    stats = load_json_file(results_path)


    try:
        

        collection.insert_one(stats)

        print(f"Stored {stats}")
    except Exception as e:
        print(f" Exception when trying to upload docker stats to mongo : {e}")


def upload_prom(session_id,results):
    mongo = MongoClient(MONGO_CLIENT)
    db = mongo[DB]
    collection = db["reports"]

    dictionary = {
        "session_id" : f"{session_id}",
        "report_type" : "prometheus",
        
        "results" : results,
    }


    try:
        

        collection.insert_one(dictionary)

        print(f"Stored {dictionary}")
    except Exception as e:
        print(f" Exception when trying to upload docker stats to mongo : {e}")   


# upload_docker_stats("6a392557af734a018d66d23d7732fc10")

# session_id = "b1ccb1ef2b124f18ad99c2f81920e357"

# # s = f'sum by (name) (rate(container_cpu_usage_seconds_total{{name=~"sandbox_{session_id}"}}[1m])) * 100'
# s = f'container_memory_working_set_bytes{{name=~"sandbox_{session_id}"}}'


# print(re.search(r'(?:rate\()?([a-zA-Z_][a-zA-Z0-9_]*)[^{]*\{', s))


# asyncio.run(prom_raw())
