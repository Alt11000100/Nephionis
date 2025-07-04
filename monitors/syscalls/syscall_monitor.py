import os
import docker

class SyscallMonitor():
    '''For now this will just be falco'''


    def __init__(self):
        self.client = docker.from_env()
        # self.net = self.client.networks.get("my_custom_network")
        pass
        
        
    def create_falco_container(self): # fix net option

        # need to test that
        rule_folder = os.path.abspath("/etc/falco")
        # falco_file = os.path.abspath("falco.yaml")

        falco = self.client.containers.run(
            image="falcosecurity/falco:latest",
            name="falco",
            privileged=True,
            volumes={
                '/var/run/docker.sock': {'bind': '/host/var/run/docker.sock', 'mode': 'rw'},
                '/dev': {'bind': '/host/dev', 'mode': 'rw'},
                '/proc': {'bind': '/host/proc', 'mode': 'ro'},
                '/boot': {'bind': '/host/boot', 'mode': 'ro'},
                '/lib/modules': {'bind': '/host/lib/modules', 'mode': 'ro'},
                '/usr': {'bind': '/host/usr', 'mode': 'ro'},
                '/etc': {'bind': '/host/etc', 'mode': 'ro'},
                rule_folder: {'bind': '/etc/falco','mode': 'ro'},
                # rule_file: {'bind': '/etc/falco/falco_rules.local.yaml', 'mode': 'ro'}
            },
            detach=True,
            # environment={"METRICS_ENABLED": "true", "PLUGINS_METRICS_ENABLED" : "true", "PROMETHEUS_METRICS_ENABLED": "true", "FALCO_METRICS_SERVER_PORT":"8765"},
            tty=True,
            stdin_open=True,
            # remove=True,
            network=self.client.networks.get("my_custom_network").name, # fix this better
            labels={"created_by": "SyscallMonitor"}
        )
        # self.started_containers.append(falco.id)
        # self.create_falco_sidekick()
        # self.create_falco_sidekick_ui()
        return falco
    
    def create_falco_sidekick(self): # fix net option
        # need to test that
        # rule_folder = os.path.abspath("/etc/falco")
        # falco_file = os.path.abspath("falco.yaml")

        falco_side = self.client.containers.run(
            image="falcosecurity/falcosidekick:latest",
            name="falco_side",
            ports={'2801/tcp': 2801},
            # privileged=True,
            # volumes={
            #     '/var/run/docker.sock': {'bind': '/host/var/run/docker.sock', 'mode': 'rw'},
            #     '/dev': {'bind': '/host/dev', 'mode': 'rw'},
            #     '/proc': {'bind': '/host/proc', 'mode': 'ro'},
            #     '/boot': {'bind': '/host/boot', 'mode': 'ro'},
            #     '/lib/modules': {'bind': '/host/lib/modules', 'mode': 'ro'},
            #     '/usr': {'bind': '/host/usr', 'mode': 'ro'},
            #     '/etc': {'bind': '/host/etc', 'mode': 'ro'},
            #     rule_folder: {'bind': '/etc/falco','mode': 'ro'},
            #     # rule_file: {'bind': '/etc/falco/falco_rules.local.yaml', 'mode': 'ro'}
            # },
            detach=True,
            # environment={"METRICS_ENABLED": "true", "PLUGINS_METRICS_ENABLED" : "true", "PROMETHEUS_METRICS_ENABLED": "true", "FALCO_METRICS_SERVER_PORT":"8765"},
            # tty=True,
            # stdin_open=True,
            # remove=True,
            network=self.client.networks.get("my_custom_network").name, # fix this better
            labels={"created_by": "SyscallMonitor"}
        )
        # self.started_containers.append(falco.id)
        return falco_side
    
    def create_falco_sidekick_ui(self): # fix net option
        # need to test that
        # rule_folder = os.path.abspath("/etc/falco")
        # falco_file = os.path.abspath("falco.yaml")

        falco_side = self.client.containers.run(
            image="falcosecurity/falcosidekick-ui:latest",
            name="falco_side_ui",
            ports={'2802/tcp': 2802},
            # privileged=True,
            # volumes={
            #     '/var/run/docker.sock': {'bind': '/host/var/run/docker.sock', 'mode': 'rw'},
            #     '/dev': {'bind': '/host/dev', 'mode': 'rw'},
            #     '/proc': {'bind': '/host/proc', 'mode': 'ro'},
            #     '/boot': {'bind': '/host/boot', 'mode': 'ro'},
            #     '/lib/modules': {'bind': '/host/lib/modules', 'mode': 'ro'},
            #     '/usr': {'bind': '/host/usr', 'mode': 'ro'},
            #     '/etc': {'bind': '/host/etc', 'mode': 'ro'},
            #     rule_folder: {'bind': '/etc/falco','mode': 'ro'},
            #     # rule_file: {'bind': '/etc/falco/falco_rules.local.yaml', 'mode': 'ro'}
            # },
            detach=True,
            environment={"FALCOSIDEKICK_UI_REDIS_URL": "redis:6379"},
            # tty=True,
            # stdin_open=True,
            # remove=True,
            network=self.client.networks.get("my_custom_network").name, # fix this better
            labels={"created_by": "SyscallMonitor"}
        )
        # self.started_containers.append(falco.id)
        return falco_side


    
# Testing

# SyscallMonitor().create_falco_container()

