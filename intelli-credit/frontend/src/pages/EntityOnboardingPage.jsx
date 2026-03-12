import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowRight,
  ArrowLeft,
  Building2,
  FileText,
  CheckCircle,
} from "lucide-react";

const SECTORS = [
  "Manufacturing",
  "Textiles",
  "Chemicals",
  "Infrastructure",
  "Real Estate",
  "Trading",
  "Services",
  "NBFC",
  "Other",
];
const CONSTITUTIONS = [
  "Private Limited",
  "Public Limited",
  "LLP",
  "Partnership",
  "Proprietorship",
];
const LOAN_TYPES = [
  "Term Loan",
  "Working Capital",
  "Cash Credit",
  "Letter of Credit",
  "Bank Guarantee",
  "Mixed Facility",
];
const COLLATERAL_TYPES = [
  "Immovable Property",
  "Plant & Machinery",
  "Receivables",
  "FD Lien",
  "Unsecured",
  "Mixed",
];
const CIN_REGEX = /^[UL]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}$/;
const PAN_REGEX = /^[A-Z]{5}\d{4}[A-Z]$/;

function PacMan({ mouthOpen }) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16">
      {mouthOpen ? (
        <path d="M8,8 L15,2 A8,8,0,1,0,15,14 Z" fill="#facc15" />
      ) : (
        <circle cx="8" cy="8" r="7.5" fill="#facc15" />
      )}
    </svg>
  );
}

function PacManLine({ eating, done }) {
  const [mouthOpen, setMouthOpen] = useState(true);
  useEffect(() => {
    if (!eating) return;
    const id = setInterval(() => setMouthOpen((o) => !o), 200);
    return () => clearInterval(id);
  }, [eating]);
  return (
    <div
      style={{
        flex: 1,
        height: "3px",
        margin: "0 10px",
        marginBottom: "22px",
        background: "var(--border)",
        borderRadius: "2px",
        position: "relative",
        overflow: "visible",
      }}
    >
      {done && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: "var(--accent)",
            borderRadius: "2px",
            animation: "trailFlash 0.3s ease",
          }}
        />
      )}
      {eating && (
        <>
          <div
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              bottom: 0,
              background: "var(--accent)",
              borderRadius: "2px",
              animation: "pacTrail 2s linear forwards",
            }}
          />
          <div
            style={{
              position: "absolute",
              top: "50%",
              transform: "translateY(-50%)",
              animation: "pacMove 2s linear forwards",
              zIndex: 10,
              filter: "drop-shadow(0 0 4px rgba(250,204,21,0.8))",
            }}
          >
            <PacMan mouthOpen={mouthOpen} />
          </div>
        </>
      )}
    </div>
  );
}

function PlainLine() {
  return (
    <div
      style={{
        flex: 1,
        height: "3px",
        margin: "0 10px",
        marginBottom: "22px",
        background: "var(--border)",
        borderRadius: "2px",
      }}
    />
  );
}

