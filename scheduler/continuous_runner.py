# ============================================================
# Super Agent v2 — 24/7 Continuous Staggered Scheduler
# ============================================================
# PURPOSE:
#   Runs the Super Agent v2 pipeline continuously with STAGGERED
#   schedules for different collectors. Instead of one big run
#   every 4 hours, each platform is checked at optimal intervals:
#
#   LinkedIn Posts  → every 1 hour  (HR posts appear constantly)
#   LinkedIn Jobs   → every 2 hours (formal listings update often)
#   Naukri          → every 3 hours (moderate update frequency)
#   Indeed          → every 4 hours (slowest to update)
#   Full Pipeline   → every 6 hours (complete analysis with email)
#
# WHY STAGGERED?
#   1. Spreads API load across time (avoids rate limit bursts)
#   2. Catches freshly posted jobs faster (recency = higher callbacks)
#   3. Keeps the model pool healthy (never exhausts all models at once)
#
# USAGE:
#   python -m scheduler.continuous_runner          → Start 24/7 scheduler
#   python -m scheduler.continuous_runner --now    → Run full pipeline once
#   python -m scheduler.continuous_runner --test   → Run a quick test cycle
# ============================================================

import sys
import argparse
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from config.settings import settings


def run_full_pipeline():
    """
    Run the complete Super Agent v2 pipeline.
    This is the main entry point called by the scheduler.
    """
    print(f"\n{'='*60}")
    print(f"  Full Pipeline triggered at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    from agents.langgraph_supervisor import SuperAgentV2
    agent = SuperAgentV2()
    success = agent.run()

    if success:
        print(f"\n[Runner] Full pipeline completed successfully")
    else:
        print(f"\n[Runner] Full pipeline completed with errors")

    return success


def run_single_collector(collector_name: str):
    """
    Run a single collector and match any new jobs found.
    Used for staggered scheduling (e.g., LinkedIn Posts every hour).
    """
    print(f"\n{'='*60}")
    print(f"  {collector_name} check at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    from agents.langgraph_supervisor import SuperAgentV2
    agent = SuperAgentV2()
    success = agent.run(collector_filter=collector_name)

    if success:
        print(f"[Runner] {collector_name} check completed")
    else:
        print(f"[Runner] {collector_name} check had errors")


def start_scheduler():
    """
    Start the 24/7 staggered scheduler.
    
    Schedule:
        LinkedIn Posts → every 1 hour
        LinkedIn Jobs  → every 2 hours
        Naukri         → every 3 hours
        Indeed         → every 4 hours
        Full Pipeline  → every 6 hours (complete analysis + email digest)
    """
    print(f"\n{'='*60}")
    print(f"  SUPER AGENT v2 — 24/7 Staggered Scheduler")
    print(f"{'='*60}")
    print(f"  Schedule:")
    if settings.ENABLE_LINKEDIN_POSTS:
        print(f"    LinkedIn Posts  → every 1 hour")
    if settings.ENABLE_LINKEDIN_JOBS:
        print(f"    LinkedIn Jobs   → every 2 hours")
    if settings.ENABLE_NAUKRI:
        print(f"    Naukri          → every 3 hours")
    if settings.ENABLE_INDEED:
        print(f"    Indeed          → every 4 hours")
    print(f"    Full Pipeline   → every 6 hours")
    print(f"  Press Ctrl+C to stop")
    print(f"{'='*60}\n")

    scheduler = BlockingScheduler()

    # --- Staggered Individual Collectors ---
    
    if settings.ENABLE_LINKEDIN_POSTS:
        scheduler.add_job(
            run_single_collector,
            trigger="interval",
            hours=1,
            args=["linkedin_posts"],
            id="linkedin_posts_hourly",
            name="LinkedIn Posts (Hourly)",
            misfire_grace_time=1800,
        )

    if settings.ENABLE_LINKEDIN_JOBS:
        scheduler.add_job(
            run_single_collector,
            trigger="interval",
            hours=2,
            args=["linkedin_jobs"],
            id="linkedin_jobs_2h",
            name="LinkedIn Jobs (2-Hourly)",
            misfire_grace_time=1800,
        )

    if settings.ENABLE_NAUKRI:
        scheduler.add_job(
            run_single_collector,
            trigger="interval",
            hours=3,
            args=["naukri"],
            id="naukri_3h",
            name="Naukri (3-Hourly)",
            misfire_grace_time=1800,
        )

    if settings.ENABLE_INDEED:
        scheduler.add_job(
            run_single_collector,
            trigger="interval",
            hours=4,
            args=["indeed"],
            id="indeed_4h",
            name="Indeed (4-Hourly)",
            misfire_grace_time=1800,
        )

    # --- Full Pipeline (complete analysis + email digest) ---
    scheduler.add_job(
        run_full_pipeline,
        trigger="interval",
        hours=6,
        id="full_pipeline_6h",
        name="Full Pipeline (6-Hourly)",
        misfire_grace_time=3600,
        next_run_time=datetime.now(),  # Run immediately on startup!
    )

    try:
        scheduler.start()
    except KeyboardInterrupt:
        print("\n[Runner] Scheduler stopped by user")
        scheduler.shutdown()


# ============================================================
# ENTRY POINT — Run from command line
# ============================================================
# python -m scheduler.continuous_runner          → Start 24/7 scheduler
# python -m scheduler.continuous_runner --now    → Run full pipeline once
# python -m scheduler.continuous_runner --test   → Quick test
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Super Agent v2 — 24/7 Job Search Pipeline")
    parser.add_argument(
        "--now",
        action="store_true",
        help="Run the full pipeline immediately (once) instead of scheduling"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run a quick test (single LinkedIn Jobs collection)"
    )
    parser.add_argument(
        "--collector",
        type=str,
        choices=["linkedin_jobs", "linkedin_posts", "naukri", "indeed"],
        help="Run a specific collector only"
    )
    args = parser.parse_args()

    if args.now:
        print("[Runner] Running full pipeline immediately...")
        run_full_pipeline()
    elif args.test:
        print("[Runner] Running quick test (LinkedIn Jobs only)...")
        run_single_collector("linkedin_jobs")
    elif args.collector:
        print(f"[Runner] Running {args.collector} only...")
        run_single_collector(args.collector)
    else:
        start_scheduler()
