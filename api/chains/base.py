from common.metrics_handler import BaseVercelHandler, MetricsHandler
from metrics.evm import (
    EthCallLatencyMetric,
    HttpBlockNumberLatencyMetric,
    HttpGasPriceLatencyMetric,
    WsBlockLatencyMetric,
)

BASE_METRICS = [
    (WsBlockLatencyMetric, "response_latency_seconds"),
    (EthCallLatencyMetric, "response_latency_seconds"),
    (HttpBlockNumberLatencyMetric, "response_latency_seconds"),
    (HttpGasPriceLatencyMetric, "response_latency_seconds"),
]


class handler(BaseVercelHandler):
    metrics_handler = MetricsHandler("Base", BASE_METRICS)
