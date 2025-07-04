FROM ubuntu:latest

# Install dependencies
RUN apt update && apt install -y python3 python3-pip python3-venv

# Create virtual environment
RUN python3 -m venv /venv

# Upgrade pip and install requirements
COPY requirements.txt /app/requirements.txt
RUN /venv/bin/pip install --upgrade pip \
 && /venv/bin/pip install -r /app/requirements.txt

# Copy the rest of the app
COPY . /app
WORKDIR /app

# Run using venv Python
# CMD ["/venv/bin/python", "process_monitor.py"] # without is proc_mon:2