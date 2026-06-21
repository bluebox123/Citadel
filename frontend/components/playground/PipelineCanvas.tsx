"use client";

import React, { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence, useAnimation, useReducedMotion } from "framer-motion";
import { Shield, Lock, Code2, Check, AlertTriangle } from "lucide-react";

// ── Shared types ───────────────────────────────────────────────────────────────

export type PipelineStatus =
  | "idle" | "scanning" | "signing" | "parsing"
  | "success" | "fail_firewall" | "fail_parser" | "fail_network";

export type NodeState = "idle" | "active" | "pass" | "fail";
export type PathState = "idle" | "flowing" | "pass" | "blocked";

export interface PipelineCanvasProps {
  n1: NodeState;
  n2: NodeState;
  n3: NodeState;
  p1: PathState;
  p2: PathState;
  pipelineStatus: PipelineStatus;
}

// ── Easing constants (Emil's strong ease-out) ─────────────────────────────────

const EASE_CINEMATIC = [0.22, 1, 0.36, 1] as const;
const SPRING_SNAPPY  = { type: "spring", stiffness: 420, damping: 28 } as const;

// ── Bezier keyframe sampler ────────────────────────────────────────────────────
// Samples N+1 evenly-spaced points along a cubic bezier P0 P1 P2 P3.

function sampleCubicBezier(
  p0x: number, p0y: number,
  p1x: number, p1y: number,
  p2x: number, p2y: number,
  p3x: number, p3y: number,
  steps = 12
): { x: number[]; y: number[] } {
  const xs: number[] = [];
  const ys: number[] = [];
  for (let i = 0; i <= steps; i++) {
    const t  = i / steps;
    const mt = 1 - t;
    xs.push(+(mt*mt*mt*p0x + 3*mt*mt*t*p1x + 3*mt*t*t*p2x + t*t*t*p3x).toFixed(1));
    ys.push(+(mt*mt*mt*p0y + 3*mt*mt*t*p1y + 3*mt*t*t*p2y + t*t*t*p3y).toFixed(1));
  }
  return { x: xs, y: ys };
}

// Pre-computed keyframes for the two bezier paths
// Path 1: M220,110 C265,110 265,220 310,220  (Firewall → HMAC)
// Path 2: M490,220 C535,220 535,110 580,110  (HMAC → CFG)
const KF1 = sampleCubicBezier(220, 110, 265, 110, 265, 220, 310, 220, 12);
const KF2 = sampleCubicBezier(490, 220, 535, 220, 535, 110, 580, 110, 12);

const PATH_1 = "M220,110 C265,110 265,220 310,220";
const PATH_2 = "M490,220 C535,220 535,110 580,110";

// ── Colour maps ────────────────────────────────────────────────────────────────

const PATH_STROKE: Record<PathState, string> = {
  idle:    "rgba(255,255,255,0.07)",
  flowing: "rgba(6,182,212,0.9)",
  pass:    "rgba(16,185,129,0.82)",
  blocked: "rgba(245,158,11,0.85)",
};

const NODE_THEME: Record<NodeState, {
  border: string; bg: string; glow: string;
  label: string; dot: string; status: string; statusColor: string;
}> = {
  idle: {
    border:      "rgba(255,255,255,0.07)",
    bg:          "rgba(255,255,255,0.015)",
    glow:        "none",
    label:       "rgba(255,255,255,0.25)",
    dot:         "#3f3f3f",
    status:      "STANDBY",
    statusColor: "rgba(255,255,255,0.22)",
  },
  active: {
    border:      "rgba(6,182,212,0.6)",
    bg:          "rgba(6,182,212,0.055)",
    glow:        "0 0 28px rgba(6,182,212,0.24)",
    label:       "rgba(255,255,255,0.92)",
    dot:         "#06B6D4",
    status:      "ACTIVE",
    statusColor: "#06B6D4",
  },
  pass: {
    border:      "rgba(16,185,129,0.52)",
    bg:          "rgba(16,185,129,0.045)",
    glow:        "0 0 18px rgba(16,185,129,0.2)",
    label:       "rgba(255,255,255,0.88)",
    dot:         "#10B981",
    status:      "PASS",
    statusColor: "#10B981",
  },
  fail: {
    border:      "rgba(245,158,11,0.65)",
    bg:          "rgba(245,158,11,0.06)",
    glow:        "0 0 28px rgba(245,158,11,0.24)",
    label:       "rgba(255,255,255,0.92)",
    dot:         "#F59E0B",
    status:      "BLOCKED",
    statusColor: "#F59E0B",
  },
};

