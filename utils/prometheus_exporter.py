"""
Prometheus Metrics Exporter for Georgian RAG
Exports metrics for Diptychs to Prometheus:
- Number of requests
- Response time
- Cache status
- Number of errors
"""

from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY
from prometheus_client.core import CollectorRegistry
import time
from functools import wraps
from typing import Dict, Any


# create a registry
registry = CollectorRegistry()

# metrics
REQUEST_COUNT = Counter(
    'rag_requests_total',
    'Total number of RAG requests',
    ['endpoint', 'language', 'status'],
    registry=registry
)

REQUEST_DURATION = Histogram(
    'rag_request_duration_seconds',
    'RAG request duration in seconds',
    ['endpoint', 'language'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
    registry=registry
)

CACHE_HITS = Counter(
    'rag_cache_hits_total',
    'Total number of cache hits',
    ['cache_type'],
    registry=registry
)

CACHE_MISSES = Counter(
    'rag_cache_misses_total',
    'Total number of cache misses',
    ['cache_type'],
    registry=registry
)

ACTIVE_REQUESTS = Gauge(
    'rag_active_requests',
    'Number of active requests',
    registry=registry
)

ERROR_COUNT = Counter(
    'rag_errors_total',
    'Total number of errors',
    ['error_type'],
    registry=registry
)

SEARCH_RESULTS = Histogram(
    'rag_search_results',
    'Number of search results returned',
    buckets=[0, 1, 3, 5, 10, 20],
    registry=registry
)

RESPONSE_LENGTH = Histogram(
    'rag_response_length_chars',
    'Response length in characters',
    buckets=[100, 500, 1000, 2000, 5000, 10000],
    registry=registry
)


def track_request(endpoint: str):
    """
    Decorator for tracking requests
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            ACTIVE_REQUESTS.inc()
            start_time = time.time()

            # extracting language from arguments
            language = kwargs.get('language', 'unknown')
            if hasattr(args[0], 'language'):
                language = args[0].language

            status = 'success'
            error_type = None

            try:
                result = await func(*args, **kwargs)

                # tracking performance metrics
                if hasattr(result, 'response'):
                    RESPONSE_LENGTH.observe(len(result.response))
                if hasattr(result, 'sources'):
                    SEARCH_RESULTS.observe(len(result.sources))

                return result

            except Exception as e:
                status = 'error'
                error_type = type(e).__name__
                ERROR_COUNT.labels(error_type=error_type).inc()
                raise

            finally:
                duration = time.time() - start_time

                REQUEST_COUNT.labels(
                    endpoint=endpoint,
                    language=language,
                    status=status
                ).inc()

                REQUEST_DURATION.labels(
                    endpoint=endpoint,
                    language=language
                ).observe(duration)

                ACTIVE_REQUESTS.dec()

        return wrapper
    return decorator


def track_cache_hit(cache_type: str):
    """Tracking cache hits"""
    CACHE_HITS.labels(cache_type=cache_type).inc()


def track_cache_miss(cache_type: str):
    """Tracking cache misses"""
    CACHE_MISSES.labels(cache_type=cache_type).inc()


def get_metrics() -> bytes:
    """Get metrics in Prometheus format"""
    return generate_latest(registry)


def get_metrics_summary() -> Dict[str, Any]:
    """
    Get a readable summary of metrics
    """
    summary = {}

    for metric in registry.collect():
        metric_name = metric.name
        metric_data = []

        for sample in metric.samples:
            metric_data.append({
                'labels': sample.labels,
                'value': sample.value
            })

        summary[metric_name] = metric_data

    return summary