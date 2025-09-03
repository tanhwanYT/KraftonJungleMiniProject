// static/js/main_new.js
(function () {
  // ---- 상태 ----
  const state = {
    board: "",       // "", "Cafeteria", "Outside", "Delivery"
    page: 1,
    per_page: 10,
    total: 0,
    pages: 1,
  };

  // ---- DOM ----
  const listEl   = document.getElementById("post-list");
  const emptyEl  = document.getElementById("post-empty");
  const prevBtn  = document.getElementById("prevBtn");
  const nextBtn  = document.getElementById("nextBtn");
  const pageInfo = document.getElementById("pageInfo");
  const listTitle= document.getElementById("listTitle");

  const boardToggleBtn = document.getElementById("boardToggle");
  const boardPanel     = document.getElementById("boardPanel");
  const boardRadios    = document.querySelectorAll("input[name='boardFilter']");

  const postViewUrl = `${window.location.origin}/post/view`;

  // ---- 유틸 ----
  const escapeHtml = (s) => (s || "")
    .replace(/&/g,"&amp;").replace(/</g,"&lt;")
    .replace(/>/g,"&gt;").replace(/"/g,"&quot;")
    .replace(/'/g,"&#039;");

  function titleByBoard(board) {
    if (!board) return "최신글";
    return {
      Cafeteria: "식당 게시판",
      Outside:   "외식 게시판",
      Delivery:  "배달 게시판",
    }[board] || "최신글";
  }

  // ---- URL ↔ 상태 동기화 ----
  function readQuery() {
    const q = new URLSearchParams(location.search);
    const b = q.get("board");
    const p = parseInt(q.get("page") || "1", 10);
    state.board = (b === "Cafeteria" || b === "Outside" || b === "Delivery") ? b : "";
    state.page  = isNaN(p) || p < 1 ? 1 : p;

    // 라디오 선택 반영
    boardRadios.forEach(r => { r.checked = (r.value === state.board); });
    listTitle.textContent = titleByBoard(state.board);
  }

  function writeQuery() {
    const q = new URLSearchParams();
    if (state.board) q.set("board", state.board);
    if (state.page > 1) q.set("page", String(state.page));
    const qs = q.toString();
    const url = qs ? `?${qs}` : location.pathname;
    history.replaceState(null, "", url);
  }

  // ---- API ----
  async function fetchPosts() {
    const params = new URLSearchParams();
    params.set("page", String(state.page));
    params.set("per_page", String(state.per_page));
    if (state.board) params.set("board", state.board);

    const res = await fetch(`/api/posts?${params.toString()}`);
    const ct = res.headers.get("content-type") || "";
    if (!ct.includes("application/json")) {
      const text = await res.text();
      throw new Error(`JSON이 아닌 응답: ${res.status}\n${text.slice(0,200)}`);
    }
    const json = await res.json();
    if (!res.ok || !json.success) {
      throw new Error(json.msg || "목록을 불러오지 못했습니다.");
    }
    return json.data; // {items, page, per_page, total, pages}
  }

  // ---- 렌더 ----
  function renderPostItem(p) {
    // 이미지(썸네일)는 의도적으로 출력하지 않습니다.
    const li = document.createElement("li");
    li.className = "post-item";
    li.innerHTML = `
      <a class="post-link" href="${postViewUrl}?id=${encodeURIComponent(p.id)}">
        <div class="post-text">
          <div class="post-title">${escapeHtml(p.title)}</div>
          <div class="post-meta">
            게시판: ${escapeHtml(p.board)} · 작성자: ${escapeHtml(p.author)} · ${new Date(p.created_at).toLocaleString()}
          </div>
        </div>
      </a>
    `;
    return li;
  }

  function renderList(data) {
    const { items, page, total, pages } = data;
    state.page  = page;
    state.total = total;
    state.pages = pages;

    listEl.innerHTML = "";
    if (!items || items.length === 0) {
      emptyEl.style.display = "block";
    } else {
      emptyEl.style.display = "none";
      items.forEach(p => listEl.appendChild(renderPostItem(p)));
    }

    // 페이징
    if (pageInfo) pageInfo.textContent = `${page} / ${pages} 페이지`;
    if (prevBtn) prevBtn.disabled = (page <= 1);
    if (nextBtn) nextBtn.disabled = (page >= pages);
  }

  // ---- 이벤트 ----
  if (boardToggleBtn && boardPanel) {
    boardToggleBtn.addEventListener("click", () => {
      const show = boardPanel.style.display === "block";
      boardPanel.style.display = show ? "none" : "block";
      boardToggleBtn.textContent = show ? "게시판 선택 ▼" : "게시판 선택 ▲";
    });
  }

  boardRadios.forEach(r => {
    r.addEventListener("change", async () => {
      state.board = r.value;     // "" | Cafeteria | Outside | Delivery
      state.page  = 1;           // 보드 바꾸면 1페이지부터
      listTitle.textContent = titleByBoard(state.board);
      writeQuery();
      try {
        const data = await fetchPosts();
        renderList(data);
      } catch (e) {
        console.error(e);
        alert(e.message || "목록 로딩 중 오류가 발생했습니다.");
      }
    });
  });

  if (prevBtn) prevBtn.addEventListener("click", async () => {
    if (state.page <= 1) return;
    state.page -= 1;
    writeQuery();
    try {
      const data = await fetchPosts();
      renderList(data);
    } catch (e) {
      console.error(e);
      alert(e.message || "목록 로딩 중 오류가 발생했습니다.");
    }
  });

  if (nextBtn) nextBtn.addEventListener("click", async () => {
    if (state.page >= state.pages) return;
    state.page += 1;
    writeQuery();
    try {
      const data = await fetchPosts();
      renderList(data);
    } catch (e) {
      console.error(e);
      alert(e.message || "목록 로딩 중 오류가 발생했습니다.");
    }
  });

  // ---- 초기 구동 ----
  (async function init() {
    try {
      readQuery();          // URL → 상태 반영(보드/페이지)
      writeQuery();         // 정규화해서 URL 갱신
      const data = await fetchPosts();
      renderList(data);
    } catch (e) {
      console.error(e);
      alert(e.message || "초기 로딩 중 오류가 발생했습니다.");
    }
  })();
})();
