/* One document owns one attempt. Server time and grading remain authoritative. */
(() => {
  'use strict';
  const app = document.getElementById('quiz-app');
  if (!app) return;
  const el = id => document.getElementById(id);
  const csrf = app.querySelector('[name=csrfmiddlewaretoken]').value;
  let attemptId, token, position = -1, active = false, starting = false;
  let departed = false, busy = false, deadline = 0, lastHeartbeat = 0;
  let announced = false;

  function finish(status, reason) {
    active = false;
    starting = false;
    el('instructions').hidden = true;
    el('question-panel').hidden = true;
    el('finished').hidden = false;
    el('finish-title').textContent = status === 'completed' ? 'Quiz submitted' : 'Attempt locked';
    el('finish-message').textContent = status === 'completed'
      ? 'Your answers have been saved for your instructor. You may now leave this page.'
      : `${reason || 'Your attempt cannot continue.'} Contact your instructor; do not start another attempt without permission.`;
    el('notice').textContent = '';
  }

  function render(state) {
    if (departed) return;
    if (state.status !== 'active') { finish(state.status, state.reason); return; }
    active = true;
    el('instructions').hidden = true;
    el('question-panel').hidden = false;
    // performance.now is monotonic; changing the student's system clock cannot add time.
    deadline = performance.now() + Math.max(0, Date.parse(state.deadline) - Date.parse(state.server_time));
    if (position !== state.position) {
      position = state.position;
      announced = false;
      el('notice').textContent = '';
      el('progress').textContent = `Question ${position + 1} of ${state.total}`;
      el('topic').textContent = state.question.topic;
      el('prompt').textContent = state.question.prompt;
      el('options').replaceChildren();
      state.question.options.forEach((option, index) => {
        const label = document.createElement('label');
        const input = document.createElement('input');
        input.type = 'radio'; input.name = 'choice'; input.value = String(index);
        const text = document.createElement('span'); text.textContent = option;
        label.append(input, text); el('options').append(label);
      });
      el('prompt').focus();
    }
  }

  async function post(url, values) {
    const data = new FormData();
    data.append('csrfmiddlewaretoken', csrf);
    Object.entries(values).forEach(([key, value]) => data.append(key, value));
    const response = await fetch(url, {method: 'POST', body: data, credentials: 'same-origin', cache: 'no-store'});
    if (!response.ok) throw new Error(response.status === 403 ? 'Access denied or session expired.' : 'The request could not be saved.');
    return response.json();
  }

  function depart() {
    if ((!active && !starting) || departed) return;
    departed = true;
    if (attemptId) {
      const data = new FormData();
      data.append('csrfmiddlewaretoken', csrf); data.append('token', token);
      // keepalive allows transmission while the document is being hidden/unloaded.
      fetch(`/api/attempt/${attemptId}/lock/`, {method: 'POST', body: data, keepalive: true,
        credentials: 'same-origin'}).catch(() => {});
    }
    finish('locked', 'The quiz page was left or lost focus.');
  }

  async function action(kind, values = {}) {
    if (!active || busy || departed) return;
    busy = true; el('answer-button').disabled = true;
    try {
      const state = await post(`/api/attempt/${attemptId}/${kind}/`, {token, ...values});
      lastHeartbeat = performance.now();
      render(state);
      if (active) el('notice').textContent = '';
    } catch (error) {
      // Do not optimistically advance: a retry with the old position is idempotent.
      el('notice').textContent = `${error.message} Reconnecting; the server timer continues.`;
    } finally { busy = false; el('answer-button').disabled = false; }
  }

  el('start-form').addEventListener('submit', async event => {
    event.preventDefault();
    if (starting || !el('consent').checked) return;
    starting = true; el('start-button').disabled = true;
    try {
      const state = await post(app.dataset.startUrl, {consent: 'yes'});
      attemptId = state.attempt_id; token = state.token;
      if (departed) { departed = false; active = true; depart(); return; }
      starting = false; lastHeartbeat = performance.now(); render(state);
    } catch (error) {
      starting = false;
      // The server may have received Start even if the response was lost.
      finish('locked', `${error.message} If the request reached the server, the attempt is reserved and will lock.`);
    }
  });

  el('answer-form').addEventListener('submit', event => {
    event.preventDefault();
    const selected = app.querySelector('input[name=choice]:checked');
    if (!selected) { el('notice').textContent = 'Select an answer before submitting.'; return; }
    action('answer', {position, choice: selected.value});
  });
  document.addEventListener('visibilitychange', () => { if (document.hidden) depart(); });
  window.addEventListener('blur', depart);
  window.addEventListener('pagehide', depart);
  window.addEventListener('pageshow', event => { if (event.persisted) depart(); });
  window.addEventListener('beforeunload', event => {
    if (!active && !starting) return;
    depart(); event.preventDefault(); event.returnValue = '';
  });
  setInterval(() => {
    if (!active || departed) return;
    const now = performance.now();
    const remaining = Math.max(0, Math.ceil((deadline - now) / 1000));
    el('timer').textContent = `${remaining}s remaining`;
    el('timer').classList.toggle('urgent', remaining <= 10);
    if (remaining <= 10 && !announced) {
      announced = true; el('notice').textContent = 'Ten seconds or fewer remain for this question.';
    }
    if (now - lastHeartbeat >= 20000) { depart(); return; }
    if (remaining === 0) action('answer', {position, choice: ''});
    else if (now - lastHeartbeat >= 5000) action('heartbeat');
  }, 250);
})();
