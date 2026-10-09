
document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('theme-form');
  if (!form) return;

  const radios = form.querySelectorAll('input[type="radio"][name="theme"]');
  const options = form.querySelectorAll('.theme-option');

  radios.forEach(radio => {
    radio.addEventListener('change', () => {
      const chosen = radio.value;
      let resolved;
      if (chosen === 'light') {
        resolved = 'light';
      } else if (chosen === 'dark') {
        resolved = 'dark';
      } else {
        resolved = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
      }
      document.documentElement.setAttribute('data-theme', resolved);

      options.forEach(opt => opt.classList.remove('theme-option--active'));
      radio.closest('.theme-option').classList.add('theme-option--active');

      form.submit();
    });
  });
});

document.addEventListener("DOMContentLoaded", () => {
  const tzField = document.getElementById("id_timezone");
  if (tzField) {
    tzField.value = Intl.DateTimeFormat().resolvedOptions().timeZone;
  }
});

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("edit-password-button");
  if (btn) {
    btn.addEventListener("click", () => {
      document.getElementById("password-modal-backdrop").classList.add("active");
    });
  }

  const cancelBtn = document.getElementById("cancel-password-change");
  if (cancelBtn) {
    cancelBtn.addEventListener("click", () => {
      document.getElementById("password-modal-backdrop").classList.remove("active");
      document.getElementById("password-modal").reset();
    });
  }

  const form = document.getElementById("password-modal");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const currentPassword = document.getElementById("current-password").value.trim();
    const newPassword = document.getElementById("new-password").value.trim();
    const confirmNewPassword = document.getElementById("confirm-new-password").value.trim();

    if (!currentPassword || !newPassword || !confirmNewPassword) {
      alert("Please fill in all password fields.");
      return;
    }
    if (newPassword !== confirmNewPassword) {
      alert("New passwords do not match.");
      return;
    }

    try {
      const response = await fetch(form.action, {
        method: "POST",
        headers: {
          "X-CSRFToken": getCsrfToken(),
        },
        credentials: "same-origin",
        body: new FormData(form),
      });

      const data = await response.json();

      if (data.status === "error") {
        alert(data.message);
        return;
      }

      window.location.reload();
    } catch (err) {
      alert("An error occurred. Please try again.");
    }
  });
});

const deleteBtn = document.getElementById("delete-account-button");
const deleteModal = document.getElementById("delete-account-modal-backdrop");
const cancelDeleteBtn = document.getElementById("cancel-delete-account");

function openModal(modal) {
  modal.classList.add("active");
}

function closeModal(modal) {
  modal.classList.remove("active");
}

if (deleteBtn && deleteModal && cancelDeleteBtn) {
  deleteBtn.addEventListener("click", () => {
    openModal(deleteModal);
    const pwd = deleteModal.querySelector("#delete-account-password");
    if (pwd) pwd.focus();
  });

  cancelDeleteBtn.addEventListener("click", () => closeModal(deleteModal));

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeModal(deleteModal);
  });

  deleteModal.addEventListener("click", (e) => {
    if (e.target === deleteModal) closeModal(deleteModal);
  });
}

document.addEventListener('DOMContentLoaded', () => {
  const openBtn     = document.getElementById('open-model-picker');
  if (!openBtn) return;

  const backdrop    = document.getElementById('model-picker-backdrop');
  const cancelBtn   = document.getElementById('cancel-model-picker');
  const confirmBtn  = document.getElementById('confirm-model-picker');
  const searchInput = document.getElementById('model-search');
  const modelList   = document.getElementById('model-list');
  const loadingEl   = document.getElementById('model-list-loading');
  const errorEl     = document.getElementById('model-list-error');
  const pickerError = document.getElementById('model-picker-error');

  let allModels    = [];
  let selectedId   = null;
  let modelsLoaded = false;

  async function loadModels() {
    loadingEl.style.display = 'block';
    errorEl.style.display   = 'none';
    modelList.style.display = 'none';

    try {
      const res  = await fetch('/settings/ai/models/');
      const data = await res.json();
      if (data.status !== 'success') throw new Error(data.message || 'Failed');
      allModels    = data.models;
      modelsLoaded = true;
      renderList(allModels);
    } catch (e) {
      if (e.message && e.message !== 'Failed') errorEl.textContent = e.message;
      loadingEl.style.display = 'none';
      errorEl.style.display   = 'block';
    }
  }

  function renderList(models) {
    modelList.innerHTML = '';
    if (!models.length) {
      modelList.innerHTML = allModels.length
        ? '<li class="model-list__empty">No models match your search.</li>'
        : '<li class="model-list__empty">The AI server has no models installed.</li>';
    } else {
      models.forEach(m => {
        const li = document.createElement('li');
        li.className = 'model-list__item' + (m.id === selectedId ? ' model-list__item--selected' : '');
        li.dataset.id = m.id;
        li.innerHTML = `
          <span class="model-list__name">${escHtml(m.name)}</span>
          <span class="model-list__id">${escHtml(m.id)}</span>
          ${m.context_length ? `<span class="model-list__ctx">${formatCtx(m.context_length)}</span>` : ''}
          ${m.free === true  ? '<span class="model-list__price model-list__price--free">Free</span>' : ''}
          ${m.free === false ? '<span class="model-list__price">Paid</span>' : ''}
        `;
        li.addEventListener('click', () => {
          document.querySelectorAll('.model-list__item').forEach(el => el.classList.remove('model-list__item--selected'));
          li.classList.add('model-list__item--selected');
          selectedId = m.id;
          confirmBtn.disabled = false;
        });
        modelList.appendChild(li);
      });
    }
    loadingEl.style.display = 'none';
    modelList.style.display = 'block';
  }

  searchInput.addEventListener('input', () => {
    const q = searchInput.value.toLowerCase().trim();
    if (!q) { renderList(allModels); return; }
    renderList(allModels.filter(m =>
      m.name.toLowerCase().includes(q) || m.id.toLowerCase().includes(q)
    ));
  });

  openBtn.addEventListener('click', () => {
    selectedId          = null;
    confirmBtn.disabled = true;
    searchInput.value   = '';
    pickerError.style.display = 'none';
    backdrop.classList.add('active');
    if (!modelsLoaded) loadModels();
    else renderList(allModels);
  });

  cancelBtn.addEventListener('click', () => backdrop.classList.remove('active'));
  backdrop.addEventListener('click', e => { if (e.target === backdrop) backdrop.classList.remove('active'); });

  confirmBtn.addEventListener('click', async () => {
    if (!selectedId) return;
    pickerError.style.display = 'none';
    confirmBtn.textContent    = 'Saving…';
    confirmBtn.disabled       = true;

    try {
      const res  = await fetch('/settings/ai/model/save/', {
        method:  'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken':  getCsrfToken(),
        },
        body: JSON.stringify({ model_id: selectedId }),
      });
      const data = await res.json();
      if (data.status === 'success') {
        document.getElementById('ai-current-model-name').textContent = selectedId;
        backdrop.classList.remove('active');
      } else {
        showPickerError(data.message || 'Something went wrong.');
      }
    } catch (e) {
      showPickerError('Network error. Please try again.');
    } finally {
      confirmBtn.textContent = 'Select Model';
      confirmBtn.disabled    = false;
    }
  });

  function showPickerError(msg) {
    pickerError.textContent   = msg;
    pickerError.style.display = 'block';
  }

  function escHtml(str) {
    return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  function formatCtx(n) {
    return n >= 1000 ? `${Math.round(n / 1000)}k ctx` : `${n} ctx`;
  }
});

