import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import Dashboard from "./components/Dashboard";
import TransactionList from "./components/TransactionList";
import AddTransaction from "./components/AddTransaction";
import CsvImport from "./components/CsvImport";
import CategoryManager from "./components/CategoryManager";

export default function App() {
  return (
    <BrowserRouter>
      <nav>
        <NavLink to="/">Dashboard</NavLink>
        <NavLink to="/transactions">Transactions</NavLink>
        <NavLink to="/add">Add</NavLink>
        <NavLink to="/import">Import CSV</NavLink>
        <NavLink to="/categories">Categories</NavLink>
      </nav>
      <main>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/transactions" element={<TransactionList />} />
          <Route path="/add" element={<AddTransaction />} />
          <Route path="/import" element={<CsvImport />} />
          <Route path="/categories" element={<CategoryManager />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}
