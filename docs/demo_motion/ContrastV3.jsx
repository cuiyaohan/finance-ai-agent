import React from "react";
import { AbsoluteFill, useCurrentFrame, interpolate, spring } from "remotion";

// 镜头 4（重设计）：前后对比 —— 修复重叠 bug + 单一焦点
// 原 bug：改造前/后用 marginTop:-196 让两块重叠，但透明度不同步导致文字叠在一起。
// 修复：改为上下排列（不是叠加），各自独立动画，永不重叠。
const F = 30;

export default function ContrastV3() {
  const frame = useCurrentFrame();
  const t = frame / F;

  const oldIn = spring({ frame, config: { damping: 200 }, durationInFrames: 16 });

  // 1.4s 后「改造前」缩小淡出
  const swapAt = 1.4;
  const swap = spring({ frame: frame - swapAt * F, config: { damping: 200 }, durationInFrames: 18 });
  const oldOpacity = interpolate(swap, [0, 1], [1, 0]);
  const oldScale = interpolate(swap, [0, 1], [1, 0.88]);

  const newIn = spring({ frame: frame - swapAt * F - 8, config: { damping: 200 }, durationInFrames: 20 });
  const tagsIn = spring({ frame: frame - swapAt * F - 40, config: { damping: 200 }, durationInFrames: 20 });

  const CAPS = [
    { t: "代码开源可审阅", c: "#4f8ef7" },
    { t: "支持私有化部署", c: "#38bdf8" },
    { t: "数据源与模板可换", c: "#a78bfa" },
    { t: "交付含部署与培训", c: "#4ade80" },
  ];

  return (
    <AbsoluteFill style={{ background: "radial-gradient(1300px 780px at 50% 34%, #16243c 0%, #080d18 72%)", fontFamily: '"PingFang SC","Hiragino Sans GB",sans-serif', color: "#fff", padding: "70px 96px", display: "flex", flexDirection: "column" }}>
      {/* 标题 */}
      <div style={{ fontSize: 23, color: "#4f8ef7", fontWeight: 700, letterSpacing: 3.4, marginBottom: 10 }}>RESULT</div>
      <div style={{ fontSize: 46, fontWeight: 800, letterSpacing: -0.5, opacity: oldIn }}>同样的工作量，两种做法</div>

      {/* 上半：改造前（会缩小淡出） */}
      <div style={{ marginTop: 46, opacity: oldOpacity, transform: `scale(${oldScale})`, transformOrigin: "center center" }}>
        <div style={{ padding: "24px 40px", borderRadius: 18, background: "rgba(255,255,255,0.045)", border: "1px solid rgba(255,255,255,0.11)", display: "flex", alignItems: "center", gap: 30 }}>
          <div style={{ width: 5, height: 84, borderRadius: 3, background: "#ff8787" }} />
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 25, color: "#7c8aa3", marginBottom: 8 }}>改造前 · 手工汇总</div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
              <span style={{ fontSize: 78, fontWeight: 800, color: "#ff8787", lineHeight: 1 }}>2</span>
              <span style={{ fontSize: 30, color: "#7c8aa3" }}>小时 / 天</span>
            </div>
          </div>
          <div style={{ fontSize: 84, color: "#334155" }}>×</div>
        </div>
      </div>

      {/* 下半：改造后（从下方升起，始终独立不与上面重叠） */}
      <div style={{ marginTop: 26, opacity: newIn, transform: `translateY(${interpolate(newIn, [0, 1], [56, 0])}px)` }}>
        <div style={{ padding: "30px 40px", borderRadius: 20, background: "linear-gradient(160deg, rgba(74,222,128,0.16), rgba(59,130,246,0.12))", border: "2px solid rgba(74,222,128,0.48)", boxShadow: "0 26px 70px rgba(74,222,128,0.18)", display: "flex", alignItems: "center", gap: 30 }}>
          <div style={{ width: 6, height: 100, borderRadius: 3, background: "#4ade80", boxShadow: "0 0 20px #4ade80" }} />
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 26, color: "#86efac", marginBottom: 10 }}>改造后 · 自动流水线</div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 14 }}>
              <span style={{ fontSize: 104, fontWeight: 800, color: "#4ade80", lineHeight: 1 }}>3</span>
              <span style={{ fontSize: 34, color: "#86efac" }}>分钟 / 天</span>
            </div>
          </div>
          <div style={{ padding: "16px 28px", borderRadius: 14, background: "rgba(74,222,128,0.14)", border: "1px solid rgba(74,222,128,0.36)", fontSize: 30, fontWeight: 800, color: "#86efac" }}>↓ 节省 97%</div>
        </div>
      </div>

      {/* 收益条 */}
      <div style={{ marginTop: 32, alignSelf: "center", padding: "14px 32px", borderRadius: 999, background: "rgba(74,222,128,0.1)", border: "1px solid rgba(74,222,128,0.3)", fontSize: 26, color: "#86efac", opacity: newIn }}>
        8 名分析师 · 每日 8:30 前自动出具 · 口径统一
      </div>

      {/* 交付能力 */}
      <div style={{ marginTop: 46, display: "flex", gap: 15, justifyContent: "center", opacity: tagsIn }}>
        {CAPS.map((c, i) => (
          <div key={i} style={{ padding: "12px 24px", borderRadius: 10, background: "rgba(255,255,255,0.055)", border: `1px solid ${c.c}3a`, fontSize: 22, color: c.c, opacity: interpolate(tagsIn, [0, 1], [0.25, 1]) * (1 - i * 0.05) }}>
            ✓ {c.t}
          </div>
        ))}
      </div>

      {/* 免责 */}
      <div style={{ marginTop: 24, textAlign: "center", fontSize: 20, color: "#5b6b82", lineHeight: 1.5, opacity: tagsIn }}>
        本工具仅用于信息整理与效率提升，不构成投资建议，仅供参考
      </div>
    </AbsoluteFill>
  );
}