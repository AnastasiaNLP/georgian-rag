"""
Performance dashboard - visualization & reporting for rag system

functions:
- html reports with charts
- real-time metrics
- export to json/csv
- comparison between runs
- cache analytics
"""

import json
import time
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class CacheStats:
    """Statistics for one cache"""
    cache_name: str
    hits: int = 0
    misses: int = 0
    total_requests: int = 0
    hit_rate: float = 0.0
    size: int = 0
    max_size: Optional[int] = None
    evictions: int = 0
    memory_mb: float = 0.0
    avg_lookup_time: float = 0.0

    def calculate_hit_rate(self):
        """Recalculate hit rate"""
        if self.total_requests > 0:
            self.hit_rate = (self.hits / self.total_requests) * 100
        else:
            self.hit_rate = 0.0


class CacheAnalytics:
    """
    Centralized analytics for all caches in rag system

    tracks:
    - translation cache (multilingualmanager)
    - prefilter cache (prefilterengine)
    - bm25 cache (bm25engine)
    - dense search cache (densesearchengine)
    - redis cache
    """

    def __init__(self):
        self.caches: Dict[str, CacheStats] = {}
        self.start_time = time.time()

        # thresholds for alerts
        self.low_hit_rate_threshold = 30.0  # %
        self.high_memory_threshold = 500.0  # mb

        logger.info("cacheanalytics initialized")

    def register_cache(self, cache_name: str, max_size: Optional[int] = None):
        """
        Register cache for tracking

        args:
            cache_name: cache name
            max_size: maximum size (if any)
        """
        if cache_name not in self.caches:
            self.caches[cache_name] = CacheStats(
                cache_name=cache_name,
                max_size=max_size
            )
            logger.info(f"registered cache: {cache_name}")

    def update_cache_stats(self, cache_name: str, stats_dict: Dict[str, Any]):
        """
        Update cache statistics

        args:
            cache_name: cache name
            stats_dict: dictionary with statistics (hits, misses, size, etc.)
        """
        if cache_name not in self.caches:
            self.register_cache(cache_name)

        cache = self.caches[cache_name]

        # update fields from dictionary
        if 'hits' in stats_dict or 'cache_hits' in stats_dict:
            cache.hits = stats_dict.get('hits', stats_dict.get('cache_hits', 0))

        if 'misses' in stats_dict or 'cache_misses' in stats_dict:
            cache.misses = stats_dict.get('misses', stats_dict.get('cache_misses', 0))

        if 'total_requests' in stats_dict:
            cache.total_requests = stats_dict['total_requests']
        else:
            cache.total_requests = cache.hits + cache.misses

        if 'size' in stats_dict or 'cache_size' in stats_dict:
            cache.size = stats_dict.get('size', stats_dict.get('cache_size', 0))

        if 'evictions' in stats_dict:
            cache.evictions = stats_dict['evictions']

        if 'memory_mb' in stats_dict:
            cache.memory_mb = stats_dict['memory_mb']

        if 'avg_lookup_time' in stats_dict:
            cache.avg_lookup_time = stats_dict['avg_lookup_time']

        # recalculate hit rate
        cache.calculate_hit_rate()

    def collect_all_cache_stats(self, rag_system) -> Dict[str, CacheStats]:
        """
        Collect statistics from all caches in rag system

        args:
            rag_system: rag system instance
        """

        # translation cache (multilingualmanager)
        if hasattr(rag_system, 'multilingual_manager') and rag_system.multilingual_manager:
            try:
                ml_stats = rag_system.multilingual_manager.get_cache_stats()
                self.update_cache_stats('translation_cache', {
                    'hits': ml_stats.get('translation_hits', 0),
                    'misses': ml_stats.get('translation_misses', 0),
                    'total_requests': ml_stats.get('total_cache_requests', 0),
                    'size': 0
                })
            except Exception as e:
                logger.debug(f"could not collect translation cache stats: {e}")

        # bm25 cache
        if hasattr(rag_system, 'hybrid_search') and rag_system.hybrid_search:
            try:
                if hasattr(rag_system.hybrid_search, 'bm25_engine'):
                    bm25_stats = rag_system.hybrid_search.bm25_engine.get_cache_stats()
                    self.update_cache_stats('bm25_cache', bm25_stats)
            except Exception as e:
                logger.debug(f"could not collect bm25 cache stats: {e}")

        # dense search cache
        if hasattr(rag_system, 'hybrid_search') and rag_system.hybrid_search:
            try:
                if hasattr(rag_system.hybrid_search, 'dense_engine'):
                    dense_stats = rag_system.hybrid_search.dense_engine.get_cache_stats()
                    self.update_cache_stats('dense_cache', dense_stats)
            except Exception as e:
                logger.debug(f"could not collect dense cache stats: {e}")

        # redis cache
        if hasattr(rag_system, 'cache_manager') and rag_system.cache_manager:
            try:
                # if there's a method to get statistics
                if hasattr(rag_system.cache_manager, 'get_stats'):
                    redis_stats = rag_system.cache_manager.get_stats()
                    self.update_cache_stats('redis_cache', redis_stats)
            except Exception as e:
                logger.debug(f"could not collect redis cache stats: {e}")

        return self.caches

    def get_overall_stats(self) -> Dict[str, Any]:
        """Get overall statistics for all caches"""
        total_hits = sum(cache.hits for cache in self.caches.values())
        total_misses = sum(cache.misses for cache in self.caches.values())
        total_requests = total_hits + total_misses
        overall_hit_rate = (total_hits / total_requests * 100) if total_requests > 0 else 0

        total_size = sum(cache.size for cache in self.caches.values())
        total_memory = sum(cache.memory_mb for cache in self.caches.values())

        return {
            'total_caches': len(self.caches),
            'total_hits': total_hits,
            'total_misses': total_misses,
            'total_requests': total_requests,
            'overall_hit_rate': round(overall_hit_rate, 2),
            'total_cache_size': total_size,
            'total_memory_mb': round(total_memory, 2),
            'uptime_seconds': round(time.time() - self.start_time, 2)
        }

    def identify_inefficient_caches(self) -> List[Dict]:
        """
        Identify inefficient caches

        returns:
            list of caches with low hit rate or other issues
        """
        inefficient = []

        for cache in self.caches.values():
            issues = []

            # low hit rate
            if cache.total_requests > 10 and cache.hit_rate < self.low_hit_rate_threshold:
                issues.append(f"low hit rate: {cache.hit_rate:.1f}%")

            # high memory usage
            if cache.memory_mb > self.high_memory_threshold:
                issues.append(f"high memory usage: {cache.memory_mb:.1f}mb")

            # many evictions
            if cache.evictions > cache.hits * 0.5:
                issues.append(f"high eviction rate: {cache.evictions} evictions")

            # cache full
            if cache.max_size and cache.size >= cache.max_size:
                issues.append(f"cache full: {cache.size}/{cache.max_size}")

            if issues:
                inefficient.append({
                    'cache_name': cache.cache_name,
                    'hit_rate': round(cache.hit_rate, 2),
                    'issues': issues,
                    'severity': len(issues) * 20
                })

        # sort by severity
        inefficient.sort(key=lambda x: x['severity'], reverse=True)

        return inefficient

    def get_recommendations(self) -> List[str]:
        """Get cache optimization recommendations"""
        recommendations = []
        inefficient = self.identify_inefficient_caches()

        for cache_info in inefficient:
            cache_name = cache_info['cache_name']
            hit_rate = cache_info['hit_rate']

            if hit_rate < 30:
                recommendations.append(
                    f"{cache_name}: very low hit rate ({hit_rate}%). "
                    f"consider: increasing cache size, adjusting ttl, or reviewing cache key strategy."
                )
            elif hit_rate < 50:
                recommendations.append(
                    f"{cache_name}: low hit rate ({hit_rate}%). "
                    f"consider: analyzing access patterns or increasing cache size."
                )

            for issue in cache_info['issues']:
                if 'memory' in issue.lower():
                    recommendations.append(
                        f"{cache_name}: high memory usage. "
                        f"consider: reducing cache size or implementing lru eviction."
                    )
                elif 'full' in issue.lower():
                    recommendations.append(
                        f"{cache_name}: cache is full. "
                        f"consider: increasing max_size or implementing better eviction policy."
                    )
                elif 'eviction' in issue.lower():
                    recommendations.append(
                        f"{cache_name}: high eviction rate. "
                        f"consider: increasing cache size to reduce churn."
                    )

        # general recommendations
        overall = self.get_overall_stats()
        if overall['overall_hit_rate'] < 50:
            recommendations.append(
                f"overall hit rate is low ({overall['overall_hit_rate']:.1f}%). "
                f"consider: reviewing caching strategy across all components."
            )

        if overall['total_memory_mb'] > 1000:
            recommendations.append(
                f"total cache memory is high ({overall['total_memory_mb']:.1f}mb). "
                f"consider: implementing memory limits or periodic cleanup."
            )

        return recommendations

    def get_cache_efficiency_score(self) -> float:
        """
        Calculate overall cache efficiency score (0-100)
        """
        overall = self.get_overall_stats()
        inefficient = self.identify_inefficient_caches()

        # base score from hit rate
        score = overall['overall_hit_rate']

        # penalties for issues
        score -= len(inefficient) * 5

        # bonuses
        if overall['overall_hit_rate'] > 80:
            score += 10

        return max(0, min(100, score))

    def print_summary(self):
        """Print cache summary"""
        overall = self.get_overall_stats()

        print("\nCache analytics summary")

        # overall stats
        print(f"\nOverall statistics:")
        print(f"   Total caches: {overall['total_caches']}")
        print(f"   Total requests: {overall['total_requests']}")
        print(f"   Total hits: {overall['total_hits']}")
        print(f"   Total misses: {overall['total_misses']}")
        print(f"   Overall hit rate: {overall['overall_hit_rate']}%")
        print(f"   Total cache size: {overall['total_cache_size']} items")
        print(f"   Total memory: {overall['total_memory_mb']}mb")

        # efficiency score
        efficiency = self.get_cache_efficiency_score()
        print(f"\nCache efficiency score: {efficiency:.1f}/100")

        # per-cache breakdown
        if self.caches:
            print(f"\nCache breakdown:")
            for cache_name, cache in sorted(self.caches.items(),
                                            key=lambda x: x[1].hit_rate,
                                            reverse=True):
                print(f"   {cache_name}:")
                print(f"      Hit rate: {cache.hit_rate:.1f}% ({cache.hits}/{cache.total_requests})")
                print(f"      Size: {cache.size} items" +
                      (f" / {cache.max_size}" if cache.max_size else ""))
                if cache.memory_mb > 0:
                    print(f"      Memory: {cache.memory_mb:.2f}mb")
                if cache.evictions > 0:
                    print(f"      Evictions: {cache.evictions}")
        else:
            print(f"\nNo caches registered yet")

        # inefficient caches
        inefficient = self.identify_inefficient_caches()
        if inefficient:
            print(f"\nInefficient caches:")
            for cache_info in inefficient:
                print(f"   {cache_info['cache_name']} (severity: {cache_info['severity']}/100)")
                for issue in cache_info['issues']:
                    print(f"      - {issue}")
        else:
            print(f"\nAll caches operating efficiently")

        # recommendations
        recommendations = self.get_recommendations()
        if recommendations:
            print(f"\nRecommendations:")
            for rec in recommendations:
                print(f"   {rec}")

    def reset(self):
        """reset all statistics"""
        self.caches.clear()
        self.start_time = time.time()
        logger.info("cacheanalytics reset")


