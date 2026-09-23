/* Social_Media front-end behaviour: CSRF-aware fetch, like/follow toggles,
   AI caption suggestions and notification polling. */
(function () {
  "use strict";

  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";

  async function api(url, { method = "GET", body = null } = {}) {
    const options = {
      method,
      headers: { "X-CSRFToken": csrfToken, "X-Requested-With": "fetch" },
    };
    if (body !== null) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }
    const response = await fetch(url, options);
    let payload = null;
    try { payload = await response.json(); } catch (_) { /* non-JSON body */ }
    if (!response.ok) {
      const detail = payload?.detail || `Request failed (${response.status})`;
      throw Object.assign(new Error(detail), { status: response.status, payload });
    }
    return payload;
  }

  function toast(message, variant = "danger") {
    const el = document.createElement("div");
    el.className = `alert alert-${variant} position-fixed top-0 start-50 translate-middle-x mt-3 shadow-sm`;
    el.style.zIndex = 2000;
    el.textContent = message;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 4000);
  }

  /* ---- Like toggles ---------------------------------------------------- */
  document.addEventListener("click", async (event) => {
    const likeBtn = event.target.closest("[data-like-toggle]");
    if (likeBtn) {
      const postId = likeBtn.dataset.postId;
      likeBtn.disabled = true;
      try {
        const data = await api(`/api/v1/posts/${postId}/like/`, { method: "POST" });
        likeBtn.classList.toggle("text-danger", data.is_liked);
        likeBtn.querySelector("i").className = data.is_liked ? "bi bi-heart-fill" : "bi bi-heart";
        likeBtn.querySelector("[data-like-count]").textContent = data.like_count;
      } catch (err) { toast(err.message); }
      finally { likeBtn.disabled = false; }
    }

    /* ---- Follow toggles ------------------------------------------------ */
    const followBtn = event.target.closest("[data-follow-toggle]");
    if (followBtn) {
      const username = followBtn.dataset.username;
      followBtn.disabled = true;
      try {
        const data = await api(`/api/v1/users/${username}/follow/`, { method: "POST" });
        const nowFollowing = data.status === "following";
        followBtn.textContent = nowFollowing ? "Unfollow" : "Follow";
        followBtn.classList.toggle("btn-primary", !nowFollowing);
        followBtn.classList.toggle("btn-outline-secondary", nowFollowing);
        if (data.status === "requested") {
          followBtn.textContent = "Requested";
          toast("Follow request sent.", "info");
        }
      } catch (err) { toast(err.message); }
      finally { followBtn.disabled = false; }
    }
  });

  /* ---- AI caption suggestions ----------------------------------------- */
  const captionBtn = document.querySelector("[data-caption-trigger]");
  if (captionBtn) {
    const ideaInput = document.querySelector("[data-caption-idea]");
    const listBox = document.querySelector("[data-caption-results]");
    const targetInput = document.querySelector("[data-caption-target]");
    const statusBox = document.querySelector("[data-caption-status]");

    captionBtn.addEventListener("click", async () => {
      const idea = (ideaInput?.value || "").trim();
      if (!idea) { toast("Write a few keywords first.", "warning"); return; }
      captionBtn.disabled = true;
      statusBox.textContent = "Asking the AI service…";
      listBox.innerHTML = "";
      try {
        const data = await api("/ai/caption/", { method: "POST", body: { idea } });
        statusBox.textContent = data.provider
          ? `${data.suggestions.length} suggestions · provider: ${data.provider}`
          : `${data.suggestions.length} suggestions`;
        data.suggestions.forEach((text) => {
          const item = document.createElement("li");
          item.className = "list-group-item caption-suggestion d-flex justify-content-between align-items-start gap-2";
          const span = document.createElement("span");
          span.textContent = text;
          const use = document.createElement("button");
          use.className = "btn btn-sm btn-outline-primary";
          use.type = "button";
          use.textContent = "Use";
          use.addEventListener("click", () => {
            if (targetInput) { targetInput.value = text; targetInput.focus(); }
          });
          item.append(span, use);
          listBox.appendChild(item);
        });
      } catch (err) {
        statusBox.textContent = err.status === 429
          ? "Rate limit reached — try again in a bit."
          : `Caption service unavailable: ${err.message}`;
      } finally { captionBtn.disabled = false; }
    });
  }

  /* ---- Notification polling (upgrade path: swap for a websocket) -------- */
  const badge = document.querySelector("#unread-count");
  if (badge) {
    const poll = async () => {
      try {
        const data = await api("/api/v1/notifications/unread-count/");
        badge.textContent = data.unread_count;
        badge.classList.toggle("d-none", data.unread_count === 0);
      } catch (_) { /* ignore transient poll failures */ }
    };
    poll();
    setInterval(poll, 45000);
  }

  window.SocialMedia = { api, toast };
})();
