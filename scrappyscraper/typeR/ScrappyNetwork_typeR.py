import time, psutil
from scapy.all import sniff
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from psutil import Process
from scapy.all import Packet
from scapy.layers.inet import IP, TCP
from datetime import datetime
from influxdb_client import WritePrecision


# Replace these values with your InfluxDB settings
influxdb_url = "http://10.0.0.49:8086"
token = "o9dclos8K53SKFK4ZDGjHEWsPStW2BLnTR7ItjxJtAsqzFKX8GkQXIxVxpksfQFvNgY3dlRHBkl-kWDJX_OivA=="
org = "Scrappy"
bucket = "Scrappybucket"

client = InfluxDBClient(url=influxdb_url, token=token)
write_api = client.write_api(write_options=SYNCHRONOUS)

def find_process(port):
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            proc_connections = proc.connections()
        except Exception:
            continue

        for conn in proc_connections:
            if conn.laddr.port == port:
                return {'name': proc.info['name'], 'cmdline': ' '.join(proc.cmdline())}
    return None

try:
    # Packet capture callback function
    def process_packet(packet, interface):
        if packet.haslayer(IP) and packet.haslayer(TCP):
            src_ip = packet[IP].src
            dst_ip = packet[IP].dst
            src_port = packet[TCP].sport
            dst_port = packet[TCP].dport
            packet_length = len(packet)

            process = find_process(src_port)
            process_name = process['name'] if process else "unknown"
            command_line = process['cmdline'] if process else "unknown"

            point = Point("network_telemetry").tag("interface", interface) \
                                            .tag("src_ip", src_ip) \
                                            .tag("dst_ip", dst_ip) \
                                            .field("src_port", src_port) \
                                            .field("dst_port", int(dst_port)) \
                                            .field("packet_length", packet_length) \
                                            .field("process_name", process_name) \
                                            .field("command_line", command_line) \
                                            .time(datetime.utcnow(), WritePrecision.NS)

            write_api.write(bucket, org, point)
            print(f"Data written to InfluxDB: src_ip={src_ip}, dst_ip={dst_ip}, dst_port={dst_port}, packet_length={packet_length}, timestamp={datetime.utcnow()}")

    # Start packet capture
    interface = "en0"  # Replace "en0" with the desired interface name
    sniff(prn=lambda packet: process_packet(packet, interface), filter="tcp", store=0)

except Exception as e:
    print(f"An error occurred: {e}")