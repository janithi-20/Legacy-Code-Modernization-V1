FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY backend ./backend
COPY frontend ./frontend
COPY demo.py .

ENV PYTHONPATH=/app
EXPOSE 8501

CMD ["sh", "-c", "python -m backend.bootstrap && python -m streamlit run frontend/dashboard_app.py --server.address 0.0.0.0 --server.port 8501 --server.headless true"]
