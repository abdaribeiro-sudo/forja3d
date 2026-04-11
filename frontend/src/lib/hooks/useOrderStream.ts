"use client";

import { useEffect, useRef, useState } from "react";

import { Order, getOrder, orderStreamUrl } from "../api";

const POLL_FALLBACK_MS = 5000;

export function useOrderStream(id: string | null) {
  const [order, setOrder] = useState<Order | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const esRef = useRef<EventSource | null>(null);
  const pollRef = useRef<number | null>(null);

  useEffect(() => {
    if (!id) return;

    const startPolling = () => {
      const poll = async () => {
        const res = await getOrder(id);
        if (res.success && res.data) {
          setOrder((prev) => ({ ...prev, ...res.data }) as Order);
        }
      };
      poll();
      pollRef.current = window.setInterval(poll, POLL_FALLBACK_MS);
    };

    // Try SSE
    try {
      const es = new EventSource(orderStreamUrl(id));
      esRef.current = es;

      es.addEventListener("snapshot", (e) => {
        const data = JSON.parse((e as MessageEvent).data);
        setOrder(data);
        setConnected(true);
      });

      es.addEventListener("update", (e) => {
        const data = JSON.parse((e as MessageEvent).data);
        setOrder((prev) => (prev ? { ...prev, ...data } : data));
      });

      es.addEventListener("closed", () => {
        es.close();
        esRef.current = null;
      });

      es.onerror = () => {
        setConnected(false);
        if (esRef.current) {
          esRef.current.close();
          esRef.current = null;
        }
        startPolling();
      };
    } catch (err) {
      setError(err as Error);
      startPolling();
    }

    return () => {
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
      if (pollRef.current) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [id]);

  return { order, connected, error };
}