class PerformanceDashboard:
    """
    Visualization and reporting for performance

    functions:
    - html reports with charts
    - real-time metrics
    - export to json/csv
    - comparison between runs
    """

    def __init__(self, performance_monitor, cache_analytics: CacheAnalytics):
        """
        Args:
            performance_monitor: performancemonitor instance
            cache_analytics: cacheanalytics instance
        """
        self.perf_monitor = performance_monitor
        self.cache_analytics = cache_analytics
        self.reports_history = []

        logger.info("performancedashboard initialized")

    def generate_html_report(self, title: str = "RAG Performance Report") -> str:
        """
        Generate html report

        returns:
            html string with full report
        """
        perf_summary = self.perf_monitor.get_summary()
        cache_overall = self.cache_analytics.get_overall_stats()

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # define class for health status
        health_class = ''
        if perf_summary['health_status'] == 'critical':
            health_class = 'critical'
        elif perf_summary['health_status'] == 'warning':
            health_class = 'warning'

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 20px;
            background: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #34495e;
            margin-top: 30px;
        }}
        .metric-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .metric-card {{
            background: #ecf0f1;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #3498db;
        }}
        .metric-card.warning {{
            border-left-color: #f39c12;
        }}
        .metric-card.critical {{
            border-left-color: #e74c3c;
        }}
        .metric-label {{
            font-size: 0.9em;
            color: #7f8c8d;
            margin-bottom: 5px;
        }}
        .metric-value {{
            font-size: 1.8em;
            font-weight: bold;
            color: #2c3e50;
        }}
        .status-badge {{
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.9em;
            font-weight: bold;
        }}
        .status-healthy {{
            background: #2ecc71;
            color: white;
        }}
        .status-warning {{
            background: #f39c12;
            color: white;
        }}
        .status-critical {{
            background: #e74c3c;
            color: white;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background: #34495e;
            color: white;
        }}
        tr:hover {{
            background: #f5f5f5;
        }}
        .recommendation {{
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin: 10px 0;
            border-radius: 4px;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            color: #7f8c8d;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{title}</h1>
        <p class="footer">Generated: {timestamp}</p>

        <!-- health status -->
        <div class="metric-card {health_class}">
            <div class="metric-label">System health</div>
            <div class="metric-value">
                <span class="status-badge status-{perf_summary['health_status']}">
                    {perf_summary['health_status'].upper()}
                </span>
            </div>
        </div>

        <!-- key metrics -->
        <h2>Key metrics</h2>
        <div class="metric-grid">
            <div class="metric-card">
                <div class="metric-label">Total searches</div>
                <div class="metric-value">{perf_summary['search_metrics']['total_searches']}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Avg search time</div>
                <div class="metric-value">{perf_summary['search_metrics']['avg_search_time']:.3f}s</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Cache hit rate</div>
                <div class="metric-value">{cache_overall['overall_hit_rate']:.1f}%</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Uptime</div>
                <div class="metric-value">{perf_summary['uptime_seconds']:.0f}s</div>
            </div>
        </div>

        <!-- component performance -->
        <h2>Component performance</h2>
        <table>
            <tr>
                <th>Component</th>
                <th>Avg time</th>
                <th>Calls</th>
                <th>Total time</th>
                <th>Trend</th>
            </tr>
"""

        # add component rows
        for name, metrics in perf_summary['component_breakdown'].items():
            html += f"""
            <tr>
                <td>{name}</td>
                <td>{metrics['avg_time']}s</td>
                <td>{metrics['total_calls']}</td>
                <td>{metrics['total_time']}s</td>
                <td>{metrics['trend']}</td>
            </tr>
"""

        html += """
        </table>

        <!-- cache statistics -->
        <h2>Cache statistics</h2>
        <table>
            <tr>
                <th>Cache</th>
                <th>Hit rate</th>
                <th>Hits / total</th>
                <th>Size</th>
            </tr>
"""

        # add cache rows
        for cache_name, cache in self.cache_analytics.caches.items():
            hit_rate_class = 'critical' if cache.hit_rate < 40 else 'warning' if cache.hit_rate < 70 else ''
            html += f"""
            <tr class="{hit_rate_class}">
                <td>{cache_name}</td>
                <td>{cache.hit_rate:.1f}%</td>
                <td>{cache.hits} / {cache.total_requests}</td>
                <td>{cache.size}</td>
            </tr>
"""

        html += """
        </table>
"""

        # bottlenecks
        if perf_summary['bottlenecks']:
            html += """
        <h2>Bottlenecks detected</h2>
"""
            for bn in perf_summary['bottlenecks']:
                html += f"""
        <div class="recommendation">
            <strong>{bn['component']}</strong>: {bn['avg_time']}s average
            (severity: {bn['severity']}/100, trend: {bn['trend']})
        </div>
"""

        # recommendations
        all_recommendations = perf_summary['recommendations'] + self.cache_analytics.get_recommendations()
        if all_recommendations:
            html += """
        <h2>Optimization recommendations</h2>
"""
            for rec in all_recommendations:
                html += f"""
        <div class="recommendation">{rec}</div>
"""

        html += """
        <div class="footer">
            <p>This report was automatically generated by the rag performance monitoring system</p>
        </div>
    </div>
</body>
</html>
"""

        return html

    def save_html_report(self, filename: str = None) -> str:
        """
        Save html report to file

        args:
            filename: path to file (if none - generated automatically)

        returns:
            path to saved file
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"performance_report_{timestamp}.html"

        html = self.generate_html_report()

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html)

        logger.info(f"html report saved to: {filename}")
        return filename

    def export_to_json(self, filename: str = None) -> str:
        """
        Export metrics to json

        args:
            filename: path to file (optional)

        returns:
            json string
        """
        data = {
            'timestamp': datetime.now().isoformat(),
            'performance': self.perf_monitor.get_summary(),
            'cache': {
                'overall': self.cache_analytics.get_overall_stats(),
                'caches': {
                    name: {
                        'hits': cache.hits,
                        'misses': cache.misses,
                        'hit_rate': cache.hit_rate,
                        'size': cache.size,
                        'memory_mb': cache.memory_mb
                    }
                    for name, cache in self.cache_analytics.caches.items()
                }
            }
        }

        json_str = json.dumps(data, indent=2)

        if filename:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(json_str)
            logger.info(f"metrics exported to {filename}")

        return json_str

    def print_quick_stats(self):
        """Quick summary for console"""
        perf_summary = self.perf_monitor.get_summary()
        cache_overall = self.cache_analytics.get_overall_stats()

        print("\nQuick stats")

        status = perf_summary['health_status']

        print(f"Health: {status.upper()}")
        print(f"Searches: {perf_summary['search_metrics']['total_searches']} " +
              f"(avg {perf_summary['search_metrics']['avg_search_time']:.3f}s)")
        print(f"Cache hit rate: {cache_overall['overall_hit_rate']:.1f}%")
        print(f"Components: {len(perf_summary['component_breakdown'])}")

        if perf_summary['bottlenecks']:
            print(f"Bottlenecks: {len(perf_summary['bottlenecks'])}")

    def save_snapshot(self):
        """Save current snapshot for comparison"""
        snapshot = {
            'timestamp': time.time(),
            'performance': self.perf_monitor.get_summary(),
            'cache': self.cache_analytics.get_overall_stats()
        }
        self.reports_history.append(snapshot)
        logger.info(f"snapshot saved ({len(self.reports_history)} total)")
        return snapshot

    def compare_snapshots(self, snapshot1_idx: int = -2, snapshot2_idx: int = -1) -> Dict[str, Any]:
        """
        Compare two snapshots

        args:
            snapshot1_idx: index of first snapshot (default second to last)
            snapshot2_idx: index of second snapshot (default last)

        returns:
            dictionary with comparison results
        """
        if len(self.reports_history) < 2:
            logger.warning("need at least 2 snapshots to compare")
            return {}

        snap1 = self.reports_history[snapshot1_idx]
        snap2 = self.reports_history[snapshot2_idx]

        # compare search time
        search1 = snap1['performance']['search_metrics']
        search2 = snap2['performance']['search_metrics']

        avg_time_change = search2['avg_search_time'] - search1['avg_search_time']
        avg_time_change_pct = (avg_time_change / search1['avg_search_time'] * 100) if search1['avg_search_time'] > 0 else 0

        # compare cache hit rate
        cache1 = snap1['cache']
        cache2 = snap2['cache']

        hit_rate_change = cache2['overall_hit_rate'] - cache1['overall_hit_rate']

        # overall assessment of changes
        improvement_score = 0

        # search time improvement
        if avg_time_change < 0:
            improvement_score += 30
        elif avg_time_change > 0:
            improvement_score -= 30

        # cache hit rate improvement
        if hit_rate_change > 0:
            improvement_score += 20
        elif hit_rate_change < 0:
            improvement_score -= 20

        comparison = {
            'time_delta': round(snap2['timestamp'] - snap1['timestamp'], 2),
            'search_performance': {
                'avg_time_change': round(avg_time_change, 3),
                'avg_time_change_pct': round(avg_time_change_pct, 2),
                'total_searches_change': search2['total_searches'] - search1['total_searches']
            },
            'cache_performance': {
                'hit_rate_change': round(hit_rate_change, 2),
                'hit_rate_change_pct': round((hit_rate_change / cache1['overall_hit_rate'] * 100) if cache1['overall_hit_rate'] > 0 else 0, 2)
            },
            'improvement_score': improvement_score,
            'verdict': self._get_comparison_verdict(improvement_score)
        }

        return comparison

    def _get_comparison_verdict(self, score: int) -> str:
        """Get verdict by improvement_score"""
        if score > 20:
            return "significant improvement"
        elif score > 0:
            return "slight improvement"
        elif score == 0:
            return "no change"
        elif score > -20:
            return "slight degradation"
        else:
            return "significant degradation"

    def print_comparison(self, comparison: Dict[str, Any]):
        """Print comparison"""
        print("\nPerformance comparison")

        print(f"\nTime delta: {comparison['time_delta']:.1f}s")

        print(f"\nSearch performance:")
        sp = comparison['search_performance']
        print(f"   Avg time change: {sp['avg_time_change']:.3f}s ({sp['avg_time_change_pct']:+.1f}%)")
        print(f"   Total searches: +{sp['total_searches_change']}")

        print(f"\nCache performance:")
        cp = comparison['cache_performance']
        print(f"   Hit rate change: {cp['hit_rate_change']:+.1f}% ({cp['hit_rate_change_pct']:+.1f}%)")

        print(f"\nVerdict: {comparison['verdict']}")
        print(f"   Score: {comparison['improvement_score']}")


if __name__ == "__main__":
    # Demo usage
    print("Performance dashboard demo")

    # import necessary modules
    try:
        from performance_monitoring import PerformanceMonitor
    except ImportError:
        print("import performance_monitoring.py first")
        exit(1)

    # create instances
    monitor = PerformanceMonitor()
    cache_analytics = CacheAnalytics()
    dashboard = PerformanceDashboard(monitor, cache_analytics)

    # simulate some data
    import random

    for i in range(10):
        monitor.track_component("BM25", random.uniform(0.2, 0.5))
        monitor.track_component("Dense", random.uniform(0.3, 0.7))
        monitor.track_search(random.uniform(0.8, 1.5), success=True)

    # register and update caches
    cache_analytics.register_cache("bm25_cache", max_size=1000)
    cache_analytics.update_cache_stats("bm25_cache", {
        'hits': 80,
        'misses': 20,
        'size': 500
    })

    # print quick stats
    dashboard.print_quick_stats()

    # generate html report
    html_file = dashboard.save_html_report("demo_report.html")
    print(f"\nHtml report saved: {html_file}")

    # export json
    json_file = "demo_metrics.json"
    dashboard.export_to_json(json_file)
    print(f"Json metrics saved: {json_file}")