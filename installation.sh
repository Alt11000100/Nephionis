#!/bin/sh


set -e  # Exit immediately if a command exits with a non-zero status

# Install Docker
echo "[*] Installing Docker..."
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install gvisor

(
  set -e
  ARCH=$(uname -m)
  URL=https://storage.googleapis.com/gvisor/releases/release/latest/${ARCH}
  wget ${URL}/runsc ${URL}/runsc.sha512 \
    ${URL}/containerd-shim-runsc-v1 ${URL}/containerd-shim-runsc-v1.sha512
  sha512sum -c runsc.sha512 \
    -c containerd-shim-runsc-v1.sha512
  rm -f *.sha512
  chmod a+rx runsc containerd-shim-runsc-v1
  sudo mv runsc containerd-shim-runsc-v1 /usr/local/bin
)


sudo /usr/local/bin/runsc install

sudo systemctl reload docker

# test gvisor
docker run --rm --runtime=runsc hello-world

# Install 
echo "[*] Installing Python 3, pip, and venv tools..."
sudo apt update
sudo apt install -y python3 python3-pip python3-venv

# Set up Python virtual environment
echo "[*] Setting up Python virtual environment..."
python3 -m venv venv
. venv/bin/activate

# Install Python dependencies
echo "[*] Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Install falco

sudo curl -fsSL https://falco.org/repo/falcosecurity-packages.asc | \
sudo gpg --dearmor -o /usr/share/keyrings/falco-archive-keyring.gpg

echo "deb [signed-by=/usr/share/keyrings/falco-archive-keyring.gpg] https://download.falco.org/packages/deb stable main" | \
sudo tee -a /etc/apt/sources.list.d/falcosecurity.list

sudo apt-get update -y

sudo apt install -y dkms make linux-headers-$(uname -r)
# If you use falcoctl driver loader to build the eBPF probe locally you need also clang toolchain
sudo apt install -y clang llvm
# You can install also the dialog package if you want it
sudo apt install -y dialog

sudo FALCO_FRONTEND=noninteractive apt-get install -y falco

# That's how the /etc/docker/daemon.json should look like
# {
#     "runtimes": {
#         "runsc": {
#             "path": "/usr/local/bin/runsc",
#             "runtimeArgs": [
#                 "--pod-init-config=/etc/docker/runsc_falco_config.json"
#             ]
#         }
#     }
# }

echo "[✓] Environment setup complete. Don't forget about falco.yaml"

