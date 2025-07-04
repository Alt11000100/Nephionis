import os
import venv
import subprocess
import shutil

class VenvInstaller:
    '''
    Class for managing python3 virtual environments,
    and generating commands for python3 scripts using the venv interpreters.
    '''

    def __init__(self) -> None:
        self.venv_dir = None
        self.command = None

    def create_venv(self, main_script, requirements):
        '''
        Creates a new python3 virtual environment with requirements installed.
        Then returns the python3 command for running the input script using
        venv python3 interpreter.

        ...

        Attributes
        ----------
        main_script : str
            Relative main python script path (including the .py extension)
        requirements : str
            The relative path to requirements.txt file
        '''

        success = True
        script = os.path.join(os.getcwd(), main_script)
        requirements_file = os.path.join(os.getcwd(), requirements)

        if not os.path.exists(script):
            print(f'Script file {script} does NOT exist')
            return None
        elif not os.path.exists(requirements_file):
            print(f'Requirements file {requirements_file} does NOT exist')
            return None

        # Path to the directory where the virtual environment will be created
        path_arr = main_script.split('/')

        self.venv_dir = os.path.join(os.getcwd(), *path_arr[:-1], f"venv_{path_arr[-1][:-3]}")

        # Create a virtual environment, if it exists it is first cleared
        venv.create(self.venv_dir, with_pip=True, clear=True)

        # Install dependencies into the virtual environment
        pip_venv = os.path.join(self.venv_dir, 'bin', 'pip3')
        result = subprocess.run(
            [pip_venv, "install", "-r", requirements_file],
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode != 0:
            print("Error installing requirements:")
            print(result.stderr)
            success = False
            return success, result.stderr
        else:
            print("Requirements installed successfully!.!")

        # Define the command to benchmark
        python3_venv = os.path.join(self.venv_dir, 'bin', 'python3')
        self.command = f"{python3_venv} {script}"

        return success, self.command

    def remove_venv(self):
        ''' Removes the created virtual environment '''

        if self.venv_dir is not None:
            shutil.rmtree(self.venv_dir)
            print(f'Removing venv {self.venv_dir}')
