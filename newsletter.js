document.querySelectorAll('.newsletter-form').forEach(function (form) {
  form.addEventListener('submit', function () {
    var email = form.querySelector('input[name="EMAIL"]').value;
    if (!email) return;

    window.setTimeout(function () {
      form.hidden = true;
      var message = document.createElement('p');
      message.className = 'newsletter-success';
      message.setAttribute('role', 'status');
      message.textContent = 'Merci ! Votre inscription a bien été prise en compte.';
      form.insertAdjacentElement('afterend', message);
    }, 300);
  });
});
