import os 
import pika
import json
from pymongo import MongoClient
import sys

from pydantic import ConfigDict, BaseModel, Field
from pydantic.functional_validators import BeforeValidator

from typing_extensions import Annotated
from typing import Optional, List

AMQP_URL = os.getenv('AMQP_URL')
QUEUE = os.getenv('QUEUE')
MONGO_CLIENT = os.getenv('MONGO_CLIENT')
COLLECTION =  os.getenv('COLLECTION')
DB = os.getenv('DB')


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

def main():   

    mongo = MongoClient(MONGO_CLIENT)
    db = mongo[DB]
    collection = db[COLLECTION]
   
    channel , connection = connect_to_queue()


    def callback(ch, method, properties, body):
        try:
            data = json.loads(body)

            
            if data.get("session_id"):
                validated = BenchmarkerReport(**data)
                collection.insert_one(validated.model_dump())
                ch.basic_ack(delivery_tag=method.delivery_tag)
                print(f"Stored: {data}")
            else:
                ch.basic_ack(delivery_tag=method.delivery_tag)
                print(f"Got this {data}")
                
        except Exception as e:
            print("Error:", e)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    channel.basic_consume(queue=QUEUE, on_message_callback=callback)

    print(' [*] Waiting for messages. To exit press CTRL+C')
    channel.start_consuming()

def connect_to_queue():
    """
    Establishes a connection to the message queue and declares the performance analysis queue.
    Returns:
        tuple: A tuple containing the channel and connection objects.
    """

    connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
    channel = connection.channel()

    channel.queue_declare(queue=QUEUE, durable=True)
    channel.basic_qos(prefetch_count=1)

    return channel, connection

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Interrupted')
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)