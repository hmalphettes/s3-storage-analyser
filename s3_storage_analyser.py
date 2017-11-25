"""
S3 Storage Analysis Tool
"""

import argparse
import re
import json
import multiprocessing as multi
# from pprint import pprint
from operator import itemgetter
from datetime import datetime, timedelta, time
import pytz
import boto3
import tabulate

def parse_args():
    """cli parser"""
    parser = argparse.ArgumentParser(description='Analyse the S3 Buckets of an Amazon AWS account.')
    parser.add_argument('--unit', # type='string',
                        choices=['B', 'KB', 'MB', 'GB', 'TB'],
                        help='file size unit B|KB|MB|GB|TB', default='MB')
    parser.add_argument('--prefix', help='Filter the keys by prefix')
    parser.add_argument('--conc', type=int, help='Number of parallel workers')
    parser.add_argument(
        '--fmt', # type='string',
        choices=['json_pretty', 'json', 'tab', 'plain', 'simple', 'grid',
                 'pipe', 'orgtbl', 'rst', 'mediawiki', 'latex'],
        help='report format json|plain|simple|grid|pipe|orgtbl|rst|mediawiki|latex',
        default='plain')
    return parser.parse_args()

STORAGE_TYPES = ['STANDARD', 'REDUCED_REDUNDANCY', 'GLACIER']
UNIT_DEFS = {'B': 1, 'KB':1024, 'MB':1024**2, 'GB':1024**3, 'TB':1024**4}
def convert_bytes(nbytes, unit='MB', append_unit=False):
    """Converts a number of bytes into a specific unit"""
    # Credit: https://stackoverflow.com/a/39284216/1273401
    formatted = ('%.2f' % (nbytes/UNIT_DEFS[unit])).rstrip('0').rstrip('.')
    return f'{formatted}{unit}' if append_unit else formatted

_POOL_SIZE = [None]
__POOL = [None]
def _conc_map(fct, iterable):
    if __POOL[0] is not None:
        return __POOL[0].map(fct, iterable)
    if _POOL_SIZE[0] is None: # TODO: should we use more workers than we have cpus?
        _POOL_SIZE[0] = multi.cpu_count()
    if _POOL_SIZE[0] <= 1:
        return map(fct, iterable)
    pool = multi.Pool(_POOL_SIZE[0])
    __POOL[0] = pool
    return pool.map(fct, iterable)

def _stop_pool():
    if __POOL[0] is not None:
        __POOL[0].close()
        __POOL[0] = None

def list_buckets(prefix=None):
    """Return the list of buckets {'Name','CreationDate'} """
    resp = boto3.client('s3').list_buckets(prefix=prefix)
    buckets = resp['Buckets']
    if prefix is not None:
        _m = re.match(r'^s3://([^\/]+).*$', prefix)
        if _m is not None:
            buckets = filter(lambda x: x['Name'].startswith(_m.group(1)), buckets)
        else:
            raise ValueError(f'Invalid prefix "{prefix}"; expected "s3://bucket_name[/blah]"')
    buckets = list(_conc_map(fetch_bucket_info, buckets))
    return sorted(buckets, key=itemgetter('Name'))

def _get_bucket_name(metric):
    for dimension in metric['Dimensions']:
        if dimension['Name'] == 'BucketName':
            return dimension['Value']

def list_metrics(buckets, prefix=None):
    """Return the list of buckets {'Name','CreationDate','Region'}"""
    regions = set()
    for bucket in buckets:
        regions.add(bucket['Region'])
    kwargs_list = [{
        'prefix': prefix,
        'region': region
    } for region in regions]
    return sum(_conc_map(_list_regional_metrics, kwargs_list), [])

def _list_regional_metrics(params):
    """ return the list of S3 metrics for a given region """
    region = params['region']
    prefix = params['prefix']
    kwargs = {'Namespace': 'AWS/S3', '_region': region}
    if prefix is not None:
        kwargs['Prefix'] = prefix
    metrics = []
    for metric in _list_metrics(**kwargs):
        # skip the buckets we are not interested in
        bucket_name = _get_bucket_name(metric)
        if prefix != None and bucket_name != prefix:
            continue
        # pass the region for the next cloudwatch API call
        metric['_region'] = region
        metrics.append(metric)
    return metrics

def _get_cw_client(region):
    assert region is not None
    return boto3.client('cloudwatch', region_name=region)

