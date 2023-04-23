from ipwhois import IPWhois
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.client.query_api import QueryApi
from ipaddress import ip_address

# Configure InfluxDB client
influxdb_url = "http://localhost:8086"
token = "HZgcXFC4W6bAy-D3bWuSoNs_gabsOCkfElPLQhxylDKhKunDe1ai86-udL2uKY4lQQT06RFqBqj9yO8hcWmgIg=="
org = "Scrappy"
bucket = "Scrappybucket2"

def is_private_ip(ip):
    private_ip_ranges = [
        ('10.0.0.0', '10.255.255.255'),
        ('172.16.0.0', '172.31.255.255'),
        ('192.168.0.0', '192.168.255.255'),
    ]
    for start, end in private_ip_ranges:
        if ip_address(start) <= ip_address(ip) <= ip_address(end):
            return True
    return False

client = InfluxDBClient(url=influxdb_url, token=token)
write_api = client.write_api(write_options=SYNCHRONOUS)
query_api = client.query_api()

# Fetch unique destination IPs from InfluxDB
query = f'''
from(bucket: "{bucket}") 
  |> range(start: -1d) 
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> keep(columns: ["dst_ip"]) 
  |> distinct(column: "dst_ip")
'''
result = query_api.query(query, org=org)

unique_dst_ips = [record.get_value() for table in result for record in table.records]
print(f"Unique destination IPs: {unique_dst_ips}")

# Fetch whois information and store it in InfluxDB
for ip in unique_dst_ips:
    try:
        # Skip private IP addresses
        if is_private_ip(ip):
            continue

        ipwhois = IPWhois(ip)
        whois_data = ipwhois.lookup_rdap()
        print(f"Whois data for {ip}: {whois_data}")
        owner = whois_data.get("network", {}).get("name", "Unknown")

        point = Point("whois_data") \
            .tag("dst_ip", ip) \
            .field("owner", owner)

        write_api.write(bucket, org, point)
    except Exception as e:
        print(f"Error fetching whois data for {ip}: {e}")

# Query whois_data measurement from InfluxDB
query = f'from(bucket: "{bucket}") |> range(start: -1d) |> filter(fn: (r) => r._measurement == "whois_data")'
result = query_api.query(query, org=org)

# Print the results
for table in result:
    for record in table.records:
        owner = record['owner']
        if owner:
            print(f"IP: {record['dst_ip']}, Owner: {owner}")
        else:
            print(f"IP: {record['dst_ip']}, Owner: Unknown")