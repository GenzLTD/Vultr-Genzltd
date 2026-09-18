import type { Meta, StoryObj } from "@storybook/react";
import { 
  SaasModal, 
  SaasTooltip, 
  SaasProgressBar, 
  SaasToggle,
  SaasDatePicker 
} from "../index";
import SaasButton from "../SaasButton";
import SaasCard from "../SaasCard";

const meta: Meta = {
  title: "SaaS/New Components",
  parameters: {
    layout: "centered",
  },
};

export default meta;

// Modal 组件示例
export const ModalExample: StoryObj = {
  render: () => {
    const [isOpen, setIsOpen] = useState(false);
    
    return (
      <div>
        <SaasButton onClick={() => setIsOpen(true)}>
          Open Settings
        </SaasButton>
        
        <SaasModal
          isOpen={isOpen}
          onClose={() => setIsOpen(false)}
          title="Account Settings"
          size="md"
          footer={
            <div style={{ display: "flex", gap: "var(--spacing-sm)", justifyContent: "flex-end" }}>
              <SaasButton variant="ghost" onClick={() => setIsOpen(false)}>Cancel</SaasButton>
              <SaasButton variant="primary">Save Changes</SaasButton>
            </div>
          }
        >
          <div style={{ padding: "var(--spacing-md)" }}>
            <h3 style={{ marginBottom: "var(--spacing-md)" }}>General Settings</h3>
            <p style={{ color: "var(--color-text-secondary)", marginBottom: "var(--spacing-lg)" }}>
              Configure your account preferences and notification settings.
            </p>
          </div>
        </SaasModal>
      </div>
    );
  },
};

// Tooltip 组件示例
export const TooltipExample: StoryObj = {
  render: () => {
    return (
      <div style={{ display: "flex", gap: "var(--spacing-xl)", alignItems: "center" }}>
        <SaasTooltip content="This is a helpful tooltip" position="top">
          <SaasButton variant="outline">Hover Top</SaasButton>
        </SaasTooltip>
        
        <SaasTooltip 
          content={
            <div>
              <strong>Rich Content Tooltip</strong>
              <div style={{ fontSize: "var(--font-size-xs)", marginTop: "4px" }}>
                Can include formatted content
              </div>
            </div>
          } 
          position="right"
          maxWidth="200px"
        >
          <SaasButton variant="outline">Hover Right</SaasButton>
        </SaasTooltip>
        
        <SaasTooltip content="Delayed tooltip (500ms)" delay={500} position="bottom">
          <SaasButton variant="outline">Delayed</SaasButton>
        </SaasTooltip>
      </div>
    );
  },
};

// ProgressBar 组件示例
export const ProgressBarExample: StoryObj = {
  render: () => {
    const [progress, setProgress] = useState(65);
    
    return (
      <div style={{ width: "400px" }}>
        <SaasCard padding="lg">
          <h3 style={{ marginBottom: "var(--spacing-md)" }}>Upload Progress</h3>
          
          <div style={{ marginBottom: "var(--spacing-lg)" }}>
            <SaasProgressBar
              value={progress}
              variant="primary"
              size="lg"
              showLabel
              labelPosition="inside"
            />
          </div>
          
          <div style={{ marginBottom: "var(--spacing-lg)" }}>
            <SaasProgressBar
              value={85}
              variant="success"
              size="md"
              showLabel
              labelPosition="outside-top"
            />
          </div>
          
          <div style={{ marginBottom: "var(--spacing-lg)" }}>
            <SaasProgressBar
              value={45}
              variant="warning"
              size="sm"
              showLabel
              labelPosition="outside-bottom"
            />
          </div>
          
          <div style={{ marginBottom: "var(--spacing-lg)" }}>
            <SaasProgressBar
              indeterminate
              variant="info"
              size="md"
            />
          </div>
          
          <div style={{ display: "flex", gap: "var(--spacing-sm)" }}>
            <SaasButton size="sm" onClick={() => setProgress(Math.max(0, progress - 10))}>
              -10%
            </SaasButton>
            <SaasButton size="sm" onClick={() => setProgress(Math.min(100, progress + 10))}>
              +10%
            </SaasButton>
          </div>
        </SaasCard>
      </div>
    );
  },
};

