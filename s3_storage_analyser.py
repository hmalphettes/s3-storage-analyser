"""
S3 Storage Analysis Tool
"""

import argparse
import re
import multiprocessing as multi
from pprint import pprint
from operator import itemgetter
from datetime import datetime
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
    parser.add_argument('--pool-size', help='Number of parallel workers')
    return parser.parse_args()

STORAGE_TYPES = ['STANDARD', 'REDUCED_REDUNDANCY', 'GLACIER']
UNIT_DEFS = {'B': 1, 'KB':1024, 'MB':1024**2, 'GB':1024**3, 'TB':1024**4}
def convert_bytes(nbytes, unit='MB', append_unit=False):
    """Converts a number of bytes into a specific unit"""
    # Credit: https://stackoverflow.com/a/39284216/1273401
    formatted = ('%.2f' % (nbytes/UNIT_DEFS[unit])).rstrip('0').rstrip('.')
    return f'{formatted}{unit}' if append_unit else formatted

def _get_s3_client():
    """Return the s3 connection."""
    return boto3.client('s3')

def _list_buckets(prefix=None):
    """Return the list of buckets {'Name','CreationDate'} """
    client = _get_s3_client()
    resp = client.list_buckets(prefix=prefix)
    buckets = resp['Buckets']
    if prefix is not None:
        _m = re.match(r'^s3://([^\/]+).*$', prefix)
        if _m is not None:
            buckets = filter(lambda x: x['Name'].startswith(_m.group(1)), buckets)
        else:
            raise ValueError(f'Invalid prefix "{prefix}"; expected "s3://bucket_name[/blah]"')
    return sorted(buckets, key=itemgetter('Name'))

def fetch_bucket_info(bucket):
    """Fetches some extra info about the bucket {'Name':bucket_name}"""
    name = bucket['Name']
    bucket_location = _get_s3_client().get_bucket_location(Bucket=name)['LocationConstraint']
    bucket.update({'Region': bucket_location})
    return bucket

def _analyse_bucket(bucket):
    bucket = fetch_bucket_info(bucket)
    # The prefix was passed to the bucket object to survive multiprocessing
    # TODO: find a cleaner way so that prefix is not None
    prefix = bucket.pop('_prefix')
    fetch_bucket_info(bucket)
    stats = traverse_bucket(bucket['Name'], prefix=prefix)
    bucket.update(stats)
    return bucket

def _analyse_buckets(prefix=None, pool_size=None):
    """Traverse all the buckets and collect the info"""
    buckets = _list_buckets(prefix=prefix)
    # Pass the prefix arguments to the workers.
    # TODO: find a cleaner way.
    for bucket in buckets:
        bucket['_prefix'] = prefix

    if pool_size is None:
        # TODO: should we use more workers than we have cpus?
        pool_size = multi.cpu_count()
    pool = multi.Pool(pool_size)

    buckets = list(pool.map(_analyse_bucket, buckets))

    pool.close()
    return buckets

def _extract_prefix_arg(prefix):
    """Extract Prefix within a bucket from s3://bucket_name/prefix"""
    if prefix is None:
        return
    _m = re.match(r'^s3://[^\/]+/(.+)$', prefix)
    return None if _m is None else _m.group(1)

def traverse_bucket(bucket, prefix=None, max_keys=None):
    """Paginates through the objects in the bucket
    keep track of the number of files; sum the size of each file"""
    total_bytes = 0
    total_files = 0
    last_modified = pytz.utc.localize(datetime.min)
    storage_type_stats = {}
    prefix = _extract_prefix_arg(prefix)
    for _type in STORAGE_TYPES:
        storage_type_stats[_type] = {
            'TotalSize': 0,
            'TotalFiles': 0
        }
    kwargs = {'Bucket': bucket}
    if prefix is not None:
        kwargs['Prefix'] = prefix
    if max_keys is not None:
        kwargs['MaxKeys'] = max_keys
    for obj in _list_objects(**kwargs):
        if obj['Size'] != 0:
            total_bytes += obj['Size']
            total_files += 1
            stats = storage_type_stats[obj['StorageClass']]
            stats['TotalSize'] += obj['Size']
            stats['TotalFiles'] += 1
            if obj['LastModified'] > last_modified:
                last_modified = obj['LastModified']
    return {
        'TotalSize': total_bytes,
        'TotalFiles': total_files,
        'LastModified': last_modified,
        'StorageStats': storage_type_stats
    }

