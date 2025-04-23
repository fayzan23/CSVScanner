# PowerShell deployment script

# Set variables
$KEY_FILE = "C:\Users\zohay\Downloads\csvscanner-prod-key.pem"
$EC2_HOST = "ubuntu@3.142.90.22"

Write-Host "Creating deployment package..."
# Create a temporary deployment directory
New-Item -ItemType Directory -Force -Path .\deploy

# Copy application files
Copy-Item app.py, requirements.txt, trading_actions.json -Destination .\deploy
Copy-Item -Recurse templates, static -Destination .\deploy

# Create environment file
@"
AWS_ACCESS_KEY_ID=$env:AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY=$env:AWS_SECRET_ACCESS_KEY
BEDROCK_AGENT_ID=$env:BEDROCK_AGENT_ID
BEDROCK_AGENT_ALIAS_ID=KG9OA19XR6
AWS_DEFAULT_REGION=us-east-2
"@ | Set-Content .\deploy\.env

Write-Host "Copying files to EC2..."
# Copy files to EC2
ssh -i $KEY_FILE $EC2_HOST "mkdir -p ~/CSVScanner"
scp -i $KEY_FILE -r .\deploy\* ${EC2_HOST}:~/CSVScanner/
scp -i $KEY_FILE pre_setup.sh ${EC2_HOST}:~/pre_setup.sh
scp -i $KEY_FILE setup_commands.sh ${EC2_HOST}:~/setup_commands.sh

# Clean up local deploy directory
Remove-Item -Recurse -Force .\deploy

Write-Host "Installing prerequisites..."
# Run the pre-setup script
ssh -i $KEY_FILE $EC2_HOST "chmod +x ~/pre_setup.sh && sudo ~/pre_setup.sh"

Write-Host "Setting up application..."
# Run the setup script
ssh -i $KEY_FILE $EC2_HOST "chmod +x ~/setup_commands.sh && ~/setup_commands.sh"

Write-Host "Deployment complete! Your application should be running at http://3.142.90.22" 