from flask import Flask, jsonify, Response, render_template, request, send_from_directory
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.query_api import QueryApi
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

influxdb_url = "http://localhost:8086"
token = "HZgcXFC4W6bAy-D3bWuSoNs_gabsOCkfElPLQhxylDKhKunDe1ai86-udL2uKY4lQQT06RFqBqj9yO8hcWmgIg=="
org = "Scrappy"
bucket = "Scrappybucket2"

client = InfluxDBClient(url=influxdb_url, token=token)
query_api = client.query_api()

@app.route('/')
def index():
    return render_template('sankey.html')

@app.route('/sankey.js')
def serve_sankey_js():
    return send_from_directory('templates', 'sankey.js')

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response

@app.route('/api/data', methods=['GET'])
def get_data():
    query = '''from(bucket: "Scrappybucket2")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "network_telemetry" or r._measurement == "whois_data")
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> drop(columns: ["_time"])
  |> group(columns: ["src_ip", "dst_ip", "dst_port", "owner"])
  |> count(column: "src_port")
  |> rename(columns: {src_port: "count"})
  |> sort(columns: ["count"], desc: true)'''

    result = query_api.query(query, org=org)
    data = process_result_to_sankey_format(result)  # You need to write this function to convert the result to the required format
    response = jsonify(data)
    return response

if __name__ == '__main__':
    app.run()