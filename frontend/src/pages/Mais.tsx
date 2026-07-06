import { Link } from "react-router-dom";

export default function Mais() {
  return (
    <div className="page">
      <header className="page-head">
        <h1 className="page-title">Mais</h1>
      </header>
      <div className="card" style={{ padding: "4px 18px" }}>
        <ul className="menu-list">
          <li><Link to="/mais/pendencias">Pendências</Link></li>
          <li><Link to="/mais/config">Configurações</Link></li>
        </ul>
      </div>
    </div>
  );
}
