/* ===== Pi-Supertonic — фронтенд ===== */

// ---------- стан ----------

const state = {
  mode: 'chat',           // chat | realtime
  sttProvider: 'google',
  voice: 'F1',
  lang: 'uk',
  speed: 1.05,
  steps: 8,
  format: 'mp3',

  // realtime
  ws: null,
  isRecording: false,
  isPlaying: false,
  audioContext: null,
  vadProcessor: null,
  mediaStream: null,
  isSpeaking: false,
  interruptProcessor: null,
  interruptStream: null,
  interruptAudioCtx: null,

  // chat voice
  chatRecognition: null,
  mediaRecorder: null,
};

// ---------- DOM refs ----------

const $ = (s) => document.querySelector(s);

const messagesEl = $('#messages');
const textInput = $('#textInput');
const btnSend = $('#btnSend');
const btnVoice = $('#btnVoice');
const btnSettings = $('#btnSettings');
const btnReset = $('#btnReset');
const settingsModal = $('#settingsModal');
const closeSettings = $('#closeSettings');
const saveSettings = $('#saveSettings');
const voiceIndicator = $('#voiceIndicator');
const voiceStatus = $('#voiceStatus');
const modeChat = $('#modeChat');
const modeRealtime = $('#modeRealtime');

// ---------- ініціалізація ----------

async function init() {
  // Завантажуємо конфіг
  try {
    const resp = await fetch('/api/config');
    const cfg = await resp.json();
    Object.assign(state, cfg);
  } catch (e) {
    console.warn('Could not load config, using defaults');
  }

  updateSettingsUI();

  // Event listeners
  btnSend.addEventListener('click', sendTextMessage);
  textInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendTextMessage();
    }
  });

  btnVoice.addEventListener('click', toggleVoiceInput);
  btnSettings.addEventListener('click', () => settingsModal.classList.remove('hidden'));
  closeSettings.addEventListener('click', () => settingsModal.classList.add('hidden'));
  saveSettings.addEventListener('click', saveSettingsHandler);

  modeChat.addEventListener('click', () => switchMode('chat'));
  modeRealtime.addEventListener('click', () => switchMode('realtime'));

  btnReset.addEventListener('click', resetConversation);

  settingsModal.addEventListener('click', (e) => {
    if (e.target === settingsModal) settingsModal.classList.add('hidden');
  });

  $('#selSpeed').addEventListener('input', () => {
    $('#speedLabel').textContent = $('#selSpeed').value;
  });
  $('#selSteps').addEventListener('input', () => {
    $('#stepsLabel').textContent = $('#selSteps').value;
  });

  console.log('Pi-Supertonic initialized — мозок: Pi');
}

// ---------- Chat mode: текст → TTS ----------

async function sendTextMessage() {
  const text = textInput.value.trim();
  if (!text) return;

  addMessage(text, 'user');
  textInput.value = '';
  textInput.disabled = true;
  btnSend.disabled = true;

  // STT повідомлення просто показуємо в чаті.
  // Я (Pi) відповідаю тут, у цьому самому чаті.
  // Для озвучення використовуй:  !speak <текст>
  // Або скопіюй мою відповідь і натисни "Speak" в інтерфейсі.

  // Показуємо підказку
  const hintId = addMessage(
    '💡 Текст отримано. Я (Pi) бачу його і відповідаю тут. ' +
    'Скопіюй мою відповідь і натисни 🎤 "Speak", або використай !speak',
    'system'
  );

  textInput.disabled = false;
  btnSend.disabled = false;
  textInput.focus();
}

// ---------- Speak: озвучити текст через TTS ----------

async function speakText(text, showInChat = true) {
  if (!text || !text.trim()) return;

  try {
    const resp = await fetch('/api/speak', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: text.trim(),
        voice: state.voice,
        lang: state.lang,
        speed: state.speed,
        steps: state.steps,
        format: state.format,
      }),
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: 'HTTP ' + resp.status }));
      addMessage(`❌ TTS помилка: ${err.detail || 'невідома'}`, 'system');
      return;
    }

    const data = await resp.json();
    if (data.audio) {
      const msgId = showInChat ? addMessage(`🔊 ${text.trim()}`, 'assistant') : null;
      playAudio(data.audio, data.format, msgId);
    }
  } catch (err) {
    addMessage(`❌ Помилка: ${err.message}`, 'system');
  }
}

