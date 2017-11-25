"""
Unit Tests
"""
from datetime import datetime
from io import StringIO
import sys
from pprint import pprint
from contextlib import redirect_stdout

from s3_storage_analyser import (
    list_buckets, fold_metrics_data, convert_bytes,
    main, list_metrics, get_metrics_data, _today)
import s3_storage_analyser

from moto import mock_s3, mock_cloudwatch
import boto3
import pytz
import pytest

def test_convert_bytes():
    """Test convert bytes to a unit"""
    assert convert_bytes(1048576, 'MB', True) == '1MB'
    assert convert_bytes(1048576, 'KB', True) == '1024KB'
    assert convert_bytes(1073741824, 'GB') == '1'

def _put_metric(bucket_name, metric_name, storage_type, value, unit):
    clientcw = boto3.client('cloudwatch', 'us-east-1')
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
    return {
        'Datapoints': [{
            'Average'  : value,
            'Timestamp': pytz.utc.localize(_today()),
            'Unit'     : unit
        }],
        'Label': metric_name,
        '_storage_type': storage_type
    }

def _setup(monkeypatch):
    s3_storage_analyser._stop_pool()
    client = boto3.client('s3')
    name = 'hm.samples'
    client.create_bucket(Bucket=name)
    for i in range(0, 3):
        client.put_object(Bucket=name, Body=b'abcdef', Key=f'{i}.txt')
    client.put_object(Bucket=name, Body=b'abcdef', Key='sub/4.txt')

    # mock the metrics data: moto does not yet support mocking get_metrics_data
    data_points = []
    for storage_type in ['StandardStorage', 'AllStorageTypes']:
        data_points.append(_put_metric(
            name, 'BucketSizeBytes', storage_type, 24.0, 'Bytes'))
    data_points.append(_put_metric(
        name, 'NumberOfObjects', 'AllStorageTypes', 4.0, 'Count'))

    def _mock_get_stats(**req):
        assert '_region' in req
        metric_type = req['MetricName']
        storage_type = req['Dimensions'][0]['Value']
        for index, elem in enumerate(data_points):
            if elem['Label'] == metric_type and elem['_storage_type'] == storage_type:
                return data_points.pop(index)
        raise ValueError('Unable to find the appropriate mock datapoint')
    monkeypatch.setattr(s3_storage_analyser, '_get_metric_statistics', _mock_get_stats)

@mock_cloudwatch
@mock_s3
def test_buckets_filter():
    """Test listing the buckets"""
    client = boto3.client('s3')
    for name in ['c', 'a', 'aa']:
        client.create_bucket(Bucket=name)
    bucket_list = list_buckets()
    assert len(bucket_list) == 3
    assert bucket_list[0]['Name'] == 'a'
    assert bucket_list[0]['Region'] == 'us-east-1'
    assert bucket_list[0]['CreationDate'] is not None

    bucket_list = list_buckets(prefix='s3://a')
    assert len(bucket_list) == 2

@mock_cloudwatch
@mock_s3
def test_get_metrics(monkeypatch):
    """Test get the metrics"""
    _setup(monkeypatch)
    # improve the coverage: test without pool as the coverage pool ignores the workers
    s3_storage_analyser._POOL_SIZE[0] = 1
    buckets = list_buckets()
    metrics = list_metrics(buckets)
    assert len(metrics) == 3
    assert metrics[0]['_region'] == 'us-east-1'
    s3_storage_analyser._POOL_SIZE[0] = None

@mock_cloudwatch
@mock_s3
def test_get_metrics_data(monkeypatch):
    """Check the sanity of the shape of the datapoint"""
    _setup(monkeypatch)
    buckets = list_buckets()
    metrics = list_metrics(buckets)
    data = get_metrics_data(metrics, buckets)
    assert len(data) == 3
    for prop in ['BucketName', 'CreationDate', 'Name', 'Region', 'StorageType', 'Value']:
        for datapoint in data:
            assert prop in datapoint
    assert data[0]['BucketName'] == 'hm.samples'
    assert data[0]['Region'] == 'us-east-1'

@mock_cloudwatch
@mock_s3
# @pytest.mark.skip(reason="moto does not support get_metric_statistics")
def test_fold_metrics_data(monkeypatch):
    """Test folding the datapoints"""
    _setup(monkeypatch)
    buckets = list_buckets()
    metrics = list_metrics(buckets)
    datapoints = get_metrics_data(metrics, buckets)
    folded = fold_metrics_data(datapoints)
    for index_type in ['bybucket', 'byregion']:
        index = folded[index_type]
        assert len(index.keys()) == 1
        key, value = index.popitem()
        if index_type == 'bybucket':
            assert key == 'hm.samples'
            assert value['Bucket'] == 'hm.samples'
        else:
            assert key == 'us-east-1'
            assert value['Buckets'] == 1
        assert value['Region'] == 'us-east-1'
        assert value['Files'] == 4
        assert value['Bytes'] == 24.0
        assert value['Bytes-ST'] == 24.0
        assert value['Bytes-RR'] == 0
        assert value['Bytes-IA'] == 0

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
def test_main(monkeypatch):
    """Test main call no prefix"""
    _setup(monkeypatch)
    out = _call_main('s3_storage_analyser.py --unit KB')
    lines = out.splitlines()
    assert ' Total(KB) ' in lines[0]
    assert ' 0.02 ' in lines[1]

@mock_cloudwatch
@mock_s3
def test_main_tab(monkeypatch):
    """Test main call tab format"""
    _setup(monkeypatch)
    out = _call_main('s3_storage_analyser.py --unit KB --fmt tab')
    lines = out.splitlines()
    assert '\tTotal(KB)\t' in lines[0]
    assert '\t0.02\t' in lines[1]

@mock_cloudwatch
@mock_s3
def test_main_json(monkeypatch):
    """Test main call json format"""
    _setup(monkeypatch)
    out = _call_main('s3_storage_analyser.py --unit KB --fmt json')
    assert out.startswith('{"Buckets": [{"Bucket": "hm.samples"')
    assert len(out.splitlines()) == 1

@mock_cloudwatch
@mock_s3
def test_main_json_pretty(monkeypatch):
    """Test main call pretty json format"""
    _setup(monkeypatch)
    out = _call_main('s3_storage_analyser.py --unit KB --fmt json_pretty')
    assert len(out.splitlines()) > 10

@mock_cloudwatch
@mock_s3
@pytest.mark.skip(reason="not ready yet")
def test_main_prefix(monkeypatch):
    """Test main call with prefix"""
    _setup(monkeypatch)
    out = _call_main('s3_storage_analyser.py --unit KB --prefix s3://hm.samples --pool-size 4')
    lines = out.splitlines()
    assert ' Size KB ' in lines[0]
    assert ' 0.02 ' in lines[1]

@mock_cloudwatch
@mock_s3
@pytest.mark.skip(reason="not ready yet")
def test_main_wrong_prefix(monkeypatch):
    """Test main call wrong prefix"""
    _setup(monkeypatch)
    try:
        _call_main('s3_storage_analyser.py --unit KB --prefix hm.samples')
    except ValueError as err:
        assert 'Invalid prefix' in err.__str__()
        return
    raise Exception('No ValueError was raised although the prefix was wrong')
