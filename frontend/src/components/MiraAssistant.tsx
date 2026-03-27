// MiraAssistant.tsx
import { useState, useEffect, useRef } from "react";
import { v4 as uuidv4 } from "uuid";
import ImageWithLoader from "../components/ImageWithLoader";
import MiraAvatar from "../components/MiraAvatar";

interface SearchResult {
  id?: string;
  image_url?: string; // "/image/<id>" OR "/generated/<file>.png"
  caption?: string;
  best_match?: string;
  score?: number;
  index?: number;
  message?: string; // fallback message case
}

interface Message {
  type: "user" | "mira";
  text: string;
  intent?: string;
  lang?: "it" | "en";
  data?: SearchResult[];
  done?: boolean;
}

type MiraApiResponse = {
  message?: string; // backend uses this
  answer?: string; // keep for backwards compatibility
  type?: string; // intent
  lang?: "it" | "en" | string;
  results?: SearchResult[];
};

type AgentState = "idle" | "listening" | "thinking" | "speaking" | "error";

function sanitizeForSpeech(text: string) {
  return (text || "")
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/\*(.*?)\*/g, "$1")
    .replace(/__(.*?)__/g, "$1")
    .replace(/_(.*?)_/g, "$1")
    .replace(/`{1,3}([^`]+)`{1,3}/g, "$1")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/^\s*[-*•]\s+/gm, "")
    .replace(/[•]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

export default function MiraAssistant() {
  const [selectedLang, setSelectedLang] = useState<"it" | "en">("it");
  const [query, setQuery] = useState<string>("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [supportsSpeech, setSupportsSpeech] = useState<boolean>(false);
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [micError, setMicError] = useState<boolean>(false);
  const [showLangSelector, setShowLangSelector] = useState(false);
  const [agentState, setAgentState] = useState<AgentState>("idle");
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const chatContainerRef = useRef<HTMLDivElement | null>(null);
  const sessionIdRef = useRef<string>("");

  // ✅ We are doing away with references: keep this ONLY for the UI button
  const [selectedReferenceId, setSelectedReferenceId] = useState<string | null>(null);

  function pickPreferredVoice(lang: "it" | "en") {
    const list = voices || [];
    if (!list.length) return undefined;

    const langPrefix = lang === "it" ? "it" : "en";

    const femaleNameHints = [
      "female",
      "zira",
      "susan",
      "samantha",
      "victoria",
      "karen",
      "tessa",
      "aria",
      "alice",
      "emma",
      "elsa",
      "monica",
      "joanna",
      "ivy",
      "kendra",
      "kimberly",
      "salli",
      "amy",
      "fiona",
      "serena",
      "olivia",
    ];

    const maleNameHints = [
      "david",
      "mark",
      "george",
      "daniel",
      "alex",
      "guy",
      "ryan",
      "thomas",
      "james",
      "diego",
      "luca",
      "riccardo",
      "cosimo",
      "marco",
      "google",
      "microsoft",
    ];

    const isFemaleByName = (v: SpeechSynthesisVoice) =>
      femaleNameHints.some((k) => v.name.toLowerCase().includes(k));

    const isMaleByName = (v: SpeechSynthesisVoice) =>
      maleNameHints.some((k) => v.name.toLowerCase().includes(k)) && !isFemaleByName(v);

    const byLang = (prefix: string) =>
      list.filter((v) => (v.lang || "").toLowerCase().startsWith(prefix));

    const primaryCandidates = byLang(langPrefix);
    const primaryMale = primaryCandidates.find(isMaleByName);
    if (primaryMale) return primaryMale;

    const fallbackCandidates = byLang(langPrefix === "it" ? "en" : "it");
    const fallbackMale = fallbackCandidates.find(isMaleByName);
    if (fallbackMale) return fallbackMale;

    const notObviouslyFemale = list.find((v) => !isFemaleByName(v));
    if (notObviouslyFemale) return notObviouslyFemale;

    return undefined;
  }

  const lastUserQueryRef = useRef<string>("");

  function stopSpeaking() {
    if (typeof window === "undefined") return;
    window.speechSynthesis?.cancel();
    setAgentState("idle");
  }

  function speak(text: string, lang: "it" | "en" = "it") {
    if (!supportsSpeech || typeof window === "undefined") return;

    window.speechSynthesis.cancel();

    const cleanText = sanitizeForSpeech(text).slice(0, 900);
    const utterance = new SpeechSynthesisUtterance(cleanText);

    const v = pickPreferredVoice(lang);

    if (v) {
      utterance.voice = v;
      utterance.lang = v.lang || (lang === "en" ? "en-US" : "it-IT");
    } else {
      console.warn(
        "⚠️ No male voice found on this device/browser. Install a male TTS voice or use Edge voices."
      );
      utterance.lang = lang === "en" ? "en-US" : "it-IT";
    }

    utterance.onstart = () => setAgentState("speaking");
    utterance.onend = () => setAgentState("idle");
    utterance.onerror = () => setAgentState("idle");

    window.speechSynthesis.speak(utterance);
  }

  function typeOutMessage(finalText: string, opts?: { speedMs?: number; onDone?: () => void }) {
    const speedMs = opts?.speedMs ?? 12;

    setMessages((prev) => [
      ...prev,
      { type: "mira", text: "", intent: undefined, lang: selectedLang, data: undefined, done: false },
    ]);

    let i = 0;
    const step = Math.max(1, Math.floor(finalText.length / 140));

    const interval = setInterval(() => {
      i = Math.min(finalText.length, i + step);
      const partial = finalText.slice(0, i);

      setMessages((prev) => {
        const copy = [...prev];
        for (let k = copy.length - 1; k >= 0; k--) {
          if (copy[k].type === "mira") {
            copy[k] = { ...copy[k], text: partial, done: i >= finalText.length };
            break;
          }
        }
        return copy;
      });

      if (i >= finalText.length) {
        clearInterval(interval);
        opts?.onDone?.();
      }
    }, speedMs);

    return () => clearInterval(interval);
  }

  useEffect(() => {
    if (!sessionIdRef.current) sessionIdRef.current = uuidv4();
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;

    setSupportsSpeech("speechSynthesis" in window);

    const loadVoices = () => {
      const all = window.speechSynthesis.getVoices();
      if (all && all.length) setVoices(all);
      console.table(all.map((v) => ({ name: v.name, lang: v.lang })));
    };

    loadVoices();
    window.speechSynthesis.onvoiceschanged = loadVoices;

    return () => {
      window.speechSynthesis.onvoiceschanged = null;
    };
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const SpeechRecognitionCtor =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognitionCtor) return;

    const recognition: SpeechRecognition = new SpeechRecognitionCtor();
    recognition.continuous = false;
    recognition.interimResults = false;

    recognition.onstart = () => {
      setAgentState("listening");
      setMicError(false);
      setMessages((prev) => [
        ...prev,
        {
          type: "mira",
          text: selectedLang === "en" ? "🎤 Listening… speak now." : "🎤 Ti ascolto… parla ora.",
          lang: selectedLang,
        },
      ]);
    };

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let spokenText = event.results[0][0].transcript || "";
      spokenText = spokenText.replace(/\bmirror\b/gi, "Mira");
      setQuery(spokenText);
      setAgentState("idle");
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      console.error("🎤 Microphone error:", event.error);
      setMicError(true);
      setAgentState("error");
      setMessages((prev) => [
        ...prev,
        {
          type: "mira",
          text:
            selectedLang === "en"
              ? "❌ Microphone error. Please try again."
              : "❌ Errore del microfono. Per favore, riprova.",
          lang: selectedLang,
        },
      ]);
    };

    recognition.onend = () => {
      setShowLangSelector(false);
      if (agentState === "listening") setAgentState("idle");
    };

    recognitionRef.current = recognition;
  }, [selectedLang, agentState]);

  useEffect(() => {
    setMessages([
      {
        type: "mira",
        lang: "it",
        text:
          "👋 Ciao! Sono Mira, il tuo esperto personale di interior design.\n\n" +
          "Posso aiutarti a scoprire disegni esclusivi realizzati a mano da Giancarlo Cundo.\n",
      },
    ]);
  }, []);

  useEffect(() => {
    const el = chatContainerRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  const lastSpokenRef = useRef<string>("");

  useEffect(() => {
    const last = messages[messages.length - 1];
    if (!last || last.type !== "mira") return;
    if (!last.done) return;

    const text = (last.text || "").trim();
    if (!text) return;

    const fingerprint = `${messages.length}:${text}`;
    if (lastSpokenRef.current === fingerprint) return;

    lastSpokenRef.current = fingerprint;

    setTimeout(() => {
      speak(text, last.lang ?? selectedLang);
    }, 150);
  }, [messages, selectedLang]);

  async function askMira(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;

    stopSpeaking();
    setAgentState("thinking");

    const userText = query.trim();
    lastUserQueryRef.current = userText;
    setMessages((prev) => [...prev, { type: "user", text: userText, lang: selectedLang }]);
    setQuery("");
    setLoading(true);

    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL;
      const res = await fetch(`${apiBase}/mira`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: userText,
          session_id: sessionIdRef.current,
          lang: selectedLang,
        }),
      });

      const data = (await res.json()) as MiraApiResponse;

      const intent = data.type || "";
      const results = Array.isArray(data.results) ? data.results : [];
      const lang: "it" | "en" = data.lang === "it" ? "it" : "en";

     


      const defaultText =
        lang === "en"
          ? "How can I help?\nCome posso aiutarti?"
          : "Come posso aiutarti?\nHow can I help?";

      const text = (data.message || data.answer || defaultText).toString();


      typeOutMessage(text, {
        onDone: () => {
          setQuery(lastUserQueryRef.current);
        },
      });

      setTimeout(() => {
        setMessages((prev) => {
          const copy = [...prev];
          for (let k = copy.length - 1; k >= 0; k--) {
            if (copy[k].type === "mira") {
              copy[k] = { ...copy[k], intent, lang, data: results };
              break;
            }
          }
          return copy;
        });
      }, 250);

      setAgentState("idle");
    } catch (err) {
      console.error(err);
      setAgentState("error");

      const text =
        selectedLang === "en"
          ? "⚠️ I couldn’t reach Mira right now."
          : "⚠️ Connessione a Mira non riuscita.";

      setMessages((prev) => [...prev, { type: "mira", text, lang: selectedLang, done: true }]);
    } finally {
      setLoading(false);
    }
  }

  // ✅ Keep this button + endpoint (clean solution), even if we no longer use references.
  async function clearReference() {
    const apiBase = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");
    if (!apiBase) {
      console.error("NEXT_PUBLIC_API_URL is missing");
      return;
    }

    try {
      const res = await fetch(`${apiBase}/session/clear-reference`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionIdRef.current,
        }),
      });

      if (!res.ok) {
        let data: any = null;
        try {
          data = await res.json();
        } catch {}
        throw new Error(data?.error || `Failed to clear reference (${res.status})`);
      }

      // ✅ update UI state
      setSelectedReferenceId(null);

      setMessages((prev) => [
        ...prev,
        {
          type: "mira",
          text:
            selectedLang === "en"
              ? "✅ Session cleared. You can start a new search now."
              : "✅ Sessione ripulita. Ora puoi iniziare una nuova ricerca.",
          lang: selectedLang,
          done: true,
        },
      ]);
    } catch (err) {
      console.error("clearReference error:", err);
      setMessages((prev) => [
        ...prev,
        {
          type: "mira",
          text:
            selectedLang === "en"
              ? "⚠️ I couldn’t clear the session. Please try again."
              : "⚠️ Non sono riuscita a ripulire la sessione. Riprova.",
          lang: selectedLang,
          done: true,
        },
      ]);
    }
  }

  function handleMicClick() {
    setShowLangSelector(true);
  }

  function startRecognition(newLang: "it" | "en") {
    const rec = recognitionRef.current;
    if (!rec) {
      setMicError(true);
      setAgentState("error");
      return;
    }

    try {
      rec.lang = newLang === "en" ? "en-US" : "it-IT";
      stopSpeaking();
      rec.start();
      setMicError(false);
      setShowLangSelector(false);
    } catch (e) {
      console.error("🎤 startRecognition error:", e);
      setMicError(true);
      setAgentState("error");
    }
  }

  function agentStatusLabel() {
    if (agentState === "listening") return selectedLang === "en" ? "Listening…" : "In ascolto…";
    if (agentState === "thinking") return selectedLang === "en" ? "Thinking…" : "Sto pensando…";
    if (agentState === "speaking") return selectedLang === "en" ? "Speaking…" : "Sto rispondendo…";
    if (agentState === "error") return selectedLang === "en" ? "Issue detected" : "Problema rilevato";
    return "Online";
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6 flex items-center justify-center">
      <div className="w-full max-w-5xl grid grid-cols-1 md:grid-cols-[260px_1fr] gap-4">
        <aside className="bg-white rounded-2xl shadow-lg p-5 h-fit md:sticky md:top-6">
          <div className="flex flex-col items-center text-center gap-3">
            <MiraAvatar state={agentState} size={180} />
            <div className="space-y-1">
              <div className="text-lg font-bold text-gray-800">Mira</div>
              <div className="text-sm text-gray-500">Il tuo esperto di interior design</div>
            </div>

            <span className="text-xs px-3 py-1 rounded-full bg-gray-100 text-gray-700">
              {agentStatusLabel()}
            </span>

            <div className="pt-2 w-full border-t border-gray-100" />
          </div>
        </aside>

        <main className="bg-white rounded-2xl shadow-lg p-6">
          <div ref={chatContainerRef} className="space-y-4 max-h-[60vh] overflow-y-auto pr-2 mb-4">
            {messages.map((msg, index) => {
              const hasImages =
                Array.isArray(msg.data) &&
                msg.data.some((r) => typeof r.image_url === "string" && r.image_url.length > 0);

              return (
                <div
                  key={index}
                  className={`flex ${msg.type === "user" ? "justify-end" : "justify-start"} w-full`}
                >
                  <div
                    className={`rounded-xl px-4 py-3 text-sm break-words max-w-[92%] sm:max-w-[80%] ${
                      msg.type === "user" ? "bg-black text-white" : "bg-gray-100 text-gray-800"
                    }`}
                  >
                    {hasImages && Array.isArray(msg.data) ? (
                      <div className="space-y-3">
                        {msg.text ? <p className="whitespace-pre-wrap">{msg.text}</p> : null}

                        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 w-full">
                          {msg.data
                            .filter(
                              (img): img is { image_url: string; caption: string } =>
                                img.image_url !== undefined &&
                                typeof img.image_url === "string" &&
                                "caption" in img
                            )
                            .map((img, i) => (
                              <div key={i} className="w-full h-auto flex items-center justify-center">
                                {/* ✅ No references anymore */}
                                <ImageWithLoader img={img} />
                              </div>
                            ))}
                        </div>
                      </div>
                    ) : Array.isArray(msg.data) && msg.data[0]?.message ? (
                      <p className="whitespace-pre-wrap">{msg.data[0].message}</p>
                    ) : (
                      <p className="whitespace-pre-wrap">{msg.text}</p>
                    )}
                  </div>
                </div>
              );
            })}

            {loading && (
              <div className="flex gap-2 items-center text-sm text-gray-400 italic">
                {selectedLang === "en" ? "Mira is thinking…" : "Mira sta pensando…"}
              </div>
            )}
          </div>

          {/* ✅ Keep this button in case you want a clean reset */}
          {selectedReferenceId && (
            <div className="mb-2 flex justify-end">
              <button
                type="button"
                onClick={clearReference}
                className="text-xs px-3 py-2 rounded-xl bg-gray-200 hover:bg-gray-300 text-black"
                title={selectedLang === "en" ? "Clear session" : "Ripulisci sessione"}
              >
                {selectedLang === "en" ? "Clear / New search" : "Pulisci / Nuova ricerca"}
              </button>
            </div>
          )}

          <form onSubmit={askMira} className="flex flex-col sm:flex-row gap-2 w-full">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="flex-1 bg-white text-gray-800 placeholder-gray-500 border border-gray-300 p-3 rounded-xl focus:outline-none focus:ring-2 focus:ring-black w-full"
              placeholder={selectedLang === "en" ? "Ask Mira…" : "Chiedi qualcosa a Mira..."}
            />

            <div className="flex flex-row sm:flex-col gap-2 w-full sm:w-auto">
              <button
                type="button"
                onClick={handleMicClick}
                className="bg-gray-200 px-4 py-2 rounded-xl hover:bg-gray-300 text-black w-full sm:w-auto"
                title="Voice input"
              >
                🎤
              </button>

              <button
                type="submit"
                className="bg-black text-white px-5 py-2 rounded-xl hover:bg-gray-800 w-full sm:w-auto"
                disabled={loading}
                title="Send"
              >
                {loading ? "..." : selectedLang === "en" ? "Send" : "Invia"}
              </button>
            </div>
          </form>

          {showLangSelector && (
            <div className="flex justify-end mt-2">
              <label htmlFor="language" className="mr-2 text-sm text-gray-700 font-medium">
                {selectedLang === "en" ? "Language:" : "Lingua:"}
              </label>

              <select
                id="language"
                value={selectedLang}
                onChange={(e) => {
                  const newLang = e.target.value as "it" | "en";
                  setSelectedLang(newLang);
                  setTimeout(() => startRecognition(newLang), 120);
                }}
                className="border rounded-md px-3 py-2 text-sm bg-white text-gray-800 shadow-md"
              >
                <option value="it">Italiano 🇮🇹</option>
                <option value="en">English 🇺🇸</option>
              </select>
            </div>
          )}

          {micError && (
            <p className="text-center text-sm text-red-500 mt-2">
              {selectedLang === "en"
                ? "⚠️ Please allow microphone access to use voice input."
                : "⚠️ Per favore, consenti l'accesso al microfono per usare l'input vocale."}
            </p>
          )}
        </main>
      </div>
    </div>
  );
}
