/**
 * Simple placeholder component for scaffolding.
 * Replace with real components as code is migrated.
 */

interface PlaceholderProps {
  title: string;
  description?: string;
}

export function Placeholder({ title, description }: PlaceholderProps) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "60vh",
        color: "var(--color-text-primary)",
        fontFamily: "system-ui, sans-serif",
      }}
    >
      <h2
        style={{
          fontSize: "1.5rem",
          fontWeight: 500,
          color: "var(--color-primary)",
          marginBottom: "8px",
        }}
      >
        T空间 - {title}
      </h2>
      <p style={{ color: "var(--color-text-secondary)" }}>
        {description || "This is a placeholder. Migrate real component here."}
      </p>
    </div>
  );
}
