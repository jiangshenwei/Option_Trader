import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { api } from "../api/client";

import type { TradeLeg } from "../types";



interface TradeContextValue {

  tradeList: TradeLeg[];

  loading: boolean;

  toggleCell: (meta: Omit<TradeLeg, "direction" | "quoteType" | "qty">) => void;

  updateLeg: (idx: number, patch: Partial<TradeLeg>) => void;

  removeLeg: (idx: number) => void;

  getCellState: (key: string) => "long" | "short" | null;

}



const TradeContext = createContext<TradeContextValue | null>(null);



export function TradeProvider({ children }: { children: ReactNode }) {

  const [tradeList, setTradeList] = useState<TradeLeg[]>([]);

  const [loading, setLoading] = useState(true);



  useEffect(() => {

    api.getTrades()

      .then(setTradeList)

      .catch(() => setTradeList([]))

      .finally(() => setLoading(false));

  }, []);



  const getCellState = useCallback(

    (key: string) => tradeList.find((t) => t.key === key)?.direction ?? null,

    [tradeList]

  );



  const toggleCell = useCallback((meta: Omit<TradeLeg, "direction" | "quoteType" | "qty">) => {

    api.toggleTrade(meta)

      .then(setTradeList)

      .catch(() => undefined);

  }, []);



  const updateLeg = useCallback((idx: number, patch: Partial<TradeLeg>) => {
    let legKey: string | undefined;
    setTradeList((prev) => {
      legKey = prev[idx]?.key;
      if (!legKey) return prev;
      return prev.map((leg, i) => (i === idx ? { ...leg, ...patch } : leg));
    });
    if (!legKey) return;
    api.patchTrade(legKey, patch)
      .then(setTradeList)
      .catch(() => {
        api.getTrades().then(setTradeList).catch(() => undefined);
      });
  }, []);



  const removeLeg = useCallback((idx: number) => {

    const key = tradeList[idx]?.key;

    if (!key) return;

    api.deleteTrade(key)

      .then(setTradeList)

      .catch(() => undefined);

  }, [tradeList]);



  const value = useMemo(

    () => ({ tradeList, loading, toggleCell, updateLeg, removeLeg, getCellState }),

    [tradeList, loading, toggleCell, updateLeg, removeLeg, getCellState]

  );



  return <TradeContext.Provider value={value}>{children}</TradeContext.Provider>;

}



export function useTrade() {

  const ctx = useContext(TradeContext);

  if (!ctx) throw new Error("useTrade must be used within TradeProvider");

  return ctx;

}


