import { createContext, useCallback, useContext, useMemo, useState } from "react";

export interface ToastItem {
  id: string;
  title: string;
  variant: "success" | "error" | "info";
}

interface ToastContextValue {
  pushToast: (title: string, variant?: ToastItem["variant"]) => void;
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

export function FeedbackLoading({ message = "Processing request..." }: { message?: string }) {
  return <div className="rounded-xl border border-blue-100 bg-blue-50 p-3 text-sm text-blue-800">{message}</div>;
}

export function FeedbackEmpty({ message }: { message: string }) {
  return <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">{message}</div>;
}

export function FeedbackError({
  message,
  code,
  onRetry,
}: {
  message: string;
  code?: string;
  onRetry?: () => void;
}) {
  return (
    <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
      <div>{message}</div>
      {code ? <div className="mt-1 text-xs text-rose-700">{code}</div> : null}
      {onRetry ? (
        <button
          type="button"
          className="mt-2 rounded-xl border border-rose-200 bg-white px-3 py-1.5 text-xs font-semibold text-rose-700"
          onClick={onRetry}
        >
          Retry
        </button>
      ) : null}
    </div>
  );
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const pushToast = useCallback((title: string, variant: ToastItem["variant"] = "info") => {
    const id = crypto.randomUUID();
    setToasts((prev) => [...prev, { id, title, variant }]);
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((toast) => toast.id !== id));
    }, 3000);
  }, []);

  const value = useMemo(() => ({ pushToast }), [pushToast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-50 space-y-2">
        {toasts.map((toast) => {
          const tone =
            toast.variant === "success"
              ? "border-emerald-200 bg-emerald-50 text-emerald-800"
              : toast.variant === "error"
                ? "border-rose-200 bg-rose-50 text-rose-800"
                : "border-blue-200 bg-blue-50 text-blue-800";
          return (
            <div key={toast.id} className={`pointer-events-auto rounded-lg border px-3 py-2 text-sm shadow ${tone}`}>
              {toast.title}
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useFeedback() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useFeedback must be used inside ToastProvider");
  }
  return context;
}
