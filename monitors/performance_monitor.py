import docker

import os
import time
from datetime import datetime
import docker.errors
import requests

import csv



class PerformanceMonitorSandbox():
    '''This class initiates the cadvisor-prometheus-grafana stack to monitor all containers-sandboxes'''

    def __init__(self,sandbox_id=""):
        self.sandbox_id = sandbox_id
        # List to store container IDs that were started by PerformanceMonitorSandbox
        self.started_containers = []
        # Initialize the Docker client maybe that shouldnt be here
        self.client = docker.from_env()

        # Get the absolute path of the prometheus.yml file
        self.prometheus_yml_path = os.path.abspath('./prometheus.yml')

        # Get the absolute path of the datasource.yml file for grafana
        # check path that's ok
        self.grafana_yml_path = os.path.abspath('./datasource.yml')
        pass


    # Create a custom network
    def create_network(self):
        network = self.client.networks.create("my_custom_network", driver="bridge")
        return network

    
    # Start Redis container
    def create_redis_container(self,net):
        redis = self.client.containers.run(
            "redislabs/redisearch:latest", 
            name="redis",
            ports={'6379/tcp': 6379},  # Expose port 6379
            detach=True,  # Run in the background
            # network=net.name, # Attach to the custom network
            runtime="runsc", # Gvisor Runtime!
            # runtime="io.containerd.kata.v2", # Kata runtime!
            labels={"created_by": "PerformanceMonitor"}  # Add a custom label
        )
        self.started_containers.append(redis.id)  # Store the container ID
        return redis

    # Start cAdvisor container , maybe needs --read-only and --security-opts?
    def create_cadvisor_container(self,net):
        cadvisor = self.client.containers.run(
            "gcr.io/cadvisor/cadvisor:latest", 
            name="cadvisor",
            ports={'8080/tcp': 8080},  # Expose port 8080
            privileged=True,
            volumes={
                '/': {'bind': '/rootfs', 'mode': 'ro'},
                '/var/run': {'bind': '/var/run', 'mode': 'rw'},
                '/sys': {'bind': '/sys', 'mode': 'ro'},
                '/var/lib/docker': {'bind': '/var/lib/docker', 'mode': 'ro'}
            },
            detach=True,  # Run in the background
            network=net.name, # Attach to the custom network
            labels={"created_by": "PerformanceMonitor"}  # Add a custom label
        )
        self.started_containers.append(cadvisor.id)  # Store the container ID
        return cadvisor

    # Start Prometheus container
    def create_prometheus_container(self,net):
        prometheus = self.client.containers.run(
            "prom/prometheus:latest", 
            name="prometheus",
            ports={'9090/tcp': 9090},  # Expose port 9090
            command="--config.file=/etc/prometheus/prometheus.yml",  # Custom command for Prometheus
            volumes={
                self.prometheus_yml_path: {'bind': '/etc/prometheus/prometheus.yml', 'mode': 'ro'}  # Mount prometheus.yml
            },
            detach=True,  # Run in the background
            network=net.name, # Attach to the custom network
            # read_only=True,  # Make the container's filesystem read-only (except mounted volumes)
            # cap_drop=["ALL"],  # Drop all Linux capabilities
            # security_opt=["no-new-privileges"],
            labels={"created_by": "PerformanceMonitor"}  # Add a custom label
        )
        self.started_containers.append(prometheus.id)  # Store the container ID
        return prometheus

    # Grafana container
    def create_grafana_container(self,net):
        grafana = self.client.containers.run(
            "grafana/grafana:latest",
            name="grafana",
            ports={'3000/tcp' : 3000},
            environment={"GF_SECURITY_ADMIN_USER": "notadmin", "GF_SECURITY_ADMIN_PASSWORD": "notgrafana"},
            volumes={ self.grafana_yml_path: {"bind": "/etc/grafana/provisioning/datasources/datasource.yml", "mode": "rw"}},
            network=net.name,
            detach=True,  # Run in the background
            labels={"created_by": "PerformanceMonitor"} , # Add a custom label
        )
        self.started_containers.append(grafana.id)  # Store the container ID
        return grafana
    

    # Create all containers manually without naming them
    def create_containers(self):
        '''Starts the whole cadvisor-prometehus-grafana stack 
        setting my_custom_network(bridge)'''
    
        # check if exists otherwise create
        # if client.networks.get("my_custom_network"):
        try:
            net = self.client.networks.get("my_custom_network")
        except docker.errors.NotFound:
            self.create_network()
        except Exception as e:
            print(f" Exception when getting my custom network : {e}")
            

        print("Starting Redis container...")
        self.create_redis_container(net)

        print("Starting cAdvisor container...")
        self.create_cadvisor_container(net)

        print("Starting Prometheus container...")
        self.create_prometheus_container(net)

        print("Starting Grafana container...")
        self.create_grafana_container(net)

        # print("Start sandboxed process_monitor container...")
        # create_proc_mon_container(net)

        print("All containers are up and running!")

    def stop_and_remove_labelled_containers(self):
        ''''''
        containers = self.client.containers.list(all=True)
        for container in containers:
            if container.labels.get("created_by") == "PerformanceMonitor":
                print(f"Stopping and removing container: {container.id}")
                container.stop()
                container.remove()

    def are_running(self):
        grafana = False
        prometheus = False
        cadvisor = False

        containers = self.client.containers.list(all=True)
        for container in containers:
           
            if container.name == "grafana" and container.status == "running":
                grafana = True
            if container.name == "prometheus" and container.status == "running":
                prometheus = True
            if container.name == "cadvisor" and container.status == "running":
                cadvisor = True
        if grafana and prometheus and cadvisor:
            
            return True,grafana,prometheus,cadvisor
        else:
           
            return False,grafana,prometheus,cadvisor



