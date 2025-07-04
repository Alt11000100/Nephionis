# pylint: disable=no-name-in-module, import-error, line-too-long

from collections import deque
import multiprocessing
import threading
import sys
import os
import subprocess
import shlex
import time
import math
import json

import numpy as np
import psutil
import matplotlib.pyplot as plt
from dotenv import load_dotenv

# if __name__ == "__main__":
from utils.utils import current_milli_time, moving_average
from utils.timeout_handler import TimeoutHandler
from utils.venv_installer import VenvInstaller
from utils.dockerManager import DockerManager
# else:                                                             # fix later
#     from .utils.utils import current_milli_time, moving_average
#     from .utils.timeout_handler import TimeoutHandler
#     from .utils.venv_installer import VenvInstaller
#     from .utils.dockerManager import DockerManager

load_dotenv(override=True)

class Benchmarker(DockerManager):
    def __init__(self, interval=0.1, cwd='.', ishost=True, execution_environment='host',
                 root_folder_path='.', process_timeout=3600, process_warning_timeout=1200,
                 cpu_limit=4, mem_limit='8g') -> None:
        self.execution_environment = execution_environment
        self.interval = interval
        self.shared_process_dict = {}
        self.cwd = cwd
        self.process_timeout = process_timeout
        self.process_warning_timeout = process_warning_timeout

        # Only initialize Docker functionality when running on host,
        # not when inside the docker container.
        if ishost:
            super().__init__(root_folder_path, execution_environment, cpu_limit, mem_limit)

    def _init_shared_dict(self):
        # TODO: Remove unecessary values
        manager = multiprocessing.Manager()
        self.shared_process_dict = manager.dict({
            "target_process_pid": -1,
            "execution_start": -1,
            "execution_end": -1, 
            "sample_milliseconds": manager.list(),
            "cpu_percentages": manager.list(),
            "memory_values": manager.list(),
            "io_values": manager.list(),
            "exit_status": None,
            "std_out": None,
            "err_out": None,
            "terminated": False,
            # "memory_max": 0,
            # "memory_perprocess_max": 0,
            # "disk_io_counters": None,
            # "cpu_times": None,
            "skip_benchmarking": False
        })

        
        # self.shared_process_dict = manager.dict(shared_process_dict_template)

    def benchmark_python3_script_docker(self, analysis_id, main_script,
                                        python_version='3.8', requirements_file='requirements.txt'):
        """
        Benchmark a script within a Docker container.

        Args:
            analysis_id (str): A unique identifier for the analysis.
            main_script (str): The relative path to script and the script name
            (e.g. src/benchmarker/code_runner/experiment_3cb15b4b-f0e9-4e53-870b-24c25f9ba593.py)
            python_version (str): The version of Python to be used in the Dockerfile.
            requirements_file (str): The relative path to the requirements file
            with respect to self.cwd.

        Returns:
            tuple: (dockerfile_path, results_folder_path, container_logs, container_metrics)
        """

        dockerfile_name = f'Dockerfile-{analysis_id}'
        dockerfile_paths_include = [{"source": "src/benchmarker", "target": "."}]
        results_folder_path = f'{self.cwd}/results-{analysis_id}'

        # Paths relative to the root_folder_path
        execution_folder_name = os.path.basename(os.path.normpath(self.cwd)) # "code_runner"
        env_variables = {
            'ANALYSIS_ID': analysis_id,
            'EXPERIMENT_WORKDIR': f'./{execution_folder_name}/',
            'REQUIREMENTS_FILE': f'./{execution_folder_name}/{requirements_file}',
            'EXPERIMENT_FILE': f'./{execution_folder_name}/{os.path.basename(main_script)}',
            'RESULTS_FOLDER': f'./{execution_folder_name}/results',
        }

        dockerfile_path = self.create_dockerfile(self.cwd, dockerfile_paths_include,
                                                 python_version, env_variables, dockerfile_name)
        image = self.build_docker_image(analysis_id, dockerfile_path)

        run_success, container, container_logs, container_metrics = False, None, None, None
        try:
            run_success, container, container_logs, container_metrics = self.run_docker_container(
                image, results_folder_path, analysis_id, self.process_timeout
            )
            self.remove_docker_container(container)
        except Exception as e:
            print(f"Docker container operation failed: {str(e)}")
        finally:
            self.remove_docker_image(image)

        return run_success, dockerfile_path, results_folder_path, container_logs, container_metrics

    def bencmark_python3_script(self, main_script, requirements_file='requirements.txt'):
        """
        Benchmarks a Python 3 script by creating a virtual environment,
        installing the required packages, and executing the script.

        Args:
            main_script (str): The path to the main Python script to be benchmarked.
            requirements_file (str, optional): The path to the requirements file.
            Defaults to 'requirements.txt'.

        Returns:
            dict: A dictionary containing the results of the benchmark. The key 'exit_status'
              will be -1 if the virtual environment creation or package installation failed,
              otherwise it will contain the results of the benchmarked command.
        """

        print('Creating venv and installing requirements ...')
        venv_installer = VenvInstaller()
        success, command = venv_installer.create_venv(main_script=main_script,
                                                      requirements=requirements_file)

        results = {'exit_status': -1}

        if success is not True:
            self.shared_process_dict['err_out'] = command
        elif command is None:
            self.shared_process_dict['err_out'] = "Command is NONE"
        else:
            results = self.benchmark_command(command)

        venv_installer.remove_venv()

        return results

    def benchmark_command(self, command):
        """
        Benchmark a shell command by monitoring its hardware usage and execution metrics.

        Args:
            command (str): The shell command to benchmark, e.g. 'python3 script.py'

        Returns:
            dict: Raw results containing hardware metrics, execution timing, process status,
              output content and monitoring data

        Raises:
            Exception: Any non-timeout related exceptions during execution
        """

        self._setup_benchmarker()

        # Initialize a sharable (among processes) dictionary
        # TODO: Check if this should stay here or move to the constructor?
        # What if we call benchmark command 2 times?
        self._init_shared_dict()

        commands_list = shlex.split(command)

        # Start the monitoring processes
        print("Starting monitoring processes")
        hardware_usage_monitor = multiprocessing.Process(target = self.collect_hardware_usage)
        # network_usage_monitor = multiprocessing.Process(target = self.collect_network_usage)

        hardware_usage_monitor.start()
        # network_usage_monitor.start()

        # Start the master/target/monitored process
        print("Starting target process")
        master_process = psutil.Popen(commands_list, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, cwd=self.cwd)
        execution_start = current_milli_time()

        if not self.shared_process_dict["skip_benchmarking"]:
            self.shared_process_dict["target_process_pid"] = master_process.pid

        self.shared_process_dict["execution_start"] = execution_start

        # Start the timer thread. This will only through a warning after PROCESS_WARNING_TIMEOUT (s)
        timeout_handler = TimeoutHandler(timeout=self.process_warning_timeout,
                                         handler_type="Warning")
        stop_flag = threading.Event()
        timer_thread = threading.Thread(target=timeout_handler.timeout_handler,
                                        args=(master_process, stop_flag))
        timer_thread.start()

        # Wait for the target process to finish
        try:
            outdata, errdata = master_process.communicate(timeout=self.process_timeout)
        except Exception as e:
            # Raise non-timeout errors
            if e.__class__.__name__ != 'TimeoutExpired':
                raise

            # TODO: This should catch other exceptions too.
            # Monitored process exceptions are caught by communicate().

            self.shared_process_dict['execution_end'] = current_milli_time()
            self.shared_process_dict['exit_status'] = -1
            self.shared_process_dict['terminated'] = True
        else:
            outdata = outdata.decode(sys.stdout.encoding)
            errdata = errdata.decode(sys.stderr.encoding)
            exit_status = master_process.wait()

            self.shared_process_dict['execution_end'] = current_milli_time()
            self.shared_process_dict['exit_status'] = exit_status
            self.shared_process_dict['terminated'] = False
            self.shared_process_dict['std_out'] = outdata
            self.shared_process_dict['err_out'] = errdata

        print("Target process finished")

        # Terminate the timing warning thread
        stop_flag.set()
        timer_thread.join()
        print('Timeout warning thread terminated')

        # Wait for the monitoring processes to finish
        hardware_usage_monitor.join()
        # network_usage_monitor.join()

        print("Monitoring processes finished")

        return self.get_raw_results()

    def collect_hardware_usage(self):
        ''' Collects the process resource usage of CPU, RAM and I/O counters '''

        # Wait for the process to start
        while self.shared_process_dict["target_process_pid"] == -1:
            if self.shared_process_dict["skip_benchmarking"]:
                return

        p = psutil.Process(self.shared_process_dict["target_process_pid"])
        execution_start = self.shared_process_dict["execution_start"]
        sample_milliseconds = self.shared_process_dict["sample_milliseconds"]
        cpu_percentages = self.shared_process_dict["cpu_percentages"]
        memory_values = self.shared_process_dict["memory_values"]
        io_values = self.shared_process_dict["io_values"]

        monitoring_process_children_set = set()
        monitoring_process_children = []

        # Total bytes read/written
        read_chars = 0
        write_chars = 0

        # Bytes read/written to disk
        read_bytes = 0
        write_bytes = 0

        while True:
            if not p.is_running() or self._target_process_exited():
                break

            # Use oneshot to cache the values of each Process.function() called multiple times
            with p.oneshot():
                try:
                    cpu_percentage = p.cpu_percent()

                    memory_usage_rss = p.memory_full_info().rss
                    memory_usage_uss = p.memory_full_info().uss

                    read_chars, write_chars, read_bytes, write_bytes = self._read_io(p)

                    current_children = p.children(recursive=True)
                    for child in current_children:
                        if child in monitoring_process_children_set:
                            # Accessing the child directly does not seem to work,
                            # instead access the first instance of the child stored in the list.
                            index_child = monitoring_process_children.index(child)
                            target_child_process = monitoring_process_children[index_child]

                            with target_child_process.oneshot():
                                cpu_percentage += target_child_process.cpu_percent()

                                memory_usage_rss += target_child_process.memory_full_info().rss
                                memory_usage_uss += target_child_process.memory_full_info().uss

                                read_chars_temp, write_chars_temp, read_bytes_temp, write_bytes_temp = \
                                    self._read_io(target_child_process)
                                read_chars += read_chars_temp
                                write_chars += write_chars_temp
                                read_bytes += read_bytes_temp
                                write_bytes += write_bytes_temp
                        else:
                            # Add children not already in our monitoring_process_children
                            monitoring_process_children_set.add(child)
                            monitoring_process_children.append(child)

                    timestamp = current_milli_time() - execution_start

                    sample_milliseconds.append(timestamp)
                    cpu_percentages.append(cpu_percentage)
                    memory_values.append({'rss': memory_usage_rss, 'uss': memory_usage_uss})
                    io_values.append({
                        'read_bytes': read_bytes,
                        'write_bytes': write_bytes,
                        'read_chars': read_chars,
                        'write_chars': write_chars
                    })

                except psutil.NoSuchProcess:
                    # The process might end while we are measuring resources
                    print('No such process')
                except psutil.AccessDenied:
                    print('Access Denied ... Printing once is OK')
                # except Exception as e: # TODO: Catch general exceptions
                #     pass

            time.sleep(self.interval)


        self.shared_process_dict["sample_milliseconds"] = sample_milliseconds
        self.shared_process_dict["cpu_percentages"] = cpu_percentages
        self.shared_process_dict["memory_values"] = memory_values
        self.shared_process_dict["io_values"] = io_values

        return

    def collect_network_usage(self):
        pass

    def plot_statistics(self):
        """
        Plot performance statistics and metrics for a monitored process.

        Creates visualizations for CPU usage, memory usage, and I/O statistics.
        Prints basic metrics like duration, average CPU usage, max memory usage
        and total I/O bytes.

        Returns:
            None. Displays plots using matplotlib.
        """

        exit_status = self.shared_process_dict['exit_status']
        terminated = self.shared_process_dict['terminated']
        outdata = self.shared_process_dict['std_out']
        errdata = self.shared_process_dict['err_out']
        execution_start = self.shared_process_dict['execution_start']
        execution_end = self.shared_process_dict['execution_end']
        timestamps_ms = self.shared_process_dict['sample_milliseconds']
        cpu_percentages = self.shared_process_dict['cpu_percentages']
        memory_values = self.shared_process_dict['memory_values']
        io_values = self.shared_process_dict['io_values']

        # TODO: Get the data from get statistics full and dont recalculate them here.
        statistics = self.get_statistics_full()

        print('\n\nTarget process info:')
        print('Exit status:', exit_status)
        print(f'Stdout: \n{outdata}')
        print(f'Stderr: \n{errdata}')

        if exit_status != 0:
            if terminated:
                print(
                    'Target process execution terminated, '
                    f'because it exceeded the timeout limit: {self.process_timeout}s'
                )
            else:
                print('Target process execution failed')
            return

        timestamps_s = [k/1000 for k in timestamps_ms]
        cpu_percentages_norm = [k/psutil.cpu_count() for k in cpu_percentages]
        memory_values_rss_mb = [k['rss']/(1024*1024) for k in memory_values]
        memory_values_uss_mb = [k['uss']/(1024*1024) for k in memory_values]
        io_values_final_mb = {key: value / (1024*1024) for key, value in io_values[-1].items()}

        # Print metrics
        print('\nMetrics:')
        print(f'Process duration: {(execution_end - execution_start)/1000} s')
        print(f'Average CPU usage: {np.mean(cpu_percentages_norm)}%')
        print(f'Max RSS memory usage: {np.max(memory_values_rss_mb)} MB')
        print(f'Max USS memory usage: {np.max(memory_values_uss_mb)} MB')
        print(f"Total bytes read: {io_values_final_mb['read_chars']} MB")
        print(f"Total bytes write: {io_values_final_mb['write_chars']} MB")
        print(f"Disk bytes read: {io_values_final_mb['read_bytes']} MB")
        print(f"Disk bytes write: {io_values_final_mb['write_bytes']} MB")

        legend_properties = {'weight':'bold'}

        # Plot CPU percentages
        plt.figure()
        plt.plot(timestamps_s, cpu_percentages_norm, color='#8da0cb', linestyle='-',
             marker=None, linewidth=2, label='Timeseries')
        plt.plot(timestamps_s, moving_average(cpu_percentages_norm, math.ceil(len(timestamps_s)/20)),
             color='#fc8d62', linestyle='-', marker=None, linewidth=2, label='Moving Average')
        plt.axhline(y=np.mean(cpu_percentages_norm), color='#66c2a5', linestyle='--',
                marker=None, linewidth=2, label=f'Average = {np.mean(cpu_percentages_norm):.2f}')
        plt.ylim(0, 100)
        plt.ylabel("CPU usage (percent %)", weight='bold', fontsize=14)
        plt.xlabel("Time (s)", weight='bold', fontsize=14)
        plt.title("CPU usage", weight='bold', fontsize=20)
        plt.legend(prop=legend_properties)
        plt.grid(True)
        # plt.show()

        # Plot Memory usage
        plt.figure()
        plt.plot(timestamps_s, memory_values_rss_mb, marker='None', linestyle='-',
             label='RSS memory', linewidth=2, color='#8da0cb')
        plt.plot(timestamps_s, statistics['timeseries']['memory_values_rss_mb_moving_avg'],
             color='#fc8d62', linestyle='-', marker=None, linewidth=2, label='RSS Moving Average')
        plt.plot(timestamps_s, memory_values_uss_mb, marker='None', linestyle='-',
             label='USS memory', linewidth=2, color='#66c2a5')
        plt.plot(timestamps_s, statistics['timeseries']['memory_values_uss_mb_moving_avg'],
             color='#dc3545', linestyle='-', marker=None, linewidth=2, label='USS Moving Average')
        plt.axhline(y=np.mean(memory_values_rss_mb), linestyle='--',
                label=f'Average = {np.mean(memory_values_rss_mb):.2f}', color='#851c22')
        plt.axhline(y=np.mean(memory_values_uss_mb), linestyle='--',
                label=f'Average = {np.mean(memory_values_uss_mb):.2f}', color='#e9967a')
        plt.xlabel("Time (s)", weight='bold', fontsize=14)
        plt.ylabel("Memory usage (MB)", weight='bold', fontsize=14)
        plt.title("Memory usage", weight='bold', fontsize=20)
        plt.legend(prop=legend_properties)
        plt.grid(True)
        # plt.show()

        # Plot I/O Counters usage
        _, ax1 = plt.subplots()

        ax1.plot(timestamps_s, [k['read_bytes']/(1024*1024) for k in io_values],
             marker='None', linestyle='-', label='Disk read bytes',
             linewidth=2, color='#ef5675')
        ax1.plot(timestamps_s, [k['write_bytes']/(1024*1024) for k in io_values],
             marker='None', linestyle='-', label='Disk write bytes',
             linewidth=2, color='#ffa600')
        ax1.set_ylabel("Disk Read/Write (MB)", color='#ffa600', weight='bold', fontsize=14)
        ax1.tick_params(axis='y', labelcolor='#ffa600')

        ax2 = ax1.twinx()
        ax2.plot(timestamps_s, [k['read_chars']/(1024*1024) for k in io_values],
             marker='None', linestyle='-', label='Total read bytes',
             linewidth=2, color='#003f5c')
        ax2.plot(timestamps_s, [k['write_chars']/(1024*1024) for k in io_values],
             marker='None', linestyle='-', label='Total write bytes',
             linewidth=2, color='#7a5195')
        ax2.set_ylabel("Total Read/Write (MB)", color='#003f5c', weight='bold', fontsize=14)
        ax2.tick_params(axis='y', labelcolor='#003f5c')

        lines, labels = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()

        ax1.set_xlabel("Time (s)", weight='bold', fontsize=14)
        plt.title("I/O Statistics (cumulative)", weight='bold', fontsize=20)
        plt.grid(True)
        plt.legend(lines + lines2, labels + labels2, loc='upper left', prop=legend_properties)
        # plt.show()

        # Plot I/O moving averages
        _, ax1 = plt.subplots()

        ax1.plot(timestamps_s, statistics['timeseries']['disk_read_mb_moving_avg'],
             marker='None', linestyle='-', label='Disk read bytes', linewidth=2, color='#ef5675')
        ax1.plot(timestamps_s, statistics['timeseries']['disk_write_mb_moving_avg'],
             marker='None', linestyle='-', label='Disk write bytes', linewidth=2, color='#ffa600')
        ax1.set_ylabel("Disk Read/Write (MB)", color='#ffa600', weight='bold', fontsize=14)
        ax1.tick_params(axis='y', labelcolor='#ffa600')

        ax2 = ax1.twinx()
        ax2.plot(timestamps_s, statistics['timeseries']['total_read_mb_moving_avg'],
             marker='None', linestyle='-', label='Total read bytes', linewidth=2, color='#003f5c')
        ax2.plot(timestamps_s, statistics['timeseries']['total_write_mb_moving_avg'],
             marker='None', linestyle='-', label='Total write bytes', linewidth=2, color='#7a5195')
        ax2.set_ylabel("Total Read/Write (MB)", color='#003f5c', weight='bold', fontsize=14)
        ax2.tick_params(axis='y', labelcolor='#003f5c')

        lines, labels = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()

        ax1.set_xlabel("Time (s)", weight='bold', fontsize=14)
        plt.title("I/O Statistics (moving average)", weight='bold', fontsize=20)
        plt.grid(True)
        plt.legend(lines + lines2, labels + labels2, loc='upper left', prop=legend_properties)
        plt.show()

    def get_statistics_full(self) -> dict:
        """
        Returns an object with the results data and their aggregations.

        ...

        Returns
        ----------
        - statistics : dict : A dictionary containing processed data categorized into 
          three sub-dictionaries:            
            - raw : dict : A dictionary containing the raw data generated by the analyzer.
            - timeseries : dict : A dictionary containing metrics and timeseries of the data.
            - numericals : dict : A dictionary containing numerical metrics of the data.
        '''

        """

        statistics = {
            'raw': self.get_raw_results(),
            'timeseries': {
                'timestamps_s': [],
                'cpu_percentages_norm': [],
                'cpu_percentages_moving_avg': [],
                'memory_values_rss_mb': [],
                'memory_values_rss_mb_moving_avg': [],
                'memory_values_uss_mb': [],
                'memory_values_uss_mb_moving_avg': [],
                'disk_read_mb': [],
                'disk_read_mb_moving_avg': [],
                'disk_write_mb': [],
                'disk_write_mb_moving_avg': [],
                'total_read_mb': [],
                'total_read_mb_moving_avg': [],
                'total_write_mb': [],
                'total_write_mb_moving_avg': []
            },
            'numericals': {
                'execution_time': 0,
                'cpu_avg': 0,
                'memory_max_rss_mb': 0,
                'memory_max_uss_mb': 0,
                'disk_read_mb': 0,
                'disk_write_mb': 0,
                'total_read_mb': 0,
                'total_write_mb': 0,
            },
            'metadata': self.get_metadata()
        }

        execution_start = self.shared_process_dict['execution_start']
        execution_end = self.shared_process_dict['execution_end']
        timestamps_ms = self.shared_process_dict['sample_milliseconds']
        cpu_percentages = self.shared_process_dict['cpu_percentages']
        memory_values = self.shared_process_dict['memory_values']
        io_values = self.shared_process_dict['io_values']

        # Timeseries
        statistics['timeseries']['timestamps_s'] = [k/1000 for k in timestamps_ms]
        statistics['timeseries']['cpu_percentages_norm'] = [k/psutil.cpu_count() for k in cpu_percentages]
        statistics['timeseries']['memory_values_rss_mb'] = [k['rss']/(1024*1024) for k in memory_values]
        statistics['timeseries']['memory_values_uss_mb'] = [k['uss']/(1024*1024) for k in memory_values]
        statistics['timeseries']['disk_read_mb'] = [k['read_bytes']/(1024*1024) for k in io_values]
        statistics['timeseries']['disk_write_mb'] = [k['write_bytes']/(1024*1024) for k in io_values]
        statistics['timeseries']['total_read_mb'] = [k['read_chars']/(1024*1024) for k in io_values]
        statistics['timeseries']['total_write_mb'] = [k['write_chars']/(1024*1024) for k in io_values]

        window_size = math.ceil(len(statistics['timeseries']['timestamps_s'])/20)
        statistics['timeseries']['cpu_percentages_moving_avg'] = moving_average(
            statistics['timeseries']['cpu_percentages_norm'], window_size)
        statistics['timeseries']['memory_values_rss_mb_moving_avg'] = moving_average(
            statistics['timeseries']['memory_values_rss_mb'], window_size)
        statistics['timeseries']['memory_values_uss_mb_moving_avg'] = moving_average(
            statistics['timeseries']['memory_values_uss_mb'], window_size)
        statistics['timeseries']['disk_read_mb_moving_avg'] = moving_average(
            statistics['timeseries']['disk_read_mb'], window_size)
        statistics['timeseries']['disk_write_mb_moving_avg'] = moving_average(
            statistics['timeseries']['disk_write_mb'], window_size)
        statistics['timeseries']['total_read_mb_moving_avg'] = moving_average(
            statistics['timeseries']['total_read_mb'], window_size)
        statistics['timeseries']['total_write_mb_moving_avg'] = moving_average(
            statistics['timeseries']['total_write_mb'], window_size)

        # Numericals
        io_values_temp = {key: value / (1024*1024) for key, value in io_values[-1].items()}

        statistics['numericals']['execution_time'] = (execution_end - execution_start)/1000
        statistics['numericals']['cpu_avg'] = np.mean(statistics['timeseries']['cpu_percentages_norm'])
        statistics['numericals']['memory_max_rss_mb'] = np.max(statistics['timeseries']['memory_values_rss_mb'])
        statistics['numericals']['memory_max_uss_mb'] = np.max(statistics['timeseries']['memory_values_uss_mb'])
        statistics['numericals']['total_read_mb'] = io_values_temp['read_chars']
        statistics['numericals']['total_write_mb'] = io_values_temp['write_chars']
        statistics['numericals']['disk_read_mb'] = io_values_temp['read_bytes']
        statistics['numericals']['disk_write_mb'] = io_values_temp['write_bytes']

        return statistics

    def get_statistics_basic(self) -> dict:
        """
        Returns an object with the results' basic data.

        ...

        Returns
        ----------
        - statistics : dict : A dictionary containing processed data categorized into 
          two sub-dictionaries:            
            - timeseries : dict : A dictionary containing timeseries of the data.
            - numericals : dict : A dictionary containing numerical metrics of the data.
        """

        statistics = {
            'timeseries': {
                'timestamps_s': [],
                'cpu_percentages_norm': [],
                'memory_values_rss_mb': [], 
                'memory_values_uss_mb': [],
            },
            'numericals': {
                'execution_time': 0,
                'cpu_avg': 0,
                'memory_max_rss_mb': 0,
                'memory_max_uss_mb': 0,
                'disk_read_mb': 0,
                'disk_write_mb': 0,
                'total_read_mb': 0,
                'total_write_mb': 0,
            },
            'metadata': self.get_metadata()
        }

        execution_start = self.shared_process_dict['execution_start']
        execution_end = self.shared_process_dict['execution_end']
        timestamps_ms = self.shared_process_dict['sample_milliseconds']
        cpu_percentages = self.shared_process_dict['cpu_percentages']
        memory_values = self.shared_process_dict['memory_values']
        io_values = self.shared_process_dict['io_values']

        # Timeseries
        statistics['timeseries']['timestamps_s'] = [k/1000 for k in timestamps_ms]
        statistics['timeseries']['cpu_percentages_norm'] = [k/psutil.cpu_count() for k in cpu_percentages]
        statistics['timeseries']['memory_values_rss_mb'] = [k['rss']/(1024*1024) for k in memory_values]
        statistics['timeseries']['memory_values_uss_mb'] = [k['uss']/(1024*1024) for k in memory_values]

        # Numericals
        io_values_temp = {key: value / (1024*1024) for key, value in io_values[-1].items()}

        statistics['numericals']['execution_time'] = (execution_end - execution_start)/1000
        statistics['numericals']['cpu_avg'] = np.mean(statistics['timeseries']['cpu_percentages_norm'])
        statistics['numericals']['memory_max_rss_mb'] = np.max(statistics['timeseries']['memory_values_rss_mb'])
        statistics['numericals']['memory_max_uss_mb'] = np.max(statistics['timeseries']['memory_values_uss_mb'])
        statistics['numericals']['total_read_mb'] = io_values_temp['read_chars']
        statistics['numericals']['total_write_mb'] = io_values_temp['write_chars']
        statistics['numericals']['disk_read_mb'] = io_values_temp['read_bytes']
        statistics['numericals']['disk_write_mb'] = io_values_temp['write_bytes']

        return statistics

    def _target_process_exited(self):
        return self.shared_process_dict['exit_status'] is not None

    def _setup_benchmarker(self):
        ''' Setup the benchmarker environment '''

        print('Setting up the benchmarker environment')
        os.makedirs(os.path.join(self.cwd, 'results'), exist_ok=True)

    def _read_io(self, p):
        try:
            io_counters = p.io_counters()
            return (io_counters.read_chars, io_counters.write_chars,
                    io_counters.read_bytes, io_counters.write_bytes)
        except Exception:
            with open(f'/proc/{p.pid}/io', 'rb') as f:
                io_data = f.read().decode().strip().split('\n')
                io_dict = dict(line.split(': ') for line in io_data)
                read_chars = int(io_dict.get('char'))
                write_chars = int(io_dict.get('wchar'))
                read_bytes = int(io_dict.get('read_bytes'))
                write_bytes = int(io_dict.get('write_bytes'))
                return read_chars, write_chars, read_bytes, write_bytes

    def get_raw_results(self):
        results = self.shared_process_dict.copy()
        results["sample_milliseconds"] = list(results["sample_milliseconds"])
        results["cpu_percentages"] = list(results["cpu_percentages"])
        results["memory_values"] = list(results["memory_values"])
        results["io_values"] = list(results["io_values"])

        return results

    def get_metadata(self):
        """
        Retrieves a copy of the shared process dictionary with specific entries removed.
        This method creates a copy of the `shared_process_dict` and removes the entries
        for "sample_milliseconds", "cpu_percentages", "memory_values", and "io_values".
        The resulting dictionary is returned.
        Returns:
            dict: A copy of the shared process dictionary with specific entries removed.
        """

        metadata_dict = self.shared_process_dict.copy()
        for entry in ("sample_milliseconds", "cpu_percentages", "memory_values", "io_values"):
            metadata_dict.pop(entry, None)

        return metadata_dict

    def load_docker_results(self, results_folder_path, analysis_id):
        """
        Load Docker benchmark results from JSON files.

        Args:
            results_folder_path (str): Path to the folder containing the result files.
            analysis_id (str): Unique identifier for the analysis.

        Returns:
            tuple: (success (bool), result (dict), statistics (dict), metadata (dict))
        """

        success = False

        try:
            with open(os.path.join(results_folder_path, f'result-{analysis_id}.json'), 'r') as f:
                result = json.load(f)
            with open(os.path.join(results_folder_path, f'statistics-{analysis_id}.json'), 'r') as f:
                statistics = json.load(f)
            with open(os.path.join(results_folder_path, f'metadata-{analysis_id}.json'), 'r') as f:
                metadata = json.load(f)

            success = True
            return success, result, statistics, metadata
        except Exception:
            return success, {}, {}, {}

