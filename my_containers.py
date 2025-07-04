import docker

import os

# Get the absolute path of the prometheus.yml file
prometheus_yml_path = os.path.abspath('./prometheus.yml')

# Get the absolute path of the datasource.yml file for grafana
grafana_yml_path = os.path.abspath('./datasource.yml')

# Initialize the Docker client
client = docker.from_env()

# List to store container IDs that were started by this script
started_containers = []

# Create a custom network
def create_network():
    network = client.networks.create("my_custom_network", driver="bridge")
    return network


# Start the process monitor
def create_proc_mon_container(net):
    '''assuming that this image already exists'''
    proc_mon = client.containers.run(
        "proc_mon:1",
        name="proc_mon",
        detach=True,  # Run in the background
        # network=net.name, # Attach to the custom network
        volumes={
            f"{os.getcwd()}/my_results": {
                "bind": "/app/results",
                "mode": "rw"
            }
        },
        runtime="runsc", # Gvisor Runtime!
        # runtime="io.containerd.kata.v2", # Kata runtime!
        labels={"created_by": "my_script"}  # Add a custom label
    )
    started_containers.append(proc_mon.id)  # Store the container ID
    return proc_mon

# Start Redis container
def create_redis_container(net):
    redis = client.containers.run(
        "redis:latest", 
        name="redis",
        ports={'6379/tcp': 6379},  # Expose port 6379
        detach=True,  # Run in the background
        # network=net.name, # Attach to the custom network
        runtime="runsc", # Gvisor Runtime!
        # runtime="io.containerd.kata.v2", # Kata runtime!
        labels={"created_by": "my_script"}  # Add a custom label
    )
    started_containers.append(redis.id)  # Store the container ID
    return redis

# Start cAdvisor container , maybe needs --read-only and --security-opts?
def create_cadvisor_container(net):
    cadvisor = client.containers.run(
        "gcr.io/cadvisor/cadvisor:latest", 
        name="cadvisor",
        ports={'8080/tcp': 8080},  # Expose port 8080
        volumes={
            '/': {'bind': '/rootfs', 'mode': 'ro'},
            '/var/run': {'bind': '/var/run', 'mode': 'rw'},
            '/sys': {'bind': '/sys', 'mode': 'ro'},
            '/var/lib/docker': {'bind': '/var/lib/docker', 'mode': 'ro'}
        },
        detach=True,  # Run in the background
        network=net.name, # Attach to the custom network
        labels={"created_by": "my_script"}  # Add a custom label
    )
    started_containers.append(cadvisor.id)  # Store the container ID
    return cadvisor

# Start Prometheus container
def create_prometheus_container(net):
    prometheus = client.containers.run(
        "prom/prometheus:latest", 
        name="prometheus",
        ports={'9090/tcp': 9090},  # Expose port 9090
        command="--config.file=/etc/prometheus/prometheus.yml",  # Custom command for Prometheus
        volumes={
            prometheus_yml_path: {'bind': '/etc/prometheus/prometheus.yml', 'mode': 'ro'}  # Mount prometheus.yml
        },
        detach=True,  # Run in the background
        network=net.name, # Attach to the custom network
        labels={"created_by": "my_script"}  # Add a custom label
    )
    started_containers.append(prometheus.id)  # Store the container ID
    return prometheus

# Grafana container
def create_grafana_container(net):
    grafana = client.containers.run(
        "grafana/grafana:latest",
        name="grafana",
        ports={'3000/tcp' : 3000},
        environment={"GF_SECURITY_ADMIN_USER": "admin", "GF_SECURITY_ADMIN_PASSWORD": "grafana"},
        volumes={ grafana_yml_path: {"bind": "/etc/grafana/provisioning/datasources/datasource.yml", "mode": "rw"}},
        network=net.name,
        detach=True,  # Run in the background
        labels={"created_by": "my_script"} , # Add a custom label
    )
    started_containers.append(grafana.id)  # Store the container ID
    return grafana

# Create all containers manually without naming them
def create_containers():
    
    # if client.networks.get("my_custom_network"):
    net = client.networks.get("my_custom_network")
        

    print("Starting Redis container...")
    create_redis_container(net)

    print("Starting cAdvisor container...")
    create_cadvisor_container(net)

    print("Starting Prometheus container...")
    create_prometheus_container(net)

    print("Starting Grafana container...")
    create_grafana_container(net)

    # print("Start sandboxed process_monitor container...")
    # create_proc_mon_container(net)

    print("All containers are up and running!")

# Stop and remove only the containers created by this script
def stop_and_remove_created_containers():
    for container_id in started_containers:
        container = client.containers.get(container_id)
        print(f"Stopping and removing container: {container.id}")
        container.stop()  # Stop the container
        container.remove()  # Remove the container

def stop_and_remove_labelled_containers():
    containers = client.containers.list(all=True)
    for container in containers:
        if container.labels.get("created_by") == "my_script":
            print(f"Stopping and removing container: {container.id}")
            container.stop()
            container.remove()

# List the status of all running containers
def list_running_containers():
    containers = client.containers.list()
    for container in containers:
        print(f'{container.name} - {container.status}')