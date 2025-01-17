import json
import requests
import prometheus_client
from prometheus_client import Gauge
from prometheus_client.core import CollectorRegistry
from flask import Response, Flask

NodeFlask = Flask(__name__)
fiber_urls = [
    "http://18.162.235.225:8227",
    "http://18.163.221.211:8227"
]


class RpcGet(object):
    def __init__(self, url):
        self.url = url

    def count_channels(self):
        channels_data = self.call("graph_channels", [{}])
        if channels_data and 'channels' in channels_data:
            return len(channels_data['channels'])
        else:
            return 0

    def count_nodes(self):
        nodes_data = self.call("graph_nodes", [{}])
        if nodes_data and 'nodes' in nodes_data:
            return len(nodes_data['nodes'])
        else:
            return 0

    def call(self, method, params):
        headers = {'content-type': 'application/json'}
        data = {
            "id": 42,
            "jsonrpc": "2.0",
            "method": method,
            "params": params
        }
        response = requests.post(self.url, data=json.dumps(data), headers=headers).json()
        if 'error' in response.keys():
            error_message = response['error'].get('message', 'Unknown error')
            raise Exception(f"Error: {error_message}")
        return response.get('result', None)


@NodeFlask.route("/metrics")
def Node_Get():
    FIBER = CollectorRegistry(auto_describe=False)
    for index, url in enumerate(fiber_urls):
        # Gauge for channels
        channels_gauge = Gauge(
            f"graph_channels_length_{index}",
            f"Graph channels length from {url}",
            [],
            registry=FIBER
        )
        # Gauge for nodes
        nodes_gauge = Gauge(
            f"graph_nodes_count_{index}",
            f"Graph nodes count from {url}",
            [],
            registry=FIBER
        )

        get_result = RpcGet(url)
        # Set channel count
        graph_channels_length = get_result.count_channels()
        channels_gauge.set(graph_channels_length)
        # Set node count
        graph_nodes_count = get_result.count_nodes()
        nodes_gauge.set(graph_nodes_count)

    return Response(prometheus_client.generate_latest(FIBER), mimetype="text/plain")


if __name__ == "__main__":
    NodeFlask.run(host="0.0.0.0", port=8200)
