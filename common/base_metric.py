"""Base class for metrics collection and processing."""

import logging
import uuid
from abc import ABC, abstractmethod
from typing import Any, List, Optional, Union

from common.metric_config import MetricConfig, MetricLabelKey, MetricLabels


class BaseMetric(ABC):
    """
    Abstract base class for metrics that manages collection and formatting.
    Suitable for a single-invocation environment like Vercel, where instances
    are created, measured, and exported within one execution.
    """

    _instances: List["BaseMetric"] = []

    def __init__(
        self,
        metric_name: str,
        labels: MetricLabels,
        config: MetricConfig,
        ws_endpoint: Optional[str] = None,
        http_endpoint: Optional[str] = None,
    ) -> None:
        self.metric_id = str(uuid.uuid4())
        self.metric_name = metric_name
        self.labels = labels
        self.config = config
        self.ws_endpoint = ws_endpoint
        self.http_endpoint = http_endpoint
        self.latest_value = None
        self.__class__._instances.append(self)

    @classmethod
    def get_all_instances(cls) -> List["BaseMetric"]:
        """Returns all instances of the metric classes (for this invocation)."""
        return cls._instances

    @classmethod
    def get_all_latest_values(cls) -> List[str]:
        """Returns all latest values in Influx line protocol."""
        return [
            instance.get_influx_format()
            for instance in cls._instances
            if instance.latest_value is not None
        ]

    @abstractmethod
    async def collect_metric(self) -> None:
        """Collect metrics once per invocation, implemented in subclasses."""

    @abstractmethod
    def process_data(self, data: Any) -> Union[int, float]:
        """Process data to extract the metric value, implemented in subclasses."""

    def get_influx_format(self) -> str:
        """Formats the metric in Influx line protocol."""
        if self.latest_value is None:
            raise ValueError("Metric value is not set")

        tag_str = ",".join(
            [f"{label.key.value}={label.value}" for label in self.labels.labels]
        )
        if tag_str:
            return f"{self.metric_name},{tag_str} value={self.latest_value}"

        return f"{self.metric_name} value={self.latest_value}"

    async def update_metric_value(self, value: Union[int, float]) -> None:
        """Updates the latest value of the metric."""
        self.latest_value = value
        self.labels.update_label(MetricLabelKey.RESPONSE_STATUS, "success")

    async def handle_error(self, error: Exception) -> None:
        """Handles errors by marking the metric as failed."""
        self.labels.update_label(MetricLabelKey.RESPONSE_STATUS, "failed")
        logging.error(
            "Error in %s: %s", self.labels.get_prometheus_labels(), str(error)
        )
