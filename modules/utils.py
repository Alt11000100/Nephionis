import docker

def stop_and_remove_labelled_containers(name):
        ''''''
        client = docker.from_env()
        containers = client.containers.list(all=True)
        for container in containers:
            if container.labels.get("created_by") == name:
                print(f"Stopping and removing container: {container.id}")
                container.stop()
                container.remove()