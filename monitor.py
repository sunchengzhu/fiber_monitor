import json
import requests
import prometheus_client
from prometheus_client import Gauge
from prometheus_client.core import CollectorRegistry
from flask import Response, Flask
import sys  # 导入 sys 用于读取命令行参数
from decode_addr import decodeAddress

NodeFlask = Flask(__name__)

# 使用命令行参数或默认 URL 和 args
default_url = "http://127.0.0.1:8227"
default_addr = "ckt1qzda0cr08m85hc8jlnfp3zer7xulejywt49kt2rr0vthywaa50xwsqfy4w0gqjsm0ulnq0l4ft6hu6spztrj72sjtcnx4"
fiber_url = sys.argv[1] if len(sys.argv) > 1 else default_url
addr = sys.argv[2] if len(sys.argv) > 2 else default_addr
decode_addr = decodeAddress(addr, "testnet")

if decode_addr:
    if decode_addr[0] == 'short':
        code_hash = "0x9bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8"
        args = decode_addr[2]
    else:
        code_hash = decode_addr[1]
        args = decode_addr[3]
else:
    print("Invalid or unsupported address format.")

FIBER = CollectorRegistry(auto_describe=False)

# 定义所有全局的Gauges
channels_gauge = Gauge("graph_channels_count", "Number of graph channels", registry=FIBER)
nodes_gauge = Gauge("graph_nodes_count", "Number of graph nodes", registry=FIBER)
peers_count_gauge = Gauge("peers_count", "Number of peers", registry=FIBER)
channel_count_gauge = Gauge("channel_count", "Number of channels", registry=FIBER)
wallet_ckb_gauge = Gauge('wallet_ckb', 'Total CKB capacity in wallet', ['wallet_address'], registry=FIBER)
wallet_rusd_gauge = Gauge('wallet_rusd', 'Total RUSD capacity in wallet', ['wallet_address'], registry=FIBER)

fiber_total_ckb_gauge = Gauge('fiber_total_ckb', 'Total local CKB balance for all channels', registry=FIBER)
fiber_total_rusd_gauge = Gauge('fiber_total_rusd', 'Total local RUSD balance for all channels', registry=FIBER)


def convert_int(value):
    try:
        return int(value)
    except ValueError:
        return int(value, base=16)
    except Exception as exp:
        raise exp


def le_to_be(v: str) -> str:
    # to big endian
    bytes_str = v[2:]  # Remove '0x' prefix
    bytes_list = [bytes_str[i:i + 2] for i in range(0, len(bytes_str), 2)]
    if not bytes_list:
        return ''
    be = '0x' + ''.join(reversed(bytes_list))
    try:
        # Check if it is a valid hexadecimal
        int(be, 16)
        return be
    except ValueError:
        raise ValueError('Invalid little-endian hex value')


def hex_to_xudt_data(v: str):
    amount = v[0:34]
    be_amount = le_to_be(amount)
    res = {
        'AMOUNT': int(be_amount, 16)  # Converting the amount to an integer from hex
    }
    data = v[34:]
    if data:
        res['DATA'] = data
    return res


class RpcGet(object):
    def __init__(self, url):
        self.url = url
        self.ckb_url = "https://testnet.ckb.dev/indexer"

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

    def get_wallet_ckb(self, code_hash_value, args_value):
        params = [{
            "script": {
                "code_hash": code_hash_value,
                "hash_type": "type",
                "args": args_value
            },
            "script_type": "lock"
        }]
        response = self.call("get_cells_capacity", params, self.ckb_url)
        if 'capacity' in response:
            capacity_value = convert_int(response['capacity']) / 100000000.0
            return capacity_value
        else:
            raise Exception("Error: Unable to retrieve wallet capacity.")

    def get_wallet_rusd(self, code_hash_value, args_value):
        params = [
            {
                "script": {
                    "code_hash": code_hash_value,
                    "hash_type": "type",
                    "args": args_value
                },
                "script_type": "lock",
                "script_search_mode": "exact",
                "filter": {
                    "script": {
                        "code_hash": "0x1142755a044bf2ee358cba9f2da187ce928c91cd4dc8692ded0337efa677d21a",
                        "hash_type": "type",
                        "args": "0x878fcc6f1f08d48e87bb1c3b3d5083f23f8a39c5d5c764f253b55b998526439b"
                    }
                }
            },
            "desc",
            "0x3e8"
        ]
        response = self.call("get_cells", params, self.ckb_url)
        if 'objects' in response:
            total_amount = 0
            for item in response['objects']:
                output_data = item.get('output_data', '')
                if output_data and output_data != "0x00000000000000000000000000000000":
                    try:
                        data_details = hex_to_xudt_data(output_data)
                        total_amount += data_details.get('AMOUNT', 0) / 100000000.0
                    except Exception as e:
                        print("Error processing data:", e)
            return total_amount
        else:
            raise Exception("No valid response or missing 'objects' key in response")

    def call(self, method, params, url=None):
        if not url:
            url = self.url
        headers = {'Content-Type': 'application/json'}
        data = {"id": 42, "jsonrpc": "2.0", "method": method, "params": params}
        response = requests.post(url, data=json.dumps(data), headers=headers).json()
        if 'error' in response.keys():
            error_message = response['error'].get('message', 'Unknown error')
            raise Exception(f"Error: {error_message}")
        return response.get('result', None)


