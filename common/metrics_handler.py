"""Handlers for collecting and pushing metrics in a serverless environment."""

import asyncio
import json
import logging
import os
from http.server import BaseHTTPRequestHandler
from typing import List, Tuple, Type

import aiohttp

from common.base_metric import BaseMetric
from common.factory import MetricFactory
from common.metric_config import MetricConfig


class MetricsHandler:
    """Handles collection and pushing of metrics for a specific blockchain."""

    def __init__(self, blockchain: str, metrics: List[Tuple[Type, str]]):
        """Initialize handler with blockchain and metrics configuration."""
        self.blockchain = blockchain
        self.metrics = metrics
        self.grafana_config = {
            "current_region": os.getenv("VERCEL_REGION"),
            "url": os.environ.get("GRAFANA_URL"),
            "user": os.environ.get("GRAFANA_USER"),
            "api_key": os.environ.get("GRAFANA_API_KEY"),
            "push_retries": int(os.environ.get("PUSH_MAX_RETRIES", "3")),
            "push_retry_delay": int(os.environ.get("PUSH_RETRY_DELAY", "10")),
            "push_timeout": int(os.environ.get("PUSH_TIMEOUT", "10")),
            "metric_request_timeout": int(os.environ.get("REQUEST_TIMEOUT", "30")),
            "metric_max_latency": int(os.environ.get("MAX_LATENCY", "30")),
        }

    async def collect_metrics(self, provider: dict, config: dict):
        """Collect metrics for a specific provider."""
        try:
            metrics = MetricFactory.create_metrics(
                blockchain_name=self.blockchain,
                config=MetricConfig(
                    timeout=self.grafana_config["metric_request_timeout"],
                    max_latency=self.grafana_config["metric_max_latency"],
                ),
                provider=provider["name"],
                source_region=self.grafana_config["current_region"],
                target_region=config.get("region", "default"),
                ws_endpoint=provider.get("websocket_endpoint"),
                http_endpoint=provider.get("http_endpoint"),
                extra_params={"tx_data": provider.get("data")},
            )
            await asyncio.gather(*(m.collect_metric() for m in metrics))
        except Exception as e:
            logging.error(
                "Error collecting %s metrics for %s: %s",
                self.blockchain,
                provider["name"],
                e,
            )

    def get_metrics_text(self) -> str:
        """Get formatted metrics text for Grafana."""
        return "\n".join(BaseMetric.get_all_latest_values())

    async def push_to_grafana(self, metrics_text: str):
        """Push collected metrics to Grafana."""
        if not all(
            [
                self.grafana_config["url"],
                self.grafana_config["user"],
                self.grafana_config["api_key"],
            ]
        ):
            return

        for attempt in range(1, self.grafana_config["push_retries"] + 1):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        self.grafana_config["url"],
                        headers={"Content-Type": "text/plain"},
                        data=metrics_text,
                        auth=aiohttp.BasicAuth(
                            self.grafana_config["user"], self.grafana_config["api_key"]
                        ),
                        timeout=self.grafana_config["push_timeout"],
                    ) as response:
                        if response.status in (200, 204):
                            return
            except Exception:
                if attempt < self.grafana_config["push_retries"]:
                    await asyncio.sleep(self.grafana_config["push_retry_delay"])

    async def handle(self) -> Tuple[str, str]:
        """Main handler for metric collection and pushing."""
        try:
            config = json.loads(os.getenv("ENDPOINTS"))
            MetricFactory.register({self.blockchain: self.metrics})

            chain_providers = [
                p
                for p in config.get("providers", [])
                if p["blockchain"] == self.blockchain
            ]
            await asyncio.gather(
                *(
                    self.collect_metrics(provider, config)
                    for provider in chain_providers
                )
            )

            metrics_text = self.get_metrics_text()
            if metrics_text:
                await self.push_to_grafana(metrics_text)

            return "done", metrics_text

        except Exception as e:
            logging.error("Error in %s metrics handler: %s", self.blockchain, e)
            raise


class BaseVercelHandler(BaseHTTPRequestHandler):
    """Base handler for Vercel serverless functions."""

    metrics_handler: MetricsHandler = None

    def validate_token(self):
        auth_token = self.headers.get("Authorization")
        expected_token = os.environ.get("API_SECRET")
        return auth_token == f"Bearer {expected_token}"

    def do_GET(self):
        if not self.validate_token():
            self.send_response(401)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write("Unauthorized".encode("utf-8"))
            return

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            _, metrics_text = loop.run_until_complete(self.metrics_handler.handle())
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            response = (
                f"{self.metrics_handler.blockchain} metrics collection "
                f"completed\n\nMetrics:\n{metrics_text}"
            )
            self.wfile.write(response.encode("utf-8"))
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(str(e).encode("utf-8"))
        finally:
            loop.close()
