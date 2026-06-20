# =========================
# run_scraper.py
# =========================

import asyncio
import sys
import os
import logging

os.chdir(os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.ERROR,
    format='%(levelname)s: %(message)s'
)

from main import (
    scrape_state,
    STATES,
    load_zips,
    ACTIVE_JOBS
)


async def run_local():

    print("\n" + "="*50)
    print(" BUSINESS SCRAPER")
    print("="*50)

    load_zips()

    if not STATES:

        print(
            "Error: uszips.csv not found."
        )

        return

    search_term = input(
        "\nEnter search term: "
    ).strip()

    if not search_term:
        search_term = "plumbers"

    print("\nAvailable States:\n")

    col_count = 4
    rows = (len(STATES) + col_count - 1) // col_count

    for row in range(rows):

        line = ""

        for col in range(col_count):

            idx = row + col * rows

            if idx < len(STATES):

                st = STATES[idx]

                item = (
                    f"{st['id']}: "
                    f"{st['name'][:12]}"
                )

                line += item.ljust(22)

        print(line)

    state_id = input(
        "\nEnter State ID: "
    ).strip().upper()

    valid_ids = [s['id'] for s in STATES]

    while state_id not in valid_ids:

        print(f"Invalid state: {state_id}")

        state_id = input(
            "Enter valid state ID: "
        ).strip().upper()

    print("\nStarting scraper...")
    print("Press CTRL+C to stop.\n")

    task = asyncio.create_task(
        scrape_state(
            state_id,
            search_term
        )
    )

    last_processed = -1

    try:

        while not task.done():

            job = ACTIVE_JOBS.get(state_id)

            if job:

                current = job.get("current", 0)
                total = job.get("total", 0)
                pct = job.get(
                    "progress_percent",
                    0
                )

                status = job.get(
                    "status",
                    "running"
                )

                msg = job.get(
                    "message",
                    ""
                )

                if current != last_processed:

                    bar_length = 30

                    filled_length = int(
                        bar_length * pct // 100
                    )

                    bar = (
                        '█' * filled_length
                        + '-'
                        * (bar_length - filled_length)
                    )

                    sys.stdout.write(
                        f"\r[{bar}] "
                        f"{pct}% | "
                        f"{status.upper()} | "
                        f"{current}/{total} | "
                        f"{msg[:30]}"
                    )

                    sys.stdout.flush()

                    last_processed = current

            await asyncio.sleep(1)

        if task.done():

            exc = task.exception()

            if exc:
                print(f"\n\nERROR: {exc}")

    except KeyboardInterrupt:

        print("\n\nStopping scraper...")

        task.cancel()

        try:
            await task
        except:
            pass

    print("\n\nDONE")
    print(
        f"Results saved in:\n"
        f"results/{state_id}/{search_term}/"
    )


if __name__ == "__main__":

    asyncio.run(run_local())