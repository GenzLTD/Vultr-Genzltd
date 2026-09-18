"""
Report Generator — Generate daily/weekly/monthly reports.
Migrated from old report_gen.py, adapted for Flask.
"""
from __future__ import annotations
import logging
from datetime import datetime
from pathlib import Path
from flask import current_app

logger = logging.getLogger("looma.report")


class ReportGenerator:
    """Generate summary reports from query logs and usage data."""

    def generate_report(self, report_type: str = "daily") -> Path:
        """Generate a report of the specified type.

        Args:
            report_type: 'daily', 'weekly', or 'monthly'

        Returns:
            Path to the generated report file
        """
        db = current_app._db
        now = datetime.now()

        # Gather data
        stats = self._gather_stats(db, report_type, now)

        # Generate report content
        content = self._format_report(report_type, stats, now)

        # Write to file
        report_dir = Path(current_app.config.get("DATABASE_PATH", "data/looma.db")).parent / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{report_type}_{now.strftime('%Y%m%d_%H%M')}.md"
        path = report_dir / filename
        path.write_text(content, encoding="utf-8")

        logger.info(f"Generated {report_type} report: {path}")
        return path

    def generate_daily(self) -> Path:
        return self.generate_report("daily")

    def generate_weekly(self) -> Path:
        return self.generate_report("weekly")

    def generate_monthly(self) -> Path:
        return self.generate_report("monthly")

    def _gather_stats(self, db, report_type: str, now: datetime) -> dict:
        """Gather statistics for the report."""
        stats = {}
        try:
            # Total queries
            with db.get_conn() as conn:
                row = conn.execute("SELECT COUNT(*) FROM query_logs").fetchone()
                stats["total_queries"] = row[0] if row else 0

                # Today's queries
                row = conn.execute(
                    "SELECT COUNT(*) FROM query_logs WHERE date(created_at) = date('now')"
                ).fetchone()
                stats["today_queries"] = row[0] if row else 0

                # Intent distribution
                rows = conn.execute(
                    "SELECT intent_label, COUNT(*) as cnt FROM query_logs WHERE intent_label IS NOT NULL GROUP BY intent_label ORDER BY cnt DESC LIMIT 10"
                ).fetchall()
                stats["intent_distribution"] = {r[0]: r[1] for r in rows}

                # Average response time
                row = conn.execute(
                    "SELECT AVG(response_time_ms) FROM query_logs WHERE date(created_at) >= date('now', '-7 days')"
                ).fetchone()
                stats["avg_response_ms"] = round(row[0], 1) if row and row[0] else 0

                # User count
                row = conn.execute("SELECT COUNT(*) FROM users").fetchone()
                stats["total_users"] = row[0] if row else 0
        except Exception as e:
            logger.warning(f"Stats gathering failed: {e}")
            stats = {"error": str(e)}

        return stats

    def _format_report(self, report_type: str, stats: dict, now: datetime) -> str:
        """Format stats into a report string."""
        title_map = {"daily": "日报", "weekly": "周报", "monthly": "月报"}
        title = title_map.get(report_type, "报告")

        lines = [
            f"# Looma {title} — {now.strftime('%Y-%m-%d %H:%M')}",
            "",
            f"## 总览",
            f"- 总查询数: {stats.get('total_queries', 0)}",
            f"- 今日查询: {stats.get('today_queries', 0)}",
            f"- 总用户数: {stats.get('total_users', 0)}",
            f"- 平均响应时间: {stats.get('avg_response_ms', 0)}ms",
            "",
            f"## 意图分布",
        ]

        for intent, count in stats.get("intent_distribution", {}).items():
            lines.append(f"- {intent}: {count}")

        lines.extend(["", "---", f"生成时间: {now.isoformat()}"])
        return "\n".join(lines)
