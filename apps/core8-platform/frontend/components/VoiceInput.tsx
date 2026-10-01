"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Mic, MicOff, Volume2, VolumeX } from "lucide-react";

interface Props {
  onTranscript: (text: string) => void;
  disabled?: boolean;
  ttsEnabled: boolean;
  onToggleTts: () => void;
}

// Extend Window for cross-browser SpeechRecognition
declare global {
  interface Window {
    SpeechRecognition: typeof SpeechRecognition;
    webkitSpeechRecognition: typeof SpeechRecognition;
  }
}

export default function VoiceInput({ onTranscript, disabled, ttsEnabled, onToggleTts }: Props) {
  const [listening, setListening] = useState(false);
  const [bars, setBars] = useState<number[]>(Array(20).fill(2));
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animRef = useRef<number>(0);
  const streamRef = useRef<MediaStream | null>(null);

  const stopListening = useCallback(() => {
    recognitionRef.current?.stop();
    cancelAnimationFrame(animRef.current);
    streamRef.current?.getTracks().forEach((t) => t.stop());
    audioCtxRef.current?.close();
    audioCtxRef.current = null;
    setListening(false);
    setBars(Array(20).fill(2));
  }, []);

  const startListening = useCallback(async () => {
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRec) {
      alert("Speech recognition is not supported in this browser. Try Chrome.");
      return;
    }

    // Start microphone for waveform
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const audioCtx = new AudioContext();
      audioCtxRef.current = audioCtx;
      const analyser = audioCtx.createAnalyser();
      analyserRef.current = analyser;
      analyser.fftSize = 64;
      audioCtx.createMediaStreamSource(stream).connect(analyser);

      const dataArr = new Uint8Array(analyser.frequencyBinCount);
      const animate = () => {
        analyser.getByteFrequencyData(dataArr);
        const newBars = Array.from({ length: 20 }, (_, i) => {
          const idx = Math.floor((i / 20) * dataArr.length);
          return Math.max(2, (dataArr[idx] / 255) * 40);
        });
        setBars(newBars);
        animRef.current = requestAnimationFrame(animate);
      };
      animate();
    } catch { /* mic permission denied */ }

    const rec = new SpeechRec();
    rec.continuous = false;
    rec.interimResults = false;
    rec.lang = "en-US";
    recognitionRef.current = rec;

    rec.onresult = (e) => {
      const text = e.results[0]?.[0]?.transcript ?? "";
      if (text.trim()) onTranscript(text.trim());
    };
    rec.onend = () => stopListening();
    rec.onerror = () => stopListening();
    rec.start();
    setListening(true);
  }, [onTranscript, stopListening]);

  useEffect(() => () => stopListening(), [stopListening]);

  return (
    <div className="flex items-center gap-2">
      {/* Waveform */}
      <AnimatePresence>
        {listening && (
          <motion.div
            initial={{ opacity: 0, width: 0 }}
            animate={{ opacity: 1, width: "auto" }}
            exit={{ opacity: 0, width: 0 }}
            className="flex items-center gap-[2px] h-8 overflow-hidden"
          >
            {bars.map((h, i) => (
              <motion.div
                key={i}
                animate={{ scaleY: h / 40 }}
                transition={{ duration: 0.05 }}
                className="w-[3px] rounded-full origin-center"
                style={{
                  height: "32px",
                  background: `hsl(${190 + i * 4}, 100%, 60%)`,
                  boxShadow: `0 0 4px hsl(${190 + i * 4}, 100%, 60%)`,
                }}
              />
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {/* TTS toggle */}
      <motion.button
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.9 }}
        onClick={onToggleTts}
        title={ttsEnabled ? "Disable voice response" : "Enable voice response"}
        className={`p-2 rounded-lg transition-colors ${
          ttsEnabled
            ? "text-[#00d4ff] bg-[#00d4ff]/10 border border-[#00d4ff]/30"
            : "text-muted-foreground hover:text-foreground border border-transparent"
        }`}
      >
        {ttsEnabled ? <Volume2 size={16} /> : <VolumeX size={16} />}
      </motion.button>

      {/* Mic button */}
      <motion.button
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.9 }}
        onClick={listening ? stopListening : startListening}
        disabled={disabled}
        className={`relative p-2.5 rounded-xl transition-all disabled:opacity-40 ${
          listening
            ? "bg-[#ff4757] text-white border border-[#ff4757]/50"
            : "bg-[#00d4ff]/10 text-[#00d4ff] border border-[#00d4ff]/30 hover:bg-[#00d4ff]/20"
        }`}
      >
        {/* Pulse rings when listening */}
        {listening && (
          <>
            <span className="absolute inset-0 rounded-xl border-2 border-[#ff4757] animate-ping opacity-60" />
            <span className="absolute inset-[-4px] rounded-xl border border-[#ff4757]/30 animate-ping" style={{ animationDelay: "0.3s" }} />
          </>
        )}
        {listening ? <MicOff size={16} /> : <Mic size={16} />}
      </motion.button>
    </div>
  );
}

// TTS utility — call this to speak agent text
export function speak(text: string) {
  if (typeof window === "undefined") return;
  window.speechSynthesis.cancel();
  const utt = new SpeechSynthesisUtterance(text);
  utt.rate = 1.0;
  utt.pitch = 1.0;
  // Prefer a natural-sounding voice
  const voices = window.speechSynthesis.getVoices();
  const preferred = voices.find((v) =>
    v.name.toLowerCase().includes("neural") ||
    v.name.toLowerCase().includes("google") ||
    v.name.toLowerCase().includes("natural")
  );
  if (preferred) utt.voice = preferred;
  window.speechSynthesis.speak(utt);
}
