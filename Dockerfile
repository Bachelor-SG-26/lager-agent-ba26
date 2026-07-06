FROM python:3.12-slim

WORKDIR /app

# Dependencies installieren
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App-Code kopieren
COPY . .

# Tests nach Installation der Dependencies ausführen
RUN python -m pytest tests/ -v

# Persistente Daten (DBs, .env) in /app/data
ENV DATA_DIR=/app/data

EXPOSE 8501

CMD ["streamlit", "run", "streamlit_app.py", "--server.address=0.0.0.0", "--server.port=8501"]