def _list_metrics(**kwargs):
    """Generator to iterate the metrics found in a bucket. yield one metric at a time"""
    region = kwargs.pop('_region')
    res = _get_cw_client(region).list_metrics(**kwargs)

    metrics = res['Metrics']
    for metric in metrics:
        yield metric

    # The moto library has some issue returning a strange next token
    # when there should be none
    if 'NextToken' in res and not res['NextToken'].startswith('\n '):
        kwargs['NextToken'] = res['NextToken'].strip()
        kwargs['_region'] = region
        for i in _list_metrics(**kwargs):
            yield i

def get_metrics_data(metrics, buckets):
    """Fetches the datapoints of the corresponding metrics"""
    regions_bybucket = {}
    for bucket in buckets:
        regions_bybucket[bucket['Name']] = bucket['Region']
    pending_requests = []
    for metric in metrics:
        metric_name = metric['MetricName']
        if metric_name == 'NumberOfObjects':
            pending_requests.append(_make_req(metric, 'Count', regions_bybucket))
        elif metric_name == 'BucketSizeBytes':
            pending_requests.append(_make_req(metric, 'Bytes', regions_bybucket))
    if pending_requests:
        return _run_requests(pending_requests, buckets)

def _today():
    return datetime.combine(datetime.utcnow().date(), time.min)

def _make_req(metric, unit, regions_bybucket):
    # Add the region to the dictionary.
    # The dictionary is executed by a python pool of processes,
    # passing the region directly on the dictionary
    # is a simple way to pass the info to the forked python process
    bucket_name = _get_bucket_name(metric)
    region = regions_bybucket[bucket_name]
    assert region is not None
    today = _today()
    return {
        'Namespace': metric['Namespace'],
        'MetricName': metric['MetricName'],
        'Dimensions': metric['Dimensions'],
        'Statistics': [
            # http://docs.aws.amazon.com/AmazonS3/latest/dev/cloudwatch-monitoring.html#s3-cloudwatch-metrics
            'Average'
        ],
        # http://docs.aws.amazon.com/AmazonS3/latest/dev/cloudwatch-monitoring.html#cloudwatch-monitoring-accessing
        'StartTime': today - timedelta(days=1),
        'EndTime': today,
        'Period': 86400, # 1 day
        'Unit': unit,
        '_region': region
    }

def _run_requests(reqs, buckets):
    """Exectutes the requests"""
    data = list(_conc_map(get_metric, reqs))
    _add_bucket_info(data, buckets)
    return data

def get_metric(req):
    """Fetch the data for a metric"""
    resp = _get_metric_statistics(**req)
    if resp['Datapoints']:
        average = resp['Datapoints'][0]['Average']
        for dimension in req['Dimensions']:
            if dimension['Name'] == 'BucketName':
                bucket_name = dimension['Value']
            elif dimension['Name'] == 'StorageType':
                storage_type = dimension['Value']
        return {
            'MetricName': req['MetricName'],
            'BucketName': bucket_name,
            'StorageType': storage_type,
            'Value': average
        }

def _get_metric_statistics(**kwargs):
    """Call boto3.get_metric_statistics
    Isolated for testing purposes as moto does not support this method yet"""
    region = kwargs.pop('_region')
    res = _get_cw_client(region).get_metric_statistics(**kwargs)
    return res

def _add_bucket_info(datapoints, buckets):
    """Adds the region, creation date"""
    buckets_indexed = {}
    for bucket in buckets:
        buckets_indexed[bucket['Name']] = bucket
    for datapoint in datapoints:
        bucket = buckets_indexed[datapoint['BucketName']]
        datapoint.update(bucket)

def fetch_bucket_info(bucket):
    """Fetches some extra info about the bucket: adds the region"""
    name = bucket['Name']
    try:
        bucket_location = boto3.client('s3').get_bucket_location(Bucket=name)['LocationConstraint']
        bucket.update({'Region': bucket_location})
        return bucket
    except Exception as err:
        msg = err.__str__()
        raise ValueError(f'{name} {msg}')

FOLDED_KEYS = {
    # MetricName-StorageType -> Folded column name
    'NumberOfObjects:AllStorageTypes': 'Files',
    'BucketSizeBytes:AllStorageTypes': 'Bytes',
    'BucketSizeBytes:StandardStorage': 'Bytes-ST',
    'BucketSizeBytes:StandardIAStorage': 'Bytes-IA',
    'BucketSizeBytes:ReducedRedundancyStorage': 'Bytes-RR'
}

