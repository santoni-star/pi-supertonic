/* ===== Pi-Supertonic — фронтенд ===== */

// ---------- стан ----------

const state = {
  mode: 'chat',           // chat | realtime
  sttProvider: 'google',  // google | groq
  llmProvider: 'groq',
  voice: 'F1',
  lang: 'uk',
  speed: 1.05,
  steps: 8,
  format: 'mp3',

  // realtime
  ws: null,
  isRecording: false,
  isPlaying: false,
  mediaRecorder: null,
  audioContext: null,
  audioChunks: [],
  silenceTimer: null,
  isSpeaking: false,
  vadEnabled: false,

  // chat voice
  chatRecognition: null,
};

// ---------- DOM refs ----------

const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

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

  // Налаштовуємо UI
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

  // Mode buttons
  modeChat.addEventListener('click', () => switchMode('chat'));
  modeRealtime.addEventListener('click', () => switchMode('realtime'));

  btnReset.addEventListener('click', resetConversation);

  // Settings modal — close on overlay click
  settingsModal.addEventListener('click', (e) => {
    if (e.target === settingsModal) settingsModal.classList.add('hidden');
  });

  // Range inputs
  $('#selSpeed').addEventListener('input', () => {
    $('#speedLabel').textContent = $('#selSpeed').value;
  });
  $('#selSteps').addEventListener('input', () => {
    $('#stepsLabel').textContent = $('#selSteps').value;
  });

  console.log('Pi-Supertonic initialized');
}

// ---------- Chat mode: текст ----------

async function sendTextMessage() {
  const text = textInput.value.trim();
  if (!text) return;

  addMessage(text, 'user');
  textInput.value = '';
  textInput.disabled = true;
  btnSend.disabled = true;

  // Показуємо "думає"
  const thinkingId = addMessage('...', 'assistant', true);

  try {
    const resp = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text,
        voice: state.voice,
        lang: state.lang,
        speed: state.speed,
        steps: state.steps,
        format: state.format,
      }),
    });

    const data = await resp.json();

    // Видаляємо "думає"
    removeMessage(thinkingId);

    if (!resp.ok) {
      addMessage(`❌ ${data.detail || data.error || 'Помилка сервера'}`, 'system');
      return;
    }

    // Додаємо відповідь
    const msgId = addMessage(data.response_text, 'assistant');

    // Програємо аудіо (якщо є)
    if (data.audio) {
      playAudio(data.audio, data.format, msgId);
    }
    if (data.error) {
      console.warn('TTS note:', data.error);
    }
  } catch (err) {
    removeMessage(thinkingId);
    addMessage(`❌ Помилка: ${err.message}`, 'system');
  } finally {
    textInput.disabled = false;
    btnSend.disabled = false;
    textInput.focus();
  }
}

// ---------- Chat mode: голос (Google STT) ----------

function toggleVoiceInput() {
  if (state.isRecording) {
    stopVoiceInput();
    return;
  }

  if (state.sttProvider === 'google') {
    startGoogleSTT();
  } else {
    // Groq STT в чат-режимі — записуємо, потім транскрибуємо
    startGroqVoiceInput();
  }
}

function startGoogleSTT() {
  if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
    addMessage('❌ Google STT не підтримується в цьому браузері. Використай Groq STT або текст.', 'system');
    return;
  }

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const recognition = new SpeechRecognition();
  state.chatRecognition = recognition;

  recognition.lang = state.lang === 'uk' ? 'uk-UA' : state.lang === 'ru' ? 'ru-RU' : 'en-US';
  recognition.continuous = false;
  recognition.interimResults = false;

  recognition.onstart = () => {
    state.isRecording = true;
    btnVoice.classList.add('recording');
    btnVoice.textContent = '⏹';
  };

  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    textInput.value = transcript;
    stopVoiceInput();
    sendTextMessage();
  };

  recognition.onerror = (event) => {
    addMessage(`❌ Помилка STT: ${event.error}`, 'system');
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

// Groq STT в чат-режимі — запис, потім відправка на сервер
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

      addMessage('🎤 Розпізнаю...', 'system');
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
          textInput.value = data.text;
          sendTextMessage();
        }
      } catch (err) {
        addMessage(`❌ STT помилка: ${err.message}`, 'system');
      }
    };

    state.isRecording = true;
    btnVoice.classList.add('recording');
    btnVoice.textContent = '⏹';
    mediaRecorder.start();

    // Автостоп через 10 секунд
    setTimeout(() => {
      if (state.isRecording && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
      }
    }, 10000);
  } catch (err) {
    addMessage(`❌ Помилка мікрофона: ${err.message}`, 'system');
  }
}

// ---------- Real-time mode ----------

