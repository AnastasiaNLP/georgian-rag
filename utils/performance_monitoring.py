"""
Performance monitoring system for rag

tracks:
- execution time for each component
- bottlenecks
- performance trends
- anomalies and degradation
"""

import time
import statistics
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ComponentMetrics:
    """Metrics for one component"""
    component_name: str
    total_calls: int = 0
    total_time: float = 0.0
    avg_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    last_10_times: List[float] = field(default_factory=list)
    error_count: int = 0

    def update(self, execution_time: float):
        """Update metrics after execution"""
        self.total_calls += 1
        self.total_time += execution_time
        self.avg_time = self.total_time / self.total_calls

        self.min_time = min(self.min_time, execution_time)
        self.max_time = max(self.max_time, execution_time)

        # store last 10 measurements
        self.last_10_times.append(execution_time)
        if len(self.last_10_times) > 10:
            self.last_10_times.pop(0)

    def get_recent_avg(self) -> float:
        """Average time for last 10 calls"""
        if not self.last_10_times:
            return 0.0
        return statistics.mean(self.last_10_times)

    def get_trend(self) -> str:
        """Determine performance trend"""
        if len(self.last_10_times) < 5:
            return "insufficient_data"

        recent = statistics.mean(self.last_10_times[-3:])
        older = statistics.mean(self.last_10_times[:3])

        if recent > older * 1.2:
            return "degrading"
        elif recent < older * 0.8:
            return "improving"
        else:
            return "stable"