// ── Travel Particle (Framer Motion, bezier keyframes) ─────────────────────────

interface TravelParticleProps {
  keyframes: { x: number[]; y: number[] };
  delay: number;
  r: number;
  opacity: number;
  color: string;
  duration: number;
  isActive: boolean;
  filterId: string;
}

function TravelParticle({
  keyframes, delay, r, opacity, color, duration, isActive, filterId,
}: TravelParticleProps) {
  const opacityKF = [0, opacity, opacity, opacity * 0.9, 0];
  const rKF       = [r * 0.5, r, r, r * 0.85, r * 0.5];

  return (
    <AnimatePresence>
      {isActive && (
        <motion.circle
          key="particle"
          initial={{
            cx: keyframes.x[0],
            cy: keyframes.y[0],
            opacity: 0,
            r: r * 0.5,
          }}
          animate={{
            cx: keyframes.x,
            cy: keyframes.y,
            opacity: opacityKF,
            r: rKF,
          }}
          exit={{ opacity: 0, transition: { duration: 0.15 } }}
          transition={{
            // cx/cy: 13 bezier keyframes distributed evenly across duration
            cx:      { duration, delay, ease: EASE_CINEMATIC, repeat: Infinity, repeatDelay: 0.04 },
            cy:      { duration, delay, ease: EASE_CINEMATIC, repeat: Infinity, repeatDelay: 0.04 },
            // opacity/r: 5 keyframes with explicit time positions for comet fade
            opacity: { duration, delay, ease: EASE_CINEMATIC, repeat: Infinity, repeatDelay: 0.04, times: [0, 0.08, 0.55, 0.85, 1] },
            r:       { duration, delay, ease: EASE_CINEMATIC, repeat: Infinity, repeatDelay: 0.04, times: [0, 0.08, 0.55, 0.85, 1] },
          }}
          fill={color}
          filter={`url(#${filterId})`}
          style={{ willChange: "transform, opacity" }}
        />
      )}
    </AnimatePresence>
  );
}

// ── Animated SVG Path with shatter ────────────────────────────────────────────

interface AnimatedPathProps {
  d: string;
  state: PathState;
  keyframes: { x: number[]; y: number[] };
  reduceMotion: boolean;
}

