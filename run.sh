#!/bin/bash
cd ~/CSVScanner
export $(cat .env | xargs)
python3 -m gunicorn --bind 0.0.0.0:80 app:app 