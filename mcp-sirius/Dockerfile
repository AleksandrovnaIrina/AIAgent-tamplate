FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium --with-deps

COPY server.py notion.py pdf.py banner.py drive.py gauth.py search.py fetch.py sheets.py youtube.py ./
COPY templates/ templates/
COPY pdf_templates/ pdf_templates/

CMD ["python", "-u", "server.py"]
