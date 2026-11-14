// Client-side behavior for the web screens. Kept in a static file (no inline
// scripts or event handlers) so the CSP can use script-src 'self'.
(function () {
  'use strict';

  // Ask for confirmation before submitting forms marked with data-confirm.
  document.addEventListener('submit', function (event) {
    var form = event.target;
    var message = form.getAttribute && form.getAttribute('data-confirm');
    if (message && !window.confirm(message)) {
      event.preventDefault();
    }
  });

  // ISBN lookup on the new-book form: fill fields from Google Books.
  var button = document.getElementById('isbn-lookup-button');
  if (!button) {
    return;
  }
  button.addEventListener('click', async function () {
    var isbn = document.getElementById('isbn').value.trim();
    var msg = document.getElementById('isbn-lookup-message');
    if (!isbn) {
      msg.textContent = 'ISBNを入力してください';
      return;
    }
    msg.textContent = '取得中...';
    try {
      var res = await fetch('/books/isbn-lookup?isbn=' + encodeURIComponent(isbn));
      var body = await res.json();
      if (!res.ok) {
        msg.textContent = body.error || '取得に失敗しました';
        return;
      }
      var data = body.data;
      if (data.title) document.getElementById('title').value = data.title;
      if (data.author) document.getElementById('author').value = data.author;
      if (data.publisher) document.getElementById('publisher').value = data.publisher;
      if (data.published_date) document.getElementById('published_date').value = data.published_date;
      if (data.isbn) document.getElementById('isbn').value = data.isbn;
      msg.textContent = '取得しました';
    } catch (e) {
      msg.textContent = '取得に失敗しました';
    }
  });
})();
