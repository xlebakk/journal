import { z } from "zod";

// Every schema imports z from here, so this runs before any of them is built: zod probes
// `new Function` while building schemas, and the strict CSP (script-src 'self') reports even
// a caught attempt. ESLint forbids importing "zod" anywhere else.
z.config({ jitless: true });

export { z };
