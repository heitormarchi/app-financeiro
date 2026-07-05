import { BrowserRouter, Routes, Route } from "react-router-dom";
import "./App.css";
import BottomNav from "./components/BottomNav";
import Dashboard from "./pages/Dashboard";
import Transacoes from "./pages/Transacoes";
import Adicionar from "./pages/Adicionar";
import Futuros from "./pages/Futuros";
import Mais from "./pages/Mais";
import Pendencias from "./pages/Pendencias";
import Config from "./pages/Config";

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-content">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/transacoes" element={<Transacoes />} />
          <Route path="/adicionar" element={<Adicionar />} />
          <Route path="/futuros" element={<Futuros />} />
          <Route path="/mais" element={<Mais />} />
          <Route path="/mais/pendencias" element={<Pendencias />} />
          <Route path="/mais/config" element={<Config />} />
        </Routes>
      </div>
      <BottomNav />
    </BrowserRouter>
  );
}
