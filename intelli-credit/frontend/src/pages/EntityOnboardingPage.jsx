import { useState } from "react";
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

export default function EntityOnboardingPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
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
    setEntity((prev) => ({ ...prev, [field]: value }));
    if (errors[field])
      setErrors((prev) => {
        const n = { ...prev };
        delete n[field];
        return n;
      });
  }

  function updateLoan(field, value) {
    setLoan((prev) => ({ ...prev, [field]: value }));
    if (errors[field])
      setErrors((prev) => {
        const n = { ...prev };
        delete n[field];
        return n;
      });
  }

  function validateStep1() {
    const errs = {};
    if (!entity.companyName.trim())
      errs.companyName = "Company name is required";
    if (entity.cin && !CIN_REGEX.test(entity.cin.toUpperCase()))
      errs.cin = "Invalid CIN format";
    if (entity.pan && !PAN_REGEX.test(entity.pan.toUpperCase()))
      errs.pan = "Invalid PAN format (e.g. ABCDE1234F)";
    if (!entity.sector) errs.sector = "Please select a sector";
    setErrors(errs);
    return Object.keys(errs).length === 0;
  }

  function validateStep2() {
    const errs = {};
    if (!loan.loanType) errs.loanType = "Please select loan type";
    if (!loan.loanAmount || Number(loan.loanAmount) <= 0)
      errs.loanAmount = "Loan amount is required";
    if (loan.purpose && loan.purpose.length > 500)
      errs.purpose = "Max 500 characters";
    setErrors(errs);
    return Object.keys(errs).length === 0;
  }

  function handleNext() {
    if (validateStep1()) setStep(2);
  }

  function handleProceed() {
    if (validateStep2()) {
      // Store form data in sessionStorage for display purposes
      sessionStorage.setItem("bluefin_entity", JSON.stringify(entity));
      sessionStorage.setItem("bluefin_loan", JSON.stringify(loan));
      navigate("/upload", {
        state: { companyName: entity.companyName.trim() },
      });
    }
  }

  function FieldError({ field }) {
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

  const inputStyle = {
    borderRadius: "var(--radius-lg)",
    padding: "12px 16px",
    width: "100%",
  };
  const labelStyle = {
    display: "block",
    marginBottom: "6px",
    fontSize: "12px",
    fontWeight: 600,
    color: "var(--text-secondary)",
    textTransform: "uppercase",
    letterSpacing: "0.5px",
  };

  return (
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
      {/* ── Progress Steps ── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "0",
          marginBottom: "48px",
          width: "100%",
          maxWidth: "700px",
        }}
      >
        {["Entity Details", "Documents", "Analysis", "Report"].map(
          (label, i) => {
            const stepNum = i + 1;
            const isActive = (stepNum === 1 && step <= 2) || false;
            const isCompleted = false;
            let status = "pending";
            if (stepNum === 1 && step >= 1)
              status = step > 2 ? "completed" : "active";
            if (stepNum === 2 && step > 2) status = "active";

            return (
              <div
                key={label}
                style={{
                  display: "flex",
                  alignItems: "center",
                  flex: i < 3 ? 1 : "none",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    minWidth: "fit-content",
                  }}
                >
                  <div
                    className="step-indicator-dot"
                    style={{
                      width: "36px",
                      height: "36px",
                      borderRadius: "50%",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: "13px",
                      fontWeight: 700,
                      transition: "all 0.4s cubic-bezier(0.4, 0, 0.2, 1)",
                      background:
                        status === "active"
                          ? "var(--accent)"
                          : status === "completed"
                            ? "var(--success)"
                            : "var(--bg-elevated)",
                      border: `2px solid ${status === "active" ? "var(--accent)" : status === "completed" ? "var(--success)" : "var(--border)"}`,
                      color:
                        status === "active" || status === "completed"
                          ? "#fff"
                          : "var(--text-muted)",
                      boxShadow:
                        status === "active"
                          ? "0 0 20px rgba(59,130,246,0.3)"
                          : "none",
                    }}
                  >
                    {status === "completed" ? (
                      <CheckCircle size={16} />
                    ) : (
                      stepNum
                    )}
                  </div>
                  <span
                    style={{
                      fontSize: "11px",
                      fontWeight: status === "active" ? 600 : 400,
                      color:
                        status === "active"
                          ? "var(--text-primary)"
                          : "var(--text-muted)",
                      marginTop: "6px",
                      whiteSpace: "nowrap",
                      transition: "all 0.3s ease",
                    }}
                  >
                    {label}
                  </span>
                </div>
                {i < 3 && (
                  <div
                    style={{
                      flex: 1,
                      height: "2px",
                      margin: "0 12px",
                      marginBottom: "20px",
                      borderRadius: "1px",
                      background: "var(--border)",
                      position: "relative",
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        position: "absolute",
                        top: 0,
                        left: 0,
                        bottom: 0,
                        width:
                          status === "completed" || (stepNum === 1 && step >= 2)
                            ? "100%"
                            : "0%",
                        background: "var(--accent)",
                        transition: "width 0.6s cubic-bezier(0.4, 0, 0.2, 1)",
                        borderRadius: "1px",
                      }}
                    />
                  </div>
                )}
              </div>
            );
          },
        )}
      </div>

      {/* ── Form Card ── */}
      <div
        className="card"
        style={{
          width: "100%",
          maxWidth: "700px",
          padding: "40px",
          borderRadius: "var(--radius-xl)",
          position: "relative",
          overflow: "hidden",
        }}
      >
        {/* Animated step transition */}
        <div
          style={{
            display: "flex",
            transition: "transform 0.5s cubic-bezier(0.4, 0, 0.2, 1)",
            transform: `translateX(${step === 1 ? "0" : "-100%"})`,
            width: "200%",
          }}
        >
          {/* ═══ STEP 1: Entity Details ═══ */}
          <div style={{ width: "50%", flexShrink: 0, paddingRight: "40px" }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "12px",
                marginBottom: "32px",
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
              {/* Company Name — full width */}
              <div style={{ gridColumn: "1 / -1" }}>
                <label style={labelStyle}>
                  Company Name <span style={{ color: "var(--danger)" }}>*</span>
                </label>
                <input
                  className="input"
                  style={inputStyle}
                  value={entity.companyName}
                  onChange={(e) => updateEntity("companyName", e.target.value)}
                  placeholder="e.g. Mehta Textiles Pvt Ltd"
                />
                <FieldError field="companyName" />
              </div>

              <div>
                <label style={labelStyle}>CIN</label>
                <input
                  className="input"
                  style={inputStyle}
                  value={entity.cin}
                  onChange={(e) =>
                    updateEntity("cin", e.target.value.toUpperCase())
                  }
                  placeholder="U12345AB1234CDE567890"
                  maxLength={21}
                />
                <FieldError field="cin" />
              </div>

              <div>
                <label style={labelStyle}>PAN</label>
                <input
                  className="input"
                  style={inputStyle}
                  value={entity.pan}
                  onChange={(e) =>
                    updateEntity("pan", e.target.value.toUpperCase())
                  }
                  placeholder="ABCDE1234F"
                  maxLength={10}
                />
                <FieldError field="pan" />
              </div>

              <div>
                <label style={labelStyle}>
                  GSTIN{" "}
                  <span style={{ color: "var(--text-muted)", fontWeight: 400 }}>
                    (optional)
                  </span>
                </label>
                <input
                  className="input"
                  style={inputStyle}
                  value={entity.gstin}
                  onChange={(e) =>
                    updateEntity("gstin", e.target.value.toUpperCase())
                  }
                  placeholder="22ABCDE1234F1Z5"
                  maxLength={15}
                />
              </div>

              <div>
                <label style={labelStyle}>
                  Sector <span style={{ color: "var(--danger)" }}>*</span>
                </label>
                <select
                  className="input"
                  style={inputStyle}
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
                <FieldError field="sector" />
              </div>

              <div>
                <label style={labelStyle}>
                  Sub-sector{" "}
                  <span style={{ color: "var(--text-muted)", fontWeight: 400 }}>
                    (optional)
                  </span>
                </label>
                <input
                  className="input"
                  style={inputStyle}
                  value={entity.subSector}
                  onChange={(e) => updateEntity("subSector", e.target.value)}
                  placeholder="e.g. Synthetic fibres"
                />
              </div>

              <div>
                <label style={labelStyle}>
                  Constitution <span style={{ color: "var(--danger)" }}>*</span>
                </label>
                <select
                  className="input"
                  style={inputStyle}
                  value={entity.constitution}
                  onChange={(e) => updateEntity("constitution", e.target.value)}
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
                <label style={labelStyle}>Annual Turnover (₹ Cr)</label>
                <input
                  className="input"
                  type="number"
                  style={inputStyle}
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
                <label style={labelStyle}>Years in Operation</label>
                <input
                  className="input"
                  type="number"
                  style={inputStyle}
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
                marginTop: "32px",
                padding: "14px",
                borderRadius: "var(--radius-lg)",
                fontSize: "15px",
              }}
            >
              Next — Loan Details <ArrowRight size={16} />
            </button>
          </div>

          {/* ═══ STEP 2: Loan Details ═══ */}
          <div style={{ width: "50%", flexShrink: 0, paddingLeft: "40px" }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "12px",
                marginBottom: "32px",
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
                <label style={labelStyle}>
                  Loan Type <span style={{ color: "var(--danger)" }}>*</span>
                </label>
                <select
                  className="input"
                  style={inputStyle}
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
                <FieldError field="loanType" />
              </div>

              <div>
                <label style={labelStyle}>
                  Loan Amount (₹ Cr){" "}
                  <span style={{ color: "var(--danger)" }}>*</span>
                </label>
                <input
                  className="input"
                  type="number"
                  style={inputStyle}
                  value={loan.loanAmount}
                  onChange={(e) => updateLoan("loanAmount", e.target.value)}
                  placeholder="e.g. 25"
                  min="0"
                  step="0.01"
                />
                <FieldError field="loanAmount" />
              </div>

              <div>
                <label style={labelStyle}>Tenure (months)</label>
                <input
                  className="input"
                  type="number"
                  style={inputStyle}
                  value={loan.tenure}
                  onChange={(e) => updateLoan("tenure", e.target.value)}
                  placeholder="e.g. 60"
                  min="1"
                />
              </div>

              <div>
                <label style={labelStyle}>Proposed Interest Rate (%)</label>
                <input
                  className="input"
                  type="number"
                  style={inputStyle}
                  value={loan.interestRate}
                  onChange={(e) => updateLoan("interestRate", e.target.value)}
                  placeholder="e.g. 10.5"
                  min="0"
                  step="0.1"
                />
              </div>

              <div>
                <label style={labelStyle}>Collateral Type</label>
                <select
                  className="input"
                  style={inputStyle}
                  value={loan.collateralType}
                  onChange={(e) => updateLoan("collateralType", e.target.value)}
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
                <label style={labelStyle}>
                  Purpose of Loan{" "}
                  <span style={{ color: "var(--text-muted)", fontWeight: 400 }}>
                    (max 500 chars)
                  </span>
                </label>
                <textarea
                  className="input"
                  style={{
                    ...inputStyle,
                    minHeight: "80px",
                    resize: "vertical",
                  }}
                  value={loan.purpose}
                  onChange={(e) => updateLoan("purpose", e.target.value)}
                  placeholder="Brief description of how the funds will be used..."
                  maxLength={500}
                />
                <FieldError field="purpose" />
                <span
                  style={{
                    fontSize: "11px",
                    color: "var(--text-muted)",
                    float: "right",
                  }}
                >
                  {loan.purpose.length}/500
                </span>
              </div>
            </div>

            <div style={{ display: "flex", gap: "12px", marginTop: "32px" }}>
              <button
                onClick={() => {
                  setStep(1);
                  setErrors({});
                }}
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
        </div>
      </div>
    </div>
  );
}
