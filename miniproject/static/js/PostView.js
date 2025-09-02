window.addEventListener('DOMContentLoaded', () => {
    const index = localStorage.getItem("currentPost");
    const posts = JSON.parse(localStorage.getItem("posts")) || [];

    if (index !== null && posts[index]) {
      const post = posts[index];
      document.querySelector('h2.title.is-3').textContent = post.title;
      document.querySelector('.level-right p').textContent = `작성자: ${post.author}`;
      document.querySelectorAll('.box')[0].textContent = post.content;

      const imagesDiv = document.querySelectorAll('.box')[1];
      imagesDiv.innerHTML = '';
      post.images.forEach(src => {
        const img = document.createElement("img");
        img.src = "https://via.placeholder.com/300x200?text=" + encodeURIComponent(src);
        img.style.maxWidth = "100%";
        img.style.marginTop = "10px";
        imagesDiv.appendChild(img);
      });
    }
});
