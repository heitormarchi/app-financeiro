import { NavLink } from "react-router-dom";

type IconProps = { size?: number };

function IconHome({ size = 22 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 10.8 12 3.5l9 7.3" />
      <path d="M5.5 9.5V20a.8.8 0 0 0 .8.8h11.4a.8.8 0 0 0 .8-.8V9.5" />
      <path d="M9.5 20.5v-5.3a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v5.3" />
    </svg>
  );
}

function IconExtrato({ size = 22 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 2.8h12v18l-2.4-1.6-2.4 1.6-2.4-1.6L8.4 20.8 6 19.2z" />
      <path d="M9 8h6M9 11.5h6M9 15h3.5" />
    </svg>
  );
}

function IconMais({ size = 24 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}

function IconCalendario({ size = 22 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3.5" y="5" width="17" height="16" rx="2" />
      <path d="M3.5 9.5h17M8 2.8V6M16 2.8V6" />
      <path d="M8 14l2.6 2.6L16.5 12" />
    </svg>
  );
}

function IconPontos({ size = 22 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" stroke="none">
      <circle cx="5" cy="12" r="1.9" />
      <circle cx="12" cy="12" r="1.9" />
      <circle cx="19" cy="12" r="1.9" />
    </svg>
  );
}

export default function BottomNav() {
  return (
    <nav className="bottom-nav">
      <NavLink to="/" end
        className={({ isActive }) => (isActive ? "nav-item active" : "nav-item")}>
        <IconHome />
        <span>Início</span>
      </NavLink>
      <NavLink to="/transacoes"
        className={({ isActive }) => (isActive ? "nav-item active" : "nav-item")}>
        <IconExtrato />
        <span>Extrato</span>
      </NavLink>
      <NavLink to="/adicionar"
        className={({ isActive }) => (isActive ? "nav-add active" : "nav-add")}>
        <span className="nav-add-circulo"><IconMais /></span>
        <span>Adicionar</span>
      </NavLink>
      <NavLink to="/futuros"
        className={({ isActive }) => (isActive ? "nav-item active" : "nav-item")}>
        <IconCalendario />
        <span>Futuros</span>
      </NavLink>
      <NavLink to="/mais"
        className={({ isActive }) => (isActive ? "nav-item active" : "nav-item")}>
        <IconPontos />
        <span>Mais</span>
      </NavLink>
    </nav>
  );
}
