#!/bin/bash
cd ~/CSVScanner

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
pip install gunicorn

# Create environment file if it doesn't exist
if [ ! -f .env ]; then
    echo "AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY
BEDROCK_AGENT_ID=$BEDROCK_AGENT_ID
BEDROCK_AGENT_ALIAS_ID=KG9OA19XR6
AWS_DEFAULT_REGION=us-east-2" > .env
fi

# Restart the service
sudo systemctl restart csvscanner.service 