import { z } from "zod";

// Imported first by main.tsx: schemas are built while modules load, and zod probes
// `new Function` at that moment. The strict CSP (script-src 'self') reports even a caught
// attempt, so the probe is switched off before any schema exists.
z.config({ jitless: true });
