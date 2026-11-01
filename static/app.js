// BillBack Frontend Application Logic
document.addEventListener('DOMContentLoaded', () => {
  // State
  let currentCaseId = null;
  let eventSource = null;
  let totalRecoveredOverall = 0;
  let isRunning = false;
  let allCases = [];
  let showAllCases = false;
  let currentCaseTerminalStatus = null;

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
  const showAllCasesBtn = document.getElementById('show-all-cases-btn');
  const devControls = document.getElementById('dev-controls');
  const clearCasesBtn = document.getElementById('clear-cases-btn');
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
  const checkChips = document.getElementById('check-chips');
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
  const caseStatusIndicator = document.getElementById('case-status-indicator');

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

  // Status Pill Manager
  // Supported States: Ready / Running / Awaiting approval / Settled / Needs review / Error
  const updateStatusPill = (status) => {
    if (!caseStatusDot || !caseStatusText) return;
    switch (status) {
      case 'Running':
        caseStatusDot.className = 'w-2 h-2 rounded-full bg-amber-500 animate-pulse';
        caseStatusText.textContent = 'Running';
        if (caseStatusIndicator) caseStatusIndicator.className = 'hidden sm:flex items-center space-x-2 text-xs font-semibold text-amber-700 bg-amber-50 px-2.5 py-1 rounded-full border border-amber-200';
        break;
      case 'Awaiting approval':
        caseStatusDot.className = 'w-2 h-2 rounded-full bg-red-500 animate-ping';
        caseStatusText.textContent = 'Awaiting approval';
        if (caseStatusIndicator) caseStatusIndicator.className = 'hidden sm:flex items-center space-x-2 text-xs font-semibold text-red-700 bg-red-50 px-2.5 py-1 rounded-full border border-red-200';
        break;
      case 'Settled':
        caseStatusDot.className = 'w-2 h-2 rounded-full bg-emerald-500';
        caseStatusText.textContent = 'Settled';
        if (caseStatusIndicator) caseStatusIndicator.className = 'hidden sm:flex items-center space-x-2 text-xs font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-200';
        break;
      case 'Needs review':
        caseStatusDot.className = 'w-2 h-2 rounded-full bg-amber-500';
        caseStatusText.textContent = 'Needs review';
        if (caseStatusIndicator) caseStatusIndicator.className = 'hidden sm:flex items-center space-x-2 text-xs font-semibold text-amber-800 bg-amber-100 px-2.5 py-1 rounded-full border border-amber-300';
        break;
      case 'Error':
        caseStatusDot.className = 'w-2 h-2 rounded-full bg-red-500';
        caseStatusText.textContent = 'Error';
        if (caseStatusIndicator) caseStatusIndicator.className = 'hidden sm:flex items-center space-x-2 text-xs font-semibold text-red-700 bg-red-50 px-2.5 py-1 rounded-full border border-red-200';
        break;
      case 'Ready':
      default:
        caseStatusDot.className = 'w-2 h-2 rounded-full bg-slate-400';
        caseStatusText.textContent = 'Ready';
        if (caseStatusIndicator) caseStatusIndicator.className = 'hidden sm:flex items-center space-x-2 text-xs font-medium text-slate-500 bg-slate-100 px-2.5 py-1 rounded-full border border-slate-200';
        break;
    }
  };

  // Check URL query parameters (?dev=1)
  const urlParams = new URLSearchParams(window.location.search);
  if (urlParams.get('dev') === '1' && devControls) {
    devControls.classList.remove('hidden');
  }

  // Dev Clear Cases Button
  if (clearCasesBtn) {
    clearCasesBtn.addEventListener('click', async () => {
      if (!confirm('Clear all test cases and reset demo data?')) return;
      try {
        const res = await fetch('/api/dev/reset', { method: 'POST' });
        if (res.ok) {
          await loadSidebarData();
          updateStatusPill('Ready');
          alert('Demo data wiped and drift history re-seeded.');
        } else {
          alert('Failed to reset demo data.');
        }
      } catch (err) {
        alert('Reset error: ' + err.message);
      }
    });
  }

  // Show all cases toggle
  if (showAllCasesBtn) {
    showAllCasesBtn.addEventListener('click', () => {
      showAllCases = !showAllCases;
      renderPastCases(allCases);
    });
  }

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
        allCases = cases;
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
      if (showAllCasesBtn) showAllCasesBtn.classList.add('hidden');
      animateCounter(totalRecoveredOverall, 0, 500);
      totalRecoveredOverall = 0;
      return;
    }

    const displayCases = showAllCases ? cases : cases.slice(0, 8);
    if (showAllCasesBtn) {
      if (cases.length > 8) {
        showAllCasesBtn.classList.remove('hidden');
        showAllCasesBtn.textContent = showAllCases ? 'Show less (latest 8)' : `Show all (${cases.length} cases)`;
      } else {
        showAllCasesBtn.classList.add('hidden');
      }
    }

    casesList.innerHTML = displayCases.map(c => {
      let vendorName = c.vendor || 'Unreadable file';
      if (vendorName.toLowerCase() === 'unknown' || vendorName.toLowerCase() === 'unknown vendor') {
        vendorName = 'Unreadable file';
      }
      const isCompleted = c.status === 'completed';
      const isEscalated = c.status === 'escalated';
      const isNeedsReview = c.status === 'needs_review';
      const isError = c.status === 'error';
      const statusBadge = isCompleted 
        ? 'bg-emerald-100 text-emerald-800' 
        : (isEscalated ? 'bg-amber-100 text-amber-800' : (isNeedsReview ? 'bg-amber-100 text-amber-800' : (isError ? 'bg-red-100 text-red-800' : 'bg-slate-100 text-slate-600')));
      return `
        <div class="p-2.5 rounded-lg border border-slate-100 hover:border-slate-200 hover:bg-slate-50 transition-colors text-xs cursor-pointer">
          <div class="flex items-center justify-between font-semibold text-slate-800">
            <span class="truncate max-w-[140px]">${vendorName}</span>
            <span class="text-emerald-700 font-bold">${formatINR(c.recovered || 0)}</span>
          </div>
          <div class="flex items-center justify-between text-[11px] text-slate-400 mt-1">
            <span>${c.invoice_no || c.id.slice(0, 14)}</span>
            <span class="px-1.5 py-0.2 rounded ${statusBadge}">${c.status || 'saved'}</span>
          </div>
        </div>
      `;
    }).join('');

    // Update global recovered counter summing only current DB cases
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

  // Demo preview query param handlers (for inspection & screenshot verification)
  if (urlParams.get('demo_preview') === 'needs_review') {
    handleExtractionUncertain({
      case_id: 'case_real_hck',
      reasons: [
        "Missing rate for 'CAMPUS LIGHTNING Sneakers For Women WHT/L'",
        "Missing amount for 'CAMPUS LIGHTNING Sneakers For Women WHT/L'",
        "Grand total is missing or Rs 0.00"
      ]
    });
  } else if (urlParams.get('demo_preview') === 'invoice_only') {
    renderFindings([], 0, {
      arithmetic: 'ok',
      delivery: 'skipped',
      rates: 'skipped'
    }, {
      arithmetic: 'Arithmetic validated across lines, subtotal, and tax.',
      delivery: 'Delivery check skipped (no slip)',
      rates: 'Rate check skipped (no agreement)'
    });
    updateStatusPill('Settled');
  }

  // Reset workspace for new case
  const resetWorkspace = () => {
    stepIndex = 0;
    activeToolCards = {};
    currentCaseTerminalStatus = null;
    stepCounter.textContent = '0 steps';
    timeline.innerHTML = '';
    timelineEmpty.classList.remove('hidden');
    timeline.appendChild(timelineEmpty);
    
    findingsContainer.innerHTML = `<div class="text-xs text-slate-400 italic text-center py-4">Evaluating discrepancies...</div>`;
    findingsCount.textContent = '0 findings';
    totalClaimedEl.textContent = '₹0.00';
    claimBadge.textContent = 'Auditing';
    claimBadge.className = 'text-[11px] font-medium px-2 py-1 rounded bg-amber-900/60 text-amber-300';
    if (checkChips) {
      checkChips.classList.add('hidden');
      checkChips.innerHTML = '';
    }
    
    emailCard.classList.add('hidden');
    negotiationCard.classList.add('hidden');
    chatThread.innerHTML = '';
    outcomeCard.classList.add('hidden');

    updateStatusPill('Running');
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
      updateStatusPill('Error');
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
      updateStatusPill('Error');
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

    eventSource.addEventListener('extraction_uncertain', (e) => {
      const payload = JSON.parse(e.data);
      currentCaseTerminalStatus = 'Needs review';
      handleExtractionUncertain(payload);
      updateStatusPill('Needs review');
    });

    eventSource.addEventListener('email_draft', (e) => {
      const payload = JSON.parse(e.data);
      handleEmailDraft(payload);
    });

    eventSource.addEventListener('awaiting_approval', (e) => {
      const payload = JSON.parse(e.data);
      currentCaseTerminalStatus = 'Awaiting approval';
      updateStatusPill('Awaiting approval');
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
      const st = (payload.status || '').toLowerCase();
      if (st.includes('needs review') || (payload.reasons && payload.reasons.length > 0)) {
        currentCaseTerminalStatus = 'Needs review';
      } else {
        currentCaseTerminalStatus = 'Settled';
      }
      handleOutcome(payload);
      updateStatusPill(currentCaseTerminalStatus);
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
      
      const existingOutcome = document.getElementById('outcome-card');
      if (existingOutcome && existingOutcome.classList.contains('hidden') && currentCaseTerminalStatus !== 'Needs review') {
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
        currentCaseTerminalStatus = 'Error';
        updateStatusPill('Error');
      } else if (currentCaseTerminalStatus) {
        updateStatusPill(currentCaseTerminalStatus);
      } else {
        updateStatusPill('Settled');
      }

      liveDot.className = 'w-2.5 h-2.5 rounded-full bg-slate-300';
      setRunning(false);
      loadSidebarData();
    });

    eventSource.addEventListener('end', () => {
      eventSource.close();
      liveDot.className = 'w-2.5 h-2.5 rounded-full bg-slate-300';
      if (!currentCaseTerminalStatus) {
        currentCaseTerminalStatus = 'Settled';
      }
      updateStatusPill(currentCaseTerminalStatus);
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
      renderFindings(findings, overcharge, res.checks, res.check_details);
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

  // Amber Card for Extraction Guard (Task 1)
  const handleExtractionUncertain = (data) => {
    updateStatusPill('Needs review');
    const reasons = data.reasons || ['Document numbers could not be reliably verified.'];
    const reasonsList = reasons.map(r => `<li class="flex items-start space-x-1.5"><span class="text-amber-600 font-bold">•</span><span>${r}</span></li>`).join('');

    const uncertainCard = document.createElement('div');
    uncertainCard.id = 'uncertain-card';
    uncertainCard.className = 'p-4 rounded-xl border border-amber-300 bg-amber-50 text-xs text-amber-900 space-y-3 animate-fade-in shadow-sm';
    uncertainCard.innerHTML = `
      <div class="flex items-center justify-between">
        <div class="flex items-center space-x-2 font-bold text-amber-900 text-sm">
          <svg class="w-5 h-5 text-amber-600 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
          <span>Couldn't read this bill reliably</span>
        </div>
        <span class="text-[10px] font-bold px-2 py-0.5 rounded bg-amber-200 text-amber-900">Needs Review</span>
      </div>
      <p class="text-xs text-amber-800">The extraction guard identified potential ambiguity or missing price values in the uploaded document:</p>
      <ul class="text-[11px] text-amber-800 space-y-1 pl-1 bg-amber-100/60 p-2.5 rounded-lg border border-amber-200">
        ${reasonsList}
      </ul>
      <div class="pt-1 flex items-center space-x-2">
        <button type="button" onclick="window.location.reload()" class="px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white rounded-lg font-medium text-xs transition-colors flex items-center space-x-1.5 shadow-sm">
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
          <span>Retry with Clearer Photo</span>
        </button>
      </div>
    `;
    timeline.appendChild(uncertainCard);
    uncertainCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    // Update findings container
    findingsContainer.innerHTML = `
      <div class="p-3.5 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-800 space-y-2">
        <div class="font-bold text-amber-900">Extraction Guard Stopped Audit</div>
        <p class="text-[11px]">No dispute email was drafted or sent because prices or line values could not be verified with confidence.</p>
      </div>
    `;
    claimBadge.textContent = 'Needs Review';
    claimBadge.className = 'text-[11px] font-semibold px-2 py-1 rounded bg-amber-900/60 text-amber-200';
  };

  // Render Findings in Column 3 (Honest Check Report Chips)
  const renderFindings = (findings, totalOvercharge, checks, checkDetails) => {
    findingsCount.textContent = `${findings.length} findings`;
    totalClaimedEl.textContent = formatINR(totalOvercharge);

    // Display 3 Honest Check Chips: Arithmetic / Delivery vs slip / Rates vs agreement
    if (checkChips && checks) {
      checkChips.classList.remove('hidden');
      const renderChip = (label, status, skippedText) => {
        if (status === 'ok') {
          return `
            <div class="flex items-center justify-between px-2.5 py-1 rounded-md bg-emerald-50 border border-emerald-200 text-emerald-800 text-[11px] font-semibold">
              <span>${label}</span>
              <span class="flex items-center space-x-1 font-bold text-emerald-700">
                <svg class="w-3.5 h-3.5 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/></svg>
                <span>OK</span>
              </span>
            </div>
          `;
        } else if (status === 'failed') {
          return `
            <div class="flex items-center justify-between px-2.5 py-1 rounded-md bg-red-50 border border-red-200 text-red-800 text-[11px] font-semibold">
              <span>${label}</span>
              <span class="flex items-center space-x-1 font-bold text-red-700">
                <svg class="w-3.5 h-3.5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 18L18 6M6 6l12 12"/></svg>
                <span>Failed</span>
              </span>
            </div>
          `;
        } else {
          return `
            <div class="flex items-center justify-between px-2.5 py-1 rounded-md bg-slate-100 border border-slate-200 text-slate-600 text-[11px]">
              <span>${label}</span>
              <span class="text-slate-400 italic font-medium">${skippedText}</span>
            </div>
          `;
        }
      };

      checkChips.innerHTML = `
        ${renderChip('Arithmetic', checks.arithmetic || 'ok', 'Skipped')}
        ${renderChip('Delivery vs slip', checks.delivery || 'skipped', 'Skipped (no slip)')}
        ${renderChip('Rates vs agreement', checks.rates || 'skipped', 'Skipped (no agreement)')}
      `;
    }

    if (totalOvercharge > 0) {
      claimBadge.textContent = 'Overcharge Found';
      claimBadge.className = 'text-[11px] font-semibold px-2 py-1 rounded bg-red-900/60 text-red-200';
    } else {
      claimBadge.textContent = 'Zero Discrepancy';
      claimBadge.className = 'text-[11px] font-semibold px-2 py-1 rounded bg-emerald-900/60 text-emerald-200';
    }

    if (!findings.length) {
      let cleanSummary = 'Clean bill verified: Arithmetic validated with zero overcharges.';
      if (checks && checks.delivery === 'ok') {
        cleanSummary += ' Delivered items matched delivery slip.';
      } else if (checks && checks.delivery === 'skipped') {
        cleanSummary += ' Delivery check skipped (no slip).';
      }
      if (checks && checks.rates === 'ok') {
        cleanSummary += ' Rates matched agreed contract terms.';
      } else if (checks && checks.rates === 'skipped') {
        cleanSummary += ' Rate check skipped (no agreement).';
      }

      findingsContainer.innerHTML = `
        <div class="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 text-center font-medium space-y-1">
          <div class="font-bold flex items-center justify-center space-x-1">
            <svg class="w-4 h-4 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
            <span>Clean Bill Verified</span>
          </div>
          <p class="text-[11px] text-emerald-700">${cleanSummary}</p>
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

    updateStatusPill('Awaiting approval');
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
    const bubbleColor = isAccepted ? 'bg-emerald-600 text-white' : (isEscalated ? 'bg-amber-600 text-white' : 'bg-brand-600 text-white');

    bubble.innerHTML = `
      <div class="flex items-center space-x-1.5 text-[11px] text-brand-700 font-semibold">
        <span>${data.sender}</span>
        <span class="px-1.5 py-0.2 rounded text-[10px] ${isAccepted ? 'bg-emerald-100 text-emerald-800' : (isEscalated ? 'bg-amber-100 text-amber-800' : 'bg-brand-100 text-brand-800')}">${data.action}</span>
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
    const isNeedsReview = (data.status || '').toLowerCase().includes('needs review') || (data.reasons && data.reasons.length > 0);
    
    let boxClass = 'bg-slate-100 text-slate-800';
    if (isNeedsReview) {
      boxClass = 'bg-amber-100 text-amber-900 border border-amber-300';
    } else if (isSettled) {
      boxClass = 'bg-emerald-100 text-emerald-900 border border-emerald-200';
    }

    outcomeStatusBox.className = `p-3 rounded-lg text-xs font-semibold ${boxClass}`;
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