// Toggle 组件示例
export const ToggleExample: StoryObj = {
  render: () => {
    const [checked1, setChecked1] = useState(true);
    const [checked2, setChecked2] = useState(false);
    const [checked3, setChecked3] = useState(true);
    
    return (
      <div style={{ width: "300px" }}>
        <SaasCard padding="lg">
          <h3 style={{ marginBottom: "var(--spacing-lg)" }}>Notification Settings</h3>
          
          <div style={{ 
            display: "flex", 
            flexDirection: "column",
            gap: "var(--spacing-lg)"
          }}>
            <SaasToggle
              checked={checked1}
              onChange={setChecked1}
              label="Email Notifications"
              description="Receive updates via email"
              size="md"
            />
            
            <SaasToggle
              checked={checked2}
              onChange={setChecked2}
              label="Push Notifications"
              description="Get real-time browser notifications"
              size="md"
            />
            
            <SaasToggle
              checked={checked3}
              onChange={setChecked3}
              label="SMS Alerts"
              description="Important alerts via SMS"
              size="md"
              disabled
            />
            
            <SaasToggle
              checked={false}
              onChange={() => {}}
              label="Loading State"
              description="Toggle is currently loading"
              size="md"
              loading
            />
          </div>
        </SaasCard>
      </div>
    );
  },
};

// DatePicker 组件示例
export const DatePickerExample: StoryObj = {
  render: () => {
    const [date, setDate] = useState<Date | null>(new Date());
    const minDate = new Date();
    minDate.setDate(minDate.getDate() - 7);
    const maxDate = new Date();
    maxDate.setDate(maxDate.getDate() + 30);
    
    return (
      <div style={{ width: "300px" }}>
        <SaasCard padding="lg">
          <h3 style={{ marginBottom: "var(--spacing-lg)" }}>Schedule Settings</h3>
          
          <div style={{ 
            display: "flex", 
            flexDirection: "column",
            gap: "var(--spacing-lg)"
          }}>
            <div>
              <label style={{ 
                display: "block", 
                marginBottom: "var(--spacing-xs)",
                fontSize: "var(--font-size-sm)",
                fontWeight: "var(--font-weight-medium)",
                color: "var(--color-text-secondary)"
              }}>
                Start Date
              </label>
              <SaasDatePicker
                value={date}
                onChange={setDate}
                placeholder="Select start date"
                size="md"
              />
            </div>
            
            <div>
              <label style={{ 
                display: "block", 
                marginBottom: "var(--spacing-xs)",
                fontSize: "var(--font-size-sm)",
                fontWeight: "var(--font-weight-medium)",
                color: "var(--color-text-secondary)"
              }}>
                End Date (with min/max)
              </label>
              <SaasDatePicker
                value={null}
                onChange={() => {}}
                placeholder="Select end date"
                minDate={minDate}
                maxDate={maxDate}
                size="md"
                clearable
              />
            </div>
            
            <div>
              <label style={{ 
                display: "block", 
                marginBottom: "var(--spacing-xs)",
                fontSize: "var(--font-size-sm)",
                fontWeight: "var(--font-weight-medium)",
                color: "var(--color-text-secondary)"
              }}>
                Disabled Date Picker
              </label>
              <SaasDatePicker
                value={null}
                onChange={() => {}}
                placeholder="Disabled field"
                disabled
                size="md"
              />
            </div>
            
            <div>
              <label style={{ 
                display: "block", 
                marginBottom: "var(--spacing-xs)",
                fontSize: "var(--font-size-sm)",
                fontWeight: "var(--font-weight-medium)",
                color: "var(--color-text-secondary)"
              }}>
                Date with Error
              </label>
              <SaasDatePicker
                value={null}
                onChange={() => {}}
                placeholder="Invalid date selected"
                error="Please select a valid date"
                size="md"
              />
            </div>
          </div>
        </SaasCard>
      </div>
    );
  },
};

