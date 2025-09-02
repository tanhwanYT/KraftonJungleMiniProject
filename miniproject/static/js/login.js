document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById("loginForm");
  const LOGIN_API = form.dataset.loginApi;
  const MAIN_PAGE = form.dataset.mainPage;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value;

    try {
      const res = await fetch(LOGIN_API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password })
      });

      if (!res.ok) { alert("서버 오류"); return; }

      const data = await res.json();
      if (data.success) window.location.href = MAIN_PAGE;
      else alert("아이디 또는 비밀번호가 올바르지 않습니다.");
    } catch (err) {
      console.error(err);
      alert("네트워크 오류");
    }
  });
});