function AnimatedPath({ d, state, keyframes, reduceMotion }: AnimatedPathProps) {
  const stroke     = PATH_STROKE[state];
  const isFlowing  = state === "flowing";
  const isPass     = state === "pass";
  const isBlocked  = state === "blocked";

  // Track state transitions to trigger one-shot shatter
  const prevRef    = useRef(state);
  const [shatterKey, setShatterKey] = useState(0);

  useEffect(() => {
    if (state === "blocked" && prevRef.current !== "blocked" && !reduceMotion) {
      setShatterKey(k => k + 1);
    }
    prevRef.current = state;
  }, [state, reduceMotion]);

  // Particle cycle duration and stagger
  const FLOW_DUR  = 0.68;
  const FLOW_LAG  = (FLOW_DUR + 0.04) / 3; // even 3-particle stagger

  const PASS_DUR  = 2.4;
  const PASS_LAG  = (PASS_DUR + 1.0) / 2;

  return (
    <g>
      {/* Ghost rail */}
      <path
        d={d}
        stroke="rgba(255,255,255,0.04)"
        strokeWidth="1.5"
        fill="none"
        strokeDasharray="3 9"
      />

      {/* Animated main stroke */}
      <motion.path
        d={d}
        fill="none"
        strokeLinecap="round"
        strokeWidth={isFlowing || isBlocked ? 2 : 1.5}
        animate={{
          stroke,
          strokeDasharray: state === "idle" ? "5 6" : "0 0",
          opacity: isBlocked ? 0.9 : 1,
        }}
        transition={{
          stroke:          { duration: 0.18, ease: "linear" },
          strokeDasharray: { duration: 0.35, ease: EASE_CINEMATIC },
          opacity:         { duration: 0.3 },
        }}
      />

      {/* Ambient glow layer */}
      <AnimatePresence>
        {isFlowing && !reduceMotion && (
          <motion.path
            key="flow-glow"
            d={d}
            stroke="rgba(6,182,212,0.18)"
            strokeWidth="10"
            fill="none"
            initial={{ opacity: 0 }}
            animate={{ opacity: [0.5, 1, 0.5] }}
            exit={{ opacity: 0, transition: { duration: 0.2 } }}
            transition={{ duration: 1.2, repeat: Infinity, ease: "easeInOut" }}
          />
        )}
        {isPass && !reduceMotion && (
          <motion.path
            key="pass-glow"
            d={d}
            stroke="rgba(16,185,129,0.12)"
            strokeWidth="8"
            fill="none"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, transition: { duration: 0.2 } }}
            transition={{ duration: 0.5 }}
          />
        )}
        {isBlocked && !reduceMotion && (
          <motion.path
            key="block-glow"
            d={d}
            stroke="rgba(245,158,11,0.18)"
            strokeWidth="10"
            fill="none"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
          />
        )}
      </AnimatePresence>

      {/* ONE-SHOT SHATTER FLASH when path becomes blocked */}
      <AnimatePresence>
        {shatterKey > 0 && (
          <motion.path
            key={`shatter-${shatterKey}`}
            d={d}
            stroke="rgba(239,68,68,1)"
            strokeWidth="3"
            fill="none"
            initial={{ opacity: 1, pathLength: 1, filter: "blur(0px)" }}
            animate={{
              opacity:    [1, 0.8, 0.3, 0],
              pathLength: [1, 0.8, 0.4, 0],
              filter:     ["blur(0px)", "blur(2px)", "blur(5px)", "blur(8px)"],
            }}
            transition={{
              duration: 0.55,
              ease: EASE_CINEMATIC,
              times: [0, 0.25, 0.65, 1],
            }}
            exit={{ opacity: 0 }}
          />
        )}
      </AnimatePresence>

      {/* Flowing particles (3 staggered, comet trail) */}
      {!reduceMotion && ([0, FLOW_LAG, FLOW_LAG * 2] as const).map((lag, i) => (
        <TravelParticle
          key={`fp-${i}`}
          keyframes={keyframes}
          delay={lag}
          r={5 - i}
          opacity={1 - i * 0.28}
          color="rgba(6,182,212,0.95)"
          duration={FLOW_DUR}
          isActive={isFlowing}
          filterId="particle-glow-cyan"
        />
      ))}

      {/* Pass particles (2 slow, emerald) */}
      {!reduceMotion && ([0, PASS_LAG] as const).map((lag, i) => (
        <TravelParticle
          key={`pp-${i}`}
          keyframes={keyframes}
          delay={lag}
          r={3}
          opacity={0.65}
          color="rgba(16,185,129,0.85)"
          duration={PASS_DUR}
          isActive={isPass}
          filterId="particle-glow-emerald"
        />
      ))}
    </g>
  );
}

// ── Pipeline Node ──────────────────────────────────────────────────────────────

