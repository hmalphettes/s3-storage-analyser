FROM python:3-slim

COPY requirements.txt /tmp/
RUN pip install --requirement /tmp/requirements.txt && \
    pip install pytz s3cmd
COPY *.py /app/
WORKDIR /app
ENTRYPOINT [ "python3", "/app/s3_storage_analyser.py" ]
CMD [ "--help" ]