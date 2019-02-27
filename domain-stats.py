#!/usr/bin/env python

import json
import logging
import os
import re
import time

import requests
from influxdb import InfluxDBClient

logger = logging.getLogger("domain_stats")


class DomainRequester:
    def __init__(self, hostname, cookies=None):
        self.hostname = hostname
        self.cookies = cookies or {}

    def get(self, path):
        base_url = 'http://%s:40100' % self.hostname
        path = re.sub(r'^/+', '', path)
        url = '/'.join((base_url, path))
        response = requests.get(url, cookies=self.cookies)
        return response.json()

    def __call__(self, path):
        return self.get(path)


def clean_measurement(measurement):
    measurement = measurement.replace(' ', '-')

    if not measurement.startswith('z_'):
        return {}, measurement

    val = measurement.split('.')
    if val[0] not in ('z_avatars', 'z_listeners'):
        return {}, measurement

    return {'uuid': val.pop(1)}, '.'.join(val)


def clean_val(val):
    try:
        return float(val)
    except ValueError:
        m = re.match(r'^(\d+) \w+$', val) # like: 0 usecs
        if m:
            val = m.groups()[0]
            return float(m.groups()[0])
        raise


def flatten(key, val):
    if isinstance(val, dict):
        for k, v in val.items():
            k = '.'.join((key, k)) if key else k
            for _ in flatten(key=k, val=v):
                yield _
    else:
        if val is not None:
            try:
                # InfluxDB is strongly typed and tries to guess types.
                # If you add a new measure measurement as 0 it will
                # guess it's an int, but when you later add 0.1234 it
                # will explode because it can't handle a float. So, just
                # assume everything is a float. This means string won't
                # work, but InfluxDB doesn't like strings anyway.
                val = clean_val(val)
            except (TypeError, ValueError) as exc:
                logger.warn("couldn't clean value for %s: %s", key, val)
            else:
                yield (key, val)


def get_stats(request, domain_name):
    nodes = {n['type']: n for n in request('nodes.json')['nodes']}
    for k in ('audio-mixer', 'avatar-mixer'):
        d = request('nodes/%s.json' % nodes[k]['uuid'])
        for measurement, value in flatten('', d):
            yield measurement, value, {'domain_name': domain_name,
                                       'assignment': k}


def write_stats(request, client_kwargs):
    client = InfluxDBClient(**client_kwargs)
    client.create_database(client_kwargs['database'])

    stats = get_stats(request, domain_name)
    body = []
    for measurement, value, tags in stats:
        _tags, measurement = clean_measurement(measurement)
        tags.update(_tags)
        point = {
            'measurement': measurement,
            'tags': tags,
            'fields': {
                'value': value,
            }
        }
        logger.debug(point)
        body.append(point)

    try:
        client.write_points(body)
    except Exception as exc:
        logger.exception("couldn't write points")
    else:
        logger.info("wrote %d points" % len(body))


if __name__ == '__main__':

    FORMAT = '%(asctime)-15s %(message)s'
    logging.basicConfig(format=FORMAT, level=logging.INFO)
    logger.info("starting")

    domain_name = os.environ.get('HIFI_DOMAIN_NAME')
    sleep_interval = int(os.environ.get('HIFI_SLEEP_INTERVAL', 3))
    ds_web_session_uuid = os.environ.get('HIFI_DS_WEB_SESSION_UUID')
    client_kwargs = {
        'host': os.environ.get('HIFI_INFLUX_HOST', 'localhost'),
        'port': int(os.environ.get('HIFI_INFLUX_PORT', '8086')),
        'username': os.environ.get('HIFI_INFLUX_USERNAME'),
        'password': os.environ.get('HIFI_INFLUX_PASSWORD'),
        'database': os.environ.get('HIFI_INFLUX_DATABASE', 'domain_stats'),
    }

    if client_kwargs:
        if not client_kwargs['username']:
            del client_kwargs['username']
        if not client_kwargs['password']:
            del client_kwargs['password']

    logger.debug("creating request")
    request = DomainRequester(
        '%s.highfidelity.io' % domain_name,
        cookies={'DS_WEB_SESSION_UUID': ds_web_session_uuid},
    )
    logger.debug("created request")

    while 1:
        logger.debug("starting loop")
        ts = time.time()
        try:
            logger.debug("write stats")
            write_stats(request, client_kwargs)
        except Exception as exp:
            logger.exception("couldn't write stats")
        sleep_for = sleep_interval - (time.time() - ts)
        logger.info("sleeping for %.02f secs" % sleep_for)
        time.sleep(max(sleep_for, 0))
