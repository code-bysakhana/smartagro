import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import AuthPage        from "./pages/AuthPage";
import Layout          from "./components/Layout";
import Dashboard       from "./pages/Dashboard";
import CropMonitoring  from "./pages/CropMonitoring";
import CropRecommend   from "./pages/CropRecommend";
import DiseaseDetect   from "./pages/DiseaseDetect";
import "./index.css";

function PrivateRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return (
    <div className="full-center">
      <div className="spinner-lg" />
      <p style={{marginTop:16,color:"#6b7280"}}>Loading SmartAgro…</p>
    </div>
  );
  return user ? children : <Navigate to="/auth" replace />;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/auth" element={<AuthPage />} />
          <Route path="/" element={<PrivateRoute><Layout /></PrivateRoute>}>
            <Route index         element={<Dashboard />} />
            <Route path="monitor"  element={<CropMonitoring />} />
            <Route path="recommend" element={<CropRecommend />} />
            <Route path="disease"  element={<DiseaseDetect />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
