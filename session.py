import os
import uuid
import json
from datetime import datetime
import typer
from monitors.monitor_handler import MonitorHandler
from sandbox_handler import SandboxHandler
from monitors.process_monitor import ProcessBenchmarker
from monitors.performance_monitor import PerformanceMonitorSandbox
from monitors.docker_stats import DockerStats
from docker_builder import Builder
import report_handler
import asyncio
from templates.template_manager import create_dockerfile
from threading import Event
import threading
import report_handler

exception_event = Event()

class Session():
    '''This could be a class for all of the configurations'''

    def __init__(self,name:str="test",sha256="none",buildargs={"malware_file":"anti_techniques"},process_monitor_flag=True):
        # Unique identifier
        self.id = uuid.uuid4().hex
        # Name of session
        self.name = name
        # sha256 of file being analyzed
        self.sha256 = sha256
        # Analyzers being used?
        self.process_monitor_flag = process_monitor_flag
        # timestamp? created last execution
        self.timestamp = datetime.now().isoformat() # fix time
        self.executed = "No"
        # Environmental variables?
        self.configuration = {"provide_raw" : True , 
                              "user_emul" : False,
                              "ubuntu_image" : "latest",
                              "prometheus_scrape_interval": "5s",
                              "add_to_db" : False,
                              "network_disabled" : False
                              }
        # Report generated?
        self.reports_list = []
        # Name of binary for now or buildargs probably later
        self.buildargs = buildargs

    @classmethod
    def get(cls, session_id: str):
        path = os.path.join("sessions/", f"session-{session_id}.json")
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Session with ID '{session_id}' not found.")

        with open(path, "r") as f:
            data = json.load(f)

        # Construct the object using stored data
        obj = cls(
            name=data.get("name", "test"),
            sha256=data.get("sha256", "none"),
            buildargs=data.get("buildargs", {"malware_file": "unknown"}),
            process_monitor_flag=data.get("process_monitor_flag", True),
           
        )
        obj.id = data.get("id")  # override random ID
        obj.timestamp = data.get("timestamp")  # set timestamp
        obj.executed = data.get("executed")
        obj.configuration = data.get("configuration")
        obj.reports_list = data.get("reports_list")

        return obj,data

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "sha256": self.sha256,
            "buildargs": self.buildargs,
            "process_monitor_flag": self.process_monitor_flag,
            "timestamp": self.timestamp,
            "executed" : self.executed,
            "configuration": self.configuration,
            "reports_list": self.reports_list,
        }

    def save_to_json(self,dir):
        os.makedirs(dir, exist_ok=True)
        file_path = os.path.join(dir, f"session-{self.id}.json")
        with open(file_path, "w") as f:
            json.dump(self.to_dict(), f, indent=4)
        return file_path

    def __repr__(self):
        return json.dumps(self.to_dict(), indent=4)


    def env_for_process_monitor(self,queue_ip=""):
        dictionary = {"ANALYSIS_ID": self.id,
                      "REQUIREMENTS_FILE" : "requirements.txt", # should fix accordingly, also .env overrides this?
                      "EXPERIMENT_FILE" : "/binary/" + self.buildargs.get("malware_file"), # for now just the name of the binary
                      "RESULTS_FOLDER" : 'results',
                      "QUEUE_IP" : queue_ip,
                      "QUEUE" : "BenchmarkerReports",
                      "RBQQAM" : "amqps://blnwivls:0CyZI5gJvRaZsgwAljN2rZnFZYZOTpBI@collie.lmq.cloudamqp.com/blnwivls" # url for amqp
                      }
        return dictionary
    

def create_session(malware_file: str,
    name: str ,
    sha256: str ,
    process_monitor_flag: bool ,
    binaries_dir : str,
    sessions_dir: str):
    ''' Create a session'''
    
    binary_filename = os.path.basename(malware_file)
    binary_path = os.path.join( binaries_dir , binary_filename)

    if not os.path.isfile(binary_path):
        typer.echo(f"❌ Error: File '{binary_path}' does not exist.", err=True)
        raise typer.Exit(1)



    try:
        buildargs_dict = {"malware_file" : binary_filename}
    except FileNotFoundError:
        typer.echo("❌ Invalid malware file for buildargs", err=True)
        raise typer.Exit(code=1)

    session = Session(
        name=name,
        sha256=sha256,
        buildargs=buildargs_dict,
        process_monitor_flag=process_monitor_flag
    )
    typer.echo(f"✅ Created session: {session}")

    json_path = session.save_to_json(sessions_dir)
    typer.echo(f"✅ Created session and saved to {json_path}")


def execute_session(session_id: str,sessions_dir:str,execute=True):
    '''Execute a session'''

    try:
        session, js = Session.get(session_id)
        # print("Session loaded:", session)
    except FileNotFoundError as e: # wrong error
        print("Error:", e)

    # Check if user wants raw data from prometheus
    monitor_up = False
    if session.configuration["provide_raw"] == True:
        monitor_up,b,c,d = PerformanceMonitorSandbox().are_running()
        if not monitor_up:
            # Monitor is not running
            typer.echo("Monitor is not running!")
            return
    
    # Create dockerfile based on session
    create_dockerfile(session.configuration["ubuntu_image"], "Dockerfile"  ,"binary" ,session.configuration["user_emul"])

    # mh = MonitorHandler()

    sd = SandboxHandler()
    sandbox , image = sd.create_sandbox_from_session(session)

    if execute:
        session.executed = datetime.now().isoformat()

        path = session.save_to_json(sessions_dir)
        
        docker_stats = DockerStats(sandbox,exception_event,session_id)
        docker_stats.start()
        try:
            ProcessBenchmarker(session.id).run_analysis()
            typer.echo(f"Finished analysis with id: {session.id} in Sandbox {sandbox} ")
            # upload session 
            report_handler.upload_session(session)
        except KeyboardInterrupt: # I don't think that's even possible
            print("Keyboard Interrupt!")
            exception_event.set()
            docker_stats.stop()
        except Exception as e:
            print(f"Exception when running analysis")
            exception_event.set()
            docker_stats.stop()
        
        try:
            exception_event.set()
            docker_stats.stop()
        except Exception as e:
            print(f"Exception when terminating docker stats thread {e}")
        
        
        sd.stop_and_remove_labelled_containers()

        Builder().remove_image(image)

        typer.echo(f"Deleted image {image}")
    else:
        typer.confirm("Done with container?",abort=True)
        sd.stop_and_remove_labelled_containers()

        Builder().remove_image(image)

        typer.echo(f"Deleted image {image}")


    
    # Write prometheus raw data | 
    return monitor_up
        
        # typer.confirm("Get raw data?",abort=True)
        # asyncio.run(report_handler.prom_raw(session_id))


# print(Session("Fr","23").id)

# print(Session().env_for_process_monitor())

# try:
#     session,js = Session.get("35af5b525fd14f6a920fc0e16dc4a178")
#     print("Session loaded:", session.configuration["provide_raw"])
# except FileNotFoundError as e:
#     print("Error:", e)

# typer.confirm("Get raw data?",abort=True)
# asyncio.run(report_handler.prom_raw("35af5b525fd14f6a920fc0e16dc4a178"))


