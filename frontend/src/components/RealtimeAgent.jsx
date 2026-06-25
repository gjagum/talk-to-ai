import React, { useState, useEffect, useRef } from 'react';
import { PhoneCall, PhoneOff, Loader2, Waves } from 'lucide-react';

// Utility to convert Float32 (browser audio) to Int16 (OpenAI pcm16)
function floatTo16BitPCM(input) {
  const output = new Int16Array(input.length);
  for (let i = 0; i < input.length; i++) {
    const s = Math.max(-1, Math.min(1, input[i]));
    output[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
  }
  return output;
}

// Utility to convert Int16 to Base64
function bufferToBase64(buffer) {
  let binary = '';
  const bytes = new Uint8Array(buffer.buffer);
  const len = bytes.byteLength;
  for (let i = 0; i < len; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return window.btoa(binary);
}

// Utility to convert Base64 back to Int16, then to Float32 for playback
function base64ToFloat32(base64) {
  const binaryString = window.atob(base64);
  const len = binaryString.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  const int16Array = new Int16Array(bytes.buffer);
  const float32Array = new Float32Array(int16Array.length);
  for (let i = 0; i < int16Array.length; i++) {
    float32Array[i] = int16Array[i] / 32768.0;
  }
  return float32Array;
}

export default function RealtimeAgent({ persona }) {
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [messages, setMessages] = useState([]);
  
  const wsRef = useRef(null);
  const audioContextRef = useRef(null);
  const processorRef = useRef(null);
  const mediaStreamRef = useRef(null);
  
  // Audio playback queue
  const playQueueRef = useRef([]);
  const isPlayingRef = useRef(false);
  const currentSourceRef = useRef(null);

  const connect = async () => {
    setIsConnecting(true);
    try {
      // 1. Connect WebSocket
      const ws = new WebSocket("ws://localhost:8000/api/realtime/ws");
      wsRef.current = ws;

      ws.onopen = () => {
        // Configure the session with the Persona. GA Realtime API shape:
        // audio config is nested under audio.input / audio.output, formats are
        // objects (not the old "pcm16" string), and modalities → output_modalities.
        const sessionUpdate = {
          type: "session.update",
          session: {
            type: "realtime",
            instructions: persona,
            output_modalities: ["audio"],
            audio: {
              input: {
                format: { type: "audio/pcm", rate: 24000 },
                // Transcribe the caller's own speech so it can be shown on the
                // thread (otherwise only the assistant's transcript is emitted).
                transcription: { model: "whisper-1" },
                turn_detection: {
                  type: "server_vad",
                  threshold: 0.5,
                  prefix_padding_ms: 300,
                  silence_duration_ms: 500
                }
              },
              output: {
                format: { type: "audio/pcm", rate: 24000 },
                voice: "shimmer"
              }
            }
          }
        };
        ws.send(JSON.stringify(sessionUpdate));
        
        // Start Microphone
        startMicrophone();
        setIsConnected(true);
        setIsConnecting(false);
      };

      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        
        if (msg.type === "response.output_audio.delta") {
          // Play audio (GA event name: response.output_audio.delta)
          const audioFloat32 = base64ToFloat32(msg.delta);
          playQueueRef.current.push(audioFloat32);
          playNextChunk();
        } else if (msg.type === "response.output_audio_transcript.delta") {
          // Append the assistant transcript delta. This updater must be PURE —
          // mutating the last message object (last.text += ...) double-applies
          // under React StrictMode's double-invoked updaters, which is what was
          // doubling every word.
          setMessages(prev => {
            const last = prev[prev.length - 1];
            if (last && last.role === 'assistant') {
              return prev.map((m, i) =>
                i === prev.length - 1 ? { ...m, text: m.text + msg.delta } : m
              );
            }
            return [...prev, { role: 'assistant', text: msg.delta }];
          });
        } else if (msg.type === "conversation.item.input_audio_transcription.completed") {
          // The caller's speech, transcribed by the server — add it as a user bubble.
          const text = (msg.transcript || '').trim();
          if (text) {
            setMessages(prev => [...prev, { role: 'user', text }]);
          }
        } else if (msg.type === "input_audio_buffer.speech_started") {
          // INTERRUPT/ENDPOINTING: User started speaking, stop the AI immediately!
          playQueueRef.current = [];
          if (currentSourceRef.current) {
            try { currentSourceRef.current.stop(); } catch (e) {}
            currentSourceRef.current = null;
          }
          isPlayingRef.current = false;
        } else if (msg.type === "error") {
          console.error("OpenAI Error:", msg.error);
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        stopMicrophone();
      };
      
    } catch (e) {
      console.error(e);
      setIsConnecting(false);
    }
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
    const stream = await navigator.mediaDevices.getUserMedia({
      // Echo cancellation / noise suppression keep the AI's voice (played through
      // the physical speakers) from being re-captured by the mic and looping back.
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
    mediaStreamRef.current = stream;

    // OpenAI Realtime requires EXACTLY 24,000 Hz sample rate
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
    audioContextRef.current = audioCtx;
    
    const source = audioCtx.createMediaStreamSource(stream);
    
    // Use ScriptProcessorNode (deprecated but easier for simple inline PCM capture)
    // 4096 buffer size at 24000Hz = ~170ms chunks
    const processor = audioCtx.createScriptProcessor(4096, 1, 1);
    processorRef.current = processor;
    
    processor.onaudioprocess = (e) => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        const inputData = e.inputBuffer.getChannelData(0);
        // Resampling is handled natively by setting AudioContext sampleRate: 24000
        const pcm16 = floatTo16BitPCM(inputData);
        const base64Audio = bufferToBase64(pcm16);

        wsRef.current.send(JSON.stringify({
          type: "input_audio_buffer.append",
          audio: base64Audio
        }));
      }
      // Zero the output buffer so the captured mic audio is NOT piped back out
      // through the speakers. Otherwise the AI's voice leaks into the mic, and
      // OpenAI's server-VAD treats it as the user speaking — triggering the agent
      // to respond to itself (the duplicated/looping greeting).
      const outData = e.outputBuffer.getChannelData(0);
      outData.fill(0);
    };

    // Route the processor through a zero-gain node so NO mic audio reaches the
    // speakers, while still connecting to destination to keep the processor firing.
    const muteGain = audioCtx.createGain();
    muteGain.gain.value = 0;
    source.connect(processor);
    processor.connect(muteGain);
    muteGain.connect(audioCtx.destination);
  };

  const disconnect = () => {
    if (wsRef.current) wsRef.current.close();
    stopMicrophone();
    setIsConnected(false);
  };

  const stopMicrophone = () => {
    if (processorRef.current) {
      processorRef.current.disconnect();
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(track => track.stop());
    }
    playQueueRef.current = [];
  };

  return (
    <div className="glass-panel rounded-3xl p-8 flex flex-col items-center justify-center relative overflow-hidden w-full max-w-lg mx-auto mt-8">
      {!isConnected ? (
        <button 
          onClick={connect}
          disabled={isConnecting}
          className="flex items-center gap-3 bg-green-500 hover:bg-green-400 text-white px-8 py-4 rounded-full text-xl font-bold shadow-lg shadow-green-500/30 transition-all hover:scale-105"
        >
          {isConnecting ? <Loader2 className="w-6 h-6 animate-spin" /> : <PhoneCall className="w-6 h-6" />}
          {isConnecting ? "Connecting..." : "Start Realtime Call"}
        </button>
      ) : (
        <div className="flex flex-col items-center gap-6">
          <div className="w-24 h-24 rounded-full bg-blue-500/20 flex items-center justify-center animate-pulse border border-blue-500/50 shadow-[0_0_50px_rgba(59,130,246,0.3)]">
            <div className="w-16 h-16 rounded-full bg-blue-500 flex items-center justify-center shadow-lg">
               <Waves className="w-8 h-8 text-white animate-bounce" />
            </div>
          </div>
          
          <div className="text-center">
            <p className="text-blue-400 font-bold text-xl">Connected Live</p>
            <p className="text-slate-400 text-sm mt-1">Speak naturally. VAD is handled by OpenAI.</p>
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
      
      {/* Transcript Log */}
      {messages.length > 0 && (
        <div className="mt-8 w-full max-h-[300px] overflow-y-auto space-y-4">
          {messages.map((m, i) => (
            <div
              key={i}
              className={`p-4 rounded-xl text-slate-300 ${
                m.role === 'user' ? 'bg-slate-800/80 ml-8' : 'bg-blue-900/30 border border-blue-700/40 mr-8'
              }`}
            >
              <span className={`font-bold ${m.role === 'user' ? 'text-slate-400' : 'text-blue-400'}`}>
                {m.role === 'user' ? 'You:' : 'Ryan:'}
              </span>{' '}
              {m.text}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
