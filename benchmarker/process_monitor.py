from benchmarker import Benchmarker
import os
import json
from dotenv import load_dotenv
import requests
from send import send_json,connect_to_queue
import asyncio
import aio_pika
from multiprocessing import  Manager
from multiprocessing.managers import ListProxy, DictProxy

 # bm = benchmarker.Benchmarker(execution_environment='docker-gvisor')

# script = ''
# requirements = 'requirements.txt'
# bm.bencmark_python3_script(script, requirements)
# bm.get_raw_results()
# bm.get_statistics_full()
from collections import deque

def convert_proxy_to_serializable(d):
    regular_dict = dict(d)  # convert DictProxy to normal dict
    for key, value in regular_dict.items():
        # convert deques to lists for serialization
        if isinstance(value, (ListProxy, list)):
            regular_dict[key] = list(value)
        # Optionally, handle nested dicts too
        elif isinstance(value, DictProxy):
            regular_dict[key] = convert_proxy_to_serializable(value)
        # Add more conversions if you have other non-serializable types
    print(f"deseriliazing {d} to {regular_dict}")
    return regular_dict



async def periodic_amqp_send(bm, amqp_channel, queue_name, interval=0.5):
    while True:
        await asyncio.sleep(interval)

        safe_dict = convert_proxy_to_serializable(bm.shared_process_dict)
        print(safe_dict)
        # Serialize the dict safely
        body = json.dumps(safe_dict).encode()
        print("I will send something")
        await amqp_channel.default_exchange.publish(
            aio_pika.Message(body=body),
            routing_key=queue_name
        )


async def main() -> None:
    """
    Main function to run the benchmarker in Docker mode.

    This function serves as the entry point for the benchmarker when executed in docker. 
    It initializes and executes the Benchmarker to analyze a Python 3 script. Finally, 
    it saves the results-<analysis_id>.json, statistics-<analysis_id>.json, and 
    metadata-<analysis_id>.json files in the specified results folder.

    Environment Variables Required:
    - ANALYSIS_ID: A unique identifier for the analysis.
    - EXPERIMENT_WORKDIR: The relative (to Dockerfile WORKDIR) working directory path for 
        the experiment, i.e., the execution folder (e.g. ./code_runner/).
    - REQUIREMENTS_FILE: The path to the requirements file for the experiment, 
        relative to the working directory.
    - EXPERIMENT_FILE: The path to the experiment file to be benchmarked, 
        relative to the working directory.
    - RESULTS_FOLDER: The folder where the results, statistics, and metadata will be saved, 
        relative to the working directory.
    """

    # load_dotenv()

    ANALYSIS_ID = os.getenv('ANALYSIS_ID')
    # EXPERIMENT_WORKDIR = os.getenv('EXPERIMENT_WORKDIR')
    REQUIREMENTS_FILE = os.getenv('REQUIREMENTS_FILE')
    EXPERIMENT_FILE = os.getenv('EXPERIMENT_FILE')
    # EXPERIMENT_FILE = "./anti_techniques"
    RESULTS_FOLDER = os.getenv('RESULTS_FOLDER')
    # QUEUE_IP = os.getenv('QUEUE_IP')
    QUEUE = os.getenv('QUEUE')
    AMQP_URL = os.getenv('RBQQAM')


    

    bm = Benchmarker(interval=0.1, ishost=False, execution_environment='docker-gvisor')


    # result = bm.bencmark_python3_script(EXPERIMENT_FILE, REQUIREMENTS_FILE)
    

    

    connection = await aio_pika.connect_robust(AMQP_URL)
    channel = await connection.channel()
    await channel.declare_queue(QUEUE, durable=True)

    # Start periodic sender
    periodic_task = asyncio.create_task(periodic_amqp_send(bm, channel, QUEUE))

    try:
        result = await asyncio.to_thread(bm.benchmark_command, EXPERIMENT_FILE)
        statistics = await asyncio.to_thread(bm.get_statistics_basic)

        metadata = await asyncio.to_thread(bm.get_metadata)

        dictionary = {
        "session_id" : f"{ANALYSIS_ID}",
        "report_type" : "benchmarker",
        "metadata" : metadata,
        "result" : result,
        "statistics" : statistics,
        }
        

        message = json.dumps(dictionary).encode('utf-8')
        print(message)

        await channel.default_exchange.publish(
            aio_pika.Message(body=message),
            routing_key=QUEUE
        )

    finally:
        periodic_task.cancel()
        print("All done from here")
        try:
            await periodic_task
        except asyncio.CancelledError:
            print("Cancelled!")
            pass
        await connection.close()

    # result = bm.benchmark_command(EXPERIMENT_FILE)
    # statistics = bm.get_statistics_basic()
    # metadata = bm.get_metadata()

    # os.makedirs(RESULTS_FOLDER, exist_ok=True)

    

    # dictionary = {
    #     "session_id" : f"{ANALYSIS_ID}",
    #     "report_type" : "benchmarker",
    #     "metadata" : metadata,
    #     "result" : result,
    #     "statistics" : statistics,
    # }
    # # print(result)
    # try:
    #     # send_json(dictionary,QUEUE_IP)
    #     connect_to_queue(QUEUE=QUEUE,AMQP_URL=AMQP_URL,data=dictionary)
    # except Exception as e:
    #     print(f"Exception when sending to queue {e}")

        
    # response = requests.post("http://172.17.0.3:8000/reports/", json=dictionary)
    # response.raise_for_status()
    # doc = response.json()
    # inserted_id = doc["id"]
    # print(f"Inserted document with id: {inserted_id}")

    try:

        with open(os.path.join(RESULTS_FOLDER, f'result-{ANALYSIS_ID}.json'), 'w') as f:
            json.dump(result, f, indent=4)
        with open(os.path.join(RESULTS_FOLDER, f'statistics-{ANALYSIS_ID}.json'), 'w') as f:
            json.dump(statistics, f, indent=4)
        with open(os.path.join(RESULTS_FOLDER, f'metadata-{ANALYSIS_ID}.json'), 'w') as f:
            json.dump(metadata, f, indent=4)
    except Exception as e:
        print(f"Exception when writing the results {e}")
if __name__ == "__main__":
    asyncio.run(main())