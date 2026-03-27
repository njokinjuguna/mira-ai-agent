// src/global.d.ts
export {};

declare global {
  interface Window {
    SpeechRecognition: typeof webkitSpeechRecognition;
    webkitSpeechRecognition: typeof webkitSpeechRecognition;
  }

  interface SpeechRecognition extends EventTarget {
    lang: string;
    continuous: boolean;
    interimResults: boolean;
    start(): void;
    stop(): void;
    abort(): void;
    onaudioend?: (event: Event) => void;
    onend?: (event: Event) => void;
    onerror?: (event: SpeechRecognitionErrorEvent) => void;
    onnomatch?: (event: Event) => void;
    onresult?: (event: SpeechRecognitionEvent) => void;
    onsoundstart?: (event: Event) => void;
    onspeechend?: (event: Event) => void;
    onstart?: (event: Event) => void;
  }

  interface SpeechRecognitionErrorEvent extends Event {
    error: string;
  }

  interface SpeechRecognitionEvent extends Event {
    results: SpeechRecognitionResultList;
  }
}
