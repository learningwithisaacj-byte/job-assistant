/**
 * content.js
 * Runs on LinkedIn job pages.
 * Extracts job title, company, location, and full JD text,
 * then sends it to the background service worker.
 */

(function () {
  "use strict";

  /** Wait for an element to appear in the DOM */
  function waitFor(selector, timeout = 5000) {
    return new Promise((resolve, reject) => {
      const el = document.querySelector(selector);
      if (el) return resolve(el);
      const observer = new MutationObserver(() => {
        const found = document.querySelector(selector);
        if (found) {
          observer.disconnect();
          resolve(found);
        }
      });
      observer.observe(document.body, { childList: true, subtree: true });
      setTimeout(() => {
        observer.disconnect();
        reject(new Error(`Timeout waiting for ${selector}`));
      }, timeout);
    });
  }

  /** Extract job details from the LinkedIn job page */
  async function extractJobDetails() {
    try {
      // Wait for the job panel to load
      await waitFor(".job-details-jobs-unified-top-card__job-title", 6000);
    } catch {
      console.warn("[Job Assistant] Job title not found yet.");
    }

    const title =
      document.querySelector(
        ".job-details-jobs-unified-top-card__job-title h1"
      )?.innerText?.trim() ||
      document.querySelector(".t-24.t-bold")?.innerText?.trim() ||
      "";

    const company =
      document.querySelector(
        ".job-details-jobs-unified-top-card__company-name a"
      )?.innerText?.trim() ||
      document.querySelector(".jobs-unified-top-card__company-name")?.innerText?.trim() ||
      "";

    const location =
      document.querySelector(
        ".job-details-jobs-unified-top-card__bullet"
      )?.innerText?.trim() ||
      document.querySelector(".jobs-unified-top-card__bullet")?.innerText?.trim() ||
      "";

    // Expand "Show more" if present
    const showMoreBtn = document.querySelector(
      ".jobs-description__footer-button, button[aria-label='Show more, visually expands previously read content']"
    );
    if (showMoreBtn) showMoreBtn.click();

    await new Promise((r) => setTimeout(r, 600));

    const description =
      document.querySelector(".jobs-description__content")?.innerText?.trim() ||
      document.querySelector("#job-details")?.innerText?.trim() ||
      document.querySelector(".jobs-box__html-content")?.innerText?.trim() ||
      "";

    const jobUrl = window.location.href;

    return { title, company, location, description, jobUrl, source: "linkedin" };
  }

  // Listen for popup asking for job data
  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg.type === "GET_JOB_DETAILS") {
      extractJobDetails()
        .then((details) => sendResponse({ success: true, data: details }))
        .catch((err) =>
          sendResponse({ success: false, error: err.message })
        );
      return true; // async response
    }
  });

  console.log("[Job Assistant] Content script loaded on LinkedIn.");
})();
