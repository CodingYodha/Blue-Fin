import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Shield, Brain, Network, Search, FileText } from "lucide-react";

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
    body: "GST-Bank variance, GSTR-2A mismatch, round-trip detection, cash ratio analysis — four independent fraud probes running in parallel.",
    icon: Shield,
    accent: "#ef4444",
  },
  {
    id: 2,
    tag: "02 — ML Scoring",
    title: "Four models. One score. Full SHAP trail.",
    body: "LightGBM ensemble trained on financial health, credit behaviour, external risk, and text signals — every number traced to its source.",
    icon: Brain,
    accent: "#3b82f6",
  },
  {
    id: 3,
    tag: "03 — Entity Graph",
    title: "See the network, not just the company.",
    body: "Force-directed graph of directors, subsidiaries, and loan accounts. Dashed edges for probable name matches.",
    icon: Network,
    accent: "#8b5cf6",
  },
  {
    id: 4,
    tag: "04 — Research Agent",
    title: "LangGraph scours courts, NCLT, and news.",
    body: "Autonomous multi-step agent queries regulatory filings, litigation records, and sector intelligence.",
    icon: Search,
    accent: "#eab308",
  },
  {
    id: 5,
    tag: "05 — CAM Generation",
    title: "Three personas. One executive memo.",
    body: "Forensic Accountant, Compliance Officer, and CRO collaborate to produce a complete Credit Appraisal Memo.",
    icon: FileText,
    accent: "#22c55e",
  },
];

