"""
Test indeed
"""

from pprint import pprint
from datetime import datetime
from s3_storage_analyser import _get_s3_client, _list_buckets, _format_buckets
from s3_storage_analyser import convert_bytes, traverse_bucket, fetch_bucket_info
from s3_storage_analyser import report
from moto import mock_s3

def test_convert_bytes():
    """Test convert bytes to a unit"""
    assert convert_bytes(1048576, 'MB', True) == '1MB'
    assert convert_bytes(1048576, 'KB', True) == '1024KB'
    assert convert_bytes(1073741824, 'GB') == '1'

def _setup_s3():
    client = _get_s3_client()
    client.create_bucket(Bucket='hm.samples')
    for i in range(0, 3):
        client.put_object(Bucket='hm.samples', Body=b'abcdef', Key=f'{i}.txt')
    client.put_object(Bucket='hm.samples', Body=b'abcdef', Key='sub/4.txt')

@mock_s3
def test_traverse_bucket():
    """Traverse bucket. single internal call"""
    _setup_s3()
    bucket_descr = traverse_bucket('hm.samples')
    assert bucket_descr['TotalFiles'] == 4
    assert bucket_descr['TotalSize'] == 24

@mock_s3
def test_traverse_bucket_2():
    """Traverse bucket. multiple s3 calls as there are more resources than the max_keys"""
    _setup_s3()
    bucket_descr = traverse_bucket('hm.samples', max_keys=2)
    assert bucket_descr['TotalFiles'] == 4
    assert bucket_descr['TotalSize'] == 24
    assert bucket_descr['StorageStats']['STANDARD']['TotalFiles'] == 4

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
    assert bucket_info['bucket_location'] == 'us-east-1'

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
        'CreationDate': datetime.now(),
        'LastModified': datetime.now(),
        'TotalSize': 1048576,
        'TotalFiles': 6
    }]
    formatted = _format_buckets(buckets)
    pprint(formatted)

@mock_s3
def test_report():
    """Test the tabulated report"""
    _setup_s3()
    _report = report(unit='KB')
    lines = _report.splitlines()
    assert ' Total size KB ' in lines[0]
    assert ' 0.02 ' in lines[1]
