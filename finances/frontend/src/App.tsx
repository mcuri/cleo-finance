import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import Dashboard from "./components/Dashboard";
import TransactionList from "./components/TransactionList";
import AddTransaction from "./components/AddTransaction";
import CsvImport from "./components/CsvImport";
import CategoryManager from "./components/CategoryManager";
import Chat from "./components/Chat";

export default function App() {
  return (
    <BrowserRouter>
      <nav>
        <span className="nav-logo">cleo</span>
        <NavLink to="/">Dashboard</NavLink>
        <NavLink to="/transactions">Transactions</NavLink>
        <NavLink to="/chat">✦ Chat</NavLink>
        <NavLink to="/add">Add</NavLink>
        <NavLink to="/import">Import CSV</NavLink>
        <NavLink to="/categories">Categories</NavLink>
      </nav>
      <main>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/transactions" element={<TransactionList />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/add" element={<AddTransaction />} />
          <Route path="/import" element={<CsvImport />} />
          <Route path="/categories" element={<CategoryManager />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}