/* ─── Feature cards ─── */
const FEATURES = [
  {
    icon: Shield,
    color: "#ef4444",
    title: "Fraud Detection",
    body: "GST, GSTR, round-trip, cash — four independent flags with explicit score penalties.",
    span: 2,
  },
  {
    icon: Brain,
    color: "#3b82f6",
    title: "SHAP Explainability",
    body: "Every model decision traced to feature contributions. Waterfall chart included.",
    span: 1,
  },
  {
    icon: Network,
    color: "#8b5cf6",
    title: "Entity Graph",
    body: "Force-directed network of directors, loans, and subsidiaries with anomaly detection.",
    span: 1,
  },
  {
    icon: Search,
    color: "#eab308",
    title: "Stress Testing",
    body: "Revenue shock, rate hike, GST scrutiny — see which scenarios flip the credit decision.",
    span: 1,
  },
  {
    icon: FileText,
    color: "#22c55e",
    title: "Research Agent",
    body: "LangGraph agent with tool calls to NCLT, eCourts, news APIs, and sector databases.",
    span: 2,
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
  const SlideIcon = slide.icon;

  return (
    <div className="page-enter">
      {/* ══════ HERO ══════ */}
      <section
        style={{
          minHeight: "92vh",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          textAlign: "center",
          padding: "120px 24px 80px",
          position: "relative",
        }}
      >
        {/* Background glow */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            pointerEvents: "none",
            background:
              "radial-gradient(ellipse 60% 40% at 50% 30%, rgba(59,130,246,0.06) 0%, transparent 65%)",
          }}
        />

        {/* Eyebrow */}
        <div className="eyebrow" style={{ marginBottom: "32px" }}>
          AI-Powered Credit Intelligence Platform
        </div>

        {/* Headline */}
        <h1
          style={{
            fontSize: "clamp(2.6rem, 6vw, 5rem)",
            maxWidth: "720px",
            marginBottom: "24px",
            fontWeight: 700,
            lineHeight: 1.08,
          }}
        >
          Credit decisions,{" "}
          <em
            className="serif-italic"
            style={{ color: "var(--accent)" }}
          >
            reimagined
          </em>
        </h1>

        {/* Subtitle */}
        <p
          style={{
            color: "var(--text-secondary)",
            fontSize: "17px",
            maxWidth: "520px",
            lineHeight: 1.7,
            marginBottom: "40px",
          }}
        >
          End-to-end AI credit appraisal for Indian banks. Forensic PDF
          analysis, LightGBM scoring, autonomous research, and
          officer-grade memos in one pipeline.
        </p>

        {/* CTAs */}
        <div className="flex gap-md" style={{ marginBottom: "48px" }}>
          <button
            className="btn btn-primary btn-lg"
            onClick={() => navigate("/upload")}
          >
            Get Started <ArrowRight size={18} />
          </button>
          <a href="#how-it-works" className="btn btn-secondary btn-lg">
            How It Works
          </a>
        </div>

        {/* Stat pills */}
        <div className="flex flex-wrap justify-center gap-sm">
          {[
            ["12", "Pipeline Stages"],
            ["4", "LightGBM Models"],
            ["3", "Risk Personas"],
            ["100pt", "Score Scale"],
          ].map(([n, label]) => (
            <div
              key={n}
              className="glass"
              style={{
                borderRadius: "var(--radius-full)",
                padding: "8px 20px",
                display: "flex",
                alignItems: "center",
                gap: "10px",
              }}
            >
              <span
                style={{
                  fontFamily: "var(--font-heading)",
                  fontWeight: 700,
                  color: "var(--accent)",
                  fontSize: "15px",
                }}
              >
                {n}
              </span>
              <span style={{ color: "var(--text-muted)", fontSize: "13px" }}>
                {label}
              </span>
            </div>
          ))}
        </div>
      </section>

      {/* ══════ MARQUEE STRIP ══════ */}
      <div
        style={{
          borderTop: "1px solid var(--border)",
          borderBottom: "1px solid var(--border)",
          padding: "14px 0",
          background: "rgba(33,33,38,0.5)",
        }}
        className="select-none"
      >
        <div className="marquee-outer">
          <div className="marquee-inner">
            {[...Array(4)].flatMap((_, di) =>
              MARQUEE_ITEMS.map((t) => (
                <span
                  key={t + di}
                  style={{
                    fontFamily: "var(--font-body)",
                    fontSize: "11px",
                    color: "var(--text-muted)",
                    whiteSpace: "nowrap",
                    letterSpacing: "0.15em",
                    fontWeight: 500,
                    textTransform: "uppercase",
                  }}
                >
                  {t}
                  <span
                    style={{
                      color: "var(--accent)",
                      opacity: 0.5,
                      margin: "0 24px",
                    }}
                  >
                    ·
                  </span>
                </span>
              )),
            )}
          </div>
        </div>
      </div>

      {/* ══════ STATS ══════ */}
      <section className="container" style={{ padding: "80px 24px" }}>
        <div
          className="grid grid-4"
          style={{
            gap: "1px",
            background: "var(--border)",
            borderRadius: "var(--radius-lg)",
            overflow: "hidden",
          }}
        >
          {[
            { target: 12, suffix: "", label: "Pipeline Stages" },
            { target: 4, suffix: "", label: "LightGBM Models" },
            { target: 3, suffix: "", label: "Risk Personas" },
            { target: 100, suffix: "pt", label: "Score Scale" },
          ].map(({ target, suffix, label }) => (
            <div
              key={label}
              className="stat-card"
              style={{ borderRadius: 0, border: "none" }}
            >
              <div className="stat-value">
                <Counter target={target} suffix={suffix} />
              </div>
              <div className="stat-label">{label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ══════ HOW IT WORKS ══════ */}
      <section
        id="how-it-works"
        className="container"
        style={{ padding: "64px 24px" }}
      >
        <div className="eyebrow" style={{ marginBottom: "16px" }}>
          How it works
        </div>
        <h2 style={{ marginBottom: "48px", maxWidth: "480px" }}>
          From raw documents to a signed memo.
        </h2>

        <div className="grid grid-3" style={{ gap: "0px" }}>
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
              body: "Score dashboard, entity graph, research findings. Add field notes to adjust the score live.",
            },
          ].map((step, i) => (
            <div
              key={step.n}
              className="card"
              style={{
                borderRadius: i === 0 ? "var(--radius-lg) 0 0 var(--radius-lg)" : i === 2 ? "0 var(--radius-lg) var(--radius-lg) 0" : "0",
                borderLeft: i > 0 ? "none" : undefined,
              }}
            >
              <span
                className="serif"
                style={{
                  fontSize: "clamp(2.5rem, 5vw, 4rem)",
                  fontWeight: 700,
                  color: "var(--border-strong)",
                  lineHeight: 1,
                  display: "block",
                  marginBottom: "16px",
                }}
              >
                {step.n}
              </span>
              <h3
                style={{
                  fontFamily: "var(--font-body)",
                  fontWeight: 600,
                  fontSize: "15px",
                  marginBottom: "8px",
                }}
              >
                {step.title}
              </h3>
              <p style={{ color: "var(--text-muted)", fontSize: "13px", lineHeight: 1.6 }}>
                {step.body}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* ══════ FEATURE CAROUSEL ══════ */}
      <section className="container" style={{ padding: "64px 24px" }}>
        <div className="eyebrow" style={{ marginBottom: "16px" }}>
          What's inside
        </div>
        <h2 style={{ marginBottom: "40px", maxWidth: "480px" }}>
          Every layer of the stack, explained.
        </h2>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "24px",
            alignItems: "start",
          }}
        >
          {/* Active slide card */}
          <div
            className="card"
            style={{
              background: `radial-gradient(ellipse at 25% 30%, ${slide.accent}12 0%, transparent 55%), var(--bg-surface)`,
              borderColor: slide.accent + "30",
              padding: "40px",
              minHeight: "300px",
              display: "flex",
              flexDirection: "column",
              gap: "20px",
            }}
          >
            <div className="flex items-center gap-sm">
              <SlideIcon size={18} style={{ color: slide.accent }} />
              <span
                className="label"
                style={{ color: slide.accent, letterSpacing: "0.1em" }}
              >
                {slide.tag}
              </span>
            </div>
            <h3
              className="serif"
              style={{ fontSize: "20px", lineHeight: 1.3 }}
            >
              {slide.title}
            </h3>
            <p
              style={{
                color: "var(--text-muted)",
                fontSize: "14px",
                lineHeight: 1.7,
                flex: 1,
              }}
            >
              {slide.body}
            </p>

            {/* Dot progress */}
            <div className="flex gap-xs" style={{ paddingTop: "8px" }}>
              {SLIDES.map((_, i) => (
                <button
                  key={i}
                  onClick={() => goToSlide(i)}
                  style={{
                    width: i === activeSlide ? "28px" : "8px",
                    height: "8px",
                    borderRadius: "var(--radius-full)",
                    background: i === activeSlide ? slide.accent : "var(--bg-elevated)",
                    border: "none",
                    cursor: "pointer",
                    transition: "all 0.3s ease",
                  }}
                />
              ))}
            </div>
          </div>

          {/* Slide list nav */}
          <div className="flex flex-col gap-xs">
            {SLIDES.map((s, i) => {
              const Icon = s.icon;
              return (
                <button
                  key={s.id}
                  onClick={() => goToSlide(i)}
                  style={{
                    textAlign: "left",
                    padding: "16px 20px",
                    borderRadius: "var(--radius-md)",
                    border: `1px solid ${i === activeSlide ? "var(--border-hover)" : "transparent"}`,
                    background: i === activeSlide ? "var(--bg-surface)" : "transparent",
                    cursor: "pointer",
                    transition: "all 0.2s ease",
                  }}
                >
                  <div className="flex items-center gap-sm" style={{ marginBottom: "4px" }}>
                    <Icon size={14} style={{ color: s.accent, opacity: 0.7 }} />
                    <span className="label" style={{ color: "var(--text-muted)" }}>
                      {s.tag.split("—")[0].trim()}
                    </span>
                  </div>
                  <p
                    style={{
                      fontSize: "14px",
                      fontWeight: 500,
                      color: i === activeSlide ? "var(--text-primary)" : "var(--text-muted)",
                      transition: "color 0.2s",
                    }}
                  >
                    {s.title}
                  </p>
                  {i === activeSlide && (
                    <div
                      style={{
                        marginTop: "10px",
                        height: "2px",
                        background: "var(--bg-elevated)",
                        borderRadius: "var(--radius-full)",
                        overflow: "hidden",
                      }}
                    >
                      <div
                        style={{
                          height: "100%",
                          borderRadius: "var(--radius-full)",
                          background: s.accent,
                          animation: "carouselProgress 4.5s linear forwards",
                        }}
                      />
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      </section>

      {/* ══════ BENTO FEATURES ══════ */}
      <section className="container" style={{ padding: "64px 24px" }}>
        <div className="eyebrow" style={{ marginBottom: "16px" }}>
          Capabilities
        </div>
        <h2 style={{ marginBottom: "40px", maxWidth: "480px" }}>
          Built for every analyst's question.
        </h2>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            gap: "16px",
          }}
        >
          {FEATURES.map((f) => {
            const Icon = f.icon;
            return (
              <div
                key={f.title}
                className="card card-interactive"
                style={{
                  gridColumn: f.span === 2 ? "span 2" : "span 1",
                  display: "flex",
                  flexDirection: "column",
                  gap: "14px",
                }}
              >
                <div
                  style={{
                    width: "40px",
                    height: "40px",
                    borderRadius: "var(--radius-md)",
                    background: f.color + "15",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <Icon size={20} style={{ color: f.color }} />
                </div>
                <h3
                  style={{
                    fontFamily: "var(--font-body)",
                    fontWeight: 600,
                    fontSize: "15px",
                  }}
                >
                  {f.title}
                </h3>
                <p style={{ color: "var(--text-muted)", fontSize: "13px", lineHeight: 1.6 }}>
                  {f.body}
                </p>
              </div>
            );
          })}
        </div>
      </section>

      {/* ══════ FINAL CTA ══════ */}
      <section className="container" style={{ padding: "48px 24px 96px" }}>
        <div
          className="card"
          style={{
            background:
              "radial-gradient(ellipse 70% 60% at 50% 50%, rgba(59,130,246,0.05) 0%, transparent 65%), var(--bg-surface)",
            borderColor: "rgba(59,130,246,0.15)",
            padding: "80px 48px",
            textAlign: "center",
            position: "relative",
            overflow: "hidden",
          }}
        >
          <div className="eyebrow" style={{ marginBottom: "20px", justifyContent: "center" }}>
            Get started today
          </div>
          <h2
            style={{
              maxWidth: "560px",
              margin: "0 auto 20px",
            }}
          >
            Analyse your first credit file in under ten minutes.
          </h2>
          <p
            style={{
              color: "var(--text-muted)",
              fontSize: "15px",
              maxWidth: "440px",
              margin: "0 auto 40px",
              lineHeight: 1.7,
            }}
          >
            Upload three documents. The pipeline handles everything else —
            scoring, research, fraud checks, and memo generation.
          </p>
          <button
            className="btn btn-primary btn-lg"
            onClick={() => navigate("/upload")}
          >
            Upload Documents <ArrowRight size={18} />
          </button>
        </div>
      </section>
    </div>
  );
}
