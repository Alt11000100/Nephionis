import pika, sys, os
from requests import post
import json

def main():

    QUEUE_IP = os.getenv('QUEUE_IP')
    print("THIS IS WHAT I WANT",QUEUE_IP)

    

    connection = pika.BlockingConnection(pika.ConnectionParameters(host=QUEUE_IP)) # need to adjust host
    channel = connection.channel()

    channel.queue_declare(queue='hello')

    def callback(ch, method, properties, body):

        # print(f" [x] Received {body}")
        data = json.loads(body.decode("utf-8"))
        # print(f" [x] Received {type(data)}")

        response = post("http://localhost:8000/reports/", json=data  )
        # print(response)
        response.raise_for_status()
        doc = response.json()
        inserted_id = doc["id"]
        print(f"Inserted document with id: {inserted_id}")


    channel.basic_consume(queue='hello', on_message_callback=callback, auto_ack=True)

    print(' [*] Waiting for messages. To exit press CTRL+C')
    channel.start_consuming()

    # AMQP_URL = os.getenv('AMQP_URL')
    # QUEUE = os.getenv('QUEUE')
    

    # connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
    # channel = connection.channel()
    # channel.queue_declare(queue=QUEUE, durable=True)


    # def callback(ch, method, properties, body):
    #     try:
    #         data = json.loads(body)
    #         collection.insert_one(data)
    #         ch.basic_ack(delivery_tag=method.delivery_tag)
    #         print(f"Stored: {data}")
    #     except Exception as e:
    #         print("Error:", e)
    #         ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    # channel.basic_consume(queue="json_input_queue", on_message_callback=callback)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Interrupted')
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)