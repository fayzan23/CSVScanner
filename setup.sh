#!/bin/bash

# Update system packages
sudo apt-get update
sudo apt-get upgrade -y

# Install Python and pip
sudo apt-get install -y python3-pip python3-dev build-essential libssl-dev libffi-dev python3-setuptools nginx

# Install virtualenv
sudo pip3 install virtualenv

# Create a directory for the application
mkdir -p ~/CSVScanner
cd ~/CSVScanner

# Create and activate virtual environment
virtualenv venv
source venv/bin/activate

# Install required packages
pip install gunicorn flask boto3 pandas python-dotenv werkzeug numpy requests

# Create Nginx configuration
sudo bash -c 'cat > /etc/nginx/sites-available/CSVScanner << EOL
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }
}
EOL'

# Enable the Nginx site
sudo ln -s /etc/nginx/sites-available/CSVScanner /etc/nginx/sites-enabled
sudo rm /etc/nginx/sites-enabled/default

# Create systemd service file for Gunicorn
sudo bash -c 'cat > /etc/systemd/system/csvscanner.service << EOL
[Unit]
Description=Gunicorn instance to serve CSVScanner
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/CSVScanner
Environment="PATH=/home/ubuntu/CSVScanner/venv/bin"
ExecStart=/home/ubuntu/CSVScanner/venv/bin/gunicorn --workers 3 --bind localhost:8000 app:app

[Install]
WantedBy=multi-user.target
EOL'

# Restart Nginx
sudo systemctl restart nginx

# Start and enable the Gunicorn service
sudo systemctl start csvscanner
sudo systemctl enable csvscanner 