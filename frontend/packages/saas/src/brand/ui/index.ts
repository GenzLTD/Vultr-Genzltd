/**
 * SaaS UI component library — barrel export.
 *
 * Pure UI components: no store, no API, no routing.
 * All data is passed via props.
 *
 * Import examples:
 *   import { SaasButton, SaasCard } from "@looma/saas/brand/ui";
 *   import type { SaasButtonProps } from "@looma/saas/brand/ui";
 */

export { default as SaasButton } from "./SaasButton";
export { default as SaasInput } from "./SaasInput";
export { default as SaasSelect } from "./SaasSelect";
export { default as SaasTextArea } from "./SaasTextArea";
export { default as SaasCard } from "./SaasCard";
export { default as SaasSidebar } from "./SaasSidebar";
export { default as SaasHeader } from "./SaasHeader";
export { default as SaasKPICard } from "./SaasKPICard";
export { default as SaasDataTable } from "./SaasDataTable";
export { default as SaasChatBubble } from "./SaasChatBubble";
export { default as SaasStreamingText } from "./SaasStreamingText";
export { default as SaasResumeUploader } from "./SaasResumeUploader";
export { SaasLoading, SaasSkeleton } from "./SaasLoading";
export { SaasEmptyState, SaasErrorState } from "./SaasEmptyState";
export { default as SaasModal } from "./SaasModal";
export { default as SaasTooltip } from "./SaasTooltip";
export { default as SaasProgressBar } from "./SaasProgressBar";
export { default as SaasToggle } from "./SaasToggle";
export { default as SaasDatePicker } from "./SaasDatePicker";

// Type exports
export type {
  ButtonVariant,
  ButtonSize,
  SaasButtonProps,
  SaasInputProps,
  SaasSelectOption,
  SaasSelectProps,
  SaasTextAreaProps,
  SaasCardProps,
  SidebarNavItem,
  SaasSidebarProps,
  SaasHeaderProps,
  KPITrend,
  SaasKPICardProps,
  DataTableColumn,
  SaasDataTableProps,
  ChatRole,
  SaasChatBubbleProps,
  SaasStreamingTextProps,
  UploadState,
  SaasResumeUploaderProps,
  SaasLoadingProps,
  SaasSkeletonProps,
  SaasEmptyStateProps,
  SaasErrorStateProps,
  SaasModalSize,
  SaasModalProps,
  TooltipPosition,
  SaasTooltipProps,
  ProgressVariant,
  ProgressSize,
  LabelPosition,
  SaasProgressBarProps,
  SaasToggleProps,
  SaasDatePickerProps,
} from "./types";
