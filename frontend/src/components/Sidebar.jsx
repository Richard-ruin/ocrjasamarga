import { Link, useLocation } from "react-router-dom";

const Sidebar = () => {
  const location = useLocation();

  const menuItems = [
    {
      path: "/dashboard",
      name: "Dashboard",
      icon: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2H5a2 2 0 00-2-2z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 5a2 2 0 012-2h4a2 2 0 012 2v6H8V5z" />
        </svg>
      )
    },
    {
      path: "/history",
      name: "History",
      icon: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      )
    }
  ];

  return (
    <aside className="bg-white w-72 min-h-screen shadow-xl border-r border-gray-200">
      <div className="p-6">
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-gray-800 mb-2">Navigation</h2>
          <div className="w-12 h-1 bg-gradient-to-r from-blue-500 to-blue-600 rounded-full"></div>
        </div>
        
        <nav className="space-y-2">
          {menuItems.map((item) => {
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center space-x-3 px-4 py-3 rounded-xl transition-all duration-200 group ${
                  isActive
                    ? "bg-gradient-to-r from-blue-500 to-blue-600 text-white shadow-lg shadow-blue-500/25"
                    : "text-gray-600 hover:bg-gray-50 hover:text-blue-600"
                }`}
              >
                <div className={`${isActive ? "text-white" : "text-gray-400 group-hover:text-blue-500"}`}>
                  {item.icon}
                </div>
                <span className="font-medium">{item.name}</span>
                {isActive && (
                  <div className="ml-auto w-2 h-2 bg-white rounded-full"></div>
                )}
              </Link>
            );
          })}
        </nav>
      </div>
      
      
    </aside>
  );
};

export default Sidebar;