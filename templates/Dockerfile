# Stage 1 : Base setup
FROM ubuntu:latest AS base

# Install dependencies
RUN apt update && apt install -y python3 python3-pip python3-venv 
  

# Create virtual environment
RUN python3 -m venv /venv

# Stage 1.1 Juice - shop


# Install dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    tar \
    ca-certificates \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

# Install Node.js (v20.x) via NodeSource
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    node -v && npm -v

# Create app directory
WORKDIR /juice-shop

# Set Juice Shop version
ENV JUICE_SHOP_VERSION=17.3.0
ENV JUICE_SHOP_DIST=juice-shop-${JUICE_SHOP_VERSION}_node20_linux_x64.tgz

# Download and extract Juice Shop
RUN curl -LO https://github.com/juice-shop/juice-shop/releases/download/v${JUICE_SHOP_VERSION}/${JUICE_SHOP_DIST} && \
    tar -xzf ${JUICE_SHOP_DIST} --strip-components=1 && \
    rm ${JUICE_SHOP_DIST}

# Expose app port
EXPOSE 3001

# Stage 1.2 User emulation 


# Install curl and cron
RUN apt-get update && apt-get install -y curl cron 

# Add the script
COPY user_emulation/rand_jobs.sh /usr/local/bin/simulate_user.sh
RUN chmod +x /usr/local/bin/simulate_user.sh

# Create a cron job entry (runs every 5 mins)
RUN echo "*/1 * * * * root /usr/local/bin/simulate_user.sh" > /etc/cron.d/simulate-cron

# Apply cron job permissions
RUN chmod 0644 /etc/cron.d/simulate-cron && \
    crontab /etc/cron.d/simulate-cron

# Ensure logs go to stdout
RUN touch /var/log/cron.log



# Stage 2 : Analyzer setup for now benchmarker

FROM base AS bench

# Upgrade pip and install requirements
COPY benchmarker/requirements.txt /app/requirements.txt
RUN /venv/bin/pip install --upgrade pip \
 && /venv/bin/pip install -r /app/requirements.txt

# Copy the rest of the app
COPY /benchmarker /app
WORKDIR /app


# Stage 3 : Copy binary or python script to analyze 

FROM bench AS final

ARG malware_file


COPY binaries/${malware_file} /binary/${malware_file}

# make executable

#RUN chmod +x /binary/${malware_file}




WORKDIR /juice-shop
CMD ["npm","--prefix","/juice-shop", "start"]
WORKDIR /app





#RUN apt install -y curl \
 #   
  #  gnupg \
   # tar \
    #ca-certificates \
    #build-essential \
    #cron \

