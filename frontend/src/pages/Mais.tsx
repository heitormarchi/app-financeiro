import { Link } from "react-router-dom";

export default function Mais() {
  return (
    <div className="page">
      <h2>Mais</h2>
      <ul className="menu-list">
        <li><Link to="/mais/pendencias">Pendências</Link></li>
        <li><Link to="/mais/config">Config</Link></li>
      </ul>
    </div>
  );
}