async function switchMode(mode) {
  if (state.mode === mode) return;

  // Вимикаємо старий режим
  if (state.mode === 'realtime') {
    disconnectRealtime();
  }

  state.mode = mode;

  // UI
  modeChat.classList.toggle('active', mode === 'chat');
  modeRealtime.classList.toggle('active', mode === 'realtime');

  document.querySelector('.input-area').style.display = mode === 'chat' ? 'flex' : 'none';
  voiceIndicator.classList.add('hidden');

  if (mode === 'realtime') {
    connectRealtime();
  }
}

function connectRealtime() {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${location.host}/ws`;

  state.ws = new WebSocket(wsUrl);

  state.ws.onopen = () => {
    voiceIndicator.classList.remove('hidden');
    voiceStatus.textContent = '🔌 З\'єднано. Говори...';
    startRealtimeMic();
  };

  state.ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);

    switch (msg.type) {
      case 'transcription':
        addMessage(msg.text, 'user');
        break;

      case 'llm_chunk':
        // Оновлюємо останнє повідомлення асистента (streaming)
        updateLastAssistant(msg.text);
        break;

      case 'audio':
        // Фінальне аудіо
        const finalText = msg.text;
        // Замінюємо останнє повідомлення фінальним текстом
        updateLastAssistant(finalText, false);
        playAudio(msg.audio, msg.format);
        voiceStatus.textContent = '🎧 Відтворюю...';
        state.isSpeaking = true;
        break;

      case 'status':
        voiceStatus.textContent = msg.message;
        break;

      case 'error':
        addMessage(`❌ ${msg.message}`, 'system');
        voiceStatus.textContent = '❌ Помилка';
        break;

      case 'interrupt_ack':
        voiceStatus.textContent = '🛑 Перебив. Слухаю...';
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
    state.ws = null;
    addMessage('🔌 З\'єднання закрито', 'system');
  };

  state.ws.onerror = (err) => {
    addMessage('❌ WebSocket помилка', 'system');
  };
}

function disconnectRealtime() {
  if (state.ws) {
    state.ws.close();
    state.ws = null;
  }
  stopRealtimeMic();
}

// Real-time: мікрофон + VAD
async function startRealtimeMic() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

    // Audio context для VAD + запис
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    state.audioContext = audioCtx;

    const source = audioCtx.createMediaStreamSource(stream);
    const processor = audioCtx.createScriptProcessor(4096, 1, 1); // 4096 samples ~ 256ms at 16kHz

    let audioBuffer = [];
    let silenceStart = null;
    let isPhraseActive = false;
    const SILENCE_THRESHOLD = 0.02;  // RMS поріг тиші
    const SILENCE_TIMEOUT_MS = 3000; // 3 секунди тиші
    const MIN_PHRASE_MS = 500;       // мінімальна довжина фрази

    source.connect(processor);
    processor.connect(audioCtx.destination);

    processor.onaudioprocess = (event) => {
      if (state.isSpeaking) return; // Не слухаємо, поки говоримо

      const input = event.inputBuffer.getChannelData(0);

      // Обчислюємо RMS
      let sum = 0;
      for (let i = 0; i < input.length; i++) {
        sum += input[i] * input[i];
      }
      const rms = Math.sqrt(sum / input.length);

      // Додаємо в буфер (реземплюємо до 16kHz)
      audioBuffer.push(...input);

      const now = Date.now();

      if (rms > SILENCE_THRESHOLD) {
        // Голос
        silenceStart = null;
        if (!isPhraseActive) {
          isPhraseActive = true;
          voiceStatus.textContent = '🎙 Чую...';
        }
      } else {
        // Тиша
        if (isPhraseActive) {
          if (silenceStart === null) {
            silenceStart = now;
          } else if (now - silenceStart >= SILENCE_TIMEOUT_MS) {
            // 3 секунди тиші — відправляємо фразу
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

  } catch (err) {
    addMessage(`❌ Помилка мікрофона: ${err.message}`, 'system');
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

  // Реземпл до 16kHz (Groq Whisper)
  const targetRate = 16000;
  const resampled = resampleAudio(samples, sampleRate, targetRate);

  // Конвертуємо float32 → PCM16
  const pcm16 = new Int16Array(resampled.length);
  for (let i = 0; i < resampled.length; i++) {
    pcm16[i] = Math.max(-32768, Math.min(32767, resampled[i] * 32768));
  }

  // Base64
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

  // Додаємо аудіо-елемент в повідомлення, якщо є msgId
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

  audio.onended = () => {
    state.isPlaying = false;
    if (state.mode === 'realtime') {
      state.isSpeaking = false;
      voiceStatus.textContent = '🎤 Слухаю...';
    }
    URL.revokeObjectURL(url);
  };

  audio.onplay = () => {
    state.isPlaying = true;
    state.isSpeaking = true;
  };

  // If realtime mode and we detect mic activity during playback → interrupt
  if (state.mode === 'realtime') {
    audio.onplay = () => {
      state.isPlaying = true;
      state.isSpeaking = true;
    };

    // We check for interrupt via the VAD processor which checks state.isSpeaking
  }

  currentAudio = audio;
  audio.play().catch(err => {
    console.warn('Audio play error:', err);
    addMessage('❌ Помилка відтворення аудіо', 'system');
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

// ---------- Допоміжні функції ----------

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
  if (msgs.length === 0) {
    addMessage(text, 'assistant');
    return;
  }
  const last = msgs[msgs.length - 1];
  const textEl = last.querySelector('.msg-text');
  if (textEl) {
    textEl.textContent = text;
    if (streaming) textEl.classList.add('typing-dots');
    else textEl.classList.remove('typing-dots');
  }
  // Видаляємо старий аудіо-плеєр, якщо є
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
  $('#selLLM').value = state.llmProvider;
  $('#selVoice').value = state.voice;
  $('#selLang').value = state.lang;
  $('#selSpeed').value = state.speed;
  $('#speedLabel').textContent = state.speed;
  $('#selSteps').value = state.steps;
  $('#stepsLabel').textContent = state.steps;
  $('#selFormat').value = state.format;

  // STT radio
  const sttRadio = document.querySelector(`input[name="stt"][value="${state.sttProvider}"]`);
  if (sttRadio) sttRadio.checked = true;
}

async function saveSettingsHandler() {
  const newConfig = {
    llm_provider: $('#selLLM').value,
    tts_voice: $('#selVoice').value,
    tts_lang: $('#selLang').value,
    tts_speed: parseFloat($('#selSpeed').value),
    tts_steps: parseInt($('#selSteps').value),
    tts_format: $('#selFormat').value,
  };

  const groqKey = $('#groqKey').value.trim();
  const openaiKey = $('#openaiKey').value.trim();

  if (groqKey) newConfig.groq_api_key = groqKey;
  if (openaiKey) newConfig.openai_api_key = openaiKey;

  const sttRadio = document.querySelector('input[name="stt"]:checked');
  state.sttProvider = sttRadio ? sttRadio.value : 'google';

  Object.assign(state, newConfig);

  // Відправляємо на сервер
  try {
    const resp = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newConfig),
    });
    if (resp.ok) {
      // Якщо в realtime режимі, оновлюємо через WS
      if (state.ws && state.ws.readyState === WebSocket.OPEN) {
        state.ws.send(JSON.stringify({ type: 'config_update', data: newConfig }));
      }
    }
  } catch (err) {
    console.warn('Failed to save config:', err);
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
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

function base64ToArrayBuffer(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes.buffer;
}

// ---------- Interruption detection: перебивання в реальному часі ----------
// Окремий аудіо-потік тільки для детекції перебивання

async function setupInterruptDetector() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const source = audioCtx.createMediaStreamSource(stream);
    const processor = audioCtx.createScriptProcessor(2048, 1, 1);

    let speechDuringPlayback = false;
    const INTERRUPT_THRESHOLD = 0.03;

    source.connect(processor);
    processor.connect(audioCtx.destination);

    processor.onaudioprocess = (event) => {
      if (state.mode !== 'realtime' || !state.isSpeaking) return;

      const input = event.inputBuffer.getChannelData(0);
      let sum = 0;
      for (let i = 0; i < input.length; i++) {
        sum += input[i] * input[i];
      }
      const rms = Math.sqrt(sum / input.length);

      if (rms > INTERRUPT_THRESHOLD) {
        if (!speechDuringPlayback) {
          speechDuringPlayback = true;
          interruptPlayback();
          voiceStatus.textContent = '🛑 Перебив. Слухаю...';
          state.isSpeaking = false;
        }
      } else {
        speechDuringPlayback = false;
      }
    };

    state.interruptProcessor = processor;
    state.interruptStream = stream;
    state.interruptAudioCtx = audioCtx;
  } catch (err) {
    console.warn('Interrupt detector setup failed:', err);
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

// Обгортаємо connectRealtime з interrupt детектором
const _origConnectRealtime = connectRealtime;
const _origDisconnectRealtime = disconnectRealtime;

connectRealtime = function() {
  _origConnectRealtime.call(this);
  setupInterruptDetector();
};

disconnectRealtime = function() {
  _origDisconnectRealtime.call(this);
  stopInterruptDetector();
};

// ---------- Start ----------

document.addEventListener('DOMContentLoaded', init);
