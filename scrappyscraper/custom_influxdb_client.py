from influxdb_client import InfluxDBClient, QueryApi
from influxdb_client.client.query_api import QueryOptions
from io import TextIOWrapper, BytesIO
from influxdb_client.client.flux_csv_parser import FluxCsvParser
from datetime import timezone
import csv

class CustomFluxCsvParser(FluxCsvParser):
    def _parse_flux_response(self):
        response_bytes = self._response.read().replace(b'\x00', b'')
        self._reader = csv.reader(TextIOWrapper(BytesIO(response_bytes), encoding='utf-8'), dialect=csv.excel)

        for row in self._reader:
            yield row

from influxdb_client.client.query_api import QueryApi

class CustomQueryApi(QueryApi):
    def _to_tables(self, response):
        parser = CustomFluxCsvParser(response, self._options.default_timezone)
        return list(parser.generator())

class CustomInfluxDBClient(InfluxDBClient):
    def __init__(self, url, token, **kwargs):
        super().__init__(url, token, **kwargs)

    def query_api(self):
        return CustomQueryApi(influxdb_client=self)

    def get_configuration(self):
        return getattr(self, '_InfluxDBClient__configuration', None)

class CustomQueryApi(QueryApi):
    def __init__(self, influxdb_client):
        super().__init__(influxdb_client=influxdb_client)

    def _to_tables(self, response, query_options=None):
        query_options = self._get_query_options()
        default_timezone = query_options.default_timezone if query_options else timezone.utc
        parser = CustomFluxCsvParser(response, default_timezone)
        return list(parser.generator())