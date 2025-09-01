document.getElementById("loginForm").addEventListener("submit", function(e) {
      e.preventDefault();

      const username = document.getElementById("username").value;
      const password = document.getElementById("password").value;

      // 임시 계정 (실제로는 서버에서 확인해야 함)
      if(username === "admin" && password === "1234") {
        localStorage.setItem("loggedIn", "true"); // 로그인 상태 저장
        window.location.href = "main.html"; // 로그인 성공 시 이동
      } else {
        document.getElementById("error").textContent = "아이디 또는 비밀번호가 올바르지 않습니다.";
      }
    });