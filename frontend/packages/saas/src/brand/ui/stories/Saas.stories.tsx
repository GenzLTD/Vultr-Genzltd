/**
 * SaaS UI Components — Storybook Stories (CSF format).
 * Run: cd frontend && pnpm storybook (see STORYBOOK.md)
 */
import type { Meta, StoryObj } from "@storybook/react";
import {
  SaasButton,
  SaasInput,
  SaasSelect,
  SaasTextArea,
  SaasCard,
  SaasSidebar,
  SaasHeader,
  SaasKPICard,
  SaasDataTable,
  SaasChatBubble,
  SaasStreamingText,
  SaasResumeUploader,
  SaasLoading,
  SaasSkeleton,
  SaasEmptyState,
  SaasErrorState,
} from "../index";

// ============================================================
// Button
// ============================================================
const meta: Meta<typeof SaasButton> = {
  title: "SaaS/Button",
  component: SaasButton,
  tags: ["autodocs"],
};
export default meta;
type Story = StoryObj<typeof SaasButton>;

export const Primary: Story = { args: { variant: "primary", children: "确认" } };
export const Secondary: Story = { args: { variant: "secondary", children: "取消" } };
export const Outline: Story = { args: { variant: "outline", children: "描边" } };
export const Danger: Story = { args: { variant: "danger", children: "删除" } };
export const Loading: Story = { args: { loading: true, children: "提交中" } };

// ============================================================
// Input / Select / TextArea
// ============================================================
export const InputDefault: StoryObj<typeof SaasInput> = {
  args: { label: "邮箱", placeholder: "请输入邮箱", value: "" },
};
export const SelectDefault: StoryObj<typeof SaasSelect> = {
  args: {
    label: "职位",
    value: "",
    options: [
      { value: "fe", label: "前端工程师" },
      { value: "be", label: "后端工程师" },
      { value: "fs", label: "全栈工程师" },
    ],
  },
};

// ============================================================
// Card
// ============================================================
export const Card: StoryObj<typeof SaasCard> = {
  render: () => <SaasCard hoverable>Card 内容</SaasCard>,
};

// ============================================================
// KPICard
// ============================================================
export const KPI: StoryObj<typeof SaasKPICard> = {
  args: {
    label: "本月新增候选人",
    value: "1,248",
    trend: "up",
    trendValue: "12.5%",
    sparklineData: [30, 45, 38, 52, 48, 65, 70, 85],
  },
};

// ============================================================
// DataTable
// ============================================================
export const Table: StoryObj<typeof SaasDataTable> = {
  render: () => (
    <SaasDataTable
      columns={[
        { key: "name", title: "姓名" },
        { key: "role", title: "职位" },
        { key: "status", title: "状态" },
      ]}
      data={[
        { id: "1", name: "张三", role: "前端", status: "在职" },
        { id: "2", name: "李四", role: "后端", status: "待入职" },
      ]}
    />
  ),
};

// ============================================================
// ChatBubble
// ============================================================
export const ChatUser: StoryObj<typeof SaasChatBubble> = {
  args: { role: "user", content: "你好，帮我分析一下这份简历" },
};
export const ChatAI: StoryObj<typeof SaasChatBubble> = {
  args: { role: "ai", content: "好的，请上传简历文件，我会为您进行详细分析。" },
};

// ============================================================
// StreamingText
// ============================================================
export const Streaming: StoryObj<typeof SaasStreamingText> = {
  args: { text: "正在分析候选人技能匹配度...", done: false },
};

// ============================================================
// ResumeUploader
// ============================================================
export const UploaderIdle: StoryObj<typeof SaasResumeUploader> = {
  args: { state: "idle" },
};
export const UploaderUploading: StoryObj<typeof SaasResumeUploader> = {
  args: { state: "uploading", fileName: "resume.pdf", fileSize: "2.3MB", progress: 60 },
};
export const UploaderSuccess: StoryObj<typeof SaasResumeUploader> = {
  args: { state: "success", fileName: "resume.pdf", fileSize: "2.3MB" },
};

// ============================================================
// Empty / Error
// ============================================================
export const EmptyState: StoryObj<typeof SaasEmptyState> = {
  args: { title: "暂无候选人", description: "上传简历后将自动解析并添加候选人" },
};
export const ErrorState: StoryObj<typeof SaasErrorState> = {
  args: { message: "网络连接失败，请检查网络后重试" },
};

// ============================================================
// Loading / Skeleton
// ============================================================
export const LoadingDefault: StoryObj<typeof SaasLoading> = {
  args: { text: "加载中..." },
};
export const Skeleton: StoryObj<typeof SaasSkeleton> = {
  render: () => <SaasSkeleton height={20} count={3} />,
};
