FROM python:3.11-slim

# System deps
RUN apt-get update && apt-get install -y \
    gcc g++ libpq-dev curl poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download NLTK data
RUN python -c "import nltk; nltk.download('stopwords'); nltk.download('punkt')"

COPY . .

# Create output directories
RUN mkdir -p outputs/uploads outputs/resumes outputs/cover_letters

EXPOSE 8000 8501

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
