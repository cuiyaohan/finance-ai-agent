import React from "react";
import { AbsoluteFill, useCurrentFrame, interpolate, spring } from "remotion";

// 镜头 2：网页演示（加长版，约 9 秒）
// 阶段：待机 → 点击 → 4 步进度逐条完成 → 结果卡片逐条浮出 → 合规条
const F = 30;

const ITEMS = [
  { tag: "利好", color: "#ff6b6b", bg: "rgba(255,107,107,0.14)", title: "长飞先进总裁：碳化硅市场短期看汽车、长期看 AI", src: "中新网·财经", time: "14:52" },
  { tag: "利好", color: "#ff6b6b", bg: "rgba(255,107,107,0.14)", title: "5 艘 LNG 船订单落地，中船集团沪东中华锁定舱容量全球榜首", src: "中新网·财经", time: "15:07" },
  { tag: "中性", color: "#a78bfa", bg: "rgba(167,139,250,0.14)", title: "深圳举办企业竞争合规大讲堂，助力互联网平台合规发展", src: "中新网·财经", time: "15:11" },
  { tag: "中性", color: "#a78bfa", bg: "rgba(167,139,250,0.14)", title: "湛江综合保税区首票出口集拼业务落地", src: "中新网·财经", time: "15:20" },
];

const STEPS = [
  "连接 3 个公开信源",
  "过滤近 7 日 · 自动去重",
  "模型摘要与利好 / 中性打标",
  "高危词扫描 · 附加免责声明",
];

// 时间轴（秒）
const T_CLICK = 1.4;
const T_STEP_END = 6.4;
const T_SHOW = 6.9;

