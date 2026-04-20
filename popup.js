/**
 * popup.js
 * Handles UI logic for the Job Assistant Chrome Extension popup.
 */

const $ = (id) => document.getElementById(id);

let jobDetails = null;

// ── Helpers ───────────────────────────────────────────────────────────────────
function setStatus(msg, type = "info") {
  const el = $("status");
  el.textContent = msg;
  el.className = `status ${type}`;
}

function loadSaved() {
  chrome.storage.local.get(["apiUrl", "userId"], (data) => {
    if (data.apiUrl) $("apiUrl").value = data.apiUrl;
    if (data.userId) $("userId").value = data.userId;
  });
}

function saveSettings() {
  chrome.storage.local.set({
    apiUrl: $("apiUrl").value.trim(),
    userId: $("userId").value.trim(),
  });
}

// ── Detect job from current tab ───────────────────────────────────────────────
async function detectJob() {
  setStatus("🔍 Detecting job details...", "loading");
  $("generateBtn").disabled = true;

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

  if (!tab.url.includes("linkedin.com/jobs")) {
    setStatus("⚠️ Navigate to a LinkedIn job page first.", "error");
    return;
  }

  chrome.tabs.sendMessage(tab.id, { type: "GET_JOB_DETAILS" }, (response) => {
    if (chrome.runtime.lastError || !response) {
      setStatus("❌ Could not read page. Refresh and try again.", "error");
      return;
    }
    if (!response.success) {
      setStatus(`❌ ${response.error}`, "error");
      return;
    }

    jobDetails = response.data;
    $("jobTitle").value = jobDetails.title || "Unknown";
    $("company").value = jobDetails.company || "Unknown";
    $("jdPreview").value = (jobDetails.description || "").slice(0, 500) + "...";
    $("generateBtn").disabled = false;

    setStatus(`✅ Job detected: "${jobDetails.title}" at ${jobDetails.company}`, "success");
  });
}

// ── Generate resume via API ───────────────────────────────────────────────────
async function generateResume() {
  const apiUrl = $("apiUrl").value.trim();
  const userId = $("userId").value.trim();

  if (!userId) {
    setStatus("⚠️ Enter your User ID (from the web app after uploading resume).", "error");
    return;
  }
  if (!jobDetails) {
    setStatus("⚠️ Detect the job first.", "error");
    return;
  }

  saveSettings();
  $("generateBtn").disabled = true;
  $("downloads").style.display = "none";
  setStatus("⚡ Step 1/2: Saving job to your profile...", "loading");

  try {
    // Step 1: Save job + get job_id via search endpoint
    const searchRes = await fetch(`${apiUrl}/api/search-jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        keywords: jobDetails.title,
        location: jobDetails.location || "Remote",
        sources: [],        // skip scraping – we inject manually
        user_id: userId,
        use_ai_matching: false,
        results_per_source: 0,
        _inject_job: {      // custom field picked up by backend
          title: jobDetails.title,
          company: jobDetails.company,
          location: jobDetails.location,
          description: jobDetails.description,
          source: "linkedin",
          job_url: jobDetails.jobUrl,
        },
      }),
    });

    // Fallback: POST job directly to a lightweight save endpoint
    // (add POST /api/save-job to backend/main.py for cleaner flow)
    let jobId;
    if (searchRes.ok) {
      const searchData = await searchRes.json();
      const jobs = searchData.jobs || [];
      jobId = jobs[0]?.job_id;
    }

    if (!jobId) {
      // Simplified: call generate with inline JD (extend API for this)
      setStatus("⚠️ Could not get job ID. Use the web app instead.", "error");
      $("generateBtn").disabled = false;
      return;
    }

    setStatus("⚡ Step 2/2: Generating ATS resume with Claude...", "loading");

    // Step 2: Generate resume
    const genRes = await fetch(`${apiUrl}/api/generate-resume`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: userId,
        job_id: jobId,
        include_cover_letter: true,
      }),
    });

    if (!genRes.ok) {
      const err = await genRes.json();
      throw new Error(err.detail || "Generation failed");
    }

    const gen = await genRes.json();
    const genId = gen.generated_id;

    setStatus(
      `✅ Resume generated! ATS Score: ${gen.ats_score?.toFixed(0)}%`,
      "success"
    );

    // Show download links
    const dl = $("downloads");
    dl.style.display = "block";
    dl.innerHTML = `
      <a href="${apiUrl}/api/download/pdf/${genId}" target="_blank">📄 Download PDF Resume</a>
      <a href="${apiUrl}/api/download/docx/${genId}" target="_blank">📝 Download DOCX Resume</a>
      ${gen.downloads?.cover_letter
        ? `<a href="${apiUrl}/api/download/cover-letter/${genId}" target="_blank">💌 Download Cover Letter</a>`
        : ""}
    `;
  } catch (err) {
    setStatus(`❌ Error: ${err.message}`, "error");
  } finally {
    $("generateBtn").disabled = false;
  }
}

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  loadSaved();
  detectJob();

  $("detectBtn").addEventListener("click", detectJob);
  $("generateBtn").addEventListener("click", generateResume);
});
