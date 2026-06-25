import React, { useState, useRef, useEffect } from 'react';
import { Mic, Square, Loader2 } from 'lucide-react';

function VoiceRecorder({ onSubmit, isProcessing, shouldRecord }) {
  const [isRecording, setIsRecording] = useState(false);
  const [interimTranscript, setInterimTranscript] = useState('');
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const audioContextRef = useRef(null);
  const streamRef = useRef(null);
  const recognitionRef = useRef(null);
  const finalTranscriptRef = useRef('');

  const startRecording = async () => {
    setInterimTranscript('');
    finalTranscriptRef.current = '';
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      mediaRecorderRef.current = new MediaRecorder(stream);
      chunksRef.current = [];
      
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (SpeechRecognition) {
        const recognition = new SpeechRecognition();
        recognition.continuous = true; // Use our custom VAD for endpointing instead of native aggressive cutoffs
        recognition.interimResults = true;
        
        recognition.onresult = (event) => {
          let interim = '';
          for (let i = event.resultIndex; i < event.results.length; ++i) {
            if (event.results[i].isFinal) {
              finalTranscriptRef.current += event.results[i][0].transcript + ' ';
            } else {
              interim += event.results[i][0].transcript;
            }
          }
          setInterimTranscript(interim || finalTranscriptRef.current);
        };
        
        recognition.onend = () => {
          // Native API might stop unexpectedly, we restart it if we are still recording
          if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
            try { recognition.start(); } catch(e) {}
          }
        };
        
        recognition.start();
        recognitionRef.current = recognition;
      }
      
      mediaRecorderRef.current.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };
      
      mediaRecorderRef.current.onstop = () => {
        const audioBlob = new Blob(chunksRef.current, { type: 'audio/webm' });
        
        if (recognitionRef.current) {
          recognitionRef.current.stop();
        }
        
        const finalObj = finalTranscriptRef.current.trim() 
            ? { text: finalTranscriptRef.current.trim() } 
            : audioBlob;
            
        onSubmit(finalObj);
        if (streamRef.current) {
          streamRef.current.getTracks().forEach(track => track.stop());
        }
        if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
          audioContextRef.current.close();
        }
      };

      // Silence / endpoint detection (VAD).
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      const audioContext = new AudioContext();
      audioContextRef.current = audioContext;
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 512;
      // A bit of smoothing stabilises the level estimate without adding lag.
      analyser.smoothingTimeConstant = 0.5;
      const source = audioContext.createMediaStreamSource(stream);
      source.connect(analyser);

      const dataArray = new Uint8Array(analyser.frequencyBinCount);

      const CALIBRATION_FRAMES = 30;    // ~0.5s sampling the ambient noise floor
      const MIN_SPEECH_MS = 400;        // ignore blips shorter than this before arming endpointing
      const SILENCE_HANGOVER_MS = 1500; // stop after this much trailing silence

      let silenceStart = Date.now();
      let speechStart = 0;
      let hasSpoken = false;
      let frameCount = 0;
      let noiseSum = 0;
      let threshold = 12; // recalculated during calibration below

      const checkSilence = () => {
        if (!mediaRecorderRef.current || mediaRecorderRef.current.state === 'inactive') return;

        // Native STT onend and this AudioContext loop run in parallel for reliability.
        analyser.getByteFrequencyData(dataArray);

        // Average energy across the spectrum. This is far more stable than the
        // single loudest bin, which spikes on random noise and made endpointing
        // either never fire or fire at the wrong moment.
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];
        const level = sum / dataArray.length;

        const now = Date.now();
        if (frameCount < CALIBRATION_FRAMES) {
          // Learn the ambient noise floor, then set the speech threshold well above it.
          noiseSum += level;
          frameCount++;
          threshold = Math.max((noiseSum / frameCount) * 2 + 5, 8);
          silenceStart = now;
        } else if (level > threshold) {
          // Voice present — require sustained energy before we trust it as speech,
          // so a single cough/click can't arm the auto-stop.
          if (speechStart === 0) speechStart = now;
          if (now - speechStart >= MIN_SPEECH_MS) hasSpoken = true;
          silenceStart = now;
        } else {
          // Below threshold: accumulate trailing silence.
          speechStart = 0;
          if (hasSpoken && now - silenceStart > SILENCE_HANGOVER_MS) {
            stopRecording();
            return;
          }
        }
        requestAnimationFrame(checkSilence);
      };
      
      mediaRecorderRef.current.start(200);
      setIsRecording(true);
      checkSilence();
    } catch (err) {
      console.error("Error accessing microphone:", err);
      alert("Microphone access is required.");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
      setIsRecording(false);
    }
  };

  useEffect(() => {
    if (shouldRecord && !isRecording && !isProcessing) {
      startRecording();
    }
  }, [shouldRecord, isRecording, isProcessing]);

  return (
    <div className="flex flex-col items-center w-full">
      <button 
        className={`
          relative flex items-center justify-center w-24 h-24 rounded-full transition-all duration-300 ease-out shadow-lg
          ${isProcessing ? 'bg-slate-800 text-slate-500 cursor-not-allowed' : 
            isRecording ? 'bg-red-500 text-white recording-pulse hover:bg-red-600 scale-105' : 
            'bg-blue-600 text-white hover:bg-blue-500 hover:scale-105 hover:shadow-blue-500/25'}
        `}
        onClick={isRecording ? stopRecording : startRecording}
        disabled={isProcessing}
      >
        {isProcessing ? (
          <Loader2 className="w-10 h-10 animate-spin" />
        ) : isRecording ? (
          <Square className="w-8 h-8 fill-current" />
        ) : (
          <Mic className="w-10 h-10" />
        )}
      </button>
      
      <div className="mt-6 flex flex-col items-center justify-center min-h-[4rem]">
        {interimTranscript && (
          <p className="text-slate-300 text-xl font-semibold italic mb-3 animate-pulse text-center max-w-lg">
            "{interimTranscript}"
          </p>
        )}
        {isProcessing ? (
          <p className="text-blue-400 font-medium animate-pulse flex items-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin" /> Analyzing and thinking...
          </p>
        ) : isRecording ? (
          <p className="text-red-400 font-medium flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse"></span>
            Listening... (Auto-detects when you finish speaking)
          </p>
        ) : (
          <p className="text-slate-400 font-medium">Click to manually speak, or wait for auto-record</p>
        )}
      </div>
    </div>
  );
}

export default VoiceRecorder;