// 组件组合示例
export const ComponentComposition: StoryObj = {
  render: () => {
    const [modalOpen, setModalOpen] = useState(false);
    const [progress, setProgress] = useState(75);
    const [notifications, setNotifications] = useState(true);
    const [darkMode, setDarkMode] = useState(false);
    const [selectedDate, setSelectedDate] = useState<Date | null>(new Date());
    
    return (
      <div style={{ maxWidth: "500px" }}>
        <SaasCard padding="lg">
          <div style={{ 
            display: "flex", 
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "var(--spacing-lg)"
          }}>
            <h2 style={{ margin: 0 }}>Project Settings</h2>
            
            <SaasTooltip content="Open advanced settings" position="bottom">
              <SaasButton variant="ghost" size="sm" onClick={() => setModalOpen(true)}>
                Advanced ⚙️
              </SaasButton>
            </SaasTooltip>
          </div>
          
          <div style={{ marginBottom: "var(--spacing-xl)" }}>
            <div style={{ 
              display: "flex", 
              justifyContent: "space-between",
              marginBottom: "var(--spacing-xs)"
            }}>
              <span style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-secondary)" }}>
                Storage Usage
              </span>
              <span style={{ fontSize: "var(--font-size-sm)", fontWeight: "var(--font-weight-medium)" }}>
                {progress}%
              </span>
            </div>
            <SaasProgressBar
              value={progress}
              variant={progress > 90 ? "danger" : progress > 75 ? "warning" : "primary"}
              size="md"
            />
          </div>
          
          <div style={{ 
            display: "flex", 
            flexDirection: "column",
            gap: "var(--spacing-lg)",
            marginBottom: "var(--spacing-xl)"
          }}>
            <SaasToggle
              checked={notifications}
              onChange={setNotifications}
              label="Project Notifications"
              description="Receive updates about this project"
              size="md"
            />
            
            <SaasToggle
              checked={darkMode}
              onChange={setDarkMode}
              label="Dark Mode"
              description="Use dark theme for this project"
              size="md"
            />
          </div>
          
          <div style={{ marginBottom: "var(--spacing-xl)" }}>
            <label style={{ 
              display: "block", 
              marginBottom: "var(--spacing-xs)",
              fontSize: "var(--font-size-sm)",
              fontWeight: "var(--font-weight-medium)",
              color: "var(--color-text-secondary)"
            }}>
              Deadline
            </label>
            <SaasDatePicker
              value={selectedDate}
              onChange={setSelectedDate}
              placeholder="Set project deadline"
              size="md"
              clearable
            />
          </div>
          
          <div style={{ 
            display: "flex", 
            gap: "var(--spacing-sm)",
            justifyContent: "flex-end"
          }}>
            <SaasButton variant="ghost">Cancel</SaasButton>
            <SaasButton variant="primary">Save Settings</SaasButton>
          </div>
        </SaasCard>
        
        <SaasModal
          isOpen={modalOpen}
          onClose={() => setModalOpen(false)}
          title="Advanced Settings"
          size="lg"
        >
          <div style={{ padding: "var(--spacing-md)" }}>
            <h3 style={{ marginBottom: "var(--spacing-md)" }}>Danger Zone</h3>
            <p style={{ color: "var(--color-text-secondary)", marginBottom: "var(--spacing-lg)" }}>
              These actions are irreversible. Please proceed with caution.
            </p>
            
            <div style={{ 
              padding: "var(--spacing-lg)",
              background: "var(--color-danger-light)",
              borderRadius: "var(--radius-md)",
              marginBottom: "var(--spacing-lg)"
            }}>
              <h4 style={{ color: "var(--color-danger)", marginBottom: "var(--spacing-sm)" }}>
                Delete Project
              </h4>
              <p style={{ color: "var(--color-text-secondary)", marginBottom: "var(--spacing-md)" }}>
                Once deleted, all project data will be permanently removed.
              </p>
              <SaasButton variant="danger">Delete Project</SaasButton>
            </div>
          </div>
        </SaasModal>
      </div>
    );
  },
};

// 辅助函数和状态管理
import { useState } from "react";