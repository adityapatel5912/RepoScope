import toast, { Toaster, ToastBar } from "react-hot-toast";
import { X } from "lucide-react";

export { toast };

export default function Toasts() {
  return (
    <Toaster
      position="top-right"
      gutter={8}
      toastOptions={{
        duration: 3000,
        style: {
          background: "#FFFFFF",
          color: "#1A1A1A",
          border: "1px solid #EAE7DC",
          borderRadius: "12px",
          fontSize: "13px",
          maxWidth: "380px",
          padding: "12px 16px",
          boxShadow: "0 12px 32px rgba(26,26,26,0.10)",
        },
        error: {
          style: { borderLeft: "4px solid #DC2626" },
          duration: 7000,
        },
        success: {
          style: { borderLeft: "4px solid #10B981" },
        },
      }}
    >
      {(t) => (
        <ToastBar toast={t}>
          {({ icon, message }) => (
            <div style={{ display: "flex", alignItems: "center", gap: 8, width: "100%" }}>
              {icon}
              <span style={{ flex: 1 }}>{message}</span>
              {t.type !== "loading" && (
                <button
                  onClick={() => toast.dismiss(t.id)}
                  aria-label="Dismiss notification"
                  style={{
                    background: "none",
                    border: "none",
                    color: "#8B8B7E",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    padding: "2px",
                    borderRadius: "4px",
                  }}
                >
                  <X size={14} />
                </button>
              )}
            </div>
          )}
        </ToastBar>
      )}
    </Toaster>
  );
}
