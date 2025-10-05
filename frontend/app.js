const $ = (sel) => document.querySelector(sel);

async function api(path, options = {}) {
  const resp = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!resp.ok) {
    let text = await resp.text();
    throw new Error(text || `Request failed: ${resp.status}`);
  }
  const ct = resp.headers.get("content-type") || "";
  if (ct.includes("application/json")) return resp.json();
  return resp.text();
}

function renderRexItem(item) {
  const media = item.mediaUrl
    ? `<a href="${item.mediaUrl}" target="_blank">media</a>`
    : "";
  const tags = (item.tags || []).join(", ");

  let amazonBlock = "";
  if (item.amazonUrl) {
    const img =
      item.amazonMeta && item.amazonMeta.image
        ? `<img src="${item.amazonMeta.image}" alt="Amazon image" style="max-width:120px;max-height:120px;border-radius:6px;margin-right:8px;"/>`
        : "";
    const title =
      item.amazonMeta && item.amazonMeta.title
        ? item.amazonMeta.title
        : "Amazon Product";
    amazonBlock = `
      <div class="amazon">
        ${img}
        <a href="${item.amazonUrl}" target="_blank">${title}</a>
      </div>
    `;
  }

  return `
    <li>
      <div class="item">
        <div class="title">${item.title}</div>
        <div class="meta">by ${item.userId} • ${item.category}</div>
        <div class="desc">${item.description || ""}</div>
        ${amazonBlock}
        <div class="footer">${media} ${tags ? "• " + tags : ""}</div>
      </div>
    </li>
  `;
}

async function refreshList() {
  const userId = $("#filterUserId").value.trim();
  const qs = userId ? `?userId=${encodeURIComponent(userId)}` : "";
  const items = await api(`/api/rex${qs}`);
  $("#rexList").innerHTML = items.map(renderRexItem).join("");
}

function wireCreateForm() {
  $("#create-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      userId: $("#userId").value.trim(),
      title: $("#title").value.trim(),
      category: $("#category").value.trim(),
      description: $("#description").value.trim(),
      mediaUrl: $("#mediaUrl").value.trim(),
      tags: $("#tags")
        .value.split(",")
        .map((t) => t.trim())
        .filter(Boolean),
    };
    const status = $("#create-status");
    status.textContent = "Saving...";
    try {
      await api("/api/rex", { method: "POST", body: JSON.stringify(payload) });
      status.textContent = "Saved!";
      await refreshList();
      e.target.reset();
    } catch (err) {
      status.textContent = `Error: ${err.message}`;
    }
  });

  $("#seedButton").addEventListener("click", async () => {
    const userId = $("#userId").value.trim();
    if (!userId) {
      alert("Please enter a User ID first.");
      return;
    }
    const status = $("#create-status");
    status.textContent = "Seeding...";
    try {
      await api("/api/seed-user", {
        method: "POST",
        body: JSON.stringify({ userId }),
      });
      status.textContent = "Seeded!";
      // Set filter to this user for convenience and refresh list
      $("#filterUserId").value = userId;
      await refreshList();
    } catch (err) {
      status.textContent = `Error: ${err.message}`;
    }
  });

  $("#loadMcAuleyButton")?.addEventListener("click", async () => {
    const status = $("#create-status");
    status.textContent = "Loading Amazon data...";
    try {
      const res = await api("/api/load-mcauley-data", {
        method: "POST",
        body: JSON.stringify({
          categories: ["Books"],
          limit: 200,
          fiveStarOnly: true,
        }),
      });
      const added = (res && res.added) || 0;
      status.textContent = `Loaded ${added} items.`;
      await refreshList();
    } catch (err) {
      status.textContent = `Error: ${err.message}`;
    }
  });
}

function wireList() {
  $("#refreshList").addEventListener("click", refreshList);
}

function wireSearch() {
  $("#search-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const body = {
      query: $("#query").value.trim(),
      userId: $("#searchUserId").value.trim() || undefined,
      useLLM: $("#useLLM").checked,
    };
    const res = await api("/api/search", {
      method: "POST",
      body: JSON.stringify(body),
    });
    const { keywords, results } = res;
    const header = `<div class="keywords">keywords: ${(keywords || []).join(
      ", "
    )}</div>`;
    const list = `<ul>${(results || []).map(renderRexItem).join("")}</ul>`;
    $("#searchResults").innerHTML = header + list;
  });
}

// --- Tabs ---
function setActiveTab(tabName) {
  document
    .querySelectorAll(".tab-btn")
    .forEach((btn) =>
      btn.classList.toggle("active", btn.dataset.tab === tabName)
    );
  document.querySelectorAll("section[data-tab]").forEach((sec) => {
    sec.classList.toggle("hidden", sec.dataset.tab !== tabName);
  });
  if (tabName === "feed") {
    // If first time opening feed, kick off initial load
    if (feedPage === 1 && !feedLoading) {
      loadFeedPage();
    }
  }
}

function wireTabs() {
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => setActiveTab(btn.dataset.tab));
  });
  setActiveTab("create");
}

// --- Feed ---
let feedPage = 1;
const FEED_LIMIT = 10;
let feedHasMore = true;
let feedLoading = false;

function feedImageFor(item) {
  return (item.amazonMeta && item.amazonMeta.image) || item.mediaUrl || "";
}

function renderFeedCard(item) {
  const img = feedImageFor(item);
  const imageHtml = img ? `<img src="${img}" alt="${item.title}" />` : "";
  const fallbackHtml = !img
    ? `<div style="height:100%;width:100%;display:flex;align-items:center;justify-content:center;color:#9ca3af;">No image</div>`
    : "";
  return `
    <div class="feed-card">
      ${imageHtml}${fallbackHtml}
      <div class="feed-overlay">
        <div style="font-weight:600;">${item.title}</div>
        <div style="font-size:12px;opacity:.8;">${item.userId} • ${item.category}</div>
      </div>
    </div>
  `;
}

async function loadFeedPage() {
  if (feedLoading || !feedHasMore) return;
  feedLoading = true;
  $("#feedStatus").textContent = "Loading...";
  try {
    const res = await api(
      `/api/rex?order=desc&page=${feedPage}&limit=${FEED_LIMIT}`
    );
    const { items, hasMore } = res;
    const html = (items || []).map(renderFeedCard).join("");
    $("#feedContainer").insertAdjacentHTML("beforeend", html);
    feedHasMore = !!hasMore;
    feedPage += 1;
    $("#feedStatus").textContent = feedHasMore ? "" : "End of feed";
  } catch (e) {
    $("#feedStatus").textContent = `Error loading feed: ${e.message}`;
  } finally {
    feedLoading = false;
  }
}

function wireFeed() {
  const container = $("#feedContainer");
  container.addEventListener("scroll", () => {
    const nearBottom =
      container.scrollTop + container.clientHeight >=
      container.scrollHeight - 50;
    if (nearBottom) loadFeedPage();
  });
}

window.addEventListener("DOMContentLoaded", () => {
  wireTabs();
  wireCreateForm();
  wireList();
  wireSearch();
  wireFeed();
  refreshList();
});
