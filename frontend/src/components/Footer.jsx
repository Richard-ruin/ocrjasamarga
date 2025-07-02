const Footer = () => {
  return (
    <footer className="bg-white border-t border-gray-200 px-6 py-4">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <p className="text-sm text-gray-600">
            &copy; 2025 <span className="font-semibold text-gray-800">OCR Jasa Marga</span>
          </p>
          <div className="w-1 h-1 bg-gray-400 rounded-full"></div>
          <p className="text-sm text-gray-500">All rights reserved</p>
        </div>
        
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-1">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
            <span className="text-xs text-gray-500">System Online</span>
          </div>
          <p className="text-xs text-gray-400">v1.0.0</p>
        </div>
      </div>
    </footer>
  );
};

export default Footer;