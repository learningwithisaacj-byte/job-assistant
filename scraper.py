# ================== IMPORTS ==================
from playwright.sync_api import sync_playwright
import time

# ================== CONFIG ==================
ROLE = "Scrum Master"
LOCATION = "India"

# ================== SCRAPER ==================
def scrape_linkedin_jobs(role, location, max_jobs=5):
    jobs = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # keep False for stability
        page = browser.new_page()

        url = f"https://www.linkedin.com/jobs/search/?keywords={role}&location={location}"
        page.goto(url)

        # wait for jobs to load
        page.wait_for_timeout(5000)

        # scroll to load more jobs
        for _ in range(3):
            page.mouse.wheel(0, 3000)
            page.wait_for_timeout(2000)

        cards = page.query_selector_all(".base-card")

        for i, job in enumerate(cards[:max_jobs]):
            try:
                title = job.query_selector(".base-search-card__title").inner_text().strip()
                company = job.query_selector(".base-search-card__subtitle").inner_text().strip()
                link = job.query_selector("a").get_attribute("href")

                # open job page for description
                job_page = browser.new_page()
                job_page.goto(link)
                job_page.wait_for_timeout(3000)

                desc = job_page.locator("body").inner_text()[:4000]

                job_page.close()

                jobs.append({
                    "title": title,
                    "company": company,
                    "link": link,
                    "description": desc
                })

                print(f"✔ {title} - {company}")

            except Exception as e:
                print("❌ Error:", e)

        browser.close()

    return jobs


# ================== TEST RUN ==================
if __name__ == "__main__":
    data = scrape_linkedin_jobs(ROLE, LOCATION)

    for j in data:
        print("\n----------------------")
        print(j["title"], "-", j["company"])
        print(j["description"][:300])