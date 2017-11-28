#!/bin/bash
docker rm --force s3analyser_endpoint &>/dev/null || true
docker run --name s3analyser_endpoint --net host \
  --restart=on-failure \
  -v /home/centos/s3analyserdata:/home/centos/s3analyserdata \
  -e PROM_TEXT=/home/centos/s3analyserdata/metrics.prom \
  -e S3_PROM_TEXT=/home/centos/s3analyserdata/metrics-s3.prom \
  -e TOKEN=1t1sas3cr3t \
  -d hmalphettes/s3-storage-analyser server