gauges = {}
# 全局变量，存储活跃通道的详细信息
global active_channel_details
active_channel_details = {}


@NodeFlask.route("/metrics")
def Node_Get():
    get_result = RpcGet(fiber_url)
    channels = get_result.list_channels()
    current_channel_ids = set()

    # 设置通道和节点的计数
    channels_gauge.set(get_result.count_channels())
    nodes_gauge.set(get_result.count_nodes())
    peers_count_gauge.set(get_result.get_peers_count())
    channel_count_gauge.set(get_result.get_channel_count())

    wallet_ckb = get_result.get_wallet_ckb(code_hash, args)
    wallet_ckb_gauge.labels(wallet_address=addr).set(wallet_ckb)
    wallet_rusd = get_result.get_wallet_rusd(code_hash, args)
    wallet_rusd_gauge.labels(wallet_address=addr).set(wallet_rusd)

    total_ckb = 0
    total_rusd = 0

    # 更新或创建当前活跃通道的Gauge
    for channel in channels:
        peer_id = channel['peer_id']
        channel_id = channel['channel_id']
        local_balance = convert_int(channel['local_balance'])
        remote_balance = convert_int(channel['remote_balance'])
        funding_udt_type_script = channel.get('funding_udt_type_script')

        state_name = channel['state']['state_name']
        if state_name != "CHANNEL_READY":
            continue  # 如果状态不是 CHANNEL_READY，则跳过

        # 判断 funding_udt_type_script 是否为 null
        if funding_udt_type_script is None:
            local_gauge_name = "channel_local_ckb"
            remote_gauge_name = "channel_remote_ckb"
            total_ckb += local_balance / 100000000.0
        else:
            local_gauge_name = "channel_local_rusd"
            remote_gauge_name = "channel_remote_rusd"
            total_rusd += local_balance / 100000000.0

        # 记录当前活跃的通道ID和详细信息
        current_channel_ids.add(channel_id)
        active_channel_details[channel_id] = {
            'peer_id': peer_id,
            'local_gauge_name': local_gauge_name,
            'remote_gauge_name': remote_gauge_name
        }
        # 只有当 Gauge 还未创建时才创建它
        if local_gauge_name not in gauges:
            gauges[local_gauge_name] = Gauge(local_gauge_name, "Local balance for channel",
                                             ['peer_id', 'channel_id'], registry=FIBER)
        if remote_gauge_name not in gauges:
            gauges[remote_gauge_name] = Gauge(remote_gauge_name, "Remote balance for channel",
                                              ['peer_id', 'channel_id'], registry=FIBER)
        # 更新 Gauge 的值
        gauges[local_gauge_name].labels(peer_id=peer_id, channel_id=channel_id).set(local_balance / 100000000.0)
        gauges[remote_gauge_name].labels(peer_id=peer_id, channel_id=channel_id).set(remote_balance / 100000000.0)

    # 确定和处理不再活跃的通道
    inactive_channel_ids = set(active_channel_details.keys()) - current_channel_ids
    print("Inactive channels: {}".format(inactive_channel_ids))
    for channel_id in inactive_channel_ids:
        channel_info = active_channel_details.pop(channel_id, None)
        if channel_info:
            gauges[channel_info['local_gauge_name']].labels(peer_id=channel_info['peer_id'],
                                                            channel_id=channel_id).set(-1)
            gauges[channel_info['remote_gauge_name']].labels(peer_id=channel_info['peer_id'],
                                                             channel_id=channel_id).set(-1)

    # 更新总累积值
    fiber_total_ckb_gauge.set(total_ckb)
    fiber_total_rusd_gauge.set(total_rusd)

    return Response(prometheus_client.generate_latest(FIBER), mimetype="text/plain")


if __name__ == "__main__":
    NodeFlask.run(host="0.0.0.0", port=8200)