document.addEventListener('DOMContentLoaded', () => {
  const root = document.getElementById('ai-connection');
  if (!root) return;

  const saved     = JSON.parse(document.getElementById('ai-connection-data').textContent);
  const radios    = root.querySelectorAll('input[name="ai_provider"]');
  const hintEl    = document.getElementById('ai-connection-hint');
  const urlRow    = document.getElementById('ai-base-url-row');
  const urlInput  = document.getElementById('ai-base-url');
  const keyRow    = document.getElementById('ai-api-key-row');
  const keyInput  = document.getElementById('ai-api-key');
  const statusEl  = document.getElementById('ai-connection-status');
  const testBtn   = document.getElementById('test-ai-connection');
  const saveBtn   = document.getElementById('save-ai-connection');

  const HINTS = {
    '':         `Uses the server's .env settings: ${saved.default_name} at ${saved.default_url}.`,
    ollama:     'Runs models on your machine. Install Ollama, then pull a model, e.g. "ollama pull llama3.2".',
    lmstudio:   "Runs models on your machine. Start LM Studio's local server first.",
    openrouter: 'Hosted models from many providers. Get a key at openrouter.ai/keys. Web search in chat is only available here.',
    custom:     'Any OpenAI-compatible API, e.g. https://api.openai.com/v1.',
  };

  const selected = () => root.querySelector('input[name="ai_provider"]:checked').value;

  function render() {
    const provider  = selected();
    const isSaved   = provider === saved.provider;
    const takesUrl  = ['ollama', 'lmstudio', 'custom'].includes(provider);
    const takesKey  = ['openrouter', 'custom'].includes(provider);

    hintEl.textContent   = HINTS[provider];
    urlRow.style.display = takesUrl ? '' : 'none';
    keyRow.style.display = takesKey ? '' : 'none';

    urlInput.value       = isSaved ? saved.base_url : '';
    urlInput.placeholder = saved.preset_urls[provider] || 'https://api.example.com/v1';

    keyInput.value = '';
    if (isSaved && saved.key_hint) {
      keyInput.placeholder = `Saved key ending ${saved.key_hint}, leave blank to keep it`;
    } else if (provider === 'openrouter' && saved.server_key) {
      keyInput.placeholder = "Leave blank to use the server's key";
    } else {
      keyInput.placeholder = provider === 'custom' ? 'Optional for servers without auth' : 'Paste your API key';
    }

    setStatus('');
  }

  function setStatus(msg, kind) {
    statusEl.textContent = msg;
    statusEl.className   = 'ai-connection__status' + (kind ? ` ai-connection__status--${kind}` : '');
  }

  async function post(url) {
    const res = await fetch(url, {
      method:  'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken':  getCsrfToken(),
      },
      body: JSON.stringify({
        provider: selected(),
        base_url: urlInput.value.trim(),
        api_key:  keyInput.value.trim(),
      }),
    });
    return res.json();
  }

  async function run(btn, busyText, url, onSuccess) {
    const label  = btn.textContent;
    btn.textContent = busyText;
    testBtn.disabled = saveBtn.disabled = true;
    setStatus('');
    try {
      const data = await post(url);
      if (data.status === 'success') onSuccess(data);
      else setStatus(data.message || 'Something went wrong.', 'error');
    } catch (e) {
      setStatus('Network error. Please try again.', 'error');
    } finally {
      btn.textContent = label;
      testBtn.disabled = saveBtn.disabled = false;
    }
  }

  radios.forEach(radio => radio.addEventListener('change', render));

  testBtn.addEventListener('click', () =>
    run(testBtn, 'Testing…', '/settings/ai/connection/test/', data => setStatus(data.message, 'ok'))
  );

  // Reload so the active model, model list and card chat all use the new connection.
  saveBtn.addEventListener('click', () =>
    run(saveBtn, 'Saving…', '/settings/ai/connection/save/', () => window.location.reload())
  );

  render();
});
