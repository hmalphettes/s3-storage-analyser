.. image:: https://travis-ci.org/hmalphettes/s3-storage-analyser.svg?branch=master
    :target: https://travis-ci.org/hmalphettes/s3-storage-analyser

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
    Name                  CreationDate               bucket_location      total_bytes    total_files  last_modified
    hm.many01             2017-11-18 08:13:58+00:00  ap-southeast-1             60000          10000  2017-11-18 08:37:59+00:00
    hm.many02             2017-11-18 08:14:14+00:00  ap-southeast-1             60000          10000  2017-11-18 08:50:51+00:00
    hm.many03             2017-11-18 08:14:25+00:00  ap-southeast-1            132006          22001  2017-11-18 09:30:26+00:00
    hm.samples            2017-11-16 08:13:39+00:00  ap-southeast-1           2259547              4  2017-11-16 08:47:39+00:00
    hm.samples.encrypted  2017-11-16 08:15:17+00:00  ap-southeast-1           3428897              1  2017-11-16 08:47:05+00:00
    hm.samples.eu-west1   2017-11-18 08:12:38+00:00  eu-west-1                 108160              1  2017-11-18 08:13:32+00:00
    hm.samples.versioned  2017-11-16 08:16:19+00:00  ap-southeast-1                 0              0  0001-01-01 00:00:00+00:00

License
-------
Public domain.