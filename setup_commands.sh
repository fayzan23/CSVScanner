#!/bin/bash
cd ~/CSVScanner

# Set up Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt

# Create Nginx configuration
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

# Create systemd service
sudo bash -c 'cat > /etc/systemd/system/csvscanner.service << EOL
[Unit]
Description=Gunicorn instance to serve CSVScanner
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/CSVScanner
Environment="PATH=/home/ubuntu/CSVScanner/venv/bin"
EnvironmentFile=/home/ubuntu/CSVScanner/.env
ExecStart=/home/ubuntu/CSVScanner/venv/bin/gunicorn --workers 4 --bind localhost:8000 app:app

[Install]
WantedBy=multi-user.target
EOL'

# Reload systemd, restart services
sudo systemctl daemon-reload
sudo systemctl restart nginx
sudo systemctl enable csvscanner
sudo systemctl start csvscanner

echo "Application setup complete!" 