// ---------- Chat mode: voice input (Google STT / Groq STT) ----------

function toggleVoiceInput() {
  if (state.isRecording) {
    stopVoiceInput();
    return;
  }

  if (state.sttProvider === 'google') {
    startGoogleSTT();
  } else {
    startGroqVoiceInput();
  }
}

function startGoogleSTT() {
  if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
    addMessage('❌ Google STT не підтримується в цьому браузері. Використай Groq STT.', 'system');
    return;
  }

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const recognition = new SpeechRecognition();
  state.chatRecognition = recognition;

  recognition.lang = state.lang === 'uk' ? 'uk-UA'
    : state.lang === 'ru' ? 'ru-RU'
    : state.lang === 'de' ? 'de-DE'
    : state.lang === 'fr' ? 'fr-FR'
    : state.lang === 'ja' ? 'ja-JP'
    : state.lang === 'ko' ? 'ko-KR'
    : 'en-US';
  recognition.continuous = false;
  recognition.interimResults = false;

  recognition.onstart = () => {
    state.isRecording = true;
    btnVoice.classList.add('recording');
    btnVoice.textContent = '⏹';
  };

  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    addMessage(`🎤 ${transcript}`, 'user');
    stopVoiceInput();

    // Підказка: скопіювати і відправити Pi
    addMessage(
      '💡 Я чую: "' + transcript + '". Напиши мені це в наш чат, і я відповім!',
      'system'
    );
  };

  recognition.onerror = (event) => {
    addMessage(`❌ STT помилка: ${event.error}`, 'system');
    stopVoiceInput();
  };

  recognition.onend = () => {
    if (state.isRecording) stopVoiceInput();
  };

  recognition.start();
}

function stopVoiceInput() {
  state.isRecording = false;
  btnVoice.classList.remove('recording');
  btnVoice.textContent = '🎤';

  if (state.chatRecognition) {
    try { state.chatRecognition.stop(); } catch (e) {}
    state.chatRecognition = null;
  }
  if (state.mediaRecorder && state.mediaRecorder.state !== 'inactive') {
    state.mediaRecorder.stop();
  }
}

async function startGroqVoiceInput() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
    state.mediaRecorder = mediaRecorder;
    const chunks = [];

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunks.push(e.data);
    };

    mediaRecorder.onstop = async () => {
      const blob = new Blob(chunks, { type: 'audio/webm' });
      stream.getTracks().forEach(t => t.stop());

      addMessage('🎤 Розпізнаю через Groq...', 'system');
      try {
        const audioBase64 = await blobToBase64(blob);
        const resp = await fetch('/api/stt/groq', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ audio: audioBase64, sample_rate: 16000 }),
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        if (data.text) {
          addMessage(`🎤 ${data.text}`, 'user');
          addMessage('💡 Я чую: "' + data.text + '". Напиши мені це в наш чат!', 'system');
        }
      } catch (err) {
        addMessage(`❌ STT помилка: ${err.message}`, 'system');
      }
    };

    state.isRecording = true;
    btnVoice.classList.add('recording');
    btnVoice.textContent = '⏹';
    mediaRecorder.start();

    setTimeout(() => {
      if (state.isRecording && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
      }
    }, 10000);
  } catch (err) {
    addMessage(`❌ Мікрофон: ${err.message}`, 'system');
  }
}

// ---------- Real-time mode ----------

async function switchMode(mode) {
  if (state.mode === mode) return;

  if (state.mode === 'realtime') {
    disconnectRealtime();
  }

  state.mode = mode;

  modeChat.classList.toggle('active', mode === 'chat');
  modeRealtime.classList.toggle('active', mode === 'realtime');
  document.querySelector('.input-area').style.display = mode === 'chat' ? 'flex' : 'none';

  if (mode === 'realtime') {
    voiceIndicator.classList.remove('hidden');
    voiceStatus.textContent = '🎤 З\'єднуюсь...';
    connectRealtime();
  } else {
    voiceIndicator.classList.add('hidden');
  }
}

