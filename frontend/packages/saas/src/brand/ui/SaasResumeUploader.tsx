/**
 * SaaS ResumeUploader — pure UI component.
 * States: idle / dragging / uploading / success / error
 * Supports drag & drop visual feedback.
 */
import { useState, useCallback } from "react";
import type { SaasResumeUploaderProps } from "./types";

const STATE_CONFIG: Record<string, { icon: string; title: string; color: string; borderColor: string; bgColor: string }> = {
  idle: {
    icon: "📄",
    title: "拖拽简历到此处，或点击上传",
    color: "var(--color-text-secondary)",
    borderColor: "var(--color-border)",
    bgColor: "var(--color-bg-surface)",
  },
  dragging: {
    icon: "📥",
    title: "松开以上传文件",
    color: "var(--color-primary)",
    borderColor: "var(--color-primary)",
    bgColor: "var(--color-primary-light)",
  },
  uploading: {
    icon: "⏳",
    title: "上传中...",
    color: "var(--color-info)",
    borderColor: "var(--color-info)",
    bgColor: "var(--color-info-light)",
  },
  success: {
    icon: "✓",
    title: "上传成功",
    color: "var(--color-success)",
    borderColor: "var(--color-success)",
    bgColor: "var(--color-success-light)",
  },
  error: {
    icon: "✗",
    title: "上传失败",
    color: "var(--color-danger)",
    borderColor: "var(--color-danger)",
    bgColor: "var(--color-danger-light)",
  },
};

export default function SaasResumeUploader({
  state = "idle",
  fileName,
  fileSize,
  progress = 0,
  error,
  acceptedFormats = [".pdf", ".doc", ".docx"],
  onFileSelect,
  onRetry,
  onClear,
}: SaasResumeUploaderProps) {
  const [internalDragging, setInternalDragging] = useState(false);
  const effectiveState = internalDragging ? "dragging" : state;
  const config = STATE_CONFIG[effectiveState];

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setInternalDragging(false);
    const file = e.dataTransfer.files[0];
    if (file && onFileSelect) onFileSelect(file);
  }, [onFileSelect]);

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file && onFileSelect) onFileSelect(file);
  };

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setInternalDragging(true); }}
      onDragLeave={() => setInternalDragging(false)}
      onDrop={handleDrop}
      style={{
        border: `2px dashed ${config.borderColor}`,
        borderRadius: "var(--radius-lg)",
        background: config.bgColor,
        padding: "32px 24px",
        textAlign: "center",
        transition: "var(--transition-normal)",
        cursor: state === "idle" || state === "error" ? "pointer" : "default",
        position: "relative",
      }}
    >
      {/* Hidden file input */}
      {(state === "idle" || state === "error") && (
        <input
          type="file"
          accept={acceptedFormats.join(",")}
          onChange={handleFileInput}
          style={{
            position: "absolute",
            inset: 0,
            opacity: 0,
            cursor: "pointer",
          }}
        />
      )}

      {/* Icon */}
      <div style={{ fontSize: 40, marginBottom: "var(--radius-md)" }}>{config.icon}</div>

      {/* Title */}
      <div style={{ fontSize: "var(--font-size-sm)", color: config.color, fontWeight: "var(--font-weight-medium)" }}>
        {state === "error" && error ? error : config.title}
      </div>

      {/* File info */}
      {(state === "uploading" || state === "success") && fileName && (
        <div style={{ marginTop: "var(--radius-sm)", fontSize: "var(--font-size-xs)", color: "var(--color-text-muted)" }}>
          {fileName} {fileSize && `(${fileSize})`}
        </div>
      )}

      {/* Progress bar */}
      {state === "uploading" && (
        <div style={{
          marginTop: "var(--radius-md)",
          height: 6,
          background: "var(--color-bg-hover)",
          borderRadius: "var(--radius-full)",
          overflow: "hidden",
        }}>
          <div style={{
            height: "100%",
            width: `${progress}%`,
            background: "var(--color-primary)",
            borderRadius: "var(--radius-full)",
            transition: "width 300ms ease",
          }} />
        </div>
      )}

      {/* Accepted formats */}
      {state === "idle" && (
        <div style={{ marginTop: "var(--radius-sm)", fontSize: "var(--font-size-xs)", color: "var(--color-text-muted)" }}>
          支持 {acceptedFormats.join(" / ")} 格式
        </div>
      )}

      {/* Actions */}
      {state === "error" && onRetry && (
        <button
          onClick={(e) => { e.stopPropagation(); onRetry(); }}
          style={{
            marginTop: "var(--radius-md)",
            padding: "6px 16px",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-md)",
            background: "var(--color-bg-card)",
            color: "var(--color-text-primary)",
            cursor: "pointer",
            fontSize: "var(--font-size-sm)",
          }}
        >
          重试
        </button>
      )}

      {state === "success" && onClear && (
        <button
          onClick={(e) => { e.stopPropagation(); onClear(); }}
          style={{
            marginTop: "var(--radius-md)",
            padding: "4px 12px",
            border: "none",
            borderRadius: "var(--radius-md)",
            background: "transparent",
            color: "var(--color-text-muted)",
            cursor: "pointer",
            fontSize: "var(--font-size-xs)",
          }}
        >
          清除 ✕
        </button>
      )}
    </div>
  );
}
