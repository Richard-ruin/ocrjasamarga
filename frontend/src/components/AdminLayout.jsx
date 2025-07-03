import Header from "./Header";
import Sidebar from "./Sidebar";
import Footer from "./Footer";

const AdminLayout = ({ children }) => {
  return (
    <div className="flex flex-col min-h-screen bg-gray-50 relative">
      {/* Header dengan z-index tinggi */}
      <div className="relative z-50">
        <Header />
      </div>
      
      <div className="flex flex-1 relative">
        {/* Sidebar dengan z-index sedang */}
        <div className="relative z-40">
          <Sidebar />
        </div>
        
        {/* Main content dengan z-index rendah */}
        <main className="flex-1 p-8 bg-gradient-to-br from-gray-50 to-gray-100 min-h-screen relative z-10">
          <div className="max-w-7xl mx-auto">
            {children}
          </div>
        </main>
      </div>
      
      <Footer />
    </div>
  );
};

export default AdminLayout;