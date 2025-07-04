import docker

class ProcessBenchmarker():
    def __init__(self,sandbox_id):
        self.client = docker.from_env()
        # self.sandbox = self.client.containers.get("proc_mon") # fix for correct name
        self.sandbox = self.client.containers.get("sandbox_"+sandbox_id)
        pass
        
    def run_analysis(self):
        '''Function to start benchmarker.py'''
        try:
            self.sandbox.exec_run(cmd=["/venv/bin/python", "process_monitor.py"])
        except Exception as e:
            print(f"Exception when running benchmarker {e}")
    

    

# ProcessBenchmarker("6da28d7cb2b74f00b3cc23b1f224f743").run_analysis()