/**
 * SaaS StreamingText — pure UI component.
 * Shows text with a blinking cursor for AI streaming output.
 *
 * Note: This component just displays the `text` prop as-is.
 * Internal team handles the actual streaming (SSE / fetch) and
 * passes the growing text via props.
 */
import type { SaasStreamingTextProps } from "./types";

export default function SaasStreamingText({
  text,
  done = false,
  cursorBlink = true,
}: SaasStreamingTextProps) {
  return (
    <span style={{
      fontSize: "var(--font-size-sm)",
      lineHeight: "var(--line-height-relaxed)",
      color: "var(--color-text-primary)",
      fontFamily: "var(--font-family)",
    }}>
      {text}
      {!done && (
        <span
          style={{
            display: "inline-block",
            width: "var(--chat-streaming-cursor-width)",
            height: "1em",
            background: "var(--chat-streaming-cursor)",
            marginLeft: 2,
            verticalAlign: "text-bottom",
            animation: cursorBlink ? "cursorBlink 1s step-end infinite" : "none",
          }}
        />
      )}
      <style>{`
        @keyframes cursorBlink {
          0%, 50% { opacity: 1; }
          51%, 100% { opacity: 0; }
        }
      `}</style>
    </span>
  );
}
