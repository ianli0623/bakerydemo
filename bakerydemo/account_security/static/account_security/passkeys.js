(() => {
  'use strict';

  const registrationButton = document.querySelector(
    '[data-passkey-registration]',
  );
  if (!registrationButton) {
    return;
  }

  const status = document.querySelector('[data-passkey-status]');
  const csrfToken =
    document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
    getCookie('csrftoken');

  function getCookie(name) {
    return (
      document.cookie
        .split(';')
        .map((item) => item.trim())
        .find((item) => item.startsWith(`${name}=`))
        ?.slice(name.length + 1) || ''
    );
  }

  function decode(value) {
    const padding = '='.repeat((4 - (value.length % 4)) % 4);
    const base64 = (value + padding).replace(/-/g, '+').replace(/_/g, '/');
    return Uint8Array.from(atob(base64), (character) =>
      character.charCodeAt(0),
    );
  }

  function encode(value) {
    const bytes = new Uint8Array(value);
    let binary = '';
    bytes.forEach((byte) => {
      binary += String.fromCharCode(byte);
    });
    return btoa(binary)
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=+$/, '');
  }

  function normaliseCreationOptions(options) {
    options.challenge = decode(options.challenge);
    options.user.id = decode(options.user.id);
    options.excludeCredentials = (options.excludeCredentials || []).map(
      (item) => ({
        ...item,
        id: decode(item.id),
      }),
    );
    return options;
  }

  function serialiseRegistration(credential) {
    return {
      id: credential.id,
      rawId: encode(credential.rawId),
      type: credential.type,
      authenticatorAttachment: credential.authenticatorAttachment,
      clientExtensionResults: credential.getClientExtensionResults(),
      response: {
        attestationObject: encode(credential.response.attestationObject),
        clientDataJSON: encode(credential.response.clientDataJSON),
        transports: credential.response.getTransports?.() || [],
      },
    };
  }

  async function postJson(url, body) {
    const response = await fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken,
      },
      body: JSON.stringify(body),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.error || 'Windows Hello registration failed.');
    }
    return payload;
  }

  registrationButton.addEventListener('click', async () => {
    if (!window.PublicKeyCredential || !navigator.credentials) {
      status.textContent =
        'This browser does not support Windows Hello sign-in.';
      return;
    }
    registrationButton.disabled = true;
    status.textContent = 'Waiting for Windows Hello…';
    try {
      const options = await postJson(registrationButton.dataset.optionsUrl, {});
      const credential = await navigator.credentials.create({
        publicKey: normaliseCreationOptions(options),
      });
      const result = await postJson(registrationButton.dataset.verifyUrl, {
        credential: serialiseRegistration(credential),
        transports: credential.response.getTransports?.() || [],
      });
      window.location.assign(
        result.redirect || registrationButton.dataset.successUrl,
      );
    } catch (error) {
      status.textContent =
        error.name === 'NotAllowedError'
          ? 'Windows Hello was cancelled or timed out.'
          : error.message;
      registrationButton.disabled = false;
    }
  });
})();