def prom_raw(QUERY = 'sum(rate(container_cpu_system_seconds_total{name="redis"}[1m]))',STEP = "10s"):
    '''Not used to be deleted'''
    # === CONFIGURATION ===
    PROMETHEUS_URL = "http://localhost:9090"
    
    session_id = "b1ccb1ef2b124f18ad99c2f81920e357"

    QUERY = '(container_fs_usage_bytes{name="redis"})'
    QUERY = 'sum by (name) (rate(container_fs_reads_bytes_total{name="redis"}[1m]) + rate(container_fs_writes_bytes_total{name="redis"}[1m]))'
    QUERY =  'sum by (name) (rate(container_network_receive_bytes_total{name=~"redis"}[1m]) + rate(container_network_transmit_bytes_total{name=~"redis"}[1m]))'
    QUERY = 'container_memory_working_set_bytes{name=~"redis"}'
    QUERY = f'sum by (name) (rate(container_cpu_usage_seconds_total{{name=~"sandbox_{session_id}"}}[1m])) * 100'

    END = int(time.time()) - (int(time.time()) % 30) # 
    START = END - 3600
    
    CSV_FILENAME = "cpu_usage_redis.csv"

    # === API CALL ===
    response = requests.get(
        f"{PROMETHEUS_URL}/api/v1/query_range",
        params={
            "query": QUERY,
            "start": START,
            "end": END,
            "step": STEP,
        },
    )

    data = response.json()

    # === VALIDATION ===
    if data["status"] != "success":
        raise Exception(f"Prometheus query failed: {data}")

    results = data["data"]["result"]

    processed_rows = []
    for series in results:
        for timestamp, value in series["values"]:
            ts = int(timestamp)
            dt = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')  # or use utcfromtimestamp for UTC
            processed_rows.append([ts, dt, float(value)])
            
    print(processed_rows)

    # === WRITE TO CSV ===
    # with open(CSV_FILENAME, mode="w", newline="") as csvfile:
    #     writer = csv.writer(csvfile)
    #     writer.writerow(["timestamp", "datetime", "value"])
    #     writer.writerows(processed_rows)


# prom_raw()

# print(time.time())

# PerformanceMonitorSandbox().are_running()