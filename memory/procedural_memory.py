"""
Procedural Memory Manager

Manages learned heuristics for retry strategy selection.
This is intelligence that improves over time through experience.
"""

import json
import logging
import mysql.connector
from mysql.connector import Error
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from orchestrator.retry_schemas import FailureType, RetryStrategy

logger = logging.getLogger(__name__)


@dataclass
class Heuristic:
    """
    A learned procedural memory heuristic.

    Represents: "When this kind of task fails in this way, this strategy works."

    Now enriched with introspection insights for deeper understanding.
    """
    id: int
    context_type: str
    failure_type: FailureType
    effective_strategy: RetryStrategy
    confidence_score: float
    usage_count: int
    success_count: int
    failure_count: int
    last_applied_at: Optional[datetime]
    last_success_at: Optional[datetime]
    notes: Optional[str]
    # Introspection fields
    root_cause: Optional[str] = None
    inefficiencies: Optional[List[str]] = None
    surprises: Optional[List[str]] = None
    generalizable_lesson: Optional[str] = None
    insight_confidence: Optional[float] = None

    @property
    def success_rate(self) -> float:
        """Calculate success rate from usage."""
        if self.usage_count == 0:
            return 0.0
        return self.success_count / self.usage_count

    @property
    def has_insights(self) -> bool:
        """Check if this heuristic has introspection insights."""
        return self.root_cause is not None or self.generalizable_lesson is not None

    def __repr__(self) -> str:
        insight_marker = " [+insights]" if self.has_insights else ""
        return (
            f"Heuristic(context={self.context_type}, "
            f"failure={self.failure_type.value}, "
            f"strategy={self.effective_strategy.value}, "
            f"confidence={self.confidence_score:.2f}{insight_marker})"
        )


