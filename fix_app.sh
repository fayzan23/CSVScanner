#!/bin/bash

# Update and install dependencies
sudo apt-get update
sudo apt-get install -y python3-pip python3-flask python3-pandas python3-boto3 nginx

# Configure Nginx
sudo bash -c 'cat > /etc/nginx/sites-available/csvscanner << EOL
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
EOL'

# Enable site and remove default
sudo ln -sf /etc/nginx/sites-available/csvscanner /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Install Gunicorn
sudo pip3 install gunicorn

# Create systemd service
sudo bash -c 'cat > /etc/systemd/system/csvscanner.service << EOL
[Unit]
Description=Gunicorn instance to serve CSVScanner
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/CSVScanner
EnvironmentFile=/home/ubuntu/CSVScanner/.env
ExecStart=/usr/local/bin/gunicorn --workers 4 --bind localhost:8000 app:app

[Install]
WantedBy=multi-user.target
EOL'

# Reload systemd and restart services
sudo systemctl daemon-reload
sudo systemctl restart nginx
sudo systemctl enable csvscanner
sudo systemctl restart csvscanner

# Show service status
sudo systemctl status nginx.service csvscanner.service 