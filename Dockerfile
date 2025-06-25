FROM python:3.8-slim

WORKDIR /app

COPY . .

# Install ping and your Python requirements
RUN apt-get update && apt-get install -y iputils-ping && \
    pip install --no-cache-dir -r requirements.txt

CMD ["python", "main.py"]