class PerformanceMonitor:
    """
    Centralized performance monitoring for rag system

    tracks:
    - execution time for each component
    - bottlenecks
    - performance trends
    - anomalies and degradation
    """

    def __init__(self):
        # component metrics
        self.components: Dict[str, ComponentMetrics] = {}

        # search metrics (end-to-end)
        self.search_metrics = {
            'total_searches': 0,
            'successful_searches': 0,
            'failed_searches': 0,
            'total_search_time': 0.0,
            'avg_search_time': 0.0,
            'fastest_search': float('inf'),
            'slowest_search': 0.0,
            'last_10_searches': []
        }

        # bottleneck detection
        self.bottleneck_threshold = 2.0  # seconds
        self.bottlenecks_detected = []

        # monitoring start time
        self.start_time = time.time()

        logger.info("performancemonitor initialized")

    def track_component(self, component_name: str, execution_time: float, success: bool = True):
        """
        Track component execution

        args:
            component_name: component name (e.g., "prefilter", "bm25", "dense")
            execution_time: execution time in seconds
            success: whether execution was successful
        """
        if component_name not in self.components:
            self.components[component_name] = ComponentMetrics(component_name)

        metrics = self.components[component_name]
        metrics.update(execution_time)

        if not success:
            metrics.error_count += 1

        # bottleneck detection
        if execution_time > self.bottleneck_threshold:
            self.bottlenecks_detected.append({
                'component': component_name,
                'time': execution_time,
                'timestamp': time.time()
            })
            logger.warning(f"bottleneck detected: {component_name} took {execution_time:.3f}s")

    def track_search(self, search_time: float, success: bool = True):
        """Track full search (end-to-end)"""
        self.search_metrics['total_searches'] += 1

        if success:
            self.search_metrics['successful_searches'] += 1
        else:
            self.search_metrics['failed_searches'] += 1

        self.search_metrics['total_search_time'] += search_time
        self.search_metrics['avg_search_time'] = (
            self.search_metrics['total_search_time'] / self.search_metrics['total_searches']
        )

        self.search_metrics['fastest_search'] = min(
            self.search_metrics['fastest_search'], search_time
        )
        self.search_metrics['slowest_search'] = max(
            self.search_metrics['slowest_search'], search_time
        )

        # store last 10 searches
        self.search_metrics['last_10_searches'].append(search_time)
        if len(self.search_metrics['last_10_searches']) > 10:
            self.search_metrics['last_10_searches'].pop(0)

    def get_component_breakdown(self) -> Dict[str, Dict]:
        """Get component breakdown"""
        breakdown = {}

        for name, metrics in self.components.items():
            breakdown[name] = {
                'avg_time': round(metrics.avg_time, 3),
                'total_calls': metrics.total_calls,
                'total_time': round(metrics.total_time, 3),
                'min_time': round(metrics.min_time, 3),
                'max_time': round(metrics.max_time, 3),
                'recent_avg': round(metrics.get_recent_avg(), 3),
                'trend': metrics.get_trend(),
                'error_count': metrics.error_count,
                'error_rate': round(metrics.error_count / max(metrics.total_calls, 1) * 100, 2)
            }

        return breakdown

    def identify_bottlenecks(self) -> List[Dict]:
        """
        Identify bottlenecks

        returns:
            list of bottleneck components with details
        """
        bottlenecks = []

        for name, metrics in self.components.items():
            # bottleneck criteria:
            # 1. average time > 1 second
            # 2. or maximum time > 3 seconds
            # 3. or degrading trend

            is_bottleneck = (
                metrics.avg_time > 1.0 or
                metrics.max_time > 3.0 or
                metrics.get_trend() == "degrading"
            )

            if is_bottleneck:
                bottlenecks.append({
                    'component': name,
                    'avg_time': round(metrics.avg_time, 3),
                    'max_time': round(metrics.max_time, 3),
                    'trend': metrics.get_trend(),
                    'severity': self._calculate_severity(metrics)
                })

        # sort by severity
        bottlenecks.sort(key=lambda x: x['severity'], reverse=True)

        return bottlenecks

    def _calculate_severity(self, metrics: ComponentMetrics) -> int:
        """Calculate problem severity (0-100)"""
        severity = 0

        # factor 1: average time
        if metrics.avg_time > 2.0:
            severity += 40
        elif metrics.avg_time > 1.0:
            severity += 20

        # factor 2: maximum time
        if metrics.max_time > 5.0:
            severity += 30
        elif metrics.max_time > 3.0:
            severity += 15

        # factor 3: trend
        if metrics.get_trend() == "degrading":
            severity += 30

        return min(severity, 100)

    def get_recommendations(self) -> List[str]:
        """
        Get optimization recommendations
        """
        recommendations = []
        bottlenecks = self.identify_bottlenecks()

        for bottleneck in bottlenecks:
            component = bottleneck['component']

            # specific recommendations for each component
            if 'PreFilter' in component:
                recommendations.append(
                    f"prefilter is slow ({bottleneck['avg_time']}s avg). "
                    f"consider: reducing candidate count, optimizing filters, or enabling filter cache."
                )

            elif 'BM25' in component:
                recommendations.append(
                    f"bm25 is slow ({bottleneck['avg_time']}s avg). "
                    f"consider: using temporary indexes cache, reducing corpus size, or optimizing tokenization."
                )

            elif 'Dense' in component:
                recommendations.append(
                    f"dense search is slow ({bottleneck['avg_time']}s avg). "
                    f"consider: batch processing, model caching, or reducing vector dimension."
                )

            elif 'Fusion' in component or 'RRF' in component:
                recommendations.append(
                    f"rrf fusion is slow ({bottleneck['avg_time']}s avg). "
                    f"consider: optimizing weight calculation or reducing result count."
                )

            elif 'Translation' in component or 'Multilingual' in component:
                recommendations.append(
                    f"translation is slow ({bottleneck['avg_time']}s avg). "
                    f"consider: increasing cache ttl, using permanent cache for common phrases."
                )

            elif 'Claude' in component or 'LLM' in component:
                recommendations.append(
                    f"llm generation is slow ({bottleneck['avg_time']}s avg). "
                    f"consider: reducing max_tokens, optimizing prompt length, or using faster model."
                )

        # general recommendations
        if self.search_metrics['avg_search_time'] > 3.0:
            recommendations.append(
                f"overall search is slow ({self.search_metrics['avg_search_time']:.2f}s avg). "
                f"consider: enabling parallel processing, warm-up optimization, or reducing top_k."
            )

        return recommendations

    def get_summary(self) -> Dict[str, Any]:
        """Get performance summary"""
        uptime = time.time() - self.start_time

        return {
            'uptime_seconds': round(uptime, 2),
            'search_metrics': self.search_metrics.copy(),
            'component_breakdown': self.get_component_breakdown(),
            'bottlenecks': self.identify_bottlenecks(),
            'recommendations': self.get_recommendations(),
            'health_status': self._get_health_status(),
            'timestamp': datetime.now().isoformat()
        }

    def _get_health_status(self) -> str:
        """Determine overall system health status"""
        bottlenecks = self.identify_bottlenecks()
        avg_search = self.search_metrics['avg_search_time']

        if not bottlenecks and avg_search < 2.0:
            return "healthy"
        elif len(bottlenecks) <= 1 and avg_search < 3.0:
            return "warning"
        else:
            return "critical"

    def reset(self):
        """Reset all metrics"""
        self.components.clear()
        self.search_metrics = {
            'total_searches': 0,
            'successful_searches': 0,
            'failed_searches': 0,
            'total_search_time': 0.0,
            'avg_search_time': 0.0,
            'fastest_search': float('inf'),
            'slowest_search': 0.0,
            'last_10_searches': []
        }
        self.bottlenecks_detected.clear()
        self.start_time = time.time()
        logger.info("performancemonitor reset")

    def print_summary(self):
        """Print summary"""
        summary = self.get_summary()

        print("\nPerformance summary")

        # health status
        status = summary['health_status']
        print(f"\nHealth status: {status.upper()}")
        print(f"   Uptime: {summary['uptime_seconds']:.1f}s")

        # search metrics
        print(f"\nSearch metrics:")
        sm = summary['search_metrics']
        print(f"   Total searches: {sm['total_searches']}")
        if sm['total_searches'] > 0:
            print(f"   Success rate: {sm['successful_searches']}/{sm['total_searches']} "
                  f"({sm['successful_searches']/sm['total_searches']*100:.1f}%)")
            print(f"   Avg time: {sm['avg_search_time']:.3f}s")
            print(f"   Fastest: {sm['fastest_search']:.3f}s")
            print(f"   Slowest: {sm['slowest_search']:.3f}s")
        else:
            print("   No searches yet")

        # component breakdown
        if summary['component_breakdown']:
            print(f"\nComponent breakdown:")
            for name, metrics in summary['component_breakdown'].items():
                print(f"   {name}:")
                print(f"      Avg: {metrics['avg_time']}s | Calls: {metrics['total_calls']} | "
                      f"Trend: {metrics['trend']}")
        else:
            print(f"\nNo component data yet")

        # bottlenecks
        if summary['bottlenecks']:
            print(f"\nBottlenecks detected:")
            for bn in summary['bottlenecks']:
                print(f"   {bn['component']}: {bn['avg_time']}s avg (severity: {bn['severity']}/100)")
        else:
            print(f"\nNo bottlenecks detected")

        # recommendations
        if summary['recommendations']:
            print(f"\nRecommendations:")
            for rec in summary['recommendations']:
                print(f"   {rec}")
        else:
            print(f"\nNo recommendations - system running well")

    def export_json(self) -> str:
        """Export metrics to json"""
        import json
        summary = self.get_summary()
        return json.dumps(summary, indent=2)

    def export_csv(self) -> str:
        """Export components to csv"""
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)

        # header
        writer.writerow(['component', 'avg time (s)', 'total calls', 'min time', 'max time',
                        'trend', 'error rate (%)', 'severity'])

        # data
        breakdown = self.get_component_breakdown()
        for name, metrics in breakdown.items():
            writer.writerow([
                name,
                metrics['avg_time'],
                metrics['total_calls'],
                metrics['min_time'],
                metrics['max_time'],
                metrics['trend'],
                metrics['error_rate'],
                ''  # severity only for bottlenecks
            ])

        return output.getvalue()


