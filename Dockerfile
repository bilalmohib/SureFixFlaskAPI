# Dockerfile
FROM python:3.12.1
RUN pip install Flask gunicorn firebase_admin pycryptodome==3.10.1 pyrebase4 flasgger

COPY . /app
WORKDIR /app
# 4
ENV PORT 8080

# 5
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 app:app