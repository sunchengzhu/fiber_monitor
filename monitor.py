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
        channels_data = self.call("list_channels", [{}])  # 获取通道数据
        if 'channels' in channels_data:
            channels_by_peer_id = {}  # 创建字典以根据 peer_id 分组
            for channel in channels_data['channels']:
                # 检查通道状态是否为 CHANNEL_READY
                if channel['state']['state_name'] == "CHANNEL_READY":
                    peer_id = channel['peer_id']  # 获取当前通道的 peer_id
                    if peer_id not in channels_by_peer_id:
                        channels_by_peer_id[peer_id] = {
                            'all_local_balance': 0,  # 初始化所有本地余额的和
                            'all_remote_balance': 0  # 初始化所有远程余额的和
                        }
                    # 将十六进制的余额转换为整数并累加
                    channels_by_peer_id[peer_id]['all_local_balance'] += int(channel['local_balance'], 16)
                    channels_by_peer_id[peer_id]['all_remote_balance'] += int(channel['remote_balance'], 16)

            # 在返回之前将所有余额除以 100000000 并格式化输出为浮点数，保留 8 位小数
            for peer_id, balances in channels_by_peer_id.items():
                balances['all_local_balance'] = "{:.8f}".format(balances['all_local_balance'] / 100000000.0)
                balances['all_remote_balance'] = "{:.8f}".format(balances['all_remote_balance'] / 100000000.0)

            return channels_by_peer_id
        else:
            return {}  # 如果没有通道数据，返回一个空字典

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
    # Gauge for channels
    channels_gauge = Gauge(
        "graph_channels_count",
        "graph_channels count",
        [],
        registry=FIBER
    )
    # Gauge for nodes
    nodes_gauge = Gauge(
        "graph_nodes_count",
        "graph_nodes count",
        [],
        registry=FIBER
    )
    peers_count_gauge = Gauge(
        "node_info_peers_count",
        "node_info peers_count",
        [],
        registry=FIBER
    )
    channel_count_gauge = Gauge(
        "node_info_channel_count",
        "node_info channel_count",
        [],
        registry=FIBER
    )

    get_result = RpcGet(fiber_url)

    # Set the countber of channels
    graph_channels_count = get_result.count_channels()
    channels_gauge.set(graph_channels_count)
    # Set the countber of nodes
    graph_nodes_count = get_result.count_nodes()
    nodes_gauge.set(graph_nodes_count)

    peers_count = get_result.get_peers_count()
    peers_count_gauge.set(peers_count)
    channel_count = get_result.get_channel_count()
    channel_count_gauge.set(channel_count)

    channels_grouped_by_peer_id = get_result.list_channels()
    gauges_local = {}
    gauges_remote = {}

    for peer_id, balances in channels_grouped_by_peer_id.items():
        # 为每个 peer_id 创建或更新 Gauge
        if peer_id not in gauges_local:
            gauges_local[peer_id] = Gauge(
                f"peer_{peer_id}_local_balance",
                "Total local balance",
                registry=FIBER
            )
        if peer_id not in gauges_remote:
            gauges_remote[peer_id] = Gauge(
                f"peer_{peer_id}_remote_balance",
                "Total remote balance",
                registry=FIBER
            )

        # 设置 Gauge 的值
        gauges_local[peer_id].set(balances['all_local_balance'])
        gauges_remote[peer_id].set(balances['all_remote_balance'])

    return Response(prometheus_client.generate_latest(FIBER), mimetype="text/plain")


if __name__ == "__main__":
    NodeFlask.run(host="0.0.0.0", port=8200)
