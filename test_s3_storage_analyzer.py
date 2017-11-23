"""
Test indeed
"""
import boto3
from pprint import pprint
from datetime import datetime
from io import StringIO
import sys
from contextlib import redirect_stdout
from s3_storage_analyser import _get_s3_client, _list_buckets, _format_buckets, _analyse_bucket
from s3_storage_analyser import convert_bytes, traverse_bucket, fetch_bucket_info
from s3_storage_analyser import main, list_metrics, get_metrics_data
from moto import mock_s3, mock_cloudwatch

def test_convert_bytes():
    """Test convert bytes to a unit"""
    assert convert_bytes(1048576, 'MB', True) == '1MB'
    assert convert_bytes(1048576, 'KB', True) == '1024KB'
    assert convert_bytes(1073741824, 'GB') == '1'

def _put_metric(bucket_name, metric_name, storage_type, value, unit):
    clientcw = boto3.client('cloudwatch')
    clientcw.put_metric_data(Namespace='AWS/S3', MetricData=[{
        'MetricName': metric_name,
        'Dimensions': [
            {
                'Name': 'StorageType',
                'Value': storage_type,
            },
            {
                'Name': 'BucketName',
                'Value': bucket_name
            },
        ],
        'Timestamp': datetime.now(),
        'Value': value,
        'StatisticValues': {
            'SampleCount': value,
            'Sum': value,
            'Minimum': value,
            'Maximum': value
        },
        'Unit': unit
    }])

def _setup():
    client = _get_s3_client()
    name = 'hm.samples'
    client.create_bucket(Bucket=name)
    for i in range(0, 3):
        client.put_object(Bucket=name, Body=b'abcdef', Key=f'{i}.txt')
    client.put_object(Bucket=name, Body=b'abcdef', Key='sub/4.txt')
    for storage_type in ['StandardStorage', 'AllStorageTypes']:
        _put_metric(name, 'BucketSizeBytes', storage_type, 24.0, 'Bytes')
        _put_metric(name, 'NumberOfObjects', storage_type, 4.0, 'Count')

@mock_cloudwatch
@mock_s3
def test_get_metrics():
    """Test get the metrics"""
    _setup()
    metrics = list_metrics()
    pprint(metrics)
    assert len(metrics) == 4
    pprint(get_metrics_data(metrics))

@mock_cloudwatch
@mock_s3
def test_traverse_bucket():
    """Traverse bucket. single internal call"""
    _setup()
    bucket_descr = _analyse_bucket({'Name': 'hm.samples', '_prefix': None})
    assert bucket_descr['TotalFiles'] == 4
    assert bucket_descr['TotalSize'] == 24

@mock_cloudwatch
@mock_s3
def test_traverse_bucket_prefix():
    """Traverse bucket. prefix to select a single file"""
    _setup()
    bucket_descr = traverse_bucket('hm.samples', prefix='s3://hm.samples/1.txt')
    assert bucket_descr['TotalFiles'] == 1
    assert bucket_descr['TotalSize'] == 6

@mock_cloudwatch
@mock_s3
def test_traverse_bucket_2():
    """Traverse bucket. multiple s3 calls as there are more resources than the max_keys"""
    _setup()
    bucket_descr = traverse_bucket('hm.samples', max_keys=2)
    assert bucket_descr['TotalFiles'] == 4
    assert bucket_descr['TotalSize'] == 24
    assert bucket_descr['StorageStats']['STANDARD']['TotalFiles'] == 4

@mock_cloudwatch
@mock_s3
def test_bucket_xinfo():
    """Test loading the extra info of a bucket"""
    client = _get_s3_client()
    client.create_bucket(Bucket='hm.samples.encrypted')
    client.put_bucket_encryption(
        Bucket='hm.samples.encrypted',
        ServerSideEncryptionConfiguration={
            'Rules': [
                {
                    'ApplyServerSideEncryptionByDefault': {
                        'SSEAlgorithm': 'AES256',
                        'KMSMasterKeyID': 'foo'
                    }
                },
            ]
        }
    )
    bucket_info = fetch_bucket_info({'Name':'hm.samples.encrypted'})
    assert bucket_info['Region'] == 'us-east-1'

@mock_cloudwatch
@mock_s3
def test_buckets_filter():
    """Test listing the buckets"""
    client = _get_s3_client()
    # map(lambda n: client.create_bucket(Bucket=n), ['aa', 'a', 'b']) # does not work. why?
    for name in ['c', 'a', 'aa']:
        client.create_bucket(Bucket=name)
    bucket_list = _list_buckets()
    assert len(bucket_list) == 3
    assert bucket_list[0]['Name'] == 'a'

    bucket_list = _list_buckets(prefix='s3://a')
    assert len(bucket_list) == 2

def test_format_buckets():
    """Format and tabulate the buckets"""
    buckets = [{
        'Name': 'hm.samples',
        'Region': 'us-east-1',
        'CreationDate': datetime.now(),
        'LastModified': datetime.now(),
        'TotalSize': 1048576, # 1MB
        'TotalFiles': 6
    }]
    formatted = _format_buckets(buckets)
    assert formatted['values'][0][0] == 'hm.samples'
    assert formatted['values'][0][4] == '1' # 1MB

def _call_main(args_str):
    sio = StringIO()
    with redirect_stdout(sio):
        old_sys_argv = sys.argv
        try:
            sys.argv = args_str.split()
            main()
        finally:
            sys.argv = old_sys_argv
    return sio.getvalue()

@mock_cloudwatch
@mock_s3
def test_main():
    """Test main call no prefix"""
    _setup()
    out = _call_main('s3_storage_analyser.py --unit KB')
    lines = out.splitlines()
    assert ' Size KB ' in lines[0]
    assert ' 0.02 ' in lines[1]

@mock_cloudwatch
@mock_s3
def test_main_prefix():
    """Test main call no prefix"""
    _setup()
    out = _call_main('s3_storage_analyser.py --unit KB --prefix s3://hm.samples --pool-size 4')
    lines = out.splitlines()
    assert ' Size KB ' in lines[0]
    assert ' 0.02 ' in lines[1]

@mock_cloudwatch
@mock_s3
def test_main_wrong_prefix():
    """Test main call no prefix"""
    _setup()
    try:
        _call_main('s3_storage_analyser.py --unit KB --prefix hm.samples')
    except ValueError as err:
        assert 'Invalid prefix' in err.__str__()
        return
    raise Exception('No ValueError was raised although the prefix was wrong')
