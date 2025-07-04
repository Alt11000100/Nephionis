import pika
import os
import json
import aio_pika

ANALYSIS_ID = os.getenv('ANALYSIS_ID')

def send_json(dictionary,target = '172.17.0.2',queue = 'hello'): # need to adjust host

    # dictionary = {
    #     "session_id" : f"{ANALYSIS_ID}",
    #     "report_type" : "benchmarker",
    # }

    message = json.dumps(dictionary).encode('utf-8')

    connection = pika.BlockingConnection(pika.ConnectionParameters(target))
    channel = connection.channel()
    channel.queue_declare(queue=queue)
    channel.basic_publish(exchange='',
                      routing_key='hello',
                      body=message)
    
    print(f" [x] Sent {dictionary}")


def connect_to_queue(QUEUE,AMQP_URL,data=""):
    """
    Establishes a connection to the message queue and declares the performance analysis queue.
    Returns:
        tuple: A tuple containing the channel and connection objects.
    """
    
    connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
    channel = connection.channel()

    channel.queue_declare(queue=QUEUE, durable=True)

    # print(channel,connection)
    # message = json.dumps(data).encode('utf-8')

    # channel.basic_publish(exchange='',
    #       routing_key=QUEUE,
    #       body=message,
    #       properties=pika.BasicProperties(
    #          delivery_mode = 2, # make message persistent
    #       ))

    # print(f" [x] Sent {message}")
    
    return channel, connection

# send_json()