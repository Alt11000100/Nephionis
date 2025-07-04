#!/bin/bash

# Simulate user login
echo "$(date) - user login" >> /var/log/fake-auth.log

# Simulate web browsing
curl -s https://news.ycombinator.com > /dev/null

# Edit file
mkdir -p ~/Documents
echo "Test entry at $(date)" >> ~/Documents/notes.txt

# Random delay to mimic user
sleep $((RANDOM % 10 + 5))