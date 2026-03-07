import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { ToastProvider } from "./context/ToastContext.jsx";
import Navbar from "./components/Navbar.jsx";
import LandingPage from "./pages/LandingPage.jsx";
import UploadPage from "./pages/UploadPage.jsx";
import AnalysisPage from "./pages/AnalysisPage.jsx";
import CAMPage from "./pages/CAMPage.jsx";
import HistoryPage from "./pages/HistoryPage.jsx";

function AppShell() {
  const location = useLocation();
  const isLanding = location.pathname === "/";
  return (
    <div className="grid-bg page">
      <Navbar />
      <div className={isLanding ? "" : "has-navbar"}>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/analysis/:jobId" element={<AnalysisPage />} />
          <Route path="/cam/:jobId" element={<CAMPage />} />
          <Route path="/history" element={<HistoryPage />} />
        </Routes>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <ToastProvider>
      <BrowserRouter>
        <AppShell />
      </BrowserRouter>
    </ToastProvider>
  );
}
