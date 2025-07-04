import typer 
from typing_extensions import Annotated, Optional
import os

import docker
import my_containers
from monitors.performance_monitor import PerformanceMonitorSandbox as pm
from session import Session,create_session,execute_session
import json

from rich.progress import Progress, SpinnerColumn, TextColumn

from sandbox_handler import SandboxHandler
from monitors.process_monitor import ProcessBenchmarker
from monitors.syscalls.syscall_monitor import SyscallMonitor
import docker_builder as dbuilder
import time
from datetime import datetime
import asyncio
import report_handler
from backend_handler import BackendHandler
from modules.utils import stop_and_remove_labelled_containers


app = typer.Typer()

client = docker.from_env()

BINARIES_DIR = f"{os.path.dirname(__file__)}/binaries"
SESSIONS_DIR = f"{os.path.dirname(__file__)}/sessions"



@app.command()
def main(configure: Annotated[str,typer.Option(help="Configure the tools you want to use")] = ""):
    print("Welcome analyst.")
    if configure:
        print(f"Let's start configurin' the {configure}")

    

@app.command()
def start_env(client): # doesnt do anything as of now
    ''' may also need  newgrp docker '''
    
    print(client.containers.run("alpine", ["echo", "hello", "world"]))

@app.command()
def killswitch():
    print("Stopping everything....")

@app.command()
def backend(up_down : str ):
    '''Start the backend and queue containers : Options up / down'''
    bh = BackendHandler()
    if up_down=="up":
    
        bh.run()
        ip = bh.queue_up()
        time.sleep(10) # random number will it always be enough??
        bh.receiver_up(ip)
        typer.echo(f"Backend up and running! Queue is running at {ip}")
    if up_down=="down":
        bh.backend_down()
    

@app.command() 
def queue (up_down : str ):
    '''Start the  queue receiver : Options up / down'''
    bh = BackendHandler()
    if up_down=="up":
        bh.queue_receiver()
    if up_down=="down":
        bh.backend_down()

@app.command()
def test_submit():
    '''Testing prometheus with cadvisor on a redis container'''
    my_containers.create_containers()

@app.command()
def listcontainers():
    '''List all running containers'''
    my_containers.list_running_containers()

@app.command()
def stop_containers(label: str=""):
    '''Stop running containers with label '''
    my_containers.stop_and_remove_labelled_containers()

@app.command()
def monitor(stop : bool=False):
    '''Start the external monitoring process'''
    # add checks if it is running or not
    if stop:
        pm().stop_and_remove_labelled_containers()
        stop_and_remove_labelled_containers("SyscallMonitor")
    else:

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            # progress.add_task(description="Processing...", total=None)
            progress.add_task(description="Preparing...", total=None)

            pm().create_containers()
            SyscallMonitor().create_falco_container()

        typer.echo("Grafana is listening at localhost:3000")


@app.command()
def getmonitor(client=client):
    '''Use the monitor for an analysis'''
    print(type(client))



# Command for creating a session
@app.command()
def init_session(
    malware_file: str = typer.Option(..., help="Can be either full path or the name  in binaries/..."),
    name: str = typer.Option("test", help="Session name"),
    sha256: str = typer.Option("none", help="SHA256 of the file being analyzed"),
    process_monitor_flag: bool = typer.Option(True, help="Enable process monitor"),
):
    ''' Create a session'''
    
    # binary_filename = os.path.basename(malware_file)
    # binary_path = os.path.join( BINARIES_DIR , binary_filename)

    # if not os.path.isfile(binary_path):
    #     typer.echo(f"❌ Error: File '{binary_path}' does not exist.", err=True)
    #     raise typer.Exit(1)



    # try:
    #     buildargs_dict = {"malware_file" : binary_filename}
    # except FileNotFoundError:
    #     typer.echo("❌ Invalid malware file for buildargs", err=True)
    #     raise typer.Exit(code=1)

    # session = Session(
    #     name=name,
    #     sha256=sha256,
    #     buildargs=buildargs_dict,
    #     process_monitor_flag=process_monitor_flag
    # )
    # typer.echo(f"✅ Created session: {session}")

    # json_path = session.save_to_json(SESSIONS_DIR)
    # typer.echo(f"✅ Created session and saved to {json_path}")

    create_session(malware_file, name, sha256, process_monitor_flag,BINARIES_DIR,SESSIONS_DIR)


@app.command("list-sessions")
def list_sessions():
    '''List saved sessions'''
    if not os.path.isdir(SESSIONS_DIR):
        typer.echo("📂 No sessions directory found.")
        raise typer.Exit()

    session_files = [f for f in os.listdir(SESSIONS_DIR) if f.startswith("session-") and f.endswith(".json")]
    if not session_files:
        typer.echo("📭 No saved sessions found.")
        return

    typer.echo("📋 Saved sessions:")
    for file in session_files:
        try:
            with open(os.path.join(SESSIONS_DIR, file), "r") as f:
                data = json.load(f)
                malware = data.get("buildargs", {}).get("malware_file", "unknown")
                typer.echo(f"🆔 {data['id']} | 🕒 {data['timestamp']} | 🧪 {data['name']} | 🐛 {malware}")
        except Exception as e:
            typer.echo(f"⚠️ Could not read {file}: {e}", err=True)


@app.command()
def analyze(
     session_id: str = typer.Option(None, help="Start an analysis based on a session",rich_help_panel="Customization") ,
     dir : str =typer.Option(None, help="Specify dir of sessions to run",rich_help_panel="Customization")
):
    '''Execute one or multiple sessions'''
    if dir:
        ids = []
        for filename in os.listdir(dir):
            binary_path = os.path.join(dir, filename)
            if os.path.isfile(binary_path):
                tmp = os.path.splitext(filename)[0].split("-",1)[1]
                
                try:
                    if execute_session(tmp,SESSIONS_DIR):
                        ids.append(tmp)
                except Exception as e:
                    print(f"Caught {e}")
        time.sleep(15)
        for session_id in ids:
            asyncio.run(report_handler.prom_raw(session_id))

    else:
        if session_id:
            if execute_session(session_id,SESSIONS_DIR):
                time.sleep(30) # this is random, need to check it
                asyncio.run(report_handler.prom_raw(session_id))
        else:
            typer.echo("Didn't specify anything! Maybe you should check --help?")


@app.command()
def sandbox_test(session_id: str = typer.Option(..., help="Start an analysis based on a session",rich_help_panel="Customization")):

    execute_session(session_id,SESSIONS_DIR,False)
    
    

if __name__ == "__main__":
    app()