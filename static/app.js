// BillBack Frontend Application Logic
document.addEventListener('DOMContentLoaded', () => {
  // State
  let currentCaseId = null;
  let eventSource = null;
  let totalRecoveredOverall = 0;
  let isRunning = false;

  // Formatting helper: Indian digit grouping
  const formatINR = (amt) => {
    const val = Number(amt) || 0;
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 2
    }).format(val);
  };

  // Elements
  const auditForm = document.getElementById('audit-form');
  const runBtn = document.getElementById('run-btn');
  const runText = document.getElementById('run-text');
  const demoBtn = document.getElementById('demo-btn');
  const recoveredCounter = document.getElementById('recovered-counter');
  const sidebar = document.getElementById('sidebar');
  const toggleSidebarBtn = document.getElementById('toggle-sidebar-btn');
  const casesList = document.getElementById('cases-list');
  const caseCountBadge = document.getElementById('case-count-badge');
  const refreshCasesBtn = document.getElementById('refresh-cases-btn');
  const driftAlertsList = document.getElementById('drift-alerts-list');
  const timeline = document.getElementById('timeline');
  const timelineEmpty = document.getElementById('timeline-empty');
  const liveDot = document.getElementById('live-dot');
  const stepCounter = document.getElementById('step-counter');
  
  // Evidence & Email Elements
  const findingsContainer = document.getElementById('findings-container');
  const findingsCount = document.getElementById('findings-count');
  const totalClaimedEl = document.getElementById('total-claimed');
  const claimBadge = document.getElementById('claim-badge');
  const emailCard = document.getElementById('email-card');
  const emailTo = document.getElementById('email-to');
  const emailSubject = document.getElementById('email-subject');
  const emailBody = document.getElementById('email-body');
  const approveBtn = document.getElementById('approve-btn');
  const approvalStatusBadge = document.getElementById('approval-status-badge');
  const negotiationCard = document.getElementById('negotiation-card');
  const chatThread = document.getElementById('chat-thread');
  const outcomeCard = document.getElementById('outcome-card');
  const outcomeClaimed = document.getElementById('outcome-claimed');
  const outcomeRecovered = document.getElementById('outcome-recovered');
  const outcomeStatusBox = document.getElementById('outcome-status-box');
  const caseStatusText = document.getElementById('case-status-text');
  const caseStatusDot = document.getElementById('case-status-dot');

  // Input & Dropzone Elements
  const invoiceInput = document.getElementById('invoice-input');
  const invoiceDropzone = document.getElementById('invoice-dropzone');
  const invoicePreview = document.getElementById('invoice-preview');
  const slipInput = document.getElementById('slip-input');
  const slipDropzone = document.getElementById('slip-dropzone');
  const slipPreview = document.getElementById('slip-preview');
  const agreementInput = document.getElementById('agreement-input');
  const agreementDropzone = document.getElementById('agreement-dropzone');
  const agreementPreview = document.getElementById('agreement-preview');
  const agreementText = document.getElementById('agreement-text');
  const tabChatBtn = document.getElementById('tab-chat-btn');
  const tabVoiceBtn = document.getElementById('tab-voice-btn');
  const chatTabPanel = document.getElementById('chat-tab-panel');
  const voiceTabPanel = document.getElementById('voice-tab-panel');
  const micBtn = document.getElementById('mic-btn');
  const micText = document.getElementById('mic-text');
  const micIcon = document.getElementById('mic-icon');
  const speechLang = document.getElementById('speech-lang');
  const minAcceptSlider = document.getElementById('min-accept');
  const sliderVal = document.getElementById('slider-val');
  const autonomousToggle = document.getElementById('autonomous-toggle');
  const vendorEmailInput = document.getElementById('vendor-email');
  const vendorModeSelect = document.getElementById('vendor-mode');

  let activeAgreementTab = 'chat';
  let stepIndex = 0;
  let activeToolCards = {};

  // Slider change
  minAcceptSlider.addEventListener('input', (e) => {
    sliderVal.textContent = `${e.target.value}%`;
  });

  // Sidebar Toggle
  toggleSidebarBtn.addEventListener('click', () => {
    sidebar.classList.toggle('-translate-x-full');
  });

  // Tab switching: Chat screenshot vs Voice/Text
  tabChatBtn.addEventListener('click', () => {
    activeAgreementTab = 'chat';
    tabChatBtn.className = 'px-2 py-0.5 rounded bg-brand-100 text-brand-700 font-medium';
    tabVoiceBtn.className = 'px-2 py-0.5 rounded text-slate-500 hover:text-slate-800';
    chatTabPanel.classList.remove('hidden');
    voiceTabPanel.classList.add('hidden');
  });

  tabVoiceBtn.addEventListener('click', () => {
    activeAgreementTab = 'voice';
    tabVoiceBtn.className = 'px-2 py-0.5 rounded bg-brand-100 text-brand-700 font-medium';
    tabChatBtn.className = 'px-2 py-0.5 rounded text-slate-500 hover:text-slate-800';
    voiceTabPanel.classList.remove('hidden');
    chatTabPanel.classList.add('hidden');
  });

  // Generic Dropzone Wire-up
  const setupDropzone = (dropzone, input, preview, placeholderHtml) => {
    dropzone.addEventListener('click', () => input.click());
    
    dropzone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropzone.classList.add('border-brand-500', 'bg-brand-50');
    });

    ['dragleave', 'dragend'].forEach(ev => {
      dropzone.addEventListener(ev, () => {
        dropzone.classList.remove('border-brand-500', 'bg-brand-50');
      });
    });

    dropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropzone.classList.remove('border-brand-500', 'bg-brand-50');
      if (e.dataTransfer.files.length) {
        input.files = e.dataTransfer.files;
        updatePreview(input, preview, placeholderHtml);
      }
    });

    input.addEventListener('change', () => updatePreview(input, preview, placeholderHtml));
  };

  const updatePreview = (input, preview, placeholderHtml) => {
    if (input.files && input.files[0]) {
      const file = input.files[0];
      preview.innerHTML = `
        <div class="flex items-center justify-center space-x-2 text-brand-700 font-semibold text-xs py-1">
          <svg class="w-4 h-4 text-emerald-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
          <span class="truncate max-w-[200px]">${file.name}</span>
          <span class="text-[10px] text-slate-400 font-normal">(${(file.size / 1024).toFixed(1)} KB)</span>
        </div>
      `;
    } else {
      preview.innerHTML = placeholderHtml;
    }
  };

  setupDropzone(invoiceDropzone, invoiceInput, invoicePreview, invoicePreview.innerHTML);
  setupDropzone(slipDropzone, slipInput, slipPreview, slipPreview.innerHTML);
  setupDropzone(agreementDropzone, agreementInput, agreementPreview, agreementPreview.innerHTML);

  // Web Speech API (Voice-to-Text Agreement)
  let recognition = null;
  let isRecording = false;

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (SpeechRecognition) {
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;

    recognition.onstart = () => {
      isRecording = true;
      micBtn.classList.add('bg-red-50', 'text-red-700', 'border-red-300');
      micText.textContent = 'Listening...';
      micIcon.classList.add('animate-pulse', 'text-red-600');
    };

    recognition.onresult = (event) => {
      let transcript = '';
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        transcript += event.results[i][0].transcript;
      }
      agreementText.value = transcript;
    };

    recognition.onerror = (e) => {
      console.warn('Speech recognition error:', e.error);
      stopRecording();
    };

    recognition.onend = () => {
      stopRecording();
    };

    const stopRecording = () => {
      isRecording = false;
      micBtn.classList.remove('bg-red-50', 'text-red-700', 'border-red-300');
      micText.textContent = 'Speak Agreement';
      micIcon.classList.remove('animate-pulse', 'text-red-600');
    };

    micBtn.addEventListener('click', () => {
      if (isRecording) {
        recognition.stop();
      } else {
        recognition.lang = speechLang.value;
        try {
          recognition.start();
        } catch (err) {
          console.error(err);
        }
      }
    });
  } else {
    micBtn.disabled = true;
    micBtn.title = 'Web Speech API not supported on this browser';
    micText.textContent = 'Mic unavailable';
  }

  // Fetch past cases & drift alerts on load
  const loadSidebarData = async () => {
    try {
      // 1. Past cases
      const resCases = await fetch('/api/cases');
      if (resCases.ok) {
        const cases = await resCases.json();
        renderPastCases(cases);
      }

      // 2. Drift alerts
      const resDrift = await fetch('/api/drift');
      if (resDrift.ok) {
        const driftData = await resDrift.json();
        renderDriftAlerts(driftData.alerts || []);
      }
    } catch (err) {
      console.error('Failed to load sidebar data:', err);
    }
  };

  const renderPastCases = (cases) => {
    caseCountBadge.textContent = `${cases.length} cases`;
    if (!cases.length) {
      casesList.innerHTML = `<div class="text-xs text-slate-400 italic py-2 text-center">No cases processed yet.</div>`;
      return;
    }

    casesList.innerHTML = cases.map(c => `
      <div class="p-2.5 rounded-lg border border-slate-100 hover:border-slate-200 hover:bg-slate-50 transition-colors text-xs cursor-pointer">
        <div class="flex items-center justify-between font-semibold text-slate-800">
          <span class="truncate max-w-[140px]">${c.vendor || 'Vendor Audit'}</span>
          <span class="text-emerald-700 font-bold">${formatINR(c.recovered || 0)}</span>
        </div>
        <div class="flex items-center justify-between text-[11px] text-slate-400 mt-1">
          <span>${c.invoice_no || c.id.slice(0, 14)}</span>
          <span class="px-1.5 py-0.2 rounded ${c.status === 'completed' ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-600'}">${c.status || 'saved'}</span>
        </div>
      </div>
    `).join('');

    // Update global recovered counter
    const totalRecovered = cases.reduce((sum, c) => sum + (Number(c.recovered) || 0), 0);
    animateCounter(totalRecoveredOverall, totalRecovered, 800);
    totalRecoveredOverall = totalRecovered;
  };

  const renderDriftAlerts = (alerts) => {
    if (!alerts.length) {
      driftAlertsList.innerHTML = `<div class="text-xs text-slate-400 italic py-2 text-center">No vendor price drift detected.</div>`;
      return;
    }

    driftAlertsList.innerHTML = alerts.map(a => `
      <div class="p-2 rounded-lg bg-amber-50/70 border border-amber-200/80 text-xs">
        <div class="flex items-center justify-between font-semibold text-amber-900">
          <span>${a.item}</span>
          <span class="text-red-600 font-bold">+${a.increase_pct}%</span>
        </div>
        <p class="text-[11px] text-amber-800 mt-0.5">${a.vendor} · ${formatINR(a.prev_rate)} → ${formatINR(a.curr_rate)}</p>
      </div>
    `).join('');
  };

  refreshCasesBtn.addEventListener('click', loadSidebarData);
  loadSidebarData();

  // Reset workspace for new case
  const resetWorkspace = () => {
    stepIndex = 0;
    activeToolCards = {};
    stepCounter.textContent = '0 steps';
    timeline.innerHTML = '';
    timelineEmpty.classList.remove('hidden');
    timeline.appendChild(timelineEmpty);
    
    findingsContainer.innerHTML = `<div class="text-xs text-slate-400 italic text-center py-4">Evaluating discrepancies...</div>`;
    findingsCount.textContent = '0 findings';
    totalClaimedEl.textContent = '₹0.00';
    claimBadge.textContent = 'Auditing';
    claimBadge.className = 'text-[11px] font-medium px-2 py-1 rounded bg-amber-900/60 text-amber-300';
    
    emailCard.classList.add('hidden');
    negotiationCard.classList.add('hidden');
    chatThread.innerHTML = '';
    outcomeCard.classList.add('hidden');

    caseStatusDot.className = 'w-2 h-2 rounded-full bg-amber-500 animate-pulse';
    caseStatusText.textContent = 'Running';
    liveDot.className = 'w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse';
  };

  // One-Click Demo Case Button (Bill 5 + Slip 5 with duplicate oil)
  demoBtn.addEventListener('click', async () => {
    if (isRunning) return;
    resetWorkspace();
    setRunning(true);

    try {
      const vendorMode = vendorModeSelect.value;
      const minAccept = minAcceptSlider.value;
      const autonomous = autonomousToggle.checked;

      const res = await fetch('/api/cases/demo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          vendor_mode: vendorMode,
          min_accept_percent: Number(minAccept),
          autonomous: autonomous
        })
      });

      if (!res.ok) throw new Error('Failed to create demo case');
      const data = await res.json();
      currentCaseId = data.case_id;
      connectSSE(currentCaseId);
    } catch (err) {
      alert(`Demo Error: ${err.message}`);
      setRunning(false);
    }
  });

  // Run Audit Form Submit
  auditForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (isRunning) return;

    if (!invoiceInput.files || !invoiceInput.files[0]) {
      alert('Please select an Invoice/Bill image.');
      return;
    }

    resetWorkspace();
    setRunning(true);

    try {
      const formData = new FormData();
      formData.append('invoice', invoiceInput.files[0]);
      
      if (slipInput.files && slipInput.files[0]) {
        formData.append('slip', slipInput.files[0]);
      }

      if (activeAgreementTab === 'chat' && agreementInput.files && agreementInput.files[0]) {
        formData.append('agreement_file', agreementInput.files[0]);
      } else if (activeAgreementTab === 'voice' && agreementText.value.trim()) {
        formData.append('agreement_text', agreementText.value.trim());
      }

      formData.append('vendor_email', vendorEmailInput.value || 'vendor@example.com');
      formData.append('vendor_mode', vendorModeSelect.value);
      formData.append('min_accept_percent', minAcceptSlider.value);
      formData.append('autonomous', autonomousToggle.checked ? 'true' : 'false');

      const res = await fetch('/api/cases', {
        method: 'POST',
        body: formData
      });

      if (!res.ok) throw new Error('Failed to upload and start case.');
      const data = await res.json();
      currentCaseId = data.case_id;
      connectSSE(currentCaseId);
    } catch (err) {
      alert(`Error starting audit: ${err.message}`);
      setRunning(false);
    }
  });

  // Connect to SSE Stream
  const connectSSE = (caseId) => {
    if (eventSource) {
      eventSource.close();
    }

    eventSource = new EventSource(`/api/cases/${caseId}/stream`);

    eventSource.addEventListener('tool_start', (e) => {
      const payload = JSON.parse(e.data);
      handleToolStart(payload);
    });

    eventSource.addEventListener('tool_result', (e) => {
      const payload = JSON.parse(e.data);
      handleToolResult(payload);
    });

    eventSource.addEventListener('email_draft', (e) => {
      const payload = JSON.parse(e.data);
      handleEmailDraft(payload);
    });

    eventSource.addEventListener('awaiting_approval', (e) => {
      const payload = JSON.parse(e.data);
      handleAwaitingApproval(payload);
    });

    eventSource.addEventListener('vendor_reply', (e) => {
      const payload = JSON.parse(e.data);
      handleVendorReply(payload);
    });

    eventSource.addEventListener('agent_reply', (e) => {
      const payload = JSON.parse(e.data);
      handleAgentReply(payload);
    });

    eventSource.addEventListener('outcome', (e) => {
      const payload = JSON.parse(e.data);
      handleOutcome(payload);
    });

    eventSource.addEventListener('error', (e) => {
      console.warn('SSE event or disconnect:', e);
      let errMsg = 'Connection interrupted or API error occurred.';
      if (e.data) {
        try {
          const parsed = JSON.parse(e.data);
          if (parsed.message) errMsg = parsed.message;
        } catch (_) {}
      }
      
      // If error occurred before outcome, show friendly error banner with Retry
      const existingOutcome = document.getElementById('outcome-card');
      if (existingOutcome && existingOutcome.classList.contains('hidden')) {
        const errorCard = document.createElement('div');
        errorCard.className = 'p-3.5 rounded-xl border border-red-200 bg-red-50 text-xs text-red-800 space-y-2 animate-fade-in';
        errorCard.innerHTML = `
          <div class="flex items-center space-x-2 font-bold text-red-900">
            <svg class="w-4 h-4 text-red-600 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            <span>Audit Interrupted</span>
          </div>
          <p class="text-[11px] text-red-700">${errMsg}</p>
          <button type="button" onclick="window.location.reload()" class="px-2.5 py-1 bg-red-600 hover:bg-red-700 text-white rounded font-medium text-[11px] transition-colors flex items-center space-x-1">
            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
            <span>Retry Audit</span>
          </button>
        `;
        timeline.appendChild(errorCard);
        caseStatusDot.className = 'w-2 h-2 rounded-full bg-red-500';
        caseStatusText.textContent = 'Error';
      } else {
        caseStatusDot.className = 'w-2 h-2 rounded-full bg-emerald-500';
        caseStatusText.textContent = 'Completed';
      }

      liveDot.className = 'w-2.5 h-2.5 rounded-full bg-slate-300';
      setRunning(false);
      loadSidebarData();
    });

    eventSource.addEventListener('end', () => {
      eventSource.close();
      setRunning(false);
      loadSidebarData();
    });
  };

  // Tool Start Event
  const handleToolStart = (data) => {
    stepIndex++;
    stepCounter.textContent = `${stepIndex} steps`;
    if (timelineEmpty) timelineEmpty.classList.add('hidden');

    const cardId = `tool-card-${stepIndex}`;
    const toolName = data.tool;
    const docType = data.doc_type ? ` [${data.doc_type}]` : '';

    const card = document.createElement('div');
    card.id = cardId;
    card.className = 'p-3 rounded-xl border border-slate-200 bg-white card-shadow transition-all space-y-2 animate-fade-in';
    card.innerHTML = `
      <div class="flex items-center justify-between">
        <div class="flex items-center space-x-2">
          <div class="w-6 h-6 rounded-md bg-brand-50 text-brand-600 flex items-center justify-center text-xs font-bold font-mono">
            ${stepIndex}
          </div>
          <span class="text-xs font-bold text-slate-800 font-mono">${toolName}${docType}</span>
        </div>
        <div class="flex items-center space-x-1.5 status-badge">
          <svg class="animate-spin w-3.5 h-3.5 text-brand-600" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
          <span class="text-[11px] text-slate-500 font-medium">Running...</span>
        </div>
      </div>
      <p class="text-xs text-slate-500 tool-summary">Reading and analyzing document data...</p>
    `;

    timeline.appendChild(card);
    card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    activeToolCards[toolName] = card;
  };

  // Tool Result Event
  const handleToolResult = (data) => {
    const toolName = data.tool;
    const card = activeToolCards[toolName];
    if (!card) return;

    // Update status badge to completed
    const badge = card.querySelector('.status-badge');
    if (badge) {
      badge.innerHTML = `
        <svg class="w-4 h-4 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
        <span class="text-[11px] text-emerald-700 font-semibold">Done</span>
      `;
    }

    // Summary generator
    const summaryEl = card.querySelector('.tool-summary');
    let summaryText = 'Step completed successfully.';

    if (toolName === 'extract_document') {
      const res = data.result || {};
      const itemCount = (res.items || []).length;
      summaryText = `Extracted ${itemCount} items from ${res.vendor || 'document'} (Grand Total: ${formatINR(res.grand_total || 0)})`;
    } else if (toolName === 'read_agreement') {
      const res = data.result || {};
      const ratesCount = Object.keys(res.agreed_rates || {}).length;
      summaryText = `Found ${ratesCount} agreed price terms. Free delivery: ${res.free_delivery === true ? 'Yes' : 'No'}`;
    } else if (toolName === 'run_audit') {
      const res = data.result || {};
      const findings = res.findings || [];
      const overcharge = res.total_overcharge || 0;
      summaryText = `Audit finished: ${findings.length} findings, ${formatINR(overcharge)} total overcharge.`;
      renderFindings(findings, overcharge);
    } else if (toolName === 'send_dispute_email') {
      const res = data.result || {};
      summaryText = `Dispute email dispatched to ${res.recipient || 'vendor'} (${res.status || 'sent'}).`;
    }

    if (summaryEl) summaryEl.textContent = summaryText;

    // Expandable Raw JSON
    const details = document.createElement('details');
    details.className = 'text-[11px] text-slate-500 pt-1 border-t border-slate-100';
    details.innerHTML = `
      <summary class="cursor-pointer hover:text-brand-600 font-medium select-none">View raw JSON payload</summary>
      <pre class="mt-1 p-2 rounded bg-slate-900 text-slate-200 font-mono text-[10px] overflow-x-auto max-h-40">${JSON.stringify(data.result, null, 2)}</pre>
    `;
    card.appendChild(details);
  };

  // Render Findings in Column 3
  const renderFindings = (findings, totalOvercharge) => {
    findingsCount.textContent = `${findings.length} findings`;
    totalClaimedEl.textContent = formatINR(totalOvercharge);

    if (totalOvercharge > 0) {
      claimBadge.textContent = 'Overcharge Found';
      claimBadge.className = 'text-[11px] font-semibold px-2 py-1 rounded bg-red-900/60 text-red-200';
    } else {
      claimBadge.textContent = 'Zero Discrepancy';
      claimBadge.className = 'text-[11px] font-semibold px-2 py-1 rounded bg-emerald-900/60 text-emerald-200';
    }

    if (!findings.length) {
      findingsContainer.innerHTML = `
        <div class="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 text-center font-medium">
          Clean bill verified. Line item arithmetic, delivery notes, and contract rates are 100% accurate.
        </div>
      `;
      return;
    }

    findingsContainer.innerHTML = findings.map(f => {
      const typeBadges = {
        line_math: 'bg-amber-100 text-amber-800',
        subtotal: 'bg-orange-100 text-orange-800',
        delivery_fee: 'bg-purple-100 text-purple-800',
        rate: 'bg-red-100 text-red-800',
        not_delivered: 'bg-rose-100 text-rose-800',
        tax_on_overcharge: 'bg-blue-100 text-blue-800'
      };
      const badgeCls = typeBadges[f.type] || 'bg-slate-100 text-slate-800';

      return `
        <div class="p-2.5 rounded-lg border border-slate-200 bg-slate-50/70 text-xs space-y-1">
          <div class="flex items-center justify-between">
            <span class="font-bold text-slate-800 capitalize">${f.item}</span>
            <span class="font-bold text-red-600">${formatINR(f.overcharge)}</span>
          </div>
          <div class="flex items-center space-x-2">
            <span class="text-[10px] font-semibold px-1.5 py-0.5 rounded ${badgeCls}">${f.type}</span>
            <span class="text-[11px] text-slate-500 truncate">${f.reason}</span>
          </div>
        </div>
      `;
    }).join('');
  };

  // Dispute Email Draft Event
  const handleEmailDraft = (data) => {
    emailCard.classList.remove('hidden');
    emailTo.textContent = data.to;
    emailSubject.value = data.subject;
    emailBody.value = data.body;
  };

  // Awaiting Human Approval Event
  const handleAwaitingApproval = (data) => {
    emailCard.classList.remove('hidden');
    approvalStatusBadge.textContent = 'Action Required';
    approvalStatusBadge.className = 'text-[10px] font-bold px-2 py-0.5 rounded bg-red-100 text-red-800 animate-pulse';
    
    approveBtn.classList.remove('hidden');
    approveBtn.disabled = false;
    approveBtn.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    caseStatusDot.className = 'w-2 h-2 rounded-full bg-red-500 animate-ping';
    caseStatusText.textContent = 'Waiting for your approval';
  };

  // Approve Button Click
  approveBtn.addEventListener('click', async () => {
    if (!currentCaseId) return;
    approveBtn.disabled = true;
    approveBtn.innerHTML = `
      <svg class="animate-spin w-4 h-4 text-white" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
      <span>Sending Dispute...</span>
    `;

    try {
      const res = await fetch(`/api/cases/${currentCaseId}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          edited_subject: emailSubject.value,
          edited_body: emailBody.value
        })
      });
      if (!res.ok) throw new Error('Failed to approve dispute');
      
      approvalStatusBadge.textContent = 'Approved & Sent';
      approvalStatusBadge.className = 'text-[10px] font-semibold px-2 py-0.5 rounded bg-emerald-100 text-emerald-800';
      approveBtn.classList.add('hidden');
    } catch (err) {
      alert(`Approval error: ${err.message}`);
      approveBtn.disabled = false;
    }
  });

  // Vendor Reply Event
  const handleVendorReply = (data) => {
    negotiationCard.classList.remove('hidden');
    const bubble = document.createElement('div');
    bubble.className = 'flex flex-col space-y-1 items-start';
    bubble.innerHTML = `
      <div class="flex items-center space-x-1.5 text-[11px] text-amber-800 font-semibold">
        <span class="w-1.5 h-1.5 rounded-full bg-amber-500"></span>
        <span>${data.sender} (Round ${data.round})</span>
        <span class="text-slate-400 font-normal">· Offer: ${formatINR(data.offer || 0)}</span>
      </div>
      <div class="p-2.5 rounded-xl rounded-tl-none bg-amber-50/80 border border-amber-200 text-xs text-slate-800 max-w-[90%] shadow-sm">
        ${data.reply.replace(/\n/g, '<br>')}
      </div>
    `;
    chatThread.appendChild(bubble);
    bubble.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  };

  // Agent Reply Event
  const handleAgentReply = (data) => {
    negotiationCard.classList.remove('hidden');
    const bubble = document.createElement('div');
    bubble.className = 'flex flex-col space-y-1 items-end';
    
    const isAccepted = data.action === 'ACCEPT';
    const isEscalated = data.action === 'ESCALATE';
    const bubbleColor = isAccepted ? 'bg-emerald-600 text-white' : (isEscalated ? 'bg-red-600 text-white' : 'bg-brand-600 text-white');

    bubble.innerHTML = `
      <div class="flex items-center space-x-1.5 text-[11px] text-brand-700 font-semibold">
        <span>${data.sender}</span>
        <span class="px-1.5 py-0.2 rounded text-[10px] ${isAccepted ? 'bg-emerald-100 text-emerald-800' : 'bg-brand-100 text-brand-800'}">${data.action}</span>
      </div>
      <div class="p-2.5 rounded-xl rounded-tr-none ${bubbleColor} text-xs max-w-[90%] shadow-sm">
        ${data.message.replace(/\n/g, '<br>')}
      </div>
    `;
    chatThread.appendChild(bubble);
    bubble.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  };

  // Outcome Event
  const handleOutcome = (data) => {
    outcomeCard.classList.remove('hidden');
    outcomeClaimed.textContent = formatINR(data.claimed || 0);
    outcomeRecovered.textContent = formatINR(data.recovered || 0);

    const isSettled = (data.recovered || 0) > 0;
    outcomeStatusBox.className = `p-3 rounded-lg text-xs font-semibold ${isSettled ? 'bg-emerald-100 text-emerald-900 border border-emerald-200' : 'bg-slate-100 text-slate-800'}`;
    outcomeStatusBox.innerHTML = `
      <div class="flex items-center space-x-2">
        <svg class="w-4 h-4 text-emerald-700 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
        <span>${data.status}</span>
      </div>
    `;

    outcomeCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  };

  const setRunning = (running) => {
    isRunning = running;
    runBtn.disabled = running;
    demoBtn.disabled = running;
    if (running) {
      runBtn.classList.add('opacity-75', 'cursor-not-allowed');
      runText.textContent = 'Auditing Case...';
    } else {
      runBtn.classList.remove('opacity-75', 'cursor-not-allowed');
      runText.textContent = 'Run Autonomous Audit';
    }
  };

  // Counter Number Animation
  const animateCounter = (start, end, duration) => {
    if (start === end) {
      recoveredCounter.textContent = formatINR(end);
      return;
    }
    const range = end - start;
    let current = start;
    const increment = end > start ? 1 : -1;
    const stepTime = Math.abs(Math.floor(duration / 30));
    const timer = setInterval(() => {
      current += range / 30;
      if ((increment > 0 && current >= end) || (increment < 0 && current <= end)) {
        current = end;
        clearInterval(timer);
      }
      recoveredCounter.textContent = formatINR(current);
    }, stepTime);
  };
});

