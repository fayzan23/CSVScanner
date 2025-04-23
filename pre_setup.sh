#!/bin/bash

# Update package lists
sudo apt-get update

# Install Python and required packages
sudo apt-get install -y python3.12-venv python3-pip nginx

# Install system dependencies
sudo apt-get install -y build-essential libssl-dev libffi-dev python3-dev

# Wait for apt to release its lock
while sudo fuser /var/lib/dpkg/lock >/dev/null 2>&1 ; do
    echo "Waiting for other package manager to finish..."
    sleep 1
done

echo "Prerequisites installed successfully!" 