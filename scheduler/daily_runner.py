# ============================================================
# Daily Runner — Schedules and Triggers the Pipeline
# ============================================================
# PURPOSE:
#   Runs the Supervisor pipeline on a daily schedule.
#   You can also trigger it manually.
#
# HOW IT WORKS:
#   - Uses APScheduler to fire the pipeline at a set time every day
#   - Default: 8:00 AM (configurable via SCHEDULE_HOUR / SCHEDULE_MINUTE in .env)
#   - Also provides a manual trigger function
#
# USAGE:
#   # Start the scheduler (runs in background)
#   python -m scheduler.daily_runner
#
#   # Or trigger a single run manually
#   python -m scheduler.daily_runner --now
# ============================================================

import sys
import argparse
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from config.settings import settings


def run_pipeline():
    """
    Trigger a single pipeline run.
    
    This is the function that APScheduler calls every day,
    and what you call when doing a manual trigger.
    """
    print(f"\n{'='*60}")
    print(f"  Pipeline triggered at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    from agents.supervisor import SupervisorAgent

    supervisor = SupervisorAgent()
    success = supervisor.run_pipeline()

    if success:
        print(f"\n[Runner] Pipeline completed successfully")
    else:
        print(f"\n[Runner] Pipeline completed with errors")

    return success


def start_scheduler():
    """
    Start the daily scheduler.
    
    This function blocks forever — it keeps running and triggers
    the pipeline at the scheduled time every day.
    
    Press Ctrl+C to stop.
    """
    hour = settings.SCHEDULE_HOUR
    minute = settings.SCHEDULE_MINUTE

    print(f"\n{'='*60}")
    print(f"  AI Job Search Agent — Scheduler")
    print(f"{'='*60}")
    print(f"  Schedule: Daily at {hour:02d}:{minute:02d}")
    print(f"  Press Ctrl+C to stop")
    print(f"{'='*60}\n")

    scheduler = BlockingScheduler()

    # Schedule the pipeline to run daily
    scheduler.add_job(
        run_pipeline,
        trigger="cron",
        hour=hour,
        minute=minute,
        id="daily_job_search",
        name="Daily Job Search Pipeline",
        misfire_grace_time=3600,  # If missed, run within 1 hour
    )

    try:
        scheduler.start()
    except KeyboardInterrupt:
        print("\n[Runner] Scheduler stopped by user")
        scheduler.shutdown()


# ============================================================
# ENTRY POINT — Run from command line
# ============================================================
# python -m scheduler.daily_runner          → Start scheduler
# python -m scheduler.daily_runner --now    → Run once immediately
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Job Search Agent — Pipeline Runner")
    parser.add_argument(
        "--now",
        action="store_true",
        help="Run the pipeline immediately (once) instead of scheduling"
    )
    args = parser.parse_args()

    if args.now:
        print("[Runner] Running pipeline immediately...")
        run_pipeline()
    else:
        start_scheduler()
