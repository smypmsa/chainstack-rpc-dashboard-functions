"""Base classes for different metric types - WebSocket and HTTP metrics with their 
core functionality."""

import logging
import time
from abc import abstractmethod
from typing import Any, Optional

import aiohttp
import websockets

from common.base_metric import BaseMetric
from common.metric_config import MetricConfig, MetricLabelKey, MetricLabels


class WebSocketMetric(BaseMetric):
    """
    WebSocket-based metric for collecting data from a WebSocket connection.
    In a serverless environment, this will be called once per invocation.
    """

    def __init__(
        self,
        metric_name: str,
        labels: MetricLabels,
        config: MetricConfig,
        ws_endpoint: Optional[str] = None,
        http_endpoint: Optional[str] = None,
    ) -> None:
        super().__init__(metric_name, labels, config, ws_endpoint, http_endpoint)
        self.last_block_hash: Optional[str] = None
        self.subscription_id: Optional[int] = None
        self.last_value_timestamp = None

    @abstractmethod
    async def subscribe(self, websocket: Any) -> None:
        """Subscribes to WebSocket messages."""

    @abstractmethod
    async def unsubscribe(self, websocket: Any) -> None:
        """Unsubscribe from WebSocket subscription."""

    @abstractmethod
    async def listen_for_data(self, websocket: Any) -> Optional[Any]:
        """Listens for data on the WebSocket connection."""

    async def connect(self) -> Any:
        """
        Establish WebSocket connection.
        """
        websocket = await websockets.connect(
            self.ws_endpoint,
            ping_timeout=self.config.timeout,
            close_timeout=self.config.timeout,
        )
        return websocket

    async def collect_metric(self) -> None:
        """
        Collect a single websocket message once.
        """
        websocket = None
        try:
            websocket = await self.connect()
            await self.subscribe(websocket)

            data = await self.listen_for_data(websocket)
            if data is not None:
                latency = self.process_data(data)
                if latency > self.config.max_latency:
                    raise ValueError(
                        f"Latency {latency}s exceeds maximum allowed {self.config.max_latency}s"
                    )
                await self.update_metric_value(latency)

        except Exception as e:
            await self.handle_error(e)

        finally:
            if websocket:
                try:
                    await self.unsubscribe(websocket)
                    await websocket.close()
                except Exception as e:
                    logging.error("Error closing websocket: %s", str(e))


class HttpMetric(BaseMetric):
    """
    HTTP-based metric for collecting data via HTTP requests.
    In a serverless environment, this will be called once per invocation.
    """

    @abstractmethod
    async def fetch_data(self) -> Optional[Any]:
        """Fetches data from the HTTP endpoint."""

    async def collect_metric(self) -> None:
        """
        Collect an HTTP metric once.
        """
        try:
            data = await self.fetch_data()
            if data is not None:
                latency = self.process_data(data)
                if latency > self.config.max_latency:
                    raise ValueError(
                        f"Latency {latency}s exceeds maximum allowed {self.config.max_latency}s"
                    )
                await self.update_metric_value(latency)
        except Exception as e:
            await self.handle_error(e)


class HttpCallLatencyMetricBase(HttpMetric):
    """
    Base class for HTTP-based Ethereum endpoint latency metrics.
    Subclasses specify JSON-RPC method and parameters.
    """

    def __init__(
        self,
        metric_name: str,
        labels: MetricLabels,
        config: MetricConfig,
        method: str,
        method_params: dict = None,
        **kwargs,
    ):
        http_endpoint = kwargs.get("http_endpoint")
        super().__init__(
            metric_name=metric_name,
            labels=labels,
            config=config,
            http_endpoint=http_endpoint,
        )
        self.method = method
        self.method_params = method_params or None
        self.labels.update_label(MetricLabelKey.API_METHOD, method)
        self._base_request = {
            "id": 1,
            "jsonrpc": "2.0",
            "method": self.method,
        }
        if self.method_params:
            self._base_request["params"] = self.method_params

    async def fetch_data(self) -> float:
        """
        Perform the HTTP request once and return the response time.
        """
        start_time = time.monotonic()

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.http_endpoint,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json=self._base_request,
                timeout=self.config.timeout,
            ) as response:
                if response.status == 200:
                    await response.json()
                    latency = time.monotonic() - start_time
                    return latency

                raise ValueError(f"Unexpected status code: {response.status}.")

    def process_data(self, value: float) -> float:
        return value
