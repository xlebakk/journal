import * as RadixDialog from "@radix-ui/react-dialog";
import { useEffect, type ReactNode } from "react";

import styles from "./Dialog.module.css";

type DialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children: ReactNode;
};

let openDialogs = 0;

/**
 * The page behind a dialog does not scroll. Radix tries to do this with an injected <style>,
 * which the CSP (style-src 'self') blocks; a class from our own stylesheet is allowed.
 */
function useScrollLock(active: boolean) {
  useEffect(() => {
    if (!active) return;
    openDialogs += 1;
    document.documentElement.classList.add("dialog-open");
    return () => {
      openDialogs -= 1;
      if (openDialogs === 0) document.documentElement.classList.remove("dialog-open");
    };
  }, [active]);
}

/** Modal with the hard ink shadow — one of the two places it is allowed (SPEC §12). */
export function Dialog({ open, onOpenChange, title, description, children }: DialogProps) {
  useScrollLock(open);
  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className={styles.overlay} />
        <RadixDialog.Content
          className={styles.content}
          aria-describedby={description ? undefined : undefined}
        >
          <RadixDialog.Title className={styles.title}>{title}</RadixDialog.Title>
          {description ? (
            <RadixDialog.Description className={styles.description}>
              {description}
            </RadixDialog.Description>
          ) : (
            <RadixDialog.Description className="visually-hidden">{title}</RadixDialog.Description>
          )}
          {children}
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}

export function DialogActions({ children }: { children: ReactNode }) {
  return <div className={styles.actions}>{children}</div>;
}