interface PipelineNodeProps {
  label: string;
  sublabel: string;
  detail: string;
  Icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>;
  state: NodeState;
  nodeIndex: number;  // 0=firewall, 1=hmac, 2=cfg
  pipelineStatus: PipelineStatus;
  left: number;
  top: number;
  reduceMotion: boolean;
}

function PipelineNode({
  label, sublabel, detail, Icon, state, nodeIndex,
  pipelineStatus, left, top, reduceMotion,
}: PipelineNodeProps) {
  const theme        = NODE_THEME[state];
  const scaleCtrl    = useAnimation();
  const shakeCtrl    = useAnimation();
  const prevStateRef = useRef<NodeState>(state);
  const prevStatusRef = useRef<PipelineStatus>(pipelineStatus);

  // ── Pulse on state transitions ─────────────────────────────────────────────
  useEffect(() => {
    if (reduceMotion) return;
    const prev = prevStateRef.current;
    prevStateRef.current = state;

    if (state === "active" && prev !== "active") {
      // Heavy arrival thump
      void scaleCtrl.start({
        scale: [1, 1.07, 0.96, 1.025, 1],
        transition: { duration: 0.55, times: [0, 0.18, 0.48, 0.75, 1], ease: EASE_CINEMATIC },
      });
    }
    if (state === "pass" && prev === "active") {
      // Stamp sealed
      void scaleCtrl.start({
        scale: [1.03, 0.96, 1.01, 1],
        transition: { duration: 0.38, ease: EASE_CINEMATIC },
      });
    }
    if (state === "fail") {
      // Collision shake
      void shakeCtrl.start({
        x: [0, -6, 6, -4, 4, -2, 2, 0],
        transition: { duration: 0.42, ease: EASE_CINEMATIC },
      });
    }
  }, [state, scaleCtrl, shakeCtrl, reduceMotion]);

  // ── Gray-out shock for bystander nodes during fail_firewall ───────────────
  useEffect(() => {
    if (reduceMotion) return;
    const prevStatus = prevStatusRef.current;
    prevStatusRef.current = pipelineStatus;

    const isFailFirewall = pipelineStatus === "fail_firewall" && prevStatus !== "fail_firewall";

    if (isFailFirewall && nodeIndex > 0 && state === "idle") {
      void shakeCtrl.start({
        x: [0, -3, 3, -1.5, 1.5, 0],
        opacity: [1, 0.7, 0.7, 0.5, 0.5, 0.35],
        transition: { duration: 0.4, ease: EASE_CINEMATIC },
      });
    }
  }, [pipelineStatus, nodeIndex, state, shakeCtrl, reduceMotion]);

  return (
    <motion.div
      className="absolute rounded-lg overflow-hidden"
      animate={{
        borderColor:     theme.border,
        backgroundColor: theme.bg,
        boxShadow:       theme.glow,
      }}
      transition={{
        borderColor:     { duration: 0.35, ease: EASE_CINEMATIC },
        backgroundColor: { duration: 0.35, ease: EASE_CINEMATIC },
        boxShadow:       { duration: 0.45, ease: EASE_CINEMATIC },
      }}
      style={{
        left:        `${left}%`,
        top:         `${top}%`,
        width:       "22.5%",
        height:      "30.56%",
        border:      `1px solid ${theme.border}`,
        background:  theme.bg,
        boxShadow:   theme.glow,
        willChange:  "transform, box-shadow",
      }}
    >
      {/* Active inner pulse ring */}
      <AnimatePresence>
        {state === "active" && !reduceMotion && (
          <motion.div
            key="ring"
            className="absolute inset-0 rounded-lg pointer-events-none"
            initial={{ opacity: 0 }}
            animate={{
              opacity: [0.35, 0.85, 0.35],
              boxShadow: [
                "inset 0 0 6px rgba(6,182,212,0.08)",
                "inset 0 0 22px rgba(6,182,212,0.2)",
                "inset 0 0 6px rgba(6,182,212,0.08)",
              ],
            }}
            exit={{ opacity: 0, transition: { duration: 0.2 } }}
            transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}
          />
        )}
      </AnimatePresence>

      {/* Fail amber wash */}
      <AnimatePresence>
        {state === "fail" && (
          <motion.div
            key="fail-wash"
            className="absolute inset-0 rounded-lg pointer-events-none"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            style={{ background: "rgba(245,158,11,0.05)" }}
          />
        )}
      </AnimatePresence>

      {/* Scale + shake wrapper */}
      <motion.div
        className="relative flex flex-col justify-between h-full px-3 py-2.5"
        animate={scaleCtrl}
        style={{ willChange: "transform" }}
      >
        <motion.div
          className="flex flex-col justify-between h-full"
          animate={shakeCtrl}
          style={{ willChange: "transform" }}
        >
          {/* Top row */}
          <div className="flex items-start justify-between">
            <motion.div
              animate={{ opacity: state === "idle" ? 0.3 : 0.92 }}
              transition={{ duration: 0.35 }}
            >
              <Icon className="w-4 h-4" style={{ color: theme.dot }} />
            </motion.div>

            {/* Status indicator */}
            <div className="flex items-center gap-1">
              <motion.div
                className="rounded-full"
                style={{ width: 5, height: 5 }}
                animate={{ backgroundColor: theme.dot }}
                transition={{ duration: 0.35 }}
              >
                {state === "active" && !reduceMotion && (
                  <motion.div
                    className="w-full h-full rounded-full"
                    style={{ backgroundColor: theme.dot }}
                    animate={{ scale: [1, 1.6, 1], opacity: [0.8, 1, 0.8] }}
                    transition={{ duration: 1.1, repeat: Infinity, ease: "easeInOut" }}
                  />
                )}
              </motion.div>
              <motion.span
                className="text-[8px] tracking-widest uppercase"
                style={{ fontFamily: "var(--font-mono)" }}
                animate={{ color: theme.statusColor }}
                transition={{ duration: 0.35 }}
              >
                {theme.status}
              </motion.span>
            </div>
          </div>

          {/* Label */}
          <div className="flex flex-col gap-0.5">
            <motion.div
              className="text-[11px] font-bold tracking-wider uppercase leading-tight"
              style={{ fontFamily: "var(--font-heading)" }}
              animate={{ color: theme.label }}
              transition={{ duration: 0.35 }}
            >
              {label}
            </motion.div>
            <motion.div
              className="text-[8px] tracking-widest uppercase"
              style={{ fontFamily: "var(--font-mono)" }}
              animate={{ color: theme.label, opacity: 0.5 }}
              transition={{ duration: 0.35 }}
            >
              {sublabel}
            </motion.div>
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between">
            <motion.div
              className="text-[7px] tracking-wider uppercase"
              style={{ fontFamily: "var(--font-mono)" }}
              animate={{ color: theme.label, opacity: 0.38 }}
              transition={{ duration: 0.35 }}
            >
              {detail}
            </motion.div>
            <AnimatePresence mode="wait">
              {state === "pass" && (
                <motion.div
                  key="check"
                  initial={{ scale: 0, opacity: 0, rotate: -20 }}
                  animate={{ scale: 1, opacity: 1, rotate: 0 }}
                  exit={{ scale: 0, opacity: 0 }}
                  transition={SPRING_SNAPPY}
                >
                  <Check className="w-3 h-3" style={{ color: "#10B981" }} />
                </motion.div>
              )}
              {state === "fail" && (
                <motion.div
                  key="alert"
                  initial={{ scale: 0, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  exit={{ scale: 0, opacity: 0 }}
                  transition={SPRING_SNAPPY}
                >
                  <AlertTriangle className="w-3 h-3" style={{ color: "#F59E0B" }} />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </motion.div>
      </motion.div>
    </motion.div>
  );
}

// ── Node layout config ─────────────────────────────────────────────────────────

const NODE_CONFIG = [
  { id: "firewall", label: "FIREWALL",   sublabel: "48-PATTERN SCAN", detail: "5 CATEGORIES",    Icon: Shield, left: 5,     top: 15.28 },
  { id: "hmac",     label: "HMAC-SHA256",sublabel: "ZERO-TRUST SIGN", detail: "CANONICAL JSON",   Icon: Lock,   left: 38.75, top: 45.83 },
  { id: "cfg",      label: "CFG PARSER", sublabel: "LALR(1) ENGINE",  detail: "7 REJECT GUARDS", Icon: Code2,  left: 72.5,  top: 15.28 },
] as const;

// ── Main Canvas Export ─────────────────────────────────────────────────────────

export function PipelineCanvas({ n1, n2, n3, p1, p2, pipelineStatus }: PipelineCanvasProps) {
  const reduceMotion = useReducedMotion() ?? false;
  const nodeStates   = [n1, n2, n3] as const;
  const pathStates   = [p1, p2] as const;
  const pathKFs      = [KF1, KF2] as const;

  // Junction dot colours
  const junctionDots = [
    { cx: 220, cy: 110, ps: p1 },
    { cx: 310, cy: 220, ps: p1 },
    { cx: 490, cy: 220, ps: p2 },
    { cx: 580, cy: 110, ps: p2 },
  ] as const;

  const dotColor = (ps: PathState) =>
    ps === "flowing" ? "rgba(6,182,212,0.85)"  :
    ps === "pass"    ? "rgba(16,185,129,0.85)" :
    ps === "blocked" ? "rgba(245,158,11,0.85)" :
    "rgba(255,255,255,0.1)";

  return (
    <div className="relative w-full" style={{ paddingBottom: "45%" }}>
      <div className="absolute inset-0">

        {/* ── SVG layer ── */}
        <svg
          viewBox="0 0 800 360"
          className="absolute inset-0 w-full h-full"
          style={{ overflow: "visible" }}
          aria-hidden="true"
        >
          <defs>
            {/* Particle glow filters */}
            <filter id="particle-glow-cyan" x="-80%" y="-80%" width="260%" height="260%">
              <feGaussianBlur in="SourceGraphic" stdDeviation="3.5" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <filter id="particle-glow-emerald" x="-80%" y="-80%" width="260%" height="260%">
              <feGaussianBlur in="SourceGraphic" stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            {/* Node edge connection dots */}
            <filter id="dot-glow" x="-100%" y="-100%" width="300%" height="300%">
              <feGaussianBlur in="SourceGraphic" stdDeviation="2" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Paths */}
          {([PATH_1, PATH_2] as const).map((d, i) => (
            <AnimatedPath
              key={i}
              d={d}
              state={pathStates[i]}
              keyframes={pathKFs[i]}
              reduceMotion={reduceMotion}
            />
          ))}

          {/* Junction dots */}
          {junctionDots.map(({ cx, cy, ps }, i) => (
            <motion.circle
              key={i}
              cx={cx}
              cy={cy}
              r={ps !== "idle" ? 3.5 : 2.5}
              filter={ps !== "idle" ? "url(#dot-glow)" : undefined}
              animate={{ fill: dotColor(ps), r: ps !== "idle" ? 3.5 : 2.5 }}
              transition={{ duration: 0.4, ease: EASE_CINEMATIC }}
            />
          ))}
        </svg>

        {/* ── HTML node overlays ── */}
        {NODE_CONFIG.map(({ id, label, sublabel, detail, Icon, left, top }, i) => (
          <PipelineNode
            key={id}
            label={label}
            sublabel={sublabel}
            detail={detail}
            Icon={Icon}
            state={nodeStates[i]}
            nodeIndex={i}
            pipelineStatus={pipelineStatus}
            left={left}
            top={top}
            reduceMotion={reduceMotion}
          />
        ))}
      </div>
    </div>
  );
}
