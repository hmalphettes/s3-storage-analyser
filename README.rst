.. image:: https://travis-ci.org/hmalphettes/s3-storage-analyser.svg?branch=master
    :target: https://travis-ci.org/hmalphettes/s3-storage-analyser
.. image:: https://codecov.io/gh/hmalphettes/s3-storage-analyser/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/hmalphettes/s3-storage-analyser
.. image:: https://images.microbadger.com/badges/version/hmalphettes/s3-storage-analyser.svg
    :target: https://hub.docker.com/r/hmalphettes/s3-storage-analyser

S3 Storage Analyser - WIP
=========================
A command line tool to display the objects stored in your AWS S3 account.

Requirements
-------------
python-3.x

Development
-----------
For now development install only.
::

    git clone --depth 1 https://github.com/hmalphettes/s3_storage_analyser
    cd s3_storage_analyser
    pip install -r requirements.txt

Usage - Command Line
--------------------
::

    hugues in ~/proj/springcleaning/s3-storage-analyser on master*
    ⚡ python s3_storage_analyser.py --unit TB --prefix s3://hm
    Bucket                Region          Created                    Last Modified                Size MB    Files
    hm.many01             ap-southeast-1  2017-11-18T08:13:58+00:00  2017-11-18T08:37:59+00:00       0.06    10000
    hm.many02             ap-southeast-1  2017-11-18T08:14:14+00:00  2017-11-18T08:50:51+00:00       0.06    10000
    hm.many03             ap-southeast-1  2017-11-18T08:14:25+00:00  2017-11-18T09:30:26+00:00       0.13    22001
    hm.samples            ap-southeast-1  2017-11-16T08:13:39+00:00  2017-11-16T08:47:39+00:00       2.15        4
    hm.samples.encrypted  ap-southeast-1  2017-11-16T08:15:17+00:00  2017-11-16T08:47:05+00:00       3.27        1
    hm.samples.eu-west1   eu-west-1       2017-11-18T08:12:38+00:00  2017-11-19T07:59:18+00:00       0.13        2
    hm.samples.versioned  ap-southeast-1  2017-11-16T08:16:19+00:00  0001-01-01T00:00:00+00:00       0           0

    Region            Buckets    Size MB    Files    Std MB    Std Files    RR MB    RR Files    IA MB    IA Files
    ap-southeast-1          6       5.67    42006      5.67        42006        0           0        0           0
    eu-west-1               1       0.13        2      0.13            2        0           0        0           0

Usage - Docker
--------------
::

    docker run --rm hmalphettes/s3-storage-analyser --unit KB

Note: if the machine where Docker is running is not configured with an appropriate IAM role to access S3, you can resort to pass the AWS credentials as environment variables:

::

    docker run -e AWS_ACCESS_KEY_ID=123 -e AWS_SECRET_ACCESS_KEY=456 --rm hmalphettes/s3-storage-analyser --unit KB

License
-------
Public domain.

Development notes: CI, CD
-------------------------
The CI is graciously operated by Travis: https://travis-ci.org/hmalphettes/s3-storage-analyser
and codecov: https://codecov.io/gh/hmalphettes/s3-storage-analyser

The docker image is graciously operated by Docker Hub on every commit and every tag: https://hub.docker.com/r/hmalphettes/s3-storage-analyser/

Integration testing
-------------------
The test integration is run from a VM on EC2. A Docker Hub webhook sends the event to the VM.
The corresponding docker image that was built is pulled and a the tool is run against a set of S3 buckets with 42k files.

The run logs are sent as a notification to a slack channel:

.. image:: https://github.com/hmalphettes/s3-storage-analyser/raw/master/onbuild-notification.jpg

The setup of such an infra is currently not automated. Some documentation here: https://github.com/hmalphettes/s3-storage-analyser/tree/master/integration

TODO: Commit the output into a github repository to monitor the state of the build as well as the evolution of the content of the buckets.
