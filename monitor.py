import json
import requests
import prometheus_client
from prometheus_client import Gauge
from prometheus_client.core import CollectorRegistry
from flask import Response, Flask
import sys  # 导入 sys 用于读取命令行参数

NodeFlask = Flask(__name__)

# 默认 URL
default_url = "http://127.0.0.1:8227"
# 使用命令行参数或默认 URL
fiber_url = sys.argv[1] if len(sys.argv) > 1 else default_url
FIBER = CollectorRegistry(auto_describe=False)

# 定义所有全局的Gauges
channels_gauge = Gauge("graph_channels_count", "Number of graph channels", registry=FIBER)
nodes_gauge = Gauge("graph_nodes_count", "Number of graph nodes", registry=FIBER)
peers_count_gauge = Gauge("peers_count", "Number of peers", registry=FIBER)
channel_count_gauge = Gauge("channel_count", "Number of channels", registry=FIBER)


def convert_int(value):
    try:
        return int(value)
    except ValueError:
        return int(value, base=16)
    except Exception as exp:
        raise exp


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

    def get_peers_count(self):
        node_info = self.call("node_info", [{}])
        if node_info and 'peers_count' in node_info:
            return convert_int(node_info['peers_count'])
        else:
            return 0

    def get_channel_count(self):
        node_info = self.call("node_info", [{}])
        if node_info and 'channel_count' in node_info:
            return convert_int(node_info['channel_count'])
        else:
            return 0

    def list_channels(self):
        channels_data = self.call("list_channels", [{}])
        return channels_data['channels'] if 'channels' in channels_data else []

    def call(self, method, params):
        headers = {'content-type': 'application/json'}
        data = {"id": 42, "jsonrpc": "2.0", "method": method, "params": params}
        response = requests.post(self.url, data=json.dumps(data), headers=headers).json()
        if 'error' in response.keys():
            error_message = response['error'].get('message', 'Unknown error')
            raise Exception(f"Error: {error_message}")
        return response.get('result', None)


gauges = {}


@NodeFlask.route("/metrics")
def Node_Get():
    get_result = RpcGet(fiber_url)

    # 设置通道和节点的计数
    channels_gauge.set(get_result.count_channels())
    nodes_gauge.set(get_result.count_nodes())
    peers_count_gauge.set(get_result.get_peers_count())
    channel_count_gauge.set(get_result.get_channel_count())

    # 获取通道数据并设置每个通道的余额指标
    channels = get_result.list_channels()

    for channel in channels:
        peer_id = channel['peer_id']
        channel_id = channel['channel_id']
        local_balance = convert_int(channel['local_balance'])
        remote_balance = convert_int(channel['remote_balance'])

        # 定义唯一的标识符
        local_gauge_name = "channel_local_balance"
        remote_gauge_name = "channel_remote_balance"

        # 只有当 Gauge 还未创建时才创建它
        if local_gauge_name not in gauges:
            gauges[local_gauge_name] = Gauge(local_gauge_name, "Local balance for channel", ['peer_id', 'channel_id'],
                                             registry=FIBER)
        if remote_gauge_name not in gauges:
            gauges[remote_gauge_name] = Gauge(remote_gauge_name, "Remote balance for channel",
                                              ['peer_id', 'channel_id'], registry=FIBER)

        # 更新 Gauge 的值
        gauges[local_gauge_name].labels(peer_id=peer_id, channel_id=channel_id).set(local_balance / 100000000.0)
        gauges[remote_gauge_name].labels(peer_id=peer_id, channel_id=channel_id).set(remote_balance / 100000000.0)

    return Response(prometheus_client.generate_latest(FIBER), mimetype="text/plain")


if __name__ == "__main__":
    NodeFlask.run(host="0.0.0.0", port=8200)
