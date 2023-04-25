import psutil
import time
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

def monitor_new_processes(ignore_list=None):
    if ignore_list is None:
        ignore_list = []

    seen_pids = set()
    while True:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time', 'username']):
            if proc.pid not in seen_pids:
                if proc.info['name'] not in ignore_list:
                    process_info = collect_process_info(proc)
                    write_process_data_to_influxdb(process_info)
                    print(f"New process: {process_info}")

                    try:
                        parent = proc.parent()
                        if parent and parent.pid not in seen_pids:
                            parent_info = collect_process_info(parent)
                            write_process_data_to_influxdb(parent_info)
                            print(f"New parent process: {parent_info}")
                    except psutil.NoSuchProcess:
                        pass

                seen_pids.add(proc.pid)

        time.sleep(60)


def collect_process_info(proc):
    return {
        'pid': proc.pid,
        'name': proc.info['name'],
        'cmdline': ' '.join(proc.info['cmdline']),
        'create_time': proc.info['create_time'],
        'username': proc.info['username']
    }


def write_process_data_to_influxdb(process_info):
    point = Point("process_telemetry") \
        .tag("pid", str(process_info['pid'])) \
        .field("name", process_info['name']) \
        .field("cmdline", process_info['cmdline']) \
        .field("create_time", process_info['create_time']) \
        .field("username", process_info['username'])

    write_api.write(bucket, org, point)


# Configuration
influxdb_url = "http://10.0.0.49:8086"
token = "o9dclos8K53SKFK4ZDGjHEWsPStW2BLnTR7ItjxJtAsqzFKX8GkQXIxVxpksfQFvNgY3dlRHBkl-kWDJX_OivA=="
org = "Scrappy"
bucket = "Scrappybucket"

client = InfluxDBClient(url=influxdb_url, token=token)
write_api = client.write_api(write_options=SYNCHRONOUS)

# Ignore list for process names
ignore_list = ['Finder', 'Dock', 'SystemUIServer']

# Start monitoring
monitor_new_processes(ignore_list)