def fold_metrics_data(metrics_data):
    """Fold the datapoints into rows with multiple dimension values
    Prepare row by buckets; aggregates rows per regions and per storage"""
    bystorage = {}
    byregion = {}
    bybucket = {}
    # Folds some column
    for data in metrics_data:
        region = data['Region']
        if region not in byregion:
            byregion[region] = {
                'Buckets': 0,
                'Region': region,
                'Files': 0,
                'Bytes': 0,
                'Bytes-ST': 0,
                'Bytes-RR': 0,
                'Bytes-IA':0
            }

        bucket = data['BucketName']
        if bucket not in bybucket:
            bybucket[bucket] = {
                'Bucket': bucket,
                'Region': region,
                'Files': 0,
                'Bytes': 0,
                'Bytes-ST': 0,
                'Bytes-RR': 0,
                'Bytes-IA':0,
                'CreationDate': pytz.utc.localize(datetime.min)
            }

        storage = data['StorageType']
        if storage not in bystorage:
            bystorage[storage] = {'Files': 0, 'Bytes': 0}

        metric_name = data['MetricName']

        key = FOLDED_KEYS[f'{metric_name}:{storage}']
        byregion[region][key] += data['Value']
        bybucket[bucket][key] += data['Value']
        if metric_name == 'NumberOfObjects':
            byregion[region]['Buckets'] += 1
            bybucket[bucket]['CreationDate'] = data['CreationDate']

        key = 'Files' if metric_name == 'NumberOfObjects' else 'Bytes'
        bystorage[storage][key] += data['Value']

    # world = {
    #     'Regions': len(byregion.keys()),
    #     'Files': sum(map(attrgetter('Files'), byregion.values())),
    #     # 'Files-ST': bystorage[''],
    #     # 'Files-RR': sum(byregion['Files-RR'].values()),
    #     # 'Files-IA': sum(byregion['Files-IA'].values())
    #     'Bytes': sum(map(attrgetter('Bytes'), byregion.values())),
    #     'Bytes-ST': sum(map(attrgetter('Bytes-ST'), byregion.values())),
    #     'Bytes-RR': sum(map(attrgetter('Bytes-RR'), byregion.values())),
    #     'Bytes-IA': sum(map(attrgetter('Bytes-IA'), byregion.values()))
    # }

    return {
        'bybucket': bybucket,
        'byregion': byregion,
        'bystorage': bystorage,
        # 'world': world
    }

def _format_buckets(buckets_data, unit='MB'):
    """Formate the buckets for the tabulate library"""
    headers = [
        'Bucket',
        'Region',
        'Files',
        f'Total({unit})',
        f'STD({unit})',
        f'RR({unit})',
        f'IA({unit})',
        'Creation(UTC)'
    ]
    rows = []
    for data in buckets_data:
        rows.append([
            data['Bucket'],
            data['Region'],
            data['Files'],
            convert_bytes(data['Bytes'], unit),
            convert_bytes(data['Bytes-ST'], unit),
            convert_bytes(data['Bytes-RR'], unit),
            convert_bytes(data['Bytes-IA'], unit),
            data['CreationDate'].replace(tzinfo=None).isoformat('T', 'seconds')
        ])
    return headers, rows

def _json_dumps(buckets_data, pretty=False):
    for data in buckets_data.values():
        data['CreationDate'] = data['CreationDate'].replace(tzinfo=None).isoformat('T', 'seconds')
    res = {'Buckets': list(buckets_data.values())}
    return json.dumps(res, sort_keys=True, indent=4 if pretty else None)

def report(prefix=None, unit='MB', conc=None, fmt='plain'):
    """Generates a formatted report"""
    if conc is not None:
        _POOL_SIZE[0] = conc
    buckets = list_buckets(prefix=prefix)
    metrics = list_metrics(buckets, prefix=prefix)
    metrics_data = get_metrics_data(metrics, buckets)
    # pprint(metrics_data)
    folded = fold_metrics_data(metrics_data)
    if fmt == 'json' or fmt == 'json_pretty':
        return _json_dumps(folded['bybucket'], pretty=True if fmt == 'json_pretty' else False)
    headers, rows = _format_buckets(folded['bybucket'].values(), unit=unit)
    if fmt == 'tab':
        lines = ['\t'.join(str(x) for x in row) for row in rows]
        return '\t'.join(headers) + '\n' + '\n'.join(lines)
    tabulated = tabulate.tabulate(rows, headers=headers, tablefmt=fmt)
    return tabulated

def main():
    """CLI entry point"""
    args = parse_args()
    rep = report(
        prefix=args.prefix,
        unit=args.unit,
        conc=args.conc,
        fmt=args.fmt
    )
    print(rep)


if __name__ == "__main__":
    main()
