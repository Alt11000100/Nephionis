import os
import docker
import docker_builder
from modules import utils
from dotenv import dotenv_values



class BackendHandler():
    def __init__(self,enable_queue=True):
        self.client = docker.from_env()
        self.enable_queue = enable_queue
        # self.queue_ip = None
        
        
    def run(self):
        base_dir = os.path.dirname(__file__)
        dockerfile_path = os.path.join(base_dir, 'backend', 'Dockerfile_api')
        builder = docker_builder.Builder(dockerfile=dockerfile_path)
        image = builder.build_image(tag="backend",buildargs=None)

        backend = self.client.containers.run(
            image,
            name=f"backend",
            detach=True,
            #network=
            command=["uvicorn", "app:app", "--reload"],
            labels={"created_by": "BackendHandler" },  # Add a custom label
        )
        return backend
    
    def create_queue(self):
            '''Queue that benchmarker will send the reports to'''

            rabbitmq = self.client.containers.run(
                "rabbitmq:4-management", # 
                name="rabbitmq", #
                detach=True,  # Run in the background
                ports={'5672/tcp': 5672 ,
                    '15672/tcp' : 15672
                    },
                # network=net.name, # Attach to the custom network
                hostname="my-rabbit",
                labels={"created_by": "BackendHandler" }  # Add a custom label
            )
            
            return rabbitmq
    

    def receiver_up(self,queue_ip:str): 
        
        container = self.client.containers.get("backend")
        if container.status == "running":
            print("Thats fine!")
        # container.exec_run(cmd=["export" , f"QUEUE_IP='{queue_ip}'"])
            res = container.exec_run(cmd=["python", "receive.py"],detach=True,environment={"QUEUE_IP": queue_ip})
            print(res)
        


    def queue_up(self):
         
         if self.enable_queue:
            queue = self.create_queue()
            queue.reload()
            queue_ip = queue.attrs['NetworkSettings']['IPAddress']
            return queue_ip

    def backend_down(self):

        utils.stop_and_remove_labelled_containers("BackendHandler")



    def queue_receiver(self):
        base_dir = os.path.dirname(__file__)
        dockerfile_path = os.path.join(base_dir, 'queue', 'Dockerfile_queue')
        builder = docker_builder.Builder(dockerfile=dockerfile_path)
        image = builder.build_image(tag="receiver",buildargs=None)
        
        env_path = os.path.join(base_dir, 'queue', '.env')
        env_vars = dotenv_values(env_path)
        # print(env_vars)

        receiver = self.client.containers.run(
            image,
            name=f"receiver",
            detach=True,
            environment=env_vars,
            #network=
        #    command=["python", "receiver.py"],
           command=["tail", "-f", "/dev/null"],
            labels={"created_by": "BackendHandler" },  # Add a custom label
        )
        return receiver

# BackendHandler().run()
# BackendHandler().receiver_up('172.17.0.3')
# BackendHandler().backend_down()
    