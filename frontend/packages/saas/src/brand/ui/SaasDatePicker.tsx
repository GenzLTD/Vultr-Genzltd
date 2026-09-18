/**
 * SaaS DatePicker — pure UI component (simplified version).
 * Features: date selection, min/max dates, disabled dates, clearable.
 *
 * Note: This is a simplified version. For full date picker functionality,
 * consider using a library like react-datepicker with custom styling.
 */
import { useState, useRef, useEffect } from "react";
import type { SaasDatePickerProps } from "./types";

export default function SaasDatePicker({
  value,
  onChange,
  placeholder = "Select date",
  minDate,
  maxDate,
  disabled = false,
  clearable = true,
  size = "md",
  error,
}: SaasDatePickerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedDate, setSelectedDate] = useState<Date | null>(value || null);
  const datePickerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (datePickerRef.current && !datePickerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen]);

  const sizeStyles: Record<string, React.CSSProperties> = {
    sm: { height: "var(--input-height-sm)", fontSize: "var(--font-size-sm)" },
    md: { height: "var(--input-height-md)", fontSize: "var(--font-size-base)" },
    lg: { height: "var(--input-height-lg)", fontSize: "var(--font-size-lg)" },
  };

  const formatDate = (date: Date | null): string => {
    if (!date) return "";
    return date.toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  const handleDateSelect = (date: Date) => {
    setSelectedDate(date);
    onChange?.(date);
    setIsOpen(false);
  };

  const handleClear = () => {
    setSelectedDate(null);
    onChange?.(null);
  };

  // Generate days for current month (simplified)
  const generateCalendarDays = () => {
    const today = new Date();
    const year = today.getFullYear();
    const month = today.getMonth();
    const lastDay = new Date(year, month + 1, 0);
    const daysInMonth = lastDay.getDate();

    const days = [];
    for (let day = 1; day <= daysInMonth; day++) {
      const date = new Date(year, month, day);
      const isDisabled =
        (minDate && date < minDate) ||
        (maxDate && date > maxDate) ||
        disabled;
      
      const isSelected = selectedDate && 
        date.getDate() === selectedDate.getDate() &&
        date.getMonth() === selectedDate.getMonth() &&
        date.getFullYear() === selectedDate.getFullYear();

      days.push({ date, isDisabled, isSelected });
    }

    return days;
  };

  const calendarDays = generateCalendarDays();

  return (
    <div
      ref={datePickerRef}
      style={{
        position: "relative",
        width: "100%",
      }}
    >
      {/* Input field */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--spacing-xs)",
          background: "var(--input-bg)",
          border: error ? "var(--input-border-error)" : "var(--input-border)",
          borderRadius: "var(--input-radius)",
          padding: "0 var(--spacing-sm)",
          cursor: disabled ? "not-allowed" : "pointer",
          opacity: disabled ? 0.5 : 1,
          transition: "var(--transition-fast)",
          ...sizeStyles[size],
        }}
        onClick={() => !disabled && setIsOpen(!isOpen)}
        onMouseEnter={(e) => {
          if (!disabled) e.currentTarget.style.borderColor = "var(--input-border-focus)";
        }}
        onMouseLeave={(e) => {
          if (!disabled) e.currentTarget.style.borderColor = error ? "var(--color-border-error)" : "var(--color-border)";
        }}
      >
        {/* Calendar icon */}
        <span style={{ color: "var(--color-text-muted)", fontSize: "1.1em" }}>📅</span>
        
        {/* Selected date or placeholder */}
        <span
          style={{
            flex: 1,
            color: selectedDate ? "var(--color-text-primary)" : "var(--color-text-disabled)",
          }}
        >
          {selectedDate ? formatDate(selectedDate) : placeholder}
        </span>

        {/* Clear button */}
        {clearable && selectedDate && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              handleClear();
            }}
            style={{
              background: "none",
              border: "none",
              color: "var(--color-text-muted)",
              cursor: "pointer",
              padding: "var(--spacing-xs)",
              fontSize: "1.2rem",
              lineHeight: 1,
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = "var(--color-text-secondary)")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "var(--color-text-muted)")}
          >
            ×
          </button>
        )}

        {/* Dropdown arrow */}
        <span
          style={{
            color: "var(--color-text-muted)",
            transition: "var(--transition-fast)",
            transform: isOpen ? "rotate(180deg)" : "rotate(0)",
          }}
        >
          ▼
        </span>
      </div>

      {/* Error message */}
      {error && (
        <div
          style={{
            fontSize: "var(--font-size-xs)",
            color: "var(--color-danger)",
            marginTop: "var(--spacing-xs)",
          }}
        >
          {error}
        </div>
      )}

      {/* Calendar dropdown */}
      {isOpen && (
        <div
          style={{
            position: "absolute",
            top: "100%",
            left: 0,
            right: 0,
            marginTop: "var(--spacing-xs)",
            background: "var(--color-bg-card)",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-md)",
            boxShadow: "var(--shadow-lg)",
            zIndex: "var(--z-dropdown)",
            padding: "var(--spacing-md)",
            animation: "fadeIn 150ms ease-out",
          }}
        >
          {/* Month/year header */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: "var(--spacing-md)",
            }}
          >
            <button
              style={{
                background: "none",
                border: "none",
                color: "var(--color-text-secondary)",
                cursor: "pointer",
                padding: "var(--spacing-xs)",
              }}
            >
              ◀
            </button>
            <div style={{ fontWeight: "var(--font-weight-semibold)" }}>
              {new Date().toLocaleDateString("en-US", { month: "long", year: "numeric" })}
            </div>
            <button
              style={{
                background: "none",
                border: "none",
                color: "var(--color-text-secondary)",
                cursor: "pointer",
                padding: "var(--spacing-xs)",
              }}
            >
              ▶
            </button>
          </div>

          {/* Weekday headers */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(7, 1fr)",
              gap: "var(--spacing-xs)",
              marginBottom: "var(--spacing-sm)",
            }}
          >
            {["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"].map((day) => (
              <div
                key={day}
                style={{
                  textAlign: "center",
                  fontSize: "var(--font-size-xs)",
                  color: "var(--color-text-muted)",
                  fontWeight: "var(--font-weight-medium)",
                }}
              >
                {day}
              </div>
            ))}
          </div>

          {/* Calendar days */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(7, 1fr)",
              gap: "var(--spacing-xs)",
            }}
          >
            {calendarDays.map(({ date, isDisabled, isSelected }) => (
              <button
                key={date.getDate()}
                onClick={() => !isDisabled && handleDateSelect(date)}
                disabled={isDisabled}
                style={{
                  background: isSelected ? "var(--color-primary)" : "transparent",
                  color: isSelected ? "#fff" : "var(--color-text-primary)",
                  border: "none",
                  borderRadius: "var(--radius-sm)",
                  padding: "var(--spacing-xs)",
                  fontSize: "var(--font-size-sm)",
                  cursor: isDisabled ? "not-allowed" : "pointer",
                  opacity: isDisabled ? 0.3 : 1,
                  transition: "var(--transition-fast)",
                }}
                onMouseEnter={(e) => {
                  if (!isDisabled && !isSelected) {
                    e.currentTarget.style.background = "var(--color-bg-hover)";
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isDisabled && !isSelected) {
                    e.currentTarget.style.background = "transparent";
                  }
                }}
              >
                {date.getDate()}
              </button>
            ))}
          </div>

          {/* Today button */}
          <div
            style={{
              marginTop: "var(--spacing-md)",
              paddingTop: "var(--spacing-md)",
              borderTop: "1px solid var(--color-border-light)",
              textAlign: "center",
            }}
          >
            <button
              onClick={() => handleDateSelect(new Date())}
              style={{
                background: "none",
                border: "none",
                color: "var(--color-primary)",
                cursor: "pointer",
                fontSize: "var(--font-size-sm)",
                padding: "var(--spacing-xs) var(--spacing-md)",
              }}
            >
              Today
            </button>
          </div>
        </div>
      )}

      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(-8px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}