Kikizakeshi — AI Alcohol Label Concierge

FastAPI × Google Vision API × LLM (OpenAI endpoint)
Hosted on Google Cloud Run

1. Overview

Kikizakeshi is an AI-powered web application that analyzes alcohol labels (sake, wine, beer, whiskey, etc.) and returns personalized recommendations.

The app performs:

OCR label extraction via Google Vision API

Keyword and metadata parsing

LLM-based drink recommendations

Multi-language output

Zero server-side data retention

Designed as a lightweight, serverless POC.

2. Live URL
https://kikizakeshi-1020268592604.asia-northeast1.run.app/


This URL remains stable unless the service name, project, or region changes.

3. Features

OCR extraction of labels

AI recommendation via OpenAI endpoint

Supports multiple alcohol types

Mobile-friendly UI

Fully serverless (Cloud Run)

Static assets delivered from /static

No data stored server-side

4. Project Structure
root/
│ main.py
│ Dockerfile
│ requirements.txt
│
├─ static/
│    favicon.ico
│    favicon.svg
│    apple-touch-icon.png
│    style.css
│
└─ templates/
     index.html

5. Environment Variables (Cloud Run)
Key	Description
OPENAI_API_KEY	OpenAI endpoint key
OPENAI_MODEL	e.g. gpt-4.1-mini
LLM_PROVIDER	Defaults to openai

Set these under Cloud Run → Variables & Secrets.

6. Deployment Steps
1. Build the Docker image
docker build -t asia-northeast1-docker.pkg.dev/sake-master-481904/kikizakeshi/kikizakeshi:v1 .

2. Push to Artifact Registry
docker push asia-northeast1-docker.pkg.dev/sake-master-481904/kikizakeshi/kikizakeshi:v1

3. Deploy to Cloud Run (Console)

Select the pushed image

Allow unauthenticated access

Region: asia-northeast1

Re-deploying the service will not change the URL.

7. Static Assets

Static files are served via:

app.mount("/static", StaticFiles(directory="static"), name="static")


Icons are referenced in templates/index.html:

<link rel="icon" href="/static/favicon.ico">
<link rel="icon" href="/static/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/static/apple-touch-icon.png">

8. Security

OCR: Google Vision API

Cloud Run service account:

1020268592604-compute@developer.gserviceaccount.com


Required Vision AI roles already granted at the project level

No persistent data storage

HTTPS only (Cloud Run default)

9. License

This project is currently intended for POC and demonstration purposes only.