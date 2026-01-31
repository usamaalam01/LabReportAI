# Lab Report AI

AI-powered lab report interpretation service that provides educational analysis of medical laboratory test results. Built with FastAPI, Next.js, and LLM-based analysis.

## Features

- **OCR Text Extraction**: Automatically extracts text from PDF and image files (JPEG/PNG)
- **PII Scrubbing**: Removes personally identifiable information before processing
- **LLM Analysis**: Uses AI to interpret lab results and provide educational insights
- **Multi-language Support**: English and Urdu (اردو) output with RTL PDF support
- **PDF Reports**: Generates formatted PDF reports with charts and visualizations
- **WhatsApp Integration**: Optional Twilio-based WhatsApp notifications (via phone number)
- **Rate Limiting & Security**: reCAPTCHA protection, file size limits, automatic cleanup
- **Responsive UI**: Drag-and-drop file upload, real-time progress tracking, mobile-friendly

## Quick Start

### Prerequisites

- Docker and Docker Compose
- LLM API key (Groq or OpenRouter)
- (Optional) reCAPTCHA site/secret keys for spam protection
- (Optional) Twilio credentials for WhatsApp integration

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd labreportai
   ```

2. Copy the example environment file and configure it:
   ```bash
   cp backend/.env.example backend/.env
   ```

3. Edit `backend/.env` and set required environment variables (see Environment Variables section below)

4. Start all services with Docker Compose:
   ```bash
   docker compose up --build -d
   ```

5. Wait for services to start (30-60 seconds), then open your browser:
   - **Frontend**: http://localhost:3000
   - **Backend API**: http://localhost:8000/docs
   - **Health Check**: http://localhost:8000/v1/health

### Stopping Services

```bash
docker compose down
```

## Basic Usage

### Web Interface

1. Open http://localhost:3000 in your browser
2. Drag and drop (or click to upload) a lab report file (PDF, JPEG, or PNG)
3. Optionally enter patient age and gender for more accurate reference ranges
4. Select output language (English or Urdu)
5. Click "Analyze Report" and wait 10-30 seconds
6. View results, download PDF report

### WhatsApp (Optional)

If Twilio WhatsApp is configured:

1. Send a photo or PDF of your lab report to your Twilio WhatsApp number
2. Receive automated analysis results in Urdu

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `LLM_PROVIDER` | LLM provider (groq or openrouter) | `groq` |
| `GROQ_API_KEY` | Groq API key (if using Groq) | `gsk_...` |
| `OPENROUTER_API_KEY` | OpenRouter API key (if using OpenRouter) | `sk-or-...` |
| `MYSQL_ROOT_PASSWORD` | MySQL root password | `secretpassword` |
| `MYSQL_DATABASE` | MySQL database name | `labreportai` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `RECAPTCHA_SITE_KEY` | Google reCAPTCHA v3 site key | `placeholder` |
| `RECAPTCHA_SECRET_KEY` | Google reCAPTCHA v3 secret key | `placeholder` |
| `TWILIO_ACCOUNT_SID` | Twilio account SID for WhatsApp | `placeholder` |
| `TWILIO_AUTH_TOKEN` | Twilio auth token for WhatsApp | `placeholder` |
| `TWILIO_WHATSAPP_NUMBER` | Twilio WhatsApp number (e.g., +14155238886) | `placeholder` |
| `MAX_FILE_SIZE_MB` | Maximum file upload size (MB) | `20` |
| `RETENTION_PERIOD` | Hours to keep uploaded files/results | `24` |
| `RATE_LIMIT_REQUESTS` | Max requests per IP per hour | `10` |

### LLM Model Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_ANALYSIS_MODEL` | Model for main analysis | `llama-3.3-70b-versatile` |
| `LLM_VALIDATION_MODEL` | Model for pre-validation | `llama-3.1-8b-instant` |
| `LLM_TRANSLATION_MODEL` | Model for translation | `llama-3.1-8b-instant` |

## Architecture

### Services

- **frontend**: Next.js web application (port 3000)
- **backend**: FastAPI REST API (port 8000)
- **mysql**: MySQL database (port 3307)
- **redis**: Redis cache for Celery (port 6379)
- **celery-worker**: Background task processor
- **celery-beat**: Scheduled task scheduler (cleanup jobs)

### Data Flow

1. User uploads lab report (PDF/image) via frontend
2. Backend validates file, stores in MySQL, dispatches Celery task
3. Celery worker processes report:
   - OCR extraction (PaddleOCR)
   - PII scrubbing (regex-based)
   - Pre-validation (LLM checks if it's a lab report)
   - Analysis (LLM interprets results)
   - Translation (if Urdu selected)
   - Chart generation (Matplotlib)
   - PDF generation (WeasyPrint)
4. Frontend polls status endpoint, displays results when complete

## Troubleshooting

### Docker Build Fails

- **Issue**: Build timeout or network errors
- **Solution**: Clear Docker cache and retry:
  ```bash
  docker builder prune -f
  docker compose down
  docker compose up --build -d
  ```

### Backend Container Exits Immediately

- **Issue**: Missing or invalid environment variables
- **Solution**: Check `backend/.env` for required variables (LLM_PROVIDER, API keys)

### "No active Celery workers" in Health Check

- **Issue**: Celery worker container not running or Redis connection failed
- **Solution**:
  ```bash
  docker compose ps  # Check if celery-worker is running
  docker compose logs celery-worker  # Check worker logs
  docker compose restart celery-worker
  ```

### "Connection refused" to MySQL

- **Issue**: MySQL container not ready yet
- **Solution**: Wait 30-60 seconds for MySQL to initialize, then restart backend:
  ```bash
  docker compose restart backend
  ```

### File Upload Fails

- **Issue**: File size exceeds limit or unsupported file type
- **Solution**: Check file is PDF/JPEG/PNG and under MAX_FILE_SIZE_MB (default 20MB)

### LLM Analysis Fails

- **Issue**: Invalid API key or rate limit exceeded
- **Solution**: Verify LLM_PROVIDER and corresponding API key in `.env`. Check API provider dashboard for quota/limits.

## Development

### Running Tests

```bash
# From backend directory
docker compose exec backend pytest tests/ -v
```

### Viewing Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend
docker compose logs -f celery-worker
```

### Accessing Database

```bash
docker compose exec mysql mysql -u root -p labreportai
# Enter password from MYSQL_ROOT_PASSWORD
```

## Security Notes

- PII is automatically scrubbed from OCR text before analysis
- All logs sanitize phone numbers, emails, and patient names
- Files and results are automatically deleted after RETENTION_PERIOD
- reCAPTCHA prevents abuse (if configured)
- Rate limiting restricts requests per IP

## License

This is an educational tool. Not for medical diagnosis. See disclaimer in application.

## Support

For issues or questions, please check the troubleshooting section above or consult the application logs.
