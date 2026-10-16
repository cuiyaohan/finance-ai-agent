import React from "react";
import { AbsoluteFill, useCurrentFrame, interpolate, spring } from "remotion";

// 镜头 3（新增）：四节点流水线
// 让观众看懂「自动化到底是怎么跑的」——这是技术客户最关心的一层
const F = 30;

const NODES = [
  { k: "01", t: "抓取", d: "3 个公开信源", c: "#4f8ef7" },
  { k: "02", t: "清洗", d: "近 7 日过滤 · 去重", c: "#38bdf8" },
  { k: "03", t: "摘要", d: "模型打标 + 行文", c: "#a78bfa" },
  { k: "04", t: "落盘", d: "简报 + trace 留痕", c: "#4ade80" },
];

export default function Pipeline() {
  const frame = useCurrentFrame();
  const t = frame / F;

  const head = spring({ frame, config: { damping: 200 }, durationInFrames: 18 });

  return (
    <AbsoluteFill
      style={{
        background: "linear-gradient(150deg,#080d18 0%,#0f1b2e 52%,#080d18 99.9%)",
        fontFamily: '"PingFang SC","Hiragino Sans GB",sans-serif',
        color: "#fff",
        padding: "78px 100px",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
      }}
    >
      <div style={{ opacity: head, transform: `translateY(${interpolate(head, [0, 1], [20, 0])}px)` }}>
        <div
          style={{
            fontSize: 23,
            color: "#4f8ef7",
            fontWeight: 700,
            letterSpacing: 3,
            marginBottom: 14,
          }}
        >
          HOW IT WORKS
        </div>
        <div style={{ fontSize: 54, fontWeight: 800, letterSpacing: -1 }}>
          一条自动化流水线，四步完成
        </div>
        <div style={{ fontSize: 25, color: "#7c8aa3", marginTop: 14 }}>
          抓取与计算全部由确定性代码完成，模型只负责摘要与行文
        </div>
      </div>

      {/* 四节点 */}
      <div style={{ display: "flex", alignItems: "stretch", marginTop: 92, position: "relative" }}>
        {/* 连接线 */}
        <div
          style={{
            position: "absolute",
            top: 62,
            left: "12%",
            right: "12%",
            height: 3,
            background: "linear-gradient(90deg,#4f8ef7,#38bdf8,#a78bfa,#4ade80)",
            opacity: 0.42,
          }}
        />
        {NODES.map((n, i) => {
          const st = spring({
            frame: frame - 16 - i * 13,
            config: { damping: 200 },
            durationInFrames: 22,
          });
          return (
            <div
              key={i}
              style={{
                flex: 1,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                opacity: st,
                transform: `translateY(${interpolate(st, [0, 1], [34, 0])}px)`,
              }}
            >
              {/* 圆点 */}
              <div
                style={{
                  width: 86,
                  height: 86,
                  borderRadius: 43,
                  background: `radial-gradient(circle at 32% 28%, ${n.c} 0%, ${n.c} 45%, rgba(0,0,0,0.5) 130%)`,
                  border: `3px solid ${n.c}`,
                  boxShadow: `0 0 40px ${n.c}66`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 27,
                  fontWeight: 800,
                  color: "#fff",
                }}
              >
                {n.k}
              </div>
              {/* 文字 */}
              <div style={{ marginTop: 24, fontSize: 34, fontWeight: 700 }}>{n.t}</div>
              <div style={{ marginTop: 11, fontSize: 21, color: "#7c8aa3", textAlign: "center", lineHeight: 1.5 }}>
                {n.d}
              </div>
            </div>
          );
        })}
      </div>

      {/* 底部说明 */}
      <div
        style={{
          marginTop: 104,
          display: "flex",
          gap: 18,
          justifyContent: "center",
        }}
      >
        {[
          { t: "数字由程序计算", c: "#38bdf8" },
          { t: "模型不参与金额运算", c: "#a78bfa" },
          { t: "每次调用写 trace 日志", c: "#4ade80" },
        ].map((x, i) => {
          const st = spring({ frame: frame - 70 - i * 8, config: { damping: 200 }, durationInFrames: 20 });
          return (
            <div
              key={i}
              style={{
                padding: "13px 26px",
                borderRadius: 11,
                background: "rgba(255,255,255,0.05)",
                border: `1px solid ${x.c}44`,
                fontSize: 23,
                color: x.c,
                opacity: st,
              }}
            >
              ✓ {x.t}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
}