export default function EntityOnboardingPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [lineEating, setLineEating] = useState(false);
  const [lineDone, setLineDone] = useState(false);
  const [errors, setErrors] = useState({});
  const [entity, setEntity] = useState({
    companyName: "",
    cin: "",
    pan: "",
    gstin: "",
    sector: "",
    subSector: "",
    annualTurnover: "",
    yearsInOperation: "",
    constitution: "",
  });
  const [loan, setLoan] = useState({
    loanType: "",
    loanAmount: "",
    tenure: "",
    interestRate: "",
    purpose: "",
    collateralType: "",
  });

  function updateEntity(field, value) {
    setEntity((p) => ({ ...p, [field]: value }));
    if (errors[field])
      setErrors((p) => {
        const n = { ...p };
        delete n[field];
        return n;
      });
  }
  function updateLoan(field, value) {
    setLoan((p) => ({ ...p, [field]: value }));
    if (errors[field])
      setErrors((p) => {
        const n = { ...p };
        delete n[field];
        return n;
      });
  }

  function validateStep1() {
    const e = {};
    if (!entity.companyName.trim()) e.companyName = "Company name is required";
    if (entity.cin && !CIN_REGEX.test(entity.cin)) e.cin = "Invalid CIN format";
    if (entity.pan && !PAN_REGEX.test(entity.pan))
      e.pan = "Invalid PAN (e.g. ABCDE1234F)";
    if (!entity.sector) e.sector = "Please select a sector";
    setErrors(e);
    return Object.keys(e).length === 0;
  }
  function validateStep2() {
    const e = {};
    if (!loan.loanType) e.loanType = "Please select loan type";
    if (!loan.loanAmount || Number(loan.loanAmount) <= 0)
      e.loanAmount = "Loan amount is required";
    if (loan.purpose.length > 500) e.purpose = "Max 500 characters";
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  function handleNext() {
    if (!validateStep1()) return;
    setLineEating(true);
    setTimeout(() => {
      setLineEating(false);
      setLineDone(true);
      setStep(2);
    }, 2100);
  }
  function handleBack() {
    setStep(1);
    setLineDone(false);
    setErrors({});
  }
  function handleProceed() {
    if (!validateStep2()) return;
    sessionStorage.setItem("bluefin_entity", JSON.stringify(entity));
    sessionStorage.setItem("bluefin_loan", JSON.stringify(loan));
    navigate("/upload", { state: { companyName: entity.companyName.trim() } });
  }

  function Err({ field }) {
    if (!errors[field]) return null;
    return (
      <span
        style={{
          color: "var(--danger)",
          fontSize: "11px",
          marginTop: "4px",
          display: "block",
        }}
      >
        {errors[field]}
      </span>
    );
  }

  const inp = {
    borderRadius: "var(--radius-lg)",
    padding: "12px 16px",
    width: "100%",
  };
  const lbl = {
    display: "block",
    marginBottom: "6px",
    fontSize: "11px",
    fontWeight: 600,
    color: "var(--text-secondary)",
    textTransform: "uppercase",
    letterSpacing: "0.6px",
  };
  const steps = ["Entity Details", "Documents", "Analysis", "Report"];
  const stepStatuses = [
    step === 1 ? "active" : "done",
    step === 2 ? "active" : "pending",
    "pending",
    "pending",
  ];

  function dotStyle(s) {
    return {
      width: "36px",
      height: "36px",
      borderRadius: "50%",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      fontSize: "13px",
      fontWeight: 700,
      transition: "all 0.4s cubic-bezier(0.4,0,0.2,1)",
      background:
        s === "active"
          ? "var(--accent)"
          : s === "done"
            ? "var(--success)"
            : "var(--bg-elevated)",
      border: `2px solid ${s === "active" ? "var(--accent)" : s === "done" ? "var(--success)" : "var(--border)"}`,
      color: s === "active" || s === "done" ? "#fff" : "var(--text-muted)",
      boxShadow: s === "active" ? "0 0 20px rgba(59,130,246,0.35)" : "none",
    };
  }

  return (
    <>
      <style>{`
        @keyframes pacTrail { from { width: 0% } to { width: calc(100% - 16px) } }
        @keyframes pacMove  { from { left: -8px } to { left: calc(100% - 8px) } }
        @keyframes trailFlash { from { opacity: 0.4 } to { opacity: 1 } }
        @keyframes stepInRight { from { opacity: 0; transform: translateX(40px) } to { opacity: 1; transform: translateX(0) } }
        @keyframes stepInLeft  { from { opacity: 0; transform: translateX(-40px) } to { opacity: 1; transform: translateX(0) } }
      `}</style>
      <div
        className="page-enter"
        style={{
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          padding: "32px 24px",
        }}
      >
        {/* Progress Steps */}
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            marginBottom: "40px",
            width: "100%",
            maxWidth: "680px",
          }}
        >
          {steps.map((label, i) => {
            const s = stepStatuses[i];
            return (
              <div
                key={label}
                style={{
                  display: "flex",
                  alignItems: "center",
                  flex: i < steps.length - 1 ? 1 : "none",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                  }}
                >
                  <div style={dotStyle(s)}>
                    {s === "done" ? <CheckCircle size={16} /> : i + 1}
                  </div>
                  <span
                    style={{
                      fontSize: "11px",
                      marginTop: "6px",
                      whiteSpace: "nowrap",
                      fontWeight: s === "active" ? 600 : 400,
                      color:
                        s === "active"
                          ? "var(--text-primary)"
                          : "var(--text-muted)",
                      transition: "all 0.3s ease",
                    }}
                  >
                    {label}
                  </span>
                </div>
                {i === 0 && <PacManLine eating={lineEating} done={lineDone} />}
                {i > 0 && i < steps.length - 1 && <PlainLine />}
              </div>
            );
          })}
        </div>

        {/* Form Card */}
        <div
          className="card"
          style={{
            width: "100%",
            maxWidth: "680px",
            padding: "40px",
            borderRadius: "var(--radius-xl)",
          }}
        >
          {step === 1 && (
            <div
              style={{ animation: "stepInLeft 0.4s cubic-bezier(0.4,0,0.2,1)" }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "12px",
                  marginBottom: "28px",
                }}
              >
                <div
                  style={{
                    width: "40px",
                    height: "40px",
                    borderRadius: "12px",
                    background: "rgba(59,130,246,0.1)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <Building2 size={20} style={{ color: "var(--accent)" }} />
                </div>
                <div>
                  <h2 style={{ fontSize: "20px", marginBottom: "2px" }}>
                    Entity Details
                  </h2>
                  <p style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                    Basic information about the borrower
                  </p>
                </div>
              </div>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: "16px",
                }}
              >
                <div style={{ gridColumn: "1 / -1" }}>
                  <label style={lbl}>
                    Company Name{" "}
                    <span style={{ color: "var(--danger)" }}>*</span>
                  </label>
                  <input
                    className="input"
                    style={inp}
                    value={entity.companyName}
                    onChange={(e) =>
                      updateEntity("companyName", e.target.value)
                    }
                    placeholder="e.g. Mehta Textiles Pvt Ltd"
                  />
                  <Err field="companyName" />
                </div>
                <div>
                  <label style={lbl}>CIN</label>
                  <input
                    className="input"
                    style={inp}
                    value={entity.cin}
                    onChange={(e) =>
                      updateEntity("cin", e.target.value.toUpperCase())
                    }
                    placeholder="U12345AB1234CDE123456"
                    maxLength={21}
                  />
                  <Err field="cin" />
                </div>
                <div>
                  <label style={lbl}>PAN</label>
                  <input
                    className="input"
                    style={inp}
                    value={entity.pan}
                    onChange={(e) =>
                      updateEntity("pan", e.target.value.toUpperCase())
                    }
                    placeholder="ABCDE1234F"
                    maxLength={10}
                  />
                  <Err field="pan" />
                </div>
                <div>
                  <label style={lbl}>
                    GSTIN{" "}
                    <span
                      style={{
                        color: "var(--text-muted)",
                        fontWeight: 400,
                        textTransform: "none",
                      }}
                    >
                      (optional)
                    </span>
                  </label>
                  <input
                    className="input"
                    style={inp}
                    value={entity.gstin}
                    onChange={(e) =>
                      updateEntity("gstin", e.target.value.toUpperCase())
                    }
                    placeholder="22ABCDE1234F1Z5"
                    maxLength={15}
                  />
                </div>
                <div>
                  <label style={lbl}>
                    Sector <span style={{ color: "var(--danger)" }}>*</span>
                  </label>
                  <select
                    className="input"
                    style={inp}
                    value={entity.sector}
                    onChange={(e) => updateEntity("sector", e.target.value)}
                  >
                    <option value="">Select sector</option>
                    {SECTORS.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                  <Err field="sector" />
                </div>
                <div>
                  <label style={lbl}>
                    Sub-sector{" "}
                    <span
                      style={{
                        color: "var(--text-muted)",
                        fontWeight: 400,
                        textTransform: "none",
                      }}
                    >
                      (optional)
                    </span>
                  </label>
                  <input
                    className="input"
                    style={inp}
                    value={entity.subSector}
                    onChange={(e) => updateEntity("subSector", e.target.value)}
                    placeholder="e.g. Synthetic fibres"
                  />
                </div>
                <div>
                  <label style={lbl}>Constitution</label>
                  <select
                    className="input"
                    style={inp}
                    value={entity.constitution}
                    onChange={(e) =>
                      updateEntity("constitution", e.target.value)
                    }
                  >
                    <option value="">Select constitution</option>
                    {CONSTITUTIONS.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label style={lbl}>Annual Turnover (Rs. Cr)</label>
                  <input
                    className="input"
                    type="number"
                    style={inp}
                    value={entity.annualTurnover}
                    onChange={(e) =>
                      updateEntity("annualTurnover", e.target.value)
                    }
                    placeholder="e.g. 150"
                    min="0"
                    step="0.01"
                  />
                </div>
                <div>
                  <label style={lbl}>Years in Operation</label>
                  <input
                    className="input"
                    type="number"
                    style={inp}
                    value={entity.yearsInOperation}
                    onChange={(e) =>
                      updateEntity("yearsInOperation", e.target.value)
                    }
                    placeholder="e.g. 12"
                    min="0"
                  />
                </div>
              </div>
              <button
                onClick={handleNext}
                className="btn btn-primary w-full"
                style={{
                  marginTop: "28px",
                  padding: "14px",
                  borderRadius: "var(--radius-lg)",
                  fontSize: "15px",
                }}
              >
                Next - Loan Details <ArrowRight size={16} />
              </button>
            </div>
          )}

          {step === 2 && (
            <div
              style={{
                animation: "stepInRight 0.4s cubic-bezier(0.4,0,0.2,1)",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "12px",
                  marginBottom: "28px",
                }}
              >
                <div
                  style={{
                    width: "40px",
                    height: "40px",
                    borderRadius: "12px",
                    background: "rgba(59,130,246,0.1)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <FileText size={20} style={{ color: "var(--accent)" }} />
                </div>
                <div>
                  <h2 style={{ fontSize: "20px", marginBottom: "2px" }}>
                    Loan Details
                  </h2>
                  <p style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                    Proposed facility information
                  </p>
                </div>
              </div>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: "16px",
                }}
              >
                <div>
                  <label style={lbl}>
                    Loan Type <span style={{ color: "var(--danger)" }}>*</span>
                  </label>
                  <select
                    className="input"
                    style={inp}
                    value={loan.loanType}
                    onChange={(e) => updateLoan("loanType", e.target.value)}
                  >
                    <option value="">Select type</option>
                    {LOAN_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                  <Err field="loanType" />
                </div>
                <div>
                  <label style={lbl}>
                    Loan Amount (Rs. Cr){" "}
                    <span style={{ color: "var(--danger)" }}>*</span>
                  </label>
                  <input
                    className="input"
                    type="number"
                    style={inp}
                    value={loan.loanAmount}
                    onChange={(e) => updateLoan("loanAmount", e.target.value)}
                    placeholder="e.g. 25"
                    min="0"
                    step="0.01"
                  />
                  <Err field="loanAmount" />
                </div>
                <div>
                  <label style={lbl}>Tenure (months)</label>
                  <input
                    className="input"
                    type="number"
                    style={inp}
                    value={loan.tenure}
                    onChange={(e) => updateLoan("tenure", e.target.value)}
                    placeholder="e.g. 60"
                    min="1"
                  />
                </div>
                <div>
                  <label style={lbl}>Proposed Interest Rate (%)</label>
                  <input
                    className="input"
                    type="number"
                    style={inp}
                    value={loan.interestRate}
                    onChange={(e) => updateLoan("interestRate", e.target.value)}
                    placeholder="e.g. 10.5"
                    min="0"
                    step="0.1"
                  />
                </div>
                <div>
                  <label style={lbl}>Collateral Type</label>
                  <select
                    className="input"
                    style={inp}
                    value={loan.collateralType}
                    onChange={(e) =>
                      updateLoan("collateralType", e.target.value)
                    }
                  >
                    <option value="">Select collateral</option>
                    {COLLATERAL_TYPES.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </div>
                <div style={{ gridColumn: "1 / -1" }}>
                  <label style={lbl}>
                    Purpose of Loan{" "}
                    <span
                      style={{
                        color: "var(--text-muted)",
                        fontWeight: 400,
                        textTransform: "none",
                      }}
                    >
                      (max 500 chars)
                    </span>
                  </label>
                  <textarea
                    className="input"
                    style={{ ...inp, minHeight: "90px", resize: "vertical" }}
                    value={loan.purpose}
                    onChange={(e) => updateLoan("purpose", e.target.value)}
                    placeholder="Brief description of how the funds will be used..."
                    maxLength={500}
                  />
                  <div style={{ display: "flex", justifyContent: "flex-end" }}>
                    <span
                      style={{ fontSize: "11px", color: "var(--text-muted)" }}
                    >
                      {loan.purpose.length}/500
                    </span>
                  </div>
                  <Err field="purpose" />
                </div>
              </div>
              <div style={{ display: "flex", gap: "12px", marginTop: "28px" }}>
                <button
                  onClick={handleBack}
                  className="btn btn-secondary"
                  style={{
                    padding: "14px 24px",
                    borderRadius: "var(--radius-lg)",
                    fontSize: "15px",
                  }}
                >
                  <ArrowLeft size={16} /> Back
                </button>
                <button
                  onClick={handleProceed}
                  className="btn btn-primary"
                  style={{
                    flex: 1,
                    padding: "14px",
                    borderRadius: "var(--radius-lg)",
                    fontSize: "15px",
                  }}
                >
                  Proceed to Document Upload <ArrowRight size={16} />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
