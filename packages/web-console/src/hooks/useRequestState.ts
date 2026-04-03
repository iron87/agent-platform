import { useCallback, useState } from "react";
import type { ApiErrorView, RequestState } from "../lib/types";

export function useRequestState<TData = unknown>() {
  const [state, setState] = useState<RequestState<TData>>({
    loading: false,
    data: null,
    error: null,
  });

  const run = useCallback(async (request: () => Promise<TData>) => {
    setState({ loading: true, data: null, error: null });
    try {
      const data = await request();
      setState({ loading: false, data, error: null });
      return data;
    } catch (error) {
      const normalized = (error as ApiErrorView) ?? {
        code: "UNKNOWN",
        message: "Unexpected error",
      };
      setState({ loading: false, data: null, error: normalized });
      throw normalized;
    }
  }, []);

  return { state, run };
}
