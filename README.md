# AI Python Teacher

An AI-powered Python tutoring application with a Flask backend and Flutter frontend.

## Project Structure

```
├── backend/          # Flask API backend
│   ├── app.py        # Main Flask application
│   ├── config.py     # Configuration and environment variables
│   ├── gemini_ai.py  # Gemini AI API integration
│   ├── test_app.py   # Unit tests
│   └── vercel.json   # Vercel deployment configuration
├── frontend/         # Flutter frontend application
│   └── lib/
│       └── main.dart # Main Flutter application
└── requirements.txt  # Python dependencies
```

## Backend Setup

### Prerequisites
- Python 3.9+
- Gemini API key from Google AI Studio

### Installation

```bash
cd backend
pip install -r requirements.txt
```

### Configuration

Create a `.env` file in the `backend` directory:

```env
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-2.5-flash
CORS_ORIGINS=*
LOG_LEVEL=INFO
```

### Running Locally

```bash
cd backend
python app.py
```

The API will be available at `http://localhost:5000`

### Running Tests

```bash
cd backend
python -m unittest test_app -v
```

## API Endpoints

### Health Check
- **GET** `/health`
- Returns: `{"status": "ok"}`

### Ask AI Tutor
- **POST** `/ask-ai`
- Body:
  ```json
  {
    "topic": "optional topic",
    "code": "optional Python code",
    "question": "required question",
    "level": "beginner|intermediate|advanced"
  }
  ```
- Returns:
  ```json
  {
    "answer": "tutor response",
    "request_id": "uuid"
  }
  ```

## Deployment to Vercel

### Backend Deployment

1. Install Vercel CLI:
   ```bash
   npm i -g vercel
   ```

2. Navigate to backend directory:
   ```bash
   cd backend
   ```

3. Deploy to Vercel:
   ```bash
   vercel
   ```

4. Set environment variables in Vercel dashboard:
   - `GEMINI_API_KEY`: Your Gemini API key
   - `GEMINI_MODEL`: gemini-2.5-flash
   - `CORS_ORIGINS`: Your frontend domain or *

### Frontend Configuration

Update the backend URL in `frontend/lib/main.dart` to point to your deployed Vercel URL.

## Features

- **AI Tutoring**: Get contextual help with Python code
- **Skill Levels**: Adapts responses for beginner, intermediate, and advanced learners
- **Code Safety**: Sanitizes AI responses to prevent giving full solutions
- **Retry Logic**: Automatic retries for transient failures
- **Thread-Safe**: HTTP connection pooling for better performance

## License

MIT License