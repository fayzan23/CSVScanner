#!/bin/bash

# Check if key file and host are provided
if [ -z "$1" ] || [ -z "$2" ]; then
    echo "Usage: ./deploy_to_ec2.sh path/to/key.pem ubuntu@your-ec2-public-dns"
    exit 1
fi

KEY_FILE=$1
EC2_HOST=$2

echo "Creating deployment package..."
# Create a temporary deployment directory
mkdir -p deploy

# Copy application files
cp app.py deploy/
cp -r templates deploy/
cp -r static deploy/
cp requirements.txt deploy/
cp trading_actions.json deploy/

# Create environment file
cat > deploy/.env << EOL
AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
BEDROCK_AGENT_ID=${BEDROCK_AGENT_ID}
BEDROCK_AGENT_ALIAS_ID=KG9OA19XR6
AWS_DEFAULT_REGION=us-east-2
EOL

echo "Copying files to EC2..."
# Copy files to EC2
scp -i "$KEY_FILE" -r deploy/* "$EC2_HOST":~/CSVScanner/

# Clean up local deploy directory
rm -rf deploy

echo "Setting up application on EC2..."
# SSH into the instance and set up the application
ssh -i "$KEY_FILE" "$EC2_HOST" 'bash -s' << 'ENDSSH'
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
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
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
ENDSSH

echo "Deployment complete! Your application should be running at http://$EC2_HOST" 