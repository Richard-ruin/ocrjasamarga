import { Link } from "react-router-dom";

const Sidebar = () => {
  return (
    <aside className="bg-gray-100 w-64 min-h-screen p-4 shadow">
      <nav className="flex flex-col gap-4">
        <Link to="/dashboard" className="hover:text-blue-600">Dashboard</Link>
        <Link to="/history" className="hover:text-blue-600">History</Link>
      </nav>
    </aside>
  );
};

export default Sidebar;
