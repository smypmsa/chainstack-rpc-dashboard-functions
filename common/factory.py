"""Factory for creating metric instances based on blockchain and provider configuration."""

from typing import Dict, List, Tuple, Type

from common.base_metric import BaseMetric
from common.metric_config import MetricConfig, MetricLabels


class MetricFactory:
    """
    Factory class to dynamically create metric instances based on blockchain name.
    Suitable for serverless: invoked each time metrics need to be created during a single invocation.
    """

    _registry: Dict[str, List[Tuple[Type[BaseMetric], str]]] = {}

    @classmethod
    def register(
        cls, blockchain_metrics: Dict[str, List[Tuple[Type[BaseMetric], str]]]
    ):
        """
        Registers multiple metric classes for multiple blockchains.

        Args:
            blockchain_metrics (Dict[str, List[Tuple[Type[BaseMetric], str]]]):
                A dictionary where keys are blockchain names (str),
                and values are lists of tuples (metric_class, metric_name).
        """
        for blockchain_name, metrics in blockchain_metrics.items():
            if blockchain_name not in cls._registry:
                cls._registry[blockchain_name] = []

            for metric in metrics:
                if isinstance(metric, tuple) and len(metric) == 2:
                    metric_class, metric_name = metric
                    cls._registry[blockchain_name].append((metric_class, metric_name))
                else:
                    raise ValueError(
                        "Each metric must be a tuple (metric_class, metric_name)"
                    )

    @classmethod
    def create_metrics(
        cls,
        blockchain_name: str,
        config: MetricConfig,
        **kwargs,
    ) -> List[BaseMetric]:
        """
        Create metric instances for a given blockchain name using the registered metrics.

        Args:
            blockchain_name (str): The name of the blockchain.
            config (MetricConfig): The configuration for the metrics.
            **kwargs: Additional parameters (e.g., source_region, target_region, provider)

        Returns:
            List[BaseMetric]: List of metric instances.
        """
        if blockchain_name not in cls._registry:
            available = list(cls._registry.keys())
            raise ValueError(
                f"No metric classes registered for blockchain '{blockchain_name}'. Available blockchains: {available}"
            )

        source_region = kwargs.get("source_region", "default")
        target_region = kwargs.get("target_region", "default")
        provider = kwargs.get("provider", "default")

        metrics = []
        for metric_class, metric_name in cls._registry[blockchain_name]:
            labels = MetricLabels(
                source_region=source_region,
                target_region=target_region,
                blockchain=blockchain_name,
                provider=provider,
            )

            metric_kwargs = kwargs.copy()
            metric_instance = metric_class(
                metric_name=metric_name,
                labels=labels,
                config=config,
                **metric_kwargs,
            )
            metrics.append(metric_instance)

        return metrics

    @classmethod
    def get_metrics(cls, blockchain_name: str) -> List[Type[BaseMetric]]:
        """
        Return all registered metric classes for a blockchain.
        """
        return [metric[0] for metric in cls._registry.get(blockchain_name, [])]

    @classmethod
    def get_all_metrics(cls) -> List[Type[BaseMetric]]:
        """
        Get all registered metric classes across all blockchains.
        """
        return [
            metric[0]
            for metric_classes in cls._registry.values()
            for metric in metric_classes
        ]
