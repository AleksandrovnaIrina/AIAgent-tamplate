FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py sheets.py carousel_image_gen.py ./

EXPOSE 3500

CMD ["python", "server.py"]
