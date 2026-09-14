(() => {
  'use strict';

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

  function normaliseRequestOptions(options) {
    options.challenge = decode(options.challenge);
    options.allowCredentials = (options.allowCredentials || []).map((item) => ({
      ...item,
      id: decode(item.id),
    }));
    if (!options.allowCredentials.length) {
      delete options.allowCredentials;
    }
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

  function serialiseAuthentication(credential) {
    return {
      id: credential.id,
      rawId: encode(credential.rawId),
      type: credential.type,
      authenticatorAttachment: credential.authenticatorAttachment,
      clientExtensionResults: credential.getClientExtensionResults(),
      response: {
        authenticatorData: encode(credential.response.authenticatorData),
        clientDataJSON: encode(credential.response.clientDataJSON),
        signature: encode(credential.response.signature),
        userHandle: credential.response.userHandle
          ? encode(credential.response.userHandle)
          : null,
      },
    };
  }

  async function postJson(url, body, fallbackMessage) {
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
      throw new Error(payload.error || fallbackMessage);
    }
    return payload;
  }

  function supportsWebAuthn() {
    return window.PublicKeyCredential && navigator.credentials;
  }

  const registrationButton = document.querySelector(
    '[data-passkey-registration]',
  );
  registrationButton?.addEventListener('click', async () => {
    const status = document.querySelector('[data-passkey-status]');
    if (!supportsWebAuthn()) {
      status.textContent = registrationButton.dataset.unsupportedMessage;
      return;
    }
    registrationButton.disabled = true;
    status.textContent = registrationButton.dataset.waitingMessage;
    try {
      const options = await postJson(
        registrationButton.dataset.optionsUrl,
        {},
        registrationButton.dataset.errorMessage,
      );
      const credential = await navigator.credentials.create({
        publicKey: normaliseCreationOptions(options),
      });
      const result = await postJson(
        registrationButton.dataset.verifyUrl,
        {
          credential: serialiseRegistration(credential),
          transports: credential.response.getTransports?.() || [],
        },
        registrationButton.dataset.errorMessage,
      );
      window.location.assign(
        result.redirect || registrationButton.dataset.successUrl,
      );
    } catch (error) {
      status.textContent =
        error.name === 'NotAllowedError'
          ? registrationButton.dataset.cancelledMessage
          : error.message;
      registrationButton.disabled = false;
    }
  });

  const authenticationButton = document.querySelector(
    '[data-passkey-authentication]',
  );
  authenticationButton?.addEventListener('click', async () => {
    const status = document.querySelector('[data-passkey-status]');
    if (!supportsWebAuthn()) {
      status.textContent = authenticationButton.dataset.unsupportedMessage;
      return;
    }
    authenticationButton.disabled = true;
    status.textContent = authenticationButton.dataset.waitingMessage;
    try {
      const options = await postJson(
        authenticationButton.dataset.optionsUrl,
        {},
        authenticationButton.dataset.errorMessage,
      );
      const credential = await navigator.credentials.get({
        publicKey: normaliseRequestOptions(options),
      });
      const result = await postJson(
        authenticationButton.dataset.verifyUrl,
        {
          credential: serialiseAuthentication(credential),
        },
        authenticationButton.dataset.errorMessage,
      );
      window.location.assign(
        result.redirect || authenticationButton.dataset.successUrl,
      );
    } catch (error) {
      status.textContent =
        error.name === 'NotAllowedError'
          ? authenticationButton.dataset.cancelledMessage
          : error.message;
      authenticationButton.disabled = false;
    }
  });
})();
