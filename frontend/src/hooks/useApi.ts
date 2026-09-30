import { useCallback, useEffect, useRef, useState } from 'react';

export function errMessage(e: unknown): string {
  if (e instanceof Error) return e.message;
  return String(e);
}

export interface ApiState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

/** Load-on-mount (and on dep change) helper with loading/error state. */
export function useApi<T>(loader: () => Promise<T>, deps: unknown[] = []): ApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    loaderRef
      .current()
      .then((d) => {
        if (!cancelled) {
          setData(d);
          setLoading(false);
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setError(errMessage(e));
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
    // deps intentionally spread; loader is read from a ref
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nonce, ...deps]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  return { data, loading, error, reload };
}

export interface ActionState<TResult> {
  loading: boolean;
  error: string | null;
  /** Last successful result of `run`, or null. */
  result: TResult | null;
}

/** Button-triggered async action helper with loading/error/result state. */
export function useAsyncAction<TArgs extends unknown[], TResult>(
  fn: (...args: TArgs) => Promise<TResult>,
): { run: (...args: TArgs) => Promise<TResult | null> } & ActionState<TResult> {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<TResult | null>(null);

  const run = useCallback(
    async (...args: TArgs): Promise<TResult | null> => {
      setLoading(true);
      setError(null);
      try {
        const r = await fn(...args);
        setResult(r);
        setLoading(false);
        return r;
      } catch (e: unknown) {
        setError(errMessage(e));
        setLoading(false);
        return null;
      }
    },
    [fn],
  );

  return { run, loading, error, result };
}