def _list_objects(**kwargs):
    """Generator to iterate the objects found in a bucket.
    yield one object at a time
    bucket, prefix=None, max_keys=1000, Marker=None"""
    objects = _get_s3_client().list_objects_v2(**kwargs)
    if not 'Contents' in objects:
        return
    contents = objects['Contents']
    for content in contents:
        yield content

    if objects['IsTruncated'] is True:
        if 'ContinuationToken' in objects:
            kwargs['ContinuationToken'] = objects['NextContinuationToken']
        else:
            kwargs['StartAfter'] = contents[-1]['Key']
        for i in _list_objects(**kwargs):
            yield i

def _compute_aggregations(buckets):
    bystorage = {}
    byregion = {}
    for bucket in buckets:
        region = bucket['Region']
        if region not in byregion:
            byregion[region] = {
                'TotalSize': 0, 'TotalFiles':0,
                'Buckets': 0, 'StorageStats': {}}
        stats = byregion[region]
        stats['Buckets'] += 1
        stats['TotalSize'] += bucket['TotalSize']
        stats['TotalFiles'] += bucket['TotalFiles']
        for storage_type in STORAGE_TYPES:
            bucket_stats = bucket['StorageStats']
            if not storage_type in bucket_stats or bucket_stats[storage_type]['TotalFiles'] == 0:
                continue
            storage_stats = stats['StorageStats']
            if not storage_type in storage_stats:
                storage_stats[storage_type] = {'TotalSize': 0, 'TotalFiles':0}
            storage_stats[storage_type]['TotalSize'] += bucket_stats[storage_type]['TotalSize']
            storage_stats[storage_type]['TotalFiles'] += bucket_stats[storage_type]['TotalFiles']
            if not storage_type in bystorage:
                bystorage[storage_type] = {'TotalSize': 0, 'TotalFiles':0}
            storage_stats = bystorage[storage_type]
            storage_stats['TotalSize'] += bucket_stats[storage_type]['TotalSize']
            storage_stats['TotalFiles'] += bucket_stats[storage_type]['TotalFiles']
    return {'bystorage': bystorage, 'byregion': byregion}

def _format_bucket(bucket, unit='MB'):
    return [
        bucket['Name'],
        bucket['Region'],
        bucket['CreationDate'].isoformat('T', 'seconds'),
        bucket['LastModified'].isoformat('T', 'seconds'),
        convert_bytes(bucket['TotalSize'], unit),
        bucket['TotalFiles']
    ]

def _format_buckets(buckets, unit='MB'):
    """Format a list of buckets as dictionary into a list of arrays
    ready to be tabulated"""
    headers = [
        'Bucket',
        'Region',
        'Created',
        'Last Modified',
        f'Size {unit}',
        'Files'
    ]
    return {
        'headers': headers,
        'values': [_format_bucket(b, unit=unit) for b in buckets]
    }

def report(prefix=None, unit='MB', tablefmt='plain', pool_size=None):
    """Generate the tabulated report"""
    buckets = _analyse_buckets(prefix=prefix, pool_size=pool_size)
    formatted = _format_buckets(buckets, unit=unit)
    buckets_report = tabulate.tabulate(
        formatted['values'],
        headers=formatted['headers'],
        tablefmt=tablefmt)

    aggregations = _compute_aggregations(buckets)
    aggregations_formatted = []

    # prepare the values by region
    byregion = aggregations['byregion']
    aggregations_report = ''
    for region in byregion:
        region_formatted = []
        aggregations_formatted.append(region_formatted)
        region_formatted.append(region)
        values = byregion[region]
        region_formatted.append(values['Buckets'])
        region_formatted.append(convert_bytes(values['TotalSize'], unit))
        region_formatted.append(values['TotalFiles'])
        storage_values = values['StorageStats']
        for storage_type in STORAGE_TYPES:
            if not storage_type in storage_values:
                region_formatted.append(0)
                region_formatted.append(0)
            else:
                storage_val = storage_values[storage_type]
                region_formatted.append(convert_bytes(storage_val['TotalSize'], unit))
                region_formatted.append(storage_val['TotalFiles'])
    headers = ['Region', 'Buckets', f'Size {unit}', 'Files']
    for storage_type in ['Std', 'RR', 'IA']:
        headers.append(f'{storage_type} {unit}')
        headers.append(f'{storage_type} Files')
    aggregations_report = '\n\n' + tabulate.tabulate(
        aggregations_formatted,
        headers=headers,
        tablefmt=tablefmt)

    return f'{buckets_report}{aggregations_report}'

def main():
    """CLI entry point"""
    args = parse_args()
    print(report(prefix=args.prefix, unit=args.unit, pool_size=args.pool_size))

if __name__ == "__main__":
    main()
