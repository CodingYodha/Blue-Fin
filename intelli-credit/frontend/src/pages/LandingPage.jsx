import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";

/* ─── Animated counter on scroll ─── */
function Counter({ target, suffix = "" }) {
  const [count, setCount] = useState(0);
  const ref = useRef(null);
  const started = useRef(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !started.current) {
          started.current = true;
          let start = null;
          const duration = 1600;
          const tick = (ts) => {
            if (!start) start = ts;
            const p = Math.min((ts - start) / duration, 1);
            const ease = 1 - Math.pow(1 - p, 3);
            setCount(Math.floor(ease * target));
            if (p < 1) requestAnimationFrame(tick);
          };
          requestAnimationFrame(tick);
        }
      },
      { threshold: 0.6 },
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, [target]);

  return (
    <span ref={ref}>
      {count}
      {suffix}
    </span>
  );
}

/* ─── Carousel slides ─── */
const SLIDES = [
  {
    id: 1,
    tag: "01 — Fraud Intelligence",
    title: "Forensic math that catches what eyes miss.",
    body: "GST-Bank variance, GSTR-2A mismatch, round-trip detection, cash ratio analysis — four independent fraud probes running in parallel, each with score penalties.",
    accent: "#ef4444",
  },
  {
    id: 2,
    tag: "02 — ML Scoring",
    title: "Four models. One score. Full SHAP trail.",
    body: "LightGBM ensemble trained on financial health, credit behaviour, external risk, and unstructured text — every number is traced back to its source feature.",
    accent: "#00d4ff",
  },
  {
    id: 3,
    tag: "03 — Entity Graph",
    title: "See the network, not just the company.",
    body: "Force-directed graph of directors, subsidiaries, and loan accounts. Dashed edges for probable name matches. Click any node to inspect its risk profile.",
    accent: "#7c3aed",
  },
  {
    id: 4,
    tag: "04 — Research Agent",
    title: "LangGraph scours courts, NCLT, and news.",
    body: "Autonomous multi-step agent queries regulatory filings, litigation records, and sector intelligence — surfaces findings ranked by severity with source citations.",
    accent: "#f59e0b",
  },
  {
    id: 5,
    tag: "05 — CAM Generation",
    title: "Three personas. One executive memo.",
    body: "Forensic Accountant writes the numbers. Compliance Officer flags risks. CRO signs off — with override logic and a 4-column final recommendation summary.",
    accent: "#10b981",
  },
];

/* ─── Bento feature cards ─── */
const FEATURES = [
  {
    symbol: "⬡",
    color: "#ef4444",
    title: "Fraud Detection",
    body: "GST, GSTR, round-trip, cash — four independent flags, each with explicit score penalties and dual-bar visuals.",
    wide: true,
  },
  {
    symbol: "◎",
    color: "#00d4ff",
    title: "SHAP Explainability",
    body: "Every model decision traced to feature contributions. Waterfall chart included.",
    wide: false,
  },
  {
    symbol: "◈",
    color: "#7c3aed",
    title: "Entity Graph",
    body: "Force-directed network of directors, loans, and subsidiaries with anomaly detection.",
    wide: false,
  },
  {
    symbol: "◉",
    color: "#f59e0b",
    title: "Stress Testing",
    body: "Revenue shock, rate hike, GST scrutiny — see exactly which scenarios flip the credit decision.",
    wide: false,
  },
  {
    symbol: "◆",
    color: "#10b981",
    title: "Research Agent",
    body: "LangGraph agent with tool calls to NCLT, eCourts, news APIs, and sector intelligence databases.",
    wide: true,
  },
];

/* ─── Marquee items ─── */
const MARQUEE_ITEMS = [
  "GST FORENSICS",
  "OCR ENGINE",
  "ENTITY GRAPH",
  "SHAP EXPLAINABILITY",
  "LangGraph RESEARCH",
  "STRESS TESTING",
  "CAM GENERATION",
  "FRAUD DETECTION",
  "4-MODEL ENSEMBLE",
  "OFFICER NOTES",
];

