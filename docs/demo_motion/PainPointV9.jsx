import React from "react";
import { AbsoluteFill, useCurrentFrame, interpolate, spring } from "remotion";

// 镜头 1（V9）：痛点开场 ——逐位数字滚动 + 光效冲击
// 修掉 V7 的叠字bug：不再用两个绝对定位的数字叠在同一位置。
// 做法：拆成 3 个独立的数字槽（"" / "1" / "2" / "0"），
//      每个槽的字符随帧切换并各自做「上翻+淡出/下翻+淡入」，永远不会同时出现两个字符。
const F = 30;

// 字符序列：空 → 120（逐位从下方翻上来）
const SLOTS = [
  { chars: ["", "1"], idx: 0 },
  { chars: ["", "2"], idx: 1 },
  { chars: ["", "0"], idx: 2 },
];

const ROLL_START = 3.0; // 秒
const ROLL_STAGGER = 0.13; // 每位间隔

export default function PainPointV9() {
  const frame = useCurrentFrame();
  const t = frame / F;

  const badge = spring({ frame, config: { damping: 200 }, durationInFrames: 16 });
  const headIn = spring({ frame: frame - 14, config: { damping: 200 }, durationInFrames: 20 });
  const kicker = spring({ frame: frame - 52, config: { damping: 200 }, durationInFrames: 20 });

  // 冲击波：最后一位落定后触发
  const shockStart = ROLL_START + ROLL_STAGGER * 2 + 0.22;
  const shock = interpolate(t, [shockStart, shockStart + 0.5], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const shockActive = t >= shockStart;
  const ringScale = interpolate(shock, [0, 1], [0.2, 2.6]);
  const ringOpacity = interpolate(shock, [0, 0.7, 1], [0.55, 0.12, 0]);
  const glowScale = interpolate(shock, [0, 0.35, 1], [1.5, 1.14, 1]);

  return (
    <AbsoluteFill style={{ background: "#080d18", fontFamily: '"PingFang SC","Hiragino Sans GB",sans-serif', color: "#fff", padding: "90px 110px", display: "flex", flexDirection: "column", justifyContent: "center" }}>
      {/* 底光 */}
      <div style={{ position: "absolute", top: -300, left: "50%", transform: "translateX(-50%)", width: 1300, height: 760, background: "radial-gradient(circle, rgba(255,170,40,0.18) 0%, transparent 66%)", filter: "blur(44px)" }} />

      {/* 徽标 */}
      <div style={{ position: "absolute", top: 86, left: 110, display: "inline-flex", alignItems: "center", gap: 13, padding: "11px 24px", borderRadius: 999, background: "rgba(255,107,107,0.13)", border: "1px solid rgba(255,107,107,0.34)", fontSize: 26, color: "#ff9b9b", opacity: badge }}>
        <div style={{ width: 10, height: 10, borderRadius: 5, background: "#ff6b6b", boxShadow: "0 0 12px #ff6b6b" }} />
        某券商研究部 · 真实工作场景
      </div>

      {/* 数字区 */}
      <div style={{ position: "relative", marginTop: 46, height: 250, transform: `scale(${glowScale})`, transformOrigin: "left bottom" }}>
        {/* 冲击波圆环 */}
        {shockActive && (
          <div
            style={{
              position: "absolute",
              left: 30,
              top: 250,
              width: 340,
              height: 340,
              marginLeft: -170,
              marginTop: -170,
              borderRadius: 170,
              border: "3px solid rgba(255,212,59,0.85)",
              transform: `scale(${ringScale})`,
              opacity: ringOpacity,
            }}
          />
        )}

        {/* 三个数字槽 —— 每个槽只渲染一个字符 */}
        <div style={{ position: "absolute", left: 0, bottom: 0, display: "flex", alignItems: "flex-end" }}>
          {SLOTS.map((slot, si) => {
            const slotStart = ROLL_START + ROLL_STAGGER * si;
            const st = spring({
              frame: frame - slotStart * F,
              config: { damping: 18, stiffness: 190 },
              durationInFrames: 15,
            });
            // 字符切换：st<0.5 显示空，>=0.5 显示目标字符
            const showChar = st >= 0.45;
            const inP = interpolate(st, [0.45, 1], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            const outP = interpolate(st, [0, 0.45], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

            return (
              <div key={si} style={{ width: si === 0 ? 152 : 150, position: "relative", height: 238 }}>
                {/* 旧字符（空→ 实际是旋转的空白，用一个短横线示意滚动） */}
                <div
                  style={{
                    position: "absolute",
                    left: 0,
                    bottom: 0,
                    clipPath: `inset(${interpolate(outP, [0, 1], [86, 0])}% 0 0 0)`,
                    transform: `translateY(${interpolate(outP, [0, 1], [-120, 0])}px)`,
                    opacity: outP * 0.55,
                  }}
                >
                  <span style={{ fontSize: 258, fontWeight: 800, lineHeight: 0.9, color: "rgba(255,255,255,0.07)" }}>
                    8
                  </span>
                </div>
                {/* 新字符 */}
                {showChar && (
                  <div
                    style={{
                      position: "absolute",
                      left: 0,
                      bottom: 0,
                      clipPath: `inset(${interpolate(inP, [0, 1], [100, 0])}% 0 0 0)`,
                      transform: `translateY(${interpolate(inP, [0, 1], [40, 0])}px)`,
                      opacity: inP,
                    }}
                  >
                    <span
                      style={{
                        fontSize: 258,
                        fontWeight: 800,
                        lineHeight: 0.9,
                        background: "linear-gradient(180deg,#ffe066 0%,#ffa94d 99.9%)",
                        WebkitBackgroundClip: "text",
                        WebkitTextFillColor: "transparent",
                        filter: "drop-shadow(0 0 40px rgba(255,180,60,0.45))",
                      }}
                    >
                      {slot.chars[1]}
                    </span>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* 单位 */}
        <div style={{ position: "absolute", left: 468, bottom: 18, display: "flex", flexDirection: "column", gap: 8, opacity: interpolate(t, [ROLL_START, ROLL_START + 0.5], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }}>
          <span style={{ fontSize: 62, fontWeight: 800, color: "#fff", lineHeight: 1 }}>分钟</span>
          <span style={{ fontSize: 30, color: "#8b9bb4" }}>每人 · 每天</span>
        </div>
      </div>

      {/* 痛点一句话 */}
      <div style={{ marginTop: 46, display: "flex", alignItems: "center", gap: 20, opacity: kicker, transform: `translateX(${interpolate(kicker, [0, 1], [-30, 0])}px)` }}>
        <div style={{ width: 6, height: 62, borderRadius: 3, background: "#ff6b6b" }} />
        <div style={{ fontSize: 46, fontWeight: 700, lineHeight: 1.3 }}>
          八位研究员，
          <br />
          <span style={{ color: "#ff8787" }}>在三个网站之间来回复制粘贴</span>
        </div>
      </div>

      {/* 底部标签 */}
      <div style={{ position: "absolute", bottom: 230, display: "flex", gap: 16, opacity: kicker }}>
        {["口径不统一", "要点易遗漏", "无法审计"].map((x, i) => (
          <div key={i} style={{ padding: "12px 24px", borderRadius: 10, background: "rgba(255,255,255,0.055)", border: "1px solid rgba(255,255,255,0.12)", fontSize: 25, color: "#94a3b8" }}>{x}</div>
        ))}
      </div>
    </AbsoluteFill>
  );
}