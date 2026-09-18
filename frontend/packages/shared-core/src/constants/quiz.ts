import type { QuizQuestion } from "../types/planetx-game";

/** PlanetX 8-题人格测评题库（单真源 · S0-3） */
export const QUIZ_QUESTIONS: QuizQuestion[] = [
  {
    q: "周末的下午，你最想做什么？",
    options: [
      { text: "约朋友去新开的咖啡店打卡", trait: "social" },
      { text: "一个人在家看剧/打游戏", trait: "introvert" },
      { text: "去报名学一个新技能", trait: "growth" },
      { text: "随便逛逛，走到哪算哪", trait: "wanderer" },
    ],
  },
  {
    q: "面对一个全新的任务，你的第一反应是？",
    options: [
      { text: "先做个计划再开始", trait: "planner" },
      { text: "直接上手，边做边调整", trait: "action" },
      { text: "先问问做过的人的经验", trait: "social" },
      { text: "先想清楚这个任务值不值得做", trait: "thinker" },
    ],
  },
  {
    q: "工作中让你最不爽的是什么？",
    options: [
      { text: "重复无聊的任务", trait: "creative" },
      { text: "不被理解/不被认可", trait: "social" },
      { text: "没有成长空间", trait: "growth" },
      { text: "996没自己的生活", trait: "balance" },
    ],
  },
  {
    q: "如果加入一个团队项目，你希望扮演什么角色？",
    options: [
      { text: "出主意的那个人", trait: "creative" },
      { text: "把大家组织起来的人", trait: "leader" },
      { text: "把细节做完美的人", trait: "perfectionist" },
      { text: "谁需要帮忙就去帮谁", trait: "supporter" },
    ],
  },
  {
    q: "朋友心情不好找你倾诉，你通常会？",
    options: [
      { text: "认真听完，给具体建议", trait: "thinker" },
      { text: "一起吐槽，情绪共鸣最重要", trait: "social" },
      { text: "拉TA出去散心转换心情", trait: "action" },
      { text: "分享一首诗或一首歌", trait: "creative" },
    ],
  },
  {
    q: "看到朋友圈都在刷某个热点，你会？",
    options: [
      { text: "马上加入讨论", trait: "social" },
      { text: "先自己查资料搞清楚再发言", trait: "thinker" },
      { text: "有点烦，划过去不看", trait: "introvert" },
      { text: "做成一个梗图发出去", trait: "creative" },
    ],
  },
  {
    q: '最近一次让你感到"我太牛了"是因为？',
    options: [
      { text: "解决了一个棘手的技术问题", trait: "thinker" },
      { text: "帮一个朋友度过了难关", trait: "supporter" },
      { text: "完成了一件拖延很久的事", trait: "action" },
      { text: "创造了一个让自己满意的作品", trait: "creative" },
    ],
  },
  {
    q: '你对"内卷"的态度是？',
    options: [
      { text: "不卷不行，但想卷得聪明一点", trait: "planner" },
      { text: "找到自己的节奏，不跟别人比", trait: "balance" },
      { text: "换条赛道，不挤同一个独木桥", trait: "creative" },
      { text: "找到志同道合的人一起对抗", trait: "social" },
    ],
  },
];
