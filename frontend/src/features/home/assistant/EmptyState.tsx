import { useEffect, useState } from "react";
import { BookOpen, Code2, MessageSquare, PenLine, Smile, Sparkles } from "lucide-react";

import { cn } from "@/lib/utils";

// 四类引导，每类 10 条；每次进入空对话随机各取一条，凑成四张便签。
// 约束：每条都是「与 AI 的第一句话」，必须独立成立、不依赖任何上文。
const CATEGORIES = [
  {
    key: "write",
    icon: PenLine,
    tilt: "-rotate-1",
    prompts: [
      "帮我写一段关于春天傍晚的散文",
      "以「如果时间可以倒流」为题写个故事开头",
      "写一首关于深夜加班的现代短诗",
      "帮我写一段温暖的睡前寄语",
      "给一篇旅行游记起十个有诗意的标题",
      "帮我构思一个科幻短篇的核心设定",
      "写一段适合下雨天发朋友圈的文案",
      "给我三个适合写进日记的随笔主题",
      "帮我写一封给十年后自己的信",
      "用拟人的手法写一段关于老猫的描写",
    ],
  },
  {
    key: "read",
    icon: BookOpen,
    tilt: "rotate-1",
    prompts: [
      "推荐几本适合周末一口气读完的书",
      "有哪些值得一看的硬核科幻小说",
      "推荐一些治愈系的散文集",
      "给我列一个哲学入门书单",
      "最近有什么口碑不错的悬疑推理小说",
      "推荐几本讲编程思维的经典书",
      "有没有适合睡前读的短篇小说集",
      "推荐三本能改变思维方式的书",
      "介绍几位值得一读的当代作家",
      "推荐一些通俗易懂的历史读物",
    ],
  },
  {
    key: "code",
    icon: Code2,
    tilt: "-rotate-1",
    prompts: [
      "帮我写一个图片轮播图的源码",
      "用 JavaScript 实现一个防抖函数",
      "讲讲虚拟滚动是怎么实现的",
      "帮我写一个快速排序并解释思路",
      "用 React 写一个倒计时的自定义 Hook",
      "实现一个 LRU 缓存并说明原理",
      "写一段 CSS 实现毛玻璃效果",
      "用 Python 写一个简单的网页爬虫示例",
      "实现一个深拷贝函数要考虑哪些情况",
      "讲讲 Promise.all 和 allSettled 的区别",
    ],
  },
  {
    key: "mood",
    icon: Smile,
    tilt: "rotate-1",
    prompts: [
      "给我讲个冷笑话吧",
      "分享一个有趣的冷知识",
      "推荐一首适合深夜听的歌",
      "给我一句今天的鼓励",
      "讲个温暖的小故事吧",
      "如果能拥有一种超能力，你会选什么",
      "陪我聊聊怎么对抗拖延症",
      "给我推荐一部适合周末看的电影",
      "说说有什么简单好用的解压方法",
      "随便跟我分享一个生活小妙招",
    ],
  },
] as const;

/** 首页助手空态：便签图标 + 标题 + 四类随机引导卡片（点击即以该提示发起对话）。 */
export function EmptyState({ onAsk }: { onAsk: (q: string) => void }) {
  // 默认各取第一条以稳定首帧；挂载后（含每次「新对话」重新挂载）再随机各取一条。
  const [picks, setPicks] = useState<number[]>(() => CATEGORIES.map(() => 0));
  useEffect(() => {
    setPicks(CATEGORIES.map((c) => Math.floor(Math.random() * c.prompts.length)));
  }, []);

  return (
    <div className="flex h-full flex-col items-center justify-center gap-7 px-6 text-center">
      <div className="flex size-16 -rotate-6 items-center justify-center rounded-2xl border border-border/60 bg-card shadow-md">
        <span className="relative">
          <MessageSquare className="h-7 w-7 text-primary/80" strokeWidth={1.6} />
          <Sparkles
            className="absolute -right-1.5 -top-1.5 h-3.5 w-3.5 text-primary"
            strokeWidth={2}
          />
        </span>
      </div>

      <div className="space-y-1.5">
        <p className="text-lg font-semibold text-foreground/90">今天想聊点什么？</p>
        <p className="text-sm text-muted-foreground">
          写作灵感、读书笔记、代码问题，或者只是随便聊两句。
        </p>
      </div>

      <div className="grid w-full max-w-md grid-cols-2 gap-3 sm:max-w-xl sm:grid-cols-4">
        {CATEGORIES.map((cat, i) => {
          const Icon = cat.icon;
          const prompt = cat.prompts[picks[i]] ?? cat.prompts[0];
          return (
            <button
              key={cat.key}
              type="button"
              data-testid="starter-prompt"
              onClick={() => onAsk(prompt)}
              className={cn(
                "group flex flex-col gap-2.5 rounded-xl border border-border/60 bg-card p-3 text-left shadow-sm transition-all",
                cat.tilt,
                "hover:-translate-y-1 hover:rotate-0 hover:border-primary/40 hover:shadow-md",
              )}
            >
              <span className="flex size-7 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <Icon className="h-4 w-4" strokeWidth={1.8} />
              </span>
              <span className="text-[13px] leading-snug text-foreground/80 group-hover:text-foreground">
                {prompt}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