function connectRealtime() {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${location.host}/ws`;

  state.ws = new WebSocket(wsUrl);

  state.ws.onopen = () => {
    voiceStatus.textContent = '🎤 Слухаю...';
    startRealtimeMic();
    setupInterruptDetector();
  };

  state.ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);

    switch (msg.type) {
      case 'transcription':
        addMessage(`🎤 ${msg.text}`, 'user');
        voiceStatus.textContent = '📝 Розпізнано! Чекаю відповіді Pi...';
        addMessage('💡 Питання передано Pi. Скоро відповім!', 'system');
        break;

      case 'status':
        voiceStatus.textContent = msg.message;
        break;

      case 'error':
        addMessage(`❌ ${msg.message}`, 'system');
        voiceStatus.textContent = '❌ Помилка';
        break;

      case 'interrupt_ack':
        voiceStatus.textContent = '🛑 Перебив. Слухаю знову...';
        state.isSpeaking = false;
        break;

      case 'audio_chunk_ack':
        break;

      case 'config_updated':
        addMessage('✅ Налаштування оновлено', 'system');
        break;
    }
  };

  state.ws.onclose = () => {
    voiceIndicator.classList.add('hidden');
    addMessage('🔌 WebSocket закрито', 'system');
    state.ws = null;
  };

  state.ws.onerror = () => {
    addMessage('❌ WebSocket помилка', 'system');
  };
}

function disconnectRealtime() {
  if (state.ws) {
    state.ws.close();
    state.ws = null;
  }
  stopRealtimeMic();
  stopInterruptDetector();
}

// Real-time: мікрофон + VAD
async function startRealtimeMic() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    state.audioContext = audioCtx;
    const source = audioCtx.createMediaStreamSource(stream);
    const processor = audioCtx.createScriptProcessor(4096, 1, 1);

    let audioBuffer = [];
    let silenceStart = null;
    let isPhraseActive = false;
    const SILENCE_THRESHOLD = 0.02;
    const SILENCE_TIMEOUT_MS = 3000;
    const MIN_SAMPLES = audioCtx.sampleRate; // ~1 сек мінімум

    source.connect(processor);
    processor.connect(audioCtx.destination);

    processor.onaudioprocess = (event) => {
      if (state.isSpeaking) return;

      const input = event.inputBuffer.getChannelData(0);
      let sum = 0;
      for (let i = 0; i < input.length; i++) sum += input[i] * input[i];
      const rms = Math.sqrt(sum / input.length);

      audioBuffer.push(...input);
      const now = Date.now();

      if (rms > SILENCE_THRESHOLD) {
        silenceStart = null;
        if (!isPhraseActive) {
          isPhraseActive = true;
          voiceStatus.textContent = '🎙 Чую...';
        }
      } else {
        if (isPhraseActive) {
          if (silenceStart === null) {
            silenceStart = now;
          } else if (now - silenceStart >= SILENCE_TIMEOUT_MS && audioBuffer.length > MIN_SAMPLES) {
            isPhraseActive = false;
            silenceStart = null;
            const phraseBuffer = audioBuffer.splice(0, audioBuffer.length);
            sendAudioPhrase(phraseBuffer, audioCtx.sampleRate);
            voiceStatus.textContent = '⏳ Обробляю...';
          }
        }
      }
    };

    state.vadProcessor = processor;
    state.mediaStream = stream;
    state.isRecording = true;

    addMessage('🎤 Режим реального часу активний. Кажи — після 3с тиші я почую.', 'system');

  } catch (err) {
    addMessage(`❌ Мікрофон: ${err.message}`, 'system');
    disconnectRealtime();
  }
}

function stopRealtimeMic() {
  state.isRecording = false;
  if (state.vadProcessor) {
    state.vadProcessor.disconnect();
    state.vadProcessor = null;
  }
  if (state.audioContext) {
    state.audioContext.close();
    state.audioContext = null;
  }
  if (state.mediaStream) {
    state.mediaStream.getTracks().forEach(t => t.stop());
    state.mediaStream = null;
  }
}

async function sendAudioPhrase(samples, sampleRate) {
  if (!state.ws || state.ws.readyState !== WebSocket.OPEN) return;

  const targetRate = 16000;
  const resampled = resampleAudio(samples, sampleRate, targetRate);

  const pcm16 = new Int16Array(resampled.length);
  for (let i = 0; i < resampled.length; i++) {
    pcm16[i] = Math.max(-32768, Math.min(32767, resampled[i] * 32768));
  }

  const audioB64 = arrayBufferToBase64(pcm16.buffer);

  state.ws.send(JSON.stringify({
    type: 'audio_chunk',
    audio: audioB64,
    sample_rate: targetRate,
    end_of_phrase: true,
  }));
}

function resampleAudio(samples, fromRate, toRate) {
  if (fromRate === toRate) return samples;
  const ratio = toRate / fromRate;
  const newLength = Math.round(samples.length * ratio);
  const result = new Float32Array(newLength);
  for (let i = 0; i < newLength; i++) {
    const pos = i / ratio;
    const idx = Math.floor(pos);
    const frac = pos - idx;
    result[i] = idx + 1 < samples.length
      ? samples[idx] * (1 - frac) + samples[idx + 1] * frac
      : samples[idx];
  }
  return result;
}

// ---------- Audio playback ----------

let currentAudio = null;

function playAudio(audioBase64, format, msgId) {
  const audioBytes = base64ToArrayBuffer(audioBase64);
  const blob = new Blob([audioBytes], { type: `audio/${format}` });
  const url = URL.createObjectURL(blob);

  const audio = new Audio(url);

  if (msgId) {
    const msgEl = document.getElementById(`msg-${msgId}`);
    if (msgEl) {
      const audioEl = document.createElement('audio');
      audioEl.src = url;
      audioEl.controls = true;
      audioEl.className = 'msg-audio';
      msgEl.appendChild(audioEl);
    }
  }

  audio.onplay = () => { state.isPlaying = true; state.isSpeaking = true; };

  audio.onended = () => {
    state.isPlaying = false;
    state.isSpeaking = false;
    if (state.mode === 'realtime') {
      voiceStatus.textContent = '🎤 Слухаю...';
    }
    URL.revokeObjectURL(url);
  };

  currentAudio = audio;
  audio.play().catch(err => {
    console.warn('Audio play error:', err);
    addMessage('❌ Помилка відтворення', 'system');
  });
}

function interruptPlayback() {
  if (currentAudio) {
    currentAudio.pause();
    currentAudio.currentTime = 0;
    currentAudio = null;
  }
  state.isPlaying = false;
  state.isSpeaking = false;

  if (state.ws && state.ws.readyState === WebSocket.OPEN) {
    state.ws.send(JSON.stringify({ type: 'interrupt' }));
  }
}

// ---------- Interrupt detection ----------

async function setupInterruptDetector() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const source = audioCtx.createMediaStreamSource(stream);
    const processor = audioCtx.createScriptProcessor(2048, 1, 1);

    let speechDetected = false;
    const THRESHOLD = 0.03;

    source.connect(processor);
    processor.connect(audioCtx.destination);

    processor.onaudioprocess = (event) => {
      if (state.mode !== 'realtime' || !state.isSpeaking) return;

      const input = event.inputBuffer.getChannelData(0);
      let sum = 0;
      for (let i = 0; i < input.length; i++) sum += input[i] * input[i];
      const rms = Math.sqrt(sum / input.length);

      if (rms > THRESHOLD) {
        if (!speechDetected) {
          speechDetected = true;
          interruptPlayback();
          voiceStatus.textContent = '🛑 Перебив. Слухаю...';
          state.isSpeaking = false;
        }
      } else {
        speechDetected = false;
      }
    };

    state.interruptProcessor = processor;
    state.interruptStream = stream;
    state.interruptAudioCtx = audioCtx;
  } catch (err) {
    console.warn('Interrupt detector:', err);
  }
}

function stopInterruptDetector() {
  if (state.interruptProcessor) {
    state.interruptProcessor.disconnect();
    state.interruptProcessor = null;
  }
  if (state.interruptAudioCtx) {
    state.interruptAudioCtx.close();
    state.interruptAudioCtx = null;
  }
  if (state.interruptStream) {
    state.interruptStream.getTracks().forEach(t => t.stop());
    state.interruptStream = null;
  }
}

// ---------- Повідомлення ----------

function addMessage(text, role, isTyping = false) {
  const id = Date.now() + Math.random().toString(36).slice(2, 6);
  const div = document.createElement('div');
  div.className = `message ${role}`;
  div.id = `msg-${id}`;
  div.innerHTML = `<div class="msg-text">${escapeHtml(text)}</div>`;
  if (isTyping) div.querySelector('.msg-text').classList.add('typing-dots');
  messagesEl.appendChild(div);
  scrollToBottom();
  return id;
}

function updateLastAssistant(text, streaming = true) {
  const msgs = messagesEl.querySelectorAll('.message.assistant');
  if (msgs.length === 0) { addMessage(text, 'assistant'); return; }
  const last = msgs[msgs.length - 1];
  const textEl = last.querySelector('.msg-text');
  if (textEl) {
    textEl.textContent = text;
    if (streaming) textEl.classList.add('typing-dots');
    else textEl.classList.remove('typing-dots');
  }
  const oldAudio = last.querySelector('.msg-audio');
  if (oldAudio) oldAudio.remove();
  scrollToBottom();
}

function removeMessage(id) {
  const el = document.getElementById(`msg-${id}`);
  if (el) el.remove();
}

function scrollToBottom() {
  const area = document.getElementById('chatArea');
  area.scrollTop = area.scrollHeight;
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// ---------- Settings ----------

function updateSettingsUI() {
  $('#selVoice').value = state.voice || 'F1';
  $('#selLang').value = state.lang || 'uk';
  $('#selSpeed').value = state.speed || 1.05;
  $('#speedLabel').textContent = state.speed || 1.05;
  $('#selSteps').value = state.steps || 8;
  $('#stepsLabel').textContent = state.steps || 8;
  $('#selFormat').value = state.format || 'mp3';
  $('#groqKey').value = state.groq_api_key || '';

  const sttRadio = document.querySelector(`input[name="stt"][value="${state.sttProvider}"]`);
  if (sttRadio) sttRadio.checked = true;
}

async function saveSettingsHandler() {
  const newConfig = {
    tts_voice: $('#selVoice').value,
    tts_lang: $('#selLang').value,
    tts_speed: parseFloat($('#selSpeed').value),
    tts_steps: parseInt($('#selSteps').value),
    tts_format: $('#selFormat').value,
  };

  const groqKey = $('#groqKey').value.trim();
  if (groqKey) newConfig.groq_api_key = groqKey;

  const sttRadio = document.querySelector('input[name="stt"]:checked');
  state.sttProvider = sttRadio ? sttRadio.value : 'google';
  Object.assign(state, newConfig);

  try {
    const resp = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newConfig),
    });
    if (!resp.ok) console.warn('Config save failed');
  } catch (err) {
    console.warn('Config save error:', err);
  }

  settingsModal.classList.add('hidden');
}

async function resetConversation() {
  try {
    await fetch('/api/reset', { method: 'POST' });
    if (state.ws && state.ws.readyState === WebSocket.OPEN) {
      state.ws.send(JSON.stringify({ type: 'reset' }));
    }
  } catch (err) {
    console.warn('Reset failed:', err);
  }
  messagesEl.innerHTML = '';
  addMessage('💬 Історію очищено', 'system');
}

// ---------- Util: Base64 <-> ArrayBuffer ----------

function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result.split(',')[1]);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

function arrayBufferToBase64(buffer) {
  let binary = '';
  const bytes = new Uint8Array(buffer);
  for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

function base64ToArrayBuffer(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes.buffer;
}

// ---------- !speak команда ----------
// Якщо ввести в текстове поле "!speak Привіт" — текст озвучиться

const _origSend = sendTextMessage;
sendTextMessage = function() {
  const text = textInput.value.trim();
  if (!text) return;

  if (text.startsWith('!speak ')) {
    const speakText = text.slice(7).trim();
    textInput.value = '';
    if (speakText) speakText(speakText);
    return;
  }

  _origSend.call(this);
};

// ---------- Start ----------

document.addEventListener('DOMContentLoaded', init);
