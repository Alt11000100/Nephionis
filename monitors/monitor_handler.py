
import docker
import time

class MonitorHandler():
    def __init__(self,enable_queue = False):
        self.client = docker.from_env()
        # these are left for rabbitmq container - unused
        self.queue_ip = None

        if enable_queue:
            queue = self.client.containers.get("rabbitmq")
            
            self.queue_ip = queue.attrs['NetworkSettings']['IPAddress']
        

    
   
    
# MonitorHandler()
