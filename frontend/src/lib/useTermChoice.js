import { useEffect, useState } from "react";
import * as api from "../api/client";

const KEY = "tt_term";

/** Loads terms once and remembers the chosen one between screens. */
export function useTermChoice() {
  const [terms, setTerms] = useState([]);
  const [termId, setTermIdState] = useState(() => localStorage.getItem(KEY) || "");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getTerms()
      .then((list) => {
        setTerms(list);
        setTermIdState((current) =>
          list.some((t) => String(t.id) === current) ? current : list.length ? String(list[list.length - 1].id) : "");
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const setTermId = (id) => {
    localStorage.setItem(KEY, id);
    setTermIdState(id);
  };
  return { terms, termId, setTermId, error, loading };
}
