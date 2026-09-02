(() => {
  const passwordField = document.querySelector('[data-temporary-password]');
  const copyButton = document.querySelector('[data-copy-temporary-password]');
  const copyStatus = document.querySelector(
    '[data-temporary-password-copy-status]',
  );

  if (!passwordField || !copyButton || !copyStatus) {
    return;
  }

  copyButton.addEventListener('click', async () => {
    await navigator.clipboard.writeText(passwordField.value);
    copyStatus.hidden = false;
  });
})();
