#!/bin/bash

# Check if key file is provided
if [ -z "$1" ]
then
    echo "Please provide the path to your .pem key file"
    echo "Usage: ./deploy.sh path/to/key.pem ec2-user@your-ec2-instance"
    exit 1
fi

if [ -z "$2" ]
then
    echo "Please provide the EC2 instance address"
    echo "Usage: ./deploy.sh path/to/key.pem ec2-user@your-ec2-instance"
    exit 1
fi

KEY_FILE=$1
EC2_ADDRESS=$2

# Create deployment directory
mkdir -p deploy
cp app.py deploy/
cp -r templates deploy/
cp -r static deploy/
cp requirements.txt deploy/
cp trading_actions.json deploy/

# Copy files to EC2
echo "Copying files to EC2..."
scp -i $KEY_FILE -r deploy/* $EC2_ADDRESS:~/CSVScanner/

# Clean up
rm -rf deploy

# Run setup script
echo "Running setup script..."
ssh -i $KEY_FILE $EC2_ADDRESS 'bash -s' < setup.sh

echo "Deployment complete! Your application should be running on http://$EC2_ADDRESS" 