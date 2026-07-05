import { NavLink } from "react-router-dom";

const items = [
  { to: "/", label: "Início", icon: "🏠" },
  { to: "/transacoes", label: "Transações", icon: "📋" },
  { to: "/adicionar", label: "Adicionar", icon: "➕" },
  { to: "/futuros", label: "Futuros", icon: "📅" },
  { to: "/mais", label: "Mais", icon: "⋯" },
];

export default function BottomNav() {
  return (
    <nav className="bottom-nav">
      {items.map((i) => (
        <NavLink key={i.to} to={i.to} end={i.to === "/"}
          className={({ isActive }) => (isActive ? "nav-item active" : "nav-item")}>
          <span className="nav-icon">{i.icon}</span>
          <span className="nav-label">{i.label}</span>
        </NavLink>
      ))}
    </nav>
  );
}
