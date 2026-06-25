/* ============================================================
   api.js — shared across every page
   Handles: auth token storage, authenticated fetch, role guards
   ============================================================ */

const Auth = {
  getToken() { return localStorage.getItem("token"); },
  getRole() { return localStorage.getItem("role"); },
  getName() { return localStorage.getItem("name"); },

  setSession(token, role, name) {
    localStorage.setItem("token", token);
    localStorage.setItem("role", role);
    localStorage.setItem("name", name);
  },

  clearSession() {
    localStorage.removeItem("token");
    localStorage.removeItem("role");
    localStorage.removeItem("name");
  },

  isLoggedIn() { return !!this.getToken(); },

  /** Redirects to /login if not logged in, or if logged in with the wrong role. */
  requireRole(role) {
    if (!this.isLoggedIn()) { window.location.href = "/login"; return false; }
    if (this.getRole() !== role) {
      window.location.href = this.getRole() === "company" ? "/admin" : "/candidate";
      return false;
    }
    return true;
  },

  logout() {
    this.clearSession();
    window.location.href = "/";
  },
};

/** Authenticated fetch — adds the Bearer token, handles 401 by logging out. */
async function apiFetch(url, options = {}) {
  const headers = options.headers || {};
  const token = Auth.getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const isFormData = options.body instanceof FormData;
  if (!isFormData && options.body && typeof options.body !== "string") {
    headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(options.body);
  }

  const res = await fetch(url, { ...options, headers });

  if (res.status === 401) {
    Auth.clearSession();
    window.location.href = "/login";
    throw new Error("Session expired. Please log in again.");
  }

  let data = null;
  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    data = await res.json();
  }

  if (!res.ok) {
    const message = (data && data.detail) ? data.detail : `Request failed (${res.status})`;
    throw new Error(typeof message === "string" ? message : JSON.stringify(message));
  }

  return data;
}

function showError(el, message) {
  el.textContent = message;
  el.style.display = "block";
}

function hideError(el) {
  el.style.display = "none";
}

function scoreLabel(category) {
  const map = {
    technical: "Technical", communication: "Communication", confidence: "Confidence",
    body_language: "Body Language", custom: "Custom Questions", awareness: "Awareness",
  };
  return map[category] || category;
}

function renderScoreBars(container, breakdown) {
  let html = "";
  for (const [key, value] of Object.entries(breakdown)) {
    const notAssessed = value === null || value === undefined;
    html += `<div class="score-row ${notAssessed ? "not-assessed" : ""}">
      <div class="label-row">
        <span>${scoreLabel(key)}</span>
        <span>${notAssessed ? "Not assessed" : value.toFixed(0) + "%"}</span>
      </div>
      <div class="score-bar-track"><div class="score-bar-fill" style="width:${notAssessed ? 0 : value}%"></div></div>
    </div>`;
  }
  container.innerHTML = html;
}
