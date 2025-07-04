import docker
import os
from docker_builder import Builder 
# import session as ses
# from monitors.process_monitor import ProcessBenchmarker


class SandboxHandler():
    '''Initialize a container with runsc'''

    def __init__(self,id="1",runtime="runsc"):
        self.id = id
        self.client = docker.from_env()
        self.runtime = runtime
        self.name = "SandboxHandler"
        pass

    # Start 
    def create_sandbox(self,net=""):
        '''assuming that this image already exists'''

        proc_mon = self.client.containers.run(
            "proc_mon:3", # should be 2
            name="proc_mon", # this should be randomly generated later
            detach=True,  # Run in the background
            # network=net.name, # Attach to the custom network
            volumes={
                f"{os.getcwd()}/my_results": {
                    "bind": "/app/results",
                    "mode": "rw"
                }
            },
            runtime=self.runtime, # Gvisor Runtime!
            # runtime="io.containerd.kata.v2", # Kata runtime!
            command=["tail", "-f", "/dev/null"], # that command keeps container alive but is this logical?
            labels={"created_by": self.name }  # Add a custom label
        )
       
        return proc_mon
    
    def create_sandbox_from_session(self,session,queue_ip=""):
        # Build an image as from session
        builder = Builder()
        # Specify tag to build image
        image = builder.build_image(session.id,session.buildargs)

        # If flag is set process monitor will be enabled
        if session.process_monitor_flag:
            # env_vars = {"ANALYSIS_ID" : session.id}

            env_vars = session.env_for_process_monitor(queue_ip)
        else:
            env_vars = None

        if session.configuration["user_emul"]:
            cmd = None
        else:
            cmd = ["tail", "-f", "/dev/null"]

        sandbox = self.client.containers.run(
            image,
            name=f"sandbox_{session.id}",
            detach=True,
            network_disabled=session.configuration["network_disabled"],
            runtime=self.runtime,
            command=cmd, # that command keeps container alive but is this logical?
            labels={"created_by": self.name },  # Add a custom label
            environment=env_vars,
            mem_limit='8g',
            volumes={
                f"{os.path.dirname(__file__)}/my_results": {
                    "bind": "/app/results",
                    "mode": "rw"
                }
            }

        )
        return sandbox , image



    
    def stop_and_remove_labelled_containers(self):
        ''''''
        containers = self.client.containers.list(all=True)
        for container in containers:
            if container.labels.get("created_by") == self.name:
                print(f"Stopping and removing container: {container.id}")
                container.stop()
                container.remove()
    

    
    def install_malware(self,container):
        # this could work either with just specifying a file somewhere, downloading from a remote etc
        # for now we can try specify a file
        
        
        pass

    
# Test

# SandboxHandler().create_sandbox()
# SandboxHandler().stop_and_remove_labelled_containers()

# tmp = ses.Session()
# SandboxHandler().create_sandbox_from_session()

# ProcessBenchmarker(tmp.id).run_analysis()

# print(f"{os.path.dirname(__file__)}/my_results")


