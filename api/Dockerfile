FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py doctors.json ./
COPY schemas.py llm.py tools.py graph.py state.py database.py config.py session.py history.py ./
COPY agents/ ./agents/
RUN mkdir -p /app/data && chown 10001 /app/data
USER 10001
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
