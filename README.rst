.. image:: https://travis-ci.org/hmalphettes/s3-storage-analyser.svg?branch=master
    :target: https://travis-ci.org/hmalphettes/s3-storage-analyser
.. image:: https://codecov.io/gh/hmalphettes/s3-storage-analyser/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/hmalphettes/s3-storage-analyser
.. image:: https://images.microbadger.com/badges/version/hmalphettes/s3-storage-analyser.svg
    :target: https://hub.docker.com/r/hmalphettes/s3-storage-analyser

S3 Storage Analyser
===================
A command line tool to display the objects stored in your AWS S3 account.

WIP: Prometheus client
======================
Expose the numbers as metrics for Prometheus

Strategy: Use Cloudwatch metrics
================================
+-------------------------------------------------+-------------------------------------------------+-------------------------------------------------------+
| Strategy                                        | Performance                                     | Drawbacks                                             |
+=================================================+=================================================+=======================================================+
| S3 API get_objects_list_v2                      | O(n) where n is the number of objects           | Slow                                                  |
+-------------------------------------------------+-------------------------------------------------+-------------------------------------------------------+
| Cloudwatch get_metrics and get_metrics_stats    | O(N) where N is the number of buckets           | No LastModified, no path filtering, not realtime      |
+-------------------------------------------------+-------------------------------------------------+-------------------------------------------------------+
| S3 Inventory                                    | As good as the DB where the inventory is stored | Setup and pay for each bucket. Maintain a DB and ETL. |
+-------------------------------------------------+-------------------------------------------------+-------------------------------------------------------+

As a starting point this implementation uses the Cloudwatch metrics.

Development
-----------
Requirement: python3

::

    git clone --depth 1 https://github.com/hmalphettes/s3_storage_analyser
    cd s3_storage_analyser
    pip install -r requirements.txt

Usage - Command Line
--------------------
::

    python3 -m s3_storage_analyser
    Bucket                Region            Files    Total(MB)    STD(MB)    RR(MB)    IA(MB)  Creation(UTC)
    hm.many02             ap-southeast-1    10000         0.19       0.19         0         0  2017-11-18T08:14:15
    hm.many01             ap-southeast-1    10000         0.19       0.19         0         0  2017-11-18T08:13:58
    hm.many03             ap-southeast-1    22001         0.42       0.42         0         0  2017-11-18T08:14:25
    hm.samples            ap-southeast-1        4         2.16       2.16         0         0  2017-11-16T08:13:39
    hm.samples.encrypted  ap-southeast-1        1         3.27       3.27         0         0  2017-11-16T08:15:17
    hm.samples.eu-west1   eu-west-1             3         0.13       0.13         0         0  2017-11-18T08:12:38

Note that currently only the buckets owned by the AWS account configured are analysed.

Performance
-----------
The requests to S3 are parallelised for each bucket up to the number of workers in the pool.
The requests to Cloudwatch are parallelised per region and then per metric requests.

That number of workers is defined by the parameter `--conc`.

It defaults to the number of CPUs available on the machine.

Even on a AWS t2.micro instance which uses a single CPU, a pool of 6 workers is reasonable.

Usage - Docker
--------------
::

    docker run --rm hmalphettes/s3-storage-analyser --unit KB --prefix "hm.many*"

Note: if the machine where Docker is running is not configured with an appropriate IAM role to access S3, you can resort to pass the AWS credentials as environment variables:

::

    docker run -e AWS_ACCESS_KEY_ID=123 -e AWS_SECRET_ACCESS_KEY=456 --rm hmalphettes/s3-storage-analyser --unit KB

Usage - REST
------------
The docker container is deployed on 'http://s3analyser.huguesm.name'
Please do request the token parameter to access the API.

::

    curl -s "https://s3analyser.huguesm.name/?token=$_TOKEN&fmt=tsv" | column -t
    Bucket                Region          Files    Total(MB)  STD(MB)  RR(MB)  IA(MB)  Creation(UTC)
    hm.samples.eu-west1   eu-west-1       3.0      0          0.13     0       0       2017-11-18T08:12:38
    hm.many02             ap-southeast-1  10000.0  0          0.19     0       0       2017-11-18T08:14:13
    hm.many01             ap-southeast-1  10000.0  0          0.19     0       0       2017-11-18T08:13:58
    hm.many03             ap-southeast-1  22001.0  0          0.42     0       0       2017-11-18T08:14:25
    hm.samples            ap-southeast-1  4.0      0          2.16     0       0       2017-11-16T08:13:39
    hm.samples.encrypted  ap-southeast-1  1.0      0          3.27     0       0       2017-11-16T08:15:16

::

    curl -s "https://s3analyser.huguesm.name/?token=$_TOKEN&fmt=json" | jq .
    {
    "Buckets": [
        {
        "Bucket": "hm.samples.eu-west1",
        "Bytes": 0,
        "Bytes-IA": 0,
        "Bytes-RR": 0,
        "Bytes-ST": 133656,
        "CreationDate": "2017-11-18T08:12:38",
        "Files": 3,
        "Region": "eu-west-1"
        },
    ...

To run the REST endpoint for development:

::

    TOKEN=secret python3 -m server

Via docker:

::

    docker run -e TOKEN=secret --name s3analyser_endpoint --net host -d hmalphettes/s3-storage-analyser server

Continuous Integration - Continuous Delivery
--------------------------------------------
The CI is graciously operated by Travis: https://travis-ci.org/hmalphettes/s3-storage-analyser
and codecov: https://codecov.io/gh/hmalphettes/s3-storage-analyser

The docker image is graciously operated by Docker Hub on every commit and every tag: https://hub.docker.com/r/hmalphettes/s3-storage-analyser/

Integration testing
-------------------
The test integration is run on a VM on AWS EC2. A Docker Hub webhook sends the event to the VM.
The corresponding docker image that was built is pulled and the tool is run against a set of S3 buckets with 42k files.

The run logs are sent as a notification to a slack channel:

.. image:: https://github.com/hmalphettes/s3-storage-analyser/raw/master/onbuild-notification.jpg

The setup of such an infra is currently not automated. Some documentation here: https://github.com/hmalphettes/s3-storage-analyser/tree/master/integration

TODO: Commit the output into a github repository to monitor the state of the build as well as the evolution of the content of the buckets.

Next steps
----------
- Support for prefix or at least bucket glob/list
- Enrich the statistics displayed
- Prometheus exporter

License
-------
Public domain.

