"""
Postgresql logger for georgian rag

Saves all queries and metrics to postgresql for:
- long-term analysis
- tracing
- debugging
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
import json
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager


Base = declarative_base()


class RequestLog(Base):
    """Log of requests to rag system"""
    __tablename__ = 'request_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    # query
    query = Column(Text, nullable=False)
    language = Column(String(10), index=True)
    top_k = Column(Integer)

    # response
    response = Column(Text)
    response_length = Column(Integer)
    num_sources = Column(Integer)

    # performance
    duration_total = Column(Float)  # seconds
    duration_search = Column(Float)
    duration_llm = Column(Float)

    # statuses
    status = Column(String(20), index=True)  # success, error
    error_message = Column(Text, nullable=True)
    error_type = Column(String(100), nullable=True)

    # cache
    cache_hit = Column(Boolean, default=False)
    cache_type = Column(String(50), nullable=True)

    # metadata (renamed from metadata - reserved word!)
    request_metadata = Column(JSON, nullable=True)


class CacheMetrics(Base):
    """Cache metrics"""
    __tablename__ = 'cache_metrics'

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    cache_type = Column(String(50), index=True)
    hit_rate = Column(Float)
    total_requests = Column(Integer)
    hits = Column(Integer)
    misses = Column(Integer)
    size_mb = Column(Float)


class SystemMetrics(Base):
    """System metrics"""
    __tablename__ = 'system_metrics'

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    active_requests = Column(Integer)
    total_requests_1h = Column(Integer)
    avg_response_time = Column(Float)
    error_rate = Column(Float)

    cpu_usage = Column(Float, nullable=True)
    memory_usage = Column(Float, nullable=True)


class PostgreSQLLogger:
    """
    Logger for saving metrics to postgresql
    """

    def __init__(self, connection_string: str):
        """
        Connection_string: postgresql://user:password@host:port/dbname
        """
        self.engine = create_engine(connection_string)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

    @contextmanager
    def get_session(self):
        """Context manager for session"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def log_request(
        self,
        query: str,
        language: str,
        response: Optional[str] = None,
        num_sources: int = 0,
        duration_total: float = 0.0,
        duration_search: float = 0.0,
        duration_llm: float = 0.0,
        status: str = 'success',
        error_message: Optional[str] = None,
        error_type: Optional[str] = None,
        cache_hit: bool = False,
        cache_type: Optional[str] = None,
        request_metadata: Optional[Dict] = None,
        top_k: int = 5
    ):
        """Log request"""
        with self.get_session() as session:
            log = RequestLog(
                query=query,
                language=language,
                top_k=top_k,
                response=response,
                response_length=len(response) if response else 0,
                num_sources=num_sources,
                duration_total=duration_total,
                duration_search=duration_search,
                duration_llm=duration_llm,
                status=status,
                error_message=error_message,
                error_type=error_type,
                cache_hit=cache_hit,
                cache_type=cache_type,
                request_metadata=request_metadata
            )
            session.add(log)

    def log_cache_metrics(
        self,
        cache_type: str,
        hit_rate: float,
        total_requests: int,
        hits: int,
        misses: int,
        size_mb: float = 0.0
    ):
        """Log cache metrics"""
        with self.get_session() as session:
            metrics = CacheMetrics(
                cache_type=cache_type,
                hit_rate=hit_rate,
                total_requests=total_requests,
                hits=hits,
                misses=misses,
                size_mb=size_mb
            )
            session.add(metrics)

    def log_system_metrics(
        self,
        active_requests: int,
        total_requests_1h: int,
        avg_response_time: float,
        error_rate: float,
        cpu_usage: Optional[float] = None,
        memory_usage: Optional[float] = None
    ):
        """Log system metrics"""
        with self.get_session() as session:
            metrics = SystemMetrics(
                active_requests=active_requests,
                total_requests_1h=total_requests_1h,
                avg_response_time=avg_response_time,
                error_rate=error_rate,
                cpu_usage=cpu_usage,
                memory_usage=memory_usage
            )
            session.add(metrics)

    def get_recent_requests(self, limit: int = 100) -> List[Dict]:
        """Get recent requests"""
        with self.get_session() as session:
            logs = session.query(RequestLog)\
                .order_by(RequestLog.timestamp.desc())\
                .limit(limit)\
                .all()

            return [
                {
                    'id': log.id,
                    'timestamp': log.timestamp.isoformat(),
                    'query': log.query,
                    'language': log.language,
                    'duration': log.duration_total,
                    'status': log.status,
                    'cache_hit': log.cache_hit
                }
                for log in logs
            ]

    def get_error_summary(self, hours: int = 24) -> Dict[str, int]:
        """Get error summary for last n hours"""
        from sqlalchemy import func
        from datetime import timedelta

        with self.get_session() as session:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)

            errors = session.query(
                RequestLog.error_type,
                func.count(RequestLog.id).label('count')
            ).filter(
                RequestLog.timestamp >= cutoff_time,
                RequestLog.status == 'error'
            ).group_by(RequestLog.error_type).all()

            return {error_type: count for error_type, count in errors}

    def get_performance_stats(self, hours: int = 24) -> Dict[str, Any]:
        """Get performance statistics"""
        from sqlalchemy import func
        from datetime import timedelta

        with self.get_session() as session:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)

            stats = session.query(
                func.count(RequestLog.id).label('total'),
                func.avg(RequestLog.duration_total).label('avg_duration'),
                func.max(RequestLog.duration_total).label('max_duration'),
                func.min(RequestLog.duration_total).label('min_duration'),
                func.sum(
                    func.cast(RequestLog.cache_hit, Integer)
                ).label('cache_hits')
            ).filter(
                RequestLog.timestamp >= cutoff_time
            ).first()

            total = stats.total or 0
            cache_hits = stats.cache_hits or 0

            return {
                'total_requests': total,
                'avg_duration': round(stats.avg_duration or 0, 2),
                'max_duration': round(stats.max_duration or 0, 2),
                'min_duration': round(stats.min_duration or 0, 2),
                'cache_hit_rate': round((cache_hits / total * 100) if total > 0 else 0, 2)
            }


# singleton instance
_logger_instance: Optional[PostgreSQLLogger] = None


def get_logger(connection_string: Optional[str] = None) -> PostgreSQLLogger:
    """Get singleton instance of logger"""
    global _logger_instance

    if _logger_instance is None:
        if connection_string is None:
            raise ValueError("connection string required for first initialization")
        _logger_instance = PostgreSQLLogger(connection_string)

    return _logger_instance