import docker
import time
import threading
import os
import json

class DockerStats(threading.Thread):
    def __init__(self,container,exception_event,session_id):
        threading.Thread.__init__(self,daemon=True)
        self.container = container
        self.interval = 0.1
        self.exception_event =  exception_event
        self.session_id = session_id
        


    def run(self):
            container = self.container
            interval = self.interval
            stop_event = self.exception_event
            """
            Collect metrics from a running Docker container.
            CPU and memory calculations are based on: 
            https://docs.docker.com/reference/api/engine/version/v1.45/#tag/Container/operation/ContainerStats
            
            CPU metrics explanation:
            - cpu_usage: Total CPU time in nanoseconds consumed by container since start
            - system_cpu_usage: Total CPU time (idle + non-idle) in nanoseconds across all CPUs since boot
            - online_cpus: Number of CPUs allocated to the container
            - cpu_delta: CPU time consumed by container between measurements
            - system_delta: Total CPU time elapsed on all system CPUs between measurements
            - cpu_percent: Container's CPU usage as percentage of its allocated CPUs (100% = all allocated CPUs fully used)

            Example calculation:
            - System has 16 CPUs total and container is allocated 4 CPUs
            - Measurement 1: system_cpu_usage = 1,000,000,000,000 ns, cpu_usage = 500,000,000 ns
            - Measurement 2: system_cpu_usage = 1,016,000,000,000 ns, cpu_usage = 2,500,000,000 ns
            - system_delta = 16,000,000,000 ns (16 CPU-seconds across all 16 CPUs)
            - cpu_delta = 2,000,000,000 ns (container used 2 CPU-seconds)
            - cpu_percent = (2,000,000,000 * 16) / (16,000,000,000 * 4) * 100.0 = 50%
            - This means the container used half (2 out of 4) of its allocated CPUs

            Memory metrics explanation (all values in bytes):
            - usage: Total memory footprint from host perspective (includes all memory used by container)
            - max_usage: Peak memory usage recorded since container start
            - limit: Maximum memory allowed for the container
            - cache: Page cache memory used (file contents cached from disk)
            - rss: Total Resident Set Size for all processes running inside the container including the container's own overhead
            - swap: Container memory written to swap space
            - memory_percent: Percentage of container's memory limit currently used
            - active_anon: Anonymous memory that has been used more recently (not file-backed)
            - inactive_anon: Anonymous memory that has been used less recently
            - active_file: File-backed memory that has been used more recently
            - inactive_file: File-backed memory that has been used less recently
            - pgfault: Number of page faults (minor faults, no disk I/O required)
            - pgmajfault: Number of major page faults (requiring disk I/O)

            I/O Metrics:
            - Note: Docker's container model means there's no real distinction between "container I/O" and "process I/O" 
            - the container is just a collection of isolated processes.
            
            Args:
                container (docker.models.containers.Container): The Docker container to monitor.
                interval (float): The time interval between metric collections in seconds.
                stop_event (threading.Event): Event to signal when to stop collecting metrics.
                
            Returns:
                dict: A dictionary containing collected metrics.
            """
            print(f"Collecting container metrics for container {container.name} ...")

            metrics = {
                "timestamps_s": [],
                "cpu_stats": {
                    "cpu_usage": [],
                    "system_cpu_usage": [],
                    "online_cpus": [],
                    "cpu_percent": []
                },
                "memory_stats": {
                    "usage": [],
                    "max_usage": [],
                    "limit": [],
                    "memory_percent": [],
                    "cache": [],
                    "rss": [],
                    "swap": [],
                    "active_anon": [],
                    "inactive_anon": [],
                    "active_file": [],
                    "inactive_file": [],
                    "pgfault": [],
                    "pgmajfault": []
                },
                "io_stats": {
                    "read_bytes": {},
                    "write_bytes": {},
                    "read_ops": {},
                    "write_ops": {}
                },
                "network_stats": {},
                "metadata": {
                    'start_time': int(time.time() * 1000),
                    'end_time': None,
                    'session_id': None

                }
            }

            start_time = time.time()

            while not (stop_event and stop_event.is_set()):
                try:
                    # Check if container is still running
                    container.reload()
                    if container.status != 'running':
                        break

                    # Get container stats
                    stats = container.stats(stream=False)

                    # Calculate timestamp in seconds directly (instead of milliseconds)
                    current_time = time.time()
                    timestamp_s = current_time - start_time
                    metrics["timestamps_s"].append(timestamp_s)

                    # Extract CPU stats
                    cpu_usage = stats.get("cpu_stats", {}).get("cpu_usage", {}).get("total_usage", 0)
                    system_cpu_usage = stats.get("cpu_stats", {}).get("system_cpu_usage", 0)
                    online_cpus = stats.get("cpu_stats", {}).get("online_cpus", 1)

                    # Calculate CPU percentage
                    previous_cpu = stats.get("precpu_stats", {}).get("cpu_usage", {}).get("total_usage", 0)
                    previous_system = stats.get("precpu_stats", {}).get("system_cpu_usage", 0)

                    cpu_percent = 0.0
                    if previous_cpu > 0 and previous_system > 0:
                        cpu_delta = cpu_usage - previous_cpu
                        system_delta = system_cpu_usage - previous_system
                        if system_delta > 0:
                            total_system_cpus = os.cpu_count()
                            cpu_percent = (cpu_delta * total_system_cpus) / (system_delta * online_cpus) * 100.0

                    # Store CPU stats directly in arrays
                    metrics["cpu_stats"]["cpu_usage"].append(cpu_usage)
                    metrics["cpu_stats"]["system_cpu_usage"].append(system_cpu_usage)
                    metrics["cpu_stats"]["online_cpus"].append(online_cpus)
                    metrics["cpu_stats"]["cpu_percent"].append(cpu_percent)

                    # Extract and store memory stats directly in arrays
                    mem_usage = stats.get("memory_stats", {}).get("usage", 0)
                    mem_limit = stats.get("memory_stats", {}).get("limit", 0)
                    mem_percent = (mem_usage / mem_limit) * 100.0 if mem_limit > 0 else 0.0

                    metrics["memory_stats"]["usage"].append(mem_usage)
                    metrics["memory_stats"]["max_usage"].append(stats.get("memory_stats", {}).get("max_usage", 0))
                    metrics["memory_stats"]["limit"].append(mem_limit)
                    metrics["memory_stats"]["memory_percent"].append(mem_percent)
                    metrics["memory_stats"]["cache"].append(stats.get("memory_stats", {}).get("stats", {}).get("cache", 0))
                    metrics["memory_stats"]["rss"].append(stats.get("memory_stats", {}).get("stats", {}).get("rss", 0))
                    metrics["memory_stats"]["swap"].append(stats.get("memory_stats", {}).get("stats", {}).get("swap", 0))
                    metrics["memory_stats"]["active_anon"].append(stats.get("memory_stats", {}).get("stats", {}).get("active_anon", 0))
                    metrics["memory_stats"]["inactive_anon"].append(stats.get("memory_stats", {}).get("stats", {}).get("inactive_anon", 0))
                    metrics["memory_stats"]["active_file"].append(stats.get("memory_stats", {}).get("stats", {}).get("active_file", 0))
                    metrics["memory_stats"]["inactive_file"].append(stats.get("memory_stats", {}).get("stats", {}).get("inactive_file", 0))
                    metrics["memory_stats"]["pgfault"].append(stats.get("memory_stats", {}).get("stats", {}).get("pgfault", 0))
                    metrics["memory_stats"]["pgmajfault"].append(stats.get("memory_stats", {}).get("stats", {}).get("pgmajfault", 0))

                    # Extract and store I/O stats
                    io_service_bytes = stats.get("blkio_stats", {}).get("io_service_bytes_recursive", [])
                    if io_service_bytes:
                        for blkio_stat in io_service_bytes:
                            op = blkio_stat.get("op", "").lower()
                            value = blkio_stat.get("value", 0)
                            major = str(blkio_stat.get("major", 0))

                            if op == "read":
                                if major not in metrics["io_stats"]["read_bytes"]:
                                    metrics["io_stats"]["read_bytes"][major] = []
                                metrics["io_stats"]["read_bytes"][major].append(value)
                            elif op == "write":
                                if major not in metrics["io_stats"]["write_bytes"]:
                                    metrics["io_stats"]["write_bytes"][major] = []
                                metrics["io_stats"]["write_bytes"][major].append(value)

                    # Make sure all io_stats arrays have the same length
                    for major in metrics["io_stats"]["read_bytes"]:
                        while len(metrics["io_stats"]["read_bytes"][major]) < len(metrics["timestamps_s"]):
                            metrics["io_stats"]["read_bytes"][major].append(0)

                    for major in metrics["io_stats"]["write_bytes"]:
                        while len(metrics["io_stats"]["write_bytes"][major]) < len(metrics["timestamps_s"]):
                            metrics["io_stats"]["write_bytes"][major].append(0)

                    # Extract and store network stats
                    networks = stats.get("networks", {})
                    if networks:
                        for network_name, network_data in networks.items():
                            if network_name not in metrics["network_stats"]:
                                metrics["network_stats"][network_name] = {
                                    "rx_bytes": [], "tx_bytes": [], "rx_packets": [], "tx_packets": [],
                                    "rx_dropped": [], "tx_dropped": [], "rx_errors": [], "tx_errors": []
                                }

                            metrics["network_stats"][network_name]["rx_bytes"].append(network_data.get("rx_bytes", 0))
                            metrics["network_stats"][network_name]["tx_bytes"].append(network_data.get("tx_bytes", 0))
                            metrics["network_stats"][network_name]["rx_packets"].append(network_data.get("rx_packets", 0))
                            metrics["network_stats"][network_name]["tx_packets"].append(network_data.get("tx_packets", 0))
                            metrics["network_stats"][network_name]["rx_dropped"].append(network_data.get("rx_dropped", 0))
                            metrics["network_stats"][network_name]["tx_dropped"].append(network_data.get("tx_dropped", 0))
                            metrics["network_stats"][network_name]["rx_errors"].append(network_data.get("rx_errors", 0))
                            metrics["network_stats"][network_name]["tx_errors"].append(network_data.get("tx_errors", 0))

                    time.sleep(interval)

                except docker.errors.NotFound:
                    # Container not found, probably removed
                    break
                except Exception as e:
                    print(f"Error collecting container metrics: {e}")
                    break

            metrics["metadata"]["end_time"] = int(time.time() * 1000)
            metrics["metadata"]["session_id"] = self.session_id

            
            with open(os.path.abspath(os.path.join(os.path.dirname(__file__), ".." , "docker_stats", f'container_metrics-{self.session_id}.json')), 'w') as f:
                json.dump(metrics, f, indent=4)

            return metrics
    
    def stop(self):
        self.join()
        print(f"Thread {self} terminating!")