def main() -> None:
    """
    Main function to run the benchmarker in Docker mode.

    This function serves as the entry point for the benchmarker when executed in docker. 
    It initializes and executes the Benchmarker to analyze a Python 3 script. Finally, 
    it saves the results-<analysis_id>.json, statistics-<analysis_id>.json, and 
    metadata-<analysis_id>.json files in the specified results folder.

    Environment Variables Required:
    - ANALYSIS_ID: A unique identifier for the analysis.
    - EXPERIMENT_WORKDIR: The relative (to Dockerfile WORKDIR) working directory path for 
        the experiment, i.e., the execution folder (e.g. ./code_runner/).
    - REQUIREMENTS_FILE: The path to the requirements file for the experiment, 
        relative to the working directory.
    - EXPERIMENT_FILE: The path to the experiment file to be benchmarked, 
        relative to the working directory.
    - RESULTS_FOLDER: The folder where the results, statistics, and metadata will be saved, 
        relative to the working directory.
    """

    ANALYSIS_ID = os.getenv('ANALYSIS_ID')
    EXPERIMENT_WORKDIR = os.getenv('EXPERIMENT_WORKDIR')
    REQUIREMENTS_FILE = os.getenv('REQUIREMENTS_FILE')
    EXPERIMENT_FILE = os.getenv('EXPERIMENT_FILE')
    RESULTS_FOLDER = os.getenv('RESULTS_FOLDER')

    bm = Benchmarker(interval=0.1, cwd=EXPERIMENT_WORKDIR, ishost=False)
    result = bm.bencmark_python3_script(EXPERIMENT_FILE, REQUIREMENTS_FILE)
    statistics = bm.get_statistics_basic()
    metadata = bm.get_metadata()

    os.makedirs(RESULTS_FOLDER, exist_ok=True)

    with open(os.path.join(RESULTS_FOLDER, f'result-{ANALYSIS_ID}.json'), 'w') as f:
        json.dump(result, f, indent=4)
    with open(os.path.join(RESULTS_FOLDER, f'statistics-{ANALYSIS_ID}.json'), 'w') as f:
        json.dump(statistics, f, indent=4)
    with open(os.path.join(RESULTS_FOLDER, f'metadata-{ANALYSIS_ID}.json'), 'w') as f:
        json.dump(metadata, f, indent=4)

if __name__ == "__main__":
    main()
