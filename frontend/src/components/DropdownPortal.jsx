// src/components/DropdownPortal.jsx
import { createPortal } from 'react-dom';

const DropdownPortal = ({ children, isOpen }) => {
  if (!isOpen) return null;
  
  return createPortal(
    <div className="fixed inset-0 z-[99999] pointer-events-none">
      <div className="pointer-events-auto">
        {children}
      </div>
    </div>,
    document.body
  );
};

export default DropdownPortal;