"""Configuration classes for metric collection settings."""

import logging
from enum import Enum
from typing import Any, Dict, Optional


class MetricLabelKey(Enum):
    """Enum defining standard label keys for metric identification and categorization.

    Keys:
    - SOURCE_REGION: Region where metric collection originates
    - TARGET_REGION: Target region being monitored
    - BLOCKCHAIN: Blockchain network identifier
    - PROVIDER: RPC provider name
    - API_METHOD: Method being called
    - RESPONSE_STATUS: Response status from provider
    """

    SOURCE_REGION = "source_region"
    TARGET_REGION = "target_region"
    BLOCKCHAIN = "blockchain"
    PROVIDER = "provider"
    API_METHOD = "api_method"
    RESPONSE_STATUS = "response_status"


class MetricConfig:
    """
    Configuration for the metric, including timeout, interval, etc.
    Suitable for serverless invocation—just holds configuration data.
    """

    def __init__(
        self,
        timeout: int,
        max_latency: int,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.timeout = timeout
        self.max_latency = max_latency
        self.extra_params = extra_params or {}


class MetricLabel:
    """
    Holds a single label for a metric.
    """

    def __init__(self, key: MetricLabelKey, value: str) -> None:
        if not isinstance(key, MetricLabelKey):
            raise ValueError(
                f"Invalid key, must be an instance of MetricLabelKey Enum: {key}"
            )
        self.key = key
        self.value = value


class MetricLabels:
    """
    Holds a collection of MetricLabel instances for a metric.
    """

    def __init__(
        self,
        source_region: str,
        target_region: str,
        blockchain: str,
        provider: str,
        api_method: str = "default",
        response_status: str = "success",
    ) -> None:
        self.labels = [
            MetricLabel(MetricLabelKey.SOURCE_REGION, source_region),
            MetricLabel(MetricLabelKey.TARGET_REGION, target_region),
            MetricLabel(MetricLabelKey.BLOCKCHAIN, blockchain),
            MetricLabel(MetricLabelKey.PROVIDER, provider),
            MetricLabel(MetricLabelKey.API_METHOD, api_method),
            MetricLabel(MetricLabelKey.RESPONSE_STATUS, response_status),
        ]

    def get_prometheus_labels(self) -> str:
        """
        Returns a string of Prometheus-style labels.
        """
        return ",".join(f'{label.key.value}="{label.value}"' for label in self.labels)

    def update_label(self, label_name: MetricLabelKey, new_value: str) -> None:
        """
        Update the value of a label.
        """
        for label in self.labels:
            if label.key == label_name:
                label.value = new_value
                return
        logging.warning("Label '%s' not found!", label_name.value)

    def add_label(self, label_name: MetricLabelKey, label_value: str) -> None:
        """
        Adds a new label to the collection.
        """
        for label in self.labels:
            if label.key == label_name:
                self.update_label(label_name, label_value)
                return

        self.labels.append(MetricLabel(label_name, label_value))

    def get_label(self, label_name: MetricLabelKey) -> Optional[str]:
        """
        Retrieve the value of a label by its key.
        """
        for label in self.labels:
            if label.key == label_name:
                return label.value
        return None
