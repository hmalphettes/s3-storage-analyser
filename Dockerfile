FROM python:3-slim

COPY requirements.txt /tmp/
RUN pip install --requirement /tmp/requirements.txt && \
    pip install pytz s3cmd
COPY *.py /app/
WORKDIR /app
USER nobody
ENTRYPOINT [ "python3", "s3_storage_analyser.py" ]
