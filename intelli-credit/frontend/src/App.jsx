import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ToastProvider } from "./context/ToastContext.jsx";
import Navbar from "./components/Navbar.jsx";
import UploadPage from "./pages/UploadPage.jsx";
import AnalysisPage from "./pages/AnalysisPage.jsx";
import CAMPage from "./pages/CAMPage.jsx";
import HistoryPage from "./pages/HistoryPage.jsx";

export default function App() {
  return (
    <ToastProvider>
      <BrowserRouter>
        <div className="bg-bg min-h-screen">
          <Navbar />
          <Routes>
            <Route path="/" element={<UploadPage />} />
            <Route path="/analysis/:jobId" element={<AnalysisPage />} />
            <Route path="/cam/:jobId" element={<CAMPage />} />
            <Route path="/history" element={<HistoryPage />} />
          </Routes>
        </div>
      </BrowserRouter>
    </ToastProvider>
  );
}
