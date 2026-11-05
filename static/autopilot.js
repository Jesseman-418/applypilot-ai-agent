const answerLabels = {
  full_name: 'Full name', email: 'Email', phone: 'Phone', linkedin: 'LinkedIn URL',
  github: 'GitHub URL', location: 'Current location', relocation: 'Relocation preference',
  notice_period: 'Notice period / earliest start', work_authorization: 'Work authorization and sponsorship',
  interests_and_constraints: 'Role interests, locations, seniority, and hard constraints',
  saved_answers: 'Other saved questions and exact answers (one question and answer per line)',
};
let activeRun = localStorage.getItem('applypilot-active-run');
let runPoll;

async function loadAutopilot() {
  try {
    const settings = await api('/api/autopilot/settings');
    const fields = $('#autopilot-answer-fields');
    fields.innerHTML = Object.entries(answerLabels).map(([name, label]) => {
      const multiline = ['interests_and_constraints', 'saved_answers', 'work_authorization'].includes(name);
      const control = multiline
        ? `<textarea name="${name}" rows="4">${esc(settings[name] || '')}</textarea>`
        : `<input name="${name}" value="${esc(settings[name] || '')}">`;
      return `<label style="display:block;margin:14px 0;font-size:12px">${label}${control}</label>`;
    }).join('');
    $('#autopilot-settings-form').elements.auto_submit.checked = !!settings.auto_submit;
    await loadDocuments();
    if (activeRun) pollRun();
  } catch (error) { notify(error.message); }
}

async function loadDocuments() {
  const documents = await api('/api/documents');
  $('#document-list').innerHTML = documents.map(document =>
    `<article class="job-row"><div><strong>${esc(document.name)}</strong><p>${esc(document.kind)} · ${esc(document.description)}</p></div></article>`
  ).join('');
}

$('#autopilot-settings-form').addEventListener('submit', async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const settings = Object.fromEntries(Object.keys(answerLabels).map(name => [name, form.elements[name].value.trim()]));
  settings.auto_submit = form.elements.auto_submit.checked;
  try {
    await api('/api/autopilot/settings', {method: 'PUT', body: JSON.stringify(settings)});
    notify('Application settings saved');
  } catch (error) { notify(error.message); }
});

$('#document-form').addEventListener('submit', async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector('button');
  button.disabled = true;
  try {
    for (const file of form.elements.documents.files) {
      const body = new FormData();
      body.set('file', file);
      body.set('kind', form.elements.kind.value);
      body.set('description', form.elements.description.value);
      const response = await fetch('/api/documents', {method: 'POST', body});
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Upload failed');
    }
    form.reset();
    await loadDocuments();
    notify('Documents saved locally');
  } catch (error) { notify(error.message); }
  finally { button.disabled = false; }
});

$('#autopilot-link-form').addEventListener('submit', async event => {
  event.preventDefault();
  $('#autopilot-start').disabled = true;
  try {
    const run = await api('/api/autopilot', {method: 'POST', body: JSON.stringify({url: $('#autopilot-url').value})});
    activeRun = run.id;
    localStorage.setItem('applypilot-active-run', activeRun);
    await pollRun();
  } catch (error) { notify(error.message); $('#autopilot-start').disabled = false; }
});

$('#autopilot-continue').addEventListener('click', async () => {
  try {
    await api(`/api/autopilot/${activeRun}/continue`, {method: 'POST'});
    $('#autopilot-continue').hidden = true;
    await pollRun();
  } catch (error) { notify(error.message); }
});

async function pollRun() {
  clearTimeout(runPoll);
  try {
    const run = await api(`/api/autopilot/${activeRun}`);
    const busy = ['running', 'paused', 'submitting'].includes(run.state);
    $('#autopilot-start').disabled = busy;
    $('#autopilot-continue').hidden = run.state !== 'paused';
    const drafts = run.linkedin?.drafts || [];
    $('#autopilot-run').innerHTML = `<section class="detail-section"><h3>${esc(run.state.replaceAll('_', ' '))}</h3><p>${esc(run.message)}</p>${run.company ? `<p>${esc(run.company)} · ${esc(run.role)}</p>` : ''}${run.error_detail ? `<p>${esc(run.error_detail)}</p>` : ''}${run.fit?.reasons ? `<ul>${run.fit.reasons.map(reason => `<li>${esc(reason)}</li>`).join('')}</ul>` : ''}<ul>${(run.events || []).map(message => `<li>${esc(message)}</li>`).join('')}</ul></section><section class="detail-section"><h3>LinkedIn outreach drafts</h3><p>${esc(run.linkedin?.message || 'Connections will be checked after the role passes your fit rules.')}</p>${drafts.map(draft => `<article><strong>${esc(draft.name)}</strong><p>${esc(draft.evidence)}</p><textarea rows="6" aria-label="Outreach draft">${esc(draft.message)}</textarea>${/^https:\/\/([a-z]+\.)?linkedin\.com\/in\//.test(draft.url) ? `<a href="${esc(draft.url)}" target="_blank" rel="noopener">Open connection profile</a>` : ''}</article>`).join('')}</section>`;
    if (busy) runPoll = setTimeout(pollRun, 2500);
  } catch (error) {
    $('#autopilot-start').disabled = false;
    notify(error.message);
  }
}
loadAutopilot();
