import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import History from "./pages/History";
import EditDashboard from "./pages/EditDashboard";
import ConfirmModal from "./components/ConfirmModal";
import PrivateRoute from "./utils/PrivateRoute";

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Login />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/history" element={<History />} />
        <Route path="/edit/:id" element={<EditDashboard />} />
      </Routes>
    </Router>
  );
}

export default App;
