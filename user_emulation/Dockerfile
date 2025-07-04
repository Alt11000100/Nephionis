FROM ubuntu:latest

# Install curl and cron
RUN apt-get update && apt-get install -y curl cron

# Add the script
COPY rand_jobs.sh /usr/local/bin/simulate_user.sh
RUN chmod +x /usr/local/bin/simulate_user.sh

# Create a cron job entry (runs every 5 mins)
RUN echo "*/1 * * * * root /usr/local/bin/simulate_user.sh" > /etc/cron.d/simulate-cron

# Apply cron job permissions
RUN chmod 0644 /etc/cron.d/simulate-cron && \
    crontab /etc/cron.d/simulate-cron

# Ensure logs go to stdout
RUN touch /var/log/cron.log

# Start cron in foreground
