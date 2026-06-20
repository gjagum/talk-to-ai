import React, { useState } from 'react';
import VoiceRecorder from './VoiceRecorder';
import ConversationLog from './ConversationLog';
import { PhoneCall, PhoneOff } from 'lucide-react';

export default function WhisperAgent({ persona }) {
  const [conversation, setConversation] = useState([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isInCall, setIsInCall] = useState(false);
  const [shouldRecord, setShouldRecord] = useState(false);

  const startCall = async () => {
    setIsInCall(true);
    setConversation([]);
    setIsProcessing(true);
    setShouldRecord(false);
    
    try {
      const formData = new FormData();
      formData.append('persona', persona);
      
      const response = await fetch('http://localhost:8000/api/voice/greeting', {
        method: 'POST',
        body: formData
      });
      
      const responseBlob = await response.blob();
      
      const aiResponseRaw = response.headers.get('X-Response') || '';
      const aiResponse = decodeURIComponent(aiResponseRaw);
      
      setConversation([
        { role: 'assistant', text: aiResponse, timestamp: new Date(), audio: responseBlob }
      ]);
      
      const audioUrl = URL.createObjectURL(responseBlob);
      const audio = new Audio(audioUrl);
      audio.onended = () => setShouldRecord(true);
      audio.play();
    } catch (error) {
      console.error('Error:', error);
      alert('Failed to connect call');
      setIsInCall(false);
    } finally {
      setIsProcessing(false);
    }
  };

  const endCall = () => {
    setIsInCall(false);
    setShouldRecord(false);
  };

  const handleVoiceSubmit = async (data) => {
    setIsProcessing(true);
    setShouldRecord(false);
    
    const formData = new FormData();
    if (data instanceof Blob) {
      formData.append('audio', data, 'recording.webm');
    } else if (data.text) {
      formData.append('text', data.text);
    }
    formData.append('persona', persona);
    
    try {
      const response = await fetch('http://localhost:8000/api/voice/process', {
        method: 'POST',
        body: formData,
      });
      
      const responseBlob = await response.blob();
      
      const transcriptRaw = response.headers.get('X-Transcript') || '';
      const aiResponseRaw = response.headers.get('X-Response') || '';
      const transcript = decodeURIComponent(transcriptRaw);
      const aiResponse = decodeURIComponent(aiResponseRaw);
      
      setConversation(prev => [
        ...prev,
        { role: 'user', text: transcript, timestamp: new Date() },
        { role: 'assistant', text: aiResponse, timestamp: new Date(), audio: responseBlob }
      ]);
      
      const audioUrl = URL.createObjectURL(responseBlob);
      const audio = new Audio(audioUrl);
      audio.onended = () => setShouldRecord(true);
      audio.play();
      
    } catch (error) {
      console.error('Error:', error);
      alert('Failed to process voice');
      setShouldRecord(true);
    } finally {
      setIsProcessing(false);
    }
  };

  if (!isInCall) {
    return (
      <div className="flex flex-col items-center justify-center gap-6 mt-8">
        <button 
          onClick={startCall}
          className="flex items-center gap-3 bg-purple-600 hover:bg-purple-500 text-white px-8 py-4 rounded-full text-xl font-bold shadow-lg shadow-purple-600/30 transition-all hover:scale-105"
        >
          <PhoneCall className="w-6 h-6" />
          Call Whisper Agent
        </button>
        <p className="text-slate-400 font-medium">Record -&gt; Transcribe -&gt; Respond (REST)</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center w-full gap-6 mt-8">
      <div className="glass-panel rounded-3xl p-8 flex flex-col items-center justify-center relative overflow-hidden w-full max-w-lg mx-auto">
        <VoiceRecorder 
          onSubmit={handleVoiceSubmit}
          isProcessing={isProcessing}
          shouldRecord={shouldRecord}
        />
        
        <button 
            onClick={endCall}
            className="mt-8 flex items-center gap-2 bg-red-500/20 text-red-400 border border-red-500/50 hover:bg-red-500 hover:text-white px-6 py-2 rounded-full font-medium transition-all"
          >
            <PhoneOff className="w-4 h-4" />
            End Call
          </button>
      </div>
      
      <div className="glass-panel rounded-3xl p-6 flex flex-col w-full">
        <ConversationLog conversation={conversation} />
      </div>
    </div>
  );
}
