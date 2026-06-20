# =========================
# main.py
# UBUNTU SERVER OPTIMIZED
# =========================

import asyncio
import csv
import os
import random
import logging
import traceback
import time

from playwright.async_api import async_playwright

RESULTS_DIR = "results"

# =========================
# SETTINGS
# =========================

# LOCAL TESTING:
# HEADLESS_MODE = False

# UBUNTU SERVER:
HEADLESS_MODE = True

# SAFE CONCURRENCY
ZIP_CONCURRENCY = 2
BUSINESS_CONCURRENCY = 2

# SCROLLING
MAX_SCROLLS = 8

os.makedirs(
    RESULTS_DIR,
    exist_ok=True
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

ZIP_MAP = {}
STATES = []
ACTIVE_JOBS = {}

ERROR_LOG = "error_log.txt"
FAILED_URLS = "failed_urls.txt"


def log_error(msg):

    with open(
        ERROR_LOG,
        "a",
        encoding="utf-8"
    ) as f:

        f.write(msg + "\n\n")


def log_failed_url(url):

    with open(
        FAILED_URLS,
        "a",
        encoding="utf-8"
    ) as f:

        f.write(url + "\n")

# =========================
# LOAD ZIPS
# =========================

def load_zips():

    global ZIP_MAP
    global STATES

    ZIP_MAP = {}
    STATES = []

    if not os.path.exists(
        "uszips.csv"
    ):

        logger.error(
            "uszips.csv not found"
        )

        return

    state_names = {}

    with open(
        "uszips.csv",
        "r",
        encoding="utf-8"
    ) as f:

        reader = csv.DictReader(f)

        for row in reader:

            state_id = row["state_id"]
            state_name = row["state_name"]
            zip_code = row["zip"]

            if state_id not in ZIP_MAP:

                ZIP_MAP[state_id] = []

                state_names[state_id] = state_name

            ZIP_MAP[state_id].append(
                zip_code
            )

    for st_id, name in state_names.items():

        STATES.append({

            "id": st_id,

            "name": name,

            "count":
                len(
                    ZIP_MAP[st_id]
                )
        })

    STATES.sort(
        key=lambda x: x["name"]
    )

    logger.info(
        "ZIP codes loaded"
    )

load_zips()

# =========================
# PHONE NORMALIZER
# =========================

def normalize_phone(phone):

    if not phone:
        return ""

    cleaned = ''.join(
        filter(str.isdigit, phone)
    )

    if (
        cleaned.startswith("1")
        and len(cleaned) > 10
    ):
        cleaned = cleaned[1:]

    return cleaned

# =========================
# SAVE RESULTS
# =========================

def save_results(
    results,
    state_id,
    search_term
):

    state_folder = state_id.upper()

    search_folder = (
        search_term
        .lower()
        .strip()
    )

    job_dir = os.path.join(
        RESULTS_DIR,
        state_folder,
        search_folder
    )

    os.makedirs(
        job_dir,
        exist_ok=True
    )

    filename = os.path.join(
        job_dir,
        f"{search_folder}.csv"
    )

    seen_phones = set()

    cleaned_rows = []

    for row in results:

        phone = normalize_phone(
            row.get(
                "Phone Number",
                ""
            )
        )

        if (
            phone
            and phone in seen_phones
        ):
            continue

        if phone:
            seen_phones.add(phone)

        cleaned_rows.append({

            "business name":
                row.get(
                    "Business Name",
                    ""
                ),

            "location":
                row.get(
                    "Location",
                    ""
                ),

            "phone number":
                phone,

            "website":
                row.get(
                    "Website",
                    ""
                ),

            "google maps url":
                row.get(
                    "Google Maps URL",
                    ""
                ),

            "rating":
                row.get(
                    "Rating",
                    ""
                ),

            "reviews count":
                row.get(
                    "Reviews Count",
                    ""
                ),

            "type":
                search_term
        })
    fields = [

        "business name",

        "location",

        "phone number",

        "website",

        "google maps url",

        "rating",

        "reviews count",

        "type"
    ]

    with open(
        filename,
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fields
        )

        writer.writeheader()

        writer.writerows(
            cleaned_rows
        )

    logger.info(
        f"Saved: {filename}"
    )

# =========================
# BROWSER
# =========================

class ScraperBrowser:

    def __init__(
        self,
        headless=HEADLESS_MODE
    ):

        self.headless = headless

        self.pw = None

        self.browser = None

        self.context = None

    async def start(self):

        self.pw = await async_playwright().start()

        browser_args = [

            '--disable-dev-shm-usage',

            '--disable-blink-features=AutomationControlled',

            '--disable-background-networking',

            '--disable-background-timer-throttling',

            '--disable-renderer-backgrounding',

            '--disable-ipc-flooding-protection',

            '--disable-features=IsolateOrigins',

            '--disable-site-isolation-trials',
        ]

        self.browser = await self.pw.chromium.launch(

            headless=self.headless,

            args=browser_args
        )

        self.context = await self.browser.new_context(

            viewport={

                'width': 1400,

                'height': 900
            },

            locale='en-US',

            timezone_id='America/New_York',

            user_agent=(

                'Mozilla/5.0 '

                '(Windows NT 10.0; Win64; x64) '

                'AppleWebKit/537.36 '

                '(KHTML, like Gecko) '

                'Chrome/122.0.0.0 Safari/537.36'
            ),

            extra_http_headers={

                "Accept-Language":
                    "en-US,en;q=0.9"
            }
        )

        # ENGLISH FINGERPRINT

        await self.context.add_init_script("""

        Object.defineProperty(
            navigator,
            'language',
            {
                get: () => 'en-US'
            }
        );

        Object.defineProperty(
            navigator,
            'languages',
            {
                get: () => ['en-US', 'en']
            }
        );

        """)

        # BLOCK HEAVY FILES

        await self.context.route(
            "**/*",
            lambda route: (

                route.abort()

                if route.request.resource_type in [

                    "image",

                    "media",

                    "font"

                ]

                else route.continue_()
            )
        )

        logger.info(
            "Browser started"
        )

    async def stop(self):

        try:
            await self.context.close()
        except:
            pass

        try:
            await self.browser.close()
        except:
            pass

        try:
            await self.pw.stop()
        except:
            pass

# =========================
# DETECT GOOGLE BLOCKS
# =========================

async def detect_google_block(page):

    try:

        content = (
            await page.content()
        ).lower()

        blocked_keywords = [

            "unusual traffic",

            "not a robot",

            "captcha",

            "sorry, but your computer",

            "verify you are human",

            "automated queries"
        ]

        for keyword in blocked_keywords:

            if keyword in content:

                logger.error(
                    "GOOGLE BLOCK DETECTED"
                )

                logger.error(
                    f"Matched keyword: {keyword}"
                )

                return True

        return False

    except Exception as e:

        logger.error(
            f"Block detection error: {e}"
        )

        return False

# =========================
# SAFE GOTO
# =========================

async def safe_goto(
    page,
    url,
    retries=2
):

    for attempt in range(retries):

        try:

            await asyncio.sleep(

                random.uniform(
                    0.3,
                    0.8
                )
            )

            logger.info(
                f"Opening: {url}"
            )

            await page.goto(

                url,

                wait_until="domcontentloaded",

                timeout=45000
            )

            blocked = await detect_google_block(
                page
            )

            if blocked:

                raise Exception(
                    "GOOGLE ROBOT VERIFICATION"
                )

            return True
        
        except Exception as e:

            error_text = (
                f"\nURL: {url}\n"
                f"ERROR: {str(e)}\n"
                f"{traceback.format_exc()}"
            )

            logger.error(error_text)

            log_error(error_text)

            log_failed_url(url)

            try:

                html = await page.content()

                with open(
                    f"failed_page_{int(time.time())}.html",
                    "w",
                    encoding="utf-8"
                ) as f:

                    f.write(html)

            except:
                pass

            if attempt < retries - 1:

                await asyncio.sleep(
                    random.uniform(
                        3,
                        6
                    )
                )

    return False

# =========================
# COLLECT BUSINESS URLS
# =========================

async def collect_business_urls(page):

    business_urls = set()

    previous_count = 0

    for scroll in range(MAX_SCROLLS):

        try:

            links = await page.locator(
                'a[href*="/maps/place/"]'
            ).all()

            for link in links:

                href = await link.get_attribute(
                    'href'
                )

                if href:
                    business_urls.add(href)

            current_count = len(
                business_urls
            )

            logger.info(
                f"Scroll {scroll+1}: "
                f"{current_count} businesses"
            )

            if current_count == previous_count:

                logger.info(
                    "No new businesses found"
                )

                break

            previous_count = current_count

            await page.evaluate(
                """
                () => {

                    const feed =
                        document.querySelector(
                            'div[role="feed"]'
                        );

                    if(feed){

                        feed.scrollBy(
                            0,
                            6000
                        );
                    }
                }
                """
            )

            await page.wait_for_timeout(

                random.randint(
                    800,
                    1400
                )
            )

        except Exception as e:

            logger.error(
                f"Scroll failed: {e}"
            )

            break

    return list(
        business_urls
    )

# =========================
# SCRAPE BUSINESS
# =========================

SEM = asyncio.Semaphore(
    BUSINESS_CONCURRENCY
)

async def scrape_business(
    context,
    biz_url
):

    async with SEM:

        page = await context.new_page()

        try:

            await asyncio.sleep(

                random.uniform(
                    0.4,
                    0.9
                )
            )

            success = await safe_goto(
                page,
                biz_url
            )

            if not success:
                return None

            try:

                await page.wait_for_selector(
                    'h1',
                    timeout=8000
                )

            except:

                logger.warning(
                    "Business page missing h1"
                )

                return None

            name = ""
            address = ""
            phone = ""
            website = ""

            google_maps_url = page.url

            rating = ""

            reviews_count = ""

            try:

                name = (
                    await page.text_content(
                        'h1'
                    ) or ""
                )

            except Exception as e:

                logger.warning(
                    f"Name scrape failed: {e}"
                )

            try:

                addr_el = await page.query_selector(
                    'button[data-item-id="address"]'
                )

                if addr_el:

                    address = (
                        await addr_el.get_attribute(
                            'aria-label'
                        ) or ""
                    ).replace(
                        'Address: ',
                        ''
                    )

            except Exception as e:

                logger.warning(
                    f"Address scrape failed: {e}"
                )

            try:
                website_btn = await page.query_selector(
                    '[data-item-id="authority"]'
                )

                if website_btn:

                    website = (
                        await website_btn.text_content()
                        or ""
                    )

                    website = (
                        website
                        .replace("", "")
                        .replace("Website", "")
                        .strip()
                    )

                    if (
                        website
                        and not website.startswith(
                            (
                                "http://",
                                "https://"
                            )
                        )
                    ):

                        website = (
                            "https://"
                            + website
                        )

            except Exception as e:

                logger.warning(
                    f"Website scrape failed: {e}"
                )

            try:

                phone_el = await page.query_selector(
                    'button[data-item-id^="phone:tel"]'
                )

                if phone_el:

                    phone = (
                        await phone_el.get_attribute(
                            'data-item-id'
                        ) or ""
                    ).replace(
                        'phone:tel:',
                        ''
                    )

            except Exception as e:

                logger.warning(
                    f"Phone scrape failed: {e}"
                )

            try:

                rating_element = await page.query_selector(
                    'span[role="img"]'
                )

                if rating_element:

                    rating = (
                        await rating_element.get_attribute(
                            "aria-label"
                        ) or ""
                    )

            except Exception as e:

                logger.warning(
                    f"Rating scrape failed: {e}"
                )

            try:

                review_buttons = await page.query_selector_all(
                    'button'
                )

                for btn in review_buttons:

                    aria = await btn.get_attribute(
                        "aria-label"
                    )

                    if (
                        aria
                        and "review" in aria.lower()
                    ):

                        reviews_count = aria

                        break

            except Exception as e:

                logger.warning(
                    f"Review scrape failed: {e}"
                )

            logger.info(
                f"Scraped: {name}"
            )

            return {

                "Business Name":
                    name,

                "Location":
                    address,

                "Phone Number":
                    phone,

                "Website":
                    website,

                "Google Maps URL":
                    google_maps_url,

                "Rating":
                    rating,

                "Reviews Count":
                    reviews_count
            }

        except Exception as e:

            error_text = (
                f"BUSINESS SCRAPE FAILED\n"
                f"URL: {biz_url}\n"
                f"{traceback.format_exc()}"
            )

            logger.error(error_text)

            log_error(error_text)

            log_failed_url(biz_url)

            return None

        finally:

            await page.close()

# =========================
# SCRAPE ZIP
# =========================

async def scrape_zip(
    context,
    state_id,
    search_term,
    zip_code
):

    page = await context.new_page()

    try:

        url = (

            f"https://www.google.com/maps/search/"

            f"{'+'.join(search_term.split())}"

            f"+in+{state_id}+{zip_code}"
        )

        success = await safe_goto(
            page,
            url
        )

        if not success:

            logger.warning(
                f"Failed ZIP: {zip_code}"
            )

            return []

        try:

            await page.wait_for_selector(
                'div[role="feed"]',
                timeout=10000
            )

        except Exception as e:

            logger.warning(
                f"No feed for ZIP "
                f"{zip_code}: {e}"
            )

            return []

        business_urls = await collect_business_urls(
            page
        )

        logger.info(

            f"{zip_code}: "

            f"{len(business_urls)} businesses"
        )

        tasks = [

            scrape_business(
                context,
                url
            )

            for url in business_urls
        ]

        results = await asyncio.gather(
            *tasks
        )

        return [

            r for r in results

            if r
        ]

    except Exception as e:

        logger.error(
            f"ZIP scrape failed: {e}"
        )

        logger.error(
            traceback.format_exc()
        )

        return []

    finally:

        await page.close()

# =========================
# MAIN SCRAPER
# =========================

async def scrape_state(
    state_id,
    search_term
):

    state_id = state_id.upper()

    zip_codes = ZIP_MAP.get(
        state_id
    )

    if not zip_codes:

        logger.error(
            f"No ZIPs for {state_id}"
        )

        return

    total_zips = len(zip_codes)

    ACTIVE_JOBS[state_id] = {

        "status": "running",

        "current": 0,

        "total": total_zips,

        "progress_percent": 0,

        "message": "Starting..."
    }

    logger.info(
        f"Starting scrape for "
        f"{search_term} in {state_id}"
    )

    sb = ScraperBrowser(
        headless=HEADLESS_MODE
    )

    await sb.start()

    all_results = []

    try:

        for i in range(

            0,

            len(zip_codes),

            ZIP_CONCURRENCY
        ):

            batch = zip_codes[
                i:i+ZIP_CONCURRENCY
            ]

            logger.info(
                f"ZIP batch: {batch}"
            )

            tasks = [

                scrape_zip(
                    sb.context,
                    state_id,
                    search_term,
                    zip_code
                )

                for zip_code in batch
            ]

            results = await asyncio.gather(
                *tasks
            )

            await asyncio.sleep(

                random.uniform(
                    2,
                    4
                )
            )

            for r in results:
                all_results.extend(r)

            save_results(
                all_results,
                state_id,
                search_term
            )

            current = min(
                i + ZIP_CONCURRENCY,
                total_zips
            )

            pct = int(
                (current / total_zips)
                * 100
            )

            ACTIVE_JOBS[state_id] = {

                "status": "running",

                "current": current,

                "total": total_zips,

                "progress_percent": pct,

                "message": (
                    f"Processed "
                    f"{current} ZIPs"
                )
            }

            logger.info(
                f"Total results: "
                f"{len(all_results)}"
            )

        save_results(
            all_results,
            state_id,
            search_term
        )

        ACTIVE_JOBS[state_id] = {

            "status": "completed",

            "current": total_zips,

            "total": total_zips,

            "progress_percent": 100,

            "message": "Finished"
        }

        logger.info(
            "SCRAPE COMPLETE"
        )

    except Exception as e:

        logger.error(
            f"MAIN SCRAPER FAILED: {e}"
        )

        logger.error(
            traceback.format_exc()
        )

    finally:

        await sb.stop()