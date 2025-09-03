// static/js/PostView.js
(async function () {
  // 0) URL에서 게시글 id 추출
  const id = new URLSearchParams(location.search).get("id");
  if (!id) {
    alert("잘못된 접근입니다. 게시글 ID가 없습니다.");
    location.href = "/";
    return;
  }

  // 1) 공용 JSON fetch 래퍼 (HTML 응답 방지)
  async function fetchJSON(url, options) {
    const res = await fetch(url, options);
    const ct = res.headers.get("content-type") || "";
    if (!ct.includes("application/json")) {
      const text = await res.text();
      throw new Error(`서버가 JSON이 아닌 응답을 보냈습니다. status=${res.status}\n${text.slice(0,200)}`);
    }
    const data = await res.json();
    return { res, data };
  }

  // 2) DOM 캐시
  const titleEl    = document.getElementById("pv-title") || document.querySelector("h2.title.is-3");
  const metaEl     = document.getElementById("pv-meta")  || document.querySelector(".level-right p");
  const contentEl  = document.getElementById("pv-content") || (document.querySelectorAll(".box")[0] ?? null);
  const imagesBox  = document.getElementById("pv-images")  || (document.querySelectorAll(".box")[1] ?? null);

  const likeBtn   = document.getElementById("like-btn");
  const likeIcon  = document.getElementById("like-icon");
  const likeText  = document.getElementById("like-text");
  const likeCount = document.getElementById("like-count");

  const cInput = document.getElementById("comment-input");
  const cBtn   = document.getElementById("comment-btn");
  const cList  = document.getElementById("comment-list");

  // 3) 유틸
  const escapeHtml = (s) =>
    (s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");

  // 4) API 호출
  async function loadPost() {
    const { res, data } = await fetchJSON(`/api/posts/${encodeURIComponent(id)}`);
    if (!res.ok || !data.success) throw new Error(data.msg || "게시글을 불러오지 못했습니다.");
    return data.data; // { id, title, content, board, author, created_at, images[], likes_count, liked_by[] }
  }

  async function loadComments() {
    const { res, data } = await fetchJSON(`/api/posts/${encodeURIComponent(id)}/comments`);
    if (!res.ok || !data.success) throw new Error(data.msg || "댓글을 불러오지 못했습니다.");
    return data.data.items || [];
  }

  async function toggleLike() {
    const { res, data } = await fetchJSON(`/api/posts/${encodeURIComponent(id)}/like`, { method: "POST" });
    if (res.status === 401) {
      alert("로그인이 필요합니다.");
      location.href = "/login";
      return;
    }
    if (!res.ok || !data.success) {
      alert(data.msg || "좋아요 처리 중 오류가 발생했습니다.");
      return;
    }
    applyLikeState(data.data.likes_count, data.data.liked);
  }

  // 5) 렌더링
  function applyLikeState(count, liked) {
    if (likeCount) likeCount.textContent = `(${count || 0})`;
    if (likeIcon) {
      likeIcon.classList.remove("far", "fas", "has-text-danger", "has-text-grey");
      if (liked) {
        likeIcon.classList.add("fas", "has-text-danger");
        if (likeText) likeText.textContent = "Likeing!";
      } else {
        likeIcon.classList.add("far", "has-text-grey");
        if (likeText) likeText.textContent = "Like It!";
      }
    }
  }

  function renderComments(items) {
    if (!cList) return;
    cList.innerHTML = "";
    if (!items.length) return;
    items.forEach((c) => {
      const box = document.createElement("div");
      box.className = "box has-background-grey-darker has-text-white mt-2";
      const when = new Date(c.created_at).toLocaleString();
      box.innerHTML = `
        <p class="subtitle is-6 has-text-grey-light">${escapeHtml(c.author)} · ${when}</p>
        <p style="white-space:pre-wrap">${escapeHtml(c.content)}</p>
      `;
      cList.appendChild(box);
    });
  }

  async function createComment() {
    const content = (cInput?.value || "").trim();
    if (!content) {
      alert("댓글 내용을 입력해 주세요.");
      return;
    }
    const { res, data } = await fetchJSON(`/api/posts/${encodeURIComponent(id)}/comments`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    });
    if (res.status === 401) {
      alert("로그인이 필요합니다.");
      location.href = "/login";
      return;
    }
    if (!res.ok || !data.success) {
      alert(data.msg || "댓글 작성 중 오류가 발생했습니다.");
      return;
    }
    cInput.value = "";
    renderComments(await loadComments());
  }

  // 6) 초기 로딩 플로우
  try {
    const p = await loadPost();

    if (titleEl) titleEl.textContent = p.title || "제목 없음";
    if (metaEl)  metaEl.textContent  = `게시판: ${p.board} · 작성자: ${p.author} · ${new Date(p.created_at).toLocaleString()}`;

    if (contentEl) {
      // contentEl이 <pre>인 경우/아닌 경우 모두 대응
      if (contentEl.tagName === "PRE") {
        contentEl.textContent = p.content || "";
      } else {
        contentEl.innerHTML = `<pre style="white-space:pre-wrap; margin:0">${escapeHtml(p.content || "")}</pre>`;
      }
    }

    if (imagesBox) {
      imagesBox.innerHTML = "";
      if (p.images && p.images.length) {
        p.images.forEach((src) => {
          const img = document.createElement("img");
          img.src = src; // /uploads/...
          img.alt = "image";
          img.style.maxWidth = "100%";
          img.style.marginTop = "10px";
          imagesBox.appendChild(img);
        });
      } else {
        imagesBox.innerHTML = `<p class="has-text-grey">이미지가 없습니다.</p>`;
      }
    }

    // 좋아요 초기 상태 (로그인 사용자별 liked 여부는 서버에서 내려주거나 추가 호출로 확인 가능)
    applyLikeState(p.likes_count || 0, false);

    // 이벤트 바인딩
    if (likeBtn) likeBtn.onclick = toggleLike;
    if (cBtn && cInput) cBtn.onclick = createComment;

    // 댓글
    renderComments(await loadComments());
  } catch (e) {
    console.error(e);
    alert(e.message || "게시글을 불러오는 중 오류가 발생했습니다.");
    location.href = "/";
  }
})();