class track_performance:
    """
    Context manager for automatic performance tracking

    usage:
        with track_performance(monitor, "componentname"):
            # your code
            pass
    """

    def __init__(self, monitor: PerformanceMonitor, component_name: str):
        self.monitor = monitor
        self.component_name = component_name
        self.start_time = None
        self.success = True

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = time.time() - self.start_time

        if exc_type is not None:
            self.success = False

        self.monitor.track_component(self.component_name, elapsed, self.success)

        # don't suppress exceptions
        return False


if __name__ == "__main__":
    # demo usage
    print("Performance monitoring demo")

    monitor = PerformanceMonitor()

    # simulate some component calls
    import random

    for i in range(10):
        # simulate prefilter
        with track_performance(monitor, "PreFilter"):
            time.sleep(random.uniform(0.1, 0.3))

        # simulate bm25
        with track_performance(monitor, "BM25"):
            time.sleep(random.uniform(0.2, 0.5))

        # simulate dense
        with track_performance(monitor, "Dense"):
            time.sleep(random.uniform(0.3, 0.7))

        # track full search
        monitor.track_search(random.uniform(0.8, 1.5), success=True)

    # print summary
    monitor.print_summary()

    # export json
    print("\nJson export:")
    print(monitor.export_json()[:500] + "...")