class ProceduralMemoryManager:
    """
    Manages procedural memory - learned heuristics for problem-solving.

    Core principle: Store PATTERNS, not DETAILS.
    - YES: "filesystem tasks with incorrect_assumptions → use verification_first"
    - NO: "when README.md not found, list directory first"

    This memory is:
    - Deterministic (SQL query, no LLM)
    - Fast (indexed lookups)
    - Inspectable (human-readable SQL table)
    - Editable (can manually adjust heuristics)
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize procedural memory manager.

        Args:
            config: Memory configuration dict
        """
        self.host = config['mysql_host']
        self.database = config['mysql_database']
        self.user = config['mysql_user']
        self.password = config['mysql_password']

        # Confidence thresholds
        self.min_confidence = config.get('procedural_min_confidence', 0.4)
        self.confidence_increment = 0.1  # Boost on success
        self.confidence_decrement = 0.2  # Penalty on failure

        # Auto-decay settings
        self.auto_decay_enabled = config.get('procedural_auto_decay', True)
        self.decay_days_threshold = config.get('procedural_decay_days', 7)
        self.decay_amount_per_day = config.get('procedural_decay_amount', 0.01)

        # Adaptive learning
        self.use_adaptive_thresholds = config.get('procedural_adaptive', True)
        self.pattern_matching = config.get('procedural_pattern_matching', True)

    def _get_connection(self):
        """Get MySQL connection."""
        return mysql.connector.connect(
            host=self.host,
            database=self.database,
            user=self.user,
            password=self.password
        )

    def query_heuristics(
        self,
        context_type: str,
        failure_type: FailureType,
        min_confidence: Optional[float] = None
    ) -> List[Heuristic]:
        """
        Query for applicable heuristics with intelligent matching.

        Features:
        - Automatic confidence decay for stale heuristics
        - Adaptive confidence thresholds based on success rate
        - Pattern matching for similar contexts

        Args:
            context_type: Task context ('filesystem', 'web_retrieval', etc.)
            failure_type: How the task failed
            min_confidence: Minimum confidence threshold (uses default if None)

        Returns:
            List of matching heuristics, sorted by confidence (highest first)
        """
        # Auto-decay stale heuristics before querying
        if self.auto_decay_enabled:
            self._auto_decay()

        if min_confidence is None:
            min_confidence = self.min_confidence

        connection = self._get_connection()
        cursor = connection.cursor(dictionary=True)

        try:
            # Exact match first
            query = """
            SELECT *
            FROM procedural_memory
            WHERE context_type = %s
              AND failure_type = %s
              AND confidence_score >= %s
            ORDER BY confidence_score DESC, success_count DESC
            """

            cursor.execute(query, (context_type, failure_type.value, min_confidence))
            exact_matches = cursor.fetchall()

            # Pattern matching: also check general context if enabled
            pattern_matches = []
            if self.pattern_matching and not exact_matches and context_type != 'general':
                cursor.execute(query, ('general', failure_type.value, min_confidence))
                pattern_matches = cursor.fetchall()

            all_rows = exact_matches + pattern_matches
            heuristics = [self._row_to_heuristic(row) for row in all_rows]

            # Adaptive filtering: boost high-success-rate heuristics
            if self.use_adaptive_thresholds:
                heuristics = self._apply_adaptive_filtering(heuristics, min_confidence)

            logger.debug(
                f"Found {len(exact_matches)} exact + {len(pattern_matches)} pattern "
                f"matches for {context_type}/{failure_type.value}"
            )

            return heuristics

        except Error as e:
            logger.error(f"Error querying heuristics: {e}")
            return []

        finally:
            cursor.close()
            connection.close()

    def _auto_decay(self) -> None:
        """Automatically decay confidence for stale heuristics."""
        try:
            connection = self._get_connection()
            cursor = connection.cursor()

            query = """
            UPDATE procedural_memory
            SET
                confidence_score = GREATEST(0.0, confidence_score - (
                    DATEDIFF(NOW(), last_applied_at) * %s
                )),
                updated_at = NOW()
            WHERE last_applied_at IS NOT NULL
              AND DATEDIFF(NOW(), last_applied_at) > %s
              AND confidence_score > 0.0
            """

            cursor.execute(query, (self.decay_amount_per_day, self.decay_days_threshold))
            connection.commit()

            if cursor.rowcount > 0:
                logger.debug(f"Auto-decayed {cursor.rowcount} stale heuristics")

        except Error as e:
            logger.error(f"Error in auto-decay: {e}")
        finally:
            cursor.close()
            connection.close()

    def _apply_adaptive_filtering(
        self,
        heuristics: List[Heuristic],
        base_confidence: float
    ) -> List[Heuristic]:
        """
        Apply adaptive filtering based on success rate.

        High success rate heuristics are kept even if confidence is lower.
        Low success rate heuristics need higher confidence.
        """
        filtered = []
        for h in heuristics:
            # Calculate adaptive threshold
            success_rate = h.success_rate if h.usage_count >= 3 else 0.0

            # High success rate (>80%) → lower confidence requirement
            if success_rate >= 0.8 and h.confidence_score >= base_confidence * 0.7:
                filtered.append(h)
            # Medium success rate (50-80%) → normal threshold
            elif success_rate >= 0.5 and h.confidence_score >= base_confidence:
                filtered.append(h)
            # Low success rate (<50%) → higher confidence requirement
            elif success_rate < 0.5 and h.confidence_score >= base_confidence * 1.2:
                filtered.append(h)
            # Not enough data yet → use base threshold
            elif h.usage_count < 3 and h.confidence_score >= base_confidence:
                filtered.append(h)

        return filtered

    def record_success(
        self,
        context_type: str,
        failure_type: FailureType,
        strategy: RetryStrategy,
        notes: Optional[str] = None,
        introspection: Optional[Any] = None  # IntrospectionInsight
    ) -> None:
        """
        Record a successful retry strategy.

        Creates new heuristic or updates existing one with confidence boost.
        Now optionally enriched with introspection insights.

        Args:
            context_type: Task context
            failure_type: How it failed before retry
            strategy: Strategy that succeeded
            notes: Optional abstract description (NO specifics!)
            introspection: Optional IntrospectionInsight from post-task reflection
        """
        connection = self._get_connection()
        cursor = connection.cursor()

        try:
            # Prepare introspection data if provided
            root_cause = None
            inefficiencies_json = None
            surprises_json = None
            generalizable_lesson = None
            insight_confidence = None

            if introspection:
                root_cause = introspection.root_cause
                inefficiencies_json = json.dumps(introspection.inefficiencies) if introspection.inefficiencies else None
                surprises_json = json.dumps(introspection.surprises) if introspection.surprises else None
                generalizable_lesson = introspection.generalizable_lesson
                insight_confidence = introspection.confidence

            # Try to update existing heuristic
            update_query = """
            UPDATE procedural_memory
            SET
                confidence_score = LEAST(1.0, confidence_score + %s),
                usage_count = usage_count + 1,
                success_count = success_count + 1,
                last_applied_at = NOW(),
                last_success_at = NOW(),
                updated_at = NOW()
            """ + ("""
                , root_cause = %s,
                  inefficiencies = %s,
                  surprises = %s,
                  generalizable_lesson = %s,
                  insight_confidence = %s
            """ if introspection else "") + """
            WHERE context_type = %s
              AND failure_type = %s
              AND effective_strategy = %s
            """

            params = [self.confidence_increment]
            if introspection:
                params.extend([root_cause, inefficiencies_json, surprises_json,
                              generalizable_lesson, insight_confidence])
            params.extend([context_type, failure_type.value, strategy.value])

            cursor.execute(update_query, tuple(params))

            if cursor.rowcount == 0:
                # No existing heuristic, create new one
                if introspection:
                    insert_query = """
                    INSERT INTO procedural_memory
                    (context_type, failure_type, effective_strategy, confidence_score,
                     usage_count, success_count, failure_count, last_applied_at,
                     last_success_at, notes, root_cause, inefficiencies, surprises,
                     generalizable_lesson, insight_confidence)
                    VALUES (%s, %s, %s, 0.5, 1, 1, 0, NOW(), NOW(), %s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(insert_query, (
                        context_type, failure_type.value, strategy.value, notes,
                        root_cause, inefficiencies_json, surprises_json,
                        generalizable_lesson, insight_confidence
                    ))
                else:
                    insert_query = """
                    INSERT INTO procedural_memory
                    (context_type, failure_type, effective_strategy, confidence_score,
                     usage_count, success_count, failure_count, last_applied_at,
                     last_success_at, notes)
                    VALUES (%s, %s, %s, 0.5, 1, 1, 0, NOW(), NOW(), %s)
                    """
                    cursor.execute(insert_query, (
                        context_type, failure_type.value, strategy.value, notes
                    ))

                insight_marker = " [+insights]" if introspection else ""
                logger.info(
                    f"Created new heuristic{insight_marker}: {context_type}/{failure_type.value} → "
                    f"{strategy.value}"
                )
            else:
                insight_marker = " [+insights]" if introspection else ""
                logger.info(
                    f"Boosted heuristic{insight_marker}: {context_type}/{failure_type.value} → "
                    f"{strategy.value} (+{self.confidence_increment})"
                )

            connection.commit()

        except Error as e:
            connection.rollback()
            logger.error(f"Error recording success: {e}")

        finally:
            cursor.close()
            connection.close()

    def record_failure(
        self,
        heuristic_id: int
    ) -> None:
        """
        Record that a heuristic failed when applied.

        Decreases confidence and increments failure count.

        Args:
            heuristic_id: ID of the heuristic that failed
        """
        connection = self._get_connection()
        cursor = connection.cursor()

        try:
            query = """
            UPDATE procedural_memory
            SET
                confidence_score = GREATEST(0.0, confidence_score - %s),
                usage_count = usage_count + 1,
                failure_count = failure_count + 1,
                last_applied_at = NOW(),
                updated_at = NOW()
            WHERE id = %s
            """

            cursor.execute(query, (self.confidence_decrement, heuristic_id))
            connection.commit()

            logger.info(f"Penalized heuristic {heuristic_id} (-{self.confidence_decrement})")

        except Error as e:
            connection.rollback()
            logger.error(f"Error recording failure: {e}")

        finally:
            cursor.close()
            connection.close()

    def decay_confidence(
        self,
        days_threshold: int = 7,
        decay_amount: float = 0.01
    ) -> int:
        """
        Decay confidence for heuristics not recently used.

        Should be run periodically (e.g., daily cron).

        Args:
            days_threshold: Decay heuristics not used in this many days
            decay_amount: How much to decay per day

        Returns:
            Number of heuristics decayed
        """
        connection = self._get_connection()
        cursor = connection.cursor()

        try:
            query = """
            UPDATE procedural_memory
            SET
                confidence_score = GREATEST(0.0, confidence_score - %s),
                updated_at = NOW()
            WHERE last_applied_at IS NOT NULL
              AND DATEDIFF(NOW(), last_applied_at) > %s
              AND confidence_score > 0.0
            """

            cursor.execute(query, (decay_amount, days_threshold))
            connection.commit()

            count = cursor.rowcount
            logger.info(f"Decayed {count} heuristics by {decay_amount}")

            return count

        except Error as e:
            connection.rollback()
            logger.error(f"Error decaying confidence: {e}")
            return 0

        finally:
            cursor.close()
            connection.close()

    def prune_low_confidence(
        self,
        threshold: float = 0.1
    ) -> int:
        """
        Delete heuristics below confidence threshold.

        Args:
            threshold: Delete heuristics below this confidence

        Returns:
            Number of heuristics deleted
        """
        connection = self._get_connection()
        cursor = connection.cursor()

        try:
            query = """
            DELETE FROM procedural_memory
            WHERE confidence_score < %s
            """

            cursor.execute(query, (threshold,))
            connection.commit()

            count = cursor.rowcount
            logger.info(f"Pruned {count} low-confidence heuristics")

            return count

        except Error as e:
            connection.rollback()
            logger.error(f"Error pruning heuristics: {e}")
            return 0

        finally:
            cursor.close()
            connection.close()

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive procedural memory statistics and learning insights.

        Returns:
            Dict with detailed stats about stored heuristics and learning progress
        """
        connection = self._get_connection()
        cursor = connection.cursor(dictionary=True)

        try:
            # Total heuristics
            cursor.execute("SELECT COUNT(*) as total FROM procedural_memory")
            total = cursor.fetchone()['total']

            # By context type
            cursor.execute("""
                SELECT context_type, COUNT(*) as count
                FROM procedural_memory
                GROUP BY context_type
                ORDER BY count DESC
            """)
            by_context = {row['context_type']: row['count'] for row in cursor.fetchall()}

            # Average confidence
            cursor.execute("SELECT AVG(confidence_score) as avg_conf FROM procedural_memory")
            avg_conf = cursor.fetchone()['avg_conf'] or 0.0

            # Confidence distribution
            cursor.execute("""
                SELECT
                    SUM(CASE WHEN confidence_score >= 0.8 THEN 1 ELSE 0 END) as very_high,
                    SUM(CASE WHEN confidence_score >= 0.6 AND confidence_score < 0.8 THEN 1 ELSE 0 END) as high,
                    SUM(CASE WHEN confidence_score >= 0.4 AND confidence_score < 0.6 THEN 1 ELSE 0 END) as medium,
                    SUM(CASE WHEN confidence_score < 0.4 THEN 1 ELSE 0 END) as low
                FROM procedural_memory
            """)
            conf_dist = cursor.fetchone()

            # Success metrics
            cursor.execute("""
                SELECT
                    SUM(usage_count) as total_applications,
                    SUM(success_count) as total_successes,
                    SUM(failure_count) as total_failures,
                    AVG(CASE WHEN usage_count > 0
                        THEN success_count / usage_count
                        ELSE 0 END) as avg_success_rate
                FROM procedural_memory
            """)
            success_metrics = cursor.fetchone()

            # Top performing heuristics
            cursor.execute("""
                SELECT
                    context_type,
                    failure_type,
                    effective_strategy,
                    confidence_score,
                    success_count,
                    usage_count,
                    (success_count / GREATEST(usage_count, 1)) as success_rate
                FROM procedural_memory
                WHERE usage_count >= 2
                ORDER BY success_rate DESC, confidence_score DESC
                LIMIT 5
            """)
            top_heuristics = cursor.fetchall()

            # Learning velocity (new heuristics in last 7/30 days)
            cursor.execute("""
                SELECT
                    SUM(CASE WHEN DATEDIFF(NOW(), created_at) <= 7 THEN 1 ELSE 0 END) as last_7_days,
                    SUM(CASE WHEN DATEDIFF(NOW(), created_at) <= 30 THEN 1 ELSE 0 END) as last_30_days
                FROM procedural_memory
            """)
            learning_velocity = cursor.fetchone()

            # Staleness check
            cursor.execute("""
                SELECT COUNT(*) as stale_count
                FROM procedural_memory
                WHERE last_applied_at IS NOT NULL
                  AND DATEDIFF(NOW(), last_applied_at) > %s
            """, (self.decay_days_threshold,))
            stale_count = cursor.fetchone()['stale_count']

            return {
                'total_heuristics': total,
                'by_context': by_context,
                'average_confidence': float(avg_conf),
                'confidence_distribution': {
                    'very_high (≥0.8)': conf_dist['very_high'] or 0,
                    'high (0.6-0.8)': conf_dist['high'] or 0,
                    'medium (0.4-0.6)': conf_dist['medium'] or 0,
                    'low (<0.4)': conf_dist['low'] or 0
                },
                'success_metrics': {
                    'total_applications': success_metrics['total_applications'] or 0,
                    'total_successes': success_metrics['total_successes'] or 0,
                    'total_failures': success_metrics['total_failures'] or 0,
                    'average_success_rate': float(success_metrics['avg_success_rate'] or 0.0)
                },
                'top_performers': [
                    {
                        'context': h['context_type'],
                        'failure': h['failure_type'],
                        'strategy': h['effective_strategy'],
                        'confidence': float(h['confidence_score']),
                        'success_rate': float(h['success_rate'])
                    }
                    for h in top_heuristics
                ],
                'learning_velocity': {
                    'new_last_7_days': learning_velocity['last_7_days'] or 0,
                    'new_last_30_days': learning_velocity['last_30_days'] or 0
                },
                'health': {
                    'stale_heuristics': stale_count,
                    'needs_pruning': stale_count > total * 0.2 if total > 0 else False
                }
            }

        except Error as e:
            logger.error(f"Error getting statistics: {e}")
            return {}

        finally:
            cursor.close()
            connection.close()

    def get_learning_insights(self) -> str:
        """
        Generate human-readable learning insights.

        Returns:
            Formatted string with learning analysis
        """
        stats = self.get_statistics()

        if not stats:
            return "No learning data available yet."

        insights = []
        insights.append("📊 PROCEDURAL MEMORY INSIGHTS")
        insights.append("="*50)

        # Overall status
        total = stats['total_heuristics']
        insights.append(f"\n🧠 Total Heuristics: {total}")

        if total == 0:
            insights.append("  No heuristics learned yet. System is in exploration mode.")
            return "\n".join(insights)

        # Confidence analysis
        avg_conf = stats['average_confidence']
        insights.append(f"📈 Average Confidence: {avg_conf:.2%}")

        dist = stats['confidence_distribution']
        insights.append(f"\nConfidence Distribution:")
        insights.append(f"  🌟 Very High: {dist['very_high (≥0.8)']} heuristics")
        insights.append(f"  ⭐ High: {dist['high (0.6-0.8)']} heuristics")
        insights.append(f"  ⚡ Medium: {dist['medium (0.4-0.6)']} heuristics")
        insights.append(f"  ⚠️  Low: {dist['low (<0.4)']} heuristics")

        # Success metrics
        metrics = stats['success_metrics']
        insights.append(f"\n✅ Success Metrics:")
        insights.append(f"  Applied: {metrics['total_applications']} times")
        insights.append(f"  Succeeded: {metrics['total_successes']} times")
        insights.append(f"  Failed: {metrics['total_failures']} times")
        insights.append(f"  Success Rate: {metrics['average_success_rate']:.1%}")

        # Top performers
        if stats['top_performers']:
            insights.append(f"\n🏆 Top Performing Strategies:")
            for i, perf in enumerate(stats['top_performers'][:3], 1):
                insights.append(
                    f"  {i}. {perf['context']}/{perf['failure']} → "
                    f"{perf['strategy']} ({perf['success_rate']:.0%} success)"
                )

        # Learning velocity
        velocity = stats['learning_velocity']
        insights.append(f"\n📚 Learning Activity:")
        insights.append(f"  Last 7 days: {velocity['new_last_7_days']} new heuristics")
        insights.append(f"  Last 30 days: {velocity['new_last_30_days']} new heuristics")

        # Health check
        health = stats['health']
        stale = health['stale_heuristics']
        if stale > 0:
            insights.append(f"\n⚠️  Health Warning:")
            insights.append(f"  {stale} stale heuristics (>{self.decay_days_threshold} days unused)")
            if health['needs_pruning']:
                insights.append(f"  Consider running prune_low_confidence() to clean up")

        # Learning maturity assessment
        if total >= 10 and avg_conf >= 0.6:
            insights.append(f"\n🎓 System Maturity: ADVANCED")
            insights.append(f"  Jarvis has developed strong problem-solving patterns!")
        elif total >= 5:
            insights.append(f"\n🌱 System Maturity: DEVELOPING")
            insights.append(f"  Jarvis is actively learning from experience.")
        else:
            insights.append(f"\n🐣 System Maturity: EARLY")
            insights.append(f"  Jarvis is just starting to build experience.")

        return "\n".join(insights)

    def _row_to_heuristic(self, row: Dict[str, Any]) -> Heuristic:
        """Convert database row to Heuristic object."""
        # Parse JSON fields
        inefficiencies = None
        surprises = None

        if row.get('inefficiencies'):
            try:
                inefficiencies = json.loads(row['inefficiencies']) if isinstance(row['inefficiencies'], str) else row['inefficiencies']
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"Failed to parse inefficiencies JSON for heuristic {row['id']}")

        if row.get('surprises'):
            try:
                surprises = json.loads(row['surprises']) if isinstance(row['surprises'], str) else row['surprises']
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"Failed to parse surprises JSON for heuristic {row['id']}")

        return Heuristic(
            id=row['id'],
            context_type=row['context_type'],
            failure_type=FailureType(row['failure_type']),
            effective_strategy=RetryStrategy(row['effective_strategy']),
            confidence_score=float(row['confidence_score']),
            usage_count=row['usage_count'] or 0,
            success_count=row['success_count'] or 0,
            failure_count=row['failure_count'] or 0,
            last_applied_at=row.get('last_applied_at'),
            last_success_at=row.get('last_success_at'),
            notes=row.get('notes'),
            root_cause=row.get('root_cause'),
            inefficiencies=inefficiencies,
            surprises=surprises,
            generalizable_lesson=row.get('generalizable_lesson'),
            insight_confidence=float(row['insight_confidence']) if row.get('insight_confidence') else None
        )
