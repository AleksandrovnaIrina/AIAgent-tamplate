FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py boolean_builder.py search.py fetch.py gauth.py sheets.py tg_channels.py tg_reader.py gmail.py tg_sender.py calendar_tool.py sourcing.py ./

CMD ["python", "-u", "server.py"]
