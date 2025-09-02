document.getElementById("loginForm").addEventListener("submit", async (e) => {
  e.preventDefault();

  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value;

  try {
    const res = await fetch("/api/login", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      credentials: "include", // 쿠키(세션) 사용 시
      body: JSON.stringify({ username, password })
    });

    const data = await res.json();

    if (data.success) {
      localStorage.setItem("loggedIn", "true");
      window.location.href = "main.html";
    } else {
      alert("아이디 또는 비밀번호가 올바르지 않습니다."); // DB에 없거나 틀린 경우
    }
  } 
  catch (err) {
    console.error(err);
    alert("서버 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.");
  }
});