export default function WebSimV2() {
  const frame = useCurrentFrame();
  const t = frame / F;

  const clicked = t >= T_CLICK;
  const done = t >= T_SHOW;
  const prog = t < T_CLICK ? 0 : interpolate(t, [T_CLICK + 0.2, T_STEP_END], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const activeStep = Math.min(STEPS.length - 1, Math.floor(prog * STEPS.length));

  const knob = t < T_CLICK ? 0 : t < T_STEP_END ? 1 : 0;
  const spin = t * 640;

  return (
    <AbsoluteFill style={{ background: "#070c16", fontFamily: '"PingFang SC","Hiragino Sans GB",sans-serif', color: "#fff", padding: 42 }}>
      {/* 背景光 */}
      <div
        style={{
          position: "absolute",
          top: -220,
          right: -140,
          width: 900,
          height: 620,
          background: "radial-gradient(circle, rgba(59,130,246,0.16) 0%, transparent 68%)",
          filter: "blur(34px)",
        }}
      />

      <div
        style={{
          position: "relative",
          flex: 1,
          borderRadius: 18,
          overflow: "hidden",
          border: "1px solid rgba(255,255,255,0.14)",
          background: "linear-gradient(180deg,#101a2e 0%,#0c1424 99.9%)",
          display: "flex",
          flexDirection: "column",
          boxShadow: "0 28px 90px rgba(0,0,0,0.55)",
        }}
      >
        {/* 标题栏 */}
        <div style={{ height: 62, background: "rgba(255,255,255,0.045)", display: "flex", alignItems: "center", padding: "0 24px", gap: 10, flexShrink: 0, borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
          {["#ff5f57", "#febc2e", "#28c840"].map((c, i) => (
            <div key={i} style={{ width: 13, height: 13, borderRadius: 7, background: c }} />
          ))}
          <div style={{ marginLeft: 22, flex: 1, height: 32, borderRadius: 9, background: "rgba(0,0,0,0.35)", display: "flex", alignItems: "center", padding: "0 16px", fontSize: 17, color: "#7c8aa3" }}>
            投研情报 Agent · 今日简报
          </div>
          <div style={{ fontSize: 16, color: "#4f6076" }}>私有化部署</div>
        </div>

        <div style={{ flex: 1, padding: "40px 56px", display: "flex", flexDirection: "column" }}>
          {!done ? (
            <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
              {/* 按钮 */}
              <div
                style={{
                  opacity: knob ? 0.42 : 1,
                  padding: "24px 56px",
                  borderRadius: 15,
                  background: knob ? "#2b3a52" : "linear-gradient(135deg,#4f8ef7,#2563eb)",
                  fontSize: 32,
                  fontWeight: 700,
                  boxShadow: knob ? "none" : "0 16px 46px rgba(59,130,246,0.45)",
                  display: "flex",
                  alignItems: "center",
                  gap: 15,
                }}
              >
                {knob ? (
                  <div style={{ width: 25, height: 25, borderRadius: 13, border: "3px solid rgba(255,255,255,0.3)", borderTopColor: "#fff", transform: `rotate(${spin}deg)` }} />
                ) : (
                  <span style={{ fontSize: 29 }}>⚡</span>
                )}
                {knob ? "生成中…" : "生成今日简报"}
              </div>

              {!clicked && (
                <div style={{ marginTop: 40, fontSize: 24, color: "#64748b" }}>
                  ↑ 单击即可 · 无需任何命令行
                </div>
              )}

              {/* 进度步骤 */}
              <div style={{ marginTop: 44, width: 640 }}>
                {STEPS.map((s, i) => {
                  const on = i <= activeStep;
                  const st = spring({ frame: frame - (T_CLICK * F + 12 + i * 30), config: { damping: 200 }, durationInFrames: 16 });
                  if (st <= 0.02 && i > activeStep) return null;
                  return (
                    <div
                      key={i}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 15,
                        marginTop: i === 0 ? 0 : 19,
                        opacity: on ? 1 : 0.32,
                        transform: `translateX(${interpolate(st, [0, 1], [-18, 0])}px)`,
                      }}
                    >
                      <div
                        style={{
                          width: 26,
                          height: 26,
                          borderRadius: 13,
                          background: on ? "#22c55e" : "rgba(255,255,255,0.09)",
                          boxShadow: on ? "0 0 16px rgba(34,197,94,0.55)" : "none",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          fontSize: 15,
                          fontWeight: 800,
                          color: "#fff",
                        }}
                      >
                        {on ? "✓" : ""}
                      </div>
                      <span style={{ fontSize: 26, color: on ? "#e8eef7" : "#64748b" }}>{s}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <div>
              {/* 结果标题 */}
              <div style={{ display: "flex", alignItems: "baseline", gap: 16 }}>
                <span style={{ fontSize: 40, fontWeight: 800 }}>今日简报</span>
                <span style={{ fontSize: 21, color: "#64748b" }}>
                  3 个信源 · 4 条资讯 · 12 秒生成
                </span>
              </div>
              <div style={{ height: 3, background: "rgba(255,255,255,0.1)", borderRadius: 2, margin: "16px 0 26px" }} />

              {ITEMS.map((it, i) => {
                const st = spring({ frame: frame - T_SHOW * F - 6 - i * 8, config: { damping: 200 }, durationInFrames: 20 });
                return (
                  <div
                    key={i}
                    style={{
                      display: "flex",
                      gap: 17,
                      alignItems: "flex-start",
                      padding: "16px 22px",
                      marginBottom: 13,
                      borderRadius: 13,
                      background: "rgba(255,255,255,0.05)",
                      border: "1px solid rgba(255,255,255,0.09)",
                      borderLeft: `4px solid ${it.color}`,
                      opacity: st,
                      transform: `translateY(${interpolate(st, [0, 1], [30, 0])}px)`,
                    }}
                  >
                    <span style={{ fontSize: 18, fontWeight: 700, color: it.color, background: it.bg, padding: "5px 14px", borderRadius: 8, flexShrink: 0, marginTop: 2 }}>
                      {it.tag}
                    </span>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 26, fontWeight: 600, lineHeight: 1.38 }}>{it.title}</div>
                      <div style={{ fontSize: 17, color: "#64748b", marginTop: 8 }}>
                        来源：{it.src} · {it.time}
                      </div>
                    </div>
                    <div style={{ fontSize: 17, color: "#4f6076", marginTop: 6 }}>原文链接 ↗</div>
                  </div>
                );
              })}

              <div
                style={{
                  marginTop: 20,
                  padding: "14px 22px",
                  borderRadius: 11,
                  background: "rgba(34,197,94,0.1)",
                  border: "1px solid rgba(34,197,94,0.28)",
                  fontSize: 20,
                  color: "#86efac",
                }}
              >
                ✓ 高危词扫描 0 命中 · 已自动附加免责声明 · 全链路留痕可审计
              </div>
            </div>
          )}
        </div>
      </div>
    </AbsoluteFill>
  );
}