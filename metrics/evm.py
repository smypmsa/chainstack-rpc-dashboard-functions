"""EVM metrics implementation for WebSocket and HTTP endpoints."""

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Optional

from web3 import Web3

from common.metric_config import MetricConfig, MetricLabelKey, MetricLabels
from common.metric_types import HttpCallLatencyMetricBase, WebSocketMetric


class WsBlockLatencyMetric(WebSocketMetric):
    """
    Collects block latency for EVM providers using a WebSocket connection.
    Suitable for serverless invocation: connects, subscribes, collects one message, and disconnects.
    """

    def __init__(
        self, metric_name: str, labels: MetricLabels, config: MetricConfig, **kwargs
    ):
        ws_endpoint = kwargs.pop("ws_endpoint", None)
        super().__init__(
            metric_name=metric_name,
            labels=labels,
            config=config,
            ws_endpoint=ws_endpoint,
        )
        self.labels.update_label(MetricLabelKey.API_METHOD, "eth_subscribe")
        self.last_block_hash: Optional[str] = None

    async def subscribe(self, websocket):
        """
        Subscribe to the newHeads event on the WebSocket endpoint.
        """
        subscription_msg = json.dumps(
            {
                "id": 1,
                "jsonrpc": "2.0",
                "method": "eth_subscribe",
                "params": ["newHeads"],
            }
        )
        await websocket.send(subscription_msg)
        response = await websocket.recv()
        subscription_data = json.loads(response)

        if subscription_data.get("result") is None:
            raise ValueError("Subscription to newHeads failed")

    async def unsubscribe(self, websocket):
        # EVM blockchains have no unsubscribe logic; do nothing.
        pass

    async def listen_for_data(self, websocket):
        """
        Listen for a single data message from the WebSocket and process block latency.
        """
        response = await websocket.recv()
        response_data = json.loads(response)

        if "params" in response_data:
            block = response_data["params"]["result"]
            block_hash = block["hash"]

            # LEGACY: Only process the block if it's not a duplicate
            if block_hash != self.last_block_hash:
                self.last_block_hash = block_hash
                return block

        return None

    def process_data(self, block):
        """
        Calculate block latency in seconds.
        """
        block_timestamp_hex = block.get("timestamp", "0x0")
        block_timestamp = int(block_timestamp_hex, 16)
        block_time = datetime.fromtimestamp(block_timestamp, timezone.utc)
        current_time = datetime.now(timezone.utc)
        latency = (current_time - block_time).total_seconds()
        return latency


class EthCallLatencyMetric(HttpCallLatencyMetricBase):
    """
    Collects transaction latency for endpoints using eth_call to simulate a transaction.
    This metric tracks the time taken for a simulated transaction (eth_call) to be processed by the RPC node.
    """

    def __init__(
        self, metric_name: str, labels: MetricLabels, config: MetricConfig, **kwargs
    ):
        super().__init__(
            metric_name=metric_name,
            labels=labels,
            config=config,
            method="eth_call",
            method_params=None,
            **kwargs,
        )

        self.tx_data = kwargs.get("extra_params", {}).get("tx_data")
        if self.tx_data:
            self.to_address = Web3.to_checksum_address(self.tx_data["to"])
            self.data = self.tx_data["data"]
            self.from_address = self.tx_data.get(
                "from", "0x0000000000000000000000000000000000000000"
            )
            self.labels.update_label(MetricLabelKey.API_METHOD, "eth_call")
        else:
            raise ValueError("Transaction data 'tx_data' is missing in extra_params")

    def get_web3_instance(self):
        """Return a Web3 instance for the HTTP endpoint."""
        web3 = Web3(
            Web3.HTTPProvider(self.http_endpoint, {"timeout": self.config.timeout})
        )
        if not web3.is_connected():
            raise ValueError(
                f"Failed to connect to {self.labels.get_label(MetricLabelKey.PROVIDER)} {self.labels.get_label(MetricLabelKey.BLOCKCHAIN)} node"
            )
        return web3

    async def fetch_data(self):
        """Perform the eth_call request to simulate a transaction and track its processing time."""
        web3 = self.get_web3_instance()
        start_time = time.monotonic()
        # Simulate transaction using eth_call in a separate thread
        response = await asyncio.to_thread(self.simulate_transaction, web3, self.data)
        end_time = time.monotonic()

        if response is None:
            raise ValueError("Response is empty")

        latency = end_time - start_time
        return latency

    def simulate_transaction(self, web3: Web3, transaction_data):
        """Simulate the transaction using eth_call and return the result."""
        call_params = {
            "from": self.from_address,
            "to": self.to_address,
            "data": transaction_data,
        }
        result = web3.eth.call(call_params, "latest")
        return result

    def process_data(self, value):
        return value


class HttpBlockNumberLatencyMetric(HttpCallLatencyMetricBase):
    """
    Collects call latency for the `eth_blockNumber` method.
    """

    def __init__(
        self, metric_name: str, labels: MetricLabels, config: MetricConfig, **kwargs
    ):
        super().__init__(
            metric_name=metric_name,
            labels=labels,
            config=config,
            method="eth_blockNumber",
            method_params=None,
            **kwargs,
        )


class HttpGasPriceLatencyMetric(HttpCallLatencyMetricBase):
    """
    Collects call latency for the `eth_gasPrice` method.
    """

    def __init__(
        self, metric_name: str, labels: MetricLabels, config: MetricConfig, **kwargs
    ):
        super().__init__(
            metric_name=metric_name,
            labels=labels,
            config=config,
            method="eth_gasPrice",
            method_params=None,
            **kwargs,
        )