export default function LandingPage() {
  const navigate = useNavigate();
  const [activeSlide, setActiveSlide] = useState(0);
  const timerRef = useRef(null);

  function startTimer() {
    clearInterval(timerRef.current);
    timerRef.current = setInterval(() => {
      setActiveSlide((s) => (s + 1) % SLIDES.length);
    }, 4500);
  }

  useEffect(() => {
    startTimer();
    return () => clearInterval(timerRef.current);
  }, []);

  function goToSlide(i) {
    setActiveSlide(i);
    startTimer();
  }

  const slide = SLIDES[activeSlide];

  return (
    <div className="page-enter bg-bg text-textprimary overflow-x-hidden">
      {/* ══════════════════════════════════════════
          HERO
      ══════════════════════════════════════════ */}
      <section className="relative min-h-[91vh] flex flex-col items-center justify-center text-center px-6">
        {/* Background glows */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background:
              "radial-gradient(ellipse 80% 55% at 50% 35%, rgba(0,212,255,0.07) 0%, transparent 65%)",
          }}
        />
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background:
              "radial-gradient(ellipse 45% 35% at 75% 75%, rgba(124,58,237,0.06) 0%, transparent 60%)",
          }}
        />

        {/* Eyebrow */}
        <div className="flex items-center gap-2 mb-8">
          <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
          <span className="font-mono text-xs tracking-[0.28em] text-accent uppercase">
            Enterprise Credit Intelligence Platform
          </span>
        </div>

        {/* Headline */}
        <h1
          className="font-sans font-bold leading-[1.06] mb-7 max-w-4xl"
          style={{ fontSize: "clamp(2.6rem, 6.5vw, 5.5rem)" }}
        >
          Credit decisions that <br className="hidden md:block" />
          <span
            style={{
              background:
                "linear-gradient(135deg, #00d4ff 0%, #7c3aed 55%, #10b981 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
            }}
          >
            know everything.
          </span>
        </h1>

        {/* Subline */}
        <p className="text-muted text-lg max-w-xl leading-relaxed mb-12 font-sans font-light">
          End-to-end AI credit appraisal for Indian banks. Forensic PDF
          analysis, LightGBM scoring, autonomous research, and officer-grade
          memos — in one pipeline.
        </p>

        {/* CTAs */}
        <div className="flex flex-wrap items-center justify-center gap-4 mb-16">
          <button
            onClick={() => navigate("/upload")}
            className="group relative rounded-2xl px-9 py-4 font-sans font-semibold text-base text-bg transition-all duration-200 hover:scale-[1.03] active:scale-95 overflow-hidden"
            style={{
              background: "linear-gradient(135deg, #00d4ff 0%, #7c3aed 100%)",
              boxShadow:
                "0 0 48px rgba(0,212,255,0.28), 0 2px 8px rgba(0,0,0,0.4)",
            }}
          >
            Start New Analysis
            <span className="ml-2 inline-block transition-transform group-hover:translate-x-1">
              →
            </span>
          </button>
          <a
            href="#how-it-works"
            className="rounded-2xl px-9 py-4 font-sans text-base text-textprimary border border-border hover:border-accent/40 hover:text-accent transition-all duration-200"
          >
            See how it works
          </a>
        </div>

        {/* Stat pills */}
        <div className="flex flex-wrap justify-center gap-3">
          {[
            ["12", "Pipeline Stages"],
            ["4", "LightGBM Models"],
            ["3", "Risk Personas"],
            ["100pt", "Score Scale"],
          ].map(([n, label]) => (
            <div
              key={n}
              className="rounded-2xl border border-border bg-surface/80 backdrop-blur px-5 py-2.5 flex items-center gap-3"
            >
              <span className="font-mono font-bold text-accent text-base">
                {n}
              </span>
              <span className="text-muted text-sm">{label}</span>
            </div>
          ))}
        </div>
      </section>

      {/* ══════════════════════════════════════════
          MARQUEE STRIP
      ══════════════════════════════════════════ */}
      <div className="border-y border-border py-4 overflow-hidden select-none bg-surface/30">
        <div className="marquee-outer">
          <div className="marquee-inner">
            {[...Array(4)].flatMap((_, di) =>
              MARQUEE_ITEMS.map((t) => (
                <span
                  key={t + di}
                  className="font-mono text-xs text-muted whitespace-nowrap tracking-widest"
                >
                  {t}
                  <span className="text-accent/60 mx-6">·</span>
                </span>
              )),
            )}
          </div>
        </div>
      </div>

      {/* ══════════════════════════════════════════
          STATS
      ══════════════════════════════════════════ */}
      <section className="max-w-5xl mx-auto px-6 py-20">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-border rounded-2xl overflow-hidden">
          {[
            { target: 12, suffix: "", label: "Pipeline Stages" },
            { target: 4, suffix: "", label: "LightGBM Models" },
            { target: 3, suffix: "", label: "Risk Personas" },
            { target: 100, suffix: "pt", label: "Score Scale" },
          ].map(({ target, suffix, label }) => (
            <div
              key={label}
              className="bg-surface p-8 text-center flex flex-col gap-2"
            >
              <span
                className="font-mono font-bold text-accent"
                style={{ fontSize: "clamp(2.2rem, 5vw, 3.5rem)" }}
              >
                <Counter target={target} suffix={suffix} />
              </span>
              <span className="text-muted text-sm font-sans">{label}</span>
            </div>
          ))}
        </div>
      </section>

      {/* ══════════════════════════════════════════
          HOW IT WORKS
      ══════════════════════════════════════════ */}
      <section id="how-it-works" className="max-w-5xl mx-auto px-6 py-16">
        <p className="font-mono text-xs text-accent tracking-widest uppercase mb-4">
          How it works
        </p>
        <h2
          className="font-sans font-bold mb-14 max-w-xl leading-tight"
          style={{ fontSize: "clamp(1.8rem, 4vw, 2.8rem)" }}
        >
          From raw documents to a signed memo.
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-3 relative">
          {[
            {
              n: "01",
              title: "Upload Documents",
              body: "Annual Report, GST filings, Bank Statement CSV. Optional ITR and MCA for deeper analysis.",
            },
            {
              n: "02",
              title: "Pipeline Runs",
              body: "12 stages in sequence — Go parses, Python scores, LangGraph researches. Watch it live over SSE.",
            },
            {
              n: "03",
              title: "Review & Decide",
              body: "Score dashboard, entity graph, research findings. Add field notes to adjust the score live. Export a full CAM.",
            },
          ].map((step, i) => (
            <div
              key={step.n}
              className="relative flex flex-col gap-4 p-8 border border-border bg-surface first:rounded-tl-2xl first:rounded-bl-2xl last:rounded-tr-2xl last:rounded-br-2xl -ml-px first:ml-0 hover:bg-surface2 transition-colors"
            >
              <span
                className="font-mono font-bold text-border"
                style={{ fontSize: "clamp(3rem, 6vw, 4.5rem)", lineHeight: 1 }}
              >
                {step.n}
              </span>
              <h3 className="font-sans font-semibold text-base text-textprimary">
                {step.title}
              </h3>
              <p className="text-muted text-sm leading-relaxed">{step.body}</p>

              {i < 2 && (
                <span className="absolute right-0 top-1/2 -translate-y-1/2 translate-x-[50%] w-5 h-5 rounded-full border-2 border-accent bg-bg z-10 hidden md:flex items-center justify-center">
                  <span className="w-1.5 h-1.5 rounded-full bg-accent" />
                </span>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* ══════════════════════════════════════════
          FEATURE CAROUSEL
      ══════════════════════════════════════════ */}
      <section className="max-w-5xl mx-auto px-6 py-16">
        <p className="font-mono text-xs text-accent tracking-widest uppercase mb-4">
          What's inside
        </p>
        <h2
          className="font-sans font-bold mb-12 max-w-xl leading-tight"
          style={{ fontSize: "clamp(1.8rem, 4vw, 2.8rem)" }}
        >
          Every layer of the stack, explained.
        </h2>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
          {/* Active slide card */}
          <div
            className="rounded-3xl border p-10 flex flex-col gap-6 min-h-64 transition-all duration-500"
            style={{
              background: `radial-gradient(ellipse at 25% 30%, ${slide.accent}18 0%, transparent 55%), #0b1120`,
              borderColor: slide.accent + "35",
            }}
          >
            <span
              className="font-mono text-xs tracking-widest uppercase"
              style={{ color: slide.accent }}
            >
              {slide.tag}
            </span>
            <h3 className="font-sans font-bold text-xl text-textprimary leading-snug">
              {slide.title}
            </h3>
            <p className="text-muted text-sm leading-relaxed flex-1">
              {slide.body}
            </p>

            {/* Dot progress */}
            <div className="flex gap-2 pt-2">
              {SLIDES.map((_, i) => (
                <button
                  key={i}
                  onClick={() => goToSlide(i)}
                  className="transition-all duration-300 rounded-full"
                  style={{
                    width: i === activeSlide ? "24px" : "8px",
                    height: "8px",
                    background: i === activeSlide ? slide.accent : "#1e2d45",
                  }}
                />
              ))}
            </div>
          </div>

          {/* Slide list nav */}
          <div className="flex flex-col gap-2">
            {SLIDES.map((s, i) => (
              <button
                key={s.id}
                onClick={() => goToSlide(i)}
                className={`text-left px-5 py-4 rounded-xl border transition-all duration-200 ${
                  i === activeSlide
                    ? "border-border bg-surface2"
                    : "border-transparent hover:border-border/50 hover:bg-surface/50"
                }`}
              >
                <p className="font-mono text-xs text-muted mb-1">
                  {s.tag.split("—")[0].trim()}
                </p>
                <p
                  className={`text-sm font-medium transition-colors ${
                    i === activeSlide ? "text-textprimary" : "text-muted"
                  }`}
                >
                  {s.title}
                </p>
                {i === activeSlide && (
                  <div className="mt-3 h-0.5 bg-surface rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full"
                      style={{
                        background: s.accent,
                        animation: "carouselProgress 4.5s linear forwards",
                      }}
                    />
                  </div>
                )}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════════
          BENTO FEATURES
      ══════════════════════════════════════════ */}
      <section className="max-w-5xl mx-auto px-6 py-16">
        <p className="font-mono text-xs text-accent tracking-widest uppercase mb-4">
          Capabilities
        </p>
        <h2
          className="font-sans font-bold mb-12 max-w-xl leading-tight"
          style={{ fontSize: "clamp(1.8rem, 4vw, 2.8rem)" }}
        >
          Built for every analyst's question.
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
          {FEATURES.map((f) => (
            <div
              key={f.title}
              className={`rounded-2xl border border-border bg-surface p-7 flex flex-col gap-4 hover:border-accent/25 hover:-translate-y-1 transition-all duration-200 group ${
                f.wide ? "md:col-span-2" : ""
              }`}
            >
              <span
                className="text-3xl font-bold"
                style={{ color: f.color, fontFamily: "monospace" }}
              >
                {f.symbol}
              </span>
              <h3 className="font-sans font-semibold text-textprimary">
                {f.title}
              </h3>
              <p className="text-muted text-sm leading-relaxed">{f.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ══════════════════════════════════════════
          FINAL CTA
      ══════════════════════════════════════════ */}
      <section className="max-w-5xl mx-auto px-6 py-24">
        <div
          className="rounded-3xl border border-accent/15 p-16 text-center relative overflow-hidden"
          style={{
            background:
              "radial-gradient(ellipse 80% 65% at 50% 50%, rgba(0,212,255,0.05) 0%, transparent 65%), #0b1120",
          }}
        >
          {/* Glow orbs */}
          <div
            className="absolute top-0 left-1/4 w-64 h-64 rounded-full pointer-events-none"
            style={{
              background:
                "radial-gradient(circle, rgba(0,212,255,0.06) 0%, transparent 70%)",
              transform: "translateY(-50%)",
            }}
          />
          <div
            className="absolute bottom-0 right-1/4 w-64 h-64 rounded-full pointer-events-none"
            style={{
              background:
                "radial-gradient(circle, rgba(124,58,237,0.07) 0%, transparent 70%)",
              transform: "translateY(50%)",
            }}
          />

          <p className="font-mono text-xs text-accent tracking-widest uppercase mb-6">
            Get started today
          </p>
          <h2
            className="font-sans font-bold leading-tight mb-6 max-w-2xl mx-auto"
            style={{ fontSize: "clamp(1.8rem, 4.5vw, 3.2rem)" }}
          >
            Analyse your first credit file in under ten minutes.
          </h2>
          <p className="text-muted text-base mb-12 max-w-lg mx-auto leading-relaxed font-light">
            Upload three documents. The pipeline handles everything else —
            scoring, research, fraud checks, and memo generation.
          </p>
          <button
            onClick={() => navigate("/upload")}
            className="rounded-2xl px-12 py-5 font-sans font-semibold text-lg text-bg transition-all duration-200 hover:scale-[1.04] active:scale-95"
            style={{
              background: "linear-gradient(135deg, #00d4ff 0%, #7c3aed 100%)",
              boxShadow:
                "0 0 64px rgba(0,212,255,0.22), 0 4px 20px rgba(0,0,0,0.4)",
            }}
          >
            Upload Documents →
          </button>
        </div>
      </section>

      {/* ══════════════════════════════════════════
          FOOTER
      ══════════════════════════════════════════ */}
      <footer className="border-t border-border px-6 py-10 max-w-5xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
        <div>
          <span className="font-mono font-bold text-accent text-sm tracking-widest">
            INTELLI-CREDIT
          </span>
          <p className="text-muted text-xs mt-0.5">
            AI-Powered Corporate Credit Decisioning
          </p>
        </div>
        <p className="text-muted text-xs font-mono">IIT Hyderabad · 2026</p>
      </footer>
    </div>
  );
}
