import React, { useState, useEffect, useRef } from 'react';
import { PhoneCall, PhoneOff, Loader2, Mic } from 'lucide-react';

/**
 * TalkAgent — Deepgram Voice Agent client.
 *
 * Connects to the backend relay at /api/agent/ws, which proxies between the
 * browser and Deepgram's Voice Agent API (wss://agent.deepgram.com/v1/agent/converse).
 *
 * Unlike RealtimeAgent (OpenAI), Deepgram streams RAW BINARY PCM16 audio:
 *   - outgoing mic audio is sent as ArrayBuffer (binary WebSocket frames)
 *   - incoming agent audio arrives as Blob frames (binary WebSocket frames)
 *   - JSON control events arrive as text frames
 */
export default function TalkAgent({ persona }) {
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [messages, setMessages] = useState([]);
  // Track whether the last assistant bubble is still streaming (so deltas append).
  const lastAssistantIdRef = useRef(null);

  const wsRef = useRef(null);
  const audioContextRef = useRef(null);
  const processorRef = useRef(null);
  const mediaStreamRef = useRef(null);

  // Audio playback queue for incoming PCM chunks.
  const playQueueRef = useRef([]);
  const isPlayingRef = useRef(false);
  const currentSourceRef = useRef(null);

  // The persona is large (often >8KB when URL-encoded), so we send it as the
  // first JSON message after the socket opens rather than in the URL query string.
  const connect = async () => {
    setIsConnecting(true);
    setMessages([]);
    lastAssistantIdRef.current = null;
    try {
      const wsUrl = `ws://localhost:8000/api/agent/ws`;
      const ws = new WebSocket(wsUrl);
      // CRITICAL: tell the browser to keep binary frames as ArrayBuffer (not Blobs)
      ws.binaryType = 'arraybuffer';
      wsRef.current = ws;

      ws.onopen = () => {
        // First message: deliver the persona before any audio flows.
        ws.send(JSON.stringify({ type: 'Init', persona }));
        setIsConnected(true);
        setIsConnecting(false);
        startMicrophone();
      };

      ws.onmessage = async (event) => {
        if (event.data instanceof ArrayBuffer) {
          // Binary audio from Deepgram TTS → convert PCM16 → Float32 → play.
          const float32 = pcm16ToFloat32(event.data);
          playQueueRef.current.push(float32);
          playNextChunk();
          return;
        }

        // Text frame: JSON control event.
        let msg;
        try {
          msg = JSON.parse(event.data);
        } catch (e) {
          return;
        }

        switch (msg.type) {
          case 'UserStartedSpeaking':
            // Barge-in: user spoke, interrupt the agent mid-sentence.
            playQueueRef.current = [];
            if (currentSourceRef.current) {
              try { currentSourceRef.current.stop(); } catch (e) {}
              currentSourceRef.current = null;
            }
            isPlayingRef.current = false;
            break;

          case 'ConversationText':
            // role can be 'user' or 'assistant'. content is the utterance.
            setMessages((prev) => {
              const newMsgs = [...prev];
              const role = msg.role === 'user' ? 'user' : 'assistant';
              if (lastAssistantIdRef.current !== null && role === 'assistant') {
                // Replace last assistant bubble with the finalized content.
                newMsgs[newMsgs.length - 1] = { role, text: msg.content };
              } else {
                newMsgs.push({ role, text: msg.content });
                lastAssistantIdRef.current = role === 'assistant' ? newMsgs.length - 1 : null;
              }
              return newMsgs;
            });
            break;

          case 'AgentStartedSpeaking':
            // Add a placeholder bubble for the assistant that's about to be transcribed.
            setMessages((prev) => {
              const newMsgs = [...prev];
              const last = newMsgs[newMsgs.length - 1];
              if (!last || last.role !== 'assistant') {
                newMsgs.push({ role: 'assistant', text: '' });
                lastAssistantIdRef.current = newMsgs.length - 1;
              }
              return newMsgs;
            });
            break;

          case 'Error':
            console.error('Deepgram error:', msg.description, msg.code);
            setMessages((prev) => [...prev, { role: 'system', text: `Error: ${msg.description || 'unknown'}` }]);
            break;

          default:
            // Welcome, SettingsApplied, AgentThinking, AgentAudioDone, etc.
            break;
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        stopMicrophone();
      };

      ws.onerror = (e) => {
        console.error('WebSocket error:', e);
        setIsConnecting(false);
      };
    } catch (e) {
      console.error(e);
      setIsConnecting(false);
    }
  };

  // Convert raw PCM16 little-endian bytes to Float32 for Web Audio playback.
  const pcm16ToFloat32 = (arrayBuffer) => {
    const int16 = new Int16Array(arrayBuffer);
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) {
      float32[i] = int16[i] / 32768.0;
    }
    return float32;
  };

  const playNextChunk = () => {
    if (isPlayingRef.current || playQueueRef.current.length === 0 || !audioContextRef.current) return;

    isPlayingRef.current = true;
    const chunk = playQueueRef.current.shift();

    const audioBuffer = audioContextRef.current.createBuffer(1, chunk.length, 24000);
    audioBuffer.getChannelData(0).set(chunk);

    const source = audioContextRef.current.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(audioContextRef.current.destination);
    currentSourceRef.current = source;

    source.onended = () => {
      isPlayingRef.current = false;
      currentSourceRef.current = null;
      playNextChunk();
    };

    source.start();
  };

  const startMicrophone = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaStreamRef.current = stream;

    // Deepgram Voice Agent expects 24kHz linear16 input.
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
    audioContextRef.current = audioCtx;

    const source = audioCtx.createMediaStreamSource(stream);

    // ScriptProcessorNode is deprecated but simplest for inline PCM capture.
    const processor = audioCtx.createScriptProcessor(4096, 1, 1);
    processorRef.current = processor;

    processor.onaudioprocess = (e) => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        const inputData = e.inputBuffer.getChannelData(0);
        const pcm16 = floatTo16BitPCM(inputData);
        // Send raw binary ArrayBuffer — Deepgram expects raw PCM16 frames.
        wsRef.current.send(pcm16.buffer);
      }
      // Crucial: zero out the output buffer. Otherwise Web Audio pipes the
      // captured mic audio into audioCtx.destination, which outputs it through
      // the speakers and creates an echo/feedback loop that distorts the AI's
      // voice. Writing silence here keeps onaudioprocess firing but mutes the
      // passthrough — the agent's audio is played separately via playNextChunk().
      const outData = e.outputBuffer.getChannelData(0);
      outData.fill(0);
    };

    // Source → processor chain must connect to destination for the processor
    // to keep running, but we route it through a zero-gain node so NO mic
    // audio actually reaches the speakers (anti-feedback).
    const muteGain = audioCtx.createGain();
    muteGain.gain.value = 0;
    source.connect(processor);
    processor.connect(muteGain);
    muteGain.connect(audioCtx.destination);
  };

  // Convert Float32 samples → Int16 PCM little-endian.
  const floatTo16BitPCM = (input) => {
    const output = new Int16Array(input.length);
    for (let i = 0; i < input.length; i++) {
      const s = Math.max(-1, Math.min(1, input[i]));
      output[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    return output;
  };

  const disconnect = () => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    stopMicrophone();
    setIsConnected(false);
  };

  const stopMicrophone = () => {
    if (processorRef.current) {
      try { processorRef.current.disconnect(); } catch (e) {}
    }
    if (audioContextRef.current) {
      try { audioContextRef.current.close(); } catch (e) {}
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
    }
    playQueueRef.current = [];
  };

  // Cleanup on unmount.
  useEffect(() => {
    return () => {
      disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="glass-panel rounded-3xl p-8 flex flex-col items-center justify-center relative overflow-hidden w-full max-w-lg mx-auto mt-8">
      {!isConnected ? (
        <button
          onClick={connect}
          disabled={isConnecting}
          className="flex items-center gap-3 bg-emerald-500 hover:bg-emerald-400 text-white px-8 py-4 rounded-full text-xl font-bold shadow-lg shadow-emerald-500/30 transition-all hover:scale-105"
        >
          {isConnecting ? <Loader2 className="w-6 h-6 animate-spin" /> : <PhoneCall className="w-6 h-6" />}
          {isConnecting ? 'Connecting...' : 'Start Talk Call'}
        </button>
      ) : (
        <div className="flex flex-col items-center gap-6">
          <div className="w-24 h-24 rounded-full bg-emerald-500/20 flex items-center justify-center animate-pulse border border-emerald-500/50 shadow-[0_0_50px_rgba(16,185,129,0.3)]">
            <div className="w-16 h-16 rounded-full bg-emerald-500 flex items-center justify-center shadow-lg">
              <Mic className="w-8 h-8 text-white animate-bounce" />
            </div>
          </div>

          <div className="text-center">
            <p className="text-emerald-400 font-bold text-xl">Connected · Deepgram Agent</p>
            <p className="text-slate-400 text-sm mt-1">Managed STT → OpenAI → TTS pipeline.</p>
          </div>

          <button
            onClick={disconnect}
            className="mt-4 flex items-center gap-2 bg-red-500/20 text-red-400 border border-red-500/50 hover:bg-red-500 hover:text-white px-6 py-2 rounded-full font-medium transition-all"
          >
            <PhoneOff className="w-4 h-4" />
            End Call
          </button>
        </div>
      )}

      {messages.length > 0 && (
        <div className="mt-8 w-full max-h-[300px] overflow-y-auto space-y-4">
          {messages.map((m, i) => (
            <div
              key={i}
              className={`p-4 rounded-xl text-slate-300 ${
                m.role === 'user'
                  ? 'bg-slate-800/80 mr-8'
                  : m.role === 'assistant'
                    ? 'bg-emerald-900/30 border border-emerald-700/40 ml-8'
                    : 'bg-red-900/30 border border-red-700/40'
              }`}
            >
              <span className={`font-bold ${m.role === 'user' ? 'text-slate-400' : 'text-emerald-400'}`}>
                {m.role === 'user' ? 'You:' : m.role === 'assistant' ? 'Ryan:' : 'System:'}
              </span>{' '}
              {m.text}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
