// components/MiraAvatar.tsx
type AgentState = "idle" | "listening" | "thinking" | "speaking" | "error";

export default function MiraAvatar({
  state,
  size = 140,
}: {
  state: AgentState;
  size?: number;
}) {
  return (
    <div
      className="relative rounded-2xl shadow-md overflow-hidden bg-gray-100"
      style={{ width: size, height: size, minWidth: size }}
      title="Mira"
    >
      <img
        src="../mira-avatar.png"
        alt="Mira"
        className="w-full h-full object-cover"
        draggable={false}
      />

      {/* Speaking glow */}
      {state === "speaking" && (
        <span className="absolute inset-0 rounded-2xl ring-2 ring-black/30 animate-pulse" />
      )}

      {/* Thinking glow */}
      {state === "thinking" && (
        <span className="absolute inset-0 rounded-2xl ring-2 ring-gray-400/40 animate-pulse" />
      )}

      {/* Listening glow */}
      {state === "listening" && (
        <span className="absolute inset-0 rounded-2xl ring-2 ring-black/20 animate-pulse" />
      )}
    </div>
  );
}
