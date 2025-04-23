#!/bin/bash

# Fix Nginx configuration
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

# Enable Nginx site
sudo ln -sf /etc/nginx/sites-available/csvscanner /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Install Gunicorn
source ~/CSVScanner/venv/bin/activate
pip install gunicorn

# Create environment file if it doesn't exist
if [ ! -f ~/CSVScanner/.env ]; then
    echo "Creating .env file..."
    touch ~/CSVScanner/.env
fi

# Restart services
sudo systemctl daemon-reload
sudo systemctl restart nginx
sudo systemctl restart csvscanner

# Check service status
echo "Nginx status:"
sudo systemctl status nginx
echo "CSVScanner status:"
sudo systemctl status csvscanner 